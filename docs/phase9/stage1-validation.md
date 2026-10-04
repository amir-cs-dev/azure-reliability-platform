# Phase 9 Stage 1 validation evidence

Date: 2026-10-04 UTC

Scope: local/static validation and a read-only Terraform plan only. No
Terraform apply, AKS resource, Kubernetes deployment, or live ACT-9 experiment
was performed.

## Python tests

Focused command:

```bash
.venv/bin/python -m pytest \
  tests/test_metrics.py \
  tests/test_phase9_assets.py \
  tests/test_workflow_controls.py \
  tests/test_terraform_plan_artifact.py -q
```

Result:

```text
25 passed, 1 existing StarletteDeprecationWarning in 0.60s
```

Full suite command used a disposable local PostgreSQL 16 database at
`127.0.0.1:55434/arp_test` through `PG_TEST_DATABASE_URL`; the container was
stopped and automatically removed immediately afterward:

```bash
PG_TEST_DATABASE_URL='postgresql://arp_ci:<local-test-only>@127.0.0.1:55434/arp_test' \
  .venv/bin/python -m pytest tests/ -q
```

Result:

```text
85 passed, 1 existing StarletteDeprecationWarning in 1.99s
```

No PostgreSQL integration test was skipped.

## Helm and observability assets

Command:

```bash
scripts/phase9/validate.sh
```

Results:

```text
Helm 3.19.0: 1 chart linted, 0 failed
Helm render: 21 Kubernetes resources
kubeconform 0.7.0, Kubernetes 1.35 schemas:
  Valid: 21, Invalid: 0, Errors: 0, Skipped: 0
Prometheus 3.7.3 promtool:
  configuration valid; 1 rule file; 2 rules
Alertmanager 0.29.0 amtool:
  configuration valid; 1 receiver
Grafana dashboard JSON:
  valid JSON
PASS: Phase 9 Helm, Kubernetes, Prometheus, Alertmanager, and Grafana artifacts are valid.
```

The rendered resources are static evidence only. No scrape target, dashboard
series, routed alert, or pod is claimed live at Stage 1.

## Terraform

Commands:

```bash
terraform fmt -check -recursive infra/app
terraform -chdir=infra/app init -backend=false -input=false
terraform -chdir=infra/app validate
terraform fmt -check -recursive infra/phase9
terraform -chdir=infra/phase9 init -backend=false -input=false
terraform -chdir=infra/phase9 validate
```

Result: both roots formatted and valid with Terraform 1.16.3 and AzureRM
5.6.0.

The final remote-state plan used the active Azure CLI session and explicit
`subscription_id` and operator object-ID variables:

```bash
terraform -chdir=infra/phase9 plan \
  -input=false -lock-timeout=60s -detailed-exitcode \
  -out=/tmp/arp-phase9-stage1-final.tfplan -no-color
```

Result:

```text
Terraform detailed exit code: 2
Plan: 3 to add, 0 to change, 0 to destroy.

azurerm_kubernetes_cluster.phase9                    [create]
azurerm_role_assignment.aks_acr_pull                 [create]
azurerm_role_assignment.operator_cluster_admin       [create]
```

The isolated state snapshot has lineage
`3fb12007-bf85-15a3-843c-a31a6157b798`, serial 1, and zero resources. Planning
created only this non-billable state metadata. The saved binary plan remains
outside the repository and must never be committed or used as a substitute for
the final trusted-`main` workflow artifact.

Read-only Azure preflight returned `NotRegistered` for
`Microsoft.ContainerService`, `Microsoft.Compute`, and `Microsoft.Network`, an
empty result for the planned cluster name, and `false` for existence of the
planned node resource group. No provider was registered and no Azure resource
was created. Registration and quota verification are explicit post-approval
prerequisites in the Stage 2 runbook.

## Docker

Commands:

```bash
docker build -t reliability-platform:phase9-stage1 .
docker build -f Dockerfile.monitor \
  -t reliability-monitor:phase9-stage1 .
docker run -d --rm --name arp-phase9-app-health \
  -p 127.0.0.1:18009:8000 reliability-platform:phase9-stage1
```

Results from the application container:

```text
Docker health state: healthy
GET /       -> 200 {"message":"Azure Reliability Platform is running"}
GET /health -> 200 {"status":"healthy"}
GET /ready  -> 200 {"status":"ready"}
GET /metrics -> 200 and includes:
  arp_http_requests_total
  arp_http_request_duration_seconds
  arp_health_status
  arp_application_info
```

Both image builds passed. The demonstration container was stopped and removed.

## Workflow and script checks

Commands:

```bash
bash -n scripts/phase9/validate.sh scripts/phase9/deploy.sh \
  scripts/phase9/experiment.sh scripts/phase9/teardown.sh
python3 -m py_compile app/main.py scripts/phase9/load.py \
  scripts/terraform_plan_artifact.py
actionlint -color
```

Results: shell syntax, Python compilation, and actionlint 1.7.12 all passed.
The deployment, experiment, apply, and teardown scripts were not executed.
