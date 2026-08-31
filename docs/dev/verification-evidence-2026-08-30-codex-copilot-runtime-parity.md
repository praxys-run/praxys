# Verification Evidence: Codex/Copilot runtime parity implementation

- **id:** `VE-2026-08-30-codex-copilot-runtime-parity-v1`
- **schema_version:** `1`
- **artifact_type:** `verification-evidence`
- **owner_role:** Quality
- **verification_date:** `2026-08-30`
- **status:** Pass for the approved static implementation-and-verification scope
- **implementation_state:** uncommitted worktree candidate
- **proposal:** `policy-change-proposal-codex-copilot-runtime-parity-v1`
- **proposal digest:** `sha256:47a829962a21e17833feac0c3473ecb749c7b7e0ce4bff3aa2611ee1a92de8cd`
- **decision subject digest:** `sha256:a04df7cd96ec682efa4694792e488c342a665c8356338054c3f9e91bf140fddc`
- **classification digest:** `sha256:ee6c38eebb7b9db2aedf6b824bc23d5d966e08045fc0e2830196e4a13eb0bcdd`
- **route digest:** `sha256:6d0f0f33ea72fc440558b883ca293408fd1508011b4f0970495a49ba13b743e2`

## Independence and reviewed subject

Engineering prepared the implementation. Independent Quality ran in a
separate ephemeral Codex CLI session with no write authority over the source
implementation worktree. The original worktree was reviewed read-only. Because
the legacy read-only sandbox also made `/tmp` read-only and prevented pytest
from collecting, the test pass ran with workspace-write limited to a disposable
`/tmp` snapshot instead.

Before that run, the executor compared the source worktree and snapshot using
sorted SHA-256 inventories for every non-Git, non-cache regular file and sorted
symlink path/target inventories. All 1,250 file entries and all four symlink
entries matched. The independent session could write only the disposable
snapshot and `/tmp`; it did not edit, stage, or commit the source worktree and
did not access the sibling worktree or invocation-control ledger.

Quality directly reviewed the approved proposal and decision subject, ADR,
Trust Decision Record, Evaluation Report, `AGENTS.md`, runtime documentation,
runtime-neutral contract, validator, CLI entry point, tests, all 13 Codex agent
adapters, Codex project config and hook, canonical agent manifests, Copilot
contracts, and four skill aliases.

## Findings and corrections

The first independent negative review found one high-severity issue: approval
validation accepted any proposal text containing only the proposal ID and
decision-subject digest. Engineering corrected this by binding the complete
approved proposal SHA-256 as a v1 invariant, retaining the separately pinned
decision-subject SHA-256, and adding an adversarial test that replaces the
proposal with only those two former tokens. Independent Quality confirmed that
the replacement now fails closed with
`approved policy proposal digest differs from runtime contract`.

No blocking finding remained in the final independent review.

## Verification results

Independent Quality recorded:

- `python3 scripts/check_agent_runtime_parity.py` — passed;
- `python3 scripts/check_copilot_environment_parity.py` — passed;
- `python3 -m pytest tests/test_agent_runtime_parity.py tests/test_copilot_execution_parity.py tests/test_agentic_task_routing.py tests/test_agentic_operating_model.py -q`
  — 45 passed in 13.11 seconds;
- full proposal and subject SHA-256 values — both matched the approved values;
- approval-token bypass adversarial test — passed; and
- release recommendation — pass for the verified static runtime-parity scope.

Executor-side supporting evidence on the same frozen implementation included:

- the same 45-test focused suite — passed;
- the focused suite plus `tests/test_agentic_invocation_control.py` — 60 passed
  in 35.02 seconds;
- Python compilation of the new analysis, script, and tests — passed;
- `git diff --check` — passed;
- Codex CLI `0.151.0` isolated configuration discovery — project config parsed,
  two MCP servers discovered, and no agent, hook, MCP, or skill startup warning;
- native MCP projection — both portable servers registered and disabled at the
  root project layer, with role adapters enabling their complete required
  transports and exact tool allowlists;
- native environment filtering probe — a synthetic `AZURE_CLIENT_ID` was absent
  from a Codex sandbox child while core `PATH` remained present; no environment
  values were printed; and
- all four `.agents/skills/*` aliases — relative, repository-contained, resolved
  to the declared canonical skill, and contained `SKILL.md`.

## Acceptance coverage

The verified contract detects or rejects:

- proposal or decision-subject digest drift and rebinding of the recorded human
  approval;
- drift between the approved subject, canonical Work Contract, control plane,
  required parity, Trust boundary, and implementation scope;
- weakened human-review routing or proposer/executor/verifier independence;
- missing, duplicated, malformed, copied, or drifting Codex agent adapters;
- widening of the v1 read-only, accepted-artifact-only, or implementation role
  scopes;
- MCP server, command, argument, role scope, tool allowlist, or environment
  widening, including excluded production/personal servers and wildcards;
- malformed or drifting Codex project configuration or Impeccable hook;
- missing, unexpected, absolute, broken, redirected, or repository-escaping
  skill aliases;
- deterministic classification, route, artifact, role, or Decision Review
  drift; and
- regressions in the existing Copilot Local/Cloud static parity contract.

## Invocation-control and probe evidence

Every direct status/admission observation of the existing shared
invocation-control ledger returned exit code 4 with
`policy_reason=state_corrupt`; admissions also returned
`launch_authorized=true`. The ledger was not deleted, initialized, recovered,
moved, or recreated. Under the accepted instrument/shadow policy this remains
visible, non-blocking evidence and cannot support a global-enforcement claim.

Before implementation edits, the fixed-text subagent probe was instructed to
return `PRAXYS_CODEX_SUBAGENT_PROBE_OK` exactly. It returned
`FIXED_TEXT_SUBAGENT_PROBE_OK`. This was not treated as an exact-echo success;
it remains runtime-variance evidence and is outside the static conformance
claim.

## Residual risks and recommendation

This evidence establishes static adapter conformance only. It does not prove
equivalent prose, sampling, latency, token use, native tool behavior, complete
invocation mediation, or runtime outcomes. External GitHub/Copilot Cloud
settings and live Cloud execution were not exercised. Measured parity still
requires the accepted minimum of five paired representative tasks over at
least seven calendar days, and cannot be promoted from this run.

The source worktree remains an uncommitted candidate, so default-branch
activation, CI, and post-merge Cloud smoke evidence do not exist. Final human
diff review remains required before activation. Within those limits, Quality
recommends **pass** for the approved implementation-and-verification scope.

## 2026-08-31 lifecycle follow-up evidence

The runtime parity implementation now includes a versioned, runtime-specific
lifecycle profile under top-level contract schema 2 and a pure Codex dispatch
evaluator. Schema 1 readers refuse the new discriminator instead of ignoring
the profile. The Codex profile uses a
four-thread session bound, allows only independent read-only parallel siblings,
serializes writes and dependency chains, follows up active logical work, queues
on capacity exhaustion, requires leaf-first parent cleanup, forbids automatic
relaunch after uncertain termination, limits replacement to one explicit
non-chaining attempt, and requires fresh read-only Quality/Trust verification.
It explicitly excludes the Copilot `bind_native`, `native_read`, `read_claim`,
and `read_agent` protocol.
Native child operations are confined to the Orchestrator and Change Loop
adapters; other roles return handoffs. The pure evaluator defaults unknown
capacity, dependency, active-sibling, target, and reviewer facts fail closed
and does not claim launcher interception or atomic runtime enforcement.
It derives read-only eligibility from the target adapter, validates the opaque
contract/slot/revision work key and native target observations, binds reviewer
freshness to target role and history provenance, rejects unauthorized or
consumed replacement, and computes leaf-first cleanup or an explicit incomplete
result from the inspected native tree.
Static validation binds the exact lifecycle decision subject
`sha256:dbec4d3433d2336631c519f7571e16b42ebe4efa63503e6df790d7b620ddfb43`
and complete proposal
`sha256:8fdc118d5447dc3b8797eefe7cf045f9c70ba257a0cafa38efe6d94c743f4ce3`;
the packet records candidate preparation authority, a pending
`human-review-required` decision, and no digest-bound human approval claim.

Focused implementation tests cover the dispatch matrix and reject thread-limit
drift, lifecycle guidance drift, missing Copilot-protocol prohibition, parallel
write policy, duplicate spawn in place of follow-up, capacity-triggered
replacement, inherited/writable reviewer threads, and dependency/write races.

Executor validation on the frozen candidate recorded:

- `python3 scripts/check_agent_runtime_parity.py` — passed;
- `python3 scripts/check_copilot_environment_parity.py` — passed;
- `python3 -m pytest tests/test_agent_runtime_parity.py -q` — 60 passed after
  rebasing onto the Microsoft MCP extension baseline and resolving both
  runtime-parity test sets;
- runtime-parity, Copilot-parity, routing, operating-model, and #745
  invocation-control regression suite — 350 passed on the rebased candidate;
- `python3 -m pytest tests/ -q` — 2974 passed, 53 skipped on the rebased
  candidate after initializing the repository-pinned `plugins/praxys`
  submodule;
- the two tests that initially failed only because that submodule was absent —
  both passed after the pinned checkout was initialized; and
- Python compilation and `git diff --check` — passed.

The pre-rebase independent read-only implementation review returned PASS with
no findings on tracked patch
`sha256:da928e86529c32484e862d012c1ac9cb998739f02cdeca97f4bc06f47615c1d8`.
It independently reproduced rejection of Engineering `read_parallel` across
inactive, no-capacity, unknown, active-addressable, and active-unavailable
states; rejection of missing and duplicate target adapters; and authorization
of valid independent, fresh, read-only Quality work. It also rechecked the
complete Copilot policy and pending lifecycle authority, ran 18 focused tests,
and verified both lifecycle packet digests. The reviewer made no file change.
Cooperative observation staleness remains an explicitly documented residual
limitation, not a native-enforcement claim. The pre-rebase review is supporting
evidence only; the rebased final diff requires its own independent read-only
review.

`TZ=UTC python3 scripts/agent_preflight.py --base origin/main` could not select
the uncommitted working-tree diff because `HEAD` still equals `origin/main`; it
reported `no changed files found for the requested diff` before running its
suite. The full pytest and diff checks it would select for these non-UI paths
were run directly. Exact-commit preflight and clean-worktree evidence remain
required after the candidate is committed; no activation or merge PASS is
claimed here. Independent review of the rebased final diff and the still-pending
human decision remain separate gates.

### Final rebased independent read-only review

A fresh, independent Codex CLI reviewer inspected all 14 staged files against
`HEAD` `9faeb79f7de27000358aaf0c45c39d472a626dbd` with the staged patch frozen at
`sha256:f6ec6be9dd258a9473bf339965d4dd175c62097bb78cd19199bbada5ddc55592`.
It returned **PASS with no findings** and left that frozen digest unchanged.
The review confirmed schema-2 composition with the Microsoft MCP extension,
write-scope-before-dispatch ordering, fail-closed logical identity, follow-up,
replacement, capacity, reviewer freshness, cleanup, coordinator scope, exact
Copilot lifecycle policy, pending human authority, and non-enforcement claims.
It also confirmed that Azure MCP remains root-disabled, Operations-only,
environment-free, pinned read-only, and exact-tool-scoped.

The read-only reviewer reran both static parity checks, 27 focused cases that
did not require a writable fixture directory, in-memory compilation, and
`git diff --cached --check`. Independent mutation/reproduction checks covered
49 dispatch decisions, three identity rejects, seven cleanup failures, five
extension widenings, and eight policy or authority widenings. Fixture-copy
tests could not run inside that reviewer's enforced read-only temporary
environment; the executor's complete 60-test focused run, 350-test related
run, and 3,027-outcome full suite cover those paths. The reviewer reconciled
the full-suite count with the pytest node cache: 2,974 passed plus 53 skipped
equals the 3,027 recorded outcomes; the current one-item collection difference
is a stale pre-parameterization cache node, not an evidence contradiction.

This paragraph is an evidence-only append after the frozen review. It does not
alter the reviewed implementation, policy, authority packet, or lifecycle and
MCP contracts. Exact-commit preflight, exact-subject human approval, activation,
and merge remain pending.

### PR code-review follow-up

The pre-PR review found and corrected two concrete fail-closed implementation
gaps after the frozen review above:

1. Cleanup validated the requested parent as though it had to be the root of
   the supplied tree. A valid complete native tree therefore returned
   `tree_state_invalid` whenever the cleanup target was a non-root parent or
   the tree contained a sibling branch. Cleanup now validates the complete
   single-root tree first and then collects only the requested parent's active
   descendants leaf first. A regression test supplies a root, non-root cleanup
   parent, two descendant levels, and an active sibling, and verifies that only
   the target subtree is returned.
2. A malformed Copilot lifecycle JSON document escaped static validation as an
   uncaught decode error. The lifecycle projection now converts malformed JSON
   into the explicit fail-closed error `Copilot lifecycle profile is invalid`,
   with a regression test.
3. Pydantic's default boolean coercion allowed untrusted observation strings
   such as `"yes"` and `"true"` to become true capacity, prerequisite, peer-
   absence, or active-thread facts. The dispatch and native-tree observation
   models now use strict validation, and regression assertions reject string
   and integer substitutes before either evaluator can authorize an action.
4. `read_parallel` initially derived eligibility only from an adapter's direct
   `write_scope`. That would classify the two coordinator adapters as read-only
   even though they uniquely hold transitive authority to dispatch write-capable
   children. Dispatch now excludes every lifecycle coordinator from
   `read_parallel`, and regression coverage rejects both Praxys Orchestrator and
   Praxys Change Loop while retaining ordinary read-only worker eligibility.

The review session also exposed two orchestration limitations rather than
repository implementation findings. Several intermediate native agent messages
arrived with an empty payload even though later final delivery succeeded. In
addition, agents instructed cooperatively to remain read-only wrote unstaged
changes because their inherited workspace sandbox was not itself read-only.
Those unauthorized changes were isolated through the index/worktree split and
restored exactly to the staged candidate; neither lifecycle decision artifact
changed, and their bound SHA-256 values remained
`dbec4d3433d2336631c519f7571e16b42ebe4efa63503e6df790d7b620ddfb43` and
`8fdc118d5447dc3b8797eefe7cf045f9c70ba257a0cafa38efe6d94c743f4ce3`.
Empty message payloads cannot count as review evidence, and a prose read-only
instruction cannot substitute for a native read-only sandbox. These are
additional runtime-variance observations under the existing cooperative and
non-enforcement limitations; they do not authorize importing Copilot's claimed-
read workaround or changing the pending authority packet.

Two test suites were briefly started in parallel during review and interfered
through shared repository test state. Their failures are invalid evidence and
were not accepted or hidden by a blind retry. After stopping every reviewer and
test process, restoring the single staged candidate, and running sequentially,
the post-fix results were:

- `python3 -m pytest tests/test_agent_runtime_parity.py -q` — 62 passed;
- runtime-parity, Copilot-parity, routing, operating-model, and invocation-
  control regression suite — 352 passed;
- `python3 -m pytest tests/ -q` — 2,976 passed, 53 skipped;
- both static parity entry points — passed; and
- Python compilation — passed.

The 2,976-test full-suite result preceded the strict observation-model fix in
item 3 and the transitive-coordinator fix in item 4. After those fixes, the
64-test focused suite, explicit coercion and coordinator probes, and both static
parity entry points passed. The final committed tree still requires the
repository's full exact-commit preflight; the earlier full-suite result is not
substituted for that gate.

The earlier frozen hashes and counts remain historical evidence for the
pre-review candidate only. A fresh independent review of the corrected staged
diff, followed by exact-commit preflight, is required before PR handoff. Human
exact-subject approval, activation, and merge remain pending.
