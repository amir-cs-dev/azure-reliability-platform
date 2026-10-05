#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
review_tmp=$(mktemp -d /tmp/arp-review.XXXXXX)
run_suffix="$$"
postgres_container="arp-review-postgres-$run_suffix"
normal_container="arp-review-normal-$run_suffix"
semantic_container="arp-review-semantic-$run_suffix"
http_container="arp-review-http500-$run_suffix"
api_image="arp-review-api:$run_suffix"
monitor_image="arp-review-monitor:$run_suffix"

cleanup() {
  docker rm -f \
    "$normal_container" "$semantic_container" "$http_container" \
    "$postgres_container" >/dev/null 2>&1 || true
  docker image rm "$api_image" "$monitor_image" >/dev/null 2>&1 || true
  rm -rf "$review_tmp"
}
trap cleanup EXIT

for command in python3 docker terraform curl git; do
  command -v "$command" >/dev/null || {
    echo "Missing required command: $command" >&2
    exit 1
  }
done

cd "$root"

python3 -m venv "$review_tmp/venv"
review_python="$review_tmp/venv/bin/python"
"$review_python" -m pip install --quiet --upgrade pip
"$review_python" -m pip install --quiet -r requirements-dev.txt

docker run --detach --name "$postgres_container" \
  --env POSTGRES_USER=arp_review \
  --env POSTGRES_PASSWORD=local_review_only \
  --env POSTGRES_DB=arp_test \
  --publish 127.0.0.1::5432 \
  postgres:16 >/dev/null

for _ in $(seq 1 30); do
  if docker exec "$postgres_container" \
    pg_isready -U arp_review -d arp_test >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
docker exec "$postgres_container" \
  pg_isready -U arp_review -d arp_test >/dev/null

postgres_binding=$(docker port "$postgres_container" 5432/tcp | head -1)
postgres_port=${postgres_binding##*:}
export PG_TEST_DATABASE_URL="postgresql://arp_review:local_review_only@127.0.0.1:$postgres_port/arp_test"

echo "== Python and PostgreSQL test suite =="
"$review_python" -m pytest tests/ -q

echo "== Azure Function package =="
"$review_python" scripts/build_function_package.py \
  --output "$review_tmp/arp-function.zip" >/dev/null
"$review_python" -m zipfile --list "$review_tmp/arp-function.zip" >/dev/null

echo "== Application and monitor images =="
docker build --quiet --tag "$api_image" . >/dev/null
docker build --quiet --file Dockerfile.monitor \
  --tag "$monitor_image" . >/dev/null

start_application() {
  local container_name=$1
  local fault_mode=${2:-}
  local docker_args=(
    run --detach --name "$container_name"
    --publish 127.0.0.1::8000
  )
  if [[ -n "$fault_mode" ]]; then
    docker_args+=(--env "ARP_PHASE8_FAULT=$fault_mode")
  fi
  docker_args+=("$api_image")
  docker "${docker_args[@]}" >/dev/null
}

container_url() {
  local container_name=$1
  local binding
  binding=$(docker port "$container_name" 8000/tcp | head -1)
  printf 'http://127.0.0.1:%s' "${binding##*:}"
}

wait_ready() {
  local base_url=$1
  for _ in $(seq 1 30); do
    if curl --fail --silent "$base_url/ready" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

echo "== Normal container behavior =="
start_application "$normal_container"
normal_url=$(container_url "$normal_container")
wait_ready "$normal_url"
[[ "$(curl --fail --silent "$normal_url/")" == \
  '{"message":"Azure Reliability Platform is running"}' ]]
[[ "$(curl --fail --silent "$normal_url/health")" == \
  '{"status":"healthy"}' ]]
[[ "$(curl --fail --silent "$normal_url/ready")" == \
  '{"status":"ready"}' ]]
for _ in $(seq 1 15); do
  [[ "$(docker inspect --format '{{.State.Health.Status}}' "$normal_container")" == "healthy" ]] && break
  sleep 1
done
[[ "$(docker inspect --format '{{.State.Health.Status}}' "$normal_container")" == "healthy" ]]

echo "== Semantic-health fault =="
start_application "$semantic_container" invalid_health
semantic_url=$(container_url "$semantic_container")
wait_ready "$semantic_url"
[[ "$(curl --fail --silent "$semantic_url/health")" == \
  '{"status":"degraded"}' ]]

echo "== HTTP-500 fault =="
start_application "$http_container" http_500
http_url=$(container_url "$http_container")
wait_ready "$http_url"
http_status=$(curl --silent --output "$review_tmp/http500.json" \
  --write-out '%{http_code}' "$http_url/health")
[[ "$http_status" == "500" ]]
[[ "$(<"$review_tmp/http500.json")" == \
  '{"detail":"Controlled health failure"}' ]]

echo "== Terraform =="
terraform fmt -check -recursive infra/app infra/phase9
terraform -chdir=infra/app init -backend=false -input=false >/dev/null
terraform -chdir=infra/app validate
terraform -chdir=infra/phase9 init -backend=false -input=false >/dev/null
terraform -chdir=infra/phase9 validate

echo "== Helm, Kubernetes, Prometheus, Alertmanager, and Grafana =="
scripts/phase9/validate.sh

echo "PASS: fresh-review application, checker, PostgreSQL, Docker, Terraform, and Phase 9 static validation completed."
