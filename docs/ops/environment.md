# Environment reference

> **Summary:** The canonical Azure resources, names, IDs, and hostnames for the
> production Praxys deployment.
> **Use when:** A runbook or command needs a resource name / subscription / RG,
> or you're onboarding to the Azure environment.

> Note: many resources still carry the legacy `trainsight` name — the on-disk
> SQLite file and several resource names predate the Praxys rename and were
> kept to avoid data-migration risk. This is expected.

## Azure

| Thing | Value | Source |
|---|---|---|
| Subscription ID | `3ff02750-211c-4579-94a6-8c9af4e6d891` | `docs/perf-baselines/ci-setup.md` |
| Resource group | `rg-trainsight` | `.github/workflows/deploy-backend.yml` |
| Backend App Service | `trainsight-app` | `deploy-backend.yml` (`--name trainsight-app`) |
| Frontend App Service | `praxys-frontend` | `deploy-frontend-appservice.yml` |
| App Service transport | `trainsight-app` and `praxys-frontend` both report `httpsOnly=true`; direct HTTP requests redirect to HTTPS (verified 2026-08-22) | [deploy.md](./deploy.md), [tencent-frontend.md](./tencent-frontend.md) |
| App Service plan | `plan-trainsight` (Linux B1, East Asia) | `docs/deployment.md`, `frontend_server` notes |
| PostgreSQL (**primary DB**, live 2026-07-04) | `praxys-pg` Flexible Server (Burstable B1ms, PG16, DB `praxys`, Entra auth, PITR 14d) | [postgres-migration.md](./postgres-migration.md); `PRAXYS_PG_SERVER` var |
| Labs isolated compute (opt-in) | Service Bus namespace tagged `praxysComponent=labs-analysis`, queue `labs-environment-response`; Container Apps environment `cae-praxys-jobs`, job `praxys-labs-environment-worker`, UAMI `id-praxys-labs-worker` | `infra/labs-worker.bicep`; [labs-analysis-worker.md](./labs-analysis-worker.md) |
| Key Vault | `kv-trainsight` (`https://kv-trainsight.vault.azure.net`) | live `KEY_VAULT_URL` |
| — RSA key | `trainsight-master-key` | live `KEY_VAULT_KEY_NAME` |
| Frontend Application Insights | `appi-trainsight` (Application ID `d10e388f-3a26-4c3d-b57d-d83fc4637a9b`; browser/RUM, local auth enabled) | `.github/azure-observability.env` |
| Backend Application Insights | `appi-praxys-backend` (Application ID `066f94a3-a340-498d-9ee1-6f093a7b8911`; managed-identity ingestion, local auth disabled, 30-day retention) | `.github/azure-observability.env`, `scripts/appinsights_boundary.sh`; live config verified 2026-08-22 |
| Log Analytics workspace | `log-trainsight` (shared storage, 30-day retention; queries must retain component scope / `_ResourceId`) | `.github/azure-observability.env`; live config verified 2026-08-22 |
| Perf-baseline storage | `stperftrainsight` (RG `rg-trainsight`, East Asia) | `docs/perf-baselines/ci-setup.md` |
| CI/deploy app registration | `trainsight-cicd` — appId `d3deb736-e95d-400e-b5a5-c2f76b23ae25` (OIDC federated creds `github-deploy`, `i18n`) | live `az ad app` |

## Dormant regional delivery target

| Thing | Value | Source |
|---|---|---|
| Mainland web frontend | EdgeOne Makers Git-integrated project `praxys-cn`; static SPA only, protected `main`, managed HTTPS | [China launch decision](./cn-web-private-alpha.md), [tencent-frontend.md](./tencent-frontend.md) |
| Preserved international frontend | Existing `.run` Azure/Cloudflare path; no China launch workflow mutation | [China launch decision](./cn-web-private-alpha.md) |
| Preserved API boundary | `api.praxys.run` remains DNS-only and resolves to `trainsight-app.azurewebsites.net`; no mainland API or proxy | [China launch decision](./cn-web-private-alpha.md) |

The design is dormant. One-time EdgeOne Git project, domain, DNS, and TLS setup
is manual. The repository does not claim that any public hostname or provider
setting is currently ready. The operator accepted PIPIA `1.2-public-parity` and
its overall **Medium** residual risk on 2026-08-31. Live control verification
and approval of the `china-production` environment remain separate human
prerequisites.

## Hostnames

| Surface | URL |
|---|---|
| API | `https://api.praxys.run` |
| Web app | `https://www.praxys.run` |
| Dormant mainland web app | `https://praxys.cn` / `https://www.praxys.cn` (public registration follows the global gate; human enable required) |

## China processing boundary

- Core authenticated processing remains in Azure East Asia (Hong Kong SAR)
  under the operator-recorded scope in
  [PIPIA-CN-2026-08-25-01](./cn-personal-information-impact-assessment.md).
- `.cn` requests are classified by exact origin and carry the current notice,
  legal digest, and API contract. Legacy client source/version/release headers
  are ignored; source SHA remains diagnostic in deployed health metadata.
  Missing or stale compatibility claims fail before personal route processing.
- Existing Miniapp ordinary/auth processing remains enabled against
  `api.praxys.run`; robot 5 development upload stays automatic while trial,
  review, and production publication stay manual. `launch-cn.yml` never
  uploads or publishes the Miniapp.
- `.cn` browser Application Insights and web/Miniapp allowlisted product
  events use the recorded minimized boundary. Browser Statsig remains disabled
  on `.cn` pending issue #754.
- Backend Statsig downloads rules and evaluates them locally with user logging
  and diagnostics disabled.
- Ordinary production Azure AI is available under current Terms while
  `PRAXYS_DISABLE_BACKGROUND_AI=false`. China launch and backend deployment
  observe and preserve that explicit setting; they never toggle it. External
  feedback publication remains separately controlled.
- Backend request/security telemetry remains in Hong Kong with a 30-day
  component/workspace retention limit.

## Identity & auth model

- **App → Key Vault / backend App Insights:** the backend App Service uses its
  **system-assigned managed identity** today (no secret in app settings). If
  `AZURE_CLIENT_ID` is configured later, runtime and deployment preflight switch
  to the matching attached user-assigned identity. The effective MI holds *Key
  Vault Crypto User* (key wrap/unwrap), *Monitoring Metrics Publisher*, and
  *Monitoring Reader* on `appi-praxys-backend`. That component disables local
  authentication; the public browser connection string points only to
  `appi-trainsight`.
  See `api/main.py`, `.github/azure-observability.env`, and
  `scripts/appinsights_boundary.sh`.
- **GitHub Actions → Azure:** OIDC federated credentials on `trainsight-cicd`
  (tenant `bd18218b-ffc1-4eef-b717-fb07368336c0`, application
  `d3deb736-e95d-400e-b5a5-c2f76b23ae25`; subjects
  `repo:praxys-run/praxys:ref:refs/heads/main` and `…:i18n-azure-openai`).
  No client secret. The identity also has *Cognitive Services OpenAI User* on the
  Foundry resource. Agentic Workflows reuse the `main` subject for keyless
  `gpt-5.4` inference: PR validation completes first, then `workflow_run` starts
  the agent from the default branch. Moving repos to the `praxys-run` org
  changes these subjects — see [org-migration.md](./org-migration.md). See
  [config-and-secrets.md](./config-and-secrets.md). The dormant China `enable`
  job uses environment `china-production` and therefore requires the additional
  exact subject `repo:praxys-run/praxys:environment:china-production` before
  human enable. Emergency disable uses the protected-main subject and is not
  delayed by the environment. This repository change does not assert that
  federation exists or create it.
- **Labs API -> queue -> worker:** the backend system identity is Service Bus
  Data Sender on the dedicated queue. `id-praxys-labs-worker` is Service Bus
  Data Receiver, Monitoring Metrics Publisher on `appi-praxys-backend`, and a
  non-admin PostgreSQL Entra principal with explicit table/column grants. Queue
  messages contain only opaque job UUIDs. See
  [labs-analysis-worker.md](./labs-analysis-worker.md).

## Data

- **Primary store:** **Azure Database for PostgreSQL** `praxys-pg` (live since
  2026-07-04; `PRAXYS_DATABASE_URL` set, keyless Entra/MI auth), schema via
  Alembic (`alembic upgrade head` on boot, advisory-locked). The code is
  dual-backend: with `PRAXYS_DATABASE_URL` unset it falls back to SQLite
  `trainsight.db` at `DATA_DIR=/home/data` (schema via `create_all`) — used for
  local dev / tests and as the frozen rollback artifact. See
  [postgres-migration.md](./postgres-migration.md).
- **Platform credentials:** Fernet-encrypted in the DB; each user's Fernet DEK is
  wrapped by the Key Vault RSA master key (`db/crypto.py`).

## Repo governance

- **Owner:** the repos live in the **`praxys-run`** org (GitHub **Free**; public repos keep branch protection + unlimited Actions minutes). Migrated from the `dddtc2005` personal account on 2026-07-10 — see [org-migration.md](./org-migration.md).
- **`main` protection is two layers.** (1) **Classic branch protection**: required `backend-tests` and `frontend-quality` contexts from `ci-premerge.yml` block backend or frontend regressions, **admins included** (`enforce_admins`); managed via `repos/praxys-run/praxys/branches/main/protection`. (2) **Repo ruleset `default`** (id `15208143`): a pull request is required, merges are **squash-only**, deletion plus non-fast-forward updates are blocked, and `backend-tests`, `frontend-quality`, plus `selective-review-policy` are required against the latest `main`. Since 2026-07-26, `required_approving_review_count` is **`0`**: human and policy-App reviews remain encouraged for risky, security-sensitive, science-affecting, or autonomous changes, but required statuses are the merge authority for the solo-maintainer workflow. The ruleset retains the repository-role admin `Always` bypass as a maintainer capability; normal green PRs do not need it. Managed via the rulesets API. ⚠️ **Transfer gotcha:** moving a repo between accounts **wipes the ruleset's `bypass_actors`** — after the org migration the bypass list was empty (then deadlocking solo self-merge under the former one-approval policy) and had to be restored (`PUT repos/praxys-run/praxys/rulesets/15208143`, requires `admin:org` scope + the full ruleset body). Transfers must still restore the bypass deliberately if this admin capability is meant to remain.

## Related

- [config-and-secrets.md](./config-and-secrets.md) · [deploy.md](./deploy.md)
- [China public web launch](./cn-web-private-alpha.md)
- `docs/deployment.md` (one-time Azure setup) · `docs/perf-baselines/azure-provisioning.md`

---
_Last reviewed: 2026-08-29 · Owner: Operations_
