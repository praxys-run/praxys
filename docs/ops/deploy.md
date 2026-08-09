# Deploy & rollback

> **Summary:** How each surface (backend, frontend, mini program) deploys, how to
> trigger/re-run, and how to roll back.
> **Use when:** Shipping a change to prod, or reverting a bad deploy.

## How deploys trigger

| Surface | Workflow | Triggers | Target |
|---|---|---|---|
| Backend (API) | `deploy-backend.yml` | push to `main` touching backend code/tests, observability config/scripts, or the workflow; or `api-*` tag | App Service `trainsight-app` |
| Frontend (SPA) | `deploy-frontend-appservice.yml` | push to `main` touching the SPA/static server, observability config/scripts, or the workflow; or `web-*` tag | App Service `praxys-frontend`; optionally Tencent Lighthouse |
| Mini program | `miniapp-publish.yml` | `miniapp-YYYY.MM.MICRO` release tag (robot 1); `main` pushes auto-publish a dev build (robot 5) | WeChat (`miniprogram-ci`) |

Targets authenticate through Azure OIDC or the WeChat upload key. The Tencent
lane uses an outbound-only self-hosted Runner restricted to the production
workflow; GitHub Actions does not SSH into Lighthouse. Backend + frontend run
their test/build gates **before** deploying.

**Pre-merge gate.** Before any deploy, `ci-premerge.yml` runs independent backend and frontend validation on every PR to `main`. A red required context blocks merge, so regressions never reach deployment (see [environment.md](./environment.md) → Repo governance). `deploy-backend.yml` re-runs the backend suite post-merge as a deploy-time backstop.

GitHub-hosted Python jobs use `actions/setup-python@v7` to provision the workflow-pinned Python 3.11/3.12 runtimes and require no separate runner configuration.

## Backend deploy

Automatic on merge to `main` (for the paths above). The workflow:
1. Checks out the Praxys plugin submodule and runs `pytest tests/`.
2. Stamps `api/_build_version.txt`.
3. Waits for a compatible live frontend `deployed_sha`.
4. Uses OIDC to enforce the telemetry boundary, sync App Service settings (see
   [config-and-secrets.md](./config-and-secrets.md)).
5. Waits for the App Service SCM deployment endpoint to remain healthy across
   three probes after the configuration recycle, then runs
   `azure/webapps-deploy`.

The settle gate is load-bearing: App Service management writes recycle the SCM
container, and starting ZipDeploy during that recycle aborts the deployment
with `Deployment has been stopped due to SCM container restart`.

Force a deploy without a code change: re-run the latest `deploy-backend.yml` run
(`gh run rerun <id>`), or push an `api-YYYY.MM.MICRO` tag for a versioned release.

## Frontend deploy

Automatic on merge touching `web/`. The workflow builds `web/dist/` once with
`VITE_API_URL` baked in, then fans the same artifact out to:

- Azure `praxys-frontend`, packaged with `frontend_server/`.
- Tencent Lighthouse when `TENCENT_LIGHTHOUSE_DEPLOY_ENABLED=true`, packaged as
  static files and atomically activated under `/var/www/praxys/current` by the
  `praxys-cn-frontend` self-hosted Runner.

Both deployments expose the same `deployed_sha`. The Tencent lane is disabled
until the server bootstrap and workflow-restricted Runner configuration in
[tencent-frontend.md](./tencent-frontend.md) are complete. A skipped Tencent
lane never blocks the existing Azure deployment.

## Mini program

Tag-driven CalVer — see the **"How to release the mini program"** runbook in
[`CLAUDE.md`](../../CLAUDE.md). Promoting 体验版 → 提交审核 → 发布 stays manual in
mp.weixin.qq.com (no first-party API).

## Verify

```bash
curl -s https://api.praxys.run/api/health      # {"status":"ok"}
curl -s https://api.praxys.run/api/version     # {"version":"YYYY.MM.DD..."}
curl -s -o /dev/null -w "%{http_code}\n" https://www.praxys.run/healthz   # 200
```

Watch a run to completion:
```bash
gh run watch "$(gh run list --workflow=deploy-backend.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
```

## Rollback / Recovery

There are **no deployment slots** on the B1 plan, so Azure rollback = re-deploy
a known-good revision:

1. **Revert the commit** on `main` (`git revert <sha> && git push`) — the deploy
   workflow re-runs and ships the reverted state. Safest for app bugs.
2. **Re-tag a prior good commit** (`api-*` / `web-*`) to redeploy that exact build.
3. **Schema note:** migrations are additive / non-destructive — `init_db()` runs
   `alembic upgrade head`, which adds tables/columns and may tweak constraints
   (e.g. adding `ON DELETE SET NULL` to a foreign key, #366) but does not drop
   tables/columns or data. A code rollback won't undo an applied migration, and
   that's safe: old code ignores added columns, and a data-preserving constraint
   change is transparent to it. A genuinely *destructive* schema change would
   need a forward-fix, not a rollback.

   A rollback commit must still retain every Alembic revision already stamped
   in the database. Reverting application code while deleting a newly applied
   migration file makes Alembic fail with `Can't locate revision identified
   by ...` before the old app can start. When reverting a migration-bearing
   change, restore the prior application behavior but keep the migration file
   as an immutable compatibility artifact; do not redeploy an artifact whose
   migration graph predates the current database revision.

> Config-only revert (a bad App Service setting): fix the GitHub secret/variable
> and re-deploy — don't hand-edit the portal (it's overwritten next deploy).

Tencent rollback is independent: atomically repoint
`/var/www/praxys/current` to one of the retained run-addressed releases. See
[tencent-frontend.md](./tencent-frontend.md).

## Related

- [config-and-secrets.md](./config-and-secrets.md) · [monitoring-and-alerts.md](./monitoring-and-alerts.md)
- `docs/deployment.md` (one-time Azure setup) · `.github/workflows/`

---
_Last reviewed: 2026-08-07 · Owner: @dddtc2005_
