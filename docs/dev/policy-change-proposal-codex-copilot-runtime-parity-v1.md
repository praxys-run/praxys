# Policy Change Proposal: Codex/Copilot runtime parity v1

- **id:** `policy-change-proposal-codex-copilot-runtime-parity-v1`
- **schema_version:** `1`
- **artifact_type:** `policy-change-proposal`
- **owner_role:** `meta-eval`
- **status:** Accepted for implementation and verification only
- **proposal_date:** `2026-08-29`
- **decision subject:** `docs/dev/codex-copilot-runtime-parity-decision-v1.json`
- **decision subject digest:** `sha256:a04df7cd96ec682efa4694792e488c342a665c8356338054c3f9e91bf140fddc`

## Work Contract binding

- **classification_digest:** `sha256:ee6c38eebb7b9db2aedf6b824bc23d5d966e08045fc0e2830196e4a13eb0bcdd`
- **route_digest:** `sha256:6d0f0f33ea72fc440558b883ca293408fd1508011b4f0970495a49ba13b743e2`
- **required artifacts:** Evaluation Report, Policy Change Proposal,
  Architecture Decision Record, Trust Decision Record, Implementation Impact
  Map, Implementation Change, and independent Verification Evidence
- **review route:** `human-review-required` because the checked-in policy
  lists all three selected risk triggers as human-review factors

## Decision requested

Approve a bounded, reversible repository change that makes Codex CLI a
parallel local execution adapter for the existing Praxys operating model. The
same canonical task taxonomy and router remain authoritative. Copilot CLI and
Copilot Cloud remain supported.

Approval authorizes Engineering to prepare and validate only the exact scope
in the decision subject:

- Codex-native project configuration and role adapters;
- skill discovery aliases that retain one source of truth;
- the existing Impeccable hook in Codex's native hook format;
- only the existing portable, allowlisted Chrome and synthetic
  `praxys-local` MCP capabilities;
- a runtime-neutral parity contract and deterministic drift tests; and
- concise operating and onboarding documentation.

## Policy invariants

1. Role ownership, loop composition, required artifacts, Decision Review, and
   human-authority boundaries remain defined by the canonical operating model.
2. Native adapters may translate file formats and tool names; they may not
   change authority or routing.
3. Codex role adapters reference canonical role Markdown rather than copy its
   body. Skill aliases reference canonical repository skills rather than fork
   them.
4. Model provider, model choice, authentication, notification settings, and
   personal preferences remain user-level state and are never committed.
5. Concurrent tasks use separate branches/worktrees. Neither CLI owns or
   replaces the other.
6. No parity, quality, or autonomy claim may be promoted from a single run.

## Explicit Trust limits

- Default local execution remains `workspace-write` with
  `on-request` approval; Full Access/`--yolo` is outside the supported
  portable path.
- Codex project configuration loads only for a trusted checkout.
- Do not register `azure-mcp`, `statsig`, `praxys-dev-test`,
  production credentials, or production mutation tools in the portable
  adapter.
- Use exact MCP tool allowlists and preserve isolated/headless browser flags
  and header redaction.
- Filter inherited credential-bearing environment variables from ordinary
  agent subprocesses. Secrets remain in established local secret mechanisms.
- Read-only roles remain read-only. Engineering is the implementation role;
  Quality remains independent.
- Project hooks require explicit Codex hook trust and may not be bypassed to
  make validation pass.

## Activation and deferrals

Human approval of the exact subject digest authorizes draft implementation and
verification, not merge, deployment, parity certification, autonomy promotion,
native interception, Codex Cloud enablement, or retirement of Copilot. The
final diff and Verification Evidence return through independent review before
activation on the default branch.

The following remain separately reviewable decisions: changing role authority,
changing routing, enabling a write-capable or production MCP tool, supporting a
Full Access parent session, moving beyond local Codex CLI, declaring measured
parity, and retiring an existing adapter.

## Rollback and observation

The adapter is additive. Rollback removes or disables the Codex registration
while leaving the canonical control plane and Copilot paths intact. Meta/Eval
owns the paired-task observation plan in the linked Evaluation Report.

## Approval statement

The independent route is `human-review-required`. A human authority may
approve only by naming this proposal and the exact decision-subject digest.
Approval must not be inferred from agreement with the general goal.

Recorded human approval timestamp: `2026-08-29`

> I approve policy-change-proposal-codex-copilot-runtime-parity-v1,
> approval-subject digest
> sha256:a04df7cd96ec682efa4694792e488c342a665c8356338054c3f9e91bf140fddc,
> only for implementing and verifying the parallel Codex CLI/Copilot CLI
> adapter.

This approval authorizes the bounded implementation and verification described
above. It does not authorize merge, deployment, Copilot retirement, autonomy
promotion, Codex Cloud, Full Access support, production tools, or production
credentials. The approved JSON subject remains unchanged so its digest stays
stable.
