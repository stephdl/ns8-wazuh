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
  --name NAME          Agent name (default: the host name)
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

# On an NS8 node the agent runs ns8-journal instead of reading journald itself, so each line
# carries the module that wrote it: its own journald reader sends only "program[pid]: message"
setup_ns8_journal() {
    [ -d /etc/nethserver ] || command -v runagent >/dev/null 2>&1 || return 0
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
import subprocess
import sys
import tempfile

CURSOR = "/var/ossec/var/ns8-journal.cursor"
FIELDS = "SYSLOG_IDENTIFIER,_COMM,_PID,MESSAGE,_SYSTEMD_UNIT,_SYSTEMD_USER_UNIT,_SYSTEMD_OWNER_UID"
# Rootful modules and the core keep their state there, named after their id
ROOTFUL_DIR = "/var/lib/nethserver"
# Bytes per line, the message is cut to fit: the agent refuses lines over 64 KB
MAX_LINE = 16384
# Lines per run. A run that never ends saves no cursor, and the next one sends the same lines again
BATCH = 5000

_owners = {}


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


def event(entry):
    owner = entry.get("_SYSTEMD_OWNER_UID", "0")
    unit = entry.get("_SYSTEMD_USER_UNIT") if owner != "0" else entry.get("_SYSTEMD_UNIT")
    module = rootless_module(owner) if owner != "0" else ""
    if not module:
        module = rootful_module(entry.get("_SYSTEMD_UNIT", ""))
    return {
        "ns8_journal": 1,
        "program": text(entry.get("SYSLOG_IDENTIFIER") or entry.get("_COMM")),
        "pid": text(entry.get("_PID")),
        "module": module,
        "unit": text(unit),
        "message": text(entry.get("MESSAGE")).rstrip("\n"),
    }


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


def main():
    cursor = read_cursor()
    if not cursor:
        # The first run starts from now: the history is already on the server, or not wanted
        last = subprocess.run(["journalctl", "--no-pager", "-o", "json", "-n", "1", "--output-fields=_PID"],
                              stdout=subprocess.PIPE, text=True).stdout
        if last.strip():
            save_cursor(json.loads(last)["__CURSOR"])
        return
    # Without --all journalctl gives null for any field over 4096 bytes. Its errors go to a file:
    # a pipe nobody reads fills up and blocks it
    errors = tempfile.TemporaryFile(mode="w+")
    proc = subprocess.Popen(["journalctl", "--no-pager", "-o", "json", "--all", f"--output-fields={FIELDS}",
                             f"--after-cursor={cursor}"], stdout=subprocess.PIPE, stderr=errors, text=True)
    count = 0
    try:
        for line in proc.stdout:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            try:
                data = encode(event(entry))
            except Exception as error:
                # A bad entry is skipped: stopping on it would send the lines before it again at each run
                print(f"ns8-journal: entry skipped: {error!r}", file=sys.stderr)
            else:
                sys.stdout.buffer.write(data)
            cursor = entry["__CURSOR"]
            count += 1
            if count >= BATCH:
                break
    finally:
        # Also when the output fails: journalctl would wait forever to write the rest, and the
        # agent never starts this command again while it runs
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        # Saved once the lines are out, so a run cut before that sends them again instead of losing them
        sys.stdout.buffer.flush()
        save_cursor(cursor)
    errors.seek(0)
    error = errors.read()
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

if [ "${UPDATE}" -eq 1 ]; then
    [ -s "${INSTALL_DIR}/etc/client.keys" ] || die "the agent is not enrolled: install it with a token first"
    before="$(installed_version)"
    say "Installed version: ${before:-unknown}, wanted: ${VERSION}"
    install_package
    setup_ns8_journal
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
    sed -i '/<enrollment>/,/<\/enrollment>/d' "${CONFIG}"
    sed -i "0,/<manager>/ s#<manager>#${enrollment}\n    </enrollment>\n    <manager>#" "${CONFIG}"
    "${INSTALL_DIR}/bin/wazuh-agentd" -t >/dev/null 2>&1 || die "the agent refuses the configuration, see ${CONFIG}"
fi

setup_ns8_journal

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
