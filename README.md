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
api-cli run module/wazuh1/get-enrollment-token --data '{"max_uses":1,"description":"web server"}'
```

The same is available on the Agents page of the module. The token holds the server address and the certificate authority, so the agent needs no other setting.

### Linux

On Debian, Ubuntu, Rocky Linux, AlmaLinux or RHEL (x86_64 or aarch64), run as root:

```
curl -fsSL https://raw.githubusercontent.com/stephdl/ns8-wazuh/main/scripts/install-agent.sh | sudo WAZUH_ENROLLMENT_TOKEN='<token>' bash
```

The script installs the Wazuh 5 agent package, checks that port 1517 of the server answers, writes the server address, enrolls the agent and starts it. The agent reads the system journal by default. Pass options after `bash -s --`:

- `--token-file FILE`: read the token from a file instead of the environment.
- `--name NAME`: agent name, the host name by default.
- `--version VERSION`, `--package-url URL`: install another agent package.
- `--sha256 HASH`: expected checksum of the package. The rpm signature is always checked, a deb is only checked with this option.
- `--no-start`: configure the agent without starting it.
- `--force`: enroll again an agent that already has a key, for example after it was revoked.
- `--update`: update an enrolled agent to `--version`, without a token.

The server must be reachable on TCP ports 1514, 1515 and 1517, and its host name must resolve on the agent.

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

On the Agents page, Revoke deletes the agent from the server. It is refused at its next connection. To bring it back, create a token and run the script again with `--force`.

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

Two rules raise findings: `NS8 authentication failure` (level low) and `NS8 CrowdSec scenario triggered` (level medium). The module loads them at each configuration and update, through the Content Manager API, and runs the rules every minute.

To watch something specific:

- A log that already reaches the server: add a decoder to extract its fields, then a rule on these fields, in `imageroot/content/`. The test tool of the Content Manager checks a sample line before the content is promoted.
- A log the agent does not read yet: add a `<localfile>` block in `/var/ossec/etc/ossec.conf` on the agent, then restart it. For a journald unit, filter on its name.
- A file or directory to watch for changes: add it to the `<syscheck>` block (FIM) of the agent.

The logs that no decoder recognizes are dropped, unless `index_unclassified_events` is true.

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

Some events are normal on an NS8 node and stay out of the email: the systemd sessions of the rootless modules (`user@`, `fix-xdg-state@`) and the restarts of `promtail`, `systemd-hostnamed`, `dnf-makecache` and `backup-timers`. They stay in the dashboard and in the export. Module users created or deleted and firewall changes are mailed, because installing or removing a module is rare.

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
