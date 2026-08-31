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
The lifecycle schema-2 addendum is separately bound to
`policy-change-proposal-codex-subagent-lifecycle-v2`, complete proposal digest
`sha256:8fdc118d5447dc3b8797eefe7cf045f9c70ba257a0cafa38efe6d94c743f4ce3`,
and decision subject digest
`sha256:dbec4d3433d2336631c519f7571e16b42ebe4efa63503e6df790d7b620ddfb43`.
It records the user's 2026-08-31 plan approval and implementation request as
authority to prepare and verify this candidate. The exact subject remains
`human-review-required` and pending; no digest-bound human approval, activation,
release, or merge decision is claimed.

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

- `.codex/config.toml`: `workspace-write` plus `on-request` defaults, two
  portable MCP registrations, two separately approved Codex-local extension
  registrations, environment filtering, hooks, and multi-agent enablement;
- `.codex/agents/*.toml`: thin adapters that direct the child to read one
  canonical `.github/agents/*.agent.md` manifest before acting;
- `.agents/skills/*`: relative symlinks to canonical repository skill
  directories, with no copied skill bodies; and
- `.codex/hooks.json`: the Codex-native PostToolUse projection of the existing
  repository-owned Impeccable hook.

The root project layer registers every MCP server as disabled. Chrome DevTools
and `praxys-local` remain the only portable servers. Microsoft Learn and Azure
MCP are separately bound by `config/codex-local-mcp-extensions.json`; they do
not change the Copilot Local/Cloud portable contract.
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

## Runtime-specific lifecycle profiles

PR #745 hardened Copilot CLI calls against reported native completion and
registry failures through a repository-owned ledger. That containment remains
the Copilot lifecycle profile: calls default to synchronous execution, direct
siblings under one active parent are serialized, and exceptional background
work uses exact task-result binding, external notification, and one claimed
native read. Codex does not emulate this protocol.

Current Codex releases expose targetable agent threads, completion-result
delivery, follow-up routing, waiting, interrupt, and tree/status inspection.
The Codex profile uses those native controls and keys each logical unit of work
by the stable opaque contract ID, stable role-slot ID, and immutable artifact
digest or Git head revision key:
The capability baseline is the current
[official OpenAI Subagents documentation](https://developers.openai.com/codex/agent-configuration/subagents/);
unsupported or unavailable native controls fail the affected orchestration
step rather than falling back to the Copilot claimed-read protocol.

- if that key is already active, send the additional instruction to that
  target instead of spawning duplicate work; if the target cannot be addressed,
  queue it as incomplete without relaunching;
- run direct siblings concurrently only when each is independent and
  read-only; serialize implementation writes and artifact dependency chains;
- cap a session at four spawned-agent threads and queue when no slot is
  available; capacity exhaustion never authorizes a replacement;
- when a parent aborts, shuts down, fails, or is replaced, inspect its tree and interrupt
  active descendants leaf first; an unconfirmed termination is incomplete
  work, not evidence that relaunch is safe;
- permit at most one explicit, non-chaining replacement after termination or
  loss is confirmed; and
- launch Quality or Trust verification as a fresh read-only thread without the
  executor's conversation history.

The Orchestrator and Change Loop Codex adapters translate only the canonical
manifests' Copilot-specific `Cooperative invocation admission` section. All
role, route, artifact, authority, safety, and Decision Review requirements in
those manifests remain authoritative. A Codex call must never invoke
`bind_native`, `native_read`, `read_claim`, or `read_agent`; those are Copilot
containment mechanics, not portable governance.
Only these two coordinator adapters may spawn, follow up, wait, or interrupt a
Codex child. Other routed roles return required handoffs to their parent
coordinator, even when their canonical Copilot manifest exposes the generic
`agent` tool. This keeps every native child call behind one scheduling boundary.

## Portable capabilities and Trust limits

The portable MCP set is exact:

1. `chrome-devtools`: `chrome-devtools-mcp@1.6.0`, headless, isolated, usage
   statistics and CrUX disabled, network headers redacted, and only the common
   tools listed in `config/agent-runtime-parity.json` enabled.
2. `praxys-local`: the repository `local` synthetic profile, with only ten
   read-only product-data tools enabled.

`azure-mcp` remains excluded from the portable baseline, along with `statsig`,
`praxys-dev-test`, wildcard tools, personal browser sessions, production
credentials, and production mutations. A separately approved Codex-local
Azure registration does not alter that exclusion.
Codex command children inherit a core environment with the default
`KEY`/`SECRET`/`TOKEN` filtering active, plus explicit exclusion of common
cloud, database, provider, athlete-connection, email, feature-flag, and
Copilot credential namespaces. The MCP registrations forward no inherited
environment variables.

## Codex-local Microsoft MCP pilot

The human-approved decision subject at
`docs/dev/codex-microsoft-mcp-extension-decision-v1.json` adds two local-only
extensions without claiming portable parity:

1. `microsoft-learn` uses `https://learn.microsoft.com/api/mcp`, no
   authentication, and exactly the documentation search, fetch, and code-sample
   tools. It is optional for Architecture, Engineering, Operations, and Trust.
2. `azure-mcp` uses stable `@azure/mcp@2.0.5`, `--read-only`, and exactly
   `azmcp_subscription_list` and `azmcp_group_list`. It is optional and enabled
   only in the Operations adapter. Every tool call prompts.

The root registrations stay disabled. The Azure entry forwards no environment
variables and stores no credential; the operator authenticates locally outside
repository configuration. Azure output is production metadata and untrusted
evidence. It cannot authorize deployment or mutation. Logs, metrics, App
Service, Resource Health, Key Vault, storage, databases, data-plane reads, and
all write tools remain outside this pilot.

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

The deterministic check fails for a changed baseline or extension approval
digest, malformed or drifting native config, copied/drifting agent projection,
extra or escaping skill link, hook drift, MCP command/tool/env widening, Azure
projection outside Operations, role-authority drift, Work Contract drift, or a
failing legacy Copilot parity check.

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
| Codex-local pilot | Adds public Microsoft documentation lookup and an Operations-only, read-only Azure inventory. It adds no application or production mutation. |

## Implementation Change

`config/agent-runtime-parity.json` schema 2 is the runtime-neutral projection
contract. Schema 1 readers fail closed rather than ignoring the new lifecycle
profile; the digest-bound v1 approval subject and proposal remain unchanged.
`analysis/agent_runtime_parity.py` strictly loads it and checks the actual
repository. It also exposes a pure Codex dispatch evaluator for the three
checked-in classes (`read_parallel`, `write_serial`, and
`dependency_serial`); it makes no native call and persists no thread state.
Every observation is caller-supplied, so the evaluator defaults unknown
capacity, prerequisites, sibling absence, target addressability, and reviewer
identity fail closed. It is conformance logic for the native coordinator, not
global interception or atomic cross-process enforcement.
Dispatch observations include the validated opaque contract/slot identities,
immutable revision key, logical-work lookup state, exact native target when
active, target role, reviewer-history provenance, and one-use replacement
facts. `read_parallel` derives read-only eligibility from the selected adapter's
checked-in `write_scope`; a caller cannot relabel Engineering or an artifact
writer as read-only. Cleanup evaluation accepts a complete native tree snapshot
and returns leaf-first interrupt order, or records incomplete when the snapshot
is absent, cyclic, duplicated, or otherwise inconsistent.
`scripts/check_agent_runtime_parity.py` is the stable local/CI entry point.
`tests/test_agent_runtime_parity.py` covers the accepted route, dispatch matrix,
and negative drift paths. The Codex-native files remain deliberately thin and
contain no provider, model, authentication, notification, telemetry, or
personal preference state.

`config/codex-local-mcp-extensions.json` independently binds the Microsoft MCP
pilot to its approved subject. Keeping it outside
`config/agent-runtime-parity.json` prevents a local production-context tool
from being mistaken for a Local/Cloud portable capability. The native
Engineering role transport did not return a payload during this change, so the
mechanical implementation remains subject to independent Quality and final
human diff review rather than claiming that invocation as execution evidence.

## Verification and evidence limits

Static validation can establish contract conformance only. It cannot establish
equivalent prose, sampling, latency, token use, native tool behavior, coverage,
or outcomes. In particular, native thread control does not prove that a thread
survives context or process loss. Measured parity still requires at least five
paired representative tasks over at least seven calendar days under the
accepted Evaluation Report. Record duplicate launches, orphaned threads,
follow-up reuse, interruptions, replacements, human corrections, latency, and
token cost separately by runtime. One setup pass or successful task cannot
promote parity or autonomy.

For the current candidate, independent Quality must record the exact reviewed
diff, test commands and results, native Codex parsing evidence, negative paths,
legacy Copilot result, residual risks, and release recommendation in separate
Verification Evidence.

## Rollback

For the Microsoft MCP pilot alone, remove its four role projections, two root
registrations, extension contract, tests, and decision documents. Leave the v1
adapter and portable servers unchanged. Full adapter rollback may remove or
disable `.codex/`, remove the `.agents/skills/` aliases, and remove the runtime
parity contract/check/test/docs. Leave `AGENTS.md`, the canonical
operating/routing/policy JSON, `.github/agents/`, `.github/skills/`, Copilot
MCP configuration, Copilot workflows, and invocation-control ledger unchanged.
