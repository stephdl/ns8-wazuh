#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

# Messages to a Nextcloud Talk conversation through a bot. The bot and its shared secret are
# installed by the Nextcloud admin (occ talk:bot:install). The secret stays in a file and only
# signs the request: it never travels, so no error raised here carries it.

import hashlib
import hmac
import json
import secrets
import urllib.error
import urllib.request

import wazuh_secrets

SECRET_FILE = "secrets/talk.env"
# Talk refuses messages over 32000 characters: the text is cut before, the rest is in the dashboard
LIMIT = 31000
# The finding levels as the first character of the message
PREFIXES = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "informational": "🔵"}

# Talk refuses these the same way until someone fixes the secret, the bot setup or the conversation
LASTING = (400, 401, 403, 404, 413)


class TalkError(Exception):
    def __init__(self, status, description):
        super().__init__(f"Nextcloud Talk answered {status}: {description}")
        self.status = status
        self.description = description

    @property
    def lasting(self):
        return self.status in LASTING


def secret():
    return wazuh_secrets.read(SECRET_FILE, "TALK_SECRET")


def cut(text):
    if len(text) <= LIMIT:
        return text
    return text[:text.rfind("\n", 0, LIMIT)] + "\n\n… more in the dashboard."


def send(url, conversation, bot_secret, title, text, level="medium", timeout=30):
    """Post a Markdown text to a conversation, signed with the secret of the bot."""
    message = f"{PREFIXES.get(level, PREFIXES['medium'])} **{title}**\n\n{cut(text)}"
    # Talk checks HMAC-SHA256(secret, random + message): the message only, not the whole body
    random = secrets.token_hex(32)
    signature = hmac.new(bot_secret.encode(), (random + message).encode(), hashlib.sha256).hexdigest()
    # The same summary sent again after a failure keeps its reference, so it can be found in the chat
    reference = hashlib.sha256(message.encode()).hexdigest()
    request = urllib.request.Request(f"{url.rstrip('/')}/ocs/v2.php/apps/spreed/api/v1/bot/{conversation}/message",
                                     data=json.dumps({"message": message, "referenceId": reference}).encode(),
                                     method="POST",
                                     headers={"Content-Type": "application/json", "Accept": "application/json",
                                              "OCS-APIRequest": "true", "X-Nextcloud-Talk-Bot-Random": random,
                                              "X-Nextcloud-Talk-Bot-Signature": signature})
    try:
        with urllib.request.urlopen(request, timeout=timeout):
            pass
    except urllib.error.HTTPError as error:
        try:
            body = json.load(error).get("ocs", {}).get("meta", {}).get("message", "")
        except (ValueError, AttributeError):
            body = ""
        raise TalkError(error.code, body or error.reason) from None
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise TalkError(0, str(getattr(error, "reason", error))) from None
