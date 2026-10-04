# Incident 002 Application Insights evidence

Evidence type: **verified read-only Azure Log Analytics query**

Queried on 2026-10-04 UTC against the workspace-backed Application Insights
resource `appi-arp-app-wus3`. The query window is the exact persisted Incident
#2 interval, inclusive of the opening and recovery checker timestamps.

## Query

```kusto
AppRequests
| where TimeGenerated between (
    datetime(2026-09-23T00:57:34.655888Z) ..
    datetime(2026-09-23T01:00:41.511268Z)
)
| where Url has "/health" or Name has "health"
| extend request_path = case(
    Url startswith "http://localhost", "container-local",
    Url has "azurecontainerapps.io", "public-endpoint",
    "other"
)
| summarize
    requests=count(),
    http_200=countif(ResultCode == "200"),
    success_true=countif(Success == true)
  by request_path
| order by request_path asc
```

## Result

| request path | captured requests | HTTP 200 | `Success=True` |
|---|---:|---:|---:|
| container-local | 38 | 38 | 38 |
| public-endpoint | 23 | 23 | 23 |
| **total** | **61** | **61** | **61** |

The Azure CLI returned the two grouped rows exactly as follows:

```json
[
  {
    "http_200": "38",
    "request_path": "container-local",
    "requests": "38",
    "success_true": "38"
  },
  {
    "http_200": "23",
    "request_path": "public-endpoint",
    "requests": "23",
    "success_true": "23"
  }
]
```

## Reliability finding

During the same interval, the independent external checker observed a
semantically unhealthy response, opened Incident #2, remained unhealthy, and
later recovered after rollback. The controlled application fault returned HTTP
200 with JSON equivalent to:

```json
{"status":"degraded"}
```

Application Insights therefore recorded correct HTTP-layer facts: the captured
requests completed with status 200 and the SDK classified them as successful.
Those facts did not establish the application's semantic health contract. The
checker evaluated the response body and supplied the signal that `AppRequests`
did not.

## What this evidence proves

- Application Insights was receiving real request telemetry during Incident #2.
- It is workspace-backed and queryable alongside Container Apps logs.
- All 23 captured public `/health` rows in the exact interval were HTTP 200 and
  `Success=True`.
- HTTP/request success alone would have produced a false-negative view of this
  semantic incident.
- A separate semantic checker is necessary for this failure mode.

## What this evidence does not prove

- It does not prove that the response body was healthy; `AppRequests` did not
  evaluate the JSON contract.
- It does not prove continuous availability between external checker samples.
- It does not establish that Application Insights captured 100% of all requests.
  No sampling percentage is asserted.
- It does not identify the Container App revision that served each request.
- It does not prove the cutover-race mechanism for the old verifier's early
  successful request.
- It does not represent a production availability SLI or SLA.

## Reviewer reproduction

Run the KQL above in the Log Analytics workspace connected to
`appi-arp-app-wus3`. Historical reproduction remains subject to Azure retention;
the result table above is the durable repository evidence captured while the
rows were still queryable.
