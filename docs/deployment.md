# Deployment Guide

## Usage Modes

**Deployed cloud app + local CLI plugin (recommended for all users):**
- Web dashboard currently deployed on Azure App Service for `praxys.run`
- Gated target delivery adds Cloudflare for the `.run` frontend and EdgeOne
  for the ICP-filed `.cn` frontend only after the regional release gates pass
- Users register, connect platforms, sync, and view dashboard in the browser
- CLI plugin (Claude Code / Copilot) connects to the deployed API via `PRAXYS_URL`
- AI features (training plans, insights) run through the CLI plugin's MCP tools
- Per-user data, encrypted credentials, background sync — all handled by the backend

**Fully local (development / personal use):**
- Backend + frontend run on localhost
- Same auth flow as cloud (register, login, JWT)
- First registered user becomes admin automatically
- Useful for development, personal training, or trying out the app

## Joining an Existing Deployment

If a Praxys instance is already deployed and you want to contribute as a developer, you do not need to deploy your own. Ask the project admin for:

1. **Access to the Azure resource group** (`rg-trainsight`) — Contributor role is sufficient for most development tasks
2. **An invitation code** — to register an account on the deployed instance
3. **Repository access** — clone the repo and follow [Local Development Setup](#local-development-setup) below for backend/frontend development

The deployed cloud instance and your local dev instance use the same codebase. You can develop locally and deploy via the existing CI/CD pipeline.

---

## Local Development Setup

### 1. Create `.env` from the example

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```bash
# Required: encryption key for platform credentials
# Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
PRAXYS_LOCAL_ENCRYPTION_KEY=<your-generated-key>

# Optional: JWT secret (tokens won't survive restarts without this)
# Generate: python -c "import secrets; print(secrets.token_urlsafe(48))"
PRAXYS_JWT_SECRET=<your-generated-secret>

# Optional: admin email (registers without invitation, always admin)
# PRAXYS_ADMIN_EMAIL=you@example.com
```

### 2. Install dependencies and start servers

```bash
# Backend
pip install -r requirements.txt
python -m uvicorn api.main:app --reload

# Frontend (separate terminal)
cd web && npm install && npm run dev
```

The database (`data/trainsight.db`) is created automatically on first startup. New columns are added automatically via auto-migration — no manual migration steps needed.

### 3. Register and configure

1. Open the frontend (default: `http://localhost:5173`)
2. Register — the first user becomes admin automatically
3. Connect platforms via the Settings page
4. Trigger a sync

## Prerequisites (Azure)

- Azure subscription
- GitHub repository (praxys-run/praxys)
- Azure CLI installed locally

## Azure Setup (One-Time)

### Resource Names

| Resource | Name | Purpose |
|----------|------|---------|
| Resource group | `rg-trainsight` | All Praxys resources, East Asia |
| App Service Plan | `plan-trainsight` | Linux B1, hosts both sites |
| App Service (backend) | `trainsight-app` | FastAPI / API at `api.praxys.run` |
| App Service (frontend) | `praxys-frontend` | Static SPA at `www.praxys.run` + apex |
| EdgeOne Makers project (frontend, gated target) | `praxys-cn` | Planned Git-integrated static SPA for `praxys.cn` + `www.praxys.cn` |
| Key Vault | `kv-trainsight` | Per-user DEK wrapping master key |

> **History:** prior versions of this doc referenced an `swa-trainsight` Static Web App. SWA was retired during F4 because Azure SWA Free routes to whichever region the global ASE picks (often Amsterdam), which added 200-300 ms of cold-load latency for CN users. Frontend now lives on a dedicated App Service site in East Asia next to the backend.

### 1. Resource Group

```bash
az group create --name rg-trainsight --location eastus
```

### 2. App Service Plan (Linux B1)

```bash
az appservice plan create \
  --name plan-trainsight \
  --resource-group rg-trainsight \
  --sku B1 \
  --is-linux
```

### 3. App Service (Python 3.12)

```bash
az webapp create \
  --name trainsight-app \
  --resource-group rg-trainsight \
  --plan plan-trainsight \
  --runtime "PYTHON:3.12"

az webapp update \
  --name trainsight-app \
  --resource-group rg-trainsight \
  --https-only true
```

### 4. Enable Managed Identity

```bash
az webapp identity assign \
  --name trainsight-app \
  --resource-group rg-trainsight
```

Save the `principalId` from the output for step 7.

### 5. Create Key Vault

```bash
az keyvault create \
  --name kv-trainsight \
  --resource-group rg-trainsight \
  --location eastus \
  --sku standard
```

### 6. Create RSA Key in Key Vault

```bash
az keyvault key create \
  --vault-name kv-trainsight \
  --name credential-encryption-key \
  --kty RSA \
  --size 2048
```

### 7. Grant App Service Key Vault Access

```bash
az role assignment create \
  --role "Key Vault Crypto User" \
  --assignee <principalId-from-step-4> \
  --scope $(az keyvault show --name kv-trainsight --query id -o tsv)
```

### 8. Create Frontend App Service site

A second site on the same Plan B1 — App Service Plans support up to 10 sites, so this is $0 incremental.

```bash
az webapp create \
  --name praxys-frontend \
  --resource-group rg-trainsight \
  --plan plan-trainsight \
  --runtime "PYTHON:3.12"

# HTTPS-only + startup command + Always On + HTTP/2 + Oryx build during deploy
az webapp update \
  --name praxys-frontend \
  --resource-group rg-trainsight \
  --https-only true

az webapp config set \
  --name praxys-frontend --resource-group rg-trainsight \
  --startup-file "uvicorn frontend_server.main:app --host 0.0.0.0 --port 8000" \
  --always-on true --http20-enabled true

az webapp config appsettings set \
  --name praxys-frontend --resource-group rg-trainsight \
  --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true ENABLE_ORYX_BUILD=true
```

The `frontend_server/` package (`main.py` + `requirements-frontend.txt`) is shipped by `.github/workflows/deploy-frontend-appservice.yml`.

### 8b. Regional frontend delivery

This is a **gated target architecture, not the current production topology**.
The frontend workflow produces two independent builds from the same source
commit:

- the filing-free package continues to run on Azure App Service and can later
  be proxied by Cloudflare Free for `praxys.run` and `www.praxys.run`;
- an independent deterministic `.cn` build is stamped with
  `沪ICP备2025109616号-2`, receives a SHA-256 manifest, and is retained as
  GitHub evidence. EdgeOne's native Git integration runs the same checked-in
  `web/edgeone.json` build from protected `main`. Its deployment marker
  disables browser-side Application Insights and Statsig until a separate
  regional privacy decision accepts those processors.

The current EdgeOne Makers project does not expose a reliable Auto Deploy or
Preview toggle, so release safety does not depend on one. Every accepted
deployment must trace to protected `main`, required CI, an exact source SHA and
manifest, and a recorded EdgeOne deployment-history entry. The EdgeOne GitHub
App receives read-only access only to this repository; GitHub Actions stores no
EdgeOne deployment token. Cloudflare changes DNS and edge delivery only; it
does not replace the Azure App Service deployment. Project bootstrap, Git
access, managed TLS, full-zone DNS migration, CORS, verification, and rollback
are documented in [`docs/ops/tencent-frontend.md`](./ops/tencent-frontend.md).
The API remains singular at `https://api.praxys.run` and stays DNS-only in
Cloudflare.

### 9. Custom domains + managed certs

Three `.run` hostnames bind to the two Azure sites: `api.*` to the backend,
`www.*` and apex to the frontend. App Service verifies ownership through the
current DNS target and/or a TXT `asuid.<host>` record matching the
subscription's `customDomainVerificationId`.

```bash
# 1. Fetch verification ID (per-subscription, same for all sites)
az webapp show --name trainsight-app --resource-group rg-trainsight \
  --query customDomainVerificationId -o tsv

# 2. Fetch the App Service inbound IP (for apex A record)
az webapp config hostname get-external-ip \
  --webapp-name praxys-frontend --resource-group rg-trainsight

# 3. Add the initial DNSPod records:
#      CNAME api    -> trainsight-app.azurewebsites.net
#      CNAME www    -> praxys-frontend.azurewebsites.net
#      A     @      -> <inbound-ip-from-step-2>
#      TXT asuid    -> <verification-id-from-step-1>     (verifies apex)
#      TXT asuid.api  -> <verification-id-from-step-1>   (verifies api)
#      TXT asuid.www  -> <verification-id-from-step-1>   (verifies www)
#    For all of www/apex/api, leave 线路类型 = 默认.

# 4. Add hostname bindings (after DNS propagates)
az webapp config hostname add --webapp-name trainsight-app  --resource-group rg-trainsight --hostname api.praxys.run
az webapp config hostname add --webapp-name praxys-frontend --resource-group rg-trainsight --hostname www.praxys.run
az webapp config hostname add --webapp-name praxys-frontend --resource-group rg-trainsight --hostname praxys.run

# 5. The DNS-only API can keep an App Service-managed certificate.
az webapp config ssl create \
  --resource-group rg-trainsight \
  --name trainsight-app \
  --hostname api.praxys.run

# 6. Bind the API certificate (SNI).
THUMB="$(
  az resource list \
    --resource-group rg-trainsight \
    --resource-type Microsoft.Web/certificates \
    --query "[?contains(name, 'api.praxys.run')] | [0].properties.thumbprint" \
    --output tsv
)"
az webapp config ssl bind \
  --resource-group rg-trainsight \
  --name trainsight-app \
  --certificate-thumbprint "$THUMB" \
  --ssl-type SNI \
  --hostname api.praxys.run

# 7. While the frontend remains direct-DNS, create and bind publicly trusted
#    App Service-managed certificates for both frontend names. This is also the
#    recovery path required before either name is ever gray-clouded.
for host in praxys.run www.praxys.run; do
  FRONTEND_THUMB="$(
    az webapp config ssl create \
      --resource-group rg-trainsight \
      --name praxys-frontend \
      --hostname "${host}" \
      --query thumbprint \
      --output tsv
  )"
  test -n "${FRONTEND_THUMB}"
  az webapp config ssl bind \
    --resource-group rg-trainsight \
    --name praxys-frontend \
    --certificate-thumbprint "${FRONTEND_THUMB}" \
    --ssl-type SNI \
    --hostname "${host}"
done
```

The frontend may use valid App Service-managed certificates for its initial
direct-DNS setup and the first Cloudflare cutover. Do not rely on them after
orange-clouding: Azure documents direct A/CNAME mapping as a prerequisite for
free managed-certificate renewal. After both frontend names are proxied, bind a
Cloudflare Origin CA certificate and keep Cloudflare in `Full (strict)`.
Migration order, PFX upload, certificate rollback, DNSSEC, and the exact
Cloudflare/EdgeOne records are in
[`docs/ops/tencent-frontend.md`](./ops/tencent-frontend.md).

### 10. Configure CORS on the backend

Browsers fetching the API must be on the allowlist. Missing entries surface as `No 'Access-Control-Allow-Origin' header is present on the requested resource` in the browser console with zero server-side signal.

```bash
# Current production origins:
az webapp cors add \
  --name trainsight-app --resource-group rg-trainsight \
  --allowed-origins \
    "https://www.praxys.run" \
    "https://praxys.run" \
    "https://praxys-frontend.azurewebsites.net"

az webapp cors show --name trainsight-app --resource-group rg-trainsight
```

Only after the EdgeOne access, cross-border privacy, and release gates in
[`docs/ops/tencent-frontend.md`](./ops/tencent-frontend.md) are accepted, add
the exact `.cn` browser origins:

```bash
az webapp cors add \
  --name trainsight-app --resource-group rg-trainsight \
  --allowed-origins \
    "https://praxys.cn" \
    "https://www.praxys.cn"
```

The backend detects when it is running on Azure (via `WEBSITE_SITE_NAME`) and skips its own FastAPI `CORSMiddleware`, deferring entirely to this platform-level allowlist.

**When to update this list:**
- Adding a new staging / PR-preview hostname that needs to hit prod API
- Adding or replacing an accepted EdgeOne `.cn` custom hostname

Changes take effect immediately; no app restart required.

For local development, FastAPI's `CORSMiddleware` is added automatically (allowing `localhost:5173`). This can be customized via the `PRAXYS_CORS_ORIGINS` environment variable.

## GitHub Configuration

### Secrets (OIDC Authentication)

The CI/CD workflows use OIDC (OpenID Connect) for passwordless Azure authentication. This requires a federated credential on an Azure AD app registration.

| Secret | Value |
|--------|-------|
| `AZURE_CLIENT_ID` | App registration client ID |
| `AZURE_TENANT_ID` | Azure AD tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |

### Variables (non-secret)

Repository → Settings → Secrets and variables → Actions → Variables tab.
`VITE_*` values are inlined into the SPA and ship to every browser. The EdgeOne
regional build clears browser telemetry keys and uses no build secrets.

| Variable | Value |
|--------|-------|
| `VITE_API_URL` | `https://api.praxys.run` |
| `EDGEONE_CN_PUBLIC_VERIFY_ENABLED` | Default `false`; enable after public `.cn` DNS cutover |

Application Insights routing is not stored in GitHub variables. Both deploy
workflows load the tracked resource names from `.github/azure-observability.env`
and fetch the appropriate connection string through Azure OIDC. See
[`docs/ops/config-and-secrets.md`](ops/config-and-secrets.md#application-insights-trust-boundary-417).

**Setting up OIDC:**

```bash
# Create app registration
az ad app create --display-name trainsight-cicd

# Create federated credential for GitHub Actions
az ad app federated-credential create \
  --id <app-object-id> \
  --parameters '{
    "name": "github-main",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:praxys-run/praxys:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# Grant Contributor role on the resource group
az role assignment create \
  --role Contributor \
  --assignee <app-client-id> \
  --scope /subscriptions/<sub-id>/resourceGroups/rg-trainsight
```

The backend workflow (`.github/workflows/deploy-backend.yml`) requests `id-token: write` permission for OIDC and uses `azure/login@v2` with the three OIDC secrets.

## App Service Environment Variables

Set via Azure Portal > App Service > Configuration > Application settings:

| Variable | Value | Notes |
|----------|-------|-------|
| `DATA_DIR` | `/home/data` | Persistent storage path |
| `PRAXYS_JWT_SECRET` | (random 32+ char string) | JWT signing key |
| `KEY_VAULT_URL` | `https://kv-trainsight.vault.azure.net/` | Key Vault URI |
| `KEY_VAULT_KEY_NAME` | `trainsight-master-key` | RSA key name |

Platform credentials are entered by each user through the Settings page and stored encrypted in the database — no provider login credentials belong in environment variables.

## Auto-Migration

The database schema is managed by `db/session.py:init_db()`. On every startup:
1. `Base.metadata.create_all()` creates any new tables
2. A lightweight migration step inspects existing tables for missing columns and runs `ALTER TABLE ... ADD COLUMN` as needed

This means deploying a new version with additional model columns just works — no manual migration steps required. The migration list is maintained in `init_db()`.

## Post-Deploy Steps

### Road 10K foundation

Do not configure or deploy a Road 10K stage-authority artifact as part of a
normal release.  The repository implementation is unconditionally hard-off
before stage-authority evaluation: no absent, present, or syntactically valid
artifact and no parsed lifecycle value can authorize a Road 10K action.  No
deployment setting can raise the compiled 60-invitation or
30-distinct-exposed-owner ceilings, create an invitation, collect a result,
upload a screenshot, or call a provider/AI.  After any restore,
deletion-marker replay and ledger validation must complete before readiness or
traffic.

1. **Register first user** — `POST /api/auth/register` with email + password (becomes admin)
2. **Connect platforms** — via Settings page (credentials stored encrypted in DB via Key Vault)
3. **Trigger first sync** — via Settings page or `POST /api/sync` (authenticated)

## CI/CD Workflows

- **Pre-merge backend and frontend quality** (`.github/workflows/ci-premerge.yml`) — runs on every `pull_request` to `main`. The independent required contexts are `backend-tests` for the backend suite and `frontend-quality` for the production web build plus Impeccable/evidence UI gate. They share one workflow so downstream review automation receives one completion event. No `paths:` filter on purpose: a required check skipped by a path filter stays permanently pending and blocks the PR.
- **Backend** (`.github/workflows/deploy-backend.yml`) — triggers on changes to `api/`, `analysis/`, `sync/`, `db/`, `data/science/`, `tests/`, `requirements.txt`. Runs tests first, then deploys via OIDC to `trainsight-app`.
- **Frontend** (`.github/workflows/deploy-frontend-appservice.yml`) — triggers
  on changes to `web/` or `frontend_server/`. Runs the static-server tests, then
  builds and stages the filing-free Azure package, then independently runs the
  checked-in `build:edgeone` path for same-SHA China evidence. Azure deploys via
  OIDC to `praxys-frontend`; EdgeOne's repository-scoped, read-only native Git
  integration builds the protected `main` commit with `web/edgeone.json`.
  GitHub stores no EdgeOne deployment credential. Oryx runs
  `pip install -r requirements.txt` (the frontend-only one) on the App Service
  side.

Background sync is handled by the backend scheduler (enabled by default; disable with `PRAXYS_SYNC_SCHEDULER=false`) — no CI job needed.

## CLI Plugin Setup

After deploying, users connect their CLI tools to the deployed backend:

```bash
# Register the local marketplace (one-time)
claude plugin marketplace add ./plugins/marketplace.json

# Install the plugin
claude plugin install praxys

# The MCP server's PRAXYS_URL env var (in .mcp.json) routes
# requests to the deployed API with JWT authentication.
```

Users authenticate via `~/.trainsight/token` (cached JWT from login).
