# Tencent Lighthouse frontend

> **Summary:** Provision the mainland-China Nginx origin and connect it to the
> shared frontend deployment workflow.
> **Use when:** Creating, replacing, deploying, or rolling back the Tencent
> Lighthouse static frontend.

## Prerequisites

- Tencent Lighthouse in a mainland-China region, Ubuntu 24.04 LTS, public IP,
  and non-zero bandwidth. Keep the subscription eligible for the ICP filing.
- SSH access from an operator workstation with `sudo`.
- Repository admin access to Actions secrets and variables.
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
sudo install -d -o praxys-deploy -g praxys-deploy -m 0700 \
  /home/praxys-deploy/.ssh
sudo touch /home/praxys-deploy/.ssh/authorized_keys
sudo chown praxys-deploy:praxys-deploy \
  /home/praxys-deploy/.ssh/authorized_keys
sudo chmod 0600 /home/praxys-deploy/.ssh/authorized_keys
```

Generate a dedicated key on the operator workstation:

```bash
ssh-keygen -t ed25519 -f praxys-tencent-deploy \
  -C "praxys GitHub Actions Tencent deploy"
```

Append `praxys-tencent-deploy.pub` to
`/home/praxys-deploy/.ssh/authorized_keys`. Disable SSH password login and root
login after verifying key authentication in a second terminal.

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

### 3. Create the GitHub Actions configuration

Repository variables:

| Variable | Value |
|---|---|
| `TENCENT_LIGHTHOUSE_DEPLOY_ENABLED` | Leave unset until bootstrap is complete; then set `true`. |
| `TENCENT_LIGHTHOUSE_HOST` | Lighthouse public IP or stable SSH hostname. |
| `TENCENT_LIGHTHOUSE_USER` | `praxys-deploy` |
| `TENCENT_LIGHTHOUSE_SSH_PORT` | SSH port, normally `22`. |

Repository secrets:

| Secret | Value |
|---|---|
| `TENCENT_LIGHTHOUSE_SSH_PRIVATE_KEY` | Entire contents of the dedicated private key. |
| `TENCENT_LIGHTHOUSE_SSH_KNOWN_HOSTS` | Pinned `known_hosts` line for the Lighthouse host. |

Create the host-key value from a trusted workstation:

```bash
export LIGHTHOUSE_SSH_PORT=22
ssh-keyscan -H -p "${LIGHTHOUSE_SSH_PORT}" <LIGHTHOUSE_IP> \
  > lighthouse_known_hosts
ssh-keygen -lf lighthouse_known_hosts
```

Compare the fingerprint with the server's host key through the Tencent console
or an already trusted SSH session before storing the file contents. Never
replace the pinned key with `StrictHostKeyChecking=no`.

### 4. Enable deployments

Set `TENCENT_LIGHTHOUSE_DEPLOY_ENABLED=true`, then manually run
`deploy-frontend-appservice.yml`. This can be done before public DNS cutover;
the workflow verifies Nginx over loopback on the server. The workflow:

1. Builds the SPA once.
2. Deploys the same package to Azure App Service.
3. Uploads the static package to a run-addressed Lighthouse release stamped
   with the source commit SHA.
4. Atomically changes `/var/www/praxys/current`.
5. Keeps the five newest releases and verifies `/healthz`.

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
without affecting Azure. If the host key changes after a legitimate rebuild,
verify the new fingerprint out of band before rotating
`TENCENT_LIGHTHOUSE_SSH_KNOWN_HOSTS`.

## Related

- [`deploy.md`](./deploy.md) · [`config-and-secrets.md`](./config-and-secrets.md)
- `.github/workflows/deploy-frontend-appservice.yml`
- `deploy/tencent/nginx-praxys.conf`

---
_Last reviewed: 2026-08-07 · Owner: @dddtc2005_
