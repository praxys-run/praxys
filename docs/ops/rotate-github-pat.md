# Rotate the feedback GitHub PAT (`PRAXYS_GITHUB_TOKEN`)

> **Summary:** Replace the expiring (or compromised) fine-grained PAT that lets
> the backend auto-file feedback as GitHub issues — with no impact to the rest of
> the app.
> **Use when:** the PAT is near expiry; has expired (feedback issues stop filing,
> rows stick at `failed`/`needs_review`); or you're rotating on suspicion of
> compromise.

## Background

- `PRAXYS_GITHUB_TOKEN` is a **fine-grained PAT** with *Issues: write* on
  `dddtc2005/praxys`, consumed by `api/github_issues.py`.
- It lives as the GitHub Actions **secret** `PRAXYS_GITHUB_TOKEN` and is pushed to
  the backend App Service on each deploy (`deploy-backend.yml`). See
  [config-and-secrets.md](./config-and-secrets.md).
- On expiry, `create_issue` gets HTTP 401 → returns `None` → triage marks the row
  `failed` (an admin can **Retry** after rotation). **The rest of the app is
  unaffected** — only auto-filing pauses.

## Prerequisites

- GitHub **admin** on `dddtc2005/praxys` (to set the Actions secret) and access to
  the account/bot that owns the token (to mint a new one).
- `gh` CLI authenticated as a repo admin. Optionally `az` CLI (Contributor on
  `rg-trainsight`) for an immediate App Service hotfix.

## Steps

### 1. Mint a new fine-grained PAT  — human step (no API to automate)

GitHub → *Settings → Developer settings → Fine-grained tokens → Generate new token*:
- **Resource owner:** the account/org owning `dddtc2005/praxys` (ideally a bot account).
- **Repository access:** *Only select repositories* → `dddtc2005/praxys`.
- **Permissions:** *Repository → Issues → Read and write*.
- **Expiration:** set a date (e.g. 90 days) and record it (see *Automation* below).

Copy the token (`github_pat_…`).

### 2. Update the Actions secret  — agent-executable

```bash
printf '%s' '<NEW_PAT>' | gh secret set PRAXYS_GITHUB_TOKEN --repo dddtc2005/praxys
```

### 3. Roll it out to App Service  — agent-executable

Trigger a backend deploy so the *sync settings* step pushes the new value:

```bash
gh workflow run deploy-backend.yml --ref main
```

Need it live immediately (before the next deploy)? Set the App Service setting
directly — but still do step 2, because the next deploy re-syncs from the secret:

```bash
az webapp config appsettings set --name trainsight-app --resource-group rg-trainsight \
  --settings PRAXYS_GITHUB_TOKEN='<NEW_PAT>'
```

### 4. Verify  — agent-executable

```bash
# token is valid for the repo? 200 = good
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer <NEW_PAT>" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/dddtc2005/praxys
```

Then in-app: Admin → User Feedback → **Retry** a `failed` row and confirm it
reaches `issue_created` with a real issue link.

### 5. Revoke the old PAT  — agent-executable (if owned by the same account)

GitHub → *Settings → Developer settings → Fine-grained tokens → (old token) → Revoke*.
Don't leave the old token valid after the rollout is verified.

## Rollback / Recovery

A wrong/empty token just leaves auto-filing dormant (rows go `failed`/
`needs_review`) — no user-facing impact. Re-run steps 1–4 with a correct token,
then Retry the affected rows.

## Automation — can an AI agent handle this?

- **Mostly, except minting.** Steps 2–5 are scriptable (`gh`/`az`/`curl`) and an
  agent can execute them **given the new token value**. Step 1 (minting a *user*
  PAT) has no GitHub API — a human or a secrets manager must produce the token.
- **Reminder loop (recommended add):** a scheduled workflow can probe the token
  weekly and, on 401 or near-expiry, open/update an **agent-labeled issue** so a
  coding agent drives steps 2–5 and rotation never silently lapses. Proactive
  expiry needs the expiry date recorded (e.g. a repo variable
  `PRAXYS_GITHUB_TOKEN_EXPIRES`); failure detection (401) needs nothing extra.
- **Eliminate rotation entirely (best — now supported):** use a **GitHub App**
  instead of a PAT. The backend mints short-lived *installation tokens*
  automatically (`api/github_issues.py`), so there is nothing to rotate. Set it
  up once via [setup-github-app.md](./setup-github-app.md). (Only the app's
  private key rotates, and rarely.)

## Related

- [config-and-secrets.md](./config-and-secrets.md) (rotation table) ·
  [monitoring-and-alerts.md](./monitoring-and-alerts.md)
- `api/github_issues.py` (token consumer) · feedback feature dddtc2005/praxys#328

---
_Last reviewed: 2026-06-30 · Owner: @dddtc2005_
