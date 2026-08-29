# Verification Evidence: Agent Lifecycle Hardening

- **artifact_type:** `verification-evidence`
- **owner_role:** `quality`
- **verification_date:** `2026-08-29`
- **verdict:** PASS for bounded cooperative instrument/shadow implementation
- **reviewed_repository:** `praxys-run/praxys`
- **reviewed_branch:** `copilot/fix-agent-lifecycle-management`
- **reviewed_commit:** `47bd3a8f8ca2fa466a87a316f2fb1ccf36ee2d81`
- **reviewed_tree:** `d3c7d455ccc2fb630c120c26cdc65b4ad0dc06b8`
- **baseline:** `origin/main` at `c99b3d45b4f15bda9ed8632ca40c78779875e089`
- **draft_pr:** `#745`

## Independence and scope

Praxys Quality independently inspected and tested the exact committed tree
above. Verification ran synchronously without child agents, background work,
implementation edits, commits, pushes, or pull-request state changes.
Engineering conclusions were not treated as evidence.

The review covers repository-owned cooperative mediation only. Native,
platform, user, and otherwise unmediated calls remain outside repository
authority and observability.

## Work Contract

Independent route recomputation returned:

- routing version `praxys-task-routing-v1`
- operating-model version `praxys-agentic-operating-model-v1`
- primary object `agent-system`
- impacts `repository-change`, `agent-policy-or-autonomy`, and
  `architecture-boundary`
- risk triggers `irreversible-or-high-blast-radius-action` and
  `out-of-policy-or-out-of-distribution-decision`
- classification digest
  `sha256:3d80f3eca01b1bff2207d6e28cefe8daa3cdfc9f3480c80b99bd3f252dde35a2`
- route digest
  `sha256:dfe65e8c108c06411ad84d7e7d8ec32d8206429780243973a31e840fb7c11f51`
- primary loop `meta-eval` with nested `delivery`
- lead `meta-eval`, contributor `architecture`, executor `engineering`, and
  verifier `quality`
- independent decision review remains required

The bounded correction's Decision Review route is `agent-resolved`. This
verification does not widen that route or authorize activation, enforcement,
release, or merge.

## Acceptance matrix

| Area | Result | Independent evidence |
|---|---|---|
| Parent-scoped concurrency | PASS | `BEGIN IMMEDIATE` protects admission. Concurrent processes admit at most one active direct child for the same non-null parent. Sequential nesting, unrelated parents, and roots remain independent. |
| Dispatch provenance | PASS | Lifecycle dispatch defaults to `sync`/`sync_inline`; partial, unknown, or mismatched pairs fail closed. Background accepts only `background`/`background_independent_immediate_no_poll`. Sync attempts cannot bind or read a native result. |
| Notification capability | PASS | `notifications_available=false` records `notifications_unavailable`; notification, read, and observation return `native_notifications_unavailable` with exit 5. No polling or weaker read path is supplied. |
| Public-ID binding | PASS | Binding requires `task_result`, a separate `nat_*` repository alias, the exact public ID, and a domain-separated SHA-256 fingerprint. Raw public IDs are absent from persisted SQLite and WAL content. Cross-attempt public-ID reuse is rejected. |
| Public-ID validation | PASS | Empty values, surrounding or internal ASCII/Unicode whitespace, controls, `call_*`, known placeholders, repository identities, and values over 512 UTF-8 bytes are rejected. Opaque non-UUID formats remain accepted. |
| Mismatch precedence | PASS | Attempt, alias, or public-ID mismatch is reported before invalidation or notification-capability state. Invalidated exact bindings report `native_binding_invalidated`. |
| Invalidation | PASS | Shutdown, resume, and context replacement invalidate the exact binding without lookup, rediscovery, inference, loss, replacement, external rebind, relaunch, or attempt-state mutation. |
| Loss and replacement | PASS | Authoritative `not_found` atomically records loss and leaf-first descendant cleanup. It creates one eligibility only for a non-replacement attempt; replacement is separately admitted, consumed once, and cannot chain. |
| Tree cleanup | PASS | Abort, shutdown, and failure use idempotent leaf-first termination, orphaning active descendants before the parent. No native cancellation is claimed. |
| Schema and migration | PASS | JSON and ledger schema remain v1 with additive lifecycle and auxiliary tables. Existing-ledger upgrades and new initialization validate before commit. Injected failures roll back schema changes. |
| Connection handling | PASS | Direct fault challenges confirmed explicit close for corrupt, unsupported, and SQLite prevalidation failures in both connection-opening paths. Failed auxiliary upgrade also rolled back and closed. |
| Legacy authentication | PASS | Upgraded native rows without binding provenance cannot authenticate, even when the old row remains present. |
| Dispatch reasons | PASS | Durable dispatch records distinguish `admit`, `policy_denied`, `direct_sibling_active`, and `lifecycle_transition_rejected`. Candidate-policy evidence remains in the decision record. |
| Stable machine contract | PASS | The implementation guide and ADR both include unavailable required notification capability in exit 5 and carry the complete `MACHINE_REASON_CODES` sequence. Tests enforce full equality. |
| Policy and parity | PASS | Policy, Evaluation, ADR, agent manifests, operations guidance, and Local/Cloud parity retain the same cooperative instrument/shadow protocol and limitations. |
| Scope containment | PASS | Routing, operating-model, autonomy, reviewer authority, starting limits, dependencies, application storage/API, deployment, infrastructure, and plugin boundaries are unchanged. |
| Durable claim hygiene | PASS | Added durable text contains no real one-off lifecycle IDs or rejected expansion JSON/digest. |
| Upstream claims | PASS | GitHub issues are community reports on the official tracker, not maintainer-confirmed causality, root cause, runtime fix, or fix verification. WSL2 is not asserted causal, and release-note silence is not treated as proof. |

## Prior blocker disposition

The independent review challenged and verified these corrections:

- internal ASCII and Unicode whitespace is rejected;
- existing and new ledger schema changes validate before commit and roll back
  on validation failure;
- every opened connection closes explicitly on corrupt, unsupported, and
  SQLite prevalidation failures;
- implementation and ADR exit 5 semantics include unavailable completion
  notifications;
- old native rows without provenance cannot authenticate;
- a public-ID fingerprint cannot be rebound across attempts; and
- the ADR and implementation documentation contain the complete stable
  machine-reason namespace.

## Commands and results

```text
/home/feitao/src/tf-personal-pensieve/praxys/.venv/bin/python -m py_compile \
  analysis/agentic_invocation_control.py \
  scripts/agent_invocation_control.py \
  tests/test_agentic_invocation_control.py
```

Result: exit 0.

```text
/home/feitao/src/tf-personal-pensieve/praxys/.venv/bin/python -m pytest -q \
  tests/test_agentic_invocation_control.py \
  tests/test_agent_policy.py \
  tests/test_agentic_task_routing.py \
  tests/test_agentic_operating_model.py \
  tests/test_decision_agents.py \
  tests/test_copilot_execution_parity.py \
  tests/test_agent_preflight.py
```

Result: `100 passed in 19.33s`, exit 0.

```text
/home/feitao/src/tf-personal-pensieve/praxys/.venv/bin/python \
  scripts/check_copilot_environment_parity.py
```

Result: `Copilot execution parity passed (static).`, exit 0.

```text
git diff --check origin/main...HEAD
```

Result: no output, exit 0.

Independent canonical digest recomputation matched both Work Contract digests.
A protected-boundary diff covering routing, operating model, autonomy, Decision
Review, dependencies, application/runtime storage, deployment, infrastructure,
and `plugins/praxys` returned no affected boundary. Direct fault injection
passed six explicit-close paths and confirmed failed auxiliary upgrades roll
back and close.

## Limitations and pending evidence

- The ledger is local to one Git common directory and has no cross-machine
  authority.
- No native registry lookup, cancellation, write, external rebind, or global
  interception exists.
- No runtime replay, five-root/seven-day observation, live shadow evaluation,
  native-runtime verification, activation, release, or merge was performed or
  claimed.
- Final `scripts/agent_preflight.py` and GitHub checks remain pending after this
  evidence is committed.

## Release recommendation

PASS for the bounded draft implementation and for proceeding to the
repository's final preflight and required GitHub checks. This verdict is not
approval for activation, enforcement, autonomy promotion, native/global
coverage claims, release, or merge.
