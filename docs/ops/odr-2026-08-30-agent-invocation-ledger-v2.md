# ODR-2026-08-30-agent-invocation-ledger-v2

- **Status:** **ACCEPTED FOR REPOSITORY IMPLEMENTATION — NO MIGRATION OR RESET AUTHORITY**
- **Decision date:** 2026-08-30
- **Artifact implementation status:** repository-native Markdown; release
  evidence pending the final corrected commit
- **Owner role:** Operations
- **Production authority:** None. This record does not authorize running init
  against a retained ledger, deleting ledger state, releasing, merging with
  failed checks, or bypassing branch protection.

## Decision record

- **id:** `ODR-2026-08-30-agent-invocation-ledger-v2`
- **schema_version:** `1`
- **decision_type:** `operations-decision-record`
- **owner_role:** `Operations`
- **question:** How must Praxys coordinate, evidence, recover, and roll back the
  same-path ledger-v1 to ledger-v2 correction without claiming online
  mixed-version safety or silently abandoning invocation-control state?
- **recommendation:** Permit the bounded repository implementation. Require
  explicit quiesced initialization, exact source-layout recognition,
  transaction-owned rollback before commit, and separately authorized
  destructive reset after a successful migration.
- **decision artifact SHA-256:**
  `5bd8d04069ef3cca0043087cd53e12d6e72de9847cf9431394e85690b6094875`
- **review route:** `human-review-required`; a separate Architecture review
  returned PASS and the authenticated maintainer approved the exact artifact.
- **outcome plan:** Operations records privacy-safe migration and rollback
  evidence; Meta/Eval observes false-corruption, duration, fan-out relevance,
  incidents, and review effort.

## Work Contract

- classification digest:
  `sha256:b61f63ea33961a3bcc25c29d784e6f561182d5dde55e7de1ae57290e46a9ed7b`
- route digest:
  `sha256:154558e84addacee607eea915bcc9eac23e899292061bbf36d675b7eddfda086`
- primary loop: `meta-eval`
- nested loops: `delivery`, `runtime`
- contributors: Architecture
- executors: Engineering, Operations
- verifier: independent Quality

## Source of truth

1. The accepted Architecture addendum in
   [`../dev/adr-2026-08-20-agent-invocation-control.md`](../dev/adr-2026-08-20-agent-invocation-control.md)
   governs the same-path ledger schema 2 boundary.
2. This record governs quiescence, operational evidence, failure handling, and
   reset-based code rollback.
3. The exact corrected commit/tree and Release Evidence identify executable
   behavior.
4. `metadata.schema_version`, canonical schema validation, SQLite integrity,
   and the checked-in policy identify actual ledger state. The stable
   `agent-invocation-control-v1.sqlite3` filename is not a layout-version
   signal.

## Prerequisites

Before running explicit init against a retained ledger:

- bind the action to an exact reviewed commit/tree;
- stop and fence every invocation-control client in all linked worktrees that
  share the Git common directory;
- stop new cooperative dispatches and confirm no old client retains an open
  ledger connection;
- record privacy-safe pre-state: recognized layout, ledger version, integrity,
  kill-switch state, and aggregate active-attempt/native-binding counts;
- determine how any still-running native work will be reconciled after v2
  starts; and
- confirm that a lifecycle-v1 source has no `native_invocations` rows. That
  legacy layout lacks public-ID fingerprints, so v2 cannot construct verified
  provenance without fabrication;
- if an archive is required, capture a SQLite-consistent database/WAL/SHM set
  after quiescence rather than copying only the main file.

`BEGIN IMMEDIATE` serializes SQLite writers. It cannot fence an already-open v1
process, another clone, another machine, or native work.

## Migration procedure

1. Keep ordinary clients stopped.
2. Run the exact corrected artifact's explicit JSON-schema-v1 `init`.
3. The client must acquire `BEGIN IMMEDIATE` before reading journal mode,
   metadata, schema objects, or migration state.
4. Accept only the exact released base-v1, lifecycle-v1, or complete
   physical-v1 layout. The existing database must already use WAL. A
   lifecycle-v1 source with native rows is unsupported; full-v1 requires one
   matching provenance row per native invocation and an exact valid
   dispatch-mode/provenance pair.
5. Apply target DDL, deterministic dispatch backfill, metadata version 2, and
   final validation in one transaction.
6. A concurrent initializer waits, takes the lock, re-reads committed state,
   and validates v2 as a no-op.
7. Start only v2-capable ordinary clients after success. A freshly opened
   released-v1 client must report `StateUnsupported`.

Ordinary commands never migrate, repair, or downgrade a ledger.
Fresh initialization checkpoints a complete same-directory temporary WAL
database and publishes it atomically with a no-overwrite hard link, so the
stable path is never an observable empty placeholder.

## Verify

Release Evidence must bind the exact implementation commit/tree, this record,
the Architecture addendum, both Work Contract digests, and the human-approved
decision-artifact hash. Record:

- pre/post schema version, canonical layout, integrity, kill-switch state, and
  reconciled aggregate counts;
- explicit-init result and second-init idempotence;
- all three source-layout fixtures, unknown/partial-layout refusal, failure
  rollback, and concurrent-initializer results;
- immutable released-v1 fresh-open `StateUnsupported` evidence;
- lock wait, write-transaction duration, total init duration, and quiescence
  duration; and
- exact independent Quality, code-review, preflight, and required-check
  results.

Do not publish ledger rows, raw public agent IDs, prompts, source, user data,
local absolute paths, stack traces, or free-form diagnostic content.

## Rollback / Recovery

### Failure before commit

Keep all clients stopped. Preserve the structured failure and privacy-safe
observations. Verify that user-defined schema objects, indexes, metadata, and
row data remain the pre-migration logical v1 state. WAL bookkeeping need not be
byte-identical. Do not retry, repair, or delete until the failure is
classified. Resume old code only after independent v1-state verification.

If commit outcome is ambiguous, take a fresh write lock and validate actual
state before retrying or recovering.

### Code rollback after successful migration

There is no in-place downgrade. A return to v1-only code is a destructive
state reset and requires authenticated human authorization at execution time:

1. stop and fence all linked-worktree clients;
2. finish or explicitly terminalize mediated work where possible;
3. record active-attempt, descendant, replacement, native-binding, progress,
   and kill-switch consequences;
4. optionally retain a SQLite-consistent evidence archive;
5. remove the database and both companions as one stopped set:
   `agent-invocation-control-v1.sqlite3`,
   `agent-invocation-control-v1.sqlite3-wal`, and
   `agent-invocation-control-v1.sqlite3-shm`;
6. restore the exact approved v1-only artifact and run its explicit init; and
7. deliberately restore the intended kill-switch posture before dispatch.

The reset abandons the control epoch. It does not cancel native work, which may
continue untracked.

## Release criteria

- the bounded Architecture decision and this Operations record are present;
- Engineering's corrected exact tree passes independent Quality and code
  review;
- focused migration tests, full UTC preflight, and required GitHub checks pass;
- no application database, service, deployment workflow, secret, alert, Azure
  resource, or native-runtime change appears in the corrective delta; and
- retained-ledger migration remains a separate, explicitly authorized
  operation.

## Related

- [Digest-bound ledger-v2 corrective decision](../dev/adr-2026-08-30-agent-invocation-ledger-v2.md)
- [Agent invocation-control developer protocol](../dev/agent-invocation-control.md)
- [Architecture decision record](../dev/adr-2026-08-20-agent-invocation-control.md)
- [Change-loop runbook](./change-loop.md)
- [Meta/Eval report](../dev/evaluation-report-2026-08-20-agent-invocation-control.md)
