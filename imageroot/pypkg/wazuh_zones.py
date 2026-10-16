#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

# Settings of each customer: the zones its users may log in from, and who gets its login alerts.
# The zones go to a KVDB that the login zone decoder reads, because a rule never sees the GeoIP fields.

import json
import os

from wazuh_api import api

CUSTOMERS_FILE = os.environ.get("CUSTOMERS_FILE", "customers.json")
CM = "_plugins/_content_manager"
KVDB_TITLE = "ns8-login-zones"
# The continent_code values of GeoIP. A zone "@EU" is a continent: NA or AS alone are countries
CONTINENTS = ("AF", "AN", "AS", "EU", "NA", "OC", "SA")


def load():
    try:
        with open(CUSTOMERS_FILE) as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    data.setdefault("customers", {})
    return data


def save(data):
    tmp = CUSTOMERS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.chmod(tmp, 0o600)
    os.replace(tmp, CUSTOMERS_FILE)


def kvdb_content(data):
    """customer:list marks a customer with zones, customer:FR and customer:@EU are its zones."""
    content = {}
    for name, customer in data["customers"].items():
        zones = customer.get("zones", [])
        if zones:
            content[f"{name}:list"] = True
            content.update({f"{name}:{zone}": True for zone in zones})
    # The Content Manager refuses an empty KVDB
    return content or {"none:list": False}


def _draft_id(index, title):
    answer = api("POST", f"{index}/_search", {"size": 50, "query": {"bool": {"filter": [
        {"match_phrase": {"space.name": "draft"}}, {"match_phrase": {"document.metadata.title": title}}]}}})
    for hit in answer.get("hits", {}).get("hits", []):
        if hit["_source"]["document"]["metadata"]["title"] == title:
            return hit["_id"]
    return None


def integration_id(title="ns8"):
    return _draft_id("wazuh-threatintel-integrations", title)


def write_kvdb(integration):
    """Create or update the KVDB of the zones in the draft space; the caller promotes it."""
    resource = {
        "metadata": {"title": KVDB_TITLE, "description": "Zones the users of each customer may log in from",
                     "author": "NethServer", "references": ["https://github.com/stephdl/ns8-wazuh"]},
        "enabled": True,
        "content": kvdb_content(load()),
    }
    existing = _draft_id("wazuh-threatintel-kvdbs", KVDB_TITLE)
    if existing:
        answer = api("PUT", f"{CM}/kvdbs/{existing}", {"resource": resource})
    else:
        answer = api("POST", f"{CM}/kvdbs", {"integration": integration, "resource": resource})
    if answer.get("status") not in (200, 201):
        raise RuntimeError(f"{KVDB_TITLE}: {answer.get('message', answer)}")


def promote():
    # A change needs both steps to reach the space the engine runs
    for space in ("draft", "test"):
        changes = api("GET", f"{CM}/promote?space={space}").get("changes", {})
        if any(changes.get(kind) for kind in changes):
            answer = api("POST", f"{CM}/promote", {"space": space, "changes": changes})
            if answer.get("status") != 200:
                raise RuntimeError(f"promotion from {space}: {answer.get('message', answer)}")
