# Cost characteristics and safe teardown

Audit date: 2026-10-05 UTC. Prices and usage vary; this document separates
observed configuration from estimates and does not invent a monthly bill.

## Persistent resources

| Driver | Audited configuration | Cost characteristic / control |
|---|---|---|
| PostgreSQL Flexible Server | Burstable `Standard_B1ms`, PostgreSQL 18, 32 GiB, HA off, geo-backup off, 7-day backup | Primary predictable persistent compute/storage driver; small non-HA portfolio tier |
| Container Apps API | Consumption environment, 0.25 vCPU / 0.5 GiB, min 1 / max 1 | One always-warm replica; fixed maximum bounds scale cost |
| Legacy monitor Container App | Resource stopped, all revisions inactive, zero replicas | No active replica compute; retain/delete decision is operational, not Phase 9 scope |
| ACR | Basic, admin disabled | Fixed registry tier plus image storage/build activity |
| Log Analytics / Application Insights | PerGB2018, 30-day retention, no configured daily cap | Usage-based ingestion is a variable cost; bounded tests and retention limit exposure, but no quota currently caps it |
| Azure Function | Linux Flex Consumption FC1, max 1 instance, 512 MiB | Execution/resource usage; one-minute timer creates predictable low-volume invocations |
| Function storage | Standard LRS StorageV2, private release container | Low data/storage/transaction usage; shared-key access disabled |
| Key Vault | Standard | Operation/storage usage for two secret references |
| Terraform state | Standard LRS, two small private blobs | Minimal persistent control-plane storage |

The API, Function, ACR, telemetry, and PostgreSQL are long-lived. There is no
claim that this single-replica, non-HA design meets a production availability
SLA. Cost prevention controls are the fixed replica count, one Function
instance, short log retention, Basic/Burstable tiers, inactive old scheduler,
temporary-only AKS, and reviewed plans before infrastructure change.

## Temporary Phase 9 lab

The reviewed envelope was:

- AKS Free-tier control plane;
- exactly one fixed `Standard_D2as_v4` system node (2 vCPU / 8 GiB class);
- no autoscaling or additional pools;
- in-cluster Prometheus, Grafana, Alertmanager, and kube-state-metrics;
- existing ACR and external Function reused;
- transient Standard load balancer, public IPs, and managed disk; and
- no Managed Prometheus, Managed Grafana, new database, service mesh, gateway,
  or unrelated networking.

Public retail observations captured on 2026-10-04 supported approximately
**USD 0.13–0.17/hour (roughly USD 3–4/day)** for the bounded lab, before tax,
egress, discounts, or temporary upgrade surge. This is a planning estimate, not
a bill or current-price guarantee. The source assumptions are retained in the
[Phase 9 cost gate](phase9/cost-gate.md#cost-estimate).

Teardown is complete:

- Helm release, namespace, and application LoadBalancer removed;
- exact reviewed plan: 0 add, 0 change, 3 destroy;
- exact manual apply: 0 added, 0 changed, 3 destroyed;
- AKS and its managed node resource group absent;
- isolated state serial 5 with zero managed resources and no outputs; and
- API, ACR, Function, PostgreSQL, and telemetry preserved and healthy.

The node, disk, load balancer, public IPs, and cluster no longer incur Phase 9
lab cost.

## Recreating and tearing down only Phase 9

Recreation is a new consequential change and requires a fresh trusted-main
plan, cost review, and explicit operator approval. Follow the [runbook](phase9/runbook.md).

Teardown order:

1. Commit and integrate sanitized evidence.
2. Restore the Function target to the persistent HTTPS Container Apps
   `/health` endpoint and observe natural healthy timer executions.
3. Remove the Helm release/namespace:

   ```bash
   PHASE9_TEARDOWN=DESTROY_K8S scripts/phase9/teardown.sh
   ```

4. Dispatch **Phase 9 Terraform plan** from current `main` with operation
   `destroy`.
5. Reject any plan affecting more than the cluster and its two tracked role
   assignments.
6. Separately dispatch **Phase 9 Terraform apply reviewed plan** with the exact
   run ID and literal `APPLY`.
7. Verify cluster/node-RG absence, empty Phase 9 state, preserved shared
   resources, and healthy Function checks.

Never use `infra/app`, the app state key, or the shared resource group to
clean up Phase 9.

## Complete project decommission

Complete decommission is intentionally not a routine workflow because the app
resource group contains Terraform-managed resources plus the external
PostgreSQL server and inactive legacy monitor. A raw `terraform destroy`
would not make that mixed ownership obvious, and deleting the Terraform-managed
resource group would also cascade-delete the untracked resources.

Use this sequence only when the explicit goal is permanent removal:

1. Confirm Phase 9 is already absent.
2. Export any required PostgreSQL backup, Incident #2 evidence, logs, and
   Terraform state to an approved secure location. Do not commit exports.
3. Inventory both project resource groups and verify the Azure subscription:

   ```bash
   az account show --query '{subscription:id,user:user.name}' -o json
   az resource list --resource-group rg-arp-app-wus3 \
     --query '[].{name:name,type:type}' -o table
   az storage blob list --auth-mode login \
     --account-name starptf3e6c8737fb3a44be \
     --container-name tfstate --query '[].name' -o table
   ```

4. Stop the Function and confirm no incident write is in progress.
5. Require a typed, resource-group-specific confirmation in the operator shell;
   then delete only `rg-arp-app-wus3`. This intentionally removes both the
   managed core and its documented external/manual resources:

   ```bash
   core_group=rg-arp-app-wus3
   read -r -p "Type DELETE-$core_group: " decommission_confirmation
   [[ "$decommission_confirmation" == "DELETE-$core_group" ]]
   az group delete --name "$core_group" --yes
   ```

6. Verify the group is absent and that no project resource remains elsewhere.
7. Remove the four project-specific GitHub OIDC application registrations and
   their role assignments only after verifying their repository-bound
   federation and exclusive use. Remove the matching repository/environment
   variables.
8. Delete `rg-arp-tfstate-wus3` last, only after the state export and project
   resource/identity audit are complete.
9. Re-run Azure inventory and repository secret/configuration checks.

The snippet deliberately names one exact group and has no wildcard or recursive
subscription scope. It is documentation, not an action taken during Phase 10.
The state backend and OIDC applications remain useful while the platform
exists and were therefore not deleted by this audit.
