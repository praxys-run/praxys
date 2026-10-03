# Policy Change Proposal: Statsig setup public projection v1

- id: `policy-change-proposal-codex-statsig-mcp-extension-public-projection-v1`
- artifact_type: `policy-change-proposal`
- owner_role: `meta-eval`
- status: Proposed; fresh Trust acceptance and independent Decision Review pending
- date: `2026-10-03`
- subject: `codex-statsig-mcp-extension-decision-public-projection-v1.json` at `sha256:e3a8b7b81725470e653710d03958c90ce1839f855a8a98e3308e79820a8398e6`
- evaluation prerequisite: `evaluation-report-codex-statsig-public-projection-v1`
- classification: `sha256:e99a2228e9037ba5c64a1c87f041e67bad58961aa5876f9e79c5f842787c9e17`
- route: `sha256:82cfd21ad3bf7067079ad242b6b4092e4738e6b8cccb72ac1d637ef58552049c`

The Statsig-only Delivery contract nests Runtime and Meta/Eval. Engineering leads; Meta/Eval, Architecture and Trust contribute; Engineering and Operations execute serially; independent Quality verifies. Meta/Eval neither approves nor implements this proposal.

## Bounded decision and provenance

Publish distinct, minimized public projections of the original Statsig companion, proposal and historical TDR. Retain the five original input artifacts privately, byte for byte. Omit the approved account's identifier from public text; use only “the single account approved in authenticated session evidence.” Publish no encoded identifier, account hash or mapping. Gate name `dfa_alpha1_auto_analysis_enabled` may remain. This changes publication, identifiers and bindings, without widening configuration or future Operations scope.

Original subject `sha256:5d2eff8ab7743bbbcd4d709ab28826f03a54457553f3e83c6274644d761c0fc6`, proposal `sha256:680b2ed4bffa2feb063e0c1b64b64245b736af410a905f39b63dfbfc5a0c8139` and TDR `sha256:21b86cf088c2f77456fa11dd6d56b02459be4f2043469900aa34a0ab655b83e1` are provenance, not approvals of these new bytes. Existing Evaluation Report and ADR remain byte-identical historical setup evidence. Their original-subject references retain that historical meaning. A new subject, proposal and TDR projection require actual new byte digests and fresh review; historical proposed status or setup-review conclusions cannot become approval of the new split head.

## Preserved controls and authority

The complete `mcp_extension` declaration is identical to the original: V3 Streamable HTTP, Codex-managed OAuth, optional root/Operations enablement, explicit disables in the other twelve roles, precisely `get_context`, `gate_read`, `gate_create`, `gate_update`, native default `prompt`, empty environment forwarding, no credentials, headers, bearer environment variable, custom scopes, generic discovery/execution or fallback. Client filtering neither narrows OAuth grants nor authorizes resources. Canonical roles, sandboxes, credential filters, portable exclusions, shared legacy `.mcp.json`, and all Microsoft/Azure and portable/lifecycle approvals remain unchanged.

Historical setup authority covered project configuration and verification. The latest user request separately authorizes repository commit, PR, independent review and merge. The current proposal is still pending independently allocated review and required checks. Neither request creates an exact-digest human approval. No additional live call or gate mutation, deployment, telemetry, scientific activation or terminal Science STOP follows. The previously confirmed single-account gate action remains a separate historical Operations action; this publication task does not repeat it.

## Implementation and acceptance

Engineering applies only the Statsig incremental hunks to fresh trusted main, with no governed DFA file changes. Exclude the original three identity-bearing records from every newly introduced commit. Add the distinct projections and unchanged historical ER/ADR; bind exact new IDs, repository paths and byte hashes in the separate Statsig contract, strict constants and path literals. Preserve setup-only `authorized_scope` and `exact_digest_human_approval_claimed = false`; repository delivery authority is recorded separately. Update current documentation links and review mirrors truthfully. Keep byte-drift, rebind, malformed, credential, scope, prompt, inheritance and collision rejection tests, including unchanged predecessor approval checks. Record fresh split-head evidence; historical test counts are not its acceptance.

Fresh Trust accepts the historical-TDR publication attachment and its digest. Independent Decision Review allocates the route using existing authenticated user scope. Independent Quality verifies exact bindings, semantic separation, introduced-history privacy, static parity, science maintenance, full final preflight and required GitHub checks. Native prompting, inheritance, OAuth scope and measured parity claims retain their observed limitations.

## Recovery and immediate demotion

Correct current public records in draft PR #871 using additive corrective commits. Build the new Statsig branch from clean main without cherry-picking identity-bearing commits. Current-tree minimization does not remove earlier GitHub commits, PR refs, caches or copies; historical exposure remains, and no purge or support contact is claimed. Do not rewrite shared repository history, delete a branch, or contact third parties under this proposal. Further history removal, if requested, needs its own bounded plan and authority.

Immediate kill switch remains disabling Statsig at root and Operations and restarting affected sessions. Rollback removes this independent extension/projections/check additions while preserving original private evidence, previous approvals, live gate state and unrelated user work. No autonomy or parity promotion is proposed.
