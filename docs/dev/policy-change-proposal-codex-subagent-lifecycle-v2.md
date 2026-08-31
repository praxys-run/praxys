# Policy Change Proposal: Codex subagent lifecycle v2

- **id:** `policy-change-proposal-codex-subagent-lifecycle-v2`
- **schema_version:** `1`
- **artifact_type:** `policy-change-proposal`
- **owner_role:** Meta/Eval
- **status:** Proposed; candidate implementation requested, exact-subject human review pending
- **proposal_date:** `2026-08-31`
- **decision subject:** `docs/dev/codex-subagent-lifecycle-decision-v2.json`
- **decision subject digest:** `sha256:dbec4d3433d2336631c519f7571e16b42ebe4efa63503e6df790d7b620ddfb43`

## Decision and authority

Adopt PR #745's portable lifecycle goals for Codex while using Codex-native
thread identity, completion delivery, follow-up, wait, interrupt, and tree
inspection. Retain the Copilot repository ledger unchanged. The user approved
the decision-complete plan, selected safe parallelism, and explicitly requested
implementation on 2026-08-31. That authorizes preparation and verification of
this bounded candidate. The independently reproduced route remains
`human-review-required`; the exact subject has not yet received human approval,
and no digest-bound approval is claimed. Activation or merge remains closed.

The recomputed Work Contract has classification digest
`sha256:ee6c38eebb7b9db2aedf6b824bc23d5d966e08045fc0e2830196e4a13eb0bcdd`
and route digest
`sha256:6d0f0f33ea72fc440558b883ca293408fd1508011b4f0970495a49ba13b743e2`.
Meta/Eval owns the proposal, Architecture and Trust constrain it, Engineering
implements it, and independent Quality verifies it.

## Accepted behavior

- Key logical work by stable opaque contract ID, stable role-slot ID, and
  immutable artifact digest or Git head. Follow up an addressable active target;
  otherwise queue incomplete work without relaunching.
- Allow parallel direct siblings only when each is independent and read-only.
  Serialize writes and dependency chains; unknown capacity, prerequisites,
  sibling absence, target addressability, or reviewer identity fails closed.
- Limit a session to four spawned-agent threads. Capacity exhaustion queues and
  never authorizes replacement.
- Interrupt descendants leaf first on parent abort, shutdown, failure, or
  replacement. Unconfirmed termination cannot authorize relaunch.
- Allow one explicit, non-chaining replacement only after termination or loss is
  confirmed.
- Start Quality and Trust verification in a distinct, fresh, read-only thread
  without executor conversation history.
- Permit only Praxys Orchestrator and Praxys Change Loop to operate native Codex
  children. Other roles return handoffs to their parent coordinator.
- Never use the Copilot `bind_native`, `native_read`, `read_claim`, or
  `read_agent` protocol for Codex.

## Boundaries and evidence

The pure dispatch evaluator and static checks are a testable projection, not a
native launcher, atomic cross-process lock, persistent registry, or global
interceptor. The existing role, route, artifact, Decision Review, Trust, and
human-authority boundaries remain unchanged. Activation, release, merge,
autonomy promotion, measured parity, and changes to the Copilot ledger are not
authorized. Runtime outcome claims still require at least five paired tasks over
seven days.

The exact implementation paths, profile, non-goals, request context, and pending
review state are
in the digest-bound decision subject. Static validation binds both the subject
and this complete proposal before accepting runtime-parity schema 2.
