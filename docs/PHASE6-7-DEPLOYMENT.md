# Phase 6 and Phase 7 implementation / verification

Authoritative source: September 21 roadmap. These are implementation files, NOT completed Azure acceptance evidence.

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
4. On GitHub protect `production` environment with required reviewer and main-only deployment branch. Configure federated Azure identity subject for exact GitHub environment, assign scoped `AcrPush` on the existing registry plus permission to update ONLY target Container Apps (custom role), and set environment variables `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`. Do not add Azure client secrets. GitHub OIDC subject formats can differ for repositories created after July 15, 2026: inspect GitHub's current OIDC guidance and use exact subject claim.
5. Push CI changes to a pull request; confirm full green CI. After protected environment/identity setup merge to main; run `Deploy Azure applications` manual dispatch; approve production; verify immutable images, health, logs and monitor PostgreSQL connection.
6. Before applying `infra/app/observability.tf` to Azure, initialize against EXISTING backend, inspect `terraform state list`, `terraform plan -var='subscription_id=...' -var='image_tag=<existing-image-tag>'` and review costs/diffs. Do not apply if Terraform proposes replacement of live state or deletion. The monitor, database, and app deployment should eventually be reconciled under Terraform instead of CLI-driven drift.
7. After reviewed Terraform apply provisions Application Insights/Workbook, deploy the instrumented app SHA and confirm `APPLICATIONINSIGHTS_CONNECTION_STRING` is present on live container (do not print full value). Open Workbook and verify real data for monitor checks, incidents, AppRequests, AppExceptions, and deployment revisions. Azure Monitor logs may take time to ingest.

## Phase 6 original exit criteria not yet demonstrated

PR tests and Terraform validate pass; failed tests block deploy; GitHub OIDC works; approved main image reaches Azure and health verifies. Additionally original requirement demands Terraform remote state, reviewed plan and approved infrastructure deployment: current app-only workflow is NOT enough; reconcile Terraform ownership first.

## Phase 7 original exit criteria not yet demonstrated

An operator can correlate checker sample timestamp, monitor event and app revision, request rate/error/latency, exceptions, and recovery in an actual populated workbook. Need screenshots and a controlled outage to verify; empty workbook != completion.

## Notes

- PostgreSQL `check_results` schema is additive and written in the same transaction as incident changes; historical checks before this migration are not backfilled.
- The monitor Dockerfile now uses Linux system CA certificates with hostname verification; validate TLS in Azure after deployment. Do not commit the previous local `azure-roots.pem`; monitor image no longer depends on it.
- Azure log retention currently configured for 30 days; observed availability is sampling-based, and first measurements are available only after logging begins.
- Do not commit `.env`, `*.tfstate*`, `*.tfvars`, credentials, root certificates, database dumps or any connection string with a password.
