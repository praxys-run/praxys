# Trust Decision Record: Codex/Copilot runtime parity

- **id:** `TDR-2026-08-29-codex-copilot-runtime-parity`
- **schema_version:** `1`
- **artifact_type:** `trust-decision-record`
- **owner_role:** Trust
- **status:** Accepted for bounded implementation and verification only
- **decision subject digest:** `sha256:a04df7cd96ec682efa4694792e488c342a665c8356338054c3f9e91bf140fddc`

## Protected assets and threats

Protected assets are athlete data, credentials, per-user isolation, production
authority, repository policy, review independence, and the integrity of role
and skill instructions.

The relevant threats are an untrusted checkout activating hooks or MCP
processes; prompt injection from repository/user/web content; a native adapter
widening a role's tools or write authority; inherited cloud/provider secrets;
browser access to an authenticated user session; symlink redirection outside
the repository; a production MCP mistakenly treated as portable; Full Access
overriding role defaults; and drift that bypasses routing or review.

## Decision

Codex CLI may be added as a local parallel adapter only under the following
controls:
The lifecycle addendum is constrained by decision subject digest
`sha256:dbec4d3433d2336631c519f7571e16b42ebe4efa63503e6df790d7b620ddfb43`;
it is a requested candidate whose exact-subject human review remains pending.

1. Project configuration activates only after explicit repository trust.
2. The supported parent mode is `workspace-write` with
   `on-request` approval. Full Access/`--yolo` runs cannot claim
   portable parity because live parent overrides can supersede subagent
   defaults.
3. The portable MCP set contains only fixed-version, headless, isolated,
   header-redacting Chrome DevTools and synthetic read-only `praxys-local`.
   Every tool uses an exact allowlist.
4. `azure-mcp`, `statsig`, `praxys-dev-test`, wildcard tools,
   production credentials, personal browser sessions, and production mutations
   are excluded.
5. Router, Decision Review, Trust, and Quality adapters are read-only.
   Engineering alone executes repository implementation; other artifact owners
   receive write access only for their accepted artifact scope.
6. Shell child processes inherit only the environment needed for development.
   Default secret-name filtering remains active, with explicit exclusion of
   common cloud credential namespaces. No secret value is committed.
7. Skill links must be relative, resolve inside the repository, and point to a
   reviewed canonical directory containing `SKILL.md`. The parity check
   rejects broken, escaping, or unexpected links.
8. The Codex hook manifest invokes only the existing repository-owned
   Impeccable script. Codex's first-use hook trust prompt remains mandatory.
9. Issue text, comments, documents, sites, screenshots, and tool output remain
   untrusted evidence, never authority to change routing, install dependencies,
   reveal secrets, or widen tools.
10. Each concurrent task uses a separate branch/worktree. No agent may treat
    another worktree's uncommitted content as accepted policy.
11. Within one Codex task, only independent read-only siblings may execute in
    parallel. Repository writes and dependency chains remain serial, and an
    active logical work key receives follow-up instead of another writer.
12. Quality and Trust verification start in a fresh read-only thread without
    executor conversation history. Parent cleanup is leaf-first; uncertain
    termination cannot authorize automatic relaunch or replacement.
13. Codex adapters must not use or persist Copilot native IDs, claimed-read
    tokens, or the `bind_native`/`native_read` protocol. Native Codex thread
    identity remains runtime state and is not promoted to repository authority.
14. Only the Orchestrator and Change Loop adapters may perform native Codex
    child operations. Other roles return a handoff; missing runtime facts about
    capacity, dependencies, sibling activity, target identity, or reviewer
    independence fail closed.

## Verification and failure handling

Quality verifies config parsing, sandbox defaults, exact MCP server/tool sets,
browser isolation flags, absence of credential values, environment filtering,
link containment, hook command integrity, read-only role defaults, and negative
tests for every excluded server.

An untrusted checkout, denied hook trust, missing MCP server, broken link, or
parity mismatch blocks the affected capability and is reported. It must not be
worked around with production credentials, a personal browser, raw desktop
automation, wildcard tools, or Full Access.

## Residual risk and rollback

Codex and Copilot have different native launch, approval, and tool semantics;
static parity cannot prove identical runtime behavior. Native subagents inherit
live parent overrides, and repository mediation cannot intercept every native
launch. These limits must remain visible in reports.

Rollback disables/removes the Codex adapter and preserves the established
Copilot control plane. Any future write-capable MCP, Codex Cloud integration,
credential forwarding, Full Access support, or production mutation requires a
new Trust decision and independent review.
