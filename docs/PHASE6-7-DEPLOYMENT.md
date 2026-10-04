# Historical Phase 6 and Phase 7 implementation notes

Authoritative source: September 21 roadmap. This file preserves the early
implementation audit. Current acceptance evidence supersedes its original
pending conclusions:

- [Phase 6 CI/CD acceptance evidence](ci-cd/phase6-acceptance.md)
- [Phase 7 Incident #2 evidence](incidents/incident-002.md)

## Audit findings from uploaded source

- Existing CI did not deploy to Azure. New CI runs PostgreSQL integration tests against disposable `arp_test` and validates Terraform.
- `infra/bootstrap/outputs.tf` references `azurerm_resource_group.state`, `azurerm_storage_account.state`, and `azurerm_storage_container.state`, but they do not exist in `infra/bootstrap/main.tf`. Do NOT run `terraform apply` from `infra/bootstrap` until its ownership and current Azure state are reconciled.
- `infra/app/backend.tf` needs the existing state storage account name passed as `-backend-config` during init. DO NOT create a replacement state account or initialize a new empty state against existing production resources.
- The standalone monitor Container App and Azure PostgreSQL server are currently not defined in this Terraform state. `terraform plan` must be reviewed for destructive diffs and reconciliation is outstanding.
- `az containerapp update --image` deploys current Container App revisions but creates Terraform image drift. This deploy workflow is intentionally an application-only bridge; infrastructure deployments must later be managed by Terraform with plan review, approval, and state reconciliation for original Phase 6 completion.

## Apply overlay safely

Unzip overlay into a review directory. From your project root run `python /path/to/overlay/apply_overlay.py /path/to/overlay`. The script compares original SHA256 hashes and will refuse to overwrite changed files. It backs up replaced files locally. Do not commit before reviewing changes.

## Local acceptance sequence (VS Code terminal)

1. `python -m pip install -r requirements.txt 'psycopg[binary]>=3.2,<4' pytest requests httpx`
2. Use ONLY disposable PostgreSQL database `arp_test` for `PG_TEST_DATABASE_URL`; the integration fixture truncates test tables and refuses other database names.
3. `python -m pytest -q` with `PG_TEST_DATABASE_URL` set; run `terraform fmt -check -recursive infra/app`, `terraform -chdir=infra/app init -backend=false`, `terraform -chdir=infra/app validate`.
4. Audit the live `production` environment, its main-only branch policy, OIDC
   variables, and the exact Azure role scopes. Do not infer reviewer protection
   from an `environment:` YAML line.
5. For infrastructure, use the separate trusted-main plan artifact and
   operator-dispatched exact-plan apply controls documented in the current
   Phase 6 report. Do not add Azure client secrets.
6. Before applying `infra/app/observability.tf` to Azure, initialize against EXISTING backend, inspect `terraform state list`, `terraform plan -var='subscription_id=...' -var='image_tag=<existing-image-tag>'` and review costs/diffs. Do not apply if Terraform proposes replacement of live state or deletion. The monitor, database, and app deployment should eventually be reconciled under Terraform instead of CLI-driven drift.
7. After reviewed Terraform apply provisions Application Insights/Workbook, deploy the instrumented app SHA and confirm `APPLICATIONINSIGHTS_CONNECTION_STRING` is present on live container (do not print full value). Open Workbook and verify real data for monitor checks, incidents, AppRequests, AppExceptions, and deployment revisions. Azure Monitor logs may take time to ingest.

## Phase 6 current status

**PASS.** PR validation, separate deployment, OIDC, remote state, controlled
plan/review, explicit operator approval, permissions/environment audits,
immutable deployment, failed-test blocking, healthy post-cutover verification,
and negative verifier regressions are demonstrated in the current evidence.

## Phase 7 current status

**PASS.** The populated Incident #2 correlation and its bounded limitations are
recorded in the current incident evidence package.

## Notes

- PostgreSQL `check_results` schema is additive and written in the same transaction as incident changes; historical checks before this migration are not backfilled.
- The monitor Dockerfile now uses Linux system CA certificates with hostname verification; validate TLS in Azure after deployment. Do not commit the previous local `azure-roots.pem`; monitor image no longer depends on it.
- Azure log retention currently configured for 30 days; observed availability is sampling-based, and first measurements are available only after logging begins.
- Do not commit `.env`, `*.tfstate*`, `*.tfvars`, credentials, root certificates, database dumps or any connection string with a password.
