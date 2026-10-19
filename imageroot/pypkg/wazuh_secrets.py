#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

# Tokens never go through agent.set_env(), which writes to Redis in plain text: each stays in its own file

import os


def read(path, key):
    try:
        with open(path) as f:
            for line in f:
                if line.startswith(f"{key}="):
                    return line.rstrip("\n").split("=", 1)[1]
    except FileNotFoundError:
        pass
    return ""


def write(path, key, value):
    """Store a token, or remove its file when the value is empty."""
    if value:
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(f"{key}={value}\n")
    elif os.path.exists(path):
        os.remove(path)
