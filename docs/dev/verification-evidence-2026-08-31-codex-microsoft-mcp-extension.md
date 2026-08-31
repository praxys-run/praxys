# Verification Evidence: Codex local Microsoft MCP extensions

- Artifact type: verification-evidence
- Owner role: Quality
- Status: PASS for bounded implementation; final human diff review pending
- Verification date: 2026-08-31
- Reviewed base: 533e0c3aaf07407fc46cfcf4a63916137e13b90f
- Decision subject digest:
  sha256:0dfb8bcf46df787aa75575e03ff02f19ae40c1df2f8cddde37095c34fa6e987d
- Proposal digest:
  sha256:b320b5e1aa205d442ff18de4837d43149593667d84225c9ce4b0e0cfddc2faa3

An isolated, read-only Codex Quality session reviewed the full working-tree
diff, governing artifacts, exact role projections, validator, tests, and native
Codex discovery. The session modified no file. The earlier native Quality
subagent transport returned no payload; the isolated review retained an
independent context without weakening the acceptance criteria.

## Findings

No blocking findings.

## Acceptance evidence

- Every project-root MCP registration is disabled.
- Microsoft Learn exposes exactly microsoft_docs_search,
  microsoft_docs_fetch, and microsoft_code_sample_search, and is projected
  only to Architecture, Engineering, Operations, and Trust.
- Azure MCP is projected only to Operations, pinned to version 2.0.5, includes
  server-side read-only mode, exposes exactly azmcp_subscription_list and
  azmcp_group_list, forwards no environment variable, and uses prompt approval.
- Chrome DevTools and praxys-local retain their existing definitions and role
  projections.
- No Copilot portable-contract or workflow file changed. Azure remains excluded
  from the portable baseline.
- Negative tests cover root enablement, version drift, removal of read-only,
  extra and wildcard tools, environment forwarding, Azure role escape, subject
  digest drift, and extra-server inventory.

## Commands and results

- Focused pytest suite: 72 passed.
- Codex/Copilot runtime parity: PASS.
- Copilot execution parity: PASS.
- Native MCP discovery: PASS; four project registrations discovered disabled,
  including exact Azure arguments and empty env_vars.
- Diff check: PASS, with non-failing line-ending notices on existing TOML
  files.
- Codex doctor: config.load and mcp.config PASS with four configured and four
  disabled project servers. Its overall failure was an unrelated custom model
  provider /models HTTP 404; a transient earlier user memory-database read
  failure did not affect the isolated MCP checks.

## Residual risks and limitations

- Azure authentication, first package startup/download, live tool discovery,
  approval prompts, and the five-task outcome pilot have not run. Static/native
  discovery does not establish those runtime outcomes.
- The recorded npm integrity and source commit document the reviewed package,
  but npx still resolves the immutable version through the configured npm
  registry at first use.
- Native role/subagent transport delivered empty payloads or failed to attach
  to the parent thread during this work. Interactive CLI or IDE role invocation
  must be confirmed in the pilot.
- This PASS does not authorize merge, deployment, Azure mutation, broader
  tools, portable-parity promotion, or autonomy promotion.

## Recommendation

PASS for the approved bounded implementation. Proceed to final human diff
review and then the local five-task pilot. Stop and roll back if runtime
discovery exposes an unexpected tool, role, credential path, or Azure write.
