#!/usr/bin/env bash

#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

# Install the Wazuh agent on a Debian or Red Hat family host and enroll it with
# a token created by the ns8-wazuh module.
#
#   curl -fsSL https://raw.githubusercontent.com/stephdl/ns8-wazuh/main/scripts/install-agent.sh \
#       | sudo WAZUH_ENROLLMENT_TOKEN='<token>' bash
#
# The token is read from the environment, so it does not show in the process list
# of the script. Options (after "bash -s --"): --token, --token-file, --name,
# --version, --package-url, --sha256, --no-start, --force, --update, --help.
#
# Update an enrolled agent to the version of its server, without a token:
#
#   curl -fsSL .../install-agent.sh | sudo bash -s -- --update --version <server version>

set -euo pipefail

# Version and download place of the agent package
VERSION="${WAZUH_AGENT_VERSION:-5.0.0-rc1}"
PACKAGE_BASE="${WAZUH_PACKAGE_BASE:-https://packages-staging.xdrsiem.wazuh.info/pre-release/5.x}"
KEY_URL="https://packages.wazuh.com/key/GPG-KEY-WAZUH"

INSTALL_DIR=/var/ossec
CONFIG="${INSTALL_DIR}/etc/ossec.conf"
TOKEN="${WAZUH_ENROLLMENT_TOKEN:-}"
AGENT_NAME="${WAZUH_AGENT_NAME:-}"
AGENT_GROUP="${WAZUH_AGENT_GROUP:-}"
PACKAGE_URL=""
SHA256=""
START=1
FORCE=0
UPDATE=0
WORKDIR=""

say() { printf '%s\n' "$*" >&2; }
die() { say "install-agent: $*"; exit 1; }

usage() {
    cat >&2 <<'EOF'
Usage: install-agent.sh [options]

The enrollment token is read from WAZUH_ENROLLMENT_TOKEN, or from --token-file.

  --token TOKEN        Enrollment token (visible in the process list, prefer the variable)
  --token-file FILE    Read the enrollment token from FILE
  --name NAME          Agent name (default: the FQDN, else the host name)
  --group GROUP        Agent group, the customer of this host (default: default)
  --version VERSION    Agent version to install (default: 5.0.0-rc1)
  --package-url URL    Download this package instead of the default one
  --sha256 HASH        Expected SHA-256 of the package, needed to check a deb
  --no-start           Configure the agent but do not start it
  --force              Enroll again even if the agent already has a key
  --update             Install the package of --version on an enrolled agent, keep its key
  --help               Show this help
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --token) TOKEN="${2:?--token needs a value}"; shift 2 ;;
        --token-file) TOKEN="$(tr -d '[:space:]' < "${2:?--token-file needs a file}")"; shift 2 ;;
        --name) AGENT_NAME="${2:?--name needs a value}"; shift 2 ;;
        --group) AGENT_GROUP="${2:?--group needs a value}"; shift 2 ;;
        --version) VERSION="${2:?--version needs a value}"; shift 2 ;;
        --package-url) PACKAGE_URL="${2:?--package-url needs a value}"; shift 2 ;;
        --sha256) SHA256="${2:?--sha256 needs a value}"; shift 2 ;;
        --no-start) START=0; shift ;;
        --force) FORCE=1; shift ;;
        --update) UPDATE=1; shift ;;
        --help|-h) usage; exit 0 ;;
        *) usage; die "unknown option: $1" ;;
    esac
done

cleanup() {
    if [ -n "${WORKDIR}" ] && [ -d "${WORKDIR}" ]; then
        rm -rf "${WORKDIR}"
    fi
}
trap cleanup EXIT

[ "$(id -u)" -eq 0 ] || die "run it as root, for example with sudo"
command -v curl >/dev/null 2>&1 || die "curl is required"
if [ "${UPDATE}" -eq 1 ]; then
    [ "${FORCE}" -eq 0 ] || die "--update and --force cannot be used together"
else
    [ -n "${TOKEN}" ] || { usage; die "no enrollment token: set WAZUH_ENROLLMENT_TOKEN"; }
fi

# Wazuh takes the short host name by default, the FQDN is easier to recognize
if [ -z "${AGENT_NAME}" ] && [ "${UPDATE}" -ne 1 ]; then
    fqdn="$(timeout 5 hostname -f 2>/dev/null || true)"
    fqdn="${fqdn%.}"
    # Loopback names are shared by many hosts, Wazuh refuses names over 128 characters
    case "${fqdn}" in
        localhost*|*.localdomain*|*[!A-Za-z0-9._-]*) ;;
        *.*) [ "${#fqdn}" -gt 128 ] || AGENT_NAME="${fqdn}" ;;
    esac
fi

# The agent name goes into the XML configuration
case "${AGENT_NAME}" in
    *[!A-Za-z0-9._-]*) die "the agent name may only hold letters, digits, dots, dashes and underscores" ;;
esac
case "${AGENT_GROUP}" in
    *[!A-Za-z0-9._-]*|.|..) die "the agent group may only hold letters, digits, dots, dashes and underscores" ;;
esac

arch="$(uname -m)"
if command -v dpkg >/dev/null 2>&1; then
    family=deb
    case "${arch}" in
        x86_64|amd64) package_arch=amd64 ;;
        aarch64|arm64) package_arch=arm64 ;;
        *) die "unsupported architecture: ${arch}" ;;
    esac
    default_url="${PACKAGE_BASE}/apt/pool/main/w/wazuh-agent/wazuh-agent_${VERSION}_${package_arch}.deb"
elif command -v rpm >/dev/null 2>&1; then
    family=rpm
    case "${arch}" in
        x86_64|amd64) package_arch=x86_64 ;;
        aarch64|arm64) package_arch=aarch64 ;;
        *) die "unsupported architecture: ${arch}" ;;
    esac
    default_url="${PACKAGE_BASE}/yum/wazuh-agent-${VERSION}.${package_arch}.rpm"
else
    die "neither dpkg nor rpm found: only Debian and Red Hat families are supported"
fi
PACKAGE_URL="${PACKAGE_URL:-${default_url}}"

installed_version() {
    if [ "${family}" = rpm ]; then
        rpm -q --qf '%{VERSION}-%{RELEASE}' wazuh-agent 2>/dev/null || true
    else
        dpkg-query -W -f '${Version}' wazuh-agent 2>/dev/null || true
    fi
}

install_package() {
    if [ -x "${INSTALL_DIR}/bin/wazuh-agentd" ] && [ "${UPDATE}" -ne 1 ]; then
        say "The agent is already installed, the package is not downloaded again."
        return
    fi

    WORKDIR="$(mktemp -d)"
    local file="${WORKDIR}/wazuh-agent.${family}"
    say "Downloading ${PACKAGE_URL}"
    curl -fsSL --retry 3 -o "${file}" "${PACKAGE_URL}" || die "cannot download the package"

    if [ -n "${SHA256}" ]; then
        printf '%s  %s\n' "${SHA256}" "${file}" | sha256sum -c - >/dev/null 2>&1 \
            || die "the SHA-256 of the package does not match"
        say "SHA-256 checked."
    fi

    if [ "${family}" = rpm ]; then
        # The rpm carries a signature made with the public Wazuh key
        curl -fsSL --retry 3 -o "${WORKDIR}/wazuh.gpg" "${KEY_URL}" || die "cannot download the Wazuh public key"
        rpm --import "${WORKDIR}/wazuh.gpg"
        rpm -K "${file}" 2>&1 | grep -q "digests signatures OK" || die "the signature of the package is not valid"
        say "Signature checked."
        # Image tags and package versions differ (5.0.0-rc1 is the package 5.0.0-1): compare the package itself
        if [ "${UPDATE}" -eq 1 ] && [ "$(rpm -qp --qf '%{VERSION}-%{RELEASE}' "${file}" 2>/dev/null)" = "$(installed_version)" ]; then
            say "The agent already runs this version, the package is kept."
            return 0
        fi
        rpm -U "${file}"
    else
        # The signature of a deb is in the metadata of the repository, which is not public for a pre-release
        if [ -z "${SHA256}" ]; then
            say "Warning: this deb is not checked. It comes from the Wazuh server over HTTPS. Use --sha256 to check it."
        fi
        if [ "${UPDATE}" -eq 1 ] && [ "$(dpkg-deb -f "${file}" Version 2>/dev/null)" = "$(installed_version)" ]; then
            say "The agent already runs this version, the package is kept."
            return 0
        fi
        DEBIAN_FRONTEND=noninteractive apt-get install -y "${file}" >&2 \
            || DEBIAN_FRONTEND=noninteractive dpkg -i "${file}" >&2
    fi
}

is_ns8() { [ -d /etc/nethserver ] || command -v runagent >/dev/null 2>&1; }

# On an NS8 node the agent runs ns8-journal instead of reading journald itself, so each line
# carries the module that wrote it: its own journald reader sends only "program[pid]: message"
setup_ns8_journal() {
    is_ns8 || return 0
    command -v python3 >/dev/null 2>&1 || { say "Warning: no python3, the lines will not carry their NS8 module"; return 0; }
    cat > "${INSTALL_DIR}/bin/ns8-journal" <<'NS8JOURNAL'
#!/usr/bin/env python3

#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

# Print the journal lines written since the last run, one JSON object per line, with the NS8 module
# that wrote each of them. The Wazuh agent runs it every few seconds: its own journald reader sends
# only "program[pid]: message" and drops the user and the unit that tell the module apart.

import json
import os
import pwd
import re
import signal
import subprocess
import sys
import time

CURSOR = "/var/ossec/var/ns8-journal.cursor"
FIELDS = "SYSLOG_IDENTIFIER,_COMM,_PID,MESSAGE,_SYSTEMD_UNIT,_SYSTEMD_USER_UNIT,_SYSTEMD_OWNER_UID"
# Rootful modules and the core keep their state there, named after their id
ROOTFUL_DIR = "/var/lib/nethserver"
# Bytes per line, the message is cut to fit: the agent refuses lines over 64 KB
MAX_LINE = 16384
# Lines per run. A run that never ends saves no cursor, and the next one sends the same lines again
BATCH = 5000
# Seconds per run. The agent never starts this command again while it runs, so a run stuck on a
# full pipe or a stalled journalctl would silence the node
DEADLINE = 60
# Readable names of the Nextcloud LDAP users, which Nextcloud logs by their UUID only
USERS = "/var/ossec/var/ns8-journal.users.json"
# occ takes about 2 seconds. Seconds of lookups per run: a burst of new users must not reach DEADLINE
LOOKUP_BUDGET = 15
LOOKUP_TIMEOUT = 5
# A user that occ cannot name is asked again after this many seconds, not at each login
RETRY_UNKNOWN = 3600

_owners = {}
_journal = None
_users = None
_lookup_time = 0.0


def text(value):
    # journald gives a byte array when the message is not valid UTF-8
    if isinstance(value, list):
        return bytes(value).decode("utf-8", "replace")
    return value or ""


def rootless_module(uid):
    """Return the module id of a rootless module user, or an empty string."""
    if uid not in _owners:
        try:
            user = pwd.getpwuid(int(uid))
            _owners[uid] = user.pw_name if os.path.isdir(os.path.join(user.pw_dir, ".config", "state")) else ""
        except (KeyError, ValueError):
            _owners[uid] = ""
    return _owners[uid]


def rootful_module(unit):
    """Return the module id found in a system unit name, or an empty string."""
    name = unit.rsplit(".", 1)[0]
    # agent@mail4.service runs the actions of mail4, crowdsec13-upgrade-hub.service belongs to crowdsec13
    candidates = [name.split("@", 1)[1]] if "@" in name else [name, name.split("-", 1)[0]]
    for candidate in candidates:
        if candidate and os.path.isdir(os.path.join(ROOTFUL_DIR, candidate)):
            return candidate
    # The agent of a rootless module runs as root too
    if "@" in name and rootless_module_by_name(candidates[0]):
        return candidates[0]
    return ""


def rootless_module_by_name(name):
    try:
        return rootless_module(str(pwd.getpwnam(name).pw_uid))
    except KeyError:
        return ""


def read_cursor():
    try:
        with open(CURSOR) as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def save_cursor(cursor):
    with open(CURSOR + ".tmp", "w") as f:
        f.write(cursor)
        # Without it a power loss can leave an empty cursor, and the next run jumps to the end of the journal
        f.flush()
        os.fsync(f.fileno())
    os.replace(CURSOR + ".tmp", CURSOR)


def load_users():
    global _users
    if _users is None:
        try:
            with open(USERS) as f:
                _users = json.load(f)
        except (OSError, ValueError):
            _users = {}
    return _users


def occ_user_info(module, uid):
    """Return the user:info of a Nextcloud user, or an empty dict."""
    # A session of its own: on timeout the whole group dies, podman exec included. Killed alone,
    # runagent would leave it holding the pipe and the read would wait past DEADLINE
    proc = subprocess.Popen(["runagent", "-m", module, "occ", "user:info", uid, "--output=json"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, start_new_session=True)
    try:
        out = proc.communicate(timeout=LOOKUP_TIMEOUT)[0]
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        return {}
    try:
        # The log lines of Nextcloud come first when its log level is debug
        return json.loads(next(line for line in out.splitlines() if line.startswith("{")))
    except (StopIteration, ValueError):
        return {}


def nextcloud_user(module, uid):
    """Return the email or display name of a Nextcloud user, or an empty string."""
    global _lookup_time
    users = load_users().setdefault(module, {})
    known = users.get(uid)
    # A name, or [time] for a user occ could not name
    if isinstance(known, str):
        return known
    if (known and time.time() - known[0] < RETRY_UNKNOWN) or _lookup_time >= LOOKUP_BUDGET:
        return ""
    start = time.time()
    try:
        info = occ_user_info(module, uid)
    except OSError:
        info = {}
    _lookup_time += time.time() - start
    name = info.get("email") or info.get("display_name") or ""
    users[uid] = name or [time.time()]
    with open(USERS + ".tmp", "w") as f:
        json.dump(_users, f)
    os.replace(USERS + ".tmp", USERS)
    return name


def event(entry):
    owner = entry.get("_SYSTEMD_OWNER_UID", "0")
    unit = entry.get("_SYSTEMD_USER_UNIT") if owner != "0" else entry.get("_SYSTEMD_UNIT")
    module = rootless_module(owner) if owner != "0" else ""
    if not module:
        module = rootful_module(entry.get("_SYSTEMD_UNIT", ""))
    data = {
        "ns8_journal": 1,
        "program": text(entry.get("SYSLOG_IDENTIFIER") or entry.get("_COMM")),
        "pid": text(entry.get("_PID")),
        "module": module,
        "unit": text(unit),
        "message": text(entry.get("MESSAGE")).rstrip("\n"),
    }
    if module.startswith("nextcloud") and " postLogin" in data["message"]:
        found = re.search(r"LoginListener - ([0-9A-Fa-f-]+) postLogin", data["message"])
        name = nextcloud_user(module, found.group(1)) if found else ""
        if name:
            data["user"] = name
    return data


def encode(event):
    """Return the event as one JSON line in UTF-8, its message cut until the line fits MAX_LINE."""
    while True:
        line = json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
        excess = len(line) - MAX_LINE
        if excess <= 0 or not event["message"]:
            return line
        message = event["message"]
        # A character can take up to 6 bytes once escaped: cut in proportion to the bytes it really takes
        size = len(json.dumps(message, ensure_ascii=False).encode("utf-8"))
        event["message"] = message[:min(len(message) - 1, len(message) * (size - excess) // size)]


def give_up(signum, frame):
    if _journal:
        _journal.kill()
    # No flush and no cursor: the next run sends the same lines again
    os._exit(1)


def main():
    global _journal
    signal.signal(signal.SIGALRM, give_up)
    signal.alarm(DEADLINE)
    cursor = read_cursor()
    if not cursor:
        # The first run starts from now: the history is already on the server, or not wanted
        last = subprocess.run(["journalctl", "--no-pager", "-o", "json", "-n", "1", "--output-fields=_PID"],
                              stdout=subprocess.PIPE, text=True).stdout
        if last.strip():
            save_cursor(json.loads(last)["__CURSOR"])
        return
    # Without --all journalctl gives null for any field over 4096 bytes. LC_ALL=C keeps its errors in
    # English, the broken cursor check below looks for a word in them
    _journal = proc = subprocess.Popen(
        ["journalctl", "--no-pager", "-o", "json", "--all", f"--output-fields={FIELDS}", f"--after-cursor={cursor}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace",
        env={**os.environ, "LC_ALL": "C"})
    count = 0
    try:
        for line in proc.stdout:
            try:
                entry = json.loads(line)
                position = entry["__CURSOR"]
            except (ValueError, TypeError, KeyError):
                continue
            try:
                data = encode(event(entry))
            except Exception as error:
                # A bad entry is skipped: stopping on it would send the lines before it again at each run
                print(f"ns8-journal: entry skipped: {error!r}", file=sys.stderr)
            else:
                sys.stdout.buffer.write(data)
            cursor = position
            count += 1
            if count >= BATCH:
                break
        sys.stdout.buffer.flush()
    except BrokenPipeError:
        # The agent stopped reading, the next run sends these lines again. Python would fail once more
        # when it flushes stdout at exit
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(1)
    finally:
        # Also when the output fails: journalctl would wait forever to write the rest
        proc.kill()
        proc.wait()
    # Saved once the lines are out, so a run cut before that sends them again instead of losing them
    save_cursor(cursor)
    error = proc.stderr.read()
    if count == 0 and proc.returncode != 0 and "cursor" in error:
        # A broken cursor would silence the node for good: the next run starts again from now
        print(f"ns8-journal: cursor dropped: {error.strip()}", file=sys.stderr)
        os.remove(CURSOR)

main()
NS8JOURNAL
    chmod 750 "${INSTALL_DIR}/bin/ns8-journal"
    # Any journald block, whatever the order of its children, becomes the command block
    python3 - "${CONFIG}" <<'NS8CONF' || die "cannot set ns8-journal in ${CONFIG}"
import re, sys
path = sys.argv[1]
text = open(path).read()
command = ("  <localfile>\n    <log_format>command</log_format>\n"
           "    <command>/var/ossec/bin/ns8-journal</command>\n    <alias>ns8-journal</alias>\n"
           "    <frequency>10</frequency>\n  </localfile>")
block = re.compile(r"[ \t]*<localfile>(?:(?!</localfile>).)*?<log_format>\s*journald\s*</log_format>(?:(?!</localfile>).)*?</localfile>",
                   re.S)
text, count = block.subn("", text)
if "<command>/var/ossec/bin/ns8-journal</command>" not in text:
    if "</ossec_config>" not in text:
        sys.exit(1)
    head, sep, tail = text.rpartition("</ossec_config>")
    text = head + command + "\n" + sep + tail
open(path, "w").write(text)
NS8CONF
    grep -q "<command>/var/ossec/bin/ns8-journal</command>" "${CONFIG}" || die "ns8-journal is not in ${CONFIG}"
    ! grep -q "<log_format>journald</log_format>" "${CONFIG}" || die "a journald block is left in ${CONFIG}"
    "${INSTALL_DIR}/bin/wazuh-agentd" -t >/dev/null 2>&1 || die "the agent refuses the ns8-journal setting, see ${CONFIG}"
    say "NS8 node: the agent reads the journal through ns8-journal, with the module of each line."
}

# The inventory of the agent has no uptime: ns8-uptime reports it every hour, on any Linux host
setup_uptime() {
    cat > "${INSTALL_DIR}/bin/ns8-uptime" <<'NS8UPTIME'
#!/bin/sh

#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

# Print the uptime in seconds and the boot time as one JSON line, read by the ns8-uptime decoder.
# The boot time comes from /proc/uptime and not from btime: an LXC container reads its own uptime there.
# Computed to the millisecond, then rounded: whole seconds made it move by one second between reports,
# and the dashboard groups the reports by boot time.

set -- $(awk -v now="$(date +%s.%N)" '{ printf "%d %d\n", $1, now - $1 + 0.5 }' /proc/uptime)
[ -n "$2" ] || { echo "ns8-uptime: cannot read /proc/uptime" >&2; exit 1; }
up="$1"
boot="$(date -u -d "@$2" +%Y-%m-%dT%H:%M:%SZ)"
printf '{"ns8_uptime":1,"uptime":%s,"boot":"%s"}\n' "${up}" "${boot}"
NS8UPTIME
    chmod 750 "${INSTALL_DIR}/bin/ns8-uptime"
    if ! grep -q "<command>/var/ossec/bin/ns8-uptime</command>" "${CONFIG}"; then
        # The last ossec_config block, as for ns8-journal, and without python3: a plain host may not have it
        last="$(grep -n "</ossec_config>" "${CONFIG}" | tail -n 1 | cut -d: -f1)"
        [ -n "${last}" ] || die "no </ossec_config> in ${CONFIG}"
        awk -v last="${last}" 'NR == last {
            print "  <localfile>\n    <log_format>command</log_format>"
            print "    <command>/var/ossec/bin/ns8-uptime</command>\n    <alias>ns8-uptime</alias>"
            print "    <frequency>3600</frequency>\n  </localfile>"
        } { print }' "${CONFIG}" > "${CONFIG}.new" && cat "${CONFIG}.new" > "${CONFIG}" && rm -f "${CONFIG}.new" \
            || die "cannot set ns8-uptime in ${CONFIG}"
    fi
    "${INSTALL_DIR}/bin/wazuh-agentd" -t >/dev/null 2>&1 || die "the agent refuses the ns8-uptime setting, see ${CONFIG}"
}

# A ca-certificates update rewrites every file of directory-hash, 670 FIM findings at once. The CA bundles next to it
# stay watched. Other files changed by an update are grouped in the findings email, not ignored here.
setup_syscheck() {
    command -v python3 >/dev/null 2>&1 || { say "Warning: no python3, file integrity keeps its defaults"; return 0; }
    python3 - "${CONFIG}" <<'SYSCHECK' || die "cannot set syscheck in ${CONFIG}"
import re, sys
path = sys.argv[1]
text = open(path).read()
match = re.search(r"<syscheck>.*?</syscheck>", text, re.S)
if not match:
    sys.exit(print("Warning: no syscheck block, file integrity keeps its defaults", file=sys.stderr))
block = match.group(0)
for ignore in ('<ignore type="sregex">^/etc/pki/ca-trust/extracted/pem/directory-hash</ignore>',):
    if ignore not in block:
        block = block.replace("</syscheck>", f"  {ignore}\n  </syscheck>")
open(path, "w").write(text[:match.start()] + block + text[match.end():])
SYSCHECK
    "${INSTALL_DIR}/bin/wazuh-agentd" -t >/dev/null 2>&1 || die "the agent refuses the syscheck setting, see ${CONFIG}"
}

# Rootcheck reports as rootkits the /dev/.lxc files of an LXC container,
# and the world-writable files of the Podman image layers of an NS8 node
setup_rootcheck() {
    local lxc=0 ns8=0
    [ "$(systemd-detect-virt -c 2>/dev/null)" != "lxc" ] || lxc=1
    ! is_ns8 || ns8=1
    [ "${lxc}" -eq 1 ] || [ "${ns8}" -eq 1 ] || return 0
    command -v python3 >/dev/null 2>&1 || { say "Warning: no python3, rootcheck keeps its defaults"; return 0; }
    python3 - "${CONFIG}" "${lxc}" "${ns8}" <<'ROOTCHECK' || die "cannot set rootcheck in ${CONFIG}"
import re, sys
path, lxc, ns8 = sys.argv[1], sys.argv[2] == "1", sys.argv[3] == "1"
text = open(path).read()
match = re.search(r"<rootcheck>.*?</rootcheck>", text, re.S)
if not match:
    sys.exit(print("Warning: no rootcheck block, rootcheck keeps its defaults", file=sys.stderr))
block = match.group(0)
if lxc:
    # check_dev is on when the tag is missing
    if re.search(r"<check_dev>", block):
        block = re.sub(r"<check_dev>.*?</check_dev>", "<check_dev>no</check_dev>", block)
    else:
        block = block.replace("</rootcheck>", "  <check_dev>no</check_dev>\n  </rootcheck>")
    print("LXC container: rootcheck does not scan /dev.", file=sys.stderr)
if ns8:
    for ignore in ("<ignore>/var/lib/containers/storage</ignore>",
                   '<ignore type="sregex">/.local/share/containers/</ignore>'):
        if ignore not in block:
            block = block.replace("</rootcheck>", f"  {ignore}\n  </rootcheck>")
    print("NS8 node: rootcheck skips the container images.", file=sys.stderr)
open(path, "w").write(text[:match.start()] + block + text[match.end():])
ROOTCHECK
    "${INSTALL_DIR}/bin/wazuh-agentd" -t >/dev/null 2>&1 || die "the agent refuses the rootcheck setting, see ${CONFIG}"
}

if [ "${UPDATE}" -eq 1 ]; then
    [ -s "${INSTALL_DIR}/etc/client.keys" ] || die "the agent is not enrolled: install it with a token first"
    before="$(installed_version)"
    say "Installed version: ${before:-unknown}, wanted: ${VERSION}"
    install_package
    setup_ns8_journal
    setup_uptime
    setup_syscheck
    setup_rootcheck
    # The agent restart leaves its commands running, so a run stuck before this fix would stay forever
    pkill -f "${INSTALL_DIR}/bin/ns8-journal" 2>/dev/null || true
    # The package keeps ossec.conf and the key, a restart loads the new binaries
    if command -v systemctl >/dev/null 2>&1; then
        systemctl restart wazuh-agent
    else
        "${INSTALL_DIR}/bin/wazuh-control" restart
    fi
    say "Updated from ${before:-unknown} to $(installed_version). The agent keeps its key and its settings."
    exit 0
fi

install_package
[ -x "${INSTALL_DIR}/bin/wazuh-agentd" ] || die "the agent is not installed"

# The address of the server is inside the token
description="$(printf '%s' "${TOKEN}" | "${INSTALL_DIR}/bin/wazuh-agentd" --show-token 2>&1)" \
    || die "the enrollment token is refused: ${description}"
address="$(printf '%s\n' "${description}" | sed -n 's/^adr: *//p' | head -n 1)"
[ -n "${address}" ] || die "the enrollment token holds no server address"
say "Server: ${address}"

host_only="${address%%/*}"
host_only="${host_only%%:*}"
if ! timeout 5 bash -c "exec 3<>/dev/tcp/${host_only}/1517" 2>/dev/null; then
    say "Warning: ${host_only} does not answer on the port 1517 from this host. The agent will retry."
fi

if [ -s "${INSTALL_DIR}/etc/client.keys" ] && [ "${FORCE}" -ne 1 ]; then
    say "The agent already has a key, so it is already enrolled. Use --force to enroll it again."
    exit 0
fi

if [ "${FORCE}" -eq 1 ]; then
    # Forget the previous server: its key and its certificate authority would be refused by the new one
    if command -v systemctl >/dev/null 2>&1; then
        systemctl stop wazuh-agent 2>/dev/null || true
    else
        "${INSTALL_DIR}/bin/wazuh-control" stop >/dev/null 2>&1 || true
    fi
    : > "${INSTALL_DIR}/etc/client.keys"
    rm -f "${INSTALL_DIR}/etc/certs/root-ca.pem" "${INSTALL_DIR}/etc/certs/.anchor-committed" "${INSTALL_DIR}/etc/reenroll.secret"
fi

# Keep the file of the package once, to compare with the changes
[ -f "${CONFIG}.orig" ] || cp -p "${CONFIG}" "${CONFIG}.orig"
sed -i "/<manager>/,/<\/manager>/ s#<endpoint>.*</endpoint>#<endpoint>${address}</endpoint>#" "${CONFIG}"
if ! grep -q "<endpoint>${address}</endpoint>" "${CONFIG}"; then
    die "cannot write the server address in ${CONFIG}"
fi

if [ -n "${AGENT_NAME}" ] || [ -n "${AGENT_GROUP}" ]; then
    # The name and the group are read from the enrollment block, the manager stores the group at enrollment
    enrollment="<enrollment>"
    [ -z "${AGENT_NAME}" ] || enrollment="${enrollment}\n      <agent_name>${AGENT_NAME}</agent_name>"
    [ -z "${AGENT_GROUP}" ] || enrollment="${enrollment}\n      <groups>${AGENT_GROUP}</groups>"
    # Keep the other settings of an existing block, only the name and the group are replaced
    if grep -q "<enrollment>" "${CONFIG}"; then
        sed -i '/<enrollment>/,/<\/enrollment>/ { /<agent_name>/d; /<groups>/d }' "${CONFIG}"
        sed -i "0,/<enrollment>/ s#<enrollment>#${enrollment}#" "${CONFIG}"
    else
        sed -i "0,/<manager>/ s#<manager>#${enrollment}\n    </enrollment>\n    <manager>#" "${CONFIG}"
    fi
    "${INSTALL_DIR}/bin/wazuh-agentd" -t >/dev/null 2>&1 || die "the agent refuses the configuration, see ${CONFIG}"
fi

setup_ns8_journal
setup_uptime
setup_syscheck
setup_rootcheck

# Only root reads the token: the agent takes it at its first start and deletes it
token_file="${INSTALL_DIR}/etc/enrollment_token"
: > "${token_file}"
chmod 600 "${token_file}"
chown root:root "${token_file}"
printf '%s' "${TOKEN}" > "${token_file}"

if [ "${START}" -ne 1 ]; then
    say "Configured. Start it with: systemctl enable --now wazuh-agent"
    exit 0
fi

log_file="${INSTALL_DIR}/logs/ossec.log"
start_line=0
[ -f "${log_file}" ] && start_line="$(wc -l < "${log_file}")"

if command -v systemctl >/dev/null 2>&1; then
    systemctl enable wazuh-agent >/dev/null 2>&1 || true
    systemctl restart wazuh-agent
else
    "${INSTALL_DIR}/bin/wazuh-control" restart
fi

# The agent writes this line once the server accepted the token
for _ in $(seq 1 30); do
    if tail -n "+$((start_line + 1))" "${log_file}" 2>/dev/null | grep -q "enrollment succeeded"; then
        say "Enrolled. The agent is running and sends its logs to ${address}."
        exit 0
    fi
    sleep 2
done

say "The agent is started but the enrollment is not confirmed after 60 seconds. Last messages:"
tail -n "+$((start_line + 1))" "${log_file}" 2>/dev/null | grep -E "ERROR|WARNING" | tail -n 4 >&2 || true
say "Full log: ${log_file}"
exit 1
