# Zulip forwarder Telegram bot

A stupid Telegram bot that can forward text messages (for now) from a Telegram group to a Zulip stream. It's still a **very rough** experimental integration, but for simple text messages it gets the job done.

It also handles replies by forwarding to Zulip a message of this format:

> *Original author (HH:MM):*
> Original message

*Replying author:*
Reply message

---

Look into `config.sample` to know which parameters are necessary. Telegram bot's token and API key/email of your Zulip bot are compulsory.
