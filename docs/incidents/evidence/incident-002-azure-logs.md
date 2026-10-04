# Incident 002 Azure monitor, revision, and persistence evidence

Evidence type: **verified read-only Azure inspection**

Captured on 2026-10-04 UTC. Secret values, connection strings, subscription
identifiers, identity identifiers, and the Discord webhook URL are intentionally
excluded.

## External checker and lifecycle logs

Query:

```kusto
ContainerAppConsoleLogs_CL
| where TimeGenerated between (
    datetime(2026-09-23T00:56:30Z) ..
    datetime(2026-09-23T01:01:30Z)
)
| where ContainerAppName_s == "ca-arp-monitor-wus3"
| where Log_s contains "healthy="
    or Log_s contains "EVENT:"
    or Log_s contains "ALERT DELIVERY"
| project TimeGenerated, RevisionName_s, Log_s
| order by TimeGenerated asc
```

Selected exact results:

| Embedded checker timestamp / ingestion time | Monitor revision | Log |
|---|---|---|
| `00:57:24.529149` / `00:57:25.197405` | `--0000005` | `healthy=True`, `latency=32.62ms`, `failures=0` |
| `00:57:28.461551` / `00:57:29.198726` | `--0000006` | `healthy=False`, `latency=27.08ms`, `failures=1` |
| `00:57:34.655888` / `00:57:36.243017` | `--0000005` | `healthy=False`, `latency=24.13ms`, `failures=2` |
| ingestion `00:57:36.243017` | `--0000005` | `EVENT: INCIDENT_OPENED` |
| ingestion `00:57:36.243017` | `--0000005` | `ALERT DELIVERY: {'delivered': 1, 'failed': 0, 'exhausted': 0}` |
| `00:57:38.615327` / `00:57:39.212736` | `--0000006` | `healthy=False`, `failures=3` |
| `00:57:45.341911` / `00:57:46.320633` | `--0000005` | `healthy=False`, `failures=4` |
| `00:57:48.785950` / `00:57:50.298657` | `--0000006` | `healthy=False`, `failures=5` |
| `00:57:55.489848` / `00:57:56.254076` | `--0000005` | `healthy=False`, `failures=6` |
| `00:57:58.920514` / `00:58:00.421464` | `--0000006` | `healthy=False`, `failures=7` |
| `00:58:05.625346` through `01:00:21.186741` | `--0000005` then `--0000006` | continuous retained failures `8` through `23` |
| `01:00:31.336924` / `01:00:32.224167` | `--0000006` | `healthy=False`, `latency=22.29ms`, `failures=24` |
| `01:00:41.511268` / `01:00:42.324458` | `--0000006` | `healthy=True`, `latency=47.36ms`, `failures=0` |
| ingestion `01:00:42.324458` | `--0000006` | `EVENT: RECOVERED` |
| ingestion `01:00:43.223919` | `--0000006` | `ALERT DELIVERY: {'delivered': 1, 'failed': 0, 'exhausted': 0}` |
| `01:00:52.049672` / `01:00:53.208150` | `--0000006` | `healthy=True`, `failures=0` |

The checker timestamp is written by the monitor when the request completes;
`TimeGenerated` is the later Azure ingestion timestamp. They must not be treated
as interchangeable.

Two monitor revisions briefly overlapped during Deploy #4 and shared the
PostgreSQL state. This incident record shows one opening event despite the
overlap, but the exact concurrent-execution acceptance gate remains a separate
Phase 5 audit and is not claimed here.

## API revision and rollback logs

Query:

```kusto
ContainerAppSystemLogs_CL
| where TimeGenerated between (
    datetime(2026-09-23T00:54:00Z) ..
    datetime(2026-09-23T01:21:00Z)
)
| where ContainerAppName_s == "ca-arp-api-wus3"
| project TimeGenerated, RevisionName_s, Reason_s, Log_s
| order by TimeGenerated asc
```

Exact incident-relevant results:

| TimeGenerated | Revision | Reason | Log |
|---|---|---|---|
| `00:56:35.9490402` | prior `--0000005` in row metadata | `RevisionCreation` | `Creating a new revision: ca-arp-api-wus3--0000006` |
| `00:56:37.0027549` | `--0000006` | `AssigningReplica` | replica scheduled for revision `--0000006` |
| `00:56:52.1375058` | `--0000006` | `PulledImage` | pulled `reliability-api:5d8e213ed5d08f37d8de362f1e8849bfebd33d81` |
| `00:56:53.9088237` | `--0000006` | `ContainerStarted` | started container `fastapi` |
| `00:57:56.0886491` | `--0000005` | `ContainerTerminated` | prior container terminated as `ManuallyStopped` |
| `00:59:55.9417032` | prior `--0000006` in row metadata | `RevisionCreation` | `Creating a new revision: ca-arp-api-wus3--0000007` |
| `01:00:10.9337261` | `--0000007` | `PulledImage` | pulled `reliability-api:9c506ada6114c550c1191d738d1291e0fae20cf9` |
| `01:00:13.9394011` | `--0000007` | `ContainerStarted` | started container `fastapi` |
| `01:01:12.9367411` | `--0000006` | `ContainerTerminated` | broken container terminated as `ManuallyStopped` |
| `01:18:32.9624355` | prior `--0000008` in row metadata | `RevisionCreation` | `Creating a new revision: ca-arp-api-wus3--0000009` |
| `01:18:47.8898843` | `--0000009` | `PulledImage` | pulled `reliability-api:e531acdbcc1ef3b85e46e213b4130acaba31ef4b` |
| `01:18:55.9594977` | `--0000009` | `ContainerStarted` | started container `fastapi` |

The current Container Apps revision listing retains only active revision
`ca-arp-api-wus3--0000009`; the historical system-log rows above are therefore
the durable exact references for broken revision `--0000006` and rollback
revision `--0000007`.

## Deploy #5 verifier evidence

Retained GitHub Actions run `35805627905`, deploy job `107005903828`:

```text
2026-09-23T01:19:00.6745499Z Target API revision: ca-arp-api-wus3--0000009
2026-09-23T01:19:02.2370993Z PASS: Exact deployed revision has 100% traffic.
2026-09-23T01:19:13.6865139Z PASS: Health/readiness sample 1/6
2026-09-23T01:19:25.4251303Z PASS: Health/readiness sample 2/6
2026-09-23T01:19:36.9441846Z PASS: Health/readiness sample 3/6
2026-09-23T01:19:48.6402842Z PASS: Health/readiness sample 4/6
2026-09-23T01:19:59.8327035Z PASS: Health/readiness sample 5/6
2026-09-23T01:20:10.9307878Z PASS: Health/readiness sample 6/6
2026-09-23T01:20:10.9308687Z PASS: Deployment verified after cutover.
```

## Persisted incident and notifications

The following projections were selected directly from the live monitor
PostgreSQL database from inside the monitor container. The connection string was
consumed only by the running process and was not printed.

```sql
SELECT id, opened_at, recovered_at, duration_seconds
FROM incidents
WHERE id = 2;
```

```text
(2,
 '2026-09-23T00:57:34.655888+00:00',
 '2026-09-23T01:00:41.511268+00:00',
 186.855)
```

```sql
SELECT id, incident_id, event, status, attempts, delivered_at, last_error
FROM notifications
WHERE incident_id = 2
ORDER BY id;
```

```text
(3, 2, 'INCIDENT_OPENED', 'delivered', 1,
 '2026-09-23T00:57:35.256595+00:00', NULL)
(4, 2, 'RECOVERED', 'delivered', 1,
 '2026-09-23T01:00:41.963336+00:00', NULL)
```

Repository code in `monitor/alerts.py` records `delivered` only after the HTTPS
webhook returns HTTP 2xx. These rows therefore demonstrate endpoint acceptance
and durable delivery state, not human viewing of the Discord messages.

## Boundaries

- No Azure resource was changed while capturing this evidence.
- No database row was inserted, updated, or deleted.
- No credential, password, token, connection string, or webhook URL is included.
- Historical log ingestion and source-event timestamps are both shown where
  available.
- The exact revision serving Deploy #4's early successful verifier request is
  absent; the cutover-race explanation remains a strong inference.
