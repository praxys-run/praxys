"""Tests for the deterministic road 10K policy service."""
from __future__ import annotations

import importlib
import hashlib
import json
import os
import tempfile
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROAD_10K_TEST_PASSWORD = "road-10k-secret"


def _history(today: date):
    from analysis.road_10k_plan_generation import RunningHistoryObservation

    current_week = today - timedelta(days=today.weekday())
    activities: list[RunningHistoryObservation] = []
    for week in range(1, 9):
        week_start = current_week - timedelta(days=7 * week)
        for offset, duration, distance in (
            (0, 55.0, 9.0),
            (2, 60.0, 10.0),
            (5, 65.0, 12.0),
        ):
            activities.append(
                RunningHistoryObservation(
                    activity_id=f"road-10k-{week}-{offset}",
                    observed_date=week_start + timedelta(days=offset),
                    duration_min=duration,
                    distance_km=distance,
                    source="garmin",
                )
            )
    return tuple(activities)


def _intensity_sources(history) -> tuple[tuple[str, str], ...]:
    return tuple((item.activity_id, "activity_splits") for item in history)


def _input(
    *,
    baseline_current: bool = True,
    target_event_date: date | None = None,
    benchmark_date: date | None = None,
    history=None,
    intensity_sources: tuple[tuple[str, str], ...] | None = None,
):
    from analysis.road_10k_plan_generation import (
        ROAD_10K_CONTRACT_DIGEST,
        ROAD_10K_POLICY_VERSION,
        ROAD_10K_SCIENCE_DECISION_ID,
        ROAD_10K_SOURCE_DECISION_DIGEST,
        Road10KGenerationInput,
        Road10KGoal,
        Road10KPlanGenerationConstraints,
        build_road_10k_training_pattern_snapshot,
    )

    today = date(2026, 8, 18)
    history_items = tuple(history or _history(today))
    sources = (
        intensity_sources
        if intensity_sources is not None
        else _intensity_sources(history_items)
    )
    training_pattern = build_road_10k_training_pattern_snapshot(
        history_items,
        athlete_today=today,
        intensity_sources=sources,
        reserved_dates=(),
    )
    return Road10KGenerationInput(
        policy_version=ROAD_10K_POLICY_VERSION,
        science_decision_id=ROAD_10K_SCIENCE_DECISION_ID,
        contract_digest=ROAD_10K_CONTRACT_DIGEST,
        source_decision_digest=ROAD_10K_SOURCE_DECISION_DIGEST,
        athlete_today=today,
        block_start=today + timedelta(days=1),
        goal=Road10KGoal(
            goal_kind="performance_10k",
            distance="10k",
            target_time_sec=2_520,
            target_event_date=target_event_date,
        ),
        baseline_current=baseline_current,
        baseline_snapshot_id=(
            "road-10k-baseline-snapshot-1" if baseline_current else None
        ),
        baseline_source="race" if baseline_current else None,
        baseline_evidence_date=(
            today - timedelta(days=6) if baseline_current else None
        ),
        history=history_items,
        intensity_sources=sources,
        reserved_dates=(),
        training_pattern_snapshot_version=training_pattern.version,
        constraints=Road10KPlanGenerationConstraints(
            adult_confirmed=True,
            current_symptom_stop=False,
            available_weekdays=(0, 2, 5),
            weekly_time_limit_min=170,
            maximum_session_duration_min=70,
            unavailable_dates=(),
            unavailable_dates_confirmed_none=True,
            event_context_confirmed_none=target_event_date is None and benchmark_date is None,
            outdoor_road_intent_confirmed=True,
            preferred_longest_easy_weekday=5,
            benchmark_date=benchmark_date,
        ),
    )


def test_constraints_type_preserves_unanswered_symptom_stop() -> None:
    from typing import get_type_hints
    from analysis.road_10k_plan_generation import Road10KPlanGenerationConstraints

    assert get_type_hints(Road10KPlanGenerationConstraints)[
        "current_symptom_stop"
    ] == bool | None


def test_generation_is_deterministic_and_uses_the_reviewed_templates() -> None:
    """A replay of the same versioned input returns the same 14-day schedule."""
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    first = generate_road_10k_plan(_input())
    replay = generate_road_10k_plan(_input())

    assert replay == first
    assert first.code == "eligible_rolling_proposal"
    assert first.plan is not None
    assert first.plan.horizon_end - first.plan.horizon_start == timedelta(days=13)
    assert list(first.plan.reassessment_dates) == [
        first.plan.horizon_start + timedelta(days=7),
    ]
    assert [week.is_taper for week in first.plan.weeks] == [False, False]
    assert [
        workout.template_id
        for week in first.plan.weeks
        for workout in week.workouts
        if workout.intensity_bucket == "quality"
    ] == [
        "road-10k-controlled-threshold-quality-v1",
        "road-10k-specific-interval-quality-v1",
    ]

    for week in first.plan.weeks:
        workouts = week.workouts
        total_minutes = sum(item.planned_duration_min for item in workouts)
        low_minutes = sum(
            item.planned_duration_min
            for item in workouts
            if item.intensity_bucket == "low"
        )
        assert 3 <= len(workouts) <= 6
        assert sum(
            item.intensity_bucket == "quality" for item in workouts
        ) == 1
        assert total_minutes <= 180
        assert low_minutes / total_minutes >= 0.75


def test_missing_baseline_and_target_conflicts_are_typed_fail_closed_results() -> None:
    """Road 10K readiness keeps missing baseline and event conflicts distinct."""
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    missing = generate_road_10k_plan(_input(baseline_current=False))
    near_term = generate_road_10k_plan(
        _input(target_event_date=date(2026, 8, 24))
    )
    dense = generate_road_10k_plan(
        _input(
            target_event_date=date(2026, 9, 2),
            benchmark_date=date(2026, 8, 29),
        )
    )

    assert missing.code == "missing_or_stale_direct_baseline"
    assert missing.plan is None
    assert near_term.code == "limited_near_term_guidance"
    assert near_term.plan is None
    assert dense.code == "limited_guidance_event_conflict"
    assert dense.plan is None


def test_explicit_science_statements_and_small_availability_fail_closed() -> None:
    """Absence never becomes a negative symptom/event/date statement."""
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    base = _input()
    missing_symptom = generate_road_10k_plan(
        replace(base, constraints=replace(base.constraints, current_symptom_stop=None))
    )
    missing_event = generate_road_10k_plan(
        replace(base, constraints=replace(base.constraints, event_context_confirmed_none=False))
    )
    missing_dates = generate_road_10k_plan(
        replace(base, constraints=replace(base.constraints, unavailable_dates=None))
    )
    one_or_two_days = generate_road_10k_plan(
        replace(base, constraints=replace(base.constraints, available_weekdays=(0, 2)))
    )

    assert missing_symptom.plan is None
    assert missing_symptom.failed_rule_id == "current_symptom_confirmation"
    assert missing_event.plan is None
    assert missing_event.failed_rule_id == "event_context_confirmation"
    assert missing_dates.plan is None
    assert missing_dates.failed_rule_id == "unavailable_dates_confirmation"
    assert one_or_two_days.code == "no_schedule_within_envelope"


def test_missing_and_explicitly_empty_unavailable_dates_hash_differently() -> None:
    from analysis.road_10k_plan_generation import deterministic_input_hash

    explicit_none = _input()
    unanswered = replace(
        explicit_none,
        constraints=replace(
            explicit_none.constraints,
            unavailable_dates=None,
        ),
    )

    assert deterministic_input_hash(unanswered) != deterministic_input_hash(
        explicit_none
    )


def test_symptom_stop_precedes_event_and_constraint_clarification() -> None:
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    base = _input()
    result = generate_road_10k_plan(
        replace(
            base,
            constraints=replace(
                base.constraints,
                current_symptom_stop=True,
                event_context_confirmed_none=False,
                available_weekdays=(0, 2),
                unavailable_dates=None,
            ),
        )
    )

    assert result.code == "safety_stop"
    assert result.failed_rule_id == "current_symptom_stop"


@pytest.mark.parametrize(
    "updates",
    [
        {"target_event_date": date(2026, 9, 2)},
        {"benchmark_date": date(2026, 9, 2)},
    ],
)
def test_confirmed_no_event_rejects_a_dated_target(updates) -> None:
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    base = _input(**updates)
    result = generate_road_10k_plan(
        replace(
            base,
            constraints=replace(
                base.constraints,
                event_context_confirmed_none=True,
            ),
        )
    )

    assert result.code == "contradictory_input"
    assert result.failed_rule_id == "event_context_confirmation"
    assert result.plan is None


def test_outdoor_road_intent_requires_explicit_confirmation() -> None:
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    base = _input()
    result = generate_road_10k_plan(
        replace(
            base,
            constraints=replace(
                base.constraints,
                outdoor_road_intent_confirmed=False,
            ),
        )
    )

    assert result.code == "adult_scope_or_constraints_unconfirmed"
    assert result.failed_rule_id == "outdoor_road_intent_confirmation"
    assert result.plan is None


def test_api_requires_explicit_unavailable_and_event_statements() -> None:
    from pydantic import ValidationError
    from api.routes.road_10k_plan_generation import Road10KConstraintsRequest

    with pytest.raises(ValidationError):
        Road10KConstraintsRequest.model_validate(
            {
                "adult_confirmed": True,
                "current_symptom_stop": False,
                "available_weekdays": [0, 2, 5],
                "weekly_time_limit_min": 170,
                "maximum_session_duration_min": 70,
                "unavailable_dates": [date(2026, 8, 30)],
                "outdoor_road_intent_confirmed": True,
            }
        )


def test_schedule_never_silently_underfills_exact_weekly_target() -> None:
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    base = _input()
    result = generate_road_10k_plan(
        replace(base, constraints=replace(base.constraints, weekly_time_limit_min=180))
    )

    assert result.code == "no_schedule_within_envelope"
    assert result.plan is None


def test_easy_remainder_is_chronological_without_preference() -> None:
    from analysis.road_10k_plan_generation import _easy_allocation_priority

    dates = (date(2026, 8, 19), date(2026, 8, 21), date(2026, 8, 23))
    assert _easy_allocation_priority(
        dates, preferred_longest_easy_weekday=None
    ) == dates


def test_easy_remainder_is_chronological_when_preferred_day_is_absent() -> None:
    from analysis.road_10k_plan_generation import _easy_allocation_priority

    dates = (date(2026, 8, 19), date(2026, 8, 21), date(2026, 8, 23))
    assert _easy_allocation_priority(
        dates,
        preferred_longest_easy_weekday=0,
    ) == dates


def test_longest_easy_designation_never_labels_a_shorter_easy_run() -> None:
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    base = _input()
    result = generate_road_10k_plan(
        replace(
            base,
            constraints=replace(
                base.constraints,
                preferred_longest_easy_weekday=None,
            ),
        )
    )

    assert result.plan is not None
    for week in result.plan.weeks:
        easy_runs = [
            workout
            for workout in week.workouts
            if workout.intensity_bucket == "low"
        ]
        designated = [
            workout
            for workout in easy_runs
            if workout.workout_type == "longest_easy"
        ]
        assert not designated or designated[0].planned_duration_min == max(
            workout.planned_duration_min for workout in easy_runs
        )


def test_eight_to_fourteen_day_target_can_fail_exact_taper_fill() -> None:
    """Taper eligibility does not guarantee an exactly fillable schedule."""
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    target_date = date(2026, 8, 29)
    result = generate_road_10k_plan(
        _input(target_event_date=target_date)
    )

    assert result.code == "no_schedule_within_envelope"
    assert result.plan is None


@pytest.mark.parametrize(
    ("days_after_start", "expected_code", "expect_taper"),
    [
        (7, "limited_near_term_guidance", None),
        (8, "no_schedule_within_envelope", None),
        (14, "eligible_taper_proposal", True),
        (15, "eligible_rolling_proposal", False),
        (21, "eligible_rolling_proposal", False),
    ],
)
def test_taper_boundaries_anchor_only_to_block_start(
    days_after_start: int,
    expected_code: str,
    expect_taper: bool | None,
) -> None:
    """Only targets 8-14 days after block start may enter the taper path."""
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    block_start = _input().block_start
    target_date = block_start + timedelta(days=days_after_start)

    result = generate_road_10k_plan(
        _input(target_event_date=target_date)
    )

    assert result.code == expected_code
    if expect_taper is None:
        assert result.plan is None
        return
    assert result.plan is not None
    assert any(week.is_taper for week in result.plan.weeks) is expect_taper
    if expect_taper:
        assert all(week.is_taper for week in result.plan.weeks)
        assert result.plan.horizon_end == target_date - timedelta(days=1)
    else:
        assert not any(week.is_taper for week in result.plan.weeks)
        assert result.plan.horizon_end == block_start + timedelta(days=13)


def test_taper_window_and_public_guardrails_match_the_accepted_contract() -> None:
    """Routing boundaries and visible guardrails stay contract-derived."""
    from analysis.road_10k_contract import (
        ROAD_10K_CONTRACT,
        ROAD_10K_GUARDRAILS,
        ROAD_10K_TAPER_MAXIMUM_DAYS_BEFORE_EVENT,
        ROAD_10K_TAPER_MINIMUM_DAYS_BEFORE_EVENT,
    )
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    parameters = ROAD_10K_CONTRACT.parameter_values
    execution = parameters[
        "road_10k_v2_execution_window_and_reassessment"
    ]
    intensity = parameters["road_10k_v2_intensity_quality_and_spacing"]
    readiness = parameters["road_10k_v2_readiness_and_missingness"]
    event_policy = parameters[
        "road_10k_v2_event_benchmark_and_taper"
    ]
    taper = event_policy["taper"]
    taper_window = taper["supported_window_days_before_event"]
    claims = parameters["road_10k_v2_demographic_and_claim_limits"]
    assert ROAD_10K_GUARDRAILS.public_payload() == {
        "committed_proposal_days": int(execution["committed_proposal_days"]),
        "advisory_reassessment_after_completed_days": int(
            execution["advisory_reassessment_after_completed_days"]
        ),
        "minimum_planned_low_intensity_running_minutes_fraction": float(
            intensity[
                "minimum_planned_low_intensity_running_minutes_fraction"
            ]
        ),
        "baseline_current_through_completed_days": int(
            readiness["baseline_current_through_completed_days"]
        ),
        "taper": {
            "planned_volume_reduction_fraction": float(
                taper["planned_volume_reduction_fraction"]
            ),
            "maintain_intensity_exposure_without_adding_quality": taper[
                "maintain_intensity_exposure_without_adding_quality"
            ],
            "evidence_population": taper["evidence_population"],
            "direct_recreational_road_10k_validation": taper[
                "direct_recreational_road_10k_validation"
            ],
            "single_target_taper_result": event_policy["single_target"][
                "target_8_to_14_days_after_start"
            ],
            "personal_performance_gain_claim": taper[
                "personal_performance_gain_claim"
            ],
            "causal_plan_benefit_claim": claims[
                "causal_plan_benefit_claim"
            ],
            "personal_injury_probability": claims[
                "personal_injury_probability"
            ],
        },
    }
    from api.routes.road_10k_plan_generation import (
        Road10KGuardrailProjectionResponse,
    )

    projected = Road10KGuardrailProjectionResponse.model_validate(
        ROAD_10K_GUARDRAILS.public_payload()
    )
    assert projected.taper.planned_volume_reduction_fraction == 0.5
    assert projected.taper.single_target_taper_result == (
        "taper_proposal_truncated_to_event_eve"
    )
    assert ROAD_10K_TAPER_MINIMUM_DAYS_BEFORE_EVENT == int(
        taper_window["minimum"]
    )
    assert ROAD_10K_TAPER_MAXIMUM_DAYS_BEFORE_EVENT == int(
        taper_window["maximum"]
    )

    block_start = _input().block_start
    cases = (
        (
            ROAD_10K_TAPER_MINIMUM_DAYS_BEFORE_EVENT - 1,
            "limited_near_term_guidance",
        ),
        (
            ROAD_10K_TAPER_MINIMUM_DAYS_BEFORE_EVENT,
            "no_schedule_within_envelope",
        ),
        (
            ROAD_10K_TAPER_MAXIMUM_DAYS_BEFORE_EVENT,
            "eligible_taper_proposal",
        ),
        (
            ROAD_10K_TAPER_MAXIMUM_DAYS_BEFORE_EVENT + 1,
            "eligible_rolling_proposal",
        ),
    )
    assert [
        generate_road_10k_plan(
            _input(
                target_event_date=block_start + timedelta(days=days)
            )
        ).code
        for days, _expected in cases
    ] == [expected for _days, expected in cases]


def test_reserved_event_is_not_appended_to_the_taper_comparator() -> None:
    """The event date is not an ordinary workout in the reference schedule."""
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    block_start = _input().block_start
    target_date = block_start + timedelta(days=13)

    result = generate_road_10k_plan(
        _input(target_event_date=target_date)
    )

    assert result.code == "no_schedule_within_envelope"
    assert result.plan is None


def test_odd_reference_minutes_return_no_inexact_taper() -> None:
    """Integer minutes must realize the accepted 0.50 reduction exactly."""
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    generation_input = _input()
    target_date = generation_input.block_start + timedelta(days=14)
    constraints = replace(
        generation_input.constraints,
        weekly_time_limit_min=169,
        event_context_confirmed_none=False,
    )
    result = generate_road_10k_plan(
        replace(
            generation_input,
            goal=replace(
                generation_input.goal,
                target_event_date=target_date,
            ),
            constraints=constraints,
        )
    )

    assert result.code == "no_schedule_within_envelope"
    assert result.plan is None


def test_distance_cap_is_required_and_preserved_per_workout() -> None:
    """Every generated workout carries the recent session-distance ceiling."""
    from analysis.road_10k_plan_generation import generate_road_10k_plan

    base_input = _input()
    missing_distance_cap = generate_road_10k_plan(
        _input(
            history=tuple(
                replace(observation, distance_km=None)
                for observation in base_input.history
            )
        )
    )

    assert missing_distance_cap.code == "insufficient_recent_history"
    assert "distance" in (
        missing_distance_cap.observed_or_stated_reason or ""
    ).casefold()

    result = generate_road_10k_plan(base_input)

    assert result.plan is not None
    recent_cap = result.history_statistics.recent_maximum_session_distance_km
    assert recent_cap == pytest.approx(12.0)
    for week in result.plan.weeks:
        for workout in week.workouts:
            assert workout.maximum_distance_ceiling_km == pytest.approx(
                recent_cap
            )
            assert workout.maximum_distance_ceiling_km <= recent_cap


def test_input_hash_tracks_intensity_source_provenance() -> None:
    """Changing split/sample provenance must change the replay hash."""
    from analysis.road_10k_plan_generation import (
        build_road_10k_training_pattern_snapshot,
        deterministic_input_hash,
    )

    base_input = _input()
    changed_sources = tuple(
        (activity_id, "activity_samples")
        for activity_id, _source in base_input.intensity_sources
    )
    changed_pattern = build_road_10k_training_pattern_snapshot(
        base_input.history,
        athlete_today=base_input.athlete_today,
        intensity_sources=changed_sources,
        reserved_dates=base_input.reserved_dates,
    )
    changed_input = replace(
        base_input,
        intensity_sources=changed_sources,
        training_pattern_snapshot_version=changed_pattern.version,
    )

    assert deterministic_input_hash(base_input) != deterministic_input_hash(
        changed_input
    )


def test_typed_outcomes_match_the_accepted_contract_and_fail_closed() -> None:
    """Each accepted road 10K code maps one-to-one to typed runtime fields."""
    from analysis.road_10k_contract import road_10k_typed_outcome

    expected = {
        "adult_scope_or_constraints_unconfirmed": {
            "route_state": "clarification_required",
            "plan_returned": False,
            "goal_remains_recorded": True,
        },
        "contradictory_input": {
            "route_state": "clarification_required",
            "plan_returned": False,
            "goal_remains_recorded": True,
        },
        "eligible_rolling_proposal": {
            "route_state": "plan_candidate",
            "plan_returned": True,
            "adoption_required": True,
        },
        "eligible_taper_proposal": {
            "route_state": "plan_candidate",
            "plan_returned": True,
            "adoption_required": True,
        },
        "insufficient_recent_history": {
            "route_state": "readiness_only",
            "plan_returned": False,
            "goal_remains_recorded": True,
        },
        "limited_guidance_event_conflict": {
            "route_state": "readiness_only",
            "plan_returned": False,
            "goal_remains_recorded": True,
            "limited_guidance_returned": True,
        },
        "limited_near_term_guidance": {
            "route_state": "readiness_only",
            "plan_returned": False,
            "goal_remains_recorded": True,
            "limited_guidance_returned": True,
        },
        "missing_or_stale_direct_baseline": {
            "route_state": "readiness_only",
            "plan_returned": False,
            "goal_remains_recorded": True,
        },
        "no_schedule_within_envelope": {
            "route_state": "readiness_only",
            "plan_returned": False,
            "goal_remains_recorded": True,
        },
        "safety_stop": {
            "route_state": "readiness_only",
            "plan_returned": False,
            "goal_remains_recorded": True,
        },
        "unsupported_intent_distance_surface_or_population": {
            "route_state": "policy_unavailable",
            "plan_returned": False,
            "goal_remains_recorded": True,
        },
        "validation_failed": {
            "route_state": "readiness_only",
            "plan_returned": False,
            "goal_remains_recorded": True,
        },
    }

    assert {
        code: road_10k_typed_outcome(code)
        for code in expected
    } == expected

    with pytest.raises(ValueError):
        road_10k_typed_outcome("unknown_result_code")


def _write_stage_authority(path) -> None:
    now = datetime.now(timezone.utc)
    payload = {
        "authority_digest": "",
        "stage_id": "road-10k-controlled-opt-in-v1",
        "capability_id": "outdoor_road_10k_performance_v1",
        "object_id": "road-10k-controlled-opt-in-foundation-v1",
        "work_contract_digest": "sha256:b2c668dc304e44407a743c8b8c2710cc6c133ac4106045986bfd1726d2a7725e",
        "route_digest": "sha256:a916feab2d029de3d6996933a7aece668670facc016f6abf8b932aa747af8214",
        "schema_version": "road-10k-stage-authority-v1",
        "control_schema_version": 2,
        "state": "active",
        "invitation_ceiling": 60,
        "exposure_ceiling": 30,
        "notice_digest": "sha256:" + "a" * 64,
        "cohort_rule_digest": "sha256:" + "b" * 64,
        "sampling_run_evidence_digest": "sha256:" + "c" * 64,
        "valid_from": (now - timedelta(minutes=1)).isoformat(),
        "valid_until": (now + timedelta(hours=1)).isoformat(),
        "heartbeat_at": now.isoformat(),
        "heartbeat_max_age_seconds": 300,
        "readiness": "ready",
        "provider_fence": "closed",
        "pause": False,
        "kill": False,
        "build_id": "2026.08.735",
    }
    encoded = json.dumps(
        {key: value for key, value in payload.items() if key != "authority_digest"},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    payload["authority_digest"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
    path.write_text(json.dumps(payload), encoding="utf-8")


def _rewrite_stage_authority_state(
    path: Path,
    *,
    state: str,
    pause: bool = False,
    kill: bool = False,
    build_id: str | None = None,
) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update({"state": state, "pause": pause, "kill": kill})
    if build_id is not None:
        payload["build_id"] = build_id
    encoded = json.dumps(
        {
            key: value
            for key, value in payload.items()
            if key != "authority_digest"
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    payload["authority_digest"] = "sha256:" + hashlib.sha256(encoded).hexdigest()
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_stage_authority_must_match_the_running_build(tmp_path, monkeypatch):
    from api.road_10k_stage_authority import load_stage_authority

    authority_path = tmp_path / "road-10k-authority.json"
    _write_stage_authority(authority_path)
    monkeypatch.setenv(
        "PRAXYS_ROAD_10K_STAGE_AUTHORITY_PATH",
        str(authority_path),
    )
    monkeypatch.setenv("PRAXYS_API_VERSION", "different-build")
    assert load_stage_authority() is None

    monkeypatch.setenv("PRAXYS_API_VERSION", "2026.08.735")
    assert load_stage_authority() is not None

    _rewrite_stage_authority_state(
        authority_path,
        state="active",
        build_id="develop",
    )
    monkeypatch.setenv("PRAXYS_API_VERSION", "develop")
    assert load_stage_authority() is None


class _MemoryManifestStore:
    def __init__(self):
        self.items: dict[str, bytes] = {}

    def put(self, key: str, payload: bytes) -> None:
        self.items[key] = payload

    def iter(self, prefix: str):
        for key, payload in list(self.items.items()):
            if key.startswith(prefix):
                yield key, payload

    def delete(self, key: str) -> None:
        self.items.pop(key, None)


def _fresh_road_10k_app(
    monkeypatch,
    *,
    authority: bool,
):
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )
    monkeypatch.setenv("PRAXYS_AUTH_RATE_LIMIT_DISABLED", "true")
    monkeypatch.setenv("PRAXYS_API_VERSION", "2026.08.735")

    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", os.path.join(tmpdir.name, "data"))
    if authority:
        authority_path = os.path.join(tmpdir.name, "road-10k-authority.json")
        _write_stage_authority(Path(authority_path))
        monkeypatch.setenv("PRAXYS_ROAD_10K_STAGE_AUTHORITY_PATH", authority_path)
    else:
        monkeypatch.delenv("PRAXYS_ROAD_10K_STAGE_AUTHORITY_PATH", raising=False)

    from db import session as db_session

    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    import api.main
    import api.road_10k_deletion_storage as deletion_storage

    importlib.reload(api.main)
    monkeypatch.setattr(deletion_storage, "_test_store", None)
    return api.main.app, db_session, tmpdir


def test_dormant_startup_succeeds_without_private_marker_storage(monkeypatch):
    from fastapi.testclient import TestClient

    app, db_session, tmpdir = _fresh_road_10k_app(monkeypatch, authority=False)
    try:
        with TestClient(app) as client:
            assert client.get("/api/health").status_code == 200
    finally:
        if db_session.engine is not None:
            db_session.engine.dispose()
        tmpdir.cleanup()


def test_hard_off_startup_and_readiness_do_not_touch_private_marker_storage(
    monkeypatch,
):
    from fastapi.testclient import TestClient
    from api import road_10k_control

    app, db_session, tmpdir = _fresh_road_10k_app(monkeypatch, authority=False)

    def unexpected(*_args, **_kwargs):
        raise AssertionError("private marker storage was touched without obligation")

    monkeypatch.setattr(road_10k_control, "private_marker_store_available", unexpected)
    try:
        with TestClient(app) as client:
            assert client.get("/api/health/ready").status_code == 200
    finally:
        if db_session.engine is not None:
            db_session.engine.dispose()
        tmpdir.cleanup()


def test_active_authority_without_obligation_stays_healthy_dormant(
    monkeypatch,
):
    from fastapi.testclient import TestClient
    from db.models import Road10KStageCounter

    app, db_session, tmpdir = _fresh_road_10k_app(monkeypatch, authority=True)
    try:
        with db_session.SessionLocal() as db:
            db.add(
                Road10KStageCounter(
                    stage_id="road-10k-controlled-opt-in-v1",
                    schema_version=2,
                    capability_id="outdoor_road_10k_performance_v1",
                    invitation_slots_consumed=0,
                    distinct_exposed_owners_consumed=0,
                    invitation_ceiling=60,
                    exposure_ceiling=30,
                )
            )
            db.commit()
        with TestClient(app) as client:
            assert client.get("/api/health/ready").status_code == 200
    finally:
        if db_session.engine is not None:
            db_session.engine.dispose()
        tmpdir.cleanup()


def test_startup_fails_for_inconsistent_existing_road_obligation(
    monkeypatch,
):
    from fastapi.testclient import TestClient
    from db.models import Road10KStageCounter

    app, db_session, tmpdir = _fresh_road_10k_app(
        monkeypatch,
        authority=False,
    )
    try:
        with db_session.SessionLocal() as db:
            db.add(
                Road10KStageCounter(
                    stage_id="road-10k-controlled-opt-in-v1",
                    schema_version=2,
                    capability_id="outdoor_road_10k_performance_v1",
                    invitation_slots_consumed=1,
                    distinct_exposed_owners_consumed=0,
                    invitation_ceiling=60,
                    exposure_ceiling=30,
                )
            )
            db.commit()
        with pytest.raises(Exception, match="counter_mismatch"):
            with TestClient(app):
                pass
    finally:
        if db_session.engine is not None:
            db_session.engine.dispose()
        tmpdir.cleanup()




def _road_10k_token(user_id: str) -> str:
    import jwt

    from api.auth_secrets import get_jwt_secret

    return jwt.encode(
        {
            "sub": user_id,
            "aud": "fastapi-users:auth",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        get_jwt_secret(),
        algorithm="HS256",
    )
































@pytest.fixture
def hard_off_road_client(monkeypatch):
    from fastapi.testclient import TestClient

    app, db_session, tmpdir = _fresh_road_10k_app(monkeypatch, authority=True)
    try:
        with TestClient(app) as client:
            yield client, db_session
    finally:
        if db_session.engine is not None:
            db_session.engine.dispose()
        tmpdir.cleanup()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/road-10k/access"),
        ("post", "/api/road-10k/opt-in"),
        ("post", "/api/plan/road-10k/readiness"),
        ("post", "/api/plan/road-10k/alternatives"),
        ("post", "/api/plan/road-10k/generate"),
        ("post", "/api/plan/road-10k/proposals/00000000-0000-4000-8000-000000000001/regenerate"),
        ("post", "/api/plan/road-10k/baseline/history/confirm"),
    ],
)
def test_hard_off_stage_routes_deny_before_auth_or_request_side_effects(
    hard_off_road_client,
    monkeypatch,
    method,
    path,
):
    import api.routes.road_10k as road_route
    import api.routes.road_10k_plan_generation as plan_route
    import api.road_10k_stage_authority as authority

    def unexpected(*_args, **_kwargs):
        raise AssertionError("hard-off route performed a request side effect")

    monkeypatch.setattr(authority, "load_stage_authority", unexpected)
    monkeypatch.setattr(road_route, "get_authenticated_identity", unexpected)
    monkeypatch.setattr(plan_route, "get_current_user_id", unexpected)
    client, _db_session = hard_off_road_client
    request = getattr(client, method)
    response = request(path) if method == "get" else request(path, json={})

    assert response.status_code == 404
    assert response.json().get("detail", "").casefold() == "not found"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["vary"] == "Authorization"


def test_hard_off_road_routes_are_absent_from_openapi(hard_off_road_client):
    client, _db_session = hard_off_road_client
    schema = client.get("/openapi.json").json()

    hidden_paths = {
        "/api/road-10k/access",
        "/api/road-10k/opt-in",
        "/api/plan/road-10k/readiness",
        "/api/plan/road-10k/alternatives",
        "/api/plan/road-10k/generate",
        "/api/plan/road-10k/proposals/{proposal_id}/regenerate",
        "/api/plan/road-10k/baseline/history/confirm",
    }
    assert hidden_paths.isdisjoint(schema["paths"])
    assert "/api/road-10k/withdraw" in schema["paths"]
    assert "/api/road-10k/export" in schema["paths"]
    components = schema.get("components", {}).get("schemas", {})
    assert "Road10KReadinessResponse" not in components
    assert "Road10KProposalResponse" not in components
    assert "Road10KExportResponse" in components


def test_hard_off_road_discovery_stays_hidden(hard_off_road_client):
    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
    from db.models import User

    client, db_session = hard_off_road_client
    with db_session.SessionLocal() as db:
        db.add(User(
            id="discovery-owner",
            email="discovery@example.test",
            hashed_password="x",
            terms_version=TERMS_VERSION,
            terms_digest=TERMS_CONTENT_DIGEST,
            terms_accepted_at=datetime.now(timezone.utc),
        ))
        db.commit()
    response = client.get(
        "/api/plan/generation/capabilities",
        headers={"Authorization": "Bearer " + _road_10k_token("discovery-owner")},
    )

    assert response.status_code == 200
    assert "road_10k" not in response.text
    assert "outdoor_road_10k" not in response.text


def test_first_party_owner_export_is_authority_independent_and_isolated(
    hard_off_road_client,
    monkeypatch,
):
    from db.models import Road10KOwnerStageReceipt, User

    client, db_session = hard_off_road_client
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with db_session.SessionLocal() as db:
        db.add_all(
            [
                User(id="owner-rights", email="owner-rights@example.test", hashed_password="x"),
                User(id="other-rights", email="other-rights@example.test", hashed_password="x"),
                User(id="demo-rights", email="demo-rights@example.test", hashed_password="x", is_demo=True),
                Road10KOwnerStageReceipt(
                    id="owner-rights-receipt",
                    user_id="owner-rights",
                    stage_id="road-10k-controlled-opt-in-v1",
                    capability_id="outdoor_road_10k_performance_v1",
                    schema_version=2,
                    policy_version="road-10k-plan-generation-policy-v2",
                    authority_digest="a" * 64,
                    notice_digest="b" * 64,
                    cohort_rule_digest="c" * 64,
                    sampling_run_evidence_digest="d" * 64,
                    invitation_idempotency_key="owner-rights-invitation",
                    state="invited_only",
                    invitation_issued_at=now,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        db.commit()

    import api.road_10k_control as control

    monkeypatch.setattr(
        control,
        "load_stage_authority",
        lambda: (_ for _ in ()).throw(AssertionError("authority file read")),
    )
    owner = client.get(
        "/api/road-10k/export",
        headers={"Authorization": "Bearer " + _road_10k_token("owner-rights")},
    )
    other = client.get(
        "/api/road-10k/export",
        headers={"Authorization": "Bearer " + _road_10k_token("other-rights")},
    )
    demo = client.get(
        "/api/road-10k/export",
        headers={"Authorization": "Bearer " + _road_10k_token("demo-rights")},
    )

    assert owner.status_code == 200
    assert owner.json()["receipt"]["state"] == "invited_only"
    assert other.status_code == 404
    assert demo.status_code == 403


def test_first_party_owner_withdrawal_is_authority_independent(
    hard_off_road_client,
    monkeypatch,
):
    from api import road_10k_deletion_storage
    from db.models import Road10KOwnerStageReceipt, User

    client, db_session = hard_off_road_client
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with db_session.SessionLocal() as db:
        db.add_all(
            [
                User(id="withdraw-rights", email="withdraw-rights@example.test", hashed_password="x"),
                Road10KOwnerStageReceipt(
                    id="withdraw-rights-receipt",
                    user_id="withdraw-rights",
                    stage_id="road-10k-controlled-opt-in-v1",
                    capability_id="outdoor_road_10k_performance_v1",
                    schema_version=2,
                    policy_version="road-10k-plan-generation-policy-v2",
                    authority_digest="a" * 64,
                    notice_digest="b" * 64,
                    cohort_rule_digest="c" * 64,
                    sampling_run_evidence_digest="d" * 64,
                    invitation_idempotency_key="withdraw-rights-invitation",
                    state="invited_only",
                    invitation_issued_at=now,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        db.commit()

    import api.road_10k_control as control

    monkeypatch.setattr(road_10k_deletion_storage, "_test_store", _MemoryManifestStore())
    monkeypatch.setattr(
        control,
        "load_stage_authority",
        lambda: (_ for _ in ()).throw(AssertionError("authority file read")),
    )
    response = client.post(
        "/api/road-10k/withdraw",
        headers={"Authorization": "Bearer " + _road_10k_token("withdraw-rights")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "outcome": "withdrawn",
        "rollout_status": "withdrawn",
        "plan_status": "unchanged",
    }
    with db_session.SessionLocal() as db:
        assert db.get(Road10KOwnerStageReceipt, "withdraw-rights-receipt").state == "withdrawn"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/road-10k/withdraw"),
        ("get", "/api/road-10k/export"),
    ],
)
def test_owner_data_rights_do_not_expose_stage_capability_anonymously(
    hard_off_road_client,
    monkeypatch,
    method,
    path,
):
    import api.road_10k_stage_authority as authority

    monkeypatch.setattr(
        authority,
        "load_stage_authority",
        lambda: (_ for _ in ()).throw(AssertionError("authority file read")),
    )
    client, _db_session = hard_off_road_client
    response = getattr(client, method)(path)

    assert response.status_code in {401, 403}
    assert "active" not in response.text.lower()
    assert "capability" not in response.text.lower()
