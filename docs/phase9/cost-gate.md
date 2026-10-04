# Phase 9 AKS resource and cost gate

Date: 2026-10-04 UTC

Decision state: **AWAITING EXPLICIT OPERATOR APPROVAL — DO NOT APPLY**

This is the mandatory Stage 1 stop gate. The local Terraform plan was created
against the isolated AzureRM state key and was not applied.

## Terraform plan summary

Terraform 1.16.3 proposes exactly:

```text
Plan: 3 to add, 0 to change, 0 to destroy.
```

| Terraform address | Action | Azure purpose |
|---|---|---|
| `azurerm_kubernetes_cluster.phase9` | create | Temporary AKS control plane and one system node pool |
| `azurerm_role_assignment.aks_acr_pull` | create | Existing ACR-scoped `AcrPull` for the generated kubelet identity |
| `azurerm_role_assignment.operator_cluster_admin` | create | Cluster-scoped Azure Kubernetes Service RBAC Cluster Admin for the named operator |

There are no planned updates, replacements, or deletes. Existing
`rg-arp-app-wus3` and ACR `arp3e6c8737fb3a44be8477` are data sources, not
managed resources in this state. `infra/bootstrap` is excluded.

Read-only Azure preflight also confirmed that no cluster named
`aks-arp-phase9-wus3` exists and the planned node resource group is absent.
`Microsoft.ContainerService`, `Microsoft.Compute`, and `Microsoft.Network`
currently report `NotRegistered`; no registration was performed in Stage 1.
After approval, the operator must register these three providers and wait for
`Registered` before generating the final apply-eligible plan. Provider
registration is a subscription-level prerequisite but does not itself create
the billable lab resources. AzureRM is configured with automatic provider
registration disabled so this mutation cannot happen implicitly.
Subscription quota for the selected compute family could not be enumerated
while `Microsoft.Compute` was unregistered. Stage 2 must stop if two vCPUs or
the selected SKU are unavailable; changing the node SKU or count requires an
updated plan and cost approval.

The AKS service will create supporting objects in its dedicated managed node
resource group `rg-arp-phase9-nodes-wus3`. Expected platform-managed resources
are one VM scale set/node, one 30 GiB managed OS disk, a virtual network and
network security group, one Standard Load Balancer, a control-plane
system-assigned managed identity, a kubelet managed identity, and public IP
resources. With `outbound_type=loadBalancer` and one public Kubernetes
`LoadBalancer` Service, budget for two Standard public IPv4 addresses: one for
AKS outbound traffic and one frontend address for `arp-api`. Azure determines
the final generated names and exact managed-resource inventory only at create;
Stage 2 must inventory them before declaring the plan reconciled.

## Compute

| Setting | Selected value |
|---|---|
| Cluster | `aks-arp-phase9-wus3`, West US 3 |
| AKS pricing tier | `Free` control-plane tier; no uptime SLA |
| Kubernetes support plan/version | KubernetesOfficial, 1.35 (current West US 3 default when checked) |
| System node pool | `system`, mode System |
| VM size | `Standard_D2as_v5` (2 vCPU, 8 GiB) |
| Node count | exactly 1 |
| Autoscaling | disabled; no min/max range |
| Upgrade surge | 1 temporary surge node may exist during a node upgrade |
| OS | Ubuntu, managed OS disk |
| OS disk | 30 GiB; expected P4 LRS billing tier because the SKU has no usable ephemeral OS disk |
| Pods | maximum 30 per node |

The one-node design is deliberately a temporary learning lab, not a
high-availability production topology. Two application replicas demonstrate
pod-level rolling behavior but do not survive loss of the only node.

## Networking and storage

- Azure CNI Overlay with Azure network policy.
- Standard Load Balancer with `outbound_type=loadBalancer`.
- One public `arp-api` Service. Prometheus, Grafana, Alertmanager, and
  kube-state-metrics remain private `ClusterIP` Services.
- Budget assumption: one Standard Load Balancer and two Standard static IPv4
  addresses after the application Service is installed.
- No application data disk, persistent volume, ingress controller, gateway,
  NAT Gateway, separately managed VNet/subnet, or service mesh.
- Prometheus, Grafana, and Alertmanager use pod-local `emptyDir`; all their
  runtime data disappears during teardown/recreation.
- Remote Terraform state remains in the existing private Azure Storage backend
  under `phase9.terraform.tfstate`.

## Identity and ACR

AKS uses a system-assigned control-plane identity and its generated kubelet
identity. Terraform grants only `AcrPull` at the existing ACR and cluster-admin
data-plane access at the new AKS resource to the configured operator object.
Local accounts are disabled; Microsoft Entra/Azure RBAC is enabled. OIDC issuer
and workload identity are enabled without creating a workload identity that
the application does not need.

The existing plan identity remains read-only. Before any Stage 2 apply, create
and configure the separate repository variable
`AZURE_PHASE9_TERRAFORM_APPLY_CLIENT_ID`. Its federated trust must be exact
`main`, and its Azure scope must be limited to:

- state read/write/lock access at the existing `tfstate` container;
- read access to the existing application resource group and ACR;
- only AKS managed-cluster lifecycle actions required at
  `rg-arp-app-wus3`;
- role-assignment write/delete constrained to built-in `AcrPull`
  (`7f951dda-4ed3-4680-a7ca-43fe172d538d`) and Azure Kubernetes Service RBAC
  Cluster Admin (`b1ff04bb-8a4e-4dc4-8eb5-8693973ce19b`).

This does not broaden the existing application/Function Terraform apply
identity. No client secret or kubeconfig may be committed.

## Observability model

Prometheus, Alertmanager, Grafana, and kube-state-metrics run inside the single
AKS node. No Azure Managed Prometheus, Managed Grafana, Log Analytics workspace,
Container Insights, or additional Application Insights resource is created.
The existing external Azure Function and existing Application Insights/Log
Analytics resources remain outside AKS and are reused for the bounded
external-checker observation.

## Cost estimate

The estimate uses the public Azure Retail Prices API in USD, without negotiated
discounts, reservations, Spot pricing, taxes, or egress. Rates observed on
2026-10-04 were:

| Driver | Retail observation | Approximate lab contribution |
|---|---|---|
| One Linux `Standard_D2as_v5` VM in West US 3 | USD 0.086/hour | USD 0.086/hour |
| Standard Load Balancer included rules | USD 0.025/hour | USD 0.025/hour |
| Two Standard IPv4 static addresses | USD 0.005/hour each | USD 0.010/hour |
| P4 LRS managed disk | USD 4.8001/month plus USD 0.26/month mount | about USD 0.007/hour |
| AKS Free control plane | no cluster-management charge | USD 0/hour control plane |
| Load Balancer data | USD 0.005/GB | negligible for bounded test traffic |

Expected steady exposure is approximately **USD 0.13/hour**, or **USD
3.1/day**, before egress, taxes, unusual build/storage consumption, or a
temporary upgrade surge node. Use **USD 0.12–0.16/hour (roughly USD 3–4/day)**
as the planning range. An upgrade surge can temporarily add another VM and disk
and roughly double compute exposure. Existing ACR and external platform costs
continue independently; one additional image/build has minimal incremental
storage/build cost for this experiment.

The lab should exist only for the same-day acceptance window. Start teardown
immediately after evidence is safely committed and reviewed.

Pricing inputs are reproducible through the [Azure Retail Prices
API](https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices).
The Free tier behavior and absence of an uptime SLA are described in the
[official AKS pricing-tier documentation](https://learn.microsoft.com/azure/aks/free-standard-pricing-tiers).
The estimate is a budget, not a bill guarantee.

## Teardown scope

First remove Helm-managed workloads and the public Service:

```bash
PHASE9_TEARDOWN=DESTROY_K8S scripts/phase9/teardown.sh
```

Then dispatch `Phase 9 Terraform plan` from current `main` with operation
`destroy`, review the exact retained plan, and separately dispatch
`Phase 9 Terraform apply reviewed plan` with that plan run ID and literal
`APPLY`.

The destroy plan must contain only the three Phase 9 state resources:

- the AKS cluster, including Azure's dedicated managed node resource group and
  its VMSS, managed disk, network, load balancer, managed identities, and public
  IP resources;
- the existing-ACR `AcrPull` assignment;
- the temporary operator AKS RBAC assignment.

The existing application resource group, ACR and images, Container Apps,
Function, PostgreSQL, Key Vault, Application Insights, Log Analytics, Discord
secret source, and the Phase 6 application state are data/shared resources and
must survive. The isolated Phase 9 state blob may remain as inexpensive audit
metadata after it tracks zero resources.

After destroy, verify that the cluster and node resource group are absent, the
shared ACR and external Function remain present, and a fresh Phase 9 plan again
shows only the original three creates. Evidence of that verification is an
ACT-9 requirement.

## Approval boundary

No command in Stage 1 created AKS or another materially billable Phase 9
resource. Explicit operator approval of this resource/cost gate and the final
trusted-`main` plan is required before the manual apply workflow may be used.
