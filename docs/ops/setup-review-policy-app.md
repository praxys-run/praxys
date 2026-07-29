# Set up the selective-review policy App

> **Summary:** Provision the independent GitHub App that approves qualifying
> low-risk Copilot PRs and enables normal auto-merge without bypassing checks.
> **Use when:** Preparing to enable, smoke-test, or rotate Loop A selective
> review. Ordinary review-required operation does not need this App.

## Prerequisites

- Organization-owner access to `praxys-run`.
- Repository admin access to `praxys-run/praxys`.
- `gh auth status` succeeds for the repository.
- A class is not promoted until `python scripts/validate_review_policy.py`
  succeeds with at least five clean, seven-day observations.

## Selected trust model

Praxys uses the **approval model**: a dedicated GitHub App is the independent
identity that submits `APPROVE` and enables normal squash auto-merge only after
deterministic policy checks. Copilot Code Review, Rubber Duck, and the Praxys
invariant reviewer remain useful evidence, but none is an approval identity or
the merge trust boundary.

The policy is intentionally safe before this App exists. When selective review
is disabled, no class is promoted, or a PR is otherwise review-required, the
workflow succeeds without minting or requiring App credentials. The App becomes
mandatory only for an exact autonomous candidate or cleanup of previously
created policy-App state.

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

Generate a private key from the App settings page, note the App ID and URL slug,
then set:

```bash
gh variable set PRAXYS_REVIEW_POLICY_APP_ID \
  --repo praxys-run/praxys --body "<APP_ID>"

gh variable set PRAXYS_REVIEW_POLICY_APP_SLUG \
  --repo praxys-run/praxys --body "<APP_SLUG>"

gh secret set PRAXYS_REVIEW_POLICY_APP_PRIVATE_KEY \
  --repo praxys-run/praxys < path/to/praxys-review-policy.pem
```

The slug is the App URL component without the `[bot]` suffix. Delete the
downloaded key after the Actions secret is confirmed.

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

Default-off behavior:

| Policy result | App credentials |
|---|---|
| Disabled, unpromoted, sensitive, or otherwise review-required | Not read or required |
| Enabled exact promoted candidate | Required; absence fails closed |
| Prior bot-authored policy approval/auto-merge needs cleanup | Required; absence leaves the required policy status failed |

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
`review-required`, `Policy App required: false`, and no App-token step or review
appears. This remains true when the App variables and secret are completely
absent. For an enabled, promoted, same-repo Copilot PR that closes an
`agent-ready` issue, has a stable ready handoff, and passes `backend-tests`, the
App submits one approval and `gh pr merge --auto --squash` schedules the normal
merge.

## Rollback / Recovery

Immediate kill switch:

```bash
gh variable set PRAXYS_SELECTIVE_REVIEW_KILL_SWITCH \
  --repo praxys-run/praxys --body "true"

gh workflow run selective-review-emergency-stop.yml \
  --repo praxys-run/praxys
```

The emergency job refuses to run until the kill-switch variable is true. It
immediately marks every head with active selective-review state as failed under
the required `selective-review-policy` context, cancels and waits for in-flight
gate runs, then reasserts the barrier on each current head before minting App
credentials. Initially affected PRs remain in the cleanup set, so a merge during
quiescence fails the run instead of disappearing from the open-PR scan. The job
then verifies the exact App identity, rejects state owned by any other bot,
replaces the policy App's approval with a blocking `REQUEST_CHANGES` review, and
disables auto-merge. The ordinary gate also rechecks the kill switch before it
may post success. If credentials or cleanup fail, the failed status remains the
merge barrier. Confirm the workflow succeeds before treating the stop as
complete.
Then open a policy PR removing the affected class from `promoted_classes` and
record the correction, failure, revert, or reopen in the evidence corpus. Never
add the policy App as a ruleset bypass actor.

If stale autonomous state exists but App credentials cannot be minted, the
workflow leaves `selective-review-policy` failed. Once that status is required,
the stale approval or auto-merge display cannot produce a merge. Restore the App
identity, rerun the gate, and then run the emergency stop if broad cleanup is
needed.

If the App key is exposed, generate a replacement key, update
`PRAXYS_REVIEW_POLICY_APP_PRIVATE_KEY`, verify one manual workflow dispatch, then
delete the old key.

## Related

- [change-loop.md](./change-loop.md)
- [config-and-secrets.md](./config-and-secrets.md)
- [`config/agent-loop-policies.json`](../../config/agent-loop-policies.json)
- [`analysis/review_policy.py`](../../analysis/review_policy.py)
