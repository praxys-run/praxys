# Evaluation Report ER-2026-08-29 Codex/Copilot runtime parity

- **id:** `ER-2026-08-29-codex-copilot-runtime-parity-v1`
- **schema_version:** `1`
- **artifact_type:** `evaluation-report`
- **owner_role:** `meta-eval`
- **status:** Accepted as implementation baseline; outcome observation pending
- **report_date:** `2026-08-29`
- **decision subject:** `docs/dev/codex-copilot-runtime-parity-decision-v1.json`

## Work Contract binding

- **primary_object:** `agent-system`
- **impacts:** `[repository-change, agent-policy-or-autonomy, architecture-boundary, trust-boundary]`
- **risk_triggers:** `[security-or-privacy-boundary, irreversible-or-high-blast-radius-action, out-of-policy-or-out-of-distribution-decision]`
- **classification_digest:** `sha256:ee6c38eebb7b9db2aedf6b824bc23d5d966e08045fc0e2830196e4a13eb0bcdd`
- **route_digest:** `sha256:6d0f0f33ea72fc440558b883ca293408fd1508011b4f0970495a49ba13b743e2`
- **lead:** Meta/Eval
- **contributors:** Architecture, Trust
- **executor:** Engineering
- **verifier:** independent Quality
- **decision_review:** required; checked-in policy resolves the current risk factors to `human-review-required`

## Evaluated baseline

Praxys already has a tool-neutral deterministic core: `AGENTS.md`, the
operating model, task taxonomy, loop policies, router, Work Contract digests,
artifacts, and role boundaries. Copilot CLI and Copilot Cloud have native
adapters in `.github/agents/`, `.mcp.json`, GitHub workflows, and
`config/copilot-execution-parity.json`.

Codex CLI currently reads `AGENTS.md` and can run the deterministic Python
router, but it does not automatically consume Copilot custom-agent manifests,
`.mcp.json`, `.github/hooks/`, or skills under `.github/skills/`. The
result is governance discovery without an equivalent native execution adapter.

Read-only inspection established:

- Codex CLI `0.151.0` is installed and loads the user's provider config.
- The repository has no committed `.codex/` or `.agents/skills/` adapter.
- The portable Copilot MCP contract already limits common tools to isolated
  Chrome DevTools and synthetic `praxys-local`.
- The shared invocation-control ledger returned `state_corrupt`. Under its
  accepted instrument/shadow policy this is visible evidence and non-blocking;
  it must not be deleted or silently recreated by this change.

## Options evaluated

1. **Keep Copilot-only execution.** Lowest change risk, but Codex cannot execute
   the checked-in role/skill/tool contract faithfully.
2. **Maintain an independent Codex governance system.** Rejected because role
   prompts, routes, and authority would drift.
3. **Use one canonical control plane with thin native adapters and deterministic
   drift checks.** Recommended as the smallest reversible path.
4. **Immediately replace Copilot with Codex.** Rejected; there is no comparative
   outcome evidence and replacement is not the user's goal.

## Recommendation and evidence limit

Authorize Engineering to prepare option 3. This authorization must not be
interpreted as parity proof, autonomy promotion, or retirement of either CLI.
Both CLIs remain available during a shadow comparison period.

No completed paired-task batch exists yet. One successful setup or task cannot
establish parity. The adapter may claim only static contract conformance until
the observation plan is complete.

## Outcome and guardrail plan

Run at least five paired, representative tasks over at least seven calendar
days, using separate branches/worktrees and the same task statement. Include a
read-only lookup, backend change, frontend/rendered change, science-sensitive
task, and Trust/Operations-sensitive task.

Record only privacy-safe aggregates:

- classification and route digest agreement;
- required role, artifact, and review-route agreement;
- missed or unnecessary role dispatches;
- verification gaps and human corrections;
- revert, incident, policy escape, and adverse-outcome counts;
- elapsed time and human review effort.

Guardrails are zero route drift, zero role-authority drift, zero review bypass,
zero policy escape, zero adverse outcome, and zero unhandled credential or
production-tool exposure. Differences in prose, model choice, token use,
latency, and native tool names are expected and are not parity failures.

## Rollback

Disable or remove only the Codex adapter and its parity registration. Preserve
the canonical router and existing Copilot adapters. No application, database,
production, or user-data migration is involved.
