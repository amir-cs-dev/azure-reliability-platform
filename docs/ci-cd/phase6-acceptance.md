# Phase 6 CI/CD and infrastructure automation acceptance evidence

Status: **PASS**

Audit and demonstration date: 2026-10-04 UTC

Control implementation: merge commit `f0176831c0a3686f6b53d6fcb135eb915c2f0960`
from [PR #10](https://github.com/amir-cs-dev/azure-reliability-platform/pull/10).

This report distinguishes repository configuration, live GitHub/Azure facts,
demonstrations, inferences, and limitations. No secret values are recorded.

## Approval model

ACT-6 requires approval before consequential infrastructure apply. It does not
require a second-person reviewer. This private, solo-operator repository uses
an **operator-controlled manual approval boundary**, not a GitHub environment
required-reviewer rule:

```text
Pull request
  -> CI tests + backend-free Terraform fmt/validate
  -> reviewed merge to main
  -> separate Terraform plan run on trusted main
  -> retained binary plan + redacted plan text + sanitized metadata
  -> operator reviews the plan
  -> separate workflow_dispatch(plan_run_id, confirmation=APPLY)
  -> exact run/artifact/SHA/tree/version/state/hash/freshness checks
  -> OIDC login with the apply-only identity
  -> apply the exact reviewed binary plan
```

The plan workflow has no apply step. The apply workflow has no automatic
trigger. A plan succeeding therefore cannot cause an apply. The explicit
`workflow_dispatch` action, plan run ID, and literal `APPLY` input are the
operator's approval.

Live remote-state planning does not run in pull-request context. PR code can
neither mint an infrastructure identity token nor read state. After merge, a
trusted-main plan captures the exact configuration that is eligible for apply.

## Workflow architecture

### PR validation

`.github/workflows/ci.yml` runs on pull requests and pushes to `main`, and is
also callable by the deployment and Terraform-plan workflows. It performs:

- all pytest tests, including the disposable PostgreSQL integration tests;
- `terraform fmt -check`;
- `terraform init -backend=false` and `terraform validate`;
- application and monitor Docker builds;
- a live application-container health check.

[PR #10 CI run 37172184831](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37172184831)
passed before merge. The resulting
[main CI run 37172267456](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37172267456)
also passed all steps with `62 passed, 1 warning`.

### Application deployment

`.github/workflows/deploy.yml` remains a separate manual application-deployment
workflow. Its `deploy` job needs the reusable `validate` job, requires
`refs/heads/main`, uses the `production` environment, builds SHA-tagged images,
updates the two existing Container Apps, and runs the cutover-aware verifier.
It does not run Terraform.

### Terraform plan

`.github/workflows/terraform-plan.yml` runs only on trusted `main` pushes that
touch the infrastructure/control path or by manual dispatch. It:

1. calls the complete reusable validation workflow;
2. logs in with the plan-only OIDC identity;
3. initializes the existing AzureRM backend;
4. runs fmt and validation again in the live plan context;
5. captures state lineage and serial before planning;
6. creates a saved binary plan with Terraform 1.16.3;
7. generates Terraform's redacted text rendering;
8. records the source SHA/ref, infrastructure tree hash, workflow run,
   Terraform version, operation, state identity, image tag, action summary,
   file sizes, and SHA-256 hashes;
9. retains the private artifact for seven days.

Raw `terraform show -json` output is transient because it can contain sensitive
values. It is reduced to resource addresses/action counts and is never uploaded.
The binary plan is necessarily sensitive and remains a short-lived private
artifact.

### Terraform apply

`.github/workflows/terraform-apply.yml` has only `workflow_dispatch`. Before
OIDC login or apply, it requires:

| Control | Enforced behavior |
|---|---|
| Explicit approval | `confirmation` must equal `APPLY` exactly. |
| Allowed branch | Dispatch ref and live repository default SHA must both be current `main`. |
| Plan run | Run ID must be numeric and identify a completed successful `Terraform plan` workflow. |
| Apply-eligible plan event | Plan must be from `push` or `workflow_dispatch`, never a PR. |
| Exact source | Plan run, metadata, checkout, and current `main` SHA must match. |
| Exact configuration | Git tree hash for `infra/app` must match the reviewed plan metadata. |
| Exact tooling | Terraform version and consumable binary plan are verified. |
| Exact artifact | One unexpired artifact with the run-derived name must exist. |
| File integrity | Binary plan and redacted text size/SHA-256 hashes must match metadata. |
| Freshness by time | Plans older than 24 hours are rejected. |
| Freshness by state | Current state lineage and serial must match the plan snapshot. |
| Terraform native freshness | Terraform itself also rejects a saved plan if state changed. |

Only after all controls pass does the workflow apply the exact saved binary
plan. `-auto-approve` removes a redundant runner prompt; it does not replace
approval because dispatch and the literal confirmation already occurred.

## Controlled plan and approved apply demonstration

### Normal plan retained but not applied

[Main plan run 37172267618](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37172267618)
proved the normal plan path and retained artifact
`terraform-plan-37172267618` with digest
`sha256:0b929448c8e3d073da9d50b9e5010d187f1733393a14cbee829a2d8284fa4f60`.
It was source commit `f0176831...`, Terraform 1.16.3, state serial 9, and
reported `0 add, 1 change, 0 destroy`. The one proposed in-place change would
restore `APP_VERSION` after CLI image deployment. It was deliberately **not**
applied because a production revision change was unnecessary for evidence.

### Reviewed safe plan

[Refresh-only plan run 37176906272](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37176906272)
passed the full reusable validation and the live plan job. Its retained artifact
was `terraform-plan-37176906272`, digest
`sha256:146631f32be75aec0e20a614c946f3d28958711bc9cba15b39ae50b8a3daf068`.

Reviewed metadata:

| Field | Value |
|---|---|
| Source | current `main` at `f0176831c0a3686f6b53d6fcb135eb915c2f0960` |
| Terraform | 1.16.3 |
| Operation | `refresh-only` |
| State | existing AzureRM backend, lineage unchanged, serial 9 |
| Azure resource actions | 0 create, 0 update, 0 replace, 0 destroy |
| Observed drift | Existing API revision/image advanced by prior application deployments |

Terraform's redacted plan explicitly stated that applying the refresh-only plan
would record existing values in state without changing remote objects.

### Separate operator-approved apply

[Apply run 37177031047](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37177031047)
was separately dispatched from `main` with plan run `37176906272` and literal
confirmation `APPLY`. Every control in the table above passed before apply.
Terraform reported:

```text
Apply complete! Resources: 0 added, 0 changed, 0 destroyed.
```

The apply evidence artifact `terraform-apply-37177031047` has digest
`sha256:d7d001345ee6df16e20da63aae1317efe8c6f8e7787aa550c8115e2715fd2823`.
State advanced from serial 9 to serial 10 with the same lineage. Live API and
monitor revisions and their immutable `e531acdb...` images were unchanged.

### Live rejection demonstrations

| Run | Deliberate invalid request | Result before apply |
|---|---|---|
| [37177119364](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37177119364) | Confirmation `DECLINE` instead of `APPLY` | Failed first control; checkout, OIDC login, state access, and apply all skipped. |
| [37177338261](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37177338261) | Apply dispatched from experiment branch | Failed main-only control; OIDC login and apply skipped. |
| [37177142642](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37177142642) | Replay of already-applied plan at state serial 10 | Failed `state serial changed`; apply skipped. |

Unit tests additionally reject mismatched run IDs, source SHA, infrastructure
tree, Terraform version, file hashes, plan age, state serial, PR-origin plans,
and non-main refs.

## Failed-test deployment-blocking experiment

The experiment used isolated PR
[#11](https://github.com/amir-cs-dev/azure-reliability-platform/pull/11) at
commit `f465f875ef55824eb5922edffe24735fb4236000`. Its entire production-neutral
change was one test with an intentional assertion failure.

- [PR CI run 37177218061](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37177218061)
  failed with exactly `1 failed, 62 passed`; the named deliberate test was the
  only failure.
- The existing manual application-deployment workflow was dispatched on that
  exact branch as
  [run 37177277882](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37177277882).
- Reusable `validate / validate` failed on the deliberate test.
- The actual downstream `deploy` job was `skipped`, ran for zero seconds, and
  contained no steps. Azure login, image push, Container App update, and the
  verifier did not execute.

The deploy job is protected by both `needs: validate` and a main-only condition.
The experiment did not weaken either control to isolate one mechanism. It proves
that failing validation cannot progress through the real deployment path while
preserving the independent branch guard.

PR #11 was closed without merge. Its remote/local branch was deleted, the
intentional test is absent from `main`, and the run/PR references remain durable.

## OIDC and Azure permissions audit

All three GitHub identities are secretless federated applications. No password
or certificate credentials exist.

| Identity | Federated trust | Azure permissions |
|---|---|---|
| Existing application deploy | Exact GitHub `production` environment subject | `AcrPush` + Reader on the exact registry; Container Apps Contributor on the exact API and monitor apps. |
| Terraform plan | Exact repository `refs/heads/main` subject only | Reader on the application resource group and state account; Storage Blob Data Contributor on the exact `tfstate` container for locking; one custom `containerApps/listSecrets/action` permission on the Terraform-managed API because AzureRM requires it during refresh. No Azure resource writes. |
| Terraform apply | Exact repository `refs/heads/main` subject only | Contributor on the seven existing Terraform-managed non-RG resources; Reader on the app resource group/state account; Storage Blob Data Contributor on the exact state container; RBAC Administrator on the exact ACR for the managed `AcrPull` assignment. |

The apply identity has no resource-group Contributor grant. It cannot write the
unmanaged PostgreSQL server or monitor Container App. A reviewed change that
adds/replaces a resource will require a deliberate permission-scope update
rather than receiving standing broad access.

## GitHub workflow-permissions audit

All external Actions are pinned to commit SHAs.

| Workflow/job | GitHub token permissions | Reason |
|---|---|---|
| CI | `contents: read` | Checkout only. |
| Application deploy validation | `contents: read` | Reusable CI checkout. |
| Application deploy | `contents: read`, `id-token: write` | Checkout and Azure OIDC. |
| Terraform-plan validation | `contents: read` | Reusable CI checkout. |
| Terraform plan | `contents: read`, `id-token: write` | Checkout and plan-identity OIDC. |
| Terraform apply | `contents: read`, `actions: read`, `id-token: write` | Checkout, verify/download another run's artifact, and apply-identity OIDC. |

No workflow requests `pull-requests: write`, `packages: write`, `actions: write`,
or repository-wide write permissions. Top-level Terraform workflow permissions
are `{}` and are added only at the job that needs them.

Repository defaults are read-only and workflows cannot approve PR reviews.
The repository-level Actions policy currently allows all Actions and does not
enforce SHA pinning, but every Action referenced by these workflows is pinned
in YAML. That repository-policy limitation is documented rather than hidden.

## GitHub environment and configuration audit

Live metadata on 2026-10-04 showed:

- exactly one environment, `production`;
- a custom deployment branch policy allowing `main` only;
- no required-reviewer rule;
- environment variables named `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and
  `AZURE_SUBSCRIPTION_ID`;
- zero environment secrets;
- six repository variables for the separate Terraform identities and existing
  backend metadata;
- zero repository Actions secrets.

Variable values are not recorded here. The infrastructure approval boundary
does not claim to use GitHub environment protection. It is the verified
operator-controlled plan/review/manual-dispatch process described above.

The private repository's current plan does not expose the branch-protection
API. This is a documented limitation, not a claimed control. Apply independently
queries the live default-branch SHA and rejects any non-main dispatch.

## Remote state and Terraform-scope audit

`infra/app/backend.tf` uses AzureRM state with Azure AD/CLI authentication,
container `tfstate`, and key `application.terraform.tfstate`. Both workflows
receive the existing state resource group/account as non-secret variables.

The live state has one stable lineage, serial 10 after the safe demonstration,
and nine resources. The plan showed no deletion of unmanaged resources. The
standalone monitor and PostgreSQL server are not in this state.

Current workflows use only `infra/app`. They do not discover or execute any
historical `infra/bootstrap` content. Bootstrap/state ownership must be handled
as a separately reviewed future change and is not silently inferred here.

## Immutable deployment and healthy-cutover evidence reused

No new outage or production deployment was needed.

[Deploy #5 run 35805627905](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/35805627905)
already proves that application commit
`e531acdbcc1ef3b85e46e213b4130acaba31ef4b` passed validation, authenticated
through OIDC, built/pushed SHA-tagged API and monitor images, updated both apps,
waited for the exact API revision to receive 100% traffic, and passed six
post-cutover semantic `/health` and `/ready` samples.

Live audit still found both Container Apps on immutable `e531acdb...` tags; the
API was revision `ca-arp-api-wus3--0000009` and monitor revision
`ca-arp-monitor-wus3--0000007`. The retained details and six-sample output are
in [Incident #2 Azure evidence](../incidents/evidence/incident-002-azure-logs.md).

## Tests and static validation

- Current full suite: **62 passed**, including PostgreSQL integration.
- Focused Terraform artifact/workflow controls: **14 passed**.
- Focused deployment verifier: **4 passed**.
- Verifier negatives cover degraded health at first and sixth sample plus
  failure to complete cutover; the healthy case covers all six samples.
- `terraform fmt -check` and `terraform validate`: passed.
- `actionlint`: passed for all workflow files.
- Application and monitor Docker builds: passed.
- Application container: HTTP 200 healthy as non-root `appuser`.

## Limitations and bounded claims

- Approval is explicit solo-operator approval, not independent second-person
  review and not a GitHub required-reviewer environment.
- The normal plan still proposes one in-place `APP_VERSION` reconciliation
  caused by the intentionally separate CLI application deployment path. It was
  reviewed and not applied. Full Terraform/application ownership reconciliation
  remains future work, but does not weaken the demonstrated plan/apply gate.
- Binary plans can contain sensitive data. The reviewed Phase 6 control operated
  while the repository was private. Before public release, retained plan
  artifacts were deleted and the plan/apply workflows were made fail-closed for
  public repositories; this report preserves non-sensitive metadata and digests.
- Current pinned Action releases emit GitHub's Node.js 20 forced-to-24 migration
  warning, and `ubuntu-latest` has a future image migration notice. Neither
  warning changed the demonstrated results; dependency updates should be
  reviewed separately.
- The apply identity intentionally cannot create arbitrary new resource-group
  resources. Permission expansion must accompany and be reviewed with such a
  plan.

## Final ACT-6 audit

| ACT-6 requirement | Evidence | Result |
|---|---|---|
| PR validation job | PR #10 run 37172184831; current `ci.yml` | **PASS** |
| Deployment separated | Manual application deploy, main-only plan, and separate manual apply workflows | **PASS** |
| OIDC | Deploy #5 plus plan/apply runs; three secretless federated identities | **PASS** |
| Remote Terraform state | AzureRM backend, live lineage/serial, plan/apply state checks | **PASS** |
| Controlled Terraform plan/review | Runs 37172267618 and 37176906272; retained redacted plans, metadata, hashes, and artifacts | **PASS** |
| Approval before consequential apply | Separate `workflow_dispatch`, run ID, literal `APPLY`, successful run 37177031047, negative run 37177119364 | **PASS** |
| GitHub environment audit | Live environment/variable/secret/protection metadata above | **PASS** |
| Restricted permissions audit | Explicit job permissions, pinned Actions, scoped Azure roles, zero credentials | **PASS** |
| Immutable artifact/revision | SHA-tagged Deploy #5 images and exact live revisions | **PASS** |
| Successful application deployment | Deploy #5 run 35805627905 at commit `e531acdb...` | **PASS** |
| Failed harmless test blocks deployment | Closed PR #11; CI run 37177218061; actual deploy run 37177277882 with skipped `deploy` job | **PASS** |
| Healthy post-cutover verification | Deploy #5 exact revision, 100% traffic, six semantic samples | **PASS** |
| Negative verifier regression tests | Four focused tests; degraded first/sixth sample and incomplete cutover rejected | **PASS** |

**Phase 6 verdict: PASS.**
