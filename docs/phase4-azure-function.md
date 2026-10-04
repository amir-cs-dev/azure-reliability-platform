# Phase 4 Azure Function acceptance

Date: 2026-10-04 UTC

Final verdict: **PASS**

The authoritative monitoring service is a live Python 3.12 timer-triggered
Azure Function. Its Azure resources are represented in Terraform, its entry
point reuses the existing monitor implementation, and three consecutive
natural timer executions were correlated with three durable PostgreSQL rows.

## Architecture

`azure_function/function_app.py` is a thin Python v2 Functions adapter. The
timer entry point parses application settings and invokes
`monitor.runner.run_monitor_once`. That shared path uses the original
`monitor.checker.check_health`, `PostgresIncidentStore`, transactional incident
state, notification queue, and webhook delivery. There is no second checker or
incident-state implementation.

The binding uses `%MONITOR_SCHEDULE%`, `run_on_startup=False`, and
`use_monitor=True`. The live `MONITOR_SCHEDULE` is `0 * * * * *`, one execution
per minute in UTC. Azure reported the registered binding with that setting and
both Boolean controls.

Structured application logs distinguish:

- `scheduled_monitor_started`, including invocation time, past-due state, and
  the non-secret checked endpoint;
- `scheduled_monitor_completed`, including health/status, latency, lifecycle
  event, consecutive failures, and `persistence=succeeded`;
- `scheduled_monitor_failed`, containing only the exception type and no secret
  values.

## Live Azure inventory

The resources use the existing `rg-arp-app-wus3` resource group, Application
Insights instance, Log Analytics workspace, PostgreSQL server, and public API.

| Terraform address | Live resource | Purpose |
|---|---|---|
| `azurerm_function_app_flex_consumption.monitor` | `func-arp-monitor-3e6c8737-wus3` | Running Python 3.12 Function |
| `azurerm_service_plan.function` | `asp-arp-function-wus3` | Linux Flex Consumption (`FC1`) plan |
| `azurerm_storage_account.function` | `starpfn3e6c8737fb3a44be` | Key-disabled Standard LRS host/deployment storage |
| `azurerm_storage_container.function_releases` | `function-releases` | Private managed package container |
| `azurerm_user_assigned_identity.function` | `id-arp-function-wus3` | Function storage identity |
| `azurerm_role_assignment.function_storage` | storage-scoped assignment | `Storage Blob Data Owner` on only the Function storage account |
| `azurerm_key_vault.function` | `kv-arp-fn-3e6c8737` | PostgreSQL/webhook secret source |
| `azurerm_key_vault_access_policy.function` | Function system-identity policy | Read-only secret access |
| `azurerm_key_vault_access_policy.operator` | named operator policy | Populate values without putting them in Terraform state |

The live Function reports `state=Running`, Python `3.12`, 512 MB memory, a
maximum of one instance, and no always-ready instance. Its package storage uses
the user-assigned identity. Storage reports `allowSharedKeyAccess=false`,
`defaultToOAuthAuthentication=true`, HTTPS-only access, and TLS 1.2.

Flex Consumption declares Python through the resource's first-class
`runtime_name` and `runtime_version` properties. It rejects the legacy
`FUNCTIONS_WORKER_RUNTIME` setting, and Flex manages deployment packages rather
than using `WEBSITE_RUN_FROM_PACKAGE`; both legacy settings are absent.

AzureRM 5.6.0 inserted an empty legacy `AzureWebJobsStorage` connection string
during the initial Flex create despite the configured identity settings and
disabled shared keys. It was removed. Terraform now ignores only that
provider-generated map key while continuing to manage
`AzureWebJobsStorage__accountName`, `__credential=managedidentity`, and
`__clientId`. A refreshed remote-state plan after this correction reported
**No changes**.

## Identity and configuration

The Flex deployment container and `AzureWebJobsStorage` use
`id-arp-function-wus3`; its only data-plane assignment is `Storage Blob Data
Owner` scoped to `starpfn3e6c8737fb3a44be`. A separate system-assigned Function
identity resolves Key Vault references. No storage key is enabled or present in
the intended settings.

The existing PostgreSQL and webhook contracts still require secret values.
Their values were copied from the Container App secret store into Key Vault
without printing them, passing them to Terraform, placing them in source, or
placing them in logs. The Function configuration contains only Key Vault
reference strings. Azure reported both references as `Resolved`.

The Container App PostgreSQL DSN named an absolute CA path inside its image.
The Function-specific Key Vault value preserves TLS hostname verification but
uses the Azure Functions Linux system CA bundle. This avoids changing the
working Container App secret or embedding a CA file or credential in the
Function package.

## Reviewed Terraform plan and apply

The first trusted-main plan was deliberately not applied because it exposed an
unrelated `APP_VERSION` drift update. After isolating that deployment-managed
field, the reviewed resource plan contained nine creates and no update,
replacement, or destroy.

Two controlled apply attempts safely exposed platform prerequisites before the
final apply:

- [run 37180801084](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37180801084)
  stopped when the Key Vault resource provider was not registered; created
  resources were retained in remote state;
- [run 37181061032](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37181061032)
  stopped when Flex rejected the legacy worker-runtime setting; the setting was
  removed and covered by a regression test.

The final [trusted-main plan run
37181398169](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37181398169)
used source `1b4b1f5839adf09efb6000c272b9881c7133efcb`, Terraform 1.16.3,
and remote-state serial 14. It proposed exactly two remaining creates (the
Function and its Key Vault policy), with zero updates, replacements, or
destroys. Retained artifact `terraform-plan-37181398169` has digest
`sha256:3df04a3818956c0c3ae41cd5a0e01c822243b3a632e02ab4539118709489a2ee`.

The separately approved [apply run
37181505842](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37181505842)
passed the branch, confirmation, source SHA, artifact hash, configuration tree,
plan-age, and state-lineage/serial gates before applying that exact binary plan.
It completed successfully at `2026-10-04T06:01:42Z`; post-apply state serial was
15 with 19 tracked resources. Retained artifact
`terraform-apply-37181505842` has digest
`sha256:ddf81ea66ac27288be66c4c7bcfb7daaff85066b08e16105d1f61d6cd41234ba`.

After the evidence merge, the trusted-main plan's first attempt correctly
failed closed because its read-only OIDC identity lacked Azure's non-`read`
`Microsoft.Web/sites/config/list/action` permission for the newly created
Function. The custom `ARP Terraform Function Plan Reader` role grants only that
action and is assigned only at
`func-arp-monitor-3e6c8737-wus3`; it adds no write or data-plane permission.
Attempt 2 of [run
37214492285](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37214492285)
then completed from merged source
`4cc44b8ee597586f531962329d442cfa38e0b033`, Terraform 1.16.3, and state
lineage `cf7dcbb6-a5c0-de04-d87e-14665ab91030` serial 15. The retained plan has
zero creates, reads, updates, replacements, or deletes. Artifact
`terraform-plan-37214492285` has digest
`sha256:ce467a69cb798d8da9e7ae60dca12a5c92a5376daf4cbc6a3066bf18ea80ed8c`.

The Function source package was then remotely built and deployed from
`2026-10-04T06:04:52Z` through `06:06:01Z`. Azure subsequently listed the
`scheduled_monitor` timer function from the deployed package.

## Cost and hosting result

[Flex Consumption](https://learn.microsoft.com/azure/azure-functions/flex-consumption-plan)
is consumption-based and can scale to zero. This app has no always-ready
instances, a one-instance cap, 512 MB per instance, and one short execution per
minute. Standard LRS storage and Standard Key Vault add only stored-data and
operation charges for this small workload. Existing Application Insights, Log
Analytics, API, and PostgreSQL resources are reused. No continuously billed
dedicated Function compute or unexpected resource was created.

## Safe cutover and rollback

The Container App monitor remained intact during implementation and
provisioning. Immediately before package deployment, revision
`ca-arp-monitor-wus3--0000007` was deactivated. Azure subsequently reported
`active=false` and `replicas=0`; the revision remains available for rollback.
The two production schedulers therefore did not intentionally process the same
incident state concurrently.

The original Function-specific database value incorrectly retained the
Container App-only `/app/monitor/azure-roots.pem` path. Natural executions
failed during initialization and emitted sanitized `OperationalError` logs;
they could not persist a health result or advance incident state. The Key Vault
value was corrected to the Functions Linux system CA bundle, its reference was
refreshed, and the host was restarted. The next natural execution succeeded.
No credential or connection string was logged, and no deliberate outage was
created.

Rollback remains: stop the Function and reactivate preserved revision
`ca-arp-monitor-wus3--0000007`. It was not needed after the corrected Function
completed the acceptance window.

## Scheduled execution and persistence evidence

Log Analytics recorded these natural Azure timer invocations:

| Timer fire (UTC) | Invocation ID | Result | Application classification |
|---|---|---|---|
| `2026-10-04T15:35:00Z` | `48060054-ecfe-49a8-b601-aeb3859c7a70` | Succeeded in 424 ms | healthy, HTTP 200, 46.19 ms, persistence succeeded |
| `2026-10-04T15:36:00Z` | `5be9bc25-4b40-4f0d-b547-7a49374540dd` | Succeeded in 496 ms | healthy, HTTP 200, 98.99 ms, persistence succeeded |
| `2026-10-04T15:37:00Z` | `1c9b7677-e5e3-43bc-a118-e83e990e72ab` | Succeeded in 505 ms | healthy, HTTP 200, 80.01 ms, persistence succeeded |

For all three, platform logs explicitly say `Reason='Timer fired at ...'`, and
each is paired with one `scheduled_monitor_completed` record. The executions
occurred more than nine hours after package deployment; no local process or
manual invocation launched them, the former Azure scheduler had zero replicas,
and Azure's hosted timer continued to drive the work. The operator laptop is
not part of the execution path.

PostgreSQL contained exactly the corresponding rows:

```text
96801  2026-10-04T15:35:00.313818+00:00  healthy=1  status=200  latency=46.19  error=NULL
96802  2026-10-04T15:36:00.230470+00:00  healthy=1  status=200  latency=98.99  error=NULL
96803  2026-10-04T15:37:00.240775+00:00  healthy=1  status=200  latency=80.01  error=NULL
```

The previous Container App's last row was `96800` at
`2026-10-04T06:04:33.515797Z`. Thus the Function window is contiguous and has
one durable row per natural minute. Across the cutover, incidents remained at
two (latest opened `2026-09-23T00:57:34Z`), notifications remained at four
(latest delivered `2026-09-23T01:00:41Z`), and state remained
`consecutive_failures=0`, `incident_open=0`. No duplicate incident or
notification was introduced.

The runtime also retains the Phase 5 controls: a one-instance Function cap,
timer schedule monitoring, PostgreSQL `SELECT ... FOR UPDATE` serialization,
and the unique `(incident_id, event)` notification constraint.

## Verification

```text
Function/packaging/Terraform focused slice: 11 passed
PostgreSQL lifecycle/concurrency slice: 3 passed
Full suite: 74 passed, 1 existing warning
Terraform fmt/init/validate: passed with AzureRM 5.6.0
Refreshed live remote-state plan: no changes
Function source package build: passed
actionlint 1.7.12: passed
Application and monitor Docker builds: passed
```

Implementation was integrated through [PR
#14](https://github.com/amir-cs-dev/azure-reliability-platform/pull/14) at merge
`c91de7acb351d3881da9a508dfaac09f6b5462fe`; the modern Flex runtime correction
was integrated through [PR
#15](https://github.com/amir-cs-dev/azure-reliability-platform/pull/15) at merge
`1b4b1f5839adf09efb6000c272b9881c7133efcb`. The live acceptance evidence and
provider-workaround guard were integrated through [PR
#16](https://github.com/amir-cs-dev/azure-reliability-platform/pull/16) at merge
`4cc44b8ee597586f531962329d442cfa38e0b033`; its [post-merge CI run
37214492100](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37214492100)
is green.

## ACT-4 matrix

| ACT-4 requirement | Evidence | Result |
|---|---|---|
| Python timer-triggered Azure Function exists | Running `func-arp-monitor-3e6c8737-wus3`; Azure lists Python `scheduled_monitor` with a timer binding. | **PASS** |
| Checker logic reused | Thin adapter calls `monitor.runner.run_monitor_once`, which imports the existing checker/store/alerts; package and focused tests verify the shared modules. | **PASS** |
| URL/schedule configured | Key Vault/app-setting audit passed; live binding uses `%MONITOR_SCHEDULE%`, `0 * * * * *`, `runOnStartup=false`, and `useMonitor=true`. | **PASS** |
| Resources provisioned with Terraform | Reviewed plan `37181398169` and separately approved successful apply `37181505842`; all long-lived resources are in `infra/app/function.tf`. | **PASS** |
| Laptop independence | Three Azure timer runs occurred long after deployment with no local invocation and the former scheduler at zero replicas. | **PASS** |
| Multiple scheduled executions | Natural UTC executions at `15:35`, `15:36`, and `15:37`; platform logs explicitly identify timer firing. | **PASS** |
| Multiple results persisted | PostgreSQL rows `96801`–`96803` exactly correlate to the three timer completions. | **PASS** |
| Logs show scheduled execution | Log Analytics contains timer reason, target, classification, latency, lifecycle state, persistence success, and sanitized error evidence. | **PASS** |

All eight authoritative ACT-4 rows pass.
