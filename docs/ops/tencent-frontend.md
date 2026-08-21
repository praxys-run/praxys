# Regional frontend delivery: EdgeOne and Cloudflare

> **Summary:** Operate the ICP-filed China frontend on EdgeOne Makers while
> Cloudflare proxies the existing Azure frontend for the international domain.
> **Use when:** Provisioning, deploying, cutting over, verifying, or rolling
> back `praxys.cn`, or moving `praxys.run` behind Cloudflare Free.

## Target topology

```text
praxys.cn / www.praxys.cn -> EdgeOne Makers (global area, mainland available)
praxys.run / www.praxys.run -> Cloudflare Free -> Azure App Service praxys-frontend
api.praxys.run -> Azure App Service trainsight-app (Cloudflare DNS-only)
```

The API, database, credentials, sync scheduler, and AI integrations remain on
Azure. EdgeOne hosts only the pre-built SPA. Cloudflare is a reverse proxy and
cache in front of the existing Azure frontend; it is not a second application
deployment.

## Compliance and release gates

- Filed hosts: `praxys.cn` and `www.praxys.cn`.
- ICP service filing: `沪ICP备2025109616号-2`.
- Required link: `https://beian.miit.gov.cn/`.
- `praxys.run` must not display the China filing footer.
- Keep the filed service information and Tencent access relationship current.
  Confirm in writing that the existing filing is accepted for the selected
  EdgeOne mainland acceleration area before public DNS cutover.
- Complete the public-security filing within 30 days after the public service
  opens. Add its issued icon, exact number, and official link in a separate
  reviewed frontend change; never publish a placeholder.

The `.cn` SPA calls `https://api.praxys.run`, so authenticated account and
training data can cross the mainland border to Azure. Public production
acceptance requires a reviewed privacy/legal basis, accurate user disclosure,
and Trust approval for that cross-border path. Until that evidence and the
EdgeOne filing/access confirmation exist, keep EdgeOne `Auto Deploy` off, do
not bind the public `.cn` domains, and do not cut over DNS.

The stamped China artifact disables browser-side Azure Application Insights and
Statsig initialization, including their identity payloads. Re-enabling either
processor for `.cn` requires a separate reviewed privacy decision, disclosure,
transfer basis, and browser egress test.

Production acceptance also requires:

- an accepted Operations Decision Record for the provider topology;
- outside-in probes and action-group alerts for `.run` apex/`www` and both
  `.cn` hosts, provisioned from the canonical inventory in
  [monitoring-and-alerts.md](./monitoring-and-alerts.md#external-availability);
- an owned Origin CA expiry check and rotation threshold;
- aggregated Release Evidence retained outside short-lived job logs.

This repository change prepares reversible artifacts only. It does not create
the EdgeOne project, move nameservers, change DNS, issue certificates, alter
CORS, or enable production traffic.

## Prerequisites

- Tencent Cloud account with EdgeOne Makers and the filed `praxys.cn` service.
- Cloudflare account with permission to add the `praxys.run` zone.
- DNSPod/registrar access for both zones, including DNSSEC and DS records.
- Azure Contributor access to `rg-trainsight`.
- GitHub repository admin access for branch protection and the EdgeOne GitHub
  App repository grant.
- A complete export of every current `praxys.run` DNS record: A/AAAA, CNAME,
  MX, TXT, CAA, SRV, verification records, wildcards, TTLs, and proxy intent.
- A recorded rollback target and maintenance window. Nameserver migration is
  not an instant per-record rollback.

## Steps

### 1. Understand the build and evidence boundary

The accepted deployment mechanism is EdgeOne native Git integration. Direct
upload was rejected because the current official npm CLI carries unresolved
critical/high dependency vulnerabilities, while the official GitHub Action
executes that CLI through unpinned `npx`. GitHub therefore stores no EdgeOne
deployment token.

The checked-in boundary is:

1. `.github/workflows/deploy-frontend-appservice.yml` builds and stages the
   filing-free Azure package first.
2. GitHub then runs `npm run build:edgeone`, which performs an independent web
   build with fixed regional inputs, stamps every route HTML, disables
   App Insights and Statsig build inputs, writes `deployed_sha.txt`/`healthz`,
   and creates a sorted `SHA256SUMS`.
3. GitHub retains that independent `.cn` artifact and its manifest for 90 days.
4. EdgeOne checks out the same protected `main` commit and runs the same
   `web/edgeone.json` install/build/output configuration.
5. Once public domains are active, GitHub compares the served `SHA256SUMS` and
   source SHA with its independently built evidence, verifies the health and
   prerendered public routes, and hashes served JavaScript and CSS assets
   against that manifest. Before that comparison, evidence proves the same
   source and controlled inputs, not deployed byte identity.

Never stamp the Azure package or reuse an EdgeOne-built `web/dist` for Azure.

### 2. Bootstrap a Git-integrated EdgeOne project

An EdgeOne project cannot switch between Direct Upload and Git integration.
Create a new Git-integrated project from the outset:

1. Choose **Import Git Repository**, grant the EdgeOne GitHub App read-only
   access to only `praxys-run/praxys`, and select the protected `main` branch.
2. Name the project exactly `praxys-cn` and select the acceleration area that
   includes the Chinese mainland.
3. Set the project root to `web`. The checked-in `web/edgeone.json` pins:
   `npm ci --legacy-peer-deps`, `npm run build:edgeone`, output `./dist`, and
   Node `24.11.0`.
4. Keep Production **Auto Deploy off** and Preview disabled. Do not add build
   secrets or EdgeOne preview origins to API CORS.
5. After the release gates are accepted, run one console deployment from the
   reviewed `main` SHA and inspect it before enabling Auto Deploy.
6. Add `praxys.cn` and `www.praxys.cn` only after that deployment is accepted.
   Use the exact ownership/CNAME records shown by EdgeOne and wait for
   EdgeOne-managed HTTPS to become active.

Official references:

- [Importing a Git repository](https://pages.edgeone.ai/document/importing-a-git-repository)
- [Build guide](https://pages.edgeone.ai/document/build-guide)
- [`edgeone.json`](https://pages.edgeone.ai/document/edgeone-json)
- [Custom domains](https://pages.edgeone.ai/document/custom-domain)

### 3. Protect the Git deployment boundary

- Require pull-request review and required CI checks on `main`; disable force
  pushes and branch deletion. Once Auto Deploy is enabled, merging to `main`
  authorizes an EdgeOne production deployment.
- Keep the EdgeOne GitHub App repository grant read-only and limited to this
  repository. Revoke the grant to stop source access.
- Configure no EdgeOne build secrets. The regional build hard-codes only the
  public API URL and deliberately clears browser telemetry keys.
- Keep Preview disabled by default. If it is later enabled, require access
  control and `noindex`, and never add preview domains to production CORS.
- The only GitHub Actions control is
  `EDGEONE_CN_PUBLIC_VERIFY_ENABLED`; leave it false until both public `.cn`
  names resolve to the accepted project.

### 4. Allow only the two `.cn` browser origins

Azure App Service owns production API CORS. Add exact HTTPS origins before
public `.cn` traffic:

```bash
az webapp cors add \
  --name trainsight-app \
  --resource-group rg-trainsight \
  --allowed-origins \
    "https://praxys.cn" \
    "https://www.praxys.cn"

az webapp cors show \
  --name trainsight-app \
  --resource-group rg-trainsight \
  --query allowedOrigins \
  --output table
```

Do not add HTTP, wildcard, EdgeOne preview, or arbitrary branch-preview origins.
The public API hostname remains singular at `api.praxys.run`.

### 5. Deploy and inspect EdgeOne before DNS cutover

After the human release gates are accepted, inspect:

- the `frontend-edgeone-cn-*` GitHub artifact and `SHA256SUMS`;
- the source/config/manifest digests in `frontend-build-evidence-*`;
- one manual EdgeOne production deployment from the same reviewed `main` SHA;
- the EdgeOne project/deployment record and preview;
- ICP footer isolation, SPA routes, security headers, and the source SHA.

Keep Auto Deploy and `EDGEONE_CN_PUBLIC_VERIFY_ENABLED` off during this
inspection. If the source SHA and behavior are accepted, enable Auto Deploy for
Production `main`; branch protection becomes the ongoing deployment gate.

### 6. Cut over `praxys.cn` inside Tencent

Keep the `.cn` zone on DNSPod/Tencent. Lower TTLs before the window, then add
the exact CNAME/verification records provided for both custom domains by
EdgeOne. Wait for:

- domain ownership verified;
- managed HTTPS active for both names;
- the expected `praxys-cn` deployment selected as production;
- the ICP footer and source SHA visible through the custom names.

Then set:

```bash
gh variable set EDGEONE_CN_PUBLIC_VERIFY_ENABLED --body true
```

The next frontend deployment verifies both hosts, the deployed SHA, ICP footer,
served manifest parity, SPA fallback, TLS reachability,
`X-Content-Type-Options`, and private-route `X-Robots-Tag`.

### 7. Import `praxys.run` into Cloudflare without changing traffic

Cloudflare Free requires full authoritative DNS setup; it cannot be used as a
partial/CNAME-only zone. This changes nameservers, not the registrar or Azure
hosting.

1. Export the DNSPod zone and save the before-state outside the repository.
2. Add `praxys.run` to Cloudflare and import every record.
3. Compare the two zones record by record. Preserve MX/TXT/CAA/asuid and all
   validation records.
4. Set every Cloudflare record to **DNS-only** initially.
5. Confirm `api.praxys.run` is a DNS-only CNAME to
   `trainsight-app.azurewebsites.net`.
6. If DNSSEC is enabled, record the parent DS TTL and remove the old DS record
   at the registrar while the old provider continues signing.
7. Wait at least the recorded parent DS TTL. Verify from multiple independent
   resolvers and with `dig +trace DS praxys.run` that the old DS is no longer
   returned. Only then disable signing at the old provider. Changing
   nameservers or stopping signatures while cached DS records remain can
   produce `SERVFAIL`.
8. Replace the registrar nameservers with the two assigned by Cloudflare.
9. Wait for the Cloudflare zone to become active, validate mail/API/frontend
   resolution, then enable Cloudflare DNSSEC and publish its new DS record.

Do not orange-cloud any record during the nameserver migration.

### 8. Put the Azure frontend behind Cloudflare safely

Before proxying, Cloudflare Universal SSL must show **Active**. Set the zone to
`Full (strict)`; never use Flexible.

The current Azure App Service managed certificate is suitable for the first
orange-cloud cutover while it is valid. However, Azure requires a frontend apex
A record or subdomain CNAME to remain mapped directly to App Service for free
managed-certificate issuance and renewal. A Cloudflare-proxied record no longer
satisfies that durable renewal assumption. Do not treat the existing App
Service managed certificate as the long-term origin certificate.

Cut over one hostname at a time:

1. Proxy `www.praxys.run`; verify edge TLS, Azure response, login, assets, and
   `/healthz`.
2. Proxy `praxys.run`; repeat the same checks.
3. Keep `api.praxys.run` DNS-only.
4. Do not add a `Cache Everything` rule. Azure already sends immutable caching
   for hashed assets and revalidation for the SPA shell.

Once both frontend records are stably proxied, create a Cloudflare Origin CA
certificate covering `praxys.run` and `*.praxys.run`, convert it to a
password-protected PFX with the matching Cloudflare Origin CA root, upload it
to `praxys-frontend`, and bind it to the two frontend hostnames. Keep the
replaced public certificate and its thumbprint in the release evidence for the
rollback window.

Example operator-side conversion and binding:

```bash
set -euo pipefail
umask 077
workdir="$(mktemp -d)"
cleanup() {
  unset PFX_PASSWORD
  rm -f "${workdir}/origin.pem" "${workdir}/origin.key" \
    "${workdir}/origin-root.pem" "${workdir}/praxys-origin.pfx"
  rmdir "${workdir}" 2>/dev/null || true
}
trap cleanup EXIT
cp <CLOUDFLARE_ORIGIN_CERT_PEM> "${workdir}/origin.pem"
cp <CLOUDFLARE_ORIGIN_PRIVATE_KEY> "${workdir}/origin.key"
curl -fsS --connect-timeout 5 --max-time 30 \
  https://developers.cloudflare.com/ssl/static/origin_ca_rsa_root.pem \
  -o "${workdir}/origin-root.pem"
read -rsp "PFX password: " PFX_PASSWORD
echo
export PFX_PASSWORD

openssl pkcs12 -export \
  -out "${workdir}/praxys-origin.pfx" \
  -inkey "${workdir}/origin.key" \
  -in "${workdir}/origin.pem" \
  -certfile "${workdir}/origin-root.pem" \
  -passout env:PFX_PASSWORD

ORIGIN_THUMBPRINT="$(
  az webapp config ssl upload \
    --name praxys-frontend \
    --resource-group rg-trainsight \
    --certificate-file "${workdir}/praxys-origin.pfx" \
    --certificate-password "${PFX_PASSWORD}" \
    --certificate-name praxys-cloudflare-origin \
    --query thumbprint \
    --output tsv
)"

for host in praxys.run www.praxys.run; do
  az webapp config ssl bind \
    --name praxys-frontend \
    --resource-group rg-trainsight \
    --hostname "${host}" \
    --certificate-thumbprint "${ORIGIN_THUMBPRINT}" \
    --ssl-type SNI
done

trap - EXIT
cleanup
```

Cloudflare Origin CA is available on the Free plan and is trusted by
`Full (strict)`, but browsers do not trust it directly. Cloudflare does not send
Origin CA expiry notifications, so record its expiry in the certificate
inventory and monitor it. See:

- [Cloudflare Origin CA](https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/)
- [Full (strict)](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/)
- [Azure App Service certificates](https://learn.microsoft.com/azure/app-service/configure-ssl-certificate)

### 9. Defer geographic redirect

DNS cannot issue an HTTP redirect. Cloudflare can later return a temporary
redirect for mainland clients, but browser storage and login sessions do not
transfer between `.run` and `.cn`.

Do not enable a geographic redirect during the initial cutover. After Product,
Trust, and Quality accept the `.cn` authenticated journey, use a Cloudflare
Single Redirect with HTTP `302`, preserving path and query. Never use a
permanent `301`/`308` for an IP-derived geography decision.

## Verify

Repository and deployment evidence:

```bash
gh run watch "$(
  gh run list \
    --workflow deploy-frontend-appservice.yml \
    --limit 1 \
    --json databaseId \
    --jq '.[0].databaseId'
)" --exit-status
```

Public topology:

```bash
dig +short NS praxys.run
dig +short CNAME api.praxys.run
curl -fsSI --connect-timeout 5 --max-time 15 \
  https://www.praxys.run/ | grep -i '^cf-ray:'
curl -fsSI --connect-timeout 5 --max-time 15 \
  https://praxys.run/ | grep -i '^cf-ray:'
curl -fsS --connect-timeout 5 --max-time 15 \
  https://api.praxys.run/api/health

for host in praxys.cn www.praxys.cn; do
  curl -fsS --connect-timeout 5 --max-time 15 \
    "https://${host}/" | grep -F '沪ICP备2025109616号-2'
  curl -fsS --connect-timeout 5 --max-time 15 \
    "https://${host}/deployed_sha.txt"
  curl -fsS --connect-timeout 5 --max-time 15 \
    "https://${host}/today" | grep -F 'id="root"'
  curl -fsSI --connect-timeout 5 --max-time 15 "https://${host}/" \
    | grep -Ei '^(x-content-type-options|x-frame-options|referrer-policy):'
done

test -z "$(
  curl -fsS --connect-timeout 5 --max-time 15 \
    https://www.praxys.run/ \
    | grep -F '沪ICP备2025109616号-2' || true
)"
```

CORS:

```bash
for origin in https://praxys.cn https://www.praxys.cn; do
  curl -isS --connect-timeout 5 --max-time 15 \
    -X OPTIONS https://api.praxys.run/api/health \
    -H "Origin: ${origin}" \
    -H 'Access-Control-Request-Method: GET' \
    | grep -Fi "access-control-allow-origin: ${origin}"
done
```

Origin certificate after the Origin CA binding:

```bash
echo \
  | openssl s_client \
      -connect praxys-frontend.azurewebsites.net:443 \
      -servername praxys.run \
      -showcerts 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates -ext subjectAltName
```

Release evidence must record the EdgeOne Git repository grant, project and
deployment IDs, source SHA, GitHub and served manifest digests, Azure
origin/public deployment receipts, public DNS answers, certificate
issuers/expiry, Cloudflare zone state and SSL mode, API DNS-only status, CORS
results, monitoring readiness, the accepted Operations Decision Record, and
human approvals for filing access and cross-border processing. Preserve the
aggregated record in the approved operations evidence store; GitHub artifacts
alone expire after 90 days.

## Rollback / Recovery

### EdgeOne deployment

Turn Production Auto Deploy off while investigating. Use the EdgeOne
deployment-history rollback only when the prior deployment's source SHA and
manifest evidence are known, then revert the bad change on protected `main` so
source and production converge. Verify the known-good SHA before re-enabling
Auto Deploy. Until public cutover, leave custom domains on their prior records.
If source access must stop, revoke the EdgeOne GitHub App repository grant.

### Cloudflare proxy

If the Azure origin still has a publicly trusted certificate bound, gray-cloud
the affected frontend record. If Cloudflare Origin CA is bound, first rebind an
unexpired public certificate to that hostname; gray-clouding first exposes an
untrusted certificate to browsers. `api.praxys.run` is already DNS-only and is
not part of this rollback.

### Cloudflare nameservers

Do not change nameservers as a first response to an edge incident. A full
nameserver rollback requires the saved DNSPod zone to be current, all records
to exist there, and a new maintenance window. Remove the Cloudflare DS record,
leave Cloudflare signing enabled, wait at least the parent DS TTL, and verify
the DS is absent. Only then disable Cloudflare DNSSEC and restore the DNSPod
nameservers. After the old authority is stable, enable its signing and publish
its DS record. Prefer per-record proxy disablement.

### Geographic redirect

Disable the Cloudflare redirect rule. No DNS or application deployment change
is required.

## Related

- [`deploy.md`](./deploy.md) · [`config-and-secrets.md`](./config-and-secrets.md)
- [`search-discovery.md`](./search-discovery.md)
- `.github/workflows/deploy-frontend-appservice.yml`
- `web/edgeone.json`
- `web/scripts/stamp-china-compliance.mjs`

---
_Last reviewed: 2026-08-20 · Owner: @dddtc2005_
