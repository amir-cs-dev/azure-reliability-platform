# Azure Reliability Platform

**Application health monitoring, persistent incident management, and automated alert delivery.**

A reliability engineering project built around a Python application and an independent monitoring service. The system detects application failures, tracks incident lifecycles, persists operational state, and delivers incident notifications through a webhook integration.

The platform is being extended with containerized deployment, infrastructure as code, and automated delivery on Microsoft Azure.

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

The latest verified local test run completed with **34 passing tests**.

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

## Technology Stack

| Component              | Technology                 |
| ---------------------- | -------------------------- |
| Application            | Python, FastAPI            |
| Monitoring             | Python, HTTP health checks |
| Persistence            | SQLite                     |
| Testing                | pytest                     |
| Containerization       | Docker                     |
| Source control         | Git, GitHub                |
| CI                     | GitHub Actions             |
| Infrastructure as code | Terraform                  |
| Cloud platform         | Microsoft Azure            |

CI configuration has been added to the repository. Successful execution on GitHub and Azure deployment remain separate verification milestones.

## Deployment Roadmap

**Completed**

* Application implementation and health checks.
* Independent monitoring and incident detection.
* Persistent incident management.
* Automatic webhook delivery and recovery.
* Local Docker build and health verification.

**In progress**

* GitHub Actions pipeline verification.
* Terraform infrastructure configuration.
* Azure application deployment.
* Secure deployment authentication.

**Planned**

* Cloud observability and operational dashboards.
* Deployment rollback and recovery testing.
* Kubernetes deployment with AKS.
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
