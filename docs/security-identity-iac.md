# Security, identity, IaC, and state audit

Audit date: 2026-10-05 UTC. This is a bounded review of the repository, GitHub
configuration visible to the operator, Azure identities/assignments, live
resource inventory, and both Terraform states. It is not a penetration test.

## Repository credential audit

The final audit covered tracked files, reachable Git history, filename classes,
and high-risk content patterns:

- passwords and connection strings;
- GitHub, Azure, AWS, Google, Stripe, Slack, and generic tokens;
- Discord webhook URLs;
- kubeconfigs and Azure CLI artifacts;
- Terraform state, variable files, saved binary plans, and crash logs;
- PEM/private keys and generated secret-bearing artifacts.

Gitleaks 8.24.2 scanned the full reachable history with redaction and returned
`no leaks found`. Its only initial candidates were public 40-character Git
commit hashes used as immutable `reliability-api` image tags in two Incident #2
documents. The versioned allowlist is deliberately constrained by both file
path and the exact `reliability-api:<40 lowercase hex>` line pattern; it does
not suppress generic findings elsewhere.

Three values found by an independent pattern review are safe fixtures:

- `ci_only_local_password` is a disposable GitHub Actions PostgreSQL service
  value bound to localhost;
- `<local-test-only>` is documentation, not a credential; and
- `https://discord.com/api/webhooks/123/test-token` is a mocked unit-test URL.

No state, plan, kubeconfig, private key, `.env`, Azure profile, database DSN,
or actual webhook URL is tracked. `.gitignore` excludes those classes.
Repository Actions secrets: **0**. Production-environment secrets: **0**.
Tenant, subscription, client, state-account, and operator object IDs are stored
as non-secret GitHub variables. Runtime database and webhook values are Key
Vault references.

Re-run:

```bash
docker run --rm -v "$PWD:/repo" \
  zricethezav/gitleaks:v8.24.2 \
  detect --source=/repo --config=/repo/.gitleaks.toml --no-banner --redact
```

## GitHub to Azure identity separation

All federated credentials use issuer
`https://token.actions.githubusercontent.com`, audience
`api://AzureADTokenExchange`, and subjects bound to this repository's numeric
owner/repository IDs. There is no wildcard-repository federation.

| Identity | Federation | Effective capability |
|---|---|---|
| Production deployer | `environment:production`; environment permits only `main` | Reader + AcrPush on the exact ACR; Container Apps Contributor on only the API |
| Terraform plan | exact `refs/heads/main` | Reader on app RG/state account, blob data on only the state container, and narrow custom read roles for the API/Function |
| Persistent Terraform apply | exact `refs/heads/main` | Resource-level Contributor on the resources managed in `infra/app`, custom Function operations, state access, and bounded role-assignment rights |
| Phase 9 Terraform apply | exact `refs/heads/main` | AKS operations in the app RG, state access, and condition-limited creation/deletion of only AcrPull for service principals or AKS RBAC Admin for the named user class |

The deployment, plan, and apply identities are separate. Only the jobs that log
in to Azure receive `id-token: write`; reusable validation has read-only
contents permission. The plan workflow cannot silently transition to apply.

Two conscious permission tradeoffs remain:

1. persistent apply has unconditioned RBAC Administrator at the exact ACR
   because Terraform must manage its ACR pull assignment under the registry's
   legacy assignment mode; and
2. the repeatable Phase 9 apply identity has AKS Contributor at the project
   resource-group scope because the cluster is temporary and does not exist as
   a stable narrower pre-provisioned scope.

Neither identity has subscription Owner/Contributor. The stronger app-RG role
assignment held by persistent apply has an Azure condition restricting writes
and deletes to Storage Blob Data Owner assignments for service principals. The
Phase 9 assignment has an equivalent explicit role/principal-type condition.

## Managed identities

| Identity | Assignment/access | Use |
|---|---|---|
| `id-arp-app-wus3` | AcrPull on the exact ACR only | API and retained monitor image pull |
| `id-arp-function-wus3` | Storage Blob Data Owner on the exact Function storage account | Identity-based Function host/package storage |
| Function system identity | Key Vault access policy: Get/List secrets; no Azure RBAC assignment | Resolve `DATABASE_URL` and `WEBHOOK_URL` references |

The human/operator Key Vault policy is Get/List/Set for controlled secret
administration. ACR admin-user access is disabled. Function storage disables
shared keys, enforces HTTPS/TLS 1.2, and blocks public blob access.

The Phase 9 cluster-scoped plan-reader assignment disappeared with the cluster.
No role assignment scoped to a managed cluster or Phase 9 node resource group
remains. The Phase 9 application identity and its static, condition-bounded
roles are retained intentionally because the repository keeps the lab
reproducible; they are not used by the persistent workload.

## IaC reconciliation

### Persistent state

The `infra/app` state has lineage
`cf7dcbb6-a5c0-de04-d87e-14665ab91030`, serial 15, Terraform 1.16.3, and 18
managed instances:

- resource group, Basic ACR, API identity, AcrPull assignment;
- Log Analytics workspace, Container Apps environment and API;
- Application Insights and Workbook;
- Function identity, LRS storage/container and storage role;
- Key Vault and two access policies;
- FC1 Flex Consumption plan and Function.

Trusted-main plan
[37258837487](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/37258837487)
used source `7ddc655b40c8957540881a54f847429851346372`, Terraform 1.16.3,
state serial 15, and the live API image tag. Its retained metadata reported
zero create/read/update/replace/delete operations and its human-readable plan
said, “No changes.” It was not applied.

The API Terraform intentionally ignores only its runtime environment-variable
block because application deployment updates immutable revisions separately.
The Function ignores only the empty legacy key-based storage setting generated
by the provider after identity-based configuration. These lifecycle boundaries
are documented in code, not broad resource-level drift suppression.

### Manual/shared resources

Azure PostgreSQL and `ca-arp-monitor-wus3` predate their current authoritative
classification and are not in `infra/app` state. PostgreSQL is the live durable
incident store. The monitor definition is retained but all eight revisions are
inactive with zero replicas; the Function is the only live scheduler. The
Application Insights smart-detection action group is Azure-managed. These
resources are inventoried explicitly so a clean Terraform plan is not
misrepresented as proof that the entire resource group is managed.

Azure's top-level Container App resource initially reported `runningStatus` as
`Running` even though every revision reported `active=false`,
`runningState=Stopped`, zero replicas, and zero traffic. The last retained
console row was 2026-10-04 06:04:34 UTC, after which the Function supplied the
continuous scheduler record. Phase 10 removed the legacy monitor from the
deployment workflow and verifier so a future API deployment cannot reactivate
it. The resource-level status was then explicitly reconciled through the Azure
Container Apps stop operation and re-audited as `runningStatus=Stopped`; all
eight revisions remained inactive, stopped, at zero replicas and zero traffic.
The now-unused production-deployer role on that monitor was removed after the
workflow change integrated.

Historical `az containerapp update` image changes are expected deployment
operations. The current no-op plan proves no unexplained change inside the
managed fields; it does not erase the documented manual-resource boundary.

### Temporary Phase 9 state

`infra/phase9` uses a different state key and never owns shared app resources.
After reviewed teardown, state lineage
`3fb12007-bf85-15a3-843c-a31a6157b798`, serial 5, contains zero managed
resources and no outputs. The AKS cluster and node resource group are absent.

## Remote state and serialization

| Property | Audited value |
|---|---|
| Backend | AzureRM |
| Resource group | `rg-arp-tfstate-wus3` |
| Storage | dedicated Standard LRS account |
| Container | private `tfstate` |
| Keys | `application.terraform.tfstate`, `phase9.terraform.tfstate` |
| Transport | HTTPS only, minimum TLS 1.2 |
| Authentication | Microsoft Entra/OIDC; shared-key access disabled |
| Public blob access | disabled |
| Locking | native Azure Blob lease |

The audit observed the application blob leased while the trusted-main plan was
active and `unlocked/available` afterward. Both current blobs are unlocked.
Plans use `-lock-timeout=60s`; apply validates the retained plan's state
lineage and serial against a fresh state pull. Source SHA, branch, Terraform
tree, Terraform version, artifact name/hash/size, originating run, expiration,
and maximum age are also verified before exact binary-plan apply.

The state storage and Key Vault endpoints permit public-network routing but
require identity authorization; private endpoints are outside this
portfolio-scale design. Raw state is never committed or included in durable
evidence.

## Result

| Domain | Result | Basis |
|---|---|---|
| Repository credentials | PASS | Redacted history-aware scan and independent pattern/path audit |
| OIDC separation | PASS | Four repository-bound identities with distinct roles |
| Managed identities | PASS | Exact ACR/storage/Key Vault relationships |
| Stale experiment roles | PASS | No cluster-scoped assignment remains |
| Persistent IaC drift | PASS | Current trusted-main zero-change plan |
| Phase 9 reconciliation | PASS | No AKS/node RG; isolated state empty |
| Remote state/locking | PASS | Private blobs, OIDC access, observed lease lifecycle and stale-state guards |
