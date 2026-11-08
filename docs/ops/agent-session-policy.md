# Agent session policy

Repository work follows `AGENTS.md`: user value, simple implementation and
sufficient verification in one session, with one independent review for material
risk. Native adapter checks validate tools, sandbox and credential boundaries.

The November 7, 2026 simplification removes task-router/config schemas, digest
output, repeated preflight receipts and automatic PR draft resets. Four automatic
agent workflows (outcomes, policy tuner, CI doctor and invariant review) are
removed with their source/lock pairs and unused gh-aw compiler/lock machinery. Claude no longer runs the full backend suite after every edit
or launches three separate specialist reviewers. Focused local checks and
required CI remain authoritative.

No service, variable, secret or ledger needs provisioning. Existing production
settings, scientific approval/activation, tool consent and selective-merge
promotion are unchanged. Operations retains its isolated tool scope. Old
invocation/trial ledgers stay retired and are not read, reset or re-enrolled.

Verify with `scripts/check_agent_runtime_parity.py`,
`scripts/check_copilot_environment_parity.py` and affected policy/workflow tests.
After this change lands on the default branch, confirm retired workflows no
longer receive triggers and feedback assignment/required CI still run. Local
verification does not claim that default-branch activation has occurred.

Rollback is a repository revert of policy, adapters, workflows and checks
together. Reverting files does not broaden deployment or credential authority.
