# Phase 9 Stage 2 provisioning preflight

Date: 2026-10-04 UTC

Historical pre-apply verdict: **DASV5 BLOCKER RESOLVED BY APPROVED D2AS_V4
SUBSTITUTION; FRESH PLAN REQUIRED**

Outcome: trusted-main D2as_v4 plan `37235069628` passed the unchanged envelope
audit and exact-plan apply `37235364607` succeeded. The complete live result is
in the [acceptance report](live-acceptance.md).

The operator explicitly approved the Stage 2 cost envelope: Free-tier AKS,
one fixed `Standard_D2as_v5` system node, no other node pools, in-cluster
Prometheus/Grafana/Alertmanager/kube-state-metrics, existing ACR, external
Function checker, no new database, and no unrelated network or platform
services.

After Azure rejected the required DASv5 quota, the operator approved exactly
one change: use one fixed `Standard_D2as_v4` system node instead. Azure reports
the SKU available without a location restriction, with the same 2 vCPU / 8 GiB
class, and reports a DASv4-family quota limit of 10 vCPUs with zero consumed.
The Free tier, node count, autoscaling setting, region, disk, networking,
observability, shared-resource boundaries, and teardown scope remain unchanged.

## Source and integration state

Preflight began from a clean `main` exactly matching `origin/main` at evidence
merge `a1f3bfe3a3068752ba939c9d161840c707499525`. [PR
#19](https://github.com/amir-cs-dev/azure-reliability-platform/pull/19)
had merged only the Stage 1 integration evidence after [green CI run
37219965511](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37219965511).
Its [post-merge CI run
37232661659](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37232661659)
also completed successfully.

## Provider and quota preflight

Only the resource providers needed for the approved AKS path were registered:

- `Microsoft.ContainerService`;
- `Microsoft.Compute`;
- `Microsoft.Network`.

`Microsoft.Quota` was subsequently registered only because the required VM
family had no quota and Azure requires that provider to request an increase.
Provider registration did not create a billable resource.

West US 3 reports:

```text
Total Regional vCPUs:          current 0, limit 10
Standard DASv5 Family vCPUs:   current 0, limit 0
```

Azure lists `Standard_D2as_v5` in West US 3 with no SKU restriction and its
expected 2 vCPUs / 8 GiB memory. Two narrowly scoped quota requests asked for
exactly 2 DASv5 vCPUs. Requests
`150b911b-fb9d-4262-95d9-96fd55da7e9d` and
`d610ea0d-8a2b-4120-9497-125db9738294` both ended `Failed` with
`QuotaNotAvailableForResource`. The limit remains zero.

No alternate VM family, region, or node count was selected during this failed
attempt. No AKS cluster exists and Azure reports the planned node resource
group absent.

## Secretless apply identity

A separate Microsoft Entra application named `ARP Phase 9 Terraform Apply` was
created with no password or certificate credential. It has one federated
credential with exact subject:

```text
repo:amir-cs-dev/azure-reliability-platform:ref:refs/heads/main
```

Repository variable `AZURE_PHASE9_TERRAFORM_APPLY_CLIENT_ID` contains its
non-secret client ID. No repository Actions secret was added. Azure assignments
are limited to:

- Reader at the existing application resource group;
- Azure Kubernetes Service Contributor Role at that resource group;
- Reader at the existing state storage account;
- Storage Blob Data Contributor at the existing `tfstate` container;
- Role Based Access Control Administrator at the application resource group
  with a condition that permits only `AcrPull` to a service principal and
  Azure Kubernetes Service RBAC Cluster Admin to a user.

The existing application/Function Terraform apply identity was not broadened.

## Fresh approved-envelope plan

[Trusted-main Phase 9 plan run
37233428622](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37233428622)
completed successfully after the Stage 1 documentation merge. It used source
`a1f3bfe3a3068752ba939c9d161840c707499525`, Terraform 1.16.3, infrastructure
tree `777853d76588001a5ae29d7036925703a2f37603`, and isolated state lineage
`3fb12007-bf85-15a3-843c-a31a6157b798` serial 1.

Retained artifact `phase9-terraform-plan-37233428622` has digest
`sha256:a73b96cef9e74d963103b099a8dffa5076f95593746584c4da0c6c6bd5836726`.
Its material configuration remains exactly inside the approved envelope:

```text
AKS tier:             Free
system nodes:         1
system VM:            Standard_D2as_v5
autoscaling:          false
OS disk:              30 GiB managed
extra node pools:     none
managed observability:none

Plan: 3 to add, 0 to change, 0 to destroy.
```

The three creates remain only the AKS cluster, existing-ACR `AcrPull`
assignment, and operator cluster-RBAC assignment. There are no unrelated or
destructive actions.

No apply workflow was dispatched. This evidence update advances `main`, so the
retained plan is intentionally stale and cannot be applied.

## Approved continuation

An AKS apply with the zero-quota DASv5 family remains prohibited. The operator
has resolved the blocker by approving only the D2as_v4 substitution. Execution
may proceed only after a new current-`main` plan proves all of the following:

1. the system pool remains exactly one fixed D2as_v4 node with autoscaling off;
2. the plan contains only the AKS cluster and the two scoped role assignments;
3. it contains no update, replacement, or destroy outside isolated Phase 9;
4. every other approved resource and teardown constraint remains unchanged.

Any material difference beyond the approved SKU substitution requires new
approval. At this preflight checkpoint, Phase 9 remained OPEN; no ACT-9 live
row or teardown row passed from preflight alone. The subsequent complete live
chain and controlled teardown are documented in
[`live-acceptance.md`](live-acceptance.md), which records the final PASS.
