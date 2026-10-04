# Phase 9 Stage 2 provisioning preflight

Date: 2026-10-04 UTC

Verdict: **APPROVED RESOURCE ENVELOPE; PROVISIONING BLOCKED BY AZURE QUOTA**

The operator explicitly approved the Stage 2 cost envelope: Free-tier AKS,
one fixed `Standard_D2as_v5` system node, no other node pools, in-cluster
Prometheus/Grafana/Alertmanager/kube-state-metrics, existing ACR, external
Function checker, no new database, and no unrelated network or platform
services.

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

No alternate VM family, region, or node count was selected. No AKS cluster
exists and Azure reports the planned node resource group absent.

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
retained plan is intentionally stale and cannot be applied. After quota is
available, a new current-`main` plan must pass the same audit.

## Blocking condition and allowed continuation

An AKS apply with a zero family quota would risk a partial failed deployment.
It is therefore prohibited. Execution may resume only after one of these
conditions is explicitly resolved:

1. Azure grants at least 2 `standardDASv5Family` vCPUs in West US 3, preserving
   the approved plan unchanged; or
2. the operator separately approves a changed VM family/region and its updated
   cost/resource plan.

Phase 9 remains OPEN. No ACT-9 live row or teardown row passes from this
preflight.

