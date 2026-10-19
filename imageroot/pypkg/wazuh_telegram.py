#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

# Messages to Telegram through one bot per instance. Its token is a secret: it stays in a file,
# and it is part of the request URL, so no error raised here may carry that URL.

import html
import json
import time
import urllib.error
import urllib.request

import wazuh_secrets

TOKEN_FILE = "secrets/telegram.env"
# Telegram refuses a longer text: the message is cut at line breaks below it
LIMIT = 4096
# A group takes about 20 messages a minute: past this, the rest is left to the dashboard
MAX_PARTS = 5
# Longer waits are not worth holding the run for: the next one retries
MAX_RETRY_AFTER = 30


# Telegram refuses these the same way until someone fixes the chat or the token
LASTING = (400, 401, 403, 404)


class TelegramError(Exception):
    def __init__(self, status, description, retry_after=0):
        super().__init__(f"Telegram answered {status}: {description}")
        self.status = status
        self.description = description
        self.retry_after = retry_after

    @property
    def lasting(self):
        return self.status in LASTING


def token():
    return wazuh_secrets.read(TOKEN_FILE, "TELEGRAM_TOKEN")


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


def call(bot_token, method, payload, retried=False, timeout=30):
    """Call a method of the Bot API and return its result. A flood limit is waited out once."""
    try:
        return _call(bot_token, method, payload, timeout)
    except TelegramError as error:
        if error.status != 429 or retried or error.retry_after > MAX_RETRY_AFTER:
            raise
        time.sleep(error.retry_after or 1)
        return call(bot_token, method, payload, True, timeout)


def _call(bot_token, method, payload, timeout):
    request = urllib.request.Request(f"https://api.telegram.org/bot{bot_token}/{method}",
                                     data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as answer:
            return json.load(answer).get("result")
    except urllib.error.HTTPError as error:
        try:
            body = json.load(error)
        except ValueError:
            body = {}
        raise TelegramError(error.code, body.get("description") or error.reason,
                            body.get("parameters", {}).get("retry_after", 0)) from None
    except (urllib.error.URLError, OSError, ValueError) as error:
        reason = getattr(error, "reason", error)
        raise TelegramError(0, str(reason).replace(bot_token, "***")) from None


def send(bot_token, chat_id, text):
    """Send an HTML text, in several messages when it is too long."""
    parts = chunks(text)
    if len(parts) > MAX_PARTS:
        parts = parts[:MAX_PARTS - 1] + ["… more in the dashboard."]
    for part in parts:
        call(bot_token, "sendMessage", {"chat_id": chat_id, "text": part, "parse_mode": "HTML",
                                        "disable_web_page_preview": True})


def describe(chat):
    """The chat as listed: numeric_id lets an @name and its number match."""
    name = chat.get("title") or " ".join(p for p in (chat.get("first_name"), chat.get("last_name")) if p)
    return {"id": str(chat["id"]), "numeric_id": str(chat["id"]), "title": name or chat.get("username", ""),
            "type": chat.get("type", "")}


def known_chat(bot_token, chat_id, quick=False):
    """The chat behind an ID, or None when the bot cannot see it. quick: no wait on a slow Telegram."""
    try:
        chat = call(bot_token, "getChat", {"chat_id": chat_id}, retried=quick, timeout=5 if quick else 30)
        # Under the ID as saved: a public channel stays @name, as the field holds it
        return dict(describe(chat), id=chat_id)
    except TelegramError as error:
        # Only a chat the bot cannot see is an answer: a wrong token or no network must reach the caller
        if error.status in (400, 403):
            return None
        raise


def recent_chats(bot_token):
    """The chats of the updates the bot got, newest first: Telegram keeps the updates a day."""
    chats = {}
    # No offset and no allowed_updates: either would change the bot for another app that reads its updates
    for update in call(bot_token, "getUpdates", {"limit": 100}):
        for kind in ("message", "edited_message", "channel_post", "my_chat_member", "chat_member"):
            chat = update.get(kind, {}).get("chat")
            if chat:
                # Moved to the end: the last update of a chat gives its place in the list
                chats.pop(chat["id"], None)
                chats[chat["id"]] = describe(chat)
    return list(reversed(chats.values()))
