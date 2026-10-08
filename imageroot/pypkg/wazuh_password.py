#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""The password rules of Wazuh: the indexer and the credentials tools refuse anything else."""

import re

ALLOWED = re.compile(r"^[A-Za-z0-9.,_+:@%^=~-]+$")


def password_error(value):
    """Return the name of the broken rule, or None when the password is accepted."""
    if not 12 <= len(value) <= 64:
        return "password_length"
    if not ALLOWED.match(value):
        return "password_characters"
    for pattern in ("[A-Z]", "[a-z]", "[0-9]", "[.,_+:@%^=~-]"):
        if not re.search(pattern, value):
            return "password_classes"
    return None
