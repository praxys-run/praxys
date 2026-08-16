"""Pure policy coverage for the history-first 5 km baseline pilot."""
from __future__ import annotations

from datetime import date, datetime, timezone

from analysis.goal_baseline import (
    BASELINE_POLICY_VERSION,
    BaselineActivity,
    BaselineConfirmation,
    BaselineTestLifecycle,
    build_goal_baseline_goal,
    build_history_candidates,
    evaluate_goal_baseline,
)


def _activity(
    activity_id: str,
    observed_date: date,
    *,
    distance_km: float | None,
    duration_sec: float | None,
    activity_type: str = "running",
    source: str = "garmin",
    split_count: int = 5,
    sample_observed_duration_sec: float | None = None,
    timing_gap_count: int = 0,
) -> BaselineActivity:
    return BaselineActivity(
        activity_id=activity_id,
        observed_date=observed_date,
        distance_km=distance_km,
        duration_sec=duration_sec,
        activity_type=activity_type,
        source=source,
        split_count=split_count,
        sample_observed_duration_sec=sample_observed_duration_sec,
        timing_gap_count=timing_gap_count,
    )


def _confirmation(
    activity_id: str,
    response: str,
    *,
    measured_5k: bool = True,
    elapsed_timing_confirmed: bool = True,
    created_at: datetime | None = None,
) -> BaselineConfirmation:
    return BaselineConfirmation(
        activity_id=activity_id,
        response=response,
        measured_5k=measured_5k,
        elapsed_timing_confirmed=elapsed_timing_confirmed,
        created_at=created_at or datetime(2026, 8, 11, tzinfo=timezone.utc),
    )


def _test_record(
    state: str,
    *,
    created_at: datetime | None = None,
    observed_date: date | None = None,
    activity_id: str | None = None,
    measured_5k: bool | None = None,
    elapsed_timing_confirmed: bool | None = None,
    protocol_followed: bool | None = None,
    safety_stop: bool = False,
) -> BaselineTestLifecycle:
    return BaselineTestLifecycle(
        state=state,
        created_at=created_at or datetime(2026, 8, 11, tzinfo=timezone.utc),
        observed_date=observed_date,
        activity_id=activity_id,
        measured_5k=measured_5k,
        elapsed_timing_confirmed=elapsed_timing_confirmed,
        protocol_followed=protocol_followed,
        safety_stop=safety_stop,
    )


def test_goal_normalizer_accepts_legacy_target_time_alias() -> None:
    goal = build_goal_baseline_goal({
        "goal_kind": "performance_5k",
        "distance": "5k",
        "race_target_time_sec": 1475,
    })

    assert goal.target_time_sec == 1475


def test_non_performance_goals_return_not_required() -> None:
    goal = build_goal_baseline_goal({
        "goal_kind": "race",
        "distance": "marathon",
        "race_date": "2026-12-01",
        "target_time_sec": 10_800,
    })

    result = evaluate_goal_baseline(
        goal,
        athlete_today=date(2026, 8, 11),
        activities=[],
        confirmations=[],
        tests=[],
    )

    assert goal.eligible is False
    assert result.policy_version == BASELINE_POLICY_VERSION
    assert result.status == "not_required"
    assert result.readiness == "sufficient_baseline"
    assert result.evidence is None
    assert result.test.state == "not_offered"
    assert result.test.available is False


def test_history_candidate_retrieval_is_full_activity_only() -> None:
    activities = [
        _activity(
            "candidate",
            date(2026, 8, 10),
            distance_km=5.07,
            duration_sec=1_260,
            split_count=5,
            sample_observed_duration_sec=1_255,
        ),
        _activity(
            "long-run",
            date(2026, 8, 9),
            distance_km=10.0,
            duration_sec=3_100,
        ),
        _activity(
            "trail",
            date(2026, 8, 8),
            distance_km=5.02,
            duration_sec=1_280,
            activity_type="trail_running",
        ),
        _activity(
            "missing-duration",
            date(2026, 8, 7),
            distance_km=5.01,
            duration_sec=None,
        ),
    ]

    candidates = build_history_candidates(activities, [])

    assert [candidate.activity_id for candidate in candidates] == ["candidate"]
    assert candidates[0].full_activity_only is True
    assert candidates[0].review_state == "needs_confirmation"
    assert candidates[0].confirmation_response is None


def test_candidate_without_explicit_confirmation_stays_incomparable() -> None:
    goal = build_goal_baseline_goal({
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": 1_200,
    })
    activities = [
        _activity(
            "candidate",
            date(2026, 8, 1),
            distance_km=5.03,
            duration_sec=1_240,
            split_count=5,
            sample_observed_duration_sec=1_238,
        )
    ]

    result = evaluate_goal_baseline(
        goal,
        athlete_today=date(2026, 8, 11),
        activities=activities,
        confirmations=[],
        tests=[],
    )

    assert result.status == "incomparable"
    assert result.readiness == "insufficient_evidence"
    assert result.evidence is None
    assert result.candidates[0].review_state == "needs_confirmation"
    assert result.test.available is True
    assert result.test.can_schedule is True


def test_explicit_confirmation_qualifies_current_capability_without_change_claim() -> None:
    goal = build_goal_baseline_goal({
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": 1_200,
    })
    activities = [
        _activity(
            "candidate",
            date(2026, 8, 1),
            distance_km=5.08,
            duration_sec=1_235,
            split_count=5,
            sample_observed_duration_sec=1_232,
        )
    ]
    confirmations = [
        _confirmation("candidate", "intentional_all_out")
    ]

    result = evaluate_goal_baseline(
        goal,
        athlete_today=date(2026, 8, 11),
        activities=activities,
        confirmations=confirmations,
        tests=[],
    )

    assert result.status == "current"
    assert result.readiness == "sufficient_baseline"
    assert result.evidence is not None
    assert result.evidence.provenance == "intentional_all_out"
    assert result.evidence.measured_5k_confirmed is True
    assert result.evidence.elapsed_timing_confirmed is True
    assert result.evidence.change_comparability == "not_assessed"
    assert result.test.available is False
    assert result.test.can_schedule is False


def test_day_42_stays_current_and_day_43_turns_stale() -> None:
    goal = build_goal_baseline_goal({
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": 1_200,
    })
    activities = [
        _activity(
            "candidate",
            date(2026, 7, 1),
            distance_km=5.00,
            duration_sec=1_250,
        )
    ]
    confirmations = [_confirmation("candidate", "race")]

    current = evaluate_goal_baseline(
        goal,
        athlete_today=date(2026, 8, 12),
        activities=activities,
        confirmations=confirmations,
        tests=[],
    )
    stale = evaluate_goal_baseline(
        goal,
        athlete_today=date(2026, 8, 13),
        activities=activities,
        confirmations=confirmations,
        tests=[],
    )

    assert current.status == "current"
    assert current.evidence is not None
    assert current.evidence.age_days == 42
    assert stale.status == "stale"
    assert stale.evidence is not None
    assert stale.evidence.age_days == 43


def test_stale_evidence_is_retained_and_optional_test_remains_available() -> None:
    goal = build_goal_baseline_goal({
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": 1_200,
    })
    activities = [
        _activity(
            "candidate",
            date(2026, 6, 15),
            distance_km=4.99,
            duration_sec=1_248,
        )
    ]
    confirmations = [_confirmation("candidate", "race")]

    result = evaluate_goal_baseline(
        goal,
        athlete_today=date(2026, 8, 11),
        activities=activities,
        confirmations=confirmations,
        tests=[],
    )

    assert result.status == "stale"
    assert result.readiness == "insufficient_evidence"
    assert result.evidence is not None
    assert result.evidence.provenance == "race"
    assert result.test.available is True
    assert result.test.can_schedule is True


def test_current_evidence_suppresses_optional_test_prompt() -> None:
    goal = build_goal_baseline_goal({
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": 1_200,
    })
    activities = [
        _activity(
            "candidate",
            date(2026, 8, 9),
            distance_km=5.01,
            duration_sec=1_222,
        )
    ]
    confirmations = [_confirmation("candidate", "race")]

    result = evaluate_goal_baseline(
        goal,
        athlete_today=date(2026, 8, 11),
        activities=activities,
        confirmations=confirmations,
        tests=[_test_record("scheduled")],
    )

    assert result.status == "current"
    assert result.test.available is False
    assert result.test.can_schedule is False
    assert result.test.state in {"scheduled", "deleted"}


def test_safety_stop_keeps_no_test_path_and_non_diagnostic_readiness() -> None:
    goal = build_goal_baseline_goal({
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": 1_200,
    })

    result = evaluate_goal_baseline(
        goal,
        athlete_today=date(2026, 8, 11),
        activities=[],
        confirmations=[],
        tests=[_test_record("stopped", safety_stop=True)],
    )

    assert result.status == "missing"
    assert result.readiness == "non_diagnostic_safety_stop"
    assert result.evidence is None
    assert result.test.state == "stopped"
    assert result.test.available is True
