#!/usr/bin/env bash
set -euo pipefail

[[ "${PHASE9_EXPERIMENT:-}" == "RUN" ]] || {
  echo "Refusing experiment: set PHASE9_EXPERIMENT=RUN after the healthy baseline is verified." >&2
  exit 1
}

for command in az curl helm jq kubectl python3; do
  command -v "$command" >/dev/null || {
    echo "Missing required command: $command" >&2
    exit 1
  }
done

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
namespace=arp-phase9
resource_group=rg-arp-app-wus3
function_name=func-arp-monitor-3e6c8737-wus3
workspace=log-arp-app-wus3
evidence=${1:-"/tmp/arp-phase9-evidence-$(date -u +%Y%m%dT%H%M%SZ)"}
mkdir -p "$evidence"

load_pid=""
prometheus_pid=""
alertmanager_pid=""
grafana_pid=""
target_changed=false
original_target=""

cleanup() {
  for pid in "$load_pid" "$prometheus_pid" "$alertmanager_pid" "$grafana_pid"; do
    [[ -n "$pid" ]] && kill "$pid" >/dev/null 2>&1 || true
  done
  if [[ "$target_changed" == true && -n "$original_target" ]]; then
    az functionapp config appsettings set \
      --resource-group "$resource_group" \
      --name "$function_name" \
      --settings "TARGET_URL=$original_target" \
      --output none || true
  fi
  unset grafana_password
}
trap cleanup EXIT

endpoint=$(kubectl -n "$namespace" get service arp-api \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
[[ -n "$endpoint" ]]
application_url="http://$endpoint"

original_target=$(az functionapp config appsettings list \
  --resource-group "$resource_group" \
  --name "$function_name" \
  --query "[?name=='TARGET_URL'].value | [0]" \
  --output tsv)
[[ -n "$original_target" ]]
az functionapp config appsettings set \
  --resource-group "$resource_group" \
  --name "$function_name" \
  --settings "TARGET_URL=$application_url/health" \
  --output none
target_changed=true
target_switched_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)

workspace_id=$(az monitor log-analytics workspace show \
  --resource-group "$resource_group" \
  --workspace-name "$workspace" \
  --query customerId --output tsv)

curl --fail --silent "$application_url/" > "$evidence/baseline-root.json"
curl --fail --silent "$application_url/health" > "$evidence/baseline-health.json"
curl --fail --silent "$application_url/ready" > "$evidence/baseline-ready.json"
curl --fail --silent "$application_url/metrics" > "$evidence/baseline-metrics.txt"

kubectl -n "$namespace" port-forward service/arp-prometheus 19090:9090 \
  > "$evidence/prometheus-port-forward.log" 2>&1 &
prometheus_pid=$!
kubectl -n "$namespace" port-forward service/arp-alertmanager 19093:9093 \
  > "$evidence/alertmanager-port-forward.log" 2>&1 &
alertmanager_pid=$!
kubectl -n "$namespace" port-forward service/arp-grafana 13000:3000 \
  > "$evidence/grafana-port-forward.log" 2>&1 &
grafana_pid=$!
sleep 5

curl --fail --silent http://127.0.0.1:19090/api/v1/targets \
  > "$evidence/prometheus-targets-baseline.json"
curl --fail --silent --get \
  --data-urlencode 'query=up{job="arp-api"}' \
  http://127.0.0.1:19090/api/v1/query \
  > "$evidence/prometheus-app-up-baseline.json"
curl --fail --silent --get \
  --data-urlencode 'query=kube_deployment_status_replicas_available{namespace="arp-phase9",deployment="arp-api"}' \
  http://127.0.0.1:19090/api/v1/query \
  > "$evidence/prometheus-cluster-baseline.json"

grafana_password=$(kubectl -n "$namespace" get secret arp-grafana-admin \
  -o jsonpath='{.data.admin-password}' | base64 --decode)
curl --fail --silent --user "admin:$grafana_password" \
  http://127.0.0.1:13000/api/datasources/uid/prometheus/health \
  > "$evidence/grafana-datasource-health.json"
curl --fail --silent --user "admin:$grafana_password" \
  'http://127.0.0.1:13000/api/search?query=ARP%20Phase%209%20Reliability' \
  > "$evidence/grafana-dashboard-search.json"

from_ms="$(( $(date +%s) - 300 ))000"
to_ms="$(date +%s)000"
curl --fail --silent --user "admin:$grafana_password" \
  --header 'Content-Type: application/json' \
  --data "{\"queries\":[{\"refId\":\"A\",\"datasource\":{\"uid\":\"prometheus\",\"type\":\"prometheus\"},\"expr\":\"sum(rate(arp_http_requests_total[1m]))\",\"instant\":true}],\"from\":\"$from_ms\",\"to\":\"$to_ms\"}" \
  http://127.0.0.1:13000/api/ds/query \
  > "$evidence/grafana-live-query.json"

# A target-setting update restarts the Function host. Waiting 90 seconds spans
# at least one natural one-minute timer boundary without manually invoking it.
sleep 90
az monitor log-analytics query --workspace "$workspace_id" \
  --analytics-query "AppTraces | where TimeGenerated >= datetime('$target_switched_at') | where AppRoleName == '$function_name' | where Message has '$endpoint' or Message has 'scheduled_monitor_completed' | project TimeGenerated, SeverityLevel, Message | order by TimeGenerated asc" \
  --output json > "$evidence/external-checker-baseline.json"

good_revision=$(helm history arp-phase9 --namespace "$namespace" \
  --output json | jq -r 'map(select(.status == "deployed")) | last | .revision')
[[ "$good_revision" =~ ^[0-9]+$ ]]
helm get values arp-phase9 --namespace "$namespace" --output json \
  > "$evidence/helm-good-values.json"
helm history arp-phase9 --namespace "$namespace" --output json \
  > "$evidence/helm-history-before.json"
kubectl -n "$namespace" get deployment,replicaset,pod -o wide \
  > "$evidence/kubernetes-before.txt"

python3 "$root/scripts/phase9/load.py" \
  --url "$application_url/health" \
  --duration 300 --interval 0.25 \
  > "$evidence/load-summary.json" &
load_pid=$!

fault_revision="phase9-http500-$(date -u +%Y%m%dT%H%M%SZ)"
fault_started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
helm upgrade arp-phase9 "$root/deploy/helm/arp-phase9" \
  --namespace "$namespace" \
  --reuse-values \
  --set-string deployment.faultMode=http_500 \
  --set-string "deployment.revision=$fault_revision" \
  --wait --timeout 5m
kubectl -n "$namespace" rollout status deployment/arp-api --timeout=5m
kubectl -n "$namespace" rollout history deployment/arp-api \
  > "$evidence/kubernetes-rollout-history-fault.txt"
kubectl -n "$namespace" get deployment,replicaset,pod -o wide \
  > "$evidence/kubernetes-fault.txt"

sleep 135
curl --silent --get \
  --data-urlencode 'query=ALERTS{alertstate="firing",service="arp-api"}' \
  http://127.0.0.1:19090/api/v1/query \
  > "$evidence/prometheus-alert-firing.json"
curl --fail --silent http://127.0.0.1:19093/api/v2/alerts \
  > "$evidence/alertmanager-alerts-firing.json"
curl --fail --silent http://127.0.0.1:19093/metrics \
  | grep '^alertmanager_notifications_' \
  > "$evidence/alertmanager-notification-metrics.txt"

az monitor log-analytics query --workspace "$workspace_id" \
  --analytics-query "AppTraces | where TimeGenerated >= datetime('$fault_started_at') | where AppRoleName == '$function_name' | where Message has '$endpoint' or Message has 'scheduled_monitor_completed' | project TimeGenerated, SeverityLevel, Message | order by TimeGenerated asc" \
  --output json > "$evidence/external-checker-fault.json"

recovery_started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
helm rollback arp-phase9 "$good_revision" \
  --namespace "$namespace" --wait --timeout 5m
kubectl -n "$namespace" rollout status deployment/arp-api --timeout=5m
kubectl -n "$namespace" rollout history deployment/arp-api \
  > "$evidence/kubernetes-rollout-history-recovery.txt"
helm history arp-phase9 --namespace "$namespace" --output json \
  > "$evidence/helm-history-after-rollback.json"
kubectl -n "$namespace" get deployment,replicaset,pod -o wide \
  > "$evidence/kubernetes-recovered.txt"

sleep 90
curl --fail --silent "$application_url/health" \
  > "$evidence/recovered-health.json"
curl --fail --silent --get \
  --data-urlencode 'query=arp_health_status' \
  http://127.0.0.1:19090/api/v1/query \
  > "$evidence/prometheus-health-recovered.json"
curl --fail --silent http://127.0.0.1:19093/api/v2/alerts \
  > "$evidence/alertmanager-alerts-recovered.json"
az monitor log-analytics query --workspace "$workspace_id" \
  --analytics-query "AppTraces | where TimeGenerated >= datetime('$recovery_started_at') | where AppRoleName == '$function_name' | where Message has '$endpoint' or Message has 'scheduled_monitor_completed' | project TimeGenerated, SeverityLevel, Message | order by TimeGenerated asc" \
  --output json > "$evidence/external-checker-recovery.json"

wait "$load_pid" || true
load_pid=""

echo "Phase 9 experiment complete. Sanitized evidence directory: $evidence"
echo "The external Function target will now be restored by the cleanup handler."
