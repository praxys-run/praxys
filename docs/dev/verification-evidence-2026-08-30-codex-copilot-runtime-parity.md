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
