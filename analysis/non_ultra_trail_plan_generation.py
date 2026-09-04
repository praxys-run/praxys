"""Pure deterministic core for the accepted, inactive Trail v2 policy.

This module has no database, HTTP, clock, provider, credential, registry, or
capability-discovery dependency. The normal entry point respects the
materialized ``inactive`` contract and cannot return a proposal. The explicit
dry-run entry point exists only for synthetic deterministic verification under
the accepted dry-run policy; it adds no runtime authority or reachability.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import hashlib
from itertools import combinations
import json
import math
from typing import Any, Literal, Mapping, Sequence

from analysis.non_ultra_trail_contract import (
    NON_ULTRA_TRAIL_ALLOWED_PROVENANCE,
    NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID,
    NON_ULTRA_TRAIL_CONTRACT,
    NON_ULTRA_TRAIL_CONTRACT_DIGEST,
    NON_ULTRA_TRAIL_COURSE_SCHEMA_ID,
    NON_ULTRA_TRAIL_DETAIL_REASON_CATALOG,
    NON_ULTRA_TRAIL_FOOTING_AND_HAZARDS,
    NON_ULTRA_TRAIL_GENERATOR_VERSION,
    NON_ULTRA_TRAIL_GRADE_DISTRIBUTION,
    NON_ULTRA_TRAIL_HISTORY,
    NON_ULTRA_TRAIL_HISTORY_LOOKBACK_COMPLETED_WEEKS,
    NON_ULTRA_TRAIL_INTENSITY,
    NON_ULTRA_TRAIL_LIMITED_MODULE_ORDER,
    NON_ULTRA_TRAIL_MODULE_KEYS,
    NON_ULTRA_TRAIL_MODULE_STATES,
    NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT,
    NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT_DIGEST,
    NON_ULTRA_TRAIL_ONTOLOGY_DECISION_ID,
    NON_ULTRA_TRAIL_ONTOLOGY_SOURCE_DECISION_DIGEST,
    NON_ULTRA_TRAIL_ONTOLOGY_VERSION,
    NON_ULTRA_TRAIL_OPTIONAL_CONTEXT,
    NON_ULTRA_TRAIL_POLICY_VERSION,
    NON_ULTRA_TRAIL_PROPOSAL_DAYS,
    NON_ULTRA_TRAIL_REASON_PAIRS,
    NON_ULTRA_TRAIL_REASSESSMENT_DAYS,
    NON_ULTRA_TRAIL_SCHEDULE,
    NON_ULTRA_TRAIL_SCIENCE_DECISION_ID,
    NON_ULTRA_TRAIL_SOURCE_DECISION_DIGEST,
    NON_ULTRA_TRAIL_STATUS_PRECEDENCE,
    NON_ULTRA_TRAIL_TEMPLATES,
)


_SCHEDULE_UNIT_DAYS = 7
_MINIMUM_USABLE_WEEKS = int(
    NON_ULTRA_TRAIL_HISTORY["minimum_usable_completed_weeks"]
)
_MINIMUM_RUNS_PER_USABLE_WEEK = int(
    NON_ULTRA_TRAIL_HISTORY["minimum_running_sessions_per_usable_week"]
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
    NON_ULTRA_TRAIL_SCHEDULE["selected_running_days_per_7_day_unit"]["minimum"]
)
_MAX_RUN_DAYS = int(
    NON_ULTRA_TRAIL_SCHEDULE["selected_running_days_per_7_day_unit"]["maximum"]
)
_LOW_INTENSITY_FLOOR = float(
    NON_ULTRA_TRAIL_INTENSITY[
        "minimum_planned_low_intensity_running_minutes_fraction"
    ]
)
_MAX_QUALITY_PER_UNIT = int(
    NON_ULTRA_TRAIL_INTENSITY["maximum_quality_exposures_per_7_day_unit"]
)
_HISTORY_ACTIVITY_TYPES = frozenset({"running", "trail_running"})
_MAX_HISTORY_OBSERVATIONS = 1000
_DIGEST_PREFIX = "sha256:"
_GRADE_KEYS = tuple(
    str(value)
    for value in NON_ULTRA_TRAIL_GRADE_DISTRIBUTION["known_value_exact_keys"]
)
_FOOTING_VALUES = tuple(
    str(value)
    for value in NON_ULTRA_TRAIL_FOOTING_AND_HAZARDS["ordinary_footing"][
        "allowed"
    ]
)
_FOOTING_ORDER = {value: index for index, value in enumerate(_FOOTING_VALUES)}
_MANDATORY_GEAR = tuple(
    str(value)
    for value in NON_ULTRA_TRAIL_OPTIONAL_CONTEXT["support"]["mandatory_gear"][
        "allowed"
    ]
)
_GEAR_ORDER = {value: index for index, value in enumerate(_MANDATORY_GEAR)}
_SECTION_KEYS = (
    "section.event-duration",
    "section.grade-footing",
    "section.training-access",
    "section.optional-context",
)
_MODULE_LIMIT_TARGETS = {
    "grade_specificity": "course.grade_distribution",
    "technical_terrain": "course.course_footing",
    "environment_altitude": "course.optional_context.environment",
    "fueling": "course.optional_context.support",
}


@dataclass(frozen=True)
class ProvenancedValue:
    """One strict known/unknown v2 value with server-owned source metadata."""

    state: Literal["known", "unknown"]
    provenance: str
    source_revision: str
    value: Any | None = None
    source_timestamp: datetime | None = None
    model_version: str | None = None
    assumption_confirmed_revision: str | None = None

    @property
    def is_unknown(self) -> bool:
        return self.state == "unknown"

    @property
    def is_known(self) -> bool:
        return self.state == "known"

    def public_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "state": self.state,
            "provenance": self.provenance,
            "source_revision": self.source_revision,
        }
        if self.is_known:
            payload["value"] = _json_safe_dates(self.value)
        if self.source_timestamp is not None:
            payload["source_timestamp"] = self.source_timestamp.isoformat()
        if self.model_version is not None:
            payload["model_version"] = self.model_version
        if self.assumption_confirmed_revision is not None:
            payload["assumption_confirmed_revision"] = (
                self.assumption_confirmed_revision
            )
        return payload


@dataclass(frozen=True)
class TrailPlanningDurationRange:
    minimum_min: int
    maximum_min: int


@dataclass(frozen=True)
class TrailGradeDistribution:
    below_neg_10: int
    neg_10_to_below_neg_3: int
    neg_3_to_below_pos_3: int
    pos_3_to_below_pos_10: int
    pos_10_and_above: int


@dataclass(frozen=True)
class TrailEnvironmentContext:
    maximum_altitude_m: ProvenancedValue
    temperature_min_c: ProvenancedValue
    temperature_max_c: ProvenancedValue
    humidity_min_pct: ProvenancedValue
    humidity_max_pct: ProvenancedValue
    sun_exposure: ProvenancedValue
    wind_exposure: ProvenancedValue
    conditions_basis: ProvenancedValue


@dataclass(frozen=True)
class TrailSupportContext:
    aid_support_mode: ProvenancedValue
    aid_station_count: ProvenancedValue
    max_aid_station_gap_m: ProvenancedValue
    water_availability: ProvenancedValue
    food_availability: ProvenancedValue
    mandatory_gear: ProvenancedValue


@dataclass(frozen=True)
class TrailFuelingContext:
    longest_practiced_duration_min: ProvenancedValue
    practice_sessions_last_42_days: ProvenancedValue
    intake_form: ProvenancedValue
    gastrointestinal_experience: ProvenancedValue


@dataclass(frozen=True)
class TrailOptionalContext:
    environment: TrailEnvironmentContext
    support: TrailSupportContext
    fueling: TrailFuelingContext


@dataclass(frozen=True)
class TrailCourseDemand:
    """Exact typed ``trail_course_demand_v2`` server response projection."""

    event_id: str
    event_date: ProvenancedValue
    distance_meters: ProvenancedValue
    total_ascent_m: ProvenancedValue
    total_descent_m: ProvenancedValue
    planning_duration_range: ProvenancedValue
    event_format: ProvenancedValue
    distance_family: ProvenancedValue
    planning_intent: ProvenancedValue
    grade_distribution: ProvenancedValue
    course_footing: ProvenancedValue
    hands_assist: ProvenancedValue
    fixed_rope: ProvenancedValue
    optional_context: TrailOptionalContext
    schema_id: str = NON_ULTRA_TRAIL_COURSE_SCHEMA_ID

    def public_payload(self) -> dict[str, Any]:
        return _serialize_course_demand(self)


@dataclass(frozen=True)
class TrailPlanGenerationConstraints:
    """Exact typed ``non_ultra_trail_constraints_v2`` response projection."""

    available_weekdays: ProvenancedValue
    weekly_time_limit_min: ProvenancedValue
    maximum_session_duration_min: ProvenancedValue
    unavailable_dates: ProvenancedValue
    nontechnical_three_minute_uphill_access: ProvenancedValue
    controlled_downhill_access: ProvenancedValue
    accessible_footing: ProvenancedValue
    adult_nonclinical_scope_confirmed: ProvenancedValue
    performance_intent_confirmed: ProvenancedValue
    current_symptom_stop: ProvenancedValue
    preferred_longest_weekday: int | None = None
    schema_id: str = NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID

    def public_payload(self) -> dict[str, Any]:
        return _serialize_constraints(self)


@dataclass(frozen=True)
class TrailRunningHistoryObservation:
    """Internal activity input for deriving a minimized v2 history snapshot."""

    activity_id: str
    observed_date: date
    activity_type: str
    duration_min: float
    distance_km: float | None
    elevation_gain_meters: int | None
    elevation_loss_meters: int | None
    observed_footing: tuple[str, ...] | None
    source_revision: str
    source_timestamp: datetime
    outdoor_confirmed: bool


@dataclass(frozen=True)
class RecentTrailHistoryStatistics:
    """Owner-scoped, privacy-minimized, server-derived history snapshot."""

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
    comparable_ascent_sessions_within_window: int
    latest_comparable_ascent_session_date: date | None
    comparable_descent_sessions_within_window: int
    latest_comparable_descent_session_date: date | None
    recently_observed_footing: tuple[str, ...]

    @classmethod
    def empty(cls) -> "RecentTrailHistoryStatistics":
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
            comparable_ascent_sessions_within_window=0,
            latest_comparable_ascent_session_date=None,
            comparable_descent_sessions_within_window=0,
            latest_comparable_descent_session_date=None,
            recently_observed_footing=(),
        )

    def public_payload(self) -> dict[str, Any]:
        payload = _json_safe_dates(asdict(self))
        payload["recently_observed_footing"] = list(
            _canonical_footing(self.recently_observed_footing)
        )
        return payload


@dataclass(frozen=True)
class TrailSectionConfirmation:
    section_key: str
    current_revision: str
    confirmed_revision: str | None


@dataclass(frozen=True)
class TrailRevisionBindings:
    course_revision: str
    planning_context_revision: str
    history_revision: str
    composite_revision: str
    section_confirmations: tuple[TrailSectionConfirmation, ...]


@dataclass(frozen=True)
class TrailWorkloadRequest:
    """Optional explicit proposal edit; reductions are allowed, increases block."""

    weekly_running_minutes: int | None = None
    maximum_session_minutes: int | None = None
    weekly_ascent_meters: int | None = None
    weekly_descent_meters: int | None = None


@dataclass(frozen=True)
class TrailWorkoutStep:
    kind: str
    phase: str | None = None
    duration_min: int | None = None
    intended_intensity: str | None = None
    repetitions: int | None = None
    steps: tuple["TrailWorkoutStep", ...] = ()


@dataclass(frozen=True)
class GeneratedTrailWorkout:
    scheduled_date: date
    workout_type: Literal["easy", "longest_easy", "controlled_quality"]
    intensity_bucket: Literal["low", "quality"]
    planned_duration_min: int
    ascent_ceiling_meters: int
    descent_ceiling_meters: int
    terrain_footing: tuple[str, ...]
    template_id: str | None
    steps: tuple[TrailWorkoutStep, ...]
    activity_type: Literal["trail_running"] = "trail_running"


@dataclass(frozen=True)
class GeneratedTrailWeek:
    week_number: int
    start_date: date
    end_date: date
    weekly_ascent_ceiling_meters: int
    weekly_descent_ceiling_meters: int
    workouts: tuple[GeneratedTrailWorkout, ...]


@dataclass(frozen=True)
class ModuleAvailability:
    module: str
    state: Literal["not_evaluated", "available", "limited"]
    reason_target: str | None


@dataclass(frozen=True)
class MatchingReason:
    status: str
    detail_reason: str

    @property
    def namespaced(self) -> str:
        return f"{self.status}.{self.detail_reason}"


@dataclass(frozen=True)
class GeneratedNonUltraTrailPlan:
    """Synthetic, non-canonical 14-day candidate for inactive verification."""

    policy_version: str
    generator_version: str
    science_decision_id: str
    contract_digest: str
    source_decision_digest: str
    ontology_version: str
    ontology_decision_id: str
    ontology_contract_digest: str
    ontology_source_decision_digest: str
    course_schema_id: str
    constraint_schema_id: str
    contract_runtime_state: Literal["inactive"]
    synthetic_verification_only: Literal[True]
    deterministic_input_hash: str
    readiness_receipt_digest: str
    revision_bindings: TrailRevisionBindings
    horizon_start: date
    horizon_end: date
    reassessment_dates: tuple[date, ...]
    course_demand_fingerprint: str
    history_statistics: RecentTrailHistoryStatistics
    module_availability: tuple[ModuleAvailability, ...]
    limited_modules: tuple[str, ...]
    weeks: tuple[GeneratedTrailWeek, ...]

    def public_payload(self) -> dict[str, Any]:
        return _json_safe_dates(asdict(self))


@dataclass(frozen=True)
class NonUltraTrailGenerationInput:
    """Complete replay input bound to exact accepted inactive v2 contracts."""

    policy_version: str
    generator_version: str
    science_decision_id: str
    contract_digest: str
    source_decision_digest: str
    ontology_version: str
    ontology_decision_id: str
    ontology_contract_digest: str
    ontology_source_decision_digest: str
    athlete_today: date
    block_start: date
    course_demand: TrailCourseDemand
    history_statistics: RecentTrailHistoryStatistics
    constraints: TrailPlanGenerationConstraints
    revision_bindings: TrailRevisionBindings
    workload_request: TrailWorkloadRequest | None = None
    synthetic_verification_only: bool = False

    def public_payload(self) -> dict[str, Any]:
        return serialize_generation_input(self)


@dataclass(frozen=True)
class NonUltraTrailGenerationResult:
    policy_version: str
    generator_version: str
    science_decision_id: str
    contract_digest: str
    source_decision_digest: str
    ontology_version: str
    ontology_decision_id: str
    ontology_contract_digest: str
    ontology_source_decision_digest: str
    course_schema_id: str
    constraint_schema_id: str
    contract_runtime_state: str
    inactive_dry_run: bool
    status: str
    detail_reason: str | None
    matching_reasons: tuple[MatchingReason, ...]
    module_availability: tuple[ModuleAvailability, ...]
    limited_modules: tuple[str, ...]
    deterministic_input_hash: str
    readiness_receipt_digest: str
    revision_bindings: TrailRevisionBindings | None
    plan: GeneratedNonUltraTrailPlan | None
    history_statistics: RecentTrailHistoryStatistics

    def public_payload(self) -> dict[str, Any]:
        return serialize_generation_result(self)


@dataclass(frozen=True)
class PlanInvariantViolation:
    rule_id: str
    detail_reason: Literal["deterministic_invariant_failed"] = (
        "deterministic_invariant_failed"
    )


@dataclass(frozen=True)
class _WorkoutTemplate:
    template_id: str
    total_minutes: int
    low_intensity_minutes: int
    steps: tuple[TrailWorkoutStep, ...]


def _build_template_step(raw: Mapping[str, Any]) -> TrailWorkoutStep:
    if str(raw["kind"]) == "repeat":
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
    return sum(
        int(step.repetitions or 0) * _steps_duration(step.steps)
        if step.kind == "repeat"
        else int(step.duration_min or 0)
        for step in steps
    )


def _steps_low_minutes(steps: Sequence[TrailWorkoutStep]) -> int:
    return sum(
        int(step.repetitions or 0) * _steps_low_minutes(step.steps)
        if step.kind == "repeat"
        else int(step.duration_min or 0)
        if step.intended_intensity == "low"
        else 0
        for step in steps
    )


CONTROLLED_UPHILL_TEMPLATE = _WorkoutTemplate(
    template_id=str(_CONTROLLED_QUALITY_RAW["template_id"]),
    total_minutes=int(_CONTROLLED_QUALITY_RAW["total_planned_minutes"]),
    low_intensity_minutes=_steps_low_minutes(_CONTROLLED_QUALITY_STEPS),
    steps=_CONTROLLED_QUALITY_STEPS,
)
if (
    _steps_duration(CONTROLLED_UPHILL_TEMPLATE.steps) != 38
    or CONTROLLED_UPHILL_TEMPLATE.total_minutes != 38
):
    raise ValueError("accepted Trail v2 quality template must total 38 minutes")


def derive_recent_history_statistics(
    history: Sequence[TrailRunningHistoryObservation],
    *,
    athlete_today: date,
) -> RecentTrailHistoryStatistics:
    """Derive the minimized v2 snapshot without retaining raw activities."""
    issue = _history_observation_issue(history, athlete_today=athlete_today)
    if issue is not None:
        raise ValueError(issue)
    completed = tuple(
        item
        for item in history
        if _is_qualifying_run(item) and item.observed_date < athlete_today
    )
    current_week_start = athlete_today - timedelta(days=athlete_today.weekday())
    first_week_start = current_week_start - timedelta(
        days=_SCHEDULE_UNIT_DAYS
        * NON_ULTRA_TRAIL_HISTORY_LOOKBACK_COMPLETED_WEEKS
    )
    complete = tuple(
        item
        for item in completed
        if first_week_start <= item.observed_date < current_week_start
    )
    week_buckets: dict[date, list[TrailRunningHistoryObservation]] = {}
    for item in complete:
        week_start = item.observed_date - timedelta(days=item.observed_date.weekday())
        week_buckets.setdefault(week_start, []).append(item)
    usable_weeks = tuple(
        (week_start, tuple(values))
        for week_start, values in sorted(week_buckets.items())
        if len(values) >= _MINIMUM_RUNS_PER_USABLE_WEEK
        and _duration_minutes_total(values) > 0
    )
    weekly_minutes = tuple(_duration_minutes_total(values) for _, values in usable_weeks)
    weekly_ascent = tuple(
        sum(
            int(item.elevation_gain_meters or 0)
            for item in values
            if _has_comparable_ascent(item)
        )
        for _, values in usable_weeks
    )
    weekly_descent = tuple(
        sum(
            int(item.elevation_loss_meters or 0)
            for item in values
            if _has_comparable_descent(item)
        )
        for _, values in usable_weeks
    )
    all_usable = tuple(item for _, values in usable_weeks for item in values)
    ascent_usable = tuple(item for item in all_usable if _has_comparable_ascent(item))
    descent_usable = tuple(item for item in all_usable if _has_comparable_descent(item))
    windowed = tuple(
        item
        for item in completed
        if item.activity_type == "trail_running"
        and 1 <= (athlete_today - item.observed_date).days <= _COMPARABLE_WINDOW_DAYS
    )
    ascent_window = tuple(item for item in windowed if _has_comparable_ascent(item))
    descent_window = tuple(item for item in windowed if _has_comparable_descent(item))
    observed_footing = {
        footing
        for item in windowed
        for footing in (item.observed_footing or ())
    }
    frequencies = tuple(len(values) for _, values in usable_weeks)
    return RecentTrailHistoryStatistics(
        usable_completed_weeks=len(usable_weeks),
        recent_modal_running_frequency=_conservative_mode(frequencies),
        recent_median_usable_weekly_minutes=_integer_median(weekly_minutes),
        recent_maximum_usable_weekly_minutes=max(weekly_minutes, default=0),
        recent_maximum_session_minutes=int(
            max((item.duration_min for item in all_usable), default=0)
        ),
        recent_median_usable_weekly_ascent_meters=_integer_median(weekly_ascent),
        recent_maximum_usable_weekly_ascent_meters=max(weekly_ascent, default=0),
        recent_median_usable_weekly_descent_meters=_integer_median(weekly_descent),
        recent_maximum_usable_weekly_descent_meters=max(weekly_descent, default=0),
        recent_maximum_session_ascent_meters=max(
            (int(item.elevation_gain_meters or 0) for item in ascent_usable),
            default=0,
        ),
        recent_maximum_session_descent_meters=max(
            (int(item.elevation_loss_meters or 0) for item in descent_usable),
            default=0,
        ),
        latest_run_date=max((item.observed_date for item in completed), default=None),
        comparable_ascent_sessions_within_window=len(ascent_window),
        latest_comparable_ascent_session_date=max(
            (item.observed_date for item in ascent_window), default=None
        ),
        comparable_descent_sessions_within_window=len(descent_window),
        latest_comparable_descent_session_date=max(
            (item.observed_date for item in descent_window), default=None
        ),
        recently_observed_footing=_canonical_footing(observed_footing),
    )


def derive_revision_bindings(
    *,
    course_demand: TrailCourseDemand,
    constraints: TrailPlanGenerationConstraints,
    history_statistics: RecentTrailHistoryStatistics,
    confirmed: bool = True,
) -> TrailRevisionBindings:
    """Build deterministic server-side revisions for a synthetic current draft."""
    section_payloads = _section_payloads(course_demand, constraints)
    confirmations = tuple(
        TrailSectionConfirmation(
            section_key=key,
            current_revision=_revision(value),
            confirmed_revision=_revision(value) if confirmed else None,
        )
        for key, value in section_payloads
    )
    course_revision = _revision(_course_revision_payload(course_demand))
    planning_revision = _revision(
        _planning_revision_payload(course_demand, constraints)
    )
    history_revision = _revision(history_statistics.public_payload())
    return TrailRevisionBindings(
        course_revision=course_revision,
        planning_context_revision=planning_revision,
        history_revision=history_revision,
        composite_revision=_composite_revision(
            course_revision=course_revision,
            planning_context_revision=planning_revision,
            history_revision=history_revision,
            section_confirmations=confirmations,
        ),
        section_confirmations=confirmations,
    )


def generate_non_ultra_trail_plan(
    generation_input: NonUltraTrailGenerationInput,
) -> NonUltraTrailGenerationResult:
    """Evaluate the actual inactive contract; it cannot return a proposal."""
    return _evaluate(generation_input, inactive_dry_run=False)


def _dry_run_non_ultra_trail_plan(
    generation_input: NonUltraTrailGenerationInput,
) -> NonUltraTrailGenerationResult:
    """Verify the candidate envelope internally using marked synthetic input."""
    if generation_input.synthetic_verification_only is not True:
        raise ValueError("synthetic verification requires an explicit marker")
    return _evaluate(generation_input, inactive_dry_run=True)


def _evaluate(
    generation_input: NonUltraTrailGenerationInput,
    *,
    inactive_dry_run: bool,
) -> NonUltraTrailGenerationResult:
    primitive_issue = _generation_input_primitive_issue(generation_input)
    if primitive_issue is not None:
        reasons = {("validation_failed", "invalid_field_value")}
        reasons.update(_safely_evaluable_contract_reasons(generation_input))
        reasons.update(_safely_evaluable_semantic_reasons(generation_input))
        if not inactive_dry_run:
            reasons.add(("policy_unavailable", "policy_inactive"))
        return _result(
            generation_input,
            reasons=reasons,
            input_hash=_invalid_input_hash(generation_input, primitive_issue),
            statistics=RecentTrailHistoryStatistics.empty(),
            inactive_dry_run=inactive_dry_run,
        )
    if (
        _course_domain_invalid(generation_input.course_demand)
        or _constraints_domain_invalid(
            generation_input.constraints,
            block_start=generation_input.block_start,
        )
        or _history_statistics_invalid(generation_input.history_statistics)
        or _workload_request_invalid(generation_input.workload_request)
    ):
        reasons = _collect_reasons(
            generation_input,
            statistics=generation_input.history_statistics,
            include_materialized_inactive=not inactive_dry_run,
        )
        return _result(
            generation_input,
            reasons=reasons,
            input_hash=_invalid_input_hash(
                generation_input,
                "domain_validation",
            ),
            statistics=generation_input.history_statistics,
            inactive_dry_run=inactive_dry_run,
        )
    input_hash = deterministic_input_hash(generation_input)
    statistics = generation_input.history_statistics
    reasons = _collect_reasons(
        generation_input,
        statistics=statistics,
        include_materialized_inactive=not inactive_dry_run,
    )
    ordered = _ordered_reasons(reasons)
    status, detail = _primary_result(ordered)
    modules = _module_availability(
        status=status,
        detail_reason=detail,
        course=generation_input.course_demand,
    )
    limited_modules = _limited_projection(modules)
    receipt_digest = _readiness_receipt_digest(
        input_hash=input_hash,
        status=status,
        detail_reason=detail,
        reasons=ordered,
        modules=modules,
        limited_modules=limited_modules,
        revisions=generation_input.revision_bindings,
        inactive_dry_run=inactive_dry_run,
    )
    weeks = None
    if status == "eligible_proposal":
        weeks = _build_schedule(
            generation_input=generation_input,
            statistics=statistics,
        )
        if weeks is None:
            reasons.add(("readiness_blocked", "no_schedule_within_envelope"))
            return _result(
                generation_input,
                reasons=reasons,
                input_hash=input_hash,
                statistics=statistics,
                inactive_dry_run=inactive_dry_run,
            )
    plan = None
    if weeks is not None:
        plan = GeneratedNonUltraTrailPlan(
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
            course_schema_id=NON_ULTRA_TRAIL_COURSE_SCHEMA_ID,
            constraint_schema_id=NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID,
            contract_runtime_state="inactive",
            synthetic_verification_only=True,
            deterministic_input_hash=input_hash,
            readiness_receipt_digest=receipt_digest,
            revision_bindings=generation_input.revision_bindings,
            horizon_start=generation_input.block_start,
            horizon_end=generation_input.block_start
            + timedelta(days=NON_ULTRA_TRAIL_PROPOSAL_DAYS - 1),
            reassessment_dates=(
                generation_input.block_start
                + timedelta(days=NON_ULTRA_TRAIL_REASSESSMENT_DAYS),
            ),
            course_demand_fingerprint=_canonical_fingerprint(
                _serialize_course_demand(generation_input.course_demand)
            ),
            history_statistics=statistics,
            module_availability=modules,
            limited_modules=limited_modules,
            weeks=weeks,
        )
        if validate_generated_plan(plan, generation_input):
            reasons.add(("validation_failed", "deterministic_invariant_failed"))
            return _result(
                generation_input,
                reasons=reasons,
                input_hash=input_hash,
                statistics=statistics,
                inactive_dry_run=inactive_dry_run,
            )
    return NonUltraTrailGenerationResult(
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
        course_schema_id=NON_ULTRA_TRAIL_COURSE_SCHEMA_ID,
        constraint_schema_id=NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID,
        contract_runtime_state=str(NON_ULTRA_TRAIL_CONTRACT.runtime_state),
        inactive_dry_run=inactive_dry_run,
        status=status,
        detail_reason=detail,
        matching_reasons=ordered,
        module_availability=modules,
        limited_modules=limited_modules,
        deterministic_input_hash=input_hash,
        readiness_receipt_digest=receipt_digest,
        revision_bindings=generation_input.revision_bindings,
        plan=plan,
        history_statistics=statistics,
    )


def _result(
    generation_input: Any,
    *,
    reasons: set[tuple[str, str]],
    input_hash: str,
    statistics: RecentTrailHistoryStatistics,
    inactive_dry_run: bool,
) -> NonUltraTrailGenerationResult:
    ordered = _ordered_reasons(reasons)
    status, detail = _primary_result(ordered)
    course = (
        generation_input.course_demand
        if isinstance(generation_input, NonUltraTrailGenerationInput)
        and isinstance(generation_input.course_demand, TrailCourseDemand)
        else None
    )
    modules = _module_availability(
        status=status, detail_reason=detail, course=course
    )
    limited = _limited_projection(modules)
    revisions = (
        generation_input.revision_bindings
        if isinstance(generation_input, NonUltraTrailGenerationInput)
        and isinstance(generation_input.revision_bindings, TrailRevisionBindings)
        else None
    )
    receipt = _readiness_receipt_digest(
        input_hash=input_hash,
        status=status,
        detail_reason=detail,
        reasons=ordered,
        modules=modules,
        limited_modules=limited,
        revisions=revisions,
        inactive_dry_run=inactive_dry_run,
    )
    return NonUltraTrailGenerationResult(
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
        course_schema_id=NON_ULTRA_TRAIL_COURSE_SCHEMA_ID,
        constraint_schema_id=NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID,
        contract_runtime_state=str(NON_ULTRA_TRAIL_CONTRACT.runtime_state),
        inactive_dry_run=inactive_dry_run,
        status=status,
        detail_reason=detail,
        matching_reasons=ordered,
        module_availability=modules,
        limited_modules=limited,
        deterministic_input_hash=input_hash,
        readiness_receipt_digest=receipt,
        revision_bindings=revisions,
        plan=None,
        history_statistics=statistics,
    )


def deterministic_input_hash(
    generation_input: NonUltraTrailGenerationInput,
) -> str:
    issue = _generation_input_primitive_issue(generation_input)
    if issue is not None:
        raise ValueError(issue)
    if (
        _course_domain_invalid(generation_input.course_demand)
        or _constraints_domain_invalid(
            generation_input.constraints,
            block_start=generation_input.block_start,
        )
        or _history_statistics_invalid(generation_input.history_statistics)
        or _workload_request_invalid(generation_input.workload_request)
    ):
        raise ValueError("domain_validation")
    return _canonical_fingerprint(serialize_generation_input(generation_input))


def serialize_generation_input(
    generation_input: NonUltraTrailGenerationInput,
) -> dict[str, Any]:
    return {
        "policy_version": generation_input.policy_version,
        "generator_version": generation_input.generator_version,
        "science_decision_id": generation_input.science_decision_id,
        "contract_digest": generation_input.contract_digest,
        "source_decision_digest": generation_input.source_decision_digest,
        "ontology_version": generation_input.ontology_version,
        "ontology_decision_id": generation_input.ontology_decision_id,
        "ontology_contract_digest": generation_input.ontology_contract_digest,
        "ontology_source_decision_digest": (
            generation_input.ontology_source_decision_digest
        ),
        "athlete_today": generation_input.athlete_today.isoformat(),
        "block_start": generation_input.block_start.isoformat(),
        "course_demand": _serialize_course_demand(generation_input.course_demand),
        "history_statistics": generation_input.history_statistics.public_payload(),
        "constraints": _serialize_constraints(generation_input.constraints),
        "revision_bindings": _json_safe_dates(
            asdict(generation_input.revision_bindings)
        ),
        "workload_request": (
            asdict(generation_input.workload_request)
            if generation_input.workload_request is not None
            else None
        ),
        "synthetic_verification_only": (
            generation_input.synthetic_verification_only
        ),
    }


def serialize_generation_result(
    result: NonUltraTrailGenerationResult,
) -> dict[str, Any]:
    return _json_safe_dates(asdict(result))


def serialize_workout_structure(
    workout: GeneratedTrailWorkout,
) -> dict[str, Any]:
    return {"steps": [_serialize_step(step) for step in workout.steps]}


def validate_generated_plan(
    plan: GeneratedNonUltraTrailPlan,
    generation_input: NonUltraTrailGenerationInput,
) -> tuple[PlanInvariantViolation, ...]:
    """Return every candidate invariant breach in deterministic rule order."""
    violations: list[PlanInvariantViolation] = []
    if _generation_input_primitive_issue(generation_input) is not None:
        return (PlanInvariantViolation("generation_input_primitives"),)
    if _collect_reasons(
        generation_input,
        statistics=generation_input.history_statistics,
        include_materialized_inactive=False,
        evaluate_schedule=False,
    ):
        violations.append(PlanInvariantViolation("eligibility"))
    expected_metadata = {
        "policy_version": NON_ULTRA_TRAIL_POLICY_VERSION,
        "generator_version": NON_ULTRA_TRAIL_GENERATOR_VERSION,
        "science_decision_id": NON_ULTRA_TRAIL_SCIENCE_DECISION_ID,
        "contract_digest": NON_ULTRA_TRAIL_CONTRACT_DIGEST,
        "source_decision_digest": NON_ULTRA_TRAIL_SOURCE_DECISION_DIGEST,
        "ontology_version": NON_ULTRA_TRAIL_ONTOLOGY_VERSION,
        "ontology_decision_id": NON_ULTRA_TRAIL_ONTOLOGY_DECISION_ID,
        "ontology_contract_digest": NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT_DIGEST,
        "ontology_source_decision_digest": (
            NON_ULTRA_TRAIL_ONTOLOGY_SOURCE_DECISION_DIGEST
        ),
        "course_schema_id": NON_ULTRA_TRAIL_COURSE_SCHEMA_ID,
        "constraint_schema_id": NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID,
        "contract_runtime_state": "inactive",
        "synthetic_verification_only": True,
    }
    for name, expected in expected_metadata.items():
        if getattr(plan, name) != expected:
            violations.append(PlanInvariantViolation(name))
    input_hash = deterministic_input_hash(generation_input)
    if plan.deterministic_input_hash != input_hash:
        violations.append(PlanInvariantViolation("deterministic_input_hash"))
    if plan.revision_bindings != generation_input.revision_bindings:
        violations.append(PlanInvariantViolation("revision_bindings"))
    if plan.course_demand_fingerprint != _canonical_fingerprint(
        _serialize_course_demand(generation_input.course_demand)
    ):
        violations.append(PlanInvariantViolation("course_fingerprint"))
    if plan.history_statistics != generation_input.history_statistics:
        violations.append(PlanInvariantViolation("history_statistics"))
    expected_modules = _module_availability(
        status="eligible_proposal",
        detail_reason=None,
        course=generation_input.course_demand,
    )
    if plan.module_availability != expected_modules:
        violations.append(PlanInvariantViolation("module_availability"))
    expected_limited = _limited_projection(expected_modules)
    if plan.limited_modules != expected_limited:
        violations.append(PlanInvariantViolation("limited_modules"))
    expected_receipt = _readiness_receipt_digest(
        input_hash=input_hash,
        status="eligible_proposal",
        detail_reason=None,
        reasons=(),
        modules=expected_modules,
        limited_modules=expected_limited,
        revisions=generation_input.revision_bindings,
        inactive_dry_run=True,
    )
    if plan.readiness_receipt_digest != expected_receipt:
        violations.append(PlanInvariantViolation("readiness_receipt_digest"))
    statistics = generation_input.history_statistics
    constraints = generation_input.constraints
    available_weekdays = _known_tuple_int(constraints.available_weekdays)
    unavailable_dates = _known_tuple_date(constraints.unavailable_dates)
    event_date = _known_date(generation_input.course_demand.event_date)
    targets = _effective_targets(generation_input, statistics)
    if (
        available_weekdays is None
        or unavailable_dates is None
        or event_date is None
        or targets is None
    ):
        return tuple((*violations, PlanInvariantViolation("known_inputs")))
    weekly_target, session_cap, ascent_target, descent_target = targets
    frequency_cap = min(
        len(available_weekdays), statistics.recent_modal_running_frequency, _MAX_RUN_DAYS
    )
    blocked_dates = set(unavailable_dates)
    seen_dates: set[date] = set()
    quality_dates: list[date] = []
    expected_end = generation_input.block_start + timedelta(
        days=NON_ULTRA_TRAIL_PROPOSAL_DAYS - 1
    )
    if (
        plan.horizon_start != generation_input.block_start
        or plan.horizon_end != expected_end
        or len(plan.weeks) != NON_ULTRA_TRAIL_PROPOSAL_DAYS // 7
    ):
        violations.append(PlanInvariantViolation("proposal_horizon"))
    if plan.reassessment_dates != (
        generation_input.block_start
        + timedelta(days=NON_ULTRA_TRAIL_REASSESSMENT_DAYS),
    ):
        violations.append(PlanInvariantViolation("reassessment_date"))
    for week_index, week in enumerate(plan.weeks):
        expected_start = generation_input.block_start + timedelta(
            days=week_index * _SCHEDULE_UNIT_DAYS
        )
        if (
            week.week_number != week_index + 1
            or week.start_date != expected_start
            or week.end_date != expected_start + timedelta(days=6)
        ):
            violations.append(PlanInvariantViolation("week_boundary"))
        if not (_MIN_RUN_DAYS <= len(week.workouts) <= frequency_cap):
            violations.append(PlanInvariantViolation("running_day_count"))
        total_minutes = sum(item.planned_duration_min for item in week.workouts)
        low_minutes = sum(_workout_low_minutes(item) for item in week.workouts)
        quality = tuple(
            item for item in week.workouts if item.intensity_bucket == "quality"
        )
        low_workouts = tuple(
            item for item in week.workouts if item.intensity_bucket == "low"
        )
        if len(quality) != _MAX_QUALITY_PER_UNIT:
            violations.append(PlanInvariantViolation("quality_exposure_count"))
        quality_dates.extend(item.scheduled_date for item in quality)
        longest = tuple(
            item for item in week.workouts if item.workout_type == "longest_easy"
        )
        expected_longest = _longest_easy_date(
            tuple(item.scheduled_date for item in low_workouts),
            preferred_longest_weekday=constraints.preferred_longest_weekday,
        )
        if len(longest) != 1 or longest[0].scheduled_date != expected_longest:
            violations.append(PlanInvariantViolation("longest_easy_date"))
        expected_easy = _allocate_easy_minutes(
            tuple(item.scheduled_date for item in low_workouts),
            total_minutes=weekly_target - CONTROLLED_UPHILL_TEMPLATE.total_minutes,
            preferred_longest_weekday=constraints.preferred_longest_weekday,
        )
        if any(
            item.planned_duration_min != expected_easy.get(item.scheduled_date)
            for item in low_workouts
        ):
            violations.append(PlanInvariantViolation("easy_duration"))
        if total_minutes != weekly_target:
            violations.append(PlanInvariantViolation("weekly_minutes_target"))
        if total_minutes <= 0 or low_minutes / total_minutes < _LOW_INTENSITY_FLOOR:
            violations.append(PlanInvariantViolation("low_intensity_floor"))
        ascent_sum = sum(item.ascent_ceiling_meters for item in week.workouts)
        descent_sum = sum(item.descent_ceiling_meters for item in week.workouts)
        if ascent_sum != week.weekly_ascent_ceiling_meters or ascent_sum > ascent_target:
            violations.append(PlanInvariantViolation("weekly_ascent_cap"))
        if descent_sum != week.weekly_descent_ceiling_meters or descent_sum > descent_target:
            violations.append(PlanInvariantViolation("weekly_descent_cap"))
        for workout in week.workouts:
            if workout.scheduled_date in seen_dates:
                violations.append(PlanInvariantViolation("duplicate_date"))
            seen_dates.add(workout.scheduled_date)
            if (
                workout.scheduled_date in blocked_dates
                or workout.scheduled_date.isoweekday() not in available_weekdays
                or workout.scheduled_date >= event_date
            ):
                violations.append(PlanInvariantViolation("calendar_constraint"))
            if workout.activity_type != "trail_running":
                violations.append(PlanInvariantViolation("activity_type"))
            if not (0 < workout.planned_duration_min <= session_cap):
                violations.append(PlanInvariantViolation("session_duration_cap"))
            if not (
                0 <= workout.ascent_ceiling_meters
                <= statistics.recent_maximum_session_ascent_meters
            ):
                violations.append(PlanInvariantViolation("session_ascent_cap"))
            if not (
                0 <= workout.descent_ceiling_meters
                <= statistics.recent_maximum_session_descent_meters
            ):
                violations.append(PlanInvariantViolation("session_descent_cap"))
            if workout.terrain_footing != _proposal_footing(
                generation_input.course_demand
            ):
                violations.append(PlanInvariantViolation("terrain_footing"))
            if workout.intensity_bucket == "quality":
                if (
                    workout.workout_type != "controlled_quality"
                    or workout.template_id != CONTROLLED_UPHILL_TEMPLATE.template_id
                    or workout.steps != CONTROLLED_UPHILL_TEMPLATE.steps
                    or workout.planned_duration_min != 38
                ):
                    violations.append(PlanInvariantViolation("quality_template"))
            elif (
                workout.workout_type not in {"easy", "longest_easy"}
                or workout.template_id is not None
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
                violations.append(PlanInvariantViolation("easy_template"))
    for previous, current in zip(sorted(quality_dates), sorted(quality_dates)[1:]):
        if (current - previous).days <= 1:
            violations.append(PlanInvariantViolation("quality_spacing"))
    ordered_dates = tuple(sorted(seen_dates))
    for previous, current in zip(ordered_dates, ordered_dates[1:]):
        if (current - previous).days <= 1:
            violations.append(PlanInvariantViolation("adjacent_running_days"))
    return tuple(violations)


def _collect_reasons(
    generation_input: NonUltraTrailGenerationInput,
    *,
    statistics: RecentTrailHistoryStatistics,
    include_materialized_inactive: bool,
    evaluate_schedule: bool = True,
    evaluate_revisions: bool = True,
) -> set[tuple[str, str]]:
    reasons = _safely_evaluable_contract_reasons(generation_input)
    if include_materialized_inactive:
        reasons.add(("policy_unavailable", "policy_inactive"))
    course = generation_input.course_demand
    constraints = generation_input.constraints
    if (
        course.schema_id != NON_ULTRA_TRAIL_COURSE_SCHEMA_ID
        or constraints.schema_id != NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID
    ):
        reasons.add(("validation_failed", "schema_version_mismatch"))
    course_invalid = _course_domain_invalid(course)
    constraints_invalid = _constraints_domain_invalid(
        constraints,
        block_start=generation_input.block_start,
    )
    history_invalid = _history_statistics_invalid(statistics)
    workload_invalid = _workload_request_invalid(
        generation_input.workload_request
    )
    if course_invalid or constraints_invalid or history_invalid or workload_invalid:
        reasons.add(("validation_failed", "invalid_field_value"))
    if not course.event_id.strip() or any(
        value.is_unknown
        for value in (
            course.event_date,
            course.distance_meters,
            course.total_ascent_m,
            course.total_descent_m,
            course.planning_duration_range,
            course.hands_assist,
            course.fixed_rope,
        )
    ):
        reasons.add(("clarification_required", "material_course_demand_unknown"))
    if any(
        value.provenance == "explicit_assumption"
        and value.assumption_confirmed_revision != value.source_revision
        for _, value in _all_provenanced_values(course, constraints)
    ):
        reasons.add(
            ("clarification_required", "assumption_confirmation_required")
        )
    if any(
        value.is_unknown
        for value in (
            course.event_format,
            course.distance_family,
            course.planning_intent,
            constraints.adult_nonclinical_scope_confirmed,
            constraints.performance_intent_confirmed,
        )
    ):
        reasons.add(
            (
                "clarification_required",
                "adult_scope_or_constraints_unconfirmed",
            )
        )
    if (
        _known_str(course.event_format) == "multi_day"
        or _known_str(course.distance_family) == "ultra"
    ):
        reasons.add(("policy_unavailable", "unsupported_ultra_or_multiday"))
    if (
        _known_str(course.planning_intent)
        in {"first_completion", "return_to_consistency"}
        or _known_bool(constraints.adult_nonclinical_scope_confirmed) is False
        or _known_bool(constraints.performance_intent_confirmed) is False
    ):
        reasons.add(("policy_unavailable", "unsupported_population_or_intent"))
    if (
        _known_bool(course.hands_assist) is True
        or _known_bool(course.fixed_rope) is True
    ):
        reasons.add(("policy_unavailable", "technical_features_outside_v2"))
    required_constraints = (
        constraints.available_weekdays,
        constraints.weekly_time_limit_min,
        constraints.maximum_session_duration_min,
        constraints.unavailable_dates,
        constraints.nontechnical_three_minute_uphill_access,
        constraints.controlled_downhill_access,
        constraints.current_symptom_stop,
    )
    if any(value.is_unknown for value in required_constraints) or (
        course.course_footing.is_known and constraints.accessible_footing.is_unknown
    ):
        reasons.add(("clarification_required", "training_constraints_missing"))
    weekdays = _known_tuple_int(constraints.available_weekdays)
    if (
        weekdays is not None
        and constraints.preferred_longest_weekday is not None
        and constraints.preferred_longest_weekday not in weekdays
    ) or generation_input.block_start < generation_input.athlete_today:
        reasons.add(("clarification_required", "contradictory_input"))
    if (
        evaluate_revisions
        and not (course_invalid or constraints_invalid or history_invalid)
        and not _revisions_are_current(generation_input)
    ):
        reasons.add(
            (
                "clarification_required",
                "stale_confirmation_or_source_revision",
            )
        )
    if not (workload_invalid or history_invalid) and _workload_above_history(
        generation_input.workload_request,
        statistics,
    ):
        reasons.add(
            (
                "clarification_required",
                "training_constraints_outside_history_envelope",
            )
        )
    if not history_invalid and (
        statistics.usable_completed_weeks < _MINIMUM_USABLE_WEEKS
        or (
        statistics.latest_run_date is None
        or (generation_input.athlete_today - statistics.latest_run_date).days
        > _LATEST_RUN_DAYS
        )
    ):
        reasons.add(
            ("readiness_blocked", "insufficient_recent_running_history")
        )
    if not history_invalid and (
        statistics.comparable_ascent_sessions_within_window < _COMPARABLE_COUNT
        or statistics.latest_comparable_ascent_session_date is None
        or (
            generation_input.athlete_today
            - statistics.latest_comparable_ascent_session_date
        ).days
        > _LATEST_COMPARABLE_DAYS
    ):
        reasons.add(
            ("readiness_blocked", "insufficient_comparable_trail_history")
        )
    if not history_invalid and (
        statistics.comparable_descent_sessions_within_window < _COMPARABLE_COUNT
        or statistics.latest_comparable_descent_session_date is None
        or (
            generation_input.athlete_today
            - statistics.latest_comparable_descent_session_date
        ).days
        > _LATEST_COMPARABLE_DAYS
    ):
        reasons.add(("readiness_blocked", "insufficient_descent_history"))
    course_footing = _known_footing(course.course_footing)
    accessible = _known_footing(constraints.accessible_footing)
    if course_footing is not None and accessible is not None and not set(
        course_footing
    ).issubset(accessible):
        reasons.add(("readiness_blocked", "insufficient_terrain_access"))
    if not history_invalid and course_footing is not None and not set(
        course_footing
    ).issubset(
        statistics.recently_observed_footing
    ):
        reasons.add(
            ("readiness_blocked", "insufficient_comparable_trail_history")
        )
    if (
        _known_bool(constraints.nontechnical_three_minute_uphill_access) is False
        or _known_bool(constraints.controlled_downhill_access) is False
    ):
        reasons.add(("readiness_blocked", "insufficient_terrain_access"))
    if _known_bool(constraints.current_symptom_stop) is True:
        reasons.add(("readiness_blocked", "current_symptom_stop"))
    event_date = _known_date(course.event_date)
    if event_date is not None and (
        event_date - generation_input.block_start
    ).days <= NON_ULTRA_TRAIL_PROPOSAL_DAYS:
        reasons.add(
            ("policy_unavailable", "event_inside_unapproved_taper_window")
        )
    if (
        evaluate_schedule
        and not (
            course_invalid
            or constraints_invalid
            or history_invalid
            or workload_invalid
        )
        and _schedule_inputs_complete(generation_input)
    ):
        if _build_schedule(
            generation_input=generation_input, statistics=statistics
        ) is None:
            reasons.add(("readiness_blocked", "no_schedule_within_envelope"))
    return reasons


def _safely_evaluable_contract_reasons(
    generation_input: Any,
) -> set[tuple[str, str]]:
    if not isinstance(generation_input, NonUltraTrailGenerationInput):
        return set()
    expected = (
        (generation_input.policy_version, NON_ULTRA_TRAIL_POLICY_VERSION),
        (generation_input.generator_version, NON_ULTRA_TRAIL_GENERATOR_VERSION),
        (generation_input.science_decision_id, NON_ULTRA_TRAIL_SCIENCE_DECISION_ID),
        (generation_input.contract_digest, NON_ULTRA_TRAIL_CONTRACT_DIGEST),
        (
            generation_input.source_decision_digest,
            NON_ULTRA_TRAIL_SOURCE_DECISION_DIGEST,
        ),
        (generation_input.ontology_version, NON_ULTRA_TRAIL_ONTOLOGY_VERSION),
        (generation_input.ontology_decision_id, NON_ULTRA_TRAIL_ONTOLOGY_DECISION_ID),
        (
            generation_input.ontology_contract_digest,
            NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT_DIGEST,
        ),
        (
            generation_input.ontology_source_decision_digest,
            NON_ULTRA_TRAIL_ONTOLOGY_SOURCE_DECISION_DIGEST,
        ),
    )
    if any(type(actual) is str and actual != wanted for actual, wanted in expected):
        return {("policy_unavailable", "policy_inactive")}
    return set()


def _safely_evaluable_semantic_reasons(
    generation_input: Any,
) -> set[tuple[str, str]]:
    """Keep independent reasons when unrelated primitive metadata is malformed."""
    if not isinstance(generation_input, NonUltraTrailGenerationInput):
        return set()
    course = generation_input.course_demand
    constraints = generation_input.constraints
    statistics = generation_input.history_statistics
    if (
        not isinstance(course, TrailCourseDemand)
        or not isinstance(constraints, TrailPlanGenerationConstraints)
        or not isinstance(statistics, RecentTrailHistoryStatistics)
        or type(generation_input.athlete_today) is not date
        or type(generation_input.block_start) is not date
        or type(course.event_id) is not str
        or type(course.schema_id) is not str
        or type(constraints.schema_id) is not str
        or (
            generation_input.workload_request is not None
            and not isinstance(
                generation_input.workload_request,
                TrailWorkloadRequest,
            )
        )
    ):
        return set()
    try:
        values = _all_provenanced_values(course, constraints)
    except (AttributeError, TypeError):
        return set()
    if any(not isinstance(value, ProvenancedValue) for _, value in values):
        return set()
    return _collect_reasons(
        generation_input,
        statistics=statistics,
        include_materialized_inactive=False,
        evaluate_revisions=False,
    )


def _ordered_reasons(
    reasons: set[tuple[str, str]],
) -> tuple[MatchingReason, ...]:
    if not reasons.issubset(NON_ULTRA_TRAIL_REASON_PAIRS):
        raise ValueError("Trail result contains a non-contract reason")
    status_order = {
        status: index for index, status in enumerate(NON_ULTRA_TRAIL_STATUS_PRECEDENCE)
    }
    detail_order = {
        status: {reason: index for index, reason in enumerate(values)}
        for status, values in NON_ULTRA_TRAIL_DETAIL_REASON_CATALOG.items()
    }
    return tuple(
        MatchingReason(status, detail)
        for status, detail in sorted(
            reasons,
            key=lambda value: (
                status_order[value[0]], detail_order[value[0]][value[1]]
            ),
        )
    )


def _primary_result(
    reasons: tuple[MatchingReason, ...],
) -> tuple[str, str | None]:
    return (
        ("eligible_proposal", None)
        if not reasons
        else (reasons[0].status, reasons[0].detail_reason)
    )


def _module_availability(
    *,
    status: str,
    detail_reason: str | None,
    course: TrailCourseDemand | None,
) -> tuple[ModuleAvailability, ...]:
    if status != "eligible_proposal" or course is None:
        target = f"{status}.{detail_reason}" if detail_reason is not None else status
        return tuple(
            ModuleAvailability(module, "not_evaluated", target)
            for module in NON_ULTRA_TRAIL_MODULE_KEYS
        )
    limited: dict[str, str] = {}
    if course.grade_distribution.is_unknown:
        limited["grade_specificity"] = _MODULE_LIMIT_TARGETS["grade_specificity"]
    if course.course_footing.is_unknown:
        limited["technical_terrain"] = _MODULE_LIMIT_TARGETS["technical_terrain"]
    if any(value.is_unknown for value in _environment_values(course.optional_context)):
        limited["environment_altitude"] = _MODULE_LIMIT_TARGETS[
            "environment_altitude"
        ]
    support_unknown = any(
        value.is_unknown for value in _support_values(course.optional_context)
    )
    fueling_unknown = any(
        value.is_unknown for value in _fueling_values(course.optional_context)
    )
    if support_unknown or fueling_unknown:
        limited["fueling"] = (
            _MODULE_LIMIT_TARGETS["fueling"]
            if support_unknown
            else "course.optional_context.fueling"
        )
    result = tuple(
        ModuleAvailability(
            module,
            "limited" if module in limited else "available",
            limited.get(module),
        )
        for module in NON_ULTRA_TRAIL_MODULE_KEYS
    )
    if any(value.state not in NON_ULTRA_TRAIL_MODULE_STATES for value in result):
        raise ValueError("Trail module state escaped the accepted contract")
    return result


def _limited_projection(
    modules: tuple[ModuleAvailability, ...],
) -> tuple[str, ...]:
    return tuple(
        module
        for module in NON_ULTRA_TRAIL_LIMITED_MODULE_ORDER
        if next(value for value in modules if value.module == module).state
        == "limited"
    )


def _build_schedule(
    *,
    generation_input: NonUltraTrailGenerationInput,
    statistics: RecentTrailHistoryStatistics,
) -> tuple[GeneratedTrailWeek, ...] | None:
    constraints = generation_input.constraints
    available_weekdays = _known_tuple_int(constraints.available_weekdays)
    unavailable_dates = _known_tuple_date(constraints.unavailable_dates)
    event_date = _known_date(generation_input.course_demand.event_date)
    if available_weekdays is None or unavailable_dates is None or event_date is None:
        return None
    targets = _effective_targets(generation_input, statistics)
    if targets is None:
        return None
    weekly_target, session_cap, ascent_target, descent_target = targets
    frequency = min(
        len(available_weekdays), statistics.recent_modal_running_frequency, _MAX_RUN_DAYS
    )
    if (
        frequency < _MIN_RUN_DAYS
        or session_cap < CONTROLLED_UPHILL_TEMPLATE.total_minutes
        or weekly_target <= 0
        or ascent_target <= 0
        or descent_target <= 0
    ):
        return None
    blocked = set(unavailable_dates)
    weeks: list[GeneratedTrailWeek] = []
    previous_quality_date: date | None = None
    previous_workout_date: date | None = None
    for week_index in range(NON_ULTRA_TRAIL_PROPOSAL_DAYS // 7):
        week_start = generation_input.block_start + timedelta(
            days=week_index * _SCHEDULE_UNIT_DAYS
        )
        available = tuple(
            value
            for value in (
                week_start + timedelta(days=offset)
                for offset in range(_SCHEDULE_UNIT_DAYS)
            )
            if value.isoweekday() in available_weekdays
            and value not in blocked
            and value < event_date
        )
        unit_frequency = min(frequency, len(available))
        if unit_frequency < _MIN_RUN_DAYS:
            return None
        selected = _select_schedule_dates(
            available,
            frequency=unit_frequency,
            preferred_longest_weekday=constraints.preferred_longest_weekday,
            previous_workout_date=previous_workout_date,
        )
        if selected is None:
            return None
        quality_date = _select_quality_date(
            selected,
            preferred_longest_weekday=constraints.preferred_longest_weekday,
            previous_quality_date=previous_quality_date,
        )
        if quality_date is None:
            return None
        workouts = _build_week_workouts(
            dates=selected,
            quality_date=quality_date,
            total_minutes=weekly_target,
            session_cap=session_cap,
            ascent_target=ascent_target,
            ascent_session_cap=statistics.recent_maximum_session_ascent_meters,
            descent_target=descent_target,
            descent_session_cap=statistics.recent_maximum_session_descent_meters,
            preferred_longest_weekday=constraints.preferred_longest_weekday,
            terrain_footing=_proposal_footing(generation_input.course_demand),
        )
        if workouts is None:
            return None
        weeks.append(
            GeneratedTrailWeek(
                week_number=week_index + 1,
                start_date=week_start,
                end_date=week_start + timedelta(days=6),
                weekly_ascent_ceiling_meters=sum(
                    value.ascent_ceiling_meters for value in workouts
                ),
                weekly_descent_ceiling_meters=sum(
                    value.descent_ceiling_meters for value in workouts
                ),
                workouts=workouts,
            )
        )
        previous_quality_date = quality_date
        previous_workout_date = max(selected)
    return tuple(weeks)


def _effective_targets(
    generation_input: NonUltraTrailGenerationInput,
    statistics: RecentTrailHistoryStatistics,
) -> tuple[int, int, int, int] | None:
    weekly_limit = _known_int(generation_input.constraints.weekly_time_limit_min)
    session_limit = _known_int(
        generation_input.constraints.maximum_session_duration_min
    )
    if weekly_limit is None or session_limit is None:
        return None
    request = generation_input.workload_request
    weekly = min(statistics.recent_median_usable_weekly_minutes, weekly_limit)
    session = min(statistics.recent_maximum_session_minutes, session_limit)
    ascent = statistics.recent_median_usable_weekly_ascent_meters
    descent = statistics.recent_median_usable_weekly_descent_meters
    if request is not None:
        if request.weekly_running_minutes is not None:
            weekly = min(weekly, request.weekly_running_minutes)
        if request.maximum_session_minutes is not None:
            session = min(session, request.maximum_session_minutes)
        if request.weekly_ascent_meters is not None:
            ascent = min(ascent, request.weekly_ascent_meters)
        if request.weekly_descent_meters is not None:
            descent = min(descent, request.weekly_descent_meters)
    return weekly, session, ascent, descent


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
    preferred_longest_weekday: int | None,
    terrain_footing: tuple[str, ...],
) -> tuple[GeneratedTrailWorkout, ...] | None:
    easy_dates = tuple(value for value in sorted(dates) if value != quality_date)
    remaining = total_minutes - CONTROLLED_UPHILL_TEMPLATE.total_minutes
    if remaining < len(easy_dates):
        return None
    easy_allocations = _allocate_easy_minutes(
        easy_dates,
        total_minutes=remaining,
        preferred_longest_weekday=preferred_longest_weekday,
    )
    if any(value > session_cap for value in easy_allocations.values()):
        return None
    low_minutes = CONTROLLED_UPHILL_TEMPLATE.low_intensity_minutes + sum(
        easy_allocations.values()
    )
    if total_minutes <= 0 or low_minutes / total_minutes < _LOW_INTENSITY_FLOOR:
        return None
    longest = _longest_easy_date(
        easy_dates, preferred_longest_weekday=preferred_longest_weekday
    )
    ascent = _allocate_integer_ceiling(
        dates,
        total_ceiling=ascent_target,
        per_session_ceiling=ascent_session_cap,
        priority=(quality_date, *tuple(value for value in dates if value != quality_date)),
    )
    descent = _allocate_integer_ceiling(
        dates,
        total_ceiling=descent_target,
        per_session_ceiling=descent_session_cap,
        priority=((longest,) if longest is not None else ())
        + tuple(value for value in dates if value != longest),
    )
    if ascent is None or descent is None:
        return None
    workouts: list[GeneratedTrailWorkout] = []
    for scheduled_date in sorted(dates):
        if scheduled_date == quality_date:
            workouts.append(
                GeneratedTrailWorkout(
                    scheduled_date=scheduled_date,
                    workout_type="controlled_quality",
                    intensity_bucket="quality",
                    planned_duration_min=CONTROLLED_UPHILL_TEMPLATE.total_minutes,
                    ascent_ceiling_meters=ascent[scheduled_date],
                    descent_ceiling_meters=descent[scheduled_date],
                    terrain_footing=terrain_footing,
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
                workout_type="longest_easy" if scheduled_date == longest else "easy",
                intensity_bucket="low",
                planned_duration_min=duration,
                ascent_ceiling_meters=ascent[scheduled_date],
                descent_ceiling_meters=descent[scheduled_date],
                terrain_footing=terrain_footing,
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
    preferred_longest_weekday: int | None,
) -> dict[date, int]:
    if not dates:
        return {}
    base, remainder = divmod(total_minutes, len(dates))
    result = {value: base for value in dates}
    priority = _easy_allocation_priority(
        dates, preferred_longest_weekday=preferred_longest_weekday
    )
    for value in priority[:remainder]:
        result[value] += 1
    return result


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
    result = {value: quotient for value in ordered}
    for value in ordered[:remainder]:
        result[value] += 1
    return (
        result
        if all(value <= per_session_ceiling for value in result.values())
        else None
    )


def _select_schedule_dates(
    dates: Sequence[date],
    *,
    frequency: int,
    preferred_longest_weekday: int | None,
    previous_workout_date: date | None,
) -> tuple[date, ...] | None:
    ordered = tuple(sorted(set(dates)))
    candidates = tuple(
        candidate
        for candidate in combinations(ordered, frequency)
        if all(
            (current - previous).days > 1
            for previous, current in zip(candidate, candidate[1:])
        )
        and (
            previous_workout_date is None
            or (candidate[0] - previous_workout_date).days > 1
        )
    )
    preferred = tuple(
        candidate
        for candidate in candidates
        if preferred_longest_weekday is not None
        and any(value.isoweekday() == preferred_longest_weekday for value in candidate)
    )
    return min(preferred or candidates, default=None)


def _select_quality_date(
    dates: Sequence[date],
    *,
    preferred_longest_weekday: int | None,
    previous_quality_date: date | None,
) -> date | None:
    longest = _longest_easy_date(
        dates, preferred_longest_weekday=preferred_longest_weekday
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
    preferred_longest_weekday: int | None,
) -> date | None:
    if preferred_longest_weekday is not None:
        selected = next(
            (
                value
                for value in sorted(dates)
                if value.isoweekday() == preferred_longest_weekday
            ),
            None,
        )
        if selected is not None:
            return selected
    return max(dates, default=None)


def _easy_allocation_priority(
    dates: Sequence[date],
    *,
    preferred_longest_weekday: int | None,
) -> tuple[date, ...]:
    longest = _longest_easy_date(
        dates, preferred_longest_weekday=preferred_longest_weekday
    )
    return (
        ()
        if longest is None
        else (longest,) + tuple(value for value in sorted(dates) if value != longest)
    )


def _generation_input_primitive_issue(generation_input: Any) -> str | None:
    if not isinstance(generation_input, NonUltraTrailGenerationInput):
        return "generation_input"
    for name in (
        "policy_version",
        "generator_version",
        "science_decision_id",
        "contract_digest",
        "source_decision_digest",
        "ontology_version",
        "ontology_decision_id",
        "ontology_contract_digest",
        "ontology_source_decision_digest",
    ):
        if type(getattr(generation_input, name)) is not str:
            return name
    if type(generation_input.athlete_today) is not date:
        return "athlete_today"
    if type(generation_input.block_start) is not date:
        return "block_start"
    if not isinstance(generation_input.course_demand, TrailCourseDemand):
        return "course_demand"
    if not isinstance(generation_input.constraints, TrailPlanGenerationConstraints):
        return "constraints"
    if not isinstance(generation_input.history_statistics, RecentTrailHistoryStatistics):
        return "history_statistics"
    if not isinstance(generation_input.revision_bindings, TrailRevisionBindings):
        return "revision_bindings"
    if generation_input.workload_request is not None and not isinstance(
        generation_input.workload_request, TrailWorkloadRequest
    ):
        return "workload_request"
    if type(generation_input.synthetic_verification_only) is not bool:
        return "synthetic_verification_only"
    for name, value in _all_provenanced_values(
        generation_input.course_demand, generation_input.constraints
    ):
        if not isinstance(value, ProvenancedValue):
            return name
        if value.state not in {"known", "unknown"}:
            return f"{name}.state"
        if value.provenance not in NON_ULTRA_TRAIL_ALLOWED_PROVENANCE:
            return f"{name}.provenance"
        if not _is_digest(value.source_revision):
            return f"{name}.source_revision"
        if value.source_timestamp is not None and type(value.source_timestamp) is not datetime:
            return f"{name}.source_timestamp"
        if value.model_version is not None and (
            type(value.model_version) is not str or not value.model_version
        ):
            return f"{name}.model_version"
        if value.assumption_confirmed_revision is not None and not _is_digest(
            value.assumption_confirmed_revision
        ):
            return f"{name}.assumption_confirmed_revision"
        if value.is_unknown and (
            value.value is not None or value.provenance != "unknown"
        ):
            return f"{name}.unknown"
        if value.is_known and (
            value.value is None and name != "support.max_aid_station_gap_m"
        ):
            return f"{name}.known"
        if value.is_known and value.provenance == "unknown":
            return f"{name}.provenance"
        if value.provenance == "model_inferred" and not value.model_version:
            return f"{name}.model_version"
    bindings = generation_input.revision_bindings
    if not all(
        _is_digest(value)
        for value in (
            bindings.course_revision,
            bindings.planning_context_revision,
            bindings.history_revision,
            bindings.composite_revision,
        )
    ):
        return "revision_bindings"
    if not isinstance(bindings.section_confirmations, tuple) or any(
        not isinstance(value, TrailSectionConfirmation)
        or type(value.section_key) is not str
        or not _is_digest(value.current_revision)
        or (
            value.confirmed_revision is not None
            and not _is_digest(value.confirmed_revision)
        )
        for value in bindings.section_confirmations
    ):
        return "section_confirmations"
    return None


def _course_domain_invalid(course: TrailCourseDemand) -> bool:
    if (
        type(course.event_id) is not str
        or not (1 <= len(course.event_id) <= 128)
        or type(course.schema_id) is not str
    ):
        return True
    checks = (
        (course.event_date, lambda value: type(value) is date),
        (course.distance_meters, lambda value: _integer_in_range(value, 1, 49999)),
        (course.total_ascent_m, lambda value: _integer_in_range(value, 0, 20000)),
        (course.total_descent_m, lambda value: _integer_in_range(value, 0, 20000)),
        (
            course.planning_duration_range,
            lambda value: isinstance(value, TrailPlanningDurationRange)
            and _integer_in_range(value.minimum_min, 1, 1440)
            and _integer_in_range(value.maximum_min, 1, 1440)
            and value.minimum_min < value.maximum_min,
        ),
        (course.event_format, lambda value: value in {"single_day", "multi_day"}),
        (course.distance_family, lambda value: value in {"non_ultra", "ultra"}),
        (
            course.planning_intent,
            lambda value: value
            in {"performance", "first_completion", "return_to_consistency"},
        ),
        (course.grade_distribution, _valid_grade_distribution),
        (course.course_footing, lambda value: _valid_footing(value, allow_empty=False)),
        (course.hands_assist, lambda value: type(value) is bool),
        (course.fixed_rope, lambda value: type(value) is bool),
    )
    if any(field.is_known and not validator(field.value) for field, validator in checks):
        return True
    if course.grade_distribution.is_known and course.grade_distribution.provenance not in {
        "athlete_stated",
        "course_verified",
    }:
        return True
    return _optional_context_invalid(course.optional_context)


def _constraints_domain_invalid(
    constraints: TrailPlanGenerationConstraints,
    *,
    block_start: date,
) -> bool:
    checks = (
        (
            constraints.available_weekdays,
            lambda value: isinstance(value, tuple)
            and len(value) > 0
            and len(value) == len(set(value))
            and all(type(item) is int and 1 <= item <= 7 for item in value),
        ),
        (
            constraints.weekly_time_limit_min,
            lambda value: _integer_in_range(value, 1, 10080),
        ),
        (
            constraints.maximum_session_duration_min,
            lambda value: _integer_in_range(value, 1, 1440),
        ),
        (
            constraints.unavailable_dates,
            lambda value: isinstance(value, tuple)
            and len(value) <= 14
            and len(value) == len(set(value))
            and tuple(sorted(value)) == value
            and all(
                type(item) is date
                and block_start
                <= item
                < block_start + timedelta(days=NON_ULTRA_TRAIL_PROPOSAL_DAYS)
                for item in value
            ),
        ),
        (
            constraints.nontechnical_three_minute_uphill_access,
            lambda value: type(value) is bool,
        ),
        (constraints.controlled_downhill_access, lambda value: type(value) is bool),
        (
            constraints.accessible_footing,
            lambda value: _valid_footing(value, allow_empty=False),
        ),
        (
            constraints.adult_nonclinical_scope_confirmed,
            lambda value: type(value) is bool,
        ),
        (constraints.performance_intent_confirmed, lambda value: type(value) is bool),
        (constraints.current_symptom_stop, lambda value: type(value) is bool),
    )
    if any(field.is_known and not validator(field.value) for field, validator in checks):
        return True
    weekly = _known_int(constraints.weekly_time_limit_min)
    session = _known_int(constraints.maximum_session_duration_min)
    if weekly is not None and session is not None and session > weekly:
        return True
    if constraints.preferred_longest_weekday is not None and not _integer_in_range(
        constraints.preferred_longest_weekday, 1, 7
    ):
        return True
    return type(constraints.schema_id) is not str


def _optional_context_invalid(context: TrailOptionalContext) -> bool:
    if (
        not isinstance(context, TrailOptionalContext)
        or not isinstance(context.environment, TrailEnvironmentContext)
        or not isinstance(context.support, TrailSupportContext)
        or not isinstance(context.fueling, TrailFuelingContext)
    ):
        return True
    environment = context.environment
    support = context.support
    fueling = context.fueling
    checks = (
        (environment.maximum_altitude_m, lambda value: _integer_in_range(value, -500, 9000)),
        (environment.temperature_min_c, lambda value: _decimal_in_range(value, -30, 55)),
        (environment.temperature_max_c, lambda value: _decimal_in_range(value, -30, 55)),
        (environment.humidity_min_pct, lambda value: _decimal_in_range(value, 0, 100)),
        (environment.humidity_max_pct, lambda value: _decimal_in_range(value, 0, 100)),
        (environment.sun_exposure, lambda value: value in {"low", "mixed", "high"}),
        (environment.wind_exposure, lambda value: value in {"sheltered", "mixed", "exposed"}),
        (
            environment.conditions_basis,
            lambda value: value
            in {"organizer_information", "seasonal_expectation", "athlete_assumption"},
        ),
        (support.aid_support_mode, lambda value: value in {"organized_aid", "mixed", "self_supported"}),
        (support.aid_station_count, lambda value: _integer_in_range(value, 0, 50)),
        (
            support.max_aid_station_gap_m,
            lambda value: value is None or _integer_in_range(value, 100, 50000),
        ),
        (support.water_availability, lambda value: value in {"none", "some_stations", "all_stations"}),
        (support.food_availability, lambda value: value in {"none", "some_stations", "all_stations"}),
        (
            support.mandatory_gear,
            lambda value: isinstance(value, tuple)
            and len(value) == len(set(value))
            and set(value).issubset(_MANDATORY_GEAR),
        ),
        (fueling.longest_practiced_duration_min, lambda value: _integer_in_range(value, 0, 1440)),
        (fueling.practice_sessions_last_42_days, lambda value: _integer_in_range(value, 0, 84)),
        (
            fueling.intake_form,
            lambda value: value
            in {"none", "fluids_only", "carbohydrate_drink", "mixed_food_and_drink"},
        ),
        (
            fueling.gastrointestinal_experience,
            lambda value: value
            in {"no_plan_altering_issue", "plan_altering_issue"},
        ),
    )
    if any(field.is_known and not validator(field.value) for field, validator in checks):
        return True
    temp_min = _known_number(environment.temperature_min_c)
    temp_max = _known_number(environment.temperature_max_c)
    humidity_min = _known_number(environment.humidity_min_pct)
    humidity_max = _known_number(environment.humidity_max_pct)
    if temp_min is not None and temp_max is not None and temp_min > temp_max:
        return True
    if humidity_min is not None and humidity_max is not None and humidity_min > humidity_max:
        return True
    return _known_str(environment.conditions_basis) == "athlete_assumption" and (
        environment.conditions_basis.provenance != "explicit_assumption"
    )


def _history_statistics_invalid(statistics: RecentTrailHistoryStatistics) -> bool:
    integer_values = (
        statistics.usable_completed_weeks,
        statistics.recent_modal_running_frequency,
        statistics.recent_median_usable_weekly_minutes,
        statistics.recent_maximum_usable_weekly_minutes,
        statistics.recent_maximum_session_minutes,
        statistics.recent_median_usable_weekly_ascent_meters,
        statistics.recent_maximum_usable_weekly_ascent_meters,
        statistics.recent_median_usable_weekly_descent_meters,
        statistics.recent_maximum_usable_weekly_descent_meters,
        statistics.recent_maximum_session_ascent_meters,
        statistics.recent_maximum_session_descent_meters,
        statistics.comparable_ascent_sessions_within_window,
        statistics.comparable_descent_sessions_within_window,
    )
    return (
        any(type(value) is not int or value < 0 for value in integer_values)
        or any(
            value is not None and type(value) is not date
            for value in (
                statistics.latest_run_date,
                statistics.latest_comparable_ascent_session_date,
                statistics.latest_comparable_descent_session_date,
            )
        )
        or not _valid_footing(
            statistics.recently_observed_footing, allow_empty=True
        )
    )


def _workload_request_invalid(request: TrailWorkloadRequest | None) -> bool:
    return request is not None and any(
        value is not None and (type(value) is not int or value < 0)
        for value in asdict(request).values()
    )


def _workload_above_history(
    request: TrailWorkloadRequest | None,
    statistics: RecentTrailHistoryStatistics,
) -> bool:
    if request is None:
        return False
    comparisons = (
        (request.weekly_running_minutes, statistics.recent_maximum_usable_weekly_minutes),
        (request.maximum_session_minutes, statistics.recent_maximum_session_minutes),
        (request.weekly_ascent_meters, statistics.recent_maximum_usable_weekly_ascent_meters),
        (request.weekly_descent_meters, statistics.recent_maximum_usable_weekly_descent_meters),
    )
    return any(
        value is not None and value > ceiling for value, ceiling in comparisons
    )


def _schedule_inputs_complete(generation_input: NonUltraTrailGenerationInput) -> bool:
    return all(
        value.is_known
        for value in (
            generation_input.course_demand.event_date,
            generation_input.constraints.available_weekdays,
            generation_input.constraints.weekly_time_limit_min,
            generation_input.constraints.maximum_session_duration_min,
            generation_input.constraints.unavailable_dates,
        )
    )


def _revisions_are_current(generation_input: NonUltraTrailGenerationInput) -> bool:
    return generation_input.revision_bindings == derive_revision_bindings(
        course_demand=generation_input.course_demand,
        constraints=generation_input.constraints,
        history_statistics=generation_input.history_statistics,
        confirmed=True,
    )


def _section_payloads(
    course: TrailCourseDemand,
    constraints: TrailPlanGenerationConstraints,
) -> tuple[tuple[str, Any], ...]:
    course_fields = _serialize_course_demand(course)["fields"]
    return (
        (
            "section.event-duration",
            {
                "event_id": course.event_id,
                **{
                    key: course_fields[key]
                    for key in (
                        "event_date",
                        "distance_meters",
                        "total_ascent_m",
                        "total_descent_m",
                        "planning_duration_range",
                        "event_format",
                        "distance_family",
                        "planning_intent",
                    )
                },
            },
        ),
        (
            "section.grade-footing",
            {
                key: course_fields[key]
                for key in (
                    "grade_distribution",
                    "course_footing",
                    "hands_assist",
                    "fixed_rope",
                )
            },
        ),
        ("section.training-access", _serialize_constraints(constraints)),
        (
            "section.optional-context",
            _serialize_optional_context(course.optional_context),
        ),
    )


def _course_revision_payload(course: TrailCourseDemand) -> dict[str, Any]:
    payload = _serialize_course_demand(course)
    return {
        "schema_id": payload["schema_id"],
        "event_id": payload["event_id"],
        "fields": {
            key: value
            for key, value in payload["fields"].items()
            if key != "optional_context"
        },
    }


def _planning_revision_payload(
    course: TrailCourseDemand,
    constraints: TrailPlanGenerationConstraints,
) -> dict[str, Any]:
    return {
        "constraints": _serialize_constraints(constraints),
        "optional_context": _serialize_optional_context(course.optional_context),
    }


def _composite_revision(
    *,
    course_revision: str,
    planning_context_revision: str,
    history_revision: str,
    section_confirmations: tuple[TrailSectionConfirmation, ...],
) -> str:
    return _revision(
        {
            "course_revision": course_revision,
            "planning_context_revision": planning_context_revision,
            "history_revision": history_revision,
            "section_confirmations": {
                value.section_key: value.confirmed_revision
                for value in sorted(
                    section_confirmations, key=lambda item: item.section_key
                )
            },
            "course_schema_id": NON_ULTRA_TRAIL_COURSE_SCHEMA_ID,
            "constraint_schema_id": NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID,
            "ontology_decision_id": NON_ULTRA_TRAIL_ONTOLOGY_DECISION_ID,
            "ontology_contract_digest": NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT_DIGEST,
            "policy_decision_id": NON_ULTRA_TRAIL_SCIENCE_DECISION_ID,
            "policy_contract_digest": NON_ULTRA_TRAIL_CONTRACT_DIGEST,
            "generator_version": NON_ULTRA_TRAIL_GENERATOR_VERSION,
        }
    )


def _serialize_course_demand(course: TrailCourseDemand) -> dict[str, Any]:
    return {
        "schema_id": course.schema_id,
        "event_id": course.event_id,
        "fields": {
            "event_date": course.event_date.public_payload(),
            "distance_meters": course.distance_meters.public_payload(),
            "total_ascent_m": course.total_ascent_m.public_payload(),
            "total_descent_m": course.total_descent_m.public_payload(),
            "planning_duration_range": course.planning_duration_range.public_payload(),
            "event_format": course.event_format.public_payload(),
            "distance_family": course.distance_family.public_payload(),
            "planning_intent": course.planning_intent.public_payload(),
            "grade_distribution": course.grade_distribution.public_payload(),
            "course_footing": _value_payload(
                course.course_footing,
                canonicalizer=lambda value: list(_canonical_footing(value)),
            ),
            "hands_assist": course.hands_assist.public_payload(),
            "fixed_rope": course.fixed_rope.public_payload(),
            "optional_context": _serialize_optional_context(course.optional_context),
        },
    }


def _value_payload(
    value: ProvenancedValue,
    *,
    canonicalizer: Any,
) -> dict[str, Any]:
    payload = value.public_payload()
    if value.is_known:
        payload["value"] = canonicalizer(value.value)
    return payload


def _serialize_optional_context(context: TrailOptionalContext) -> dict[str, Any]:
    result = {
        "environment": {
            field.name: getattr(context.environment, field.name).public_payload()
            for field in fields(context.environment)
        },
        "support": {
            field.name: getattr(context.support, field.name).public_payload()
            for field in fields(context.support)
        },
        "fueling": {
            field.name: getattr(context.fueling, field.name).public_payload()
            for field in fields(context.fueling)
        },
    }
    mandatory_gear = context.support.mandatory_gear
    result["support"]["mandatory_gear"] = _value_payload(
        mandatory_gear,
        canonicalizer=lambda value: list(
            sorted(value, key=_GEAR_ORDER.__getitem__)
        ),
    )
    return result


def _serialize_constraints(
    constraints: TrailPlanGenerationConstraints,
) -> dict[str, Any]:
    return {
        "schema_id": constraints.schema_id,
        "available_weekdays": _value_payload(
            constraints.available_weekdays,
            canonicalizer=lambda value: sorted(value),
        ),
        "weekly_time_limit_min": constraints.weekly_time_limit_min.public_payload(),
        "maximum_session_duration_min": (
            constraints.maximum_session_duration_min.public_payload()
        ),
        "unavailable_dates": _value_payload(
            constraints.unavailable_dates,
            canonicalizer=lambda value: [item.isoformat() for item in sorted(value)],
        ),
        "preferred_longest_weekday": constraints.preferred_longest_weekday,
        "nontechnical_three_minute_uphill_access": (
            constraints.nontechnical_three_minute_uphill_access.public_payload()
        ),
        "controlled_downhill_access": (
            constraints.controlled_downhill_access.public_payload()
        ),
        "accessible_footing": _value_payload(
            constraints.accessible_footing,
            canonicalizer=lambda value: list(_canonical_footing(value)),
        ),
        "adult_nonclinical_scope_confirmed": (
            constraints.adult_nonclinical_scope_confirmed.public_payload()
        ),
        "performance_intent_confirmed": (
            constraints.performance_intent_confirmed.public_payload()
        ),
        "current_symptom_stop": constraints.current_symptom_stop.public_payload(),
    }


def _all_provenanced_values(
    course: TrailCourseDemand,
    constraints: TrailPlanGenerationConstraints,
) -> tuple[tuple[str, ProvenancedValue], ...]:
    course_values = tuple(
        (name, getattr(course, name))
        for name in (
            "event_date",
            "distance_meters",
            "total_ascent_m",
            "total_descent_m",
            "planning_duration_range",
            "event_format",
            "distance_family",
            "planning_intent",
            "grade_distribution",
            "course_footing",
            "hands_assist",
            "fixed_rope",
        )
    )
    optional = tuple(
        (f"environment.{field.name}", getattr(course.optional_context.environment, field.name))
        for field in fields(course.optional_context.environment)
    )
    support = tuple(
        (f"support.{field.name}", getattr(course.optional_context.support, field.name))
        for field in fields(course.optional_context.support)
    )
    fueling = tuple(
        (f"fueling.{field.name}", getattr(course.optional_context.fueling, field.name))
        for field in fields(course.optional_context.fueling)
    )
    constraint_values = tuple(
        (f"constraints.{name}", getattr(constraints, name))
        for name in (
            "available_weekdays",
            "weekly_time_limit_min",
            "maximum_session_duration_min",
            "unavailable_dates",
            "nontechnical_three_minute_uphill_access",
            "controlled_downhill_access",
            "accessible_footing",
            "adult_nonclinical_scope_confirmed",
            "performance_intent_confirmed",
            "current_symptom_stop",
        )
    )
    return (*course_values, *optional, *support, *fueling, *constraint_values)


def _environment_values(context: TrailOptionalContext) -> tuple[ProvenancedValue, ...]:
    return tuple(
        getattr(context.environment, field.name) for field in fields(context.environment)
    )


def _support_values(context: TrailOptionalContext) -> tuple[ProvenancedValue, ...]:
    return tuple(getattr(context.support, field.name) for field in fields(context.support))


def _fueling_values(context: TrailOptionalContext) -> tuple[ProvenancedValue, ...]:
    return tuple(getattr(context.fueling, field.name) for field in fields(context.fueling))


def _readiness_receipt_digest(
    *,
    input_hash: str,
    status: str,
    detail_reason: str | None,
    reasons: tuple[MatchingReason, ...],
    modules: tuple[ModuleAvailability, ...],
    limited_modules: tuple[str, ...],
    revisions: TrailRevisionBindings | None,
    inactive_dry_run: bool,
) -> str:
    return _revision(
        {
            "input_hash": input_hash,
            "status": status,
            "detail_reason": detail_reason,
            "matching_reasons": [asdict(value) for value in reasons],
            "module_availability": [asdict(value) for value in modules],
            "limited_modules": limited_modules,
            "revision_bindings": asdict(revisions) if revisions is not None else None,
            "inactive_dry_run": inactive_dry_run,
            "policy": {
                "model_version": NON_ULTRA_TRAIL_POLICY_VERSION,
                "decision_id": NON_ULTRA_TRAIL_SCIENCE_DECISION_ID,
                "source_decision_digest": NON_ULTRA_TRAIL_SOURCE_DECISION_DIGEST,
                "contract_digest": NON_ULTRA_TRAIL_CONTRACT_DIGEST,
                "runtime_state": str(NON_ULTRA_TRAIL_CONTRACT.runtime_state),
            },
            "ontology": {
                "model_version": NON_ULTRA_TRAIL_ONTOLOGY_VERSION,
                "decision_id": NON_ULTRA_TRAIL_ONTOLOGY_DECISION_ID,
                "source_decision_digest": (
                    NON_ULTRA_TRAIL_ONTOLOGY_SOURCE_DECISION_DIGEST
                ),
                "contract_digest": NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT_DIGEST,
                "runtime_state": str(NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT.runtime_state),
            },
            "generator_version": NON_ULTRA_TRAIL_GENERATOR_VERSION,
            "course_schema_id": NON_ULTRA_TRAIL_COURSE_SCHEMA_ID,
            "constraint_schema_id": NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID,
        }
    )


def _history_observation_issue(
    history: Sequence[TrailRunningHistoryObservation],
    *,
    athlete_today: date,
) -> str | None:
    if type(athlete_today) is not date:
        return "athlete_today"
    if not isinstance(history, Sequence) or len(history) > _MAX_HISTORY_OBSERVATIONS:
        return "history_observation_count"
    ids = [
        value.activity_id
        for value in history
        if isinstance(value, TrailRunningHistoryObservation)
    ]
    if len(ids) != len(history) or len(ids) != len(set(ids)):
        return "history.duplicate_activity_id"
    for item in history:
        if (
            type(item.activity_id) is not str
            or not item.activity_id
            or type(item.observed_date) is not date
            or type(item.activity_type) is not str
            or not _is_finite_number(item.duration_min)
            or (
                item.distance_km is not None
                and not _is_finite_number(item.distance_km)
            )
            or not _is_digest(item.source_revision)
            or type(item.source_timestamp) is not datetime
            or item.source_timestamp.tzinfo is None
            or type(item.outdoor_confirmed) is not bool
            or (
                item.observed_footing is not None
                and not _valid_footing(item.observed_footing, allow_empty=False)
            )
        ):
            return "history_observation"
        for value in (item.elevation_gain_meters, item.elevation_loss_meters):
            if value is not None and (type(value) is not int or value < 0):
                return "history_observation"
    return None


def _is_qualifying_run(item: TrailRunningHistoryObservation) -> bool:
    return (
        item.activity_type in _HISTORY_ACTIVITY_TYPES
        and item.outdoor_confirmed is True
        and item.duration_min > 0
        and item.distance_km is not None
        and item.distance_km > 0
    )


def _has_comparable_ascent(item: TrailRunningHistoryObservation) -> bool:
    return (
        _is_qualifying_run(item)
        and item.activity_type == "trail_running"
        and item.elevation_gain_meters is not None
        and item.elevation_gain_meters > 0
    )


def _has_comparable_descent(item: TrailRunningHistoryObservation) -> bool:
    return (
        _is_qualifying_run(item)
        and item.activity_type == "trail_running"
        and item.elevation_loss_meters is not None
        and item.elevation_loss_meters > 0
    )


def _proposal_footing(course: TrailCourseDemand) -> tuple[str, ...]:
    return _known_footing(course.course_footing) or ()


def _known_int(value: ProvenancedValue) -> int | None:
    return value.value if value.is_known and type(value.value) is int else None


def _known_number(value: ProvenancedValue) -> Decimal | None:
    if not value.is_known or not _is_finite_number(value.value):
        return None
    return Decimal(str(value.value))


def _known_bool(value: ProvenancedValue) -> bool | None:
    return value.value if value.is_known and type(value.value) is bool else None


def _known_str(value: ProvenancedValue) -> str | None:
    return value.value if value.is_known and type(value.value) is str else None


def _known_date(value: ProvenancedValue) -> date | None:
    return value.value if value.is_known and type(value.value) is date else None


def _known_tuple_int(value: ProvenancedValue) -> tuple[int, ...] | None:
    return (
        value.value
        if value.is_known
        and isinstance(value.value, tuple)
        and all(type(item) is int for item in value.value)
        else None
    )


def _known_tuple_date(value: ProvenancedValue) -> tuple[date, ...] | None:
    return (
        value.value
        if value.is_known
        and isinstance(value.value, tuple)
        and all(type(item) is date for item in value.value)
        else None
    )


def _known_footing(value: ProvenancedValue) -> tuple[str, ...] | None:
    return (
        _canonical_footing(value.value)
        if value.is_known and _valid_footing(value.value, allow_empty=False)
        else None
    )


def _valid_grade_distribution(value: Any) -> bool:
    return (
        isinstance(value, TrailGradeDistribution)
        and all(
            type(getattr(value, key)) is int
            and 0 <= getattr(value, key) <= 10000
            for key in _GRADE_KEYS
        )
        and sum(getattr(value, key) for key in _GRADE_KEYS) == 10000
    )


def _valid_footing(value: Any, *, allow_empty: bool) -> bool:
    return (
        isinstance(value, tuple)
        and (allow_empty or bool(value))
        and len(value) == len(set(value))
        and all(type(item) is str and item in _FOOTING_ORDER for item in value)
    )


def _canonical_footing(values: Sequence[str] | set[str]) -> tuple[str, ...]:
    return tuple(sorted(values, key=_FOOTING_ORDER.__getitem__))


def _integer_in_range(value: Any, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _decimal_in_range(value: Any, minimum: int, maximum: int) -> bool:
    if not _is_finite_number(value):
        return False
    try:
        decimal = Decimal(str(value))
    except InvalidOperation:
        return False
    return (
        decimal.as_tuple().exponent >= -2
        and Decimal(minimum) <= decimal <= Decimal(maximum)
    )


def _is_finite_number(value: Any) -> bool:
    return type(value) is int or (type(value) is float and math.isfinite(value))


def _duration_minutes_total(
    values: Sequence[TrailRunningHistoryObservation],
) -> int:
    return int(
        sum(
            (_exact_number_fraction(value.duration_min) for value in values),
            start=Fraction(0),
        )
    )


def _exact_number_fraction(value: int | float) -> Fraction:
    if type(value) is int:
        return Fraction(value)
    numerator, denominator = value.as_integer_ratio()
    return Fraction(numerator, denominator)


def _integer_median(values: Sequence[int]) -> int:
    if not values:
        return 0
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("integer median requires nonnegative integers")
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    return (
        ordered[midpoint]
        if len(ordered) % 2
        else (ordered[midpoint - 1] + ordered[midpoint]) // 2
    )


def _conservative_mode(values: Sequence[int]) -> int:
    if not values:
        return 0
    counts = {value: values.count(value) for value in set(values)}
    maximum = max(counts.values())
    return min(value for value, count in counts.items() if count == maximum)


def _workout_low_minutes(workout: GeneratedTrailWorkout) -> int:
    if workout.intensity_bucket == "low":
        return workout.planned_duration_min
    return (
        CONTROLLED_UPHILL_TEMPLATE.low_intensity_minutes
        if workout.template_id == CONTROLLED_UPHILL_TEMPLATE.template_id
        else 0
    )


def _serialize_step(step: TrailWorkoutStep) -> dict[str, Any]:
    if step.kind == "repeat":
        return {
            "type": "repeat",
            "repetitions": step.repetitions,
            "steps": [_serialize_step(value) for value in step.steps],
        }
    return {
        "type": "step",
        "phase": step.phase,
        "termination": {
            "type": "time",
            "seconds": int(step.duration_min or 0) * 60,
        },
        "intended_intensity": step.intended_intensity,
        "target": {"metric": "none", "unit": "none", "reference": "none"},
    }


def _invalid_input_hash(value: Any, issue: str) -> str:
    return _canonical_fingerprint(
        {
            "invalid_input": True,
            "field": issue,
            "sanitized_input": _sanitize_invalid_value(value),
        }
    )


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
    if type(value) is int:
        if value.bit_length() <= 63:
            return value
        magnitude = abs(value)
        encoded = magnitude.to_bytes(
            max(1, (magnitude.bit_length() + 7) // 8),
            byteorder="big",
        )
        return {
            "__out_of_domain_integer__": {
                "sign": -1 if value < 0 else 1,
                "bit_length": magnitude.bit_length(),
                "magnitude_sha256": hashlib.sha256(encoded).hexdigest(),
            }
        }
    if value is None or type(value) in {bool, str}:
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _sanitize_invalid_value(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        pairs = [
            (_sanitize_invalid_value(key), _sanitize_invalid_value(item))
            for key, item in value.items()
        ]
        return {
            "__mapping__": sorted(
                pairs,
                key=lambda pair: json.dumps(
                    pair[0], sort_keys=True, separators=(",", ":")
                ),
            )
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_invalid_value(item) for item in value]
    return {"__unsupported_type__": type(value).__qualname__}


def _revision(value: Any) -> str:
    return f"{_DIGEST_PREFIX}{_canonical_fingerprint(value)}"


def _is_digest(value: Any) -> bool:
    return (
        type(value) is str
        and value.startswith(_DIGEST_PREFIX)
        and len(value) == len(_DIGEST_PREFIX) + 64
        and all(character in "0123456789abcdef" for character in value[7:])
    )


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
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _json_safe_dates(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {str(key): _json_safe_dates(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_dates(item) for item in value]
    return value
