# Road 10K controlled opt-in foundation

> **Summary:** Inspect the repository-only Road 10K foundation. This revision is
> mechanically hard-off: deployment or configuration cannot activate, invite,
> expose, collect, or authorize a stage action, and cannot schedule or execute
> the unscheduled explicit purge primitive.
> **Use when:** A repository review, restore plan, or readiness investigation
> touches the dormant Road ledger or deletion replay contract.

## Prerequisites

- Repository access to the exact deployed revision and Alembic history.
- Restricted access to aggregate readiness output when separately authorized.
- A future Product, Trust, Architecture, Science, Design, and Operations
  decision before any activation design or live evidence collection.

This runbook does not authorize deployment, live configuration, stage actions,
provider calls, purge work, alerts, resources, or drills.

## Repository checks

1. Confirm one Road migration head with python -m alembic heads.
2. Treat every Road authority file as a dormant parser fixture. The stage
   access, opt-in, readiness, generation, regeneration, and baseline routes
   return a private 404 before authority, authentication, database, storage, or
   provider work. No file, environment value, configuration, receipt, or
   deployment can change that behavior in this revision.
3. Confirm web and miniapp do not mount a Road opt-in surface and reject the
   Road constraint schema from plan-start discovery.
4. Inspect road_10k_runtime_snapshot only as low-cardinality evidence. Its
   authority value is inactive_revision for a valid dormant ledger or
   counter_mismatch for invalid state. Replay is pending or not_required and
   never contains an owner dimension.

## Ledger and rights invariants

- The cumulative ceilings are exactly 60 distinct-owner invitations and 30
  distinct-owner first-result exposures. They cannot be lowered, raised,
  decremented, or recycled after withdrawal or deletion.
- First exposure and its durable evaluation result commit in one serialized
  transaction. A standalone pre-result exposure reservation is rejected.
- Owner, authority, receipt, lifecycle, and timestamp identity is protected by
  database constraints and triggers. Exposure receipts are immutable except
  for owner unlink during account deletion.
- Evaluations expire no later than 30 days after creation. Reads, updates,
  restore, and reenrollment never slide that deadline. Screenshot capture is
  unavailable.
- Authenticated first-party owner export and withdrawal, and global account
  export and deletion, remain rights independent of stage authority. They do
  not activate or expose the capability.

## Deletion replay

A deletion with evaluation or private-object targets first writes a payload-free
private marker, then commits a matching database obligation in the destructive
transaction. Startup touches private marker storage only while a committed
obligation exists. A missing or malformed matching marker, unavailable storage,
or failed delete keeps readiness closed. Prepared markers without a committed
obligation are ignored. Completion is monotonic and obligations cannot be
mutated or deleted.

A withdrawal with no evaluation or object target creates no empty marker and
does not depend on private storage. The in-process replay flag is diagnostic
only; database obligations are the cross-worker source of truth.

The 14-day marker cleanup horizon matches the current database restore horizon.
A restore from a snapshot older than a deletion may also be older than its
database obligation. Live database/private-store restore reconciliation has not
been demonstrated and remains a separately authorized release obligation; do
not claim restore safety or resume traffic from repository tests alone.

## Verification boundaries

Repository tests cover static route denial, fixed counters, SQLite serialization,
ledger triggers, payload retention, deletion replay, data rights, and hidden
web/miniapp clients. Live PostgreSQL concurrency, private-store deletion and
restore, purge scheduling and alerts, provider audit, monitoring, rollback, and
post-release outcomes remain release-only evidence.

The purge_expired_evaluations primitive is unscheduled. Do not run or schedule
it under this repository authorization.

## Rollback / recovery

- There is no operational pause, kill, resume, or activation artifact in this
  revision. A code rollback must remain on a verified hard-off revision.
- Preserve ledgers, obligations, manifests, migration, and private objects.
- Never run the destructive migration downgrade after any counter consumption,
  receipt, evaluation, screenshot reference, or deletion obligation exists; use
  a forward fix.
- Keep traffic closed when a committed obligation cannot replay. Never infer
  completion from elapsed time or a process-local flag.

## Related

- api/road_10k_control.py
- api/road_10k_stage_authority.py
- api/road_10k_deletion_storage.py
- config/road-10k-stage-authority.schema.json
- docs/ops/backup-and-restore.md
- docs/ops/monitoring-and-alerts.md

---
_Last reviewed: 2026-08-22 · Owner: Operations_
