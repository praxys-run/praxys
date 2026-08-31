# ADR-2026-08-29 Codex/Copilot runtime parity

- **id:** `ADR-2026-08-29-codex-copilot-runtime-parity`
- **schema_version:** `1`
- **artifact_type:** `architecture-decision-record`
- **owner_role:** Architecture
- **status:** Proposed — bounded implementation authorized; final implementation review pending
- **decision subject digest:** `sha256:a04df7cd96ec682efa4694792e488c342a665c8356338054c3f9e91bf140fddc`

## Question

How should Praxys support Codex CLI and Copilot CLI concurrently without
forking its roles, loops, routing, authority, skills, or verification policy?

## Options

1. Separate, independently maintained governance trees for each runtime.
2. Move every existing manifest immediately into a new neutral schema and
   regenerate both runtimes.
3. Preserve the current canonical operating model and role/skill bodies, add
   thin native adapters, and validate their projections deterministically.

## Recommendation

Adopt option 3. It provides a reversible compatibility layer without a
high-blast-radius manifest migration. The authoritative semantics remain in
`AGENTS.md`, the versioned operating/routing/policy JSON, the router, and
the existing role and skill bodies. Their current `.github` location is a
path convention, not permission for the Codex adapter to reinterpret them.

Codex custom-agent TOML files contain only native metadata, sandbox defaults,
and an instruction to load the corresponding canonical role manifest before
acting. They do not copy role bodies. Repository skill aliases are relative
links to canonical skill directories. Codex hooks call the existing reviewed
Impeccable implementation. The runtime parity validator resolves links and
references, compares declared role/skill/tool inventories, and fails on drift.

## Architecture boundaries

- Introduce a runtime-neutral top-level parity contract that references the
  existing Copilot Local/Cloud contract and the Codex Local adapter.
- Keep the existing Copilot contract and commands as backward-compatible
  projections during the evaluation period.
- Do not add a service, datastore, dependency, production configuration, or
  cross-machine agent coordinator.
- Do not store provider configuration, authentication, personal preferences,
  or credentials in project files.
- Preserve deterministic task routing as the only source of Work Contracts.
- Treat native subagent launch mechanics as adapters. Codex `/agent` is a
  thread switcher, not a semantic replacement for Copilot custom-agent
  selection; the root Codex agent must invoke the routed role types.
- Concurrent Codex and Copilot work uses distinct branches/worktrees. Git's
  one-branch-per-worktree rule remains authoritative.

### 2026-08-31 lifecycle projection addendum

PR #745 makes a Copilot runtime constraint explicit in the canonical
Orchestrator and Change Loop manifests. Codex has a materially different native
surface, so contract parity does not mean copying those mechanics. The accepted
thin-adapter architecture permits a versioned runtime-specific projection while
keeping shared governance unchanged.
The exact addendum is bound to
`docs/dev/codex-subagent-lifecycle-decision-v2.json` at
`sha256:dbec4d3433d2336631c519f7571e16b42ebe4efa63503e6df790d7b620ddfb43`
and its complete policy proposal at
`sha256:8fdc118d5447dc3b8797eefe7cf045f9c70ba257a0cafa38efe6d94c743f4ce3`.
The packet records an explicit request to prepare this candidate while keeping
the exact-subject `human-review-required` disposition pending.

Copilot retains its repository ledger, one-active-direct-sibling rule, and
notification/claimed-read boundary. Codex uses targetable native threads,
completion delivery, follow-up, wait, interrupt, and tree inspection. It may
parallelize independent read-only siblings, but serializes writes and dependency
chains. Logical work is keyed by stable opaque contract ID, stable role-slot ID,
and immutable artifact digest or Git head; active matching work is followed up
rather than duplicated.
Parent abort, shutdown, failure, or replacement triggers leaf-first descendant interruption; replacement is
explicit and non-chaining, and high-risk verification uses a fresh read-only
thread without executor history.

This addendum adds no service, datastore, native registry mirror, credential,
role, authority, autonomy promotion, or cross-session liveness claim. The pure
dispatch evaluator is a testable policy projection, not a launcher or lifecycle
ledger. Adding this required top-level contract section advances the runtime
parity JSON discriminator to schema 2; schema 1 readers refuse it rather than
silently treating lifecycle mechanics as absent.
Only the Orchestrator and Change Loop Codex adapters own native child dispatch;
other roles return handoffs to a coordinator. Unknown capacity, prerequisites,
active-sibling absence, target addressability, or reviewer identity cannot
authorize a spawn.
Read-only parallel eligibility is derived from the target adapter rather than
caller assertion. The cooperative evaluator requires immutable logical-key and
native-observation facts, rejects consumed or unconfirmed replacement, and
computes leaf-first cleanup from a complete inspected tree; an unavailable or
invalid tree remains incomplete without relaunch.

## Failure behavior

Missing, malformed, duplicated, or drifting adapters fail the static parity
check. Missing required portable MCP tools blocks the affected loop. Optional
runtime-only tools cannot widen a Work Contract. An untrusted checkout ignores
Codex project configuration and must report the limitation. Hook trust denial
leaves UI validation incomplete rather than silently bypassed.

The current invocation-control `state_corrupt` result is retained as
evidence. Instrument/shadow semantics continue native dispatch and forbid
claims of global enforcement or complete mediated coverage.

## Compatibility, migration, and rollback

The first release is additive and leaves all Copilot paths operational. Static
tests must cover legacy Copilot validation and the new cross-runtime contract.
Rollback removes the Codex projection and runtime registration; it does not
rewrite canonical roles or application state.

A later move to fully neutral physical role paths requires paired-run evidence,
a separately reviewed migration, compatibility shims, and default-branch smoke
tests. It is not authorized here.

## Verification obligations

Quality must independently verify native config parsing, role discovery,
canonical-reference integrity, skill resolution, hook schema, exact MCP
allowlists, environment filtering, deterministic route equality, legacy
Copilot checks, failure paths, and a clean rollback. This ADR cannot approve
its own implementation.
