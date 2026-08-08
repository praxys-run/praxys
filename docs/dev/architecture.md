# Architecture

## System Overview

```
Garmin/Stryd/Oura APIs
        |
   sync/*.py          Fetch + normalize → DB rows
        |
   db/                SQLAlchemy ORM + SQLite
   ├── models.py         9 models (User, Activity, etc.)
   ├── session.py        Engine + session management + auto-migration
   ├── crypto.py         Envelope encryption (Key Vault / Fernet)
   └── sync_writer.py    Upsert helpers for sync scripts
        |
   analysis/          Pure computation layer
   ├── data_loader.py    DB + CSV loading, cross-source merging
   ├── metrics.py        All metric functions (pure, no I/O)
   ├── zones.py          Zone boundary calculation
   ├── config.py         User config (DB-backed with file fallback)
   ├── science.py        Theory loading from YAML
   ├── evidence_registry.py
   │                     Evidence + decision validation
   └── providers/        Platform-specific data adapters
        |
   api/               FastAPI application
   ├── main.py           App + lifespan (init_db, scheduler)
   ├── auth.py           JWT token validation middleware
   ├── users.py          FastAPI-Users integration
   ├── deps.py           Data layer (get_dashboard_data())
   ├── ai.py             AI context builder + plan validation
   ├── plan_delivery/    Provider-neutral workout delivery + adapters
   └── routes/           Thin endpoint handlers
        |
   ┌────┴────────────┐
   web/    plugins/praxys/
   React   MCP server (12 tools,
   SPA     local + remote modes)
```

## Key Design Decisions

### Single Computation Entry Point

`api/deps.py:get_dashboard_data()` is the sole entry point for all computed data. It:
1. Loads config and data from the database (per-user)
2. Resolves thresholds (auto-detect + manual overrides)
3. Loads active science theories
4. Computes all metrics (fitness/fatigue, diagnosis, predictions, recovery)

Both the API routes and MCP plugin tools call this function. This ensures web and CLI always show identical data.

### Pure Metric Functions

All functions in `analysis/metrics.py` are pure — they take data in, return results out, with no I/O or side effects. This makes them testable and composable. I/O is handled by `data_loader.py` (reading) and `api/deps.py` (orchestration).

### SQLite Database

Training data is stored in a SQLite database (`DATA_DIR/trainsight.db`) via SQLAlchemy ORM. This replaced the earlier flat-CSV approach to support multi-user deployments:
- Per-user data isolation via `user_id` foreign keys on all data tables
- Encrypted credential storage (platform passwords never stored in plaintext)
- Atomic writes via transactions
- `data/sample/` CSVs still exist for seeding and testing

### Database Layer

**Engine:** SQLAlchemy ORM with both sync (for pandas data loading) and async (for FastAPI-Users) sessions. The database file lives at `DATA_DIR/trainsight.db` (configurable via the `DATA_DIR` environment variable, defaults to `data/`).

**Models** (defined in `db/models.py`):

| Model | Table | Purpose |
|-------|-------|---------|
| `User` | `users` | FastAPI-Users user model (email, hashed_password, is_superuser) |
| `Invitation` | `invitations` | One-time registration codes (code, created_by, used_by, is_active) |
| `UserConfig` | `user_config` | Per-user settings (training_base, thresholds, zones, goal, science, preferences) |
| `UserConnection` | `user_connections` | Platform credentials per user (encrypted_credentials, wrapped_dek, status) |
| `Activity` | `activities` | Merged activity data from all sources (distance, duration, power, HR, pace, load scores) |
| `ActivitySplit` | `activity_splits` | Per-interval split data within activities (split-level power, pace, HR) |
| `RecoveryData` | `recovery_data` | Sleep and readiness data (HRV, sleep score, resting HR, body temp) |
| `FitnessData` | `fitness_data` | Per-metric fitness tracking (VO2max, CP estimate, LTHR, max HR) |
| `TrainingPlan` | `training_plans` | Canonical Praxys-owned or imported provider workouts, with explicit provenance and durable workout identity |
| `PlanRevision` | `plan_revisions` | Append-only plan mutation events with actor/origin and before/after snapshots |
| `PlanDelivery` | `plan_deliveries` | Provider-neutral state for one canonical workout/provider-payload version, including normalized content and provider-account fencing |
| `PlanDeliveryAttempt` | `plan_delivery_attempts` | Append-only deliver/remove/import attempt history |
| `PlanTargetCalendarSync` | `plan_target_calendar_syncs` | Latest successful account-fenced target-calendar coverage window |
| `PlanTargetWorkout` | `plan_target_workouts` | Normalized target workout observations and confirmed absences keyed by external ID |

**Session management** (`db/session.py`):
- `init_db()` creates both sync and async engines, runs `create_all()`, then applies lightweight schema migrations
- `get_db()` is a FastAPI dependency yielding sync sessions
- `get_async_db()` yields async sessions for FastAPI-Users

### Schema Migration

SQLite development databases use `create_all()` plus narrow additive
compatibility columns in `db/session.py`. PostgreSQL deployments run Alembic
to the current head during startup.

### Authentication

**JWT via FastAPI-Users.** All data endpoints require a valid `Authorization: Bearer <token>` header. Tokens are issued by `POST /api/auth/login` (FastAPI-Users auth backend) and validated by `api/auth.py:get_current_user_id()`.

**Registration flow:**
1. First user on a fresh database becomes admin automatically (no invitation code needed)
2. A user whose email matches `PRAXYS_ADMIN_EMAIL` env var registers without an invitation and becomes admin
3. All other users must provide a valid one-time invitation code (generated by an admin via `POST /api/admin/invitations`)

The custom registration endpoint (`api/routes/register.py`) enforces these rules and delegates password hashing to FastAPI-Users' `UserManager`.

### Credential Encryption

Platform credentials (Garmin/Stryd passwords, Oura tokens) are stored encrypted using envelope encryption (`db/crypto.py`):

1. A fresh **Data Encryption Key (DEK)** is generated per credential (Fernet)
2. The DEK encrypts the credential JSON
3. The DEK itself is wrapped by a **master key**:
   - **Production:** RSA key in Azure Key Vault (`KEY_VAULT_URL` + `KEY_VAULT_KEY_NAME` env vars)
   - **Development:** Local Fernet key (`PRAXYS_LOCAL_ENCRYPTION_KEY` env var)
4. Both `encrypted_credentials` and `wrapped_dek` are stored as binary columns on `UserConnection`

If `KEY_VAULT_URL` is set, the `CredentialVault` initializes an Azure `CryptographyClient`. Otherwise, it falls back to local Fernet encryption. If neither is configured, it generates an ephemeral key and logs a warning (credentials will not survive restarts).

### Plan Delivery Boundary

`api/plan_delivery/` separates provider-neutral orchestration from Stryd API
details. The service authenticates before starting a durable attempt, scopes
credentials and ledger rows to the authenticated Praxys user, and records a
fingerprint of the exact provider payload (including CP-derived workout
blocks), plus a normalized content fingerprint that excludes volatile provider
identifiers. The canonical Praxys plan version remains separate so
reconciliation can distinguish a Praxys edit from a target edit.

Successful creates persist the authenticated provider account ID. A later
delete is refused if the user has reconnected a different provider account.
Replacement is intentionally a confirmed delete followed by create so a
partial failure is explicit and recoverable rather than success-shaped.
Unowned provider workouts are never deleted and do not block Praxys from adding
a separate workout on the same date.

`api/plan_delivery/rolling.py` applies that boundary to the next 14 calendar
days. Every provider mutation rechecks Praxys ownership mode, explicit delivery
consent, adapter capability, and the current connection status. A fresh target
calendar snapshot then gates each workout through reconciliation: matching or
pending observations are no-ops, target edits/deletions remain explicit
conflicts, and accepted canonical edits replace only the exact UUID-owned
delivery. Deleting a canonical workout while managed removes that owned target
workout. Pausing delivery never performs cleanup. Leaving managed mode keeps
target workouts by default; a separate, explicit cleanup can remove future
workouts recorded in the caller's delivery ledger only after external mode has
disabled further writes. Cleanup repeats that lifecycle check and fences every
delete on the unchanged target, live connection status, and credential
generation. Uncertain ledger rows remain visible as partial cleanup rather than
being mistaken for an empty provider calendar.

Only one rolling pass may run per user. PostgreSQL holds a session-level
advisory lock and runs the complete ORM pass on that same physical connection,
so a small shared pool never needs a second slot just for serialization.
SQLite uses the equivalent process-local lock. Connection-success bookkeeping
also carries the starting health fence, so a stale successful calendar read
cannot clear a newer authentication or rate-limit backoff recorded by another
sync path.

Explicit row delivery uses the same just-in-time connection-generation fence
and re-reads the exact canonical UUID/version while holding the plan-write lock
immediately before provider I/O. A concurrent plan edit or deletion therefore
blocks the stale write instead of creating an obsolete target workout.
Reconciliation restore applies the same composite connection and canonical
version fence before each provider delete or create. Its opaque generation
also fingerprints the complete semantic target-calendar snapshot, preventing
a concurrent sync from introducing an unseen matching workout mid-resolution
without invalidating IDs for timestamp-only refreshes.
Adoption previews retain the 14-day UTC delivery window and persist the
detected IANA timezone. Daily plan views use the device-local date so
athlete-local automatic changes stay visible across UTC midnight. The settings
mutation carries the reviewed start date, accepts the current athlete-local
date plus the current UTC date for rolling client compatibility, rejects an
expired preview, and pins the immediate delivery pass to that boundary without
backdating its retry or observation clock.

Plan commits and delivery commits remain separate. Settings adoption and
committed plan upload/upsert/delete operations start a best-effort post-commit
pass, while the existing background scheduler advances the rolling horizon and
retries safe failures. Automatic retries are durable, exponential, capped, and
limited to definite retry-safe outcomes; ambiguous create outcomes remain
conflicts to prevent duplicate workouts.

Garmin is also available as an explicitly opt-in experimental execution
target. Its undocumented two-ID, two-POST lifecycle is represented with
durable provider references and intermediate attempt checkpoints: the reusable
template ID is persisted before schedule, and the scheduled-instance ID
remains the delivery `external_id`. Recovery may adopt only one newly observed, account-fenced
marker-and-payload template match. Scheduled instances require the exact ID
returned and durably checkpointed from Praxys's own request; a schedule seen
only by calendar set difference remains unowned and fails closed. A returned
ID that existed before the request is rejected. A returned instance on an
unexpected date is directly verified and retained only as an unowned conflict
candidate; explicit reconciliation is required before it may be adopted or
removed.
Calendar reconciliation retains the rollout-compatible account hash; every
new observation and mutation also carries a private immutable
`userProfileId` fence. Matching immutable references bridge display-name key
changes; different profiles fail closed, including for empty calendar
snapshots. Template recovery scans are bounded to 500 entries: saturation
before upload is non-retryable, while saturation after a possible upload
remains an unknown outcome. Confirmed authentication failures stop delivery;
rate limiting stops the current batch and backs off the connection.
Unsupported power, pace, and heart-rate targets are rejected, so the current
adapter advertises duration-only fidelity. Static Garmin plan capability stays
false; the default-off deployment gate and connection- and region-bound
consent must both be active before that user gains an effective capability. The
[Garmin workout-delivery feasibility study](../studies/garmin-workout-delivery-feasibility.md)
documents the remaining unsupported-API and unvalidated international/CN
risks. Garmin's official Training API remains the preferred replacement.

### Admin System

Admin endpoints (`api/routes/admin.py`) are gated by `is_superuser=True` on the authenticated user. Capabilities:

- **User management:** List all users, delete a user (cascades all their data), toggle admin role
- **Invitation codes:** Generate (`TS-XXXX-XXXX` format), list with usage status, revoke
- Self-modification safeguards: admins cannot delete themselves or change their own role
- **Demo accounts:** Read-only accounts that mirror an admin's data (see below)

### Demo Accounts

Demo accounts let admins share a live, read-only view of their dashboard with others.

**Data model:** Two columns on `User`: `is_demo: bool` and `demo_of: FK → users.id`. When `is_demo` is true, all data queries resolve to `demo_of` (the admin's user_id) instead of the demo user's own id.

**Auth dependencies (`api/auth.py`):**
- `get_current_user_id` — resolves the authenticated user (unchanged)
- `get_data_user_id` — returns `demo_of` for demo users, own `user_id` for normal users. Used on all READ endpoints.
- `require_write_access` — raises 403 for demo users. Used on all WRITE endpoints.

**How it works:**
1. Admin creates a demo account via `POST /api/admin/demo-accounts` (email + password)
2. The demo user is created with `is_demo=True, demo_of=<admin's user_id>`
3. Demo user logs in normally (JWT auth) but all data reads are scoped to the admin's data
4. All write operations (settings, sync, plans, connections) return 403
5. Frontend shows a persistent amber banner: "Live demo with real training data — read-only mode"
6. Settings page is visually dimmed with pointer-events disabled

**Key design decisions:**
- No data duplication — demo users see live data that updates when the admin syncs
- Each admin's demo accounts only see that admin's data (supports multiple admins)
- Server-side enforcement — even direct API calls get 403, not just UI hiding

### Pluggable Science Framework

Training theories (load models, zone frameworks, prediction methods, recovery protocols) are YAML files in `data/science/`. The user selects one theory per pillar in their config. This means:
- Metrics adapt to the selected theory (zone boundaries, time constants, etc.)
- New theories can be added by creating a YAML file — no code changes
- Linked theories resolve citations from the versioned evidence registry rather
  than duplicating bibliographic metadata in English and Chinese files

`analysis/evidence_registry.py` strictly validates two separate record graphs:

- `data/science/evidence/` preserves reproducible literature searches, bounded
  claims, evidence strength, applicability, limitations, and citation metadata.
- `data/science/decisions/` records the human-reviewed product interpretation,
  rejected alternatives, published-versus-Praxys parameter provenance,
  validation/falsification plans, affected surfaces, and supersession history.

Accepted theory YAML links an exact model version to an accepted SDR. The loader
rejects missing claims, conflicting citation identifiers, unreviewed decisions,
or parameters whose value/provenance differs from the linked decision. The
generated `data/science/REGISTRY.md` is the human-readable lifecycle index.

### Multi-Source Data Merging

Activities can come from Garmin, Stryd, or Coros. `data_loader.py` merges them:
- Primary source set via `config.preferences.activities`
- Secondary sources enrich with additional columns (e.g., Stryd adds power to Garmin activities)
- Matching uses date + timestamp proximity (handles timezone differences)

Analytical recovery inputs are intentionally not blended: the configured
provider wins when it has rows, otherwise Praxys selects one deterministic
fallback by newest row, row count, then source name.

Plan ownership is separate from provider preference. `config.plan_management`
contains `mode`, `execution_target`, `delivery_enabled`, and
`adjustment_policy`. External mode preserves the legacy
`config.preferences.plan` preferred-source fallback. Praxys mode treats only
the explicit Praxys-owned lane (`source='praxys'`) as canonical; historical
`source='ai'` rows remain a read-compatible storage alias during the
expand/contract rollout. The expand release centralized writes behind
`PRAXYS_PLAN_WRITE_SOURCE` while retaining `ai`; after that release deployed,
the contract release flipped the constant to `praxys` and added an idempotent
startup normalization for legacy rows. Reads continue accepting both aliases,
so a late expand worker or rollback to the expand release remains safe.
Platform rows remain loaded for management and reconciliation but never
silently become the plan. The additive contract defaults to external mode with
delivery disabled, so existing users are not enrolled in platform writes.
Enabling delivery requires an actively connected target with a registered plan
adapter. Once selected, that target remains part of the managed-plan intent
through a disconnect so the UI can request reconnection and later clean up the
correct delivery ledger; provider writes remain gated on the live connection.
The normalized target is also stored in the additive
`user_config.plan_execution_target` column. New workers restore it only when a
legacy worker has dropped the target from `plan_management` JSON, while a
valid explicit JSON target remains authoritative. A target change first imports
legacy Stryd delivery evidence and is rejected while any future, non-removed
delivery remains on another connector. Users therefore leave managed mode,
clean up old owned deliveries, and only then select a different connector;
manual Stryd writes enforce the same fence immediately before provider I/O.

Automatic plan adjustment is a second, independent consent boundary.
`suggest_only` remains the default in every ownership mode.
`auto_conservative` is available only while Praxys owns the canonical plan and
is reset when the user leaves that mode. Consent also persists the device's
valid IANA timezone in `source_options.athlete_timezone`; adjustment evaluation
derives the plan day in that athlete-local timezone and fails closed when the
timezone is absent or invalid. Consent updates do not depend on execution-target
connectivity, and the compatibility layer preserves an existing opt-in when an
older client resumes paused delivery with its historical `suggest_only`
placeholder. The pure evaluator in
`analysis/plan_adjustments.py` currently permits one bounded action: replace
today's single Praxys-generated hard workout with rest when same-day
individualized HRV is below its personal caution band and a dedicated HRV-only
daily signal agrees. The adjustment loader selects only plan rows, recovery
observations, and an activity-existence ID; activity intensity is never loaded.
Prior-day, stale, missing, or internally inconsistent recovery; manual or
adopted provenance; an already-recorded activity; ambiguous plan rows; changed
canonical content; or uncertain target state fails closed. Target evidence is
loaded through the same bounded loader and is current only when the latest
calendar snapshot covers the athlete-local workout date and refreshed its
matching observation. The threshold and rest-day mapping are explicit product
estimates, not diagnoses or clinically validated prescriptions. Manual and
scheduled syncs invoke the isolated lifecycle before post-sync insight
generation; mutation, undo, and audit-recovery delivery passes are pinned to
the snapshot's logical workout date.

The lifecycle serializes with plan delivery and reconciliation, re-evaluates
all evidence under the plan-write fence, and records the mutation plus delivery
consequence as append-only `PlanRevision` events. Undo restores only an exact
still-current after-snapshot, including provenance and metadata; later edits
turn the history item into `superseded` rather than being overwritten. The
mutation revision is also a durable pending-delivery record. A later identical
evaluation retries a missing consequence record only while that exact adjusted
snapshot remains current.

The proposed agent-native lifecycle above the current workout-level contract is
documented in
[`adaptive-plan-architecture.md`](./adaptive-plan-architecture.md). It defines
the future plan aggregate, proposal and approval boundary, athlete-scoped
decision/outcome traces, Plan/Insights client split, and compatibility sequence.
It is an architecture proposal under #584, not shipped behavior; current
automatic adjustment remains limited to the separately consented conservative
policy described above.

Ownership and authorship are separate. `TrainingPlan.source` identifies the
owner lane, while `TrainingPlan.workout_origin` records whether content was
`generated`, `accepted_target`, `manual`, `imported`, or retained as `legacy`
history.

Plan mutations write immutable `PlanRevision` events in the same transaction as
their `TrainingPlan` changes. Each plan row has a durable UUID that survives
unique content matches or otherwise unambiguous one-to-one edits and permits
multiple same-day/same-type workouts. Ambiguous replacement groups receive new
UUIDs rather than transferring delivery ownership by row order. Modern delivery
rows bind `PlanDelivery.canonical_id` to that exact UUID; content/date heuristics
are restricted to legacy rows that predate canonical identity. The legacy
`canonical_key` value `ai:<uuid>` is deliberately frozen as a compatibility
namespace so old and new workers converge on the same delivery row during a
rolling deployment; its prefix no longer denotes ownership or AI authorship.
Platform delivery rows are keyed by that logical workout plus a SHA-256
fingerprint of delivery-relevant content;
attempts append beneath that identity, so a retry cannot duplicate a successful
delivery of the same version. Provider writes run through
`api/plan_delivery/`: the service owns ledger transitions and fencing, while
provider adapters own authentication plus create/delete/calendar operations.
Adapters receive credentials resolved from the caller's encrypted
`UserConnection`; the Stryd adapter never reads another user's connection.

Successful Stryd and Garmin syncs also write account-fenced calendar
snapshots. Garmin calendar reads always remain available for reconciliation;
consumer-API writes are exposed only when the operator gate is enabled and
explicit experimental consent is bound to the current credential generation
and region. Reconnect, credential rotation, or disconnect invalidates that
consent; a region change also disconnects the old region and requires a fresh
login. Garmin OAuth sessions use garminconnect's in-memory serialization and are
envelope-encrypted on the user's connection row with a separate wrapped DEK.
A stored credential-generation fingerprint makes the ciphertext unusable after
any credential replacement, including one performed by an older worker.
A per-user cross-process lease serializes token refreshes across sync, delivery,
reconnect, and cleanup workers. Interactive login keeps MFA state and completed
tokens in memory until credentials and the same generation-fenced token bundle
commit atomically. Startup migrates valid legacy token files into the database
and removes every plaintext store before the scheduler starts. A sync rechecks
its captured generation before provider work and each commit. The entire legacy
token root is replaced by a non-secret blocker file, so an older worker cannot
recreate plaintext for any existing or newly registered user during rollout or
rollback. A stale
sync rolls back without degrading the replacement connection. Every external ID is
retained as a normalized
observation; previously observed or Praxys-delivered IDs are marked absent only
inside the conservatively covered sync window for the same provider account.
Fetch-start generations prevent an older concurrent provider read from
overwriting a newer snapshot.
`GET /api/plan` joins these
observations to canonical workouts globally before filtering the requested
display window, preventing a moved owned workout from appearing target-only.
Exact external IDs win;
a unique date/fingerprint match is surfaced only as a stale-ID conflict
candidate and never authorizes deletion.

Conflict resolution is always explicit. Accepting the target version updates
the canonical plan, revision, delivery binding, and provenance in one database
transaction. Restoring Praxys records an idempotent revision, then runs the
owned-ID remove/create saga through `PlanDeliveryService`; partial outcomes
remain retryable delivery attempts. Client-visible reconciliation IDs include a
frozen conflict-generation token, so an exact successful HTTP retry can recover
its prior revision/result without reapplying a later state. An interrupted
remove/create retry can reconstruct only its own recorded removal transition;
the durable revision, successful-removal attempt, and unchanged remainder of
the calendar generation remain mandatory.

The former per-user Stryd push-status JSON is
lazy-reconciled through an ordered snapshot cursor. During rolling deployment it
is retained and dual-written after successful push/delete operations so old
workers remain compatible; additions, replacements, and removals are reflected
without certifying unknown content as the current version. Corrupt files are
quarantined and never converted into successful delivery state. Their durable
unresolved marker keeps cleanup blocked after quarantine until a
provenance-marked authoritative recovery import or explicit review;
pre-marker quarantine archives are backfilled on first cleanup. Routine valid
files remain non-authoritative while fenced, including files recreated by an
older deployed worker. Compatibility dual-writes are suspended on marker-aware
workers, so a newly delivered subset cannot masquerade as a recovery snapshot.
A verified
ledger row is authoritative over a stale legacy snapshot, including after
removal, so an old worker cannot resurrect a deleted delivery. Per-user database
locks plus a cross-process file lock serialize cursor/file changes on both
PostgreSQL and SQLite, and dual-writes verify the user still exists so an
in-flight request cannot recreate status after account deletion. Because the
legacy file holds only one ID per date, replacing that entry between two
verified, distinct canonical workouts never tombstones either same-day delivery.

### LLM-backed Insights

The post-sync hook (`api/insights_runner.py`) runs two durable bilingual generators
(`training_review`, `race_forecast`) after syncs that wrote new rows, gated by:

- **Content-addressable cache.** Each durable insight type has a SHA-256 fingerprint (`analysis/insight_hash.py`) of the inputs that drive it (sessions, CP trend, goal, etc.). The user's selected science pillars are folded in, so swapping load model from Banister to Seiler invalidates the hash and regenerates on next sync. A matching hash is trusted only when the row also carries server-owned generation provenance.
- **Per-user daily cap.** `PRAXYS_INSIGHT_DAILY_CAP` (default 30) bounds LLM calls per user per UTC day. When the cap is exhausted the runner short-circuits and existing rows persist.
- **Graceful fallback.** When `AZURE_AI_ENDPOINT` is unset (or the openai/azure-identity SDKs are missing), `api.llm.get_client()` returns `None`, generators return `None`, and rule-based product surfaces continue to render. Sync never fails because of insight generation; both hook sites catch and log exceptions.

**Deterministic Today.** Same-day guidance comes only from `daily_training_signal()`.
The runner never generates or refreshes `daily_brief`; insight reads hide legacy
rows, and daily pushes or feedback return HTTP 410. This prevents narrative prose
from contradicting the canonical verdict.

**Bilingual generation (issue #103).** A single LLM call returns `{"en": {...}, "zh": {...}}`. The English block populates the existing top-level columns (`headline`, `summary`, `findings`, `recommendations`); the zh block lands in the new additive `translations` JSON column. Categorical enums (finding `type`) stay as English keys and are translated client-side via `web/src/lib/display-labels.ts`. The frontend reads `insight.translations[locale]` with English fallback. `LocaleContext.setLocale` invalidates React Query so cached locale-sensitive payloads (science labels, AI insights) refetch immediately on switch.

**Hook points.** `api/routes/sync.py::_run_sync()` (the API-triggered path) and `db/sync_scheduler.py::_sync_connection()` (background scheduler) both call `run_insights_for_user(user_id, db, counts)` after `db.commit()`, wrapped in try/except.

**Auth.** `api/llm.py::get_client()` uses `DefaultAzureCredential` + `get_bearer_token_provider` — same scaffolding as `scripts/translate_missing.py`. No API key path. Reasoning deployment configured via `PRAXYS_INSIGHT_MODEL`; new-string translation via `TRANSLATE_MODEL`; native-language catalog editor/critic review via `TRANSLATE_REVIEW_MODEL`.

**Mini program.** Training and Goal render the same durable insight receipts as
web with deterministic fallbacks. Today renders only the canonical deterministic
signal and never requests a `daily_brief` row.

### MCP Plugin

The Praxys MCP plugin (`plugins/praxys/mcp-server/server.py`) provides 12 tools for Claude Code and Copilot CLI. It operates in two modes:

**Remote mode** (`PRAXYS_URL` env var set):
- All tool calls proxy to the deployed API via HTTP
- JWT token read from `~/.trainsight/token`
- Used by end users connecting to the cloud deployment

**Local mode** (`PRAXYS_URL` not set):
- Direct Python imports from the project codebase
- Uses the first active user in the local database (or `PRAXYS_USER_ID` override)
- `get_dashboard_data()` called directly, no HTTP overhead
- Used during development

**Tools:**

| Tool | Description |
|------|-------------|
| `get_daily_brief` | Today's training signal, recovery, upcoming workouts |
| `get_training_review` | Zone distribution, fitness/fatigue, diagnosis, suggestions |
| `get_race_forecast` | Race prediction, CP trend, goal feasibility |
| `get_training_context` | Full context for AI plan generation |
| `get_settings` | Current user settings and display config |
| `update_settings` | Update training base, thresholds, zones, goal |
| `get_connections` | Connected platforms and their status |
| `connect_platform` | Store encrypted credentials for a platform |
| `disconnect_platform` | Remove platform credentials |
| `push_training_plan` | Upload AI-generated plan as CSV |
| `trigger_sync` | Trigger data sync from connected platforms |
| `get_sync_status` | Check sync status for all platforms |

## Module Responsibilities

### db/

Database layer:
- **`models.py`**: 9 SQLAlchemy ORM models (see Database Layer section above)
- **`session.py`**: Engine initialization, `init_db()` with auto-migration, `get_db()`/`get_async_db()` FastAPI dependencies
- **`crypto.py`**: `CredentialVault` class — envelope encryption with Azure Key Vault or local Fernet fallback
- **`sync_writer.py`**: Upsert helpers for writing sync data (activities, splits, recovery, fitness, plans)
- **`csv_import.py`**: One-time migration from flat CSVs to database
- **`sync_scheduler.py`**: Optional background sync scheduler (per-user, periodic)

### sync/

Each sync script (`garmin_sync.py`, `stryd_sync.py`, `oura_sync.py`) is self-contained:
- Authenticates with the platform API
- Fetches new data since last sync (or from `--from-date`)
- Normalizes to the model schema
- Writes to the database via `db/sync_writer.py`

`sync_all.py` orchestrates all three with error isolation per source.

### analysis/

- **`config.py`**: `UserConfig` dataclass, `load_config()`/`save_config()` (file), `load_config_from_db()`/`save_config_to_db()` (DB), platform capabilities, zone defaults
- **`data_loader.py`**: `load_data()` returns a dict of DataFrames: `activities`, `splits`, `recovery`, `fitness`, `plan`
- **`metrics.py`**: ~40 pure functions covering RSS, TRIMP, EWMA, TSB, predictions, diagnosis, recovery analysis
- **`zones.py`**: Computes zone ranges from threshold + boundary fractions
- **`science.py`**: Loads YAML theories, merges with label sets, provides `load_active_science()`
- **`evidence_registry.py`**: Validates evidence reviews, SDRs, citations, claims, parameter provenance, and supersession
- **`training_base.py`**: Display config per training base (labels, units, abbreviations)
- **`providers/`**: Platform-specific adapters for threshold detection and plan loading

### api/

- **`main.py`**: FastAPI app, lifespan (init_db, optional sync scheduler), CORS (local dev only), route registration
- **`auth.py`**: JWT validation middleware — `get_current_user_id()` extracts user ID from Bearer token
- **`users.py`**: FastAPI-Users integration — auth backend, user manager, transport configuration
- **`deps.py`**: The big orchestrator. `get_dashboard_data()` loads everything, computes everything, returns a dict consumed by all routes.
- **`ai.py`**: `build_training_context()` serializes dashboard data into LLM-optimized JSON. `validate_plan()` checks generated plans.
- **`routes/`**: Each route file is a thin wrapper extracting relevant keys from `get_dashboard_data()`. Includes `register.py` (custom registration with invitation codes) and `admin.py` (user/invitation management).

### web/

React SPA (Vite + TypeScript + Tailwind v4 + shadcn/ui):
- **`pages/`**: 4 pages matching dashboard tabs (Today, Training, Goal, Settings) + Science
- **`components/`**: UI components, one per card/section
- **`hooks/`**: `useApi<T>` for data fetching with loading/error states
- **`types/api.ts`**: TypeScript interfaces matching API response shapes
- **`lib/chart-theme.ts`**: Single source of truth for chart colors

### plugins/praxys/

MCP plugin for Claude Code and Copilot CLI:
- **`mcp-server/server.py`**: 12 tools with dual-mode execution (see MCP Plugin section)
- **`mcp-server/auth.py`**: Token management helpers for remote mode

### .claude/skills/

8 skill directories, each with a `SKILL.md` (instructions for AI tools). Skills that need data have corresponding Python CLI tools in the top-level `scripts/` directory that output JSON to stdout.

## Data Flow Examples

### "What should I do today?"

```
GET /api/today (with Bearer token)
  → get_current_user_id() → JWT validation → user_id
  → get_dashboard_data(user_id, db)
    → load_data() → query activities + recovery + plan from DB
    → _resolve_thresholds() → auto-detect CP from fitness_data
    → load_active_science() → get recovery theory params
    → analyze_recovery() → HRV status (Kiviniemi/Plews)
    → daily_training_signal() → Go/Modify/Rest
  → extract signal + recovery + upcoming + last activity
  → JSON response
```

### "Diagnose my training"

```
GET /api/training (with Bearer token)
  → get_current_user_id() → JWT validation → user_id
  → get_dashboard_data(user_id, db)
    → load_data() → activities + splits from DB
    → diagnose_training(merged, splits, cp_trend, ...)
      → volume analysis (weekly km, trend)
      → consistency check (gaps, session count)
      → interval intensity (split-level, supra-CP sessions)
      → zone distribution (actual vs target from theory)
      → _add_diagnosis_items() → findings + suggestions
  → JSON response
```
