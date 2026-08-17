# AGENTS.md — Multi-Agent Workflow Guide

## Agent Roles

### Data Pipeline Agent
- **Focus:** `sync/`, `db/sync_writer.py`, `db/models.py`, `analysis/data_loader.py`
- **Tasks:** Add new data sources, fix sync issues, extend database schemas
- **Context needed:** `.env.example` for server config, `db/models.py` for schema, `data_loader.py` for loading conventions
- **Key rule:** All sync scripts write via `db/sync_writer.py` upsert functions for dedup-on-write

### Analysis Agent
- **Focus:** `analysis/metrics.py`, `api/deps.py`
- **Tasks:** Add new metrics, improve predictions, fix computation bugs
- **Context needed:** Read the "Split-Level Power Analysis" section in CLAUDE.md first
- **Key rule:** All metric functions must be **pure** — no file I/O, no side effects, no global state. Data flows in via parameters, results flow out via return values.

### Frontend Agent
- **Focus:** `web/src/`, `miniapp/`, and shared product/design context
- **Tasks:** Add UI components, new pages, improve visualizations, and preserve web/miniapp feature parity
- **Context needed:** `.github/skills/ui-quality/SKILL.md`, `PRODUCT.md`, `DESIGN.md`, `docs/dev/design-system.md`, `web/src/types/api.ts`, and the `useApi` hook pattern
- **Key rule:** Invoke the `ui-quality` skill for every user-visible change. It must route through Impeccable, rendered desktop/mobile inspection, state and accessibility coverage, and the CI evidence block. All data comes from API via `useApi<T>`; data numbers use `font-data`.
- **WeChat desktop boundary:** Tencent provides no headless/no-focus simulator mode. On Windows + WSL2, use `wechat-devtools` only during a user-approved foreground window, never from an unattended background agent, and never via raw Windows focus/cursor/mouse/keyboard automation.

### API Agent
- **Focus:** `api/main.py`, `api/deps.py`, `api/auth.py`, `api/routes/`
- **Tasks:** Add endpoints, modify data layer
- **Context needed:** `api/deps.py` `get_dashboard_data()` is the central data function — all routes call it fresh per request. All endpoints require JWT auth (see `api/auth.py`)
- **Key rule:** Routes are thin — computation belongs in `analysis/metrics.py`, not in route handlers

### AI Features Agent
- **Focus:** `api/ai.py`, `api/routes/ai.py`, `analysis/providers/ai.py`, frontend AI components
- **Tasks:** Extend LLM-powered coaching, natural language queries, plan generation
- **Context needed:** `api/deps.py` for data access, existing metrics for context injection, `plugins/praxys/` (git submodule of public [`praxys-run/praxys-coach-plugin`](https://github.com/praxys-run/praxys-coach-plugin)) for MCP tools
- **Key rule:** AI features must be optional — guard with `is_available()`, app works fully without API key

### Product Policy Agent
- **Focus:** user problems, product value, evidence-to-product decisions, and schema-v2 SDRs
- **Tasks:** turn accepted or draft evidence into user scenarios, product options, a recommended experience, a minimum valuable slice, and measurable success/guardrail outcomes
- **Context needed:** `.github/agents/product-policy.agent.md`, `PRODUCT.md`, `docs/dev/product-decision-loop.md`, relevant Evidence Reviews/SDRs, current behavior, and representative feedback or telemetry
- **Key rule:** Scientific constraints are inputs, not the product recommendation. State what value Praxys should provide and why; never approve your own decision or implementation.

### Decision Review Router
- **Focus:** cross-cutting allocation of agent review versus human review
- **Tasks:** independently route product, science, implementation, UI, and operations judgments as `agent-resolved`, `agent-reviewed`, `human-review-required`, or `blocked`
- **Context needed:** `.github/agents/decision-review-router.agent.md`, `config/agent-loop-policies.json`, accepted policies, independent reviewer findings, and observed outcomes
- **Key rule:** The proposer and implementation agent cannot route or approve their own work. Default human review applies to unpromoted judgment classes.

### Ops / DevOps Agent
- **Focus:** production operations — deploy, App Service config, secrets, monitoring/alerts, admin tasks
- **Tasks:** wire alerts, rotate/add config, deploy & rollback, diagnose prod issues
- **Context needed:** the operations handbook **`docs/ops/README.md`** (runbook index). Each runbook is self-contained: `Prerequisites · Steps · Verify · Rollback`. `docs/deployment.md` for one-time Azure setup.
- **Key rule:** App Service settings are owned by `deploy-backend.yml`, not the portal — change the GitHub secret/variable and re-deploy. Never commit secrets. **Any config / secret / infra / deploy change must update `docs/ops/` (esp. `config-and-secrets.md`) in the same PR** — where it's set and how to provision it.
- **Monitoring / alerts:** the live alert inventory + cost model is `docs/ops/monitoring-and-alerts.md`. Log alerts bill by evaluation frequency (every frequency ≥15 min hits the same 0.50 floor — only sub-15-min costs more); metric alerts are flat and frequency-free. Every alert needs an action group (or it pages nobody) and a row in the inventory table — update it in the same PR.

## Workflow Patterns

### Adding a Feature End-to-End
1. **Product Policy Agent** confirms the accepted product behavior or drafts a product-first decision; use **Science Research** when evidence is needed
2. **Decision Review Router** resolves the authorized review path and narrows any human decision
3. **Analysis Agent** adds metric or computation changes plus tests
4. **API Agent** exposes the behavior via `deps.py` + route
5. **Frontend Agent** invokes `ui-quality`, then adds types, web/miniapp UI, and page integration
6. Run `python -m pytest tests/`, `cd web && npm run build`, the relevant miniapp checks, and `python scripts/check_ui_quality.py --base origin/main --head HEAD --skip-evidence`

### Debugging a Data Issue
1. **Data Pipeline Agent** checks sync output and database integrity
2. **Analysis Agent** traces through `data_loader.py` → `metrics.py` with sample data
3. Use `tests/test_integration.py` fixture pattern for reproducible test cases

### Working with Sample Data
- `data/sample/` contains tracked synthetic CSVs for all 7 data sources
- `python scripts/seed_sample_data.py` copies sample → data/ for local testing
- `python scripts/generate_sample_data.py` regenerates sample data after schema changes
