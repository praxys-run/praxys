# TDR-2026-08-31-agent-native-read-claim-ownership

- **Date:** 2026-08-31
- **Status:** proposed; Trust recommendation only, with no human approval
- **Trust outcome:** design PASS; recommend bounded repository implementation
  only after authenticated human disposition and final implementation review
- **Architecture artifact:**
  `docs/dev/adr-2026-08-31-agent-native-read-claim-ownership.md`
- **Required Architecture SHA-256:**
  `a78541c75bad209abff2bbcce99ce5599d8b142d04f4b0c50cd1dd86559d8fd9`
- **Evidence baseline:** `984c8c084080f089686c51e455bb4d6db80b15f2`
- **Predecessor ledger-v2 ADR SHA-256:**
  `5bd8d04069ef3cca0043087cd53e12d6e72de9847cf9431394e85690b6094875`
- **Classification digest:**
  `sha256:e3c17d24f3e95a7629a8a86d7454e1cd2e5dbf94b32011c6beaa596408de3ac9`
- **Route digest:**
  `sha256:d44577261f0413c0df43f34a13d18e4f84a9fd1c7aea6cdb9ab089724fd9b132`
- **Owner:** Trust
- **Executors:** Engineering and Operations
- **Independent verification:** Quality, Trust implementation review, and
  independent code review
- **Human authority:** authenticated repository maintainer

Any artifact-digest mismatch voids this review.

## Trust decision

Trust supports a caller-obtained `read_claim_id` to distinguish ownership of
the existing one-read claim after an ambiguous commit. The
server-authoritative mediator remains responsible for schema validation, exact
tuple binding, authorization, lifecycle enforcement, transaction ordering, and
refusal. The token never replaces or weakens checks for
`(attempt_id, native_alias, public_agent_id)`.

The bounded design stores only one nullable `read_claim_fingerprint` and its
partial unique index. It authorizes no service, datastore, caller-side
persistence layer, claim transfer, polling, multiple reads, native-runtime
interception, or broader autonomy.

## Assets, actors, and boundaries

Protected assets are one-read authority, exact native binding, lifecycle and
migration integrity, raw claim tokens, retained fingerprints, the ledger and
WAL/SHM companions, consistent backups, and operational evidence.

Relevant actors are cooperative callers, concurrent or faulty callers, the
mediator, same-principal local processes, Engineering, Operations and backup
identities, authenticated maintainers, and any dependency or telemetry/support
system able to inspect request or ledger material.

Trust boundaries are:

1. caller-controlled request/session context to strict JSON input;
2. validated mediator logic to the SQLite transaction;
3. SQLite to WAL/SHM, filesystem, backup, and restore systems;
4. old and new clients across migration or rollback; and
5. structured runtime events to logs, telemetry, crash, and support channels.

The design does not change athlete-data purposes, consent, disclosure,
feedback-screenshot privacy, encrypted credentials, or per-user provider
isolation. Claim material must not be used for analytics, profiling, or
user-visible attribution.

## Threat model

The controls address concurrent first-claim races, ambiguous commits, lost
responses, replacement-token generation after uncertainty, token theft or
reuse, tuple substitution, confused-deputy calls, malformed or tokenless
requests, presenting a fingerprint as a token, old-client access, downgrade,
database or backup disclosure, and leakage through process arguments, logs,
telemetry, errors, crash artifacts, or support material.

Possession of the raw token plus the exact tuple and existing caller authority
may reproduce the same claim acknowledgement or submit the permitted one-shot
observation. The token is therefore restricted transient control data and
scoped bearer-like ownership proof, but not caller authentication or an
independent credential. A fingerprint disclosure permits retained-ledger
correlation but, given correct entropy, does not feasibly recover the token.
Compromise of the mediator, ledger writer, or same-principal runtime remains a
larger boundary than this token can contain.

## Token and fingerprint controls

The raw token is exactly `rcl_[0-9a-f]{32}`. Generate all 128 suffix bits
directly from an operating-system CSPRNG. Do not derive them from users,
attempts, aliases, public IDs, time, counters, process state, or another token.
No new cryptographic dependency is authorized without separate dependency
review.

Before hashing or database access, require exact type, key set, JSON schema 2,
ASCII encoding, length, lowercase prefix, and lowercase hexadecimal suffix.
Do not trim, normalize, case-fold, coerce, or accept a fingerprint-shaped
value. Malformed or missing values fail closed without mutation or reflection.

Store only:

```text
sha256:<lowercase SHA-256(
  ASCII("praxys/read-claim/v1\0") || canonical ASCII read_claim_id
)>
```

Compute the fingerprint only after canonical validation. Application-level
ownership comparison uses constant-time comparison over equal-length canonical
fingerprints. SQL timing, uniqueness errors, or state-only rereads are not
ownership proof and must not reveal another row.

The partial unique index is the final cross-row collision control. Any
collision or deliberate reuse rolls back and fails closed without revealing
the owning row. It must not trigger automatic token replacement during an
uncertain operation.

## Authorization and lifecycle behavior

- `completion_notified` plus null fingerprint may atomically become
  `read_claimed` with the fingerprint.
- The same token on the same valid `read_claimed` tuple may return the original
  acknowledgement without mutation.
- A different token on that row, or the same token on another retained row,
  fails closed.
- Pre-notification, invalidated, observed, migrated-null terminal, or other
  terminal states never authorize a read.
- A repeated acknowledgement represents the same logical read and never
  authorizes executing it twice.
- `native_observation` requires the exact tuple, `read_claimed`, existing
  authorization, and exact token match. It remains one-shot.
- An ambiguous observation commit fails closed and does not promise replay of
  its result or `orphaned_attempt_ids`.
- Token mismatch cannot create loss, replacement eligibility, recovery
  evidence, invalidation, or terminalization.
- Invalidation or terminalization takes precedence over later claim retries
  and never clears or transfers the fingerprint.
- Null migrated or terminal rows cannot be reopened or assigned ownership.

These controls prevent state-only ownership inference. They do not make
physical native execution exactly-once. If the caller loses the token or
cannot determine whether it already performed the read after a request may
have reached the mediator, it fails closed and does not generate a replacement
or recover the token from Operations.

## Exposure, storage, and retention

The raw token necessarily appears in the caller's controlled request/session
context and transient mediator processing. Accept it only through controlled
JSON input on stdin. The sole output exception is the controlled
`new_identity(kind: "read_claim")` success response that creates the token for
its caller; `native_read`, `native_observation`, and every error response must
not echo it. Do not place it in argv, URLs, environment variables, repository
files, durable runtime artifacts, ledger storage, WAL, backups, ordinary logs,
traces, metrics, errors, crash reports, screenshots, or support workflows.
Redact the identity field before structured logging or exception capture.

The fingerprint is sensitive operational metadata. Do not emit it in ordinary
logs, telemetry, errors, or support output. Privacy-safe telemetry may contain
aggregate reason counts, schema versions, and state categories only.

Restrict the ledger directory, database, WAL/SHM, backup, and restoration
material to the owning principal and designated Operations identities, with
owner-only permissions where supported, encrypted transfer/storage for copied
backups, and audited restore access. Operations must detect permission drift.

The caller-controlled session retains the token only for the logical operation
and its retries. No server recovery store or new caller persistence is
authorized. The fingerprint remains immutable for the life of its row and is
deleted only by an existing authorized whole-row or whole-ledger retention
operation. Uniqueness is guaranteed only among retained rows; no tombstone or
permanent reuse registry is authorized. Callers must never intentionally reuse
a token, while accidental post-deletion reuse remains bounded by the 128-bit
random space.

## Migration, compatibility, and rollback

Migration refuses every ownerless `read_claimed` source row. No fabricated
backfill is allowed. Old clients must be stopped and fenced across linked
worktrees; JSON-schema-1 requests and old binaries against ledger 3 are
refused. Mixed versions, optional tokens, dual writes, online migration,
stale-backup restoration, and in-place downgrade are prohibited.

Before any schema-3 mutation, a quiesced rollback may restore the complete
verified source backup with the matching old binary. After a schema-3 claim or
later mutation, safe rollback retains ledger 3, disables new claims, preserves
fingerprints, and corrects forward. Deleting ownership data or restoring stale
state requires separate authenticated incident authority and an assessment of
discarded ledger and native effects.

## Incident signals and response

Record redacted counters or alerts, never tokens, fingerprints, native results,
or personal content, for:

- malformed, tokenless, wrong-schema, or fingerprint-shaped input;
- same-row mismatch and cross-row uniqueness conflict;
- unexpected repeat acknowledgements or ambiguous-commit retries;
- ownerless `read_claimed` migration sources;
- old-client, mixed-version, or downgrade attempts;
- schema/index drift, immutable-fingerprint violations, or forbidden null
  states;
- ledger/WAL/backup permission drift; and
- suspected token appearance in logs, telemetry, errors, crash data, or
  support channels.

On suspected disclosure or misuse, disable new claims, fence clients, preserve
a restricted SQLite-consistent evidence set, and assess whether claim or
observation occurred. Claims cannot be rotated or transferred. Ledger deletion,
stale restore, destructive reset, or downgrade requires separate human
incident authorization.

## Implementation and verification gates

Engineering may implement only after human approval of the exact bounded
design. Operations owns quiescence, permissions, backup, monitoring, and
rollback. Trust must independently review the final implementation and cannot
approve its own security-sensitive implementation.

Independent evidence must cover:

1. exact artifact digests, schema layouts, index, and predecessor boundaries;
2. CSPRNG generation, canonical validation, deterministic fingerprint vectors,
   and constant-time comparison;
3. the single controlled `new_identity` response exception and absence of raw
   tokens from database, WAL, backups, other output, logs, telemetry, errors,
   crash handling, and support material;
4. existing tuple and authorization enforcement on every claim and
   observation;
5. same-token retry, different-token same-row races, and same-token cross-row
   races;
6. commit-then-raise, rollback-then-raise, lost response, invalidation,
   terminalization, and ambiguous-observation behavior;
7. fingerprint immutability, null-history restrictions, retention, and
   deletion behavior;
8. direct recognized-v1-to-v3 and v2-to-v3 migration, ownerless-row refusal,
   old-client refusal, and downgrade fencing; and
9. dependency review, independent code review, Quality PASS, UTC preflight,
   and required repository checks.

Any raw-token persistence, token-only authorization, optional compatibility,
fingerprint clearing, or state-only reconciliation requires renewed Trust and
Architecture review.

## Residual risks

Residual risks include theft of a token together with sufficient tuple and
caller authority; a faulty caller performing the physical read twice; host,
process-memory, side-channel, or mediator compromise; denial of progress after
token loss; fingerprint correlation; extremely improbable entropy, hash, or
post-deletion token reuse; and operator error during restore. This decision
adds no caller authentication, native-runtime interception, permanent token
tombstone, or exactly-once guarantee.

## Human disposition

Choose exactly one; no choice is selected here:

- **Approve** the bounded claim-ID/fingerprint design for repository
  implementation only.
- **Return for revision** with the exact unresolved Trust constraint.
- **Reject** the design, retain ledger schema 2, prohibit state-only
  reconciliation, and keep the affected native-read path disabled.
