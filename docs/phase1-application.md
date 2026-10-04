# Phase 1 monitored application acceptance evidence

Status: **PASS**

Audit date: 2026-10-04 UTC

This document closes ACT-1 with two intentionally reproducible and genuinely
different application failure modes. Both are enabled only through process
configuration; no HTTP fault-control endpoint exists.

## Pre-change audit

The application already provided:

- `GET /` returning the normal application message;
- `GET /health` returning `{"status":"healthy"}` by default;
- `GET /ready` returning `{"status":"ready"}`;
- `ARP_PHASE8_FAULT=invalid_health`, which changes `/health` to HTTP 200 with
  `{"status":"degraded"}`.

No second dormant app-level failure behavior existed. Checker tests for HTTP
500, timeout, and connection failure used mocks; they did not make the
application itself reproduce those failures and therefore did not satisfy
ACT-1.

## Implementation

`app/main.py` now recognizes a second value of the existing backward-compatible
configuration variable:

| Configuration | `/health` behavior | Failure class |
|---|---|---|
| variable unset | HTTP 200, `{"status":"healthy"}` | Normal/default |
| `ARP_PHASE8_FAULT=invalid_health` | HTTP 200, `{"status":"degraded"}` | Semantic contract failure |
| `ARP_PHASE8_FAULT=http_500` | HTTP 500, `{"detail":"Controlled health failure"}` | HTTP status failure |

The two faults are distinct at the protocol level. Mode A deliberately succeeds
at HTTP transport while violating the expected JSON contract. Mode B fails the
HTTP request with status 500. They are not two invalid JSON values.

## Safety properties

- Fault activation requires an environment variable before process/container
  startup.
- There is no route that turns a fault on or off.
- With the variable unset, production-default behavior is unchanged.
- The existing `invalid_health` value and its Phase 8 behavior are preserved.
- The fault logic is limited to `/health`; Mode B's Docker demonstration also
  verifies that `/` and `/ready` remain HTTP 200 while `/health` is HTTP 500.
- No Azure resource or deployed configuration was changed for this audit.

## Test evidence

Focused command:

```bash
./.venv/bin/python -m pytest -q \
  tests/test_app.py tests/test_phase8_fault.py
```

Result:

```text
8 passed, 1 warning in 1.39s
```

The focused tests exercise the HTTP interface through FastAPI's test client and
assert exact status/body pairs for normal health and both controlled faults.

Full suite command:

```bash
PG_TEST_DATABASE_URL=<disposable-local-arp_test-url> \
  ./.venv/bin/python -m pytest -q
```

Result:

```text
48 passed, 1 warning in 2.23s
```

The warning is the existing Starlette deprecation warning for its current
`httpx` TestClient integration; it is unrelated to application behavior.

## Docker evidence

The application image was built once and the same image was used for the normal
and both fault demonstrations.

Build:

```bash
docker build -t azure-reliability-platform:phase1-act1 .
docker image inspect azure-reliability-platform:phase1-act1 \
  --format '{{.Id}}'
```

Result:

```text
sha256:d987c45f3dce284c2cd099a7cd9c456318f11bed3faf8c0f8cd678b7acb56936
```

### Normal/default container

```bash
docker run --rm -d \
  --name arp-phase1-normal \
  -p 127.0.0.1:18001:8000 \
  azure-reliability-platform:phase1-act1
```

Observed responses:

```text
GET /        -> HTTP 200 {"message":"Azure Reliability Platform is running"}
GET /health -> HTTP 200 {"status":"healthy"}
GET /ready  -> HTTP 200 {"status":"ready"}
```

Docker inspection:

```text
status=running health=healthy user=appuser
image=sha256:d987c45f3dce284c2cd099a7cd9c456318f11bed3faf8c0f8cd678b7acb56936
```

This proves the application starts as the configured non-root user and passes
its Docker health check under normal configuration.

### Failure mode A: semantic invalid health

```bash
docker run --rm -d \
  --name arp-phase1-invalid-health \
  -e ARP_PHASE8_FAULT=invalid_health \
  -p 127.0.0.1:18002:8000 \
  azure-reliability-platform:phase1-act1
```

Observed while the container was running:

```text
configured_fault=ARP_PHASE8_FAULT=invalid_health
GET /health -> HTTP 200 {"status":"degraded"}
```

The Dockerfile health check validates HTTP success only, so direct response-body
evidence—not Docker's health label—is authoritative for this semantic fault.
The independent application checker performs the required semantic validation.

### Failure mode B: controlled HTTP 500

```bash
docker run --rm -d \
  --name arp-phase1-http-500 \
  -e ARP_PHASE8_FAULT=http_500 \
  -p 127.0.0.1:18003:8000 \
  azure-reliability-platform:phase1-act1
```

Observed while the container was running:

```text
configured_fault=ARP_PHASE8_FAULT=http_500
GET /        -> HTTP 200 {"message":"Azure Reliability Platform is running"}
GET /ready  -> HTTP 200 {"status":"ready"}
GET /health -> HTTP 500 {"detail":"Controlled health failure"}
```

All three application containers and the disposable PostgreSQL test container
were stopped and removed after the demonstration.

## ACT-1 audit

| ACT-1 requirement | Demonstration | Result |
|---|---|---|
| 1. Normal application response works | Unit test and Docker `GET /` returned the exact message with HTTP 200 | PASS |
| 2. `/health` works | Unit test and normal Docker container returned HTTP 200 healthy | PASS |
| 3. `/ready` works | Unit test and normal Docker container returned HTTP 200 ready | PASS |
| 4. Failure mode A intentionally reproducible | Environment-driven `invalid_health` returned HTTP 200 degraded in tests and Docker | PASS |
| 5. Failure mode B intentionally reproducible | Environment-driven `http_500` returned HTTP 500 in tests and Docker | PASS |
| 6. Tests pass | 8 focused; 48 full | PASS |
| 7. Application runs correctly in Docker | One image built; normal container running/healthy; all normal endpoints and both faults demonstrated | PASS |

**Phase 1 verdict: PASS.**
