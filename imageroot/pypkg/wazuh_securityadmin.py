#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Read and apply the security documents of the indexer from the host.

The documents are streamed through stdin into the container, so a password or
a hash never touches the host disk."""

import hashlib
import json
import os
import subprocess
import sys
import time

import agent
import yaml

CONFIG_DIR = "/usr/share/wazuh-indexer/config/opensearch-security"


def podman_exec(args, stdin=None):
    return subprocess.run(["podman", "exec", "-i", "wazuh-indexer"] + args,
                          input=stdin, capture_output=True, text=True)


def wait_indexer():
    # The restart of the services returns before the indexer accepts requests
    for _ in range(60):
        if subprocess.run(["podman", "healthcheck", "run", "wazuh-indexer"],
                          capture_output=True).returncode == 0:
            return
        time.sleep(5)
    agent.assert_exp(False, "the indexer is not healthy")


def read_default(name, key):
    # A file read while the indexer is still rewriting its configuration can come back empty
    for _ in range(12):
        proc = podman_exec(["cat", f"{CONFIG_DIR}/{name}"])
        if proc.returncode == 0:
            document = yaml.safe_load(proc.stdout)
            if isinstance(document, dict) and key in document:
                return document
        time.sleep(5)
    agent.assert_exp(False, f"cannot read {name} from the indexer")


def apply_document(document, doc_type):
    tmp = f"/tmp/ns8-{doc_type}.yml"
    proc = podman_exec(["sh", "-c", f"umask 077; cat > {tmp}"], yaml.safe_dump(document))
    agent.assert_exp(proc.returncode == 0, f"cannot write {tmp}: {proc.stderr}")
    try:
        # securityadmin.sh without FILE would replace the whole security configuration
        for attempt in range(3):
            proc = podman_exec(["env", f"FILE={tmp}", f"TYPE={doc_type}", "/securityadmin.sh"])
            print(proc.stdout, file=sys.stderr)
            print(proc.stderr, file=sys.stderr)
            if proc.returncode == 0:
                break
            # The security index may still be reloading after the previous change
            time.sleep(10)
        agent.assert_exp(proc.returncode == 0, f"securityadmin.sh failed for {doc_type}")
    finally:
        podman_exec(["rm", "-f", tmp])


APPLIED_FILE = "security-applied.json"


def _security_index_uuid():
    # Imported here: wazuh_api is not needed by the other helpers of this file
    from wazuh_api import api
    answer = api("GET", "_cat/indices/.opendistro_security?format=json&h=uuid", admin_cert=True)
    return answer[0]["uuid"] if isinstance(answer, list) and answer else ""


def _fingerprints(index_uuid):
    try:
        with open(APPLIED_FILE) as f:
            applied = json.load(f)
    except (FileNotFoundError, ValueError):
        return {}
    # A new security index (new data volume, restore) holds the defaults again
    return applied if applied.get("index") == index_uuid else {}


def apply_document_if_changed(document, doc_type, force=False):
    """Apply the document only when it differs from the last one applied.

    securityadmin.sh takes about 8 seconds each time. Only a hash is kept on disk:
    the config document holds the LDAP bind password.
    """
    digest = hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()
    index_uuid = _security_index_uuid()
    applied = _fingerprints(index_uuid)
    if not force and index_uuid and applied.get(doc_type) == digest:
        print(f"{doc_type} unchanged, not applied", file=sys.stderr)
        return False
    apply_document(document, doc_type)
    applied[doc_type] = digest
    applied["index"] = index_uuid
    fd = os.open(APPLIED_FILE + ".new", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(applied, f)
    os.replace(APPLIED_FILE + ".new", APPLIED_FILE)
    return True
