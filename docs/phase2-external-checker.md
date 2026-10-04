# Phase 2 external checker acceptance

Date: 2026-10-04 UTC

Verdict: **PASS**

The Stage A audit inspected the implementation and existing tests before making
changes. The existing checker suite already proves every ACT-2 behavior, so no
redundant implementation or test was added.

## Implementation contract

`monitor/checker.py` exposes the single `check_health` implementation used by
the monitoring service. It performs an external request with a five-second
timeout, requires both HTTP 200 and the exact semantic body status `healthy`,
and catches request and response-decoding failures.

Every return path has the same structured fields:

- `timestamp`: timezone-aware UTC ISO-8601 timestamp;
- `healthy`: boolean classification;
- `status_code`: received HTTP status, or `None` when no response exists;
- `latency_ms`: elapsed request/check time;
- `error`: `None` for a healthy result and diagnostic text for a failure.

The durable stores persist the timestamp, classification, status, latency, and
error. `tests/test_check_history.py` and the PostgreSQL history integration test
cover that storage shape.

## Test evidence

Commands run from the repository root:

```text
.venv/bin/python -m pytest tests/test_checker.py -q
6 passed in 0.20s

.venv/bin/python -m pytest \
  tests/test_checker.py tests/test_check_history.py tests/test_runner.py -q
14 passed in 0.30s

PG_TEST_DATABASE_URL=<disposable-local-arp_test-url> \
  .venv/bin/python -m pytest -q
62 passed, 1 existing warning in 2.14s
```

The PostgreSQL tests ran against a disposable local database named `arp_test`.
No production database or credential was used, and the URL is intentionally
redacted from this evidence.

## ACT-2 matrix

| ACT-2 requirement | Exact evidence | Result |
|---|---|---|
| Healthy response | `test_healthy_response` supplies HTTP 200 plus `{"status":"healthy"}` and asserts healthy classification, status, no error, latency, and timestamp. | **PASS** |
| HTTP failure | `test_http_500_failure` supplies HTTP 500 and asserts unhealthy classification and retained status 500. | **PASS** |
| Invalid semantic content | `test_incorrect_health_content` supplies HTTP 200 plus `{"status":"unhealthy"}` and asserts unhealthy classification. This proves semantic validation is independent of transport success. | **PASS** |
| Timeout | `test_request_timeout` raises `requests.Timeout` and asserts unhealthy classification, absent HTTP status, and the timeout diagnostic. | **PASS** |
| Connection/request exception | `test_connection_failure` raises `requests.ConnectionError` and asserts unhealthy classification, absent HTTP status, and the connection diagnostic. | **PASS** |
| Structured timestamp | `test_healthy_response` asserts the timestamp field; both success and exception return paths construct timezone-aware UTC ISO-8601 timestamps in `check_health`. | **PASS** |
| Structured health/status classification | Healthy, HTTP failure, semantic failure, timeout, and connection tests assert `healthy`; response tests also assert `status_code`. | **PASS** |
| Structured latency | `test_healthy_response` asserts non-negative `latency_ms`; both implementation return paths calculate elapsed latency. | **PASS** |
| Error information where applicable | Healthy test asserts `error is None`; timeout, connection, and invalid-JSON tests assert their diagnostic text; HTTP/semantic failures return `Unhealthy response`. | **PASS** |

All exact ACT-2 requirements are implemented, tested, demonstrated by the
focused executable suite, and evidenced here. Phase 2 is therefore **PASS**,
with no pending-audit qualifier.
