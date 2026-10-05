# Reviewer reproduction guide

This is the entry point for an unfamiliar reviewer. The default path is local,
does not need Azure credentials, does not modify the live platform, and does not
recreate the temporary AKS lab.

## Prerequisites

- Git
- Python 3.14
- Docker with at least 4 GiB available
- Terraform 1.16.3
- curl

Helm is optional: `scripts/phase9/validate.sh` uses Helm 3.19.0 from a pinned
container tag when no local `helm` executable exists. The validation also uses
the versioned Prometheus, Alertmanager, and kubeconform images declared in the
script.

## One-command cold-review path

```bash
git clone https://github.com/amir-cs-dev/azure-reliability-platform.git
cd azure-reliability-platform
scripts/review.sh
```

The script:

1. creates an isolated temporary Python virtual environment;
2. starts a disposable PostgreSQL 16 container whose database is exactly
   `arp_test`;
3. installs `requirements-dev.txt` and runs all 87 tests, including the real
   PostgreSQL overlap/lock test;
4. creates and lists the Azure Function package;
5. builds the application and monitor images;
6. starts the application normally and verifies `/`, `/health`, `/ready`,
   and Docker health;
7. starts separate containers for `invalid_health` and `http_500` and checks
   their distinct response contracts;
8. runs format/init/validate against both Terraform roots without remote state;
9. lints/renders the Helm chart, schema-validates 21 Kubernetes resources,
   checks Prometheus configuration/rules and Alertmanager routing, and parses
   the Grafana dashboard JSON; and
10. removes all temporary containers and files, including on failure.

The final line is:

```text
PASS: fresh-review application, checker, PostgreSQL, Docker, Terraform, and Phase 9 static validation completed.
```

No webhook, Azure credential, production database, kubeconfig, or cloud
provisioning is used.

## Manual local application and fault checks

Build once:

```bash
docker build -t arp-review .
```

Normal behavior:

```bash
docker run --rm -d --name arp-normal -p 127.0.0.1:8001:8000 arp-review
curl --fail http://127.0.0.1:8001/
curl --fail http://127.0.0.1:8001/health
curl --fail http://127.0.0.1:8001/ready
docker rm -f arp-normal
```

Semantic fault: HTTP remains 200, but the required body is invalid.

```bash
docker run --rm -d --name arp-semantic -p 127.0.0.1:8002:8000 \
  -e ARP_PHASE8_FAULT=invalid_health arp-review
curl --include http://127.0.0.1:8002/health
docker rm -f arp-semantic
```

Protocol fault: the same endpoint returns controlled HTTP 500.

```bash
docker run --rm -d --name arp-http500 -p 127.0.0.1:8003:8000 \
  -e ARP_PHASE8_FAULT=http_500 arp-review
curl --include http://127.0.0.1:8003/health
docker rm -f arp-http500
```

Fault activation is environment-only. There is no unauthenticated fault-control
endpoint, and the unset production default is healthy.

## Configuration reference

| Setting | Consumer | Meaning |
|---|---|---|
| `ARP_PHASE8_FAULT` | API | Unset/healthy, `invalid_health`, or `http_500`; intended for controlled tests |
| `APP_VERSION` | API | Immutable revision label exported as telemetry |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | API | Enables Azure Monitor OpenTelemetry |
| `TARGET_URL` | Monitor/Function | Absolute health URL |
| `FAILURE_THRESHOLD` | Function | Positive consecutive-failure threshold; production uses 2 |
| `MONITOR_SCHEDULE` | Function | NCRONTAB timer schedule |
| `DATABASE_URL` | Monitor/Function | PostgreSQL DSN; a Key Vault reference in Azure |
| `WEBHOOK_URL` | Monitor/Function | Discord webhook; a Key Vault reference in Azure |
| `PG_TEST_DATABASE_URL` | Tests only | Must name the disposable `arp_test` database |

SQLite is the local default for `python -m monitor.runner` when
`DATABASE_URL` is absent. PostgreSQL is authoritative in Azure and in the
integration/concurrency tests.

## Individual validation commands

```bash
python3 -m venv .review-venv
.review-venv/bin/python -m pip install -r requirements-dev.txt

# Requires a disposable arp_test PostgreSQL database:
PG_TEST_DATABASE_URL='postgresql://USER:PASSWORD@127.0.0.1:5432/arp_test' \
  .review-venv/bin/python -m pytest tests/ -q

terraform fmt -check -recursive infra/app infra/phase9
terraform -chdir=infra/app init -backend=false -input=false
terraform -chdir=infra/app validate
terraform -chdir=infra/phase9 init -backend=false -input=false
terraform -chdir=infra/phase9 validate

scripts/phase9/validate.sh
```

The test fixture refuses to truncate a database not named `arp_test`.

For a history-aware secret scan, use a fresh clone so Docker can mount it:

```bash
docker run --rm -v "$PWD:/repo" \
  zricethezav/gitleaks:v8.24.2 \
  detect --source=/repo --no-banner --redact
```

The narrow `.gitleaks.toml` exception covers only public immutable
`reliability-api:<40-hex-git-SHA>` image tags in the two Incident #2 evidence
documents.

## Azure deployment and rollback

Cloud operations require the repository's configured GitHub variables and Azure
OIDC applications; no client secret is expected.

- **Application:** dispatch `Deploy Azure applications` from current `main`.
  It first calls the complete CI workflow, builds the commit-SHA API image,
  pushes it to the existing ACR, updates the API Container App, and runs
  `scripts/verify_deploy.py`.
- **Infrastructure:** dispatch `Terraform plan` from current `main`. Review
  `plan.txt`, `metadata.json`, hashes, source SHA, Terraform version, and
  state identity in its artifact. If and only if acceptable, separately
  dispatch `Terraform apply reviewed plan` with that run ID and literal
  `APPLY`. There is no automatic plan-to-apply edge.
- **Container Apps rollback:** identify the known-good immutable image tag and
  update the API to that exact tag, then run the same exact-revision, traffic,
  health, and readiness verification used by deployment. The retained
  [Incident #2 rollback](incidents/incident-002.md#recovery-and-rollback)
  demonstrates this path.
- **Phase 9:** Stage 1 validation is safe and local. Live creation requires a
  separately reviewed plan and explicit cost approval. Follow the
  [Phase 9 runbook](phase9/runbook.md), never the historical `infra/bootstrap`
  path. Do not recreate AKS merely to review Phase 10.

## Evidence navigation

| Question | Repository source |
|---|---|
| Current architecture and ownership | [Architecture](architecture.md) |
| Application faults and Docker | [ACT-1](phase1-application.md) |
| Checker response contract | [ACT-2](phase2-external-checker.md) |
| Function timer and identity | [ACT-4](phase4-azure-function.md) |
| Concurrent deduplication | [ACT-5](phase5-concurrency.md) |
| CI/CD and Terraform approval | [ACT-6](ci-cd/phase6-acceptance.md) |
| Incident #2 and rollback | [Incident report](incidents/incident-002.md) |
| AKS experiment | [Phase 9 live acceptance](phase9/live-acceptance.md) |
| Identities, state, and security | [Security/IaC audit](security-identity-iac.md) |
| Cost and teardown | [Cost/teardown](cost-and-teardown.md) |
| Final matrices and cold review | [Final acceptance](final-acceptance.md) |

## Reproduction boundary

The local path proves code, packaging, concurrency, fault behavior, workflow
guards, and rendered infrastructure assets without cost or outage. Historical
live cloud claims are reviewed from durable repository evidence and linked
workflow runs. The repository can recreate the isolated Phase 9 lab, but the
current persistent estate includes documented manual/external PostgreSQL and
legacy-monitor resources; it is not claimed to be a one-command greenfield
production deployment.
