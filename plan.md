# Plan: make configure-module faster

Status: findings only, nothing is implemented yet.

## Measures

Measured on wazuh1 (image 1.0.5) on 2026-10-20, from the agent journal.

A configure-module that changes nothing and does not restart the services takes 80 s:

| Step | Time |
|---|---|
| 01 to 86 | 10 s |
| 90provision_content | 70 s |

Inside 90provision_content:

| Part | Time | Why |
|---|---|---|
| 38 decoders | 23 s | one `find_draft` then one `PUT` each, about 0.6 s per decoder |
| 12 rules | 12 s | same, about 1 s per rule |
| promotion | 13 s | draft to test, then test to custom |
| detector and retention | 4 s | |
| dashboards | 15 s | 10 bulk creates, the settings and the mapping |

A configure-module that restarts the services takes 4 min:

| Step | Time |
|---|---|
| 80start_services | 64 s |
| 85setup_ldap | 26 s |
| 86set_admin_password | 15 s |
| 90provision_content | 114 s |

Every indexer call goes through `podman exec curl` and costs 0.3 to 0.5 s. Most of the time is spent writing content that did not change.

## Checks done on wazuh1

All of them were read only.

Decoders: one `_search` on `wazuh-threatintel-decoders` in the draft space returns the 38 decoders in 0.31 s. Each stored document equals the resource of its file once `id`, `metadata.date` and `metadata.modified` are removed.

Rules: the 12 stored rules equal their files once `id`, `metadata.date`, `metadata.modified` and `metadata.supports` are removed. The server adds `supports` with the value `[]`. It must be compared as `[]` when the file does not set it, not ignored, or a future change of `supports` in a file would never be applied.

No duplicate, no missing item and no extra item in the draft space.

KVDB of the login zones: `write_kvdb()` writes it on every run. The stored content already equals `kvdb_content(load())`. Same volatile fields as the rules. A real zone change goes through its own action, which calls `promote()`, so that path does not change.

Draft policy: the body that provision-content sends equals the stored policy for `root_decoder`, `integrations`, `filters`, `enrichments`, `enabled`, `index_unclassified_events`, `index_discarded_events` and the metadata fields we send. The standard policy is already written only when `index_unclassified_events` changes.

Promotion: with nothing written, `GET promote?space=draft` and `GET promote?space=test` both return no pending change, so `promote()` already stops at "nothing to promote".

Detector: the stored ns8 detector matches the body we send. The 12 wanted rule ids equal the stored `custom_rules`, and `enabled`, `schedule`, `indices` and `triggers` are the same. The server adds its own fields (`monitor_id`, `last_update_time`, `workflow_ids` and others), so only our fields must be compared.

## Changes to make

### 1. provision-content: write only what differs

Read all draft decoders, rules and KVDBs with one `_search` per index (`size: 500`) instead of one `find_draft` per item. Compare each file with the stored document after removing the volatile fields. Send the `PUT` only when they differ, and the `POST` only when the item is missing. Do the same for the KVDB in `write_kvdb()` and for the draft policy.

When nothing is written, the promotion finds nothing to promote. Expected gain: about 45 s.

### 2. provision-detector: update only when needed

Compare `inputs`, `enabled`, `schedule` and `triggers` of the stored detector with the body. Send the `PUT` only when they differ. Keep `--recreate` as it is. This also avoids rebuilding the monitors of the detector on each run. Comparing `enabled` keeps today's behavior of turning a detector back on when someone disabled it.

### 3. provision-dashboards: skip unchanged dashboards

Send all ndjson files in one `_bulk_create` instead of one per file. Skip it when a hash of the files equals the hash of the last load. Keep the settings and the mapping on every run, they take about 3 s. Expected gain: about 12 s.

[restore-snapshot](imageroot/bin/restore-snapshot) deletes `.kibana_*` and restores the copy of the backup, so a stored hash can lie after a restore. Either check that one object exists with a `GET` before skipping, or remove the hash file in restore-snapshot.

Decision needed: today a dashboard edited by hand is overwritten on every configure. After this change it is overwritten only when the module ships new dashboards.

## Risks

A comparison that says "equal" by mistake would never apply a change of a file. This is the only real danger, so remove only the fields listed above and compare everything else.

If the server rewrites a document on save, the comparison always says "different". The gain is lost but nothing breaks.

A promotion that failed on the previous run leaves the draft up to date and the custom space behind. `promote()` compares the spaces on its own, so it still pushes the change.

## Tests

Configure with no change: check the journal shows no decoder, rule or KVDB write, "nothing to promote" for both spaces, and the run time.

Change one decoder file and configure: check the change reaches the custom space and the engine uses it.

Change a rule: check the detector gets the new rule id.

Restore a backup, then configure: check the dashboards are there.

## Later

The restart path (64 s in 80start_services, 26 s in 85setup_ldap waiting for the Wazuh API) is not covered here.
