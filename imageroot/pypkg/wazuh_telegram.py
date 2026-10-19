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


def call(bot_token, method, payload):
    """Call a method of the Bot API and return its result."""
    request = urllib.request.Request(f"https://api.telegram.org/bot{bot_token}/{method}",
                                     data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as answer:
            return json.load(answer).get("result")
    except urllib.error.HTTPError as error:
        try:
            description = json.load(error).get("description", "")
        except ValueError:
            description = ""
        raise TelegramError(error.code, description or error.reason) from None
    except (urllib.error.URLError, OSError, ValueError) as error:
        reason = getattr(error, "reason", error)
        raise TelegramError(0, str(reason).replace(bot_token, "***")) from None


def send(bot_token, chat_id, text):
    """Send an HTML text, in several messages when it is too long."""
    for part in chunks(text):
        call(bot_token, "sendMessage", {"chat_id": chat_id, "text": part, "parse_mode": "HTML",
                                        "disable_web_page_preview": True})


def recent_chats(bot_token):
    """The chats the bot heard from lately, newest first: Telegram keeps the updates a day."""
    chats = {}
    # Without an offset nothing is marked as read: the next call sees the same chats again
    for update in call(bot_token, "getUpdates", {"allowed_updates": ["message", "channel_post", "my_chat_member"]}):
        for kind in ("message", "edited_message", "channel_post", "my_chat_member", "chat_member"):
            chat = update.get(kind, {}).get("chat")
            if chat:
                name = chat.get("title") or " ".join(p for p in (chat.get("first_name"), chat.get("last_name")) if p)
                # Moved to the end: the last update of a chat gives its place in the list
                chats.pop(chat["id"], None)
                chats[chat["id"]] = {"id": str(chat["id"]), "title": name or chat.get("username", ""),
                                     "type": chat.get("type", "")}
    return list(reversed(chats.values()))
