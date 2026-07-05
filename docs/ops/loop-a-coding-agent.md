# Loop A — hand qualifying bugs to the Copilot coding agent

> **Summary:** How the `agent-ready` label routes a bug to the GitHub Copilot
> coding agent (which drafts a fix PR), and the one-time setup that makes it work.
> **Use when:** Enabling / operating Loop A, or debugging "I labeled an issue
> `agent-ready` but Copilot was never assigned".

## How it works

```
feedback triage (api/feedback_triage.py)  ──adds `agent-ready` for a qualifying bug──┐
a maintainer manually adds `agent-ready`  ───────────────────────────────────────────┤
                                                                                      ▼
                          .github/workflows/assign-copilot.yml  ──assigns──▶  Copilot coding agent
                                                                                      │ opens
                                                                                      ▼
                                                          draft PR ──▶ human review + merge (protected)
```

- **`agent-ready` is the sole trigger.** A bare issue-open never fires. Triage
  auto-adds the label only for a **bug** that is **not** sensitive / `needs_review`
  and has **enough detail** (`_qualifies_for_agent` in `api/feedback_triage.py`).
  Features, `other`, sensitive, and low-detail reports never get it. Because the
  label is gated on the sensitivity decision, it never even lands in a parked
  row's `ai_labels`, so a later admin "approve" cannot auto-assign it either.
- **Backlog escape hatch:** a `backlog` or `later` label makes an issue
  ineligible even if it is a bug — the workflow skips it.
- **Merge is always human.** Autonomy is *drafting* the fix; branch protection
  keeps a human in the loop (see below).

## Prerequisites

- Repo admin (to enable the coding agent, create labels, set branch protection).
- `gh` CLI authenticated (`gh auth status`).

## Steps

### 1. Enable the Copilot coding agent for the repo

Repo (or org) admin: **Settings → Copilot → Coding agent** → enable. Verify it is
assignable — the bot must appear as `copilot-swe-agent`:

```bash
gh api graphql -f query='query($o:String!,$n:String!){
  repository(owner:$o,name:$n){ suggestedActors(capabilities:[CAN_BE_ASSIGNED], first:100){
    nodes{ login } } } }' -F o=dddtc2005 -F n=praxys \
  --jq '.data.repository.suggestedActors.nodes[].login' | grep copilot-swe-agent
```

### 2. Create the labels

```bash
gh label create agent-ready -c 1D76DB -d "Trigger: hand this issue to the Copilot coding agent (Loop A)" -R dddtc2005/praxys
gh label create backlog     -c 5319E7 -d "Deferred; ineligible for auto-assign even if a bug" -R dddtc2005/praxys
```

The workflow also honours an existing `later` label as a backlog synonym; create
it too if your team uses it.

### 3. (Optional) provide an assignment token

The workflow uses the built-in `GITHUB_TOKEN` by default. If an assignment made
by that token does not actually *start* the agent in your org, add a fine-grained
PAT with **Issues: write** on this repo as the secret `COPILOT_ASSIGN_TOKEN`
(`Settings → Secrets and variables → Actions`); the workflow prefers it when set.

### 4. Confirm branch protection on `main`

So the agent can draft but never ship, protect `main`:

- **Require a pull request before merging** with **at least 1 approving review**.
- **Require status checks to pass** — the backend-tests check from **#361**
  (`Run backend pytest on pull requests`). Add it once that workflow has run on a
  PR so the check name is selectable.

```bash
# Inspect current protection (requires admin):
gh api repos/dddtc2005/praxys/branches/main/protection --jq '{reviews:.required_pull_request_reviews, checks:.required_status_checks}'
```

## Verify

- Label a **qualifying bug** `agent-ready` → the `Loop A — assign agent-ready
  issues to Copilot` workflow runs and the issue gets `copilot-swe-agent` as an
  assignee; a draft PR follows shortly.
- Label a **feature**, or a bug also tagged `backlog`/`later` → the workflow run
  is skipped (its `if` condition is false).
- A `needs_review` / sensitive feedback report never carries `agent-ready`, so it
  is never auto-assigned even after an admin approves it.

```bash
gh run list --workflow=assign-copilot.yml -R dddtc2005/praxys --limit 5
```

## Rollback / Recovery

- **Pause Loop A:** disable the workflow (`Actions → Loop A … → ⋯ → Disable`) or
  delete `.github/workflows/assign-copilot.yml`. Triage will still *add* the
  label, but nothing will act on it.
- **Stop triage tagging too:** it is inherent to `api/feedback_triage.py`; to
  suppress, unassign in-flight issues (`gh issue edit <n> --remove-assignee
  copilot-swe-agent`) and remove the `agent-ready` label.
- Copilot was mis-assigned: `gh issue edit <n> --remove-assignee copilot-swe-agent`.

## Related

- Trigger source: `api/feedback_triage.py` (`_qualifies_for_agent`).
- Workflow: `.github/workflows/assign-copilot.yml`.
- Secrets: [config-and-secrets.md](./config-and-secrets.md) (`COPILOT_ASSIGN_TOKEN`).
- Issue-filing setup: [setup-github-app.md](./setup-github-app.md).
- Design: dddtc2005/praxys#362 (Loop A); depends on #361 (backend pytest gate).

---
_Last reviewed: 2026-07-05 · Owner: @dddtc2005_