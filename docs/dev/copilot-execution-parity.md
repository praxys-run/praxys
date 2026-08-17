# Local and Cloud Copilot execution parity

Praxys uses one repository-owned agent runtime for Copilot CLI and Copilot cloud
agent. The target is **contract parity**, not identical model prose:

- the same task classification vocabulary;
- the same deterministic Work Contract for that classification;
- the same loop and role-agent manifests;
- the same decision and review authority;
- the same common repository, browser, and synthetic product-context tools;
- explicit fail-closed behavior where an environment cannot provide a
  capability.

The machine contract is
`config/copilot-execution-parity.json`. Static and live checks are implemented
by `scripts/check_copilot_environment_parity.py`.

## Common entry point

Every material task enters through
`.github/agents/praxys-orchestrator.agent.md`.

```text
task
  |
  v
Praxys Orchestrator
  |
  v
Work Router -> enumerated Task Classification
  |
  v
scripts/route_agentic_task.py
  |
  v
digest-bound Work Contract
  |
  +-> primary loop agent
  +-> nested loop agents
  +-> cross-cutting Architecture / Trust roles
  +-> independent Decision Review Router when required
```

The model classifies only:

1. one primary object from `primary_objects`;
2. zero or more cross-loop `impacts`;
3. zero or more review `risk_triggers`.

`analysis/agentic_task_routing.py` performs the rest deterministically. It
selects loops, loop agents, role slots, required inputs and outputs, outcome
artifacts, and whether material decision review is required. The classification
and resulting route both receive stable SHA-256 digests.

The selected loop set is not a one-pass call order. The primary loop owns the
iteration, nested loops produce bounded dependencies, and a loop resumes when a
later stage depends on those outputs. Required inputs are accepted
preconditions, required artifacts are current-iteration outputs, and outcome
artifacts are future observation obligations.

All seven loops are selectable as a primary object:

| Primary object | Loop |
|---|---|
| Product promise | Product |
| Scientific evidence | Science |
| User experience | Design |
| Repository behavior | Delivery |
| Production state | Runtime |
| Production incident | Incident |
| Agent system | Meta/Eval |

Not every task runs every loop. The router composes the smallest sufficient set
from the task characteristics. Architecture and Trust remain cross-cutting
roles rather than standalone loops.

## Local entry

Copilot CLI discovers the repository agents in `.github/agents/`.
`.github/copilot-instructions.md` and `AGENTS.md` require material work to begin
with Praxys Orchestrator. A user can also select it explicitly:

```text
/agent Praxys Orchestrator
```

The portable agents ignore user-level or local-only MCP extensions. A user may
leave the portable path explicitly for a bounded local operation, but that run
cannot claim Local/Cloud parity.

## Cloud entry

`.github/workflows/assign-copilot.yml` assigns `agent-ready` issues with:

```text
customAgent=praxys-orchestrator
```

The orchestrator then delegates Delivery work to
`.github/agents/praxys-change-loop.agent.md`. Product, Science, Design,
Runtime, Incident, and Meta/Eval tasks that do not originate from an
`agent-ready` issue must explicitly select Praxys Orchestrator when the cloud
task is created. No safe repository event exists for every possible signal.

`.github/workflows/copilot-setup-steps.yml` prepares the ephemeral repository,
Python and Node dependencies, Chrome DevTools MCP, and the synthetic
`praxys-local` launcher before the cloud agent starts.

## Common tools

Portable agents use only:

- Copilot's common `execute`, `read`, `edit`, `search`, and `agent` tools;
- the same pinned Chrome DevTools MCP tool allowlist for public-source
  research and rendered review;
- the same read-only synthetic `praxys-local` tool allowlist.

`.mcp.json` may define additional local servers, but portable agent manifests
cannot request them. The Cloud MCP payload is
`config/copilot-cloud-mcp.json`. Chrome DevTools is the common rendered-review
provider; built-in Cloud Playwright is an optional extension and is not required
by portable agents.

## Checks and drift detection

Run the repository-only check:

```bash
python scripts/check_copilot_environment_parity.py
```

Also compare the authenticated live Cloud MCP setting:

```bash
python scripts/check_copilot_environment_parity.py \
  --live \
  --repo praxys-run/praxys
```

`.github/workflows/copilot-environment-parity.yml` runs the static check on
relevant pull requests and runs the live check on its weekly schedule or manual
dispatch. The live endpoint requires `COPILOT_ASSIGN_TOKEN` to have repository
`Copilot agent settings: read` in addition to the assignment permission.

## Limitations

The canonical limitations are machine-readable in
`config/copilot-execution-parity.json`:

| Limitation | Required behavior |
|---|---|
| Model nondeterminism | Compare classification and route digests; do not require identical prose or hidden reasoning. |
| Cloud settings are external state | Run live drift checks and block a loop when a required MCP server is missing. |
| Production credentials and mutations | Portable Cloud agents use only synthetic read-only product context. |
| WeChat desktop simulator | Keep the PR draft until a user-approved local foreground simulator pass is complete. |
| Local user tool extensions | Portable agents ignore local-only Azure, Statsig, dev-test, credential, or personal tools. |
| Automatic Cloud triggers | `agent-ready` is automatic; other Cloud task types require explicit orchestrator selection. |
| Default-branch activation | Custom agents and setup changes require a disposable Cloud smoke task after merge. |
| External source access | Use public sources, record the actual verification level, and block strong claims when full text is unavailable. |

An unavailable capability never authorizes a weaker substitute. The agent
records the limitation, leaves the affected artifact unverified, and blocks or
keeps the PR draft as required.
