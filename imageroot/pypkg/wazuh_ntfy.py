#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

# Messages to an ntfy server, ntfy.sh or a self-hosted one. The optional access token is a secret:
# it stays in a file and goes only in the Authorization header, so no error raised here carries it.
# It is stored with the server it was given for and goes to that server only: a changed URL drops it.

import json
import os
import urllib.error
import urllib.request

import wazuh_http
import wazuh_secrets

TOKEN_FILE = "secrets/ntfy.env"
# ntfy turns a message over 4096 bytes into an attachment: the text is cut before, the rest is in the dashboard
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


def base_url(url):
    return url.strip().rstrip("/")


def token(url):
    """The stored token if it was stored for this server, else empty."""
    if wazuh_secrets.read(TOKEN_FILE, "NTFY_URL") != base_url(url):
        return ""
    return wazuh_secrets.read(TOKEN_FILE, "NTFY_TOKEN")


def save_token(value, url):
    """Store a token for a server, or remove it when the value is empty."""
    if not value:
        wazuh_secrets.write(TOKEN_FILE, "NTFY_TOKEN", "")
        return
    os.makedirs(os.path.dirname(TOKEN_FILE), mode=0o700, exist_ok=True)
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f"NTFY_TOKEN={value}\nNTFY_URL={base_url(url)}\n")


def cut(text):
    data = text.encode()
    if len(data) <= LIMIT:
        return text
    # ntfy counts bytes: an umlaut takes two. At the last line break below the limit, or at the limit
    # when one line is longer, never inside a character
    head = data[:LIMIT].decode(errors="ignore")
    end = head.rfind("\n")
    return head[:end if end > 0 else len(head)] + "\n\n… more in the dashboard."


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
        wazuh_http.send(request, timeout)
    except urllib.error.HTTPError as error:
        try:
            body = json.load(error)
        except ValueError:
            body = {}
        raise NtfyError(error.code, body.get("error") or error.reason) from None
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise NtfyError(0, str(getattr(error, "reason", error))) from None
