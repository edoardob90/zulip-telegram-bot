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
from dateutil import tz
from configparser import ConfigParser
from argparse import ArgumentParser

from telegram import Update, ForceReply
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

import zulip

# Argument parser
ap = ArgumentParser()
ap.add_argument('-c', '--config', default='', help="Path to config file. Default is $PWD/config")
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

config = ConfigParser()
# Read configuration
with open(config_file) as config_fp:
    config.read_file(config_fp)


# Local time-zone. Use 'Europe/Zurich'
local_tz = tz.gettz("Europe/Zurich")

# Date & time formats for printing
date_fmt = "%d %B %Y"
time_fmt = "%H:%M"

# Config file should contain:
# 1. Bot Token
# 2. Path to 'zuliprc'
# 3. Path for logging to file (default: zulip_bot_logs)

# Set up logging
formatter_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
date_format = "%Y-%m-%d"
date_log_format = "%Y-%m-%d %HH:%MM"
log_level = int(config["log"]["log_level"])

# Enable logging
logging.basicConfig(
    format=formatter_str, level=log_level
)
logger = logging.getLogger(__name__)

# Current timestamp for logging
date = datetime.datetime.now(tz=local_tz).strftime(date_format)

# Add a file handler to the logger if enabled
if config["log"]["log_to_file"]:
    # Where to put log files
    if config["log"]["log_dir"] != "":
        log_dir = config["log"]["log_dir"]
    else:
        log_dir = "logs"
    
    # If log directory doesn't exist, create it
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

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

# Log an event and save it in a file with current date as name if enabled
def log(severity, msg):
    # Check if logging is enabled
    if log_level == 0:
        return

    # Add file handler to logger if enabled
    if config["log"]["log_to_file"]:
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

# Zulip
# Check the response JSON of the API call
def check_result(result):
    if result['result'] != 'success':
        log(logging.ERROR, f"Zulip API returned an error: {result['code']} - {result['msg']}")

# Get stream & topic where to forward the message
stream = config['zulip']['stream']
topic = config['zulip']['to']
date_as_topic = True if not topic else False


# Telegram bot
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

def forward_text(update: Update, _: CallbackContext) -> None:
    user = update.message.from_user
    date = update.message.date.astimezone(local_tz)

    log(logging.INFO, f"Forwarwding message '{update.message.text}' of user {user} received at {date.strftime(date_log_format)}")
    
    # Build an API request
    request = {
        "type": "stream",
        "to": stream,
        "topic": date.strftime(date_fmt) if date_as_topic else topic,
        "content": f"*{user.first_name}:*\n{update.message.text}"
    }
    
    # Process API request
    result = zulip_client.send_message(request)

    check_result(result)

def forward_reply(update: Update, _: CallbackContext):
    # The replying message
    user = update.message.from_user
    msg = update.message
    date = msg.date.astimezone(local_tz)
    
    # The message being replied to
    reply_msg = update.message.reply_to_message
    reply_to_user = reply_msg.from_user
    reply_date = reply_msg.date.astimezone(local_tz)
    
    # Check if original message and reply have the same date
    # If not, include the date in the quoted reply
    reply_date_print = reply_date.strftime(time_fmt) if (reply_date.strftime(date_fmt) == date.strftime(date_fmt)) else reply_date.strftime(f"{date_fmt}, {time_fmt}")

    log(logging.INFO, f"Reply to {reply_to_user} at {reply_date.strftime(date_log_format)}\nForwarwding message '{msg.text}' of user {user} received at {date.strftime(date_log_format)}")

    # Build the message content for Zulip
    content = f"> *{reply_to_user.first_name} wrote ({reply_date_print}):*\n> {reply_msg.text}\n\n*{user.first_name}:*\n{msg.text}"

    # Build an API request
    request = {
        "type": "stream",
        "to": stream,
        "topic": date.strftime(date_fmt) if date_as_topic else topic,
        "content": content
    }
    
    # Process API request
    result = zulip_client.send_message(request)

    check_result(result)

################################################################################################################

# Set up Zulip API
api_key, email, site = config["zulip"]["key"], config["zulip"]["email"], config["zulip"]["site"]
if None in (api_key, email):
    msg = "Zulip API: 'api_key' and 'email' are required"
    log(logging.ERROR, msg)
    exit(msg)
else:
    zulip_client = zulip.Client(api_key=api_key, email=email, site=site)
    
# Create the Updater and pass it your bot's token.
updater = Updater(config["telegram"]['bot_token'])

# Get the dispatcher to register handlers
dispatcher = updater.dispatcher

# on different commands - answer in Telegram
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("help", help_command))

# on non command i.e message - echo the message on Telegram
dispatcher.add_handler(MessageHandler(~Filters.command & Filters.reply, forward_reply))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, forward_text))

# Start the Bot
updater.start_polling()

# Run the bot until you press Ctrl-C or the process receives SIGINT,
# SIGTERM or SIGABRT. This should be used most of the time, since
# start_polling() is non-blocking and will stop the bot gracefully.
updater.idle()