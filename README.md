# ns8-wazuh

A central [Wazuh](https://wazuh.com) 5 server for [NethServer 8](https://github.com/NethServer/ns8-core).

It is meant to run on its own node, outside the clusters it watches. Wazuh agents installed on servers (NS8 nodes, other Linux hosts, Windows) send their logs to it. The server decodes them, raises alerts, keeps everything searchable in the Wazuh dashboard, and can post the new findings to an HTTPS endpoint.

The module is not ready for production: it targets Wazuh `5.0.0-rc1`. The plan and the open points are in [docs/PLAN.md](docs/PLAN.md).

## What runs

One rootless pod with three containers: the Wazuh manager (agents, API), the indexer (data) and the dashboard (web interface). Traefik publishes the dashboard over HTTPS, always. The agents connect to the ports 1514, 1515 and 1517 of the node, which the module opens in the firewall. For this reason only one instance can run on a node.

The node needs `vm.max_map_count=262144`, 4 to 6 GB of RAM and 50 GB of disk.

## Install

    add-module ghcr.io/stephdl/wazuh:latest 1

The output of the command returns the instance name, for example `wazuh1`.

## Configure

Launch `configure-module` with:

- `host`: the public host name. It is the name of the dashboard and the address the agents connect to.
- `lets_encrypt`: request a Let's Encrypt certificate for the host (true/false).
- `ldap_domain`: the user domain whose users can log in to the dashboard. Empty to disable.
- `ldap_admin_group`: the group of that domain that gets the administrator role.
- `index_unclassified_events`: also keep the logs that no decoder recognizes (true/false).
- `export_url`: HTTPS address that receives the new findings as JSON. Empty to disable.
- `export_token`: optional bearer token sent to the export address. It is stored in a secret file.

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

Create an enrollment token, valid for a limited time and a limited number of agents:

```
api-cli run module/wazuh1/get-enrollment-token --data '{"ttl":"1h","max_uses":1,"description":"web server"}'
```

The same is available on the Agents page of the module. The token holds the server address and the certificate authority, so the agent needs no other setting.

## Health

`get-health` returns the state of the indexer, the number of agents and the expiry date of the agent listener certificate. The Status page shows the same.

## Backup

The module is backed up by the NS8 backup. Before each backup the indexer writes a snapshot of the user data (events, findings, dashboards). The detection content comes back by itself from the Wazuh CTI at start and from this module. Restoring a module also restores the snapshot.

## Uninstall

    remove-module --no-preserve wazuh1

## Test

The Robot tests are in `tests/`. They need a node and the image URL:

    ./test-module.sh <node address> ghcr.io/stephdl/wazuh:latest
