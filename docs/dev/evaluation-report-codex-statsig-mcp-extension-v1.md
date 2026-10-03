# Evaluation Report: Codex-local Statsig MCP

- **id:** `evaluation-report-codex-statsig-mcp-extension-v1`
- **artifact_type:** `evaluation-report`
- **owner_role:** `meta-eval`
- **status:** Bounded baseline and evaluation design; no cohort outcome evaluation or autonomy promotion
- **date:** `2026-10-02`
- **classification_digest:** `sha256:9c5760a626c81730cfae0585c8cea3d3b2df885b2b3261388cbdb884dc9cde78`
- **route_digest:** `sha256:a34def4290983c74c81d49906a279065f1a7bfb0ae3e9f5a1b197a695a85ea0a`

The user explicitly requested project Codex Statsig MCP configuration and intends to test in a fresh session. The configuration may make optional tools available; this iteration executes no authenticated Statsig call, Console mutation, flag update, science activation, deployment, commit, or merge. Quality remains responsible for verification of the exact implementation.

## Observed baseline

The portable baseline excludes Statsig. Its immutable approved artifacts remain unchanged. `config/codex-local-mcp-extensions.json` separately binds the Microsoft/Azure pilot to a previous exact subject and proposal; adding Statsig to that file would impersonate a wider approval. A new independent Statsig extension contract is proposed.

The project Codex root has no Statsig registration. Shared Copilot `.mcp.json` registers a legacy V1 URL and wildcard tools; neither is authority to copy that configuration. The authenticated runtime catalog and OAuth grant have not been discovered. Documentation is the evidence for declared tool names only.

The current official Statsig Codex guide specifies `https://api.statsig.com/v3/mcp` and OAuth. The current V3 reference describes 18 default tools and documents `get_context`, `gate_read`, `gate_create`, and `gate_update`. Older manual-setup and `/en` alias responses still contain V1 examples. Prefer the current product-specific Codex guide and V3 reference, retain the shared legacy config unchanged, and require the fresh session to check actual availability.

## Alternatives and hypothesis

1. Leave configuration absent and use the Console manually. This does not meet the user's explicit fresh-session tool request.
2. Copy the legacy wildcard entry. This unnecessarily admits discovery, generic execution, creation, experiments, metrics and logs, and leaves the interface version unresolved.
3. Register a local optional V3 extension with four exact tools, managed OAuth, prompting, and bounded root/Operations enablement. Recommended for independent review.
4. Enable only reads. This cannot support the previously authorized named account gate update if the user resumes that separate task.

The hypothesis is that bounded project context and exact gate inspection/provisioning will improve task selection and reduce operator effort, while prompted create/update capabilities can support a separately authorized Operations task when the exact named gate is absent or requires an owner-only rule change. No measured benefit is asserted.

## Outcomes, uncertainty, and future observation

Completed Statsig task cohort: **0**. Observation days: **0**. Corrections, overrides, missed/unnecessary escalations, incidents, reverts, approval effort, latency, target movement, and guardrail movement are **unmeasured**, not zero. Replay and shadow comparison have **not run**. No autonomy, parity, routing, review-effort, or role promotion is proposed.

After Quality verifies configuration, the user's fresh session should report startup/authentication status and the actual filtered tool names without making a mutation. Failure to connect, insufficient grant, missing tools, role inheritance leakage, or default prompting loss makes the affected capability unavailable. It does not authorize wildcard expansion, generic execution, API-key recovery, or production secret access.

Before any future broader policy proposal, aggregate at least five completed bounded decisions over at least seven days and compare equivalent Console/runbook tasks. Record task outcome, tool selection correction, review effort, prompt count, unavailable capability, latency, stale state detection, reverts, incidents, and role/tool escape using privacy-safe task identifiers. Include negative replay cases for another gate/account, unapproved creation, deletion, wildcard/generic execution, wrong project, failed OAuth, stale gate state, missing approval and non-Operations access. Replay and shadow results are prerequisites to any later promotion; the current setup pass is insufficient.

## Immediate demotion

Disable the Statsig root and Operations registrations on tool/role escape, unexpected schema, credential disclosure, attempted unauthorized update, or lost prompt behavior. Restart affected sessions so cached tools cease to be used. Remove only the independent Statsig extension if rollback is needed; preserve the portable baseline, Microsoft/Azure approvals, unrelated DFA work and user-owned changes.

## Primary sources checked on 2026-10-02

- https://developers.openai.com/codex/mcp — project TOML registration, OAuth login and exact enabled-tool filtering.
- https://developers.openai.com/codex/config-reference — `default_tools_approval_mode`, optional-server startup behavior and MCP configuration keys.
- https://docs.statsig.com/integrations/mcp/codex — current direct Codex setup uses V3 and OAuth.
- https://docs.statsig.com/integrations/mcp/tool-reference — current V3, 18 default tools, direct gate read/create/update names and full-resource update caution.
- https://docs.statsig.com/integrations/mcp/overview — current overview and legacy V1 section.
- https://docs.statsig.com/integrations/mcp/manual-setup — legacy V1 example retained as version-mismatch evidence, not copied.
- https://docs.statsig.com/en/integrations/mcp — alias response contained a legacy V1 example during this investigation.

The official V3 reference declares `gate_create` a default write-access tool. It accepts a JSON body; Target-App projects require a Target App name. Future creation must use the live schema and the exact authorized gate, account and project. No authenticated catalog or creation has been performed.

This report records source-derived declarations, not live server discovery or independent Quality evidence.
