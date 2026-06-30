# Set up the feedback GitHub App (no-rotation issue filing)

> **Summary:** Configure a GitHub App so the backend mints short-lived
> installation tokens on demand — the rotation-free alternative to the feedback
> PAT.
> **Use when:** Standing up feedback → GitHub issue filing for the first time, or
> migrating off the PAT to stop dealing with [rotation](./rotate-github-pat.md).

## Why an App instead of a PAT

A fine-grained PAT is long-lived and expires (manual rotation). A **GitHub App**
issues ~1h *installation tokens* that the backend mints + caches automatically
(`api/github_issues.py`), so there is **nothing to rotate**. When both are
configured the App is preferred; the PAT is the fallback.

## Steps

### 1. Create the App  — human (GitHub UI)

GitHub → *Settings → Developer settings → GitHub Apps → New GitHub App*:
- **Name:** e.g. `praxys-feedback`.
- **Homepage URL:** `https://www.praxys.run` (anything valid).
- **Webhook:** uncheck *Active* (we don't receive webhooks).
- **Permissions → Repository → Issues:** **Read and write**. No other permissions.
- **Where can this App be installed:** *Only on this account*.
- Create, then note the **App ID**.
- *Generate a private key* → downloads a `.pem`. Keep it secret.

### 2. Install it on the repo  — human

App → *Install App* → install on `dddtc2005/praxys` (or your triage repo), *Only
select repositories* → that repo. After installing, the URL is
`…/installations/<INSTALLATION_ID>` — note the **Installation ID** (or fetch it
via the API below).

```bash
# Find the installation id with the app JWT (or just read it from the install URL)
gh api /repos/dddtc2005/praxys/installation --jq '.id'   # needs app-JWT auth; the URL is easier
```

### 3. Store the config  — agent-executable

The private key must be stored **single-line with `\n` escapes** (App Service
settings don't keep multi-line cleanly; the backend restores the newlines).

```bash
# App ID + Installation ID are non-secret → Actions variables
gh variable set PRAXYS_GITHUB_APP_ID --repo dddtc2005/praxys --body '<APP_ID>'
gh variable set PRAXYS_GITHUB_APP_INSTALLATION_ID --repo dddtc2005/praxys --body '<INSTALLATION_ID>'
gh variable set PRAXYS_FEEDBACK_GITHUB_REPO --repo dddtc2005/praxys --body 'dddtc2005/praxys'

# Private key → Actions secret, flattened to one line with literal \n
KEY_ONELINE=$(awk 'BEGIN{ORS="\\n"}{print}' path/to/private-key.pem)
printf '%s' "$KEY_ONELINE" | gh secret set PRAXYS_GITHUB_APP_PRIVATE_KEY --repo dddtc2005/praxys
```

### 4. Roll out  — agent-executable

```bash
gh workflow run deploy-backend.yml --ref main
```

The deploy's *sync settings* step pushes the variables + secret to App Service
(they're optional — see [config-and-secrets.md](./config-and-secrets.md)).

## Verify

Submit a test bug report (or Admin → User Feedback → **Retry** a `failed` row) and
confirm it reaches `issue_created` with a real issue link. The issue is authored
by the App (e.g. `praxys-feedback[bot]`), not a personal account.

## Rollback / Recovery

Remove the three App settings (or just unset them) and the backend falls back to
the PAT, or to admin-only manual promotion if no PAT is set. The App can be
uninstalled from the repo at any time without affecting the rest of the app.

## Related

- [rotate-github-pat.md](./rotate-github-pat.md) (the thing this lets you stop doing)
- [config-and-secrets.md](./config-and-secrets.md) · `api/github_issues.py`
- Feedback feature: dddtc2005/praxys#328

---
_Last reviewed: 2026-06-30 · Owner: @dddtc2005_
