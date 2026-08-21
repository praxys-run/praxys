# Road 10K controlled opt-in foundation

> **Summary:** Inspect and recover the dormant Road 10K repository foundation
> without activating, inviting, exposing, collecting, purging, or provisioning
> anything.
> **Use when:** A deploy, restore, rollback, or readiness investigation touches
> the Road 10K control ledger, external authority reader, or deletion replay.

## Prerequisites

- Repository access to the exact deployed revision and its Alembic history.
- Restricted read access to aggregate readiness output and startup logs.
- A separately authorized operator for any future deployment or stage action.
  This runbook authorizes no live configuration, authority publication,
  invitation, exposure, purge, alert, or provider action.

## Steps

1. Confirm that the deployed revision contains one Road migration head and no
   live authority artifact or permissive application writer.

   ```bash
   python -m alembic heads
   git grep -n "PRAXYS_ROAD_10K_STAGE_AUTHORITY_PATH"
   ```

2. Treat Road 10K as **default-off and default-hidden**. The only activation
   input is a read-only, independently issued stage-authority artifact consumed
   by `api/road_10k_stage_authority.py`. There is no application writer, seed,
   admin toggle, permissive local override, or public navigation/deep link.
   Missing, off, malformed, stale, incompatible, mixed-version, paused, killed,
   not-ready, provider-fence-open, or nonmatching deployed-build authority is
   denied. The local `develop` fallback is never an authorizable build.

3. Inspect the restricted `road_10k_runtime_snapshot()` only as aggregate
   evidence. With authority absent it must still report retained consumed
   counts, remain unready, and expose no owner dimension. Never reconstruct
   counters from logs.

4. Validate ledger and deletion behavior before considering traffic ready.

   - `road_10k_stage_counters` stores monotonic invitation and first-exposure
     counts. Compiled maximums are 60 cumulative invitations and 30 cumulative
     distinct exposed native owners; authority may only tighten them.
   - `road_10k_owner_stage_receipts` is unique on native `users.id` plus stage.
     Invitation retries and same-stage reenrollment are idempotent; withdrawal,
     deletion, retry, rollback, or expiry never decrements a counter or reuses
     a slot.
   - `road_10k_exposure_receipts` is committed under the serialized write
     before any Road result is serialized, cached, exported, or downloaded.
   - `road_10k_evaluations` expires at most 30 days from creation. Reads,
     updates, restore, and reenrollment never slide the deadline.
   - `road_10k_screenshot_references` contains only private object references.
     Capture/upload remains unavailable in this foundation.

   SQLite uses `BEGIN IMMEDIATE`; PostgreSQL uses the stage lock and row locks.
   Database triggers prevent counter decrements and receipt deletion.

5. Preserve owner lifecycle and deletion replay. Only an active, non-demo
   first-party JWT can discover a returned catalog, reauthenticate, enroll,
   withdraw, or receive a result. MCP, plugin, context, service, AI, demo, and
   anonymous identities are denied. Adoption is a separate exact-version
   action; provider delivery, automatic adoption/successor, and AI remain
   unavailable.

   Withdrawal immediately deletes evaluation payloads and screenshot
   references without changing counters. Account deletion stages a
   payload-free out-of-database marker before unlinking native owner links,
   then commits it only after DB deletion intent commits. Replay acts only on
   committed/completed intent. Completed markers remain through the 14-day
   restore horizon; unresolved markers are never aged out. Startup replays
   markers and validates ledger consistency before readiness whenever Road
   authority or durable Road obligations exist.

6. Keep operations definitions inactive. No live metric resource, schedule,
   alert, action group, actor binding, or purge job is created here. The
   explicit `purge_expired_evaluations()` primitive must not be scheduled by
   this repository authorization.

## Verify

- `python -m alembic history --rev-range=b8d4e6f7a9c1:heads` shows only
  `d2e3f4a5b6c7` after the merge point.
- `/api/health/ready` denies partial Road schemas, counter/receipt mismatch, and
  blocked replay; absent schema or absent/off authority with no Road obligation
  remains a healthy dormant state.
- The restricted runtime snapshot preserves actual aggregate consumed counts
  when authority is absent and never exposes an owner ID, hash, roster, raw
  payload, or screenshot.
- Provider audit shows zero Road delivery, removal, AI, MCP, or automatic
  adoption calls.
- Repository tests cover SQLite concurrency, migration triggers, deletion
  replay, marker retention, and default-hidden clients. Live PostgreSQL and
  private-object restore evidence remains a later operator obligation.

## Rollback / Recovery

- Pause and kill are independent authority states. They make proposals
  read-only while preserving export, withdrawal, deletion, and adopted-plan
  owner controls.
- Rollback is a soft kill plus redeploy of a verified known-good inactive
  revision. Leave ledgers, manifests, migration, and objects intact.
- Never run the destructive migration downgrade after any slot or receipt has
  been consumed; the migration refuses it. Use a forward fix.
- A restored database must replay out-of-database deletion markers and pass
  ledger consistency before traffic. Never resume automatically.

## Related

- `api/road_10k_control.py`
- `api/road_10k_stage_authority.py`
- `api/road_10k_deletion_storage.py`
- `config/road-10k-stage-authority.schema.json`
- `docs/ops/backup-and-restore.md`
- `docs/ops/monitoring-and-alerts.md`

---
_Last reviewed: 2026-08-21 · Owner: Operations_
