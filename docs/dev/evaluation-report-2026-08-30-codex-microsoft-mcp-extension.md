# Evaluation Report: Codex local Microsoft MCP extensions

- **id:** `ER-2026-08-30-codex-microsoft-mcp-extension-v1`
- **artifact_type:** `evaluation-report`
- **owner_role:** `meta-eval`
- **status:** Human-approved implementation baseline; outcome observation has
  not started
- **decision subject digest:**
  `sha256:0dfb8bcf46df787aa75575e03ff02f19ae40c1df2f8cddde37095c34fa6e987d`

The Meta/Eval role invocation failed closed because its payload was empty. The
human authority reviewed this bounded evaluation design through the approved
policy proposal. It is the implementation baseline, not a completed outcome
evaluation or an autonomy/parity promotion.

## Baseline and hypothesis

PR #746 registers only isolated Chrome DevTools and synthetic read-only
`praxys-local` in the portable contract. Local Copilot separately exposes a
broad Azure MCP, but that server is intentionally non-portable. Praxys relies
heavily on Azure and Microsoft services, so two narrower capabilities may
reduce documentation mistakes and shorten Operations diagnosis without
weakening deployment authority.

The hypothesis is that public Microsoft documentation plus Azure subscription
and resource-group inventory will resolve common setup and routing questions.
If logs, metrics, App Service state, or Resource Health are repeatedly required,
their exact tools must be proposed in a later reviewed subject; the pilot does
not pre-authorize them.

## Compared options

1. Continue with browser search and `az`/`gh` only. Lowest tool risk, but less
   structured and more dependent on remembered command schemas.
2. Add Microsoft Learn only. Lowest-risk improvement, but no live Azure context.
3. Add broad Azure MCP. Rejected because it exposes unnecessary tools and
   production context.
4. Pilot Microsoft Learn plus a pinned, read-only, two-tool Azure server only
   for Operations. Recommended for review.

## Measurement and decision rules

Use the five-task pilot defined in the proposal. Compare against equivalent
tasks using Microsoft Learn in the browser and `az`/repository runbooks. Track
completion, corrections, elapsed operator effort, approval prompts, unavailable
capabilities, sensitive metadata class, and tool/role escapes.

Stop and roll back on any write tool, credential disclosure, unprompted Azure
read, non-Operations Azure access, unexpected server tool, or attempted bypass
of a repository deployment workflow. Wider adoption requires a new proposal; a
successful pilot alone cannot promote parity or autonomy.
