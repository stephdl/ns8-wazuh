#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

# Messages to Telegram through one bot per instance. Its token is a secret: it stays in a file,
# and it is part of the request URL, so no error raised here may carry that URL.

import html
import json
import urllib.error
import urllib.request

TOKEN_FILE = "secrets/telegram.env"
# Telegram refuses a longer text: the message is cut at line breaks below it
LIMIT = 4096


class TelegramError(Exception):
    def __init__(self, status, description):
        super().__init__(f"Telegram answered {status}: {description}")
        self.status = status
        self.description = description


def read_secret(path, key):
    try:
        with open(path) as f:
            for line in f:
                if line.startswith(f"{key}="):
                    return line.rstrip("\n").split("=", 1)[1]
    except FileNotFoundError:
        pass
    return ""


def token():
    return read_secret(TOKEN_FILE, "TELEGRAM_TOKEN")


def escape(text):
    return html.escape(text, quote=False)


def chunks(text):
    parts, current = [], ""
    for line in text.split("\n"):
        # A single line longer than the limit is cut as it is, tags included: none is that long
        while len(line) > LIMIT:
            parts += [current] if current else []
            parts.append(line[:LIMIT])
            current, line = "", line[LIMIT:]
        if current and len(current) + 1 + len(line) > LIMIT:
            parts.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    return parts + ([current] if current.strip() else [])


def send(bot_token, chat_id, text):
    """Send an HTML text, in several messages when it is too long."""
    for part in chunks(text):
        body = json.dumps({"chat_id": chat_id, "text": part, "parse_mode": "HTML",
                           "disable_web_page_preview": True}).encode()
        request = urllib.request.Request(f"https://api.telegram.org/bot{bot_token}/sendMessage", data=body,
                                         method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=30) as answer:
                answer.read()
        except urllib.error.HTTPError as error:
            try:
                description = json.load(error).get("description", "")
            except ValueError:
                description = ""
            raise TelegramError(error.code, description or error.reason) from None
        except (urllib.error.URLError, OSError) as error:
            reason = getattr(error, "reason", error)
            raise TelegramError(0, str(reason).replace(bot_token, "***")) from None
