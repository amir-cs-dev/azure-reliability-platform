# Azure Application Reliability & Incident Response Platform

A production-shaped reliability system that independently detects semantic
application failures, serializes durable incident state, delivers deduplicated
alerts, and demonstrates verified rollback across Azure Container Apps and a
temporary AKS observability lab.

The project is evidence-gated: **implemented → tested → demonstrated →
evidenced → PASS**. The authoritative status and final audit are in
[Phase acceptance status](docs/acceptance-status.md).

## What this system demonstrates

- A FastAPI workload with liveness, readiness, semantic health, structured
  request logs, latency metrics, and controlled configuration-only faults.
- An Azure Function timer that checks the public application independently of
  the workload and persists every check, incident transition, and notification
  in PostgreSQL.
- Thresholded incident opening, transactionally durable notification outbox
  records, PostgreSQL row-lock concurrency safety, recovery duration, retry,
  and Discord webhook delivery.
- GitHub Actions CI/CD with secretless Azure OIDC, immutable commit-tagged
  images, exact-revision cutover checks, and a failed-test deployment barrier.
- Reviewed Terraform plans and a separate, explicit, exact-plan manual apply
  boundary with SHA, configuration, artifact, age, and state-serial guards.
- Azure-native telemetry plus a reproducible, temporary AKS lab with
  Prometheus, Grafana, Alertmanager, kube-state-metrics, rolling update,
  rollback, external checking, and controlled teardown.

## Architecture

```mermaid
flowchart TB
  GH[GitHub pull request / main] --> CI[GitHub Actions CI]
  CI --> ACR[Azure Container Registry]
  CI --> CA[Azure Container Apps API]
  TF[Terraform plan<br/>manual exact-plan apply] --> CORE[Persistent Azure resources]
  ACR --> CA
  CA --> AI[Application Insights<br/>Log Analytics + Workbook]

  FN[Azure Function timer<br/>external semantic checker] -->|HTTPS /health| CA
  FN --> PG[(Azure PostgreSQL<br/>checks + incident state + outbox)]
  FN --> DISCORD[Discord webhook]
  FN --> AI

  subgraph LAB[Temporary Phase 9 lab — destroyed after evidence]
    AKS[One-node AKS Free-tier cluster] --> PODS[Digest-pinned API pods]
    PODS --> METRICS[/metrics]
    METRICS --> PROM[Prometheus]
    PROM --> GRAFANA[Grafana]
    PROM --> ALERT[Alertmanager]
    KSM[kube-state-metrics] --> PROM
    ALERT --> DISCORD
  end

  ACR -. reused by lab .-> PODS
  FN -. remained outside AKS .-> PODS
  TF -. isolated Phase 9 state .-> AKS
```

The solid core is the current persistent deployment. The dashed Phase 9 path
was deliberately small and temporary; AKS, its node resource group, workloads,
and public load balancer are gone, while sanitized live evidence and the
reproduction assets remain. See [Architecture and resource
ownership](docs/architecture.md).

## Key reliability behavior

The checker requires both HTTP 200 and the exact semantic body
`{"status":"healthy"}`. A response can therefore be HTTP-successful while the
platform correctly treats it as unhealthy. Two consecutive failures open an
incident. PostgreSQL `SELECT … FOR UPDATE` serializes concurrent monitor
executions; a unique `(incident_id, event)` constraint reinforces notification
idempotency. Continued failures update the counter without creating another
incident or opening alert. Recovery closes the one open incident, stores its
duration, and queues exactly one recovery notification.

Notifications are persisted before delivery. Webhook failures retain retryable
outbox state instead of interrupting monitoring. The deployment verifier waits
for the intended Container Apps revision to own 100% of traffic and then checks
both health endpoints six times after cutover. The Phase 9 experiment performed
a real Helm rolling update into controlled HTTP 500 responses and an actual
rollback to the recorded known-good revision.

Detailed proofs:

- [ACT-1 application and controlled-fault evidence](docs/phase1-application.md)
- [ACT-2 checker contract](docs/phase2-external-checker.md)
- [Concurrent incident-opening proof](docs/phase5-concurrency.md)
- [Incident #2 report](docs/incidents/incident-002.md)
- [Phase 9 live acceptance](docs/phase9/live-acceptance.md)

## CI/CD and infrastructure governance

Every pull request runs the complete PostgreSQL-backed Python suite, Terraform
format/init/validate for both roots, Helm/Kubernetes and observability
validation, Function packaging, both Docker builds, and a live application
container health check. Workflow actions are pinned by full commit SHA.

Application deployment is separately dispatched from `main`. A production-
environment OIDC identity can push only to the existing ACR and update only the
API Container App. Images use the source commit SHA; the post-cutover
verifier rejects the wrong revision, semantic degradation, or unstable health.

Infrastructure has no automatic plan-to-apply transition. Trusted `main`
creates a saved binary plan, human-readable summary, source/configuration/state
metadata, and hashes. A separate `workflow_dispatch` requires the reviewed run
ID and literal `APPLY`, then rejects a non-current SHA, wrong branch, tampered
or missing artifact, changed Terraform tree, stale plan, or changed state
lineage/serial. This is accurately an **operator-controlled manual approval
boundary**, not a GitHub required-reviewer environment. The complete live
control evidence is in [ACT-6](docs/ci-cd/phase6-acceptance.md).

## Incident #2

A controlled deployment returned HTTP 200 with a semantically degraded health
body. The old deploy gate sampled too early and reported green; the independent
checker reached its threshold, opened exactly one durable incident, and sent
one opening notification. Application Insights continued to report successful
HTTP requests, demonstrating that transport success did not prove semantic
health. An operator rolled back to the known-good image, after which the
checker persisted recovery and duration and delivered one recovery
notification. The verifier was then corrected and deployed.

Times, revisions, database rows, telemetry queries, bounded causal claims, and
limitations are in the [full Incident #2 report](docs/incidents/incident-002.md).

## Phase 9 controlled experiment

The approved lab used the AKS Free control plane and exactly one fixed
`Standard_D2as_v4` system node. In-cluster Prometheus scraped real application
and kube-state-metrics data; Grafana queried that datasource; Alertmanager
routed a controlled alert to Discord; and the Azure Function remained outside
AKS and independently observed the public endpoint. A controlled HTTP 500
release produced a rolling update, Prometheus alert, routed notification, and
Function incident. Helm rollback restored the known-good revision and all
signals recovered. A reviewed destroy plan then removed the lab and left its
isolated state at zero managed resources.

See the [Phase 9 overview](docs/phase9/README.md), [sanitized evidence
index](docs/phase9/evidence/README.md), and [runbook](docs/phase9/runbook.md).

## Testing

The current suite contains **87 passing tests**. It covers application and
checker units, SQLite behavior, PostgreSQL lifecycle and real concurrent
locking, notification delivery/retry, Azure Function reuse, deployment
verification, Terraform artifact guards, workflow boundaries, metrics, and
Phase 9 assets. Static gates also validate two Terraform roots, 21 rendered
Kubernetes resources, Prometheus rules/configuration, Alertmanager, Grafana,
Function packaging, and both Docker images.

The exact final matrix and failure-path coverage are in [Final acceptance](docs/final-acceptance.md).

## Reproduce locally

Prerequisites are Python 3.14, Docker, Terraform 1.16.3, Git, and curl. Helm is
optional locally because the validator uses a pinned container fallback.

```bash
git clone https://github.com/amir-cs-dev/azure-reliability-platform.git
cd azure-reliability-platform
scripts/review.sh
```

The script creates only temporary local resources and exercises the full
PostgreSQL-backed suite, both images, `/`, `/health`, `/ready`, both
controlled faults, Function packaging, Terraform, Helm/Kubernetes rendering,
Prometheus, Alertmanager, and Grafana configuration. It does not authenticate
to Azure, modify production, or provision AKS. Manual commands, configuration,
cloud procedures, and expected output are in the [Reviewer reproduction
guide](docs/reproduction.md).

## Cost and teardown

Long-lived cost drivers are the burstable PostgreSQL server and storage, one
minimum Container Apps API replica, Basic ACR, Log Analytics/Application
Insights ingestion and retention, Flex Consumption Function executions,
Function storage, and Key Vault operations. The retained legacy monitor
Container App is explicitly stopped with no active revisions or replicas. No exact monthly total is
claimed because usage and regional prices vary.

The Phase 9 lab was hourly and temporary: the Free AKS control plane, one
`Standard_D2as_v4` node, and transient load-balancer/public-IP resources. Its
measured plan envelope, estimate assumptions, and completed teardown are
documented separately from persistent costs. Follow [Cost and safe
teardown](docs/cost-and-teardown.md); never destroy `infra/app` or the shared
resource group as part of Phase 9 cleanup.

## Security and identity

The repository contains no Azure client secret, password, connection string,
Discord webhook, kubeconfig, Terraform state, binary plan, or private key.
GitHub Actions has zero repository/environment secrets; non-secret IDs live in
variables. Runtime secrets are Key Vault references. Azure access uses
repository-ID-bound GitHub OIDC identities separated across deployment,
read-oriented planning, persistent apply, and Phase 9 apply. Managed identities
handle ACR pull and Function storage/Key Vault access.

The audited role scopes, remote-state design, resource classification,
history-aware secret scan, and known privilege tradeoffs are in [Security,
identity, and IaC reconciliation](docs/security-identity-iac.md).

## Important limitations

- The external checker samples once per minute; events between samples can be
  missed, and experiment latencies are observations rather than SLAs.
- Discord evidence proves webhook acceptance (2xx), not human viewing.
- Application Insights HTTP success does not prove semantic response health.
- The persistent API uses one Container Apps replica and PostgreSQL has no HA;
  this is a portfolio-scale reliability system, not a multi-region design.
- PostgreSQL and the retained inactive legacy monitor are documented external/
  manual dependencies rather than resources in the application Terraform
  state, so the complete cloud estate is not recreated from one Terraform root.
- The Phase 9 lab was single-node, HTTP at its temporary public endpoint, and
  intentionally destroyed; it does not claim production Kubernetes HA.
- Retained Azure logs and workflow artifacts are subject to provider retention;
  sanitized evidence in the repository is the durable review record.

Additional operational tradeoffs and the complete cold-review answers are in
[Final acceptance](docs/final-acceptance.md).

## Repository map

```text
app/                 FastAPI workload and Prometheus metrics
monitor/             Checker, incident state, storage, and notification logic
azure_function/      Timer-trigger adapter reusing the monitor modules
tests/                Unit, integration, control, and regression tests
infra/app/            Persistent Terraform-managed Azure core
infra/phase9/         Isolated temporary AKS Terraform root
deploy/helm/          Phase 9 workload and observability chart
scripts/              Review, deployment verification, and Phase 9 runbooks
docs/                 Acceptance reports, operational docs, and evidence
.github/workflows/    CI, deployment, reviewed-plan, and manual-apply controls
```
