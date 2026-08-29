# Agent invocation control v1

## Status and authorized scope

This document is the durable Engineering Implementation Impact Map and
Implementation Change for the accepted instrument/shadow implementation. The
control is repository-owned and cooperatively mediated. It is not native
launcher interception, cross-machine authority, or global protection.
Enforcement is unavailable and unapproved. The lifecycle-first P0/P1
extension described below is a local, uncommitted implementation and is **not
approved for release**. It corrects cooperative lifecycle bookkeeping inside
the accepted policy; it changes no policy value, role, route, reviewer
authority, or autonomy level.

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

Current bounded local handoff: contract `ctr_124fe6b57155999474f3aa7f3829426b`,
slot `slt_a3f95d836676a59960d82b3b15499648`, generation
`gen_ef44174f758181040c7bcb4c734a7b19`, logical invocation
`log_22311bf9d8ac4ea54ed3f8bb01859ace`, attempt
`att_2db630c4f73b35c6b303ee7ba1cf3093`, and parent
`att_177f2b079711adc654290353bd85fffa`. Admission was explicitly recorded as
`launch_authorized=true` with policy reason `admit`. These opaque IDs are a
durable handoff record, not a claim of native cancellation or callback control.

Every admission recomputes this kind of authoritative Work Contract from the
bounded classification before ledger access or candidate-policy evaluation.
Caller-supplied digests and slot roles must match the recomputed contract. The
guard never changes routing, loops, roles, reviewers, artifacts, autonomy, or
the operating-model version.

## Accepted decision trail

The governing artifacts are:

- docs/dev/evaluation-report-2026-08-20-agent-invocation-control.md
- docs/dev/policy-change-proposal-agent-invocation-control-v1.md
- docs/dev/adr-2026-08-20-agent-invocation-control.md

Independent Decision Review Router outcome: human-review-required.

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
| Data | Compatibly extends the disposable Git-common-dir SQLite v1 ledger with additive lifecycle, immutable-revision, native-binding, one-read, replacement-eligibility, and progress-evidence tables. It remains outside the application database and stores no task, prompt, source, user, issue, artifact content, credential, output, stack trace, or free-form diagnostic text. |
| Analysis | Adds analysis/agentic_invocation_control.py, an I/O-free stdlib identity validator and deterministic candidate-policy evaluator. Existing static routing remains authoritative and unchanged. |
| API | No application API or authentication change. |
| Clients | Adds a versioned stdin/stdout CLI and cooperative instructions in the Orchestrator and Delivery Loop manifests. No UI, provider, sync, or native-agent API changes. |
| Operations | Adds no service, deployment setting, secret, alert, or production runtime. Local and Cloud use the same repository protocol, subject to the same native-interception limitation. |
| Migration | Explicit `init` transactionally adds the compatible lifecycle tables to a valid original v1 ledger; no mandatory v2, application migration, destructive rewrite, or automatic incompatible migration is introduced. Partial or unsupported state fails visibly. |
| Tests | Extends focused policy/lifecycle tests for logical-key deduplication, first loss, permanent read refusal, one replacement/no chain, leaf-first parent cleanup, new-revision review, illegal transitions, explicit progress, original #737 behavior, manifests, and parity. Independent Quality verification remains a separate artifact and has not yet occurred for this local change. |

## Implementation Change

The checked-in policy is config/agent-invocation-control.json. It fixes schema
and policy version 1, the approved modes, unavailable enforcement, and the
accepted starting limits. The implementation adds:

1. Pure identity and policy evaluation in
   analysis/agentic_invocation_control.py.
2. A thin versioned JSON CLI in scripts/agent_invocation_control.py.
3. A WAL SQLite ledger under
   git-common-dir/praxys/agent-invocation-control-v1.sqlite3, with foreign keys
   enabled per connection and BEGIN IMMEDIATE for admission and lifecycle
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
10. Completion-notification-driven one-read native bindings. The first claimed
    `not_found` result records loss, permanently closes that opaque native ID,
    and creates at most one explicit, manually consumed replacement eligibility.
    A replacement is separately identified, never automatic, and cannot create
    a replacement chain.
11. Idempotent `terminate_tree` cleanup for abort, shutdown, and failure. Active
    descendants terminalize leaf first as `orphaned` before the parent. This is
    ledger cleanup, not a native kill or cancellation claim.
12. Explicit substantive progress fingerprints. Duplicate evidence is
    idempotent; reads, notifications, and elapsed time never advance
    `last_progress_at_ms`, and phase one infers no staleness.

scripts/route_agentic_task.py, Decision Review behavior, role/reviewer
authority, autonomy policy, operating-model version, application storage,
plugins/praxys, providers, sync, authentication, and UI are outside this
change.

## Identity and privacy contract

The CLI accepts only exact command-specific key sets. Opaque identities, including repository-side aliases for native
invocations, use a kind prefix plus 128 random bits. Immutable work revisions
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

Permitted ledger facts are versions, route/classification digests, bounded role
IDs, opaque identities and parent links, lifecycle state, opaque fingerprints,
policy reasons, booleans, depths, and epoch-millisecond timing facts. The CLI
rejects unknown fields rather than ignoring possible content.

## Versioned CLI contract

Every request and response is one JSON object with schema_version 1. Requests
are read from standard input; exactly one compact JSON response is written to
standard output.

Commands:

- init: explicitly create or validate ledger schema v1.
- new_identity: create contract, slot, generation, logical, attempt, or native identity.
- admit: recompute the Work Contract, evaluate atomically, and record the
  decision and any authorized instrument/shadow launch. Lifecycle-aware calls
  also supply artifact_revision, lifecycle_transition, and nullable
  replacement_of_attempt_id.
- bind_native: bind one opaque native alias and declare whether authoritative
  completion notifications are available.
- native_notification: record the authoritative completion notification.
- native_read: claim the single native read after that notification.
- native_observation: record the claimed read as found or authoritative
  not_found; not_found atomically records loss and cleanup.
- progress: record a new substantive progress fingerprint.
- terminate_tree: leaf-first terminal cleanup for abort, shutdown, or failure.
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
| 5 | Requested mode unavailable or unapproved. |

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
`tree_termination_idempotent`. Additions must remain additive within v1.

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

## Activation

Use the repository virtual environment. First recompute and retain the exact
Work Contract:

    .venv/bin/python scripts/route_agentic_task.py       --primary-object agent-system       --impact repository-change       --impact agent-policy-or-autonomy       --impact architecture-boundary       --risk-trigger irreversible-or-high-blast-radius-action       --risk-trigger out-of-policy-or-out-of-distribution-decision

Explicitly initialize the local ledger:

    echo '{"schema_version":1,"command":"init"}' |       .venv/bin/python scripts/agent_invocation_control.py

Create each opaque identity separately, changing kind as needed:

    echo '{"schema_version":1,"command":"new_identity","kind":"contract"}' |       .venv/bin/python scripts/agent_invocation_control.py

Begin with admit requests whose mode is instrument. Each request also carries
the bounded classification arrays, recomputed classification and route digests,
contract_id, stable slot_id and slot_role, generation_id, logical_id,
attempt_id, nullable parent_attempt_id, nullable retry_fingerprint, immutable
artifact_revision, an explicit lifecycle_transition, and nullable
replacement_of_attempt_id. Retain attempt IDs until their finish or recovery is
recorded. The original request shape remains accepted for #737 compatibility,
but orchestrator/change-loop calls use lifecycle-aware admissions. Move individual
cooperative requests to shadow only after instrument lifecycle and recovery
records are healthy; this is not enforcement promotion.

Check privacy-safe local state with:

    echo '{"schema_version":1,"command":"status"}' |       .venv/bin/python scripts/agent_invocation_control.py

Activate the immediate mediated-launch stop path with:

    echo '{"schema_version":1,"command":"kill_switch","active":true}' |       .venv/bin/python scripts/agent_invocation_control.py

The switch affects only calls that cooperate with this protocol.

## Notification, read, and replacement sequence

After native launch, bind its repository-side opaque alias. If the binding says
notifications are available, do no read and no polling while waiting. Record
the native completion notification, claim exactly one `native_read`, perform
that native read once, then record `found` or `not_found`. A read before the
notification and every read after the first claim are refused. If notifications
are unavailable, the binding returns `notifications_unavailable_no_polling`;
record that limitation and stop rather than substituting polling. The
repository provides no native callback adapter in phase one.

An authoritative `not_found` terminalizes that attempt as `lost` and active
descendants as `orphaned`. It creates one replacement eligibility only for a
non-replacement attempt. A caller may later submit one separately identified
`replacement` admission that names the lost attempt; admission consumes the
eligibility transactionally but never launches by itself. Loss of that
replacement creates no new eligibility.

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

Example request shape:

    {"schema_version":1,"command":"recover","attempt_id":"att_00000000000000000000000000000001","terminal_fingerprint":"fpr_0000000000000000000000000000000000000000000000000000000000000001"}

## Rollback

Stop making cooperative CLI calls from the invoking manifest and retain native
dispatch behavior. This immediately removes instrument/shadow mediation; it
does not activate enforcement. The ledger is disposable local metadata. After
all CLI processes have stopped, it may be retained for evidence, archived
locally, or removed together with its SQLite WAL and shared-memory companions
from the Git common directory. No application rollback or database migration is
needed.

A corrupt or unsupported ledger is never overwritten automatically. Preserve
it if evidence is needed, move it aside locally, and run explicit init to create
a new schema-v1 ledger. Instrument/shadow reports state_missing, state_corrupt, or state_unsupported
with launch_authorized true; only a future separately approved enforce mode
could fail closed on unavailable state.

## Local and Cloud parity and limits

Local and Cloud use the same checked-in policy, pure evaluator, CLI, Work
Contract recomputation, manifests, JSON surface, reason codes, and ledger
semantics. Each clone or ephemeral Cloud checkout has its own Git-common-dir
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
9. kill-switch inactive/active behavior; and
10. Local and Cloud cooperative coverage with unmediated activity explicitly
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
