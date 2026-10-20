#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

# Messages to an ntfy server, ntfy.sh or a self-hosted one. The optional access token is a secret:
# it stays in a file and goes only in the Authorization header, so no error raised here carries it.

import json
import urllib.error
import urllib.request

import wazuh_secrets

TOKEN_FILE = "secrets/ntfy.env"
# ntfy turns a longer message into an attachment: the text is cut before, the rest is in the dashboard
LIMIT = 4000
# The finding levels as ntfy priorities: 5 is the urgent one, 3 the default
PRIORITIES = {"critical": 5, "high": 4, "medium": 3, "low": 2, "informational": 1}

# ntfy refuses these the same way until someone fixes the topic, the token or the access rules
LASTING = (400, 401, 403, 404)


class NtfyError(Exception):
    def __init__(self, status, description):
        super().__init__(f"ntfy answered {status}: {description}")
        self.status = status
        self.description = description

    @property
    def lasting(self):
        return self.status in LASTING


def token():
    return wazuh_secrets.read(TOKEN_FILE, "NTFY_TOKEN")


def cut(text):
    if len(text) <= LIMIT:
        return text
    return text[:text.rfind("\n", 0, LIMIT)] + "\n\n… more in the dashboard."


def send(url, access_token, topic, title, text, level="medium", click="", timeout=30):
    """Publish a Markdown text to a topic, with the priority of the level."""
    payload = {"topic": topic, "title": title, "message": cut(text), "markdown": True,
               "priority": PRIORITIES.get(level, 3), "tags": ["rotating_light" if level == "critical" else "shield"]}
    if click:
        payload["click"] = click
    # The topic travels in the body: the base URL is the endpoint that takes JSON messages
    request = urllib.request.Request(url.rstrip("/"), data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
    if access_token:
        request.add_header("Authorization", f"Bearer {access_token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout):
            pass
    except urllib.error.HTTPError as error:
        try:
            body = json.load(error)
        except ValueError:
            body = {}
        raise NtfyError(error.code, body.get("error") or error.reason) from None
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise NtfyError(0, str(getattr(error, "reason", error))) from None
