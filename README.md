# Zulip forwarder Telegram bot

A simple Telegram bot that can forward messages from a Telegram group to a Zulip stream. The bot must be given the permission to access the messages of the group (you can turn this option on/off with the `/setprivacy` command sent to the [BotFather](https://t.me/BotFather)).

Currently, it supports:

1. Text-only messages, including replies

2. Messages with attachments:
    - Photo
    - Audio
    - Voice message
    - Video
    - Document (i.e., generic file)

3. @-mentions (i.e., a user mentioned in Telegram will be mentioned in the message forwarded to Zulip. This feature **requires** a JSON file mapping Telegram with Zulip's usernames)

4. Message editing as long as the edit occurs no later than 60 minutes after the message has been sent on Telegram

At present, **the attachments are not uploaded to Zulip's storage** but are directly linked with an URL from Telegram API. This might be a security issue if your Zulip workspace is open to anyone since the link to the attachment retrieved by the bot exposes the bot's token.

### Formatting

When forwarding a reply, the message sent to Zulip will follow this format:

```
> *Original author (HH:MM):*
> Original message

*Replying author:*
Reply message
```

Markdown syntax will be rendered automatically by Zulip. If the original message's date differs from that of the reply, the timestamp will include the date for an easier reference.

### `config` file

Look into `config.sample` to know which parameters are necessary. Telegram bot's token and API key/email of your Zulip bot are compulsory.

Specifying paths with string interpolation, might be a more robust solution to avoid `FileNotFound` errors. For example, you can define a `[paths]` section in your `config` file and then specify the database path as `db_path = %(custom_dir)s/%(db_name)s`.

```
[paths]
my_dir = /home

[db]
db_name = data.db
db_path = %(my_dir)s/%(db_name)s
```

### Usernames mapping

The JSON file should be as simple as

```json
{ 
    "telegram_user_1": "zulip_user_1",
    "...": "***"
}
```

**Note:** if a user has a Telegram @-username, the bot will receive a mention **without** `first_name` or `last_name`. For these users, you should add their @-usernames as their keys in the JSON file.

The path to this file can be specified in the `config` in the `[zulip]` section as `zulip_users`. The default is `zulip_users.json` in the current working directory.

### TODO

- [ ] Add a customizable format for replies
- [ ] Add a customizable time-interval for message editing
- [ ] Add the possibility to download a file from Telegram and upload it to Zulip's server (partially implemented)
