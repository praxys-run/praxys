# Tencent Lighthouse frontend

> **Summary:** Provision the mainland-China Nginx origin and connect it to the
> shared frontend deployment workflow for `praxys.cn` and `www.praxys.cn`.
> **Use when:** Creating, replacing, deploying, or rolling back the Tencent
> Lighthouse static frontend.

## Filed service

- Public hosts: `praxys.cn` and `www.praxys.cn`.
- ICP service filing number: `沪ICP备2025109616号-2`.
- Required destination: `https://beian.miit.gov.cn/`.
- The `praxys.run` frontend, served through non-mainland EdgeOne from its Azure
  origin, does not display this filing number.

`praxys.cn` resolves directly to the Lighthouse public IP and does not consume a
second EdgeOne site. `praxys.run` remains on its existing EdgeOne site, whose
acceleration region is the global availability zone excluding the Chinese
mainland. That non-mainland site may return an HTTP `302` for mainland visitors,
redirecting them to `https://praxys.cn` while preserving path and query string.
Do not add `praxys.cn` as a second site to the single-site free EdgeOne plan.

The deploy workflow builds the SPA once, copies `web/dist` to a Tencent-only
staging directory, and injects the filing footer into every generated HTML
route document (`index.html`) before packaging that copy. Standalone capture
templates such as `og-card.html` remain unchanged. Never stamp `web/dist` in
place: doing so would leak the mainland-China disclosure into the Azure artifact.

## Prerequisites

- Tencent Lighthouse in a mainland-China region, Ubuntu 24.04 LTS, public IP,
  and non-zero bandwidth. Keep the subscription eligible for the ICP filing.
- SSH access from an operator workstation with `sudo`.
- Organization admin access to Actions runner groups and repository variables.
- The approved ICP record must continue to cover both public hosts.

The Lighthouse host serves only the immutable output of `web/dist`. The API,
database, sync scheduler, credentials, and AI integrations remain on Azure.

## Steps

### 1. Bootstrap Nginx and the deploy account

Run on the Lighthouse instance:

```bash
sudo apt-get update
sudo apt-get install -y nginx curl
sudo adduser --disabled-password --gecos "" praxys-deploy
sudo install -d -o praxys-deploy -g www-data -m 0755 \
  /var/www/praxys /var/www/praxys/releases
```

The account runs the deployment Runner and owns release files. Do not grant it
`sudo`, a password, or an SSH authorized key. Keep operator SSH access on a
separate administrative account, restricted to known operator IPs.

### 2. Install TLS material and the repository Nginx configuration

Obtain a certificate covering both `praxys.cn` and `www.praxys.cn` before
changing their A records. Use DNS validation so certificate issuance does not
require exposing an HTTP-only public site. Install the reviewed certificate
files at the paths owned by the checked-in Nginx configuration:

```bash
sudo install -d -o root -g www-data -m 0750 /etc/praxys/tls
sudo install -o root -g www-data -m 0644 <FULLCHAIN_FILE> \
  /etc/praxys/tls/fullchain.pem
sudo install -o root -g www-data -m 0640 <PRIVATE_KEY_FILE> \
  /etc/praxys/tls/privkey.pem
```

Configure provider-supported renewal or rotation before launch. A renewed
certificate must replace these two files atomically, pass `nginx -t`, and be
followed by `systemctl reload nginx`.

From the repository root:

```bash
scp deploy/tencent/nginx-praxys.conf <operator>@<LIGHTHOUSE_IP>:/tmp/praxys.conf
ssh <operator>@<LIGHTHOUSE_IP>
sudo install -m 0644 /tmp/praxys.conf /etc/nginx/sites-available/praxys
sudo ln -sfn /etc/nginx/sites-available/praxys /etc/nginx/sites-enabled/praxys
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

The config mirrors `frontend_server/main.py`: hashed Vite assets are immutable
for one year, ordinary assets cache for one day, SPA routes fall back to
`index.html`, and the shell revalidates on every visit. Nginx also compresses
compressible JavaScript, CSS, JSON, XML, SVG, and text responses; keep this
enabled because Lighthouse egress bandwidth otherwise dominates mainland cold
loads. HTTP requests for the two filed names redirect to HTTPS; unknown HTTP
and HTTPS hosts receive Nginx's closed `444` response.

Do not route public production traffic until certificate installation,
`nginx -t`, HTTPS loopback verification, and the unknown-host rejection check
all pass. The public `.cn` hosts terminate TLS on Lighthouse; there is no
EdgeOne origin-pull layer for them.

### 2a. Add DNS and HTTPS

Only after the TLS configuration above is active, point both public hosts
directly at the Lighthouse public IP in DNSPod:

```text
@    A    <LIGHTHOUSE_PUBLIC_IP>
www  A    <LIGHTHOUSE_PUBLIC_IP>
```

Allow inbound TCP 80 and 443 in the Lighthouse firewall. Keep SSH restricted to
the operator allowlist; no other public port is required.

After both records resolve, verify the certificate names and expiry:

```bash
openssl s_client -connect praxys.cn:443 -servername praxys.cn </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates -ext subjectAltName
curl -fsSI https://praxys.cn/
curl -fsSI https://www.praxys.cn/
```

Do not point either filed host at Azure or the non-mainland `praxys.run`
EdgeOne site.

### 2b. Allow the CN frontend to call the API

Production API CORS is owned by Azure App Service rather than FastAPI. Add both
CN origins before enabling public traffic:

```bash
az webapp cors add \
  --name trainsight-app \
  --resource-group rg-trainsight \
  --allowed-origins \
    "https://praxys.cn" \
    "https://www.praxys.cn"

az webapp cors show \
  --name trainsight-app \
  --resource-group rg-trainsight
```

Both origins must appear in `allowedOrigins`. The frontend already sends its
actual `window.location.origin` through the Strava connection flow, so no
separate Strava frontend-origin setting is required.

### 3. Create the restricted Runner group

This repository is public. Never register a repository-level self-hosted Runner
on the production host: a pull-request workflow could otherwise target it.

Under the `praxys-run` organization, create the `praxys-production` Runner
group with:

- Repository access: selected repository `praxys-run/praxys`.
- Public repositories: allowed.
- Workflow access: selected workflow
  `praxys-run/praxys/.github/workflows/deploy-frontend-appservice.yml@refs/heads/main`.

The workflow restriction is load-bearing. Do not broaden it to all workflows or
an unpinned ref.

### 4. Install the self-hosted Runner

From **Organization settings → Actions → Runners**, add a Linux x64 Runner to
the `praxys-production` group. Download the current GitHub Actions Runner,
verify the SHA-256 digest shown by GitHub, and configure it as
`praxys-deploy`:

```bash
sudo install -d -o praxys-deploy -g praxys-deploy -m 0750 \
  /home/praxys-deploy/actions-runner
cd /home/praxys-deploy/actions-runner

sudo -u praxys-deploy ./config.sh --unattended \
  --url https://github.com/praxys-run \
  --token <SHORT_LIVED_ORG_REGISTRATION_TOKEN> \
  --runnergroup praxys-production \
  --name praxys-cn-frontend \
  --labels praxys-cn-frontend \
  --work _work

sudo ./svc.sh install praxys-deploy
sudo ./svc.sh start
sudo ./svc.sh status
```

The service connects outbound to GitHub over HTTPS. It does not require GitHub
Actions to SSH into the host.

### 5. Create the GitHub Actions configuration

Repository variables:

| Variable | Value |
|---|---|
| `TENCENT_LIGHTHOUSE_DEPLOY_ENABLED` | Leave unset until Nginx and the restricted Runner are healthy; then set `true`. |

The Tencent deployment lane requires no repository secret. After migration,
delete the obsolete `TENCENT_LIGHTHOUSE_SSH_PRIVATE_KEY` and
`TENCENT_LIGHTHOUSE_SSH_KNOWN_HOSTS` secrets and the
`TENCENT_LIGHTHOUSE_HOST`, `TENCENT_LIGHTHOUSE_USER`, and
`TENCENT_LIGHTHOUSE_SSH_PORT` variables.

### 6. Enable deployments

Set `TENCENT_LIGHTHOUSE_DEPLOY_ENABLED=true`, then manually run
`deploy-frontend-appservice.yml`. This can be done before public DNS cutover;
the workflow verifies Nginx over loopback on the server. The workflow:

1. Builds the SPA once.
2. Deploys the same package to Azure App Service.
3. Copies the build to a Tencent-only staging directory and injects
   `沪ICP备2025109616号-2`, linked to the MIIT filing homepage, into every HTML
   route document.
4. Packages the reviewed Nginx configuration beside the static archive.
5. Lets the restricted Lighthouse Runner download the package and fails closed
   unless the installed Nginx file exactly matches the reviewed copy.
6. Extracts it to a run-addressed release stamped with the source commit SHA.
7. Atomically changes `/var/www/praxys/current`.
8. Keeps the five newest releases and verifies HTTPS for both `.cn` hosts,
   `/healthz`, the filing footer, and unknown-host rejection.

The Tencent lane runs only for `main`. A `web-*` tag can still deploy Azure,
but cannot use the production Runner because its Runner Group is pinned to the
workflow on `refs/heads/main`.

## Configure the mainland handoff

The redirect belongs to the existing `praxys.run` EdgeOne site, not DNS and not
the `.cn` Lighthouse:

1. Keep the site acceleration region set to **global availability zone
   excluding the Chinese mainland**. `praxys.run` has no ICP filing and must
   never use mainland nodes.
2. In **EdgeOne → praxys.run → Site Acceleration → Rule Engine**, add a rule
   matching mainland-China client geography for the public frontend hosts.
3. Return HTTP `302` to `https://praxys.cn`, preserving the original path and
   query string.
4. Keep the redirect temporary. Do not use `301`/`308`: browsers can cache a
   permanent geographic decision after the user changes region or VPN.
5. Verify authentication and account-link flows on `.cn` before enabling the
   rule. Browser storage is isolated by origin, so an existing `.run` session
   does not automatically transfer to `.cn`.

Rollback is disabling this one EdgeOne rule; it does not change either origin
or DNS zone.

## Verify

On the server:

```bash
readlink -f /var/www/praxys/current
cat /var/www/praxys/current/deployed_sha.txt
for host in praxys.cn www.praxys.cn; do
  test "$(
    curl -sS --resolve "${host}:80:127.0.0.1" \
      -o /dev/null -w '%{http_code} %{redirect_url}' "http://${host}/"
  )" = "308 https://${host}/"
  curl -sS --resolve "${host}:443:127.0.0.1" "https://${host}/healthz"
  curl -sS --resolve "${host}:443:127.0.0.1" "https://${host}/" \
    | grep -F '沪ICP备2025109616号-2'
  curl -sSI -H 'Accept-Encoding: gzip' \
    --resolve "${host}:443:127.0.0.1" \
    "https://${host}/assets/<current-hashed-javascript>" \
    | grep -i '^Content-Encoding: gzip'
done
test "$(
  curl -k -sS --resolve "unknown.invalid:443:127.0.0.1" \
    -o /dev/null -w '%{http_code}' https://unknown.invalid/ || true
)" = "000"
```

The SHA must match the workflow commit, and the JavaScript response must include
`Content-Encoding: gzip`. After DNS and HTTPS are configured, verify the public
response and cache headers:

```bash
for host in praxys.cn www.praxys.cn; do
  curl -fsS "https://${host}/" | grep -F '沪ICP备2025109616号-2'
  curl -I "https://${host}/"
  curl -I "https://${host}/assets/<current-hashed-asset>"
done
```

The shell must revalidate; hashed assets must be immutable.

## Keep the filing valid

Both public hosts must remain reachable and resolve directly to the filed
Tencent Lighthouse access path. Before launch and after any DNS, Lighthouse,
certificate, registrant, operator, contact, or website-information change:

```bash
dig +short praxys.cn A
dig +short www.praxys.cn A
curl -fsS https://praxys.cn/ | grep -F '沪ICP备2025109616号-2'
curl -fsS https://www.praxys.cn/ | grep -F '沪ICP备2025109616号-2'
```

Confirm the returned addresses are the Lighthouse public address.
If filed subject or service information changes, complete the corresponding
change filing before treating the production configuration as current.

## Public-security filing follow-up

Complete the public-security filing within 30 days after the website opens.
After approval, make a separate reviewed frontend change that adds the issued
public-security filing icon, exact number, and official link beside the ICP
record. Do not publish a placeholder number or badge.

## Rollback / Recovery

To roll back only the Lighthouse frontend:

```bash
set -euo pipefail
cd /var/www/praxys
ls -1t releases
sudo -u praxys-deploy ln -sfn \
  "/var/www/praxys/releases/<GOOD_RELEASE_ID>" current.next
sudo -u praxys-deploy mv -Tf current.next current
for host in praxys.cn www.praxys.cn; do
  curl --fail --silent --show-error \
    --resolve "${host}:443:127.0.0.1" \
    "https://${host}/healthz"
  curl --fail --silent --show-error \
    --resolve "${host}:443:127.0.0.1" \
    "https://${host}/" \
    | grep -F '沪ICP备2025109616号-2'
done
```

Set `TENCENT_LIGHTHOUSE_DEPLOY_ENABLED=false` to stop future Tencent deploys
without affecting Azure. To stop the Runner itself:

```bash
cd /home/praxys-deploy/actions-runner
sudo ./svc.sh stop
```

Do not move the Runner into the organization default group as a recovery
shortcut. Repair the workflow-restricted `praxys-production` group instead.

## Related

- [`deploy.md`](./deploy.md) · [`config-and-secrets.md`](./config-and-secrets.md)
- `.github/workflows/deploy-frontend-appservice.yml`
- `deploy/tencent/nginx-praxys.conf`

---
_Last reviewed: 2026-08-20 · Owner: @dddtc2005_
