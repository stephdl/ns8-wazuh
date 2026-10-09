# ns8-wazuh

A central [Wazuh](https://wazuh.com) 5 server for [NethServer 8](https://github.com/NethServer/ns8-core).

It is meant to run on its own node, outside the clusters it watches. Wazuh agents installed on servers (NS8 nodes, other Linux hosts, Windows) send their logs to it. The server decodes them, raises alerts, keeps everything searchable in the Wazuh dashboard, and can post the new findings to an HTTPS endpoint.

The module is not ready for production: it targets Wazuh `5.0.0-rc1`. The plan and the open points are in [docs/PLAN.md](docs/PLAN.md).

## What runs

One rootless pod with three containers: the Wazuh manager (agents, API), the indexer (data) and the dashboard (web interface). Traefik publishes the dashboard over HTTPS, always. The agents connect to the ports 1514, 1515 and 1517 of the node, which the module opens in the firewall. For this reason only one instance can run on a node.

The node needs `vm.max_map_count=262144`, at least 6 GB of RAM (the indexer alone takes a 2 GB heap, about 3 GB in total) and 50 GB of disk.

## Install

    add-module ghcr.io/stephdl/wazuh:latest 1

The output of the command returns the instance name, for example `wazuh1`.

## Configure

Launch `configure-module` with:

- `host`: the public host name. It is the name of the dashboard and the address the agents connect to.
- `lets_encrypt`: request a Let's Encrypt certificate for the dashboard (true/false). The agent ports always use the internal certificate authority.
- `ldap_domain`: the user domain whose users can log in to the dashboard. Empty to disable.
- `ldap_admin_group`: the group of that domain that gets the administrator role.
- `ldap_readonly_group`: optional group of that domain that can read alerts and agents without changing anything.
- `index_unclassified_events`: also keep the logs that no decoder recognizes (true/false).
- `export_url`: HTTPS address that receives the new findings as JSON. Empty to disable.
- `export_token`: optional bearer token sent to the export address. It is stored in a secret file.
- `notify_recipients`: email addresses that receive a summary of the new findings every 5 minutes. Empty to disable.
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
  "index_unclassified_events": false,
  "export_url": ""
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

The script installs the Wazuh 5 agent package, checks that port 1517 of the server answers, writes the server address, enrolls the agent and starts it. Pass options after `bash -s --`:

- `--token-file FILE`: read the token from a file instead of the environment.
- `--name NAME`: agent name, the host name by default.
- `--version VERSION`, `--package-url URL`: install another agent package.
- `--sha256 HASH`: expected checksum of the package. The rpm signature is always checked, a deb is only checked with this option.
- `--no-start`: configure the agent without starting it.
- `--force`: enroll again an agent that already has a key, for example after it was revoked.

The server must be reachable on TCP ports 1514, 1515 and 1517, and its host name must resolve on the agent.

### Windows and macOS

The script covers Linux only. Install the Wazuh 5 agent following the [Wazuh documentation](https://documentation.wazuh.com/current/installation-guide/wazuh-agent/index.html), then enroll it with the same token. The token carries the server address and the certificate authority, so no other certificate is needed.

## Health

`get-health` returns the state of the indexer, the number of agents and the expiry date of the agent listener certificate. The Status page shows the same.

## Email notifications

The module sends the new findings by email through the SMTP smarthost of the cluster, set in the cluster settings. Without a smarthost or without recipients, nothing is sent. Every 5 minutes, one email lists the findings of the last 5 minutes at the chosen level or above. When the smarthost changes, the module applies it at once.

The SMTP password is kept in the keystore of the indexer, never in the module environment. The indexer always checks the TLS certificate of the smarthost, even when the cluster setting disables the check.

## Host name and certificates

Choose the host name once. Agents connect to it and check it in the server certificate, so changing it disconnects every agent. `configure-module` refuses a new host name while agents are enrolled. To move the server, restore the backup on the new node and point the DNS record of the same name to it.

The module creates an internal certificate authority at install time. It signs the certificates of the indexer, of the manager connector and of the agent ports (1514, 1515, 1517). The authority and these certificates last 10 years and are not renewed automatically. The agents pin the authority when they enroll: a new authority forces every agent to enroll again. Keep the backup, it holds the authority key in `state/ca`.

To issue the signed certificates again, for example after an algorithm becomes weak, run:

    api-cli run module/wazuh1/renew-certificates --data '{}'

The authority stays, so enrolled agents keep working after the pod restarts. If the server is compromised, create a new module instance and enroll the agents again.

Let's Encrypt, when enabled, only covers the dashboard behind Traefik.

## Backup

The module is backed up by the NS8 backup. Before each backup the indexer writes a snapshot of the user data (events, findings, dashboards). The detection content comes back by itself from the Wazuh CTI at start and from this module. Restoring a module also restores the snapshot.

## Uninstall

    remove-module --no-preserve wazuh1

## Test

The Robot tests are in `tests/`. They need a node and the image URL:

    ./test-module.sh <node address> ghcr.io/stephdl/wazuh:latest
