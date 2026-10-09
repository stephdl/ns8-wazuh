#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Call the indexer REST API from the host, through curl inside the indexer container."""

import json
import os
import subprocess

_password = None

# What a backup keeps: user data and dashboards. The detection content comes back by itself
# from the CTI sync and from provision-content, and the system indices are rebuilt at start.
USER_INDICES = ("wazuh-events-v5-*,wazuh-findings-v5-*,wazuh-states-*,wazuh-active-responses*,"
                "wazuh-metrics-*,wazuh-agent-*,.kibana_*")
USER_DATA_STREAMS = ["wazuh-events-v5-*", "wazuh-findings-v5-*", "wazuh-active-responses*", "wazuh-metrics-*"]
CERTS = "/usr/share/wazuh-indexer/config/certs"


def container():
    return os.environ.get("INDEXER_CONTAINER", "wazuh-indexer")


def admin_password():
    global _password
    if _password is None:
        path = os.environ.get("INDEXER_SECRETS", "secrets/indexer.env")
        with open(path) as f:
            for line in f:
                if line.startswith("WAZUH_INDEXER_ADMIN_PASSWORD="):
                    _password = line.rstrip("\n").split("=", 1)[1]
        if _password is None:
            raise RuntimeError("admin password not found")
    return _password


def curl_quote(value):
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def api(method, path, body=None, admin_cert=False):
    # The curl options go through stdin, so the password never appears in a process list.
    # Restoring protected indices needs the admin certificate: the password is not enough.
    if admin_cert:
        config = f'cert = "{CERTS}/admin.pem"\nkey = "{CERTS}/admin-key.pem"\n'
    else:
        config = f'user = "admin:{curl_quote(admin_password())}"\n'
    config += f'request = "{method}"\nurl = "https://localhost:9200/{path}"\n'
    config += 'header = "Content-Type: application/json"\n'
    if body is not None:
        config += f'data-binary = "{curl_quote(json.dumps(body))}"\n'
    proc = subprocess.run(["podman", "exec", "-i", container(), "curl", "-sk", "-K", "-"],
                          input=config, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"curl failed: {proc.stderr}")
    if not proc.stdout.strip():
        return {}
    try:
        return json.loads(proc.stdout)
    except ValueError:
        raise RuntimeError(f"not a JSON answer: {proc.stdout[:200]}")


def manager_container():
    return os.environ.get("MANAGER_CONTAINER", "wazuh-manager")


def _manager_curl(config):
    proc = subprocess.run(["podman", "exec", "-i", manager_container(), "curl", "-sk", "-K", "-"],
                          input=config, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"curl failed: {proc.stderr}")
    return proc.stdout


def _manager_jwt():
    path = os.environ.get("MANAGER_SECRETS", "secrets/manager.env")
    password = None
    with open(path) as f:
        for line in f:
            if line.startswith("WAZUH_MANAGER_API_PASSWORD="):
                password = line.rstrip("\n").split("=", 1)[1]
    if password is None:
        raise RuntimeError("API password not found")
    jwt = _manager_curl(f'user = "wazuh:{curl_quote(password)}"\nrequest = "POST"\n'
                        'url = "https://localhost:55000/security/user/authenticate?raw=true"\n').strip()
    if jwt.count(".") != 2:
        raise RuntimeError("the Wazuh API refused the login")
    return jwt


def manager_api(method, path, body=None):
    """Call the Wazuh API, which listens inside the pod only."""
    config = f'request = "{method}"\nurl = "https://localhost:55000/{path}"\n'
    config += f'header = "Authorization: Bearer {_manager_jwt()}"\nheader = "Content-Type: application/json"\n'
    if body is not None:
        config += f'data-binary = "{curl_quote(json.dumps(body))}"\n'
    try:
        return json.loads(_manager_curl(config))
    except ValueError:
        raise RuntimeError("the Wazuh API did not answer with JSON")


def count_agents():
    """Return the number of enrolled agents, the manager excluded, or None when the API does not answer."""
    try:
        return manager_api("GET", "agents/summary/status")["data"]["connection"]["total"]
    except (RuntimeError, KeyError, TypeError):
        return None
