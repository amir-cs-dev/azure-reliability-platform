# Phase 9 live evidence index

Status: **AWAITING STAGE 2 — NO LIVE EVIDENCE YET**

Stage 1 intentionally did not provision AKS. Do not populate this directory
with claims inferred from repository configuration. After explicit approval,
retain reviewed, sanitized artifacts for:

- approved Terraform plan and apply identity/run metadata;
- post-create Azure/AKS managed-resource inventory;
- immutable application image digest and Helm release values/history;
- live application endpoint and readiness/liveness state;
- Prometheus targets and real application/cluster queries;
- Grafana datasource, dashboard, and real query response;
- Prometheus firing and resolved alert states;
- Alertmanager routed alert plus destination receipt;
- external Azure Function healthy, failure, and recovery observations;
- ReplicaSet/rolling-update progression and the bad revision;
- actual rollback to the named known-good revision and restored pods;
- bounded load summary and endpoint recovery;
- reviewed destroy plan/apply and post-destroy absence/preservation audit.

Never commit kubeconfigs, tokens, passwords, webhook URLs, Terraform binary
plans, raw Terraform state, or unredacted environment/application settings.
