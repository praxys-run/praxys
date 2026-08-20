# Road 10K controlled opt-in foundation

The Road 10K performance capability remains **inactive and default-hidden**.
This repository-only foundation does not expose a route or client control,
invite users, collect evaluation data, adopt plans, deliver workouts, or
change deployment configuration.

## Durable control primitive

`road_10k_owner_opt_in_receipts` is an owner-scoped receipt table whose decision
rows are append-only while the account exists. It is not a feature flag, rollout
assignment, or live configuration value. Receipts are constrained to the reviewed
capability, schema/policy versions, `granted`/`withdrawn` decisions, and
first-party client names. Account deletion cascades to receipts so privacy
deletions remain authoritative; this is the only supported history removal.

`api.road_10k_opt_in.road_10k_owner_opted_in` is intentionally unused by
runtime routes. It requires the capability to be active before it can return
true, and missing, stale, withdrawn, malformed, or unavailable state fails
closed. A future rollout must separately authorize activation, wire an
explicit user journey, and complete independent trust/operations review.

The JSON file in `config/` is a schema only. It contains no live values,
assignments, users, or deployment settings. Do not add a percentage rollout,
global allow rule, invite list, or environment value for this foundation.

## Evaluation boundary

No Road 10K evaluation telemetry, aggregate report, cohort, or runtime
collection is added by this change. Future evaluation requires a separate
privacy-reviewed contract and may only use aggregate result/reason/version
signals; it must not include users, activities, dates, routes, targets,
workouts, samples, personal context, or provider identifiers.
