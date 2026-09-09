from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from decimal import getcontext
import hashlib
import math
import sys
from types import FrameType

import pytest

import analysis.non_ultra_trail_plan_generation as trail_generation
from analysis.non_ultra_trail_contract import (
    NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID,
    NON_ULTRA_TRAIL_CONTRACT,
    NON_ULTRA_TRAIL_CONTRACT_DIGEST,
    NON_ULTRA_TRAIL_COURSE_SCHEMA_ID,
    NON_ULTRA_TRAIL_DETAIL_REASON_CATALOG,
    NON_ULTRA_TRAIL_GENERATOR_VERSION,
    NON_ULTRA_TRAIL_MODULE_KEYS,
    NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT,
    NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT_DIGEST,
    NON_ULTRA_TRAIL_ONTOLOGY_DECISION_ID,
    NON_ULTRA_TRAIL_ONTOLOGY_SOURCE_DECISION_DIGEST,
    NON_ULTRA_TRAIL_ONTOLOGY_VERSION,
    NON_ULTRA_TRAIL_POLICY_VERSION,
    NON_ULTRA_TRAIL_REASON_PAIRS,
    NON_ULTRA_TRAIL_SCIENCE_DECISION_ID,
    NON_ULTRA_TRAIL_SOURCE_DECISION_DIGEST,
    NON_ULTRA_TRAIL_STATUS_PRECEDENCE,
)
from analysis.non_ultra_trail_plan_generation import (
    CONTROLLED_UPHILL_TEMPLATE,
    GeneratedNonUltraTrailPlan,
    NonUltraTrailGenerationInput,
    ProvenancedValue,
    RecentTrailHistoryStatistics,
    TrailCourseDemand,
    TrailEnvironmentContext,
    TrailFuelingContext,
    TrailGradeDistribution,
    TrailOptionalContext,
    TrailPlanGenerationConstraints,
    TrailPlanningDurationRange,
    TrailRunningHistoryObservation,
    TrailSupportContext,
    TrailWorkloadRequest,
    derive_recent_history_statistics,
    derive_revision_bindings,
    deterministic_input_hash,
    _dry_run_non_ultra_trail_plan,
    generate_non_ultra_trail_plan,
    serialize_generation_input,
    serialize_workout_structure,
    validate_generated_plan,
)


ATHLETE_TODAY = date(2026, 9, 3)
BLOCK_START = date(2026, 9, 7)


def _digest(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode()).hexdigest()}"


def _known(
    value: object,
    *,
    label: str = "fixture",
    provenance: str = "athlete_stated",
    confirmed_assumption: bool = False,
) -> ProvenancedValue:
    revision = _digest(label)
    return ProvenancedValue(
        state="known",
        provenance=provenance,
        source_revision=revision,
        value=value,
        assumption_confirmed_revision=(
            revision if confirmed_assumption else None
        ),
    )


def _unknown(label: str = "unknown") -> ProvenancedValue:
    return ProvenancedValue(
        state="unknown",
        provenance="unknown",
        source_revision=_digest(label),
    )


def _optional_context() -> TrailOptionalContext:
    return TrailOptionalContext(
        environment=TrailEnvironmentContext(
            maximum_altitude_m=_known(430, label="altitude"),
            temperature_min_c=_known(10.5, label="temperature-min"),
            temperature_max_c=_known(24.0, label="temperature-max"),
            humidity_min_pct=_known(45, label="humidity-min"),
            humidity_max_pct=_known(85, label="humidity-max"),
            sun_exposure=_known("mixed", label="sun"),
            wind_exposure=_known("mixed", label="wind"),
            conditions_basis=_known(
                "organizer_information", label="conditions-basis"
            ),
        ),
        support=TrailSupportContext(
            aid_support_mode=_known("organized_aid", label="aid-mode"),
            aid_station_count=_known(4, label="aid-count"),
            max_aid_station_gap_m=_known(6000, label="aid-gap"),
            water_availability=_known("all_stations", label="water"),
            food_availability=_known("some_stations", label="food"),
            mandatory_gear=_known(
                ("water_carry", "weather_shell"), label="gear"
            ),
        ),
        fueling=TrailFuelingContext(
            longest_practiced_duration_min=_known(180, label="fuel-duration"),
            practice_sessions_last_42_days=_known(4, label="fuel-sessions"),
            intake_form=_known("mixed_food_and_drink", label="intake"),
            gastrointestinal_experience=_known(
                "no_plan_altering_issue", label="gi"
            ),
        ),
    )


def _course() -> TrailCourseDemand:
    return TrailCourseDemand(
        event_id="event-ninghai-2026",
        event_date=_known(date(2026, 11, 15), label="event-date"),
        distance_meters=_known(24700, label="distance"),
        total_ascent_m=_known(618, label="ascent"),
        total_descent_m=_known(620, label="descent"),
        planning_duration_range=_known(
            TrailPlanningDurationRange(180, 300), label="duration-range"
        ),
        event_format=_known("single_day", label="event-format"),
        distance_family=_known("non_ultra", label="distance-family"),
        planning_intent=_known("performance", label="intent"),
        grade_distribution=_known(
            TrailGradeDistribution(500, 1500, 4000, 3000, 1000),
            label="grade",
        ),
        course_footing=_known(
            ("firm_smooth", "loose_gravel"), label="course-footing"
        ),
        hands_assist=_known(False, label="hands"),
        fixed_rope=_known(False, label="rope"),
        optional_context=_optional_context(),
    )


def _constraints() -> TrailPlanGenerationConstraints:
    return TrailPlanGenerationConstraints(
        available_weekdays=_known((2, 4, 6), label="weekdays"),
        weekly_time_limit_min=_known(240, label="weekly-time"),
        maximum_session_duration_min=_known(70, label="session-time"),
        unavailable_dates=_known((), label="unavailable"),
        preferred_longest_weekday=6,
        nontechnical_three_minute_uphill_access=_known(
            True, label="uphill-access"
        ),
        controlled_downhill_access=_known(True, label="downhill-access"),
        accessible_footing=_known(
            ("firm_smooth", "loose_gravel", "mud"),
            label="accessible-footing",
        ),
        adult_nonclinical_scope_confirmed=_known(True, label="adult"),
        performance_intent_confirmed=_known(True, label="performance"),
        current_symptom_stop=_known(False, label="symptom"),
    )


def _history() -> tuple[TrailRunningHistoryObservation, ...]:
    current_week_start = ATHLETE_TODAY - timedelta(days=ATHLETE_TODAY.weekday())
    first_week_start = current_week_start - timedelta(weeks=8)
    observations: list[TrailRunningHistoryObservation] = []
    for week in range(8):
        week_start = first_week_start + timedelta(weeks=week)
        for index, (offset, duration) in enumerate(((0, 40), (2, 50), (4, 60))):
            trail = index >= 1
            observed_date = week_start + timedelta(days=offset)
            observations.append(
                TrailRunningHistoryObservation(
                    activity_id=f"w{week}-{index}",
                    observed_date=observed_date,
                    activity_type="trail_running" if trail else "running",
                    duration_min=float(duration),
                    distance_km=float(duration) / 6,
                    elevation_gain_meters=(200 if index == 1 else 300)
                    if trail
                    else 50,
                    elevation_loss_meters=(180 if index == 1 else 280)
                    if trail
                    else 40,
                    observed_footing=("firm_smooth", "loose_gravel")
                    if trail
                    else None,
                    source_revision=_digest(f"activity-{week}-{index}"),
                    source_timestamp=datetime.combine(
                        observed_date, time(hour=12), tzinfo=timezone.utc
                    ),
                    outdoor_confirmed=True,
                )
            )
    return tuple(observations)


def _generation_input(
    *,
    course: TrailCourseDemand | None = None,
    constraints: TrailPlanGenerationConstraints | None = None,
    statistics: RecentTrailHistoryStatistics | None = None,
    workload_request: TrailWorkloadRequest | None = None,
    **changes: object,
) -> NonUltraTrailGenerationInput:
    course = course or _course()
    constraints = constraints or _constraints()
    statistics = statistics or derive_recent_history_statistics(
        _history(), athlete_today=ATHLETE_TODAY
    )
    value = NonUltraTrailGenerationInput(
        policy_version=NON_ULTRA_TRAIL_POLICY_VERSION,
        generator_version=NON_ULTRA_TRAIL_GENERATOR_VERSION,
        science_decision_id=NON_ULTRA_TRAIL_SCIENCE_DECISION_ID,
        contract_digest=NON_ULTRA_TRAIL_CONTRACT_DIGEST,
        source_decision_digest=NON_ULTRA_TRAIL_SOURCE_DECISION_DIGEST,
        ontology_version=NON_ULTRA_TRAIL_ONTOLOGY_VERSION,
        ontology_decision_id=NON_ULTRA_TRAIL_ONTOLOGY_DECISION_ID,
        ontology_contract_digest=NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT_DIGEST,
        ontology_source_decision_digest=(
            NON_ULTRA_TRAIL_ONTOLOGY_SOURCE_DECISION_DIGEST
        ),
        athlete_today=ATHLETE_TODAY,
        block_start=BLOCK_START,
        course_demand=course,
        history_statistics=statistics,
        constraints=constraints,
        revision_bindings=derive_revision_bindings(
            course_demand=course,
            constraints=constraints,
            history_statistics=statistics,
        ),
        workload_request=workload_request,
        synthetic_verification_only=True,
    )
    return replace(value, **changes)


def _reason_names(result: object) -> tuple[str, ...]:
    return tuple(reason.namespaced for reason in result.matching_reasons)  # type: ignore[attr-defined]


@contextmanager
def _record_schedule_returns() -> Iterator[list[object]]:
    """Observe the real scheduler without replacing its execution or result."""
    returns: list[object] = []
    schedule_code = trail_generation._build_schedule.__code__
    previous = sys.getprofile()

    def observe(frame: FrameType, event: str, result: object) -> None:
        if frame.f_code is schedule_code and event == "return":
            returns.append(result)

    sys.setprofile(observe)
    try:
        yield returns
    finally:
        sys.setprofile(previous)


def test_exact_v2_contracts_are_accepted_but_remain_inactive() -> None:
    assert NON_ULTRA_TRAIL_ONTOLOGY_DECISION_ID.endswith("-v2")
    assert NON_ULTRA_TRAIL_SCIENCE_DECISION_ID.endswith("-v2")
    assert NON_ULTRA_TRAIL_GENERATOR_VERSION.endswith("-v2")
    assert NON_ULTRA_TRAIL_COURSE_SCHEMA_ID == "trail_course_demand_v2"
    assert NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID == "non_ultra_trail_constraints_v2"
    assert str(NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT.decision_status) == "accepted"
    assert str(NON_ULTRA_TRAIL_CONTRACT.decision_status) == "accepted"
    assert str(NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT.runtime_state) == "inactive"
    assert str(NON_ULTRA_TRAIL_CONTRACT.runtime_state) == "inactive"
    assert (
        NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT.contract_digest
        == "sha256:0d3e4056e081e07bb52cbda15fc161ff9584a50f25f97f39fd513e1dad404c9c"
    )
    assert (
        NON_ULTRA_TRAIL_CONTRACT.contract_digest
        == "sha256:1952421299cb59ddfea00115b6824d3116bd6e5f9175741916aa6f1015f8f9f9"
    )


def test_v2_status_reason_and_module_catalog_is_exact_and_closed() -> None:
    assert NON_ULTRA_TRAIL_STATUS_PRECEDENCE == (
        "validation_failed",
        "policy_unavailable",
        "readiness_blocked",
        "clarification_required",
        "eligible_proposal",
    )
    assert len(NON_ULTRA_TRAIL_REASON_PAIRS) == 21
    assert NON_ULTRA_TRAIL_DETAIL_REASON_CATALOG["eligible_proposal"] == ()
    assert NON_ULTRA_TRAIL_MODULE_KEYS == (
        "grade_specificity",
        "technical_terrain",
        "environment_altitude",
        "fueling",
    )


def test_actual_inactive_entry_point_fails_closed_without_a_plan() -> None:
    with _record_schedule_returns() as schedules:
        result = generate_non_ultra_trail_plan(
            replace(_generation_input(), synthetic_verification_only=False)
        )
    assert len(schedules) == 1
    assert schedules[0] is not None
    assert result.status == "policy_unavailable"
    assert result.detail_reason == "policy_inactive"
    assert _reason_names(result) == ("policy_unavailable.policy_inactive",)
    assert result.plan is None
    assert result.inactive_dry_run is False
    assert all(
        module.state == "not_evaluated"
        and module.reason_target == "policy_unavailable.policy_inactive"
        for module in result.module_availability
    )


def test_explicit_synthetic_dry_run_preserves_14_day_v1_envelope() -> None:
    generation_input = _generation_input()
    first = _dry_run_non_ultra_trail_plan(generation_input)
    replay = _dry_run_non_ultra_trail_plan(generation_input)
    assert first == replay
    assert first.status == "eligible_proposal"
    assert first.detail_reason is None
    assert first.matching_reasons == ()
    assert first.inactive_dry_run is True
    assert first.plan is not None
    assert first.contract_runtime_state == "inactive"
    assert first.plan.contract_runtime_state == "inactive"
    assert first.plan.synthetic_verification_only is True
    assert first.plan.public_payload()["synthetic_verification_only"] is True
    assert first.plan.horizon_end == BLOCK_START + timedelta(days=13)
    assert first.plan.reassessment_dates == (BLOCK_START + timedelta(days=7),)
    assert validate_generated_plan(first.plan, generation_input) == ()
    assert len(first.plan.weeks) == 2
    for week in first.plan.weeks:
        assert len(week.workouts) == 3
        assert sum(item.planned_duration_min for item in week.workouts) == 150
        assert sum(item.intensity_bucket == "quality" for item in week.workouts) == 1
        assert week.weekly_ascent_ceiling_meters <= 500
        assert week.weekly_descent_ceiling_meters <= 460
        assert max(item.planned_duration_min for item in week.workouts) <= 60
        assert max(item.ascent_ceiling_meters for item in week.workouts) <= 300
        assert max(item.descent_ceiling_meters for item in week.workouts) <= 280
        assert all(item.activity_type == "trail_running" for item in week.workouts)


def test_synthetic_verification_is_private_and_requires_an_explicit_marker() -> None:
    assert not hasattr(trail_generation, "dry_run_non_ultra_trail_plan")
    unmarked = replace(
        _generation_input(),
        synthetic_verification_only=False,
    )
    with pytest.raises(ValueError, match="explicit marker"):
        _dry_run_non_ultra_trail_plan(unmarked)


def test_quality_template_is_exact_targetless_38_minutes() -> None:
    assert CONTROLLED_UPHILL_TEMPLATE.total_minutes == 38
    assert CONTROLLED_UPHILL_TEMPLATE.low_intensity_minutes == 26
    result = _dry_run_non_ultra_trail_plan(_generation_input())
    assert result.plan is not None
    quality = result.plan.weeks[0].workouts[1]
    structure = serialize_workout_structure(quality)
    assert quality.template_id == "trail-controlled-uphill-quality-v1"
    assert structure["steps"][1]["repetitions"] == 4
    assert all(
        step.get("target", {}).get("metric") in {None, "none"}
        for step in structure["steps"]
    )


def test_history_snapshot_separates_ascent_descent_and_footing() -> None:
    statistics = derive_recent_history_statistics(
        _history(), athlete_today=ATHLETE_TODAY
    )
    assert statistics.usable_completed_weeks == 8
    assert statistics.recent_modal_running_frequency == 3
    assert statistics.recent_median_usable_weekly_minutes == 150
    assert statistics.recent_median_usable_weekly_ascent_meters == 500
    assert statistics.recent_median_usable_weekly_descent_meters == 460
    assert statistics.recent_maximum_session_ascent_meters == 300
    assert statistics.recent_maximum_session_descent_meters == 280
    assert statistics.comparable_ascent_sessions_within_window > 2
    assert statistics.comparable_descent_sessions_within_window > 2
    assert statistics.recently_observed_footing == (
        "firm_smooth",
        "loose_gravel",
    )
    assert statistics.observation_window_start is not None
    assert statistics.observation_window_end == ATHLETE_TODAY - timedelta(days=1)
    assert statistics.source_revision_fingerprint.startswith("sha256:")
    assert "activity_id" not in statistics.public_payload()


def test_history_revision_changes_when_source_revision_changes_at_same_totals() -> None:
    history = _history()
    first = derive_recent_history_statistics(
        history,
        athlete_today=ATHLETE_TODAY,
    )
    corrected = (
        replace(history[0], source_revision=_digest("corrected-source")),
        *history[1:],
    )
    second = derive_recent_history_statistics(
        corrected,
        athlete_today=ATHLETE_TODAY,
    )

    assert first.source_revision_fingerprint != (
        second.source_revision_fingerprint
    )
    assert replace(
        first,
        source_revision_fingerprint=second.source_revision_fingerprint,
    ) == second
    first_bindings = derive_revision_bindings(
        course_demand=_course(),
        constraints=_constraints(),
        history_statistics=first,
    )
    second_bindings = derive_revision_bindings(
        course_demand=_course(),
        constraints=_constraints(),
        history_statistics=second,
    )
    assert first_bindings.history_revision != second_bindings.history_revision
    assert first_bindings.composite_revision != (
        second_bindings.composite_revision
    )


def test_history_derivation_rejects_duplicate_unstamped_and_nonfinite_input() -> None:
    history = _history()
    with pytest.raises(ValueError, match="duplicate_activity_id"):
        derive_recent_history_statistics(
            (*history, history[-1]), athlete_today=ATHLETE_TODAY
        )
    with pytest.raises(ValueError, match="history_observation"):
        derive_recent_history_statistics(
            (replace(history[0], source_timestamp=None), *history[1:]),  # type: ignore[arg-type]
            athlete_today=ATHLETE_TODAY,
        )
    with pytest.raises(ValueError, match="history_observation"):
        derive_recent_history_statistics(
            (replace(history[0], duration_min=math.nan), *history[1:]),
            athlete_today=ATHLETE_TODAY,
        )


def test_every_receipt_preserves_precedence_and_all_safe_matching_reasons() -> None:
    course = replace(
        _course(),
        event_format=_known("multi_day", label="multi"),
        hands_assist=_known(True, label="hands-true"),
    )
    constraints = replace(
        _constraints(),
        current_symptom_stop=_known(True, label="symptom-true"),
        controlled_downhill_access=_known(False, label="no-downhill"),
    )
    statistics = replace(
        derive_recent_history_statistics(_history(), athlete_today=ATHLETE_TODAY),
        comparable_descent_sessions_within_window=0,
        latest_comparable_descent_session_date=None,
    )
    result = _dry_run_non_ultra_trail_plan(
        _generation_input(
            course=course, constraints=constraints, statistics=statistics
        )
    )
    assert result.status == "policy_unavailable"
    assert result.detail_reason == "unsupported_ultra_or_multiday"
    assert _reason_names(result) == (
        "policy_unavailable.unsupported_ultra_or_multiday",
        "policy_unavailable.technical_features_outside_v2",
        "readiness_blocked.insufficient_descent_history",
        "readiness_blocked.insufficient_terrain_access",
        "readiness_blocked.current_symptom_stop",
    )
    assert all(
        item.reason_target
        == "policy_unavailable.unsupported_ultra_or_multiday"
        for item in result.module_availability
    )


@pytest.mark.parametrize(
    ("field_name", "value", "expected"),
    [
        ("event_format", "multi_day", "unsupported_ultra_or_multiday"),
        ("distance_family", "ultra", "unsupported_ultra_or_multiday"),
        ("planning_intent", "first_completion", "unsupported_population_or_intent"),
        ("hands_assist", True, "technical_features_outside_v2"),
        ("fixed_rope", True, "technical_features_outside_v2"),
    ],
)
def test_policy_scope_reasons_are_exact(
    field_name: str, value: object, expected: str
) -> None:
    course = replace(_course(), **{field_name: _known(value, label=field_name)})
    result = _dry_run_non_ultra_trail_plan(_generation_input(course=course))
    assert result.status == "policy_unavailable"
    assert result.detail_reason == expected
    assert result.plan is None


def test_core_unknown_assumption_and_missing_constraints_are_distinct() -> None:
    course = replace(_course(), total_descent_m=_unknown("unknown-descent"))
    result = _dry_run_non_ultra_trail_plan(_generation_input(course=course))
    assert result.status == "clarification_required"
    assert result.detail_reason == "material_course_demand_unknown"

    context = _optional_context()
    assumption = _known(
        "athlete_assumption",
        label="assumed-conditions",
        provenance="explicit_assumption",
    )
    context = replace(
        context,
        environment=replace(context.environment, conditions_basis=assumption),
    )
    result = _dry_run_non_ultra_trail_plan(
        _generation_input(course=replace(_course(), optional_context=context))
    )
    assert result.detail_reason == "assumption_confirmation_required"

    constraints = replace(
        _constraints(),
        controlled_downhill_access=_unknown("unknown-downhill-access"),
    )
    result = _dry_run_non_ultra_trail_plan(
        _generation_input(constraints=constraints)
    )
    assert result.detail_reason == "training_constraints_missing"


def test_non_core_unknowns_limit_exactly_four_modules() -> None:
    context = _optional_context()
    context = TrailOptionalContext(
        environment=TrailEnvironmentContext(
            *(_unknown(f"environment-{index}") for index in range(8))
        ),
        support=TrailSupportContext(
            *(_unknown(f"support-{index}") for index in range(6))
        ),
        fueling=TrailFuelingContext(
            *(_unknown(f"fueling-{index}") for index in range(4))
        ),
    )
    course = replace(
        _course(),
        grade_distribution=_unknown("grade-unknown"),
        course_footing=_unknown("footing-unknown"),
        optional_context=context,
    )
    result = _dry_run_non_ultra_trail_plan(_generation_input(course=course))
    assert result.status == "eligible_proposal"
    assert result.limited_modules == (
        "environment_altitude",
        "fueling",
        "grade_specificity",
        "technical_terrain",
    )
    assert tuple(item.state for item in result.module_availability) == (
        "limited",
        "limited",
        "limited",
        "limited",
    )
    assert tuple(item.reason_target for item in result.module_availability) == (
        "course.grade_distribution",
        "course.course_footing",
        "course.optional_context.environment",
        "course.optional_context.support",
    )


def test_grade_and_footing_validation_is_strict_and_order_independent() -> None:
    invalid_grade = replace(
        _course(),
        grade_distribution=_known(
            TrailGradeDistribution(500, 1500, 4000, 3000, 999),
            label="invalid-grade",
        ),
    )
    result = _dry_run_non_ultra_trail_plan(
        _generation_input(course=invalid_grade)
    )
    assert result.status == "validation_failed"
    assert result.detail_reason == "invalid_field_value"

    first = _generation_input()
    course = replace(
        first.course_demand,
        course_footing=_known(
            ("loose_gravel", "firm_smooth"), label="course-footing"
        ),
    )
    constraints = replace(
        first.constraints,
        available_weekdays=_known((6, 2, 4), label="weekdays"),
        accessible_footing=_known(
            ("mud", "loose_gravel", "firm_smooth"),
            label="accessible-footing",
        ),
    )
    reordered = _generation_input(
        course=course,
        constraints=constraints,
        statistics=first.history_statistics,
    )
    assert deterministic_input_hash(first) == deterministic_input_hash(reordered)


def test_footing_containment_distinguishes_access_from_observed_history() -> None:
    rocky = replace(
        _course(),
        course_footing=_known(("rocks_or_roots",), label="rocky-course"),
    )
    result = _dry_run_non_ultra_trail_plan(_generation_input(course=rocky))
    assert "readiness_blocked.insufficient_terrain_access" in _reason_names(result)
    assert (
        "readiness_blocked.insufficient_comparable_trail_history"
        in _reason_names(result)
    )

    constraints = replace(
        _constraints(),
        accessible_footing=_known(
            ("firm_smooth", "loose_gravel", "rocks_or_roots"),
            label="rock-access",
        ),
    )
    result = _dry_run_non_ultra_trail_plan(
        _generation_input(course=rocky, constraints=constraints)
    )
    assert "readiness_blocked.insufficient_terrain_access" not in _reason_names(
        result
    )
    assert result.detail_reason == "insufficient_comparable_trail_history"


def test_running_ascent_and_descent_history_have_separate_blockers() -> None:
    base = derive_recent_history_statistics(_history(), athlete_today=ATHLETE_TODAY)
    cases = (
        (
            replace(base, usable_completed_weeks=0, latest_run_date=None),
            "insufficient_recent_running_history",
        ),
        (
            replace(
                base,
                comparable_ascent_sessions_within_window=0,
                latest_comparable_ascent_session_date=None,
            ),
            "insufficient_comparable_trail_history",
        ),
        (
            replace(
                base,
                comparable_descent_sessions_within_window=0,
                latest_comparable_descent_session_date=None,
            ),
            "insufficient_descent_history",
        ),
    )
    for statistics, detail in cases:
        result = _dry_run_non_ultra_trail_plan(
            _generation_input(statistics=statistics)
        )
        assert result.status == "readiness_blocked"
        assert detail in tuple(reason.detail_reason for reason in result.matching_reasons)


def test_stale_revision_and_v1_v2_mix_fail_closed() -> None:
    generation_input = _generation_input()
    changed_course = replace(
        generation_input.course_demand,
        distance_meters=_known(24701, label="changed-distance"),
    )
    stale = replace(generation_input, course_demand=changed_course)
    result = _dry_run_non_ultra_trail_plan(stale)
    assert result.status == "clarification_required"
    assert result.detail_reason == "stale_confirmation_or_source_revision"

    mixed = replace(
        _generation_input(),
        policy_version="non-ultra-trail-plan-generation-policy-v1",
        ontology_decision_id="sdr-trail-running-goal-ontology-v1",
        course_demand=replace(_course(), schema_id="trail_course_demand_v1"),
    )
    result = _dry_run_non_ultra_trail_plan(mixed)
    assert result.status == "validation_failed"
    assert _reason_names(result)[:2] == (
        "validation_failed.schema_version_mismatch",
        "policy_unavailable.policy_inactive",
    )
    assert result.plan is None


def test_assumption_confirmation_does_not_change_value_revision() -> None:
    generation_input = _generation_input()
    course = generation_input.course_demand
    unconfirmed_basis = _known(
        "athlete_assumption",
        label="athlete-assumption",
        provenance="explicit_assumption",
    )
    unconfirmed_course = replace(
        course,
        optional_context=replace(
            course.optional_context,
            environment=replace(
                course.optional_context.environment,
                conditions_basis=unconfirmed_basis,
            ),
        ),
    )
    confirmed_course = replace(
        unconfirmed_course,
        optional_context=replace(
            unconfirmed_course.optional_context,
            environment=replace(
                unconfirmed_course.optional_context.environment,
                conditions_basis=replace(
                    unconfirmed_basis,
                    assumption_confirmed_revision=(
                        unconfirmed_basis.source_revision
                    ),
                ),
            ),
        ),
    )

    before = derive_revision_bindings(
        course_demand=unconfirmed_course,
        constraints=generation_input.constraints,
        history_statistics=generation_input.history_statistics,
        confirmed=False,
    )
    after = derive_revision_bindings(
        course_demand=confirmed_course,
        constraints=generation_input.constraints,
        history_statistics=generation_input.history_statistics,
        confirmed=False,
    )

    assert before == after


def test_malformed_revision_preserves_safe_scope_and_inactive_reasons() -> None:
    course = replace(
        _course(),
        event_format=_known("multi_day", label="malformed-multi-day"),
    )
    generation_input = _generation_input(course=course)
    malformed = replace(
        generation_input,
        revision_bindings=replace(
            generation_input.revision_bindings,
            course_revision="malformed",
        ),
    )
    synthetic = _dry_run_non_ultra_trail_plan(malformed)
    assert synthetic.status == "validation_failed"
    assert _reason_names(synthetic) == (
        "validation_failed.invalid_field_value",
        "policy_unavailable.unsupported_ultra_or_multiday",
    )

    actual = generate_non_ultra_trail_plan(
        replace(malformed, synthetic_verification_only=False)
    )
    assert actual.status == "validation_failed"
    assert actual.detail_reason == "invalid_field_value"
    assert _reason_names(actual) == (
        "validation_failed.invalid_field_value",
        "policy_unavailable.policy_inactive",
        "policy_unavailable.unsupported_ultra_or_multiday",
    )
    assert actual.plan is None

    infeasible = _generation_input(
        constraints=replace(
            _constraints(),
            maximum_session_duration_min=_known(37, label="short-session"),
        ),
        synthetic_verification_only=False,
    )
    with _record_schedule_returns() as schedules:
        actual = generate_non_ultra_trail_plan(replace(
            infeasible,
            revision_bindings=replace(
                infeasible.revision_bindings, course_revision="malformed",
            ),
        ))
    assert schedules == [None]
    assert _reason_names(actual) == (
        "validation_failed.invalid_field_value",
        "policy_unavailable.policy_inactive",
        "readiness_blocked.no_schedule_within_envelope",
    )
    assert actual.plan is None
    assert actual.inactive_dry_run is False


def test_adult_scope_unknown_and_contradictory_input_have_explicit_triggers() -> None:
    constraints = replace(
        _constraints(),
        adult_nonclinical_scope_confirmed=_unknown("adult-unknown"),
    )
    result = _dry_run_non_ultra_trail_plan(
        _generation_input(constraints=constraints)
    )
    assert result.status == "clarification_required"
    assert result.detail_reason == "adult_scope_or_constraints_unconfirmed"

    contradictory = replace(
        _constraints(),
        preferred_longest_weekday=1,
    )
    result = _dry_run_non_ultra_trail_plan(
        _generation_input(constraints=contradictory)
    )
    assert result.status == "clarification_required"
    assert result.detail_reason == "contradictory_input"

    for constraints, block_start in (
        (contradictory, BLOCK_START),
        (_constraints(), ATHLETE_TODAY - timedelta(days=1)),
    ):
        actual = generate_non_ultra_trail_plan(_generation_input(
            constraints=constraints,
            block_start=block_start,
            synthetic_verification_only=False,
        ))
        assert "clarification_required.contradictory_input" in _reason_names(actual)
        assert actual.status == "policy_unavailable"
        assert actual.detail_reason == "policy_inactive"
        assert actual.plan is None
        assert actual.inactive_dry_run is False


def test_explicit_workload_above_history_is_clarification_not_progression() -> None:
    result = _dry_run_non_ultra_trail_plan(
        _generation_input(
            workload_request=TrailWorkloadRequest(weekly_running_minutes=999)
        )
    )
    assert result.status == "clarification_required"
    assert result.detail_reason == "training_constraints_outside_history_envelope"
    assert result.plan is None


def test_event_window_and_no_schedule_are_canonical_policy_and_readiness_results() -> None:
    near_event = replace(
        _course(),
        event_date=_known(BLOCK_START + timedelta(days=14), label="near-event"),
    )
    result = _dry_run_non_ultra_trail_plan(
        _generation_input(course=near_event)
    )
    assert result.status == "policy_unavailable"
    assert result.detail_reason == "event_inside_unapproved_taper_window"

    constraints = replace(
        _constraints(),
        maximum_session_duration_min=_known(37, label="short-session"),
    )
    result = _dry_run_non_ultra_trail_plan(
        _generation_input(constraints=constraints)
    )
    assert result.status == "readiness_blocked"
    assert result.detail_reason == "no_schedule_within_envelope"

    with _record_schedule_returns() as schedules:
        actual = generate_non_ultra_trail_plan(_generation_input(
            constraints=constraints,
            synthetic_verification_only=False,
        ))
    assert schedules == [None]
    assert _reason_names(actual) == (
        "policy_unavailable.policy_inactive",
        "readiness_blocked.no_schedule_within_envelope",
    )
    assert actual.plan is None
    assert actual.inactive_dry_run is False


@pytest.mark.parametrize(
    ("group", "field"),
    [
        ("course", "event_date"),
        ("constraints", "available_weekdays"),
        ("constraints", "weekly_time_limit_min"),
        ("constraints", "maximum_session_duration_min"),
        ("constraints", "unavailable_dates"),
    ],
)
def test_normal_inactive_entry_skips_schedule_for_each_unknown_prerequisite(
    group: str, field: str,
) -> None:
    course = _course()
    constraints = _constraints()
    if group == "course":
        course = replace(course, **{field: _unknown(field)})
    else:
        constraints = replace(constraints, **{field: _unknown(field)})
    with _record_schedule_returns() as schedules:
        result = generate_non_ultra_trail_plan(_generation_input(
            course=course,
            constraints=constraints,
            synthetic_verification_only=False,
        ))
    assert schedules == []
    clarification = (
        "material_course_demand_unknown"
        if group == "course" else "training_constraints_missing"
    )
    assert _reason_names(result) == (
        "policy_unavailable.policy_inactive",
        f"clarification_required.{clarification}",
    )
    assert result.plan is None
    assert result.inactive_dry_run is False


def test_normal_inactive_entry_skips_schedule_for_invalid_session_domain() -> None:
    constraints = replace(
        _constraints(),
        maximum_session_duration_min=_known(0, label="invalid-session"),
    )
    with _record_schedule_returns() as schedules:
        result = generate_non_ultra_trail_plan(_generation_input(
            constraints=constraints,
            synthetic_verification_only=False,
        ))
    assert schedules == []
    assert _reason_names(result) == (
        "validation_failed.invalid_field_value",
        "policy_unavailable.policy_inactive",
    )
    assert result.plan is None
    assert result.inactive_dry_run is False


def test_plan_validator_binds_contract_receipt_revisions_and_workouts() -> None:
    generation_input = _generation_input()
    result = _dry_run_non_ultra_trail_plan(generation_input)
    assert result.plan is not None
    plan = result.plan
    candidates: tuple[tuple[GeneratedNonUltraTrailPlan, str], ...] = (
        (replace(plan, policy_version="v1"), "policy_version"),
        (replace(plan, generator_version="v1"), "generator_version"),
        (
            replace(plan, ontology_contract_digest="sha256:" + "0" * 64),
            "ontology_contract_digest",
        ),
        (
            replace(plan, readiness_receipt_digest="sha256:" + "0" * 64),
            "readiness_receipt_digest",
        ),
        (
            replace(plan, revision_bindings=replace(
                plan.revision_bindings,
                composite_revision="sha256:" + "0" * 64,
            )),
            "revision_bindings",
        ),
    )
    for candidate, rule in candidates:
        assert rule in {
            value.rule_id
            for value in validate_generated_plan(candidate, generation_input)
        }
    first_week = plan.weeks[0]
    first_workout = first_week.workouts[0]
    tampered = replace(
        plan,
        weeks=(
            replace(
                first_week,
                workouts=(
                    replace(first_workout, activity_type="running"),  # type: ignore[arg-type]
                    *first_week.workouts[1:],
                ),
            ),
            plan.weeks[1],
        ),
    )
    assert "activity_type" in {
        value.rule_id for value in validate_generated_plan(tampered, generation_input)
    }


def test_replay_binds_course_ascent_descent_and_source_revisions_separately() -> None:
    base = _generation_input()
    hashes = {deterministic_input_hash(base)}
    for field_name, value in (("total_ascent_m", 619), ("total_descent_m", 621)):
        course = replace(
            base.course_demand,
            **{field_name: _known(value, label=f"changed-{field_name}")},
        )
        hashes.add(deterministic_input_hash(_generation_input(course=course)))
    changed_source = replace(
        base.course_demand,
        distance_meters=replace(
            base.course_demand.distance_meters,
            source_revision=_digest("new-distance-source"),
        ),
    )
    hashes.add(deterministic_input_hash(_generation_input(course=changed_source)))
    assert len(hashes) == 4


def test_large_integer_and_decimal_context_do_not_escape_or_change_history() -> None:
    history = _history()
    original_precision = getcontext().prec
    try:
        getcontext().prec = 2
        low_precision = derive_recent_history_statistics(
            history, athlete_today=ATHLETE_TODAY
        )
        getcontext().prec = 50
        high_precision = derive_recent_history_statistics(
            tuple(reversed(history)), athlete_today=ATHLETE_TODAY
        )
    finally:
        getcontext().prec = original_precision
    assert low_precision == high_precision

    huge = 10**10000
    generation_input = _generation_input()
    course = replace(
        generation_input.course_demand,
        distance_meters=_known(huge, label="huge-distance"),
    )
    result = _dry_run_non_ultra_trail_plan(
        replace(generation_input, course_demand=course)
    )
    assert result.status == "validation_failed"
    assert result.detail_reason == "invalid_field_value"


def test_serialized_replay_contains_no_raw_history_or_provider_identifier() -> None:
    payload = serialize_generation_input(_generation_input())
    assert "history_statistics" in payload
    assert "history" not in payload
    rendered = repr(payload)
    assert "activity_id" not in rendered
    assert "provider" not in rendered
    assert payload["generator_version"].endswith("-v2")
