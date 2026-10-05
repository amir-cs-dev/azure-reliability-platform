# Phase 9 live acceptance evidence

Date: 2026-10-05 UTC

Verdict: **ACT-9 PASS — 14/14 REQUIREMENTS**

Only the complete final run under
[`evidence/live-20261005`](evidence/live-20261005/) is ACT-9 acceptance
evidence. Earlier interrupted runs exposed deployment and evidence-capture
defects and were not promoted or reused as a completed chain.

## Reviewed plan and apply

The D2as_v4 substitution was integrated through [PR
#21](https://github.com/amir-cs-dev/azure-reliability-platform/pull/21). Trusted
`main` plan [37235069628](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37235069628)
used source `7a89f916a1622a599bf6f92d21995f9ee03f51c3`, Terraform 1.16.3,
isolated state lineage `3fb12007-bf85-15a3-843c-a31a6157b798` serial 1,
and proposed exactly:

```text
Plan: 3 to add, 0 to change, 0 to destroy.
```

The creates were only:

- `azurerm_kubernetes_cluster.phase9`;
- `azurerm_role_assignment.aks_acr_pull`;
- `azurerm_role_assignment.operator_cluster_admin`.

The reviewed plan contained the Free control-plane tier, Kubernetes 1.35,
one fixed `Standard_D2as_v4` system node, autoscaling disabled, a 30 GiB OS
disk, Azure CNI Overlay, and the Standard load-balancer outbound model. It had
no additional pool, managed observability service, unrelated update, replace,
or destroy. The retained sanitized metadata is
[`terraform-plan-metadata.json`](evidence/live-20261005/terraform-plan-metadata.json).

Apply run
[37235294156](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37235294156)
stopped at Azure login before Terraform because GitHub emitted its newer
repository-ID-bound OIDC subject. No resource changed. The one Phase 9 apply
federation was narrowed to that observed exact `main` subject, retained in
[`apply-oidc-federation.json`](evidence/live-20261005/apply-oidc-federation.json).
The same untouched plan then passed every source, artifact, hash, state,
version, branch, and age check and was applied by run
[37235364607](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37235364607).
Its apply metadata is retained in
[`terraform-apply-metadata.json`](evidence/live-20261005/terraform-apply-metadata.json).

Post-create state serial 3 tracks exactly the cluster and two assignments; see
[`terraform-state-summary.json`](evidence/live-20261005/terraform-state-summary.json).
The live AKS and managed-node-resource inventories are
[`azure-cluster.json`](evidence/live-20261005/azure-cluster.json) and
[`azure-node-resource-inventory.json`](evidence/live-20261005/azure-node-resource-inventory.json).
They prove one D2as_v4 VMSS, two temporary Standard public IPs, one Standard
load balancer, the generated VNet/NSG, and the kubelet identity—no additional
pool or managed monitoring resource.

## Live corrections

Live execution found four bounded defects. Each fix was separately reviewed,
tested, merged after green CI, and retained in the reproducible repository:

- [PR #22](https://github.com/amir-cs-dev/azure-reliability-platform/pull/22)
  made the ACR digest lookup tolerate historical untagged manifests;
- [PR #23](https://github.com/amir-cs-dev/azure-reliability-platform/pull/23)
  preserved `runAsNonRoot` while setting image-appropriate numeric UIDs;
- [PR #24](https://github.com/amir-cs-dev/azure-reliability-platform/pull/24)
  made the bounded loader depend only on Python's standard library;
- [PR #25](https://github.com/amir-cs-dev/azure-reliability-platform/pull/25)
  refreshes and health-checks private observability port-forwards before each
  evidence window.

Post-merge CI run
[37252153780](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37252153780)
passed all 87 tests, both Terraform validations, Helm lint, all 21 strict
Kubernetes schema validations, Prometheus/Alertmanager/Grafana validation,
both Docker builds, and container health.

## Healthy baseline

The accepted run started from deployed Helm revision 5, a known-good rollback
with no fault setting. The application used immutable digest
`sha256:e4eb809c41def75713defc41afb8230b3d832dc5d17b49c2bd444df5808c0418`.
Two replicas were Ready and Available. `/`, `/health`, `/ready`, and `/metrics`
all succeeded; see the baseline response files and
[`baseline-metrics.txt`](evidence/live-20261005/baseline-metrics.txt).

The live deployment evidence in
[`kubernetes-application.json`](evidence/live-20261005/kubernetes-application.json)
shows `/ready` readiness/startup probes, `/health` liveness, the zero-downtime
`maxUnavailable: 0` / `maxSurge: 1` strategy, resource hardening, two healthy
replicas, and the digest-pinned image.

Prometheus discovered and reported UP for both API pod IPs,
kube-state-metrics, and itself. Its application query returned two `up=1`
series, and its cluster query returned two available API replicas. Evidence:

- [`prometheus-targets-baseline.json`](evidence/live-20261005/prometheus-targets-baseline.json);
- [`prometheus-app-up-baseline.json`](evidence/live-20261005/prometheus-app-up-baseline.json);
- [`prometheus-cluster-baseline.json`](evidence/live-20261005/prometheus-cluster-baseline.json).

Grafana's private datasource health API reported `Successfully queried the
Prometheus API`, its provisioned reliability dashboard was found by UID, and a
Grafana datasource query returned live request-rate data (`0.6` requests per
second). Evidence:

- [`grafana-datasource-health.json`](evidence/live-20261005/grafana-datasource-health.json);
- [`grafana-dashboard-search.json`](evidence/live-20261005/grafana-dashboard-search.json);
- [`grafana-live-query.json`](evidence/live-20261005/grafana-live-query.json).

The external Azure Function was temporarily pointed to the AKS `/health` URL.
Its natural 01:39 UTC timer execution recorded HTTP 200, `healthy: true`, zero
consecutive failures, and successful persistence in
[`external-checker-baseline.json`](evidence/live-20261005/external-checker-baseline.json).

## Controlled fault, alert, and rolling update

The loader began at 01:39:44 UTC. Helm revision 6 changed only the deployment
revision and configuration-driven fault mode to `http_500`; it retained the
same immutable image digest. The exact values are in
[`helm-fault-revision-values.json`](evidence/live-20261005/helm-fault-revision-values.json).

The real rolling update replaced known-good ReplicaSet `arp-api-7857f48c4c`
with fault ReplicaSet `arp-api-56749b85f6`. Both fault pods became Running and
Ready, while `/health` produced HTTP 500. The before/fault workload snapshots
and rollout history are retained in the evidence directory.

The bounded five-minute run made 986 requests: 480 HTTP 200 before/after the
fault boundary, 486 controlled HTTP 500 responses, and 20 expected transport
errors while unhealthy pods were restarted. See
[`load-summary.json`](evidence/live-20261005/load-summary.json).

Prometheus fired `ArpApplicationHealthEndpointFailing`. Alertmanager received
the active warning with the runbook URL and routed it to receiver
`existing-discord`. The same live Alertmanager instance reported seven Discord
notifications and zero Discord notification failures across every failure
class. Evidence:

- [`prometheus-alert-firing.json`](evidence/live-20261005/prometheus-alert-firing.json);
- [`alertmanager-alerts-firing.json`](evidence/live-20261005/alertmanager-alerts-firing.json);
- [`alertmanager-discord-notification-metrics.txt`](evidence/live-20261005/alertmanager-discord-notification-metrics.txt).

The external Function independently observed the AKS endpoint. Its natural
01:41 execution recorded the first HTTP 500; the 01:42 execution recorded the
second consecutive failure, successful persistence, and `INCIDENT_OPENED`.
See [`external-checker-fault.json`](evidence/live-20261005/external-checker-fault.json).
The Function, its database, and its Azure telemetry remained outside AKS.

## Rollback and recovery

The operator rolled back to captured known-good Helm revision 5. Helm created
deployed revision 7 with the good revision value and no fault mode; the exact
values are in
[`helm-recovered-revision-values.json`](evidence/live-20261005/helm-recovered-revision-values.json).
Fault ReplicaSet `arp-api-56749b85f6` scaled to zero, known-good ReplicaSet
`arp-api-7857f48c4c` returned to two Ready pods, and the endpoint returned
healthy. The complete history and recovered workload snapshot are retained in
[`helm-history-after-rollback.json`](evidence/live-20261005/helm-history-after-rollback.json)
and [`kubernetes-recovered.txt`](evidence/live-20261005/kubernetes-recovered.txt).

Prometheus then reported `arp_health_status=1` for both restored pods, and the
Alertmanager active-alert API returned an empty list. The external Function's
natural 01:43 execution recorded HTTP 200, zero consecutive failures,
successful persistence, and `RECOVERED`. Evidence:

- [`recovered-health.json`](evidence/live-20261005/recovered-health.json);
- [`prometheus-health-recovered.json`](evidence/live-20261005/prometheus-health-recovered.json);
- [`alertmanager-alerts-recovered.json`](evidence/live-20261005/alertmanager-alerts-recovered.json);
- [`external-checker-recovery.json`](evidence/live-20261005/external-checker-recovery.json).

Cleanup restored the Function to its original HTTPS Container Apps target;
three subsequent natural runs at 01:44, 01:45, and 01:46 UTC remained healthy
with successful persistence. See
[`external-checker-restored-target.json`](evidence/live-20261005/external-checker-restored-target.json)
and [`external-checker-post-cleanup.json`](evidence/live-20261005/external-checker-post-cleanup.json).

## Controlled teardown and reconciliation

After this complete evidence chain was merged through PR #26, the guarded
teardown removed the Helm release, `arp-phase9` namespace, and public
application Service before infrastructure deletion. Kubernetes confirmed the
namespace was absent.

The first destroy-plan run
[`37253330559`](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37253330559)
failed before creating an artifact because the read-only plan identity lacked
the AzureRM provider's required
`Microsoft.ContainerService/managedClusters/listClusterUserCredential/action`
while refreshing the live cluster. It made no infrastructure change. The
identity received only the built-in `Azure Kubernetes Service Cluster User
Role`, scoped to this temporary cluster. That role grants cluster read and the
single credential-list action; it did not grant Contributor or any wider
scope. Its assignment disappeared with the cluster, as shown in
[`plan-identity-destroy-read-scope.json`](evidence/live-20261005/plan-identity-destroy-read-scope.json).

Fresh trusted-main destroy plan
[`37253535368`](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37253535368)
used source `bc980c450401c03371b86c8aa139c5fbbbd729a9`, Terraform 1.16.3,
the unchanged infrastructure tree, and state lineage
`3fb12007-bf85-15a3-843c-a31a6157b798` serial 3. Its artifact hashes were
independently verified. The exact reviewed scope was:

```text
Plan: 0 to add, 0 to change, 3 to destroy.
```

Only `azurerm_kubernetes_cluster.phase9`,
`azurerm_role_assignment.aks_acr_pull`, and
`azurerm_role_assignment.operator_cluster_admin` were affected. There was no
shared-resource delete, create, update, or replacement. See
[`terraform-destroy-plan-metadata.json`](evidence/live-20261005/terraform-destroy-plan-metadata.json).

Separate manual apply
[`37253751373`](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37253751373)
required literal `APPLY`, reverified the exact current-main source, branch,
artifact hashes, age, and state lineage/serial, and reported `0 added, 0
changed, 3 destroyed`. The resulting state retained the same lineage at serial
5 and contains zero managed resources. Evidence:

- [`terraform-destroy-apply-metadata.json`](evidence/live-20261005/terraform-destroy-apply-metadata.json);
- [`terraform-state-after-destroy.json`](evidence/live-20261005/terraform-state-after-destroy.json);
- [`aks-after-destroy.json`](evidence/live-20261005/aks-after-destroy.json);
- [`node-resource-group-after-destroy.json`](evidence/live-20261005/node-resource-group-after-destroy.json).

The existing ACR and Container App remain provisioned successfully, and the
external Function remains enabled and running. Its `TARGET_URL` is the
original HTTPS Container Apps `/health` URL, and five natural post-destroy
timer executions remained healthy HTTP 200 with zero consecutive failures and
successful persistence. Evidence:

- [`shared-acr-after-destroy.json`](evidence/live-20261005/shared-acr-after-destroy.json);
- [`shared-container-app-after-destroy.json`](evidence/live-20261005/shared-container-app-after-destroy.json);
- [`shared-function-after-destroy.json`](evidence/live-20261005/shared-function-after-destroy.json);
- [`external-checker-target-after-destroy.json`](evidence/live-20261005/external-checker-target-after-destroy.json);
- [`external-checker-post-destroy.json`](evidence/live-20261005/external-checker-post-destroy.json).

Finally, normal plan
[`37254291825`](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37254291825)
read state serial 5 and proposed exactly the original three creates with zero
update, replace, or delete. It was retained as reconciliation evidence and was
not applied. See
[`terraform-post-destroy-plan-metadata.json`](evidence/live-20261005/terraform-post-destroy-plan-metadata.json).

## Final ACT-9 matrix

| ACT-9 requirement | Live evidence | Result |
|---|---|---|
| AKS provisioned with Terraform | Reviewed plan/apply runs, apply metadata, state summary, and Azure inventory | **PASS** |
| Kubernetes deployment | Helm revision history, immutable digest, and live workload snapshots | **PASS** |
| Readiness/liveness probes | Live deployment JSON plus two Ready/Available API replicas | **PASS** |
| Application metrics | Live `/metrics` capture with request, latency, status, and health series | **PASS** |
| Prometheus scraping real targets | Two API targets and kube-state-metrics UP; live app/cluster queries | **PASS** |
| Grafana showing real telemetry | Healthy datasource, provisioned dashboard, and live numeric query result | **PASS** |
| Alertmanager actionable alert | Active measured alert, runbook, Discord receiver, notification count, zero failures | **PASS** |
| External checker outside AKS | Natural Function baseline, two failures/incident opening, recovery, and restored target | **PASS** |
| Controlled load/deployment experiment | 986-request summary and configuration-driven fault revision | **PASS** |
| Rolling update | New revision 6 and fault ReplicaSet replaced the good ReplicaSet | **PASS** |
| Rollback | Actual rollback to revision 5 created deployed revision 7 | **PASS** |
| Monitoring/alerts/recovery | Prometheus fire/recover, Alertmanager route/clear, Function open/recover | **PASS** |
| Reproducibility | Integrated scripts/chart/Terraform plus green 87-test CI and validators | **PASS** |
| Teardown | Helm/public Service removed; exact three-delete plan applied; AKS/node resource group absent; shared services preserved; state reconciled empty | **PASS** |

All fourteen ACT-9 requirements are demonstrated. Phase 9 is **PASS**. Phase 10
has not begun.
