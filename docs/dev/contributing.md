# Contributing

How to extend Praxys with new features.

## Adding a New Metric

1. **Add a pure function** to `analysis/metrics.py`:
   - Type hints on all parameters and return value
   - Docstring explaining the metric and citing the source
   - No I/O, no side effects — data in, result out

2. **Call it from `api/deps.py`** in `get_dashboard_data()`:
   - Add the result to the returned dict

3. **Expose via API route** in `api/routes/`:
   - Add to an existing route, or create a new route file
   - Register in `api/routes/__init__.py`

4. **Add TypeScript type** to `web/src/types/api.ts`

5. **Build UI component** in `web/src/components/`

6. **Add to the relevant page** in `web/src/pages/`

7. **Add test** in `tests/`

8. **Update docs**: Add to `CLAUDE.md` if it changes the architecture, `docs/features.md` for user-facing description, `docs/dev/api-reference.md` for the endpoint.

> **Claude Code tip:** after the edits, ask the `metric-addition-reviewer` subagent to verify the 7-step checklist is complete and that your formula has a citation. The `api-contract-reviewer` subagent will cross-check that your new field in `api/deps.py` matches the TS interface in `web/src/types/api.ts`.

## Adding a New Data Source

1. **Create sync script** `sync/{source}_sync.py`:
   - Follow the pattern in `garmin_sync.py`
   - Use `db/sync_writer.py` for writing synced data to the database
   - Accept `user_id` and `from_date` parameters

2. **Define database models** in `db/models.py` — add SQLAlchemy models for the new source's tables

3. **Register in `data_loader.py`** — add to both `load_all_data()` and `load_data()` (provider-based loading)

4. **Add credentials** to `sync/.env.example`

5. **Add platform capabilities** to `analysis/config.py` `PLATFORM_CAPABILITIES`

6. **Update sample data generator** `scripts/generate_sample_data.py`

7. **Update docs**: `CLAUDE.md` data sources table, `docs/features.md`, `docs/getting-started.md` credentials section.

## Adding a New Skill

> **Plugin lives in its own repo.** `plugins/praxys/` is a git submodule of the public [`praxys-run/praxys-coach-plugin`](https://github.com/praxys-run/praxys-coach-plugin) repo. Skill changes are PRed there; once merged, bump the submodule pointer in this repo (`git submodule update --remote plugins/praxys && git add plugins/praxys && git commit`).

1. **Create skill directory** `plugins/praxys/skills/{skill-name}/`

2. **Write `SKILL.md`** with frontmatter:
   ```yaml
   ---
   name: skill-name
   description: >-
     When to trigger this skill. Be specific about trigger phrases.
   ---
   ```

3. **Add MCP tool** (if needed) in `plugins/praxys/mcp-server/`:
   - Define the tool handler following existing MCP tool patterns
   - The tool will be available to both Claude Code and Copilot CLI via the plugin's MCP server

4. **Add helper script** (if needed) in `scripts/`:
   - Follow the `build_training_context.py` pattern
   - Set `sys.path` to project root
   - Output JSON to stdout
   - Accept `--pretty` flag

5. **Update docs**: `docs/skills.md`, `CLAUDE.md` skills table.

## Adding a New Science Theory

Science changes use two linked, versioned science records before implementation:

- An **Evidence Review** records what the literature supports.
- A **Science Decision Record (SDR)** records Praxys's scientific
  interpretation, parameters, applicability, claim limits, and runtime
  boundary.

When the work also changes product behavior, Product separately owns a Product
Decision Record covering the user problem, options, promise, trade-offs,
minimum valuable scope, non-goals, and outcome plan. Science artifacts are
dependencies of that product decision; they do not own product value. The
shared record contract is specified in
[`agentic-operating-model.md`](agentic-operating-model.md).

New records use the artifact review workflow documented in
[`science-review-artifacts.md`](science-review-artifacts.md). The canonical
typed record generates a human review packet and a separate machine JSON
contract with matching digests. Humans approve the generated packet in an
authenticated GitHub or agent session. Session approvals are mirrored by the
agent to an exact human-authenticated GitHub PR comment; trusted automation
materializes the role-scoped artifact. Runtime code consumes only the generated
contract and never derives values from prose.

Artifact-mode SDRs also provide a typed `decision_review` manifest. The science
packet begins with its concise scientific decision sheet. Every contract
parameter group must be mapped to an explicit proposed decision or deferral.
The complete evidence, parameter, and contract material remains a collapsed
audit appendix rather than the reviewer's primary task. Product value belongs
in the linked Product Decision Record, not the SDR.

### Research before changing science

Use the repository-owned
[`science-research`](../../.github/skills/science-research/SKILL.md) skill
before changing a scientific claim, formula, constant, safety boundary, theory,
or user-facing interpretation. Its **Research-only** mode creates a bounded,
auditable evidence update without changing accepted behavior; its **Decision
proposal** mode creates any required draft SDR, then hands the evidence and
science artifacts to
[`Praxys Product`](../../.github/agents/product.agent.md), which owns the
separate product decision and outcome plan.

The athlete-facing `/science` plugin skill remains browse/select only. It does
not research literature, edit evidence records, or make product decisions.

Every new theory added after the registry introduction must link an accepted
SDR. Unlinked pre-existing theories remain supported only as a legacy migration
exception; do not use that compatibility path for new science.

Use a **rapid review** for a bounded product question when the important
databases, exact search strings, inclusion/exclusion rules, applicability,
limitations, and known conflicts can be recorded reproducibly. Use a
**rigorous review** when the decision is safety-critical, evidence is broad or
materially conflicting, a quantitative effect will drive user-facing output,
or the result is intended to support several models. A rigorous review should
add a protocol, duplicate screening or extraction where practical, a formal
risk-of-bias/quality appraisal, and a complete search log. Label the method
honestly; neither level lets schema validation declare a paper true.

1. **Add an Evidence Review** at
   `data/science/evidence/{topic}/evidence-{topic}-v{N}.yaml`:
   - Set `approval_mode: artifact` for new records. Human approval lives in a
     digest-bound file beneath `data/science/approvals/`, not in the legacy
     `human_reviewers` list.
   - Identify authors, purpose, and lifecycle status.
   - Preserve the exact searches, search date, selection rules, scope,
     evidence strength, effect estimates, applicability, limitations,
     conflicting findings, gaps, and follow-up questions.
   - Give every claim and citation a stable ID. Include a DOI, PMID, or stable
     URL for each citation; identifier syntax checks do not verify correctness.

2. **Add an SDR** at
   `data/science/decisions/sdr-{decision}-v{N}.yaml`:
   - Set `approval_mode: artifact` and declare
     `artifact_policy.runtime_state`. Draft decisions start `inactive`.
   - Link the exact evidence-review and claim IDs used.
   - Record the accepted interpretation, rejected alternatives, claim limits,
     applicability, safety/privacy implications, validation and falsification
     plans, and every affected model/API/client/`ScienceNote`.
   - Classify every model value as `published`, `estimate`, or `guardrail`.
     Published values require a supporting claim; estimates and guardrails
     require an explicit Praxys rationale. This includes `params` plus
     behavior-driving `signal`, `diagnosis`, and `tsb_zones` values.
   - Only an explicit human `decision_approver` approval bound to the displayed
     digest may move an artifact-mode SDR to `accepted`. The human may approve
     in GitHub or an authenticated agent session; the agent mirrors session
     approval to a human-authenticated GitHub PR comment, then automation may
     materialize the YAML and lifecycle transition. It must preserve human
     identity and may not infer or widen approval. Runtime activation remains
     blocked until `implementation_reviewer` approval also binds the exact
     reviewed code diff and validation evidence.

   If the proposal changes product value or user behavior, also create or reuse
   the separate Product Decision Record required by the Work Router. Do not put
   product ownership into the SDR merely because the product decision depends
   on science.

3. **Create or update the canonical English theory YAML** in
   `data/science/{pillar}/{theory_id}.yaml`:
   ```yaml
   id: theory_id
   pillar: load|recovery|prediction|zones
   name: "Display Name"
   model_version: model-v1
   science_decision_id: sdr-example-v1
   description: Brief description
   simple_description: Plain-language explanation
   advanced_description: |
     Detailed technical explanation with formulas and tables.
   params:
     # Theory-specific parameters
   ```

   Linked theories resolve citations from the registry; do not copy citation
   metadata into theory or locale files. Localized YAML should contain only
   translated user-facing prose and identifiers needed by the locale loader.

4. **Generate review and implementation artifacts**:

   `python scripts/generate_science_artifacts.py`.

   Review
   `data/science/generated/review-packets/<record-id>.md`. The exact contract
   JSON embedded in the packet must match
   `data/science/generated/contracts/<sdr-id>.json`.

5. **Regenerate the index**:
   `python scripts/generate_science_registry_index.py`.

6. **Validate** with
   `python scripts/generate_science_artifacts.py --check` and
   `python -m pytest tests/test_evidence_registry.py
   tests/test_science_artifacts.py tests/test_science.py`.
   Then test the theory in Settings or through the `/science` skill.

### Updating a review without rewriting history

Do not edit the methods, claims, interpretations, or parameter rationale in an
accepted record. While a successor is under review, add the new version with
`status: draft`, leave `supersedes` empty, and leave the accepted predecessor
unchanged. Enumerate every accepted SDR that references the predecessor and
draft successor decision coverage for all of them before proposing a lifecycle
transition.

Only after explicit human approval should one atomic change accept the
successor Evidence Review and successor SDRs, activate reciprocal
`supersedes`/`superseded_by` links, mark every replaced record `superseded`,
bump implementation model versions when behavior changes, and update all
governed theories' `science_decision_id` values. Regenerate
`data/science/REGISTRY.md` in that approved change. Retain retired and
superseded files so a past model version remains auditable.

When a new review version uses the same paper, repeat its stable citation ID
and identical metadata; the registry de-duplicates that source across versions.
Use new, globally unique claim IDs for the new review's claims.

## Keeping UI and CLI Skills in Sync

The web API routes and CLI skill scripts share the same computation layer (`get_dashboard_data()` in `api/deps.py`). They also share **view helpers** in `api/views.py` for extracting presentation-ready data:

- `last_activity()` — most recent activity summary
- `upcoming_workouts()` — next N planned workouts
- `week_load()` — current week load vs plan
- `fitness_summary()` — latest CTL/ATL/TSB values

When adding a new field or changing how data is extracted for display:
1. Add or modify the function in `api/views.py`
2. Both API routes and CLI scripts get the change automatically
3. Never duplicate extraction logic between routes and scripts

## Making a UI Change

Invoke the repository `ui-quality` skill for every user-visible change in
`web/` or `miniapp/`. It loads the vendored Impeccable playbooks, `PRODUCT.md`,
`DESIGN.md`, the design-system rules, rendered desktop/mobile verification,
state and accessibility coverage, web/miniapp parity, and the required PR
evidence.

The full flow and maintenance instructions live in
`docs/dev/ui-quality-harness.md`. At minimum:

1. Invoke `ui-quality` before editing and run Impeccable context once for the
   primary target.
2. Preserve the incumbent visual world for bounded changes; use `shape` for a
   new or materially reworked flow and `polish` before handoff.
3. Inspect the real feature with sample data at desktop and mobile sizes, with
   keyboard navigation and relevant states.
4. Keep detailed screenshots and recordings local under the gitignored
   `test-screenshots/ui-quality/<branch-or-pr>/` directory. Use screenshots for
   static/state comparisons, a short video for sequence-dependent interaction,
   and publish only the minimum media needed for asynchronous PR review.
5. Run the web build, miniapp typecheck when applicable, and
   `python scripts/check_ui_quality.py --base origin/main --head HEAD --skip-evidence`.
6. Complete the PR template's `## UI quality` block, including the primary
   journey and reviewer handoff mode. If a browser is
   unavailable, keep the PR draft and state that rendered verification remains
   incomplete.

## Code Conventions

### Python
- Type hints on all function signatures
- Docstrings on public functions
- Metrics in `analysis/metrics.py` must be pure functions
- Data loading in `analysis/data_loader.py`
- API routes are thin wrappers

### Frontend
- TypeScript strict mode
- All API responses typed in `web/src/types/api.ts`
- Mandatory `ui-quality` skill and Impeccable-led rendered review for user-visible changes
- `useApi<T>` hook for data fetching
- shadcn/ui components (never raw HTML elements)
- Tailwind CSS v4 with OKLCH color variables
- Recharts with colors from `@/lib/chart-theme.ts`
- Data numbers use `font-data` CSS class

### Git
- Commit messages reference the project folder: `trail-running: add zone distribution chart`
- Never put sensitive content in commit messages

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_metrics.py -v

# Run with coverage
python -m pytest tests/ --cov=analysis --cov=api
```

## Documentation Updates

When making changes, update the relevant docs:

| Change | Update |
|--------|--------|
| New module or page | `CLAUDE.md` module map, `docs/dev/architecture.md` |
| New/changed endpoint | `docs/dev/api-reference.md` |
| New skill | `docs/skills.md`, `CLAUDE.md` skills table |
| New user feature | `docs/features.md` |
| Setup changes | `README.md`, `docs/getting-started.md` |
| Convention changes | `CLAUDE.md` |
| DB model changes | `CLAUDE.md` data sources |
| New Claude automation (hook, agent, dev skill) | `CLAUDE.md` "Claude Code Automations" section |
| Agentic loop / self-improvement / autonomy change | `docs/dev/agentic-loops.md`, `docs/dev/agentic-operating-model.md`, and `docs/dev/copilot-execution-parity.md` when entry points or tools change; tracker `#377` |
| UI quality harness / design-agent policy | `docs/dev/ui-quality-harness.md`, `CLAUDE.md`, and `docs/ops/change-loop.md` when coding-agent behavior changes |
| Config / secret / infra / deploy change (env var, GitHub Actions secret/variable, App Service setting, Azure resource, RBAC, deploy workflow) | **`docs/ops/` handbook** — esp. `config-and-secrets.md` (where it's set + how to provision it) |

## Claude Code Dev Tooling

The repo ships committed Claude Code automations in `.claude/`. Full inventory is in `CLAUDE.md` under "Claude Code Automations". Quick reference:

- **Post-edit hooks** run automatically after every `Edit`/`Write`:
  - `.claude/hooks/pytest_on_py.py` (PostToolUse, `.py` files) — runs pytest via the project venv with fail-fast and surfaces failures to Claude via stderr + exit 2.
  - `.claude/hooks/web_lint.py` (PostToolUse, `.ts(x)` under project `web/`) — per-file ESLint; lint errors go to stderr + exit 2 so Claude sees them and can self-correct.
  - `.github/skills/impeccable/scripts/hook.mjs` — shared web/miniapp design detector on edits plus a stop-time deep pass.
- **Reviewer agents** (read-only; auto-triggered by Claude when their description matches the current change, or invoked explicitly via the `Agent` tool / `subagent_type`):
  - `science-reviewer` — citation and published-value checks for `analysis/` and `data/science/`.
  - `metric-addition-reviewer` — verifies the 7-step add-metric checklist is complete.
  - `api-contract-reviewer` — cross-reads Python response shapes against TS interfaces.
- **Dev skills**:
  - `ui-quality` — mandatory cross-agent UI workflow; delegates to the canonical Impeccable copy under `.github/skills/`.
  - `wechat-devtools` — bridges WSL2 agents to the separately installed Windows
    Nightly WeChat DevTools. It loads Tencent's installed `wechatide-skill`
    rather than vendoring a stale copy, and provides simulator, compile,
    screenshot, console/network, preview, and upload workflows.
  - `seed-and-preview` — resets the local DB to sample data and boots API + Vite. User-invocable only (has side effects). See `.claude/skills/seed-and-preview/SKILL.md`.

If a hook is getting in your way, edit `.claude/settings.json`. If a reviewer agent misses a pattern, extend its prompt in `.claude/agents/<name>.md` — they are just markdown with YAML frontmatter.
