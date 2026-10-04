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

## Pull request and trusted-main evidence

[PR #18](https://github.com/amir-cs-dev/azure-reliability-platform/pull/18)
used implementation commit `131fbcadab753c2a3035d26977ad1e6ae9b49cfe`.
Its [validation run
37219575396](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37219575396)
was green before merge. The PR merged as
`a15ad3912b723ed986f3329b97f7c1e7c39e0532`.

The [post-merge CI run
37219716454](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37219716454)
was green. Its hosted logs record 85 passed tests, 21/21 valid Kubernetes
resources, two valid Prometheus rules, successful observability validation,
both Docker builds, and a healthy application container. The existing
application [Terraform plan run
37219716656](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37219716656)
also remained green after the shared plan-control extension.

The isolated [trusted-main Phase 9 plan run
37219716637](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37219716637)
completed successfully from merge source
`a15ad3912b723ed986f3329b97f7c1e7c39e0532`. Retained artifact
`phase9-terraform-plan-37219716637` has GitHub artifact digest
`sha256:58fbbb12101240643c981c189c4f72272cc7d0a426cd856e86f9421b1d29658b`
and expires after its deliberate seven-day review window.

Its metadata records Terraform 1.16.3, operation `normal`, exact `main` ref and
source SHA, infrastructure tree
`777853d76588001a5ae29d7036925703a2f37603`, isolated state lineage
`3fb12007-bf85-15a3-843c-a31a6157b798` serial 1, and:

```text
create: 3
read: 0
update: 0
replace: 0
delete: 0
```

The affected addresses are exactly the cluster and two role assignments listed
above. The retained binary-plan SHA-256 is
`06ddc32abde504111ad09f25e0af71082b7a3e10a61800971de1edff1aebeedb`;
the redacted plan-text SHA-256 is
`41ddab10520127d5b4c9dcba390858e41d59488f08f6322f9ffc3ce69323309c`.

No apply workflow was dispatched. This evidence-only documentation update
advances `main`, deliberately making run `37219716637` ineligible for apply
under the current-main SHA control. After explicit approval and provider/
identity prerequisites, Stage 2 must generate and review a fresh plan.
