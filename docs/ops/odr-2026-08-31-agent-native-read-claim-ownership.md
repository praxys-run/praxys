# ODR-2026-08-31-agent-native-read-claim-ownership

- **Date:** 2026-08-31
- **Status:** proposed; no implementation, migration, reset, deployment, or
  release authority
- **Owner:** Operations
- **Evidence baseline:** `984c8c084080f089686c51e455bb4d6db80b15f2`
- **Classification digest:**
  `sha256:e3c17d24f3e95a7629a8a86d7454e1cd2e5dbf94b32011c6beaa596408de3ac9`
- **Route digest:**
  `sha256:d44577261f0413c0df43f34a13d18e4f84a9fd1c7aea6cdb9ab089724fd9b132`
- **Architecture input:**
  `docs/dev/adr-2026-08-31-agent-native-read-claim-ownership.md`, SHA-256
  `a78541c75bad209abff2bbcce99ce5599d8b142d04f4b0c50cd1dd86559d8fd9`
- **Trust input:**
  `docs/ops/tdr-2026-08-31-agent-native-read-claim-ownership.md`, SHA-256
  `ad464cbd41f8375ce684f80bb35117c6ddf98783d2ee4d7817f23a4693844847`
- **Predecessor ledger-v2 ADR SHA-256:**
  `5bd8d04069ef3cca0043087cd53e12d6e72de9847cf9431394e85690b6094875`
- **Predecessor Operations record:**
  `docs/ops/odr-2026-08-30-agent-invocation-ledger-v2.md`
- **Human authority:** authenticated repository maintainer
- **Independent verification:** Quality, Trust implementation review, and
  independent code review

Any digest mismatch voids this proposal.

## Decision requested

Define the runtime boundary for advancing global JSON schema 1 to 2 and the
same-path SQLite ledger from schema 2 to 3 while retaining policy
`agent-invocation-control-v1` and:

```text
<git-common-dir>/praxys/agent-invocation-control-v1.sqlite3
```

Ledger 3 adds only nullable
`native_invocations.read_claim_fingerprint` and its exact partial unique index.
Migration is explicit, offline, transactional, and limited to exact recognized
v1 or v2 sources. No mixed versions, optional-token period, dual writing,
ordinary-command migration, or online migration is permitted.

This record may support repository implementation only after exact human
acceptance. A retained-ledger migration, restore, reset, deployment, or release
requires a separate authenticated authorization bound to the final executable
artifact and privacy-safe preflight.

## Sources of truth and blockers

1. The digest-bound Architecture record governs schema, lifecycle, ownership,
   and migration invariants.
2. The digest-bound Trust record governs token handling, redaction,
   permissions, disclosure response, and authorization boundaries.
3. The immutable ledger-v2 ADR and existing ledger-v2 ODR govern recognized
   v1 layouts and their exact v1-to-v2 backfill.
4. The final reviewed commit/tree and repository workflow identify executable
   behavior.
5. Locked inspection of metadata, canonical SQLite objects, integrity, journal
   mode, and logical invariants identifies actual ledger state. The filename
   does not identify layout version.

Architecture and Trust remain proposed. No authenticated disposition, final
implementation, Quality PASS, release evidence, or retained-ledger migration
authority exists. An ownerless `read_claimed` row is an additional hard
migration blocker and may not be reset or backfilled.

## Prerequisites and quiescence

Before retained-ledger preflight or explicit init:

1. Bind the action to the exact reviewed commit/tree, decision digests, policy
   file, and approved repository workflow.
2. Stop new dispatches and event producers. Fence automatic restarts and every
   invocation-control process in linked worktrees sharing the Git common
   directory.
3. Confirm no old client retains an open ledger connection.
   `BEGIN IMMEDIATE` does not fence a pre-opened process, another clone,
   machine, or native task.
4. Drain, complete, or explicitly refuse queued and in-flight
   JSON-schema-1/tokenless native-read, observation, init, and ledger-write
   events using the matching source artifact. Do not replay them blindly after
   cutover.
5. Confirm no process can enqueue another old-format event. Active native work
   need not finish, but its pending old-client ledger writes must be resolved.
6. Record privacy-safe pre-state: exact artifact, recognized source class,
   ledger/policy version, WAL and integrity results, canonical-layout result,
   kill-switch posture, aggregate lifecycle and native-binding counts,
   database/WAL sizes, free space, process/connection inventory, and queue
   drain result. Record no row contents, identifiers, tokens, fingerprints,
   prompts, native results, personal data, or free-form stack traces.
7. Take and verify a SQLite-consistent backup after quiescence. Treat the
   database, `-wal`, and `-shm` companions as one stopped set when archiving
   files; never copy only the main file. Encrypt copied backup material,
   restrict it to the owning principal and designated Operations identities,
   preserve owner-only permissions where supported, and record a restricted
   backup identifier, hashes, method, time, size, restore check, and retention
   disposition.
8. Use observed ledger/WAL size and a rehearsal to establish same-filesystem
   headroom and maintenance-window limits. Capacity must cover source, backup,
   temporary database where applicable, index construction, and worst observed
   WAL growth plus an explicit margin.

Quiescence does not require an empty ledger. `active`,
`notifications_unavailable`, `completion_notified`, observed, and terminal
rows may remain.

## Explicit init and migration

For an existing path, the exact schema-3 artifact must:

1. Establish only connection-local safety settings before locking; make no
   persistent database, journal-mode, or filesystem mutation.
2. Acquire `BEGIN IMMEDIATE` before inspecting journal mode, metadata, schema
   objects, columns, constraints, indexes, rows, or migration state.
3. Under that lock, validate the exact source. Existing sources must already
   use WAL. Unknown, partial, non-WAL, ambiguous, unsupported, or noncanonical
   layouts fail closed without repair.
4. Refuse migration if any source row has
   `lifecycle_status = 'read_claimed'`. Preserve the source and emit only a
   redacted reason category.
5. For an exact recognized v1 source, perform the predecessor's complete
   v1-to-v2 schema and deterministic backfill, then add the schema-3 claim
   fingerprint column and exact partial unique index in the same transaction.
   No intermediate schema-2 state may commit.
6. For an exact valid v2 source, apply only the claim column and index delta.
7. Initialize existing rows with null claim fingerprints. Preserve all rows
   and state. Null `found`, `lost`, and terminal history remains closed; no row
   may be reopened or assigned fabricated ownership.
8. Validate the physical schema-3 target, index SQL, policy v1, logical
   nullability and immutability rules, aggregate preservation, and integrity
   before committing metadata version 3.
9. Serialize concurrent initializers. A follower locks, rereads committed
   state, and validates exact schema 3 as a no-op.

A fresh ledger is built and validated as a complete schema-3 WAL database at a
same-directory temporary path, checkpointed, given restrictive permissions,
and published atomically with the established no-overwrite hard-link
procedure. A publication loser removes only its unpublished files, reopens the
winner, and validates schema 3. The stable path never exposes an empty
placeholder.

## Ownerless `read_claimed` recovery

Do not migrate, clear the state, assign a token, fabricate a fingerprint, or
return it to `completion_notified`. Keep clients fenced and classify the
condition.

If operationally safe and separately authorized, the matching source artifact
may be restored solely to finish or terminalize the already-claimed operation
under its existing rules, without reopening read authority. Quiesce again,
take a new backup, and repeat locked preflight. If the row cannot be resolved
without guessing, keep the path disabled and request a new Architecture,
Trust, Operations, and human decision.

## Commit ambiguity, validation, and cutover

A pre-commit failure rolls back transaction-owned logical changes. Keep
clients stopped, preserve redacted failure evidence, and independently verify
the exact source layout, metadata, rows, indexes, and integrity before retry or
source-code resumption.

For an ambiguous migration commit, open a fresh connection, take a fresh
`BEGIN IMMEDIATE`, and validate:

- exact schema 3 means migration committed;
- the exact original source means it did not commit; or
- any other state is an incident requiring continued fencing and recovery
  review.

After a confirmed commit, keep producers fenced and verify integrity, WAL,
metadata and policy versions, canonical column/index definitions, logical
invariants, preserved aggregate counts and kill-switch posture, permissions,
second-init no-op behavior, and backup readability.

Prove that JSON-schema-1 requests are refused and immutable old clients freshly
opening ledger 3 report it unsupported. This does not establish safety for a
client opened before migration; process fencing remains mandatory.

Start only the exact JSON-schema-2/ledger-schema-3 mediator in
maintenance/no-dispatch posture, verify health, then enable one controlled
producer cohort. Observe bounded signals before enabling remaining linked
worktrees and normal dispatch. Never admit an old queued event or old binary.

## Rollback and recovery

### Before any ordinary schema-3 mutation

If schema 3 committed but no ordinary schema-3 operation has mutated ledger
state, keep all clients quiesced. Under separate execution authorization,
restore the complete verified source backup and matching old artifact as one
database/WAL/SHM set, restore approved permissions and kill-switch posture, and
validate canonical source state before dispatch. Never mix companions from
different snapshots.

### After any schema-3 mutation

In-place downgrade and ordinary restoration of the pre-migration backup are
prohibited because schema 2 cannot preserve claim ownership or later effects.
Disable new native claims, retain ledger 3 and all fingerprints, fence
incompatible clients, preserve a restricted consistent evidence set, and
correct forward.

Deleting the column, clearing fingerprints, restoring stale state, or
resetting/removing the database and companions requires separate authenticated
incident authority plus an assessment of discarded attempts, claims,
observations, descendants, replacement eligibility, native work, and
kill-switch consequences. A reset starts a new control epoch and does not
cancel native work.

## Monitoring, incidents, and cost

Use redacted bounded counters and structured reason categories for init outcome
and duration, lock wait, quiescence duration, schema/version refusal, malformed
or tokenless input, repeat acknowledgement, same-row mismatch, cross-row
uniqueness conflict, ambiguous commit retry, ownerless migration row,
schema/index/invariant drift, old-client attempt, and ledger/WAL/backup
permission drift. Never record tokens, fingerprints, tuple identifiers, native
results, or personal content.

Treat suspected duplicate or unauthorized read, ownership corruption, usable
token disclosure, or integrity loss as the highest applicable incident
severity. Treat blocked migration, mixed-version attempts, or schema drift
without demonstrated authority breach as availability/control incidents.
Initial mitigation is to disable new claims and fence clients.

This local control does not justify a new always-on service or high-cardinality
telemetry. Prefer per-run evidence, aggregate counters, rate-limited logs, and
existing monitoring. Alert only on actionable invariant, compatibility,
permission, or sustained-refusal conditions; establish thresholds from
rehearsal and observed baseline.

## Release evidence and gates

Release Evidence for the exact artifact must include:

- final commit, tree, script blob/digest, policy digest, decision digests, and
  workflow identity;
- human repository-implementation disposition and, separately, any future
  retained-ledger migration/deployment authorization;
- schema/index fixtures; direct v1-to-v3 and v2-to-v3 tests; fresh
  publication; concurrent init; injected failures; ambiguous commits;
  ownerless-row refusal; state preservation; permissions; backup/restore
  rehearsal; and old-client refusal;
- Trust implementation PASS, independent Quality PASS, independent code
  review, full UTC preflight, and required GitHub checks on the final head; and
- privacy-safe pre/post versions, integrity/invariant results, aggregate
  reconciliation, kill-switch posture, queue/process fencing, timings,
  capacity observations, backup identifier, cutover cohorts, monitoring
  results, and rollback boundary.

Confirm no unexpected application database, secret, Azure resource,
alert/action group, service, deployment workflow, native-runtime, or dependency
change. Any such change requires its own review and same-change Operations
documentation.

Repository acceptance, if granted, authorizes only bounded implementation and
documentation. It does not authorize merge with failed checks, retained-ledger
init, reset, restore, production deployment, release, or workflow bypass.

## Human disposition

Choose exactly one; no choice is selected here:

- **Approve** the bounded claim-ID/fingerprint, JSON schema 2, and ledger
  schema 3 correction for repository implementation only.
- **Return for revision** with the exact unresolved Operations constraint.
- **Reject** the design, retain ledger schema 2, prohibit state-only
  reconciliation, and keep the affected native-read path disabled.
