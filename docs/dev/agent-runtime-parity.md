# Codex and Copilot adapters

The active execution policy is [single-session execution](agentic-operating-model.md).
Both runtimes use the same main executor, optional Quality reviewer, domain
skills and external authority boundaries. The runtime owns thread lifecycle;
repository code does not reimplement admission, binding, read claims or cleanup.

`config/agent-runtime-parity.json` schema 3 validates three thin native profiles
under `.codex/agents/`, against `.github/agents/`. Older schema readers reject
this version. `AGENTS.md` and the canonical manifests are the shared instructions.
Existing sessions do not spawn an orchestrator just to adopt them.

## Capabilities

The main executor has the previous Engineering implementation capability and
portable isolated browser/synthetic data tools. Quality is read-only, has the
portable browser and must start without executor conversation history.
Operations retains its separate local grants and is used only when needed.

Root configuration, credential environment filtering and Impeccable hooks are
unchanged. The portable MCP baseline remains isolated `chrome-devtools` plus
read-only synthetic `praxys-local`. Production/personal credentials, wildcard
MCP tools and Full Access are not substitutes for missing portable capabilities.
A missing tool blocks only the work requiring it.

The separately bound Microsoft/Azure and Statsig extension documents retain
their exact bytes and historical scope. Azure inventory remains Operations-only
and prompted. Statsig remains enabled at the root and Operations, disabled in
the executor and Quality; its four-tool allowlist, OAuth and prompting remain
unchanged. Removing old profiles does not transfer their grants to the executor.
Microsoft Learn remains available in the surviving Operations profile. Tools
are capabilities, not per-resource authorization or permission to deploy.

No native MCP server is started by static validation. Native consent, actual
permissions and tool availability must still be checked at use time. Do not
store tokens, callbacks, credentials or personal runtime data in the repository.
The old runtime/lifecycle approval packets describe their historical versions;
this change does not manufacture or reuse an approval receipt for schema 3.

## Verify

```bash
python3 scripts/check_agent_runtime_parity.py
python3 scripts/check_copilot_environment_parity.py
```

Checks cover exact sandbox/tool/environment projection, immutable MCP extension
bindings, read-only review, canonical agent inventory, skill-link containment,
hooks and portable Local/Cloud capability agreement. Negative tests exercise
scope widening, credential/prompt drift, malformed contracts and evidence drift.
They do not establish successful child transport, independent review quality,
latency, OAuth consent or measured runtime parity.

The project's Codex layer still requires a trusted checkout. Native trust or
sandbox restrictions cannot be bypassed by changing this policy. Concurrent
unrelated tasks use separate worktrees; writes within one task stay serialized.

## Retirement and rollback

The custom invocation protocol and decision-card experiment are retired. Their
private Git-common-directory ledgers are not opened, reset, migrated or deleted.
Pending historical observations remain unknown. Old decision documents remain
historical evidence, not live entry instructions.

Rollback reverts the policy/adapters/checks as one change. Do not reset private
ledgers or widen MCP grants. Re-enabling an expired or stopped experiment needs
its own scoped decision; reverting code does not create that authority.
