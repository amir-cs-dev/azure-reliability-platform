#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
chart="$root/deploy/helm/arp-phase9"
rendered=$(mktemp /tmp/arp-phase9-rendered.XXXXXX.yaml)
containers=()

cleanup() {
  for container in "${containers[@]:-}"; do
    docker stop "$container" >/dev/null 2>&1 || true
    docker rm "$container" >/dev/null 2>&1 || true
  done
  rm -f "$rendered"
}
trap cleanup EXIT

helm lint "$chart"
helm template arp-phase9 "$chart" \
  --namespace arp-phase9 > "$rendered"

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
