# Azure Reliability Platform

**Application health monitoring, persistent incident management, and automated alert delivery.**

A reliability engineering project built around a Python application and an independent monitoring service. The system detects application failures, tracks incident lifecycles, persists operational state, and delivers incident notifications through a webhook integration.

The platform is being extended with containerized deployment, infrastructure as code, and automated delivery on Microsoft Azure.

See the evidence-gated [phase acceptance status](docs/acceptance-status.md) for the current implementation, test, demonstration, and blocker state. A phase is not considered complete merely because its code exists.

## Architecture

```text
                       FastAPI Application
                         GET /health
                              |
                              v
                    Independent Health Monitor
                              |
                              v
                      Incident State Machine
                              |
                              v
                     SQLite Incident Store
                              |
                              v
                     Notification Outbox
                              |
                              v
                    Webhook Delivery System
                              |
                              v
                      External Receiver
```

The application and monitoring service are separate components. The monitor evaluates application availability without relying on the application to report its own failures.

Operational state and incident records are persisted in SQLite. Notification delivery uses a persistent outbox, allowing pending alerts to survive process restarts.

## Implemented Capabilities

### Application Health Monitoring

* FastAPI application with a dedicated health endpoint.
* Independent HTTP health checks.
* Response status, latency, and error capture.
* Configurable consecutive-failure threshold.
* Recovery detection and failure-counter reset.

### Incident Management

* Persistent monitoring state and incident history.
* Incident creation after the configured failure threshold.
* Recovery timestamps and outage-duration calculation.
* State preservation across process restarts.
* Transactional updates to incident records and notification events.

### Alert Delivery

* Durable notification records stored in SQLite.
* Webhook delivery for incident-opening and recovery events.
* Delivery-status and attempt tracking.
* Retry handling and exhausted-notification recovery.
* Event-level idempotency constraints.
* Configurable outbound webhook destination.

### Automated Verification

The test suite exercises application health checks, monitoring behavior, incident persistence, notification generation, webhook delivery, and dispatch recovery.

Additional tests cover invalid state transitions, restart behavior, duplicate prevention, and transaction rollback.

The 2026-10-04 Mission 4 audit completed with **62 passing tests**, including the PostgreSQL integration tests against a disposable local `arp_test` database. The focused application endpoint and controlled-fault suite completed with **8 passing tests**; the Terraform artifact/workflow control suite completed with **14 passing tests**.

Phase 9 extends the current suite to **87 passing tests**, including
Prometheus metrics, AKS/Helm architecture, observability assets, and the
isolated Phase 9 plan/apply controls. The same CI gate also validates both
Docker images, container health, Terraform, Helm, 21 Kubernetes resources,
Prometheus, Alertmanager, and Grafana.

## Containerization

The FastAPI application is packaged as a Docker image using a minimal Python runtime and a non-root application user.

The container includes a dedicated health check and exposes port 8000.

The image has been built and executed successfully. Local verification confirmed an HTTP 200 response from `/health` and a healthy Docker container status.

The independent monitor and its SQLite database remain outside the application container. Their deployment and persistent storage will be addressed separately.

## Reliability Validation

The platform has been exercised through controlled failure scenarios rather than relying exclusively on unit tests.

**Validated scenarios:**

| Scenario             | Verified behavior                                 |
| -------------------- | ------------------------------------------------- |
| Application failure  | Incident opens after the configured threshold     |
| Continued failure    | Existing incident remains active                  |
| Application recovery | Incident closes and recovery metrics are recorded |
| Process restart      | Monitoring state and incident history persist     |
| Webhook unavailable  | Notification remains recoverable                  |
| Webhook restored     | Pending notification is delivered                 |
| Invalid operation    | Transaction rollback preserves stored state       |

A live failure-and-recovery exercise confirmed successful delivery of both the incident-opening and recovery notifications.

Final database inspection verified that both notifications had a delivered status and no notifications remained pending.

### Incident #2 evidence

The controlled semantic-health failure, detection, Discord notification delivery, operator rollback, persisted recovery, and verifier remediation are documented in the reviewer-facing [Incident #2 report](docs/incidents/incident-002.md).

The report includes the complete ACT-7 timeline, ACT-8 rollback audit, exact deployment and revision references, Application Insights results, real notification timings, telemetry limitations, and the bounded—not overstated—revision-cutover diagnosis. Phase 7 and Phase 8 are PASS; other phases retain their explicit blockers in the acceptance-status table.

Phase 5's final concurrency requirement is closed by a [deterministic PostgreSQL overlap test and evidence report](docs/phase5-concurrency.md). The test observes the second monitor execution waiting on the production state-row lock and verifies that two overlapping threshold checks persist exactly one incident and one opening-notification record.

### Controlled application failures

ACT-1 is closed by the [Phase 1 application and Docker evidence](docs/phase1-application.md). The application supports two environment-driven fault modes without exposing a public control endpoint:

| `ARP_PHASE8_FAULT` value | `/health` result |
|---|---|
| unset | HTTP 200 `{"status":"healthy"}` |
| `invalid_health` | HTTP 200 `{"status":"degraded"}` |
| `http_500` | HTTP 500 `{"detail":"Controlled health failure"}` |

The first fault violates the semantic body contract while retaining HTTP success; the second is a distinct HTTP status failure. Normal production behavior remains the default when the variable is unset.

ACT-2 is closed by the [external checker acceptance evidence](docs/phase2-external-checker.md). The checker distinguishes transport, HTTP, and semantic failures while returning a consistent timestamp/classification/status/latency/error record.

### Authoritative monitoring service

ACT-4 is closed by the [Phase 4 Azure Function evidence](docs/phase4-azure-function.md). A thin Python timer adapter calls the existing checker, PostgreSQL incident store, state-row locking, notification queue, and alert delivery behavior. Terraform provisions the Flex Consumption Function, managed-identity-only storage, Key Vault references, and existing Application Insights integration. Three natural Azure timer executions are correlated with three durable PostgreSQL rows and structured logs while the previous Container App scheduler remains safely inactive.

### CI/CD and infrastructure approval

ACT-6 is closed by the [Phase 6 CI/CD acceptance evidence](docs/ci-cd/phase6-acceptance.md). Pull requests receive full validation, while trusted `main` produces a retained Terraform plan. Infrastructure apply is a separate manual workflow that requires the reviewed plan run ID and literal `APPLY`, verifies the exact source/configuration/state/artifact, and uses an apply-only OIDC identity. A safe refresh-only apply and live rejection/failing-test experiments demonstrate the controls without creating a production revision or outage.

### Kubernetes and deeper observability

Phase 9's one-node AKS lab and complete reliability chain are live-demonstrated
in the [Phase 9 package](docs/phase9/README.md) and [acceptance
evidence](docs/phase9/live-acceptance.md). The reviewed D2as_v4 plan created
only the isolated cluster and two role assignments. The digest-pinned Helm
deployment, probes, application metrics, in-cluster Prometheus/Grafana/
Alertmanager/kube-state-metrics, external Function checker, controlled fault,
real rolling update, actual rollback, alerts, and recovery all pass. A separate
reviewed destroy removed the Helm workloads, public service, cluster, and two
tracked role assignments; shared services survived and the isolated state now
tracks zero resources. Phase 9 is **PASS**.

## Technology Stack

| Component              | Technology                 |
| ---------------------- | -------------------------- |
| Application            | Python, FastAPI            |
| Monitoring             | Python, HTTP health checks |
| Persistence            | SQLite, PostgreSQL         |
| Testing                | pytest                     |
| Containerization       | Docker                     |
| Source control         | Git, GitHub                |
| CI                     | GitHub Actions             |
| Infrastructure as code | Terraform                  |
| Cloud platform         | Microsoft Azure            |
| Kubernetes packaging   | AKS, Helm                   |
| Deeper observability   | Prometheus, Grafana, Alertmanager |

CI, application deployment, Terraform planning, and operator-approved Terraform apply are separate workflows with explicit least-privilege permissions.

## Deployment Roadmap

**Completed**

* Application implementation and health checks.
* Independent monitoring and incident detection.
* Persistent incident management.
* Automatic webhook delivery and recovery.
* Local Docker build and health verification.
* GitHub PR validation and Azure application deployment through OIDC.
* Remote-state Terraform plan review and operator-approved exact-plan apply.

**Remaining authoritative work**

* Complete Phase 10 portfolio publication and the final ACT-0–ACT-10 audit.

**Planned**

* Performance and reliability measurement.
* AWS implementation.

## Engineering Considerations

The system separates health evaluation, incident-state transitions, persistence, and notification delivery to make individual components independently testable.

Persistent state is updated transactionally. Incident notifications are stored alongside incident records to reduce the risk of losing alerts when a process terminates or an external receiver becomes unavailable.

Webhook delivery uses bounded retry behavior. Exhausted notifications can be reset and retried without recreating incident records.

The current implementation is a development and validation platform. Production deployment requires additional controls for authentication, persistent cloud storage, monitoring, operational access, and infrastructure lifecycle management.

## Repository Structure

```text
app/                FastAPI application
monitor/            Monitoring and incident management
tests/              Automated regression tests
docs/               Architecture and operational documentation
deploy/helm/        Repeatable Phase 9 Kubernetes deployment
infra/              Isolated application and temporary AKS Terraform roots
.github/workflows/  CI configuration
Dockerfile          Application container definition
requirements.txt    Application dependencies
```

## Local Application

Build the application image:

```bash
docker build -t azure-reliability-platform .
```

Run the container:

```bash
docker run --rm -p 127.0.0.1:8001:8000 \
  azure-reliability-platform
```

Verify the health endpoint:

```bash
curl -f http://127.0.0.1:8001/health
```

Expected response:

```json
{"status":"healthy"}
```

## Project Scope

This repository demonstrates the construction and verification of a reliability system, from basic application health checks through incident persistence and automated notification delivery.

The immediate engineering objective is to extend that validated local system into a reproducible cloud deployment with automated testing, infrastructure provisioning, secure delivery, and measurable recovery behavior.

Infrastructure and operational capabilities are documented as complete only after their corresponding deployment and verification tests have succeeded.
