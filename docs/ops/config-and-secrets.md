# Configuration & secrets

> **Summary:** Every Praxys config value, **where it is set** (the source of
> truth), what consumes it, and how to rotate it.
> **Use when:** Adding/changing/rotating an env var, secret, or build variable —
> or debugging "I changed a setting in the portal and it reverted".

## The golden rule

The backend's App Service **application settings are owned by the deploy
workflow**, not the portal. `.github/workflows/deploy-backend.yml` → *Sync App
Service settings* runs `az webapp config appsettings set` when deployment
configuration changes, or when a manual dispatch uses `sync_config=true` (the
default), with a fixed list sourced from GitHub Actions secrets/variables (plus
a few literals). Runtime-only merges skip the write because even an idempotent
App Service configuration update recycles the SCM container. The Application
Insights routing string is the deliberate exception to the GitHub-value
source: the workflow resolves it directly from the backend-only Azure
component. **Editing these keys in the Azure Portal is transient — the next
configuration-sync deploy overwrites them.**

## Where each thing lives

### GitHub Actions → Secrets
`Repo → Settings → Secrets and variables → Actions → Secrets`

| Secret | Purpose | Consumed by |
|---|---|---|
| `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` | OIDC login to Azure for deploys (no client secret). The principal is resource-group Contributor; the Labs runbook additionally grants only `Microsoft.Resources/subscriptions/providers/read` through a custom subscription role so provider preflight works without RBAC-write authority. | deploy workflows |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription targeted by deployment workflows | deploy workflows |
| `PRAXYS_JWT_SECRET` | JWT signing key | pushed to App Service setting by `deploy-backend.yml` |
| `STATSIG_SDK_KEY` | Optional for the main app, required for the isolated Labs worker. Statsig server SDK key (`secret-*`); absence fails closed with all gates off. | App Service setting (backend); Container Apps Job secret `statsig-sdk-key` via `deploy-labs-worker.yml` |
| `STRYD_CLIENT_WHEEL_B64` | Base64-encoded, hash-pinned private `stryd-client` v0.2.0 wheel. Trusted CI installs it for transport tests; backend deployment materializes the wheel for Oryx. Fork CI receives no secret and exercises the package-absent path instead. | `ci-premerge.yml`, `deploy-backend.yml` |
| `PRAXYS_DATABASE_URL` | Postgres DSN (#360). May carry the DB password unless Entra auth is used. **Optional** until cutover; empty = SQLite. | App Service setting (backend) |
| `PRAXYS_LABS_DATABASE_URL` | Passwordless Postgres DSN whose username is `id-praxys-labs-worker`. Stored separately so the Container Apps Job uses its own least-privilege Entra principal, never the backend admin identity. | `deploy-labs-worker.yml` -> Container Apps secret `database-url` |
| `WECHAT_MINIAPP_APPID` / `WECHAT_MINIAPP_SECRET` | WeChat Mini Program auth | App Service setting (backend) |
| `PRAXYS_SMTP_PASSWORD` | SMTP client authorization code (WeCom/Exmail) for verification + invitation emails. **Optional.** | App Service setting (backend) |
| `WECHAT_MINIAPP_UPLOAD_KEY` | Mini program CI upload key | `miniapp-publish.yml` |
| `COPILOT_GITHUB_TOKEN` | Fine-grained PAT owned by the Copilot subscriber, with only *Account permissions → Copilot Requests: Read*. Used solely for Agentic Workflow inference; repository operations continue to use `GITHUB_TOKEN`. Do not grant `copilot-requests: write` in those workflows or gh-aw ignores this secret in favor of organization billing. | Agentic Workflow `.md` sources |
| `COPILOT_ASSIGN_TOKEN` | **Required for workflow auto-assign and live Cloud drift checks** — fine-grained PAT (*Issues: write* and *Copilot agent settings: read*, this repo only, with expiry). Agent assignment needs a user token; the built-in `GITHUB_TOKEN` is forbidden (issue #400). Manual UI assignment doesn't need it. | `assign-copilot.yml`, `copilot-environment-parity.yml` |
| `PRAXYS_GITHUB_APP_PRIVATE_KEY` | Feedback GitHub App private key. The app has Issues read/write and Pull requests read; tokens are minted on demand. | App Service setting (backend) |
| `PRAXYS_REVIEW_POLICY_APP_PRIVATE_KEY` | Independent review-governance App key. The App has Contents write + Pull requests write to approve qualifying PRs, enable normal auto-merge, and commit verified science approval-ledger updates without using `GITHUB_TOKEN`. Optional for ordinary review-required PRs without science acceptance; required for autonomous review actions and science approval materialization. | `selective-review.yml`, `science-approval-ledger.yml` |

### GitHub Actions → Variables
`… → Variables` (non-secret; only `VITE_*` build variables are inlined into
the SPA and ship to browsers)

| Variable | Purpose | Consumed by |
|---|---|---|
| `VITE_API_URL` (`https://api.praxys.run`) | API base baked into the SPA | `deploy-frontend-appservice.yml` build |
| `VITE_STATSIG_CLIENT_KEY` | Optional public Statsig client key (`client-*`) baked into the SPA. It is not a server credential; never put `STATSIG_SDK_KEY` here. | `deploy-frontend-appservice.yml` build |
| `STATSIG_ENV` (`production`) | Shared Statsig environment tier. The deploy workflows default production when the variable is absent. | App Service setting + frontend build |
| `AZURE_AI_ENDPOINT` | Azure OpenAI endpoint for production insights, feedback triage, and i18n. Keep the trailing `/`. Agentic Workflows use GitHub Copilot-hosted inference instead. | App Service setting + `i18n.yml` |
| `TRANSLATE_MODEL` (`gpt-5.4-mini`) | Optional deployment override for translating newly extracted UI strings and science copy. | `i18n.yml`; script default applies when unset |
| `TRANSLATE_REVIEW_MODEL` (`gpt-5.4`) | Optional stronger deployment override for the weekly native-Chinese catalog review. | `i18n.yml`; script default applies when unset |
| `KEY_VAULT_URL` / `KEY_VAULT_KEY_NAME` | Key Vault + RSA key name | App Service setting |
| `PRAXYS_FEEDBACK_BLOB_ACCOUNT_URL` (`https://stperftrainsight.blob.core.windows.net`) | Private Blob store for feedback screenshots and 14-day Labs/personal-context deletion markers (keyless via MI) | App Service setting (backend) |
| `PRAXYS_FEEDBACK_BLOB_CONTAINER` (`feedback-screenshots`) | Private container for screenshots and restore-safe privacy deletion markers | App Service setting (backend) |
| `PRAXYS_SMTP_HOST` / `PRAXYS_SMTP_PORT` / `PRAXYS_SMTP_USER` / `PRAXYS_SMTP_FROM` / `PRAXYS_SMTP_STARTTLS` | SMTP transport for verification + invitation emails (non-secret; the password is the secret above). **Optional.** | App Service setting (backend) |
| `PRAXYS_APP_BASE_URL` (`https://praxys.run`) | Public origin for verify/invite links in those emails | App Service setting (backend) |
| `PRAXYS_DB_AUTH` (`entra` or unset) | Postgres auth mode: `entra` = AAD token via managed identity, no password. **Optional.** | App Service setting (backend) |
| `PRAXYS_LABS_EXECUTION_MODE` (`inline` by default) | Labs execution route: `inline`, `service_bus`, or maintenance-only `disabled`. Set `service_bus` only after the worker runbook verifies Azure and DB prerequisites; no runtime fallback occurs. | App Service setting via `deploy-backend.yml` |
| `PRAXYS_LABS_SERVICE_BUS_CLIENT_ID` (unset by default) | Optional client ID of a user-assigned identity attached to `trainsight-app` for Labs queue sends. Empty uses the App Service system identity. The worker workflow verifies RBAC for the same effective identity. | App Service setting via `deploy-backend.yml`; RBAC verification in `deploy-labs-worker.yml` |
| `PRAXYS_LABS_WORKER_DEPLOY_ENABLED` (`false`) | Opt-in infrastructure reconciliation gate. Only exact `true` runs the Azure deployment job; image tests/builds still run. | `deploy-labs-worker.yml` |
| `PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED` (`false`) | Default-off hard deployment prerequisite for unsupported Garmin consumer-API workout writes. Set `true` only on an approved validation deployment, or in production after both regional lifecycle matrices pass. Statsig eligibility, durable execution-target selection, and the account-generation/region fence remain independently required. | App Service setting (backend) |
| `PRAXYS_PG_SERVER` | Postgres Flexible Server name. **Reserved / currently unused** - the on-demand backup jobs it gated were removed (Burstable tier can't do on-demand backups; PITR covers backup). Kept for a future off-site backup job. | (reserved) |
| `PRAXYS_GITHUB_APP_ID` / `PRAXYS_GITHUB_APP_INSTALLATION_ID` | Feedback GitHub App identifiers. | App Service setting (backend) |
| `PRAXYS_FEEDBACK_GITHUB_REPO` / `PRAXYS_FEEDBACK_GITHUB_LABELS` / `PRAXYS_FEEDBACK_GITHUB_ASSIGNEES` | Feedback issue target and optional issue metadata. | App Service setting (backend) |
| `PRAXYS_AGENT_READY_SHADOW` / `PRAXYS_AGENT_READY_CHALLENGER_PROMPT_VERSION` | Withhold active labels, or run a versioned semantic challenger without acting. Both are optional and default off. | App Service setting (backend) |
| `PRAXYS_REVIEW_POLICY_APP_ID` | App ID for the independent review-governance GitHub App. Optional on ordinary review-required runs, but required to materialize verified science approvals. | `selective-review.yml`, `science-approval-ledger.yml` |
| `PRAXYS_REVIEW_POLICY_APP_SLUG` | Expected URL slug for the independent App, without `[bot]`; lets pre-credential evaluation recognize only that App's prior blocking reviews and verifies every minted privileged identity. | `selective-review.yml`, `selective-review-emergency-stop.yml`, `science-approval-ledger.yml` |
| `PRAXYS_SELECTIVE_REVIEW_ENABLED` | Master enable; absent/anything except `true` keeps every PR review-required. | `selective-review.yml` |
| `PRAXYS_SELECTIVE_REVIEW_KILL_SWITCH` | Emergency stop; `true` disables approval even when the master enable and class promotion are active. | `selective-review.yml` |
| `EDGEONE_CN_PUBLIC_VERIFY_ENABLED` | Default-off public-host probe. Exact `true` only after both `.cn` custom domains resolve to the accepted EdgeOne project. | `deploy-frontend-appservice.yml` |

### Tencent public website filing

The approved service filing for `praxys.cn` and `www.praxys.cn` is
`沪ICP备2025109616号-2`, linked to `https://beian.miit.gov.cn/`. Its code source
of truth is `web/scripts/stamp-china-compliance.mjs`; the frontend workflow
applies it only to the independently built EdgeOne evidence artifact, while the
EdgeOne Git integration runs the same checked-in regional build. This is public
regulatory metadata, not a secret or mutable Actions variable. Update it only
after an approved filing change, together with
`docs/ops/tencent-frontend.md` and deployment verification.

Under the gated regional target, the `.cn` hosts will be served by the
Git-integrated EdgeOne Makers project `praxys-cn` in the global area, with
platform-managed HTTPS. EdgeOne receives read-only access only to this
repository and uses no build secrets. The filing-free `.run` build will remain
on Azure behind Cloudflare Free, while `api.praxys.run` stays DNS-only. Azure
App Service CORS must then include exactly `https://praxys.cn` and
`https://www.praxys.cn` only for an accepted authenticated `.cn` release.
Repository access, the protected-main deployment boundary, the Cloudflare
origin-certificate sequence, DNS migration, and rollback commands live in
`docs/ops/tencent-frontend.md`.

The China stamping step also adds a deployment-region marker. Browser-side
Application Insights and Statsig read that marker and remain disabled for the
EdgeOne artifact. Enabling either processor for `.cn` is a separate privacy and
runtime-config change, not an Actions variable toggle.

Changing `PRAXYS_FEEDBACK_GITHUB_REPO` does not reinterpret historical issue
numbers. Feedback sync and adjudication compare each stored GitHub URL with the
current repo and fail closed on a mismatch, exposing the skipped count in Admin
Feedback. Plan a deliberate link migration before switching repositories; do
not assume issue `#N` refers to the same work in the new target.

### Copilot repository MCP servers

Cloud-agent MCP configuration is a repository setting, not an Actions variable
and not the committed `.mcp.json` used by local Copilot CLI clients. Its source
of truth is **Repository → Settings → Copilot → MCP servers**; the reviewed
copy/paste payload is `config/copilot-cloud-mcp.json`.

Portable Praxys agents use the same reviewed capabilities in Local and Cloud.
The Cloud repository setting adds:

- pinned, headless, isolated Chrome DevTools with an explicit UI-review
  tool allowlist, usage statistics and CrUX disabled, and network headers
  redacted;
- the synthetic `praxys-local` server with read-only product-context tools.

It requires no secret or `COPILOT_MCP_*` variable. Never add `praxys-dev-test`,
production tokens, provider credentials, sync tools, or plan-mutation tools to
the cloud allowlist. `.github/workflows/copilot-setup-steps.yml` must remain the
owner of the submodule checkout, MCP Python dependency, Chrome verification,
and synthetic sandbox preparation. The cloud config's literal
`praxys-local-mcp` command uses the interpreter prepared by
`actions/setup-python`; local profiles continue to require the project
virtualenv unless `PRAXYS_MCP_PYTHON` is explicitly set.

The setup workflow also owns the cloud agent's Node 24 LTS dependency
bootstrap. Application web and mini-program build workflows use the same Node
major so CI validation and production artifacts share a supported baseline. It
uses `npm install` because the current Lingui package metadata is not strict
`npm ci` compatible, then restores and verifies `web/package-lock.json` before
the agent starts. This requires no secret or repository variable; change the
workflow and this runbook together if the install strategy changes.

The cloud agent's **Start MCP Servers** step does not guarantee the repository
root as its working directory or propagate `GITHUB_WORKSPACE` to the MCP
process. The setup workflow therefore symlinks
`/usr/local/bin/praxys-local-mcp` to
`scripts/run_praxys_mcp_cloud.sh` in the checked-out workspace. The launcher
resolves that symlink to derive the repository root, changes there, and exports
`PRAXYS_MCP_USE_CURRENT_PYTHON=1` before starting the repository module. The
plugin pins `mcp==1.28.1`, and setup verifies the exact
`mcp.server.fastmcp.FastMCP` import used by its server. Keep the cloud payload
pointed at the installed command; relying on inherited MCP environment
variables, or using
`python -m scripts.run_praxys_mcp` directly can silently leave every
`praxys-local` tool unregistered.

Provision after the setup workflow is present on `main`:

1. Copy `config/copilot-cloud-mcp.json` into the repository MCP configuration
   field and save it.
2. Confirm the public-preview read endpoint returns the same two servers:

   ```bash
   gh api -H "X-GitHub-Api-Version: 2026-03-10" \
     repos/praxys-run/praxys/copilot/cloud-agent/configuration \
     --jq '.mcp_configuration.mcpServers | keys'
   ```

3. Assign a disposable test issue to Copilot and ask it to call
   `chrome-devtools/list_pages` and `praxys-local/whoami`. Open **View
   session**, expand **Start MCP Servers**, and confirm both servers list their
   allowlisted tools and both calls succeed.

Rollback by removing the affected server from repository MCP settings and
saving. Built-in Playwright remains available when Chrome DevTools is removed.
Portable Praxys agents must nevertheless record rendered verification as
blocked rather than silently switching to an environment-specific path.

The common capability contract is `config/copilot-execution-parity.json`.
Validate repository state with:

```bash
python scripts/check_copilot_environment_parity.py
```

The live Cloud setting is external GitHub state. The scheduled and
manually-dispatchable `.github/workflows/copilot-environment-parity.yml` calls
the versioned `2026-03-10` configuration endpoint and compares it with the
checked-in payload:

```bash
python scripts/check_copilot_environment_parity.py \
  --live \
  --repo praxys-run/praxys
```

The live check uses `COPILOT_ASSIGN_TOKEN`, which must include repository
*Copilot agent settings: read*. A missing token, denied permission, missing
required server, tool drift, or undeclared environment override fails the
workflow. Restore the reviewed repository MCP payload to roll back accidental
drift. If the contract itself changes, update the config, agents, setup
workflow, parity tests, and this runbook in the same PR.

### GitHub Actions → Workflow permissions

The i18n workflow uses its built-in `GITHUB_TOKEN` to update
`i18n/refresh-zh` and open the review PR. GitHub suppresses normal
`pull_request` workflow events for PRs opened by that token, so `i18n.yml`
explicitly uses the permitted `workflow_dispatch` exception: it dispatches
Pre-merge CI and Miniapp build on the bot branch, then waits for Pre-merge CI. Do
not remove that chain; otherwise automated translation PRs lose their required
validation. Their semantic review already happened inside `i18n.yml` through
the independent editor/critic pair; the invariant workflow remains the
additional guard for ordinary human/Copilot PRs that change copy.

The same workflow runs a deterministic Chinese catalog gate on every relevant
PR. After extraction it immediately reviews up to 200 newly introduced or
resurrected strings, including translations recovered from obsolete catalog
history; overflow still enters the weekly rotation. On Monday at 02:17 UTC it
also reviews one stable eighth of the active catalog (capped at 200 entries)
with `TRANSLATE_REVIEW_MODEL`, then applies a revision only when a separate
critic pass agrees at high confidence. At the current catalog size every string
therefore receives a page-context-aware native-language pass within eight weeks
without accepting subjective synonym churn. The shard uses an epoch-based week
number so year boundaries cannot skip it; if a future shard exceeds the cap,
its window rotates on the next cycle instead of starving the tail. The
scheduled run updates the same `i18n/refresh-zh` branch and still requires human
review. A manual dispatch with
`full_review=true` reviews the entire catalog and has materially higher model
cost because both editor and critic run; use it for a terminology or voice
reset, not routine maintenance.

`TRANSLATE_MAX` is atomic: if missing copy exceeds the configured limit, the
job stops before any billable model call. If an individual output still fails
the deterministic gate (for example, a malformed placeholder), the workflow
opens the translation PR so successful work is not lost, then marks the run
failed; the PR's required checks remain red until a human repairs the entry.

Mini-program-only copy remains in `miniapp/utils/i18n-extra.ts`. Its existing
`npm run check-i18n` gate reads the same glossary and rejects missing/renamed
placeholders, English-style Chinese typography, banned translationese, and
canonical-term drift. Shared web/mini keys must match unless
`MINI_TRANSLATION_OVERRIDES` records a reviewed mobile-specific rationale. The
Praxys invariant Agentic Workflow then reviews
user-facing copy changes for semantic/native-language quality after `Pre-merge CI`.

Provision and verify:

1. Keep repository **Default workflow permissions** at `read`, but enable
   **Allow GitHub Actions to create and approve pull requests** for
   `praxys-run/praxys`. The workflow grants only its translation job the
   explicit `actions: write`, `contents: write`, and `pull-requests: write`
   permissions it needs.
2. Verify the repository gate:

   ```bash
   gh api repos/praxys-run/praxys/actions/permissions/workflow
   ```

   `can_approve_pull_request_reviews` must be `true`. If the organization blocks
   repository opt-in, an organization owner must enable the corresponding gate
   first.
3. Dispatch `i18n.yml`. Confirm the generated PR receives manual-dispatch runs
   for Pre-merge CI and Miniapp build on `i18n/refresh-zh`.

#### Dependabot patch auto-merge

`.github/workflows/dependabot-auto-merge.yml` uses the built-in
`GITHUB_TOKEN` to queue normal squash auto-merge for a deliberately narrow
dependency-update class. **No repository secret or variable is required.**
The job runs from trusted default-branch code through `pull_request_target`,
never checks out pull-request code, and grants `actions: read` plus only the
`contents: write` and `pull-requests: write` permissions GitHub requires to
inspect workflow state and enable auto-merge.

Eligibility is fail-closed:

- the pull request must still be open, non-draft, same-repository, target
  `main`, and be authored by `dependabot[bot]`;
- `dependabot/fetch-metadata` is commit-pinned and must verify the pull request
  plus its metadata commit; the workflow separately paginates and verifies
  every commit author and signature;
- the highest update must be `semver-patch` and must not belong to a dependency
  group;
- only root `pip` updates and `/web` `npm` updates qualify; miniapp, GitHub
  Actions, grouped, minor, and major updates remain manual;
- changed files must be modifications limited to `requirements.txt` or the
  `/web` package manifest and lockfile appropriate to the verified ecosystem;
- the workflow re-reads the pull request immediately before acting and binds
  `gh pr merge` to the exact verified head SHA.

Auto-merge still obeys the strict `main` ruleset. The current head must be up to
date and pass both `backend-tests` and `selective-review-policy`; a failed,
conflicted, or stale update remains open. Existing Dependabot pull requests are
not retroactively queued until Dependabot updates/reopens them or the workflow
is otherwise retriggered.

Verify a qualifying PR:

```bash
gh pr view <number> --json author,autoMergeRequest,baseRefName,headRefOid,statusCheckRollup
```

Emergency rollback first prevents new queueing, then disables any pending
Dependabot auto-merges:

```bash
repo=praxys-run/praxys
workflow=dependabot-auto-merge.yml
workflow_id=$(gh api "repos/$repo/actions/workflows/$workflow" --jq '.id')
test -n "$workflow_id"
gh workflow disable "$workflow_id" --repo "$repo"

disable_pending_dependabot_auto_merges() {
  for pr in $(gh pr list --repo "$repo" --author app/dependabot --state open \
    --limit 1000 --json number,autoMergeRequest \
    --jq '.[] | select(.autoMergeRequest != null) | .number'); do
    gh pr merge --disable-auto "$pr" --repo "$repo"
  done
}

disable_pending_dependabot_auto_merges

for run in $(gh run list --repo "$repo" --workflow "$workflow_id" \
  --all --limit 1000 --json databaseId,status \
  --jq '.[] | select(.status != "completed") | .databaseId'); do
  gh run cancel "$run" --repo "$repo"
done

while [ -n "$(gh run list --repo "$repo" --workflow "$workflow_id" \
  --all --limit 1000 --json status \
  --jq '.[] | select(.status != "completed") | .status')" ]; do
  sleep 2
done

disable_pending_dependabot_auto_merges

test "$(gh pr list --repo "$repo" --author app/dependabot --state open \
  --limit 1000 --json autoMergeRequest \
  --jq '[.[] | select(.autoMergeRequest != null)] | length')" = "0"
```

Application Insights resource names are tracked in
`.github/azure-observability.env`, not repository variables. The deploy
workflows use Azure OIDC to read each component's connection string at runtime;
the frontend workflow receives only the frontend/RUM value. The backend helper
also derives `PRAXYS_BACKEND_APPINSIGHTS_RESOURCE_ID` from the trusted component
and writes it directly to App Service; it is not a GitHub variable.

When one `main` push triggers both deployment surfaces, `deploy-backend.yml`
waits for every active frontend production run to settle, then verifies the
`deployed_sha` returned by the live `praxys-frontend` `/healthz` endpoint before
backend cutover. The frontend package contains
`frontend_server/_deployed_sha.txt`, generated from `GITHUB_SHA` during staging,
so the value comes from the code actually serving production rather than
workflow-list ordering. Rerunning a pre-marker historical workflow exposes no
SHA and therefore cannot masquerade as a compatible deployment.
Accepting a newer descendant handles GitHub's replacement of pending concurrency
runs when a frontend-only push follows closely. The required commit is the
latest frontend-triggering change in the backend SHA's first-parent history, so
a later backend-only push still waits for an earlier combined change. The new
frontend remains compatible with the Phase 1 API, so this frontend-first
ordering prevents an older bundle from hiding newly available alert and
platform aggregates during rollout.
Each workflow also serializes every production deployment, including `main`
pushes and release tags, without cancelling the active run. A newer run remains
queued and deploys last, so an older package cannot overwrite it.

Backend App Service setting, site-config, and telemetry-cutover writes recycle
the SCM container. `deploy-backend.yml` therefore waits at least 90 seconds and
requires three consecutive successful reads from the App Service deployment
endpoint before invoking ZipDeploy. Do not remove or shorten this settle gate:
deploying during the recycle is rejected with
`Deployment has been stopped due to SCM container restart`. Each probe has a
20-second command timeout and the full gate is capped at eight minutes so a
stalled SCM endpoint cannot monopolize the serialized production lane.

### Azure App Service → Application settings (backend `trainsight-app`)
Source of truth = `deploy-backend.yml`. Literals set inline: `DATA_DIR=/home/data`,
`WEBSITES_PORT=8000`, `SCM_DO_BUILD_DURING_DEPLOYMENT=true`,
`WEBSITE_HTTPLOGGING_RETENTION_DAYS=3`. `APPLICATIONINSIGHTS_CONNECTION_STRING`
and `PRAXYS_BACKEND_APPINSIGHTS_RESOURCE_ID` come from
`appi-praxys-backend` through `scripts/appinsights_boundary.sh`; everything else
comes from the secrets/variables above.

### Statsig feature gates

Statsig is optional runtime configuration, not an availability dependency.
`STATSIG_SDK_KEY` is a repository Actions **secret** and is copied only to the
backend App Service. `VITE_STATSIG_CLIENT_KEY` is a repository Actions
**variable** because a Statsig `client-*` key is intentionally shipped in the
browser bundle. Never reuse or copy the `secret-*` server key into a Vite
variable. `STATSIG_ENV` is the shared non-secret environment tier.

The final Statsig Console state owned by this integration is exactly:

| Resource type | Name | Default / schema | Rules |
|---|---|---|---|
| Feature gate | `garmin_plan_delivery_eligible` | `false` in every environment | Optional reviewed allow rule matching only dedicated users by internal Praxys UUID. Never add a global pass rule. |
| Feature gate | `stryd_connection_enabled` | `false` in every environment | One exact-email allow rule for the maintainer account only. The backend removes Stryd from settings, sync, plan delivery, Labs, schedulers, and direct actions for every other account. Never add a percentage or global pass rule. |
| Dynamic config | `insight_daily_cap` | `{"value": 30}` where `value` is an integer | No experiment assignment. Runtime rules may return another validated positive integer. |
| Dynamic config | `labs_environment_recompute_policy` | `{"value":{"cooldown_hours":6,"window_hours":24,"max_requests":3}}`; all fields are integers | No experiment assignment. A reviewed per-user UUID rule may set `cooldown_hours` to `0` for targeted testing. Keep `window_hours` between 1 and 168, `cooldown_hours` between 0 and `window_hours`, and `max_requests` between 1 and 100. |

Repository-level Console automation uses the official `statsig` HTTP server in
`.mcp.json`. The entry intentionally contains an empty `headers` object and no
credential. Each operator or agent authenticates through the MCP OAuth flow;
the Statsig organization owner must first enable personal Console API keys.
Never commit an OAuth token or Console API key to `.mcp.json`, environment
examples, workflow variables, or documentation.

Automation must treat the table above as declarative state and reconcile it
idempotently: reads and repeated runs produce the same gate/config definition,
and every mutation remains reviewable. Before destructively deleting a
superseded Statsig resource, verify repository code and tests no longer
reference its name and update this inventory in the same change.

The Garmin gate is evaluated only after
`PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED=true` and never replaces provider
capability checks, durable execution-target selection, or the
account-generation/region fence. Remove superseded issue-251 resources from
the Statsig project; do not create an experiment for this integration.

The Stryd gate has no client-side authority. Backend responses omit the private
provider and Stryd-only Labs capability for ineligible users, and direct action
paths return 404. Web and miniapp navigation mirror those filtered responses.
The account must also be active, non-demo, connected, and running a deployment
that contains the private wheel. Missing Statsig configuration or evaluation
errors fail closed.

When Statsig is unavailable or the dynamic-config property is absent, the
backend keeps `PRAXYS_INSIGHT_DAILY_CAP` and then `30` as the insight fallback.
The Labs recompute policy keeps its code-owned 6-hour cooldown, 24-hour rolling
window, and three-request limit. Invalid Labs values fail back to that complete
default policy rather than partially applying a malformed rule. A zero-hour
targeted cooldown bypasses only the time delay: active-job single-flight and
the configured rolling request limit remain authoritative.
`AZURE_AI_ENDPOINT` remains the hard infrastructure prerequisite for model
calls. There is no AI feature gate.

Provision repository values, then redeploy both surfaces:

```bash
# Prompts securely; do not place the server key in shell history.
gh secret set STATSIG_SDK_KEY --repo praxys-run/praxys

gh variable set STATSIG_ENV --body production --repo praxys-run/praxys
# A public client-* key from the same Statsig project:
gh variable set VITE_STATSIG_CLIENT_KEY --repo praxys-run/praxys
```

Verify the backend App Service contains `STATSIG_SDK_KEY` and `STATSIG_ENV`
without printing their values, and inspect the built SPA only for the expected
public `client-*` key. Removing `STATSIG_SDK_KEY` and redeploying is a
fail-closed rollback for Garmin and Stryd eligibility; both dynamic configs
resume their documented fallbacks. To roll back only Stryd access, disable
`stryd_connection_enabled` or remove its single maintainer rule. To roll back
only a Labs recompute exception, remove its targeted rule and confirm the API
again reports `cooldown_hours: 6`,
`window_hours: 24`, and `remaining_requests` against a three-request window.

### Private Stryd wheel provisioning

The public Praxys repository must not hold a token that can clone the private
client repository. GitHub deploy keys are disabled for that repository, so the
current pinned wheel is stored directly as an encrypted Actions secret. The
workflows materialize it under ignored `.private-deps/`, verify SHA-256
`d5ecc8c14beafe1cf2df6e5021b0bee71094b15cf14dfc039f0652c8c9c030e4`,
and never deploy client source.

Provision or rotate the secret from a trusted local checkout after verifying
the intended wheel:

```bash
wheel=/path/to/stryd_client-0.2.0-py3-none-any.whl
test "$(sha256sum "$wheel" | cut -d' ' -f1)" = \
  d5ecc8c14beafe1cf2df6e5021b0bee71094b15cf14dfc039f0652c8c9c030e4
base64 -w 0 "$wheel" \
  | gh secret set STRYD_CLIENT_WHEEL_B64 --repo praxys-run/praxys
```

When upgrading the private package, change the filename and expected digest in
both workflows in the same PR, update this runbook, then replace the secret
before merge. A missing or mismatched secret fails backend deployment; normal
CI without the secret validates that Praxys still imports and serves all
non-Stryd features. Removing the secret is an emergency package-distribution
rollback, but disable the Statsig gate first so the maintainer UI also fails
closed.

### Azure Key Vault (`kv-trainsight`)
- RSA key `trainsight-master-key` — the master key that wraps the per-user
  Fernet data-encryption keys (DEKs) protecting platform credentials
  (`db/crypto.py`). The App Service MI has *Key Vault Crypto User*. **Not** a
  plain env var.

### Local development → `.env`
Local only; never committed. See [`.env.example`](../../.env.example) for the full
annotated list. Minimum: `PRAXYS_LOCAL_ENCRYPTION_KEY` (Fernet); `PRAXYS_ENV=development`
to boot without a JWT secret.

Platform credentials used by sync and plan delivery are encrypted per user in
`user_connections`; the server does not read global platform usernames or
passwords for API writes. Do not add personal platform credentials to
`deploy-backend.yml`, GitHub Actions, App Service settings, or shared local
environment files.

Garmin consumer-API workout delivery is an unsupported, duration-only
rollout protected by independent deployment, eligibility, account-generation,
and durable execution-target fences. The
deploy workflow writes the non-secret GitHub Actions variable
`PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED` to App Service on every deployment,
defaulting to `false` when the variable is absent. Keep production false until
both controlled regional lifecycle matrices pass.

Controlled validation requires an approved deployment with the hard
prerequisite set to `true`, plus a Statsig
`garmin_plan_delivery_eligible` rule targeting only dedicated Praxys test
users connected to dedicated Garmin test accounts. Do not target personal
accounts or copy emails, tokens, or credentials into the rule. Eligible users
must still connect Garmin and explicitly choose it as their execution platform;
all other users remain blocked. Statsig eligibility is not consent or durable
product state. Changing the App Service setting directly is transient and will
be overwritten by the next deploy. The legacy
`user_connections.plan_delivery_consent` column holds a non-secret SHA-256
account-generation fence, not a separate user preference. Selecting or resuming
Garmin refreshes the binding to that encrypted credential generation and Garmin
region. It is never accepted as a portable entitlement. Reconnecting, rotating
credentials, or disconnecting clears the fence and pauses active Garmin
delivery. Changing region also disconnects the old region, clears its cached
tokens, and requires a fresh login. Cached sessions are garminconnect
`Client.dumps()` JSON values envelope-encrypted
on `user_connections` with a token-specific wrapped DEK and the exact
credential-generation fingerprint. Interactive login
holds completed tokens only in process memory, bound to an opaque
server-generated login-attempt ID, until the encrypted connection transaction
commits. Concurrent attempts cannot consume one another's tokens.
On first startup after the migration, valid legacy per-user token files are
encrypted before deletion; orphaned, partial, malformed, and abandoned stores
are deleted. Failure to remove a plaintext store aborts startup rather than
leaving the scheduler active. Migration also refuses to delete a valid token
file when Key Vault is unavailable and no persistent local encryption key is
configured. Startup first moves the source to `.garmin_tokens.migration`, then
installs a non-secret blocker at the entire old `.garmin_tokens` root before
decrypting or encrypting anything. A failed migration preserves the quarantine
for the next startup; a root recreated during an interrupted cutover is merged
back into quarantine before retry. Pre-upgrade workers and a rolled-back release therefore
cannot recreate plaintext tokens for existing or newly registered users; they
fail Garmin authentication until the encrypted-token release is restored.
A cross-worker migration lock elects one startup worker, which acquires all
known per-user token leases before the cutover. The blocker is written and
fsynced under a temporary name, then atomically installed.
A running Garmin sync is generation fenced and
rolls back if the connection changes, so old OAuth sessions cannot
authorize or degrade the replacement connection. Do not provision, copy, or
restore consent or token files through App Service settings, Actions
variables, SQL scripts, storage tooling, or an admin override. To roll back
per-user access, disable the Statsig gate or remove its targeting rule. To roll
back Garmin writes globally, set
`PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED=false` and redeploy. The capability and
every fresh mutation guard fail closed without deleting user consent or
unrelated Garmin data.

#### Garmin eligibility provisioning

Prerequisites: the dedicated test user has logged into
`praxys-dev-test`, `whoami` shows the expected internal UUID, and its Garmin
connection belongs to a dedicated validation account.

```bash
repo=praxys-run/praxys
gh variable set PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED \
  --repo "$repo" --body true
```

In the Statsig console, keep `garmin_plan_delivery_eligible` default-off and add
a reviewed targeting rule for only the dedicated user's internal UUID. This
repository does not automate Console API changes. If automation is added, its
credential must be an Actions secret and the change must be idempotent and
reviewable.

Redeploy the current `main` head so the workflow writes the hard prerequisite
to App Service. Verify only that non-secret setting:

```bash
az webapp config appsettings list \
  --name trainsight-app \
  --resource-group rg-trainsight \
  --query "[?name=='PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED'].value" \
  --output tsv
```

Then verify `praxys-dev-test.get_settings` reports Garmin as a selectable
execution target only for the eligible user. The configured execution target
must remain unchanged until that user explicitly selects Garmin, and the
account-generation/region fence must remain absent until selection or resume.
Garmin must remain unselectable for a control user.

Rollback disables the Statsig gate first. To close the hard deployment
prerequisite too, update the repository variable and redeploy:

```bash
gh variable set PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED \
  --repo "$repo" --body false
```

Confirm both eligible and control users report Garmin delivery unavailable
before considering rollback complete.

### Application Insights trust boundary (#417)

Both components store data in `log-trainsight`, but they have separate ingestion
identities and resource IDs:

| Component | Purpose | Ingestion auth | Exposed to browser |
|---|---|---|---|
| `appi-trainsight` | SPA page views, dependencies, exceptions, Web Vitals; homepage availability test | Local/instrumentation-key auth enabled | **Yes** — expected |
| `appi-praxys-backend` | API requests/traces/logs, `praxys.*` product and Coach signals, backend alerts, API availability test | Entra-only (`DisableLocalAuth=true`) through `trainsight-app` MI | **No** |

The existing `appi-trainsight` instrumentation key was already shipped in
browser bundles, so it is permanently treated as untrusted RUM ingestion. The
new backend component was created with a fresh key and immediately locked to
Entra authentication. Sharing a Log Analytics workspace does not collapse the
boundary: alerts and queries remain scoped to the component resource ID (or
filter `_ResourceId` at workspace scope).

The workspace must keep
`features.enableLogAccessUsingOnlyResourcePermissions=true`. That setting lets
the backend query its linked component with exact-resource `Monitoring Reader`
instead of granting workspace-wide read access; `backend-preflight` rejects
drift.

The runtime identity is the App Service system-assigned identity unless the
`trainsight-app` setting `AZURE_CLIENT_ID` names an attached user-assigned
identity. `backend-preflight` resolves that effective identity and checks both
roles against it; changing `AZURE_CLIENT_ID` without attaching and granting the
matching identity blocks deployment.

#### One-time provisioning

```bash
RG=rg-trainsight
WORKSPACE_ID=$(az monitor log-analytics workspace show \
  -g "$RG" -n log-trainsight --query id -o tsv)
az resource update --ids "$WORKSPACE_ID" \
  --set properties.features.enableLogAccessUsingOnlyResourcePermissions=true

# Existing frontend component: keep local auth enabled for the browser SDK.
FRONTEND_ID=$(az resource show -g "$RG" -n appi-trainsight \
  --resource-type Microsoft.Insights/components --query id -o tsv)
az resource update --ids "$FRONTEND_ID" \
  --set properties.DisableLocalAuth=false \
        tags.trustBoundary=frontend \
        tags.managedBy=deploy-frontend-appservice

# Backend-only component. Safe to re-run if it already exists by skipping create.
az monitor app-insights component create \
  -g "$RG" -a appi-praxys-backend -l eastasia \
  --workspace "$WORKSPACE_ID" --kind web --application-type web
BACKEND_ID=$(az resource show -g "$RG" -n appi-praxys-backend \
  --resource-type Microsoft.Insights/components --query id -o tsv)
az resource update --ids "$BACKEND_ID" \
  --set properties.DisableLocalAuth=true \
        tags.trustBoundary=backend \
        tags.managedBy=deploy-backend

# The deploy identity is RG Contributor and cannot grant RBAC; an operator with
# role-assignment permission performs this once.
MI=$(az webapp identity show -g "$RG" -n trainsight-app \
  --query principalId -o tsv)
az role assignment create \
  --assignee-object-id "$MI" \
  --assignee-principal-type ServicePrincipal \
  --role "Monitoring Metrics Publisher" \
  --scope "$BACKEND_ID"
az role assignment create \
  --assignee-object-id "$MI" \
  --assignee-principal-type ServicePrincipal \
  --role "Monitoring Reader" \
  --scope "$BACKEND_ID"
```

For a user-assigned identity, first mirror every runtime grant held by the
system-assigned identity (including Key Vault and PostgreSQL access), attach it
to `trainsight-app`, set its client ID as the `AZURE_CLIENT_ID` App Service
setting, and use that identity's `principalId` as `MI` for both monitoring role
assignments above.

Record only the five non-secret identifiers in
`.github/azure-observability.env`. Do **not**
create `APPLICATIONINSIGHTS_CONNECTION_STRING` or
`VITE_APPINSIGHTS_CONNECTION_STRING` GitHub variables. On every deployment:

1. `backend-preflight` confirms distinct resources, shared workspace linkage,
   backend local-auth disabled, exact-resource `Monitoring Metrics Publisher`
   and `Monitoring Reader` RBAC for the effective runtime managed identity, and
   a 401/403 response when an anonymous forged `praxys.product_event` is sent
   with the backend instrumentation key. It also idempotently upserts the
   source-controlled `praxys-managed-plan-provider-failures` and
   `praxys-managed-plan-defects` scheduled-query rules at the currently active
   telemetry scope and verifies that each routes only to the existing
   `praxys-feedback-ag` action group. Provisioning fails closed if the action
   group or its `support@praxys.run` email receiver is disabled. This requires
   no new secret or repository variable; the deploy identity's resource-group
   Contributor grant owns the rules and the action-group lookup.
2. The backend cutover updates the App Service routing plus all backend alert
   scopes as one rollback-guarded operation. Azure makes scheduled-query scopes
   immutable, so the helper preserves each full rule definition and recreates
   it under the same name with the new component scope. Deletion ignores only a
   confirmed 404; creation retries and then compares the complete normalized
   rule (criteria, actions, severity, cadence, identity, and tags). The same
   transaction writes `PRAXYS_BACKEND_APPINSIGHTS_RESOURCE_ID`, enabling the
   admin operations console only while the trusted backend boundary is active.
   Standalone rollback tolerates either deployment-owned managed-plan rule being
   absent after a partial preflight and migrates only the alert resources that
   actually exist.
3. `frontend-resolve` refuses to build unless only the frontend component allows
   local auth, then injects that frontend connection string into Vite.

#### Verify production

```bash
set -a
source .github/azure-observability.env
set +a
export GITHUB_ENV=$(mktemp)
bash scripts/appinsights_boundary.sh backend-preflight

BACKEND_ID=$(az resource show -g "$AZURE_RESOURCE_GROUP" \
  -n "$BACKEND_APPINSIGHTS_NAME" \
  --resource-type Microsoft.Insights/components --query id -o tsv)
az resource show --ids "$BACKEND_ID" \
  --query "{workspace:properties.WorkspaceResourceId,localAuthDisabled:properties.DisableLocalAuth}" \
  -o table
az webapp config appsettings list -g "$AZURE_RESOURCE_GROUP" \
  -n trainsight-app \
  --query "[?name=='APPLICATIONINSIGHTS_CONNECTION_STRING' || name=='PRAXYS_BACKEND_APPINSIGHTS_RESOURCE_ID'].{name:name,value:value}" \
  -o table
MI=$(az webapp identity show -g "$AZURE_RESOURCE_GROUP" -n trainsight-app \
  --query principalId -o tsv)
az role assignment list --assignee-object-id "$MI" --scope "$BACKEND_ID" \
  --query "[?roleDefinitionName=='Monitoring Metrics Publisher' || roleDefinitionName=='Monitoring Reader'].{role:roleDefinitionName,scope:scope}" \
  -o table
```

The preflight's forged-event probe is the trust test: HTTP 401/403 proves that a
browser possessing an instrumentation key cannot place
`praxys.product_event` or `praxys.coach_feedback` into the backend component.
The authenticated product API can still accept its documented enum payload,
but the server owns the telemetry timestamp, pseudonym, provenance, and final
dimensions.

#### Rollback

`backend-cutover` captures the prior App Service value, scheduled-query scopes,
web-test link, and metric-alert component. Any failed mutation restores all of
them automatically. To reverse a successful cutover, pause/revert the backend
deploy workflow first (otherwise the next deploy re-applies the boundary), then
run the rollback mode:

```bash
set -a
source .github/azure-observability.env
set +a
bash scripts/appinsights_boundary.sh rollback-to-frontend
```

The reverse cutover atomically restores backend routing, all five scheduled
queries, the API web-test hidden link, and its metric-alert component to
`appi-trainsight`. It also removes
`PRAXYS_BACKEND_APPINSIGHTS_RESOURCE_ID`, so the in-app admin Azure sections
become explicitly unavailable rather than reading the untrusted browser
component. It restores the previous shared-resource behavior and therefore
removes the trust boundary; use it only as temporary telemetry recovery while
fixing the backend component or RBAC.

## Adding a NEW backend setting (checklist)

1. Read it in code via `os.environ` / `getenv_compat` (treat unset as a safe default).
2. Add it to `.env.example` (annotated) for local dev.
3. Add it to `deploy-backend.yml`: the `env:` block (from `secrets.*` or `vars.*`)
   **and** the `az webapp config appsettings set` arg list. Azure-derived routing
   values such as Application Insights belong in a deployment helper instead.
4. If it must be present, add it to the *required-settings* loop; if optional,
   **leave it out** of that loop so an unset value can't fail the deploy.
5. Create the GitHub secret (sensitive) or variable (non-sensitive).

> Example: the feedback → GitHub-issue settings (`PRAXYS_GITHUB_APP_*`,
> `PRAXYS_FEEDBACK_GITHUB_*`) follow exactly this pattern and are intentionally
> optional. (Added by the feedback feature — praxys-run/praxys#328.)

### Feedback screenshot storage (Azure Blob, keyless)

Screenshots attached to feedback (issue #337) are stored **privately** in Blob
(reusing the `stperftrainsight` account). Auth is keyless via the backend's
system-assigned managed identity — no key or connection string. One-time infra:

```bash
# 1. Dedicated container (kept separate from the perf data in this account)
az storage container create --account-name stperftrainsight \
  --name feedback-screenshots --auth-mode login

# 2. Grant the app MI data access on JUST that container (least privilege)
MI=$(az webapp identity show -n trainsight-app -g rg-trainsight --query principalId -o tsv)
SUB=$(az account show --query id -o tsv)
az role assignment create --assignee-object-id "$MI" --assignee-principal-type ServicePrincipal \
  --role "Storage Blob Data Contributor" \
  --scope "/subscriptions/$SUB/resourceGroups/rg-trainsight/providers/Microsoft.Storage/storageAccounts/stperftrainsight/blobServices/default/containers/feedback-screenshots"

# 3. Register the two non-secret GitHub Actions variables (the source of truth).
#    deploy-backend.yml syncs them to the App Service settings on the next deploy.
gh variable set PRAXYS_FEEDBACK_BLOB_ACCOUNT_URL --body "https://stperftrainsight.blob.core.windows.net"
gh variable set PRAXYS_FEEDBACK_BLOB_CONTAINER   --body "feedback-screenshots"
```

The two `PRAXYS_FEEDBACK_BLOB_*` variables above point the app at it. The same
private container stores `labs-deletions/` withdrawal markers and
`personal-context-deletions/` payload-free deletion manifests for 14 days so a
PITR restore cannot resurrect Labs consent/results or deleted adaptive-plan
context. Unset the variables and the app falls back to local filesystem
storage under `DATA_DIR` (persistent on `/home`, but not the recommended
long-term home).
`api/feedback_storage.py` selects the shared private backend and authenticates
with `DefaultAzureCredential`.

### The change loop — coding-agent labels & assignment (issue #362)

`agent-ready` (auto-added to qualifying, actionable bugs by `api/feedback_triage.py`, or added
by hand) triggers `.github/workflows/assign-copilot.yml`, which assigns the issue
to the Copilot coding agent with the checked-in `praxys-change-loop` custom
agent profile. These are **repo settings, not deploy-managed**:

- **Labels** `agent-ready` and `backlog` (optionally `later`) are created once
  with `gh label create` — see [change-loop.md](./change-loop.md).
- **Required secret for auto-assign** `COPILOT_ASSIGN_TOKEN` (fine-grained PAT,
  *Issues: write*, this repo only, with expiry). Agent assignment needs a user
  token — the built-in `GITHUB_TOKEN` is forbidden (issue #400); without it the
  workflow fails loudly and a human assigns manually. See
  [change-loop.md](./change-loop.md) §3.
- **Optional flag** `PRAXYS_AGENT_READY_SHADOW=true` (App Service setting)
  computes the agent-ready decision but withholds the label — measure precision
  before going live (issue #377).
- **Optional challenger**
  `PRAXYS_AGENT_READY_CHALLENGER_PROMPT_VERSION=v2` runs the checked-in v2
  prompt on the same scrubbed report and records its candidate decision without
  changing labels. Priority is deliberately absent from the readiness gate.
  Configure both controls through repository variables so
  `deploy-backend.yml` remains the App Service source of truth:

  ```bash
  gh variable set PRAXYS_AGENT_READY_SHADOW --body "false"
  gh variable set PRAXYS_AGENT_READY_CHALLENGER_PROMPT_VERSION --body "v2"
  ```

  Set the challenger variable to an empty value and redeploy to stop the extra
  model call. Unknown prompt versions fail closed and do not affect active
  triage.
- **Agent environment:** `.github/workflows/copilot-setup-steps.yml` preinstalls
  the toolchain so the agent can run `pytest` / `npm` deterministically.
- **PR readiness enforcement:** `.github/workflows/copilot-pr-readiness.yml`
  uses the repository `GITHUB_TOKEN` only; it requires no additional secret.
  It returns Copilot PRs to draft after new commits, missing final-preflight
  evidence for the current head SHA, or failed required checks.
- **Versioned policy metadata:** `config/agent-loop-policies.json` is committed
  code config. It names the active assignment policy, narrow candidate classes,
  protected paths, evidence thresholds, and promoted classes. Promotion is
  blocked by `scripts/validate_review_policy.py` unless the checked-in evidence
  meets the full bar. `docs/science/**` and `docs/dev/contributing.md` are
  protected paths explicitly excluded from documentation-only promotion, while
  `web/src/locales/**` is protected because the shared catalogs contain
  scientific copy. These paths stay outside policy-owned auto-merge and are
  routed through CODEOWNERS. This is a documented human-review requirement,
  not currently a ruleset-enforced approval gate; the solo-maintainer ruleset
  still requires zero approvals.
- **Selective-review runtime controls** are repository Actions variables:
  `PRAXYS_SELECTIVE_REVIEW_ENABLED` defaults to `false`;
  `PRAXYS_SELECTIVE_REVIEW_KILL_SWITCH=true` stops approval immediately. The
  independent App identity is
  `PRAXYS_REVIEW_POLICY_APP_ID` +
  `PRAXYS_REVIEW_POLICY_APP_SLUG` +
  `PRAXYS_REVIEW_POLICY_APP_PRIVATE_KEY`; workflows derive the exact bot login
  from the minted token and verify it against the configured slug. These App
  values may remain absent while the committed policy is unpromoted/default-off
  only when no science approval must be materialized; the science approval
  ledger fails closed without them. Provisioning:
  [setup-review-policy-app.md](./setup-review-policy-app.md).
- The repository setting **Allow auto-merge** is shared by
  `selective-review.yml` and `dependabot-auto-merge.yml`. Auto-merge remains
  squash-only and obeys the active ruleset; neither the policy App nor the
  workflow token is a bypass actor. The rules require zero approvals but require
  the branch to be up to date before merging. Both `backend-tests` and the
  explicit `selective-review-policy` status are required on the current head.

### Azure Database for PostgreSQL (#360)

The backend is dual-backend: `PRAXYS_DATABASE_URL` empty/unset = SQLite on
`/home/data`; set it to a Postgres DSN and the app uses Postgres. Keep it empty
until the cutover so this can ship ahead of the migration. Full runbook:
[postgres-migration.md](./postgres-migration.md).

- `PRAXYS_DATABASE_URL` (**secret**) - the Postgres DSN. With Entra/MI auth it
  carries no password.
- `PRAXYS_DB_AUTH` (**variable**) - `entra` makes the app authenticate with an
  AAD token from its managed identity (no DB password anywhere).
- `PRAXYS_PG_SERVER` (**variable**) - the Flexible Server name. Reserved /
  currently unused (the on-demand backup jobs it gated were removed - Burstable
  can't do on-demand backups; PITR covers backup). Kept for future off-site
  backup automation.

```bash
gh variable set PRAXYS_PG_SERVER --body "praxys-pg"
gh variable set PRAXYS_DB_AUTH   --body "entra"
gh secret   set PRAXYS_DATABASE_URL --body "postgresql://trainsight-app@praxys-pg.postgres.database.azure.com:5432/praxys?sslmode=require"
```

**Status (2026-07-04):** all three are **set** and production runs on Postgres.
`PRAXYS_DATABASE_URL` = `postgresql://trainsight-app@praxys-pg.postgres.database.azure.com:5432/praxys?sslmode=require`
(no password — Entra/MI). They remain out of the required-settings loop, so
clearing `PRAXYS_DATABASE_URL` cleanly rolls back to the frozen SQLite file.
Provisioning + PITR + MI-as-AAD-principal wiring: [postgres-migration.md](./postgres-migration.md).

### Isolated Labs analysis compute (#619)

The source of truth is split intentionally so infrastructure can be staged
without routing production work to it:

| Value | Source of truth | Notes |
|---|---|---|
| `PRAXYS_LABS_DATABASE_URL` | GitHub Actions secret | Passwordless DSN using username `id-praxys-labs-worker`; injected only into the Container Apps Job secret. |
| `STATSIG_SDK_KEY` | Existing GitHub Actions secret | Injected into the Container Apps Job as secret `statsig-sdk-key`. The worker refuses to receive a message until Statsig initializes so a targeting outage cannot cancel eligible queued work. |
| `STATSIG_ENV` | Existing GitHub Actions variable | Injected as the worker's Statsig tier; defaults to `production` in `deploy-labs-worker.yml`. |
| `PRAXYS_LABS_WORKER_DEPLOY_ENABLED` | GitHub Actions variable | Default off. Exact `true` lets `deploy-labs-worker.yml` reconcile Bicep resources, but only after the one-time GHCR package visibility check in the worker runbook. |
| `PRAXYS_LABS_EXECUTION_MODE` | GitHub Actions variable | Defaults to `inline`; switch to `service_bus` only after worker verification. |
| `PRAXYS_LABS_SERVICE_BUS_FQDN` | Derived by `deploy-backend.yml` | The workflow discovers the namespace tagged `praxysComponent=labs-analysis`; do not hand-set it in the portal. |
| `PRAXYS_LABS_SERVICE_BUS_QUEUE` | Literal owned by `deploy-backend.yml` | `labs-environment-response`. |
| `PRAXYS_LABS_SERVICE_BUS_CLIENT_ID` | Optional GitHub Actions variable | Empty selects the backend system identity. When set, it must name a user-assigned identity attached to `trainsight-app`; both runtime and the worker deployment RBAC check resolve it. |
| `PRAXYS_HIDE_SQL_PARAMETERS` | Literal owned by `infra/labs-worker.bicep` and enforced again by `api/labs_worker.py` | `true` in the isolated worker so SQLAlchemy exceptions cannot export bind values to Application Insights. |
| `AZURE_CLIENT_ID` (worker) | Bicep-derived Container Apps env | Client ID of `id-praxys-labs-worker`, used for PostgreSQL, Service Bus, and App Insights Entra auth. |

Provisioning order and least-privilege PostgreSQL grants are in
[labs-analysis-worker.md](./labs-analysis-worker.md). The checked-in
`scripts/provision_labs_worker_principal.sql` verifies the Entra object-ID
mapping as an Entra administrator. The table-owning backend identity then runs
`scripts/provision_labs_worker_db.py`, which excludes `training_plans`, grants
only the non-GPS sample columns consumed by the research pack, restricts
enrollment/job updates to worker-owned processing fields, and permits only
`user_id`, `platform`, `status`, and `preferences` reads on
`user_connections`. Gate targeting receives column-limited reads of `users.id`,
`email`, `is_active`, `is_superuser`, and `is_demo`; password hashes and other
account columns remain denied. It does not grant access to encrypted
credentials or token bundles.

```bash
gh secret set PRAXYS_LABS_DATABASE_URL \
  --body "postgresql://id-praxys-labs-worker@praxys-pg.postgres.database.azure.com:5432/praxys?sslmode=require"
gh variable set PRAXYS_LABS_WORKER_DEPLOY_ENABLED --body "false"
# Publish once, make the GHCR package public per the runbook, then:
gh variable set PRAXYS_LABS_WORKER_DEPLOY_ENABLED --body "true"
# Only after the runbook's Azure, DB-principal, idle-job, and alert checks:
gh variable set PRAXYS_LABS_EXECUTION_MODE --body "service_bus"
```

Rollback through `disabled`: deploy it first, drain Service Bus and any running
Container Apps execution, then deploy `inline` before disabling worker
reconciliation. `disabled` preserves durable jobs without dispatch and is
reserved for maintenance or this drain step.

### Database connection budget, pool sizing & Always On

The production DB is a **Burstable B1ms** Flexible Server: `max_connections=50`
(Azure default for the tier), of which ~15 are reserved
(`superuser_reserved_connections=10` + `reserved_connections=5`, both Azure
defaults) — leaving **~35 usable by the app**. Don't lower the reserved values;
they're Azure-managed.

The backend's SQLAlchemy pools are bounded (`db/session.py`) and tunable via
optional App Service settings (defaults shown):

| Setting | Default | Meaning |
|---|---|---|
| `PRAXYS_DB_POOL_SIZE` | `5` | Steady pool size, **per engine, per worker** |
| `PRAXYS_DB_MAX_OVERFLOW` | `5` | Burst connections above `pool_size` |
| `PRAXYS_DB_POOL_RECYCLE` | `1800` | Recycle (reconnect) a connection after N seconds |

There are **two** engines (sync + async), so one gunicorn worker holds at most
`2 × (pool_size + max_overflow)` = **20** connections — under the 35-slot
budget. If you raise the worker count or pool sizes, keep
`workers × 2 × (pool_size + max_overflow)` **< 35**, or move off Burstable.
These envs are optional (not in the required-settings loop).

**Always On = `true`** — App Service **site config** (NOT an app setting), so a
separate command, owned by `deploy-backend.yml`:
`az webapp config set --name trainsight-app --resource-group rg-trainsight --always-on true`.
It keeps one warm container instead of stop/starting on idle; each recycle
abandons the container's pool as idle "zombie" backends that linger until
TCP-keepalive reap (~6 min), and that churn helped exhaust Postgres in the
2026-07-05 outage. The app also disposes its engines on shutdown
(`dispose_engines`, `api/main.py` lifespan) so a *clean* recycle frees
connections immediately.

Guarded by two alerts (see
[monitoring-and-alerts.md](./monitoring-and-alerts.md)):
`praxys-pg-connections-high` (Sev 2, `active_connections` > 40) and
`praxys-db-health-unhealthy` (Sev 1, DB unreachable/corrupt).

### Self-registration gate + email

Opening self-registration is **runtime config, not a setting**: an admin toggles
it and sets the seat cap on the Admin page (persisted in the `app_config` DB table
via `api/app_config.py`). Nothing to deploy for that — see
[admin-tasks.md](./admin-tasks.md).

The *email* prerequisites ARE optional settings (tables above): the `PRAXYS_SMTP_*`
group + `PRAXYS_APP_BASE_URL`. They power (a) double-opt-in email verification for
code-less sign-ups and (b) emailing invitation codes to waitlist signups. Unset →
the app still works: codes are shown for the admin to copy/mailto by hand, and open
sign-ups are created verified (no ownership check possible). To provision (WeCom /
Tencent Exmail):

```bash
# 1. In the Exmail mailbox: 设置 → 账号 → enable POP3/IMAP/SMTP, then generate a
#    客户端授权码 (client authorization code) — that is PRAXYS_SMTP_PASSWORD.
# 2. Register the non-secret variables + the secret (source of truth):
gh variable set PRAXYS_SMTP_HOST     --body "smtp.exmail.qq.com"
gh variable set PRAXYS_SMTP_PORT     --body "465"
gh variable set PRAXYS_SMTP_USER     --body "no-reply@praxys.run"
gh variable set PRAXYS_SMTP_FROM     --body "Praxys <no-reply@praxys.run>"
gh variable set PRAXYS_APP_BASE_URL  --body "https://praxys.run"
gh secret   set PRAXYS_SMTP_PASSWORD --body "<客户端授权码>"
# 3. Re-deploy the backend — deploy-backend.yml syncs them to App Service.
```

Azure App Service blocks outbound port **25** but allows **465/587** to an
authenticated relay like Exmail. The `EmailSender` interface (`api/email_sender.py`)
is provider-agnostic, so Azure Communication Services (HTTPS) can be swapped in
later without touching call sites if SMTP is ever blocked or Exmail's daily cap is
outgrown.

## Rotation

| Value | How | Impact |
|---|---|---|
| `PRAXYS_JWT_SECRET` | New `secrets.PRAXYS_JWT_SECRET`, re-deploy backend | **All active sessions invalidated** — every user must log in again. |
| `WECHAT_MINIAPP_SECRET` | Rotate in mp.weixin.qq.com, update GitHub secret, re-deploy | Mini program auth briefly fails until deploy lands. |
| `WECHAT_MINIAPP_UPLOAD_KEY` | Regenerate in mp.weixin.qq.com, update GitHub secret | Only affects mini program CI publishing. |
| Frontend/backend Application Insights routing | Provision the replacement component, update `.github/azure-observability.env`, grant backend MI RBAC if needed, and re-deploy | The workflows fetch fresh routing strings directly from Azure; no GitHub value rotates. |
| Feedback GitHub App key (`PRAXYS_GITHUB_APP_PRIVATE_KEY`) | Generate a new private key on the app, update the secret, re-deploy (rarely needed). Setup: [setup-github-app.md](./setup-github-app.md). | Issue auto-filing dormant until updated; rest of app unaffected. |
| SMTP auth code (`PRAXYS_SMTP_PASSWORD`) | Regenerate the 客户端授权码 in the Exmail/WeCom mailbox settings, update the GitHub secret, re-deploy. | Verification + invitation emails fail to send until updated (codes can still be copied by hand). |
| Key Vault RSA key `trainsight-master-key` | ⚠️ **High-impact** — the per-user DEKs were wrapped with the current key; rotating without a re-wrap/re-encrypt migration makes stored platform credentials undecryptable. Treat as non-rotatable until the migration tool and operator-approved drill in [secret-rotation.md](./secret-rotation.md) exist. | Users would have to reconnect platforms. |

## Related

- [deploy.md](./deploy.md) · [environment.md](./environment.md) · `docs/deployment.md`
- `.github/workflows/deploy-backend.yml` and `scripts/appinsights_boundary.sh`
  (source of truth for App Service settings and telemetry routing)

---
_Last reviewed: 2026-08-04 · Owner: @dddtc2005_
