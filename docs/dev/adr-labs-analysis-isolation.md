# ADR: isolate Labs analysis compute

- **Status:** Accepted
- **Decision date:** 2026-08-09
- **Issue:** [#619](https://github.com/praxys-run/praxys/issues/619)

## Context

The environmental-response experiment is CPU- and memory-intensive relative to
the B1 App Service plan that serves the interactive API and frontend.

A production-sized run processed 287 activities and 1,325 candidate segments.
The analysis itself ran for 421 seconds and consumed about 223 CPU-seconds. At
the App Service plan level, average CPU reached 81%, peak CPU reached 99%, and
memory reached 86%. During the run, successful API request latency increased
from a quiet p50 of about 19 ms and p95 of 110-222 ms to a p50 of 130 ms, p95
of 800 ms, and maximum of 1,207 ms. No HTTP 5xx or request-queue buildup was
observed, but one analysis nearly exhausted the shared plan.

The current FastAPI `BackgroundTasks` execution is also process-local. App
recycles can abandon work, and a GET request currently acts as a recovery
dispatcher. Repeated recomputes can replace an active generation while its old
worker continues consuming CPU.

## Decision

Production execution uses this pipeline:

```text
FastAPI
  -> PostgreSQL job + transactional outbox
  -> Azure Service Bus Basic queue
  -> Azure Container Apps event-driven Job
  -> PostgreSQL aggregate result/status
```

The queue message contains only an opaque job ID. The worker resolves the
owner, experiment, model version, source revision, and correlation fence from
PostgreSQL. Raw activities, samples, routes, dates, and research rows never
enter Service Bus or persistent worker storage.

The Container Apps Job is configured for one execution and one replica at a
time, 1 vCPU / 2 GiB, a 30-minute timeout, scale-to-zero, and one queue message
per execution. This provides the global concurrency cap and queue backpressure
without reserving a permanently running worker.

## Durability and retry semantics

- Enqueue creates the job and payload-free outbox row in the same transaction.
- The API attempts immediate outbox dispatch, while a lightweight reconciler
  retries pending dispatches and recovers expired processing leases.
- Service Bus delivery is at least once. Job claiming and result persistence
  are idempotent, so duplicate messages are harmless.
- The worker locks one broker delivery before database initialization or
  importing the analysis runtime. Initialization failures therefore abandon a
  real delivery instead of causing unbounded event-trigger launches that never
  consume retry budget.
- Unexpected transient analysis failures are abandoned for redelivery. The
  durable job permits three claimed analysis attempts; Service Bus permits ten
  transport deliveries so initialization/settlement failures still terminate
  in the broker DLQ.
- Scientific outcomes such as insufficient support, unstable association, or
  stale source data are successful terminal executions and are never retried.
- Source-revision, correlation-ID, consent, and deletion-tombstone checks remain
  mandatory immediately before persistence.
- Withdrawal marks queued/running jobs cancelled and deletes consent/results.
  Residual compute may finish, but its fenced write is discarded.

## Abuse and accidental-repeat controls

- A database-enforced partial unique index permits at most one active job per
  user and experiment.
- Recompute accepts an idempotency key; replaying the same key returns the
  original job instead of creating another generation.
- Requests made while a job is active return that active state.
- Manual recompute has a six-hour cooldown and a maximum of three accepted
  requests in a rolling 24-hour window.
- Eligibility and authenticated write access are checked before every enqueue.

## Observability

`praxys.labs_job` structured events record enqueue, dispatch, start, retry,
completion, cancellation, and failure outcomes with a pseudonymous user ID,
attempt, trigger, failure class, queue delay, and duration. Service Bus metric
alerts cover sustained active-message backlog and any dead-lettered message.
The worker uses the backend Application Insights component and contains no raw
athlete data in telemetry.

## Alternatives considered

- **Keep FastAPI background tasks:** rejected because compute still competes
  with interactive traffic and recycle durability remains process-local.
- **Separate process on the same App Service plan:** rejected because CPU and
  memory contention are plan-wide.
- **Azure Functions:** viable, but a Container Apps Job better matches the
  existing Python runtime, seven-minute CPU-heavy process, 30-minute safety
  envelope, and explicit one-container concurrency.
- **Permanent VM/container worker:** rejected because the low current volume
  does not justify always-on cost or operations.
- **Tencent SCF/TKE worker:** rejected for the current architecture because the
  API, PostgreSQL database, identities, and athlete data remain in Azure.
  Cross-cloud transfer would add latency, privacy surface, and operational
  coupling. Revisit only with a complete future mainland-China data plane.

## Cost

At East Asia list rates, a 421-second 1-vCPU/2-GiB execution costs about
USD 0.0126 before the Container Apps monthly free grant. The free grant covers
roughly 375-428 runs of this size per month. Service Bus Basic operations are
negligible at this volume. The public GHCR image avoids a standing registry
charge.

## Rollout

The backend keeps an explicit local/integration-test inline mode. Production
switches to `service_bus` only after the queue, worker identity, least-privilege
PostgreSQL principal, Container Apps Job, and alerts are verified. Once
`service_bus` is selected, dispatch failures remain durable in the outbox; the
backend never silently falls back to in-process analysis.
