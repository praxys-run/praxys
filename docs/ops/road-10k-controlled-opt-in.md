# Road 10K controlled opt-in foundation

Road 10K is **default-off and default-hidden**.  The only activation input is a
read-only, independently issued stage-authority artifact consumed by
`api/road_10k_stage_authority.py`.  There is no application writer, seed,
admin toggle, permissive local override, or public navigation/deep link.
Missing, off, malformed, stale, incompatible, mixed-version, paused, killed,
not-ready, or provider-fence-open authority is denied.

## Ledger and boundaries

The additive `d2e3f4a5b6c7` migration adds a Road-10K-specific ledger:

* `road_10k_stage_counters` stores monotonic invitation and first-exposure
  counts.  Compiled maximums are 60 cumulative invitations and 30 cumulative
  distinct exposed native owners; authority may only tighten them.
* `road_10k_owner_stage_receipts` is unique on native `users.id` plus stage.
  Invitation retries and same-stage reenrollment are idempotent; withdrawal,
  deletion, retry, rollback, or expiry never decrements a counter or reuses a
  slot.
* `road_10k_exposure_receipts` is committed under the serialized write before
  any Road-10K result is serialized, cached, exported, or downloaded.
* `road_10k_evaluations` is owner-scoped, deletable payload state.  Expiry is
  calculated once from creation and is never slid by reads, updates, restore,
  or reenrollment.  Retention is at most 30 days.
* `road_10k_screenshot_references` stores only private object references.  The
  independent screenshot capture/upload fence is permanently closed in this
  foundation; no screenshot bytes are accepted.

SQLite uses `BEGIN IMMEDIATE`; PostgreSQL uses the stage-counter and
owner-receipt row locks.  Counters are never rebuilt from logs and no owner
identifier, hash, pseudonym, roster, raw event, payload, or screenshot enters
aggregate status or telemetry.

## Owner lifecycle

Only an active, non-demo first-party JWT can discover a returned owner catalog,
reauthenticate, enroll, withdraw, or receive a result.  MCP, plugin, context,
service, AI, demo, and anonymous identities are denied.  Explicit proposal
adoption remains a separate exact-version action; no provider delivery,
automatic adoption, automatic successor, or AI path exists.

Withdrawal immediately deletes evaluation payloads and screenshot references
without changing counters.  Account deletion stages an out-of-database,
payload-free prepared marker before unlinking native owner links, then commits
that marker only after the DB deletion intent commits.  Replay acts only on
committed/completed intent and uses the committed DB state as compensation if a
post-commit marker promotion fails.  The marker contains only deletion
references and retains for the 14-day restore horizon; startup replays markers
before traffic/readiness whenever Road 10K authority or committed obligations
exist, and fails closed if storage or replay is unavailable.  With absent/off
authority and no Road 10K obligation, missing private marker storage is the
healthy dormant state.  A deleted account cannot be linked to a later account.

## Operations and rollback

`road_10k_runtime_snapshot()` is a restricted, read-only low-cardinality
snapshot of authority/readiness, cap state, and replay readiness.  No live
metric resource, schedule, alert, action group, actor binding, or purge job is
created here.  The explicit `purge_expired_evaluations()` primitive is
repository-only and must not be scheduled by deployment.

Pause and kill are independent authority states.  They make proposals
read-only while leaving export, withdrawal, deletion, private feedback, and
existing adopted-plan controls available; they never mutate adopted content.
Rollback is a soft kill that leaves the ledger, manifests, migration, and
objects intact.  A future known-good revision must be forward-compatible and
inactive until fresh authority and independent verification exist.

The checked-in schema/config files document names and shapes only.  They
contain no live authority, user, ceiling override, secret, provider
credential, or deployment value.
