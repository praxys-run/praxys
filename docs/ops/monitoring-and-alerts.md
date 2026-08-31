# Monitoring & alerts

> **Summary:** The Praxys telemetry signals, how to query them, the live **alert
> inventory + cost model**, and how to add or tune an alert without overspending.
> **Use when:** You want to graph a signal, investigate spend/errors, add or tune
> an alert, or get notified when something needs attention.

## Telemetry model

Production has two workspace-linked Application Insights components with
different trust levels:

| Component | Data | Trust / auth |
|---|---|---|
| `appi-trainsight` | Browser page views, exceptions, dependencies, Web Vitals; homepage availability test | Untrusted RUM. Local/instrumentation-key auth is enabled because the connection string ships in the SPA. |
| `appi-praxys-backend` | API requests/traces/logs, every `praxys.*` signal, backend alerts, API availability test | Trusted server emission. Local auth is disabled; `trainsight-app` must present its managed identity. |

Both write to `log-trainsight`, so a workspace query can see both. The trust
boundary is the component resource ID: keep alert scopes component-specific and
filter `_ResourceId` when querying the workspace directly.

The backend ships telemetry automatically when
`APPLICATIONINSIGHTS_CONNECTION_STRING` is set (it is resolved from
`appi-praxys-backend` by the deploy workflow; on App Service the SDK
authenticates via managed identity — see `api/main.py`). Raw user ids are never
emitted: custom signals use a SHA-256 pseudonym. Product events carry only
allowlisted enums and build/surface metadata. The one free-text field, an
optional Coach-feedback comment, is PII/secret-scrubbed, whitespace-collapsed,
and truncated to 120 characters before it reaches telemetry; the raw comment is
never persisted or logged.

For the public China launch, regional browser Application Insights is limited
to sanitized page/dependency/performance data: URL query/fragment values are
removed and automatic exception capture is disabled. Web and Miniapp product
events contain allowlisted event names, surface/build metadata, and bounded
response enums; the backend derives the pseudonymous account hash and rejects
extra fields. Browser Statsig is absent from the stamped `.cn` artifact
pending [#754](https://github.com/praxys-run/praxys/issues/754). Essential
backend request/security telemetry remains in `appi-praxys-backend` in East
Asia (Hong Kong). Frontend/backend Application Insights and the shared
workspace use 30-day retention. Server-side Statsig evaluations are local and
disable both user-event logging and SDK diagnostics.
These controls are part of
[`PIPIA-CN-2026-08-25-01`](./cn-personal-information-impact-assessment.md).
`launch-cn.yml` `status` does not inspect availability tests or alert rules.
Their outside-in verification remains a human pre-enable PIPIA/topology
responsibility; use this inventory and Azure/provider consoles directly.

Custom signals are emitted by `api/telemetry.py`. Each lands as either:
- a **customEvent** with that name through the required
  `azure-monitor-events-extension` runtime dependency, **or**
- a **customMetric** counter when the extension is unavailable at runtime.

Queries below `union` both shapes so they remain valid during fallback. All
custom signals in the table below belong to `appi-praxys-backend`.

## Signals

| Signal | Dimensions | Meaning | Emitter |
|---|---|---|---|
| `praxys.coach_tokens` | `insight_type`, `model`, `token_type` | Azure OpenAI tokens consumed (spend) | `record_coach_tokens` |
| `praxys.coach_run` | `insight_type`, `status`, `user_id_hash` | Insight-runner outcomes (cache hit rate) | `record_coach_run` |
| `praxys.coach_error` | `error_class` | Operator-actionable Coach errors (Auth/BadRequest) | `record_coach_error` |
| `praxys.coach_feedback` | `insight_type`, `dataset_hash`*, `model`, `pillars`*, `vote`, `has_comment`, `comment_length`*, `comment_excerpt`*, `user_id_hash` | Dataset-scoped feedback on generated Coach insights. `*` customEvent only; the metric fallback omits high-cardinality fields. | `record_coach_feedback` |
| `praxys.product_event` | `event_name`, `surface`, `app_version`, `response`, `user_id_hash` | Authenticated app/Today exposure, reasoning, and Decision Check events | `record_product_event` |
| `praxys.feedback` | `kind`, `status` | In-app feedback submissions + triage outcomes | `record_feedback` |
| `praxys.db_health` | `status`, `backend` | DB integrity/connectivity failures (startup check + readiness probe) | `record_db_health` |
| `praxys.sync` | `platform`, `outcome`, `failure_class`, `trigger`, `user_id_hash` | Per-platform sync attempt outcomes (success/failure + why) | `record_sync` |
| `praxys.connection` | `platform`, `flow`, `stage`, `outcome`, `failure_class`, `region`, `user_id_hash` | Account-connect attempts; `flow` is the Garmin **mfa** vs **non_mfa** sub-category | `record_connection` |
| `praxys.managed_plan` | `category`, `action`, `outcome`, `target`, `trigger`, `reason`, `failure_domain`, `user_id_hash`; `duration_ms`* | Managed-plan lifecycle, reconciliation, cleanup, delivery-run, item, and operator-recovery outcomes. `*` customEvent only; the metric fallback records latency separately as `praxys.managed_plan.delivery_latency`. | `record_managed_plan_event` |
| `praxys.labs_job` | `event`, `outcome`, `trigger`, `attempt`, `failure_class`, `user_id_hash`; `queue_delay_ms`*, `duration_ms`* | Durable Labs enqueue/dispatch/start/retry/completion/cancellation lifecycle. Queue payloads and telemetry contain no athlete rows. `*` present when known. | `record_labs_job` |

> `praxys.feedback`'s `status` dimension includes `needs_review` — the trigger for
> the feedback alert below.
>
> `praxys.sync` / `praxys.connection` `failure_class` is split into **user-fault**
> (`bad_credentials`, `mfa_code_rejected` — individual, never pages) and **systemic**
> (`rate_limited`, `captcha_required`, `access_blocked`, `token_rejected`,
> `mfa_unattended`, `platform_error`, `network_error`, `unknown`) in
> `api/telemetry.py` (`USER_FAULT_FAILURE_CLASSES` / `SYSTEMIC_FAILURE_CLASSES`).
> `token_rejected` is the class the upstream #369 widget-token break would have lit up.
>
> `praxys.managed_plan` maps bounded reasons into `provider_auth`, `provider`,
> `praxys`, `conflict`, `policy`, `none`, or `unknown`. The signal never includes
> provider account/workout ids, canonical workout ids, dates/content, credentials,
> raw errors, email, or the raw user id. The 16-character user pseudonym exists
> only to distinguish one athlete's failure from a fleet-wide incident.

## Querying (Logs blade → KQL)

Run backend requests, traces, logs, and `praxys.*` queries from
`appi-praxys-backend`. Run browser `pageViews`, client exceptions/dependencies,
and `WebVitals.*` from `appi-trainsight`. There are currently **no live Azure
Workbook resources**; these checked-in queries are the product-measurement
source of truth. Any future saved workbook must pin each query to the component
named above or explicitly use a cross-resource `app(...)` query.

### In-app admin operations read model

`GET /api/admin/ops/summary` reads only aggregate telemetry from
`appi-praxys-backend`. The backend managed identity has `Monitoring Reader` at
that exact component scope; it has no workspace-, resource-group-, or
subscription-wide read grant. The resource ID is deployment-derived as
`PRAXYS_BACKEND_APPINSIGHTS_RESOURCE_ID` and is removed by the
`rollback-to-frontend` path.

`api/admin_azure_monitor.py` owns a static allowlist of four KQL queries:

- `requests` + `availabilityResults` for request volume/failures, p95 latency,
  availability, and `praxys.db_health`;
- `customEvents` + `customMetrics` for aggregate Today/Decision Check/Coach
  value signals; and
- `customEvents` + `customMetrics` for sync reliability, systemic failure
  clusters (at least five distinct users across systemic failure classes for
  one platform in 15 minutes), and connection outcomes; and
- `customEvents` + `customMetrics` for aggregate managed-plan delivery,
  failure-domain, lifecycle, recovery, and p95 run-latency outcomes.

These are Application Insights **resource-context** table aliases, and every
query also filters `_ResourceId` to the configured backend component. Distinct
user calculations happen inside KQL; the API never returns pseudonyms, event
rows, comments, traces, or log bodies. Alert counts come from Azure Alerts
Management API requests scoped to that exact component resource ID, with
context and egress content disabled. Selected-window history is merged with
currently fired alert instances across Azure's full 30-day retention window, so
a long-running alert cannot produce a false-clear state. Direct PostgreSQL
connection counts come from aggregate `pg_stat_activity`, not Azure Metrics.

The console refreshes in the browser every minute, but Azure reads are cached
server-side for three minutes per section and selected window. Product value
always uses a trailing 28-day query so repeated weekly use is meaningful;
alerts, service, platform health, and managed-plan telemetry follow the selected
window. Failed refreshes may serve the last good
service/platform/managed-plan/alert value for up to 15 minutes and
product aggregates for up to 60 minutes; failures without a usable snapshot are
negative-cached for 20 seconds. The four KQL calls run concurrently with an
8-second server timeout and a 12-second overall deadline, so one slow Azure
section cannot block the database-backed admin workflows. These on-demand reads
create no alert-rule charge; Log Analytics cost remains the data scanned within
the selected `24h`, `7d`, or `28d` range.

Daily LLM token spend by surface:
```kql
customMetrics
| where name == "praxys.coach_tokens"
| extend insight_type = tostring(customDimensions.insight_type),
         token_type = tostring(customDimensions.token_type)
| where token_type == "total"
| summarize tokens = sum(valueSum) by insight_type, bin(timestamp, 1d)
```

Coach cache-hit rate (last 7d):
```kql
customMetrics | where name == "praxys.coach_run"
| extend status = tostring(customDimensions.status)
| summarize hits = countif(status == "hash_match"), total = count()
| extend hit_rate = todouble(hits) / total
```

In **`appi-trainsight`**, active users (DAU / WAU) of registered accounts. The
SPA tags telemetry with
`user_AuthenticatedId` = a SHA-256(user_id)[:16] pseudonym (set on login by
`web/src/lib/appinsights.ts`, matching `api/telemetry.py::hash_user_id`), so this
counts distinct *registered* users — not anonymous browsers — and correlates with
the backend `praxys.*` events. Only authenticated navigation is counted (the
anonymous landing page is excluded); demo accounts are included.
```kql
// WAU (last 7d) and DAU trend (last 30d)
pageViews
| where timestamp > ago(7d)
| where isnotempty(user_AuthenticatedId)
| summarize wau = dcount(user_AuthenticatedId)

pageViews
| where timestamp > ago(30d)
| where isnotempty(user_AuthenticatedId)
| summarize dau = dcount(user_AuthenticatedId) by bin(timestamp, 1d)
| render timechart
```

### Today value and Coach feedback

`praxys.product_event` is emitted by both clients through the authenticated
`POST /api/product-events` endpoint. The server supplies the timestamp and user
pseudonym; clients may send only the documented event/response enums — never
health values, recommendation prose, email, OpenID, or raw ids. The resulting
event is emitted only to `appi-praxys-backend`, where local authentication is
disabled. A browser can call the documented product endpoint, but it cannot use
an exposed instrumentation key to forge event names, timestamps, user hashes,
Coach provenance, or arbitrary dimensions in the trusted component.

The cutover occurred on 2026-07-18. Historical product/Coach events in
`appi-trainsight` remain **legacy shared-ingestion data** and must not be
silently mixed with trusted data. A continuity workbook may query both
Application IDs, but keep the trust epoch visible:

```kql
let trusted = app("066f94a3-a340-498d-9ee1-6f093a7b8911").customEvents
  | where name in ("praxys.product_event", "praxys.coach_feedback")
  | extend trust_epoch = "backend_enforced";
let legacy = app("d10e388f-3a26-4c3d-b57d-d83fc4637a9b").customEvents
  | where name in ("praxys.product_event", "praxys.coach_feedback")
  | extend trust_epoch = "legacy_shared";
union trusted, legacy
| summarize events=count() by trust_epoch, name, bin(timestamp, 1d)
```

Run the product and Coach queries below in **`appi-praxys-backend`** for
post-cutover trusted measurement.

Clients first reserve a two-minute render window through
`POST /api/product-events/today-feedback-claim`. After the prompt is onscreen,
`today_feedback_shown` confirms the claim and stores the cadence timestamp on
`user_config.today_decision_check_shown_at`. This prevents competing web,
miniapp, device, or worker claims without counting abandoned/lost requests as
prompt exposure. Unconfirmed claims expire and emit no product event. A valid
Decision Check submission can finalize a claim within the seven-day cadence if
the separate render confirmation was lost, even after the two-minute
competition lease expires. The backend then emits the missing shown event
before the submission and accepts no second answer for that prompt. Clients
also persist account-scoped local cadence as soon as the prompt renders, so a
lost confirmation cannot cause repeated prompts on the same device; the
confirmed server timestamp remains the cross-device authority.

Today reach and Decision Check response rate by surface:
```kql
let product_events = union isfuzzy=true
  (customEvents
    | where name == "praxys.product_event"
    | project timestamp,
        event_name=tostring(customDimensions.event_name),
        surface=tostring(customDimensions.surface),
        response=tostring(customDimensions.response),
        user=tostring(customDimensions.user_id_hash), events=1.0),
  (customMetrics
    | where name == "praxys.product_event"
    | project timestamp,
        event_name=tostring(customDimensions.event_name),
        surface=tostring(customDimensions.surface),
        response=tostring(customDimensions.response),
        user=tostring(customDimensions.user_id_hash), events=todouble(valueSum));
product_events
| where timestamp > ago(28d)
| summarize app_users=dcountif(user, event_name == "app_opened"),
    today_users=dcountif(user, event_name == "today_brief_rendered"),
    prompts=sumif(events, event_name == "today_feedback_shown"),
    responses=sumif(events, event_name == "today_feedback_submitted")
    by bin(timestamp, 7d), surface
| extend today_reach_rate=iif(app_users > 0, todouble(today_users) / app_users, real(null)),
    response_rate=iif(prompts > 0, responses / prompts, real(null))
| order by timestamp asc, surface asc
```

Compare `today_users` with `app_users` here and with the broad WAU reported by
Admin Usage. Broad WAU still means any authenticated activity; it is context,
not evidence that Today delivered value.

Repeated Today use across distinct weeks:
```kql
let product_events = union isfuzzy=true
  (customEvents | where name == "praxys.product_event"
    | project timestamp, event_name=tostring(customDimensions.event_name),
        surface=tostring(customDimensions.surface), user=tostring(customDimensions.user_id_hash)),
  (customMetrics | where name == "praxys.product_event"
    | project timestamp, event_name=tostring(customDimensions.event_name),
        surface=tostring(customDimensions.surface), user=tostring(customDimensions.user_id_hash));
product_events
| where timestamp > ago(28d) and event_name == "today_brief_rendered"
| summarize active_weeks=dcount(startofweek(timestamp)) by user, surface
| summarize today_users=count(), weeks_2_plus=countif(active_weeks >= 2),
    weeks_3_plus=countif(active_weeks >= 3), weeks_4_plus=countif(active_weeks >= 4)
    by surface
| extend weeks_2_plus_rate=todouble(weeks_2_plus) / today_users,
    weeks_3_plus_rate=todouble(weeks_3_plus) / today_users,
    weeks_4_plus_rate=todouble(weeks_4_plus) / today_users
```

Decision Check outcomes and reported value rate:
```kql
let product_events = union isfuzzy=true
  (customEvents | where name == "praxys.product_event"
    | project timestamp, event_name=tostring(customDimensions.event_name),
        response=tostring(customDimensions.response),
        surface=tostring(customDimensions.surface), events=1.0),
  (customMetrics | where name == "praxys.product_event"
    | project timestamp, event_name=tostring(customDimensions.event_name),
        response=tostring(customDimensions.response),
        surface=tostring(customDimensions.surface), events=todouble(valueSum));
product_events
| where timestamp > ago(28d) and event_name == "today_feedback_submitted"
| summarize changed_plan=sumif(events, response == "changed_plan"),
    confirmed_plan=sumif(events, response == "confirmed_plan"),
    not_helpful=sumif(events, response == "not_helpful"),
    not_training=sumif(events, response == "not_training"), total=sum(events)
    by surface
| extend eligible_responses=total - not_training
| extend reported_value_rate=iif(
    eligible_responses > 0,
    (changed_plan + confirmed_plan) / eligible_responses,
    real(null)
  )
```

Coach useful-vote rate by insight type:
```kql
let coach_feedback = union isfuzzy=true
  (customEvents | where name == "praxys.coach_feedback"
    | project timestamp, insight_type=tostring(customDimensions.insight_type),
        vote=tostring(customDimensions.vote), events=1.0),
  (customMetrics | where name == "praxys.coach_feedback"
    | project timestamp, insight_type=tostring(customDimensions.insight_type),
        vote=tostring(customDimensions.vote), events=todouble(valueSum));
coach_feedback
| where timestamp > ago(28d)
| summarize up=sumif(events, vote == "up"), total=sum(events) by insight_type
| extend useful_rate=up / total
```
Review scrubbed comment themes (customEvent path only):
```kql
customEvents
| where name == "praxys.coach_feedback" and timestamp > ago(28d)
| extend insight_type=tostring(customDimensions.insight_type),
         vote=tostring(customDimensions.vote),
         comment=tostring(customDimensions.comment_excerpt)
| where isnotempty(comment)
| project timestamp, insight_type, vote, comment
| order by timestamp desc
```

Durable idempotency state in `ai_insight_feedback` is unique by
`(user_id, insight_type, dataset_hash)` and contains only `dataset_hash`, `vote`,
and `submitted_at`; the current vote is mirrored into `AiInsight.meta.feedback`
for API reads. It deliberately excludes the raw comment. A new `dataset_hash`
permits one new vote, while a previously seen hash remains a duplicate if it
later becomes current again. Coach `model` and science-pillar dimensions come
from immutable server-generation provenance rather than submission-time settings
or pushed insight metadata. Model values remain bounded safe labels, and only registered theory ids for the
`load`, `recovery`, `prediction`, and `zones` pillars may enter telemetry;
unsafe values are replaced with `unknown` or omitted. CLI-pushed insights without
server provenance report `unknown` instead of guessing current settings. Runner
provenance also records the source revision vector; generation is serialized per
user and revision commits share a transaction lock with publication, so an older
snapshot cannot overwrite a newer sync result.

`today_feedback_shown` is emitted only when the fresh, actionable prompt is
rendered on a visible client. Hidden web tabs and hidden miniapp tabs neither
claim nor confirm the prompt. Keep response rate beside Decision Check outcomes
so non-response and respondent-selection bias remain explicit.

### Connection & sync health (per platform)

Sync failure rate per platform + failure class (last 24h):
```kql
customMetrics
| where name == "praxys.sync"
| extend platform = tostring(customDimensions.platform),
         outcome = tostring(customDimensions.outcome),
         failure_class = tostring(customDimensions.failure_class)
| summarize failures = countif(outcome == "failure"), total = count() by platform, failure_class
| extend failure_rate = todouble(failures) / total
| order by failures desc
```

**Systemic vs individual** — the discriminator. The provisioned sync rule
counts distinct *affected users* across all systemic failure classes for each
platform in its 15-minute evaluation window; a spike here means a platform-side
or our-side break, not one user's wrong password:
```kql
union isfuzzy=true
  (customMetrics
   | where name == "praxys.sync"
   | extend platform=tostring(customDimensions.platform),
            outcome=tostring(customDimensions.outcome),
            failure_class=tostring(customDimensions.failure_class),
            user=tostring(customDimensions.user_id_hash)),
  (customEvents
   | where name == "praxys.sync"
   | extend platform=tostring(customDimensions.platform),
            outcome=tostring(customDimensions.outcome),
            failure_class=tostring(customDimensions.failure_class),
            user=tostring(customDimensions.user_id_hash))
| where outcome == "failure"
| where failure_class in ("rate_limited","captcha_required","access_blocked",
        "token_rejected","mfa_unattended","platform_error","network_error","unknown")
| summarize affected_users=dcount(user) by platform
| where affected_users >= 5
```

The admin console applies that same gate to each 15-minute bucket in the
selected history window, then joins the qualifying platform buckets back to the
aggregate signal and groups by `platform, failure_class` for diagnosis.

Garmin MFA vs non-MFA connect funnel (last 7d):
```kql
customMetrics
| where name == "praxys.connection"
| where tostring(customDimensions.platform) == "garmin"
| extend flow = tostring(customDimensions.flow),
         stage = tostring(customDimensions.stage),
         outcome = tostring(customDimensions.outcome)
| summarize attempts = count() by flow, stage, outcome
```

> These land in `customMetrics` by default (the OTel-counter fallback).
> Installing `azure-monitor-events-extension` on the App Service routes them to
> `customEvents` instead — recommended here, since the
> systemic-vs-individual signal keys on `dcount(user_id_hash)`: exact and cheap
> in `customEvents`, but one series per user in `customMetrics`. Production
> queries union both tables so migration does not create a blind spot.

### Managed-plan delivery

Use the bounded `failure_domain` to separate execution-platform incidents from
Praxys defects. Do not alert on raw `reason` alone and do not add provider ids or
workout content to this signal.

```kql
let managed = union isfuzzy=true
  (customEvents
   | where name == "praxys.managed_plan"
   | project timestamp,
       category=tostring(customDimensions.category),
       action=tostring(customDimensions.action),
       outcome=tostring(customDimensions.outcome),
       target=tostring(customDimensions.target),
       trigger=tostring(customDimensions.trigger),
       reason=tostring(customDimensions.reason),
       failure_domain=tostring(customDimensions.failure_domain),
       user=tostring(customDimensions.user_id_hash),
       events=1.0),
  (customMetrics
   | where name == "praxys.managed_plan"
   | project timestamp,
       category=tostring(customDimensions.category),
       action=tostring(customDimensions.action),
       outcome=tostring(customDimensions.outcome),
       target=tostring(customDimensions.target),
       trigger=tostring(customDimensions.trigger),
       reason=tostring(customDimensions.reason),
       failure_domain=tostring(customDimensions.failure_domain),
       user=tostring(customDimensions.user_id_hash),
       events=coalesce(valueSum, value, todouble(valueCount), 0.0));
managed
| where timestamp > ago(7d)
| summarize events=sum(events), affected_users=dcountif(user, isnotempty(user))
    by category, action, outcome, target, failure_domain, reason
| order by events desc
```

Interpretation:

- `provider_auth`: reconnect/rotate the athlete's execution-target credentials;
  alert only when at least five distinct athletes fail for the same target in
  15 minutes.
- `provider`: execution-platform rejection, transient failure, or uncertain
  result; the systemic rule uses the same five-athlete gate.
- `praxys`: a known ledger start/finalization, reconciliation, or adapter defect;
  one occurrence is operator-actionable and pages.
- `conflict`: ownership/content disagreement. This is athlete-resolved in the
  plan reconciliation flow and is never blindly replayed.
- `policy`: expected safety gates such as pause, retry backoff/limit, connection
  change, or unavailable threshold. Diagnose the prerequisite; do not page.
- `unknown`: inspect the bounded category/action/reason and classify it in code
  before adding an alert.

## Alert inventory (source of truth)

Every unmarked rule below is live in `rg-trainsight` (region **eastasia**) and
routes to the `praxys-feedback-ag` action group
(→ `support@praxys.run`). Rows marked **provisioned-disabled** exist with both
the web test and alert disabled. Rows marked **planned** do not exist. Costs are
the eastasia retail rate per the [cost model](#alert-cost-model) below.

Regional availability states are exact:

- **planned** — neither the web test nor its alert exists;
- **provisioned-disabled** — both resources exist and both are disabled;
- **live** — both resources exist and both are enabled.

| Rule | Type | Scope | Watches | Eval | Sev | ~USD/mo |
|---|---|---|---|---|---|---|
| `praxys-db-health-unhealthy` | log | `appi-praxys-backend` | `praxys.db_health` failure (corrupt/unreachable DB) | 5 min | 1 | **1.50** |
| `praxys-pg-connections-high` | metric | `praxys-pg` | `active_connections` avg > 40 | 5 min | 2 | ~0.10 |
| `wt-praxys-homepage` | metric (web test) | `appi-trainsight` + homepage test | `https://www.praxys.run/` reachable | 1 min | 1 | ~0.10 |
| `wt-praxys-run-apex` | metric (web test) | `appi-trainsight` + regional frontend test | `https://praxys.run/` reachable | 1 min | 1 | ~0.10 |
| `wt-praxys-cn-apex` **provisioned-disabled** | metric (web test) | `appi-trainsight` + regional frontend test | `https://praxys.cn/` reachable | 1 min | 1 | 0 while disabled |
| `wt-praxys-cn-www` **provisioned-disabled** | metric (web test) | `appi-trainsight` + regional frontend test | `https://www.praxys.cn/` reachable | 1 min | 1 | 0 while disabled |
| `wt-praxys-api-health` | metric (web test) | `appi-praxys-backend` + API test | `.../api/health` reachable | 1 min | 1 | ~0.10 |
| `praxys-feedback-needs-review` | log | `appi-praxys-backend` | `praxys.feedback` `status == needs_review` | 15 min | 3 | 0.50 |
| `praxys-today-latency-regression` | log | `appi-praxys-backend` | `GET /api/today` avg latency > 3000 ms | 1 h | 3 | 0.50 |
| `praxys-sync-systemic-failures` | log | `appi-praxys-backend` | `praxys.sync` — ≥5 distinct users hit systemic failure classes for one platform / 15 min | 15 min | 2 | 0.50 |
| `praxys-connect-systemic-failures` | log | `appi-praxys-backend` | `praxys.connection` — ≥5 distinct users fail connect with systemic classes for one platform / 15 min | 15 min | 2 | 0.50 |
| `praxys-managed-plan-provider-failures` | log | `appi-praxys-backend` | `praxys.managed_plan` — ≥5 distinct users hit `provider` / `provider_auth` failures for one execution target / 15 min | 15 min | 2 | 0.50 |
| `praxys-managed-plan-defects` | log | `appi-praxys-backend` | `praxys.managed_plan` — any known `praxys` ledger/reconciliation/finalization/adapter defect | 15 min | 2 | 0.50 |
| `praxys-labs-queue-backlog` | metric | dedicated Labs Service Bus namespace / `labs-environment-response` | `ActiveMessages` average > 2 over 30 min | 5 min | 2 | ~0.10 |
| `praxys-labs-dead-lettered` | metric | dedicated Labs Service Bus namespace / `labs-environment-response` | `DeadletteredMessages` maximum > 0 over 5 min | 5 min | 2 | ~0.10 |

**Current total ≈ 4.6–5.1 USD/mo.** The live `.run` apex pair adds at most
~0.10 USD/mo before the metric-alert free allotment. Enabling both disabled
`.cn` pairs later adds at most another ~0.20 USD/mo.

### Labs analysis worker alerts (deployment-owned)

`infra/labs-worker.bicep` owns both Sev 2 metric alerts and attaches
`praxys-feedback-ag`. The namespace is dedicated to this pipeline, and each
criterion also filters `EntityName=labs-environment-response`.

- `praxys-labs-queue-backlog` catches sustained capacity pressure without
  paging on one short burst.
- `praxys-labs-dead-lettered` catches any message that exhausted bounded
  infrastructure retries. Scientific unavailable/stale outcomes complete
  successfully and never enter the DLQ.

Use `praxys.labs_job` to distinguish dispatch, transient worker, terminal
worker, cancellation, and scientific outcomes:

```kql
let labs = union isfuzzy=true
  (customEvents
   | where name == "praxys.labs_job"
   | project timestamp,
       event=tostring(customDimensions.event),
       outcome=tostring(customDimensions.outcome),
       trigger=tostring(customDimensions.trigger),
       attempt=toint(customDimensions.attempt),
       failure_class=tostring(customDimensions.failure_class),
       user=tostring(customDimensions.user_id_hash),
       queue_delay_ms=todouble(customDimensions.queue_delay_ms),
       duration_ms=todouble(customDimensions.duration_ms),
       events=1.0),
  (customMetrics
   | where name == "praxys.labs_job"
   | project timestamp,
       event=tostring(customDimensions.event),
       outcome=tostring(customDimensions.outcome),
       trigger=tostring(customDimensions.trigger),
       attempt=toint(customDimensions.attempt),
       failure_class=tostring(customDimensions.failure_class),
       user=tostring(customDimensions.user_id_hash),
       queue_delay_ms=todouble(customDimensions.queue_delay_ms),
       duration_ms=todouble(customDimensions.duration_ms),
       events=coalesce(valueSum, value, todouble(valueCount), 0.0));
labs
| where timestamp > ago(7d)
| summarize events=sum(events), users=dcount(user),
    p95_queue_delay_ms=percentile(queue_delay_ms, 95),
    p95_duration_ms=percentile(duration_ms, 95)
    by event, outcome, trigger, attempt, failure_class
| order by events desc
```

Deployment, diagnosis, and rollback are in
[labs-analysis-worker.md](./labs-analysis-worker.md).

### Systemic connection/sync alerts (provisioned)

`praxys-sync-systemic-failures` and `praxys-connect-systemic-failures` (in the table
above) fire when **≥5 distinct users** hit any *systemic* failure classes for one
platform in 15 min — the distinct-user gate is what separates a fleet-wide break
(platform outage, Cloudflare block, a regression like #369) from one user's wrong
password. The console uses the same platform-level gate, then breaks qualifying
events back down by failure class for diagnosis. Both rules use the
`union (customMetrics),(customEvents)` dual-path shown above, `Count > 0`, and the
`praxys-feedback-ag` action group. `scripts/appinsights_boundary.sh` keeps both
rules scoped to `appi-praxys-backend` on every backend deployment.

> **Dormant until deploy.** The `praxys.sync` / `praxys.connection` signals ship in
> the PR that added these rules; until it deploys there is no data, so the rules
> evaluate to zero and never fire. Threshold `≥5 / 15 min` is a starting point —
> tune to the active-user base once real volume lands.

### Managed-plan alerts (deployment-owned)

`scripts/appinsights_boundary.sh backend-preflight` idempotently creates or
updates both managed-plan rules **before** telemetry cutover, validates their
KQL, 15-minute cadence, Sev 2 threshold, exact component scope, and sole action
group `praxys-feedback-ag`. Preflight also refuses to provision the rules unless
that action group and its `support@praxys.run` email receiver are enabled. It
then includes both rules in `BACKEND_ALERT_NAMES`, so the cutover transaction
migrates and verifies them with every other backend log alert. The definitions
are source-controlled; do not tune them only in the Azure portal.

- `praxys-managed-plan-provider-failures` groups failed/blocked/partial events
  by execution target and `provider` / `provider_auth`, then returns a row only
  at **≥5 distinct athlete pseudonyms**. A single expired credential does not
  page.
- `praxys-managed-plan-defects` returns a row for any failed/blocked/partial
  event with the centrally allowlisted `praxys` domain. These are defects in
  ledger start/finalization, reconciliation, or adapter wiring, so one event is
  actionable.

Provision or repair the checked-in definitions without deploying application
code:

```bash
set -a
source .github/azure-observability.env
set +a
export GITHUB_ENV=$(mktemp)
bash scripts/appinsights_boundary.sh backend-preflight
rm -f "$GITHUB_ENV"
```

Verify both definitions and the paging route:

```bash
for rule in \
  praxys-managed-plan-provider-failures \
  praxys-managed-plan-defects; do
  az monitor scheduled-query show -g rg-trainsight -n "$rule" \
    --query '{name:name,scope:scopes[0],enabled:enabled,severity:severity,frequency:evaluationFrequency,actionGroups:actions.actionGroups}' \
    -o json
done
```

Both scopes must be `appi-praxys-backend`, both frequencies `PT15M`, both
severities `2`, and each `actionGroups` array must contain exactly the
`praxys-feedback-ag` resource id. The action group and its
`support@praxys.run` receiver must both report `Enabled`. To roll back only
these two rules, delete them by exact name; the next backend preflight recreates
them. To roll back the entire telemetry trust boundary, use
`bash scripts/appinsights_boundary.sh rollback-to-frontend`; its guarded
transaction preserves each existing rule and restores every prior scope on
failure. If a partial preflight never created one of these deployment-owned
rules, standalone rollback logs and skips that missing rule rather than
blocking recovery.

> **Currency rule.** Any PR that adds, removes, or re-tunes an alert **must update
> this table in the same PR** — rule name, what it watches, eval frequency,
> severity, and cost. This table is the source of truth; the Azure portal is not.

Verify the live state at any time:
```bash
az monitor scheduled-query list -g rg-trainsight \
  --query "[].{name:name,scope:scopes[0],enabled:enabled,sev:severity,freq:evaluationFrequency,hasAG:length(actions.actionGroups)}" -o table
az monitor metrics alert list -g rg-trainsight \
  --query "[].{name:name,scopes:scopes,enabled:enabled,sev:severity,freq:evaluationFrequency,hasAG:length(actions)}" -o json
```

## Alert cost model

Azure Monitor bills alert rules three different ways — knowing which lever exists
prevents "optimisations" that save nothing. Prices are **eastasia retail**
(via the Retail Prices API; re-check as they change):

```bash
curl -s "https://prices.azure.com/api/retail/prices?\$filter=serviceName%20eq%20'Azure%20Monitor'%20and%20armRegionName%20eq%20'eastasia'%20and%20contains(meterName,'Alert')" | jq '.Items[] | {meterName,unitPrice} '
```

| Alert type | Billed on | eastasia price |
|---|---|---|
| **Log** (scheduled query) | evaluation frequency | 1 min **3.00** · 5 min **1.50** · 10 min **1.00** · **≥15 min 0.50 (floor)** — per rule/mo |
| **Metric** (incl. web-test availability) | monitored time-series | **~0.10** per series/mo, **frequency-independent** (small free allotment) |
| **Metric, dynamic threshold** | monitored time-series | ~2× the static rate |
| **Standard web test execution** | per execution | **0.00** in eastasia (free grant) |

Three rules that follow from the table:

1. **The log-alert floor is 15 min.** Every frequency of 15 min or slower bills at
   the same **0.50**. Slowing a log alert from 15 min to hourly (or daily) saves
   **nothing** — pick that frequency for signal quality, not cost.
2. **Only sub-15-min log alerts cost more.** 5 min = 3× the floor, 1 min = 6×.
   Spend that premium **only where detection latency matters** (a Sev 1 outage).
   Today the sole example is `praxys-db-health-unhealthy` (5 min, +~1.00/mo over the
   floor) — justified: it's the detector for the DB-corruption (2026-07-03) and
   connection-exhaustion (2026-07-05) outages that were previously invisible.
3. **Metric-alert frequency is free.** A 1-min metric alert costs the same as a
   15-min one. When a *metric* signal exists and you want fast detection, a metric
   alert is both cheaper and faster than a log alert.

> Tempting but rejected: re-expressing `praxys.db_health` as a metric alert (flat
> ~0.10, could even run at 1 min) to shave the log premium. `record_db_health`
> emits a customEvent **or** customMetric opportunistically, so a metric alert
> would silently go blind if `azure-monitor-events-extension` is ever installed —
> too fragile for the highest-severity signal. Keep it a log alert.

## Severity & frequency (SLA guidance)

| Severity | Meaning | Recommended shape | Rationale |
|---|---|---|---|
| **Sev 1** | Outage — page a human now | metric alert (any freq) *or* log @ 5 min | MTTD matters; pay the log premium only when no metric signal exists |
| **Sev 2** | Early warning — head off an outage | metric @ ≤5 min (freq is free) *or* log @ 15 min | catch the *cause* one layer before the symptom |
| **Sev 3** | Needs attention, not urgent | log @ 15 min–1 h | all at the 0.50 floor — choose for noise/signal, not cost |

## Adding monitoring — guidance for developers & AI agents

When you add or change a feature, treat monitoring as part of "done":

1. **Does it have an operator-actionable failure mode?** (a sync that can wedge, a
   dependency that can 5xx, a budget that can blow.) If yes, it needs a signal.
2. **Emit through `api/telemetry.py`** — low-cardinality dimensions, **no PII**
   (hash user ids via `hash_user_id`). Prefer a **failure-only** counter (like
   `record_db_health`) so a plain `count > 0` alert works without dimension
   gymnastics.
3. **Pick the alert type from the [cost model](#alert-cost-model):** a metric
   signal that needs fast MTTD → **metric alert** (flat, cheap, any frequency); a
   query that needs KQL or multi-signal correlation → **log alert** (respect the
   0.50 floor; don't go below 5 min unless it's Sev 1).
4. **Wire an action group.** An alert with no action group evaluates but **pages
   nobody** — a silent no-op (three Praxys alerts were in this state until
   2026-07-05). Reuse `praxys-feedback-ag`.
5. **Set severity per the SLA table** — don't over-page (Sev 1 wakes someone).
6. **Update the [inventory table](#alert-inventory-source-of-truth) in the same
   PR** (currency rule).
7. **Keep an alert and its underlying probe in the same enabled state** — a running
   web test whose alert is disabled pays to watch nothing; a disabled probe with a
   live alert never fires.

## Create an alert (general recipe)

1. **Application Insights → Monitoring → Alerts → Create → Alert rule.**
2. **Scope:** `appi-praxys-backend` for server signals,
   `appi-trainsight` for browser RUM, or `praxys-pg` for DB metrics.
3. **Condition → Custom log search:** paste a KQL query that returns rows only
   when you want to fire. Measurement = **Number of results**, **> 0**. Choose the
   evaluation frequency with the cost model in mind (15 min is the log floor; go to
   5 min only for Sev 1).
4. **Actions:** attach the **`praxys-feedback-ag`** action group (Email; Teams /
   webhook / SMS also available). **Don't skip this** — an action-less alert is a
   no-op.
5. **Details:** name + severity (Sev 3 "needs attention", Sev 1 outage), then record
   the rule in the inventory table above.

## Worked example — feedback awaiting triage (`needs_review`)

When a feedback report can't be auto-filed safely it's parked as `needs_review`
(shown as an Admin-sidebar badge in-app). To also email admins:

```kql
union isfuzzy=true
  (customMetrics
    | where name == "praxys.feedback"
    | extend status = tostring(customDimensions.status)),
  (customEvents
    | where name == "praxys.feedback"
    | extend status = tostring(customDimensions.status))
| where status == "needs_review"
```

Wired as `praxys-feedback-needs-review` (results > 0, every 15 min, Sev 3,
`praxys-feedback-ag`). To also catch publish failures use
`where status in ("needs_review", "failed")`.

**Verify:** submit a test report that trips the gate (e.g. with `AZURE_AI_ENDPOINT`
unset, or paste a fake `sk-...` token) and confirm the email within ~15 min.

## Alert deep-dives

### Database health — `praxys-db-health-unhealthy` (#350)

`praxys.db_health` fires from the startup integrity check (`db/session.py`) and
the `/api/health/ready` probe when the database is corrupt or unreachable — the
gap that made the 2026-07-03 corruption *and* the 2026-07-05 connection-
exhaustion outage invisible to the liveness-only `/api/health`. Sev 1, every
5 min (the one justified sub-floor log premium — see cost model).

```kql
union isfuzzy=true
  (customMetrics | where name == "praxys.db_health"
    | extend status = tostring(customDimensions.status)),
  (customEvents  | where name == "praxys.db_health"
    | extend status = tostring(customDimensions.status))
| where status in ("integrity_failed", "check_error", "readiness_failed")
```

Recreate it with (collapse the KQL above onto one line as `<KQL>`):
```bash
AI=$(az resource show -g rg-trainsight -n appi-praxys-backend \
  --resource-type Microsoft.Insights/components --query id -o tsv)
AG=$(az monitor action-group show -g rg-trainsight -n praxys-feedback-ag --query id -o tsv)
az monitor scheduled-query create -g rg-trainsight -n praxys-db-health-unhealthy --scopes "$AI" --condition "count 'q' > 0" --condition-query "q=<KQL>" --evaluation-frequency 5m --window-size 5m --severity 1 --action-groups "$AG"
```

### Postgres connection pressure — `praxys-pg-connections-high`

Catches the *cause* one layer before the readiness 503. Burstable B1ms allows
`max_connections=50` (~35 usable by the app after reserved slots); healthy
baseline is <15. Sev 2, avg `active_connections` > 40 over 5 min. Metric alert,
so the 5-min frequency is free.

```bash
PG=$(az postgres flexible-server show -g rg-trainsight -n praxys-pg --query id -o tsv)
AG=$(az monitor action-group show -g rg-trainsight -n praxys-feedback-ag --query id -o tsv)
az monitor metrics alert create -g rg-trainsight -n praxys-pg-connections-high --scopes "$PG" --condition "avg active_connections > 40" --window-size 5m --evaluation-frequency 5m --severity 2 --action "$AG"
```

> **Health-check caveat (single instance).** Do **not** wire `/api/health/ready`
> as the App Service *health-check path* on this single-instance backend: a
> DB-down readiness failure would trigger health-check-driven container
> restarts, and each restart abandons its connection pool — *amplifying* a
> connection-exhaustion event instead of mitigating it (see the 2026-07-05
> outage in [incident-response.md](./incident-response.md)). The alerts page a
> human instead. Revisit only at ≥2 instances, where a health check removes a
> bad instance from rotation without a restart storm.

### `/api/today` latency regression — `praxys-today-latency-regression`

Sev 3 scheduled query, evaluated hourly over a 24 h window. Fires when the
`GET /api/today` average server duration drifts above 3000 ms (post-PR-139
baseline ~1900 ms; the `n >= 5` guard avoids noise on low-traffic days). At 1 h
eval it bills at the 15-min 0.50 floor.

```kql
requests
| where name == 'GET /api/today'
| summarize avg_ms = avg(duration), n = count()
| where n >= 5 and avg_ms > 3000
```

```bash
AI=$(az resource show -g rg-trainsight -n appi-praxys-backend \
  --resource-type Microsoft.Insights/components --query id -o tsv)
AG=$(az monitor action-group show -g rg-trainsight -n praxys-feedback-ag --query id -o tsv)
az monitor scheduled-query create -g rg-trainsight -n praxys-today-latency-regression --scopes "$AI" --condition "count 'q' > 0" --condition-query "q=<KQL>" --evaluation-frequency 1h --window-size 24h --severity 3 --action-groups "$AG"
```

### External availability

The live **Standard availability tests** ping outside-in every 15 min (30 s
timeout) from **US-West (San Jose, `us-ca-sjc-azr`)** and **APAC (Hong Kong,
`apac-hk-hkn-azr`)** — the vantages that match the audience (US + CN/APAC).
Each has a same-named **metric alert** (Sev 1,
`praxys-feedback-ag`) that evaluates every minute and fires when **≥1
location** reports failure. This is black-box coverage that complements the
inside-the-process db-health / readiness probes.

| Web test | State | Component | Target |
|---|---|---|---|
| `wt-praxys-homepage` | live | `appi-trainsight` | `https://www.praxys.run/` |
| `wt-praxys-run-apex` | live | `appi-trainsight` | `https://praxys.run/` |
| `wt-praxys-cn-apex` | provisioned-disabled | `appi-trainsight` | `https://praxys.cn/` |
| `wt-praxys-cn-www` | provisioned-disabled | `appi-trainsight` | `https://www.praxys.cn/` |
| `wt-praxys-api-health` | live | `appi-praxys-backend` | `https://trainsight-app.azurewebsites.net/api/health` |

Standard web-test execution is **0.00** in eastasia (free grant); three
frontend/API availability alerts are live and both `.cn` pairs are
provisioned-disabled. **Keep each web test and its alert in the same enabled
state** — a probe that runs while its alert is disabled pays to watch nothing
(found and fixed 2026-07-05). Re-point locations via the availability test's
*Locations* in the portal or `az resource update`.

The three regional pairs were provisioned on 2026-08-22. To recreate a missing
pair, use **Application Insights → `appi-trainsight` → Availability → Add
Standard test**:

1. Use the exact name and HTTPS target in the table. Set frequency to 15 min,
   timeout to 30 s, and locations to San Jose plus Hong Kong.
2. Require a successful HTTP response and valid TLS certificate. Do not follow
   a hostname to an unapproved preview or origin URL.
3. Create the same-named Sev 1 metric alert, evaluate every minute, fire when
   at least one location fails, and attach only `praxys-feedback-ag`.
4. Verify the action group and its `support@praxys.run` receiver are enabled.
   Record the web-test resource ID, alert resource ID, and a successful sample
   in the operator change record before DNS or proxy cutover.
5. Creating a missing pair moves it from `planned` to
   `provisioned-disabled`. Before a human approves `launch-cn.yml` `enable`,
   enable each `.cn` test and alert together only after its public hostname is
   ready for outside-in traffic. That reviewed transition is
   `provisioned-disabled` to `live`; the launch workflow only reports the state
   and never changes monitoring resources.

The CLI equivalent below creates an exact test/alert pair in the disabled
state. It refuses to overwrite an existing or partial pair. Use it only to
recreate a missing pair, then enable only a hostname that is already public and
accepted:

```bash
set -euo pipefail

RG=rg-trainsight
SUB="$(az account show --query id -o tsv)"
AI_ID="$(az resource show -g "$RG" -n appi-trainsight \
  --resource-type Microsoft.Insights/components --query id -o tsv)"
AG_ID="$(az monitor action-group show -g "$RG" \
  -n praxys-feedback-ag --query id -o tsv)"

provision_availability_pair() {
  name="$1"
  url="$2"
  alert_id="/subscriptions/${SUB}/resourceGroups/${RG}/providers/Microsoft.Insights/metricAlerts/${name}"

  if az resource show -g "$RG" -n "$name" \
      --resource-type Microsoft.Insights/webtests \
      --api-version 2022-06-15 --output none 2>/dev/null ||
    az monitor metrics alert show -g "$RG" -n "$name" \
      --output none 2>/dev/null; then
    echo "Refusing to overwrite an existing partial or complete pair: ${name}" >&2
    return 1
  fi

  az monitor app-insights web-test create \
    --resource-group "$RG" \
    --name "$name" \
    --location eastasia \
    --web-test-kind standard \
    --defined-web-test-name "$name" \
    --synthetic-monitor-id "$name" \
    --description "Praxys outside-in availability: ${url}" \
    --enabled false \
    --frequency 900 \
    --timeout 30 \
    --retry-enabled true \
    --locations Id=us-ca-sjc-azr \
    --locations Id=apac-hk-hkn-azr \
    --request-url "$url" \
    --http-verb GET \
    --parse-requests false \
    --follow-redirects false \
    --expected-status-code 200 \
    --ignore-status-code false \
    --ssl-check true \
    --tags "hidden-link:${AI_ID}=Resource" \
    --output none

  web_test_id="$(az resource show -g "$RG" -n "$name" \
    --resource-type Microsoft.Insights/webtests \
    --api-version 2022-06-15 --query id -o tsv)"

  body="$(jq -n \
    --arg name "$name" \
    --arg ai "$AI_ID" \
    --arg web "$web_test_id" \
    --arg ag "$AG_ID" \
    --arg ai_tag "hidden-link:${AI_ID}" \
    --arg web_tag "hidden-link:${web_test_id}" '
    {
      location: "global",
      tags: {
        ($ai_tag): "Resource",
        ($web_tag): "Resource"
      },
      properties: {
        description: ("Availability alert for " + $name),
        severity: 1,
        enabled: false,
        scopes: [$web, $ai],
        evaluationFrequency: "PT1M",
        windowSize: "PT5M",
        criteria: {
          "odata.type":
            "Microsoft.Azure.Monitor.WebtestLocationAvailabilityCriteria",
          webTestId: $web,
          componentId: $ai,
          failedLocationCount: 1
        },
        actions: [{actionGroupId: $ag}]
      }
    }')"

  if ! az rest --method put \
      --url "https://management.azure.com${alert_id}?api-version=2018-03-01" \
      --body "$body" \
      --output none; then
    az resource delete --ids "$web_test_id" || true
    return 1
  fi

  test "$(az resource show --ids "$web_test_id" \
    --api-version 2022-06-15 \
    --query properties.Enabled -o tsv)" = "false"
  test "$(az monitor metrics alert show -g "$RG" -n "$name" \
    --query enabled -o tsv)" = "false"
}

# Invoke the function for only the pair proven missing. Examples:
# provision_availability_pair wt-praxys-run-apex https://praxys.run/
# provision_availability_pair wt-praxys-cn-apex https://praxys.cn/
# provision_availability_pair wt-praxys-cn-www https://www.praxys.cn/
```

Enable or disable a pair transactionally. A failed enable compensates back to
both resources disabled, and every transition is read back:

```bash
disable_availability_pair() {
  name="$1"
  rc=0
  web_test_id="$(az resource show -g rg-trainsight -n "$name" \
    --resource-type Microsoft.Insights/webtests \
    --api-version 2022-06-15 --query id -o tsv)"

  az resource update --ids "$web_test_id" \
    --api-version 2022-06-15 \
    --set properties.Enabled=false || rc=1
  az monitor metrics alert update -g rg-trainsight \
    -n "$name" --enabled false || rc=1

  test "$(az resource show --ids "$web_test_id" \
    --api-version 2022-06-15 \
    --query properties.Enabled -o tsv)" = "false" || rc=1
  test "$(az monitor metrics alert show -g rg-trainsight -n "$name" \
    --query enabled -o tsv)" = "false" || rc=1

  return "$rc"
}

enable_availability_pair() {
  name="$1"
  web_test_id="$(az resource show -g rg-trainsight -n "$name" \
    --resource-type Microsoft.Insights/webtests \
    --api-version 2022-06-15 --query id -o tsv)"

  if ! az monitor metrics alert update -g rg-trainsight \
      -n "$name" --enabled true; then
    disable_availability_pair "$name" || true
    return 1
  fi

  if ! az resource update --ids "$web_test_id" \
      --api-version 2022-06-15 \
      --set properties.Enabled=true; then
    disable_availability_pair "$name" || true
    return 1
  fi

  if ! test_enabled="$(az resource show --ids "$web_test_id" \
      --api-version 2022-06-15 \
      --query properties.Enabled -o tsv)" ||
    ! alert_enabled="$(az monitor metrics alert show -g rg-trainsight \
      -n "$name" --query enabled -o tsv)"; then
    disable_availability_pair "$name" || true
    return 1
  fi

  if test "$test_enabled" != "true" ||
    test "$alert_enabled" != "true"; then
    disable_availability_pair "$name" || true
    return 1
  fi
}

enable_availability_pair wt-praxys-run-apex
```

The 2026-08-22 preparation receipt records:

| Web test | Recorded state |
|---|---|
| `wt-praxys-run-apex` | `live` |
| `wt-praxys-cn-apex` | `provisioned-disabled` |
| `wt-praxys-cn-www` | `provisioned-disabled` |

The first `.run` apex samples succeeded from both
`apac-hk-hkn-azr` and `us-ca-sjc-azr` at `2026-08-22T03:25:02Z`.

For an aborted cutover, disable the same-named metric alert and web test in the
same maintenance window, then verify neither continues evaluating. Delete both
only if the hostname is permanently retired; otherwise keep them disabled for
the next window. A provider rollback normally keeps the tests enabled because
they watch the public contract rather than a specific CDN. Re-pointing a test
to an origin hostname is not a rollback and would hide the user-visible outage.

## Rollback / Recovery

`scripts/appinsights_boundary.sh backend-cutover` restores the prior App Service
routing, scheduled-query scopes, API web-test hidden link, and metric-alert
component if any step fails. For an operator-requested reverse migration,
`rollback-to-frontend` moves the same complete set back to `appi-trainsight`.
Scheduled-query scopes are immutable in Azure, so both directions preserve the
full writable rule JSON and delete/recreate each rule under the same name. Each
replacement is read back and compared before the cutover continues; an
incomplete rollback exits with a distinct critical failure. Alerts are otherwise
non-destructive — disable or delete the rule to stop notifications.
To cut cost, remember the log floor: dropping a log alert below 15 min is the only
frequency change that saves money; slowing one past 15 min saves nothing. To cut
noise, tune the window/threshold rather than deleting. Update the inventory table
after any change.

## GitHub automation health

Selective review is repository governance rather than an Azure Monitor signal,
so it has no alert-rule charge and is not included in the Azure inventory
subtotal above. Its required commit status and Actions run are the operational
health surface.

| Workflow | Healthy default-off result | Privileged result | Failure response |
|---|---|---|---|
| `Selective review gate` | Run succeeds as `review-required`; summary says `Policy App required: false`; token step is skipped | An exact promoted candidate or detected stale policy state mints the dedicated App token, rechecks exact refs, and approves or revokes | Keep/restore `PRAXYS_SELECTIVE_REVIEW_ENABLED=false`; inspect the run; restore App credentials before stale-state cleanup |
| `Selective review issue guard` | Linked issue changes dispatch a fresh evaluation and leave the current head pending until it completes | A no-longer-valid candidate is revoked by the policy App | Set the kill switch and dispatch the emergency stop if reevaluation cannot complete |
| `Selective review emergency stop` | No active policy state means no App token is needed | With the kill switch set, immediately fails affected heads, quiesces in-flight gates, reasserts current-head barriers, then disables policy-owned auto-merge and replaces policy approval through the exact App identity | Treat the failed status as the merge barrier; any merge race fails the run; restore/rotate the App identity, rerun, and verify every affected PR is neutralized |

Inspect recent runs and the status on a PR head:

```bash
gh run list --workflow=selective-review.yml \
  --repo praxys-run/praxys --limit 10
gh pr checks <PR_NUMBER> --repo praxys-run/praxys
```

An absent policy App is healthy only when no privileged action is needed. A
candidate or stale-state cleanup that cannot mint the App token must remain
failed because the required `selective-review-policy` status is the fail-closed
merge barrier. Runtime rechecks use workflow-injected repository variables;
`GITHUB_TOKEN` cannot call the repository Actions-variables REST endpoint.
For an immediate mid-run stop, set the kill switch and dispatch the emergency
workflow: it cancels gate runs and reasserts failed required statuses after
quiescence, so a stale workflow variable snapshot is not the final authority.

## Related

- `api/telemetry.py` (signal emitters) · [cost-and-scaling.md](./cost-and-scaling.md) (budget + LLM spend) · [admin-tasks.md](./admin-tasks.md) (feedback triage)
- In-app: Admin → User Feedback (badge + Approve/Retry/Reject).

---
_Last reviewed: 2026-08-22 · Owner: @dddtc2005 · Alert inventory + cost model current as of this review._
