# Deploy & rollback

> **Summary:** How each Praxys surface deploys and how to recover.
> **Use when:** Shipping a change, rerunning a deployment, or rolling back.

## Deployment inventory

| Surface | Workflow | Trigger / target |
|---|---|---|
| Backend API | `deploy-backend.yml` | protected `main` backend paths or manual protected-main dispatch → App Service `trainsight-app` |
| Frontend SPA | `deploy-frontend-appservice.yml` | protected `main` web paths or manual protected-main dispatch → App Service `praxys-frontend`; regional build validation only |
| China web gate | `launch-cn.yml` | manual current protected `main`; only `enable` requires `china-production` |
| Labs worker | `deploy-labs-worker.yml` | its documented main/tag/manual triggers; Azure reconciliation remains gated |
| Miniapp candidate upload | `miniapp-publish.yml` | protected-main robot 5 development upload or `miniapp-*` robot 1 candidate upload; provider review/promotion/publication remain manual |

Azure targets use OIDC. There is no Azure client secret, publish profile,
self-hosted production runner, or EdgeOne deployment credential in GitHub
Actions. EdgeOne uses a repository-scoped read-only native Git integration.

## Backend

The workflow:

1. Optionally relies on the required pre-merge suite or runs it again.
2. Stamps the API version and full source SHA.
3. Logs in with protected-main OIDC.
4. Quiesces `PRAXYS_ENABLE_FEEDBACK_PUBLICATION=false` before old code can
   observe any new publication configuration.
5. Leaves `PRAXYS_DISABLE_CN_PROCESSING`, CORS,
   `PRAXYS_DISABLE_FEEDBACK_PUBLICATION`, and
   `PRAXYS_DISABLE_BACKGROUND_AI` untouched.
6. Preserves telemetry, database, Labs, secrets, Always On, and other ordinary
   configuration behavior when `sync_config=true`.
7. Preserves the Miniapp emergency switch and existing WeChat App Service
   credentials when both GitHub secrets are absent; on the first rollout, an
   absent Miniapp switch is initialized enabled. Supplying exactly one
   WeChat secret fails before any configuration mutation.
8. Deploys and verifies exact API version/source SHA and readiness while
   feedback publication remains quiesced, then restores and verifies the
   reviewed positive value. It also verifies either
   preserved China/Miniapp state and the reported Azure
   AI emergency state.
9. Writes a concise run summary. It performs no EdgeOne probe or restoration.

An ordinary healthy production state has
`PRAXYS_DISABLE_BACKGROUND_AI=false`. An explicit `true` emergency stop is
preserved, not silently cleared. The workflow never writes China release
metadata.

```bash
gh workflow run deploy-backend.yml --ref main -f sync_config=false
gh workflow run deploy-backend.yml --ref main -f sync_config=true
```

The configuration path still waits for App Service management-write recycle
before ZipDeploy. The B1 plan has no slots. PostgreSQL uses its configured PITR;
there is no unsupported on-demand Burstable-tier snapshot.

## Frontend

The workflow builds the filing-free `.run` bundle first and copies it into the
Azure package before running `npm run build:edgeone` as validation. It then:

- deploys and verifies `praxys-frontend` plus `www.praxys.run`;
- performs no EdgeOne deployment, DNS, TLS, domain, or production-authorization
  action;
- uploads no EdgeOne artifact and performs no public `.cn` verification.

The EdgeOne native Git project separately runs `web/edgeone.json`. Its static
build contains `healthz`, `deployed_sha.txt`, ICP markup, and security
configuration without a checksum manifest or release-preflight ceremony.

### Service-worker cache contract

Both frontend providers must serve the exact `/sw.js` path with:

```text
Cache-Control: no-cache, max-age=0, must-revalidate
```

For `.run`, `frontend_server/main.py` sets this at the Azure origin and
Cloudflare must preserve it. For `.cn`, `web/edgeone.json` sets the same value
at EdgeOne. The exact rule precedes generic JavaScript/static rules. Only
content-addressed `/assets/*` files receive
`public, max-age=31536000, immutable`; never apply that policy to `sw.js`.

After both provider releases report the expected protected-main SHA, read back
the final response at all four public origins:

```bash
for url in \
  https://praxys.run/sw.js \
  https://www.praxys.run/sw.js \
  https://praxys.cn/sw.js \
  https://www.praxys.cn/sw.js; do
  curl -fsSIL --max-time 15 "${url}" \
    | grep -Ei '^(HTTP/|cache-control:|etag:|last-modified:)'
done
```

If a previously cacheable worker is still present during this correction,
purge **only those four exact `/sw.js` URLs** in Cloudflare and EdgeOne after
the matching deployment is live. Do not wildcard-purge `/`, HTML, or
`/assets/*`. Repeat the readback and verify a normal reload reaches the current
Terms bundle while keeping its acceptance checkbox initially clear.

Rollback application code through protected `main`, then repeat the SHA and
header readback. Preserve this `sw.js` header contract during rollback: restoring
the old cacheable-worker policy recreates the incident. The client recovery is
bounded to one automatic reload per tab episode. It reloads only after a
same-origin replacement worker reaches `activated` and takes control of the
current page; activation or controller-handoff timeout remains gated. Recovery
also remains gated when offline, storage is unavailable, no same-origin worker
exists, or the update fails.

## China public web launch

Follow [cn-web-private-alpha.md](./cn-web-private-alpha.md). `status` is
read-only and unprotected by an environment; only `enable` uses
`china-production`. `disable` is an emergency main-branch action with no
frontend/API SHA dependency.

Status validates core API/`.run`, filtered settings, and exact CORS and reports
`.cn` host warnings before DNS exists. It does not verify GitHub environment
protection, web tests, monitoring, alerts, or the human PIPIA/topology gates.

The operator accepted PIPIA `1.2-public-parity` and its overall **Medium**
residual risk on 2026-08-31. Before enable, a human still verifies that the
exact implementation and live controls match it. Public registration follows
the global `.run` switch and
seat cap. The existing Miniapp remains enabled on `api.praxys.run`. Regional
Application Insights and product events use the minimized boundary, while
browser Statsig stays absent from `.cn` pending #754. There is no proxy,
mainland API, or mainland datastore. Geographic `302` is separately enabled
only after `.cn` stabilizes.

## Labs worker

`deploy-labs-worker.yml` continues to build/test the 1-vCPU/2-GiB image and
reconciles Azure only when `PRAXYS_LABS_WORKER_DEPLOY_ENABLED=true`. Backend
deployment accepts `inline`, `service_bus`, or maintenance-only `disabled`.
Before `service_bus` is selected, the worker identity, queue, database
principal, image, shared processing-authority checks, and alerts must pass
[labs-analysis-worker.md](./labs-analysis-worker.md).

## Miniapp

Robot 5 remains a protected-main development lane. Robot 1 remains only a
candidate upload lane; promotion to trial, review submission, and publication
stay manual in WeChat. The China web launch workflow never calls or waits for
Miniapp publication. Backend config sync preserves
`PRAXYS_DISABLE_MINIAPP_PROCESSING`; an initially absent setting defaults to
`false`. Release tags must point to a commit
reachable from protected `main` before the upload key is made available.

## Verify

```bash
curl -fsS https://api.praxys.run/api/health
curl -fsS https://api.praxys.run/api/version
curl -fsS https://api.praxys.run/api/health/ready \
  | jq '{status, china_processing, miniapp_processing, optional_processing}'
curl -fsS https://www.praxys.run/healthz
```

Use `launch-cn.yml` `status` for its filtered settings, exact CORS, core
API/`.run`, and `.cn` host snapshot. Verify monitoring, alerts, environment
protection, PIPIA acceptance, and provider topology separately.

## Rollback / Recovery

- **Backend/frontend code:** revert through protected `main`; keep every
  already-applied Alembic revision in the graph. A destructive schema change
  requires a forward fix.
- **Failed backend deploy:** the workflow does not change China, CORS, or Azure
  AI state. Verify those controls and shared API/`.run` health before claiming
  mitigation.
- **China-only incident:** run `launch-cn.yml` `disable`. Static EdgeOne
  takedown is manual because the repository holds no provider credential.
  Do not stop the shared API or mutate `.run` for a China-only event.
- **Azure AI incident:** use its independent emergency process. China and
  backend deployment workflows never toggle that control.
- **Configuration:** correct the repository-owned secret/variable and rerun
  with `sync_config=true`; do not rely on a portal edit that the workflow owns.

## Related

- [config-and-secrets.md](./config-and-secrets.md)
- [cn-web-private-alpha.md](./cn-web-private-alpha.md)
- [monitoring-and-alerts.md](./monitoring-and-alerts.md)
- [labs-analysis-worker.md](./labs-analysis-worker.md)

---
_Last reviewed: 2026-09-06 · Owner: Operations_
