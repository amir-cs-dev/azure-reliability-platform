# Phase 9 live evidence index

Status: **COMPLETE ACT-9 CHAIN AND CONTROLLED TEARDOWN RETAINED**

The reviewed and sanitized final-run artifacts are under
[`live-20261005`](live-20261005/). Their interpretation and the exact
final matrix are in the [live acceptance report](../live-acceptance.md).
Only that complete run is acceptance evidence. Earlier interrupted diagnostic
runs were not imported.

The retained evidence covers:

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
- reviewed create plan/apply and live state reconciliation;
- reviewed destroy plan/apply, post-destroy absence and shared-resource
  preservation, healthy external checking, zero-resource state, and the
  unapplied three-create reconciliation plan.

Never commit kubeconfigs, tokens, passwords, webhook URLs, Terraform binary
plans, raw Terraform state, or unredacted environment/application settings.
