"""Pure deterministic generation for the accepted inactive Trail policy.

This module accepts only typed, already-loaded values.  It never reads a
database, file, clock, provider, or mutable service state.  It is deliberately
not registered with a route or capability registry: the governing contracts
authorize an inactive implementation only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import date, datetime, timedelta
from fractions import Fraction
import hashlib
from itertools import combinations
import json
import math
from typing import Any, Literal, Mapping, Sequence

from analysis.non_ultra_trail_contract import (
    NON_ULTRA_TRAIL_ALLOWED_PROVENANCE,
    NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID,
    NON_ULTRA_TRAIL_CONTRACT_DIGEST,
    NON_ULTRA_TRAIL_COURSE_SCHEMA,
    NON_ULTRA_TRAIL_COURSE_SCHEMA_ID,
    NON_ULTRA_TRAIL_GENERATOR_VERSION,
    NON_ULTRA_TRAIL_HISTORY,
    NON_ULTRA_TRAIL_HISTORY_LOOKBACK_COMPLETED_WEEKS,
    NON_ULTRA_TRAIL_INTENSITY,
    NON_ULTRA_TRAIL_NO_PLAN_RESULT_CODES,
    NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT_DIGEST,
    NON_ULTRA_TRAIL_ONTOLOGY_DECISION_ID,
    NON_ULTRA_TRAIL_ONTOLOGY_SOURCE_DECISION_DIGEST,
    NON_ULTRA_TRAIL_POLICY_VERSION,
    NON_ULTRA_TRAIL_PROPOSAL_DAYS,
    NON_ULTRA_TRAIL_REASSESSMENT_DAYS,
    NON_ULTRA_TRAIL_SCHEDULE,
    NON_ULTRA_TRAIL_SCIENCE_DECISION_ID,
    NON_ULTRA_TRAIL_SOURCE_DECISION_DIGEST,
    NON_ULTRA_TRAIL_SUCCESS_CODE,
    NON_ULTRA_TRAIL_TEMPLATES,
)


_SCHEDULE_UNIT_DAYS = 7
_MINIMUM_USABLE_WEEKS = int(
    NON_ULTRA_TRAIL_HISTORY["minimum_usable_completed_weeks"]
)
_MINIMUM_RUNS_PER_USABLE_WEEK = int(
    NON_ULTRA_TRAIL_HISTORY[
        "minimum_running_sessions_per_usable_week"
    ]
)
_LATEST_RUN_DAYS = int(
    NON_ULTRA_TRAIL_HISTORY["latest_run_within_completed_days"]
)
_COMPARABLE_REQUIREMENT = NON_ULTRA_TRAIL_HISTORY[
    "comparable_hilly_or_trail_sessions_within_completed_days"
]
_COMPARABLE_COUNT = int(_COMPARABLE_REQUIREMENT["count"])
_COMPARABLE_WINDOW_DAYS = int(_COMPARABLE_REQUIREMENT["window"])
_LATEST_COMPARABLE_DAYS = int(
    NON_ULTRA_TRAIL_HISTORY[
        "latest_comparable_hilly_or_trail_session_within_completed_days"
    ]
)
_MIN_RUN_DAYS = int(
    NON_ULTRA_TRAIL_SCHEDULE[
        "selected_running_days_per_7_day_unit"
    ]["minimum"]
)
_MAX_RUN_DAYS = int(
    NON_ULTRA_TRAIL_SCHEDULE[
        "selected_running_days_per_7_day_unit"
    ]["maximum"]
)
_LOW_INTENSITY_FLOOR = float(
    NON_ULTRA_TRAIL_INTENSITY[
        "minimum_planned_low_intensity_running_minutes_fraction"
    ]
)
_MAX_QUALITY_PER_UNIT = int(
    NON_ULTRA_TRAIL_INTENSITY[
        "maximum_quality_exposures_per_7_day_unit"
    ]
)
_MATERIAL_COURSE_FIELDS = tuple(
    name
    for name, specification in NON_ULTRA_TRAIL_COURSE_SCHEMA["fields"].items()
    if specification["material"] is True
)
_OBJECT_COURSE_FIELDS = frozenset({
    name
    for name, specification in NON_ULTRA_TRAIL_COURSE_SCHEMA["fields"].items()
    if specification["type"] in {"object", "categorical_object"}
})
_INTEGER_COURSE_FIELDS = frozenset({
    name
    for name, specification in NON_ULTRA_TRAIL_COURSE_SCHEMA["fields"].items()
    if specification["type"] == "integer"
})
_HISTORY_ACTIVITY_TYPES = frozenset({"running", "trail_running"})
_MAX_HISTORY_OBSERVATIONS = 1000


@dataclass(frozen=True)
class ProvenancedValue:
    """One course-demand value with explicit origin and missingness."""

    value: Any | None
    provenance: str
    source_reference: str | None = None
    source_timestamp: date | None = None
    model_version: str | None = None
    athlete_confirmed: bool = False

    @property
    def is_unknown(self) -> bool:
        """Return whether the value is explicitly unknown."""
        return self.provenance == "unknown"

    def public_payload(self) -> dict[str, Any]:
        """Return the portable value/provenance representation."""
        return _json_safe_dates(asdict(self))


@dataclass(frozen=True)
class TrailCourseDemand:
    """Exact ``trail_course_demand_v1`` fields admitted by the policy."""

    expected_duration_seconds: ProvenancedValue
    distance_meters: ProvenancedValue
    elevation_gain_meters: ProvenancedValue
    elevation_loss_meters: ProvenancedValue
    grade_distribution: ProvenancedValue
    technicality: ProvenancedValue
    maximum_altitude_meters: ProvenancedValue
    environmental_demand: ProvenancedValue
    aid_and_support: ProvenancedValue
    training_terrain_access: ProvenancedValue
    recent_downhill_exposure: ProvenancedValue
    fueling_practice_experience: ProvenancedValue
    athlete_confirmed: bool
    schema_id: str = NON_ULTRA_TRAIL_COURSE_SCHEMA_ID

    def public_payload(self) -> dict[str, Any]:
        """Return a stable response-safe course snapshot."""
        return _serialize_course_demand(self)


@dataclass(frozen=True)
class NonUltraTrailGoal:
    """Preclassified goal tuple admitted by the inactive generator."""

    intent: str
    event_format: str
    distance_family: str
    target_event_date: date
    event_confirmed: bool
    clinical_or_return_to_sport: bool = False


@dataclass(frozen=True)
class TrailPlanGenerationConstraints:
    """Athlete-stated calendar and duration boundaries."""

    adult_confirmed: bool | None
    current_symptom_stop: bool | None
    available_weekdays: tuple[int, ...]
    weekly_time_limit_min: int
    maximum_session_duration_min: int
    unavailable_dates: tuple[date, ...] = ()
    reserved_dates: tuple[date, ...] = ()
    preferred_longest_easy_weekday: int | None = None
    schema_id: str = NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID


@dataclass(frozen=True)
class InternalTrailPrevalidation:
    """Internal-only semantic checks that this core must not invent.

    Course materiality and terrain-category comparison require a separately
    reviewed caller.  Only literal ``True`` values cross this boundary.
    Opaque terrain references are propagated, never ordered or classified.
    """

    course_demand_eligible: bool | None
    terrain_access_eligible: bool | None
    nontechnical_uphill_accessible: bool | None
    training_terrain_reference: str | None
    technical_terrain_module_supported: bool | None = None


@dataclass(frozen=True)
class TrailRunningHistoryObservation:
    """One completed activity observation; average power is intentionally absent."""

    activity_id: str
    observed_date: date
    activity_type: str
    duration_min: float
    distance_km: float | None
    elevation_gain_meters: int | None
    elevation_loss_meters: int | None
    source: str
    source_timestamp: datetime
    outdoor_confirmed: bool


@dataclass(frozen=True)
class RecentTrailHistoryStatistics:
    """Reproducible running and direct Trail anchors."""

    usable_completed_weeks: int
    recent_modal_running_frequency: int
    recent_median_usable_weekly_minutes: int
    recent_maximum_usable_weekly_minutes: int
    recent_maximum_session_minutes: int
    recent_median_usable_weekly_ascent_meters: int
    recent_maximum_usable_weekly_ascent_meters: int
    recent_median_usable_weekly_descent_meters: int
    recent_maximum_usable_weekly_descent_meters: int
    recent_maximum_session_ascent_meters: int
    recent_maximum_session_descent_meters: int
    latest_run_date: date | None
    comparable_trail_sessions_within_window: int
    latest_comparable_trail_session_date: date | None

    @classmethod
    def empty(cls) -> "RecentTrailHistoryStatistics":
        """Return the deterministic empty aggregate used for invalid input."""
        return cls(
            usable_completed_weeks=0,
            recent_modal_running_frequency=0,
            recent_median_usable_weekly_minutes=0,
            recent_maximum_usable_weekly_minutes=0,
            recent_maximum_session_minutes=0,
            recent_median_usable_weekly_ascent_meters=0,
            recent_maximum_usable_weekly_ascent_meters=0,
            recent_median_usable_weekly_descent_meters=0,
            recent_maximum_usable_weekly_descent_meters=0,
            recent_maximum_session_ascent_meters=0,
            recent_maximum_session_descent_meters=0,
            latest_run_date=None,
            comparable_trail_sessions_within_window=0,
            latest_comparable_trail_session_date=None,
        )

    def public_payload(self) -> dict[str, Any]:
        """Return the JSON-safe aggregate projection."""
        return _json_safe_dates(asdict(self))


@dataclass(frozen=True)
class TrailWorkoutStep:
    """One targetless duration/phase/effort step."""

    kind: str
    phase: str | None = None
    duration_min: int | None = None
    intended_intensity: str | None = None
    repetitions: int | None = None
    steps: tuple["TrailWorkoutStep", ...] = ()


@dataclass(frozen=True)
class GeneratedTrailWorkout:
    """One deterministic, non-canonical Trail proposal workout."""

    scheduled_date: date
    workout_type: Literal["easy", "longest_easy", "controlled_quality"]
    intensity_bucket: Literal["low", "quality"]
    planned_duration_min: int
    ascent_ceiling_meters: int
    descent_ceiling_meters: int
    terrain_reference: str
    template_id: str | None
    steps: tuple[TrailWorkoutStep, ...]
    activity_type: Literal["trail_running"] = "trail_running"

    def public_payload(self) -> dict[str, Any]:
        """Return one JSON-safe proposal workout."""
        return _json_safe_dates(asdict(self))


@dataclass(frozen=True)
class GeneratedTrailWeek:
    """One seven-day unit with independently capped ascent and descent."""

    week_number: int
    start_date: date
    end_date: date
    weekly_ascent_ceiling_meters: int
    weekly_descent_ceiling_meters: int
    workouts: tuple[GeneratedTrailWorkout, ...]


@dataclass(frozen=True)
class GeneratedNonUltraTrailPlan:
    """Immutable 14-day suggestion; never a canonical or delivered plan."""

    policy_version: str
    generator_version: str
    horizon_start: date
    horizon_end: date
    reassessment_dates: tuple[date, ...]
    course_demand_fingerprint: str
    history_statistics: RecentTrailHistoryStatistics
    limited_modules: tuple[str, ...]
    weeks: tuple[GeneratedTrailWeek, ...]

    def public_payload(self) -> dict[str, Any]:
        """Return the complete JSON-safe suggestion."""
        return _json_safe_dates(asdict(self))


@dataclass(frozen=True)
class NonUltraTrailGenerationInput:
    """All versioned values needed to replay one pure generation decision."""

    policy_version: str
    science_decision_id: str
    contract_digest: str
    source_decision_digest: str
    ontology_decision_id: str
    ontology_contract_digest: str
    ontology_source_decision_digest: str
    athlete_today: date
    block_start: date
    goal: NonUltraTrailGoal
    course_demand: TrailCourseDemand
    history: tuple[TrailRunningHistoryObservation, ...]
    constraints: TrailPlanGenerationConstraints
    prevalidation: InternalTrailPrevalidation

    def public_payload(self) -> dict[str, Any]:
        """Return the complete replay input without adding authority."""
        return serialize_generation_input(self)


@dataclass(frozen=True)
class NonUltraTrailGenerationResult:
    """Canonical Science outcome plus a separate Product detail reason."""

    policy_version: str
    generator_version: str
    science_decision_id: str
    contract_digest: str
    source_decision_digest: str
    code: str
    detail_reason: str
    deterministic_input_hash: str
    plan: GeneratedNonUltraTrailPlan | None
    history_statistics: RecentTrailHistoryStatistics
    limited_modules: tuple[str, ...]
    failed_rule_id: str | None
    uncertainty_or_missing_field: str | None

    def public_payload(self) -> dict[str, Any]:
        """Return a JSON-safe outcome without changing its authority."""
        return serialize_generation_result(self)


@dataclass(frozen=True)
class PlanInvariantViolation:
    """One stable fail-closed invariant result."""

    rule_id: str
    detail_reason: str


@dataclass(frozen=True)
class _InputIssue:
    code: str
    detail_reason: str
    rule_id: str
    missing_field: str | None = None


@dataclass(frozen=True)
class _WorkoutTemplate:
    template_id: str
    total_minutes: int
    low_intensity_minutes: int
    steps: tuple[TrailWorkoutStep, ...]


def _build_template_step(raw: Mapping[str, Any]) -> TrailWorkoutStep:
    kind = str(raw["kind"])
    if kind == "repeat":
        return TrailWorkoutStep(
            kind="repeat",
            repetitions=int(raw["repetitions"]),
            steps=tuple(_build_template_step(item) for item in raw["steps"]),
        )
    return TrailWorkoutStep(
        kind="step",
        phase=str(raw["phase"]),
        duration_min=int(raw["duration_minutes"]),
        intended_intensity=str(raw["intended_intensity"]),
    )


_CONTROLLED_QUALITY_RAW = NON_ULTRA_TRAIL_TEMPLATES["controlled_quality"]
_CONTROLLED_QUALITY_STEPS = tuple(
    _build_template_step(step) for step in _CONTROLLED_QUALITY_RAW["steps"]
)


def _steps_duration(steps: Sequence[TrailWorkoutStep]) -> int:
    total = 0
    for step in steps:
        if step.kind == "repeat":
            total += int(step.repetitions or 0) * _steps_duration(step.steps)
        else:
            total += int(step.duration_min or 0)
    return total


def _steps_low_minutes(steps: Sequence[TrailWorkoutStep]) -> int:
    total = 0
    for step in steps:
        if step.kind == "repeat":
            total += int(step.repetitions or 0) * _steps_low_minutes(step.steps)
        elif step.intended_intensity == "low":
            total += int(step.duration_min or 0)
    return total


CONTROLLED_UPHILL_TEMPLATE = _WorkoutTemplate(
    template_id=str(_CONTROLLED_QUALITY_RAW["template_id"]),
    total_minutes=int(_CONTROLLED_QUALITY_RAW["total_planned_minutes"]),
    low_intensity_minutes=_steps_low_minutes(_CONTROLLED_QUALITY_STEPS),
    steps=_CONTROLLED_QUALITY_STEPS,
)

if _steps_duration(CONTROLLED_UPHILL_TEMPLATE.steps) != 38:
    raise ValueError("accepted Trail quality template must total 38 minutes")
if CONTROLLED_UPHILL_TEMPLATE.total_minutes != 38:
    raise ValueError("Trail quality template contract total mismatch")


def derive_recent_history_statistics(
    history: Sequence[TrailRunningHistoryObservation],
    *,
    athlete_today: date,
) -> RecentTrailHistoryStatistics:
    """Derive eight complete-week running anchors and direct Trail exposure.

    ``running`` and ``trail_running`` both contribute to usable running weeks.
    Only an exact ``trail_running`` observation with independently known gain
    and loss contributes comparable exposure or vertical anchors.
    """
    issue = _history_primitive_issue(history, athlete_today=athlete_today)
    if issue is not None:
        raise ValueError(issue.detail_reason)

    completed_observations = tuple(
        item
        for item in history
        if _is_qualifying_run(item) and item.observed_date < athlete_today
    )
    current_week_start = athlete_today - timedelta(days=athlete_today.weekday())
    first_week_start = current_week_start - timedelta(
        days=(
            _SCHEDULE_UNIT_DAYS
            * NON_ULTRA_TRAIL_HISTORY_LOOKBACK_COMPLETED_WEEKS
        )
    )
    complete_week_observations = tuple(
        item
        for item in completed_observations
        if first_week_start <= item.observed_date < current_week_start
    )

    week_buckets: dict[date, list[TrailRunningHistoryObservation]] = {}
    for item in complete_week_observations:
        week_start = item.observed_date - timedelta(
            days=item.observed_date.weekday()
        )
        week_buckets.setdefault(week_start, []).append(item)

    usable_weeks = tuple(
        (week_start, tuple(values))
        for week_start, values in sorted(week_buckets.items())
        if len(values) >= _MINIMUM_RUNS_PER_USABLE_WEEK
        and _duration_minutes_total(values) > 0
    )
    weekly_minutes = tuple(
        _duration_minutes_total(values)
        for _, values in usable_weeks
    )
    weekly_ascent = tuple(
        sum(
            int(item.elevation_gain_meters or 0)
            for item in values
            if _is_comparable_trail(item)
        )
        for _, values in usable_weeks
    )
    weekly_descent = tuple(
        sum(
            int(item.elevation_loss_meters or 0)
            for item in values
            if _is_comparable_trail(item)
        )
        for _, values in usable_weeks
    )
    all_usable = tuple(
        item for _, values in usable_weeks for item in values
    )
    usable_comparable_trail = tuple(
        item for item in all_usable if _is_comparable_trail(item)
    )

    comparable_in_window = tuple(
        item
        for item in completed_observations
        if _is_comparable_trail(item)
        and 1 <= (athlete_today - item.observed_date).days
        <= _COMPARABLE_WINDOW_DAYS
    )
    frequencies = tuple(len(values) for _, values in usable_weeks)
    return RecentTrailHistoryStatistics(
        usable_completed_weeks=len(usable_weeks),
        recent_modal_running_frequency=_conservative_mode(frequencies),
        recent_median_usable_weekly_minutes=_integer_median(weekly_minutes),
        recent_maximum_usable_weekly_minutes=max(weekly_minutes, default=0),
        recent_maximum_session_minutes=int(
            max((item.duration_min for item in all_usable), default=0)
        ),
        recent_median_usable_weekly_ascent_meters=_integer_median(
            weekly_ascent
        ),
        recent_maximum_usable_weekly_ascent_meters=max(
            weekly_ascent,
            default=0,
        ),
        recent_median_usable_weekly_descent_meters=_integer_median(
            weekly_descent
        ),
        recent_maximum_usable_weekly_descent_meters=max(
            weekly_descent,
            default=0,
        ),
        recent_maximum_session_ascent_meters=max(
            (
                int(item.elevation_gain_meters or 0)
                for item in usable_comparable_trail
            ),
            default=0,
        ),
        recent_maximum_session_descent_meters=max(
            (
                int(item.elevation_loss_meters or 0)
                for item in usable_comparable_trail
            ),
            default=0,
        ),
        latest_run_date=max(
            (item.observed_date for item in completed_observations),
            default=None,
        ),
        comparable_trail_sessions_within_window=len(comparable_in_window),
        latest_comparable_trail_session_date=max(
            (item.observed_date for item in comparable_in_window),
            default=None,
        ),
    )


def generate_non_ultra_trail_plan(
    generation_input: NonUltraTrailGenerationInput,
) -> NonUltraTrailGenerationResult:
    """Return an inactive deterministic suggestion or a canonical no-plan code."""
    primitive_issue = _generation_input_primitive_issue(generation_input)
    if primitive_issue is not None:
        return _no_plan(
            issue=primitive_issue,
            input_hash=_invalid_input_hash(generation_input, primitive_issue),
            statistics=RecentTrailHistoryStatistics.empty(),
        )

    input_hash = deterministic_input_hash(generation_input)
    statistics = derive_recent_history_statistics(
        generation_input.history,
        athlete_today=generation_input.athlete_today,
    )

    contract_issue = _contract_issue(generation_input)
    if contract_issue is not None:
        return _no_plan(
            issue=contract_issue,
            input_hash=input_hash,
            statistics=statistics,
        )
    scope_issue = _scope_issue(generation_input)
    if scope_issue is not None:
        return _no_plan(
            issue=scope_issue,
            input_hash=input_hash,
            statistics=statistics,
        )
    course_issue = _course_issue(generation_input.course_demand)
    if course_issue is not None:
        return _no_plan(
            issue=course_issue,
            input_hash=input_hash,
            statistics=statistics,
        )
    prevalidation_issue = _prevalidation_issue(generation_input.prevalidation)
    if prevalidation_issue is not None:
        return _no_plan(
            issue=prevalidation_issue,
            input_hash=input_hash,
            statistics=statistics,
        )
    history_issue = _history_issue(
        statistics,
        athlete_today=generation_input.athlete_today,
    )
    if history_issue is not None:
        return _no_plan(
            issue=history_issue,
            input_hash=input_hash,
            statistics=statistics,
        )
    constraint_issue = _constraint_issue(generation_input.constraints)
    if constraint_issue is not None:
        return _no_plan(
            issue=constraint_issue,
            input_hash=input_hash,
            statistics=statistics,
        )
    if (
        generation_input.goal.target_event_date
        - generation_input.block_start
    ).days <= NON_ULTRA_TRAIL_PROPOSAL_DAYS:
        return _no_plan(
            issue=_InputIssue(
                code="validation_failed",
                detail_reason="event_inside_unapproved_taper_window",
                rule_id="event_and_taper",
                missing_field="accepted Trail taper policy",
            ),
            input_hash=input_hash,
            statistics=statistics,
        )

    limited_modules = _limited_modules(
        generation_input.course_demand,
        generation_input.prevalidation,
    )
    weeks = _build_schedule(
        generation_input=generation_input,
        statistics=statistics,
    )
    if weeks is None:
        return _no_plan(
            issue=_InputIssue(
                code="validation_failed",
                detail_reason="no_schedule_within_envelope",
                rule_id="schedule_construction",
            ),
            input_hash=input_hash,
            statistics=statistics,
            limited_modules=limited_modules,
        )

    plan = GeneratedNonUltraTrailPlan(
        policy_version=NON_ULTRA_TRAIL_POLICY_VERSION,
        generator_version=NON_ULTRA_TRAIL_GENERATOR_VERSION,
        horizon_start=generation_input.block_start,
        horizon_end=(
            generation_input.block_start
            + timedelta(days=NON_ULTRA_TRAIL_PROPOSAL_DAYS - 1)
        ),
        reassessment_dates=(
            generation_input.block_start
            + timedelta(days=NON_ULTRA_TRAIL_REASSESSMENT_DAYS),
        ),
        course_demand_fingerprint=_canonical_fingerprint(
            _serialize_course_demand(generation_input.course_demand)
        ),
        history_statistics=statistics,
        limited_modules=limited_modules,
        weeks=weeks,
    )
    violations = validate_generated_plan(plan, generation_input)
    if violations:
        violation = violations[0]
        return _no_plan(
            issue=_InputIssue(
                code="validation_failed",
                detail_reason=violation.detail_reason,
                rule_id=violation.rule_id,
            ),
            input_hash=input_hash,
            statistics=statistics,
            limited_modules=limited_modules,
        )
    return NonUltraTrailGenerationResult(
        policy_version=NON_ULTRA_TRAIL_POLICY_VERSION,
        generator_version=NON_ULTRA_TRAIL_GENERATOR_VERSION,
        science_decision_id=NON_ULTRA_TRAIL_SCIENCE_DECISION_ID,
        contract_digest=NON_ULTRA_TRAIL_CONTRACT_DIGEST,
        source_decision_digest=NON_ULTRA_TRAIL_SOURCE_DECISION_DIGEST,
        code=NON_ULTRA_TRAIL_SUCCESS_CODE,
        detail_reason="eligible_rolling_proposal",
        deterministic_input_hash=input_hash,
        plan=plan,
        history_statistics=statistics,
        limited_modules=limited_modules,
        failed_rule_id=None,
        uncertainty_or_missing_field=None,
    )


def deterministic_input_hash(
    generation_input: NonUltraTrailGenerationInput,
) -> str:
    """Return a stable order-independent hash for the complete valid input."""
    issue = _generation_input_primitive_issue(generation_input)
    if issue is not None:
        raise ValueError(issue.detail_reason)
    return _canonical_fingerprint(serialize_generation_input(generation_input))


def serialize_generation_input(
    generation_input: NonUltraTrailGenerationInput,
) -> dict[str, Any]:
    """Return the explicit JSON-safe replay snapshot."""
    history = [
        _serialize_history_observation(item)
        for item in sorted(
            generation_input.history,
            key=_history_canonical_sort_key,
        )
    ]
    constraints = generation_input.constraints
    return {
        "policy_version": generation_input.policy_version,
        "science_decision_id": generation_input.science_decision_id,
        "contract_digest": generation_input.contract_digest,
        "source_decision_digest": generation_input.source_decision_digest,
        "ontology_decision_id": generation_input.ontology_decision_id,
        "ontology_contract_digest": generation_input.ontology_contract_digest,
        "ontology_source_decision_digest": (
            generation_input.ontology_source_decision_digest
        ),
        "generator_version": NON_ULTRA_TRAIL_GENERATOR_VERSION,
        "athlete_today": generation_input.athlete_today.isoformat(),
        "block_start": generation_input.block_start.isoformat(),
        "goal": _json_safe_dates(asdict(generation_input.goal)),
        "course_demand": _serialize_course_demand(
            generation_input.course_demand
        ),
        "history": history,
        "constraints": {
            "adult_confirmed": constraints.adult_confirmed,
            "current_symptom_stop": constraints.current_symptom_stop,
            "available_weekdays": sorted(constraints.available_weekdays),
            "weekly_time_limit_min": constraints.weekly_time_limit_min,
            "maximum_session_duration_min": (
                constraints.maximum_session_duration_min
            ),
            "unavailable_dates": sorted(
                value.isoformat() for value in constraints.unavailable_dates
            ),
            "reserved_dates": sorted(
                value.isoformat() for value in constraints.reserved_dates
            ),
            "preferred_longest_easy_weekday": (
                constraints.preferred_longest_easy_weekday
            ),
            "schema_id": constraints.schema_id,
        },
        "prevalidation": asdict(generation_input.prevalidation),
    }


def serialize_generation_result(
    result: NonUltraTrailGenerationResult,
) -> dict[str, Any]:
    """Return the explicit JSON-safe result projection."""
    return _json_safe_dates(asdict(result))


def serialize_workout_structure(
    workout: GeneratedTrailWorkout,
) -> dict[str, Any]:
    """Return the provider-neutral targetless step structure."""
    return {"steps": [_serialize_step(step) for step in workout.steps]}


def validate_generated_plan(
    plan: GeneratedNonUltraTrailPlan,
    generation_input: NonUltraTrailGenerationInput,
) -> tuple[PlanInvariantViolation, ...]:
    """Return every deterministic policy-invariant violation in stable order."""
    violations: list[PlanInvariantViolation] = []
    primitive_issue = _generation_input_primitive_issue(generation_input)
    if primitive_issue is not None:
        return (
            PlanInvariantViolation(
                "generation_input_primitives",
                primitive_issue.detail_reason,
            ),
        )
    statistics = derive_recent_history_statistics(
        generation_input.history,
        athlete_today=generation_input.athlete_today,
    )
    constraints = generation_input.constraints
    if plan.policy_version != NON_ULTRA_TRAIL_POLICY_VERSION:
        violations.append(
            PlanInvariantViolation("policy_version", "validation_failed")
        )
    if plan.generator_version != NON_ULTRA_TRAIL_GENERATOR_VERSION:
        violations.append(
            PlanInvariantViolation("generator_version", "validation_failed")
        )
    expected_course_fingerprint = _canonical_fingerprint(
        _serialize_course_demand(generation_input.course_demand)
    )
    if plan.course_demand_fingerprint != expected_course_fingerprint:
        violations.append(
            PlanInvariantViolation("course_fingerprint", "validation_failed")
        )
    expected_limited_modules = _limited_modules(
        generation_input.course_demand,
        generation_input.prevalidation,
    )
    if plan.limited_modules != expected_limited_modules:
        violations.append(
            PlanInvariantViolation("limited_modules", "validation_failed")
        )
    if plan.history_statistics != statistics:
        violations.append(
            PlanInvariantViolation("history_statistics", "validation_failed")
        )
    eligibility_issues = (
        _contract_issue(generation_input),
        _scope_issue(generation_input),
        _course_issue(generation_input.course_demand),
        _prevalidation_issue(generation_input.prevalidation),
        _history_issue(
            statistics,
            athlete_today=generation_input.athlete_today,
        ),
        _constraint_issue(generation_input.constraints),
    )
    for issue in eligibility_issues:
        if issue is not None:
            violations.append(
                PlanInvariantViolation(
                    f"eligibility:{issue.rule_id}",
                    issue.detail_reason,
                )
            )
    if (
        generation_input.goal.target_event_date
        - generation_input.block_start
    ).days <= NON_ULTRA_TRAIL_PROPOSAL_DAYS:
        violations.append(
            PlanInvariantViolation(
                "eligibility:event_and_taper",
                "event_inside_unapproved_taper_window",
            )
        )
    expected_end = generation_input.block_start + timedelta(
        days=NON_ULTRA_TRAIL_PROPOSAL_DAYS - 1
    )
    if (
        plan.horizon_start != generation_input.block_start
        or plan.horizon_end != expected_end
        or len(plan.weeks) != NON_ULTRA_TRAIL_PROPOSAL_DAYS // 7
    ):
        violations.append(
            PlanInvariantViolation("proposal_horizon", "validation_failed")
        )
    expected_reassessment = (
        generation_input.block_start
        + timedelta(days=NON_ULTRA_TRAIL_REASSESSMENT_DAYS),
    )
    if plan.reassessment_dates != expected_reassessment:
        violations.append(
            PlanInvariantViolation("reassessment_date", "validation_failed")
        )

    frequency_cap = min(
        len(set(constraints.available_weekdays)),
        statistics.recent_modal_running_frequency,
        _MAX_RUN_DAYS,
    )
    session_duration_cap = min(
        statistics.recent_maximum_session_minutes,
        constraints.maximum_session_duration_min,
    )
    weekly_minutes_target = min(
        statistics.recent_median_usable_weekly_minutes,
        constraints.weekly_time_limit_min,
    )
    weekly_minutes_hard_cap = min(
        statistics.recent_maximum_usable_weekly_minutes,
        constraints.weekly_time_limit_min,
    )
    ascent_target = statistics.recent_median_usable_weekly_ascent_meters
    ascent_hard_cap = statistics.recent_maximum_usable_weekly_ascent_meters
    descent_target = statistics.recent_median_usable_weekly_descent_meters
    descent_hard_cap = statistics.recent_maximum_usable_weekly_descent_meters
    blocked_dates = set(constraints.unavailable_dates) | set(
        constraints.reserved_dates
    )
    seen_dates: set[date] = set()
    quality_dates: list[date] = []

    for week_index, week in enumerate(plan.weeks):
        expected_start = generation_input.block_start + timedelta(
            days=week_index * _SCHEDULE_UNIT_DAYS
        )
        expected_week_end = expected_start + timedelta(days=6)
        if (
            week.week_number != week_index + 1
            or week.start_date != expected_start
            or week.end_date != expected_week_end
        ):
            violations.append(
                PlanInvariantViolation("week_boundary", "validation_failed")
            )
        if not (_MIN_RUN_DAYS <= len(week.workouts) <= frequency_cap):
            violations.append(
                PlanInvariantViolation("running_day_count", "validation_failed")
            )

        total_minutes = sum(item.planned_duration_min for item in week.workouts)
        low_minutes = sum(_workout_low_minutes(item) for item in week.workouts)
        quality = tuple(
            item for item in week.workouts if item.intensity_bucket == "quality"
        )
        low_workouts = tuple(
            item for item in week.workouts if item.intensity_bucket == "low"
        )
        if len(quality) != _MAX_QUALITY_PER_UNIT:
            violations.append(
                PlanInvariantViolation(
                    "quality_exposure_count",
                    "validation_failed",
                )
            )
        quality_dates.extend(item.scheduled_date for item in quality)
        longest_easy = tuple(
            item for item in week.workouts if item.workout_type == "longest_easy"
        )
        expected_longest_date = _longest_easy_date(
            tuple(item.scheduled_date for item in low_workouts),
            preferred_longest_easy_weekday=(
                constraints.preferred_longest_easy_weekday
            ),
        )
        if (
            len(longest_easy) != 1
            or expected_longest_date is None
            or longest_easy[0].scheduled_date != expected_longest_date
        ):
            violations.append(
                PlanInvariantViolation("longest_easy_date", "validation_failed")
            )
        expected_easy_minutes = _allocate_easy_minutes(
            tuple(item.scheduled_date for item in low_workouts),
            total_minutes=(
                weekly_minutes_target
                - CONTROLLED_UPHILL_TEMPLATE.total_minutes
            ),
            preferred_longest_easy_weekday=(
                constraints.preferred_longest_easy_weekday
            ),
        )
        if any(
            item.planned_duration_min
            != expected_easy_minutes.get(item.scheduled_date)
            for item in low_workouts
        ):
            violations.append(
                PlanInvariantViolation(
                    "longest_easy_duration",
                    "validation_failed",
                )
            )
        if total_minutes != weekly_minutes_target:
            violations.append(
                PlanInvariantViolation("weekly_minutes_target", "validation_failed")
            )
        if total_minutes > weekly_minutes_hard_cap:
            violations.append(
                PlanInvariantViolation("weekly_minutes_cap", "validation_failed")
            )
        if total_minutes <= 0 or low_minutes / total_minutes < _LOW_INTENSITY_FLOOR:
            violations.append(
                PlanInvariantViolation("low_intensity_floor", "validation_failed")
            )

        ascent_sum = sum(item.ascent_ceiling_meters for item in week.workouts)
        descent_sum = sum(item.descent_ceiling_meters for item in week.workouts)
        if (
            ascent_sum != week.weekly_ascent_ceiling_meters
            or ascent_sum > ascent_target
            or ascent_sum > ascent_hard_cap
        ):
            violations.append(
                PlanInvariantViolation("weekly_ascent_cap", "validation_failed")
            )
        if (
            descent_sum != week.weekly_descent_ceiling_meters
            or descent_sum > descent_target
            or descent_sum > descent_hard_cap
        ):
            violations.append(
                PlanInvariantViolation("weekly_descent_cap", "validation_failed")
            )

        for workout in week.workouts:
            if workout.scheduled_date in seen_dates:
                violations.append(
                    PlanInvariantViolation("duplicate_date", "validation_failed")
                )
            seen_dates.add(workout.scheduled_date)
            if not (week.start_date <= workout.scheduled_date <= week.end_date):
                violations.append(
                    PlanInvariantViolation("workout_week", "validation_failed")
                )
            if (
                workout.scheduled_date in blocked_dates
                or workout.scheduled_date.weekday()
                not in constraints.available_weekdays
            ):
                violations.append(
                    PlanInvariantViolation("calendar_constraint", "validation_failed")
                )
            if workout.scheduled_date >= generation_input.goal.target_event_date:
                violations.append(
                    PlanInvariantViolation("event_boundary", "validation_failed")
                )
            if workout.activity_type != "trail_running":
                violations.append(
                    PlanInvariantViolation("activity_type", "validation_failed")
                )
            if (
                workout.planned_duration_min <= 0
                or workout.planned_duration_min > session_duration_cap
            ):
                violations.append(
                    PlanInvariantViolation("session_duration_cap", "validation_failed")
                )
            if (
                workout.ascent_ceiling_meters < 0
                or workout.ascent_ceiling_meters
                > statistics.recent_maximum_session_ascent_meters
            ):
                violations.append(
                    PlanInvariantViolation("session_ascent_cap", "validation_failed")
                )
            if (
                workout.descent_ceiling_meters < 0
                or workout.descent_ceiling_meters
                > statistics.recent_maximum_session_descent_meters
            ):
                violations.append(
                    PlanInvariantViolation("session_descent_cap", "validation_failed")
                )
            if (
                workout.terrain_reference
                != generation_input.prevalidation.training_terrain_reference
            ):
                violations.append(
                    PlanInvariantViolation("terrain_reference", "validation_failed")
                )
            if workout.intensity_bucket == "quality":
                if workout.workout_type != "controlled_quality":
                    violations.append(
                        PlanInvariantViolation(
                            "quality_workout_type",
                            "validation_failed",
                        )
                    )
                if (
                    workout.template_id
                    != CONTROLLED_UPHILL_TEMPLATE.template_id
                    or workout.steps != CONTROLLED_UPHILL_TEMPLATE.steps
                    or workout.planned_duration_min != 38
                ):
                    violations.append(
                        PlanInvariantViolation(
                            "quality_template",
                            "validation_failed",
                        )
                    )
            else:
                if workout.workout_type not in {"easy", "longest_easy"}:
                    violations.append(
                        PlanInvariantViolation(
                            "easy_workout_type",
                            "validation_failed",
                        )
                    )
                if (
                    workout.template_id is not None
                    or workout.steps
                    != (
                        TrailWorkoutStep(
                            kind="step",
                            phase="easy",
                            duration_min=workout.planned_duration_min,
                            intended_intensity="low",
                        ),
                    )
                ):
                    violations.append(
                        PlanInvariantViolation(
                            "easy_template",
                            "validation_failed",
                        )
                    )

    for previous, current in zip(quality_dates, quality_dates[1:], strict=False):
        if (current - previous).days <= 1:
            violations.append(
                PlanInvariantViolation("quality_spacing", "validation_failed")
            )
    ordered_running_dates = tuple(sorted(seen_dates))
    for previous, current in zip(
        ordered_running_dates,
        ordered_running_dates[1:],
        strict=False,
    ):
        if (current - previous).days <= 1:
            violations.append(
                PlanInvariantViolation(
                    "adjacent_running_days",
                    "validation_failed",
                )
            )
    return tuple(violations)


def _build_schedule(
    *,
    generation_input: NonUltraTrailGenerationInput,
    statistics: RecentTrailHistoryStatistics,
) -> tuple[GeneratedTrailWeek, ...] | None:
    constraints = generation_input.constraints
    frequency = min(
        len(constraints.available_weekdays),
        statistics.recent_modal_running_frequency,
        _MAX_RUN_DAYS,
    )
    if frequency < _MIN_RUN_DAYS:
        return None
    session_cap = min(
        constraints.maximum_session_duration_min,
        statistics.recent_maximum_session_minutes,
    )
    weekly_target = min(
        constraints.weekly_time_limit_min,
        statistics.recent_median_usable_weekly_minutes,
    )
    weekly_hard_cap = min(
        constraints.weekly_time_limit_min,
        statistics.recent_maximum_usable_weekly_minutes,
    )
    if (
        session_cap < CONTROLLED_UPHILL_TEMPLATE.total_minutes
        or weekly_target <= 0
        or weekly_target > weekly_hard_cap
        or statistics.recent_median_usable_weekly_ascent_meters <= 0
        or statistics.recent_maximum_session_ascent_meters <= 0
    ):
        return None

    blocked = set(constraints.unavailable_dates) | set(
        constraints.reserved_dates
    )
    weeks: list[GeneratedTrailWeek] = []
    previous_quality_date: date | None = None
    previous_workout_date: date | None = None
    for week_index in range(NON_ULTRA_TRAIL_PROPOSAL_DAYS // 7):
        week_start = generation_input.block_start + timedelta(
            days=week_index * _SCHEDULE_UNIT_DAYS
        )
        week_end = week_start + timedelta(days=6)
        available = tuple(
            value
            for value in (
                week_start + timedelta(days=offset)
                for offset in range(_SCHEDULE_UNIT_DAYS)
            )
            if value.weekday() in constraints.available_weekdays
            and value not in blocked
            and value < generation_input.goal.target_event_date
        )
        unit_frequency = min(frequency, len(available))
        if unit_frequency < _MIN_RUN_DAYS:
            return None
        selected = _select_schedule_dates(
            available,
            frequency=unit_frequency,
            preferred_longest_easy_weekday=(
                constraints.preferred_longest_easy_weekday
            ),
            previous_workout_date=previous_workout_date,
        )
        if selected is None:
            return None
        quality_date = _select_quality_date(
            selected,
            preferred_longest_easy_weekday=(
                constraints.preferred_longest_easy_weekday
            ),
            previous_quality_date=previous_quality_date,
        )
        if quality_date is None:
            return None
        workouts = _build_week_workouts(
            dates=selected,
            quality_date=quality_date,
            total_minutes=weekly_target,
            session_cap=session_cap,
            ascent_target=statistics.recent_median_usable_weekly_ascent_meters,
            ascent_session_cap=(
                statistics.recent_maximum_session_ascent_meters
            ),
            descent_target=(
                statistics.recent_median_usable_weekly_descent_meters
            ),
            descent_session_cap=(
                statistics.recent_maximum_session_descent_meters
            ),
            preferred_longest_easy_weekday=(
                constraints.preferred_longest_easy_weekday
            ),
            terrain_reference=str(
                generation_input.prevalidation.training_terrain_reference
            ),
        )
        if workouts is None:
            return None
        weeks.append(
            GeneratedTrailWeek(
                week_number=week_index + 1,
                start_date=week_start,
                end_date=week_end,
                weekly_ascent_ceiling_meters=sum(
                    item.ascent_ceiling_meters for item in workouts
                ),
                weekly_descent_ceiling_meters=sum(
                    item.descent_ceiling_meters for item in workouts
                ),
                workouts=workouts,
            )
        )
        previous_quality_date = quality_date
        previous_workout_date = max(selected)
    return tuple(weeks)


def _build_week_workouts(
    *,
    dates: Sequence[date],
    quality_date: date,
    total_minutes: int,
    session_cap: int,
    ascent_target: int,
    ascent_session_cap: int,
    descent_target: int,
    descent_session_cap: int,
    preferred_longest_easy_weekday: int | None,
    terrain_reference: str,
) -> tuple[GeneratedTrailWorkout, ...] | None:
    easy_dates = tuple(value for value in sorted(dates) if value != quality_date)
    remaining_minutes = total_minutes - CONTROLLED_UPHILL_TEMPLATE.total_minutes
    if remaining_minutes < len(easy_dates):
        return None
    easy_allocations = _allocate_easy_minutes(
        easy_dates,
        total_minutes=remaining_minutes,
        preferred_longest_easy_weekday=preferred_longest_easy_weekday,
    )
    if any(value > session_cap for value in easy_allocations.values()):
        return None
    low_minutes = (
        CONTROLLED_UPHILL_TEMPLATE.low_intensity_minutes
        + sum(easy_allocations.values())
    )
    if total_minutes <= 0 or low_minutes / total_minutes < _LOW_INTENSITY_FLOOR:
        return None

    longest_date = _longest_easy_date(
        easy_dates,
        preferred_longest_easy_weekday=preferred_longest_easy_weekday,
    )
    ascent_allocations = _allocate_integer_ceiling(
        dates,
        total_ceiling=ascent_target,
        per_session_ceiling=ascent_session_cap,
        priority=(
            quality_date,
            *tuple(value for value in dates if value != quality_date),
        ),
    )
    descent_priority = (
        (longest_date,) if longest_date is not None else ()
    ) + tuple(value for value in dates if value != longest_date)
    descent_allocations = _allocate_integer_ceiling(
        dates,
        total_ceiling=descent_target,
        per_session_ceiling=descent_session_cap,
        priority=descent_priority,
    )
    if ascent_allocations is None or descent_allocations is None:
        return None

    workouts: list[GeneratedTrailWorkout] = []
    for scheduled_date in sorted(dates):
        if scheduled_date == quality_date:
            workouts.append(
                GeneratedTrailWorkout(
                    scheduled_date=scheduled_date,
                    workout_type="controlled_quality",
                    intensity_bucket="quality",
                    planned_duration_min=(
                        CONTROLLED_UPHILL_TEMPLATE.total_minutes
                    ),
                    ascent_ceiling_meters=ascent_allocations[scheduled_date],
                    descent_ceiling_meters=descent_allocations[scheduled_date],
                    terrain_reference=terrain_reference,
                    template_id=CONTROLLED_UPHILL_TEMPLATE.template_id,
                    steps=CONTROLLED_UPHILL_TEMPLATE.steps,
                )
            )
            continue
        duration = easy_allocations.get(scheduled_date, 0)
        if duration <= 0:
            return None
        workouts.append(
            GeneratedTrailWorkout(
                scheduled_date=scheduled_date,
                workout_type=(
                    "longest_easy"
                    if scheduled_date == longest_date
                    else "easy"
                ),
                intensity_bucket="low",
                planned_duration_min=duration,
                ascent_ceiling_meters=ascent_allocations[scheduled_date],
                descent_ceiling_meters=descent_allocations[scheduled_date],
                terrain_reference=terrain_reference,
                template_id=None,
                steps=(
                    TrailWorkoutStep(
                        kind="step",
                        phase="easy",
                        duration_min=duration,
                        intended_intensity="low",
                    ),
                ),
            )
        )
    return tuple(workouts)


def _allocate_easy_minutes(
    dates: Sequence[date],
    *,
    total_minutes: int,
    preferred_longest_easy_weekday: int | None,
) -> dict[date, int]:
    if not dates:
        return {}
    base, remainder = divmod(total_minutes, len(dates))
    allocations = {value: base for value in dates}
    priority = _easy_allocation_priority(
        dates,
        preferred_longest_easy_weekday=preferred_longest_easy_weekday,
    )
    for value in priority[:remainder]:
        allocations[value] += 1
    return allocations


def _allocate_integer_ceiling(
    dates: Sequence[date],
    *,
    total_ceiling: int,
    per_session_ceiling: int,
    priority: Sequence[date],
) -> dict[date, int] | None:
    ordered = tuple(dict.fromkeys(priority))
    if (
        not dates
        or set(ordered) != set(dates)
        or total_ceiling < 0
        or per_session_ceiling < 0
    ):
        return None
    effective_total = min(total_ceiling, per_session_ceiling * len(dates))
    quotient, remainder = divmod(effective_total, len(ordered))
    allocations = {value: quotient for value in ordered}
    for value in ordered[:remainder]:
        allocations[value] += 1
    if any(value > per_session_ceiling for value in allocations.values()):
        return None
    return allocations


def _select_schedule_dates(
    dates: Sequence[date],
    *,
    frequency: int,
    preferred_longest_easy_weekday: int | None,
    previous_workout_date: date | None,
) -> tuple[date, ...] | None:
    ordered = tuple(sorted(set(dates)))
    if len(ordered) < frequency:
        return None
    candidates = tuple(
        candidate
        for candidate in combinations(ordered, frequency)
        if all(
            (current - previous).days > 1
            for previous, current in zip(
                candidate,
                candidate[1:],
                strict=False,
            )
        )
        and (
            previous_workout_date is None
            or (candidate[0] - previous_workout_date).days > 1
        )
    )
    if not candidates:
        return None
    preferred_candidates = tuple(
        candidate
        for candidate in candidates
        if preferred_longest_easy_weekday is not None
        and any(
            value.weekday() == preferred_longest_easy_weekday
            for value in candidate
        )
    )
    return min(preferred_candidates or candidates)


def _select_quality_date(
    dates: Sequence[date],
    *,
    preferred_longest_easy_weekday: int | None,
    previous_quality_date: date | None,
) -> date | None:
    longest = _longest_easy_date(
        dates,
        preferred_longest_easy_weekday=preferred_longest_easy_weekday,
    )
    unit_start = min(dates, default=None)
    if unit_start is None:
        return None
    candidates = sorted(
        (value for value in dates if value != longest),
        key=lambda value: (abs((value - unit_start).days - 2), value),
    )
    return next(
        (
            value
            for value in candidates
            if previous_quality_date is None
            or (value - previous_quality_date).days > 1
        ),
        None,
    )


def _longest_easy_date(
    dates: Sequence[date],
    *,
    preferred_longest_easy_weekday: int | None,
) -> date | None:
    if preferred_longest_easy_weekday is not None:
        preferred = next(
            (
                value
                for value in sorted(dates)
                if value.weekday() == preferred_longest_easy_weekday
            ),
            None,
        )
        if preferred is not None:
            return preferred
    return max(dates, default=None)


def _easy_allocation_priority(
    dates: Sequence[date],
    *,
    preferred_longest_easy_weekday: int | None,
) -> tuple[date, ...]:
    longest = _longest_easy_date(
        dates,
        preferred_longest_easy_weekday=preferred_longest_easy_weekday,
    )
    if longest is None:
        return ()
    return (longest,) + tuple(value for value in sorted(dates) if value != longest)


def _contract_issue(
    generation_input: NonUltraTrailGenerationInput,
) -> _InputIssue | None:
    if (
        generation_input.ontology_decision_id
        != NON_ULTRA_TRAIL_ONTOLOGY_DECISION_ID
        or generation_input.ontology_contract_digest
        != NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT_DIGEST
        or generation_input.ontology_source_decision_digest
        != NON_ULTRA_TRAIL_ONTOLOGY_SOURCE_DECISION_DIGEST
    ):
        return _InputIssue(
            code="ontology_not_accepted",
            detail_reason="ontology_contract_mismatch",
            rule_id="accepted_ontology_contract",
        )
    if (
        generation_input.policy_version != NON_ULTRA_TRAIL_POLICY_VERSION
        or generation_input.science_decision_id
        != NON_ULTRA_TRAIL_SCIENCE_DECISION_ID
        or generation_input.contract_digest != NON_ULTRA_TRAIL_CONTRACT_DIGEST
        or generation_input.source_decision_digest
        != NON_ULTRA_TRAIL_SOURCE_DECISION_DIGEST
    ):
        return _InputIssue(
            code="policy_inactive",
            detail_reason="policy_contract_mismatch",
            rule_id="accepted_inactive_policy_contract",
        )
    return None


def _scope_issue(
    generation_input: NonUltraTrailGenerationInput,
) -> _InputIssue | None:
    goal = generation_input.goal
    constraints = generation_input.constraints
    if goal.event_format != "single_day" or goal.distance_family != "non_ultra":
        return _InputIssue(
            code="unsupported_ultra_or_multiday",
            detail_reason="unsupported_ultra_or_multiday",
            rule_id="scope_and_dependencies",
        )
    if goal.intent != "performance" or goal.clinical_or_return_to_sport:
        return _InputIssue(
            code="adult_scope_or_constraints_unconfirmed",
            detail_reason="adult_scope_or_constraints_unconfirmed",
            rule_id="scope_and_dependencies",
        )
    if constraints.adult_confirmed is not True:
        return _InputIssue(
            code="adult_scope_or_constraints_unconfirmed",
            detail_reason="adult_scope_or_constraints_unconfirmed",
            rule_id="adult_scope",
            missing_field="adult confirmation",
        )
    if constraints.current_symptom_stop is None:
        return _InputIssue(
            code="adult_scope_or_constraints_unconfirmed",
            detail_reason="adult_scope_or_constraints_unconfirmed",
            rule_id="current_symptom_stop",
            missing_field="current symptom-stop response",
        )
    if constraints.current_symptom_stop is True:
        return _InputIssue(
            code="current_symptom_stop",
            detail_reason="current_symptom_stop",
            rule_id="current_symptom_stop",
        )
    if not goal.event_confirmed:
        return _InputIssue(
            code="course_clarification_required",
            detail_reason="course_clarification_required",
            rule_id="confirmed_event",
            missing_field="athlete-confirmed event",
        )
    if generation_input.block_start < generation_input.athlete_today:
        return _InputIssue(
            code="adult_scope_or_constraints_unconfirmed",
            detail_reason="contradictory_input",
            rule_id="block_start",
        )
    return None


def _course_issue(course: TrailCourseDemand) -> _InputIssue | None:
    if course.schema_id != NON_ULTRA_TRAIL_COURSE_SCHEMA_ID:
        return _InputIssue(
            code="ontology_not_accepted",
            detail_reason="ontology_contract_mismatch",
            rule_id="course_schema",
        )
    if course.athlete_confirmed is not True:
        return _InputIssue(
            code="course_clarification_required",
            detail_reason="course_clarification_required",
            rule_id="athlete_confirmed_course",
            missing_field=NON_ULTRA_TRAIL_COURSE_SCHEMA_ID,
        )
    for field_name, field in _course_fields(course):
        if (
            field.provenance == "explicit_assumption"
            and field.athlete_confirmed is not True
        ):
            return _InputIssue(
                code="course_clarification_required",
                detail_reason="course_clarification_required",
                rule_id="assumption_confirmation",
                missing_field=field_name,
            )
    for field_name in _MATERIAL_COURSE_FIELDS:
        field = getattr(course, field_name)
        if field.is_unknown:
            return _InputIssue(
                code="material_course_demand_unknown",
                detail_reason="material_course_demand_unknown",
                rule_id="material_course_demand",
                missing_field=field_name,
            )
        if isinstance(field.value, Mapping) and not field.value:
            return _InputIssue(
                code="course_clarification_required",
                detail_reason="course_clarification_required",
                rule_id="material_course_demand",
                missing_field=field_name,
            )
    return None


def _prevalidation_issue(
    prevalidation: InternalTrailPrevalidation,
) -> _InputIssue | None:
    if prevalidation.course_demand_eligible is None:
        return _InputIssue(
            code="material_course_demand_unknown",
            detail_reason="material_course_demand_unknown",
            rule_id="internal_course_prevalidation",
        )
    if prevalidation.course_demand_eligible is not True:
        return _InputIssue(
            code="course_clarification_required",
            detail_reason="course_clarification_required",
            rule_id="internal_course_prevalidation",
        )
    if prevalidation.terrain_access_eligible is None:
        return _InputIssue(
            code="material_course_demand_unknown",
            detail_reason="insufficient_terrain_access",
            rule_id="internal_terrain_prevalidation",
        )
    if prevalidation.terrain_access_eligible is not True:
        return _InputIssue(
            code="insufficient_terrain_access",
            detail_reason="insufficient_terrain_access",
            rule_id="internal_terrain_prevalidation",
        )
    if prevalidation.nontechnical_uphill_accessible is not True:
        return _InputIssue(
            code=(
                "material_course_demand_unknown"
                if prevalidation.nontechnical_uphill_accessible is None
                else "insufficient_terrain_access"
            ),
            detail_reason="insufficient_terrain_access",
            rule_id="controlled_uphill_access",
        )
    if not str(prevalidation.training_terrain_reference or "").strip():
        return _InputIssue(
            code="material_course_demand_unknown",
            detail_reason="insufficient_terrain_access",
            rule_id="training_terrain_reference",
        )
    return None


def _history_issue(
    statistics: RecentTrailHistoryStatistics,
    *,
    athlete_today: date,
) -> _InputIssue | None:
    if statistics.usable_completed_weeks < _MINIMUM_USABLE_WEEKS:
        return _InputIssue(
            code="insufficient_comparable_history",
            detail_reason="insufficient_recent_history",
            rule_id="usable_completed_weeks",
        )
    if (
        statistics.latest_run_date is None
        or (athlete_today - statistics.latest_run_date).days > _LATEST_RUN_DAYS
    ):
        return _InputIssue(
            code="insufficient_comparable_history",
            detail_reason="insufficient_recent_history",
            rule_id="latest_run",
        )
    if (
        statistics.comparable_trail_sessions_within_window < _COMPARABLE_COUNT
        or statistics.latest_comparable_trail_session_date is None
        or (
            athlete_today - statistics.latest_comparable_trail_session_date
        ).days
        > _LATEST_COMPARABLE_DAYS
    ):
        return _InputIssue(
            code="insufficient_comparable_history",
            detail_reason="insufficient_comparable_trail_history",
            rule_id="comparable_trail_exposure",
        )
    return None


def _constraint_issue(
    constraints: TrailPlanGenerationConstraints,
) -> _InputIssue | None:
    weekdays = constraints.available_weekdays
    if constraints.schema_id != NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID:
        return _InputIssue(
            code="adult_scope_or_constraints_unconfirmed",
            detail_reason="contradictory_input",
            rule_id="constraint_schema",
        )
    if len(set(weekdays)) != len(weekdays) or any(
        value < 0 or value > 6 for value in weekdays
    ):
        return _InputIssue(
            code="adult_scope_or_constraints_unconfirmed",
            detail_reason="contradictory_input",
            rule_id="available_weekdays",
        )
    if len(weekdays) < _MIN_RUN_DAYS:
        return _InputIssue(
            code="adult_scope_or_constraints_unconfirmed",
            detail_reason="no_schedule_within_envelope",
            rule_id="available_weekdays",
        )
    if len(weekdays) > _MAX_RUN_DAYS:
        return _InputIssue(
            code="adult_scope_or_constraints_unconfirmed",
            detail_reason="clarification_required",
            rule_id="available_weekdays",
        )
    if (
        constraints.weekly_time_limit_min <= 0
        or constraints.maximum_session_duration_min <= 0
    ):
        return _InputIssue(
            code="adult_scope_or_constraints_unconfirmed",
            detail_reason="adult_scope_or_constraints_unconfirmed",
            rule_id="duration_constraints",
        )
    preferred = constraints.preferred_longest_easy_weekday
    if preferred is not None and preferred not in weekdays:
        return _InputIssue(
            code="adult_scope_or_constraints_unconfirmed",
            detail_reason="contradictory_input",
            rule_id="preferred_longest_easy_weekday",
        )
    return None


def _limited_modules(
    course: TrailCourseDemand,
    prevalidation: InternalTrailPrevalidation,
) -> tuple[str, ...]:
    limited: set[str] = set()
    if (
        course.maximum_altitude_meters.is_unknown
        or course.environmental_demand.is_unknown
    ):
        limited.add("environment_module_limited")
    if course.fueling_practice_experience.is_unknown:
        limited.add("fueling_module_limited")
    if prevalidation.technical_terrain_module_supported is not True:
        limited.add("technicality_module_limited")
    return tuple(sorted(limited))


def _generation_input_primitive_issue(
    generation_input: NonUltraTrailGenerationInput,
) -> _InputIssue | None:
    for field_name in (
        "policy_version",
        "science_decision_id",
        "contract_digest",
        "source_decision_digest",
        "ontology_decision_id",
        "ontology_contract_digest",
        "ontology_source_decision_digest",
    ):
        if not isinstance(getattr(generation_input, field_name), str):
            return _primitive_issue(field_name)
    if type(generation_input.athlete_today) is not date:
        return _primitive_issue("athlete_today")
    if type(generation_input.block_start) is not date:
        return _primitive_issue("block_start")
    goal = generation_input.goal
    if not isinstance(goal, NonUltraTrailGoal):
        return _primitive_issue("goal")
    if not all(
        isinstance(value, str)
        for value in (goal.intent, goal.event_format, goal.distance_family)
    ):
        return _primitive_issue("goal")
    if type(goal.target_event_date) is not date:
        return _primitive_issue("target_event_date")
    if type(goal.event_confirmed) is not bool:
        return _primitive_issue("event_confirmed")
    if type(goal.clinical_or_return_to_sport) is not bool:
        return _primitive_issue("clinical_or_return_to_sport")

    course_issue = _course_primitive_issue(generation_input.course_demand)
    if course_issue is not None:
        return course_issue
    history_issue = _history_primitive_issue(
        generation_input.history,
        athlete_today=generation_input.athlete_today,
    )
    if history_issue is not None:
        return history_issue
    constraints = generation_input.constraints
    if not isinstance(constraints, TrailPlanGenerationConstraints):
        return _primitive_issue("constraints")
    if type(constraints.adult_confirmed) not in {bool, type(None)}:
        return _primitive_issue("adult_confirmed")
    if type(constraints.current_symptom_stop) not in {bool, type(None)}:
        return _primitive_issue("current_symptom_stop")
    if not isinstance(constraints.available_weekdays, tuple) or any(
        type(value) is not int for value in constraints.available_weekdays
    ):
        return _primitive_issue("available_weekdays")
    if type(constraints.weekly_time_limit_min) is not int:
        return _primitive_issue("weekly_time_limit_min")
    if type(constraints.maximum_session_duration_min) is not int:
        return _primitive_issue("maximum_session_duration_min")
    if any(
        type(value) is not date
        for value in (*constraints.unavailable_dates, *constraints.reserved_dates)
    ):
        return _primitive_issue("blocked_dates")
    if (
        constraints.preferred_longest_easy_weekday is not None
        and type(constraints.preferred_longest_easy_weekday) is not int
    ):
        return _primitive_issue("preferred_longest_easy_weekday")
    if not isinstance(constraints.schema_id, str):
        return _primitive_issue("constraint_schema")
    prevalidation = generation_input.prevalidation
    if not isinstance(prevalidation, InternalTrailPrevalidation):
        return _primitive_issue("prevalidation")
    if any(
        type(value) not in {bool, type(None)}
        for value in (
            prevalidation.course_demand_eligible,
            prevalidation.terrain_access_eligible,
            prevalidation.nontechnical_uphill_accessible,
            prevalidation.technical_terrain_module_supported,
        )
    ):
        return _primitive_issue("prevalidation")
    if (
        prevalidation.training_terrain_reference is not None
        and not isinstance(prevalidation.training_terrain_reference, str)
    ):
        return _primitive_issue("training_terrain_reference")
    return None


def _course_primitive_issue(course: TrailCourseDemand) -> _InputIssue | None:
    if not isinstance(course, TrailCourseDemand):
        return _primitive_issue("course_demand")
    if type(course.athlete_confirmed) is not bool or not isinstance(
        course.schema_id,
        str,
    ):
        return _primitive_issue("course_demand")
    for field_name, field in _course_fields(course):
        if not isinstance(field, ProvenancedValue):
            return _primitive_issue(field_name)
        if field.provenance not in NON_ULTRA_TRAIL_ALLOWED_PROVENANCE:
            return _primitive_issue(f"{field_name}.provenance")
        if type(field.athlete_confirmed) is not bool:
            return _primitive_issue(f"{field_name}.athlete_confirmed")
        if field.source_reference is not None and (
            not isinstance(field.source_reference, str)
            or not field.source_reference.strip()
        ):
            return _primitive_issue(f"{field_name}.source_reference")
        if (
            field.source_timestamp is not None
            and type(field.source_timestamp) is not date
        ):
            return _primitive_issue(f"{field_name}.source_timestamp")
        if field.model_version is not None and (
            not isinstance(field.model_version, str) or not field.model_version.strip()
        ):
            return _primitive_issue(f"{field_name}.model_version")
        if field.is_unknown and field.value is not None:
            return _primitive_issue(f"{field_name}.unknown_value")
        if not field.is_unknown and field.value is None:
            return _primitive_issue(f"{field_name}.value")
        if field.provenance == "model_inferred" and not field.model_version:
            return _primitive_issue(f"{field_name}.model_version")
        if not _is_json_value(field.value):
            return _primitive_issue(f"{field_name}.value")
        if field_name in _INTEGER_COURSE_FIELDS and not field.is_unknown:
            if type(field.value) is not int:
                return _primitive_issue(field_name)
            minimum = NON_ULTRA_TRAIL_COURSE_SCHEMA["fields"][field_name].get(
                "minimum"
            )
            if minimum is not None and int(field.value) < int(minimum):
                return _primitive_issue(field_name)
        if field_name in _OBJECT_COURSE_FIELDS and not field.is_unknown:
            if not isinstance(field.value, Mapping):
                return _primitive_issue(field_name)
    return None


def _history_primitive_issue(
    history: Sequence[TrailRunningHistoryObservation],
    *,
    athlete_today: date,
) -> _InputIssue | None:
    if type(athlete_today) is not date:
        return _primitive_issue("athlete_today")
    if len(history) > _MAX_HISTORY_OBSERVATIONS:
        return _primitive_issue("history_observation_count")
    activity_ids = [
        item.activity_id
        for item in history
        if isinstance(item, TrailRunningHistoryObservation)
        and isinstance(item.activity_id, str)
    ]
    if len(activity_ids) != len(set(activity_ids)):
        return _primitive_issue("history.duplicate_activity_id")
    for item in history:
        if not isinstance(item, TrailRunningHistoryObservation):
            return _primitive_issue("history_observation")
        if (
            not isinstance(item.activity_id, str)
            or not item.activity_id.strip()
            or not isinstance(item.activity_type, str)
            or type(item.observed_date) is not date
            or not isinstance(item.source, str)
            or not item.source.strip()
            or type(item.source_timestamp) is not datetime
            or type(item.outdoor_confirmed) is not bool
        ):
            return _primitive_issue("history_observation")
        if not _is_finite_number(item.duration_min):
            return _primitive_issue("history.duration_min")
        if item.distance_km is not None and not _is_finite_number(item.distance_km):
            return _primitive_issue("history.distance_km")
        for field_name, value in (
            ("elevation_gain_meters", item.elevation_gain_meters),
            ("elevation_loss_meters", item.elevation_loss_meters),
        ):
            if value is not None and (type(value) is not int or value < 0):
                return _primitive_issue(f"history.{field_name}")
    return None


def _primitive_issue(field_name: str) -> _InputIssue:
    return _InputIssue(
        code="validation_failed",
        detail_reason="contradictory_input",
        rule_id="primitive_validation",
        missing_field=field_name,
    )


def _course_fields(
    course: TrailCourseDemand,
) -> tuple[tuple[str, ProvenancedValue], ...]:
    return tuple(
        (field_name, getattr(course, field_name))
        for field_name in NON_ULTRA_TRAIL_COURSE_SCHEMA["fields"]
    )


def _serialize_course_demand(course: TrailCourseDemand) -> dict[str, Any]:
    return {
        "schema_id": course.schema_id,
        "athlete_confirmed": course.athlete_confirmed,
        "fields": {
            name: value.public_payload()
            for name, value in sorted(_course_fields(course))
        },
    }


def _serialize_history_observation(
    item: TrailRunningHistoryObservation,
) -> dict[str, Any]:
    return {
        "activity_id": item.activity_id,
        "observed_date": item.observed_date.isoformat(),
        "activity_type": item.activity_type,
        "duration_min": item.duration_min,
        "distance_km": item.distance_km,
        "elevation_gain_meters": item.elevation_gain_meters,
        "elevation_loss_meters": item.elevation_loss_meters,
        "source": item.source,
        "source_timestamp": item.source_timestamp.isoformat(),
        "outdoor_confirmed": item.outdoor_confirmed,
    }


def _history_canonical_sort_key(
    item: TrailRunningHistoryObservation,
) -> str:
    return json.dumps(
        _serialize_history_observation(item),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _is_qualifying_run(item: TrailRunningHistoryObservation) -> bool:
    return (
        item.activity_type in _HISTORY_ACTIVITY_TYPES
        and item.outdoor_confirmed is True
        and type(item.source_timestamp) is datetime
        and item.duration_min > 0
        and item.distance_km is not None
        and item.distance_km > 0
    )


def _is_comparable_trail(item: TrailRunningHistoryObservation) -> bool:
    return (
        _is_qualifying_run(item)
        and item.activity_type == "trail_running"
        and item.elevation_gain_meters is not None
        and item.elevation_loss_meters is not None
    )


def _workout_low_minutes(workout: GeneratedTrailWorkout) -> int:
    if workout.intensity_bucket == "low":
        return workout.planned_duration_min
    if workout.template_id == CONTROLLED_UPHILL_TEMPLATE.template_id:
        return CONTROLLED_UPHILL_TEMPLATE.low_intensity_minutes
    return 0


def _integer_median(values: Sequence[int]) -> int:
    if not values:
        return 0
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("integer median requires nonnegative integers")
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) // 2


def _duration_minutes_total(
    values: Sequence[TrailRunningHistoryObservation],
) -> int:
    total = sum(
        (_exact_number_fraction(value.duration_min) for value in values),
        start=Fraction(0),
    )
    return int(total)


def _exact_number_fraction(value: int | float) -> Fraction:
    if type(value) is int:
        return Fraction(value)
    numerator, denominator = value.as_integer_ratio()
    return Fraction(numerator, denominator)


def _conservative_mode(values: Sequence[int]) -> int:
    if not values:
        return 0
    counts = {value: values.count(value) for value in set(values)}
    maximum = max(counts.values())
    return min(value for value, count in counts.items() if count == maximum)


def _is_finite_number(value: Any) -> bool:
    if type(value) is int:
        return True
    if type(value) is float:
        return math.isfinite(value)
    return False


def _is_json_value(value: Any) -> bool:
    if value is None or type(value) in {bool, int, str}:
        return True
    if type(value) is float:
        return math.isfinite(value)
    if isinstance(value, Mapping):
        return all(
            isinstance(key, str) and _is_json_value(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return all(_is_json_value(item) for item in value)
    return False


def _no_plan(
    *,
    issue: _InputIssue,
    input_hash: str,
    statistics: RecentTrailHistoryStatistics,
    limited_modules: tuple[str, ...] = (),
) -> NonUltraTrailGenerationResult:
    if issue.code not in NON_ULTRA_TRAIL_NO_PLAN_RESULT_CODES:
        raise ValueError("code must be a canonical accepted no-plan result")
    return NonUltraTrailGenerationResult(
        policy_version=NON_ULTRA_TRAIL_POLICY_VERSION,
        generator_version=NON_ULTRA_TRAIL_GENERATOR_VERSION,
        science_decision_id=NON_ULTRA_TRAIL_SCIENCE_DECISION_ID,
        contract_digest=NON_ULTRA_TRAIL_CONTRACT_DIGEST,
        source_decision_digest=NON_ULTRA_TRAIL_SOURCE_DECISION_DIGEST,
        code=issue.code,
        detail_reason=issue.detail_reason,
        deterministic_input_hash=input_hash,
        plan=None,
        history_statistics=statistics,
        limited_modules=limited_modules,
        failed_rule_id=issue.rule_id,
        uncertainty_or_missing_field=issue.missing_field,
    )


def _serialize_step(step: TrailWorkoutStep) -> dict[str, Any]:
    if step.kind == "repeat":
        return {
            "type": "repeat",
            "repetitions": step.repetitions,
            "steps": [_serialize_step(child) for child in step.steps],
        }
    return {
        "type": "step",
        "phase": step.phase,
        "termination": {
            "type": "time",
            "seconds": int(step.duration_min or 0) * 60,
        },
        "intended_intensity": step.intended_intensity,
        "target": {
            "metric": "none",
            "unit": "none",
            "reference": "none",
        },
    }


def _invalid_input_hash(
    generation_input: NonUltraTrailGenerationInput,
    issue: _InputIssue,
) -> str:
    return _canonical_fingerprint({
        "invalid_input": True,
        "rule_id": issue.rule_id,
        "field": issue.missing_field,
        "sanitized_input": _sanitize_invalid_value(generation_input),
    })


def _sanitize_invalid_value(value: Any) -> Any:
    if type(value) in {date, datetime}:
        return value.isoformat()
    if type(value) is float:
        if math.isnan(value):
            return {"__nonfinite_float__": "nan"}
        if math.isinf(value):
            return {
                "__nonfinite_float__": (
                    "positive_infinity" if value > 0 else "negative_infinity"
                )
            }
        return value
    if value is None or type(value) in {bool, int, str}:
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _sanitize_invalid_value(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        pairs = [
            (
                _sanitize_invalid_value(key),
                _sanitize_invalid_value(item),
            )
            for key, item in value.items()
        ]
        return {
            "__mapping__": sorted(
                pairs,
                key=lambda pair: json.dumps(
                    pair[0],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_invalid_value(item) for item in value]
    return {"__unsupported_type__": type(value).__qualname__}


def _canonical_fingerprint(value: Any) -> str:
    canonical = json.dumps(
        _json_safe_dates(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _json_safe_dates(value: Any) -> Any:
    if type(value) in {date, datetime}:
        return value.isoformat()
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe_dates(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe_dates(item) for item in value]
    return value
