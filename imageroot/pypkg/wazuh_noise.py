#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Routine findings: NOISE is left out of the email, DASHBOARD_NOISE is hidden by default in the fleet dashboard."""

# Timers, module sessions and backups stop services all day. Only these units stopping is worth a line,
# an attacker stops them to hide. A failed unit stays in, whatever its name. Debian names: ssh, chrony.
# The starts are informational: they stay out of the email and stay in the dashboard, for a new unit.
GUARD_UNITS = ["firewalld", "sshd", "ssh", "auditd", "wazuh-agent", "chronyd", "chrony"]

NOISE = [
    {"bool": {"filter": [{"terms": {"event.action": ["service-stopped", "service-deleted"]}},
                         {"term": {"event.outcome": "success"}}],
              "must_not": [{"terms": {"service.name": GUARD_UNITS}},
                           # The CrowdSec module service, not its crowdsec1-upgrade-hub timer
                           {"regexp": {"service.name": "crowdsec[0-9]+"}}]}},
    # The CrowdSec bouncer adds each banned address to its nftables set. Other firewall changes stay in.
    {"bool": {"filter": [{"term": {"wazuh.rule.title": "Firewall rule modified"}},
                         {"prefix": {"process.name": "crowdsec-firew"}}]}},
    # The hourly anacron line of Debian and Proxmox, run by cron as root
    {"term": {"wazuh.rule.title": "Sudo command targeting a persistence path - if [ -x /etc/init.d/anacron ] && "
                                  "! [ -d /run/systemd/system ]; then exec /usr/sbin/invoke-rc.d anacron start >/dev/null; fi"}},
    # The Proxmox cluster filesystem rewrites its state files and rotates its auth key every day.
    # Its configuration files, users, storage and firewall, stay in.
    {"prefix": {"wazuh.rule.title": "Wazuh FIM - File modified - /etc/pve/."}},
    {"wildcard": {"wazuh.rule.title": "Wazuh FIM - File modified - /etc/pve/nodes/*/lrm_status"}},
    {"prefix": {"wazuh.rule.title": "Wazuh FIM - File modified - /etc/pve/authkey."}},
    {"prefix": {"wazuh.rule.title": "Wazuh FIM - File modified - /etc/pve/priv/authkey."}},
    {"term": {"wazuh.rule.title": "Wazuh FIM - File modified - /etc/apt/apt.conf.d/76pveproxy"}},
    # Spam image signatures of the third-party ClamAV database: the message is refused, it is no virus
    {"bool": {"filter": [{"term": {"wazuh.rule.title": "NS8 mail virus found"}},
                         {"wildcard": {"event.reason": "*Sanesecurity.Spam*"}}]}},
]

DASHBOARD_NOISE = list(NOISE)

# The vulnerability scan finds the same CVE again at each run: the Vulnerability Detection page lists them.
# The fleet dashboard keeps them, so a critical CVE still shows in the level counts.
NOISE = NOISE + [{"prefix": {"wazuh.rule.title": "Wazuh VD - "}}]
