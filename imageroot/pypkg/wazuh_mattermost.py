#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

# Messages to a Mattermost incoming webhook. The webhook URL is the secret: anybody who knows it
# can post to the channel, so it stays in a file and no error raised here carries it.

import json
import urllib.error
import urllib.request

import wazuh_http
import wazuh_secrets

WEBHOOK_FILE = "secrets/mattermost.env"
# Mattermost splits a post over 16383 characters: the text is cut before, the rest is in the dashboard
LIMIT = 16000
# The finding levels as the left border of the attachment
COLORS = {"critical": "#da1e28", "high": "#ff832b", "medium": "#f1c21b", "low": "#0f62fe", "informational": "#0f62fe"}

# Mattermost refuses these the same way until someone fixes the webhook or the channel
LASTING = (400, 401, 403, 404)


class MattermostError(Exception):
    def __init__(self, status, description):
        super().__init__(f"Mattermost answered {status}: {description}")
        self.status = status
        self.description = description

    @property
    def lasting(self):
        return self.status in LASTING

    @property
    def channel_unknown(self):
        # Every refusal has the same id: only the status tells a missing channel (404) from an unknown
        # webhook or user (400)
        return self.status == 404


def webhook():
    return wazuh_secrets.read(WEBHOOK_FILE, "MATTERMOST_WEBHOOK")


def cut(text):
    if len(text) <= LIMIT:
        return text
    # At the last line break below the limit, or at the limit when one line is longer
    end = text.rfind("\n", 0, LIMIT)
    return text[:end if end > 0 else LIMIT] + "\n\n… more in the dashboard."


def send(url, title, text, level="medium", link="", channel="", username="", timeout=30):
    """Post a Markdown text as an attachment, its border coloured by the level."""
    attachment = {"fallback": title, "title": title, "color": COLORS.get(level, COLORS["medium"]),
                  "text": cut(text)}
    if link:
        attachment["title_link"] = link
    payload = {"attachments": [attachment]}
    # Both are optional: without them the webhook posts to its own channel, under its own name
    if channel:
        payload["channel"] = channel
    if username:
        payload["username"] = username
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
    try:
        wazuh_http.send(request, timeout)
    except urllib.error.HTTPError as error:
        try:
            body = json.load(error)
        except ValueError:
            body = {}
        # Only the error id: the message of Mattermost quotes the webhook, which is the secret
        raise MattermostError(error.code, body.get("id") or error.reason) from None
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise MattermostError(0, str(getattr(error, "reason", error))) from None
