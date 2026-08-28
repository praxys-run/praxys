# Regional frontend delivery: EdgeOne and Cloudflare

> **Summary:** Operate the ICP-filed China frontend on EdgeOne Makers while
> Cloudflare proxies the existing Azure frontend for the international domain.
> **Use when:** Provisioning, deploying, cutting over, verifying, or rolling
> back `praxys.cn`, or moving `praxys.run` behind Cloudflare Free.

## Target topology

The governing
[Operations Decision Record](./odr-2026-08-26-cn-provider-topology.md) is
**PROPOSED — PENDING HUMAN ACCEPTANCE**. The topology below is not current
production authority.

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
  The approved filing covers both public `.cn` hosts; changes to the operator,
  service, domain, or access provider require the corresponding filing update.
- Complete the public-security filing within 30 days after the public service
  opens. Add its issued icon, exact number, and official link in a separate
  reviewed frontend change; never publish a placeholder.

The `.cn` SPA calls `https://api.praxys.run`, so authenticated account and
training data can cross the mainland border to Azure East Asia in Hong Kong.
The operator is reviewing that cross-border path under the contract-necessity
assessment `PIPIA-CN-2026-08-25-01`; see
[cn-personal-information-impact-assessment.md](./cn-personal-information-impact-assessment.md).
Public production acceptance still requires the exact policy/gate build,
provider just-in-time disclosure, production privacy switches, CORS, HTTPS,
outside-in monitoring, and Release Evidence below. A Git-triggered EdgeOne
build does not itself create a public data path.

The stamped China artifact disables browser-side Azure Application Insights and
Statsig initialization, including their identity payloads. Re-enabling either
processor for `.cn` requires a separate reviewed privacy decision, disclosure,
transfer basis, and browser egress test.

The authenticated China release also requires:

- the versioned processing notice to block auth prefetch/restoration and all
  mini-program requests before acknowledgement;
- `.cn` requests to carry the stamped source SHA, current notice version and
  digest, and `cn-privacy-v1` API contract;
- WeChat requests to carry Miniapp version `2026.08.2` or newer, its stamped
  source SHA, current notice version and digest, and API contract; the API
  accepts only entries in the server-owned exact release registry and rejects
  missing, older, or unlisted clients before route processing;
- current Terms/Privacy acceptance to be recorded as a digest-bound,
  append-only server receipt, with
  personal-data endpoints returning `428 TERMS_ACCEPTANCE_REQUIRED` until the
  current receipt exists;
- every provider connection dialog to show the provider transfer notice and
  official privacy/contact link before credentials or OAuth authorization;
- `PRAXYS_DISABLE_BACKGROUND_AI=false` for ordinary Azure AI availability while the independent China boundary remains disabled,
  `PRAXYS_ENABLE_FEEDBACK_PUBLICATION=false`, and
  `PRAXYS_DISABLE_FEEDBACK_PUBLICATION=true` in the backend App Service;
- Statsig server evaluation to remain local with user logging and diagnostics
  disabled;
- backend monitoring retention to remain 30 days.

Production acceptance also requires:

- final operator approval of `PIPIA-CN-2026-08-25-01`;
- human acceptance of the proposed
  [Operations Decision Record](./odr-2026-08-26-cn-provider-topology.md) for
  the provider topology and staged rollback floor;
- `CN_PRIVACY_FLOOR_SHA` set to the first privacy-capable protected-main
  commit, with backend, frontend, and Miniapp workflow checks passing;
- outside-in probes and action-group alerts for `.run` apex/`www` and both
  `.cn` hosts, provisioned from the canonical inventory in
  [monitoring-and-alerts.md](./monitoring-and-alerts.md#external-availability);
- Azure App Service `httpsOnly=true` for both frontend and API sites;
- aggregated Release Evidence retained outside short-lived job logs.

Cloudflare Origin CA is optional `.run` origin hardening, not a `.cn` cutover
gate while the Azure origin keeps a publicly trusted certificate. If it is
adopted later, record its expiry and rotation threshold before binding it.

The EdgeOne Git project, candidate deployment, filing, and draft PIPIA now
exist. Preparation may harden Azure HTTPS and provision monitoring, but it
does not bind public `.cn` domains, change DNS, add `.cn` CORS, or enable
production traffic.

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
4. EdgeOne native Git runs the checked-in `web/edgeone.json` boundary. The
   build invokes an explicit unpublished-preparation preflight. Without a
   GitHub token it uses local protected-main ancestry and exact disabled-runtime
   readback plus the project-level non-secret `CN_PRIVACY_FLOOR_SHA`, but it
   cannot claim a provider release ID or registry authorization.
5. After the provider creates a deployment, retain its exact deployment ID and
   successful build evidence, then create the separately reviewed registry
   entry. Only after that binding may GitHub compare the served `SHA256SUMS` and
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
4. Configure one non-secret project build variable,
   `CN_PRIVACY_FLOOR_SHA`, only after the accepted floor reaches protected
   `main`; its value must exactly match the GitHub Actions variable. Configure
   no approved-release registry or build secret.
5. Record the project's actual Git trigger and preview/default-URL behavior;
   current Makers projects may not expose Auto Deploy or Preview switches. Do
   not add build secrets or EdgeOne preview origins to API CORS.
6. Before release, inspect the deployment-history entry for the reviewed
   `main` SHA and record the project ID, deployment ID, source SHA, manifest,
   and known-good rollback deployment.
7. Add `praxys.cn` and `www.praxys.cn` only after that deployment is accepted.
   Use the exact ownership/CNAME records shown by EdgeOne and wait for
   EdgeOne-managed HTTPS to become active.

Official references:

- [Importing a Git repository](https://pages.edgeone.ai/document/importing-a-git-repository)
- [Build guide](https://pages.edgeone.ai/document/build-guide)
- [`edgeone.json`](https://pages.edgeone.ai/document/edgeone-json)
- [Custom domains](https://pages.edgeone.ai/document/custom-domain)

### 3. Protect the Git deployment boundary

- Require pull-request review and required CI checks on `main`; disable force
  pushes and branch deletion. These current records do not prove pre-merge
  timing, absence of admin bypass, or producer identity. Native EdgeOne remains
  fail-closed until authenticated protected-check evidence is available through
  an accepted mechanism; deployment history, source SHA, and manifests are not
  authority.
- Do not use the ruleset admin bypass for a regional release.
- Keep the EdgeOne GitHub App repository grant read-only and limited to this
  repository. Revoke the grant to stop source access.
- Configure no EdgeOne build secrets. The regional build hard-codes the public
  API URL, deliberately clears browser telemetry keys, and accepts only the
  non-secret `CN_PRIVACY_FLOOR_SHA` control input.
- Treat preview/default URLs as non-production: require access control and
  `noindex`, never add them to production CORS, and never accept them as public
  release evidence.
- The only GitHub Actions control is
  `EDGEONE_CN_PUBLIC_VERIFY_ENABLED`; leave it false until both public `.cn`
  names resolve to the accepted project.

### 3a. Stage the privacy floor and disabled candidate evidence

The privacy-floor merge does not block ordinary filing-free `.run` backend or
Azure frontend deployment. Those lanes remain operable and enforce fixed
disabled privacy literals plus absent `.cn` CORS. China release authorization and robot 1 Miniapp release publication fail closed
until exact floor, registry, disabled-runtime, CORS, readiness, and deployed-SHA
evidence exists. EdgeOne artifact preparation is the earlier non-authorizing
phase: it requires the floor and disabled-runtime readback but no not-yet-created
provider ID. Robot 5 development uploads
remain separate: they require protected-main provenance and use synthetic
versions, but never become registry authorization.

Step 1 is repository preparation under normal protected-branch authority.
Steps 2–7 are proposed production actions and must not begin while the
[Operations Decision Record](./odr-2026-08-26-cn-provider-topology.md) or PIPIA
is pending:

1. Merge the complete floor through protected `main` and record its full SHA.
   Allow ordinary `.run` deployment to complete in the fixed disabled state.
2. After the human gate cites that exact SHA, set it as
   `CN_PRIVACY_FLOOR_SHA` in both GitHub Actions and the EdgeOne `praxys-cn`
   build environment, and retain exact readback from both control planes.
3. Prepare the EdgeOne artifact while processing and `.cn` CORS remain disabled.
   After EdgeOne creates the candidate deployment, retain its exact provider ID,
   source/manifest evidence, and successful provider status, then populate the
   exact approved-release registry. For the Miniapp, stage only the deterministic
   `wechat:robot-1:<version>` locator while processing remains disabled, then
   retain the successful upload evidence before any activation. Manually
   dispatch `deploy-backend.yml` with
   `china_release_validation=true` and `sync_config=true`.
4. Require exact registry bytes/digest/count, all four fixed runtime literals,
   disabled `.cn` CORS, readiness, privacy contract, API version, and deployed
   source SHA. No current workflow can set the China processing switch false
   or add CORS.
5. Dispatch the frontend workflow. Verify `.run` independently. EdgeOne
   artifact preparation proceeds only if its public disabled-runtime readback
   matches the same candidate; otherwise it is skipped fail closed. A prepared
   artifact remains unauthorized until step 3's provider evidence and registry
   binding are complete.
6. Create the exact `miniapp-2026.08.2` Miniapp tag only after the matching
   disabled backend is deployed and the registry binds that SHA/version to
   `wechat:robot-1:2026.08.2`. The robot 1 upload lane repeats the floor,
   registry, runtime, CORS, readiness, ref/version/provider-locator, and SHA
   checks before uploading a candidate.
7. Promotion, publication, `.cn` CORS, DNS binding, and processing activation
   remain separate human-authorized actions with no implemented activation
   workflow.

The production Azure OIDC federated credential remains scoped to protected
`main`, never wildcard refs or arbitrary tags. Azure workflows use OIDC only;
do not add a client secret or publish profile as a fallback. The WeChat release
line remains manual and cannot bypass the exact candidate checks.

### 4. Allow only the two `.cn` browser origins

Azure App Service owns production API CORS. The current workflows enforce the
exact disabled inventory and cannot add `.cn` origins. The commands below are
a future human-authorized operation only; they are not accepted or implemented
activation. A public-only `.cn` site must keep both origins absent.

```bash
az webapp cors add \
  --name trainsight-app \
  --resource-group rg-trainsight \
  --allowed-origins \
    "https://praxys.cn" \
    "https://www.praxys.cn"

expected_origins='["https://praxys.run","https://www.praxys.run","https://praxys-frontend.azurewebsites.net","https://praxys.cn","https://www.praxys.cn"]'
actual_origins="$(az webapp cors show \
  --name trainsight-app \
  --resource-group rg-trainsight \
  --query allowedOrigins \
  --output json)"
jq -e --argjson expected "${expected_origins}" \
  '(sort == ($expected | sort) and index("*") == null)' \
  <<< "${actual_origins}"
```

Disabled state has one exact inventory and must contain no `.cn` origin:

```json
["https://praxys.run", "https://www.praxys.run", "https://praxys-frontend.azurewebsites.net"]
```

Enabled state has the five-origin inventory shown above. Readback compares full
normalized equality and Release Evidence records the complete non-secret array,
not only a filtered China subset.

Do not add HTTP, wildcard, EdgeOne preview, or arbitrary branch-preview origins.
The public API hostname remains singular at `api.praxys.run`.

### 5. Deploy and inspect EdgeOne before DNS cutover

After the release controls above are accepted, inspect:

- the `frontend-edgeone-cn-*` GitHub artifact and `SHA256SUMS`;
- the source/config/manifest digests in `frontend-build-evidence-*`;
- one manual EdgeOne production deployment from the same reviewed `main` SHA;
- the EdgeOne project/deployment record and preview;
- ICP footer isolation, SPA routes, security headers, and the source SHA.

Keep `EDGEONE_CN_PUBLIC_VERIFY_ENABLED=false` during this inspection. Accept
only a deployment-history entry whose source SHA and manifest match the
independent GitHub evidence; protected `main` and required CI remain the
ongoing deployment gate.

### 6. Cut over `praxys.cn` inside Tencent

Keep the `.cn` zone on DNSPod/Tencent. Lower TTLs before the window, then add
the exact CNAME/verification records provided for both custom domains by
EdgeOne. Wait for:

- domain ownership verified;
- managed HTTPS active for both names;
- the expected `praxys-cn` deployment selected as production;
- the ICP footer and source SHA visible through the custom names.

After both hosts are public and accepted, set:

```bash
gh variable set EDGEONE_CN_PUBLIC_VERIFY_ENABLED \
  --repo praxys-run/praxys \
  --body true
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
    -X OPTIONS https://api.praxys.run/api/today \
    -H "Origin: ${origin}" \
    -H 'Access-Control-Request-Method: GET' \
    -H 'Access-Control-Request-Headers: authorization,content-type,x-praxys-client,x-praxys-client-version,x-praxys-source-sha,x-praxys-notice-version,x-praxys-policy-digest,x-praxys-api-contract' \
    | grep -Ei '^(access-control-allow-origin|access-control-allow-headers):'
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
results, monitoring readiness, `CN_PRIVACY_FLOOR_SHA`, Miniapp `2026.08.2`
with its full source SHA and `wechat:robot-1:2026.08.2` provider locator, the human-accepted
[Operations Decision Record](./odr-2026-08-26-cn-provider-topology.md), and the
final operator-approved
`PIPIA-CN-2026-08-25-01`. Preserve the aggregated record in the approved
operations evidence store; GitHub artifacts alone expire after 90 days.

## Rollback / Recovery

### EdgeOne deployment

Use EdgeOne deployment-history rollback only when the prior deployment is an
exact current registry-authorized release whose full source SHA, provider ID,
and manifest evidence are retained. Floor ancestry is still required but is
not authorization. Select that known-good deployment immediately, then
revert the bad change through protected `main` so source and production
converge. Verify the known-good SHA and its current client-boundary headers
before resuming merges. Never select a notice-incapable artifact even as a
temporary rollback. Until public cutover, leave custom domains on their prior
records. If source access must stop, revoke the EdgeOne GitHub App repository
grant.

### Backend or Miniapp privacy floor

Backend, frontend, and Miniapp release workflows reject any candidate older
than `CN_PRIVACY_FLOOR_SHA` or outside protected-`main` provenance. Miniapp
rollback may select only an exact current registry-authorized provider
release with its full source SHA and retained evidence. CalVer `2026.08.2` or
newer is necessary metadata, not authorization. If
no compliant revision is healthy, set `PRAXYS_DISABLE_CN_PROCESSING=true` and
disable the affected `.cn` routing while preserving rights routes; stop the
shared API only if the narrower control is insufficient and separately
authorized. Restore service only with a forward fix or an exact registry-authorized
revision. If none exists, keep China processing and the affected route disabled;
do not reconstruct or prune registry records during an incident.

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
- [`odr-2026-08-26-cn-provider-topology.md`](./odr-2026-08-26-cn-provider-topology.md)
- [`cn-personal-information-impact-assessment.md`](./cn-personal-information-impact-assessment.md)
- [`search-discovery.md`](./search-discovery.md)
- `.github/workflows/deploy-frontend-appservice.yml`
- `web/edgeone.json`
- `web/scripts/stamp-china-compliance.mjs`

---
_Last reviewed: 2026-08-27 · Owner: @dddtc2005_
