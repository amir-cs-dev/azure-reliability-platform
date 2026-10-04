# Phase 9 live acceptance runbook

Status: **STAGE 2 ONLY — DO NOT RUN WITHOUT EXPLICIT APPROVAL**

This runbook creates a short-lived AKS lab. It must be executed from a clean
current `main` checkout after the [resource and cost gate](cost-gate.md) is
approved. Do not use `infra/bootstrap`.

## 1. Pre-apply controls

1. Confirm current `main`, clean worktree, green CI, and successful
   `Phase 9 Terraform plan` run for that exact SHA.
2. Register the required Azure providers, wait for completion, and verify the
   selected VM SKU is available within regional subscription quota:

   ```bash
   az provider register --namespace Microsoft.ContainerService --wait
   az provider register --namespace Microsoft.Compute --wait
   az provider register --namespace Microsoft.Network --wait
   az provider show --namespace Microsoft.ContainerService \
     --query registrationState -o tsv
   az provider show --namespace Microsoft.Compute \
     --query registrationState -o tsv
   az provider show --namespace Microsoft.Network \
     --query registrationState -o tsv
   az vm list-usage --location westus3 -o table
   ```

3. Generate a fresh trusted-`main` plan after registration. Download/review
   the plan summary and retained artifact. It must show only
   the three approved creates from the cost gate.
4. Audit the separate Phase 9 apply OIDC identity and configure repository
   variable `AZURE_PHASE9_TERRAFORM_APPLY_CLIENT_ID`. Do not reuse or broaden
   the application infrastructure apply identity.
5. Confirm plan age is below 24 hours and remote-state lineage/serial is still
   the one in plan metadata.
6. Dispatch `Phase 9 Terraform apply reviewed plan` from `main` with the exact
   plan run ID and `confirmation=APPLY`.
7. Retain the apply workflow URL and artifact. Inventory the resulting AKS and
   managed node-resource-group objects and reconcile them to Terraform.

## 2. Deploy the application and in-cluster observability

The script refuses to run unless the guard is explicit. It obtains a temporary
kubeconfig, uses Azure CLI/OIDC session credentials, builds one immutable image
in the existing ACR, resolves its digest, reads the existing Discord webhook
from Key Vault directly into a Kubernetes Secret, generates a temporary
Grafana password, and installs the chart.

```bash
PHASE9_DEPLOY=DEPLOY scripts/phase9/deploy.sh
```

Never paste the generated kubeconfig, Grafana password, or webhook value into
evidence. Confirm:

```bash
kubectl -n arp-phase9 get deployment,replicaset,pod,service
kubectl -n arp-phase9 describe deployment arp-api
kubectl -n arp-phase9 get pod -l app.kubernetes.io/name=arp-api \
  -o jsonpath='{range .items[*]}{.metadata.name}{" ready="}{.status.containerStatuses[0].ready}{" imageID="}{.status.containerStatuses[0].imageID}{"\n"}{end}'
```

The image IDs must contain the reviewed digest, both application pods must be
ready, and the observability Services must not be public.

## 3. Healthy baseline

Capture the public endpoint and verify `/`, `/health`, `/ready`, and `/metrics`.
Wait for at least three natural external Function runs after its controlled
target switch. Confirm Prometheus reports both API targets `UP`, a real
`arp_http_requests_total` query returns samples, kube-state-metrics returns the
API deployment state, Grafana's datasource is healthy, and a Grafana datasource
query returns series data.

Record Kubernetes events, deployment/ReplicaSet state, Helm values/history,
Prometheus target/query output, Grafana API evidence, and sanitized external
checker logs. Screenshots may supplement, but not replace, machine-readable
evidence.

## 4. Controlled rolling-failure and rollback experiment

The guarded experiment performs the reversible target switch, bounded traffic,
real configuration-driven rolling update, alert capture, Helm rollback, and
recovery capture:

```bash
PHASE9_EXPERIMENT=RUN scripts/phase9/experiment.sh \
  /tmp/arp-phase9-evidence-$(date -u +%Y%m%dT%H%M%SZ)
```

Before accepting the run, inspect its output and prove all of these facts:

1. healthy endpoint and external-checker baseline;
2. Prometheus application targets `UP` and cluster metric present;
3. Grafana datasource/dashboard and live query return real data;
4. known-good Helm revision and ReplicaSet identified;
5. `http_500` Helm revision creates a different ReplicaSet and rolling history
   records the change while the immutable image digest is unchanged;
6. bounded load sees the expected status transition;
7. the real 5xx rule is firing in Prometheus;
8. Alertmanager receives it and notification metrics prove a send attempt;
9. the external Function independently records the failure/incident behavior;
10. `helm rollback` targets the recorded good revision and creates/restores the
    expected rollout state;
11. endpoint, Prometheus, Alertmanager, Grafana, and external checker all show
    recovery; and
12. the Function `TARGET_URL` is restored to its original value even if the
    experiment exits early.

Also obtain the actual Discord notification and resolved-notification evidence
without recording the webhook URL. A delivery counter alone does not prove
receipt at the destination.

## 5. Retain sanitized evidence

Copy only reviewed, secret-free artifacts into `docs/phase9/evidence/`. Add a
manifest containing UTC timestamps, source and image digests, workflow/run
URLs, cluster version, Helm revisions, file hashes, and the operator's explicit
interpretation. Never commit kubeconfig material, bearer tokens, passwords,
webhooks, Terraform binary plans, raw state, or unredacted environment output.

Update the ACT-9 matrix one row at a time. A valid configuration or successful
command does not replace live evidence.

## 6. Mandatory teardown

After evidence is committed and safely available, remove Kubernetes workloads
first:

```bash
PHASE9_TEARDOWN=DESTROY_K8S scripts/phase9/teardown.sh
```

Dispatch a new current-`main` Phase 9 `destroy` plan. Review that it deletes
only the cluster and two Phase 9 role assignments. Apply that exact binary
destroy plan through the separate manual workflow with literal `APPLY`.

Verify:

```bash
az aks show --resource-group rg-arp-app-wus3 \
  --name aks-arp-phase9-wus3
az group exists --name rg-arp-phase9-nodes-wus3
az acr show --resource-group rg-arp-app-wus3 \
  --name arp3e6c8737fb3a44be8477 --query name -o tsv
az functionapp show --resource-group rg-arp-app-wus3 \
  --name func-arp-monitor-3e6c8737-wus3 --query state -o tsv
```

The first command must return not found, the node resource group must return
`false`, and the shared ACR and Function must still exist. Run a fresh normal
plan showing the expected three creates and zero tracked live lab resources.
Only then can the teardown row pass.
