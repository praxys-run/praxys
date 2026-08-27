# Deploy & rollback

> **Summary:** How each surface (backend, frontend, mini program) deploys, how to
> trigger/re-run, and how to roll back.
> **Use when:** Shipping a change to prod, or reverting a bad deploy.

## How deploys trigger

| Surface | Workflow | Triggers | Target |
|---|---|---|---|
| Backend (API) | `deploy-backend.yml` | push to protected `main` touching backend runtime code, observability config/scripts, dependencies, or the workflow; manual dispatch is eligible only from `main` | App Service `trainsight-app` |
| Labs analysis worker | `deploy-labs-worker.yml` | push to `main` touching worker/backend analysis code, its Dockerfile/requirements, Bicep, tests, or the workflow; `api-*` tag; manual dispatch from the selected ref | Service Bus + Container Apps Job; Azure deploy is gated by `PRAXYS_LABS_WORKER_DEPLOY_ENABLED=true` |
| Frontend (SPA) | `deploy-frontend-appservice.yml`; EdgeOne native Git integration | push to protected `main` touching the SPA/static server, observability config/scripts, or the workflow; manual dispatch is eligible only from `main` | App Service `praxys-frontend`; gated EdgeOne Git build for `.cn` |
| Mini program | `miniapp-publish.yml` | `miniapp-YYYY.MM.MICRO` release tag (robot 1); `main` pushes auto-publish a synthetic dev build (robot 5) | WeChat (`miniprogram-ci`) |

Targets authenticate through Azure OIDC or the WeChat upload key. EdgeOne uses
a least-privilege read-only GitHub App repository grant and no GitHub Actions
deployment token. There is no production self-hosted frontend Runner and
GitHub Actions does not SSH into a Tencent host.

Backend, frontend, and Miniapp release lanes freeze one exact lowercase
40-character SHA and enforce protected-`main` provenance. The Labs worker is a
separate exception: its workflow also accepts `api-*` tags and unrestricted
manual refs, runs its own targeted tests/build, and reconciles Azure only when
its deployment gate is true. Only China-capable backend, EdgeOne, and Miniapp
release lanes additionally require `CN_PRIVACY_FLOOR_SHA` plus exact current
notice/digest/API-contract and release-registry validation; filing-free `.run`
lanes do not require China-only values. Those ancestry checks are provenance and
rollback-floor guards only; they never prove privacy compatibility, release
authorization, or runtime compatibility. Current named-check API snapshots are
supporting records with the evidence limitations below, not proof of historical
pre-merge semantics.

**Pre-merge gate.** For the protected-`main` backend, frontend, and Miniapp
release lanes, `ci-premerge.yml` runs independent backend and frontend
validation on every PR to `main`. The Labs tag/manual-ref exception instead
runs the targeted worker tests in `deploy-labs-worker.yml`. A red required context blocks the protected-`main` merge (see
[environment.md](./environment.md) -> Repo governance). This is the intended
pre-merge safeguard, subject to the current evidence limitations below; it is
not proof that administrative bypass or historical timing is impossible. Normal backend deploys
rely on that required check instead of repeating the same five-minute suite
after merge. Manual protected-`main` dispatches can opt in with `run_tests=true`;
Backend/frontend App Service deployment tags are not eligible for those
protected-`main` OIDC federations; the Labs exception is described above.

GitHub-hosted Python jobs use `actions/setup-python@v7` to provision the workflow-pinned Python 3.11/3.12 runtimes and require no separate runner configuration.

The preflight captures a current API snapshot of rules, pull-request mapping,
and successful named records. Existing APIs and policy do **not** establish
pre-merge timing, absence of admin bypass, or producer identity for those
records, and historical semantics remain unresolved. **Permanent aggregated Release Evidence storage** and retained provider upload/deployment-success
evidence are still blockers; deterministic locators alone are not provider
success evidence, and 90-day artifacts are supporting inputs only. The release remains blocked and not released.


## Backend deploy

Automatic on merge to `main` (for the paths above). The workflow:
1. Stamps `api/_build_version.txt`.
2. Uses the live frontend `deployed_sha` only as protected-main deployment-order
   provenance and, in isolated Labs
   mode, the exact same commit of the Labs worker.
3. Uses Azure OIDC and runs `azure/webapps-deploy`.
4. When deployment configuration changed, first reconciles the telemetry
   boundary, App Service settings, and alerts (see
   [config-and-secrets.md](./config-and-secrets.md)), then waits for the SCM
   endpoint to settle after the resulting configuration recycle.
5. Verifies that `/api/version` reports the stamped build and database
   readiness is green. If OneDeploy has not activated the new process after
   the initial activation probes, the workflow performs one App Service
   restart and verifies again before reporting success.

The configuration path runs automatically when the workflow, observability
resource map, or telemetry boundary script changes. Manual dispatch defaults
`sync_config=true`, which is required after changing a GitHub Actions secret or
variable. Ordinary runtime-only merges skip those idempotent management writes
and their two-minute recycle wait.

When configuration is reconciled, the settle gate remains load-bearing: App
Service management writes recycle the SCM container, and starting ZipDeploy
during that recycle aborts the deployment with
`Deployment has been stopped due to SCM container restart`.

Test-only changes do not deploy the backend. Pull requests already run the
backend suite in the required pre-merge workflow; recycling production when no
runtime artifact changed adds outage risk without changing the service.

Force a deploy without a code change:

```bash
# Fast code redeploy; preserves the current App Service configuration.
gh workflow run deploy-backend.yml --ref main -f sync_config=false

# Reconcile GitHub-owned settings/telemetry before deploying (the default).
gh workflow run deploy-backend.yml --ref main -f sync_config=true
```

`api-*` and `web-*` tags are not backend/frontend App Service deploy triggers.
The Labs worker is the explicit exception: `api-*` tags can reach its gated
Container Apps reconciliation. Backend/frontend App Service OIDC federation is
limited to protected `main`; those lanes use no client secret, publish profile,
wildcard ref, or tag federation.

Configuration reconciliation may stage the China exact-release registry only
for a manual `china_release_validation=true` dispatch. Every ordinary deploy
writes fixed fail-closed literals for the China kill switch and both optional-
processing switch pairs, removes `.cn` CORS, and exactly reads them back.
Repository variables cannot enable those controls. `/api/health/ready` exposes
non-secret effective and switch state for deterministic comparison; no live
readback is claimed here.

## Labs analysis worker deploy

`deploy-labs-worker.yml` always runs the targeted backend tests, builds the
1-vCPU/2-GiB worker image, publishes its commit-SHA tag to GHCR, verifies that
the package is anonymously pullable, and validates the Bicep template. It
reconciles Azure only when
`PRAXYS_LABS_WORKER_DEPLOY_ENABLED=true`.

Infrastructure deployment does not itself cut over the API. The separate
`PRAXYS_LABS_EXECUTION_MODE=service_bus` backend variable is enabled only after
the user-assigned identity has its least-privilege PostgreSQL principal and the
idle worker/alerts have been verified. Follow
[labs-analysis-worker.md](./labs-analysis-worker.md); do not reverse those two
steps. Once isolated mode is active, backend deployment waits for the worker
job to run the exact same commit-SHA image before updating App Service. The
worker workflow mirrors every backend trigger, including `data/science/**`, so
an older worker cannot consume jobs created by a newer model deployment.

## Frontend deploy

Automatic on merge touching `web/`. GitHub first builds the filing-free Azure
artifact, then independently runs the checked-in deterministic EdgeOne build
for evidence:

- Azure `praxys-frontend`, packaged with `frontend_server/`. This copy never
  receives the China filing footer and is the Cloudflare origin for `.run`.
- The independent `.cn` artifact is stamped, telemetry-disabled, bound to the
  source SHA, and given a SHA-256 manifest. Its preflight is explicitly an
  unpublished preparation check: it proves the disabled privacy floor but cannot
  claim a provider release ID or registry authorization. GitHub retains the
  artifact and the separate preflight JSON for 90 days; the frontend build
  evidence binds both the manifest and preflight hashes to the source SHA. The
  artifact is not uploaded by GitHub.

  EdgeOne native Git separately checks out `main` and runs the checked-in
  `web/edgeone.json` boundary. That build always omits GitHub API credentials
  and relies only on local protected-main ancestry plus exact disabled-runtime
  readback. This can prepare provider bytes
  but cannot authorize them. Provider deployment evidence and an exact registry
  entry are recorded only afterward, before any public promotion or activation.
  An ancestry check, source stamp, manifest, or deployment-history entry is
  provenance only and cannot authorize or establish compatibility. The native provider path is therefore blocked, not released. After public cutover,
`EDGEONE_CN_PUBLIC_VERIFY_ENABLED` makes GitHub compare both hosts' source SHA
and served manifest with its independent build evidence. Cloudflare requires no
application deployment; it proxies the Azure response and honors its cache
headers.

## Mini program

Tag-driven CalVer — see the **"How to release the mini program"** runbook in
[`CLAUDE.md`](../../CLAUDE.md). Robot 1 receives the exact
`miniapp-YYYY.MM.MICRO` tag version; robot 5 receives a synthetic
`YYYY.MM.DD.<run>-<sha>` development version so it cannot overwrite or
impersonate the release candidate. Promoting 体验版 → 提交审核 → 发布 stays manual
in mp.weixin.qq.com (no first-party API). `MINIMUM_MINIAPP_VERSION` is the
separate oldest supported privacy floor, currently `2026.08.1`; choosing a
newer release tag does not raise it. The first notice-capable production floor
is `miniapp-2026.08.1`. Its upload and every later release candidate must descend
from the repository variable `CN_PRIVACY_FLOOR_SHA` and remain reachable from
protected `main`; preserve the workflow SHA and exact
`wechat:robot-1:<version>` provider locator in the China Release Evidence.
Robot 5 development uploads require protected-main provenance but are never
registry authorization. Before a robot 1 upload, the release preflight also
locates the successful `china_release_validation=true` backend workflow for the
same full source SHA, verifies the retained final-evidence artifact against its
GitHub SHA-256 digest, and requires exact registry digest/count plus successful
disabled runtime, readiness, source-SHA, and App Service registry readbacks.
Missing, expired, stale, or digest-mismatched backend evidence fails the upload
gate closed.

The workflow initializes redacted upload evidence before it writes the temporary
upload key or contacts WeChat. An `always()` finalizer records success, failure,
or non-completion and retains that evidence artifact even when upload fails.
This records an upload attempt only; promotion, review submission, and
publication remain manual and unauthorized by the workflow. The required
staged sequence and its pending human gate are defined in the
[proposed China Operations Decision Record](./odr-2026-08-26-cn-provider-topology.md).

## Verify

```bash
curl -s https://api.praxys.run/api/health      # {"status":"ok"}
curl -s https://api.praxys.run/api/version     # {"version":"YYYY.MM.DD..."}
curl -s https://api.praxys.run/api/health/ready \
  | jq '{status, china_processing, optional_processing}'
curl -s -o /dev/null -w "%{http_code}\n" https://www.praxys.run/healthz   # 200
```

Watch a run to completion:
```bash
gh run watch "$(gh run list --workflow=deploy-backend.yml --limit 1 --json databaseId --jq '.[0].databaseId')" --exit-status
```

## Rollback / Recovery

There are **no deployment slots** on the B1 plan, so Azure rollback = re-deploy
a known-good revision:

1. Freeze the exact 40-character candidate SHA and confirm its protected-`main`
   and required-check evidence. For a China-capable rollback, also require an
   exact current registry entry binding that full SHA to retained provider
   evidence. Ancestry, CalVer, and an abbreviated SHA are not authorization.
2. **Revert the commit** on `main` (`git revert <sha> && git push`) — the deploy
   workflow re-runs and ships the reverted state. Safest for app bugs, provided
   the resulting revision remains at or above the privacy floor.
3. **Schema note:** migrations are additive / non-destructive — `init_db()` runs
   `alembic upgrade head`, which adds tables/columns and may tweak constraints
   (e.g. adding `ON DELETE SET NULL` to a foreign key, #366) but does not drop
   tables/columns or data. A code rollback won't undo an applied migration, and
   that's safe: old code ignores added columns, and a data-preserving constraint
   change is transparent to it. A genuinely *destructive* schema change would
   need a forward-fix, not a rollback.

For a China-specific privacy incident, rerun the ordinary backend workflow,
which writes the fixed `PRAXYS_DISABLE_CN_PROCESSING=true` literal and removes
`.cn` CORS. This preserves export, deletion, provider
disconnect, and owned feedback-image access. Do not delete the approved-release
registry or cross the privacy floor as a rollback shortcut.

   A rollback commit must still retain every Alembic revision already stamped
   in the database. Reverting application code while deleting a newly applied
   migration file makes Alembic fail with `Can't locate revision identified
   by ...` before the old app can start. When reverting a migration-bearing
   change, restore the prior application behavior but keep the migration file
   as an immutable compatibility artifact; do not redeploy an artifact whose
   migration graph predates the current database revision.

> Config-only revert (a bad App Service setting): fix the GitHub secret/variable
> and re-deploy — don't hand-edit the portal (it's overwritten next deploy).

Do not re-tag or manually deploy a pre-floor commit. If no floor-compatible
revision is healthy, disable the affected `.cn` routing and stop the shared API
if required rather than restoring a notice-incapable build. Recover with a
forward fix or a known-good descendant of the floor. Stopping the shared API
is a separately authorized, all-region last resort; this runbook and the
[proposed ODR](./odr-2026-08-26-cn-provider-topology.md) grant no standing
authority.

EdgeOne rollback is independent: select only the exact registry-authorized
known-good deployment whose full source SHA and manifest evidence are retained, then revert the bad change
through protected `main` so source and production converge. Confirm the
known-good public SHA, routes, and manifest before resuming merges. Cloudflare
proxy rollback must restore a publicly trusted Azure certificate before
gray-clouding a hostname that uses Cloudflare Origin CA. See
[tencent-frontend.md](./tencent-frontend.md).

## Related

- [config-and-secrets.md](./config-and-secrets.md) · [monitoring-and-alerts.md](./monitoring-and-alerts.md)
- [Proposed China Operations Decision Record](./odr-2026-08-26-cn-provider-topology.md)
- [labs-analysis-worker.md](./labs-analysis-worker.md)
- `docs/deployment.md` (one-time Azure setup) · `.github/workflows/`

---
_Last reviewed: 2026-08-27 · Owner: @dddtc2005_
