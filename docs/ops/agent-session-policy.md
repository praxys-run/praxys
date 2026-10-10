# Agent session policy

Repository task execution uses one main session and risk-based independent
review. `AGENTS.md` is the entry point. `config/agentic-operating-model.json`,
`config/agentic-task-routing.json` and `config/agent-loop-policies.json` define
session behavior; runtime adapter conformance is checked by
`scripts/check_agent_runtime_parity.py`.

The 2026-10-10 simplification removes per-task custom invocation and decision-card
bookkeeping. It does not alter production deployment settings, scientific
approval ledgers, CI gates or selective merge promotion. Root MCP registrations,
credential filters and hooks remain unchanged. Operations retains its existing
local tool/consent boundary and is used only when those tools are required.

No service, environment variable, secret or new ledger needs provisioning.
Existing private invocation/trial ledgers remain on disk and are no longer used;
do not delete/reset them or treat unobserved attempts as success. Rollback is a
repository revert; re-enrollment in an old trial is not automatically authorized.

Run static adapter checks after config changes. Missing independent review keeps
the affected handoff/release incomplete. Native runtime failures are reported as
failures, not synthesized as successful review. The existing repository workflow
and platform authority still govern any actual deployment.
