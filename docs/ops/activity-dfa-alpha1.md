# Activity DFA V2 operations

**Summary:** Keep V2 inactive by default, pin the Linux supervisor, and require physical exit before reuse.

**Use when:** Preparing reviewed inactive source, diagnosing origin/queue/retirement state, or restoring synthetic/authorized data.

## Prerequisites

Actual designated V2 remains accepted/inactive and historical V1 remains terminally
stopped. Gate ON, a supervisor setting, a nonce and source maintenance are not
activation or host-handover authority. Fresh independent implementation/source
review, current CI and separate Operations rollout remain required.

## Steps

The repository startup command is `python -m api.runtime_startup`; this task does
not change live App Service settings. `PRAXYS_DFA_SUPERVISOR_ENABLED` defaults
false and API workers never execute DFA. The optional supervisor candidate must
match the durable control row and observed instance, slot, source SHA, boot and
PID/mount namespaces. Missing or changed identity stays disabled; no first-start
self-election or heartbeat takeover exists.

Manual and automatic have independent immutable grants/results. An explicit
current processing receipt is required, and automatic additionally requires an
exact account-sync action, current account generation, a newly successful daily
archive-unit receipt, current metadata predicate and server gate. Date backfill,
partial sync, reparse, report view/focus/poll never creates automatic computation.
Source/gate/rights are rechecked before result hydration and publication.

A private local runtime directory under `/tmp` has mode0700. Its supervisor lock
is not inherited, its recovery mutex is distinct, and its physical guard is
inherited by controlled children. An existing private recovery-only incarnation receipt, written after durable
host validation, permits exact old-group retirement before cold DB/SDK startup
and before physical-lock acquisition. It never permits launch or host election.
Missing receipt with an actor or ambiguous launch intent remains blocked. TERM grace is500ms, followed by KILL/reaping and group
absence observation; a lease, signal delivery or leader exit is not exit proof.
Unexpected members, identity reuse or unacknowledged launch remain blocked.

Control validation starts no more than8 times/s (125ms minimum interval); its aggregate completion budget is250ms.
Local automatic permission expires after750ms without
a completed valid renewal. Current control readiness, generation, drain and queue
reservation gate durable manual admission. The retirement reactor is independent
of DB/auth/gate/loading/serialization I/O. Physical exit commits through dedicated
control before owner cleanup. Admission-to-exit/availability and manual process
start are separate observations. A post-acceptance capacity failure remains a miss.

The control pool has two connections/zero overflow,100ms checkout,200ms statement
and lock bounds, and1s driver connect timeout. Token acquisition/cold connections
may exceed the healthy envelope; permission expiry remains local. Supervisor work
pools are explicitly1/zero-overflow; its unused async engine is still counted.
One API worker at existing defaults configures20 potential connections, supervisor
work/async/control4, coordinator0 steady-state after disposal:24 total potential
connections. Coordinator migration/drain pools are transient and must also be
counted during startup/shutdown. This is accounting, not demonstrated live capacity.

Children have explicit credential-free environment allowlists and private bounded
pipes. The supervisor alone publishes; actor/token/epoch/generation/input and
nested result schemas/size are checked. Same-container processes share an OS/cloud
identity; environment filtering does not establish separate managed-identity isolation.

## Verify

Use synthetic data only. Retain failed admissions and interrupted runs. The first
capacity test and its rerun rejected manual admission with503; their original logs
are preserved. A later100-trial post-handshake ignored-TERM synthetic cell passed
with observed durable admission/retirement, independently from real raw-reference
and both-origin numerical tests. It does not prove maximum-input/native-compute,
loading/IPC, Azure contention, a60-minute soak or host handover. Final exact-head
preflight, fresh specialist/Quality review and both rendered clients remain required.

## Rollback / Recovery

The workflow installs the coordinator startup command but permits inactive source
and an unset/false candidate setting only; enabled/active deployment is blocked
before its first mutation. This does not authorize a live startup change.

Before any recycling settings/deploy/rollback action, durably drain both origins,
fence publication and prove the old registered group/environment exited. Keep
replacement compute disabled until separately authorized incarnation handover.
Use `python -m api.dfa_drain` only inside the separately authorized exact bound
environment. It commits admission/publication closure before observing the matching
local and SQL idle receipt and actual group absence. Timeout retains closure and
is not exit evidence. Environment handover remains separately authorized.
Never unlink held locks, erase actor metadata with a run/user, or restore an older
unsafe per-API-worker dispatcher. The additive migration retains historical data
without granting V2 authority; destructive downgrade requires independent drain.

Independent private negative authority uses Blob ETag CAS or fsynced local files,
separate from SQL. Never replace it with an old SQL backup or restore an archive
whose recoverable horizon outlives its current negative history. Pending cleanup
never expires; active-owner high-watermarks and deleted-incarnation fences remain
until every recoverable copy/execution reference is retired.

Before reopening a restored API, run `python -m api.dfa_restore` in the separately
authorized restore procedure: disable/drain, advance epoch, replay unconditional
account deletion, discard restored DFA grants/proofs/results/receipts and clear
restored sync-authority generations. Original activities remain. Restore creates
neither a grant nor a successful-sync event. Missing authority with retained grants
fails closed. Fresh owner actions must establish new independent authority.

## Related

- [Implementation](../dev/pr871-original-runtime.md)
- [Impact map](../dev/pr871-original-implementation-impact.md)
- [Backup and restore](backup-and-restore.md)

<details><summary>Historical V1 runbook and prior staging proposals (not current runtime authority)</summary>

# Activity DFA α1 operations

**Summary:** Operate bounded post-run DFA jobs and preserve owner erasure across restores.

**Use when:** Reviewing scientific activation, diagnosing queue failures, or restoring DFA data.

## Prerequisites

This feature consumes the private original FIT archive described in
[Connect IQ archives](connectiq-archives.md). It makes no provider requests and
does not require a live provider connection. Premerge evidence on 2026-09-28:
PR #839 was draft at `5b8148a93a1def57589d7a38ee3e8ac8f889c509`, with the
science contract draft/inactive. Merging uses the existing main-triggered backend
and Azure web workflows, the Labs workflow (deployment conditional on its existing
enable variable), and the miniapp robot5 development upload. That upload is not
WeChat review submission or public release. EdgeOne native Git deployment is
separate from Azure web deployment. Ordinary rollout does not activate science:
`require_policy()` continues to reject computation until the existing signed
scientific approval workflow is complete.

## Steps

### Activation and rollback

PostgreSQL startup applies the additive `b4d5f6a70819` Alembic migration under
the existing advisory lock; SQLite startup creates the three new tables. Generation of a draft science contract does not authorize
processing. `sdr-activity-dfa-alpha1-v1` must pass the existing evidence/decision/
implementation approval workflow and become active. The executor also verifies
model version and the complete parameter-map fingerprint. No feature flag,
service, credential or environment setting is added. Roll back application code
using the ordinary deployment workflow. A rollback build must retain revision
`b4d5f6a70819` in its Alembic revision graph, as well as the additive tables,
original FIT archives and deletion manifests. A build that cannot resolve the
already-applied revision is not a valid rollback artifact.

### Dispatcher and resource bounds

Each API worker has one dedicated execution thread and a lightweight coordinator
waking on explicit POST or every5s. SQL allows one valid global execution lease,
180s renewed every15s, one queued/running task per owner and20globally. A failed
worker's expired lease recovers once. A stale physical thread may continue until
the next cooperative check, but generation+lease fencing prevents publication.
Closing a client does not cancel; explicit rights cancellation does.

Hard bounds: FIT64MiB,250000frames,200000RR positions,48h elapsed,8MiB output,
120s cooperative work deadline,30s SQL statement/lock timeout. Failure is explicit;
no truncated results. Output reservation8MiB counts against256MiB per-owner cache
quota. Old completed caches may be evicted, never active work, proof or originals.
Cleanup is hourly and before admission: prepare/unavailable24h, failed/cancelled7d,
complete at most30d from completion. Reads never extend retention.

## Rollback / Recovery

Payload-free manifests use the existing private Blob container or local DATA_DIR
fallback, prefix `activity-dfa-deletions` / directory
`activity_dfa_deletion_manifests`. They contain operation ID, owner/target references,
reason and requested/completed timestamps; no RR, alpha values or sensor identifiers.
Persist requested before SQL erase; completed only after commit. Pending manifests
never expire; completed manifests remain14d from completion to cover backups.
Never restore SQL without the current manifest store. Every DFA read/compute/export
preflight replays that owner's active manifests before returning data or admitting
work. Dispatcher reconciliation is asynchronous and advances a cursor through at
most 20 stored manifests per tick, counting expired records toward the same bound.
Startup and public readiness do not prove global DFA erasure replay has finished. Unavailable or
invalid storage closes DFA reads/admission and complete export, while cancellation
and deletion remain available. Cancellation always returns metadata only, including
for completed runs. Deletion can proceed without successful replay/listing when a
new request can be persisted; if durable request storage is unavailable, it fails
without erasing SQL. Repeated deletion reuses a covering retained target request;
newly created work requires a new cutoff. Nonexistent targets do not create new
manifests. Absence of derived SQL rows never discards a pending durable request. Do not manually discard pending manifests to restore
service. Restore storage access, let reconciliation retry, then verify exact owner
deletion before resuming. No new monitoring alert is created by this change.

Reparse invalidates generations and source proof before active parse replacement.
Revocation/deletion clears dependent caches and the execution slot. Account erasure
stages owner-wide manifests before deactivation/row deletion. Never recreate missing
runs when recovering worker output; publish is conditional UPDATE only.

Inspect aggregate task state, failure reason, elapsed execution and recoveries in
SQL and application logs. Logs must exclude athlete identities, RR, alpha values,
device identifiers and raw metadata. Diagnose `source_unsupported`, `rr_missing`,
`timer_invalid` as input eligibility, not service outages; `DFA_RESTORE_REPLAY_UNAVAILABLE`
requires private-storage recovery. `DFA_SCIENCE_POLICY_INACTIVE` is an activation
boundary; do not bypass it with a test override or undocumented switch.

## Verify

Use synthetic fixtures only in committed tests/screenshots. Targeted backend tests:
`python3 -m pytest tests/test_activity_dfa.py tests/test_garmin_connectiq.py tests/test_data_export.py`.
`DFA_TEST_DATABASE_URL` is a test-harness-only optional URL for an isolated migrated
PostgreSQL database; it is not runtime configuration. Production credentials must
never be used for these tests. The PostgreSQL test creates/deletes only its uniquely
named synthetic owners. Web build, miniapp typecheck/i18n, actual rendered checks
and independent Science/Trust/Quality review precede release.

## Related

- [Connect IQ archives](connectiq-archives.md)
- [Backup and restore](backup-and-restore.md)
- [DFA implementation contract](../dev/activity-dfa-alpha1-implementation.md)

## Implementation-bound activation staging

The capability PR leaves the DFA Evidence Review and decision draft/inactive.
After this mechanism is protected-merged to trusted main, a separate activation
PR freezes a preapproval revision and projected accepted/active contract. The
trusted-main `Validate frozen science activation` workflow runs synthetic checks
without production credentials and a separate collector publishes immutable
validation evidence. Fresh independent reviews and exact source-backed human
role statements precede deterministic lifecycle materialization. Never interpret
an inactive decision/contract digest as the final active digest.

PR #853's authenticated comment `5924024414`, materialized head
`092ec3b43c197f8fcab93ffd0d299adbadac0df0`, validation and implementation
envelope remain historical and PR/base/head-bound. Its post-materialization CI run
`36809913896` exposed deterministic lifecycle-test assumptions, not a runtime
guard failure. PR #868 repaired only `tests/test_activity_dfa.py` and
`tests/test_health_ready.py`, then squash-merged as
`ac1bfd37cd1c79064b3920bee33c689f106f1c58`. A replacement activation candidate
must start from that exact main and obtain a new trusted validation, envelope and
exact source-backed human package. Nothing from the old activation attempt is
transferable authority.

The ledger and required selective-review verifier authenticate GitHub identity,
current repository permission, PR/base/head, validation workflow revision and
attempt, artifact identity and digest. The final activation tree must exactly
replay from the approved preapproval tree; generated directories are not broad
exclusions. `config/science-implementation-coverage.json` explicitly lists
subsequently governed files. The 34-file current-main review is recorded in
[DFA activation current-main drift impact](../dev/dfa-activation/current-main-drift-impact-20260930.md).
Editing a shared governed file, even for another
feature, is blocked while active. The terminal stop-only source change must land
first; later maintenance requires fresh review and isolated actual-guard denial
evidence. This capability does not implement subject renewal. Unrelated paths
remain ordinary maintenance. Preserve the reviewed inactive PR839 source
`9e7034442ec1a027ee5f6d2ca56ede0c2b85e5d2` as the default
migration-compatible rollback candidate. Retain the newer
`8dcd9b4f2905e29376f9e17126ca3bd2b6720342` source only as the separately
authorized configuration-reconciling alternative described below, and never delete
approval history.

After deployment restores the feedback-publication value selected by the workflow,
deployment observes
`/api/health/ready` `dfa_policy` and `/api/version` source SHA for at most 20
minutes. `dfa_policy` contains exactly `policy_active` and `contract_digest`;
actual `require_policy()` success returns true and its digest, otherwise false
and null. The endpoint is no-store and does not query DFA owner data or compute.
The existing readiness database and shared-authority checks still apply. Missing,
malformed or mismatched metadata fails this observation without restarting or
undoing feedback-publication restoration. An ordinary activation-only push changes
no deployment/configuration path, selects `sync_config=false`, captures the current
feedback-publication value and restores it. With the current production value
`false`, this can validly deploy DFA while preserving `false`; it neither proves an
outage nor authorizes changing that setting. Retain source SHA, state, contract
digest, observation time and workflow URL only. This is a sampled acceptance
check, not proof of all instances, user processing or global erasure replay.

Miniapp robot5 upload previously failed at 2207 KB above its 2 MB limit (the
preexisting baseline was 2134 KB). Packaging repair and manual upload are separate
work. Physical Skyline, gesture, screen-reader and larger-text evidence gaps
remain disclosed; simulator evidence does not close them.

Rollback is time-bounded. The default route reruns successful backend main/push run
`36367840399`, deploy job `108757706180`, attempt 1, at source
`9e7034442ec1a027ee5f6d2ca56ede0c2b85e5d2` while GitHub's 30-day/50-attempt
eligibility remains (deadline `2026-10-28T01:55:43Z`). The workflow rebuilds the
pinned source; it has no retained byte-identical package or target-ref input. The
original run used `sync_config=false`: settings synchronization and telemetry
cutover were skipped, while state capture, quiescence, deployment and restoration
succeeded. A rerun therefore captures and restores the current feedback-publication
value, preserving the current `false` value rather than reconciling it to a
repository variable.

The old readiness response has no `dfa_policy` field. Bind verification to the
exact source SHA plus readiness/database observations and the existing exact-source
synthetic PostgreSQL startup/state/rights and real inactive-guard evidence recorded
in `docs/ops/incidents/ir-dfa-readiness-recovery-20260928.md` lines 56–60. That
incident record also preserves the historical no-blind-rollback boundary. No fresh
exact-`9e703444` test receipt was produced by this correction. Immediately before
use, Operations must recheck run retention, attempt eligibility, deployment/Labs
queue state, dependencies, identity and migration compatibility. This makes the
preserve-`false` route the viable default; it is not a fresh Quality
recertification, retained-package claim or live rollback rehearsal.

The newer source `8dcd9b4f2905e29376f9e17126ca3bd2b6720342`, backend run
`36445536979`, attempt 1, remains eligible only until
`2026-10-28T15:41:49Z`. That push used `sync_config=true`; settings synchronization
and telemetry cutover ran. A rerun would select the current configured repository
intent `PRAXYS_ENABLE_FEEDBACK_PUBLICATION=true` and may mutate current production
`false` to `true`. Use it only with explicit separate authority for that
reconciliation or a separately validated preserve-`false` route. Its historical
success does not prove an outage or authorize a settings change. Fresh Quality
byte-identity evidence for this source is limited to the migration, DFA, rights and
dependency surfaces actually compared. The task-local comparison archive is
`/tmp/praxys-dfa-activation-20260930.E4E4cL/quality-rollback-8dcd.6TEkta/source.tar`,
SHA256 `348559b39acbdd11c45c2c050787fa620f9fafb7db9ff28925281ac11889b93c`;
that provenance does not transfer to `9e703444`, attest to deployed package bytes
or runtime settings, or constitute a live rollback rehearsal.

## Supported terminal STOP and later maintenance

A STOP requires a separate, explicit human statement for the exact repository,
subject, active contract and implementation envelope. Never infer it from an
outage or agent recommendation. Use a clean trusted-current-main checkout to run
`scripts/materialize_science_stop.py` and an isolated candidate branch at the
same current main revision. `--output /tmp/dfa-stop-statement.md` prepares only
the canonical statement. After the human explicitly makes that assertion, the
agent transcribes it to the **original bound activation PR**. The tool prints its
PR number. It does not create a comment or assert consent itself.

Then run the same trusted tool with `--comment-id ID` instead of `--output`.
It re-fetches that immutable GitHub comment identity, body, repository, linked
target and current human permission before writing only:

- `data/science/stops/<subject>.yaml`;
- `data/science/generated/implementation-stops/<subject>.md`.

Commit exactly that diff on the isolated branch, push it, and open an ordinary
protected stop-only PR with the existing maintainer identity. No new App grant,
secret, setting or automated PR-creation permission is needed. The existing
trusted source verifier independently re-fetches the source even when the comment
is on the already merged activation PR. Any simultaneous implementation, workflow,
science activation or historical-artifact change is rejected.

The merged stop means **source-recorded**. Deploy that stopped source through the
ordinary workflow, restore feedback publication, then observe exact stopped SHA,
application readiness and false/null DFA policy metadata. The observation helper
loads the signed terminal state, so a historically active contract does not make
it expect true after STOP. Its small source-policy dependencies install only after
feedback restoration. No athlete data is read for this observation.

The current guard denies new computation and final publication. Existing workers
notice at their next cooperative check; source commit, deployed stop and drained
workers are distinct milestones. Retained proof, rights export, cancellation,
delete and restore-manifest replay remain available. Never claim instant or global
cessation from one metadata sample.

Only a STOP already in **trusted base** unlocks a later maintenance PR. Run the
trusted-main `Validate frozen science activation` workflow with
`purpose=stopped-maintenance`, the exact candidate SHA/PR/subject and historical
active contract digest. Its authoritative probe executes the actual DFA guard
and requires denial on a fresh hosted runner with pinned checkouts and trusted
dependencies. It shares no regression workspace, environment, cache or artifact.
A third trusted collector binds current base/head, stop, workflow revision and
run/attempt, requiring both regression and probe success; source admission also
requires both jobs and the collector. The probe controller requires a complete
strict child observation of the actual caught STOP status/detail, not process exit
success alone. The controller never imports candidate code; its bounded child
uses candidate dependencies and an explicit environment without credentials,
Python loader overrides or GitHub command-file variables. Timeout, excessive or
missing output, nonzero exit and mismatched observations fail. No child artifacts
reach the collector. This is a completed validated observation, not proof against
arbitrary candidate code forging stdout; specialist source review remains needed.
The privileged verifier consumes authenticated artifact evidence without executing
candidate code. Missing, stale, failed, skipped or substituted evidence blocks maintenance.
Fresh specialist review and ordinary protected checks remain required. This path
permits future separately reviewed maintenance of the verifier itself without
retaining the obsolete active implementation freeze. It does not authorize
renewal or revival of the stopped subject.

Whole shared files such as `api/main.py`, `api/deps.py`, requirements, client API
types, global EN/zh catalogs and package locks are guarded while active, even for
otherwise unrelated edits within a file. Subsequent maintenance checks protect
enumerated source files only. Changes elsewhere in the application can affect DFA
behavior, including through imports or shared process state. Such changes require
ordinary impact review and renewed specialist review when they affect the
approved implementation; the file guard does not determine semantic independence.

After STOP, roll back only to a committed stopped release or the independently
verified inactive PR839 fallback within its documented rerun eligibility. Never
rerun an older active artifact for this subject. Coordinate queued deployments.
An old active binary cannot discover a later repository stop by itself, and source
terminality does not technically prevent all privileged historical deployments.
Treat an older active deployment as a stop breach and restore a stopped/inactive
release. No live STOP or rollback is claimed by this capability PR.

Example operator commands (substitute the clean current-main and isolated branch
paths; these preparation commands do not constitute human approval):

```bash
python /trusted-main/scripts/materialize_science_stop.py \
  --candidate /isolated-stop-branch --repository praxys-run/praxys \
  --output /tmp/dfa-stop-statement.md
# After the explicit human assertion is transcribed to the original activation PR:
python /trusted-main/scripts/materialize_science_stop.py \
  --candidate /isolated-stop-branch --repository praxys-run/praxys \
  --comment-id EXACT_SOURCE_COMMENT_ID
```

Both checkouts must still be clean at the exact current main revision when
materialization begins. Commit only the printed two paths and use ordinary
`git push` / `gh pr create`; no workflow is granted automatic stop-PR creation.
The comment fetch uses the existing authenticated read capability and checks
current write/maintain/admin permission. The historical activation validation
artifact need not remain downloadable to honor a later explicit STOP.

## PR842 readiness incident and bounded recovery

The [open Incident Record](incidents/ir-dfa-readiness-recovery-20260928.md) retains
the failed `bafd1714` rollout and interrupted feedback restoration. Root cause and
production recovery are not yet established. A local strict-parser speedup is not
proof of the production cause. No DFA activation is part of this repair.

First allow the ordinary automatic deployment of the reviewed correction. The
following is an **Operations-only, one-use incident procedure**, permitted only
if that automatic run fails terminally **before package/App Service deployment**,
all deployment/Labs queues are terminal, `/api/version.source_sha` is still exactly
`bafd1714df108747758bd58273578be3613b7bd0`, and configured/original feedback-positive
intent remains exactly true. Do not use it after an automatic success.

```sh
gh workflow run deploy-backend.yml --repo praxys-run/praxys --ref main \
  -f sync_config=true -f run_tests=false -f recover_dfa_cutover_842=true
```

Record the created dispatch run ID in the Operations incident/release receipt.
Failure or ambiguous completion consumes the one-use authority; do not rerun or
create another dispatch. This is an authorization/receipt boundary, not technical
prevention of every privileged distinct dispatch. The workflow rejects attempts
other than 1 and requires the exact event/ref/config/intent/serving-source guards
before quiescence mutation.

Only predeployment quiescence gets the bounded transport window: connect 5s,
request maximum 210s, at most 2 sequential complete attempts with a single 5s gap,
inside a 9-minute step deadline. Every existing actual-readiness, false
positive-enable, boolean kill-switch and false effective-publication predicate
remains required. No nested retries or liveness substitution. Default/push
transport and all post-repair 8-second gates stay unchanged.

The normal repaired-source cutover must pass before the existing restoration of
verified configured/original positive intent true, respecting the negative kill
switch. Then verify no-store actual DFA false/null and the repair source SHA.
Do not force feedback settings, bypass readiness, blindly rerun old PR839, or
claim recovery from source merge alone. Preserve all original FIT/deletion state
and the existing finite rollback limitations.

## Readiness timing and restoration deadline follow-up

PR845's repair source `00577ce859ff90bbdf50a90e8ba00c4822243ec4` reached normal
cutover, but incident dispatch `36414310829` timed out during restoration. The
PR842 recovery allowance is consumed and cannot be repeated. The incident remains
open. A later 18.257-second diagnostic ready response with feedback enabled and
DFA false/null does not meet the normal eight-second release gate.

Readiness stage timing now distinguishes dispatch wait, database acquisition and
queries, cleanup, controls and real DFA policy work. Use the bounded signal in
[Monitoring & alerts](monitoring-and-alerts.md); plan CPU alone does not establish
which process or stage is responsible. Public readiness shape and no-store remain
unchanged, and no scientific guard is cached or bypassed.

The restoration controller has a 360-second work deadline, at most 105 seconds
for cleanup, and an absolute 465-second finish target inside the unchanged
480-second step. Every command, parsing and output operation consumes the budget.
The controller and command process groups have independent watchdogs. Transport
must succeed before JSON can satisfy a predicate. A failed/timed-out Azure write
can still complete remotely, so later matching samples cannot erase unresolved
write ambiguity. Cleanup writes positive=false at most once and never changes
the kill switch. Its observations are `verified_disabled`, `control_plane_only`
or `unknown`; only the first proves all current configuration/runtime/source
predicates with no ambiguous write. None turns the failed restoration into a
successful deployment. Failed-step summary values are unknown, not cutover
fallbacks. Runner loss/SIGKILL or missing/failed output leaves unknown state.

The distinct default-false `recover_readiness_timing_00577` option is preparation
for separately reviewed diagnostic delivery, not a latency remedy or an issued
dispatch allowance. It rejects simultaneous use with the consumed PR842 option.
Before any mutation it checks exact serving 00577, main workflow_dispatch attempt 1,
sync_config=true, configured positive=true, authenticated automatic-producer
original intent=true and current captured/fresh positive=false.
Its predeployment-only transport is two complete 210s requests with one 5s gap
inside 9min; all postdeployment probes retain 8s. First allow ordinary automatic
deployment. Only a final reviewed delivery decision may permit one distinct
receipted dispatch after terminal PRE-package automatic failure and clear queues.
Failure or ambiguity consumes it; no rerun or redispatch. Quiescence may interrupt
the currently sampled restored feedback. Single use is enforced by Operations
receipts/authority, not a cross-run technical ledger.

The [implementation boundary record](../dev/dfa-readiness-recovery/readiness-timing-deadline-v1.md)
discloses the whole-file coverage consequence for future unrelated telemetry
edits. After activation, changing either newly bound telemetry file requires the
supported terminal STOP before maintenance or another explicitly supported route.

### Cross-run proof relay and the consumed-attempt boundary

The first diagnostic draft's current-original=true gate was unreachable after
ordinary automatic quiescence disabled publication. The corrected producer
publishes `readiness-quiescence-<run>-1`, containing only
`quiescence-proof.json`, after acknowledged disable and false readback. It can be
uploaded even when later readiness fails, but absent/ambiguous proof denies the
option. Do not substitute a manual snapshot or a historical release's archive.

For a separately authorized dispatch, obtain the ORIGINAL nonsecret ZIP under
existing read authority, preserve its bytes/digest, and put canonical base64 in
`quiescence_proof_zip` with numeric `quiescence_producer_run`. Supply input as data
through the structured workflow request; never interpolate it as shell code.
The helper uses public anonymous GitHub metadata only; rate limiting, unavailable
metadata or partial reads deny. No token fallback or new Actions permission exists.
The deploy job retains only its existing contents:read and id-token:write grants.

Admission binds exact protected main/target, repository, PUSH workflow/attempt1,
terminal failure at quiescence, successful immutable proof upload, and skipped
actual post-quiescence configuration/package/deployment steps. Stamp/private-wheel
preparation before quiescence is allowed. Artifact identity, expiry and SHA256 are
verified before bounded one-member JSON parsing, with fresh metadata rechecks.
The consumer checks exact serving00577/configuredtrue/currentfalse before mutation.
Only historical restoration intent is reused; current kill-switch authority and
normal8s runtime acceptance remain unchanged.

A valid receipt is TECHNICALLY REUSABLE across distinct dispatches. It carries no
global one-use enforcement or new24h age rule. Operations owns the one-attempt
boundary: record consumption BEFORE the dispatch attempt, then its immediate
run ID or unresolved identity. Failure/ambiguity consumes it; no second attempt.
Current source preparation is not that final delivery authorization. Preserve
producer/consumer receipts and the older consumed842/error history separately.

## Unsigned activation preparation after accepted recovery

Operations accepted the inactive baseline at source
`8dcd9b4f2905e29376f9e17126ca3bd2b6720342`: automatic backend run
[36445536979](https://github.com/praxys-run/praxys/actions/runs/36445536979)
and Labs run
[36445537386](https://github.com/praxys-run/praxys/actions/runs/36445537386)
completed successfully. The 2026-09-28 16:05:35 UTC sample returned ready in
1.583 seconds, no-store, DFA false/null, feedback publication enabled and current
kill switch false. This is sampled acceptance, not all-worker or erasure proof.
The sealed external [acceptance receipt](/tmp/readiness-pr846-accepted-20260928T160849Z.json)
has SHA256 `0c43e147eaf93bf0f2a485bd01d3fe75f2c3f17d7fe8af996c3837b0d8fad833`;
the external [stage-timing evidence](/tmp/readiness-pr846-stage-metrics-20260928T160423Z.json)
has SHA256 `26a9caade04bc11d0c71604620b0a91152b0d4727a9335aba566ca213bd5d092`.
These are retained local review artifacts, not repository-hosted downloads.
The sampled slow DFA-policy stage remains an unresolved performance finding;
the successful sample does not establish a permanent latency remedy.

PR #868's test-only squash
`ac1bfd37cd1c79064b3920bee33c689f106f1c58` did not deploy the API. Labs run
`36822621006` built and published the exact source tag and `latest` at OCI
digest
`sha256:b3986b3116cd56f01975e74f2356ea4f04093b6caa88513630a61593fa0402a3`,
then deploy job `110241989344` stopped as designed at the API-SHA guard before
Azure login or actions; the existing worker remained unchanged. No backend
deployment ran for the squash. The public `2026-10-01T06:24:24Z` sample still
reported API source `3067bcba6ecd22d29fab612fd58b3960b987c5b2`, ready/database
healthy, unchanged AI and feedback state, and DFA false/null. Miniapp run
`36822620989` performed no upload. Treat this as bounded source/release evidence:
it proves neither byte identity nor the prior `latest` digest or any movement
from it.

At the public `2026-10-01T06:24:24Z` sample, the frozen preapproval state was
unsigned: Evidence Review and SDR were draft, `reviewed_on` was null, and runtime
was inactive. PR #869 later materialized accepted/active source on its unmerged
branch, but never established protected merge, deployment or production activation;
that branch is superseded because its runbook retained the preapproval state as
current after materialization. A successor still requires fresh source approval,
deterministic replay and required checks, protected merge, rollout, and
post-restoration observation before any production activation claim.
Trusted validation must project the accepted/active contract
and observe actual `require_policy()`, model `dfa-alpha1-raw120-v1` and complete
parameter fingerprint
`c9db9df13212d152c5a34ff4ddfb8f08ea5cb32dd98d14207ddbd0ef86386438`.
Existing enablement consent does not invent an unseen exact three-role attestation.
Only after real source-verified approvals, deterministic replay, required checks
and protected merge may rollout establish the exact deployed SHA, normal
eight-second checks, the captured feedback state restored without an activation-
driven settings change, and no-store `policy_active: true` with the exact approved
active contract digest. The ordinary activation-only push uses `sync_config=false`
and may validly activate DFA while preserving the current feedback value `false`.
Retain the existing 20-minute observation bound. No athlete catalog access,
submission or computation is needed; legacy `/api/science` is not an activation
proxy. No recovery dispatch allowance carries into this preparation or release.

Prefer PR839 source `9e7034442ec1a027ee5f6d2ca56ede0c2b85e5d2` and backend run
`36367840399`, deploy job `108757706180`, attempt 1, as the default fallback. Its
30-day rerun deadline is `2026-10-28T01:55:43Z`; `sync_config=false` preserves the
captured current feedback value, and the settings/telemetry steps were skipped in
the original run. Old readiness lacks `dfa_policy`, so require exact SHA and
readiness/database evidence plus the checked-in historical inactive-policy and
rights evidence. No fresh exact-`9e703444` test receipt was produced; recheck
retention, attempt eligibility and deployment/Labs queue state immediately before
use. The alternative `8dcd9b4f2905e29376f9e17126ca3bd2b6720342`
run `36445536979`, attempt 1, remains eligible until
`2026-10-28T15:41:49Z`, but its `sync_config=true` path ran settings/telemetry and
may reconcile current production `false` to configured repository intent `true`;
it requires explicit separate authority or a validated preserve-`false` route.
Fresh Quality byte-identity evidence applies only to that newer source's actually
compared migration/DFA/rights/dependency surfaces and does not transfer to PR839.
Neither route is a retained byte-identical package or live rollback rehearsal.
Existing readiness gates still apply; rollback does not guarantee recovery from
broken readiness.
Preserve Alembic head `b4d5f6a70819`, additive tables, retained FIT, deletion
manifests and owner rights. Retain the older PR839 synthetic PostgreSQL proof
under its original source and scope; do not relabel the newer source comparison as
an exact-PR839 receipt.

Activation protects whole governed shared files: main/deps, requirements, client
API types, global catalogs and package locks, plus telemetry/proof helpers and
their tests. Even unrelated edits inside those files require a separately
authenticated exact human terminal STOP first. Only STOP already in trusted base
unlocks later reviewed maintenance; source recording, deployment and worker
drainage remain distinct. There is no subject revival or renewal. Never deploy an
old active release after STOP. Enumerated file protection is not semantic isolation.

Earlier candidate-linked synthetic EN/zh web desktop/mobile and miniapp light/dark
evidence is source-equivalent carry only because neither PR #868 nor this
preapproval changes client source; it is not a fresh render or deployment result.
Rendered acceptance remains an independent obligation, separate from real guard
evidence. Physical Skyline canvas, gestures, screen readers, larger text, native
focus and contrast gaps remain disclosed. The robot5 package-size failure and
packaging repair/manual upload remain outside this activation work.

## Designated V2 tooling bridge

The [designated bridge](../dev/designated-dfa-v2-tooling.md) changes admission
preparation only. V1 STOP, approvals and generated history remain immutable.
Use the existing trusted `stopped-maintenance` purpose with V1, actual bridge PR,
exact candidate head and V1 contract for bridge admission. The bridge's new V2
protocol cannot certify this admission. Independent review and current gates
remain required; fixture exceptions confer no bridge authority.

The approval-ledger materialization job disables Python bytecode generation at
job scope and uses `python -B` on both source verifiers and the materializer.
Physical bytecode/native-shadow/import-slot guards still reject injected artifacts;
no cache ignore or deletion supplies success. The materializer receives the trusted
base science snapshot for designated decision-only acceptance.

After trusted tooling is admitted, a later separately authorized V2 activation
uses `dfa-v2-activation` and the exact V2 subject/contract. Its three-phase actual
probe must complete on a fresh runner before the separate trusted collector can
produce schema-2 validation. The current shipped guards cannot complete it.
Do not interpret simulated protocol tests, repository STOP presence, or successful
bridge CI as deployment, process drain or V2 activation evidence.

Before V2 activation, roll back bridge source through reviewed stopped-maintenance
while preserving all terminal STOP and historical science bytes/modes. After V2
acceptance/activation, use its own reviewed lifecycle; bridge rollback cannot
implicitly undo V2 or revive V1. Rebind source/base/full diff, current checks and
reviews after every material source revision. Physical drain remains UNKNOWN
until Operations supplies actual completion/retirement evidence.

For staged V2 activation, use the
[immutable assertion linkage](../dev/designated-dfa-v2-staged-assertions.md).
Preserve the inactive assertion, append the fresh digest-qualified active assertion
and derived companion, and require authenticated predecessor/current source
closure plus exact replay. Once linked history exists, rollback must retain a
compatible history-validating reader; do not roll back to a validator that rejects
preserved lineage. A lawful V2 terminal STOP remains an exact authenticated two-file
transaction. Its bound PR may retain historical activation comments, but these
only reauthenticate existing immutable source history and supply no new authority.
New approvals, altered envelope/source, extra files, revival or general stopped-V2
maintenance remain denied. Physical drain remains a separate UNKNOWN obligation.

The approval-ledger automation permits only the designated companion output
namespace in addition to existing Science outputs. Its complete trusted replay
and source verifier determine the exact filename/content; the workflow path
allowlist itself supplies no authority or stale-approval exception.

</details>


Inactive candidate startup keeps ordinary API availability separate from DFA
compute readiness. Missing, malformed or stale candidate observations cannot
start the supervisor. A structurally valid previous-source identity in the same
boot and process/mount namespace may retire its exact locally receipted actor
before database initialization; that retirement receipt grants no launch rights.
Missing or mismatched receipts leave uncertain actors untouched and deny compute.


The synthetic capacity cohort now distinguishes ingress availability from
accepted-request preemption. Every ingress attempt records readiness, before/
after durable admission fields, denial reason and any five-second backoff. Only
an exact capacity refusal with unchanged durable fields can be retried, at most
three attempts per trial, 300 total attempts and 600 seconds overall. Any
post-admission failure remains a failure. Report the denial rate and total elapsed
time alongside 100 accepted preemptions; never label retries as 100/100 ingress
success. Exit/availability uses the conservative before-transaction bracket;
post-Popen/PID process-start observations remain separate. These measurements
cover the documented healthy synthetic cell only, not live capacity or soak.


Accepted preemption evidence also binds a real control-query observation of the
newly committed queued manual admission ID, generation and execution epoch to
the matching occupied automatic actor token. The actual retirement must follow the observed priority-triggered permission
invalidation and start with permission disabled. The separately assigned reason
string can lag that write; it is retained as a diagnostic, not used alone as
proof of the cause. A permission-expiry exit
during the ingress/commit bracket cannot count as accepted preemption. Exit
need not follow response delivery: fast post-commit priority retirement is valid.
The test observer observes the actual priority queries, reads selected metadata
on the reserved control connection, and records actual retirement events; it does not extend the 750ms watchdog or
modify production decisions.


The positive transaction regression synchronizes at a real completed renewal,
then parks only the following control I/O until actual admission commit. The
independent 750ms timer remains live and is never extended; slow admission still
fails the positive case. Benchmark execution does not enable that test
synchronization. A separate regression delays the diagnostic reason assignment
until physical exit to exercise the real invalidation/reason interleaving.

## Admission/control contention observations

Retry authorization remains serialized with owner/source generation changes.
Its response is queued metadata only; superseded result bytes/revision are
cleared. The global control-row admission mutation follows response metadata
preparation and pending writes, immediately before commit. Response delivery
must not hold that transaction while repeating source/storage/authority checks.

The supervisor control pool uses two connections with zero overflow and 100ms
checkout, reserving bounded capacity for renewal and lifecycle acknowledgements.
A cancelled worker acknowledgement can race verified-exit projection: exact
incarnation/epoch/prior-actor CAS prevents it from overwriting an exit receipt
or replacement actor. Pool checkout and command deadlines still apply when
those calls overlap; no extra connection or overflow is introduced. SQLite uses a dedicated bounded
control pool with the existing durable journal/synchronous settings and 100ms
busy timeout. PostgreSQL retains 200ms statement and lock timeouts. This reduces
avoidable pool contention; it does not remove database writer/row-lock
contention. The actual 250ms renewal budget and 750ms independent expiry remain
binding, including when authority/source/storage checks or database I/O stall.

The `15ebd0b` accepted SQLite synthetic cohort failed causal certification;
it cannot be dismissed as an unsupported deployment cell. PostgreSQL production
and SQLite local/test remain supported. Preserve all accepted failures and
refusal rates when measuring a prospective profile. Distinguish authority checks,
completed renewal, durable acceptance, physical exit, durable availability and
post-Popen process start. A timely physical exit alone does not prove that a new
durable manual admission caused retirement. Focused synthetic cells and code
review are not maximum-input, mixed-load/soak, live placement or activation
certification. Native compiler/render verification remains externally blocked.

The aggregate renewal deadline includes completed control commit. If commit
finishes after 250ms, readiness in SQL is insufficient: local permission remains
denied and the previous local expiry is not extended. Diagnose such deadline
or database exceptions separately from observed committed manual priority;
never infer a lock exception from a permission retirement reason alone.

Admission refreshes the actual locked control row even if response metadata
already loaded it. A concurrent drain/epoch/readiness change must not be hidden
by the ORM identity cache. Equal PostgreSQL 200ms statement/lock deadlines may
produce statement cancellation (`57014`) or lock timeout (`55P03`); record the
actual class/code and operation. SQLite lock failure reports BUSY. All remain
fail-closed without extending local permission.

## SQL admission pulse and ACK boundary

A SQL admission pulse ends250ms after the renewal starts. Publishing after that
instant leaves an already-expired pulse; local denial does not depend on a
subsequent cleanup transaction. Readiness publication uses an exact-generation
conditional update and cannot overwrite a concurrently drained/replaced binding.
SQL-visible commit and supervisor-observed ACK differ. Admission checked inside
an eligible pulse stays accepted if its own commit/response crosses expiry or
supervisor ACK later times out. Physical execution requires a completed current
ACK within250ms, and only then extends the separate750ms local permission.
The supported drain/restore/startup-failure operations clear readiness atomically;
no new host election or binding authority is created.

Starts are bounded to at most8/s (125ms minimum start interval), including failed
publication attempts. This prospectively doubles the previous4/s active control
validation rate; include source/rights/Science reads and write contention in
capacity review. Pulse250ms and start125ms do not guarantee continuous eligibility:
processing/commit delays above the overlap or failed renewals cause gaps. Keep
all ingress and refusal rates, admission-check/commit/response brackets, accepted
outcomes and physical exit/durable availability/post-Popen timings. Selecting
only fast readiness windows is not general healthy capacity. Focused25ms SQL
coverage sampling adds up to40 observer reads/s and is an estimate, not a live
availability certificate. No maximum-input/shared-service/soak capacity is proved.

### Cancelled I/O and independent physical retirement

The failed `644b1c4` canonical run is retained:4498 passed,1 failed,53 skipped.
The SQLite capacity cell recorded15 ingress,5 pre-admission refusals,10 durable
acceptances and9 complete outcomes. The tenth remained an accepted failure:
its matching priority invalidation and physical group exit were observed, but
the Python loading/IPC continuation remained alive after the old250ms join.
Its exact blocked stack/resource was not recorded and is unknown. One bounded
12-step diagnostic completed all12; that does not repair the failed certificate.

Physical retirement no longer joins a Python I/O continuation. Before retirement,
a job-local event irrevocably denies later launch; it is never cleared for a new
job. All launches check that event under the physical mutex. Intent writes are
generation/status fenced; actor acknowledgements use exact CAS. Verified group
exit and its durable receipt precede slot reuse. Old private result queues are
discarded; current owner/origin/rights/source checks remain required for any
publication. A late worker owns and closes its own pipe handles, because closing
a buffered reader from the reactor can block on that reader's lock.

There are at most two Python I/O continuations including the active job. With
one cancelled continuation, automatic loading is paused and the remaining slot
is reserved for manual work. At two cancelled continuations no new work starts
and completed renewal denies new readiness; requests already durably accepted
stay accepted. A formerly valid admission pulse can expire naturally while that
denial completes. No250ms SQL/750ms physical bound or125ms cadence changes.

Focused SQLite/PostgreSQL tests deliberately hold a private stdout continuation
after actual pipe EOF, retain every ingress outcome, and require real admitted
manual computation/physical exit before reuse before releasing cleanup. Other
tests delay raw loading and actual actor UPDATE execution, proving cancelled
loads cannot launch/write a newer generation and old acknowledgements cannot
overwrite a replacement. These deterministic delays reproduce a lifecycle
boundary; they do not identify the original644 blocked dependency. Permanent
storage/driver stalls, maximum input and mixed-load/soak capacity remain unproved.
A stuck dependency exhausting both continuation slots requires recovery; do not
claim universal manual availability or increase slots/deadlines to hide it.

The EOF-boundary cell uses one work connection/zero overflow and two control
connections; it observes zero checked-out work connections at the paused pipe
continuation. An indefinitely blocked raw-loading transaction can instead hold
that sole work connection. The extra Python continuation does not create another
DB connection or prove service during such a stall; pool/driver contention and
permanent dependency failure remain explicit recovery/capacity limitations.
Focused regressions passed12 lifecycle cases and59 existing runtime/authority/
readiness cases; the wider bounded combination passed72 with the100-trial case
excluded. This is preparation for independent review, not final canonical proof.

Automatic loading pause includes successful-sync receipt admission/inventory
decoding, not only acquisition of an already queued automatic run. While a
cancelled continuation remains, leave the receipt pending without consuming a
grant or linking a run, and select manual work first. After cleanup pruning
removes that continuation, normal receipt admission resumes. The focused
SQLite/PostgreSQL regression queues another genuine receipt before live startup,
observes actual child payload acknowledgement without parking renewal, and
requires manual completion before releasing EOF cleanup; only then may that
receipt be loaded and associated. Earlier failed focused attempts remain
diagnostics, including an accepted SQLite failure during live receipt creation
and a cancellation before the EOF boundary existed. These tests do not identify
the original644 blocked phase or establish a new capacity certificate.

### Prospective preemption cohort and supplemental service outcomes

The32f canonical run remains failed:4512 passed,1 failed,53 skipped,
90 ingress/23 refusals/67 durable acceptances/66 complete causal steps. Its
last retry followed a real5s pre-admission refusal backoff into an already idle
actor, so the old occupied-only assertion stopped observation of accepted
service. Original permission-loss cause remains unknown. The observed DELETE
journal setting is not a demonstrated cause. Four bounded DELETE/WAL idle and
explicit durable-drain boundary cells completed service without forged renewals;
they are separate from the operational profile and do not repair that certificate.

The prospective test checks exact actor/token/incarnation/epoch/input/generation
and running automatic workload before every ingress, including retries. It
never selects a favourable remaining SQL pulse. Five-second refusal backoff and
three-attempt per-episode bounds remain; the entire setup/live qualification/
API/service observation schedule has300 ingress slots and600s total, with15s
bounded qualification/accepted-service observations. A lack of eligible work or
an exhausted budget reports insufficient coverage.

Thirty-two independently originated synthetic daily completion units are
predeclared before live startup through the real sync writer: distinct activity,
snapshot, parse, job, item and completion identifiers. They are actual newly
completed synthetic units, not historical/backfill synthesis or an adaptive
replacement for an accepted failure. A terminal automatic row is never reset;
no grant or physical permission is forged. This changes the prospective
workload population and incurs receipt inventory overhead; it does not certify
concurrent sync workloads or substitute a retrospective profile.

A test-only request adapter captures the already-read locked control actor and
real commit invocation/ACK bracket, without an extra authority read under the
lock. Every durable acknowledgement (including a post-commit503) is recorded
before classification, and every accepted request receives an actual service
outcome, current authorization check and post-Popen/physical reuse evidence.
Independent committed-priority actor/generation/epoch/admission/sequence proof,
verified group exit and durable availability still govern required preemption.
Fast post-commit retirement before client ACK can qualify only with that actual
committed-priority proof; ACK time is not invented as server commit time.

Certification still requires100 causally proven accepted preemptions with
complete authorized service and physical exit/durable availability within5s,
PLUS separate idle/race acceptances and outcomes.100 mixed successes does not
meet that target. Retirement races do not become idle/preemption successes;
ambiguity remains insufficient evidence. Genuine accepted failures stop
certification after observation and stay retained rather than resampled.
All ingress, refusals, supplemental outcomes, renewal denial/exception classes,
automatic terminal transitions, source hashes and budget elapsed time remain
in the final ledger, including failed or incomplete runs. Runtime125ms cadence,
250ms SQL pulse/ACK budget,750ms local permission and pool2 are unchanged.


Prospective occupied-acceptance classification requires the exact locked actor
(token, full binding, incarnation and state), a real request commit bracket,
and matching verified physical exit plus durable availability. Every occupied
supplemental race also retains these timings and must satisfy the conservative
five-second bound from the pre-ingress observation (earlier than acceptance).
A precommit race is affirmative only when verified exit precedes the observed
SQLAlchemy commit event, which occurs before the DBAPI COMMIT invocation.
Exit before client ACK alone proves neither precommit retirement nor priority.
The event does not identify SQL server commit time. Missing/mismatched evidence,
invalid committed-priority proof, ambiguous ordering or overbudget retirement
blocks certification after retaining actual accepted service. No failed causal
assertion is converted into a permitted race category.
