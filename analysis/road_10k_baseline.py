"""Pure helpers for reviewed direct 10K baseline evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
from typing import Any, Mapping, Sequence

from analysis.road_10k_contract import (
    ROAD_10K_BASELINE_SNAPSHOT_VERSION,
    ROAD_10K_BASELINE_CURRENT_THROUGH_COMPLETED_DAYS,
    ROAD_10K_POLICY_VERSION,
    ROAD_10K_SCIENCE_DECISION_ID,
)

ROAD_10K_RACE_SURFACE_OR_PROTOCOL = "organized_outdoor_road_10k_race"
ROAD_10K_TIME_TRIAL_SURFACE_OR_PROTOCOLS = frozenset({
    "standardized_outdoor_road_10k_time_trial",
    "standardized_track_10k_time_trial",
})
ROAD_10K_ACCEPTED_SURFACE_OR_PROTOCOLS = frozenset(
    {ROAD_10K_RACE_SURFACE_OR_PROTOCOL}
    | ROAD_10K_TIME_TRIAL_SURFACE_OR_PROTOCOLS
)
ROAD_10K_ASSISTANCE_STATUSES = frozenset({
    "unassisted",
    "assisted",
    "unknown_or_unreported",
})


@dataclass(frozen=True)
class Road10KBaselineGoal:
    """Normalized goal fields relevant to direct 10K baseline evaluation."""

    goal_kind: str
    distance: str | None
    target_time_sec: int | None
    eligible: bool
    goal_snapshot: dict[str, Any]
    goal_signature: str


@dataclass(frozen=True)
class Road10KBaselineActivity:
    """One full completed activity considered for direct 10K evidence."""

    activity_id: str
    observed_date: date
    distance_km: float | None
    duration_sec: float | None
    activity_type: str | None
    source: str | None
    completed_at: datetime | None = None
    split_count: int = 0
    sample_observed_duration_sec: float | None = None
    timing_gap_count: int = 0


@dataclass(frozen=True)
class Road10KBaselineConfirmation:
    """One explicit athlete confirmation for a candidate activity."""

    activity_id: str
    response: str
    measured_10k: bool
    elapsed_timing_confirmed: bool
    completed_at: datetime | None
    elapsed_time_sec: float | None
    surface_or_protocol: str | None
    route_or_venue_identifier: str | None
    assistance_status: str | None
    source_provider: str | None
    created_at: datetime


@dataclass(frozen=True)
class Road10KHistoryCandidate:
    """A surfaced current-window full activity awaiting confirmation."""

    activity_id: str
    observed_date: date
    distance_km: float | None
    duration_sec: float | None
    source: str | None
    completed_at: datetime | None
    review_state: str
    confirmation_response: str | None
    measured_10k_confirmed: bool | None
    elapsed_timing_confirmed: bool | None
    surface_or_protocol: str | None
    route_or_venue_identifier: str | None
    assistance_status: str | None
    source_provider: str | None
    full_activity_only: bool
    split_count: int
    sample_observed_duration_sec: float | None
    timing_gap_count: int


@dataclass(frozen=True)
class Road10KBaselineEvidence:
    """Qualified direct current-capability 10K evidence."""

    provenance: str
    observed_date: date
    age_days: int
    completed_at: datetime | None
    distance_km: float | None
    elapsed_time_sec: float | None
    activity_id: str | None
    measured_10k_confirmed: bool
    elapsed_timing_confirmed: bool
    surface_or_protocol: str | None
    route_or_venue_identifier: str | None
    assistance_status: str | None
    source_provider: str | None
    change_comparability: str


@dataclass(frozen=True)
class Road10KBaselineEvaluation:
    """Deterministic baseline status for one 10K performance goal."""

    policy_version: str
    status: str
    readiness: str
    evidence: Road10KBaselineEvidence | None
    candidates: tuple[Road10KHistoryCandidate, ...]
    alternatives: tuple[str, ...]


def build_road_10k_goal(
    raw_goal: Mapping[str, Any] | None,
) -> Road10KBaselineGoal:
    """Return the normalized goal slice used by direct 10K baseline logic."""
    payload = dict(raw_goal or {})
    raw_kind = str(payload.get("goal_kind") or "").strip().casefold()
    if raw_kind in {"race", "continuous", "performance_5k", "performance_10k"}:
        goal_kind = raw_kind
    elif payload.get("race_date"):
        goal_kind = "race"
    else:
        goal_kind = "continuous"

    distance = str(payload.get("distance") or "").strip().casefold() or None
    if goal_kind == "performance_10k" and not distance:
        distance = "10k"

    raw_target = payload.get("target_time_sec")
    if raw_target is None:
        raw_target = payload.get("race_target_time_sec")
    try:
        target_time_sec = (
            None if raw_target in (None, "", 0, "0") else int(raw_target)
        )
    except (TypeError, ValueError):
        target_time_sec = None

    eligible = goal_kind == "performance_10k" and distance == "10k"
    snapshot = {
        "goal_kind": goal_kind,
        "distance": distance,
        "criterion": "elapsed_time_seconds" if eligible else None,
        "setting": "outdoor_road" if eligible else None,
        "policy_version": ROAD_10K_POLICY_VERSION if eligible else None,
        "baseline_snapshot_version": (
            ROAD_10K_BASELINE_SNAPSHOT_VERSION if eligible else None
        ),
    }
    goal_signature = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return Road10KBaselineGoal(
        goal_kind=goal_kind,
        distance=distance,
        target_time_sec=target_time_sec,
        eligible=eligible,
        goal_snapshot=snapshot,
        goal_signature=goal_signature,
    )


def build_history_candidates(
    activities: Sequence[Road10KBaselineActivity],
    confirmations: Sequence[Road10KBaselineConfirmation],
) -> list[Road10KHistoryCandidate]:
    """Surface full current-window activities for explicit confirmation only."""
    latest_confirmation = _latest_confirmation_by_activity(confirmations)
    candidates: list[Road10KHistoryCandidate] = []
    for activity in activities:
        activity_type = str(activity.activity_type or "").strip().casefold()
        if activity_type != "running":
            continue
        if activity.distance_km is None or activity.duration_sec is None:
            continue
        if activity.duration_sec <= 0:
            continue
        confirmation = latest_confirmation.get(activity.activity_id)
        review_state, response, measured, elapsed = _candidate_review_state(
            confirmation
        )
        candidates.append(
            Road10KHistoryCandidate(
                activity_id=activity.activity_id,
                observed_date=activity.observed_date,
                distance_km=activity.distance_km,
                duration_sec=activity.duration_sec,
                source=activity.source,
                completed_at=activity.completed_at,
                review_state=review_state,
                confirmation_response=response,
                measured_10k_confirmed=measured,
                elapsed_timing_confirmed=elapsed,
                surface_or_protocol=(
                    None
                    if confirmation is None
                    else confirmation.surface_or_protocol
                ),
                route_or_venue_identifier=(
                    None
                    if confirmation is None
                    else confirmation.route_or_venue_identifier
                ),
                assistance_status=(
                    None
                    if confirmation is None
                    else confirmation.assistance_status
                ),
                source_provider=(
                    activity.source
                    or (
                        None
                        if confirmation is None
                        else confirmation.source_provider
                    )
                ),
                full_activity_only=True,
                split_count=activity.split_count,
                sample_observed_duration_sec=activity.sample_observed_duration_sec,
                timing_gap_count=activity.timing_gap_count,
            )
        )
    candidates.sort(
        key=lambda item: (item.observed_date, item.activity_id),
        reverse=True,
    )
    return candidates


def evaluate_road_10k_baseline(
    goal: Road10KBaselineGoal,
    *,
    athlete_today: date,
    activities: Sequence[Road10KBaselineActivity],
    confirmations: Sequence[Road10KBaselineConfirmation],
) -> Road10KBaselineEvaluation:
    """Return the reviewed direct-baseline status for one 10K goal."""
    if not goal.eligible:
        return Road10KBaselineEvaluation(
            policy_version=ROAD_10K_POLICY_VERSION,
            status="not_required",
            readiness="sufficient_baseline",
            evidence=None,
            candidates=(),
            alternatives=("manual_training",),
        )

    candidates = tuple(build_history_candidates(activities, confirmations))
    evidence = _select_direct_history_evidence(candidates, athlete_today)
    if evidence is not None:
        current_through = ROAD_10K_BASELINE_CURRENT_THROUGH_COMPLETED_DAYS
        status = "current" if evidence.age_days <= current_through else "stale"
        readiness = (
            "sufficient_baseline"
            if status == "current"
            else "insufficient_evidence"
        )
    elif candidates:
        status = "incomparable"
        readiness = "insufficient_evidence"
    else:
        status = "missing"
        readiness = "insufficient_evidence"

    return Road10KBaselineEvaluation(
        policy_version=ROAD_10K_POLICY_VERSION,
        status=status,
        readiness=readiness,
        evidence=evidence,
        candidates=candidates,
        alternatives=("optional_10k_benchmark", "manual_training"),
    )


def _latest_confirmation_by_activity(
    confirmations: Sequence[Road10KBaselineConfirmation],
) -> dict[str, Road10KBaselineConfirmation]:
    latest: dict[str, Road10KBaselineConfirmation] = {}
    for confirmation in confirmations:
        current = latest.get(confirmation.activity_id)
        if current is None or confirmation.created_at >= current.created_at:
            latest[confirmation.activity_id] = confirmation
    return latest


def _candidate_review_state(
    confirmation: Road10KBaselineConfirmation | None,
) -> tuple[str, str | None, bool | None, bool | None]:
    if confirmation is None or confirmation.response == "deleted":
        return "needs_confirmation", None, None, None
    if confirmation.response == "not_all_out":
        return (
            "excluded",
            confirmation.response,
            confirmation.measured_10k,
            confirmation.elapsed_timing_confirmed,
        )
    if not confirmation.measured_10k:
        return (
            "distance_unverified",
            confirmation.response,
            False,
            confirmation.elapsed_timing_confirmed,
        )
    if not confirmation.elapsed_timing_confirmed:
        return (
            "timing_unresolved",
            confirmation.response,
            confirmation.measured_10k,
            False,
        )
    if (
        confirmation.response in {"race", "intentional_all_out"}
        and _has_direct_baseline_contract_metadata(confirmation)
    ):
        return "qualified", confirmation.response, True, True
    return (
        "needs_confirmation",
        confirmation.response,
        confirmation.measured_10k,
        confirmation.elapsed_timing_confirmed,
    )


def _select_direct_history_evidence(
    candidates: Sequence[Road10KHistoryCandidate],
    athlete_today: date,
) -> Road10KBaselineEvidence | None:
    qualified = [
        candidate
        for candidate in candidates
        if candidate.review_state == "qualified"
    ]
    if not qualified:
        return None
    latest = max(qualified, key=lambda item: (item.observed_date, item.activity_id))
    return Road10KBaselineEvidence(
        provenance=str(latest.confirmation_response or "race"),
        observed_date=latest.observed_date,
        age_days=(athlete_today - latest.observed_date).days,
        completed_at=latest.completed_at,
        distance_km=latest.distance_km,
        elapsed_time_sec=latest.duration_sec,
        activity_id=latest.activity_id,
        measured_10k_confirmed=bool(latest.measured_10k_confirmed),
        elapsed_timing_confirmed=bool(latest.elapsed_timing_confirmed),
        surface_or_protocol=latest.surface_or_protocol,
        route_or_venue_identifier=latest.route_or_venue_identifier,
        assistance_status=latest.assistance_status,
        source_provider=latest.source_provider,
        change_comparability="not_assessed",
    )


def _has_direct_baseline_contract_metadata(
    confirmation: Road10KBaselineConfirmation,
) -> bool:
    if confirmation.completed_at is None:
        return False
    if confirmation.elapsed_time_sec is None or confirmation.elapsed_time_sec <= 0:
        return False
    if not _surface_or_protocol_matches_response(
        confirmation.response,
        confirmation.surface_or_protocol,
    ):
        return False
    if not str(confirmation.route_or_venue_identifier or "").strip():
        return False
    if confirmation.assistance_status not in ROAD_10K_ASSISTANCE_STATUSES:
        return False
    return bool(str(confirmation.source_provider or "").strip())


def _surface_or_protocol_matches_response(
    response: str,
    surface_or_protocol: str | None,
) -> bool:
    if response == "race":
        return surface_or_protocol == ROAD_10K_RACE_SURFACE_OR_PROTOCOL
    if response == "intentional_all_out":
        return surface_or_protocol in ROAD_10K_TIME_TRIAL_SURFACE_OR_PROTOCOLS
    return False
