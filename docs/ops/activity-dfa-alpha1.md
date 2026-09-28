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
subsequently governed files. Editing a shared governed file, even for another
feature, requires separately reviewed renewal before acceptance. This first
capability does not implement renewal or revocation automation. Unrelated paths
remain ordinary maintenance. Preserve the reviewed inactive PR839 build as the
migration-compatible rollback option; never delete approval history.

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

Rollback is time-bounded: rerun original successful backend main/push run
`36367840399` at source `9e7034442ec1a027ee5f6d2ca56ede0c2b85e5d2` while GitHub's
30-day/50-attempt eligibility remains (deadline `2026-10-28T01:55:43Z`). The old
workflow rebuilds source; it has no retained byte-identical package or target-ref
input. Original run configuration-sync and telemetry steps were skipped; ordinary
feedback quiesce/restore remains. Before activation, Operations reconfirms
eligibility and Quality verifies the old migration-compatible build against
synthetic retained DFA state, including inactive policy and rights/erasure paths.
No live rollback is claimed. The old readiness response does not contain
`dfa_policy`; use its exact SHA, readiness and independent inactive-policy proof.
