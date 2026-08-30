# Praxys Operations Handbook

Operational runbooks and troubleshooting guides (TSGs) for running Praxys in
production. This is the single entry point for "how do I configure / deploy /
diagnose X". It complements — and links out to — the setup-oriented
[`docs/deployment.md`](../deployment.md).

> **For AI agents:** every runbook follows [`_TEMPLATE.md`](./_TEMPLATE.md) — a
> one-line *Summary*, a **Use when** line, then `Prerequisites · Steps · Verify ·
> Rollback / Recovery · Related`. Parse the **Use when** line of each runbook in
> the index below to route a task; the `## Steps` blocks are copy-pasteable.
> Runbooks with bounded autonomous actions also carry a validated hybrid machine
> block described in [`ai/README.md`](./ai/README.md).

## Runbook index

| Runbook | Use when |
|---|---|
| [environment.md](./environment.md) | You need the canonical Azure resource names / IDs / hostnames. |
| [config-and-secrets.md](./config-and-secrets.md) | You're adding, changing, or rotating an env var / secret / variable, and need to know **where** it's set. |
| [deploy.md](./deploy.md) | You're deploying the backend, frontend, or mini program — or need to roll back. |
| [labs-analysis-worker.md](./labs-analysis-worker.md) | You're provisioning, enabling, or diagnosing isolated Labs analysis compute. |
| [tencent-frontend.md](./tencent-frontend.md) | Operating EdgeOne for `.cn`, Cloudflare for `.run`, or their DNS/certificate cutovers. |
| [cn-personal-information-impact-assessment.md](./cn-personal-information-impact-assessment.md) | Reviewing the proposed China personal-information, sensitive-data, recipient, or overseas-processing boundary; it remains pending operator decision. |
| [search-discovery.md](./search-discovery.md) | You're submitting public pages to search engines, measuring SEO/GEO, or preparing the `praxys.cn` cutover. |
| [org-migration.md](./org-migration.md) | Migrating the repos from `dddtc2005` into the `praxys-run` org (OIDC pre-stage, App reinstall, tokens). |
| [monitoring-and-alerts.md](./monitoring-and-alerts.md) | You want to query a telemetry signal or wire an email/Teams alert. |
| [admin-tasks.md](./admin-tasks.md) | You're using `/admin/ops` or a focused admin route for health, incidents, users, feedback, or communications. |
| [setup-github-app.md](./setup-github-app.md) | Setting up feedback → GitHub issue filing (GitHub App auth — no token to rotate). |
| [setup-review-policy-app.md](./setup-review-policy-app.md) | Provisioning the independent GitHub App and kill switch for selective no-human-review merges. |
| [change-loop.md](./change-loop.md) | Operating the change loop (Loop A): the `agent-ready` label that hands a qualifying bug to the Copilot coding agent. |
| [incident-response.md](./incident-response.md) | The app is down / erroring and you need first-response triage. |
| [status-page.md](./status-page.md) | You need to declare / update / resolve an incident on the public status page (`/status`). |
| [sync-troubleshooting.md](./sync-troubleshooting.md) | A user's data stopped updating or a connection shows `auth_required`. |
| [backup-and-restore.md](./backup-and-restore.md) | You need to back up or restore the database. |
| [postgres-migration.md](./postgres-migration.md) | You are migrating the database from SQLite to Azure Postgres (#360), or provisioning Postgres. |
| [secret-rotation.md](./secret-rotation.md) | Rotating a secret (JWT, WeChat, feedback App key, Key Vault key). |
| [cost-and-scaling.md](./cost-and-scaling.md) | Setting cost guardrails or scaling the backend. |
| [disaster-recovery.md](./disaster-recovery.md) | Rebuilding the whole deployment from scratch + restoring data. |

## Operations decision records

- [ODR-2026-08-26-cn-provider-topology](./odr-2026-08-26-cn-provider-topology.md)
  — **PROPOSED — BLOCKED PENDING INDEPENDENT AND HUMAN REVIEW**. It grants no production
  authority and defines the proposed China topology, rollout order, rollback
  floor, emergency disable path, and Release Evidence contract.
- [TDR-2026-08-26-cn-privacy-control-boundary](./tdr-2026-08-26-cn-privacy-control-boundary.md)
  — **PROPOSED — BLOCKED** Trust boundary for rights availability, optional
  processing, release identity, and provider disclosure.
- [ADR-2026-08-26-cn-client-provenance-and-receipt-semantics](../dev/adr-2026-08-26-cn-client-provenance-and-receipt-semantics.md)
  — **PROPOSED** Architecture contract for release provenance and append-only
  legal receipts.

## Environment at a glance

| | |
|---|---|
| Subscription | `3ff02750-211c-4579-94a6-8c9af4e6d891` |
| Resource group | `rg-trainsight` |
| Backend (API) | App Service `trainsight-app` → `api.praxys.run` |
| Current frontend (SPA) | App Service `praxys-frontend` → `www.praxys.run` |
| Proposed regional target | Cloudflare Free → Azure for `.run`; EdgeOne Makers `praxys-cn` for `.cn` (pending human acceptance and cutover) |
| Secrets at rest | Key Vault `kv-trainsight` (RSA key `trainsight-master-key`) |
| Observability | Application Insights (signals prefixed `praxys.`) |

Full detail: [environment.md](./environment.md).

## Conventions

- One runbook per operational task or failure mode. Keep it self-contained.
- Ground every claim in the repo or Azure reality — link the source file/workflow.
- Commands are copy-pasteable (`az` / `gh` / KQL). Note the auth each step needs.
- Mark anything not yet verified with `TODO(owner)` rather than guessing.
- Keep destructive or judgment-heavy procedures prose-only. Structured actions
  must resolve through [`ai/tool-registry.yaml`](./ai/tool-registry.yaml), state
  their policy tier, and provide deterministic verification signals.

## Coverage & roadmap

Incident response now validates the first hybrid AI-native runbook schema and
generates route evaluation fixtures in CI. Severity and escalation ownership
are defined without publishing private contacts. Production restore timing,
Key Vault re-wrap, and permanent cost/scale commitments remain explicitly
deferred at their runbooks because each needs operator approval or production
tooling; no value is guessed. Runbooks stay repository-owned rather than being
duplicated into `plugins/praxys` until the contract has at least two autonomous
consumers. Add new runbooks against [`_TEMPLATE.md`](./_TEMPLATE.md) and link
them from the index above.
