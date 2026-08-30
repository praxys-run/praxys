# Regional frontend delivery: EdgeOne and `.run`

> **Summary:** Operate the static China web private-alpha frontend without
> changing the existing `.run` service.
> **Use when:** Creating, checking, or taking down the EdgeOne custom domains.

## Topology

```text
praxys.cn / www.praxys.cn -> EdgeOne Makers static SPA
praxys.run / www.praxys.run -> existing Cloudflare/Azure frontend
api.praxys.run -> Azure App Service trainsight-app (DNS-only)
```

The invite-only private alpha is web-only. There is no public signup,
geographic redirect, new telemetry, API proxy, SSR, function, mainland API, or
mainland datastore. Miniapp publication is deferred. `.run` remains available
and is not changed by `launch-cn.yml`.

EdgeOne receives static HTML, JavaScript, CSS, `healthz`,
`deployed_sha.txt`, ICP markup, and checked-in security configuration. It
receives no secret, telemetry credential, personal data, server-side rendering,
function, or API proxy. Authenticated requests go directly from the browser to
the DNS-only `https://api.praxys.run`.

## Prerequisites

- Human acceptance of the exact
  [PIPIA](./cn-personal-information-impact-assessment.md) before enable.
- Tencent/EdgeOne and registrar/DNS access.
- Current protected-main SHA and successful required checks.
- Filed service metadata `沪ICP备2025109616号-2`.
- A manual static-takedown owner and saved DNS/provider before-state.
- Outside-in tests and alerts from
  [monitoring-and-alerts.md](./monitoring-and-alerts.md).

## Public-security filing

The ICP footer is not a public-security filing. Record the first public-access
time, then follow [File the China website with public
security](./cn-public-security-filing.md) within the statutory 30-day window.
Never publish a placeholder number, guessed query code, or unofficial icon.

## One-time manual EdgeOne setup

These are human provider actions. No repository workflow performs them.

1. In EdgeOne Makers choose **Import Git Repository**.
2. Grant its GitHub App read-only access to only `praxys-run/praxys`.
3. Select protected `main`, project root `web`, and project name `praxys-cn`.
4. Use the checked-in `web/edgeone.json` build:
   `npm ci --legacy-peer-deps`, `npm run build:edgeone`, `./dist`, Node
   `24.11.0`.
5. Configure no environment secret, browser telemetry key, API token, server
   function, or API proxy.
6. Bind `praxys.cn` and `www.praxys.cn` using only the exact ownership/CNAME
   records EdgeOne provides.
7. Wait for managed TLS and verify the selected production deployment reports
   the expected full protected-main SHA.
8. Record the Git grant, project/deployment IDs, domain state, DNS answers, TLS
   issuer/expiry, and rollback/takedown path outside short-lived logs.

Preview/default provider URLs are non-production: keep them access-controlled
and `noindex`; never add them to API CORS.

## Repository build boundary

`deploy-frontend-appservice.yml` first copies the filing-free Azure build into
its deploy package, then runs `npm run build:edgeone` only as build validation.
It uploads no EdgeOne artifact, does not deploy to EdgeOne, and holds no
EdgeOne credential.

The native Git project separately runs the same checked-in regional build.
The output contains:

- exact `deployed_sha.txt`;
- JSON `healthz`;
- ICP footer and China deployment marker; after public-security approval, the
  separately reviewed exact public-security filing markup;
- SPA rewrites and checked-in security headers.

There is no checksum-manifest, release-floor, registry, or repeated preflight
evidence ceremony. Source SHA is provenance, not PIPIA acceptance or production
authority.

## API CORS and runtime gate

Before the first launch CORS may be exactly:

```json
[
  "https://praxys.run",
  "https://www.praxys.run",
  "https://praxys-frontend.azurewebsites.net"
]
```

After launch, enabled or disabled processing keeps the exact five-origin
base-plus-China set:

```json
[
  "https://praxys.run",
  "https://www.praxys.run",
  "https://praxys-frontend.azurewebsites.net",
  "https://praxys.cn",
  "https://www.praxys.cn"
]
```

Do not add HTTP, wildcard, provider preview, or branch-preview origins. CORS is
not processing authority: keeping the two `.cn` origins after disable lets
authenticated rights requests preflight while the server kill switch blocks
ordinary routes. Keep `api.praxys.run` DNS-only.

Use `.github/workflows/launch-cn.yml` from current protected `main`:

- `status` performs no mutation and validates core API/`.run`, filtered
  China/Miniapp/AI/Labs settings, and exact CORS. It reports unavailable `.cn`
  hosts as warnings before DNS exists. It does not inspect GitHub environment
  protection, web tests, monitoring, or alerts.
- `enable` requires the exact PIPIA human gate and `china-production`, then
  changes only the China processing switch and the two CORS origins.
- `disable` sets only the China processing switch. It leaves valid CORS and
  Azure AI unchanged; static takedown remains manual.

The workflow never changes `PRAXYS_DISABLE_BACKGROUND_AI`. Enable requires its
healthy value `false`; emergency disable accepts and preserves either explicit
boolean state.

## Verify

Run `launch-cn.yml` `status`, then independently verify:

```bash
for host in praxys.cn www.praxys.cn; do
  getent ahostsv4 "${host}"
  curl -fsSI --connect-timeout 5 --max-time 15 "https://${host}/" \
    | grep -Ei '^(x-content-type-options|x-frame-options|referrer-policy):'
  curl -fsS --connect-timeout 5 --max-time 15 \
    "https://${host}/deployed_sha.txt"
  curl -fsS --connect-timeout 5 --max-time 15 \
    "https://${host}/healthz" | jq .
done

curl -fsS https://api.praxys.run/api/health
curl -fsS https://www.praxys.run/healthz
```

Enable verification additionally requires exact five-origin CORS, successful
OPTIONS preflight from both `.cn` origins, unauthenticated `401`, and stale
policy `428 CLIENT_PRIVACY_UPDATE_REQUIRED`.

## Rollback / Recovery

1. Dispatch `launch-cn.yml` `disable` from current protected `main`.
2. Verify China disabled, exact base or base-plus-CN CORS, healthy API/`.run`,
   and unchanged Azure AI state. The static site and bounded rights routes
   remain reachable while ordinary processing is disabled.
3. If static content must be unavailable, manually disable/unbind both custom
   domains or restore their saved DNS records. Verify both public names before
   claiming takedown.
4. Revoke the EdgeOne GitHub App grant if source access itself must stop.
5. Do not change `.run`, proxy `api.praxys.run`, or stop the shared API for a
   China-only static incident.

For a security or personal-data incident, involve Trust and follow
[incident-response.md](./incident-response.md). Record signals, severity,
mitigation, verification, recurrence, and durable follow-ups.

## Related

- [cn-web-private-alpha.md](./cn-web-private-alpha.md)
- [deploy.md](./deploy.md)
- [config-and-secrets.md](./config-and-secrets.md)
- [monitoring-and-alerts.md](./monitoring-and-alerts.md)

---
_Last reviewed: 2026-08-29 · Owner: Operations_
