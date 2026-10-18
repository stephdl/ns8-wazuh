# ns8-wazuh

A central [Wazuh](https://wazuh.com) 5 server for [NethServer 8](https://github.com/NethServer/ns8-core).

It is meant to run on its own node, outside the clusters it watches. Wazuh agents installed on servers (NS8 nodes, other Linux hosts, Windows) send their logs to it. The server decodes them, raises alerts, keeps everything searchable in the Wazuh dashboard, and can post the new findings to an HTTPS endpoint.

The module is not ready for production: it targets Wazuh `5.0.0-rc1`. The plan and the open points are in [docs/PLAN.md](docs/PLAN.md).

The work happens on the `docs-plan` branch until it is merged. Until then, replace `main` with `docs-plan` in the script address below.

## How it works

```
 Watched servers                          NS8 node running this module
 ┌──────────────────────┐                 ┌──────────────────────────────────────┐
 │ journald, files      │  1514 events    │ manager  ── decoders, rules ──┐      │
 │        ▼             │ ──────────────▶ │   ▲ API 55000 (pod only)      ▼      │
 │ wazuh-agent (deb/rpm)│  1517 enroll    │   └────── dashboard ◀──── indexer   │
 └──────────────────────┘                 └───────────────┬──────────────────────┘
                                                          │ Traefik, HTTPS
                                                          ▼
                                              Wazuh dashboard, LDAP login
```

The agent is a service installed on each watched server. It reads the system journal and the files it is told to, watches file changes (FIM), lists packages and checks the configuration (SCA). It sends everything over an encrypted channel to the manager.

The manager decodes each line into fields (user, source IP, URL...) and stores it as an event in the indexer. Rules run on these events: when one matches, the indexer stores a finding, which is the alert. The dashboard shows events, findings, agents and their inventory. The module can mail the new findings or post them to an HTTPS endpoint.

The agent always connects to the server, never the opposite: only the inbound ports of the Wazuh node must be open.

## What runs

One rootless pod with three containers: the Wazuh manager (agents, API), the indexer (data) and the dashboard (web interface). Traefik publishes the dashboard over HTTPS, always. The agents connect to the ports 1514, 1515 and 1517 of the node, which the module opens in the firewall. For this reason only one instance can run on a node.

The node needs at least 6 GB of RAM (the indexer alone takes a 2 GB heap, about 3 GB in total) and 50 GB of disk. With the default `vm.max_map_count` of Rocky Linux (65530), the indexer reads its files without memory mapping: it works, a bit slower. `vm.max_map_count=262144` on the node is better.

Saving the settings does not restart the containers, unless the host name changed or a service is down.

## Install

    add-module ghcr.io/stephdl/wazuh:latest 1

The output of the command returns the instance name, for example `wazuh1`.

## Configure

Launch `configure-module` with:

- `host`: the public host name. It is the name of the dashboard and the address the agents connect to. It cannot change while agents are enrolled.
- `admin_password`: password of the local `admin` account of the dashboard. Required the first time, then optional: it changes at once, nothing restarts. 12 to 64 characters with an uppercase letter, a lowercase letter, a digit and a symbol among `. , _ + : @ % ^ = ~ -`.
- `lets_encrypt`: request a Let's Encrypt certificate for the dashboard (true/false). The agent ports always use the internal certificate authority.
- `ldap_domain`: the user domain (OpenLDAP or Samba AD) whose users can log in to the dashboard. Empty to disable. The local `admin` account always works.
- `ldap_admin_group`: the group of that domain that gets the administrator role.
- `ldap_readonly_group`: optional group of that domain that can read alerts and agents without changing anything. Its members can still save their own dashboard views.
- `index_unclassified_events`: also keep the logs that no decoder recognizes (true/false).
- `export_url`: HTTPS address that receives the new findings as JSON, every minute. Empty to disable.
- `export_token`: optional bearer token sent to the export address. It is stored in a secret file.
- `notify_enabled`: send a summary of the new findings by email every 5 minutes (true/false). Needs at least one recipient.
- `notify_recipients`: email addresses that receive this summary. They are kept when the emails are disabled.
- `notify_sender`: sender address of these emails. Empty means `wazuh@` followed by the host name.
- `notify_min_level`: only the findings at this level or above are mailed: `low`, `medium` (default), `high` or `critical`.

Example:

```
api-cli run module/wazuh1/configure-module --data - <<EOF
{
  "host": "wazuh.domain.com",
  "lets_encrypt": true,
  "ldap_domain": "domain.com",
  "ldap_admin_group": "wazuh-admins",
  "ldap_readonly_group": "wazuh-readers",
  "admin_password": "Change.Me-2026",
  "index_unclassified_events": false,
  "export_url": "",
  "notify_enabled": true,
  "notify_recipients": ["soc@domain.com"],
  "notify_sender": "",
  "notify_min_level": "medium"
}
EOF
```

Read the settings back with `api-cli run module/wazuh1/get-configuration`.

## Add an agent

Create an enrollment token. It allows enrollment during one day, for up to `max_uses` agents (1 to 100). Enrolled agents stay connected after it expires.

```
api-cli run module/wazuh1/get-enrollment-token --data '{"max_uses":1,"group":"acme"}'
```

The same is available on the Agents page of the module. The token holds the server address and the certificate authority, so the agent needs no other setting.

### Customers

One server often watches the servers of several customers. Give the customer when you create the token: the agents enroll in a Wazuh group named after it, created when missing. The Agents page shows the customer of each agent, each `NS8 - ...` dashboard has a Customer then an Agent picker, and the findings email is grouped by customer, then by agent. Under each agent, the findings of the same kind share one line with their count, and the accounts, services, files or CVEs they are about are listed below it.

A customer can have allowed login zones, see [Login zones](#login-zones).

A customer name holds letters, digits, dots, dashes and underscores. The page lists the known customers under the field, because `acme` and `Acme` are two different customers. Without a customer the agent goes in the `default` group.

The customer is set at enrollment and cannot change after. To move a server to another customer, revoke its agent, then enroll it again with a token of the new customer and `--force`. It gets a new id, and its past events keep the old customer.

### Login zones

A customer can have allowed login zones, countries or continents, set on the Customers page. A successful login from a public address outside them raises a finding, and an email to the recipients of the customer. Each user, address and service is reported once a day. A login from a LAN or a VPN has no country and is not checked. A customer without zones is not watched.

These logins are checked:

| Service | User in the alert | Needs |
|---|---|---|
| Dovecot (IMAP, POP3) | login name | |
| SMTP authentication (Postfix) | login name | |
| SSH | login name | |
| NS8 admin interface | login name | |
| Proxmox | login name | |
| SOGo | login name | |
| Roundcube | email | its `log_logins` option, set by ns8-roundcubemail since NethServer/ns8-roundcubemail#143 |
| Nextcloud | email | a log level of 1 or lower, as Nextcloud writes its successful logins at the info level |
| WebTop | none | |

Nextcloud gives the LDAP UUID of the user. ns8-journal on the agent replaces it with the email of the user, read once with `occ user:info`, and keeps it in `/var/ossec/var/ns8-journal.users.json`. An agent installed before gets it with `--update`. WebTop logs no client address, so its logins come from the reverse proxy log and carry no user name: the alert still gives the address and the country.

### Linux

On Debian, Ubuntu, Rocky Linux, AlmaLinux or RHEL (x86_64 or aarch64), run as root:

```
curl -fsSL https://raw.githubusercontent.com/stephdl/ns8-wazuh/main/scripts/install-agent.sh | sudo WAZUH_ENROLLMENT_TOKEN='<token>' bash
```

The script installs the Wazuh 5 agent package, checks that port 1517 of the server answers, writes the server address, enrolls the agent and starts it. The agent reads the system journal by default. Pass options after `bash -s --`:

- `--token-file FILE`: read the token from a file instead of the environment.
- `--name NAME`: agent name, the host name by default.
- `--group GROUP`: customer of the server, see [Customers](#customers). The Agents page adds it to the command.
- `--version VERSION`, `--package-url URL`: install another agent package.
- `--sha256 HASH`: expected checksum of the package. The rpm signature is always checked, a deb is only checked with this option.
- `--no-start`: configure the agent without starting it.
- `--force`: enroll again an agent that already has a key, for example after it was revoked.
- `--update`: update an enrolled agent to `--version`, without a token.

The server must be reachable on TCP ports 1514, 1515 and 1517, and its host name must resolve on the agent.

### NS8 nodes and their modules

On an NS8 node the script makes the agent run `/var/ossec/bin/ns8-journal` every 10 seconds instead of reading journald itself. The Wazuh agent sends a journal line as `program[pid]: message` only, without the user or the unit that tell which module wrote it: mail4 logs as dovecot, rspamd and postfix, piler7 and piler10 both as piler-app. ns8-journal reads the new lines with `journalctl -o json`, adds the module (the owner user for a rootless module, the unit name for a rootful one) and prints one JSON line each. A cursor in `/var/ossec/var/ns8-journal.cursor` makes each run start where the last one stopped. A run sends at most 5000 lines, so a burst is sent over the next runs. A line longer than 16 KB is cut. The cursor is saved after the lines are out: a run killed in between sends them again on the next run, rather than losing them. A cursor that journalctl refuses is dropped, and the next run starts again from now. The Journal, Logins and Telephony dashboards then have an Application picker, with the NS8 modules. The other dashboards show one kind of service, so the picker would list applications that match nothing there. An agent installed before gets it with `--update`. On a host that is not an NS8 node, the agent keeps reading journald. A line without a module, from the host system of an NS8 node or from any other server, gets the application `system`, so the Program picker works on it too. Raw audit lines get the program `auditd`.

### Agent updates

The script installs one package file, it does not add the Wazuh repository. So the agent is not updated with the system packages. This is on purpose: an agent must not be newer than its server, and Wazuh 5 is a release candidate.

An agent older than its server keeps working. The Agents page tags it as Outdated, and its menu shows the command to run on it as root:

```
curl -fsSL https://raw.githubusercontent.com/stephdl/ns8-wazuh/main/scripts/install-agent.sh | sudo bash -s -- --update --version 5.0.0-rc1
```

`--update` installs the package of the server version and restarts the agent. It keeps the key and the settings, so no token is needed.

### NS8 nodes

An NS8 node is a Linux host like any other: run the same command as root on it. The agent is not shipped as an NS8 module, because it needs root on the host to read the whole journal, the packages and the files, so a module would have to run privileged.

### Revoke an agent

On the Agents page, Revoke deletes the agent from the server. It is refused at its next connection, and its past events stay in the indexer. The agent service keeps running on the host until you uninstall it there. To bring it back, create a token and run the script again with `--force`. The server refuses a second agent with the same name, so revoke the old one first.

The same with the API:

```
api-cli run module/wazuh1/list-agents
api-cli run module/wazuh1/remove-agent --data '{"id":"001"}'
```

`list-agents` also returns the server version, used by the Agents page to tag the outdated agents.

### Windows and macOS

The script covers Linux only. Install the Wazuh 5 agent following the [Wazuh documentation](https://documentation.wazuh.com/current/installation-guide/wazuh-agent/index.html), then enroll it with the same token. The token carries the server address and the certificate authority, so no other certificate is needed.

## Detection content

Wazuh downloads its decoders and rules from the Wazuh CTI service, so the node needs Internet access. They cover common Linux services (sshd, sudo, auditd, systemd...), but not the NS8 applications. The module adds its own content, in `imageroot/content/`:

| Source | Decoded fields |
|---|---|
| Dovecot login, success and failure | user, source IP |
| NS8 API server login, success and failure | user, source IP |
| Traefik access log | source IP, method, path, status |
| CrowdSec alerts | scenario, source IP |
| CrowdSec bans | scenario, source IP |

Two rules raise findings: `NS8 authentication failure` (level low) and `NS8 CrowdSec scenario triggered` (level low, CrowdSec has already banned the address). Mail spam senders (`crowdsecurity/postfix-spam`) raise no finding: thousands a day, already refused by the mail server, they stay in the NS8 - CrowdSec dashboard. The module loads them at each configuration and update, through the Content Manager API, and runs the rules every minute.

To watch something specific:

- A log that already reaches the server: add a decoder to extract its fields, then a rule on these fields, in `imageroot/content/`. The test tool of the Content Manager checks a sample line before the content is promoted.
- A log the agent does not read yet: add a `<localfile>` block in `/var/ossec/etc/ossec.conf` on the agent, then restart it. For a journald unit, filter on its name.
- A file or directory to watch for changes: add it to the `<syscheck>` block (FIM) of the agent.

Every journal line of an agent is kept, even when no decoder reads it in detail: the NS8 root decoder takes it with its program and its text, and the NS8 - Journal dashboard lists it. The decoders keep the program name of the line, as `journalctl` shows it (`pvedaemon`, `postfix/smtpd`, `samba-dc`), and put the family they recognize in `service.type` (`proxmox`, `postfix`, `samba`, `web` for the access logs). The dashboards filter on `service.type`. `index_unclassified_events` only adds the few logs that even that decoder refuses, in the `wazuh-events-v5-unclassified` index, seen in Explore > Discover. Leave it off: it is mostly noise.

## Retention

Events and findings are kept for 365 days by default. Change it in Settings > Advanced > Log retention, from 30 to 3650 days. Metrics stay 30 days.

Each stream starts a new index every month, or sooner at 20 GB. An index is deleted once its newest log is older than the retention. So the deletion runs month by month: a log stays at least the chosen time, and at most about 30 days more. With 365 days, a log is kept between one year and about 13 months. Beyond a year, the indices cover a twelfth of the retention each, so the number of indices stays under the limit of a single node: with 10 years, a log can stay about 10 months more. The module writes this in the `stream-events-policy` and `stream-findings-policy` policies of the indexer at each configuration and update, and every hour because the indexer writes back the Wazuh policies when it starts. It moves the existing indices to it. A policy changed by hand is overwritten.

Plan the disk before raising the retention. Two NS8 nodes write about 40 MB of events a day, so count about 20 MB a day per NS8 node, and more for a busy mail or web server. For 365 days, plan about 8 GB per NS8 node, plus the findings and 20% of free space. Check the real rate after a few days, from the size of the `wazuh-events-v5-*` indices.

The Status page warns once the disk of the indexer is 80% full. At 95% the indexer stops writing: the new logs are lost until space is freed. Lower the retention or add disk space before that.

## Dashboards

The module adds twelve dashboards to the Wazuh dashboard, under Explore > Dashboards:

| Dashboard | Content |
|---|---|
| NS8 - Journal | every log line, like `journalctl`. Pick a server, an application and a program, or type a word in the search bar, any case |
| NS8 - Logins | successful and failed logins on every service and server, with a map of each. The successful logins table shows who logged in from where. Click a service, such as sogo, to see only its logins |
| NS8 - Web | web traffic of every site: status codes, errors, probed paths and scanners, with a map |
| NS8 - CrowdSec | attacks detected and IP addresses banned by CrowdSec, with a map for each |
| NS8 - Fleet | alerts of every server by level, rule and MITRE tactic, and when each server last reported |
| NS8 - System changes | accounts, groups, services and firewall rules changed on the servers |
| NS8 - Mail | sent and rejected mail, spam, viruses and failed mail logins, and the countries the mail comes from, with a map |
| NS8 - Directory | Samba domain logins, failures by account and workstation, account and group changes. Needs the Samba audit below |
| NS8 - Telephony | failed SIP, CTI and reports logins of NethVoice, by source and extension |
| NS8 - Proxmox | Proxmox VE logins, virtual machine tasks, failed tasks and backups, deleted guests |

The country and the city come from the GeoIP database of the manager, so they show for public IP addresses only. The maps color each country by count, and its name shows on hover. They load the country shapes from the OpenSearch maps service, so the browser needs Internet access. The Logins, Web, CrowdSec and Telephony dashboards also have a Country picker. To see every country but one, pick it, then click its filter and choose Exclude results. The dashboards live in `imageroot/content/dashboards/` and are loaded at each configuration and update with fixed ids: a change made in the interface is lost. To customize one, clone it first.

### Samba audit

The NS8 - Directory dashboard reads the audit of the Samba domain controller: logins and their failures (LDAP, Kerberos, NTLM, SMB), group membership, password resets, created and deleted accounts, and password policy changes. The samba module does not log the logins by default, so turn the audit on once on the node that runs it. Replace `samba1` with the instance name:

```
runagent -m samba1 podman exec samba-dc sh -c 'echo "log level = 0 auth_json_audit:3 dsdb_json_audit:5 dsdb_password_json_audit:5 dsdb_group_json_audit:5" >> /etc/samba/include.conf'
runagent -m samba1 systemctl --user restart samba-dc
```

`include.conf` is meant for local settings and is kept by the samba updates. The node needs a Wazuh agent. The address in the events is the one that reached the domain controller, a local or VPN address, so the dashboard shows no country. For a Windows login, the workstation name tells where it comes from.

To turn the audit off, remove that line from `include.conf` and restart `samba-dc` the same way:

```
runagent -m samba1 podman exec samba-dc sed -i '/auth_json_audit/d' /etc/samba/include.conf
runagent -m samba1 systemctl --user restart samba-dc
```

## LDAP login

The user domain is optional. When it is set, the indexer checks the logins against it through the NS8 LDAP proxy, and the module gives the same rights on the indexer and on the Wazuh API, which the dashboard calls on behalf of the user:

| Group | Indexer | Wazuh API |
|---|---|---|
| `ldap_admin_group` | `all_access` | `administrator` |
| `ldap_readonly_group` | `readall`, `kibana_user` | `readonly` |

The local `admin` account always works, also when the user domain is down. Its password is changed from the Settings page, without restart.

## Health

`get-health` returns the state of the indexer, the number of agents and the expiry date of the agent listener certificate. The Status page shows the same.

## Findings export and email notifications

A timer of the module sends the new findings, every minute to the export address and every 5 minutes by email. It keeps a cursor, the position of the last finding sent, in `state/`. So a stopped pod, an export endpoint down or a slow detector loses nothing: the next run starts after the cursor and catches up. The cursor moves only after a successful delivery, so after a partial failure a finding can be sent twice, never zero times. It waits one minute after a finding before sending it, the time it needs to become searchable.

The cursor is not in the backup: a restored module starts from the time of the restore. Turning an output off forgets its cursor, so turning it on again does not send the backlog.

The export posts JSON batches of up to 100 findings:

```
{"source": "ns8-wazuh", "host": "wazuh.domain.com", "findings": [{"_id": "...", "_index": "...", "_source": {...}}]}
```

The email goes through the SMTP smarthost of the cluster, set in the cluster settings, with its own TLS settings. Nothing is sent when the emails are disabled or when the cluster has no smarthost. One email lists the findings at the chosen level or above, grouped by agent, with a count per rule:

```
12 new findings.

r1-node1
  2 x User account kuma13 deleted
  1 x Group deleted - kuma13
```

Some events are normal on an NS8 node and stay out of the email: the systemd sessions of the rootless modules (`user@`, `fix-xdg-state@`) and the services that a timer starts and stops at each run: `promtail`, `systemd-hostnamed`, `dnf-makecache`, `logrotate`, `phonehome`, the backups, the CrowdSec hub update and alert export, and a few more. The vulnerabilities stay out too: the scan finds the same CVE again at each run, and the Vulnerability Detection page lists them. Module users created or deleted and firewall changes are mailed, because installing or removing a module is rare. The firewall changes of the CrowdSec bouncer, one at each ban, stay out. On Proxmox, the status files and the auth key of `/etc/pve/` that the cluster rewrites every day stay out, while its configuration files stay in. The spam images that the Sanesecurity signatures of ClamAV refuse as a virus stay out too. All of them stay in the export. The NS8 - Fleet dashboard hides them with the `Routine findings hidden` filter, except the vulnerabilities: switch the filter off to see them.

Some smarthosts refuse the default sender `wazuh@` followed by the host name. Set `notify_sender` to an address they accept.

## Host name and certificates

Choose the host name once. Agents connect to it and check it in the server certificate, so changing it disconnects every agent. `configure-module` refuses a new host name while agents are enrolled. To move the server, restore the backup on the new node and point the DNS record of the same name to it.

The module creates an internal certificate authority at install time. It signs the certificates of the indexer, of the manager connector and of the agent ports (1514, 1515, 1517). The authority and these certificates last 10 years and are not renewed automatically. The agents pin the authority when they enroll: a new authority forces every agent to enroll again. Keep the backup, it holds the authority key in `state/ca`.

To issue the signed certificates again, for example after an algorithm becomes weak, run:

    api-cli run module/wazuh1/renew-certificates --data '{}'

The authority stays, so enrolled agents keep working after the pod restarts. If the server is compromised, create a new module instance and enroll the agents again.

Let's Encrypt, when enabled, only covers the dashboard behind Traefik.

## Backup

The module is backed up by the NS8 backup. Before each backup the indexer writes a snapshot of the user data (events, findings, dashboards). The backup also holds the settings, the certificate authority, the agent keys and the API configuration. It leaves out the vulnerability feed of the manager, about 7 GB, which is downloaded again. The detection content comes back by itself from the Wazuh CTI at start and from this module.

A restore or a clone on another node gives back the same server: same host name, same certificate authority, same agents and history. To move the server, restore it on the new node, then point the DNS record of the host name to it: the agents reconnect by themselves, without a new token. Only one instance can run on a node.

## Uninstall

    remove-module --no-preserve wazuh1

## Test

The Robot tests are in `tests/`. They install the module, configure it, install an agent on the same node with the script of this repository, then check the enrollment, the locked host name, `--update`, `renew-certificates`, the revocation and the removal. The node needs Internet access for the agent package.

    ./test-module.sh <leader address> ghcr.io/stephdl/wazuh:latest

To put the module and the agent on another node of the cluster, give its number and an address the test runner can reach:

    ROBOT_ARGS="-v INSTALL_NODE:2 -v INSTALL_ADDR:<node address>" ./test-module.sh <leader address> <image>

The GitHub workflow runs the same tests on a fresh Rocky Linux 9 and Debian 13 node after each image build.
