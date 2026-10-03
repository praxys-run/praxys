# Policy Change Proposal: Codex-local Statsig MCP v1

- **id:** `policy-change-proposal-codex-statsig-mcp-extension-v1`
- **schema_version:** `1`
- **artifact_type:** `policy-change-proposal`
- **owner_role:** `meta-eval`
- **status:** Proposed; Architecture, Trust and independent Decision Review pending
- **date:** `2026-10-02`
- **evaluation prerequisite:** `evaluation-report-codex-statsig-mcp-extension-v1`
- **decision subject:** `codex-statsig-mcp-extension-decision-v1.json` (companion to this proposal)
- **review_route:** Unallocated; only independent Decision Review Router may select it

## Work Contract

Primary object `agent-system`; primary loop Meta/Eval with Delivery nested. Impacts: `repository-change`, `agent-policy-or-autonomy`, `architecture-boundary`, `trust-boundary`. Risks: `security-or-privacy-boundary`, `out-of-policy-or-out-of-distribution-decision`.

Classification digest `sha256:9c5760a626c81730cfae0585c8cea3d3b2df885b2b3261388cbdb884dc9cde78`; route digest `sha256:a34def4290983c74c81d49906a279065f1a7bfb0ae3e9f5a1b197a695a85ea0a`.

Architecture owns the ADR; Trust owns the TDR; Engineering owns the Implementation Impact Map and Implementation Change; a fresh independent Quality thread owns Verification Evidence. Meta/Eval owns this proposal and its prerequisite Evaluation Report and cannot approve or execute it.

## Bounded decision

Register optional `statsig` at `https://api.statsig.com/v3/mcp` as a new Codex-local project extension. Use Codex-managed OAuth without repository credentials, Authorization headers, bearer-token environment variables, environment forwarding, custom client secrets, arbitrary scope requests, or API-key fallback. Declare only `get_context`, `gate_read`, `gate_create`, and `gate_update`; default tool approval is `prompt` with no auto-approved per-tool override.

Root/session registration is enabled so the user's fresh session can discover the optional tools. Root tool presence grants no Operations authority: material work is still routed, and production mutations belong to an explicitly authorized Operations task. Operations is the only child role enabled. Every other checked-in child adapter explicitly disables Statsig so inherited root settings cannot expose it. `required = false` prevents optional auth/startup failure from blocking unrelated work; the affected Statsig task must still report unavailable rather than silently widening access.

Keep Statsig outside the portable Local/Cloud baseline. Preserve the exact Microsoft/Azure extension contract, proposals, subjects, approval digests and capabilities. Use a separate `config/codex-statsig-mcp-extension.json` and narrowly extend deterministic static checking to bind its own decision/proposal. Keep shared `.mcp.json`, Copilot Cloud configuration, portable allowlists, canonical roles, router policy, deployment workflows and shell credential filters unchanged.

The external OAuth grant may be broader than these four client tool names. Local filtering is not a server-side authorization boundary or per-resource restriction. Tool names are documentation-derived declarations until the fresh session authenticates and discovers them. Project identity, permissions and schemas must be checked before any later action; no live discovery is claimed here.

## Configuration authority and separate mutation authority

The current explicit request authorizes project configuration and verification only. Record that session authorization accurately; do not forge a new exact-digest human approval or transfer the older Microsoft approval. Independent Decision Review assesses whether any concrete decision exceeds the existing user scope. Meta/Eval does not select that route or require a repeat permission request itself.

The previously named future task concerns only `dfa_alpha1_auto_analysis_enabled` and the user account `dddtc2006@live.cn`. This proposal does not execute it. When a later explicitly authorized Operations task resumes, confirm the project and live schema, inspect the exact gate and resolve only the authorized existing account identifier. If the gate is confirmed absent, a prompted `gate_create` may provision that exact gate within the separately authorized task. Use the live create schema and any required Target App name; creation must preserve safe default-false behavior and admit only the authorized account. If the gate exists, read its complete current state and preserve unrelated targeting/rules/fields. Preview the exact creation or update, satisfy native prompting, any schema confirmation and existing project review requirements, then read back the exact resulting gate. Ambiguous absence or identity, wrong project, unsupported required create fields, unrelated target change, broad activation or missing prerequisite fails closed. Gate deletion remains excluded.

`gate_update` can replace a whole resource. Its availability does not permit arbitrary gate mutation. No discovered `api_write`, `api_destructive`, `discover_tools`, wildcard, gate delete, experiments, configs, log-query, metric-query or SDK-key capability is admitted. The bounded gate lifecycle is create/read/update only; registering its tools does not authorize live use in this iteration.

## Evaluation and rollback

The Evaluation Report records zero completed Statsig decisions and no replay/shadow results. The bounded optional pilot is an explicit configuration response, not an autonomy or parity promotion. Any broader access requires a new independently reviewed subject and sufficient measured outcomes.

Immediate kill switch: disable Statsig in root and Operations, restart affected sessions and stop using cached tools. Full rollback removes only Statsig's registration, explicit overrides, separate contract/check additions and its documentation. It preserves prior approval files/digests, portable behavior and unrelated changes. No rollback step changes a live gate.

## Specialist handoff

Architecture must assess V3/direct HTTP, inheritance isolation, independent contract composition and adapter-conformance consequences. Trust must assess OAuth/consent, prompt behavior, broader provider grant, project/account identity, exact absent-gate provisioning, full-resource update safeguards and absence of secret passthrough. Decision Review must evaluate the concrete bounded proposal against existing session authorization without self-approval. Quality must independently verify the exact allowlist, root/Operations enablement, all other child disables, OAuth-only secret-free config, previous immutable digests and negative drift paths. Native fresh-session tool discovery remains user testing unless separately performed and recorded.

Primary source declarations and the V1/V3 documentation mismatch are recorded in the Evaluation Report; no authenticated tool discovery or production mutation has occurred in this Meta/Eval work.
