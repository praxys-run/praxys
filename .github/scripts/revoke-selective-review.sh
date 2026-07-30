#!/usr/bin/env bash
set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN is required}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
: "${PR_NUMBER:?PR_NUMBER is required}"
: "${POLICY_APP_LOGIN:?POLICY_APP_LOGIN is required}"

pull_json="$(gh api "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}")"
pull_state="$(jq -r '.state' <<< "$pull_json")"
pull_merged="$(jq -r '.merged' <<< "$pull_json")"
if [[ "$pull_state" != "open" ]]; then
  if [[ "${REQUIRE_POLICY_STATE:-false}" == "true" &&
    "$pull_merged" == "true" ]]; then
    echo "::error::Pull request #${PR_NUMBER} merged during selective-review cleanup."
    exit 1
  fi
  exit 0
fi

reviews_json="$(
  gh api "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}/reviews?per_page=100" \
    --paginate --slurp
)"
auto_merge_enabled="$(jq -r '.auto_merge != null' <<< "$pull_json")"
latest_policy_reviews="$(
  jq '
    [.[][] |
      select(
        (((.user.type // "") | ascii_downcase) == "bot") or
        (((.user.login // "") | ascii_downcase) | endswith("[bot]"))
      ) |
      select(
        (.body // "") |
        test("\\(selective-review:[A-Za-z0-9._-]+:[0-9a-f]{40}\\)$|\\(selective-review-(revoked|emergency-stop)\\)")
      ) |
      {
        login: ((.user.login // "") | ascii_downcase),
        submitted_at: (.submitted_at // ""),
        id: (.id // 0),
        state: (.state // ""),
        body: (.body // "")
      }
    ] |
    sort_by([.login, .submitted_at, .id]) |
    group_by(.login) |
    map(last)
  ' \
    <<< "$reviews_json"
)"
active_policy_reviews="$(
  jq --argjson auto_merge "$auto_merge_enabled" '
    [.[] |
      select(
        (
          .state == "APPROVED" and
          ((.body // "") | test("\\(selective-review:[A-Za-z0-9._-]+:[0-9a-f]{40}\\)$"))
        ) or
        $auto_merge
      )
    ]
  ' <<< "$latest_policy_reviews"
)"
foreign_owners="$(
  jq -r --arg login "${POLICY_APP_LOGIN,,}" \
    '[.[] | select(.login != $login) | .login] | unique | join(",")' \
    <<< "$active_policy_reviews"
)"
if [[ -n "$foreign_owners" ]]; then
  echo "::error::Active selective-review state is owned by an unexpected bot: ${foreign_owners}."
  exit 1
fi
configured_state_active="$(
  jq -r --arg login "${POLICY_APP_LOGIN,,}" \
    'any(.[]; .login == $login)' <<< "$active_policy_reviews"
)"
if [[ "$configured_state_active" != "true" ]]; then
  if [[ "${REQUIRE_POLICY_STATE:-false}" == "true" &&
    "$auto_merge_enabled" == "true" ]]; then
    echo "::error::Detected policy auto-merge has no verifiable owner."
    exit 1
  fi
  exit 0
fi

if [[ "$auto_merge_enabled" == "true" ]]; then
  gh pr merge "$PR_NUMBER" --repo "$GITHUB_REPOSITORY" --disable-auto
fi

current_head="$(jq -r '.head.sha' <<< "$pull_json")"
latest_policy_review_is_blocking="$(
  jq --arg login "${POLICY_APP_LOGIN,,}" --arg head "$current_head" \
    '[.[][] | select(((.user.login // "") | ascii_downcase) == $login) | select((.body // "") | test("selective-review"))] | sort_by([.submitted_at, (.id // 0)]) | last | (.commit_id == $head and .state == "CHANGES_REQUESTED")' \
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
final_state="$(jq -r '.state' <<< "$final_pull_json")"
final_merged="$(jq -r '.merged' <<< "$final_pull_json")"
if [[ "$final_state" != "open" ]]; then
  if [[ "${REQUIRE_POLICY_STATE:-false}" == "true" &&
    "$final_merged" == "true" ]]; then
    echo "::error::Pull request #${PR_NUMBER} merged during selective-review cleanup."
    exit 1
  fi
  exit 0
fi
final_reviews_json="$(
  gh api "repos/${GITHUB_REPOSITORY}/pulls/${PR_NUMBER}/reviews?per_page=100" \
    --paginate --slurp
)"
final_auto_merge="$(jq -r '.auto_merge != null' <<< "$final_pull_json")"
latest_policy_review_is_blocking="$(
  jq --arg login "${POLICY_APP_LOGIN,,}" --arg head "$current_head" \
    '[.[][] | select(((.user.login // "") | ascii_downcase) == $login) | select((.body // "") | test("selective-review"))] | sort_by([.submitted_at, (.id // 0)]) | last | (.commit_id == $head and .state == "CHANGES_REQUESTED")' \
    <<< "$final_reviews_json"
)"
if [[ "$final_auto_merge" == "true" ||
  "$latest_policy_review_is_blocking" != "true" ]]; then
  echo "::error::Failed to revoke stale selective-review state."
  exit 1
fi
