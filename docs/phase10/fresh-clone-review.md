# Phase 10 fresh-clone reviewer evidence

Date: 2026-10-05 UTC
Source: integrated `origin/main`
`a869f849d87271ed310cd07232b7e7e9be313e35`

This is the mandatory reproduction record. It was run in a new temporary
directory, not the development worktree and not a copy with uncommitted files.
No Azure login, cloud apply, AKS creation, production deployment, webhook, or
production database was used.

## Clone and identity

```bash
review_root=$(mktemp -d /tmp/arp-phase10-fresh-main.XXXXXX)
git clone https://github.com/amir-cs-dev/azure-reliability-platform.git \
  "$review_root/azure-reliability-platform"
cd "$review_root/azure-reliability-platform"
git rev-parse HEAD
git rev-parse origin/main
git status --short
```

Result:

```text
HEAD=a869f849d87271ed310cd07232b7e7e9be313e35
ORIGIN_MAIN=a869f849d87271ed310cd07232b7e7e9be313e35
working tree: clean
Python 3.14.7
Docker 29.5.3
Terraform 1.16.3
```

## Documented reviewer path

```bash
scripts/review.sh
```

Results:

| Gate | Result |
|---|---|
| Dependency install from `requirements-dev.txt` | PASS |
| PostgreSQL-backed complete suite | **87 passed**, one upstream Starlette/httpx deprecation warning |
| Function source package | PASS |
| Application image build | PASS |
| Monitor image build | PASS |
| Normal container `/` | exact running message, PASS |
| Normal container `/health` | HTTP 200 `{"status":"healthy"}`, PASS |
| Normal container `/ready` | HTTP 200 `{"status":"ready"}`, PASS |
| Docker health state | `healthy`, PASS |
| `invalid_health` container | HTTP 200 `{"status":"degraded"}`, PASS |
| `http_500` container | HTTP 500 `{"detail":"Controlled health failure"}`, PASS |
| `infra/app` fmt/init without backend/validate | PASS |
| `infra/phase9` fmt/init without backend/validate | PASS |
| Helm lint and render | PASS |
| Kubernetes schema validation | **21 valid, 0 invalid, 0 errors, 0 skipped** |
| Prometheus configuration and rule file | PASS; one rule file, two rules |
| Alertmanager configuration | PASS; one receiver |
| Grafana dashboard JSON/provisioning assets | PASS |
| Script cleanup | PASS; no review containers or review images remained |

Final script output:

```text
PASS: Phase 9 Helm, Kubernetes, Prometheus, Alertmanager, and Grafana artifacts are valid.
PASS: fresh-review application, checker, PostgreSQL, Docker, Terraform, and Phase 9 static validation completed.
```

The clone remained clean after the script; generated Terraform directories were
ignored and all temporary containers, images, virtual environments, and
Function packages were removed.

## Independent focused and repository checks

The same fresh clone then ran:

```bash
python -m pytest tests/test_app.py tests/test_phase8_fault.py -q
python -m pytest tests/test_checker.py -q
docker run --rm -v "$PWD:/repo" -w /repo \
  rhysd/actionlint:1.7.7 .github/workflows/*.yml
docker run --rm -v "$PWD:/repo" \
  zricethezav/gitleaks:v8.24.2 \
  detect --source=/repo --config=/repo/.gitleaks.toml --no-banner --redact
```

Results:

- application/controlled-fault focus: **8 passed**, the same one upstream
  deprecation warning;
- checker focus: **6 passed**;
- every relative Markdown link target exists;
- every GitHub Actions workflow passed Actionlint;
- Gitleaks scanned **37 commits / approximately 574 KB** and reported
  **no leaks found**;
- architecture, deployment, rollback, Phase 9, cost, full teardown, and all 20
  cold-review answers were present and linked; and
- the clone was still clean with no reviewer container or image left.

## Reviewer findings

The README led directly to the one-command path and detailed documents. The
only runtime warning is an upstream FastAPI/Starlette TestClient warning that
recommends future migration from `httpx` to `httpx2`; it does not fail or
skip a test. No confusing or broken command remained after the foundation PR.

The documented cloud boundary is explicit: local reproduction validates code
and assets safely, while retained live reports support historical Azure/AKS
claims. The guide does not imply that the external PostgreSQL server or stopped
legacy monitor is created by `infra/app`, and it does not ask a reviewer to
recreate AKS or cause another outage.

## Verdict

All 18 safe fresh-clone checks requested by Phase 10 are satisfied. Expensive
cloud provisioning and a new production fault were correctly omitted because
Phases 7–9 already retain sufficient live evidence.
