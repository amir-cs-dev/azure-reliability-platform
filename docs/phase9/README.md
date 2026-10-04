# Phase 9 Kubernetes and deeper observability

Date: 2026-10-04 UTC

Current verdict: **IMPLEMENTED AND STATICALLY VALIDATED; D2AS_V4 PROVISIONING
APPROVED; FRESH PLAN AND LIVE ACCEPTANCE OPEN**

Phase 9 is not PASS. Stage 1 deliberately stopped before an AKS apply. The
authoritative sequence remains implemented, tested, demonstrated, evidenced,
then PASS. The resource and cost gate is in [cost-gate.md](cost-gate.md), the
exact Stage 1 results are in [stage1-validation.md](stage1-validation.md), the
controlled live procedure is in [runbook.md](runbook.md), and live evidence
must be added under [evidence/](evidence/) during Stage 2.

The operator approved the exact Stage 1 resource envelope. The subsequent
[Stage 2 preflight](stage2-preflight.md) found zero West US 3 DASv5-family
vCPU quota, and Azure rejected two exact 2-vCPU requests. No apply occurred and
no substitute compute was selected during that attempt. The operator then
approved the single substitution to one fixed `Standard_D2as_v4` node after
availability, matching 2-vCPU/8-GiB capacity, and sufficient DASv4-family quota
were verified. Every other envelope constraint remains unchanged.

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

## ACT-9 status after Stage 1

| ACT-9 requirement | Stage 1 state | Result |
|---|---|---|
| AKS provisioned with Terraform | Terraform and exact plan exist; no apply authorized | **OPEN — LIVE** |
| Kubernetes deployment | Helm chart renders and validates | **OPEN — LIVE** |
| Readiness/liveness probes | Declared and statically validated | **OPEN — LIVE** |
| Application metrics | Implemented and locally tested | **OPEN — LIVE** |
| Prometheus scraping real targets | Discovery/config validated only | **OPEN — LIVE** |
| Grafana showing real telemetry | Provisioning/dashboard validated only | **OPEN — LIVE** |
| Alertmanager actionable alert | Rules/route validated only | **OPEN — LIVE** |
| External checker outside AKS | Existing Function preserved; switch tooling not run | **OPEN — LIVE** |
| Controlled load/deployment experiment | Guarded tooling implemented, not run | **OPEN — LIVE** |
| Rolling update | Real revision-change procedure designed, not run | **OPEN — LIVE** |
| Rollback | Actual Helm rollback procedure designed, not run | **OPEN — LIVE** |
| Monitoring/alerts/recovery | Evidence capture designed, no live evidence | **OPEN — LIVE** |
| Reproducibility | Repository instructions and controls implemented | **OPEN — LIVE** |
| Teardown | Exact destroy workflow/procedure implemented, not demonstrated | **OPEN — LIVE** |

No row is marked PASS from Stage 1 repository evidence alone.
