# ns8-wazuh

A central [Wazuh](https://wazuh.com) 5 server for [NethServer 8](https://github.com/NethServer/ns8-core).

Run it on its own node, outside the clusters it watches. Wazuh agents on your servers send their logs to it. The server decodes them, raises alerts and keeps everything searchable.

The module is not ready for production. It runs Wazuh `5.0.0-rc1`. The plan and the open points are in [docs/PLAN.md](docs/PLAN.md).

## How it works

```text
 Watched servers                     NS8 node running this module
┌────────────────────┐              ┌──────────────────────────────────────┐
│ journald, files    │  1514, 1515  │ manager ───▶ indexer ◀─── dashboard│
│         │          │  1517, TLS   │              decodes,        ▲       │
│         ▼          │ ───────────▶│               raises alerts, │       │
│ wazuh-agent        │              │              stores          │       │
└────────────────────┘              └──────────────┬───────────────┼───────┘
                                                   │               │
                                                   ▼               │
                                     findings: email,          Traefik, HTTPS,
                                     Telegram, HTTPS           LDAP login
```

The agent runs on each watched server. It reads the journal, watches file changes, lists packages and checks the configuration. It sends everything to the manager over an encrypted channel.

The manager receives the lines. The Wazuh engine, in the indexer container, turns each line into fields, such as user, source IP or URL. The indexer stores it as an event. When a rule matches an event, the indexer stores a finding: that is the alert. The dashboard shows events, findings and agents.

The agent always connects to the server, never the opposite. Only the Wazuh node needs open inbound ports.

## What runs

One rootless pod with three containers: the manager, the indexer and the dashboard. Traefik publishes the dashboard over HTTPS. The module opens ports 1514, 1515 and 1517 for the agents, so only one instance can run on a node.

The node needs at least 6 GB of RAM and 50 GB of disk. At install, the volumes `wazuh-indexer-data`, `wazuh-snapshots` and `wazuh-logs` can go on an additional disk. The snapshots volume holds a copy of the indices before each backup, so keep it next to the indexer data. Set `vm.max_map_count=262144` on the node if you can. With the Rocky Linux default (65530) the indexer still works, a bit slower.

Saving the settings restarts nothing, unless the host name changed or a service is down.

## Install

    add-module ghcr.io/stephdl/wazuh:latest 1

The command prints the instance name, for example `wazuh1`.

## Configure

Run `configure-module` with:

- `host`: public host name of the dashboard. Agents connect to it. It cannot change while agents are enrolled.
- `admin_password`: password of the local `admin` account. Required the first time. 12 to 64 characters, with an uppercase letter, a lowercase letter, a digit and one of `. , _ + : @ % ^ = ~ -`.
- `lets_encrypt`: Let's Encrypt certificate for the dashboard (true/false).
- `ldap_domain`: user domain allowed to log in, OpenLDAP or Samba AD. Empty to disable.
- `ldap_admin_group`: group of that domain with the admin role.
- `ldap_readonly_group`: optional group with read-only access.
- `index_unclassified_events`: also keep the logs no decoder knows (true/false). Mostly noise, leave it off.
- `export_url`: HTTPS address that receives the new findings as JSON, every minute. Empty to disable.
- `export_token`: optional bearer token for the export.
- `notify_enabled`: email the new findings every 5 minutes (true/false). Needs a recipient.
- `notify_recipients`: addresses that receive the email.
- `notify_sender`: sender address. Empty means `wazuh@<host>`.
- `notify_min_level`: lowest level mailed: `low`, `medium` (default), `high` or `critical`.
- `retention_days`: days to keep events and findings, 30 to 3650, 365 by default.
- `telegram_token`: token of the Telegram bot, from BotFather. Omit it to keep the saved one, send `""` to remove it.
- `telegram_enabled`: turn the bot on (true/false). Off, no chat gets anything.
- `telegram_admin_enabled`: send the findings summary to the admin chat (true/false).
- `telegram_chat_id`: admin chat. A group ID like `-1001234567890`, a user ID or a public channel like `@name`.

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
  "notify_min_level": "medium",
  "retention_days": 365,
  "telegram_token": "123456789:AAH-example",
  "telegram_enabled": true,
  "telegram_admin_enabled": true,
  "telegram_chat_id": "-1001234567890"
}
EOF
```

Read the settings with `api-cli run module/wazuh1/get-configuration`.

## Add an agent

Create an enrollment token on the Agents page, or with:

```
api-cli run module/wazuh1/get-enrollment-token --data '{"max_uses":1,"group":"acme"}'
```

A token works for one day and up to `max_uses` agents (1 to 100). It holds the server address and certificate authority. Enrolled agents stay connected after it expires.

### Linux

On Debian, Ubuntu, Rocky Linux, AlmaLinux or RHEL (x86_64 or aarch64), run as root:

```
curl -fsSL https://raw.githubusercontent.com/stephdl/ns8-wazuh/main/scripts/install-agent.sh | sudo WAZUH_ENROLLMENT_TOKEN='<token>' bash
```

The Agents page gives the full command. The script installs the agent package, enrolls the agent and starts it. The server must answer on TCP 1514, 1515 and 1517, and its host name must resolve.

Options go after `bash -s --`:

- `--token-file FILE`: read the token from a file.
- `--name NAME`: agent name. Default: the FQDN, else the host name.
- `--group GROUP`: customer of the server.
- `--version VERSION`, `--package-url URL`: install another agent package.
- `--sha256 HASH`: expected package checksum. The rpm signature is always checked, a deb only with this option.
- `--no-start`: configure the agent without starting it.
- `--force`: enroll again an agent that has a key, for example after a revoke.
- `--update`: update an enrolled agent, no token needed. Not with `--force`.
- `--help`: list the options.

An NS8 node is a Linux host like any other. The agent is not an NS8 module, because it needs root on the host.

### NS8 nodes

On an NS8 node, the agent reads the journal through `/var/ossec/bin/ns8-journal`. Plain journald lines do not say which module wrote them: mail4 logs as dovecot, postfix and rspamd. ns8-journal adds the module name. The dashboards then have an Application picker.

It runs every 10 seconds and sends up to 5000 lines per run. It keeps its place in `/var/ossec/var/ns8-journal.cursor`, so no line is lost. Lines from the host system get the application `system`.

Rootcheck skips the container images on an NS8 node: their layers hold world-writable files on purpose. In an LXC container it does not scan `/dev`, where LXC keeps its own files. `--update` sets both on agents installed before.

File integrity skips `/etc/pki/ca-trust/extracted/pem/directory-hash`. A ca-certificates update rewrites every file there. The CA bundles stay watched. `--update` sets it on agents installed before.

The audit log skips the routine starts and stops of an NS8 node: the backup and metrics timers, dnf-makecache, logrotate and the root sessions. They made about 730 findings a day per node. Only a success by systemd is skipped: a failed unit, sshd, firewalld or any other unit stays in. It also skips the CrowdSec bouncer when it adds or removes a banned address in its nftables set, about 80 findings a day per node. A change to a rule or a table stays in. `--update` sets it on agents installed before.

### Uptime

The Wazuh inventory has no uptime. On every Linux host, the agent runs `/var/ossec/bin/ns8-uptime` at start and then every hour. It sends the uptime and the boot time. NS8 - Fleet shows the uptime in days and the last boot of each server. `--update` adds it to agents installed before.

### Windows and macOS

The script covers Linux only. Install the agent with the [Wazuh documentation](https://documentation.wazuh.com/current/installation-guide/wazuh-agent/index.html), then enroll it with the same token.

### Agent hardening

The server must not change what an agent runs. If someone takes over the server, they must not get root on the agents. The script turns off three Wazuh features on every agent:

- Remote configuration: `agent.remote_conf=0` in `/var/ossec/etc/local_internal_options.conf`. A shared `agent.conf` from the server could make the agent read any file as root and send it.
- Active response: `<active-response><disabled>yes</disabled>`. The module does not use it, CrowdSec already bans.
- Remote upgrade: `<agent-upgrade><enabled>no</enabled>`. The agent is updated by the script only.

`--update` sets them on agents installed before.

### Agent updates

The script does not add the Wazuh repository, so system updates leave the agent alone. This is on purpose: an agent must not be newer than its server.

The Agents page shows two tags:

- Outdated: the agent runs an older Wazuh version than the server.
- Setup outdated: the agent runs the right version, but an older script set it up. A new module release can change what the script sets on the agent, like the hardening above.

The script writes its `AGENT_SETUP` in the agent configuration, as the alias `ns8-setup:<version>` of a command that prints nothing. The agent reports its configuration at start and every hour, the module compares it with the `AGENT_SETUP` it ships. An agent installed before this has no marker and shows Setup outdated. After an update, the tag can stay up to an hour.

Contributors: raise `AGENT_SETUP` in `scripts/install-agent.sh` to the next module version whenever a change touches the agent side.

The Update command of an agent gives the command to run as root on it. It downloads the script of the module version, not main:

```
curl -fsSL https://raw.githubusercontent.com/stephdl/ns8-wazuh/<module version>/scripts/install-agent.sh | sudo bash -s -- --update --version 5.0.0-rc1
```

`--update` installs `--version`, applies the settings of the script and restarts the agent. It keeps the key and the enrollment.

#### Many agents: Ansible

The module never runs the update itself. With many agents, run the same command from Ansible, or any tool you already use. The playbook [scripts/ansible/update-agents.yml](scripts/ansible/update-agents.yml) updates 20% of the agents at a time and stops at the first failure.

```
[wazuh_agents]
web1.example.com
mail.example.com
```

```
ansible-playbook -i inventory.ini scripts/ansible/update-agents.yml \
    -e module_tag=1.2.0 -e wazuh_version=5.0.0-rc1
```

`module_tag` is the module version on the About page. `wazuh_version` is the `--version` of the Update command. When customers run different servers, set both per group in the inventory.

### Revoke an agent

On the Agents page, Revoke deletes the agent from the server. Its past events stay. The service keeps running on the host until you remove it there. To bring it back, run the script again with a new token and `--force`. The server refuses two agents with the same name, so revoke the old one first.

```
api-cli run module/wazuh1/list-agents
api-cli run module/wazuh1/remove-agent --data '{"id":"001"}'
```

## Customers

One server often watches several customers. Each token names a customer. Its agents join a Wazuh group of that name, created if missing. An agent installed by hand without `--group` goes in `default`.

The Agents page shows the customer of each agent. Every dashboard has a Customer picker. The findings email is grouped by customer, then by agent.

A customer name holds letters, digits, dots, dashes and underscores. Case matters: `acme` and `Acme` are two customers.

To move a server, use Change customer in the agent menu. The agent keeps its id. Past events keep the old customer. A customer can be removed once it has no agents.

```
api-cli run module/wazuh1/list-customers --data '{}'
api-cli run module/wazuh1/set-agent-customer --data '{"id":"001","customer":"acme"}'
api-cli run module/wazuh1/set-customer --data '{"name":"acme","zones":["@EU","CA"],"recipients":["soc@acme.example"],"telegram_enabled":true,"telegram_chat_id":"-1001234567890"}'
api-cli run module/wazuh1/remove-customer --data '{"name":"acme"}'
```

### Login zones

On the Customers page, give a customer its allowed countries or continents. A successful login from a public address outside them raises a finding. The customer recipients also get an email, and its Telegram chat a message if it has one. Each user, address and service is reported once a day.

A customer without zones is not watched. LAN and VPN logins have no country and are not checked.

| Service | User in the alert | Needs |
|---|---|---|
| Dovecot, SMTP, SSH, NS8 admin, Proxmox, SOGo | login name | nothing |
| Roundcube | email | its `log_logins` option, set since NethServer/ns8-roundcubemail#143 |
| Nextcloud | email | a log level of 1 or lower |
| WebTop | none | |

WebTop logs no client address, so its logins come from the Traefik log, without a user.

## Detection content

Wazuh downloads its decoders and rules from the Wazuh CTI service, so the node needs Internet access. They cover common Linux services, not NS8 applications. The module adds its own, in `imageroot/content/`:

| Source | Decoded lines |
|---|---|
| SSH, Dovecot, NS8 API server | logins and failures, with user and source IP |
| Postfix, Rspamd | SMTP logins, rejected mail, deliveries, spam |
| Traefik, nginx, apache | access lines: IP, method, path, status, user agent |
| CrowdSec | alerts and bans |
| Samba AD | domain logins, group, password, account and policy changes |
| SOGo, Roundcube, Nextcloud, WebTop, Matrix, Ejabberd, Mattermost | logins or failures |
| NethVoice | failed SIP, CTI and reports logins |
| Proxmox VE | logins, failures and tasks |

Twelve rules raise findings, the web scan rule is off:

| Rule | Level |
|---|---|
| NS8 authentication failure | low |
| NS8 mail authentication failure | informational: mostly password spraying from the Internet |
| NS8 CrowdSec scenario triggered | informational: the address is already banned |
| NS8 mail virus found | low |
| NS8 mail relay denied | low |
| NS8 domain account locked | medium |
| NS8 domain admin group changed | high |
| NS8 domain password reset | low |
| NS8 domain password policy changed | medium |
| NS8 web scan | off: one finding per request. NS8 - Web shows the scans |
| NS8 Proxmox guest destroyed | high |
| NS8 Proxmox backup failed | medium |
| NS8 login from outside the allowed zones | medium |

Every journal line is kept, even with no detailed decoder. The NS8 - Journal dashboard lists it.

The module loads this content at each configuration and update. To add your own:

- For a log that reaches the server: add a decoder, then a rule, in `imageroot/content/`.
- For a log the agent does not read: add a `<localfile>` block in `/var/ossec/etc/ossec.conf` on the agent, then restart it.
- For a file to watch: add it to the `<syscheck>` block of the agent.

## Dashboards

Ten dashboards, under Explore > Dashboards:

| Dashboard | Content |
|---|---|
| NS8 - Journal | every log line, like `journalctl` |
| NS8 - Logins | logins and failures on every service, with maps |
| NS8 - Web | status codes, errors, scans, with a map |
| NS8 - CrowdSec | attacks and bans, with maps |
| NS8 - Fleet | alerts by level, rule and MITRE tactic, last report and uptime per server |
| NS8 - System changes | accounts, groups, services and firewall changes |
| NS8 - Mail | sent and rejected mail, spam, viruses, source countries |
| NS8 - Directory | Samba domain logins and changes. Needs the Samba audit below |
| NS8 - Telephony | failed NethVoice logins |
| NS8 - Proxmox | Proxmox VE logins, tasks, backups, deleted guests |

Log tables load the 10000 newest lines, 50 per page. Narrow the time range to see older lines. The limit is `discover:sampleSize` in Advanced settings.

Countries and cities come from GeoIP, for public addresses only. The maps need Internet access in the browser. Logins, Web, CrowdSec and Telephony have a Country picker. To hide one country, pick it, click its filter and choose Exclude results. The Successful logins map shows a circle per city, with its name and country on hover. A click on a circle filters that city.

The dashboards are reloaded at each configuration and update. A change made in the interface is lost: clone a dashboard before you edit it.

### Samba audit

The samba module does not log logins by default. To fill NS8 - Directory, turn the audit on once on the samba node. Replace `samba1` with your instance:

```
runagent -m samba1 podman exec samba-dc sh -c 'echo "log level = 0 auth_json_audit:3 dsdb_json_audit:5 dsdb_password_json_audit:5 dsdb_group_json_audit:5" >> /etc/samba/include.conf'
runagent -m samba1 systemctl --user restart samba-dc
```

`include.conf` survives samba updates. The node needs a Wazuh agent.

To turn it off:

```
runagent -m samba1 podman exec samba-dc sed -i '/auth_json_audit/d' /etc/samba/include.conf
runagent -m samba1 systemctl --user restart samba-dc
```

## Retention

Events and findings are kept 365 days by default. Change it in Settings > Advanced, from 30 to 3650 days. Metrics stay 30 days.

A new index starts every month, or at 20 GB. An index is deleted when its newest log is older than the retention. So a log stays up to about one month more. Beyond one year, an index covers a twelfth of the retention: with 10 years, a log can stay about 10 months more.

The module writes this policy at each configuration, update and every hour. A policy changed by hand is overwritten.

Plan the disk first. Count about 20 MB a day per NS8 node, more for a busy mail or web server. For 365 days, plan about 8 GB per node, plus 20% free. Check the real rate after a few days, from the size of the `wazuh-events-v5-*` indices.

The Status page warns at 80% disk. At 95% the indexer stops writing and new logs are lost.

## LDAP login

With a user domain, the indexer checks logins through the NS8 LDAP proxy:

| Group | Indexer | Wazuh API |
|---|---|---|
| `ldap_admin_group` | `all_access` | `administrator` |
| `ldap_readonly_group` | `readall`, `kibana_user` | `readonly` |

The local `admin` account always works, even when the domain is down.

## Health

`get-health` returns the indexer state, the number of agents and the expiry of the agent certificate. The Status page shows the same.

## Findings export, email and Telegram

A timer sends the new findings: every minute to the export address, every 5 minutes by email and Telegram. It keeps a cursor, so nothing is lost when the pod stops or the endpoint is down. A finding may be sent twice, never zero times.

The export posts batches of up to 100 findings:

```
{"source": "ns8-wazuh", "host": "wazuh.domain.com", "findings": [{"_id": "...", "_index": "...", "_source": {...}}]}
```

The email goes through the cluster smarthost. It lists the findings by agent, with a count per rule:

```text
12 new findings.

r1-node1
  2 x User account kuma13 deleted
  1 x Group deleted - kuma13
```

Routine NS8 events stay out of the email: services that stop or go away without error, CrowdSec bans, vulnerabilities. Service starts are informational, so they are not mailed, but NS8 - Fleet keeps them so a new unit shows. A service that fails to start is mailed when `notify_min_level` is `low` or `medium`. A stop of firewalld, ssh, auditd, chrony, wazuh-agent or the CrowdSec service is mailed too. They all stay in the export. NS8 - Fleet hides the routine ones with the `Routine findings hidden` filter.

A file changed within 13 hours after a package install, update or removal on the same agent goes under `Files changed after a package update`, apart from the new findings. The file integrity scan runs every 12 hours, so a change from a night update shows at the next scan. The files are still listed, 10 at most. An NS8 core update is not a package update: its files stay in the new findings.

Some smarthosts refuse `wazuh@<host>`. Set `notify_sender` then.

### Telegram

One bot sends every Telegram message of the instance. The admin chat gets the same summary as the email, at the same minimum level. Each customer chat gets only its logins from outside the allowed zones. The admin summary also lists those logins, whatever the minimum level.

To set it up:

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy its token.
2. Add the bot to the admin group or channel. In a channel, make it an administrator. For a private chat, send it a message.
3. In Settings, paste the token and turn the bot on.
4. Click Find chats. It lists the chats the bot joined or got a message from during the last day. Pick one, or type its ID by hand.
5. Send a test message, then save.

For a customer, add the bot to its chat, then pick the chat on the Customers page and turn its Telegram alerts on.

Each message starts with the server name, since one chat can get the alerts of several servers. Each chat keeps its own cursor: a chat that is down retries alone, and never makes another one send twice. After more than a day down, the older findings are counted but not sent. A customer chat that refuses the bot for good is skipped.

Find chats only reads the bot updates. It does not confirm them, so a bot shared with another app keeps working. It fails if a webhook already reads them. Then type the chat ID by hand.

Removing the token turns the bot off and clears every chat ID.

```
api-cli run module/wazuh1/list-telegram-chats --data '{}'
api-cli run module/wazuh1/test-telegram --data '{"chat_id":"-1001234567890"}'
```

## Host name and certificates

Choose the host name once. Agents check it in the server certificate. `configure-module` refuses a new name while agents are enrolled.

The module creates an internal certificate authority. It signs the certificates of the indexer and of the agent ports. They last 10 years. Agents pin the authority at enrollment: a new one means every agent enrolls again. Keep the backup, it holds the key.

To issue the certificates again, the authority stays:

    api-cli run module/wazuh1/renew-certificates --data '{}'

Let's Encrypt only covers the dashboard.

## Backup

The NS8 backup covers the module. It holds a snapshot of events, findings and dashboards, plus the settings, customers, certificate authority and agent keys. The vulnerability feed, about 7 GB, is downloaded again.

A restore on another node gives back the same server. Point the DNS name to the new node: agents reconnect without a new token.

## Uninstall

    remove-module --no-preserve wazuh1

## Test

The Robot tests are in `tests/`. They install the module, enroll an agent on the same node and check the main features. The node needs Internet access.

    ./test-module.sh <leader address> ghcr.io/stephdl/wazuh:latest

To use another node of the cluster:

    ROBOT_ARGS="-v INSTALL_NODE:2 -v INSTALL_ADDR:<node address>" ./test-module.sh <leader address> <image>

The GitHub workflow runs them after each image build.
