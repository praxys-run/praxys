"""Pure selective-review classification and promotion evaluation."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields as dataclass_fields
from fnmatch import fnmatchcase
from typing import Any, Literal


ReviewDisposition = Literal["review-required", "auto-merge-candidate"]


@dataclass(frozen=True)
class PullRequestFacts:
    """Structured, text-free facts used by the selective-review gate."""

    author_login: str
    base_repository: str
    base_ref: str
    base_sha: str
    head_repository: str
    is_draft: bool
    changed_files: tuple[str, ...]
    changed_file_list_complete: bool
    check_states: dict[str, str]
    head_sha: str
    ready_head_sha: str | None
    changes_requested: bool
    agent_ready_issue_linked: bool
    repository_auto_merge_enabled: bool
    required_approving_review_count: int
    approval_invalidated_on_push: bool
    required_status_checks_strict: bool


@dataclass(frozen=True)
class ReviewDecision:
    """Deterministic review disposition with auditable reasons."""

    disposition: ReviewDisposition
    change_class: str | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PromotionObservation:
    """One completed, privacy-safe PR observation for a named change class."""

    pr_number: int
    completed: bool
    merged: bool
    required_checks_successful: bool | None
    pr_caused_readiness_failure: bool | None
    corrected_after_ready: bool | None
    test_policy: str
    reverted_or_reopened: bool | None
    observation_days: float


@dataclass(frozen=True)
class PromotionAssessment:
    """Evidence-gate result for promoting one narrow change class."""

    eligible: bool
    reasons: tuple[str, ...]
    metrics: dict[str, float | int]


PROMOTION_REQUIREMENT_FLOORS: dict[str, float | int] = {
    "minimum_completed_prs": 5,
    "minimum_observation_days": 7,
    "maximum_correction_rate": 0.0,
    "maximum_pr_caused_failure_rate": 0.0,
    "maximum_revert_or_reopen_rate": 0.0,
    "minimum_test_policy_rate": 1.0,
}


def _matches_any(path: str, patterns: list[str] | tuple[str, ...]) -> bool:
    return any(fnmatchcase(path, pattern) for pattern in patterns)


def class_policy_fingerprint(policy: dict[str, Any], class_name: str) -> str:
    """Hash the class definition and global gates its observations represent."""
    candidate_classes = dict(policy.get("candidate_classes", {}))
    if class_name not in candidate_classes:
        raise KeyError(class_name)
    bound_policy = {
        "allowed_authors": policy.get("allowed_authors", []),
        "allowed_base_branches": policy.get("allowed_base_branches", []),
        "candidate_class": candidate_classes[class_name],
        "classifier_semantics": policy.get("classifier_semantics"),
        "default_decision": policy.get("default_decision"),
        "enforcement_model": policy.get("enforcement_model"),
        "policy_version": policy.get("version"),
        "promotion_requirements": policy.get("promotion_requirements", {}),
        "required_checks": policy.get("required_checks", []),
        "merge_gate_status": policy.get("merge_gate_status"),
        "sensitive_paths": policy.get("sensitive_paths", []),
        "trusted_assignment_actors": policy.get(
            "trusted_assignment_actors",
            [],
        ),
        "assignment_assignee_login": policy.get(
            "assignment_assignee_login"
        ),
        "maximum_assignment_to_pr_minutes": policy.get(
            "maximum_assignment_to_pr_minutes"
        ),
        "maximum_pr_cross_reference_minutes": policy.get(
            "maximum_pr_cross_reference_minutes"
        ),
        "disqualifying_issue_labels": policy.get(
            "disqualifying_issue_labels",
            [],
        ),
    }
    canonical = json.dumps(
        bound_policy,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def classify_change(
    changed_files: tuple[str, ...],
    candidate_classes: dict[str, dict[str, Any]],
) -> str | None:
    """Return the first narrow class whose exclusive path policy matches."""
    if not changed_files:
        return None
    for name, definition in candidate_classes.items():
        allowed = tuple(str(item) for item in definition.get("allowed_paths", []))
        denied = tuple(str(item) for item in definition.get("denied_paths", []))
        if not allowed:
            continue
        if any(_matches_any(path, denied) for path in changed_files):
            continue
        if all(_matches_any(path, allowed) for path in changed_files):
            return name
    return None


def _has_test_change(changed_files: tuple[str, ...]) -> bool:
    patterns = (
        "tests/**",
        "web/src/**/*.test.*",
        "web/src/**/*.spec.*",
        "miniapp/**/*.test.*",
        "miniapp/**/*.spec.*",
    )
    return any(_matches_any(path, patterns) for path in changed_files)


def evaluate_selective_review(
    facts: PullRequestFacts,
    policy: dict[str, Any],
) -> ReviewDecision:
    """Classify a PR and fail closed unless every policy gate passes."""
    candidate_classes = dict(policy.get("candidate_classes", {}))
    change_class = classify_change(facts.changed_files, candidate_classes)
    reasons: list[str] = []

    if facts.author_login not in set(policy.get("allowed_authors", [])):
        reasons.append("author_not_allowed")
    if facts.head_repository != facts.base_repository:
        reasons.append("cross_repository_pull_request")
    if facts.base_ref not in set(policy.get("allowed_base_branches", [])):
        reasons.append("base_branch_not_allowed")
    if facts.is_draft:
        reasons.append("pull_request_is_draft")
    if facts.ready_head_sha is None:
        reasons.append("ready_for_review_handoff_missing")
    elif facts.ready_head_sha != facts.head_sha:
        reasons.append("commit_after_ready_for_review")
    if facts.changes_requested:
        reasons.append("changes_requested")
    if not facts.agent_ready_issue_linked:
        reasons.append("agent_ready_issue_not_linked")
    if not facts.changed_file_list_complete:
        reasons.append("changed_file_list_incomplete")
    if not facts.repository_auto_merge_enabled:
        reasons.append("repository_auto_merge_disabled")
    enforcement_model = str(policy.get("enforcement_model") or "")
    if enforcement_model == "independent-github-app-approval":
        if facts.required_approving_review_count < 1:
            reasons.append("independent_approval_not_required")
        if not facts.approval_invalidated_on_push:
            reasons.append("stale_policy_approval_not_invalidated")
    elif enforcement_model != "deterministic-required-status":
        reasons.append("unsupported_enforcement_model")
    if not facts.required_status_checks_strict:
        reasons.append("required_checks_do_not_require_latest_base")

    sensitive_paths = tuple(str(item) for item in policy.get("sensitive_paths", []))
    if any(_matches_any(path, sensitive_paths) for path in facts.changed_files):
        reasons.append("sensitive_path_changed")

    required_checks = tuple(str(item) for item in policy.get("required_checks", []))
    for check in required_checks:
        if facts.check_states.get(check) != "success":
            reasons.append(f"required_check_not_successful:{check}")

    if change_class is None:
        reasons.append("no_narrow_change_class")
    else:
        promoted = {
            str(item["name"]) if isinstance(item, dict) else str(item)
            for item in policy.get("promoted_classes", [])
        }
        if change_class not in promoted:
            reasons.append(f"class_not_promoted:{change_class}")
        test_policy = str(
            candidate_classes.get(change_class, {}).get("test_policy", "required")
        )
        if test_policy == "required" and not _has_test_change(facts.changed_files):
            reasons.append("required_test_change_missing")
        elif test_policy not in ("required", "not-applicable"):
            reasons.append(f"invalid_test_policy:{test_policy}")

    unique_reasons = tuple(dict.fromkeys(reasons))
    return ReviewDecision(
        disposition=(
            "auto-merge-candidate" if not unique_reasons else "review-required"
        ),
        change_class=change_class,
        reasons=unique_reasons,
    )


def apply_runtime_controls(
    decision: ReviewDecision,
    *,
    enabled: bool,
    kill_switch: bool,
) -> ReviewDecision:
    """Apply default-off runtime controls to a deterministic policy decision."""
    reasons = list(decision.reasons)
    if not enabled:
        reasons.append("selective_review_disabled")
    if kill_switch:
        reasons.append("kill_switch_enabled")
    unique_reasons = tuple(dict.fromkeys(reasons))
    return ReviewDecision(
        disposition=(
            "auto-merge-candidate"
            if decision.disposition == "auto-merge-candidate"
            and enabled
            and not kill_switch
            else "review-required"
        ),
        change_class=decision.change_class,
        reasons=unique_reasons,
    )


def evaluate_promotion(
    observations: list[PromotionObservation],
    requirements: dict[str, Any],
    class_test_policy: str = "required",
) -> PromotionAssessment:
    """Evaluate whether completed observations meet the promotion bar."""
    requirement_errors = _promotion_requirement_errors(requirements)
    if requirement_errors:
        return PromotionAssessment(
            eligible=False,
            reasons=tuple(requirement_errors),
            metrics={
                "completed_prs": 0,
                "correction_rate": 0.0,
                "pr_caused_failure_rate": 0.0,
                "test_policy_rate": 0.0,
                "revert_or_reopen_rate": 0.0,
                "minimum_observation_days": 0.0,
            },
        )

    reasons: list[str] = []
    valid_observations: list[PromotionObservation] = []
    for index, item in enumerate(observations):
        item_errors = _promotion_observation_errors(item)
        if item_errors:
            reasons.append(
                f"invalid_observation:{index}:{','.join(item_errors)}"
            )
        else:
            valid_observations.append(item)

    completed_rows = [item for item in valid_observations if item.completed]
    duplicate_count = len(completed_rows) - len(
        {item.pr_number for item in completed_rows}
    )
    completed_by_pr: dict[int, PromotionObservation] = {}
    for item in completed_rows:
        completed_by_pr.setdefault(item.pr_number, item)
    completed = list(completed_by_pr.values())
    total = len(completed)
    minimum = int(requirements["minimum_completed_prs"])
    minimum_days = float(requirements["minimum_observation_days"])

    if duplicate_count:
        reasons.append(f"duplicate_pr_observations:{duplicate_count}")
    if total < minimum:
        reasons.append(f"insufficient_completed_prs:{total}/{minimum}")

    unknown_checks = sum(
        item.required_checks_successful is not True for item in completed
    )
    readiness_failures = sum(
        item.pr_caused_readiness_failure is not False for item in completed
    )
    corrections = sum(item.corrected_after_ready is not False for item in completed)
    if class_test_policy == "required":
        test_policy_misses = sum(
            item.test_policy != "covered" for item in completed
        )
    elif class_test_policy == "not-applicable":
        test_policy_misses = sum(
            item.test_policy not in ("covered", "not-applicable")
            for item in completed
        )
    else:
        test_policy_misses = total
        reasons.append(f"invalid_class_test_policy:{class_test_policy}")
    reversals = sum(item.reverted_or_reopened is not False for item in completed)
    young_observations = sum(
        item.observation_days < minimum_days for item in completed
    )
    unmerged = sum(not item.merged for item in completed)

    if unmerged:
        reasons.append(f"unmerged_prs:{unmerged}")
    if unknown_checks:
        reasons.append(f"required_checks_not_proven:{unknown_checks}")
    if young_observations:
        reasons.append(f"observation_window_too_short:{young_observations}")

    denominator = total or 1
    correction_rate = corrections / denominator
    failure_rate = readiness_failures / denominator
    test_policy_rate = (total - test_policy_misses) / denominator if total else 0.0
    reversal_rate = reversals / denominator

    if correction_rate > float(requirements["maximum_correction_rate"]):
        reasons.append("correction_rate_above_limit")
    if failure_rate > float(requirements["maximum_pr_caused_failure_rate"]):
        reasons.append("pr_caused_failure_rate_above_limit")
    if test_policy_rate < float(requirements["minimum_test_policy_rate"]):
        reasons.append("test_policy_rate_below_minimum")
    if reversal_rate > float(requirements["maximum_revert_or_reopen_rate"]):
        reasons.append("revert_or_reopen_rate_above_limit")

    return PromotionAssessment(
        eligible=not reasons,
        reasons=tuple(dict.fromkeys(reasons)),
        metrics={
            "completed_prs": total,
            "correction_rate": correction_rate,
            "pr_caused_failure_rate": failure_rate,
            "test_policy_rate": test_policy_rate,
            "revert_or_reopen_rate": reversal_rate,
            "minimum_observation_days": (
                min((item.observation_days for item in completed), default=0.0)
            ),
        },
    )


def _promotion_observation_errors(
    item: PromotionObservation,
) -> list[str]:
    errors: list[str] = []
    if type(item.pr_number) is not int or item.pr_number <= 0:
        errors.append("pr_number")
    for field in ("completed", "merged"):
        if type(getattr(item, field)) is not bool:
            errors.append(field)
    for field in (
        "required_checks_successful",
        "pr_caused_readiness_failure",
        "corrected_after_ready",
        "reverted_or_reopened",
    ):
        value = getattr(item, field)
        if value is not None and type(value) is not bool:
            errors.append(field)
    if not isinstance(item.test_policy, str):
        errors.append("test_policy")
    if (
        type(item.observation_days) not in (int, float)
        or not math.isfinite(float(item.observation_days))
        or float(item.observation_days) < 0
    ):
        errors.append("observation_days")
    return errors


def _promotion_requirement_errors(requirements: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_fields = set(PROMOTION_REQUIREMENT_FLOORS)
    missing_fields = sorted(required_fields - set(requirements))
    if missing_fields:
        return [f"missing_promotion_requirement:{field}" for field in missing_fields]

    minimum_fields = ("minimum_completed_prs", "minimum_observation_days")
    maximum_fields = (
        "maximum_correction_rate",
        "maximum_pr_caused_failure_rate",
        "maximum_revert_or_reopen_rate",
    )
    for field in minimum_fields:
        raw_value = requirements[field]
        if type(raw_value) not in (int, float) or not math.isfinite(
            float(raw_value)
        ):
            errors.append(f"{field}_not_finite_number")
            continue
        if field == "minimum_completed_prs" and (
            type(raw_value) is not int or type(raw_value) is bool
        ):
            errors.append(f"{field}_not_integer")
            continue
        value = float(raw_value)
        floor = float(PROMOTION_REQUIREMENT_FLOORS[field])
        if value < floor:
            errors.append(f"{field}_below_floor:{value:g}/{floor:g}")
    for field in maximum_fields:
        raw_value = requirements[field]
        if type(raw_value) not in (int, float) or not math.isfinite(
            float(raw_value)
        ):
            errors.append(f"{field}_not_finite_number")
            continue
        value = float(raw_value)
        ceiling = float(PROMOTION_REQUIREMENT_FLOORS[field])
        if value > ceiling:
            errors.append(f"{field}_above_ceiling:{value:g}/{ceiling:g}")
        if value < 0:
            errors.append(f"{field}_below_zero:{value:g}")
    raw_test_rate = requirements["minimum_test_policy_rate"]
    if type(raw_test_rate) not in (int, float) or not math.isfinite(
        float(raw_test_rate)
    ):
        errors.append("minimum_test_policy_rate_not_finite_number")
    else:
        test_rate = float(raw_test_rate)
        test_floor = float(
            PROMOTION_REQUIREMENT_FLOORS["minimum_test_policy_rate"]
        )
        if test_rate < test_floor:
            errors.append(
                "minimum_test_policy_rate_below_floor:"
                f"{test_rate:g}/{test_floor:g}"
            )
        if test_rate > 1:
            errors.append(f"minimum_test_policy_rate_above_one:{test_rate:g}")
    return errors


def validate_promoted_classes(
    policy: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, PromotionAssessment]:
    """Return promotion assessments, raising when a promoted class is unsupported."""
    selective = policy["change"]["selective_review"]
    candidate_document = selective.get("candidate_classes")
    if not isinstance(candidate_document, dict):
        raise ValueError("candidate_classes_not_object")
    candidate_classes = set(candidate_document)
    evidence_classes = evidence.get("classes")
    if not isinstance(evidence_classes, dict):
        raise ValueError("evidence_classes_not_object")
    requirements = selective.get("promotion_requirements")
    if not isinstance(requirements, dict):
        raise ValueError("promotion_requirements_not_object")
    promoted_classes = selective.get("promoted_classes")
    if not isinstance(promoted_classes, list):
        raise ValueError("promoted_classes_not_list")
    results: dict[str, PromotionAssessment] = {}
    errors = _promotion_requirement_errors(requirements)
    if not str(selective.get("version") or ""):
        errors.append("policy_version_missing")
    if not str(selective.get("classifier_semantics") or ""):
        errors.append("classifier_semantics_missing")
    if selective.get("default_decision") != "review-required":
        errors.append("default_decision_must_require_review")
    if selective.get("enforcement_model") != "deterministic-required-status":
        errors.append("enforcement_model_must_use_deterministic_status")
    if set(selective.get("allowed_base_branches") or []) != {"main"}:
        errors.append("allowed_base_branches_must_be_main")
    if "Copilot" not in set(selective.get("allowed_authors") or []):
        errors.append("copilot_author_missing")
    if selective.get("assignment_assignee_login") != "Copilot":
        errors.append("assignment_assignee_must_be_copilot")
    if not set(selective.get("trusted_assignment_actors") or []):
        errors.append("trusted_assignment_actors_missing")
    if not {"backlog", "later"}.issubset(
        set(selective.get("disqualifying_issue_labels") or [])
    ):
        errors.append("disqualifying_issue_labels_incomplete")
    if selective.get("merge_gate_status") != "selective-review-policy":
        errors.append("merge_gate_status_mismatch")
    for field, ceiling in (
        ("maximum_assignment_to_pr_minutes", 30.0),
        ("maximum_pr_cross_reference_minutes", 10.0),
    ):
        value = selective.get(field)
        if (
            type(value) not in (int, float)
            or not math.isfinite(float(value))
            or not 0 < float(value) <= ceiling
        ):
            errors.append(f"{field}_invalid")
    if errors:
        raise ValueError("; ".join(errors))

    seen_pr_classes: dict[int, str] = {}
    parsed_observations: dict[str, list[PromotionObservation]] = {}
    observation_fields = {
        field.name for field in dataclass_fields(PromotionObservation)
    }
    for name in sorted(candidate_classes):
        class_evidence = evidence_classes.get(name)
        if not isinstance(class_evidence, dict):
            errors.append(f"{name}:promotion_evidence_missing")
            continue
        expected_fingerprint = class_policy_fingerprint(selective, name)
        if class_evidence.get("policy_fingerprint") != expected_fingerprint:
            errors.append(f"{name}:policy_fingerprint_mismatch")
        observations = class_evidence.get("observations", [])
        if not isinstance(observations, list):
            errors.append(f"{name}:observations_not_list")
            continue
        parsed_observations[name] = []
        for index, row in enumerate(observations):
            if not isinstance(row, dict):
                errors.append(f"{name}:observation_not_object:{index}")
                continue
            if set(row) != observation_fields:
                errors.append(f"{name}:observation_fields_invalid:{index}")
                continue
            observation = PromotionObservation(**row)
            observation_errors = _promotion_observation_errors(observation)
            if observation_errors:
                errors.append(
                    f"{name}:invalid_observation:{index}:"
                    f"{','.join(observation_errors)}"
                )
                continue
            parsed_observations[name].append(observation)
            pr_number = observation.pr_number
            previous_class = seen_pr_classes.setdefault(pr_number, name)
            if previous_class != name:
                errors.append(
                    f"pr_observed_in_multiple_classes:{pr_number}:"
                    f"{previous_class},{name}"
                )

    for item in promoted_classes:
        if isinstance(item, dict):
            if set(item) != {"name"} or not isinstance(item.get("name"), str):
                errors.append("promoted_class_entry_invalid")
                continue
            name = item["name"]
        elif isinstance(item, str):
            name = item
        else:
            errors.append("promoted_class_entry_invalid")
            continue
        if name not in candidate_classes:
            errors.append(f"{name}:not_a_candidate_class")
            continue
        class_evidence = evidence_classes.get(name)
        if not isinstance(class_evidence, dict):
            continue
        expected_fingerprint = class_policy_fingerprint(selective, name)
        if class_evidence.get("policy_fingerprint") != expected_fingerprint:
            continue
        observations = parsed_observations.get(name, [])
        assessment = evaluate_promotion(
            observations,
            requirements,
            str(candidate_document[name].get("test_policy") or ""),
        )
        results[name] = assessment
        if not assessment.eligible:
            errors.append(f"{name}:{','.join(assessment.reasons)}")

    if errors:
        raise ValueError("; ".join(errors))
    return results
