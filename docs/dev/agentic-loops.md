# Task execution and outcome learning

Per-task execution follows [single-session execution](agentic-operating-model.md):
understand, implement, verify. There are no separate Product, Science, Design,
Delivery, Runtime, Incident or Meta/Eval loop invocations. The session applies
the appropriate domain context and retains actual scientific and release gates.

Outcome learning remains separate from completing the current task. Existing
feedback/triage, agent-ready assignment, outcome reporting and policy-proposal
workflows continue to run on their configured schedules and events. Their
trace/outcome data, selective-review policy and branch controls are unchanged.
They do not create mandatory session handoffs or approve their own proposals.

Use batches of actual outcomes to assess time, corrections, missed checks and
human attention. Proposal work can occur in one session with independent review
for policy changes. Do not start another Meta/Eval agent after every task or
make observation of future outcomes a prerequisite for finishing today's work.
See [change-loop operations](../ops/change-loop.md) for deployed automation.
