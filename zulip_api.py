#!/usr/bin/env python

import logging
import zulip
from pprint import pprint
from typing import Dict

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG
)

logger = logging.getLogger(__name__)

# Zulip client
client = zulip.Client(config_file='~/.zuliprc')

def send_message(message: str) -> Dict:
    request = {
    "type": "stream",
    "to": "From Telegram",
    "topic": "Test",
    "content": message,
    }

    return client.send_message(request)

def main() -> None:
    message = input("Message text: ")
    result = send_message(message)
    pprint(result)

if __name__ == "__main__":
    main()