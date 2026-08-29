# ADR-2026-08-20-agent-invocation-control

- **Status:** Proposed — instrument/shadow scope human-authorized; final implementation-bound ADR approval pending separate review
- **Decision date:** 2026-08-20
- **Artifact implementation status:** repository-native Markdown; not schema-backed
- **Owner role:** Architecture

## 2026-08-29 bounded architecture addendum

Architecture accepts a schema-v1 additive correction for lifecycle-aware,
manifest-coordinated calls:

- serialize admission with `BEGIN IMMEDIATE` so one non-null parent attempt has
  at most one active direct child, without serializing roots or unrelated
  parents;
- keep omitted dispatch fields compatible as sync, while cooperative manifests
  explicitly use `sync`/`sync_inline` or the sole accepted background pair
  `background`/`background_independent_immediate_no_poll`;
- split sync inline return from background notification-driven one-read
  completion, with no polling or `read_agent(wait:true)` loops;
- keep `nat_*` as a repository alias and bind it to a domain-separated SHA-256
  fingerprint of the exact public ID returned by successful `task`;
- require attempt ID, alias, and exact public ID for notification, read, and
  observation; and
- add explicit binding invalidation for shutdown, resume, and context
  replacement without registry lookup, automatic loss, replacement, relaunch,
  or external rebind.

The change keeps JSON schema 1 and ledger schema 1 by adding auxiliary tables
and a transactional `init` upgrade for #745-era lifecycle ledgers. Schema v2,
context epochs, keyed/native ID formats, generalized alias/rebind design, and
external rediscovery are explicitly deferred as overbroad. A future exact-match
native capability would require separate architecture and policy review.

## Decision record

- **id:** `ADR-2026-08-20-agent-invocation-control`
- **schema_version:** `1`
- **decision_type:** `architecture-decision-record`
- **owner_role:** `Architecture`
- **question:** Should Praxys add repository-owned mediated agent invocation admission for instrument/shadow evaluation now, and, if so, what architectural boundaries and machine-stable contracts constrain that implementation without broadening the authorized scope?
- **options:**
  1. Status quo with no mediated ledger.
  2. Repository-owned mediated invocation admission with a pure, I/O-free identity/policy core, a thin CLI, and a local SQLite ledger under the Git common directory.
  3. Flat JSON/file ledger.
  4. Application database extension or a new service.
  5. Immediate native interception and enforcement.
- **recommendation:** Adopt option 2 for instrument/shadow scope only. Preserve the current repository architecture. Defer and do not decide enforcement, native interception, autonomy promotion, policy-bound tuning, operating-model version changes, and final implementation-bound ADR approval.
- **rationale:** The authorized scope needs local, worktree-safe mediated observation with deterministic contracts, durable lifecycle state, and concurrency-safe recovery, while avoiding a new service, dependency, or application datastore. A pure identity/policy core plus thin CLI and local SQLite ledger provides the smallest architecture change that still supports instrument/shadow evaluation, explicit recovery, and stable machine contracts. The short horizon is shadow-evaluation implementation only; the long-lived horizon is the stable v1 JSON, exit-code, reason-code, identity, and ledger semantics that future review can accept, revise, or supersede.
- **dependencies:**
  - Approved policy proposal subject and digest: `policy-change-proposal-agent-invocation-control-v1` at `sha256:d6b9a136b44ae52d993ae07dd0000d946e201f73ea1b4db5cb116f01bab9e0f6`.
  - Digest-bound Work Contract identified below, including classification digest `sha256:3d80f3eca01b1bff2207d6e28cefe8daa3cdfc9f3480c80b99bd3f252dde35a2` and route digest `sha256:dfe65e8c108c06411ad84d7e7d8ec32d8206429780243973a31e840fb7c11f51`.
  - Independent Decision Review Router outcome `human-review-required` and the recorded human approval below.
  - Downstream implementation artifacts: evaluation report, implementation impact map, implementation change, and verification evidence. Evaluation and policy artifacts are owned by Meta/Eval and are not modified here.
- **review_route:** Independent Decision Review Router outcome `human-review-required`; human authorization currently covers instrument/shadow implementation only and does not accept this final implementation-bound ADR.
- **outcome_plan:** Engineering implements only the accepted instrument/shadow scope. Meta/Eval compares shadow outcomes and mediated coverage without content persistence. Quality produces independent verification evidence. Any deferred decision requires separate independent/human review after implementation and verification evidence.
- **digest:** `sha256:d6b9a136b44ae52d993ae07dd0000d946e201f73ea1b4db5cb116f01bab9e0f6` — digest of `policy-change-proposal-agent-invocation-control-v1`, not a self-hash of this ADR.

## Work Contract binding

- **routing_version:** `praxys-task-routing-v1`
- **operating_model_version:** `praxys-agentic-operating-model-v1`
- **primary_object:** `agent-system`
- **impacts:** `[repository-change, agent-policy-or-autonomy, architecture-boundary]`
- **risk_triggers:** `[irreversible-or-high-blast-radius-action, out-of-policy-or-out-of-distribution-decision]`
- **classification_digest:** `sha256:3d80f3eca01b1bff2207d6e28cefe8daa3cdfc9f3480c80b99bd3f252dde35a2`
- **primary_loop:** `meta-eval`
- **nested_loop:** `delivery`
- **lead:** `meta-eval`
- **contributor:** `architecture`
- **executor:** `engineering`
- **verifier:** `quality`
- **required_artifacts:** `evaluation-report`, `implementation-impact-map`, `implementation-change`, `verification-evidence`, `policy-change-proposal`, `architecture-decision-record`
- **decision_review:** required
- **route_digest:** `sha256:dfe65e8c108c06411ad84d7e7d8ec32d8206429780243973a31e840fb7c11f51`

Every mediated admission evaluation must recompute this digest-bound Work Contract. Caller-supplied classification or route is not trusted. In instrument/shadow scope, a mismatch is structured evidence, not a blocker.

## Review and authorization boundary

Independent Decision Review Router outcome: `human-review-required`.

Recorded human approval timestamp: `2026-08-20T23:38:10.880+08:00`

> I approve policy-change-proposal-agent-invocation-control-v1 at sha256:d6b9a136b44ae52d993ae07dd0000d946e201f73ea1b4db5cb116f01bab9e0f6 for instrument/shadow implementation only.

This authorization is limited to implementation in instrument/shadow scope. It does not accept this final implementation-bound ADR. Final ADR approval is pending separate independent/human review after implementation and verification evidence.

Explicitly deferred and not decided here:

- enforcement;
- native interception;
- autonomy promotion;
- policy-bound tuning;
- operating-model version changes; and
- final implementation-bound ADR approval.

## Context, constraints, affected systems, and reversibility

The decision concerns the `agent-system` object and affects only repository-owned mediated invocation boundaries. The authorized near-term scope is a short shadow-evaluation horizon: implement instrument/shadow observation and hypothetical-admission evaluation without blocking native dispatch. The longer-lived horizon is the stable v1 machine contract surface for JSON I/O, exit semantics, reason-code semantics, identity semantics, and ledger lifecycle semantics.

Affected systems for the authorized scope are bounded implementation targets only: `config` policy, `analysis/agentic_invocation_control.py`, `scripts/agent_invocation_control.py`, focused tests, developer docs, cooperative agent-manifest integration, and Local/Cloud parity/limitation updates. These are implementation boundaries, not authorization for Architecture to edit them. This ADR does not authorize changes to `scripts/route_agentic_task.py` composition, Decision Review behavior, the application database, or `plugins/praxys`.

Reversibility is high. Cooperative integrations can be disabled. The local ledger is disposable observational/control metadata, not product or runtime truth, and has no cross-machine authority.

## Options considered

### 1. Status quo / no mediated ledger

Rejected for the authorized scope. It has the lowest migration cost, but it provides no durable mediated coverage, no local lifecycle record, no deterministic shadow-evaluation output, and no crash-recovery surface for cooperative integrations.

### 2. Repository-owned mediated invocation admission with pure core + thin CLI + local SQLite ledger

Recommended for instrument/shadow scope. It preserves the current repository architecture and keeps the policy/identity decision core pure and I/O-free. The CLI stays thin. The ledger lives under the Git common directory so worktree discovery is safe and local concurrency is coordinated without expanding product/runtime storage. Operational cost stays local and migration cost is reversible.

SQLite is required to run with WAL, foreign keys enabled per connection, and `BEGIN IMMEDIATE` around admission and lifecycle state transitions. The ledger is local observational/control metadata only, not portable truth across clones or machines.

### 3. Flat JSON/file ledger

Rejected. It appears simple but creates higher operational and migration cost for concurrency control, transactional state changes, leaf-first crash recovery, and durable lifecycle bookkeeping. It is materially weaker than SQLite for concurrent local attempts and idempotent recovery.

### 4. Application database extension or new service

Rejected for now. Either choice broadens the architecture boundary, increases privacy and operations scope, and turns a local mediated control into product/runtime infrastructure. That conflicts with the authorized scope and the requirement to avoid a new service, dependency, or application datastore.

### 5. Immediate native interception and enforcement

Deferred and not authorized. Repository tooling and cooperative manifests cannot intercept every platform-native agent invocation. Unmediated native calls remain possible and unobserved. Immediate interception/enforcement would overclaim repository authority, broaden the decision, and require separate review.

## Recommended architecture boundaries

- Preserve the current repository architecture.
- Use repository-owned mediated invocation admission with a pure, I/O-free identity/policy core separated from a thin CLI and a local SQLite ledger under the Git common directory.
- Add no new service, dependency, or application datastore.
- Recompute the digest-bound Work Contract before every mediated admission evaluation; do not trust caller-supplied classification or route.
- Use generation-independent Work Contract slot identity for ancestry and cycle detection. Runtime agent or generation identifiers cannot define ancestry.
- Treat logical invocation identity and attempt identity separately: one logical invocation spans retries, while every execution or retry has its own attempt identity.
- Persist no task, prompt, source-code, user, artifact, or free-form text. Limit ledger and machine output to versioned policy/route identifiers, digests, bounded role/slot identity, opaque invocation and attempt IDs, lifecycle states, reason codes, and necessary timestamps.
- Keep errors and diagnostic columns text-free. Trust must verify the privacy, path, and filesystem boundary before any broader use.

## Machine contract and state boundaries

All JSON input and output must be versioned.

Stable v1 exit contract:

- `0`: instrumentation/shadow evaluation completed, including a hypothetical deny;
- `2`: invalid request, schema, or identity;
- `3`: policy or Work Contract unavailable, invalid, or mismatched for evaluation;
- `4`: ledger, transaction, or recovery failure; and
- `5`: requested mode or required native notification capability unavailable
  or unapproved.

These meanings cannot be repurposed within v1. Ordinary candidate-policy
would-denials remain observational in instrument/shadow. Lifecycle protocol
violations added by the bounded addendum fail closed for cooperative dispatch;
this is not native interception and does not affect unmediated calls.

Stable v1 machine reason-code namespace:

- `instrument_recorded`
- `shadow_would_admit`
- `shadow_would_deny_cycle`
- `shadow_would_deny_policy_limit`
- `invalid_request`
- `invalid_identity`
- `work_contract_unavailable`
- `work_contract_mismatch`
- `policy_unavailable`
- `recovery_required`
- `ledger_unavailable`
- `enforcement_unavailable`
- `kill_switch_active`
- `ledger_initialized`
- `ledger_ready`
- `identity_created`
- `finish_recorded`
- `finish_idempotent`
- `recovery_recorded`
- `kill_switch_updated`
- `status_reported`
- `lifecycle_transition_rejected`
- `native_bound`
- `native_notification_recorded`
- `completion_notification_required`
- `native_notifications_unavailable`
- `native_read_authorized`
- `native_read_refused`
- `native_observation_recorded`
- `progress_recorded`
- `progress_idempotent`
- `tree_termination_recorded`
- `tree_termination_idempotent`
- `direct_sibling_active`
- `execution_provenance_invalid`
- `native_binding_mismatch`
- `native_binding_invalidated`
- `native_invalidated`

Meanings cannot change within schema v1. Additions are additive and require documentation and tests. Human or task text is not permitted as a reason. Exact policy bounds and tuning remain deferred to approved policy review.

## Consequences

The recommended design provides local durability, transactional lifecycle recording, explicit recovery, and concurrency coordination without changing the application database or introducing a service. Using the Git common directory keeps the ledger aligned with repository lifecycle and worktree-safe discovery.

The same design also has hard limits. It creates no cross-machine authority, no platform-wide denominator for all native invocations, and no claim of repository-native enforcement over unmediated calls. Reports must distinguish mediated coverage from all native invocation volume and must not claim platform-wide protection or a known total denominator.

## Activation boundaries

Only explicit instrument/shadow configuration and cooperative integrations may
activate this path. Instrument mode observes candidate-policy lifecycle and
identity; shadow mode computes the exact ordinary would-admit or would-deny
result without blocking dispatch. Direct-sibling conflicts, invalid dispatch
provenance, invalid lifecycle transitions, binding mismatch/invalidation, and
one-read violations are protocol correctness failures and do block the
cooperative action. Enforcement mode remains unavailable and cannot silently
alias to shadow or instrument.

## Rollback and migration

Rollback disables cooperative hooks and integrations. The disposable local ledger may be retained, archived, or deleted locally. Version mismatch must fail visibly. No irreversible migration is authorized here. Any incompatible ledger migration requires new review. Rollback never activates enforcement.

## Recovery boundary

Crash recovery is explicit and leaf-first: active descendant attempts close or recover before their ancestors, transactionally and idempotently. Elapsed time never implies a crash. No stale timeout or lease is authorized. A new shadow evaluation may report `recovery_required`, but cannot enforce or block.

## Handoffs

- **Engineering:** implement only the accepted instrument/shadow scope and preserve the architectural boundaries above.
- **Operations:** own future rollout and runtime consequences if a later review broadens scope; the current change adds no production service.
- **Trust:** verify privacy, filesystem, and path boundaries before any broader use.
- **Quality:** independently verify the deterministic pure core, Work Contract recomputation, concurrency and transactions, logical invocation versus attempt semantics, ancestry and cycle detection, recovery behavior, exit codes, JSON versioning, no-text persistence, shadow non-blocking behavior, unavailable enforcement behavior, and Local/Cloud parity and limitations.

## Outcome plan and review triggers

Meta/Eval compares shadow outcomes and measures mediated coverage, would-deny categories, false-positive and false-negative rates, human correction rates, and recovery or error rates without recording content. Quality produces verification evidence. Separate review is required before any deferred decision becomes active.

Trigger Architecture and independent review if any implementation proposes or demonstrates a need for:

- a new service, application database use, or cross-machine authority;
- incompatible ledger schema migration;
- enforcement or native interception;
- operating-model version changes;
- policy-bound tuning;
- privacy-scope expansion; or
- evidence that local SQLite is inadequate for the authorized scope.
