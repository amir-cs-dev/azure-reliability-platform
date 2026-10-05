# Phase 9 live acceptance evidence

Date: 2026-10-05 UTC

Verdict: **LIVE PROVISIONING, OBSERVABILITY, FAULT, ROLLING UPDATE, ROLLBACK,
AND RECOVERY PASS; CONTROLLED TEARDOWN REMAINS OPEN**

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

## ACT-9 matrix before teardown

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
| Teardown | Evidence-safe destroy has not yet run | **OPEN** |

Phase 9 remains OPEN until the Helm workloads and LoadBalancer are removed,
an exact current-main destroy plan deletes only the three isolated Phase 9
resources, that plan is separately applied, and shared-resource survival plus
zero-resource state are demonstrated.
