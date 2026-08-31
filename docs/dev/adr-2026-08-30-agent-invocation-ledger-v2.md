# PR #745 ledger schema v2 corrective decision

- Status: proposed; no implementation or migration authority
- Evidence baseline: `0f8358af44f5f9ba3b0fafcb540c048d7b6e8933`
- Classification digest: `sha256:b61f63ea33961a3bcc25c29d784e6f561182d5dde55e7de1ae57290e46a9ed7b`
- Route digest: `sha256:154558e84addacee607eea915bcc9eac23e899292061bbf36d675b7eddfda086`
- Decision owner/proposer: Architecture
- Independent reviewer: separate Architecture instance
- Repository executor: Engineering
- Runtime/rollback owner: Operations
- Independent verifier: Quality
- Outcome observer: Meta/Eval through the review-authority overlay
- Human authority: authenticated repository maintainer

## Decision requested

Authorize only the ledger-versioning and explicit-migration correction relative
to evidence baseline `0f8358af44f5f9ba3b0fafcb540c048d7b6e8933`.
This decision neither approves nor re-approves lifecycle, native-binding,
progress, autonomy, identifier, or dispatch behavior already present in that
baseline.

The accepted correction would:

1. Keep JSON request/response schema 1 and policy version
   `agent-invocation-control-v1`.
2. Advance only the SQLite ledger layout discriminator from version 1 to
   version 2.
3. Keep the existing stable path
   `<git-common-dir>/praxys/agent-invocation-control-v1.sqlite3`; the filename
   identifies the policy ledger, not its internal SQLite schema.
4. Allow migration only through explicit `init`.
5. For an existing ledger, make no persistent database, journal-mode, or
   filesystem change before acquiring `BEGIN IMMEDIATE`. Connection-local
   safety settings may be established first. After acquiring the lock, re-read
   and validate journal mode, metadata, schema objects, columns, constraints,
   indexes, and migration state. A recognized v1 source must already use WAL;
   migration does not change its journal mode.
6. Recognize only exact valid version-1 source layouts:
   - the released original-v1 base layout;
   - the PR #745 lifecycle-v1 layout without auxiliary tables; and
   - the current full-v1 layout with lifecycle and auxiliary tables.
7. Apply only the target-schema delta and normative dispatch backfill defined
   below, update metadata to ledger schema 2, and validate before committing the
   same transaction.
8. For a failure before successful `COMMIT`, restore transaction-owned logical
   state - user-defined schema objects, indexes, metadata, and row data - to
   the pre-migration state. This is not a byte-for-byte database/WAL/SHM
   guarantee and excludes persistent settings or filesystem effects, which is
   why migration may introduce none before the transaction. A failure reported
   after commit is not a rolled-back migration. An ambiguous commit outcome
   must be resolved by taking a fresh lock and validating state before retry or
   recovery.
9. Require valid ledger schema 2 for every ordinary operation. Ordinary
   commands never migrate or repair a version-1 ledger.
10. Serialize concurrent explicit initializers. The first may migrate; later
    initializers re-read and validate committed version 2 as a no-op.
11. Preserve base rows and control state, including active attempts, ancestry,
    identities, decisions, timestamps, retry/terminal fingerprints, and the
    kill switch. Legacy base attempts must remain visible and terminalizable
    without fabricated lifecycle facts.
12. After quiescence and successful commit, ensure an unmodified client built
    from released commit `c99b3d45b4f15bda9ed8632ca40c78779875e089`,
    freshly opening the same path, reports `StateUnsupported` before its exact
    version-1 layout check. This guarantee does not cover a process that opened
    and validated the ledger before migration.

## Scope and review horizon

- Time horizon: until ledger schema 3, replacement of this ledger, or an
  approved ownership/cutover design.
- Affected systems: the invocation-control script, its policy/configuration,
  tests, developer and Operations documentation, and linked worktrees sharing
  one Git common directory.
- Unaffected systems: the application database, JSON contract schema, policy
  version, native runtime authority, external rediscovery, and autonomous
  migration.
- Mandatory new review: target-layout change; JSON or policy-version change;
  new datastore or path; live mixed-version operation; online migration;
  material migration availability cost; or any migration/reset incident.

## Normative target and source fingerprints

The version-2 target is exactly the full ledger layout present in the immutable
baseline script:

- commit/path:
  `0f8358af44f5f9ba3b0fafcb540c048d7b6e8933:scripts/agent_invocation_control.py`
- Git blob: `a599b99ccec39ce4fed03cbea69b0997944d32a8`
- file SHA-256:
  `fc888a3aa66e26e78bb26bd20bad5eb41ae37c8c7eb6b9e557d686f7f48a64a1`
- canonical definitions: `_SCHEMA`, `_LIFECYCLE_SCHEMA`,
  `_AUXILIARY_SCHEMA`, `_SCHEMA_COLUMNS`, and `_SCHEMA_INDEXES`

The only target-layout difference from those definitions is
`metadata.schema_version = '2'`. No additional user-defined table, index,
column, constraint, trigger, view, identifier format, lifecycle semantic, or
native authority is authorized.

Target user-defined tables:

- Base: `metadata`, `control`, `contracts`, `slots`, `generations`,
  `logical_invocations`, `decisions`, `attempts`.
- Lifecycle: `lifecycle_decisions`, `work_history`, `active_work_keys`,
  `replacement_eligibility`, `native_invocations`, `progress_evidence`.
- Auxiliary: `lifecycle_dispatch`, `native_binding_provenance`.

Target user-defined indexes:

- Base: `attempts_active_contract`, `attempts_active_match`,
  `attempts_parent_status`, `attempts_slot_finished`,
  `decisions_contract_reason`.
- Lifecycle: `work_history_slot_revision`, `work_history_replacement`,
  `native_invocations_attempt`.
- Auxiliary: none.

Target metadata has exactly the keys `schema_version` and `policy_version`,
with values `2` and `agent-invocation-control-v1`. There are no user-defined
triggers or views. SQLite-owned automatic indexes with null SQL definitions are
permitted and are not separate user-defined schema objects.

The three accepted version-1 sources use the same canonical definitions and
metadata policy value, with `metadata.schema_version = '1'`:

1. Base source: only the base tables and base indexes.
2. Lifecycle source: base plus lifecycle tables/indexes, with no auxiliary
   table or object.
3. Full source: the complete target physical layout while metadata still says
   version 1.

Validation must cover ordered columns and canonical constraints as well as
object names. Unknown extra user-defined objects, missing objects, changed
constraints, partial auxiliary state, or conflicting rows are corrupt and must
be refused rather than normalized.

Under the acquired write transaction, the decision tree is:

1. exact valid version 2 -> validate and commit/no-op;
2. one exact recognized version-1 source -> migrate;
3. readable unsupported metadata version -> `StateUnsupported`;
4. unknown or partial schema -> `StateCorrupt`.

No pre-lock observation may select a migration path.

## Normative legacy-data handling

- Base-only attempts receive no synthetic lifecycle, dispatch, progress,
  replacement, native-binding, native-provenance, public-ID, or artifact
  revision facts.
- Existing full-v1 auxiliary rows are preserved and never overwritten.
- Lifecycle-v1 rows lacking `lifecycle_dispatch` receive exactly one row using:
  - `dispatch_mode = sync`;
  - `execution_provenance = sync_inline`;
  - `recorded_at_ms = lifecycle_decisions.decided_at_ms`;
  - `admission_reason = lifecycle_transition_rejected` when
    `effective_transition` is `duplicate_launch` or `illegal_transition`;
  - otherwise `direct_sibling_active` when the lifecycle decision has no
    matching base `decisions` row, `launch_authorized = 0`, and
    `effective_transition` is one of `initial_launch`, `resume`, `replacement`,
    or `review_after_new_digest`;
  - otherwise `policy_denied` when launch authorization is false; and
  - otherwise `admit`.
- A missing or mismatched base decision that is not uniquely explained by the
  durable predicates above and the baseline table relationships is corrupt;
  migration rolls back instead of guessing. Migration does not require the
  formerly conflicting sibling to remain active because that historical state
  is not persisted in `lifecycle_decisions`.
- Terminalizing a legacy base attempt writes only the newly supplied terminal
  status, fingerprint, and time. A missing lifecycle-history row remains valid
  and must not cause failure or synthesize historical lifecycle facts.

## Defects corrected

1. Current PR code inspects optional tables before `BEGIN IMMEDIATE`. Two
   concurrent first initializers can both decide to migrate; after one commits,
   the follower can execute stale DDL and falsely report a valid ledger as
   corrupt.
2. Current PR code adds tables while retaining ledger schema version 1. The
   released exact-set version-1 validator therefore reports the valid expanded
   layout as corrupt even though its metadata claims to be the released format.

## Alternatives

- Selected: same-path ledger schema version 2 with an explicit transactional
  migration.
- Rejected: a sidecar or independent new ledger file, because separate stores
  would permit split-brain attempts, kill-switch state, and recovery history
  without a broader ownership-cutover design.
- Rejected: documentation-only correction while retaining the version-1
  discriminator, because it leaves the machine contract false.
- Deferred: removing the lifecycle additions and restoring the exact released
  layout. This remains the fallback if the requested decision is rejected.

## Compatibility and rollback consequences

Failure before commit restores transaction-owned logical state as defined
above. Successful migration is not backward-readable by the released
version-1 client.

Before explicit migration, all invocation-control clients in every linked
worktree sharing the Git common directory must be stopped and prevented from
restarting. `BEGIN IMMEDIATE` coordinates SQLite writers but cannot fence a
version-1 process that validated the ledger before migration.

After successful migration, a code rollback to a version-1-only client requires
a separately authorized destructive reset:

1. stop and fence all clients across linked worktrees;
2. record active-attempt, native-binding, descendant, replacement, progress,
   and kill-switch consequences;
3. optionally archive a SQLite-consistent evidence set;
4. remove the database, `-wal`, and `-shm` companions as one stopped set;
5. restore the old client and run its explicit version-1 `init`; and
6. deliberately restore the intended kill-switch posture.

That reset abandons invocation-control state and starts a new control epoch.
It does not cancel native work, which may continue untracked. Executing such a
reset requires authenticated human authorization at that future time.

## Implementation and verification gates

Approval of this record authorizes repository implementation and review only.
It does not authorize running migration against any retained user ledger,
deleting a ledger, merging with failed checks, bypassing branch protection, or
changing native/runtime authority.

Before PR #745 may merge:

1. Engineering must implement only the bounded correction above.
2. The ADR, policy/config, developer protocol, Operations handbook, and
   implementation impact map must distinguish JSON schema 1, policy v1, and
   ledger schema 2.
3. Operations documentation must define quiescence, exact-artifact binding,
   privacy-safe pre/post evidence, failed-init recovery, successful-migration
   rollback, and database/WAL/SHM handling.
4. Tests must cover all three recognized source layouts, active legacy-attempt
   preservation and terminalization, concurrent init, idempotent v2 init,
   ordinary-operation refusal of v1, unknown/partial layout refusal, injected
   failure after each transactional phase followed by logical pre/post
   comparison, and released-v1 `StateUnsupported` behavior.
5. Tests must also cover exact source/target schema fingerprints and
   constraints, unknown extra objects, no persistent pre-lock mutation, every
   dispatch-backfill branch including `direct_sibling_active`, preservation of
   exact `decided_at_ms` -> `recorded_at_ms` mapping, classification after the
   formerly active sibling has terminalized, preservation of existing
   auxiliary rows, refusal of conflicting/ambiguous rows, and fresh locked
   validation after an ambiguous commit result.
6. Released-client verification must run the immutable
   `c99b3d45b4f15bda9ed8632ca40c78779875e089` validator artifact, or a
   content-verified equivalent, against committed v2. It must explicitly avoid
   claiming safety for a pre-opened v1 process.
7. Independent Quality must verify the corrected exact tree.
8. An independent code-review specialist must report no blocking finding on
   the complete final diff.
9. The full UTC preflight and required GitHub checks must pass on the final
   head.

## Narrow supersession

The earlier ADR is immutably identified as:

- commit/path:
  `0f8358af44f5f9ba3b0fafcb540c048d7b6e8933:docs/dev/adr-2026-08-20-agent-invocation-control.md`
- Git blob: `a16f1f2b11f668da56a616f5917ebe8580d5a5fd`
- file SHA-256:
  `061d2b8b04418407cf83712d8a9a1a6c324b42bd5c8ce190a9b207f3a1f4aa3d`

That ADR deferred ledger schema v2 because it assumed the additive layout
remained readable as valid v1. The released exact-set validator disproves that
premise. Approval supersedes that deferral only for the ledger-format
discriminator and explicit transactional migration described here.

Context epochs, keyed/native ID formats, generalized alias/rebind design,
external rediscovery, enforcement, native interception, automatic migration by
ordinary operations, and all other deferred mechanisms remain deferred.

## Human disposition

Choose exactly one:

- Approve the bounded same-path ledger schema v2 correction.
- Reject it and remove/defer the incompatible lifecycle layout before merge.
