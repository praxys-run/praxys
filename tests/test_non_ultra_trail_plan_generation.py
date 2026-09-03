from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone

import pytest

from analysis.non_ultra_trail_contract import (
    NON_ULTRA_TRAIL_CONTRACT,
    NON_ULTRA_TRAIL_CONTRACT_DIGEST,
    NON_ULTRA_TRAIL_COURSE_SCHEMA_ID,
    NON_ULTRA_TRAIL_GUARDRAILS,
    NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT,
    NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT_DIGEST,
    NON_ULTRA_TRAIL_ONTOLOGY_DECISION_ID,
    NON_ULTRA_TRAIL_ONTOLOGY_SOURCE_DECISION_DIGEST,
    NON_ULTRA_TRAIL_POLICY_VERSION,
    NON_ULTRA_TRAIL_SCIENCE_DECISION_ID,
    NON_ULTRA_TRAIL_SOURCE_DECISION_DIGEST,
)
from analysis.non_ultra_trail_plan_generation import (
    CONTROLLED_UPHILL_TEMPLATE,
    GeneratedNonUltraTrailPlan,
    InternalTrailPrevalidation,
    NonUltraTrailGenerationInput,
    NonUltraTrailGoal,
    ProvenancedValue,
    TrailCourseDemand,
    TrailPlanGenerationConstraints,
    TrailRunningHistoryObservation,
    derive_recent_history_statistics,
    deterministic_input_hash,
    generate_non_ultra_trail_plan,
    serialize_workout_structure,
    validate_generated_plan,
)


ATHLETE_TODAY = date(2026, 9, 3)
BLOCK_START = date(2026, 9, 7)


def _known(value: object) -> ProvenancedValue:
    return ProvenancedValue(
        value=value,
        provenance="athlete_stated",
        source_reference="owner-review",
        source_timestamp=ATHLETE_TODAY,
        athlete_confirmed=True,
    )


def _unknown() -> ProvenancedValue:
    return ProvenancedValue(value=None, provenance="unknown")


def _course() -> TrailCourseDemand:
    return TrailCourseDemand(
        expected_duration_seconds=_known(10_800),
        distance_meters=_known(24_700),
        elevation_gain_meters=_known(618),
        elevation_loss_meters=_known(620),
        grade_distribution=_known({"reference": "course-profile-v1"}),
        technicality=_known({"reference": "course-technicality-v1"}),
        maximum_altitude_meters=_known(430),
        environmental_demand=_known({"reference": "event-conditions-v1"}),
        aid_and_support=_known({"reference": "event-support-v1"}),
        training_terrain_access=_known({"reference": "owner-access-v1"}),
        recent_downhill_exposure=_known({"reference": "history-v1"}),
        fueling_practice_experience=_known({"reference": "practice-v1"}),
        athlete_confirmed=True,
    )


def _history() -> tuple[TrailRunningHistoryObservation, ...]:
    current_week_start = ATHLETE_TODAY - timedelta(days=ATHLETE_TODAY.weekday())
    first_week_start = current_week_start - timedelta(weeks=8)
    observations: list[TrailRunningHistoryObservation] = []
    for week in range(8):
        week_start = first_week_start + timedelta(weeks=week)
        schedule = ((0, 40), (2, 50), (4, 60))
        for index, (offset, duration) in enumerate(schedule):
            trail = index >= 1
            observed_date = week_start + timedelta(days=offset)
            observations.append(
                TrailRunningHistoryObservation(
                    activity_id=f"w{week}-{index}",
                    observed_date=observed_date,
                    activity_type="trail_running" if trail else "running",
                    duration_min=float(duration),
                    distance_km=float(duration) / 6,
                    elevation_gain_meters=(200 if index == 1 else 300) if trail else 50,
                    elevation_loss_meters=(180 if index == 1 else 280) if trail else 40,
                    source="garmin",
                    source_timestamp=datetime.combine(
                        observed_date,
                        time(hour=12),
                        tzinfo=timezone.utc,
                    ),
                    outdoor_confirmed=True,
                )
            )
    return tuple(observations)


def _generation_input(**changes: object) -> NonUltraTrailGenerationInput:
    value = NonUltraTrailGenerationInput(
        policy_version=NON_ULTRA_TRAIL_POLICY_VERSION,
        science_decision_id=NON_ULTRA_TRAIL_SCIENCE_DECISION_ID,
        contract_digest=NON_ULTRA_TRAIL_CONTRACT_DIGEST,
        source_decision_digest=NON_ULTRA_TRAIL_SOURCE_DECISION_DIGEST,
        ontology_decision_id=NON_ULTRA_TRAIL_ONTOLOGY_DECISION_ID,
        ontology_contract_digest=NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT_DIGEST,
        ontology_source_decision_digest=(
            NON_ULTRA_TRAIL_ONTOLOGY_SOURCE_DECISION_DIGEST
        ),
        athlete_today=ATHLETE_TODAY,
        block_start=BLOCK_START,
        goal=NonUltraTrailGoal(
            intent="performance",
            event_format="single_day",
            distance_family="non_ultra",
            target_event_date=date(2026, 11, 15),
            event_confirmed=True,
        ),
        course_demand=_course(),
        history=_history(),
        constraints=TrailPlanGenerationConstraints(
            adult_confirmed=True,
            current_symptom_stop=False,
            available_weekdays=(1, 3, 5),
            weekly_time_limit_min=240,
            maximum_session_duration_min=70,
            preferred_longest_easy_weekday=5,
        ),
        prevalidation=InternalTrailPrevalidation(
            course_demand_eligible=True,
            terrain_access_eligible=True,
            nontechnical_uphill_accessible=True,
            training_terrain_reference="owner-access-v1",
            technical_terrain_module_supported=True,
        ),
    )
    return replace(value, **changes)


def test_contracts_are_exactly_bound_and_remain_inactive() -> None:
    assert NON_ULTRA_TRAIL_CONTRACT.contract_digest == NON_ULTRA_TRAIL_CONTRACT_DIGEST
    assert (
        NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT.contract_digest
        == NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT_DIGEST
    )
    assert str(NON_ULTRA_TRAIL_CONTRACT.runtime_state) == "inactive"
    assert str(NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT.runtime_state) == "inactive"
    assert NON_ULTRA_TRAIL_COURSE_SCHEMA_ID == "trail_course_demand_v1"
    assert NON_ULTRA_TRAIL_GUARDRAILS.committed_proposal_days == 14
    assert NON_ULTRA_TRAIL_GUARDRAILS.advisory_reassessment_after_completed_days == 7


def test_quality_template_is_exact_targetless_38_minute_contract() -> None:
    assert CONTROLLED_UPHILL_TEMPLATE.total_minutes == 38
    assert CONTROLLED_UPHILL_TEMPLATE.low_intensity_minutes == 26
    input_value = _generation_input()
    workout = generate_non_ultra_trail_plan(input_value).plan.weeks[0].workouts[1]
    structure = serialize_workout_structure(workout)
    assert workout.template_id == "trail-controlled-uphill-quality-v1"
    assert structure["steps"][1]["repetitions"] == 4
    assert all(
        step.get("target", {}).get("metric") in {None, "none"}
        for step in structure["steps"]
    )


def test_history_uses_all_runs_but_only_unambiguous_trail_for_vertical() -> None:
    history = list(_history())
    history.append(
        TrailRunningHistoryObservation(
            activity_id="ambiguous",
            observed_date=ATHLETE_TODAY - timedelta(days=2),
            activity_type="running",
            duration_min=60,
            distance_km=8,
            elevation_gain_meters=999,
            elevation_loss_meters=999,
            source="garmin",
            source_timestamp=datetime(
                2026,
                9,
                1,
                12,
                tzinfo=timezone.utc,
            ),
            outdoor_confirmed=True,
        )
    )
    history.append(
        TrailRunningHistoryObservation(
            activity_id="unknown-loss",
            observed_date=ATHLETE_TODAY - timedelta(days=1),
            activity_type="trail_running",
            duration_min=60,
            distance_km=8,
            elevation_gain_meters=999,
            elevation_loss_meters=None,
            source="garmin",
            source_timestamp=datetime(
                2026,
                9,
                2,
                12,
                tzinfo=timezone.utc,
            ),
            outdoor_confirmed=True,
        )
    )
    statistics = derive_recent_history_statistics(history, athlete_today=ATHLETE_TODAY)
    assert statistics.usable_completed_weeks == 8
    assert statistics.recent_modal_running_frequency == 3
    assert statistics.recent_median_usable_weekly_minutes == 150
    assert statistics.recent_median_usable_weekly_ascent_meters == 500
    assert statistics.recent_median_usable_weekly_descent_meters == 460
    assert statistics.recent_maximum_session_ascent_meters == 300
    assert statistics.latest_run_date == ATHLETE_TODAY - timedelta(days=1)
    assert statistics.comparable_trail_sessions_within_window == 11


def test_duplicate_activity_ids_cannot_inflate_history() -> None:
    history = _history()
    duplicate = replace(
        history[-1],
        observed_date=ATHLETE_TODAY - timedelta(days=1),
    )
    result = generate_non_ultra_trail_plan(
        _generation_input(history=(*history, duplicate))
    )
    assert result.code == "validation_failed"
    assert result.uncertainty_or_missing_field == "history.duplicate_activity_id"


def test_history_requires_typed_source_timestamp_and_outdoor_confirmation() -> None:
    missing_timestamp = replace(
        _history()[0],
        source_timestamp=None,  # type: ignore[arg-type]
    )
    result = generate_non_ultra_trail_plan(
        _generation_input(history=(missing_timestamp, *_history()[1:]))
    )
    assert result.code == "validation_failed"
    assert result.uncertainty_or_missing_field == "history_observation"

    indoor_history = tuple(
        replace(item, outdoor_confirmed=False) for item in _history()
    )
    result = generate_non_ultra_trail_plan(
        _generation_input(history=indoor_history)
    )
    assert result.code == "insufficient_comparable_history"
    assert result.detail_reason == "insufficient_recent_history"


def test_eligible_generation_is_deterministic_and_within_every_cap() -> None:
    generation_input = _generation_input()
    first = generate_non_ultra_trail_plan(generation_input)
    replay = generate_non_ultra_trail_plan(generation_input)
    assert first == replay
    assert first.code == "eligible_proposal"
    assert first.detail_reason == "eligible_rolling_proposal"
    assert first.plan is not None
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


def test_adjacent_running_days_fail_closed_across_schedule_units() -> None:
    history = list(_history())
    current_week_start = ATHLETE_TODAY - timedelta(days=ATHLETE_TODAY.weekday())
    first_week_start = current_week_start - timedelta(weeks=8)
    for week in range(8):
        observed_date = first_week_start + timedelta(weeks=week, days=6)
        history.append(
            TrailRunningHistoryObservation(
                activity_id=f"w{week}-extra",
                observed_date=observed_date,
                activity_type="running",
                duration_min=1,
                distance_km=0.1,
                elevation_gain_meters=0,
                elevation_loss_meters=0,
                source="garmin",
                source_timestamp=datetime.combine(
                    observed_date,
                    time(hour=12),
                    tzinfo=timezone.utc,
                ),
                outdoor_confirmed=True,
            )
        )
    constraints = replace(
        _generation_input().constraints,
        available_weekdays=(0, 2, 4, 6),
        preferred_longest_easy_weekday=6,
    )
    result = generate_non_ultra_trail_plan(
        _generation_input(history=tuple(history), constraints=constraints)
    )
    assert result.code == "validation_failed"
    assert result.detail_reason == "no_schedule_within_envelope"


def test_hash_is_order_independent_and_binds_ascent_and_descent_separately() -> None:
    generation_input = _generation_input()
    reordered = replace(
        generation_input,
        history=tuple(reversed(generation_input.history)),
    )
    assert deterministic_input_hash(generation_input) == deterministic_input_hash(
        reordered
    )

    changed_gain = replace(
        generation_input,
        course_demand=replace(
            generation_input.course_demand,
            elevation_gain_meters=_known(619),
        ),
    )
    changed_loss = replace(
        generation_input,
        course_demand=replace(
            generation_input.course_demand,
            elevation_loss_meters=_known(621),
        ),
    )
    hashes = {
        deterministic_input_hash(generation_input),
        deterministic_input_hash(changed_gain),
        deterministic_input_hash(changed_loss),
    }
    assert len(hashes) == 3


@pytest.mark.parametrize(
    ("prevalidation", "code"),
    [
        (
            InternalTrailPrevalidation(None, True, True, "terrain"),
            "material_course_demand_unknown",
        ),
        (
            InternalTrailPrevalidation(False, True, True, "terrain"),
            "course_clarification_required",
        ),
        (
            InternalTrailPrevalidation(True, False, True, "terrain"),
            "insufficient_terrain_access",
        ),
        (
            InternalTrailPrevalidation(True, True, None, "terrain"),
            "material_course_demand_unknown",
        ),
    ],
)
def test_prevalidation_false_or_unknown_fails_closed(
    prevalidation: InternalTrailPrevalidation,
    code: str,
) -> None:
    result = generate_non_ultra_trail_plan(
        _generation_input(prevalidation=prevalidation)
    )
    assert result.code == code
    assert result.plan is None


def test_material_unknown_and_unconfirmed_assumption_fail_closed() -> None:
    unknown = replace(_course(), elevation_loss_meters=_unknown())
    result = generate_non_ultra_trail_plan(_generation_input(course_demand=unknown))
    assert result.code == "material_course_demand_unknown"
    assert result.uncertainty_or_missing_field == "elevation_loss_meters"

    assumption = replace(
        _course(),
        technicality=ProvenancedValue(
            value={"reference": "assumption"},
            provenance="explicit_assumption",
            athlete_confirmed=False,
        ),
    )
    result = generate_non_ultra_trail_plan(_generation_input(course_demand=assumption))
    assert result.code == "course_clarification_required"


@pytest.mark.parametrize(
    "field_name",
    (
        "maximum_altitude_meters",
        "environmental_demand",
        "fueling_practice_experience",
    ),
)
def test_unconfirmed_assumption_fails_for_every_conditional_field(
    field_name: str,
) -> None:
    assumed_value: object = (
        430 if field_name == "maximum_altitude_meters" else {"reference": "x"}
    )
    course = replace(
        _course(),
        **{
            field_name: ProvenancedValue(
                value=assumed_value,
                provenance="explicit_assumption",
                athlete_confirmed=False,
            )
        },
    )
    result = generate_non_ultra_trail_plan(
        _generation_input(course_demand=course)
    )
    assert result.code == "course_clarification_required"
    assert result.failed_rule_id == "assumption_confirmation"
    assert result.uncertainty_or_missing_field == field_name


def test_conditional_unknowns_limit_modules_without_inventing_values() -> None:
    course = replace(
        _course(),
        maximum_altitude_meters=_unknown(),
        environmental_demand=_unknown(),
        fueling_practice_experience=_unknown(),
    )
    result = generate_non_ultra_trail_plan(
        _generation_input(
            course_demand=course,
            prevalidation=replace(
                _generation_input().prevalidation,
                technical_terrain_module_supported=None,
            ),
        )
    )
    assert result.code == "eligible_proposal"
    assert result.limited_modules == (
        "environment_module_limited",
        "fueling_module_limited",
        "technicality_module_limited",
    )


def test_product_detail_reasons_do_not_replace_canonical_science_codes() -> None:
    short_history = _history()[:6]
    result = generate_non_ultra_trail_plan(_generation_input(history=short_history))
    assert result.code == "insufficient_comparable_history"
    assert result.detail_reason == "insufficient_recent_history"

    near_event = replace(
        _generation_input().goal,
        target_event_date=BLOCK_START + timedelta(days=14),
    )
    result = generate_non_ultra_trail_plan(_generation_input(goal=near_event))
    assert result.code == "validation_failed"
    assert result.detail_reason == "event_inside_unapproved_taper_window"


def test_no_schedule_relaxes_no_guardrail() -> None:
    constraints = replace(
        _generation_input().constraints,
        maximum_session_duration_min=37,
    )
    result = generate_non_ultra_trail_plan(
        _generation_input(constraints=constraints)
    )
    assert result.code == "validation_failed"
    assert result.detail_reason == "no_schedule_within_envelope"
    assert result.plan is None


def test_invariant_validator_rejects_a_tampered_week() -> None:
    generation_input = _generation_input()
    result = generate_non_ultra_trail_plan(generation_input)
    assert result.plan is not None
    first_week = result.plan.weeks[0]
    tampered_week = replace(
        first_week,
        workouts=(
            replace(
                first_week.workouts[0],
                activity_type="running",  # type: ignore[arg-type]
            ),
            *first_week.workouts[1:],
        ),
    )
    tampered_plan: GeneratedNonUltraTrailPlan = replace(
        result.plan,
        weeks=(tampered_week, result.plan.weeks[1]),
    )
    assert "activity_type" in {
        violation.rule_id
        for violation in validate_generated_plan(tampered_plan, generation_input)
    }


def test_invariant_validator_rebinds_versions_course_modules_and_history() -> None:
    generation_input = _generation_input()
    result = generate_non_ultra_trail_plan(generation_input)
    assert result.plan is not None
    plan = result.plan
    tampered = (
        (replace(plan, policy_version="other"), "policy_version"),
        (replace(plan, generator_version="other"), "generator_version"),
        (replace(plan, course_demand_fingerprint="0" * 64), "course_fingerprint"),
        (replace(plan, limited_modules=("fueling_module_limited",)), "limited_modules"),
        (
            replace(
                plan,
                history_statistics=replace(
                    plan.history_statistics,
                    usable_completed_weeks=99,
                ),
            ),
            "history_statistics",
        ),
    )
    for candidate, expected_rule in tampered:
        rules = {
            violation.rule_id
            for violation in validate_generated_plan(candidate, generation_input)
        }
        assert expected_rule in rules

    ineligible_input = replace(
        generation_input,
        prevalidation=replace(
            generation_input.prevalidation,
            terrain_access_eligible=False,
        ),
    )
    assert "eligibility:internal_terrain_prevalidation" in {
        violation.rule_id
        for violation in validate_generated_plan(plan, ineligible_input)
    }


def test_invariant_validator_binds_workout_and_longest_easy_semantics() -> None:
    generation_input = _generation_input()
    result = generate_non_ultra_trail_plan(generation_input)
    assert result.plan is not None
    week = result.plan.weeks[0]
    ordinary_easy = next(
        workout for workout in week.workouts if workout.workout_type == "easy"
    )
    changed_type = replace(ordinary_easy, workout_type="controlled_quality")
    type_tampered_week = replace(
        week,
        workouts=tuple(
            changed_type if workout == ordinary_easy else workout
            for workout in week.workouts
        ),
    )
    type_tampered_plan = replace(
        result.plan,
        weeks=(type_tampered_week, result.plan.weeks[1]),
    )
    assert "easy_workout_type" in {
        violation.rule_id
        for violation in validate_generated_plan(
            type_tampered_plan,
            generation_input,
        )
    }

    longest = next(
        workout
        for workout in week.workouts
        if workout.workout_type == "longest_easy"
    )
    removed_longest = replace(longest, workout_type="easy")
    longest_tampered_week = replace(
        week,
        workouts=tuple(
            removed_longest if workout == longest else workout
            for workout in week.workouts
        ),
    )
    longest_tampered_plan = replace(
        result.plan,
        weeks=(longest_tampered_week, result.plan.weeks[1]),
    )
    assert "longest_easy_date" in {
        violation.rule_id
        for violation in validate_generated_plan(
            longest_tampered_plan,
            generation_input,
        )
    }

    shortened_ordinary = replace(
        ordinary_easy,
        planned_duration_min=ordinary_easy.planned_duration_min - 1,
        steps=(
            replace(
                ordinary_easy.steps[0],
                duration_min=ordinary_easy.planned_duration_min - 1,
            ),
        ),
    )
    lengthened_longest = replace(
        longest,
        planned_duration_min=longest.planned_duration_min + 1,
        steps=(
            replace(
                longest.steps[0],
                duration_min=longest.planned_duration_min + 1,
            ),
        ),
    )
    duration_tampered_week = replace(
        week,
        workouts=tuple(
            shortened_ordinary
            if workout == ordinary_easy
            else lengthened_longest
            if workout == longest
            else workout
            for workout in week.workouts
        ),
    )
    duration_tampered_plan = replace(
        result.plan,
        weeks=(duration_tampered_week, result.plan.weeks[1]),
    )
    assert "longest_easy_duration" in {
        violation.rule_id
        for violation in validate_generated_plan(
            duration_tampered_plan,
            generation_input,
        )
    }


def test_nonfinite_history_is_a_typed_validation_failure() -> None:
    invalid = replace(_history()[0], duration_min=float("nan"))
    result = generate_non_ultra_trail_plan(
        _generation_input(history=(invalid, *_history()[1:]))
    )
    assert result.code == "validation_failed"
    assert result.detail_reason == "contradictory_input"
    assert result.uncertainty_or_missing_field == "history.duration_min"
    with pytest.raises(ValueError):
        deterministic_input_hash(_generation_input(history=(invalid,)))


def test_invalid_hash_distinguishes_each_nonfinite_representation() -> None:
    hashes = set()
    for value in (float("nan"), float("inf"), float("-inf")):
        invalid = replace(_history()[0], duration_min=value)
        result = generate_non_ultra_trail_plan(
            _generation_input(history=(invalid, *_history()[1:]))
        )
        assert result.code == "validation_failed"
        hashes.add(result.deterministic_input_hash)
    assert len(hashes) == 3


def test_very_large_vertical_values_remain_bounded_without_per_meter_work() -> None:
    huge = 10**400
    history = tuple(
        replace(
            item,
            elevation_gain_meters=huge,
            elevation_loss_meters=huge - 1,
        )
        if item.activity_type == "trail_running"
        else item
        for item in _history()
    )
    result = generate_non_ultra_trail_plan(
        _generation_input(history=history)
    )
    assert result.code == "eligible_proposal"
    assert result.plan is not None
    for week in result.plan.weeks:
        assert week.weekly_ascent_ceiling_meters == huge * 2
        assert week.weekly_descent_ceiling_meters == (huge - 1) * 2


def test_arbitrary_size_integer_duration_and_distance_do_not_overflow() -> None:
    huge = 10**400
    first = replace(
        _history()[0],
        duration_min=huge,
        distance_km=huge,
    )
    generation_input = _generation_input(
        history=(first, *_history()[1:])
    )
    result = generate_non_ultra_trail_plan(generation_input)
    replay = generate_non_ultra_trail_plan(generation_input)
    assert result == replay
    assert result.code == "eligible_proposal"
    assert deterministic_input_hash(generation_input) == (
        result.deterministic_input_hash
    )
