# Phase 5 concurrent incident-opening proof

Status: **PASS**

Audit date: 2026-10-04 UTC

This evidence closes the only unresolved authoritative Phase 5 requirement:
deterministic proof that overlapping monitor executions cannot create duplicate
incidents or duplicate opening-notification records.

The Incident #2 lifecycle evidence remains accepted independently: one incident
opened after the threshold, sustained failure did not create an alert storm,
recovery closed the incident, both notifications were delivered, and the
duration was persisted. This document does not replace or downgrade that
evidence.

## Existing-test audit

The pre-existing tests did not prove overlap:

| Existing test | What it proves | Why it is not concurrency proof |
|---|---|---|
| `tests/test_runner.py::test_no_duplicate_incidents` | State-machine deduplication for a third sequential failure. | Calls `evaluate` one operation at a time with no shared-store transaction. |
| `tests/test_storage.py::test_duplicate_incident_prevention` | A later failure after restart does not open a second SQLite incident. | The first incident is fully committed before the new store is created. |
| `tests/test_alerts.py::test_recovery_and_no_duplicate_alerts` | A later sequential failure does not add another opening notification. | No operations overlap. |
| Restart-survival tests | State, incidents, and notifications persist across store/process replacement. | Replacement happens after the earlier transaction completes. |
| `tests/test_postgres_integration.py::test_postgres_incident_lifecycle` | PostgreSQL transaction rollback, lifecycle, outbox, retry, and persistence. | Its operations are sequential. |

No existing test used multiple workers, multiple simultaneous database
connections, a transaction barrier, or database lock observation. Those tests
remain valuable but were not accepted as the missing proof.

## Production mechanism under test

The deployed monitor uses `PostgresIncidentStore`. Each call to `record` opens a
transaction and executes:

```sql
SELECT consecutive_failures, incident_open
FROM monitor_state
WHERE id = 1
FOR UPDATE;
```

The singleton row lock serializes incident-state transitions. Incident creation,
opening-notification insertion, check-history insertion, and state update occur
within the same transaction. The local SQLite implementation uses
`BEGIN IMMEDIATE`, but the authoritative Azure persistence path and this
acceptance proof use PostgreSQL.

## Deterministic overlap test

Test:
`tests/test_postgres_integration.py::test_overlapping_checks_open_one_incident`

The test uses only the fixture-protected disposable database named `arp_test`.
Its sequence is:

1. Persist one failure so both new calls arrive at the threshold boundary.
2. Create two `PostgresIncidentStore` instances with distinct PostgreSQL
   `application_name` values, ensuring independent connections.
3. Start worker A. After it acquires the `FOR UPDATE` lock, pause it inside the
   transaction using a `threading.Event`.
4. Start worker B while worker A still holds the row lock.
5. Query `pg_stat_activity` and require worker B to report
   `wait_event_type = 'Lock'`. This establishes actual database overlap; the test
   does not infer concurrency from call order or a sleep.
6. Release worker A, allow both transactions to finish, and inspect persisted
   state through a separate connection.

The five-second waits are failure bounds only. A run passes only if PostgreSQL
reports that the second execution is blocked on the first execution's lock.

## Exact assertions

After both overlapping calls finish, the test requires:

- worker A returns `INCIDENT_OPENED`;
- worker B returns no event after reading worker A's committed open state;
- `consecutive_failures == 3` and `incident_open is True`;
- exactly one incident row exists;
- exactly one pending notification row exists;
- that row belongs to the one incident and has event `INCIDENT_OPENED`.

The notification assertion is important: uniqueness on `(incident_id, event)`
alone would not prevent duplicate opening notifications if a race created two
different incidents. Requiring one incident and one associated opening row
proves the complete state/outbox invariant.

## Test results

Commands were run against a disposable PostgreSQL 17 container bound only to a
Docker-assigned loopback port. The container was stopped and removed afterward.

Baseline before adding the test:

```text
tests/test_runner.py
tests/test_storage.py
tests/test_alerts.py
tests/test_postgres_integration.py

19 passed in 0.77s
```

After adding the deterministic overlap test:

```text
Relevant lifecycle and persistence suite:
20 passed in 0.84s

Full repository suite:
46 passed, 1 warning in 1.08s

Concurrency test repeated independently ten times:
10/10 passed (each run observed the PostgreSQL lock wait)
```

The warning is the existing Starlette deprecation warning for its current
`httpx` TestClient integration; it is unrelated to incident concurrency.

## Acceptance verdict

| Requirement | Evidence | Result |
|---|---|---|
| Existing tests audited before implementation | Test-by-test classification above | PASS |
| Genuine overlap, not sequential deduplication | Two independent connections; worker A held; worker B observed waiting on PostgreSQL `Lock` | PASS |
| Duplicate incidents prevented | Exactly one incident after both calls | PASS |
| Duplicate opening notifications prevented | Exactly one `INCIDENT_OPENED` outbox row tied to that incident | PASS |
| Deterministic and repeatable | Lock-state assertion plus 10/10 repeated passes | PASS |
| Relevant and full suites pass | 20 relevant; 46 full | PASS |

**Phase 5 verdict: PASS.**
