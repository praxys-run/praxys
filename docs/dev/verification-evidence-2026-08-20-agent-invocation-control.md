# Verification Evidence: Agent Invocation Control v1

- **artifact_type:** `verification-evidence`
- **owner_role:** `quality`
- **verification_date:** `2026-08-21`
- **verdict:** PASS for cooperative instrument/shadow only
- **reviewed_repository:** `praxys-run/praxys`
- **reviewed_branch:** `copilot/agent-invocation-control-shadow`
- **reviewed_commit:** `07d45ceb0801da365c7ce37e10afc7f719d9a5c4`
- **baseline:** `origin/main` at `de746503532421cbcfe008993fa95b51418ea306`
- **reviewed_tree:** `59211e9fda3b8f4a23133f13af8fa3c2d50bd9be`
- **draft_pr:** `#737`

## Independence and attribution

Quality independently inspected and tested the exact committed tree above. This
verification did not rely on Engineering conclusions and did not modify the
implementation, configuration, manifests, tests, accepted Meta/Eval or
Architecture artifacts, or PR state.

The only pre-existing working-tree difference was `plugins/praxys`. The PR tree
and `origin/main` both pin that gitlink to
`a074ce4f018d3811f9f8af840c156ff98a335dd9`; the local submodule checkout is
`7cbaa021234a62a59199ee4e7b45663108f7dc34`. It was excluded from attribution
and was not touched, reset, updated, staged, or overwritten.

## Governing decision and authorization

The independent Decision Review Router result was `human-review-required`.
The recorded approval at `2026-08-20T23:38:10.880+08:00` is:

> I approve policy-change-proposal-agent-invocation-control-v1 at sha256:d6b9a136b44ae52d993ae07dd0000d946e201f73ea1b4db5cb116f01bab9e0f6 for instrument/shadow implementation only.

This verification does not widen that approval. Enforcement, native
interception, autonomy promotion, bound tuning, operating-model version
changes, and final implementation-bound ADR approval remain deferred.

## Recomputed Work Contract

Independent execution of `scripts/route_agentic_task.py` returned exactly:

- routing version `praxys-task-routing-v1`
- operating-model version `praxys-agentic-operating-model-v1`
- primary object `agent-system`
- impacts `[repository-change, agent-policy-or-autonomy, architecture-boundary]`
- risk triggers `[irreversible-or-high-blast-radius-action, out-of-policy-or-out-of-distribution-decision]`
- classification digest `sha256:3d80f3eca01b1bff2207d6e28cefe8daa3cdfc9f3480c80b99bd3f252dde35a2`
- primary loop `meta-eval`; nested loops `[delivery]`
- lead `meta-eval`; contributors `[architecture]`; executors `[engineering]`; verifiers `[quality]`
- required artifacts `[evaluation-report, implementation-impact-map, implementation-change, verification-evidence, policy-change-proposal, architecture-decision-record]`
- decision review required through `.github/agents/decision-review-router.agent.md`
- route digest `sha256:dfe65e8c108c06411ad84d7e7d8ec32d8206429780243973a31e840fb7c11f51`

The routing implementation, routing configuration, operating model, autonomy
policy, and Decision Review Router were unchanged by the reviewed commit.

## Acceptance matrix

| # | Result | Independent evidence |
|---:|---|---|
| 1 | PASS | Admission uses SQLite WAL and `BEGIN IMMEDIATE`; the gated six-OS-process test durably produced one `admit`, five `duplicate_active`, six decisions, and six authorized active attempts. Ordinary instrument/shadow candidate denials remain authorized; only the kill switch returns `launch_authorized=false`. |
| 2 | PASS | Focused tests cover direct and indirect cycles; depth 6/7; active 8/9; logical 32/33; attempts 3/4; first and repeated same-fingerprint retry; two identical terminal fingerprints; kill switch; missing, corrupt, and unsupported state; parent mismatch; active children; leaf-first recovery; idempotent finish; and conflicting finish. |
| 3 | PASS | A completed stable slot resumes under a changed generation and new logical identity. Slot ancestry ignores generation, so direct and indirect changed-generation cycles still produce `ancestry_cycle`. |
| 4 | PASS | The new control core and ledger use Python stdlib facilities, including `sqlite3`; no dependency or requirements file changed. Existing internal routing imports are reused. |
| 5 | PASS | Exact request key sets reject unknown content fields. The strict schema contains only bounded roles, opaque IDs and fingerprints, versions/digests, lifecycle, reasons, booleans, depth, and times. Tests verify WAL, foreign keys, schema columns, sentinel rejection, and absence from persisted database/WAL files. |
| 6 | PASS | Exact route recomputation matched both supplied digests and composition. Regression tests preserve routing, autonomy default-human behavior, role/reviewer independence, and the executor/verifier split. Protected routing and Decision Review paths have zero PR diff. |
| 7 | PASS | Manifests, machine-readable parity configuration, and developer docs consistently say cooperative repository mediation, instrument/shadow only, per-clone state, unknown unmediated activity, and no native/global enforcement. Static Local/Cloud parity passed. |
| 8 | PASS | The Evaluation Report, Policy Change Proposal, proposed ADR, and Engineering impact/change document record the exact decision trail, approval, digests, activation, rollback, explicit leaf-first recovery, stable reasons and limits, five-root/seven-day observation plan, replay corpus, zero-false-block/escape/correction bar, and all deferrals. |
| 9 | PASS for pre-commit scope | Focused and complete relevant policy/routing/parity/preflight tests, route recomputation, static parity, compilation, protected-boundary diff, and diff checks passed. Final all-tests preflight and GitHub checks were intentionally not claimed and remain post-artifact-commit work. |
| 10 | PASS | `plugins/praxys` is absent from the PR diff, and its gitlink is identical at baseline and reviewed head. The unrelated dirty local submodule was not changed. |

## Challenged semantic findings

- `scripts/agent_invocation_control.py:886-888` recomputes and validates the
  Work Contract before loading policy or connecting to the ledger. The
  mismatched-route/missing-ledger test confirms observable precedence.
- Ancestry walks active parent attempts and compares stable slot IDs, not
  generations (`scripts/agent_invocation_control.py:589-609`). A generation
  cannot launder a nested slot cycle.
- Logical identities bind to contract and slot; every attempt has a distinct
  attempt identity. Attempt limits count by logical identity. Retry provenance
  requires a failed attempt in the same logical invocation; the
  same-fingerprint retry budget aggregates by stable slot and fingerprint.
  No-progress aggregates the two newest terminal fingerprints by stable slot.
  An exploratory scope probe confirmed that a new logical identity does not
  reset the stable-slot retry budget or no-progress history, while a different
  slot has an independent retry budget.
- Policy, decision, and machine reason namespaces are closed in the pure core,
  checked by response construction, mirrored exactly in durable docs, and
  exercised by a reason/mapping probe. Every ordinary candidate reason is
  non-blocking in instrument/shadow; `kill_switch_active` alone is blocking.
- A readable ledger with a changed schema or policy version reports
  `state_unsupported`; missing metadata or tables reports `state_corrupt`.
- Finish and recovery use immediate transactions, require active children to
  close first, and are idempotent only for an identical terminal transition.
  No lease, heartbeat, age inference, or timeout recovers an attempt.
- `enforce` returns exit 5 with `enforcement_unavailable` and null decision
  fields; it is not aliased to instrument or shadow.
- The commit changes no application DB, migration, API, service, deployment,
  dependency, routing implementation/configuration, autonomy policy, Decision
  Review behavior, or plugin gitlink.

## Commands and results

All commands were run from the repository root against the reviewed head.

```text
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
git branch --show-current
git submodule status plugins/praxys
```

Result: correct branch; HEAD
`07d45ceb0801da365c7ce37e10afc7f719d9a5c4`; baseline
`de746503532421cbcfe008993fa95b51418ea306`; only pre-existing dirty
`plugins/praxys` reported.

```text
git diff --name-status origin/main...07d45ceb0801da365c7ce37e10afc7f719d9a5c4
git diff --stat origin/main...07d45ceb0801da365c7ce37e10afc7f719d9a5c4
```

Result: 12 attributed files, 3,039 insertions, no deletion, and no
`plugins/praxys` entry.

```text
.venv/bin/python scripts/route_agentic_task.py --primary-object agent-system --impact repository-change --impact agent-policy-or-autonomy --impact architecture-boundary --risk-trigger irreversible-or-high-blast-radius-action --risk-trigger out-of-policy-or-out-of-distribution-decision
```

Result: exact Work Contract and digests recorded above; exit 0.

```text
.venv/bin/pytest -q tests/test_agentic_invocation_control.py
```

Result: `15 passed in 6.55s`; exit 0.

```text
.venv/bin/pytest -q tests/test_agentic_invocation_control.py tests/test_agent_policy.py tests/test_agentic_task_routing.py tests/test_agentic_operating_model.py tests/test_decision_agents.py tests/test_copilot_execution_parity.py tests/test_agent_preflight.py
```

Result: `57 passed in 6.79s`; exit 0.

```text
.venv/bin/python scripts/check_copilot_environment_parity.py
```

Result: `Copilot execution parity passed (static).`; exit 0.

```text
.venv/bin/python -m py_compile analysis/agentic_invocation_control.py scripts/agent_invocation_control.py tests/test_agentic_invocation_control.py
git diff --check origin/main...07d45ceb0801da365c7ce37e10afc7f719d9a5c4
```

Result: no output; both exited 0.

```text
git diff --exit-code origin/main...07d45ceb0801da365c7ce37e10afc7f719d9a5c4 -- analysis/agentic_task_routing.py scripts/route_agentic_task.py config/agentic-task-routing.json config/agentic-operating-model.json config/agent-loop-policies.json .github/agents/decision-review-router.agent.md requirements.txt api db alembic deploy infra plugins/praxys
git diff --exit-code origin/main...07d45ceb0801da365c7ce37e10afc7f719d9a5c4 -- plugins/praxys
```

Result: both exited 0. Baseline and head both contain plugin gitlink
`a074ce4f018d3811f9f8af840c156ff98a335dd9`.

A separate reason-mapping probe exercised all ten candidate policy reasons.
It observed `launch_authorized=true` for `admit` and every ordinary hypothetical
deny, `launch_authorized=false` only for `kill_switch_active`,
`shadow_would_deny_cycle` only for ancestry cycles, the generic shadow policy
limit code for other hypothetical denials, and `instrument_recorded` for
ordinary instrument results. A separate scope probe observed:

```text
logical1-first-retry admit
same-slot-new-logical-retry retry_fingerprint_limit
different-slot-retry admit
same-slot-new-generation-logical-no-progress no_progress
```

The unqualified `python` executable and `rg` were unavailable in this
environment during initial discovery. Authoritative Python commands were rerun
successfully with `.venv/bin/python`; `grep` and `find` were used for discovery.
This caused no validation gap.

## Limitations and residual risk

- This is cooperative repository mediation only. Native, user, platform, and
  otherwise unmediated launches remain possible and unobserved.
- The ledger is local to one Git common directory and has no cross-machine or
  global authority.
- The candidate retry and no-progress scopes still require replay and observed
  human reconciliation; passing deterministic tests is not outcome evidence.
- No five-root/seven-day instrument-shadow observation, live Cloud invocation,
  native interception, enforcement trial, or final ADR approval was performed.
- Final all-tests preflight and GitHub checks must run after this Quality
  artifact is committed, as required by the delivery sequence.

## Release recommendation

**Recommend release of this draft implementation for cooperative instrument and
shadow evaluation only**, after committing this Quality-owned evidence and
then passing the final all-tests preflight and required GitHub checks. Do not
activate enforcement, claim native/global interception, tune bounds, promote
autonomy, change the operating-model version, or treat the proposed ADR as
finally approved.

No implementation blocker was found within the human-authorized scope.
