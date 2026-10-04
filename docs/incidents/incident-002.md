# Incident 002: semantically degraded health after Deploy #4

Status: **closed; ACT-7 and ACT-8 evidence complete**

All timestamps in this report are UTC. This report is the reviewer-visible
timeline for the Phase 7 observability and Phase 8 rollback acceptance gates.
It distinguishes directly verified records from inference and does not include
credentials, connection strings, or the Discord webhook URL.

## Executive summary

Deploy #4 installed image commit `5d8e213ed5d08f37d8de362f1e8849bfebd33d81`
as API revision `ca-arp-api-wus3--0000006`. The controlled setting
`ARP_PHASE8_FAULT=invalid_health` made `/health` return HTTP 200 with the
semantically unhealthy body `{"status":"degraded"}`.

The then-current deployment verifier returned success after one health/readiness
attempt. The independent checker subsequently rejected the response body,
opened Incident #2 after its second consecutive failure, delivered the opening
notification, and continued to record failures without creating another
incident. The operator rolled the API back to image commit
`9c506ada6114c550c1191d738d1291e0fae20cf9`. Azure created known-good revision
`ca-arp-api-wus3--0000007`; the checker then observed semantic health, persisted
recovery after **186.855 seconds**, and delivered the recovery notification.

During the exact persisted incident interval, Application Insights captured 23
public `/health` request rows and marked all 23 as HTTP 200 and `Success=True`.
That signal was accurate at the HTTP layer but blind to the response-body
contract. The external checker supplied the missing semantic signal.

The evidence strongly supports a revision-cutover false green: the old verifier
ran while the prior revision had not yet been terminated and did not identify
which revision served its request. It does **not** prove that the successful
request was served by the prior revision, so this report does not present that
mechanism as certain.

## Scope and evidence classification

| Classification | Meaning in this report |
|---|---|
| Verified fact | Re-read on 2026-10-04 from retained GitHub Actions logs, Azure Log Analytics, or the live incident database. |
| Repository fact | Directly established by committed code or Git history at `989832536586e5434bc04e3f585b11bb789a63ee`. |
| Operator record | Command/result retained from the controlled experiment and corroborated where possible by Azure logs. |
| Strong inference | Best explanation supported by multiple signals, but a missing request-to-revision correlation prevents proof. |
| Limitation | A statement about what a signal or retained artifact cannot establish. |

Evidence artifacts:

- [Deploy #4 secret-safe log excerpt](evidence/incident-002-deploy4.log)
- [Azure monitor, revision, and database evidence](evidence/incident-002-azure-logs.md)
- [Application Insights query and result](evidence/incident-002-app-insights.md)
- [Deploy #4 run 35804076293](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/35804076293)
- [Deploy #5 run 35805627905](https://github.com/amir-cs-dev/azure-reliability-platform/actions/runs/35805627905)
- Controlled-fault implementation: commit `5d8e213ed5d08f37d8de362f1e8849bfebd33d81` (PR #4)
- Cutover-aware verifier: commit `e531acdbcc1ef3b85e46e213b4130acaba31ef4b` (PR #5)
- Verifier regression tests: commit `989832536586e5434bc04e3f585b11bb789a63ee` (PR #6)

## Complete ACT-7 timeline

| Timestamp | Event and reference | What it proves | What it does not prove |
|---|---|---|---|
| 2026-09-23 00:54:38 | GitHub Deploy #4 run `35804076293` started on `main` at commit `5d8e213ed5d08f37d8de362f1e8849bfebd33d81`. | Exact workflow and source revision used for the controlled fault. | That the new API revision was already serving traffic. |
| 00:56:26.132 | The deploy job invoked `az containerapp update` for the API and monitor with immutable `5d8e213…` image tags. | Deployment action and immutable image reference. | Which revision served any later ingress request. |
| 00:56:35.949 | Azure system logs recorded creation of API revision `ca-arp-api-wus3--0000006`. | Exact broken revision. | Immediate or exclusive ingress cutover. |
| 00:56:52.138–00:56:53.909 | Azure pulled API image `…/reliability-api:5d8e213…` and started the container in revision `--0000006`. | Broken image was actually scheduled and started. | Readiness or 100% traffic at that instant. |
| 00:56:57.930–00:57:02.854 | The old verifier ran one health/readiness loop iteration and exited successfully; the deploy job completed successfully at 00:57:04. | The historical gate produced a false-green deployment result. | The revision that answered the successful request. The old script did not query target revision or traffic weight. |
| 00:57:28.461 | External checker recorded `healthy=False`, latency `27.08ms`, `failures=1`. | First retained semantic-health failure. HTTP availability alone was insufficient. | An incident at the first failure; threshold was two. |
| 00:57:34.655888 | External checker recorded the second failure and emitted `EVENT: INCIDENT_OPENED`; PostgreSQL persisted Incident ID `2` with this `opened_at`. | Threshold crossing, unique incident opening, and persisted start time. | Human receipt of an alert. |
| 00:57:35.256595 | Notification ID `3`, event `INCIDENT_OPENED`, became `delivered` after one attempt and no recorded error. | The configured Discord webhook accepted the opening POST with a 2xx response; measured experiment latency was about `0.601s`. | That a person viewed the Discord message, or a general delivery SLA. |
| 00:57:36.243 | Log Analytics ingested `EVENT: INCIDENT_OPENED` and `ALERT DELIVERY: {'delivered': 1, …}`. | Independent operational-log correlation for the opening and delivery result. | Exact ingestion latency for all future events. |
| 00:57:38.616–01:00:31.337 | Checker logs remained `healthy=False`; the persisted failure counter progressed through `24`. Only one opening event exists in the interval. | Sustained failure and no alert storm during this incident. | The separate Phase 5 concurrent-execution acceptance gate, which is audited in Mission 2. |
| 00:57:34.655888–01:00:41.511268 | Application Insights captured 38 container-local and 23 public `/health` rows; every row was HTTP 200 and `Success=True`. | Application request telemetry remained green at the HTTP layer throughout the semantic incident. | Semantic response correctness, complete unsampled request volume, or end-user success. |
| 00:59:55.942 | Azure system logs recorded creation of rollback revision `ca-arp-api-wus3--0000007`. | Operator rollback initiated a distinct revision. | That rollback was serving immediately. |
| 01:00:10.934–01:00:13.939 | Azure pulled known-good image `…/reliability-api:9c506ada6114c550c1191d738d1291e0fae20cf9` and started it in revision `--0000007`. | Exact known-good artifact and rollback revision ran. | Semantic recovery before the checker observed it. |
| 01:00:41.511268 | External checker recorded `healthy=True`, latency `47.36ms`, reset failures to `0`, and emitted `EVENT: RECOVERED`. PostgreSQL persisted this `recovered_at` and duration `186.855`. | Public endpoint satisfied the checker's HTTP and exact JSON contract after rollback; recovery and duration were persisted. | Continuous availability between samples. |
| 01:00:41.963336 | Notification ID `4`, event `RECOVERED`, became `delivered` after one attempt and no recorded error. | The configured Discord webhook accepted the recovery POST; measured experiment latency was about `0.452s`. | Human viewing or a general delivery SLA. |
| 01:00:43.224 | Log Analytics ingested the recovery alert-delivery summary. | Operational log corroboration of recovery notification delivery. | Zero ingestion delay. |
| 01:16:37–01:20:15 | Deploy #5 run `35805627905` deployed verifier-fix commit `e531acd…`. It identified target revision `ca-arp-api-wus3--0000009`, waited for 100% traffic, then passed six semantic health/readiness samples. | The remediation was deployed and demonstrated against the exact post-cutover revision. | That every future deployment is immune to unrelated failure modes. |

## Detection and incident lifecycle

The checker validates both transport and content. For `/health`, HTTP 200 is not
enough; the response must equal `{"status":"healthy"}`. The controlled fault
therefore produced a valid semantic failure without an HTTP error.

The persisted lifecycle is:

| Record | Value |
|---|---|
| Incident | `2` |
| Opened | `2026-09-23T00:57:34.655888+00:00` |
| Recovered | `2026-09-23T01:00:41.511268+00:00` |
| Duration | `186.855 seconds` |
| Opening notification | ID `3`; `INCIDENT_OPENED`; `delivered`; attempts `1`; delivered `2026-09-23T00:57:35.256595+00:00` |
| Recovery notification | ID `4`; `RECOVERED`; `delivered`; attempts `1`; delivered `2026-09-23T01:00:41.963336+00:00` |

The delivery code marks a notification delivered only after the configured
HTTPS webhook returns a 2xx response. The timestamps above therefore support
experiment-specific latencies of approximately `0.601s` and `0.452s`. They are
two observations, not production SLOs or SLAs.

## Investigation and diagnosis

### Confirmed

1. PR #4 made the deployed commit return HTTP 200 with a degraded JSON body
   when `ARP_PHASE8_FAULT=invalid_health` was configured.
2. Deploy #4 built and pushed that exact immutable commit tag.
3. Azure created and started revision `ca-arp-api-wus3--0000006` from that tag.
4. The old verifier passed after one request pair and did not identify the
   serving revision or wait for 100% target-revision traffic.
5. The old revision `ca-arp-api-wus3--0000005` was not terminated until
   `00:57:56.089`, after the verifier had already passed.
6. The independent checker detected semantic failure, while Application
   Insights classified the captured HTTP requests as successful.

### Strong inference, not proof

The most likely mechanism is a revision-cutover race: the verifier's successful
request was answered before the broken target revision exclusively served
traffic. This is strongly supported by the old revision's lifetime, the new
revision's creation/start timestamps, the verifier's single early pass, and the
subsequent semantic failures.

It is not mathematically proven because the successful request was not tagged
with its serving API revision. Other propagation behavior cannot be excluded.
The corrective control therefore addresses the observed verification gap
without overstating the historical request path.

## Recovery and rollback

The retained operator command was:

```bash
az containerapp update \
  -g rg-arp-app-wus3 \
  -n ca-arp-api-wus3 \
  --image arp3e6c8737fb3a44be8477.azurecr.io/reliability-api:9c506ada6114c550c1191d738d1291e0fae20cf9
```

Azure system logs independently corroborate the resulting revision and image:
revision `ca-arp-api-wus3--0000007` pulled the exact `9c506ada…` tag and started.
The semantic checker then returned healthy, persisted recovery, and delivered
the recovery notification. A later revision `--0000008` used the same known-good
image; it occurred after persisted recovery and is not used to claim the
rollback detection time.

## Corrective action

PR #5 replaced the single early request loop with `scripts/verify_deploy.py`.
The verifier now:

1. verifies API and monitor images match the workflow commit;
2. identifies the exact target API revision;
3. waits until that target alone has 100% traffic;
4. waits an additional ten seconds after cutover;
5. checks exact `/health` and `/ready` JSON contracts;
6. repeats those checks six times while rechecking serving revision stability.

PR #6 added deterministic regressions for a healthy deployment, semantic
degradation at sample 1, semantic degradation at sample 6, and a revision that
never reaches cutover. Deploy #5 then demonstrated the corrected gate against
target revision `ca-arp-api-wus3--0000009`.

## Signal interpretation and limitations

| Signal | Proves | Does not prove |
|---|---|---|
| GitHub Actions run | Workflow revision, job/step result, deployment command timing, immutable tag. | Which revision served an ingress request unless explicitly queried. |
| Container App system log | Revision creation, image pull, container start/stop, and platform traffic-update events. | Per-request routing unless request telemetry carries revision identity. |
| External checker log | Sampled HTTP status, exact semantic body result, latency, failure counter, and lifecycle event. | Continuous availability between samples or end-user experience. |
| PostgreSQL incident row | Durable opened/recovered timestamps and computed duration. | That notifications were received. |
| PostgreSQL notification row | Configured webhook returned 2xx and the delivery result was durably recorded. | Human viewing of a Discord message. |
| Application Insights `AppRequests` | Captured server request result code, duration, and SDK success classification. | Semantic JSON correctness; unsampled total request volume was not established. |
| Log Analytics `TimeGenerated` | Azure ingestion time for the retained row. | Exact event occurrence time when the log message embeds a separate checker timestamp. |

The repository preserves text evidence instead of secrets or generated
screenshots. Source telemetry is retention-bound, so the Markdown evidence is
the durable reviewer artifact. No sampling percentage is claimed because it was
not established in the incident record.

## Current test evidence

Re-run on 2026-10-04 UTC from commit
`989832536586e5434bc04e3f585b11bb789a63ee`:

```text
PG_TEST_DATABASE_URL=<disposable local arp_test database> \
  ./.venv/bin/python -m pytest -q
45 passed, 1 warning in 1.41s

./.venv/bin/python -m pytest -q \
  tests/test_verify_deploy.py tests/test_phase8_fault.py
6 passed in 0.44s
```

The warning is a Starlette deprecation warning about its current `httpx`
TestClient integration; it is not a failing assertion. The disposable database
container was stopped and removed after the run.

## Acceptance audit

### ACT-7

| Requirement | Evidence | Result |
|---|---|---|
| Deployment timestamp/reference | Deploy #4 run, commit, step timestamps, revision `--0000006` | PASS |
| External unhealthy observations | Checker logs from failure 1 through 24 | PASS |
| Application Insights behavior | Exact-interval KQL and captured result table | PASS |
| Incident opening | Checker event plus persisted Incident #2 | PASS |
| Discord opening delivery | Notification ID `3`, one attempt, delivered timestamp; checker delivery log | PASS |
| Rollback | Operator command plus revision `--0000007` system logs | PASS |
| External recovery | Semantic checker `healthy=True` and `EVENT: RECOVERED` | PASS |
| Recovery notification | Notification ID `4`, one attempt, delivered timestamp; checker delivery log | PASS |
| Every signal's scope/limits explained | Signal interpretation table above | PASS |

**ACT-7 verdict: PASS. Phase 7 is closed.**

### ACT-8

| Requirement | Evidence | Result |
|---|---|---|
| Broken revision/reference | API revision `--0000006`; image/commit `5d8e213…` | PASS |
| Known-good revision/reference | API revision `--0000007`; image/commit `9c506ada…` | PASS |
| Detection and alert | Threshold-crossing logs, Incident #2, notification ID `3` | PASS |
| Investigation | Confirmed facts and bounded cutover-race inference above | PASS |
| Operator rollback | Retained command corroborated by Azure system logs | PASS |
| Healthy endpoint after rollback | Exact semantic checker pass at `01:00:41.511268` | PASS |
| Persisted recovery/duration | Incident row with recovery and `186.855` seconds | PASS |
| Incident report | This document | PASS |
| Logs, deployment references, timestamps | Linked evidence package and GitHub runs | PASS |
| Remediation demonstrated | Deploy #5 target revision, 100% traffic, six samples | PASS |

**ACT-8 verdict: PASS. Phase 8 is closed.**
