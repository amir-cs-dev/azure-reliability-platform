#!/usr/bin/env bash
set -euo pipefail

[[ "${PHASE9_DEPLOY:-}" == "DEPLOY" ]] || {
  echo "Refusing deployment: set PHASE9_DEPLOY=DEPLOY after the approved AKS apply." >&2
  exit 1
}

for command in az kubectl kubelogin helm openssl; do
  command -v "$command" >/dev/null || {
    echo "Missing required command: $command" >&2
    exit 1
  }
done

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
resource_group=rg-arp-app-wus3
cluster=aks-arp-phase9-wus3
namespace=arp-phase9
registry=arp3e6c8737fb3a44be8477
repository=reliability-api
vault=kv-arp-fn-3e6c8737
image_tag=${1:-"phase9-$(git -C "$root" rev-parse --short=12 HEAD)"}
kubeconfig=$(mktemp /tmp/arp-phase9-kubeconfig.XXXXXX)

cleanup() {
  unset webhook_url grafana_password
  rm -f "$kubeconfig"
}
trap cleanup EXIT

export KUBECONFIG="$kubeconfig"
az aks get-credentials \
  --resource-group "$resource_group" \
  --name "$cluster" \
  --overwrite-existing >/dev/null
kubelogin convert-kubeconfig -l azurecli

az acr build \
  --registry "$registry" \
  --image "$repository:$image_tag" \
  "$root" >/dev/null

digest=$(az acr manifest list-metadata \
  --registry "$registry" \
  --name "$repository" \
  --query "[?tags != null && contains(tags, '$image_tag')].digest | [0]" \
  --output tsv)
[[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] || {
  echo "Unable to resolve the immutable ACR image digest." >&2
  exit 1
}

kubectl create namespace "$namespace" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

webhook_url=$(az keyvault secret show \
  --vault-name "$vault" \
  --name webhook-url \
  --query value --output tsv)
[[ -n "$webhook_url" ]]
kubectl -n "$namespace" create secret generic arp-alertmanager-webhook \
  --from-literal=webhook-url="$webhook_url" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

grafana_password=$(openssl rand -hex 24)
kubectl -n "$namespace" create secret generic arp-grafana-admin \
  --from-literal=admin-password="$grafana_password" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

helm upgrade --install arp-phase9 \
  "$root/deploy/helm/arp-phase9" \
  --namespace "$namespace" \
  --set-string "image.repository=$registry.azurecr.io/$repository" \
  --set-string "image.digest=$digest" \
  --set-string "deployment.revision=$image_tag" \
  --wait --timeout 10m

kubectl -n "$namespace" rollout status deployment/arp-api --timeout=5m
kubectl -n "$namespace" wait \
  --for=condition=Available deployment/arp-prometheus \
  --for=condition=Available deployment/arp-alertmanager \
  --for=condition=Available deployment/arp-grafana \
  --for=condition=Available deployment/arp-kube-state-metrics \
  --timeout=5m

for _ in $(seq 1 60); do
  endpoint=$(kubectl -n "$namespace" get service arp-api \
    -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
  [[ -n "$endpoint" ]] && break
  sleep 5
done
[[ -n "${endpoint:-}" ]] || {
  echo "The application LoadBalancer did not receive a public IP." >&2
  exit 1
}

echo "Phase 9 chart deployed from immutable digest $digest."
echo "Application endpoint: http://$endpoint"
echo "Grafana remains ClusterIP-only; use kubectl port-forward service/arp-grafana 3000:3000."
