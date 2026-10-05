#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
chart_relative="deploy/helm/arp-phase9"
chart="$root/$chart_relative"
rendered=$(mktemp /tmp/arp-phase9-rendered.XXXXXX.yaml)
helm_workspace=""
containers=()

cleanup() {
  for container in "${containers[@]:-}"; do
    docker stop "$container" >/dev/null 2>&1 || true
    docker rm "$container" >/dev/null 2>&1 || true
  done
  rm -f "$rendered"
  if [[ -n "$helm_workspace" ]]; then
    rm -rf "$helm_workspace"
  fi
}
trap cleanup EXIT

if command -v helm >/dev/null; then
  (cd "$root" && helm lint "$chart_relative")
  (cd "$root" && helm template arp-phase9 "$chart_relative" \
    --namespace arp-phase9) > "$rendered"
else
  helm_workspace=$(mktemp -d /tmp/arp-phase9-helm.XXXXXX)
  mkdir -p "$helm_workspace/deploy/helm"
  cp -R "$chart" "$helm_workspace/deploy/helm/arp-phase9"
  docker run --rm \
    -v "$helm_workspace:/work" -w /work \
    alpine/helm:3.19.0 lint "$chart_relative" >/dev/null
  docker run --rm \
    -v "$helm_workspace:/work" -w /work \
    alpine/helm:3.19.0 template arp-phase9 "$chart_relative" \
      --namespace arp-phase9 > "$rendered"
fi

docker run --rm -i \
  ghcr.io/yannh/kubeconform:v0.7.0 \
  -strict -summary -ignore-missing-schemas \
  -kubernetes-version 1.35.0 - < "$rendered"

prometheus=$(docker create \
  --entrypoint sh prom/prometheus:v3.7.3 -c 'sleep 300')
containers+=("$prometheus")
docker start "$prometheus" >/dev/null
docker exec "$prometheus" mkdir -p /etc/prometheus/rules
docker cp "$chart/files/prometheus.yml" \
  "$prometheus:/etc/prometheus/prometheus.yml" >/dev/null
docker cp "$chart/files/arp-rules.yml" \
  "$prometheus:/etc/prometheus/rules/arp-rules.yml" >/dev/null
docker exec "$prometheus" \
  promtool check config /etc/prometheus/prometheus.yml

alertmanager=$(docker create \
  --entrypoint sh prom/alertmanager:v0.29.0 -c 'sleep 300')
containers+=("$alertmanager")
docker start "$alertmanager" >/dev/null
docker cp "$chart/files/alertmanager.yml" \
  "$alertmanager:/tmp/alertmanager.yml" >/dev/null
docker exec "$alertmanager" \
  amtool check-config /tmp/alertmanager.yml

python3 -m json.tool \
  "$chart/files/grafana-dashboard.json" >/dev/null

echo "PASS: Phase 9 Helm, Kubernetes, Prometheus, Alertmanager, and Grafana artifacts are valid."
