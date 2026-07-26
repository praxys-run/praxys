# Set up the selective-review policy App

> **Summary:** Provision the independent GitHub App that approves qualifying
> low-risk Copilot PRs and enables normal auto-merge without bypassing checks.
> **Use when:** Enabling or rotating Loop A selective review.

## Prerequisites

- Organization-owner access to `praxys-run`.
- Repository admin access to `praxys-run/praxys`.
- `gh auth status` succeeds for the repository.
- A class is not promoted until `python scripts/validate_review_policy.py`
  succeeds with at least five clean, seven-day observations.

## Steps

### 1. Create the independent App

GitHub → **Settings → Developer settings → GitHub Apps → New GitHub App**:

- **Name:** `praxys-review-policy` (or another dedicated policy-only name).
- **Homepage URL:** `https://www.praxys.run`.
- **Webhook:** disabled.
- **Repository permissions → Contents:** **Read and write**. GitHub requires this
  to enable normal pull-request auto-merge.
- **Repository permissions → Pull requests:** **Read and write**. This permits
  the App to submit an approving review.
- No Issues, Actions, Checks, Administration, or Workflow write permission.
- Install only on `praxys-run/praxys`.

Do not reuse the feedback App or the coding-agent identity. The policy App is an
independent merge-gate identity and is not a ruleset bypass actor.

### 2. Store the App identity

Generate a private key from the App settings page, note the App ID, then set:

```bash
gh variable set PRAXYS_REVIEW_POLICY_APP_ID \
  --repo praxys-run/praxys --body "<APP_ID>"

gh secret set PRAXYS_REVIEW_POLICY_APP_PRIVATE_KEY \
  --repo praxys-run/praxys < path/to/praxys-review-policy.pem
```

Delete the downloaded key after the Actions secret is confirmed.

### 3. Provision runtime controls default-off

```bash
gh variable set PRAXYS_SELECTIVE_REVIEW_ENABLED \
  --repo praxys-run/praxys --body "false"
gh variable set PRAXYS_SELECTIVE_REVIEW_KILL_SWITCH \
  --repo praxys-run/praxys --body "false"

# Auto-merge still obeys the ruleset, approvals, and required checks.
gh api -X PATCH repos/praxys-run/praxys -F allow_auto_merge=true
```

Before enabling the runtime, edit **Settings → Rules → Rulesets → default**:

- Require a pull request before merging.
- Require **1 approving review**.
- Enable **Dismiss stale pull request approvals when new commits are pushed**
  (or require approval of the most recent reviewable push).
- Keep squash as the only merge method and `backend-tests` as the required
  check.
- Add both `backend-tests` and `selective-review-policy` to the ruleset's
  **Require status checks to pass** rule and enable **Require branches to be up
  to date before merging**. The policy workflow marks its explicit status
  pending before touching App credentials, so an App-token or evaluation failure
  cannot leave an older autonomous merge armed. The gate reads effective
  rulesets; a legacy-only branch-protection check is not enough for no-review
  merges.
- Do not add the review-policy App as a bypass actor.

Provisioning the App does not approve anything: the committed
`promoted_classes` list starts empty and the runtime enable variable starts
`false`.

### 4. Promote one proven class

1. Add at least five completed observations for the same named class to
   `data/agent_evals/change/review_promotion.json`. PR numbers must be unique.
2. Ensure every observation has successful required checks, no PR-caused
   readiness failure, no correction after ready-for-review, acceptable test
   policy, no revert/reopen, and at least seven observation days.
3. Run `python scripts/validate_review_policy.py` and bind the evidence bucket
   to the printed fingerprint for that policy version, classifier semantics,
   allowed author and base-branch sets, class definition, promotion thresholds,
   sensitive-path list, and required-check list. A changed fingerprint requires
   fresh evidence.
4. Add the class to `promoted_classes` in
   `config/agent-loop-policies.json` through a normal reviewed policy PR.
5. Run:

   ```bash
   python scripts/validate_review_policy.py
   ```

   The required `backend-tests` check runs the same validator, so unsupported
   promotions cannot merge while only an optional workflow is red.

6. After that policy PR merges, enable the runtime:

   ```bash
   gh variable set PRAXYS_SELECTIVE_REVIEW_ENABLED \
     --repo praxys-run/praxys --body "true"
   ```

The coding agent cannot promote itself. The gh-aw tuner can modify only
`config/agent-loop-policy-proposals.json` and opens draft PRs.

## Verify

```bash
gh variable list --repo praxys-run/praxys
gh api repos/praxys-run/praxys --jq '{allow_auto_merge}'
gh api repos/praxys-run/praxys/rules/branches/main \
  --jq '.[] | select(.type == "pull_request") | .parameters'
python scripts/validate_review_policy.py

gh workflow run selective-review.yml \
  --repo praxys-run/praxys \
  -f pr_number=<COPILOT_PR_NUMBER>
```

For an unpromoted or sensitive PR, the Actions summary must say
`review-required` and no App review appears. For an enabled, promoted, same-repo
Copilot PR that closes an `agent-ready` issue, has a stable ready handoff, and
passes `backend-tests`, the App submits one approval and
`gh pr merge --auto --squash` schedules the normal merge.

## Rollback / Recovery

Immediate kill switch:

```bash
gh variable set PRAXYS_SELECTIVE_REVIEW_KILL_SWITCH \
  --repo praxys-run/praxys --body "true"

gh workflow run selective-review-emergency-stop.yml \
  --repo praxys-run/praxys
```

The emergency job refuses to run until the kill-switch variable is true. On
every affected open PR it replaces the policy App's approval with a blocking
`REQUEST_CHANGES` review and disables auto-merge. Confirm the workflow succeeds
before treating the stop as complete. Then open a policy PR removing the
affected class from `promoted_classes` and record the correction, failure,
revert, or reopen in the evidence corpus. Never add the policy App as a ruleset
bypass actor.

If the App key is exposed, generate a replacement key, update
`PRAXYS_REVIEW_POLICY_APP_PRIVATE_KEY`, verify one manual workflow dispatch, then
delete the old key.

## Related

- [change-loop.md](./change-loop.md)
- [config-and-secrets.md](./config-and-secrets.md)
- [`config/agent-loop-policies.json`](../../config/agent-loop-policies.json)
- [`analysis/review_policy.py`](../../analysis/review_policy.py)
