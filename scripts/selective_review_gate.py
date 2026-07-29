"""Evaluate one GitHub pull request against the selective-review policy."""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.review_policy import (  # noqa: E402
    PullRequestFacts,
    apply_runtime_controls,
    evaluate_selective_review,
)


_POLICY_APPROVAL_MARKER = re.compile(
    r"\(selective-review:[A-Za-z0-9._-]+:[0-9a-f]{40}\)$"
)
_POLICY_REVOCATION_MARKERS = (
    "selective-review-revoked",
    "selective-review-emergency-stop",
)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc)


def _review_order(
    row: dict[str, Any],
    submitted: datetime,
    position: int,
) -> tuple[datetime, int]:
    """Return a stable chronological key for reviews submitted together."""
    raw_id = row.get("id")
    try:
        review_id = int(raw_id)
    except (TypeError, ValueError):
        review_id = position
    return submitted, review_id


def _request_json(path: str) -> tuple[Any, dict[str, str]]:
    token = os.environ["GH_TOKEN"]
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    request = urllib.request.Request(
        f"{api_url}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "praxys-selective-review",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response), dict(response.headers.items())


def _paged(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page = 1
    while True:
        separator = "&" if "?" in path else "?"
        payload, _ = _request_json(f"{path}{separator}per_page=100&page={page}")
        batch = list(payload or [])
        rows.extend(item for item in batch if isinstance(item, dict))
        if len(batch) < 100:
            return rows
        page += 1


def _graphql_json(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    token = os.environ["GH_TOKEN"]
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com")
    request = urllib.request.Request(
        f"{api_url}/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "praxys-selective-review",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors"):
        raise RuntimeError("GitHub GraphQL request failed")
    return dict(payload.get("data") or {})


def _resolve_pr_number(event: dict[str, Any]) -> int | None:
    explicit = os.environ.get("INPUT_PR_NUMBER", "").strip()
    if explicit:
        return int(explicit)
    pull = event.get("pull_request")
    if isinstance(pull, dict) and pull.get("number"):
        return int(pull["number"])
    workflow_run = event.get("workflow_run")
    if isinstance(workflow_run, dict):
        pulls = workflow_run.get("pull_requests") or []
        if pulls and pulls[0].get("number"):
            return int(pulls[0]["number"])
    return None


def _ready_head_sha(timeline: list[dict[str, Any]]) -> str | None:
    current_head: str | None = None
    ready_head: str | None = None
    for row in timeline:
        event = row.get("event")
        if event == "committed" and row.get("sha"):
            current_head = str(row["sha"])
        elif event == "head_ref_force_pushed" and row.get("commit_id"):
            current_head = str(row["commit_id"])
        elif event == "ready_for_review":
            ready_head = current_head
    return ready_head


def _changes_requested(
    reviews: list[dict[str, Any]],
    policy_app_login: str = "",
) -> bool:
    latest_by_reviewer: dict[str, tuple[tuple[datetime, int], str]] = {}
    for position, row in enumerate(reviews):
        login = str((row.get("user") or {}).get("login") or "")
        submitted = _parse_time(row.get("submitted_at"))
        if not login or submitted is None:
            continue
        state = str(row.get("state") or "")
        if state in ("COMMENTED", "PENDING"):
            continue
        body = str(row.get("body") or "")
        if (
            login.lower() == policy_app_login.lower()
            and state == "CHANGES_REQUESTED"
            and any(marker in body for marker in _POLICY_REVOCATION_MARKERS)
        ):
            continue
        order = _review_order(row, submitted, position)
        current = latest_by_reviewer.get(login)
        if current is None or order > current[0]:
            latest_by_reviewer[login] = (order, state)
    return any(state == "CHANGES_REQUESTED" for _, state in latest_by_reviewer.values())


def _policy_app_login(slug: str) -> str:
    normalized = slug.strip()
    if not normalized:
        return ""
    return normalized if normalized.lower().endswith("[bot]") else f"{normalized}[bot]"


def _policy_state_present(
    reviews: list[dict[str, Any]],
    *,
    auto_merge_enabled: bool,
) -> bool:
    """Return whether a bot-authored selective-review state still needs cleanup."""
    latest_by_bot: dict[str, tuple[tuple[datetime, int], str, str]] = {}
    for position, row in enumerate(reviews):
        user = row.get("user") or {}
        login = str(user.get("login") or "")
        user_type = str(user.get("type") or "")
        submitted = _parse_time(row.get("submitted_at"))
        state = str(row.get("state") or "")
        body = str(row.get("body") or "").strip()
        is_bot = user_type.lower() == "bot" or login.lower().endswith("[bot]")
        is_approval = bool(_POLICY_APPROVAL_MARKER.search(body))
        is_revocation = any(
            marker in body for marker in _POLICY_REVOCATION_MARKERS
        )
        if (
            not login
            or not is_bot
            or submitted is None
            or state not in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED")
            or not (is_approval or is_revocation)
        ):
            continue
        order = _review_order(row, submitted, position)
        current = latest_by_bot.get(login.lower())
        if current is None or order > current[0]:
            latest_by_bot[login.lower()] = (
                order,
                state,
                "approval" if is_approval else "revocation",
            )

    active_approval = any(
        state == "APPROVED" and marker_type == "approval"
        for _, state, marker_type in latest_by_bot.values()
    )
    return active_approval or (auto_merge_enabled and bool(latest_by_bot))


def _check_states(
    repository: str,
    head_sha: str,
) -> dict[str, str]:
    check_payload, _ = _request_json(
        f"/repos/{repository}/commits/{head_sha}/check-runs?per_page=100"
    )
    states: dict[str, tuple[datetime, str]] = {}
    for row in (check_payload or {}).get("check_runs", []):
        name = str(row.get("name") or "")
        timestamp = _parse_time(row.get("completed_at") or row.get("started_at"))
        if not name or timestamp is None:
            continue
        conclusion = str(row.get("conclusion") or row.get("status") or "").lower()
        current = states.get(name)
        if current is None or timestamp > current[0]:
            states[name] = (timestamp, conclusion)

    status_payload, _ = _request_json(
        f"/repos/{repository}/commits/{head_sha}/status"
    )
    for row in (status_payload or {}).get("statuses", []):
        name = str(row.get("context") or "")
        timestamp = _parse_time(row.get("updated_at") or row.get("created_at"))
        if not name or timestamp is None:
            continue
        current = states.get(name)
        if current is None or timestamp > current[0]:
            states[name] = (timestamp, str(row.get("state") or "").lower())
    return {name: state for name, (_, state) in states.items()}


def _repository_review_guardrails(
    repository: str,
    base_branch: str,
    required_checks: tuple[str, ...],
) -> tuple[bool, int, bool, bool]:
    repository_payload, _ = _request_json(f"/repos/{repository}")
    branch_rules, _ = _request_json(
        f"/repos/{repository}/rules/branches/{base_branch}"
    )
    pull_request_rules = [
        dict(row.get("parameters") or {})
        for row in (branch_rules or [])
        if row.get("type") == "pull_request"
    ]
    approval_count = max(
        (
            int(parameters.get("required_approving_review_count") or 0)
            for parameters in pull_request_rules
        ),
        default=0,
    )
    approval_invalidated_on_push = any(
        bool(parameters.get("dismiss_stale_reviews_on_push"))
        or bool(parameters.get("require_last_push_approval"))
        for parameters in pull_request_rules
    )
    status_check_rules = [
        dict(row.get("parameters") or {})
        for row in (branch_rules or [])
        if row.get("type") == "required_status_checks"
    ]
    enforced_contexts = {
        str(check.get("context") or "")
        for parameters in status_check_rules
        for check in parameters.get("required_status_checks", [])
        if isinstance(check, dict)
    }
    required_status_checks_strict = (
        bool(status_check_rules)
        and all(
            bool(parameters.get("strict_required_status_checks_policy"))
            for parameters in status_check_rules
        )
        and set(required_checks).issubset(enforced_contexts)
    )
    return (
        bool(repository_payload.get("allow_auto_merge")),
        approval_count,
        approval_invalidated_on_push,
        required_status_checks_strict,
    )


def _trusted_assignment_matches(
    timeline: list[dict[str, Any]],
    *,
    pr_number: int,
    pr_created_at: datetime,
    trusted_assignment_actors: set[str],
    assignment_assignee_login: str,
    pr_author_login: str,
    pr_api_url: str,
    maximum_assignment_to_pr_minutes: float,
    maximum_pr_cross_reference_minutes: float,
) -> bool:
    assignment_events: list[tuple[datetime, str, str]] = []
    cross_references: list[tuple[datetime, int, str, str]] = []
    for row in timeline:
        created_at = _parse_time(row.get("created_at"))
        if created_at is None:
            continue
        if (
            row.get("event") in ("assigned", "unassigned")
            and str((row.get("assignee") or {}).get("login") or "")
            == assignment_assignee_login
            and created_at <= pr_created_at
        ):
            assignment_events.append(
                (
                    created_at,
                    str(row.get("event") or ""),
                    str((row.get("actor") or {}).get("login") or ""),
                )
            )
        if row.get("event") == "cross-referenced":
            source_issue = (row.get("source") or {}).get("issue") or {}
            if not (source_issue.get("pull_request") or {}).get("url"):
                continue
            source_number = source_issue.get("number")
            if type(source_number) is not int:
                continue
            cross_references.append(
                (
                    created_at,
                    source_number,
                    str((row.get("actor") or {}).get("login") or ""),
                    str((source_issue.get("pull_request") or {}).get("url") or ""),
                )
            )

    latest_assignment_event = max(assignment_events, default=None)
    if latest_assignment_event is None:
        return False
    assigned_at, assignment_event, assignment_actor = latest_assignment_event
    if (
        assignment_event != "assigned"
        or assignment_actor not in trusted_assignment_actors
    ):
        return False
    assignment_age_minutes = (
        pr_created_at - assigned_at
    ).total_seconds() / 60
    if not 0 <= assignment_age_minutes <= maximum_assignment_to_pr_minutes:
        return False

    matching_cross_references = [
        created_at
        for created_at, source_number, actor_login, source_url in cross_references
        if source_number == pr_number
        and actor_login == pr_author_login
        and source_url == pr_api_url
        and created_at >= pr_created_at
        and (created_at - pr_created_at).total_seconds() / 60
        <= maximum_pr_cross_reference_minutes
    ]
    matched_at = min(matching_cross_references, default=None)
    if matched_at is None:
        return False
    return not any(
        source_url != pr_api_url
        and actor_login == pr_author_login
        and assigned_at <= created_at <= matched_at
        for created_at, _source_number, actor_login, source_url in cross_references
    )


def _has_agent_ready_closing_issue(
    repository: str,
    pr_number: int,
    pull: dict[str, Any],
    policy: dict[str, Any],
) -> bool:
    owner, name = repository.split("/", 1)
    data = _graphql_json(
        """
        query($owner: String!, $name: String!, $number: Int!) {
          repository(owner: $owner, name: $name) {
            pullRequest(number: $number) {
              closingIssuesReferences(first: 20) {
                pageInfo { hasNextPage }
                nodes {
                  number
                  state
                  repository { nameWithOwner }
                  labels(first: 100) {
                    pageInfo { hasNextPage }
                    nodes { name }
                  }
                  assignees(first: 100) {
                    pageInfo { hasNextPage }
                    nodes { login }
                  }
                }
              }
            }
          }
        }
        """,
        {"owner": owner, "name": name, "number": pr_number},
    )
    repository_node = dict(data.get("repository") or {})
    pull_request = dict(repository_node.get("pullRequest") or {})
    references = dict(pull_request.get("closingIssuesReferences") or {})
    if (references.get("pageInfo") or {}).get("hasNextPage"):
        return False
    pr_created_at = _parse_time(pull.get("created_at"))
    if pr_created_at is None:
        return False
    trusted_assignment_actors = {
        str(item) for item in policy.get("trusted_assignment_actors", [])
    }
    assignment_assignee_login = str(
        policy.get("assignment_assignee_login") or ""
    )
    disqualifying_labels = {
        str(item) for item in policy.get("disqualifying_issue_labels", [])
    }
    pr_author_login = str((pull.get("user") or {}).get("login") or "")
    for issue in references.get("nodes") or []:
        issue_repository = str(
            ((issue.get("repository") or {}).get("nameWithOwner")) or ""
        )
        labels = {
            str(row.get("name") or "")
            for row in ((issue.get("labels") or {}).get("nodes") or [])
        }
        assignees = {
            str(row.get("login") or "")
            for row in ((issue.get("assignees") or {}).get("nodes") or [])
        }
        if (
            issue_repository == repository
            and issue.get("state") == "OPEN"
            and not (issue.get("labels") or {})
            .get("pageInfo", {})
            .get("hasNextPage")
            and not (issue.get("assignees") or {})
            .get("pageInfo", {})
            .get("hasNextPage")
            and "agent-ready" in labels
            and not labels.intersection(disqualifying_labels)
            and assignment_assignee_login in assignees
        ):
            issue_number = issue.get("number")
            if type(issue_number) is not int:
                continue
            issue_timeline = _paged(
                f"/repos/{repository}/issues/{issue_number}/timeline"
            )
            if _trusted_assignment_matches(
                issue_timeline,
                pr_number=pr_number,
                pr_created_at=pr_created_at,
                trusted_assignment_actors=trusted_assignment_actors,
                assignment_assignee_login=assignment_assignee_login,
                pr_author_login=pr_author_login,
                pr_api_url=str(pull.get("url") or ""),
                maximum_assignment_to_pr_minutes=float(
                    policy.get("maximum_assignment_to_pr_minutes") or 0
                ),
                maximum_pr_cross_reference_minutes=float(
                    policy.get("maximum_pr_cross_reference_minutes") or 0
                ),
            ):
                return True
    return False


def _write_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def _write_summary(lines: list[str]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")


def main() -> int:
    """Collect structured GitHub facts, evaluate policy, and emit action outputs."""
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    pr_number = _resolve_pr_number(event)
    if pr_number is None:
        _write_output("skip", "true")
        _write_output("decision", "review-required")
        _write_output("policy_state_present", "false")
        _write_output("needs_policy_app", "false")
        _write_summary(["## Selective review", "", "No pull request was associated with this run."])
        return 0

    repository = os.environ["GITHUB_REPOSITORY"]
    policy_document = json.loads(
        (ROOT / "config" / "agent-loop-policies.json").read_text(encoding="utf-8")
    )
    policy = policy_document["change"]["selective_review"]
    pull, _ = _request_json(f"/repos/{repository}/pulls/{pr_number}")
    files = _paged(f"/repos/{repository}/pulls/{pr_number}/files")
    timeline = _paged(f"/repos/{repository}/issues/{pr_number}/timeline")
    reviews = _paged(f"/repos/{repository}/pulls/{pr_number}/reviews")
    head_sha = str((pull.get("head") or {}).get("sha") or "")
    base_branch = str((pull.get("base") or {}).get("ref") or "")
    encoded_base_branch = urllib.parse.quote(base_branch, safe="")
    base_ref_payload, _ = _request_json(
        f"/repos/{repository}/git/ref/heads/{encoded_base_branch}"
    )
    base_sha = str((base_ref_payload.get("object") or {}).get("sha") or "")
    reported_changed_files = pull.get("changed_files")
    changed_file_list_complete = (
        type(reported_changed_files) is int
        and len(files) == reported_changed_files
        and len(files) < 3000
    )
    required_checks = tuple(
        str(item) for item in policy.get("required_checks", [])
    )
    merge_gate_status = str(policy.get("merge_gate_status") or "")
    repository_required_checks = (
        required_checks + (merge_gate_status,)
        if merge_gate_status
        else required_checks
    )
    (
        repository_auto_merge_enabled,
        required_approving_review_count,
        approval_invalidated_on_push,
        required_status_checks_strict,
    ) = _repository_review_guardrails(
        repository,
        base_branch,
        repository_required_checks,
    )

    facts = PullRequestFacts(
        author_login=str((pull.get("user") or {}).get("login") or ""),
        base_repository=str(((pull.get("base") or {}).get("repo") or {}).get("full_name") or ""),
        base_ref=base_branch,
        base_sha=base_sha,
        head_repository=str(((pull.get("head") or {}).get("repo") or {}).get("full_name") or ""),
        is_draft=bool(pull.get("draft")),
        changed_files=tuple(
            dict.fromkeys(
                str(path)
                for row in files
                for path in (row.get("filename"), row.get("previous_filename"))
                if path
            )
        ),
        changed_file_list_complete=changed_file_list_complete,
        check_states=_check_states(repository, head_sha),
        head_sha=head_sha,
        ready_head_sha=_ready_head_sha(timeline),
        changes_requested=_changes_requested(
            reviews,
            _policy_app_login(os.environ.get("POLICY_APP_SLUG", "")),
        ),
        agent_ready_issue_linked=_has_agent_ready_closing_issue(
            repository,
            pr_number,
            pull,
            policy,
        ),
        repository_auto_merge_enabled=repository_auto_merge_enabled,
        required_approving_review_count=required_approving_review_count,
        approval_invalidated_on_push=approval_invalidated_on_push,
        required_status_checks_strict=required_status_checks_strict,
    )
    policy_result = evaluate_selective_review(facts, policy)
    enabled = os.environ.get("SELECTIVE_REVIEW_ENABLED", "").lower() == "true"
    kill_switch = os.environ.get("SELECTIVE_REVIEW_KILL_SWITCH", "").lower() == "true"
    runtime_result = apply_runtime_controls(
        policy_result,
        enabled=enabled,
        kill_switch=kill_switch,
    )
    policy_state_present = _policy_state_present(
        reviews,
        auto_merge_enabled=pull.get("auto_merge") is not None,
    )
    needs_policy_app = (
        runtime_result.disposition == "auto-merge-candidate"
        or policy_state_present
    )

    _write_output("skip", "false")
    _write_output("pr_number", str(pr_number))
    _write_output("head_sha", head_sha)
    _write_output("base_ref", base_branch)
    _write_output("base_sha", base_sha)
    _write_output("policy_version", str(policy["version"]))
    _write_output("change_class", policy_result.change_class or "unclassified")
    _write_output("policy_decision", policy_result.disposition)
    _write_output("decision", runtime_result.disposition)
    _write_output("enabled", str(enabled).lower())
    _write_output("kill_switch", str(kill_switch).lower())
    _write_output("policy_state_present", str(policy_state_present).lower())
    _write_output("needs_policy_app", str(needs_policy_app).lower())
    _write_output("reasons", ",".join(runtime_result.reasons))
    _write_summary(
        [
            "## Selective review",
            "",
            f"- PR: `#{pr_number}`",
            f"- Policy: `{policy['version']}`",
            f"- Class: `{policy_result.change_class or 'unclassified'}`",
            f"- Policy disposition: `{policy_result.disposition}`",
            f"- Runtime disposition: `{runtime_result.disposition}`",
            f"- Prior autonomous state: `{str(policy_state_present).lower()}`",
            f"- Policy App required: `{str(needs_policy_app).lower()}`",
            f"- Reasons: `{','.join(runtime_result.reasons) or 'none'}`",
            "",
            "The workflow never bypasses branch protection; qualifying PRs receive an "
            "independent App approval and normal squash auto-merge.",
        ]
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as exc:
        print(f"GitHub API request failed: HTTP {exc.code} {exc.reason}", file=sys.stderr)
        raise
