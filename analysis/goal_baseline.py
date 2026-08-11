"""Pure policy helpers for the history-first 5 km baseline pilot."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
from typing import Any, Mapping, Sequence

BASELINE_POLICY_VERSION = "preplan-baseline-policy-v1"
BASELINE_SCIENCE_DECISION_ID = "sdr-preplan-baseline-policy-v1"
BASELINE_PROTOCOL_ID = "outdoor-5k-tt-pilot-v1"
BASELINE_GUARDRAIL_DAYS = 42  # Accepted SDR freshness_age_calculation pilot guardrail: day 42 current, day 43 stale.
# Retrieval-only heuristic for surfacing near-5 km full activities during issue #654; it never qualifies evidence by itself.
_HISTORY_RETRIEVAL_MAX_DISTANCE_DELTA_KM = 0.25


@dataclass(frozen=True)
class GoalBaselineGoal:
    """Normalized goal fields relevant to the baseline pilot."""

    goal_kind: str
    distance: str | None
    target_time_sec: int | None
    eligible: bool
    goal_snapshot: dict[str, Any]
    goal_signature: str


@dataclass(frozen=True)
class BaselineActivity:
    """One complete activity candidate considered by the history search."""

    activity_id: str
    observed_date: date
    distance_km: float | None
    duration_sec: float | None
    activity_type: str | None
    source: str | None
    split_count: int = 0
    sample_observed_duration_sec: float | None = None
    timing_gap_count: int = 0


@dataclass(frozen=True)
class BaselineConfirmation:
    """One explicit athlete confirmation for a candidate activity."""

    activity_id: str
    response: str
    measured_5k: bool
    elapsed_timing_confirmed: bool
    created_at: datetime


@dataclass(frozen=True)
class BaselineTestLifecycle:
    """One retained optional-test lifecycle record."""

    state: str
    created_at: datetime
    observed_date: date | None = None
    activity_id: str | None = None
    measured_5k: bool | None = None
    elapsed_timing_confirmed: bool | None = None
    protocol_followed: bool | None = None
    safety_stop: bool = False


@dataclass(frozen=True)
class HistoryCandidate:
    """Candidate surfaced to the athlete for review."""

    activity_id: str
    observed_date: date
    distance_km: float | None
    duration_sec: float | None
    source: str | None
    review_state: str
    confirmation_response: str | None
    measured_5k_confirmed: bool | None
    elapsed_timing_confirmed: bool | None
    full_activity_only: bool
    split_count: int
    sample_observed_duration_sec: float | None
    timing_gap_count: int


@dataclass(frozen=True)
class BaselineEvidence:
    """Qualified direct current-capability evidence."""

    provenance: str
    observed_date: date
    age_days: int
    distance_km: float | None
    elapsed_time_sec: float | None
    activity_id: str | None
    measured_5k_confirmed: bool
    elapsed_timing_confirmed: bool
    change_comparability: str


@dataclass(frozen=True)
class BaselineTestView:
    """UI-facing optional-test availability derived from retained records."""

    state: str
    available: bool
    can_schedule: bool


@dataclass(frozen=True)
class GoalBaselineEvaluation:
    """Pure, deterministic baseline assessment for one goal."""

    policy_version: str
    status: str
    readiness: str
    evidence: BaselineEvidence | None
    candidates: tuple[HistoryCandidate, ...]
    test: BaselineTestView
    alternatives: tuple[str, ...]


def build_goal_baseline_goal(raw_goal: Mapping[str, Any] | None) -> GoalBaselineGoal:
    """Return the normalized goal contract slice for baseline evaluation."""
    payload = dict(raw_goal or {})
    raw_kind = str(payload.get("goal_kind") or "").strip().casefold()
    if raw_kind in {"race", "continuous", "performance_5k"}:
        goal_kind = raw_kind
    elif payload.get("race_date"):
        goal_kind = "race"
    else:
        goal_kind = "continuous"

    distance = str(payload.get("distance") or "").strip().casefold() or None
    if goal_kind == "performance_5k" and not distance:
        distance = "5k"

    raw_target = payload.get("target_time_sec")
    target_time_sec: int | None
    if raw_target in (None, "", 0, "0"):
        target_time_sec = None
    else:
        try:
            target_time_sec = int(raw_target)
        except (TypeError, ValueError):
            target_time_sec = None

    eligible = goal_kind == "performance_5k" and distance == "5k"
    snapshot = {
        "goal_kind": goal_kind,
        "distance": distance,
        "criterion": "elapsed_time_seconds" if eligible else None,
        "setting": "outdoor_road" if eligible else None,
        "policy_version": BASELINE_POLICY_VERSION if eligible else None,
    }
    goal_signature = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return GoalBaselineGoal(
        goal_kind=goal_kind,
        distance=distance,
        target_time_sec=target_time_sec,
        eligible=eligible,
        goal_snapshot=snapshot,
        goal_signature=goal_signature,
    )


def build_history_candidates(
    activities: Sequence[BaselineActivity],
    confirmations: Sequence[BaselineConfirmation],
) -> list[HistoryCandidate]:
    """Surface bounded, full-activity candidates for athlete review.

    Retrieval is intentionally distinct from qualification. The bounded
    distance window is a discovery heuristic only; a surfaced candidate still
    requires explicit measured-distance and elapsed-timing confirmation plus
    race provenance or all-out intent before it can qualify.
    """
    latest_confirmation = _latest_confirmation_by_activity(confirmations)
    candidates: list[HistoryCandidate] = []
    for activity in activities:
        activity_type = str(activity.activity_type or "").strip().casefold()
        if activity_type != "running":
            continue
        if activity.distance_km is None or activity.duration_sec is None:
            continue
        if activity.duration_sec <= 0:
            continue
        if abs(float(activity.distance_km) - 5.0) > _HISTORY_RETRIEVAL_MAX_DISTANCE_DELTA_KM:
            continue
        confirmation = latest_confirmation.get(activity.activity_id)
        review_state, response, measured, elapsed = _candidate_review_state(
            confirmation
        )
        candidates.append(
            HistoryCandidate(
                activity_id=activity.activity_id,
                observed_date=activity.observed_date,
                distance_km=activity.distance_km,
                duration_sec=activity.duration_sec,
                source=activity.source,
                review_state=review_state,
                confirmation_response=response,
                measured_5k_confirmed=measured,
                elapsed_timing_confirmed=elapsed,
                full_activity_only=True,
                split_count=activity.split_count,
                sample_observed_duration_sec=activity.sample_observed_duration_sec,
                timing_gap_count=activity.timing_gap_count,
            )
        )
    candidates.sort(
        key=lambda candidate: (
            candidate.observed_date,
            -(candidate.distance_km or 0),
            candidate.activity_id,
        ),
        reverse=True,
    )
    return candidates


def evaluate_goal_baseline(
    goal: GoalBaselineGoal,
    *,
    athlete_today: date,
    activities: Sequence[BaselineActivity],
    confirmations: Sequence[BaselineConfirmation],
    tests: Sequence[BaselineTestLifecycle],
) -> GoalBaselineEvaluation:
    """Return the pure pilot status for one goal at one athlete-local date."""
    if not goal.eligible:
        return GoalBaselineEvaluation(
            policy_version=BASELINE_POLICY_VERSION,
            status="not_required",
            readiness="sufficient_baseline",
            evidence=None,
            candidates=(),
            test=BaselineTestView(
                state="not_offered",
                available=False,
                can_schedule=False,
            ),
            alternatives=("no_test_path",),
        )

    candidates = tuple(build_history_candidates(activities, confirmations))
    direct_history = _select_direct_history_evidence(candidates, athlete_today)
    direct_test = _select_direct_test_evidence(tests, athlete_today)
    evidence = _pick_latest_evidence(direct_history, direct_test)
    latest_test = _latest_test(tests)

    if evidence is not None:
        status = "current" if evidence.age_days <= BASELINE_GUARDRAIL_DAYS else "stale"
        readiness = "sufficient_baseline" if status == "current" else "insufficient_evidence"
    elif candidates:
        status = "incomparable"
        readiness = "insufficient_evidence"
    else:
        status = "missing"
        readiness = "insufficient_evidence"

    if latest_test is not None and latest_test.safety_stop and evidence is None:
        readiness = "non_diagnostic_safety_stop"

    test_state = latest_test.state if latest_test is not None else "not_offered"
    if evidence is None and test_state in {"offered", "scheduled"}:
        status = "pending_test"

    test_available = status in {"missing", "stale", "incomparable", "pending_test"}
    if evidence is not None and evidence.age_days <= BASELINE_GUARDRAIL_DAYS:
        test_available = False

    can_schedule = test_available and test_state != "scheduled"
    return GoalBaselineEvaluation(
        policy_version=BASELINE_POLICY_VERSION,
        status=status,
        readiness=readiness,
        evidence=evidence,
        candidates=candidates,
        test=BaselineTestView(
            state=test_state,
            available=test_available,
            can_schedule=can_schedule,
        ),
        alternatives=("no_test_path", "completion_or_consistency_goal"),
    )


def _latest_confirmation_by_activity(
    confirmations: Sequence[BaselineConfirmation],
) -> dict[str, BaselineConfirmation]:
    latest: dict[str, BaselineConfirmation] = {}
    for confirmation in confirmations:
        current = latest.get(confirmation.activity_id)
        if current is None or confirmation.created_at >= current.created_at:
            latest[confirmation.activity_id] = confirmation
    return latest


def _candidate_review_state(
    confirmation: BaselineConfirmation | None,
) -> tuple[str, str | None, bool | None, bool | None]:
    if confirmation is None or confirmation.response == "deleted":
        return "needs_confirmation", None, None, None
    if confirmation.response == "not_all_out":
        return "excluded", confirmation.response, confirmation.measured_5k, confirmation.elapsed_timing_confirmed
    if not confirmation.measured_5k:
        return "distance_unverified", confirmation.response, False, confirmation.elapsed_timing_confirmed
    if not confirmation.elapsed_timing_confirmed:
        return "timing_unresolved", confirmation.response, confirmation.measured_5k, False
    if confirmation.response in {"race", "intentional_all_out"}:
        return "qualified", confirmation.response, True, True
    return "needs_confirmation", confirmation.response, confirmation.measured_5k, confirmation.elapsed_timing_confirmed


def _select_direct_history_evidence(
    candidates: Sequence[HistoryCandidate],
    athlete_today: date,
) -> BaselineEvidence | None:
    qualified = [candidate for candidate in candidates if candidate.review_state == "qualified"]
    if not qualified:
        return None
    best = max(qualified, key=lambda candidate: (candidate.observed_date, candidate.activity_id))
    age_days = max(0, (athlete_today - best.observed_date).days)
    return BaselineEvidence(
        provenance=str(best.confirmation_response or "intentional_all_out"),
        observed_date=best.observed_date,
        age_days=age_days,
        distance_km=best.distance_km,
        elapsed_time_sec=best.duration_sec,
        activity_id=best.activity_id,
        measured_5k_confirmed=best.measured_5k_confirmed is True,
        elapsed_timing_confirmed=best.elapsed_timing_confirmed is True,
        change_comparability="not_assessed",
    )


def _select_direct_test_evidence(
    tests: Sequence[BaselineTestLifecycle],
    athlete_today: date,
) -> BaselineEvidence | None:
    qualified = [
        test
        for test in tests
        if test.state == "completed"
        and test.observed_date is not None
        and test.measured_5k is True
        and test.elapsed_timing_confirmed is True
        and test.protocol_followed is True
    ]
    if not qualified:
        return None
    best = max(qualified, key=lambda test: (test.observed_date or date.min, test.created_at))
    observed_date = best.observed_date or athlete_today
    age_days = max(0, (athlete_today - observed_date).days)
    return BaselineEvidence(
        provenance="pilot_test",
        observed_date=observed_date,
        age_days=age_days,
        distance_km=5.0 if best.measured_5k else None,
        elapsed_time_sec=None,
        activity_id=best.activity_id,
        measured_5k_confirmed=best.measured_5k is True,
        elapsed_timing_confirmed=best.elapsed_timing_confirmed is True,
        change_comparability="not_assessed",
    )


def _pick_latest_evidence(
    left: BaselineEvidence | None,
    right: BaselineEvidence | None,
) -> BaselineEvidence | None:
    if left is None:
        return right
    if right is None:
        return left
    return left if (left.observed_date, left.provenance) >= (right.observed_date, right.provenance) else right


def _latest_test(tests: Sequence[BaselineTestLifecycle]) -> BaselineTestLifecycle | None:
    if not tests:
        return None
    return max(tests, key=lambda test: (test.created_at, test.state))
