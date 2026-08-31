# Policy Change Proposal: Codex local Microsoft MCP extensions v1

- **id:** `policy-change-proposal-codex-microsoft-mcp-extension-v1`
- **schema_version:** `1`
- **artifact_type:** `policy-change-proposal`
- **owner_role:** `meta-eval`
- **status:** Human-approved for bounded implementation and verification;
  independent Quality and final diff review pending
- **proposal_date:** `2026-08-30`
- **decision subject:**
  `docs/dev/codex-microsoft-mcp-extension-decision-v1.json`
- **decision subject digest:**
  `sha256:0dfb8bcf46df787aa75575e03ff02f19ae40c1df2f8cddde37095c34fa6e987d`

This proposal was prepared after the native role-adapter transport repeatedly
delivered empty task payloads. The human authority subsequently reviewed and
accepted the Architecture and Trust draft boundaries and approved this exact
decision-subject digest. Independent Quality and final diff review remain
mandatory.

## Work Contract binding

- **classification_digest:**
  `sha256:ee6c38eebb7b9db2aedf6b824bc23d5d966e08045fc0e2830196e4a13eb0bcdd`
- **route_digest:**
  `sha256:6d0f0f33ea72fc440558b883ca293408fd1508011b4f0970495a49ba13b743e2`
- **primary loop:** Meta/Eval, with Delivery nested
- **contributors:** Architecture and Trust
- **executor:** Engineering
- **verifier:** independent Quality
- **review route:** `human-review-required`

## Decision requested

Approve a reversible Codex-local pilot that registers two disabled MCP servers
in the trusted project layer and enables them only in the roles named by the
decision subject.

1. Microsoft Learn provides public Microsoft documentation through exactly
   `microsoft_docs_search`, `microsoft_docs_fetch`, and
   `microsoft_code_sample_search`. It uses no credential.
2. Azure MCP is pinned to `@azure/mcp@2.0.5`, runs with `--read-only`, and
   exposes only subscription and resource-group listing. It is enabled only in
   the Operations adapter for an explicitly routed Operations task.
3. Existing Chrome DevTools and `praxys-local` role scoping remains unchanged.
4. Repository deployment workflows remain the only deployment authority.

This proposal supersedes the v1 `azure-mcp` exclusion only for the exact
disabled registration and Operations projection in the decision subject. It
does not modify any other v1 approval, role boundary, tool allowlist, or
portable-parity claim.

## Trust and architecture constraints

- No `@latest`, wildcard tool, Azure environment forwarding, committed
  credential, Key Vault, storage, database, log-query, metric-query, data-plane,
  or mutation tool.
- Azure authentication is an explicit local operator session. Repository files
  neither create nor transport it.
- Every Azure tool call prompts. Read-only results may still reveal production
  topology and remain untrusted evidence rather than authority.
- A missing package, missing login, changed tool name, unexpected tool, or
  failed server startup blocks the Azure-assisted portion of the Operations
  task. It must not broaden permissions or fall back to production secrets.
- The pilot is Codex-local and environment-specific. It is not part of the
  Copilot Local/Cloud portable baseline and cannot support a parity claim.

The reviewed package identity is npm integrity
`sha512-o451hyeCa9u1jr1zYNi3OpF560IRH7LkHQHr7uOjWgaXNgF8m8aNbuxLdqs1PJcJEfrib4W8vVl0GY5X1fXtsw==`,
corresponding to Microsoft source tag `Azure.Mcp.Server-2.0.5` at commit
`f43b47a21545e5f3f87b3bceee35986442217bb4`.

## Pilot outcome plan

Run at least five bounded tasks before considering wider access:

1. two Microsoft documentation lookups where the answer is checked against the
   fetched Microsoft Learn page;
2. one Azure subscription/resource-group inventory with no repository change;
3. one incident or deployment-debug task where Azure MCP supplies only context
   and the repository runbook determines the action; and
4. one negative task proving a requested Azure write, secret, log, metric,
   database, or storage operation is unavailable.

Record startup success, tool-selection accuracy, human corrections, exposed
metadata class, approval count, missing capability, and whether `az`/runbooks
were still needed. Promotion requires zero write capability, zero credential
exposure, zero role escape, and zero bypass of repository workflows.

## Rollback

Remove the two extension registrations, their role projections, and the
extension contract. Retain PR #746's v1 adapter, Chrome DevTools,
`praxys-local`, canonical roles, routing, and all production workflows.

## Recorded approval

Recorded human approval timestamp: `2026-08-30T23:51:39+08:00`

The human authority supplied this exact authorization after reviewing the
Architecture and Trust drafts:

> I approve
> policy-change-proposal-codex-microsoft-mcp-extension-v1, decision-subject
> digest
> sha256:0dfb8bcf46df787aa75575e03ff02f19ae40c1df2f8cddde37095c34fa6e987d,
> only for implementing and verifying the disabled, role-scoped, read-only
> Microsoft Learn and Azure MCP pilot described by that subject.

This approval does not authorize merge, deployment, Azure mutation, secret or
data-plane access, broader tools, portable-parity promotion, or autonomy
promotion.
