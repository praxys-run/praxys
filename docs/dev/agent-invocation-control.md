# Agent invocation control v1

## Status and authorized scope

This document is the durable Engineering Implementation Impact Map and
Implementation Change for the accepted instrument/shadow implementation. The
control is repository-owned and cooperatively mediated. It is not native
launcher interception, cross-machine authority, or global protection.
Enforcement is unavailable and unapproved. PR #745 extends the original
instrument/shadow control with lifecycle correctness and caller-owned native
read claims. The current bounded implementation is in the working tree and has
not yet received final independent Quality verification. It changes no policy
bound, role, route, reviewer authority, autonomy level, or release state.

The proposed ADR remains Proposed — instrument/shadow scope human-authorized;
final implementation-bound ADR approval pending separate review. This document
does not approve that ADR or any deferred decision.

## Work Contract linkage

- routing_version: praxys-task-routing-v1
- operating_model_version: praxys-agentic-operating-model-v1
- primary_object: agent-system
- impacts: repository-change, agent-policy-or-autonomy,
  architecture-boundary
- risk_triggers: irreversible-or-high-blast-radius-action,
  out-of-policy-or-out-of-distribution-decision
- classification_digest:
  sha256:3d80f3eca01b1bff2207d6e28cefe8daa3cdfc9f3480c80b99bd3f252dde35a2
- primary_loop: meta-eval
- nested_loops: delivery
- lead: meta-eval
- contributor: architecture
- executor: engineering
- verifier: quality
- required_artifacts: evaluation-report, implementation-impact-map,
  implementation-change, verification-evidence, policy-change-proposal,
  architecture-decision-record
- decision_review: required
- route_digest:
  sha256:dfe65e8c108c06411ad84d7e7d8ec32d8206429780243973a31e840fb7c11f51

Every admission recomputes this kind of authoritative Work Contract from the
bounded classification before ledger access or candidate-policy evaluation.
Caller-supplied digests and slot roles must match the recomputed contract. The
guard never changes routing, loops, roles, reviewers, artifacts, autonomy, or
the operating-model version.

The native-read claim correction was separately routed as
`primary_object=repository-behavior`, with impacts `repository-change`,
`production-operation`, `architecture-boundary`, and `trust-boundary`; risks
`security-or-privacy-boundary`,
`irreversible-or-high-blast-radius-action`, and
`out-of-policy-or-out-of-distribution-decision`; classification digest
`sha256:e3c17d24f3e95a7629a8a86d7454e1cd2e5dbf94b32011c6beaa596408de3ac9`;
and route digest
`sha256:d44577261f0413c0df43f34a13d18e4f84a9fd1c7aea6cdb9ab089724fd9b132`.
That contract has Delivery as primary, Runtime nested, Architecture and Trust
as contributors, Engineering and Operations as executors, and Quality as
verifier.

## Accepted decision trail

The governing artifacts are:

- docs/dev/evaluation-report-2026-08-20-agent-invocation-control.md
- docs/dev/policy-change-proposal-agent-invocation-control-v1.md
- docs/dev/adr-2026-08-20-agent-invocation-control.md
- docs/dev/adr-2026-08-30-agent-invocation-ledger-v2.md
- docs/dev/adr-2026-08-31-agent-native-read-claim-ownership.md
- docs/ops/tdr-2026-08-31-agent-native-read-claim-ownership.md
- docs/ops/odr-2026-08-31-agent-native-read-claim-ownership.md

The original instrument/shadow proposal used a `human-review-required` route
and the recorded approval below. For the 2026-08-29 bounded correction, the
Decision Review route is `agent-resolved` because implementation is
deterministic within the accepted behavior. The user's statements “好，那根据这个改进一下这个PR？”
and “继续没做完的工作” provide semantic authority for that bounded correction.
No digest-bound approval is fabricated or implied.

For the native-read ownership correction, the authenticated maintainer
approved repository implementation only on 2026-08-30T14:07:27Z against these
exact SHA-256 file digests:

- Architecture:
  `a78541c75bad209abff2bbcce99ce5599d8b142d04f4b0c50cd1dd86559d8fd9`
- Trust:
  `ad464cbd41f8375ce684f80bb35117c6ddf98783d2ee4d7817f23a4693844847`
- Operations:
  `013b94dc6de8276dea82abcb38dbb38bb89d5be9ea69a2efc3c852e3d06c512a`

That disposition authorizes this bounded repository implementation, not
retained-ledger migration, reset, restore, deployment, release, merge, or
autonomy expansion. The digest-bound proposal files remain byte-stable.

Recorded human approval timestamp: 2026-08-20T23:38:10.880+08:00

> I approve policy-change-proposal-agent-invocation-control-v1 at
> sha256:d6b9a136b44ae52d993ae07dd0000d946e201f73ea1b4db5cb116f01bab9e0f6
> for instrument/shadow implementation only.

The proposal digest identifies the approved subject; it is not claimed to be a
rendered-file hash. Enforcement, native interception, autonomy promotion,
bound tuning, operating-model changes, and final implementation-bound ADR
approval remain deferred.

## Implementation Impact Map

| Area | Impact |
|---|---|
| Data | Advances the disposable Git-common-dir SQLite ledger to layout schema 3. It retains the ledger-v2 lifecycle and provenance tables and adds one nullable `native_invocations.read_claim_fingerprint` column plus an exact partial unique index. Explicit `init` can transactionally migrate exact recognized v1 or v2 sources after taking the SQLite write lock. Public agent IDs and read-claim IDs are stored only as separate domain-separated SHA-256 fingerprints. The ledger remains outside the application database and stores no task, prompt, source, user, issue, artifact content, credential, output, stack trace, free-form work description, or free-form diagnostic text. |
| Analysis | Adds analysis/agentic_invocation_control.py, an I/O-free stdlib identity validator and deterministic candidate-policy evaluator. Existing static routing remains authoritative and unchanged. |
| API | No application API or authentication change. |
| Clients | Advances the stdin/stdout JSON contract to schema 2. Cooperative Orchestrator/Delivery Loop callers generate one caller-owned `rcl_*` identity before claiming a completed background invocation, reuse it for claim retries and the one observation, and locally prevent a second physical native read. No UI, provider, sync, or native-agent API changes. |
| Operations | Adds no service, deployment setting, secret, alert, registry lookup, polling loop, or production runtime. Local and Cloud use the same repository protocol and the same native-interception limitation. |
| Migration | Keeps policy v1, advances JSON schema 1 to 2, and advances the SQLite layout from schema 2 to 3. Only explicit `init` may migrate exact recognized v1 or v2 sources. It acquires `BEGIN IMMEDIATE` before inspection, refuses every ownerless `read_claimed` source row, composes any required predecessor backfill and the claim delta in one transaction, and commits only metadata version 3. Ordinary commands require ledger 3. Old binaries report it unsupported. |
| Tests | Covers lifecycle races and recovery plus claim generation, deterministic fingerprinting, malformed and tokenless requests, same-token idempotency, different-token and cross-row refusal, commit ambiguity, one-shot observation, fingerprint retention, raw-token non-persistence, direct v1/v2-to-v3 migration, ownerless-row refusal, JSON compatibility, and old-client refusal. Independent Quality verification remains a separate artifact and has not yet occurred for this change. |

## Implementation Change

The checked-in policy is config/agent-invocation-control.json. It fixes JSON
schema version 2 and policy version 1, the approved modes, unavailable
enforcement, and the accepted starting limits. The implementation adds:

1. Pure identity and policy evaluation in
   analysis/agentic_invocation_control.py.
2. A thin versioned JSON CLI in scripts/agent_invocation_control.py.
3. A WAL SQLite ledger under
   git-common-dir/praxys/agent-invocation-control-v1.sqlite3. The stable
   filename identifies the policy-v1 ledger, while metadata identifies the
   internal layout as ledger schema 3. Foreign keys are enabled per connection,
   and `BEGIN IMMEDIATE` protects initialization, admission, and lifecycle
   transitions.
4. Stable opaque contract, slot, generation, logical-invocation, attempt, and
   decision identities. Slot identity is generation-independent, so a new
   generation cannot hide a nested slot cycle. Logical and concrete attempt
   identities remain separate.
5. Atomic duplicate-active, ancestry, active-count, logical-count, retry,
   attempt, no-progress, and kill-switch decisions. Ordinary instrument/shadow
   would-reject decisions are recorded as launched and remain non-blocking. The
   explicit kill switch records the decision and rejects that mediated launch.
6. Explicit terminal transitions and leaf-first crash recovery. No lease,
   heartbeat expiry, elapsed-time inference, or stale timeout exists.
7. Cooperative Local/Cloud agent-manifest guidance with no native-interception
   or global-enforcement claim.
8. A lifecycle work key of contract, stable bounded-role slot, and immutable
   artifact digest or Git head. One active key is allowed; a different immutable
   revision is an explicit `review_after_new_digest`, not a duplicate.
9. Explicit `initial_launch`, `resume`, `replacement`,
   `review_after_new_digest`, `duplicate_launch`, and `illegal_transition`
   records. Duplicate and illegal lifecycle transitions fail closed even though
   ordinary instrument/shadow candidate-policy denials remain observational.
10. A transactionally serialized direct-child boundary for lifecycle-aware
    calls. One non-null parent attempt may have at most one active direct child;
    another direct sibling receives `direct_sibling_active` and no attempt is
    created. A nested chain remains allowed because every link has a different
    parent. Roots and unrelated parents are not globally serialized. Once a
    duplicate, illegal transition, active direct sibling, or other hard
    admission rejection is known, failure to persist its decision or audit row
    returns `ledger_unavailable` with `launch_authorized=false`; unavailable
    storage cannot turn that known rejection into permission to launch.
11. Closed dispatch provenance. Omitted fields retain compatibility as
    `sync`/`sync_inline`; cooperative manifests send that pair explicitly.
    Background is valid only as
    `background`/`background_independent_immediate_no_poll`. Unknown, partial,
    or mismatched provenance fails closed as `execution_provenance_invalid`.
12. Split completion semantics. Sync work returns inline and cannot bind or
    read a native agent. Background work may bind the exact public agent ID
    returned by successful `task` with `binding_source=task_result`, wait for
    an external completion notification without polling, and claim one read.
    If notifications are unavailable, it records that capability result and
    stops without a read or poll.
13. Completion-notification-driven one-read native bindings. `nat_*` is only a
    repository alias. The raw public ID is validated but never persisted; a
    domain-separated SHA-256 fingerprint is bound to the alias and attempt.
    Notification requires the exact attempt, alias, and public ID. Before
    claiming, the caller generates one `rcl_*` identity. Read and observation
    require the exact tuple and that same claim ID. Only the domain-separated
    claim fingerprint is persisted, remains immutable for the retained row,
    and is unique among retained native rows. Same-token claim retry is
    idempotent; a different token, cross-row reuse, lost token, or uncertainty
    about whether the physical read already ran fails closed.
    The first observed `not_found` result records loss, permanently closes
    that opaque native ID,
    and creates at most one explicit, manually consumed replacement eligibility.
    A replacement is separately identified, never automatic, and cannot create
    a replacement chain.
14. Explicit `invalidate_native` state for `shutdown`, `resume`, and
    `context_replacement`. Invalidation permanently refuses the old
    alias/public-ID binding without registry lookup, polling, inference,
    relaunch, replacement, or automatic loss. External rebind is deferred.
    Mediated pre-completion native write is unsupported.
15. Idempotent `terminate_tree` cleanup for abort, shutdown, and failure. Active
    descendants terminalize leaf first as `orphaned` before the parent. This is
    ledger cleanup, not a native kill or cancellation claim.
16. Explicit substantive progress fingerprints. Duplicate evidence is
    idempotent; reads, notifications, and elapsed time never advance
    `last_progress_at_ms`, and phase one infers no staleness.

scripts/route_agentic_task.py, Decision Review behavior, role/reviewer
authority, autonomy policy, operating-model version, application storage,
plugins/praxys, providers, sync, authentication, and UI are outside this
change.

## Identity and privacy contract

The CLI accepts only exact command-specific key sets. Opaque repository
identities, including `nat_*` repository-side aliases and `rcl_*` read claims,
use a kind prefix plus 128 random bits. A `nat_*` value is never the
native/public agent ID. An `rcl_*` value is caller-held proof for one logical
claim, not authentication or a transferable credential. Immutable work revisions
are lowercase `sha256:<64 hex>` digests or `git:<40 or 64 hex>` heads. Failure,
progress, and terminal fingerprints use the
fpr_ prefix plus 256 hexadecimal bits. Callers hash or otherwise derive a
privacy-safe fingerprint before invoking the CLI; raw failures and task text
must never be supplied.

The stable slot identity denotes the composed work slot and is reused across
its generations. A logical identity spans its permitted retry attempts. Every
execution gets a fresh attempt identity. Nested calls carry only the active
parent attempt identity. Contract and slot identities are durably bound to the
recomputed route and bounded role, and conflicting reuse is invalid.

Task-returned public agent IDs must be non-empty, bounded, whitespace-free,
control-free values that are not repository identities, `call_*` call IDs, or
obvious placeholders. The binding persists only
`SHA-256("praxys-native-public-agent-id-v1\0" || exact_public_id)`, never the
raw ID.

The raw read-claim ID may appear only in the caller-controlled stdin request
and the single controlled `new_identity(kind: "read_claim")` success response.
The ledger, WAL, and backups may contain only
`SHA-256("praxys/read-claim/v1\0" || canonical_read_claim_id)`, never the raw
token. Ordinary responses, logs, telemetry, errors, and support artifacts emit
neither the raw token nor its fingerprint.

Permitted ledger facts are versions, route/classification digests, bounded role
IDs, opaque identities and parent links, lifecycle state, opaque fingerprints,
policy reasons, booleans, depths, and epoch-millisecond timing facts. The CLI
rejects unknown fields rather than ignoring possible content.

## Versioned CLI contract

Every request and response is one JSON object with `schema_version: 2`. Requests
are read from standard input; exactly one compact JSON response is written to
standard output.

Commands:

- init: explicitly create/validate ledger schema 3 or transactionally migrate
  one exact recognized ledger-v1 or ledger-v2 layout after acquiring the write
  lock.
- new_identity: create contract, slot, generation, logical, attempt, native, or
  read-claim identity.
- admit: recompute the Work Contract, evaluate atomically, and record the
  decision and any authorized instrument/shadow launch. Lifecycle-aware calls
  also supply artifact_revision, lifecycle_transition, and nullable
  replacement_of_attempt_id.
- bind_native: for background only, bind a `nat_*` alias to the fingerprint of
  the exact task-returned public ID with `binding_source=task_result`, recording
  whether completion notifications are available.
- native_notification: record the authoritative completion notification.
- native_read: require `read_claim_id` and claim the single logical native read
  after that notification. The response includes `idempotent`; callers still
  use their own operation state to ensure the physical native read runs at
  most once.
- native_observation: record the claimed read as found or authoritative
  not_found using the same `read_claim_id`; not_found atomically records loss
  and cleanup.
- progress: record a new substantive progress fingerprint.
  Repeating any prior fingerprint is idempotent and reports the attempt's
  current `last_progress_at_ms`, never the older evidence row's timestamp.
  New evidence clamps its timestamp to the current latest value if wall-clock
  time moves backward.
- terminate_tree: leaf-first terminal cleanup for abort, shutdown, or failure.
- invalidate_native: permanently invalidate one exact alias/public-ID binding
  for shutdown, resume, or context replacement without changing attempt state.
- finish: terminally record succeeded or failed with an opaque fingerprint.
- recover: terminally record recovered with an opaque fingerprint, leaf first.
- kill_switch: atomically enable or disable mediated-launch rejection.
- status: report aggregate counts, reason counts, kill-switch state, and opaque
  active-attempt/parent/depth facts in leaf-first order.

Stable exit meanings:

| Exit | Meaning |
|---:|---|
| 0 | Instrument/shadow evaluation or lifecycle command completed, including an ordinary hypothetical deny. |
| 2 | Invalid request, identity, parent binding, or conflicting terminal transition. |
| 3 | Policy or recomputed Work Contract unavailable, invalid, or mismatched. |
| 4 | Ledger, transaction, state validation, or leaf-first recovery failure. |
| 5 | Requested mode or required native notification capability unavailable or unapproved. |

Ordinary instrument/shadow candidate-policy denials remain observational. A
cooperative caller must not dispatch when the lifecycle response has
`launch_authorized=false` because the same logical work is already active, the
transition is illegal, or the accepted kill switch is active. It must also not
perform a native read unless `native_read` returns `read_authorized=true`. These
are local protocol/state-machine correctness boundaries, not enforcement of a
new policy or interception of an unmediated native call. An enforce request
returns enforcement_unavailable and does not silently alias to another mode.

Stable policy reasons:

| Reason | Meaning |
|---|---|
| admit | Candidate guards pass. |
| work_contract_invalid | Recomputed Work Contract is unavailable or mismatched. |
| kill_switch_active | Explicitly reject this mediated launch. |
| duplicate_active | Matching logical or slot-generation work is active. |
| ancestry_cycle | The generation-independent slot repeats in ancestry. |
| ancestry_depth_limit | Proposed depth is greater than 6. |
| active_contract_limit | The next launch crosses 8 active attempts. |
| logical_contract_limit | The next new logical invocation crosses 32. |
| retry_fingerprint_limit | One retry for the same failure fingerprint is already recorded. |
| attempt_limit | Three attempts for the logical invocation are already recorded. |
| no_progress | The last two terminal fingerprints for the slot are identical. |
| state_missing | The explicitly initialized ledger is absent. |
| state_corrupt | The ledger is structurally missing, incomplete, or damaged. |
| state_unsupported | The readable ledger has an unsupported schema or policy version. |

Stable machine reason codes are `instrument_recorded`,
`shadow_would_admit`, `shadow_would_deny_cycle`,
`shadow_would_deny_policy_limit`, `invalid_request`, `invalid_identity`,
`work_contract_unavailable`, `work_contract_mismatch`, `policy_unavailable`,
`recovery_required`, `ledger_unavailable`, `enforcement_unavailable`,
`kill_switch_active`, `ledger_initialized`, `ledger_ready`,
`identity_created`, `finish_recorded`, `finish_idempotent`,
`recovery_recorded`, `kill_switch_updated`, `status_reported`,
`lifecycle_transition_rejected`, `native_bound`,
`native_notification_recorded`, `completion_notification_required`,
`native_notifications_unavailable`, `native_read_authorized`,
`native_read_refused`, `native_observation_recorded`, `progress_recorded`,
`progress_idempotent`, `tree_termination_recorded`, and
`tree_termination_idempotent`, `direct_sibling_active`,
`execution_provenance_invalid`, `native_binding_mismatch`,
`native_binding_invalidated`, and `native_invalidated`. Additions must remain
compatible with policy v1 and explicit about JSON schema changes.

## Starting limits

| Guard | Bound |
|---|---:|
| Maximum ancestry depth | 6 |
| Maximum active attempts per contract | 8 |
| Maximum logical invocations per contract | 32 |
| Maximum attempts per logical invocation | 3 |
| Retries per failure fingerprint | 1 |
| Identical terminal fingerprints establishing no progress | 2 |

These values are not runtime tuning knobs. Any change requires evidence and a
separately reviewed proposal.

## Ledger schema 3 migration

The machine JSON contract is version 2, the policy remains
`agent-invocation-control-v1`, and the SQLite target is ledger schema 3.
Schema 3 is the exact ledger-v2 target plus nullable
`native_invocations.read_claim_fingerprint` and the partial unique index
`native_invocations_read_claim_fingerprint_uq`.

Only explicit `init` may migrate. For an existing ledger it establishes only
connection-local safety settings, acquires `BEGIN IMMEDIATE`, and then reads
journal mode, metadata, schema objects, and rows. It accepts exactly:

1. the released base-v1 tables and indexes;
2. base-v1 plus the lifecycle tables and indexes;
3. the complete ledger-v2 physical layout while metadata still says version 1;
   or
4. the exact valid ledger-v2 target with metadata version 2.

The existing ledger must already use WAL. Unknown objects, missing objects,
changed columns or constraints, partial auxiliary state, unsupported metadata,
and ambiguous historical rows are not repaired. A lifecycle-v1 ledger with an
existing `native_invocations` row remains unsupported because verified public
ID provenance cannot be reconstructed. Full-v1 and v2 require exactly one
matching provenance row for every native invocation.

Any recognized source containing `lifecycle_status = 'read_claimed'` is also
unsupported. Its caller-owned token cannot be reconstructed, so migration
never clears the state, returns it to `completion_notified`, fabricates a
fingerprint, or guesses ownership. Other active,
`notifications_unavailable`, `completion_notified`, observed, and terminal
rows may migrate and receive a null claim fingerprint. Null historical rows
remain closed and can never acquire a claim later.

For a version-1 source, the transaction first applies the immutable
ledger-v1-to-v2 schema and dispatch/provenance rules, then applies the claim
column and index. It does not commit an intermediate version 2. A valid
version-2 source receives only the claim delta. Metadata is set to 3 only after
the exact physical and logical target validates.

The predecessor validation remains in force: authorized decisions, attempts,
work history, active keys, parent/depth graph, dispatch provenance, progress
evidence, native state, and replacement eligibility must match
bidirectionally. Schema-3 validation additionally requires canonical claim
fingerprints, null fingerprints in pre-claim states, a non-null fingerprint in
`read_claimed`, retained-row uniqueness, and only the explicitly permitted
null observed or terminal history.

DDL, backfill, metadata update, and final validation commit together. A
pre-commit failure restores the prior logical schema, metadata, and rows. An
ambiguous migration commit is resolved under one fresh write lock: exact schema
3 means committed, the exact source means rolled back, and any other state
fails closed. Concurrent initializers serialize; a follower rereads and
validates the committed schema-3 state.

Fresh initializers each build and checkpoint a complete same-directory
temporary WAL database, apply owner-only permissions, then atomically publish
with a no-overwrite hard link. The final path is never visible as an empty
placeholder; one initializer publishes and the others validate the complete
ledger. Filesystem allocation or publication failures use the versioned
`ledger_unavailable` response and do not emit an unstructured traceback.
Ordinary commands never migrate ledger 1 or 2 and report either as
unsupported.

## Activation

Use the repository virtual environment. First recompute and retain the exact
Work Contract:

    .venv/bin/python scripts/route_agentic_task.py       --primary-object agent-system       --impact repository-change       --impact agent-policy-or-autonomy       --impact architecture-boundary       --risk-trigger irreversible-or-high-blast-radius-action       --risk-trigger out-of-policy-or-out-of-distribution-decision

Explicitly initialize the local ledger:

    echo '{"schema_version":2,"command":"init"}' |       .venv/bin/python scripts/agent_invocation_control.py

Create each opaque identity separately, changing kind as needed:

    echo '{"schema_version":2,"command":"new_identity","kind":"contract"}' |       .venv/bin/python scripts/agent_invocation_control.py

Begin with admit requests whose mode is instrument. Each request also carries
the bounded classification arrays, recomputed classification and route digests,
contract_id, stable slot_id and slot_role, generation_id, logical_id,
attempt_id, nullable parent_attempt_id, nullable retry_fingerprint, immutable
artifact_revision, an explicit lifecycle_transition, and nullable
replacement_of_attempt_id. Lifecycle-aware requests may omit dispatch fields
for compatibility, which means `dispatch_mode=sync` and
`execution_provenance=sync_inline`; Orchestrator and Change Loop calls send
that pair explicitly. They use background only with
`dispatch_mode=background` and
`execution_provenance=background_independent_immediate_no_poll`. Retain attempt
IDs until their finish or recovery is recorded. The original request shape
remains accepted for #737 compatibility, but orchestrator/change-loop calls use
lifecycle-aware admissions. Move individual
cooperative requests to shadow only after instrument lifecycle and recovery
records are healthy; this is not enforcement promotion.

Check privacy-safe local state with:

    echo '{"schema_version":2,"command":"status"}' |       .venv/bin/python scripts/agent_invocation_control.py

Activate the immediate mediated-launch stop path with:

    echo '{"schema_version":2,"command":"kill_switch","active":true}' |       .venv/bin/python scripts/agent_invocation_control.py

The switch affects only calls that cooperate with this protocol.

## Notification, read, and replacement sequence

Sync dispatch returns inline. Do not call `bind_native`, `native_read`, or
`read_agent` for sync work.

For a valid background dispatch, take the public agent ID returned by successful
`task`, create a separate `nat_*` repository alias, and submit `bind_native`
with the attempt ID, alias, exact public ID, and
`binding_source=task_result`. The ledger stores only a domain-separated
fingerprint. If completion notifications are unavailable, record that
capability result and stop without reading or polling. Otherwise, wait for the
external completion notification without reads, status checks,
`read_agent(wait:true)`, or any polling loop. After notification, create one
fresh `read_claim` identity and retain it in the caller's current operation
state. The one `native_read` claim and resulting `native_observation` must carry
the same exact attempt ID, alias, public ID, and `read_claim_id`.

If the claim response is lost before any physical native read, retry the exact
claim request with the same token. `idempotent=true` means the same logical
claim already exists; it never authorizes a second physical read. The caller
must separately know whether it has already invoked the physical read. If the
caller loses the token or cannot determine whether that physical read already
ran, stop without rereading, generating a replacement token, observing,
marking loss, or launching a replacement.

A claim before notification, a different token on the claimed row, reuse of
the token on another retained row, any tuple mismatch, post-observation state,
invalidation, or terminal state is refused. The at-rest claim fingerprint
never changes or clears while its row remains.

An authoritative `not_found` terminalizes that attempt as `lost` and active
descendants as `orphaned`. It creates one replacement eligibility only for a
non-replacement attempt. A caller may later submit one separately identified
`replacement` admission that names the lost attempt; admission consumes the
eligibility transactionally but never launches by itself. Loss of that
replacement creates no new eligibility. A revision with replacement history
cannot be resumed, so an intervening `resume` cannot erase replacement lineage
and reopen eligibility.

Mediated native write is unsupported. Do not invent a pre-completion multi-turn
write subsystem. If a future native capability supports exact writes or exact
external rebind, it requires a separately reviewed policy.

## Recovery

There is no stale timeout. A process ending or elapsed time alone never changes
an active attempt. Use status to read active opaque attempt IDs, parents, and
depths. Determine that recovery is appropriate outside this content-free
ledger, then submit recover commands from greatest depth to least depth. An
ancestor with an active child returns recovery_required without mutation.
Repeating the exact terminal transition is idempotent; a different status or
fingerprint conflicts and does not mutate state. For parent abort, shutdown,
or failure, use `terminate_tree`; it atomically marks every active descendant
`orphaned` from deepest leaf upward and then terminalizes the parent. It does
not call or claim native cancellation.

For session shutdown, resume, or context replacement, use `invalidate_native`
with the exact attempt, alias, and public ID. This writes only the invalidation
enum and timestamp. The old binding is permanently unusable for notification,
read, observation, or any future write. Invalidation performs zero native
registry lookup, polling, or inference; it does not mark the attempt lost,
create replacement eligibility, relaunch work, or select a replacement.
External rebind remains deferred unless a future native capability supplies an
exact match under separately reviewed policy.

Example request shape:

    {"schema_version":2,"command":"recover","attempt_id":"att_00000000000000000000000000000001","terminal_fingerprint":"fpr_0000000000000000000000000000000000000000000000000000000000000001"}

## Rollback

Repository implementation approval does not authorize operating a retained
ledger. Follow the claim-ownership ODR before any migration, restore, reset, or
release.

If schema 3 committed but no ordinary schema-3 operation has mutated the
ledger, a quiesced operator may restore the complete verified source backup and
matching old binary only under separate execution authority. Restore the
database, WAL, and SHM as one consistent set and revalidate the exact source
before dispatch.

After any schema-3 claim or later mutation, do not downgrade in place, remove
the claim column, clear fingerprints, or restore a stale schema-2 backup. Fence
incompatible clients, disable new claims, retain ledger 3 and its ownership
facts, and correct forward. Destructive reset, stale restore, or column
deletion requires new authenticated incident authority and an assessment of
discarded attempts, claims, observations, descendants, replacement
eligibility, native work, and kill-switch effects.

A corrupt or unsupported ledger is never overwritten automatically. Preserve
a restricted SQLite-consistent evidence set when needed and diagnose it before
retrying. Resetting the ledger starts a new control epoch but never cancels
native work.

Instrument/shadow generally reports `state_missing`, `state_corrupt`, or
`state_unsupported` with `launch_authorized=true`; only a future separately
approved enforce mode could fail closed on unavailable state. The narrow
exception is a hard admission rejection already established from a valid
snapshot, including the kill switch and lifecycle protocol violations: if its
decision or rejection evidence cannot be committed, the response remains
`launch_authorized=false`. Replaying an already recorded lifecycle rejection
also remains fail-closed if its consumed attempt identity is encountered again.

## Local and Cloud parity and limits

Local and Cloud use the same checked-in policy, pure evaluator, CLI, Work
Contract recomputation, manifests, JSON surface, reason codes, and ledger
semantics, including explicit dispatch profiles, parent-scoped direct-sibling
serialization, exact binding verification, no-poll notification waiting,
caller-owned claim tokens, one logical claim and one physical read,
token-matched one-shot observation, and invalidation. Each clone or ephemeral
Cloud checkout has its own Git-common-dir
ledger. There is no shared or cross-machine authority and no known denominator
for all platform invocations.

This protocol mediates only agent calls whose repository manifest cooperates.
It does not own the Copilot registry, completion-notification delivery, native
read implementation, or native cancellation. The repository has no native hook
that can intercept Copilot, platform, user, or other unmediated invocations. Those calls remain possible and unknown. Any
report must distinguish mediated coverage from all native invocation volume and
must not claim global prevention or enforcement.

## Observation plan and enforcement evidence bar

Run instrument and then shadow across at least five distinct contract/root runs
over at least seven calendar days. Replay and review at least:

1. valid first launch and clean terminal finish;
2. active duplicate and nonmatching concurrency;
3. direct/indirect cycles and ancestry at/beyond depth 6;
4. active attempts 8/9 and logical invocations 32/33;
5. attempts 3/4, one same-fingerprint retry, and an additional retry;
6. two identical terminal fingerprints followed by a proposed launch;
7. valid, mismatched, unavailable, missing, corrupt, and unsupported contracts
   or state;
8. parent mismatch, active-child finish, leaf-first recovery, idempotent finish,
   and conflicting finish;
9. kill-switch inactive/active behavior;
10. same-token claim retry, different-token and cross-row refusal, ambiguous
    claim commit, one-shot observation, and token-loss fail-closed behavior;
    and
11. Local and Cloud cooperative coverage with unmediated activity explicitly
    unknown.

Aggregate mediated coverage, decisions and stable reasons, latency, recovery
and state errors, corrections, overrides, missed and unnecessary escalations,
adverse outcomes, reverts, incidents, reviewer effort, target/guardrail
movement, false blocks, and policy escapes without adding content to the
ledger.

A later enforcement proposal requires the complete replay corpus and the
minimum observation window to show zero false blocks, zero policy escapes, and
zero human corrections. Those are prerequisites, not automatic authorization.
Enforcement, native interception, bound tuning, autonomy promotion, and
operating-model version changes still require separate evidence, independent
decision review, and human approval.
