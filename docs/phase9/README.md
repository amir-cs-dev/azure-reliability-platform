# Phase 9 Kubernetes and deeper observability

Date: 2026-10-05 UTC

Current verdict: **LIVE ACT-9 PROVISIONING, OBSERVABILITY, FAULT, ROLLBACK,
AND RECOVERY PASS; CONTROLLED TEARDOWN OPEN**

Phase 9 is not yet PASS because the expensive temporary lab has not been torn
down. Its implementation, tests, provisioning, deployment, metrics,
Prometheus, Grafana, Alertmanager, independent Function checking, controlled
fault, rolling update, rollback, and recovery are demonstrated in the [live
acceptance report](live-acceptance.md). The resource and cost gate is in
[cost-gate.md](cost-gate.md), Stage 1 results are in
[stage1-validation.md](stage1-validation.md), and the controlled procedure is
in [runbook.md](runbook.md).

The operator approved the exact Stage 1 resource envelope. The subsequent
[Stage 2 preflight](stage2-preflight.md) found zero West US 3 DASv5-family
vCPU quota, and Azure rejected two exact 2-vCPU requests. No apply occurred and
no substitute compute was selected during that attempt. The operator then
approved the single substitution to one fixed `Standard_D2as_v4` node after
availability, matching 2-vCPU/8-GiB capacity, and sufficient DASv4-family quota
were verified. Every other envelope constraint remains unchanged.

Trusted-main plan `37235069628` and separately approved apply `37235364607`
created only the cluster and two scoped role assignments. The accepted final
experiment completed on 2026-10-05 UTC. Evidence was retained before starting
the exact-plan teardown sequence.

## Architecture

```text
Internet
  |
  +-- Azure Function semantic checker (existing, outside AKS)
  |      -> existing PostgreSQL incident state and notification outbox
  |
  +-- AKS Standard Load Balancer
         -> arp-api Service
              -> 2 FastAPI pods from one immutable ACR digest
                 /, /health, /ready, /metrics

Inside the temporary AKS namespace arp-phase9
  Prometheus -> discovers and scrapes both API pod endpoints
             -> scrapes kube-state-metrics
             -> evaluates target-down and health-5xx rules
             -> Alertmanager -> existing Discord webhook from a Kubernetes Secret
  Grafana    -> ClusterIP-only -> Prometheus -> provisioned reliability dashboard
```

The existing Azure Function remains the authoritative independent checker. It
is not moved into AKS. During the bounded experiment only, the runbook changes
its `TARGET_URL` to the AKS application's `/health` URL and restores the
original value in a cleanup handler.

## Repository implementation

- `infra/phase9` is an isolated Terraform root with remote state key
  `phase9.terraform.tfstate`. It reads the existing resource group and ACR and
  does not reference `infra/bootstrap`.
- `deploy/helm/arp-phase9` installs the application, Prometheus,
  Alertmanager, Grafana, and kube-state-metrics. Only the application Service
  is public; the observability Services are `ClusterIP`.
- `app/main.py` exposes bounded-cardinality Prometheus counters, latency
  histograms, semantic-health state, and immutable revision information at
  `/metrics`.
- `scripts/phase9` contains guarded validation, deployment, load/failure,
  rollout/rollback, evidence-capture, and teardown tooling.
- Phase 9 plan and apply workflows preserve the Phase 6 approval boundary:
  trusted `main` retains an exact plan, while a distinct manual apply requires
  its run ID and literal `APPLY`. No plan automatically applies.

## Kubernetes design

The API runs two replicas from `repository@sha256:digest`, not a mutable tag.
Its rolling strategy is `maxUnavailable: 0`, `maxSurge: 1`; startup and
readiness use `/ready`, and liveness uses `/health`. CPU/memory requests and
limits, a PodDisruptionBudget, non-root execution, dropped capabilities,
runtime-default seccomp, and a read-only root filesystem are declared.

Prometheus discovers real API endpoints through namespace-scoped Kubernetes
RBAC and scrapes kube-state-metrics for workload state. The two rules are:

- `ArpApplicationTargetDown`: a pod target is unavailable for 30 seconds;
- `ArpApplicationHealthEndpointFailing`: measured `/health` HTTP 5xx traffic
  exists and persists for 15 seconds.

Alertmanager reads the existing webhook URL from a mounted Secret file. The
secret value is obtained from the existing Key Vault at deployment time and is
never stored in Helm values, Terraform, source, or evidence. Grafana is
provisioned with a Prometheus datasource and a five-panel dashboard covering
request rate, p95 latency, health state, unavailable replicas, and 5xx ratio.
All observability storage is short-lived `emptyDir` storage; no persistent
volume or Azure managed observability service is created.

## Controlled experiment design

After an explicitly approved apply, `scripts/phase9/experiment.sh` captures a
healthy baseline, verifies Prometheus application and cluster data, asks
Grafana to execute a real query, and records the known-good Helm revision. It
then keeps bounded traffic on `/health` while a Helm upgrade creates a new
ReplicaSet using the existing immutable image digest with
`ARP_PHASE8_FAULT=http_500`. This is a real configuration-driven rolling
update, not an unchanged rollout command.

The script waits for the measured 5xx rule to fire, records Prometheus and
Alertmanager API output plus delivery counters and external-checker logs, and
performs `helm rollback` to the captured good revision. It then records the
rollout history, restored pods, endpoint health, alert state, Prometheus health
metric, and external-checker recovery. There is no public fault-control
endpoint.

The live operator must review each artifact before accepting a row. A script
running successfully is not by itself acceptance evidence.

## Stage 1 validation

The final Stage 1 evidence must retain exact command output for:

- the full Python/PostgreSQL suite and the focused Phase 9 tests;
- both Docker builds plus live container `/health`, `/ready`, and `/metrics`;
- Terraform fmt, backend-free init/validate, and the isolated remote-state
  plan;
- Helm lint and render;
- strict Kubernetes schema validation for Kubernetes 1.35;
- `promtool` config/rule validation, `amtool` config validation, and Grafana
  dashboard JSON validation;
- `actionlint`.

The local Terraform 1.16.3 plan reports exactly three direct creates: the AKS
cluster and two role assignments, with no update, replacement, or deletion.
It did not apply anything. Initializing/planning created only an empty,
non-billable state snapshot at the isolated state key (serial 1, zero tracked
resources).

## ACT-9 status before teardown

| ACT-9 requirement | Demonstrated state | Result |
|---|---|---|
| AKS provisioned with Terraform | Reviewed three-create plan and separately approved exact-plan apply | **PASS** |
| Kubernetes deployment | Digest-pinned Helm release and healthy workload inventory | **PASS** |
| Readiness/liveness probes | Live probe configuration and two Ready/Available replicas | **PASS** |
| Application metrics | Live request/latency/status/health metrics | **PASS** |
| Prometheus scraping real targets | Both API pods and kube-state-metrics UP with real query results | **PASS** |
| Grafana showing real telemetry | Datasource, dashboard, and live numeric query response | **PASS** |
| Alertmanager actionable alert | Firing measured alert routed to Discord with zero delivery failures | **PASS** |
| External checker outside AKS | Natural Function healthy/failure/open/recovery sequence | **PASS** |
| Controlled load/deployment experiment | 986 bounded requests across good/fault/recovery states | **PASS** |
| Rolling update | New fault revision and ReplicaSet replaced known-good pods | **PASS** |
| Rollback | Actual Helm rollback restored known-good revision and pods | **PASS** |
| Monitoring/alerts/recovery | Prometheus, Alertmanager, and Function all observed the chain | **PASS** |
| Reproducibility | Integrated automation plus green 87-test CI and validators | **PASS** |
| Teardown | Evidence-safe exact destroy remains to be run | **OPEN** |

No earlier Stage 1 claim was promoted to live evidence. Phase 9 becomes PASS
only after the teardown row is demonstrated and integrated.
