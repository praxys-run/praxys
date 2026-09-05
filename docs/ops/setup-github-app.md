# Set up the feedback GitHub App (no-rotation issue filing)

> **Summary:** Configure the GitHub App that lets the backend file feedback as
> public GitHub issues through the consent-bound durable outbox. It mints
> short-lived installation tokens on demand, so there is no token to rotate.
> **Use when:** Standing up feedback → GitHub issue filing. The App is the only
> auth path; without it, feedback is still captured privately and publication
> reports unavailable.

## Why a GitHub App

A **GitHub App** issues ~1h *installation tokens* that the backend mints + caches
automatically (`api/github_issues.py`), so there is **nothing to rotate** — unlike
a long-lived personal access token. This is the sole auth path for feedback issue
filing.

## Inputs an agent needs

Gather these before step 3 — an agent can't derive them:
- **App ID** — the app's settings page (from step 1).
- **Installation ID** — the number at the end of the install URL
  `…/installations/<ID>` (step 2). A normal `gh`/PAT token can't read it via the API.
- **Private key** — the `.pem` downloaded in step 1 (its path on the operator's machine).

## Prerequisite — running backend build

Steps 1–3 (create / install / store config) can run before release. Publication
must remain ineffective until the v2 outbox migration, current legal bundle,
client parity, independent verification, protected enable approval, and live
readback all bind to the same released head.

## Steps

### 1. Create the App  — human (GitHub UI)

GitHub → *Settings → Developer settings → GitHub Apps → New GitHub App*:
- **Name:** e.g. `praxys-feedback`.
- **Homepage URL:** `https://www.praxys.run` (anything valid).
- **Webhook:** uncheck *Active* (we don't receive webhooks).
- **Permissions → Repository → Issues:** **Read and write**.
- **Permissions → Repository → Pull requests:** **Read-only**. This is used only
  to read numeric/state metadata for PRs that close a feedback issue; the backend
  never requests PR text, comments, commits, reviews, or authors.
- GitHub grants **Metadata: read** implicitly. Do not grant Contents, Actions,
  Administration, organization write, or webhook permissions.
- **Where can this App be installed:** *Only on this account*.
- Create, then note the **App ID**.
- *Generate a private key* → downloads a `.pem`. Keep it secret.

For an existing installation, adding Pull requests permission creates a pending
permission update. An organization owner must approve it from the app's
installation settings (or reinstall the app) before closing-PR outcomes appear.
Until approval, issue close/reopen sync continues through the state-only
fallback. Re-run the token-grant check below to verify `pull_requests: read`.

### 2. Install it on the repo  — human

App → *Install App* → install on `praxys-run/praxys`, *Only select
repositories* → that exact repo. After installing, the browser URL ends in
`…/installations/<INSTALLATION_ID>` — **that number is the Installation ID.**

> Heads up: a normal `gh` / PAT token **cannot** read this via the API
> (`gh api /repos/<owner>/<repo>/installation` requires the app's own JWT, not a
> user token). The install URL is the reliable source.

### 3. Store the config  — agent-executable

The private key must be stored **single-line with `\n` escapes** (App Service
settings don't keep multi-line cleanly; the backend restores the newlines).

```bash
# App ID + Installation ID are non-secret → Actions variables
gh variable set PRAXYS_GITHUB_APP_ID --repo praxys-run/praxys --body '<APP_ID>'
gh variable set PRAXYS_GITHUB_APP_INSTALLATION_ID --repo praxys-run/praxys --body '<INSTALLATION_ID>'
gh variable set PRAXYS_FEEDBACK_GITHUB_REPO --repo praxys-run/praxys --body 'praxys-run/praxys'
gh variable set PRAXYS_ENABLE_FEEDBACK_PUBLICATION --repo praxys-run/praxys --body 'false'

# Private key → Actions secret, flattened to one line with literal \n
KEY_ONELINE=$(awk 'BEGIN{ORS="\\n"}{print}' path/to/private-key.pem)
printf '%s' "$KEY_ONELINE" | gh secret set PRAXYS_GITHUB_APP_PRIVATE_KEY --repo praxys-run/praxys
```

Do not store the emergency stop as a GitHub variable. The ordinary backend
workflow reads and validates `PRAXYS_DISABLE_FEEDBACK_PUBLICATION` but never
writes it, so a concurrent incident stop cannot be cleared by deployment.

### 4. Roll out — separately approved release operation

```bash
gh workflow run deploy-backend.yml --ref main
```

The deploy first quiesces the positive flag, pushes the reviewed repo metadata
and secret, verifies the exact new API source SHA, and only then restores the
reviewed positive value. The protected emergency stop remains read-only. This
command is release documentation, not authorization to deploy.

## Verify

**Before deploy (optional, fast):** confirm the credentials are right without
shipping anything — sign the app JWT, mint an installation token, and check the
grant. A `201` with `"issues": "write"` and `"pull_requests": "read"` means
filing and outcome reconciliation will work:

```bash
# needs python + cryptography/PyJWT; or do the JWT+POST by hand
python - <<'PY'
import jwt, time, httpx, pathlib
app_id, inst = "<APP_ID>", "<INSTALLATION_ID>"
key = pathlib.Path("<path/to/key.pem>").read_text()
j = jwt.encode({"iat": int(time.time())-60, "exp": int(time.time())+540, "iss": app_id}, key, algorithm="RS256")
r = httpx.post(f"https://api.github.com/app/installations/{inst}/access_tokens",
               headers={"Authorization": f"Bearer {j}", "Accept": "application/vnd.github+json"})
print(r.status_code, r.json().get("permissions"), r.json().get("repository_selection"))
PY
```

**After an independently approved deploy:** first read back the exact repo,
positive switch, emergency stop, credential presence, and App grants. Then run
one separately approved synthetic v2 canary and confirm one opaque marker maps
to one allowlisted issue URL whose `performed_via_github_app.id` matches the
configured App ID. Missing or mismatched provenance must remain unknown rather
than being adopted. A repository test, config sync, or ordinary user submission
is not a canary and cannot prove recovery. Never replay a v1 or old feedback row.

## Rollback / Recovery

Set and read back `PRAXYS_DISABLE_FEEDBACK_PUBLICATION=true`. Confirm effective
publication is false and new claims stop; retain every outbox and attempt row so
unknown outcomes can still be reconciled. Do not make an unknown attempt
pending, delete evidence, or replay old feedback. The App can then be
uninstalled without affecting private feedback capture.

## Related

- [config-and-secrets.md](./config-and-secrets.md) · [admin-tasks.md](./admin-tasks.md) · `api/github_issues.py`
- Feedback feature: praxys-run/praxys#328

---
_Last reviewed: 2026-09-04 · Owner: @dddtc2005_
