# AGENTS.md - Praxys role and loop guide

## Operating model

Agents are bounded **roles**. Loops are learning workflows around an **object**.
The Work Router composes roles into each loop instance; the independent
Decision Review Router allocates review authority.

`Praxys Orchestrator` is the common Local and Cloud entry point for every
material task. It obtains an enumerated classification from Work Router, runs
the deterministic task router, and invokes only the loops and roles in the
resulting digest-bound Work Contract.

Read:

- `docs/dev/agentic-operating-model.md`
- `docs/dev/agent-runtime-parity.md`
- `config/agentic-operating-model.json`
- `config/agentic-task-routing.json`
- `config/agent-runtime-parity.json`
- `config/copilot-execution-parity.json`
- `config/agent-loop-policies.json`

Codex CLI and Copilot CLI are parallel local adapters to this same control
plane. In a trusted checkout, Codex loads `.codex/config.toml`, thin role
adapters under `.codex/agents/`, repository skill aliases under
`.agents/skills/`, and `.codex/hooks.json`. These native files translate
runtime formats only; they never replace the canonical role manifests,
taxonomy, router, artifact ownership, Decision Review, or human authority.
Run `python3 scripts/check_agent_runtime_parity.py` before claiming static
adapter conformance. Static conformance is not measured runtime parity.

Do not treat this role list as a permanent org chart. Create, merge, or retire a
role only through the checked-in evolution criteria and a reviewed policy
change.

## Role agents

### Product

- **Owns:** user problems, product promises, prioritization, value trade-offs,
  minimum valuable scope, and target/guardrail outcomes.
- **Agent:** `.github/agents/product.agent.md`
- **Artifacts:** Product Decision Record and Product Outcome Record.
- **Boundary:** Product does not invent science, design the final interaction,
  implement code, or approve its own decision.

### Design

- **Owns:** user journeys, information architecture, interaction, visual
  language, content, accessibility, and rendered experience.
- **Agent:** `.github/agents/design.agent.md`
- **Harness:** `.github/skills/ui-quality/SKILL.md`
- **Artifacts:** Design Decision Record and Experience Specification.
- **Boundary:** Design does not choose product priority or implement backend
  behavior. Engineering implements; Quality independently verifies.

### Engineering

- **Owns:** implementation inside accepted Product, Design, Architecture,
  Science, Trust, and Operations boundaries.
- **Agent:** `.github/agents/engineering.agent.md`
- **Artifacts:** Implementation Impact Map and Implementation Change.
- **Capabilities:** frontend, backend/API, analysis, database, data pipeline,
  provider integration, AI integration, migration, and test automation.
- **Boundary:** A different directory or technology is not a new role.

Engineering capabilities preserve repository-specific rules:

| Capability | Primary paths | Invariants |
|---|---|---|
| Data pipeline | `sync/`, `db/sync_writer.py`, `db/models.py`, `analysis/data_loader.py` | All sync writes use `db/sync_writer.py` upserts |
| Analysis | `analysis/metrics.py`, `api/deps.py` | Metrics are pure; intensity uses splits/samples, never activity `avg_power` |
| API | `api/main.py`, `api/deps.py`, `api/auth.py`, `api/routes/` | Routes stay thin; authenticated data is recomputed through deps; only register/token are public |
| Frontend | `web/src/`, `miniapp/` | Use `useApi<T>`, strict types, UI quality, and web/miniapp parity; use `wechat-devtools` only in a user-approved foreground window |
| AI features | `api/ai.py`, `api/routes/ai.py`, `analysis/providers/ai.py`, `plugins/praxys/` | Azure AI is an ordinary authenticated-service capability, not an optional enhancement. During an outage or emergency stop, AI-only features report unavailable while separately labelled deterministic metrics continue; deterministic content is never presented as AI. Plugin edits land in its submodule repository first |

### Architecture

- **Owns:** cross-cutting system boundaries, long-lived technical constraints,
  non-functional trade-offs, and irreversible technical choices.
- **Agent:** `.github/agents/architecture.agent.md`
- **Artifact:** Architecture Decision Record.
- **Activate for:** new service/datastore, cross-domain contract, irreversible
  migration, or material reliability/scalability/performance risk.
- **Boundary:** Routine local code design stays with Engineering.

### Quality

- **Owns:** test strategy, acceptance sufficiency, regression, exploratory
  validation, and release confidence for the current change.
- **Agent:** `.github/agents/quality.agent.md`
- **Artifact:** Verification Evidence.
- **Boundary:** High-risk verification is independent from the executor.
  Quality does not replace specialist Science, Trust, Design, or Architecture
  review.

### Science

- **Owns:** evidence claims, applicability, uncertainty, formulas, constants,
  claim limits, and science-specific runtime boundaries.
- **Agent:** `.github/agents/science.agent.md`
- **Skill:** `.github/skills/science-research/SKILL.md`
- **Artifacts:** Evidence Review; Science Decision Record when the routed task
  changes scientific product/runtime policy.
- **Boundary:** Science constrains product choices but does not choose product
  value.

### Trust

- **Owns:** security, privacy, identity, authorization, sensitive data, threat
  models, and dependency trust.
- **Agent:** `.github/agents/trust.agent.md`
- **Artifact:** Trust Decision Record.
- **Boundary:** Never expose secrets or weaken private-by-construction,
  encrypted-credential, per-user isolation, or server-authoritative controls.

### Operations

- **Owns:** deployment, runtime configuration, observability, capacity,
  incidents, mitigation, rollback, and recovery.
- **Agent:** `.github/agents/operations.agent.md`
- **Artifacts:** Operations Decision Record, Release Evidence, Incident Record.
- **Context:** start at `docs/ops/README.md`.
- **Boundary:** Repository workflows own deployment settings. Any config,
  secret, infra, alert, or deploy change updates `docs/ops/` in the same PR.
  Every alert needs an action group and an inventory entry in
  `docs/ops/monitoring-and-alerts.md`.

### Meta/Eval

- **Owns:** evaluation of agents, prompts, policies, routing, review effort, and
  autonomy across batches of outcomes.
- **Agent:** `.github/agents/meta-eval.agent.md`
- **Artifacts:** Evaluation Report; Policy Change Proposal when the routed task
  changes policy.
- **Boundary:** Meta/Eval does not replace Quality for the current change and
  cannot promote itself from one successful outcome.

## Control plane

### Praxys Orchestrator

`.github/agents/praxys-orchestrator.agent.md` is selected locally through
Copilot agent invocation and explicitly by the cloud assignment workflow. It
does not classify or execute work itself: it delegates classification to Work
Router, deterministic composition to `scripts/route_agentic_task.py`, and
execution to the returned loop agents.

### Work Router

`.github/agents/work-router.agent.md` identifies:

- exactly one checked-in primary object;
- every applicable checked-in impact and risk trigger;
- concise evidence and uncertainty for that classification.

`scripts/route_agentic_task.py` then deterministically returns the primary and
nested loops, agents, lead, contributors, executor, verifier, input/output and
outcome artifacts/observers, and decision-review requirement. Decision Review
Router allocates independent reviewer and human-authority slots. Work Router
adds entry and exit criteria; it does not execute or review the task.

The primary loop owns the iteration. Nested-loop order is canonical
presentation order, not a one-pass execution plan: schedule and resume agents
from artifact dependencies until every current required artifact is complete.
Outcome artifacts remain future observation obligations.

### Decision Review Router

`.github/agents/decision-review-router.agent.md` returns exactly one route:

```text
agent-resolved | agent-reviewed | human-review-required | blocked
```

The proposer cannot select its own route or review its own decision. The
executor cannot verify its own high-risk work. Routers cannot approve or
materialize human authority.

## Loop patterns

### Adding or changing a product capability

1. Praxys Orchestrator obtains the bounded classification and deterministic
   Work Contract, with Product as the primary loop.
2. Product produces or reuses an accepted Product Decision Record.
3. Science, Trust, Architecture, and Design contribute only when their decision
   classes are present.
4. Decision Review Router resolves the authorized review path.
5. Engineering implements the accepted artifacts.
6. Quality independently verifies; Operations owns rollout when applicable.
7. Product observes user outcomes; Meta/Eval observes agent and routing quality.

### Debugging a data issue

1. Praxys Orchestrator normally routes the task to Delivery with Engineering
   as executor and Quality as verifier.
2. Engineering traces sync -> writer -> database -> loader -> metric.
3. Add a reproducible test using the `tests/test_integration.py` fixture
   pattern.
4. Invoke Science only if interpretation or scientific behavior changes,
   Architecture only for cross-cutting data choices, and Trust for sensitive
   data or isolation boundaries.

### Working with sample data

- `data/sample/` contains tracked synthetic fixtures.
- `python scripts/seed_sample_data.py` copies sample data for local testing.
- `python scripts/generate_sample_data.py` regenerates fixtures after schema
  changes.
