# Architecture Decision Record: Codex-local Statsig MCP

- **id:** `architecture-decision-record-codex-statsig-mcp-extension-v1`
- **schema_version:** `1`
- **decision_type:** `cross-domain-contract`
- **artifact_type:** `architecture-decision-record`
- **owner_role:** `architecture`
- **status:** Proposed Architecture contribution; independent Decision Review pending
- **date:** `2026-10-02`
- **review_route:** Unallocated; this proposer does not select or approve the route
- **dependencies:** None in the logical ADR contract; implementation depends on accepted Meta/Eval, Architecture and Trust decisions plus the independently allocated review path
- **digest:** Decision-subject binding `sha256:5d2eff8ab7743bbbcd4d709ab28826f03a54457553f3e83c6274644d761c0fc6`; this does not claim approval or the ADR's own file hash

## Question and scope

How should project Codex expose the user's requested optional Statsig tools in a fresh session while preserving the portable baseline, bounded child roles and the earlier immutable Microsoft/Azure extension approval?

The exact routed Work Contract has classification digest `sha256:9c5760a626c81730cfae0585c8cea3d3b2df885b2b3261388cbdb884dc9cde78` and route digest `sha256:a34def4290983c74c81d49906a279065f1a7bfb0ae3e9f5a1b197a695a85ea0a`. It selects the Meta/Eval loop with Delivery nested, Architecture and Trust contributors, Engineering executor, independent Quality verifier and required Decision Review. This artifact is Architecture judgment only. No repository implementation, child dispatch, live Statsig call, OAuth login, gate mutation, science activation, deployment, commit or merge occurs here.

The reviewed inputs are the Meta/Eval decision subject above, proposal at `/tmp/praxys-statsig-policy-change-proposal-v1.md` with digest `sha256:680b2ed4bffa2feb063e0c1b64b64245b736af410a905f39b63dfbfc5a0c8139`, and Evaluation Report at `/tmp/praxys-statsig-evaluation-report-2026-10-02.md` with digest `sha256:c340b12fe6b4fbc72530de2399ff7b03a1c522f26d401e1db3416c287e3147b3`. Their bytes were independently checked. The parent reports explicit session authorization for project configuration and verification. This ADR does not invent an exact-digest human approval or transfer the older Microsoft approval.

## Options

1. Keep Statsig absent and use its Console. This has the lowest adapter maintenance cost but leaves the explicit fresh-session MCP request unsatisfied.
2. Copy the shared legacy V1 wildcard entry. This minimizes editing but introduces an unresolved interface version and more capabilities than the four-tool proposal. Reject it.
3. Expand the existing Microsoft/Azure contract and its generic HTTP model. This appears economical but changes an exact two-server inventory and a prior digest-bound approval. The existing HTTP model deliberately requires no authentication, disabled root and automatic approval for public Microsoft documentation. Reject relaxing those invariants for an unrelated OAuth service.
4. Add one separate exact Statsig contract and a small additive projection in the existing checker. This adds one maintained file/model and thirteen explicit role projections while preserving existing approvals. Recommend it for the optional pilot.
5. Register reads only. This has a smaller exposed capability set, but cannot support the separately authorized exact gate provisioning/update task if the user resumes it. The proposed four-tool boundary supports that future task without authorizing its execution during configuration.

## Recommendation and rationale

Use direct Streamable HTTP at `https://api.statsig.com/v3/mcp` with Codex-managed OAuth. The current product-specific Statsig Codex guide uses V3 and directs users to `codex mcp login statsig`; it states OAuth inherits the user account's Statsig permissions. The official V3 tool reference declares `get_context`, `gate_read`, `gate_create` and `gate_update`. These are documentation-derived names, not an authenticated catalog observation. Older V1 examples do not establish the required current interface.

Configure only those four names, optional startup and native prompting. Root/session availability serves the fresh-session setup request. Only Operations children receive the enabled registration. Every other checked-in child adapter explicitly disables it. Root tool availability grants no Operations authority; all material work still follows the deterministic Work Contract and relevant accepted decisions.

This is a reversible local integration pilot. The time horizon is the current setup and subsequent separately authorized bounded Operations work. There is no datastore migration or application-runtime dependency. Non-functional consequences are optional startup/authentication latency, OAuth consent, provider availability and maintenance of exact role projections. Unrelated work can proceed if optional startup fails; work requiring Statsig must report the capability unavailable and stop its dependent action.

## Separate contract and static projection

Engineering should add `config/codex-statsig-mcp-extension.json` with its own strict versioned model/loader in `analysis/agent_runtime_parity.py`. Keep the original `CodexLocalMcpExtensions`, `HttpMcpExtension`, `StdioMcpExtension`, constants, snapshots and approval digests unchanged. Do not introduce a generic extension registry or broaden the portable schema for this single extension.

The smallest new logical contract contains:

- Exact schema/extension version, descriptive candidate status and its own proposal/subject ID, repository-relative paths and SHA-256 byte bindings.
- The subject's exact `mcp_extension` declaration: `statsig`, V3 HTTPS, `codex-managed-oauth`, root enabled, optional, Operations-only, twelve explicit disables, four exact tools, prompting, empty environment forwarding, no repository credentials/headers/bearer variable and documentation-only discovery status.
- Accurate current authorization scope, `project-configuration-and-verification-only`, with no claimed exact-digest human approval. Any review result is supplied by independent Decision Review and does not become an approval inferred by the checker.

Use the existing strict unknown-field and repository-path checks. Bind the complete immutable proposal and subject bytes, not merely IDs or tool names. Compare the complete declared extension to the subject's `mcp_extension` object, and validate its role partition against the current thirteen adapter IDs. Require exactly Operations enabled and the other twelve disabled. Do not reuse the old `approval` object or add a synthetic approval timestamp. The logical ADR has no new invented persistence/approval semantics.

Extend `_expected_codex_config` by composing the unchanged portable projection, unchanged Microsoft/Azure projection and new Statsig projection. Reject server-ID collisions. For adapter comparisons, preserve all existing expected fields and add exactly one Statsig table for every role. Keep `config/agent-runtime-parity.json`, its lifecycle/portable approval bindings, and its `excluded_mcp_servers` entry for Statsig unchanged. Local extension conformance is an additive check alongside portable conformance, not evidence that Statsig is portable.

Missing/malformed Statsig contract, changed proposal/subject bytes, extra tools/roles, omitted child disables, endpoint or authentication drift, approval overrides, headers, bearer variables, env forwarding, generic execution or fallback registrations must fail the extension's static check. Native user/session overrides can supersede project settings; conformance claims apply only when effective settings match the checked project/role configuration.

## Native TOML and inheritance

The intended root and complete Operations registration is:

```toml
[mcp_servers.statsig]
url = "https://api.statsig.com/v3/mcp"
auth = "oauth"
enabled = true
required = false
enabled_tools = ["get_context", "gate_read", "gate_create", "gate_update"]
default_tools_approval_mode = "prompt"
```

Map logical `authentication = "codex-managed-oauth"` to native `auth = "oauth"`. Do not project the logical `transport`, `authentication` or `environment_forwarding` labels as unsupported TOML keys. Add no HTTP-header, header-helper, bearer-token environment, custom OAuth client, client-secret or scope configuration. Keep the existing `STATSIG_*` shell exclusion intact. OAuth consent and credential storage belong to the local Codex runtime.

In each of the other twelve `.codex/agents/*.toml` files, explicitly set:

```toml
[mcp_servers.statsig]
enabled = false
```

This explicit override addresses inherited root enablement. Repeat the complete approved transport for Operations as the repository already does for enabled role extensions. Preserve all unrelated root fields, canonical role instructions, role sandboxes and other MCP tables. No canonical role/tool taxonomy or child-dispatch authority changes.

The documentation's current blanket statement that every root MCP is disabled needs a bounded Statsig exception. Describe root discovery separately from Operations execution authority and retain portable exclusion and the older Microsoft/Azure root-disabled statements. Document OAuth handling and restart/disable recovery in `docs/ops/config-and-secrets.md`, as already included in the proposal, without exposing tokens or recording a live flag change.

## Verification evidence and limits

Observed installed runtime: `codex-cli 0.159.2`. Read-only `codex mcp get` with command-line-only synthetic Statsig configuration parsed the proposed registration and returned exactly the four enabled names, Streamable HTTP V3 transport and null token/header fields. This command does not initialize the MCP server. Negative command-line probes rejected an invalid `auth` enum, an invalid `default_tools_approval_mode` enum and a string `required` value. They confirm these are recognized native fields rather than silently ignored labels. No project configuration was changed by these probes.

The `get --json` output omits `auth`, `required` and `default_tools_approval_mode`, so it cannot itself certify runtime OAuth or prompt behavior. Local CLI help confirms `codex mcp login statsig` and supported `--no-browser`; there is no need to invent a discovery subcommand. Neither help nor config parsing establishes authorization, authenticated discovery, schemas or successful gate access.

Independent Quality should verify the exact final diff and run the static parity entry point plus relevant existing and new mutation-based parity tests. Cover altered proposal/subject bytes, V1 URL substitution, another/missing tool, another enabled role, a missing explicit disable, loss of prompting, non-OAuth auth, token/header/env fallback, absent/malformed contract, collision and unchanged Microsoft/Azure/portable approval behavior. Authentication must not be required for deterministic tests.

For the user's fresh trusted session: verify effective registration with `codex mcp get statsig --json`; use `codex mcp login statsig` if OAuth is unavailable, or `codex mcp login statsig --no-browser` when the browser callback must be completed manually; inspect `/mcp` and the actual filtered tool inventory. Record authentication and actual tool availability separately from static results. Do not invoke a mutation to test prompting during this setup. Missing tools, failed OAuth, changed schemas or ambiguous identity make the affected task unavailable; there is no wildcard or API-key recovery path.

## Consequences, rollback and review triggers

The root session can see two gate mutation capabilities. That is a capability-presence consequence, not current live-state authority. Client allowlisting does not narrow the provider OAuth grant or enforce a per-project/per-gate boundary. Trust must assess consent, prompt behavior, identity, output handling and full-resource update/provisioning safeguards. The server's account/project permissions remain necessary.

Immediate rollback disables Statsig in root and Operations and restarts affected sessions so cached tools are not used. Full rollback removes only this extension's registration, child overrides, independent contract, checker/test additions and documentation. Retain all earlier approval snapshots/digests, portable behavior, shared legacy `.mcp.json`, unrelated DFA work and user-owned Paseo changes. Do not alter live gate state during rollback.

Review again for endpoint/interface changes, missing/renamed tools, prompt enforcement loss, a broader OAuth grant requirement, custom credential storage, additional enabled roles, account/project ambiguity, server schema changes, any creation outside the exact named gate, generic execution/deletion/data access, or any attempt to move Statsig into portable parity. Optional-server recovery must remain bounded; provider unavailability does not authorize a wider capability set.

## Outcome plan and role handoff

Engineering implements only accepted specialist decisions and the independently allocated review result. Operations owns any later explicitly authorized exact gate task and its recovery; configuration does not execute that task. Trust owns the authentication and authorization boundary. Fresh independent Quality owns verification of the implemented configuration. Meta/Eval owns observation of the pilot and any future promotion proposal. Architecture does not approve its own design or its implementation.

Success for this iteration is correct secret-free project/role configuration, passing deterministic checks and honest fresh-session instructions. Native OAuth/tool availability remains unmeasured until the user actually tests it. No autonomy promotion, measured portable parity or operational outcome is claimed.

## Primary-source provenance

Sources accessed on October 2, 2026:

- OpenAI MCP configuration and OAuth documentation: `https://developers.openai.com/codex/mcp`.
- OpenAI config fields and tool approval modes: `https://developers.openai.com/codex/config-reference`.
- OpenAI role inheritance documentation: `https://developers.openai.com/codex/agent-configuration/subagents`.
- Statsig's current product-specific Codex OAuth/V3 guide: `https://docs.statsig.com/integrations/mcp/codex`.
- Statsig V3 tool declarations, JSON-body creation and full-resource update caution: `https://docs.statsig.com/integrations/mcp/tool-reference`.

The public sources describe intended interfaces. The local probes describe only this installed CLI's config parser. Neither is authenticated Statsig evidence.
