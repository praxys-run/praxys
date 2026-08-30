# PR #745 native-read claim ownership decision

- **Date:** 2026-08-31
- **Status:** proposed; no implementation, migration, or deployment authority
- **Evidence baseline:** `984c8c084080f089686c51e455bb4d6db80b15f2`
- **Decision owner/proposer:** Architecture
- **Contributors:** Trust
- **Repository executors:** Engineering and Operations
- **Independent verifier:** Quality
- **Human authority:** authenticated repository maintainer
- **Classification digest:**
  `sha256:e3c17d24f3e95a7629a8a86d7454e1cd2e5dbf94b32011c6beaa596408de3ac9`
- **Route digest:**
  `sha256:d44577261f0413c0df43f34a13d18e4f84a9fd1c7aea6cdb9ab089724fd9b132`
- **Routing:** Delivery primary loop, Runtime nested loop;
  Architecture and Trust contributors; Engineering and Operations executors;
  Quality verifier; human review required and currently blocked.

## Decision requested

Authorize a narrow ownership identity for the existing native one-read claim.
The current JSON request/response schema is 1 and the current SQLite ledger
schema is 2. A claim changes shared state from `completion_notified` to
`read_claimed`, but that state alone cannot prove whether an ambiguous commit
belongs to caller A or a concurrent caller B. State-only reconciliation is
therefore prohibited.

The proposed correction binds each successful claim to one caller-obtained,
opaque `read_claim_id`. The same invocation identity and claim ID is one
logical operation and may be acknowledged idempotently. A different claim ID
for an already claimed invocation, or reuse of one claim ID for another
invocation, fails closed without mutation.

## Scope and review horizon

This decision affects the invocation-control JSON contract, the shared SQLite
ledger, cooperative callers of `native_read` and `native_observation`,
migration and rollback procedures, tests, and release evidence. It remains in
force until the native-invocation lifecycle or ledger is replaced.

It does not authorize a new service or datastore, caller authentication,
multiple reads, claim transfer, polling, native-runtime interception,
enforcement or autonomy expansion, retained-ledger migration, destructive
reset, deployment, or merge.

## Ownership identity

Extend the existing repository identity convention with kind `read_claim`:

```text
rcl_[0-9a-f]{32}
```

The 32 hexadecimal characters encode 128 bits from an operating-system CSPRNG.
The caller obtains the ID before its first claim request, retains it for that
logical operation, and reuses it for every retry and observation. The existing
`new_identity` command may generate it using `kind: "read_claim"`. It is not
derived from an attempt, native alias, public agent ID, timestamp, process, or
user data.

The ID is scoped proof of claim ownership, not caller authentication or
independent authorization. Existing validation of `attempt_id`,
`native_alias`, and `public_agent_id` remains mandatory. If the caller loses
the ID or cannot determine whether it already performed the native read, it
fails closed. No new caller-side persistence layer is authorized.

The raw ID is accepted only on the request boundary. The ledger stores:

```text
sha256:<SHA-256("praxys/read-claim/v1\0" || canonical ASCII read_claim_id)>
```

The domain-separated fingerprint is sensitive operational metadata but cannot
be presented in place of the raw claim ID.

## Versioned machine contract

If accepted:

1. Advance the global JSON request/response schema from 1 to 2.
2. Advance the SQLite ledger schema from 2 to 3.
3. Keep policy version `agent-invocation-control-v1`.
4. Keep the stable ledger path
   `<git-common-dir>/praxys/agent-invocation-control-v1.sqlite3`.
5. Preserve every command's semantics except:
   - `new_identity` accepts `kind: "read_claim"`;
   - `native_read` requires `read_claim_id`; and
   - `native_observation` requires the same `read_claim_id`.

The changed requests are exactly the existing requests with the required
field added:

```json
{
  "schema_version": 2,
  "command": "native_read",
  "attempt_id": "att_<32 lowercase hex>",
  "native_alias": "nat_<32 lowercase hex>",
  "public_agent_id": "<validated native task-result ID>",
  "read_claim_id": "rcl_<32 lowercase hex>"
}
```

```json
{
  "schema_version": 2,
  "command": "native_observation",
  "attempt_id": "att_<32 lowercase hex>",
  "native_alias": "nat_<32 lowercase hex>",
  "public_agent_id": "<validated native task-result ID>",
  "read_claim_id": "rcl_<32 lowercase hex>",
  "observation": "found | not_found",
  "terminal_fingerprint": null
}
```

The existing rule remains: `terminal_fingerprint` is null for `found` and a
valid fingerprint for `not_found`. Exact-key validation remains mandatory.
All successful and error responses use JSON schema 2. JSON-schema-1 requests
are refused, not upgraded. Old binaries must refuse ledger schema 3.

## SQLite target and invariants

Add exactly one nullable column to `native_invocations`:

```sql
read_claim_fingerprint TEXT
```

and exactly one partial unique index:

```sql
CREATE UNIQUE INDEX native_invocations_read_claim_fingerprint_uq
ON native_invocations(read_claim_fingerprint)
WHERE read_claim_fingerprint IS NOT NULL;
```

Canonical schema validation must require the column and exact index. Logical
validation must enforce:

1. Every new transition into `read_claimed` writes a valid, non-null
   `read_claim_fingerprint` in the same transaction.
2. Every row currently in `read_claimed` has a non-null claim fingerprint.
3. A non-null claim fingerprint is globally unique among retained native rows.
4. Once assigned, a claim fingerprint never changes or clears while the row
   exists, including after observation, invalidation, attempt terminalization,
   or recovery.
5. Only `completion_notified` with a null claim fingerprint may acquire one
   and transition to `read_claimed`.
6. `active`, `notifications_unavailable`, and `completion_notified` require a
   null claim fingerprint.
7. `read_claimed` requires a non-null claim fingerprint.
8. `found` and `lost` may be null only for migrated history; every new
   schema-3 observation that creates either state requires a non-null claim
   fingerprint.
9. `orphaned`, `aborted`, `shutdown`, `failed`, `recovered`, and `succeeded`
   may be null when terminalization occurred before a claim, or non-null when
   terminalization occurred after a claim.
10. A null `found`, `lost`, or terminal row cannot be reopened or assigned a
   claim fingerprint. Because the single column cannot prove whether a null
   terminal row came from migration or pre-claim schema-3 terminalization,
   this is a migration and transition invariant rather than a claim of
   recoverable at-rest provenance.
11. No migration source may contain `lifecycle_status = 'read_claimed'`,
   because its owner cannot be reconstructed.

## Claim, observation, and reconciliation

The claim runs under `BEGIN IMMEDIATE` and verifies the exact existing
`(attempt_id, native_alias, public_agent_id)` binding before applying:

| Durable state | Stored fingerprint | Presented claim | Result |
|---|---|---|---|
| `completion_notified` | null | canonical `T` | atomically set `read_claimed`, fingerprint of `T`, and claim time; commit; authorize |
| `read_claimed` | fingerprint of `T` | `T` | no mutation; return the same authorization acknowledgement |
| `read_claimed` | fingerprint of `T1` | `T2` | fail closed |
| another row owns fingerprint of `T` | any | `T` | fail closed |
| pre-notification, invalidated, post-observation, or terminal | any | any | preserve the existing refusal; do not authorize another read |

The mediator validates the raw ID, computes the domain-separated fingerprint,
and uses constant-time comparison for application-level equality. The initial
update uses both the expected state and null fingerprint in its predicate. A
zero-row update is resolved by rereading under the same transaction; state
without an exact fingerprint match is never ownership evidence.

If commit outcome is ambiguous, the mediator may open one fresh transaction
and rerun the same claim algorithm with the same token:

- if the first commit succeeded and the binding remains valid in
  `read_claimed`, exact token match returns the original authorization;
- if it rolled back, the retry may perform the transition;
- if another token won, the retry fails closed; and
- if invalidation, observation, or terminalization won after the commit, that
  later durable refusal takes precedence; and
- if state remains unavailable or ambiguous, no authorization is inferred.

If a successful response is lost, the caller resubmits the same request and
token. It must never generate a replacement token merely because a response
was lost. A repeated acknowledgement represents the same logical read and
does not authorize executing the native read twice.

`native_observation` requires state `read_claimed` and exact token match before
applying the existing `found` or `not_found` transition. The token remains
stored. Observation remains a one-shot operation: after its state transition,
the same or a different token does not authorize another observation. An
ambiguous observation commit therefore fails closed; this single-column
decision does not promise replay of the original result or
`orphaned_attempt_ids`. Token mismatch cannot create loss, replacement
eligibility, recovery evidence, or a terminal transition.

Existing invalidation and terminal rules remain authoritative and never clear
or transfer a stored claim fingerprint. Invalidation may still close a
binding, but it does not make the claim ID reusable.

## Migration and compatibility

Migration occurs only through explicit, same-path, transactional `init`.
Operations must stop and fence old clients, drain in-flight tokenless native
requests, take the established consistent backup, and revalidate the source
under the migration write lock.

Accepted sources are:

1. the exact valid ledger-v2 target defined by the predecessor ADR; and
2. the exact recognized version-1 source layouts defined by that ADR.

A recognized version-1 source migrates directly to version 3 in one
transaction: apply the predecessor's exact v1-to-v2 schema/backfill rules, add
the claim column and index, validate the combined target, then set metadata to
3. No intermediate version-2 state is committed. A valid version-2 source
receives only the claim delta. Unknown, partial, non-WAL, ambiguous, or
otherwise invalid sources remain refused.

Before mutation, the locked source must contain no native row in
`read_claimed`. Existing rows receive null claim fingerprints. Active,
`notifications_unavailable`, and `completion_notified` rows may continue under
version 3; historical and terminal null rows remain closed. Complete ledger
quiescence or fabricated backfill is not required.

There is no mixed-version operation, optional-token compatibility, dual write,
online migration, or automatic migration by ordinary commands.

## Rollback

Failure before commit restores the source's transaction-owned logical state.
An ambiguous migration commit is resolved by taking a fresh lock and
validating the actual ledger version and target layout.

Before any schema-3 operation mutates the ledger, a quiesced rollback may
restore the complete verified source backup and matching old binary. After
any schema-3 claim or later mutation, in-place downgrade is prohibited because
schema 2 cannot preserve claim ownership. Safe feature rollback keeps ledger
3, disables new native claims, preserves claim fingerprints, and corrects
forward.
Restoring a stale backup or deleting the column requires separate human
incident authority and an explicit assessment of discarded ledger and native
effects.

## Alternatives

- **State-only reread:** rejected because it cannot identify the winning
  caller.
- **Process-local or server-generated-after-receipt token:** rejected because
  response loss leaves the caller without durable operation identity.
- **Optional token under JSON schema 1:** rejected because old callers could
  bypass ownership and the version would misstate a breaking contract.
- **Deterministic token from the native tuple:** rejected because competing
  callers would share it.
- **Reset `read_claimed` to `completion_notified`:** rejected because it may
  authorize a second read.
- **Separate table, ledger, service, or caller datastore:** rejected as
  unnecessary split ownership for a one-to-one binding.
- **Require every active attempt to finish before migration:** rejected as
  unnecessary; only ownerless `read_claimed` rows block safe migration.
- **Abandon retry after ambiguous commit:** safe but rejected because the
  bounded token design provides deterministic recovery without polling or a
  new service.

## Implementation and verification gates

After exact human acceptance, Engineering may implement only this bounded
change. Trust must separately approve token generation, comparison, storage,
redaction, replay, and authorization boundaries. Operations must provide the
quiescence, migration, backup, monitoring, and rollback record. Quality must
independently verify at least:

- canonical identity generation, deterministic domain-separated fingerprint
  vectors, malformed-token refusal, and absence of raw token persistence;
- same-token idempotency without a second native read;
- different-token same-row and same-token cross-row races;
- commit-then-raise, rollback-then-raise, and lost-response retries;
- one-shot observation and exact token/fingerprint matching, including
  fail-closed ambiguous observation commit behavior;
- fingerprint immutability across invalidation and every terminal path;
- direct recognized-v1-to-v3 and v2-to-v3 migration;
- active, notifications-unavailable, completion-notified, and historical rows;
- refusal to migrate any ownerless `read_claimed` row;
- JSON 1/2 and ledger 1/2/3 compatibility boundaries;
- exact schema, rollback, unchanged policy behavior, and old-client refusal.

The final exact tree also requires independent code review, Quality PASS, UTC
preflight, required GitHub checks, and a separate release or retained-ledger
migration disposition.

## Narrow supersession

The immutable predecessor remains authoritative except for the exact
ownerless native-read transition, JSON schema declaration, ledger target
version, and migration composition changed here. This record does not modify
the predecessor file or its digest. Any additional field, table, state,
identifier, public reason code, service boundary, or native authority requires
new review.

## Human disposition

Choose exactly one; no choice is selected by this proposed record:

- **Approve** the bounded caller-obtained `read_claim_id`, JSON schema 2, and
  ledger schema 3 correction for repository implementation only.
- **Return for revision** with the exact unresolved section and constraint.
- **Reject** the correction, retain ledger schema 2, prohibit state-only
  reconciliation, and keep the affected native-read path disabled until a
  different design is approved.
