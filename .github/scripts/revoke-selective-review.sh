#!/usr/bin/env bash
set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN is required}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
: "${PR_NUMBER:?PR_NUMBER is required}"
: "${POLICY_APP_LOGIN:?POLICY_APP_LOGIN is required}"

pull_json="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}")"
[[ "$(jq -r '.state' <<< "$pull_json")" == "open" ]] || exit 0

reviews_json="$(
  gh api "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}/reviews?per_page=100" \
    --paginate --slurp
)"
policy_review_count="$(
  jq --arg login "${POLICY_APP_LOGIN,,}" \
    '[.[][] | select(((.user.login // "") | ascii_downcase) == $login) | select((.body // "") | test("\\(selective-review:[A-Za-z0-9._-]+:[0-9a-f]{40}\\)$"))] | length' \
    <<< "$reviews_json"
)"
(( policy_review_count > 0 )) || exit 0

if [[ "$(jq -r '.auto_merge != null' <<< "$pull_json")" == "true" ]]; then
  gh pr merge "$PR_NUMBER" --repo "$GITHUB_REPOSITORY" --disable-auto
fi

current_head="$(jq -r '.head.sha' <<< "$pull_json")"
latest_policy_review_is_blocking="$(
  jq --arg login "${POLICY_APP_LOGIN,,}" --arg head "$current_head" \
    '[.[][] | select(((.user.login // "") | ascii_downcase) == $login) | select((.body // "") | test("selective-review"))] | sort_by(.submitted_at) | last | (.commit_id == $head and .state == "CHANGES_REQUESTED")' \
    <<< "$reviews_json"
)"
if [[ "$latest_policy_review_is_blocking" != "true" ]]; then
  gh api -X POST "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}/reviews" \
    -f event=REQUEST_CHANGES \
    -f commit_id="$current_head" \
    -f body="Selective-review policy no longer qualifies this PR; human review is required. (selective-review-revoked)" \
    >/dev/null
fi

final_pull_json="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}")"
final_reviews_json="$(
  gh api "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}/reviews?per_page=100" \
    --paginate --slurp
)"
final_auto_merge="$(jq -r '.auto_merge != null' <<< "$final_pull_json")"
latest_policy_review_is_blocking="$(
  jq --arg login "${POLICY_APP_LOGIN,,}" --arg head "$current_head" \
    '[.[][] | select(((.user.login // "") | ascii_downcase) == $login) | select((.body // "") | test("selective-review"))] | sort_by(.submitted_at) | last | (.commit_id == $head and .state == "CHANGES_REQUESTED")' \
    <<< "$final_reviews_json"
)"
if [[ "$final_auto_merge" == "true" ||
  "$latest_policy_review_is_blocking" != "true" ]]; then
  echo "::error::Failed to revoke stale selective-review state."
  exit 1
fi
