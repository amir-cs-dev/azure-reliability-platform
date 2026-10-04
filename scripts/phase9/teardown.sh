#!/usr/bin/env bash
set -euo pipefail

[[ "${PHASE9_TEARDOWN:-}" == "DESTROY_K8S" ]] || {
  echo "Refusing teardown: set PHASE9_TEARDOWN=DESTROY_K8S after evidence is retained." >&2
  exit 1
}

namespace=arp-phase9

helm uninstall arp-phase9 --namespace "$namespace" --wait
kubectl delete namespace "$namespace" --wait=true

cat <<'EOF'
Kubernetes workloads and the application LoadBalancer were removed.
Next: create and review a Phase 9 Terraform destroy plan, then run the separate
manual Phase 9 apply workflow with literal APPLY. Do not destroy infra/app.
EOF
