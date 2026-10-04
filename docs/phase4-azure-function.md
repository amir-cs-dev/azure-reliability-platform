# Phase 4 Azure Function acceptance

Date: 2026-10-04 UTC

Current verdict: **OPEN — live Azure demonstration pending**

This document begins the durable evidence record for the authoritative Python
timer-triggered Azure Function architecture. It must not be read as a PASS
until the final ACT-4 matrix contains live scheduled-run, persistence, and log
evidence for every row.

## Architecture

The Function is a thin adapter in `azure_function/function_app.py`. Its timer
entry point parses configuration and invokes `monitor.runner.run_monitor_once`.
That shared function uses the original `monitor.checker.check_health`, existing
PostgreSQL/SQLite stores, transactional incident state, notification queue, and
webhook delivery. There is no second checker or incident-state implementation.

The timer binding uses `%MONITOR_SCHEDULE%`, `run_on_startup=False`, and
`use_monitor=True`. The intended Azure setting is `0 * * * * *`, one execution
per minute in UTC. Startup does not create unscheduled business executions.

Structured application logs distinguish:

- `scheduled_monitor_started`, including invocation time, past-due state, and
  the non-secret checked endpoint;
- `scheduled_monitor_completed`, including health/status, latency, lifecycle
  event, consecutive failures, and `persistence=succeeded`;
- `scheduled_monitor_failed`, containing only the exception type and no secret
  values.

## Terraform resource inventory

The implementation uses the supported AzureRM
`azurerm_function_app_flex_consumption` resource and reuses the existing
resource group, Application Insights instance, Log Analytics workspace,
external API, and PostgreSQL server.

Flex Consumption declares Python through the resource's first-class
`runtime_name` and `runtime_version` properties. It rejects the legacy
`FUNCTIONS_WORKER_RUNTIME` app setting, so that setting is intentionally absent.
Flex also runs from its managed deployment package by default; the legacy
`WEBSITE_RUN_FROM_PACKAGE` setting is intentionally absent.

| Terraform address | Purpose |
|---|---|
| `azurerm_function_app_flex_consumption.monitor` | Python 3.12 timer Function, maximum one 512-MB instance |
| `azurerm_service_plan.function` | Linux Flex Consumption (`FC1`) hosting plan; no always-ready instance |
| `azurerm_storage_account.function` | Key-disabled Standard LRS host/deployment storage |
| `azurerm_storage_container.function_releases` | Private managed package deployment container |
| `azurerm_user_assigned_identity.function` | Secretless Function-to-storage identity |
| `azurerm_role_assignment.function_storage` | Storage Blob Data Owner on only the Function storage account |
| `azurerm_key_vault.function` | Standard vault for unavoidable PostgreSQL/webhook values |
| `azurerm_key_vault_access_policy.function` | System identity read-only secret access |
| `azurerm_key_vault_access_policy.operator` | Named operator can populate values without Terraform state |

No new database, Log Analytics workspace, Application Insights instance,
Container App environment, registry, or always-on compute is proposed.

## Identity and secret model

The Flex app uses a user-assigned managed identity for both its deployment
container and `AzureWebJobsStorage`; storage shared-key authentication is
disabled. A separate system-assigned identity resolves Key Vault references.

The current PostgreSQL monitor and webhook integrations are secret-bearing and
cannot be switched to a different authentication contract without changing the
working production database/receiver configuration. Their existing values are
therefore copied directly from the Container App secret store into Key Vault
without printing them, passing them to Terraform, placing them in source, or
placing them in logs. The Function receives only Key Vault reference strings as
Terraform-managed application settings.

## Pre-creation plan and cost review

A local remote-state preview was generated before any Function resource was
created. The first preview found the pre-existing `APP_VERSION` Container App
drift. The configuration now ignores deployment-managed Container App
environment values so the final reviewed plan cannot create an unrelated API
revision.

The expected final inventory is nine creates, zero updates, zero replacements,
and zero destroys. The authoritative saved plan will be generated from merged
`main` by the Phase 6 Terraform plan workflow and reviewed before the separate
manual apply workflow is dispatched.

Cost characteristics are deliberately bounded:

- [Flex Consumption](https://learn.microsoft.com/azure/azure-functions/flex-consumption-plan)
  is consumption-based, can scale to zero, and is the recommended serverless
  hosting plan; this app has no always-ready instances and a one-instance cap;
- the 512-MB timer execution runs once per minute and performs one short HTTP
  request plus one PostgreSQL transaction;
- Standard LRS storage and Standard Key Vault incur only their small stored-data
  and operation charges for this workload;
- existing Application Insights/Log Analytics resources are reused, so their
  normal ingestion charges continue rather than creating a parallel stack.

This is not continuously billed dedicated compute, and the inventory contains
no unexpected or materially nontrivial cost exposure.

## Safe coexistence and cutover plan

The Container App monitor remains running while infrastructure is reviewed and
applied. The new Function has no timer code until its package is deployed.

Immediately before the package deployment:

1. snapshot persisted check, incident, and notification counts;
2. deactivate the current Container App monitor revision and verify zero
   replicas;
3. deploy the Function package with remote build;
4. verify the timer trigger and multiple scheduled executions;
5. correlate Function logs with newly persisted healthy check rows;
6. verify incidents and notifications did not increase.

The Function is limited to one instance, Azure timer schedule monitoring is
enabled, and PostgreSQL still serializes state changes with the existing
`SELECT ... FOR UPDATE` lock and unique notification constraint. If the
Function cannot execute correctly, the rollback is to reactivate the preserved
Container App revision. The two schedulers will not intentionally run together
against production state.

## Verification completed before live deployment

```text
Function/packaging/Terraform slice: 10 passed
PostgreSQL lifecycle/concurrency slice: 3 passed
Full suite: 73 passed, 1 existing warning
Terraform fmt/init/validate: passed with AzureRM 5.6.0
Function source package build: passed
actionlint 1.7.12: passed
```

## ACT-4 matrix

| ACT-4 requirement | Evidence | Result |
|---|---|---|
| Python timer-triggered Azure Function exists | Adapter and Terraform are implemented; live resource pending. | **OPEN** |
| Checker logic reused | Adapter imports `run_monitor_once`; package contains the original `monitor` modules; focused test proves no adapter checker. | **PASS** |
| URL/schedule configured | Terraform and timer metadata tests prove the intended settings; live configuration pending. | **OPEN** |
| Resources provisioned with Terraform | Configuration validates and pre-creation plan is reviewed; apply pending. | **OPEN** |
| Laptop independence | Flex Consumption architecture is remote; scheduled Azure proof pending. | **OPEN** |
| Multiple scheduled executions | Live evidence pending. | **OPEN** |
| Multiple results persisted | Live evidence pending. | **OPEN** |
| Logs show scheduled execution | Structured log implementation tested; live Log Analytics evidence pending. | **OPEN** |

Phase 4 remains **OPEN** until all eight rows are demonstrated and evidenced.
