# Final authoritative acceptance audit

This audit consolidates, rather than replaces, the phase-specific evidence.
The documentation/reviewer foundation merged through green
[PR #28](https://github.com/amir-cs-dev/azure-reliability-platform/pull/28)
at `a869f849d87271ed310cd07232b7e7e9be313e35`. The mandatory reproduction
then succeeded from a new clone whose `HEAD` exactly equaled that integrated
`origin/main`. ACT-10 and every cross-cutting domain are **PASS**.

## Phase 10 reviewer result

The complete command/result record is [fresh-clone reviewer
evidence](phase10/fresh-clone-review.md). It proves:

- 8 focused application/fault tests, 6 focused checker tests, and all 87 tests;
- normal `/`, `/health`, and `/ready` behavior plus two protocol-distinct
  configuration-only faults through Docker;
- both Docker image builds and Function packaging;
- both Terraform roots and 21 rendered Kubernetes resources;
- Prometheus rules/configuration, Alertmanager, Grafana, Actionlint, and every
  relative documentation target;
- a 37-commit history-aware secret scan with no leaks;
- complete linked deployment, rollback, Phase 9, teardown, cost, security, and
  cold-review answers; and
- a clean clone with no test containers/images left afterward.

The legacy scheduler discrepancy was also closed before the reviewer run. Its
top-level Azure resource had said `Running` while all eight revisions were
inactive/stopped with zero replicas and traffic. The app was explicitly stopped
through the Container Apps REST operation, the production workflow/verifier no
longer touches it, and its unused deployer role was removed. The Azure Function
remains the only scheduler.

## Final test matrix

Collection on 2026-10-05 found 87 tests:

| Class | Test files / scope | Count |
|---|---|---:|
| Application, checker, storage, monitor units | alerts, app, history, checker, delivery, Discord adapter, runner, SQLite storage, metrics, controlled faults | 42 |
| Azure Function | timer adapter, package, Terraform contract | 11 |
| PostgreSQL integration | lifecycle/rollback/retry, overlapping state-row lock, check history | 3 |
| Deployment verifier | exact revision, cutover stability, healthy and degraded behavior | 4 |
| Terraform and workflow controls | artifact metadata/validation, workflow permissions/guards, automatic dispatch boundaries | 20 |
| Kubernetes / Phase 9 | chart rendering, configuration, metrics and observability controls | 7 |
| **Total** | `python -m pytest tests/ -q` | **87** |

CI additionally:

- formats, initializes without the backend, and validates `infra/app` and
  `infra/phase9`;
- lints/renders the chart and schema-validates 21 Kubernetes resources;
- validates Prometheus configuration/rules, Alertmanager, and Grafana JSON;
- builds and inspects the Function package;
- builds application and monitor images; and
- starts the application image and checks it through the container boundary.

### Required failure paths

| Failure / control | Test or demonstration | Result |
|---|---|---|
| Invalid semantic health | Unit + Docker: HTTP 200, body `degraded`; checker marks unhealthy | PASS |
| Controlled HTTP 500 | Unit + Docker: HTTP 500 with controlled detail | PASS |
| Timeout | Checker mocked timeout returns complete unhealthy record | PASS |
| Request exception | Checker mocked transport exception returns complete unhealthy record | PASS |
| Failed CI test | PR #11 produced 1 failed / 62 passed; downstream real deploy job skipped | PASS |
| Stale Terraform plan | Apply run 37177142642 rejected replay after state serial changed | PASS |
| Wrong confirmation | Apply run 37177119364 rejected non-`APPLY` input | PASS |
| Non-main apply | Apply run 37177338261 rejected dispatch outside `main` | PASS |
| Concurrent overlap | Real PostgreSQL lock observed; one incident and one opening outbox row | PASS |
| Controlled Phase 9 rollout | HTTP 500 rolling update, Prometheus/Alertmanager/Function incident, rollback/recovery | PASS |

## Reliability audit

| Property | Evidence | Result |
|---|---|---|
| Failure threshold | State-machine tests and Incident #2: incident opens on second consecutive failure | PASS |
| Exactly one opening | Incident #2 persisted one opening; sustained failures created no alert storm | PASS |
| Concurrent safety | Deterministic PostgreSQL test observes second execution waiting on `FOR UPDATE` | PASS |
| Recovery threshold/reset | Lifecycle tests and live incidents reset counter and close the open incident | PASS |
| Exactly one recovery notification | Unique outbox event and Incident #2/Phase 9 persisted recovery | PASS |
| Persisted duration | Incident #2 stores 186.855 seconds; tests validate duration calculation | PASS |
| Rollback | Container Apps Incident #2 and AKS Helm experiment both use known-good immutable revisions | PASS |
| Timeout/transport handling | Checker returns stable records without crashing the state path | PASS |
| False-green remediation | Deployment verifier waits for exact 100%-traffic revision and performs six post-cutover samples | PASS |
| Phase 9 fault/recovery | Full baseline → rolling fault → alert → rollback → recovery chain retained | PASS |

The concurrency proof is
[separate and deterministic](phase5-concurrency.md); sequential deduplication
and restart survival are not used as substitutes.

## Observability audit

| Layer | Persistent or temporary | Proven behavior |
|---|---|---|
| External semantic checker | Persistent | Public HTTP status + exact JSON contract, latency, error class, timestamp |
| Azure Function structured traces | Persistent | Natural timer starts/completions, state and lifecycle event |
| PostgreSQL check/incident/outbox rows | Persistent | Durable independent operational truth |
| Application Insights requests | Persistent | Request count/status/success/duration; Incident #2 limitation exposed |
| Log Analytics | Persistent | Application/Function structured timestamps and Container Apps system logs |
| Azure Workbook | Persistent | Versioned incident/request/latency investigation views |
| Prometheus | Temporary/reproducible | Real API and kube-state-metrics targets plus alert rule evaluation |
| Grafana | Temporary/reproducible | Provisioned Prometheus datasource, dashboard, successful live query |
| Alertmanager | Temporary/reproducible | Controlled firing alert routed to Discord receiver |
| Discord | External | Webhook 2xx acceptance for opening/recovery and Phase 9 alert |
| Rollback/recovery telemetry | Both | Health, alert, state, and workload evidence returned to good baseline |

Application Insights recorded HTTP 200 and `Success=True` during Incident #2;
it did **not** prove the response body was semantically healthy. Discord 2xx
proves webhook acceptance, not human viewing. Those boundaries are part of the
acceptance result.

## Cold reviewer answers

These answers use only version-controlled repository content.

1. **What problem does it solve?** It detects semantic application failures
   independently, durably manages incident/recovery state, delivers
   deduplicated notifications, and verifies recovery/deployment behavior.
2. **What is the architecture?** GitHub Actions and Terraform deliver an ACR
   image to Container Apps; an external Function checks it, writes PostgreSQL,
   sends Discord alerts, and emits Azure telemetry. A destroyed/reproducible AKS
   lab adds Prometheus, Grafana, Alertmanager, and kube-state-metrics.
3. **What is permanent?** The app resource group's API/ACR/telemetry/Function/
   storage/Key Vault/identities, PostgreSQL, remote state, and OIDC control
   plane.
4. **What was temporary?** The one-node Phase 9 AKS cluster, node resource
   group, Kubernetes workloads, disk, load balancer, public IPs, and two tracked
   cluster-related role assignments.
5. **Why Container Apps?** It gives the persistent small HTTP service managed
   ingress, revisions, probes, consumption hosting, and identity-based ACR pull
   without a permanent Kubernetes operations/cost burden.
6. **Why an Azure Function monitor?** It schedules outside the workload, keeps
   monitoring independent, uses consumption hosting, and reuses the tested
   monitor modules.
7. **Why PostgreSQL?** Durable multi-process transactions and row locks make
   incident transitions safe across overlapping executions.
8. **Why semantic health?** HTTP 200 alone can carry a degraded body; Incident
   #2 proved the distinction in production telemetry.
9. **How are incidents deduplicated?** A locked singleton state row serializes
   transitions; open-state logic suppresses repeats; a unique incident/event
   constraint protects outbox idempotency.
10. **How does CI/CD work?** PR CI validates tests/IaC/chart/images; a separate
    main-only deployment uses OIDC and immutable tags, then verifies exact
    traffic cutover and repeated semantic health.
11. **How is Terraform apply governed?** Current-main plan artifacts are
    reviewed; a separate dispatch with run ID and `APPLY` revalidates run,
    branch, SHA, tree, hashes, age, Terraform version, and state identity.
12. **What happened in Incident #2?** A semantically degraded HTTP-200 release
    passed the old gate, the external checker opened one incident and alerted,
    rollback recovered it, and the verifier was fixed.
13. **What did Application Insights miss?** It saw transport-level 200/success
    but did not validate the JSON health contract.
14. **What happened in Phase 9?** A digest-pinned AKS app and in-cluster
    observability stack established baseline, rolled into HTTP 500, alerted,
    was independently detected, rolled back, recovered, and was destroyed.
15. **How did Prometheus/Alertmanager behave?** Prometheus scraped real app and
    cluster metrics and fired the controlled rule; Alertmanager exposed the
    alert and recorded Discord notification delivery metrics.
16. **How was rollback performed?** Incident #2 updated Container Apps to a
    known-good image; Phase 9 used `helm rollback` to the recorded good
    revision, followed by rollout and health verification.
17. **What are the limitations?** Minute sampling, webhook acceptance rather
    than human-read proof, single-replica/non-HA persistent tiers, partial
    Terraform ownership, single-node temporary AKS, retention-bound cloud
    artifacts, and no latency SLA.
18. **What does it cost?** Persistent usage is driven mainly by PostgreSQL,
    always-warm API, ACR, telemetry, Function, storage, and Key Vault. The
    destroyed AKS lab was estimated at USD 0.13–0.17/hour; no unsupported
    monthly total is claimed.
19. **How is it reproduced?** Clone current `main`, meet the five local
    prerequisites, and run `scripts/review.sh`; cloud and Phase 9 procedures
    are linked but no expensive resource is needed for review.
20. **How is it torn down?** Phase 9 uses Helm removal then a reviewed isolated
    destroy plan/apply. Full decommission inventories/backs up mixed-ownership
    resources, deletes the exact app RG, then identities and state last.

## ACT-0 through ACT-10

| ACT | Result | Evidence | Remaining blocker |
|---|---|---|---|
| ACT-0 | PASS | Repository scope, clean phase history, [status ledger](acceptance-status.md) | None |
| ACT-1 | PASS | [Two distinct controlled faults and Docker](phase1-application.md) | None |
| ACT-2 | PASS | [Complete checker result contract](phase2-external-checker.md) | None |
| ACT-3 | PASS | Live public Container Apps API; root/health/readiness checks | None |
| ACT-4 | PASS | [Function timer, identity, persistence, natural runs](phase4-azure-function.md) | None |
| ACT-5 | PASS | [Lifecycle plus deterministic overlap](phase5-concurrency.md) | None |
| ACT-6 | PASS | [CI/CD, OIDC, exact-plan approval controls](ci-cd/phase6-acceptance.md) | None |
| ACT-7 | PASS | [Incident #2 correlated observability](incidents/incident-002.md) | None |
| ACT-8 | PASS | [Rollback and verifier remediation](incidents/incident-002.md#recovery-and-rollback) | None |
| ACT-9 | PASS | [Complete live chain and teardown](phase9/live-acceptance.md) | None |
| ACT-10 | PASS | [Integrated-main fresh-clone reviewer evidence](phase10/fresh-clone-review.md) and cold-review answers above | None |

## Cross-cutting audit

| Domain | Result | Evidence |
|---|---|---|
| Security | PASS | [History-aware credential audit](security-identity-iac.md#repository-credential-audit) |
| Identity | PASS | [OIDC and managed-identity audit](security-identity-iac.md#github-to-azure-identity-separation) |
| Infrastructure/IaC | PASS | [Ownership classification and no-op plan](security-identity-iac.md#iac-reconciliation) |
| Remote state/locking | PASS | [Backend and observed lease audit](security-identity-iac.md#remote-state-and-serialization) |
| Testing | PASS | 87-test matrix plus static/Docker gates above |
| Reliability | PASS | Reliability matrix above and phase evidence |
| Observability | PASS | Persistent/temporary observability matrix above |
| Reproducibility | PASS | [Fresh clone of integrated `origin/main`](phase10/fresh-clone-review.md) completed every safe reviewer gate |
| Cost controls/documentation | PASS | [Cost and safe teardown](cost-and-teardown.md) |

Every ACT and cross-cutting row passes. The final audit is eligible for its
green-CI integration and post-merge verification.
