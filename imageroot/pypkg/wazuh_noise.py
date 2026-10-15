#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

"""Routine findings: NOISE is left out of the email, DASHBOARD_NOISE is hidden by default in the fleet dashboard."""

# Expected on an NS8 node: each rootless module has its own systemd session, and the log collector
# restarts with it. Module users and firewall changes stay in:
# installing or removing a module is rare enough to be worth a line.
# Oneshot services run by a timer log a start, a stop and sometimes a delete at each run.
TIMER_UNITS = ["promtail", "systemd-hostnamed", "dnf-makecache", "backup-timers", "phonehome", "logrotate",
               "mlocate-updatedb", "man-db-cache-update", "refresh-volume-metrics", "password-warning",
               "ns8-cluster-updater", "sssd-kcm", "droplet-agent-update"]

NOISE = [
    {"prefix": {"wazuh.rule.title": "System service stopped - user@"}},
    {"prefix": {"wazuh.rule.title": "System service started - user@"}},
    {"prefix": {"wazuh.rule.title": "System service stopped - fix-xdg-state@"}},
    {"prefix": {"wazuh.rule.title": "System service started - fix-xdg-state@"}},
    {"prefix": {"wazuh.rule.title": "System service deleted - user"}},
    {"prefix": {"wazuh.rule.title": "System service deleted - fix-xdg-state@"}},
    {"terms": {"wazuh.rule.title": [f"System service {state} - {unit}"
                                    for unit in TIMER_UNITS for state in ("started", "stopped", "deleted")]}},
    # Numbered after the module: backup12, crowdsec13-upgrade-hub
    {"wildcard": {"wazuh.rule.title": "System service st*ed - backup*"}},
    {"wildcard": {"wazuh.rule.title": "System service deleted - backup*"}},
    {"wildcard": {"wazuh.rule.title": "System service st*ed - crowdsec*-export-alerts"}},
    {"wildcard": {"wazuh.rule.title": "System service deleted - crowdsec*-export-alerts"}},
    {"wildcard": {"wazuh.rule.title": "System service st*ed - crowdsec*-upgrade-hub"}},
    {"wildcard": {"wazuh.rule.title": "System service deleted - crowdsec*-upgrade-hub"}},
    # Transient units of systemd-run
    {"wildcard": {"wazuh.rule.title": "System service st*ed - run-r*"}},
    {"wildcard": {"wazuh.rule.title": "System service deleted - run-r*"}},
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
