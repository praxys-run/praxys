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
remain ordinary maintenance. Preserve the verified inactive
`8dcd9b4f2905e29376f9e17126ca3bd2b6720342` build as the preferred
migration-compatible rollback candidate; retain the older PR839 source and its
synthetic proof as historical secondary evidence, and never delete approval history.

After ordinary feedback publication restoration, deployment observes
`/api/health/ready` `dfa_policy` and `/api/version` source SHA for at most 20
minutes. `dfa_policy` contains exactly `policy_active` and `contract_digest`;
actual `require_policy()` success returns true and its digest, otherwise false
and null. The endpoint is no-store and does not query DFA owner data or compute.
The existing readiness database and shared-authority checks still apply. Missing,
malformed or mismatched metadata fails this observation without restarting or
undoing feedback-publication restoration. Retain source SHA, state, contract
digest, observation time and workflow URL only. This is a sampled acceptance
check, not proof of all instances, user processing or global erasure replay.

Miniapp robot5 upload previously failed at 2207 KB above its 2 MB limit (the
preexisting baseline was 2134 KB). Packaging repair and manual upload are separate
work. Physical Skyline, gesture, screen-reader and larger-text evidence gaps
remain disclosed; simulator evidence does not close them.

Rollback is time-bounded: the preferred candidate is a rerun of successful backend
main/push run `36445536979`, attempt 1, at source
`8dcd9b4f2905e29376f9e17126ca3bd2b6720342` while GitHub's 30-day/50-attempt
eligibility remains (deadline `2026-10-28T15:41:49Z`). The workflow rebuilds the
pinned source; it has no retained byte-identical package or target-ref input.
That run used `sync_config=false`; its successful quiesce, restoration and exact
inactive DFA observation do not authorize a future rerun when current/original
feedback-positive intent cannot be independently established. Unresolved feedback
intent is a rollback blocker, not permission to force a setting. Before activation
and again before rollback, Operations must reconfirm retention, attempt limits,
dependencies, identity, feedback intent and migration compatibility. Independent
Quality must verify the rebuilt candidate against isolated synthetic PostgreSQL
with retained representative DFA state, including inactive guard denial and
rights/export/cancellation/deletion/manifest replay. No live rollback is claimed.
The older PR839 source `9e7034442ec1a027ee5f6d2ca56ede0c2b85e5d2`
and its synthetic PostgreSQL proof remain historical secondary evidence only.

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

The activation candidate remains unsigned: Evidence Review and SDR draft,
runtime inactive. Trusted validation must project the accepted/active contract
and observe actual `require_policy()`, model `dfa-alpha1-raw120-v1` and complete
parameter fingerprint
`c9db9df13212d152c5a34ff4ddfb8f08ea5cb32dd98d14207ddbd0ef86386438`.
Existing enablement consent does not invent an unseen exact three-role attestation.
Only after real source-verified approvals, deterministic replay, required checks
and protected merge may rollout establish the exact deployed SHA, normal
eight-second checks, restored feedback subject to the current kill switch, and
no-store `policy_active: true` with the exact approved active contract digest.
Retain the existing 20-minute observation bound. No athlete catalog access,
submission or computation is needed; legacy `/api/science` is not an activation
proxy. No recovery dispatch allowance carries into this preparation or release.

Prefer the verified inactive source above and backend run `36445536979`, attempt 1,
as the fallback candidate, ahead of historical PR839 source
`9e7034442ec1a027ee5f6d2ca56ede0c2b85e5d2`. Its candidate 30-day rerun deadline
is `2026-10-28T15:41:49Z`. Before activation and again before rollback, Operations
must reconfirm retention, attempt limits, dependencies, identity, migration
compatibility and current/original feedback intent. Because the run used
`sync_config=false`, the rerun cannot establish missing intent by itself; unresolved
intent blocks rollback. This rebuild is not a retained byte-identical package or a
live rollback rehearsal. Existing readiness gates still apply; rollback does not
guarantee recovery from broken readiness.
Preserve Alembic head `b4d5f6a70819`, additive tables, retained FIT, deletion
manifests and owner rights. Retain the older PR839 synthetic PostgreSQL proof
under its original source and scope; it does not attest to a new build.

Activation protects whole governed shared files: main/deps, requirements, client
API types, global catalogs and package locks, plus telemetry/proof helpers and
their tests. Even unrelated edits inside those files require a separately
authenticated exact human terminal STOP first. Only STOP already in trusted base
unlocks later reviewed maintenance; source recording, deployment and worker
drainage remain distinct. There is no subject revival or renewal. Never deploy an
old active release after STOP. Enumerated file protection is not semantic isolation.

Candidate-linked synthetic EN/zh web desktop/mobile and miniapp light/dark
rendering remains an independent acceptance obligation, separate from real guard
evidence. Physical Skyline canvas, gestures, screen readers, larger text, native
focus and contrast gaps remain disclosed. The robot5 package-size failure and
packaging repair/manual upload remain outside this activation work.
