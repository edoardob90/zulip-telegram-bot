#!/usr/bin/env python
# pylint: disable=C0116
# This program is dedicated to the public domain under the CC0 license.

"""
Simple Bot to reply to Telegram messages.
First, a few handler functions are defined. Then, those functions are passed to
the Dispatcher and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.
Usage:
Basic Echobot example, repeats messages.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import os
import sys
import logging
import datetime
from json import load
from typing import Any, Union, List, IO, Text, Dict, Optional
from dateutil import tz
from configparser import ConfigParser
from argparse import ArgumentParser

from telegram import Update, ForceReply, File, Message, MessageEntity
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

import zulip

# Log an event and save it in a file with current date as name if enabled
def log(severity, msg):
    # Check if logging is enabled
    if log_level == 0:
        return

    # Add file handler to logger if enabled
    # TODO: this if-block can be removed. Logging to disk is managed by supervisor
    if config["log"].getboolean("log_to_file"):
        now = datetime.datetime.now(tz=local_tz).strftime(date_format)

        # If current date not the same as initial one, create new FileHandler
        if str(now) != str(date):
            # Remove old handlers
            for hdlr in logger.handlers[:]:
                logger.removeHandler(hdlr)

            new_hdlr = logging.FileHandler(logfile_path, encoding="utf-8")
            new_hdlr.setLevel(log_level)

            # Format file handler
            new_hdlr.setFormatter(formatter)

            # Add file handler to logger
            logger.addHandler(new_hdlr)

    # The actual logging
    logger.log(severity, msg)

################################################################################################################
# Zulip
################################################################################################################

def build_request(stream: Text,
                topic: Union[Text, datetime.datetime],
                content: List[Message],
                attachment_url: Optional[Text] = None,
                mentions: Optional[List] = None) -> Dict:
    """Construct the request dict to send to Zulip"""

    # Message timestamp
    date = content[0].date.astimezone(local_tz)

    request = {
        "type": "stream",
        "to": stream,
        "topic": date.strftime(date_fmt) if date_as_topic else topic,
        "content": ""
    }

    # If there are mentions, they should be prepended to the message content
    if mentions:
        mentioned_users = " ".join(mentions)
        request['content'] += f"{mentioned_users} "

    # Check if content represents a message with a reply
    if content[1] is None:
        # content = simple message, no attachments
        if content[0].caption:
            text = content[0].caption
        elif content[0].text:
            text = content[0].text
        else:
            text = ""
        request['content'] += f"*{content[0].from_user.first_name}:*\n{text}"
    else:
        # content = reply message + original message 
        # Check if original message and reply have the same date
        # If not, include the date in the quoted reply
        reply_date = content[1].date.astimezone(local_tz)
        reply_date_print = reply_date.strftime(time_fmt) if (reply_date.strftime(date_fmt) == date.strftime(date_fmt)) else reply_date.strftime(f"{date_fmt}, {time_fmt}")

        text, original_text = [x if x is not None else "" for x in [c.caption if c.caption else c.text for c in content]]

        request['content'] += f"> *{content[0].from_user.first_name} wrote ({reply_date_print}):*\n> {original_text}\n\n*{content[0].from_user.first_name}:*\n{text}"

    # Append a link to the attached file to the message being forwarded
    if attachment_url is not None:
        request['content'] += f"\n[Link to file]({attachment_url})" 

    return request

def submit_request(request: Dict) -> None:
    """Submit the request & check the response JSON"""
    if not request:
        log(logging.ERROR, "Empty request to Zulip API ignored")
        return
    result = zulip_client.send_message(request)
    if result['result'] != 'success':
        log(logging.ERROR, f"Zulip API returned an error: {result['code']} - {result['msg']}")

################################################################################################################
# Telegram bot
################################################################################################################

# Define a few command handlers. These usually take the two arguments update and
# context.
def start(update: Update, _: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    update.message.reply_markdown_v2(
        fr'Hi {user.mention_markdown_v2()}\!',
        reply_markup=ForceReply(selective=True),
    )

def help_command(update: Update, _: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    update.message.reply_text('Help!')

def download_file(file: File) -> Text:
    """Request the download of a file"""
    file_path = os.path.join(downloads_dir, file.file_unique_id)
    with open(file_path, 'wb') as out:
        file.download(custom_path=None, out=out)
    return file_path

def process_message(update: Update, context: CallbackContext) -> None:
    """Process an update message: text-only or with a media (photo, video, document, audio)"""
    message = update.effective_message
    user = message.from_user

    # Is the message a reply?
    original_msg = update.message.reply_to_message if message.reply_to_message else None

    # Does the message contain a @mention (or more than one)?
    mentioned_users = []
    if message.entities and users_mapping:
        for entity in message.entities:
            if entity.type == 'TEXT_MENTION':
                mentioned_users.append(f"@_**{users_mapping[entity.user.first_name]}**")

    if message.text:
        # text-only message
        request = build_request(
            stream = stream,
            topic = topic,
            content = [message, original_msg],
            attachment_url = None,
            mentions = mentioned_users)
        
        submit_request(request)

    else:
        # the message has some content: photo, generic file, video, or audio are supported
        if message.photo:
            file_id = message.photo[-1].file_id
        elif message.document:
            file_id = message.document.file_id
        elif message.video:
            file_id = message.video.file_id
        elif message.video_note:
            file_id = message.video_note.file_id
        elif message.audio:
            file_id = message.audio.file_id
        elif message.voice:
            file_id = message.voice.file_id
        else:
            file_id = None
            log(logging.WARNING, f"User {user} sent a message with an unsupported content")
            text = f"Sorry {user.first_name}, I cannot forward a message with this content to Zulip 😞"
            message.reply_text(text=text, quote=True, disable_notification=True)
        
        # Download the file and build a request with the file attached
        if file_id is not None:
            file_path = (context.bot.get_file(file_id)).file_path 
            request = build_request(stream = stream,
                topic = topic,
                content = [message, original_msg],
                attachment_url = file_path,
                mentions = mentioned_users)
            
            submit_request(request)
    

################################################################################################################
# Main                                                                  
################################################################################################################

# Argument parser
ap = ArgumentParser()
ap.add_argument('-c', '--config', default='', help="Path to config file. Default is $PWD/config")
ap.add_argument('-u', '--users', default='', help="Path to JSON file containing a mapping between Telegram users' first names and Zulip usernames")
args = vars(ap.parse_args())

# If no config file is supplied, look into PWD
if not args['config']:
    if not os.path.isfile(os.path.join(os.getcwd(), 'config')):
        exit(f"No configuration file in {os.getcwd()}!")
    else:
        config_file = os.path.abspath(os.path.join(os.getcwd(), 'config'))
elif os.path.isfile(args['config']):
    config_file = os.path.abspath(args['config'])
else:
    exit(f"Configuration file {args['config']} doesn't exist!")

# Check config.sample to know which parameters the config must/can contain
config = ConfigParser()
# Read configuration
with open(config_file) as config_fp:
    config.read_file(config_fp)

# Local time-zone. Use 'Europe/Zurich'
local_tz = tz.gettz("Europe/Zurich")

# Date & time formats for printing
date_fmt = "%d %B %Y"
time_fmt = "%H:%M"

# Set up logging
formatter_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
date_format = "%Y-%m-%d"
date_log_format = "%Y-%m-%d %H:%M"
log_level = int(config["log"]["log_level"])

# Enable logging
logging.basicConfig(format=formatter_str, level=log_level, datefmt=date_log_format)
logger = logging.getLogger(__name__)

# Current timestamp for logging
date = datetime.datetime.now(tz=local_tz).strftime(date_format)

# Add a file handler to the logger if enabled
# TODO: all this stuff can be removed as the bot is managed by supervisor which manages logging to disk
if config["log"].getboolean("log_to_file"):
    # Where to put log files
    if config["log"]["log_dir"] != '':
        log_dir = os.path.abspath(config["log"]["log_dir"])
    else:
        log_dir = os.path.abspath(os.path.join(os.getcwd(), "logs"))
    
    # If log directory doesn't exist, create it
    try:
        os.makedirs(log_dir)
    except (FileExistsError, PermissionError):
        log(logging.ERROR, f"Directory {log_dir} already exists! Or some 'PermissionError' occurred")

    # Create a file handler for logging
    logfile_path = os.path.join(log_dir, date + ".log")
    handler = logging.FileHandler(logfile_path, encoding="utf-8")
    handler.setLevel(log_level)

    # Format file handler
    formatter = logging.Formatter(formatter_str)
    handler.setFormatter(formatter)

    # Add file handler to logger
    logger.addHandler(handler)

    # Redirect all uncaught exceptions to logfile
    sys.stderr = open(logfile_path, "w")

# Set up Zulip API
api_key, email, site = config["zulip"]["key"], config["zulip"]["email"], config["zulip"]["site"]
if None in (api_key, email):
    msg = "Zulip API: 'api_key' and 'email' are required"
    log(logging.ERROR, msg)
    exit(msg)
else:
    zulip_client = zulip.Client(api_key=api_key, email=email, site=site)

# Get stream & topic where to forward the message
stream = config['zulip']['stream']
topic = config['zulip']['to']
# If 'topic' empty, the topic will be the current date formatted as dd-MM-YYYY
date_as_topic = True if not topic else False

# Create the directory where to download files requested to Telegram
# Downloads dir is by default in $PWD/telegram_downloads
# TODO: implement something to purge this folder when the bot stops or restarts
downloads_dir = os.path.join(os.getcwd(), 'telegram_downloads')
try:
    os.makedirs(downloads_dir)
except (FileExistsError, PermissionError):
    log(logging.ERROR, f"Directory {downloads_dir} exists!")

# Check if a Telegram-Zulip username mappings has been supplied
users_mapping = {}
if args['users']:
    users_fpath = os.path.abspath(args['users'])
    try:
        with open(users_fpath, 'r') as fp:
            users_mapping = load(fp)
    except FileNotFoundError:
        log(logging.ERROR, f"Users mapping file {users_fpath} not found!")
        raise
    
# Create the Updater and pass it your bot's token.
updater = Updater(config["telegram"]['bot_token'])

# Get the dispatcher to register handlers
dispatcher = updater.dispatcher

# on different commands - answer in Telegram
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_command))

# on non command i.e message - echo the message on Telegram
dispatcher.add_handler(MessageHandler(Filters.all & ~Filters.command, process_message))

# Start the Bot
updater.start_polling()

# Run the bot until you press Ctrl-C or the process receives SIGINT,
# SIGTERM or SIGABRT. This should be used most of the time, since
# start_polling() is non-blocking and will stop the bot gracefully.
updater.idle()