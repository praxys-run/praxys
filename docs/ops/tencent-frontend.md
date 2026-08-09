# Tencent Lighthouse frontend

> **Summary:** Provision the mainland-China Nginx origin and connect it to the
> shared frontend deployment workflow.
> **Use when:** Creating, replacing, deploying, or rolling back the Tencent
> Lighthouse static frontend.

## Prerequisites

- Tencent Lighthouse in a mainland-China region, Ubuntu 24.04 LTS, public IP,
  and non-zero bandwidth. Keep the subscription eligible for the ICP filing.
- SSH access from an operator workstation with `sudo`.
- Organization admin access to Actions runner groups and repository variables.
- The ICP filing must be approved before serving the public mainland hostname.

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

### 2. Install the repository Nginx configuration

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
loads.

This bootstrap exposes HTTP only for local verification and the first CI
deployment. Do not route public production traffic to it yet. Before the
EdgeOne cutover, provision a certificate-valid origin hostname and an Nginx
443 listener, then configure EdgeOne for HTTPS origin pull. The exact
certificate flow depends on the approved ICP/DNS arrangement and must be
verified on the provisioned site rather than guessed in this pre-provisioning
runbook.

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
3. Lets the restricted Lighthouse Runner download the static package.
4. Extracts it to a run-addressed release stamped with the source commit SHA.
5. Atomically changes `/var/www/praxys/current`.
6. Keeps the five newest releases and verifies `/healthz`.

The Tencent lane runs only for `main`. A `web-*` tag can still deploy Azure,
but cannot use the production Runner because its Runner Group is pinned to the
workflow on `refs/heads/main`.

## Verify

On the server:

```bash
readlink -f /var/www/praxys/current
cat /var/www/praxys/current/deployed_sha.txt
curl -sS -H 'Host: www.praxys.run' http://127.0.0.1/healthz
curl -sSI -H 'Accept-Encoding: gzip' \
  -H 'Host: www.praxys.run' \
  http://127.0.0.1/assets/<current-hashed-javascript> \
  | grep -i '^Content-Encoding: gzip'
```

The SHA must match the workflow commit, and the JavaScript response must include
`Content-Encoding: gzip`. After EdgeOne and DNS are configured, verify the
public response and cache headers:

```bash
curl -I https://www.praxys.run/
curl -I https://www.praxys.run/assets/<current-hashed-asset>
```

The shell must revalidate; hashed assets must be immutable.

## Rollback / Recovery

To roll back only the Lighthouse frontend:

```bash
cd /var/www/praxys
ls -1t releases
ln -sfn "/var/www/praxys/releases/<GOOD_RELEASE_ID>" current.next
mv -Tf current.next current
curl -sS -H 'Host: www.praxys.run' http://127.0.0.1/healthz
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
_Last reviewed: 2026-08-09 · Owner: @dddtc2005_
