# Codex CLI and Copilot CLI runtime adapters

**Status:** implementation candidate; independent Verification Evidence and
final diff review are required before activation. This document does not claim
measured runtime parity.

## Approval and Work Contract

Implementation and verification are authorized only by
`policy-change-proposal-codex-copilot-runtime-parity-v1` for decision subject
digest
`sha256:a04df7cd96ec682efa4694792e488c342a665c8356338054c3f9e91bf140fddc`.
The parity contract also binds the complete approved proposal at
`sha256:47a829962a21e17833feac0c3473ecb749c7b7e0ce4bff3aa2611ee1a92de8cd`,
so retaining only its ID and subject digest cannot impersonate approval. The
approved decision JSON and proposal remain byte-for-byte unchanged.

The authoritative deterministic route is:

- classification digest:
  `sha256:ee6c38eebb7b9db2aedf6b824bc23d5d966e08045fc0e2830196e4a13eb0bcdd`;
- route digest:
  `sha256:6d0f0f33ea72fc440558b883ca293408fd1508011b4f0970495a49ba13b743e2`;
- primary loop: Meta/Eval, with the Delivery loop nested;
- contributors: Architecture and Trust;
- executor: Engineering;
- verifier: independent Quality; and
- decision review: required, with the already recorded bounded human approval.

The canonical operating model, router, roles, skills, artifacts, and review
policy remain authoritative. Runtime adapters may translate native file and
tool names but may not change those semantics.

## Codex local adapter

Codex loads the project layer only after the user trusts the checkout. The
project adapter contains:

- `.codex/config.toml`: `workspace-write` plus `on-request` defaults, the two
  portable MCP registrations, environment filtering, hooks, and multi-agent
  enablement;
- `.codex/agents/*.toml`: thin adapters that direct the child to read one
  canonical `.github/agents/*.agent.md` manifest before acting;
- `.agents/skills/*`: relative symlinks to canonical repository skill
  directories, with no copied skill bodies; and
- `.codex/hooks.json`: the Codex-native PostToolUse projection of the existing
  repository-owned Impeccable hook.

The root project layer registers Chrome DevTools and `praxys-local` as disabled.
The selected role adapter repeats the complete native MCP transport and enables
only the servers that role's canonical manifest permits. A required role MCP
server uses `required = true`, so startup fails instead of silently dropping an
affected required capability. Router-only roles load no MCP process.

Role adapters preserve separation:

- Praxys Orchestrator, Work Router, Decision Review Router, Change Loop,
  Quality, and Trust are read-only;
- artifact-owning roles may write only accepted artifacts that the exact Work
  Contract requires; and
- Engineering is the only adapter authorized to execute repository
  implementation. It cannot approve or independently verify that work.

Use Codex's native subagent selection after the root Praxys Orchestrator has
recomputed the Work Contract. Native thread controls are mechanics, not a new
authority or routing source.

## Portable capabilities and Trust limits

The portable MCP set is exact:

1. `chrome-devtools`: `chrome-devtools-mcp@1.6.0`, headless, isolated, usage
   statistics and CrUX disabled, network headers redacted, and only the common
   tools listed in `config/agent-runtime-parity.json` enabled.
2. `praxys-local`: the repository `local` synthetic profile, with only ten
   read-only product-data tools enabled.

`azure-mcp`, `statsig`, `praxys-dev-test`, wildcard tools, personal browser
sessions, production credentials, and production mutations are excluded.
Codex command children inherit a core environment with the default
`KEY`/`SECRET`/`TOKEN` filtering active, plus explicit exclusion of common
cloud, database, provider, athlete-connection, email, feature-flag, and
Copilot credential namespaces. The MCP registrations forward no inherited
environment variables.

A native Codex sandbox probe used only a synthetic `AZURE_CLIENT_ID` and exit
codes: the credential-shaped name was absent in the child while core `PATH`
remained present. No environment values were printed. The automated suite also
tests the same filters with placeholder values only.

The supported parent mode is `workspace-write` with `on-request` approval.
Full Access, `--yolo`, or another live parent override can supersede child
defaults and therefore cannot claim portable conformance. Project hook changes
require Codex's normal hash-bound review and trust; do not use the hook-trust
bypass to make validation pass.

Run each concurrent Codex or Copilot task in its own branch/worktree. Neither
adapter owns or shares another task's uncommitted state, and Git's
one-branch-per-worktree rule remains authoritative. No provider credential or
production credential is stored in this adapter.

## Failure behavior

Run:

```bash
python3 scripts/check_agent_runtime_parity.py
```

The deterministic check fails for a changed approval digest, malformed or
drifting native config, copied/drifting agent projection, extra or escaping
skill link, hook drift, MCP command/tool/env widening, role-authority drift,
Work Contract drift, or a failing legacy Copilot parity check.

An untrusted checkout skips the entire project `.codex` layer; report the
adapter unavailable. A missing role-required portable MCP server blocks that
role or loop. Denied hook trust leaves UI validation incomplete. Never replace
these capabilities with production credentials, personal browser state,
wildcard tools, or Full Access.

The shared invocation-control ledger currently reports `state_corrupt`. That
condition is retained as evidence. This implementation does not delete,
recover, move, initialize, or recreate the ledger. Under the accepted
instrument/shadow semantics it remains visible and non-blocking when
`launch_authorized` is true. Repository mediation is cooperative and cannot
intercept every native launch, so global enforcement or complete coverage must
not be claimed.

## Implementation Impact Map

| Area | Impact |
|---|---|
| Data, API, clients | No application data, database, API, UI, authentication, sync, or provider behavior changes. |
| Agent analysis | Adds strict loading and deterministic comparison of approval, canonical routing, roles, artifacts, tools, hooks, and adapters. |
| Runtime adapter | Adds trusted-checkout Codex project configuration while leaving Copilot Local and Cloud paths operational. |
| Trust | Filters credential-bearing environment names, prohibits production MCPs and Full Access claims, contains skill links, and keeps tool allowlists exact. |
| Operations | No deploy, infrastructure, secret, alert, or production configuration change. |
| Migration and rollback | Additive only; rollback removes the Codex adapter and runtime parity registration while retaining the canonical control plane and Copilot adapters. |
| Tests | Adds positive and mutation-based negative static tests plus native Codex config discovery evidence when Codex is installed. |

## Implementation Change

`config/agent-runtime-parity.json` is the runtime-neutral projection contract.
`analysis/agent_runtime_parity.py` strictly loads it and checks the actual
repository. `scripts/check_agent_runtime_parity.py` is the stable local/CI
entry point. `tests/test_agent_runtime_parity.py` covers the accepted route and
negative drift paths. The Codex-native files remain deliberately thin and
contain no provider, model, authentication, notification, telemetry, or
personal preference state.

## Verification and evidence limits

Static validation can establish contract conformance only. It cannot establish
equivalent prose, sampling, latency, token use, native tool behavior, coverage,
or outcomes. Measured parity still requires at least five paired representative
tasks over at least seven calendar days under the accepted Evaluation Report.
One setup pass or successful task cannot promote parity or autonomy.

For the current candidate, independent Quality must record the exact reviewed
diff, test commands and results, native Codex parsing evidence, negative paths,
legacy Copilot result, residual risks, and release recommendation in separate
Verification Evidence.

## Rollback

Remove or disable `.codex/`, remove the `.agents/skills/` aliases, and remove
the runtime parity contract/check/test/docs. Leave `AGENTS.md`, the canonical
operating/routing/policy JSON, `.github/agents/`, `.github/skills/`, Copilot
MCP configuration, Copilot workflows, and invocation-control ledger unchanged.
