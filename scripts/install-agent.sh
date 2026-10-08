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
# --version, --package-url, --sha256, --no-start, --force, --help.

set -euo pipefail

# Version and download place of the agent package
VERSION="${WAZUH_AGENT_VERSION:-5.0.0-rc1}"
PACKAGE_BASE="${WAZUH_PACKAGE_BASE:-https://packages-staging.xdrsiem.wazuh.info/pre-release/5.x}"
KEY_URL="https://packages.wazuh.com/key/GPG-KEY-WAZUH"

INSTALL_DIR=/var/ossec
CONFIG="${INSTALL_DIR}/etc/ossec.conf"
TOKEN="${WAZUH_ENROLLMENT_TOKEN:-}"
AGENT_NAME="${WAZUH_AGENT_NAME:-}"
PACKAGE_URL=""
SHA256=""
START=1
FORCE=0
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
  --version VERSION    Agent version to install (default: 5.0.0-rc1)
  --package-url URL    Download this package instead of the default one
  --sha256 HASH        Expected SHA-256 of the package, needed to check a deb
  --no-start           Configure the agent but do not start it
  --force              Enroll again even if the agent already has a key
  --help               Show this help
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --token) TOKEN="${2:?--token needs a value}"; shift 2 ;;
        --token-file) TOKEN="$(tr -d '[:space:]' < "${2:?--token-file needs a file}")"; shift 2 ;;
        --name) AGENT_NAME="${2:?--name needs a value}"; shift 2 ;;
        --version) VERSION="${2:?--version needs a value}"; shift 2 ;;
        --package-url) PACKAGE_URL="${2:?--package-url needs a value}"; shift 2 ;;
        --sha256) SHA256="${2:?--sha256 needs a value}"; shift 2 ;;
        --no-start) START=0; shift ;;
        --force) FORCE=1; shift ;;
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
[ -n "${TOKEN}" ] || { usage; die "no enrollment token: set WAZUH_ENROLLMENT_TOKEN"; }

# The agent name goes into the XML configuration
case "${AGENT_NAME}" in
    *[!A-Za-z0-9._-]*) die "the agent name may only hold letters, digits, dots, dashes and underscores" ;;
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

install_package() {
    if [ -x "${INSTALL_DIR}/bin/wazuh-agentd" ]; then
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
        rpm -U "${file}"
    else
        # The signature of a deb is in the metadata of the repository, which is not public for a pre-release
        if [ -z "${SHA256}" ]; then
            say "Warning: this deb is not checked. It comes from the Wazuh server over HTTPS. Use --sha256 to check it."
        fi
        DEBIAN_FRONTEND=noninteractive apt-get install -y "${file}" >&2 \
            || DEBIAN_FRONTEND=noninteractive dpkg -i "${file}" >&2
    fi
}

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

if [ -n "${AGENT_NAME}" ]; then
    # The name is read from the enrollment block, an agent_name next to the manager is refused
    sed -i '/<enrollment>/,/<\/enrollment>/d' "${CONFIG}"
    sed -i "0,/<manager>/ s#<manager>#<enrollment>\n      <agent_name>${AGENT_NAME}</agent_name>\n    </enrollment>\n    <manager>#" "${CONFIG}"
    "${INSTALL_DIR}/bin/wazuh-agentd" -t >/dev/null 2>&1 || die "the agent refuses the configuration, see ${CONFIG}"
fi

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
