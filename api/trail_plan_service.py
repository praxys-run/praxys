"""Inactive, owner-scoped Trail v2 draft and readiness orchestration.

The module deliberately has no router registration, capability discovery,
proposal persistence, provider access, or synthetic dry-run entry point.  The
only durable state is one current draft inside ``UserConfig.goal``.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from analysis.non_ultra_trail_contract import (
    NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID,
    NON_ULTRA_TRAIL_CONTRACT_DIGEST,
    NON_ULTRA_TRAIL_COURSE_SCHEMA_ID,
    NON_ULTRA_TRAIL_GENERATOR_VERSION,
    NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT_DIGEST,
    NON_ULTRA_TRAIL_ONTOLOGY_DECISION_ID,
    NON_ULTRA_TRAIL_ONTOLOGY_SOURCE_DECISION_DIGEST,
    NON_ULTRA_TRAIL_ONTOLOGY_VERSION,
    NON_ULTRA_TRAIL_POLICY_VERSION,
    NON_ULTRA_TRAIL_SCIENCE_DECISION_ID,
    NON_ULTRA_TRAIL_SOURCE_DECISION_DIGEST,
)
from analysis.non_ultra_trail_plan_generation import (
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
    TrailRevisionBindings,
    TrailRunningHistoryObservation,
    TrailSectionConfirmation,
    TrailSupportContext,
    derive_recent_history_statistics,
    derive_revision_bindings,
    generate_non_ultra_trail_plan,
)
from analysis.config import normalize_athlete_timezone
from api.plan_generation_capabilities import current_goal_reference
from db.cache_revision import bump_revisions, lock_revision_writes
from db.models import Activity, UserConfig
from db.session import begin_serialized_write


TRAIL_PLAN_GOAL_NAMESPACE = "trail_plan"
TRAIL_PLAN_NAMESPACE_VERSION = 1
TRAIL_EDITABLE_SECTION_KEYS = (
    "section.event-duration",
    "section.grade-footing",
    "section.training-access",
    "section.optional-context",
)

_FOOTING = (
    "firm_smooth",
    "loose_gravel",
    "mud",
    "rocks_or_roots",
    "built_steps",
    "water_crossing",
)
_FOOTING_ORDER = {value: index for index, value in enumerate(_FOOTING)}
_GEAR = (
    "water_carry",
    "food_carry",
    "weather_shell",
    "lighting",
    "navigation_device",
    "other_required",
)
_GEAR_ORDER = {value: index for index, value in enumerate(_GEAR)}
_COURSE_FIELDS = frozenset({
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
    "optional_context",
})
_CONSTRAINT_FIELDS = frozenset({
    "schema_id",
    "available_weekdays",
    "weekly_time_limit_min",
    "maximum_session_duration_min",
    "unavailable_dates",
    "preferred_longest_weekday",
    "nontechnical_three_minute_uphill_access",
    "controlled_downhill_access",
    "accessible_footing",
    "adult_nonclinical_scope_confirmed",
    "performance_intent_confirmed",
    "current_symptom_stop",
})
_ENVIRONMENT_FIELDS = (
    "maximum_altitude_m",
    "temperature_min_c",
    "temperature_max_c",
    "humidity_min_pct",
    "humidity_max_pct",
    "sun_exposure",
    "wind_exposure",
    "conditions_basis",
)
_SUPPORT_FIELDS = (
    "aid_support_mode",
    "aid_station_count",
    "max_aid_station_gap_m",
    "water_availability",
    "food_availability",
    "mandatory_gear",
)
_FUELING_FIELDS = (
    "longest_practiced_duration_min",
    "practice_sessions_last_42_days",
    "intake_form",
    "gastrointestinal_experience",
)
_GRADE_FIELDS = (
    "below_neg_10",
    "neg_10_to_below_neg_3",
    "neg_3_to_below_pos_3",
    "pos_3_to_below_pos_10",
    "pos_10_and_above",
)


class TrailPlanServiceError(RuntimeError):
    """Low-cardinality error safe for the private Trail route adapter."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        private: bool = False,
        **details: Any,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.private = private
        self.details = details

    @property
    def detail(self) -> str | dict[str, Any]:
        if self.private:
            return "Not found"
        return {"code": self.code, "message": self.message, **self.details}


def _invalid(field: str, message: str = "Invalid Trail v2 request.") -> TrailPlanServiceError:
    return TrailPlanServiceError(
        400,
        "TRAIL_INVALID_FIELD_VALUE",
        message,
        field=field,
        status="validation_failed",
        detail_reason="invalid_field_value",
    )


def _schema_mismatch(field: str) -> TrailPlanServiceError:
    return TrailPlanServiceError(
        409,
        "TRAIL_SCHEMA_VERSION_MISMATCH",
        "The stored or requested Trail schema is not executable by v2.",
        field=field,
        status="validation_failed",
        detail_reason="schema_version_mismatch",
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        normalized = value.normalize()
        return int(normalized) if normalized == normalized.to_integral() else float(normalized)
    if isinstance(value, TrailPlanningDurationRange):
        return {"minimum_min": value.minimum_min, "maximum_min": value.maximum_min}
    if isinstance(value, TrailGradeDistribution):
        return asdict(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    return value


def _fingerprint(value: Any) -> str:
    canonical = json.dumps(
        _json_safe(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _revision(value: Any) -> str:
    return f"sha256:{_fingerprint(value)}"


def _is_revision(value: Any) -> bool:
    return (
        type(value) is str
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


ABSENT_TRAIL_PLAN_REVISION = _revision({
    "namespace": TRAIL_PLAN_GOAL_NAMESPACE,
    "state": "absent",
})


def _mapping(
    value: Any,
    *,
    field: str,
    required: Sequence[str],
    optional: Sequence[str] = (),
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _invalid(field)
    keys = set(value)
    required_keys = set(required)
    if not required_keys.issubset(keys) or not keys.issubset(
        required_keys | set(optional)
    ):
        raise _invalid(field)
    return value


def _strict_int(value: Any, *, field: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise _invalid(field)
    return value


def _strict_bool(value: Any, *, field: str) -> bool:
    if type(value) is not bool:
        raise _invalid(field)
    return value


def _enum(value: Any, *, field: str, allowed: Sequence[str]) -> str:
    if type(value) is not str or value not in allowed:
        raise _invalid(field)
    return value


def _decimal_number(
    value: Any,
    *,
    field: str,
    minimum: int,
    maximum: int,
) -> int | float:
    if type(value) is bool or not isinstance(value, (int, float, Decimal)):
        raise _invalid(field)
    if isinstance(value, float) and not math.isfinite(value):
        raise _invalid(field)
    try:
        numeric = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise _invalid(field) from None
    if not numeric.is_finite() or numeric.as_tuple().exponent < -2:
        raise _invalid(field)
    if numeric < minimum or numeric > maximum:
        raise _invalid(field)
    normalized = numeric.normalize()
    return int(normalized) if normalized == normalized.to_integral() else float(normalized)


def _iso_date(value: Any, *, field: str) -> date:
    if type(value) is not str:
        raise _invalid(field)
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise _invalid(field) from None
    if parsed.isoformat() != value:
        raise _invalid(field)
    return parsed


def _closed_set(
    value: Any,
    *,
    field: str,
    allowed: Sequence[Any],
    allow_empty: bool,
    require_sorted: bool = False,
) -> tuple[Any, ...]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise _invalid(field)
    if any(type(item) is not type(allowed[0]) or item not in allowed for item in value):
        raise _invalid(field)
    if len(value) != len(set(value)):
        raise _invalid(field)
    if require_sorted and value != sorted(value):
        raise _invalid(field)
    order = {item: index for index, item in enumerate(allowed)}
    return tuple(sorted(value, key=order.__getitem__))


def _date_set(value: Any, *, field: str) -> tuple[date, ...]:
    if not isinstance(value, list) or len(value) > 14:
        raise _invalid(field)
    parsed = tuple(_iso_date(item, field=field) for item in value)
    if len(parsed) != len(set(parsed)) or tuple(sorted(parsed)) != parsed:
        raise _invalid(field)
    return parsed


def _duration_range(value: Any, *, field: str) -> TrailPlanningDurationRange:
    raw = _mapping(
        value,
        field=field,
        required=("minimum_min", "maximum_min"),
    )
    minimum = _strict_int(raw["minimum_min"], field=f"{field}.minimum_min", minimum=1, maximum=1440)
    maximum = _strict_int(raw["maximum_min"], field=f"{field}.maximum_min", minimum=1, maximum=1440)
    if minimum >= maximum:
        raise _invalid(field)
    return TrailPlanningDurationRange(minimum, maximum)


def _grade(value: Any, *, field: str) -> TrailGradeDistribution:
    raw = _mapping(value, field=field, required=_GRADE_FIELDS)
    shares = {
        name: _strict_int(raw[name], field=f"{field}.{name}", minimum=0, maximum=10000)
        for name in _GRADE_FIELDS
    }
    if sum(shares.values()) != 10000:
        raise _invalid(field)
    return TrailGradeDistribution(**shares)


def _envelope(
    value: Any,
    *,
    field: str,
    validator: Callable[[Any], Any],
    known_null: bool = False,
) -> dict[str, Any]:
    if not isinstance(value, dict) or type(value.get("state")) is not str:
        raise _invalid(field)
    if value["state"] == "unknown":
        if set(value) != {"state"}:
            raise _invalid(field)
        return {"state": "unknown"}
    if value["state"] != "known" or set(value) != {"state", "value"}:
        raise _invalid(field)
    if value["value"] is None and known_null:
        return {"state": "known", "value": None}
    if value["value"] is None:
        raise _invalid(field)
    return {"state": "known", "value": validator(value["value"])}


def _validate_optional_context(value: Any) -> dict[str, dict[str, dict[str, Any]]]:
    raw = _mapping(
        value,
        field="course_demand.fields.optional_context",
        required=("environment", "support", "fueling"),
    )
    environment = _mapping(
        raw["environment"],
        field="course_demand.fields.optional_context.environment",
        required=_ENVIRONMENT_FIELDS,
    )
    support = _mapping(
        raw["support"],
        field="course_demand.fields.optional_context.support",
        required=_SUPPORT_FIELDS,
    )
    fueling = _mapping(
        raw["fueling"],
        field="course_demand.fields.optional_context.fueling",
        required=_FUELING_FIELDS,
    )
    env_path = "course_demand.fields.optional_context.environment"
    support_path = "course_demand.fields.optional_context.support"
    fueling_path = "course_demand.fields.optional_context.fueling"
    normalized_environment = {
        "maximum_altitude_m": _envelope(environment["maximum_altitude_m"], field=f"{env_path}.maximum_altitude_m", validator=lambda item: _strict_int(item, field=f"{env_path}.maximum_altitude_m.value", minimum=-500, maximum=9000)),
        "temperature_min_c": _envelope(environment["temperature_min_c"], field=f"{env_path}.temperature_min_c", validator=lambda item: _decimal_number(item, field=f"{env_path}.temperature_min_c.value", minimum=-30, maximum=55)),
        "temperature_max_c": _envelope(environment["temperature_max_c"], field=f"{env_path}.temperature_max_c", validator=lambda item: _decimal_number(item, field=f"{env_path}.temperature_max_c.value", minimum=-30, maximum=55)),
        "humidity_min_pct": _envelope(environment["humidity_min_pct"], field=f"{env_path}.humidity_min_pct", validator=lambda item: _decimal_number(item, field=f"{env_path}.humidity_min_pct.value", minimum=0, maximum=100)),
        "humidity_max_pct": _envelope(environment["humidity_max_pct"], field=f"{env_path}.humidity_max_pct", validator=lambda item: _decimal_number(item, field=f"{env_path}.humidity_max_pct.value", minimum=0, maximum=100)),
        "sun_exposure": _envelope(environment["sun_exposure"], field=f"{env_path}.sun_exposure", validator=lambda item: _enum(item, field=f"{env_path}.sun_exposure.value", allowed=("low", "mixed", "high"))),
        "wind_exposure": _envelope(environment["wind_exposure"], field=f"{env_path}.wind_exposure", validator=lambda item: _enum(item, field=f"{env_path}.wind_exposure.value", allowed=("sheltered", "mixed", "exposed"))),
        "conditions_basis": _envelope(environment["conditions_basis"], field=f"{env_path}.conditions_basis", validator=lambda item: _enum(item, field=f"{env_path}.conditions_basis.value", allowed=("organizer_information", "seasonal_expectation", "athlete_assumption"))),
    }
    normalized_support = {
        "aid_support_mode": _envelope(support["aid_support_mode"], field=f"{support_path}.aid_support_mode", validator=lambda item: _enum(item, field=f"{support_path}.aid_support_mode.value", allowed=("organized_aid", "mixed", "self_supported"))),
        "aid_station_count": _envelope(support["aid_station_count"], field=f"{support_path}.aid_station_count", validator=lambda item: _strict_int(item, field=f"{support_path}.aid_station_count.value", minimum=0, maximum=50)),
        "max_aid_station_gap_m": _envelope(support["max_aid_station_gap_m"], field=f"{support_path}.max_aid_station_gap_m", validator=lambda item: _strict_int(item, field=f"{support_path}.max_aid_station_gap_m.value", minimum=100, maximum=50000), known_null=True),
        "water_availability": _envelope(support["water_availability"], field=f"{support_path}.water_availability", validator=lambda item: _enum(item, field=f"{support_path}.water_availability.value", allowed=("none", "some_stations", "all_stations"))),
        "food_availability": _envelope(support["food_availability"], field=f"{support_path}.food_availability", validator=lambda item: _enum(item, field=f"{support_path}.food_availability.value", allowed=("none", "some_stations", "all_stations"))),
        "mandatory_gear": _envelope(support["mandatory_gear"], field=f"{support_path}.mandatory_gear", validator=lambda item: _closed_set(item, field=f"{support_path}.mandatory_gear.value", allowed=_GEAR, allow_empty=True)),
    }
    normalized_fueling = {
        "longest_practiced_duration_min": _envelope(fueling["longest_practiced_duration_min"], field=f"{fueling_path}.longest_practiced_duration_min", validator=lambda item: _strict_int(item, field=f"{fueling_path}.longest_practiced_duration_min.value", minimum=0, maximum=1440)),
        "practice_sessions_last_42_days": _envelope(fueling["practice_sessions_last_42_days"], field=f"{fueling_path}.practice_sessions_last_42_days", validator=lambda item: _strict_int(item, field=f"{fueling_path}.practice_sessions_last_42_days.value", minimum=0, maximum=84)),
        "intake_form": _envelope(fueling["intake_form"], field=f"{fueling_path}.intake_form", validator=lambda item: _enum(item, field=f"{fueling_path}.intake_form.value", allowed=("none", "fluids_only", "carbohydrate_drink", "mixed_food_and_drink"))),
        "gastrointestinal_experience": _envelope(fueling["gastrointestinal_experience"], field=f"{fueling_path}.gastrointestinal_experience", validator=lambda item: _enum(item, field=f"{fueling_path}.gastrointestinal_experience.value", allowed=("no_plan_altering_issue", "plan_altering_issue"))),
    }
    for minimum_key, maximum_key in (
        ("temperature_min_c", "temperature_max_c"),
        ("humidity_min_pct", "humidity_max_pct"),
    ):
        minimum_value = normalized_environment[minimum_key]
        maximum_value = normalized_environment[maximum_key]
        if (
            minimum_value["state"] == "known"
            and maximum_value["state"] == "known"
            and minimum_value["value"] > maximum_value["value"]
        ):
            raise _invalid(f"{env_path}.{minimum_key}")
    return {
        "environment": normalized_environment,
        "support": normalized_support,
        "fueling": normalized_fueling,
    }


def validate_trail_draft_request(value: Any) -> dict[str, Any]:
    """Validate and normalize the exact client-writable Trail v2 DTO."""
    root = _mapping(
        value,
        field="body",
        required=("course_demand", "constraints"),
    )
    course = _mapping(
        root["course_demand"],
        field="course_demand",
        required=("schema_id", "fields"),
    )
    if course["schema_id"] != NON_ULTRA_TRAIL_COURSE_SCHEMA_ID:
        raise _schema_mismatch("course_demand.schema_id")
    fields = _mapping(
        course["fields"],
        field="course_demand.fields",
        required=tuple(_COURSE_FIELDS),
    )
    course_path = "course_demand.fields"
    normalized_course = {
        "event_date": _envelope(fields["event_date"], field=f"{course_path}.event_date", validator=lambda item: _iso_date(item, field=f"{course_path}.event_date.value")),
        "distance_meters": _envelope(fields["distance_meters"], field=f"{course_path}.distance_meters", validator=lambda item: _strict_int(item, field=f"{course_path}.distance_meters.value", minimum=1, maximum=49999)),
        "total_ascent_m": _envelope(fields["total_ascent_m"], field=f"{course_path}.total_ascent_m", validator=lambda item: _strict_int(item, field=f"{course_path}.total_ascent_m.value", minimum=0, maximum=20000)),
        "total_descent_m": _envelope(fields["total_descent_m"], field=f"{course_path}.total_descent_m", validator=lambda item: _strict_int(item, field=f"{course_path}.total_descent_m.value", minimum=0, maximum=20000)),
        "planning_duration_range": _envelope(fields["planning_duration_range"], field=f"{course_path}.planning_duration_range", validator=lambda item: _duration_range(item, field=f"{course_path}.planning_duration_range.value")),
        "event_format": _envelope(fields["event_format"], field=f"{course_path}.event_format", validator=lambda item: _enum(item, field=f"{course_path}.event_format.value", allowed=("single_day", "multi_day"))),
        "distance_family": _envelope(fields["distance_family"], field=f"{course_path}.distance_family", validator=lambda item: _enum(item, field=f"{course_path}.distance_family.value", allowed=("non_ultra", "ultra"))),
        "planning_intent": _envelope(fields["planning_intent"], field=f"{course_path}.planning_intent", validator=lambda item: _enum(item, field=f"{course_path}.planning_intent.value", allowed=("performance", "first_completion", "return_to_consistency"))),
        "grade_distribution": _envelope(fields["grade_distribution"], field=f"{course_path}.grade_distribution", validator=lambda item: _grade(item, field=f"{course_path}.grade_distribution.value")),
        "course_footing": _envelope(fields["course_footing"], field=f"{course_path}.course_footing", validator=lambda item: _closed_set(item, field=f"{course_path}.course_footing.value", allowed=_FOOTING, allow_empty=False)),
        "hands_assist": _envelope(fields["hands_assist"], field=f"{course_path}.hands_assist", validator=lambda item: _strict_bool(item, field=f"{course_path}.hands_assist.value")),
        "fixed_rope": _envelope(fields["fixed_rope"], field=f"{course_path}.fixed_rope", validator=lambda item: _strict_bool(item, field=f"{course_path}.fixed_rope.value")),
        "optional_context": _validate_optional_context(fields["optional_context"]),
    }
    constraints = _mapping(
        root["constraints"],
        field="constraints",
        required=tuple(_CONSTRAINT_FIELDS - {"preferred_longest_weekday"}),
        optional=("preferred_longest_weekday",),
    )
    if constraints["schema_id"] != NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID:
        raise _schema_mismatch("constraints.schema_id")
    constraint_path = "constraints"
    preferred = None
    if "preferred_longest_weekday" in constraints:
        if constraints["preferred_longest_weekday"] is None:
            raise _invalid("constraints.preferred_longest_weekday")
        preferred = _strict_int(
            constraints["preferred_longest_weekday"],
            field=f"{constraint_path}.preferred_longest_weekday",
            minimum=1,
            maximum=7,
        )
    normalized_constraints = {
        "available_weekdays": _envelope(constraints["available_weekdays"], field=f"{constraint_path}.available_weekdays", validator=lambda item: _closed_set(item, field=f"{constraint_path}.available_weekdays.value", allowed=(1, 2, 3, 4, 5, 6, 7), allow_empty=False)),
        "weekly_time_limit_min": _envelope(constraints["weekly_time_limit_min"], field=f"{constraint_path}.weekly_time_limit_min", validator=lambda item: _strict_int(item, field=f"{constraint_path}.weekly_time_limit_min.value", minimum=1, maximum=10080)),
        "maximum_session_duration_min": _envelope(constraints["maximum_session_duration_min"], field=f"{constraint_path}.maximum_session_duration_min", validator=lambda item: _strict_int(item, field=f"{constraint_path}.maximum_session_duration_min.value", minimum=1, maximum=1440)),
        "unavailable_dates": _envelope(constraints["unavailable_dates"], field=f"{constraint_path}.unavailable_dates", validator=lambda item: _date_set(item, field=f"{constraint_path}.unavailable_dates.value")),
        "preferred_longest_weekday": preferred,
        "nontechnical_three_minute_uphill_access": _envelope(constraints["nontechnical_three_minute_uphill_access"], field=f"{constraint_path}.nontechnical_three_minute_uphill_access", validator=lambda item: _strict_bool(item, field=f"{constraint_path}.nontechnical_three_minute_uphill_access.value")),
        "controlled_downhill_access": _envelope(constraints["controlled_downhill_access"], field=f"{constraint_path}.controlled_downhill_access", validator=lambda item: _strict_bool(item, field=f"{constraint_path}.controlled_downhill_access.value")),
        "accessible_footing": _envelope(constraints["accessible_footing"], field=f"{constraint_path}.accessible_footing", validator=lambda item: _closed_set(item, field=f"{constraint_path}.accessible_footing.value", allowed=_FOOTING, allow_empty=False)),
        "adult_nonclinical_scope_confirmed": _envelope(constraints["adult_nonclinical_scope_confirmed"], field=f"{constraint_path}.adult_nonclinical_scope_confirmed", validator=lambda item: _strict_bool(item, field=f"{constraint_path}.adult_nonclinical_scope_confirmed.value")),
        "performance_intent_confirmed": _envelope(constraints["performance_intent_confirmed"], field=f"{constraint_path}.performance_intent_confirmed", validator=lambda item: _strict_bool(item, field=f"{constraint_path}.performance_intent_confirmed.value")),
        "current_symptom_stop": _envelope(constraints["current_symptom_stop"], field=f"{constraint_path}.current_symptom_stop", validator=lambda item: _strict_bool(item, field=f"{constraint_path}.current_symptom_stop.value")),
    }
    weekly = normalized_constraints["weekly_time_limit_min"]
    session = normalized_constraints["maximum_session_duration_min"]
    if weekly["state"] == session["state"] == "known" and session["value"] > weekly["value"]:
        raise _invalid("constraints.maximum_session_duration_min")
    weekdays = normalized_constraints["available_weekdays"]
    if preferred is not None and weekdays["state"] == "known" and preferred not in weekdays["value"]:
        # The pure core preserves this as contradictory input; both values are
        # individually valid, so do not collapse it into transport validation.
        pass
    return {
        "course_demand": {
            "schema_id": NON_ULTRA_TRAIL_COURSE_SCHEMA_ID,
            "fields": normalized_course,
        },
        "constraints": {
            "schema_id": NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID,
            **normalized_constraints,
        },
    }


def _unknown_envelope() -> dict[str, str]:
    return {"state": "unknown"}


def _reset_request() -> dict[str, Any]:
    optional = {
        "environment": {name: _unknown_envelope() for name in _ENVIRONMENT_FIELDS},
        "support": {name: _unknown_envelope() for name in _SUPPORT_FIELDS},
        "fueling": {name: _unknown_envelope() for name in _FUELING_FIELDS},
    }
    return {
        "course_demand": {
            "schema_id": NON_ULTRA_TRAIL_COURSE_SCHEMA_ID,
            "fields": {
                **{
                    name: _unknown_envelope()
                    for name in _COURSE_FIELDS
                    if name != "optional_context"
                },
                "optional_context": optional,
            },
        },
        "constraints": {
            "schema_id": NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID,
            **{
                name: _unknown_envelope()
                for name in _CONSTRAINT_FIELDS
                if name not in {"schema_id", "preferred_longest_weekday"}
            },
            "preferred_longest_weekday": None,
        },
    }


def _client_projection(value: ProvenancedValue) -> dict[str, Any]:
    payload: dict[str, Any] = {"state": value.state}
    if value.is_known:
        payload["value"] = _json_safe(value.value)
    return payload


def _stamp(
    envelope: Mapping[str, Any],
    *,
    field: str,
    now: datetime,
    previous: ProvenancedValue | None,
    force_new: bool,
) -> ProvenancedValue:
    provenance = "unknown"
    if envelope["state"] == "known":
        provenance = (
            "explicit_assumption"
            if field == "environment.conditions_basis"
            and envelope["value"] == "athlete_assumption"
            else "athlete_stated"
        )
    if (
        not force_new
        and previous is not None
        and previous.provenance == provenance
        and _client_projection(previous) == _json_safe(dict(envelope))
    ):
        return previous
    source_revision = _revision({
        "field": field,
        "previous": previous.source_revision if previous is not None else None,
        "value": envelope,
        "mutation": uuid4().hex,
    })
    return ProvenancedValue(
        state=str(envelope["state"]),  # type: ignore[arg-type]
        provenance=provenance,
        source_revision=source_revision,
        value=envelope.get("value"),
        source_timestamp=now,
    )


def _previous_values(
    course: TrailCourseDemand | None,
    constraints: TrailPlanGenerationConstraints | None,
) -> dict[str, ProvenancedValue]:
    if course is None or constraints is None:
        return {}
    values: dict[str, ProvenancedValue] = {
        name: getattr(course, name)
        for name in _COURSE_FIELDS
        if name != "optional_context"
    }
    values.update({
        f"environment.{name}": getattr(course.optional_context.environment, name)
        for name in _ENVIRONMENT_FIELDS
    })
    values.update({
        f"support.{name}": getattr(course.optional_context.support, name)
        for name in _SUPPORT_FIELDS
    })
    values.update({
        f"fueling.{name}": getattr(course.optional_context.fueling, name)
        for name in _FUELING_FIELDS
    })
    values.update({
        f"constraints.{name}": getattr(constraints, name)
        for name in _CONSTRAINT_FIELDS
        if name not in {"schema_id", "preferred_longest_weekday"}
    })
    return values


def _build_models(
    request: Mapping[str, Any],
    *,
    event_id: str,
    now: datetime,
    previous_course: TrailCourseDemand | None,
    previous_constraints: TrailPlanGenerationConstraints | None,
    force_new: bool = False,
) -> tuple[TrailCourseDemand, TrailPlanGenerationConstraints]:
    previous = _previous_values(previous_course, previous_constraints)
    course_fields = request["course_demand"]["fields"]
    optional = course_fields["optional_context"]

    def stamp(path: str, envelope: Mapping[str, Any]) -> ProvenancedValue:
        return _stamp(
            envelope,
            field=path,
            now=now,
            previous=previous.get(path),
            force_new=force_new,
        )

    environment = TrailEnvironmentContext(**{
        name: stamp(f"environment.{name}", optional["environment"][name])
        for name in _ENVIRONMENT_FIELDS
    })
    support = TrailSupportContext(**{
        name: stamp(f"support.{name}", optional["support"][name])
        for name in _SUPPORT_FIELDS
    })
    fueling = TrailFuelingContext(**{
        name: stamp(f"fueling.{name}", optional["fueling"][name])
        for name in _FUELING_FIELDS
    })
    course = TrailCourseDemand(
        event_id=event_id,
        optional_context=TrailOptionalContext(
            environment=environment,
            support=support,
            fueling=fueling,
        ),
        **{
            name: stamp(name, course_fields[name])
            for name in _COURSE_FIELDS
            if name != "optional_context"
        },
    )
    constraint_request = request["constraints"]
    constraints = TrailPlanGenerationConstraints(
        preferred_longest_weekday=constraint_request.get(
            "preferred_longest_weekday"
        ),
        **{
            name: stamp(f"constraints.{name}", constraint_request[name])
            for name in _CONSTRAINT_FIELDS
            if name not in {"schema_id", "preferred_longest_weekday"}
        },
    )
    return course, constraints


def _stored_value(
    raw: Any,
    *,
    field: str,
    converter: Callable[[Any], Any] = lambda value: value,
) -> ProvenancedValue:
    value = _mapping(
        raw,
        field=field,
        required=("state", "provenance", "source_revision"),
        optional=(
            "value",
            "source_timestamp",
            "model_version",
            "assumption_confirmed_revision",
        ),
    )
    state = value["state"]
    if state not in {"known", "unknown"}:
        raise _schema_mismatch(field)
    if state == "known" and "value" not in value:
        raise _schema_mismatch(field)
    if state == "unknown" and "value" in value:
        raise _schema_mismatch(field)
    timestamp = None
    if value.get("source_timestamp") is not None:
        try:
            timestamp = datetime.fromisoformat(str(value["source_timestamp"]))
        except ValueError:
            raise _schema_mismatch(field) from None
        if timestamp.tzinfo is None:
            raise _schema_mismatch(field)
    converted = converter(value.get("value")) if state == "known" else None
    return ProvenancedValue(
        state=state,
        provenance=str(value["provenance"]),
        source_revision=str(value["source_revision"]),
        value=converted,
        source_timestamp=timestamp,
        model_version=value.get("model_version"),
        assumption_confirmed_revision=value.get(
            "assumption_confirmed_revision"
        ),
    )


def _deserialize_models(raw: Mapping[str, Any]) -> tuple[TrailCourseDemand, TrailPlanGenerationConstraints, dict[str, str | None]]:
    if raw.get("namespace_version") != TRAIL_PLAN_NAMESPACE_VERSION:
        raise _schema_mismatch("trail_plan.namespace_version")
    course_raw = _mapping(
        raw.get("course_demand"),
        field="trail_plan.course_demand",
        required=("schema_id", "event_id", "fields"),
    )
    if course_raw["schema_id"] != NON_ULTRA_TRAIL_COURSE_SCHEMA_ID:
        raise _schema_mismatch("trail_plan.course_demand.schema_id")
    fields_raw = _mapping(
        course_raw["fields"],
        field="trail_plan.course_demand.fields",
        required=tuple(_COURSE_FIELDS),
    )
    optional_raw = _mapping(
        fields_raw["optional_context"],
        field="trail_plan.course_demand.fields.optional_context",
        required=("environment", "support", "fueling"),
    )
    environment_raw = _mapping(optional_raw["environment"], field="trail_plan.environment", required=_ENVIRONMENT_FIELDS)
    support_raw = _mapping(optional_raw["support"], field="trail_plan.support", required=_SUPPORT_FIELDS)
    fueling_raw = _mapping(optional_raw["fueling"], field="trail_plan.fueling", required=_FUELING_FIELDS)
    converters: dict[str, Callable[[Any], Any]] = {
        "event_date": lambda value: date.fromisoformat(str(value)),
        "planning_duration_range": lambda value: TrailPlanningDurationRange(
            int(value["minimum_min"]), int(value["maximum_min"])
        ),
        "grade_distribution": lambda value: TrailGradeDistribution(**{
            key: int(value[key]) for key in _GRADE_FIELDS
        }),
        "course_footing": lambda value: tuple(value),
    }
    course = TrailCourseDemand(
        event_id=str(course_raw["event_id"]),
        optional_context=TrailOptionalContext(
            environment=TrailEnvironmentContext(**{
                name: _stored_value(environment_raw[name], field=f"environment.{name}")
                for name in _ENVIRONMENT_FIELDS
            }),
            support=TrailSupportContext(**{
                name: _stored_value(
                    support_raw[name],
                    field=f"support.{name}",
                    converter=(lambda value: tuple(value)) if name == "mandatory_gear" else (lambda value: value),
                )
                for name in _SUPPORT_FIELDS
            }),
            fueling=TrailFuelingContext(**{
                name: _stored_value(fueling_raw[name], field=f"fueling.{name}")
                for name in _FUELING_FIELDS
            }),
        ),
        **{
            name: _stored_value(
                fields_raw[name],
                field=name,
                converter=converters.get(name, lambda value: value),
            )
            for name in _COURSE_FIELDS
            if name != "optional_context"
        },
    )
    constraints_raw = _mapping(
        raw.get("constraints"),
        field="trail_plan.constraints",
        required=tuple(_CONSTRAINT_FIELDS),
    )
    if constraints_raw["schema_id"] != NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID:
        raise _schema_mismatch("trail_plan.constraints.schema_id")
    constraint_converters: dict[str, Callable[[Any], Any]] = {
        "available_weekdays": lambda value: tuple(value),
        "unavailable_dates": lambda value: tuple(
            date.fromisoformat(str(item)) for item in value
        ),
        "accessible_footing": lambda value: tuple(value),
    }
    constraints = TrailPlanGenerationConstraints(
        preferred_longest_weekday=constraints_raw["preferred_longest_weekday"],
        **{
            name: _stored_value(
                constraints_raw[name],
                field=f"constraints.{name}",
                converter=constraint_converters.get(name, lambda value: value),
            )
            for name in _CONSTRAINT_FIELDS
            if name not in {"schema_id", "preferred_longest_weekday"}
        },
    )
    confirmations_raw = _mapping(
        raw.get("confirmations"),
        field="trail_plan.confirmations",
        required=TRAIL_EDITABLE_SECTION_KEYS,
    )
    confirmations: dict[str, str | None] = {}
    for key in TRAIL_EDITABLE_SECTION_KEYS:
        confirmed = confirmations_raw[key]
        if confirmed is not None and (
            type(confirmed) is not str
            or not confirmed.startswith("sha256:")
            or len(confirmed) != 71
        ):
            raise _schema_mismatch("trail_plan.confirmations")
        confirmations[key] = confirmed
    return course, constraints, confirmations


def _serialize_stored(
    course: TrailCourseDemand,
    constraints: TrailPlanGenerationConstraints,
    confirmations: Mapping[str, str | None],
    bindings: TrailRevisionBindings,
) -> dict[str, Any]:
    return {
        "namespace_version": TRAIL_PLAN_NAMESPACE_VERSION,
        "course_demand": course.public_payload(),
        "constraints": constraints.public_payload(),
        "confirmations": {
            key: confirmations.get(key) for key in TRAIL_EDITABLE_SECTION_KEYS
        },
        "last_revision_bindings": _json_safe(asdict(bindings)),
    }


def _current_goal_event_id(*, user_id: str, goal: Mapping[str, Any]) -> str:
    base_goal = dict(goal)
    base_goal.pop(TRAIL_PLAN_GOAL_NAMESPACE, None)
    if not base_goal:
        raise TrailPlanServiceError(
            404,
            "TRAIL_GOAL_NOT_FOUND",
            "Not found",
            private=True,
        )
    reference = current_goal_reference(user_id=user_id, goal=base_goal)
    if reference is None:
        raise TrailPlanServiceError(
            404,
            "TRAIL_GOAL_NOT_FOUND",
            "Not found",
            private=True,
        )
    return reference.goal_id


def _parse_source_timestamp(
    value: Any,
    *,
    athlete_timezone: str | None,
) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed
    if athlete_timezone is None:
        return None
    return parsed.replace(tzinfo=ZoneInfo(athlete_timezone))


def _whole_nonnegative_int(value: Any) -> int | None:
    if type(value) is int and value >= 0:
        return value
    if type(value) is float and math.isfinite(value) and value >= 0 and value.is_integer():
        return int(value)
    return None


def _history_statistics(
    db: Session,
    *,
    user_id: str,
    athlete_today: date,
    athlete_timezone: str | None,
) -> RecentTrailHistoryStatistics:
    """Derive only evidence represented authoritatively by current tables.

    ``Activity`` has no descent or footing fields, so neither is inferred.
    Canonical Garmin/COROS ``running`` values exclude their separately named
    treadmill activity types and can support general running continuity;
    ``trail_running`` additionally supports direct ascent context.
    """
    rows = db.execute(
        select(Activity)
        .where(
            Activity.user_id == user_id,
            Activity.date >= athlete_today - timedelta(days=70),
            Activity.date < athlete_today,
        )
        .order_by(Activity.date, Activity.id)
    ).scalars().all()
    observations: list[TrailRunningHistoryObservation] = []
    for row in rows:
        activity_type = str(row.activity_type or "").strip().casefold()
        source = str(row.source or "").strip().casefold()
        outdoor_confirmed = activity_type == "trail_running" or (
            activity_type == "running" and source in {"garmin", "coros"}
        )
        timestamp = _parse_source_timestamp(
            row.start_time,
            athlete_timezone=athlete_timezone,
        )
        if not outdoor_confirmed or timestamp is None:
            continue
        if (
            not isinstance(row.duration_sec, (int, float))
            or isinstance(row.duration_sec, bool)
            or not math.isfinite(float(row.duration_sec))
            or float(row.duration_sec) <= 0
            or not isinstance(row.distance_km, (int, float))
            or isinstance(row.distance_km, bool)
            or not math.isfinite(float(row.distance_km))
            or float(row.distance_km) <= 0
        ):
            continue
        source_revision = _revision({
            "activity_id": str(row.activity_id),
            "source": source,
            "date": row.date.isoformat(),
            "activity_type": activity_type,
            "duration_sec": float(row.duration_sec),
            "distance_km": float(row.distance_km),
            "elevation_gain_m": row.elevation_gain_m,
            "start_time": timestamp.isoformat(),
        })
        observations.append(
            TrailRunningHistoryObservation(
                activity_id=str(row.activity_id),
                observed_date=row.date,
                activity_type=activity_type,
                duration_min=float(row.duration_sec) / 60.0,
                distance_km=float(row.distance_km),
                elevation_gain_meters=_whole_nonnegative_int(
                    row.elevation_gain_m
                ),
                elevation_loss_meters=None,
                observed_footing=None,
                source_revision=source_revision,
                source_timestamp=timestamp,
                outdoor_confirmed=outdoor_confirmed,
            )
        )
    try:
        return derive_recent_history_statistics(
            tuple(observations),
            athlete_today=athlete_today,
        )
    except ValueError:
        return RecentTrailHistoryStatistics.empty()


def _composite_revision(
    *,
    course_revision: str,
    planning_context_revision: str,
    history_revision: str,
    confirmations: Sequence[TrailSectionConfirmation],
) -> str:
    return _revision({
        "course_revision": course_revision,
        "planning_context_revision": planning_context_revision,
        "history_revision": history_revision,
        "section_confirmations": {
            item.section_key: item.confirmed_revision
            for item in sorted(confirmations, key=lambda item: item.section_key)
        },
        "course_schema_id": NON_ULTRA_TRAIL_COURSE_SCHEMA_ID,
        "constraint_schema_id": NON_ULTRA_TRAIL_CONSTRAINT_SCHEMA_ID,
        "ontology_decision_id": NON_ULTRA_TRAIL_ONTOLOGY_DECISION_ID,
        "ontology_contract_digest": NON_ULTRA_TRAIL_ONTOLOGY_CONTRACT_DIGEST,
        "policy_decision_id": NON_ULTRA_TRAIL_SCIENCE_DECISION_ID,
        "policy_contract_digest": NON_ULTRA_TRAIL_CONTRACT_DIGEST,
        "generator_version": NON_ULTRA_TRAIL_GENERATOR_VERSION,
    })


def _bindings(
    course: TrailCourseDemand,
    constraints: TrailPlanGenerationConstraints,
    statistics: RecentTrailHistoryStatistics,
    confirmations: Mapping[str, str | None],
) -> TrailRevisionBindings:
    base = derive_revision_bindings(
        course_demand=course,
        constraints=constraints,
        history_statistics=statistics,
        confirmed=False,
    )
    section_confirmations = tuple(
        TrailSectionConfirmation(
            section_key=item.section_key,
            current_revision=item.current_revision,
            confirmed_revision=confirmations.get(item.section_key),
        )
        for item in base.section_confirmations
    )
    if all(
        item.confirmed_revision == item.current_revision
        for item in section_confirmations
    ):
        # Use the core's exact fully-confirmed representation so readiness can
        # compare it without a second implementation of accepted semantics.
        return derive_revision_bindings(
            course_demand=course,
            constraints=constraints,
            history_statistics=statistics,
            confirmed=True,
        )
    return TrailRevisionBindings(
        course_revision=base.course_revision,
        planning_context_revision=base.planning_context_revision,
        history_revision=base.history_revision,
        composite_revision=_composite_revision(
            course_revision=base.course_revision,
            planning_context_revision=base.planning_context_revision,
            history_revision=base.history_revision,
            confirmations=section_confirmations,
        ),
        section_confirmations=section_confirmations,
    )


def _row(db: Session, *, user_id: str, for_update: bool = False) -> UserConfig:
    statement = select(UserConfig).where(UserConfig.user_id == user_id)
    if for_update:
        statement = statement.with_for_update()
    row = db.execute(statement).scalar_one_or_none()
    if row is None:
        raise TrailPlanServiceError(
            404,
            "TRAIL_GOAL_NOT_FOUND",
            "Not found",
            private=True,
        )
    return row


def _unknown_state(raw: Any) -> dict[str, Any]:
    return {
        "state": "unknown_schema",
        "namespace": deepcopy(raw),
        "composite_revision": _revision({"trail_plan": raw}),
    }


def _current(
    db: Session,
    *,
    user_id: str,
    row: UserConfig,
    athlete_today: date,
) -> tuple[dict[str, Any], TrailCourseDemand | None, TrailPlanGenerationConstraints | None, RecentTrailHistoryStatistics | None, dict[str, str | None] | None, TrailRevisionBindings | None]:
    goal = dict(row.goal or {})
    if TRAIL_PLAN_GOAL_NAMESPACE not in goal:
        return (
            {"state": "absent", "composite_revision": ABSENT_TRAIL_PLAN_REVISION},
            None,
            None,
            None,
            None,
            None,
        )
    raw = goal[TRAIL_PLAN_GOAL_NAMESPACE]
    if not isinstance(raw, Mapping):
        return _unknown_state(raw), None, None, None, None, None
    try:
        course, constraints, confirmations = _deserialize_models(raw)
    except (TrailPlanServiceError, TypeError, ValueError, KeyError):
        return _unknown_state(raw), None, None, None, None, None
    event_id = _current_goal_event_id(user_id=user_id, goal=goal)
    if course.event_id != event_id:
        course = replace(course, event_id=event_id)
    statistics = _history_statistics(
        db,
        user_id=user_id,
        athlete_today=athlete_today,
        athlete_timezone=normalize_athlete_timezone(
            (row.source_options or {}).get("athlete_timezone")
        ),
    )
    bindings = _bindings(course, constraints, statistics, confirmations)
    return (
        {
            "state": "current",
            "namespace_version": TRAIL_PLAN_NAMESPACE_VERSION,
            "course_demand": course.public_payload(),
            "constraints": constraints.public_payload(),
            "revision_bindings": _json_safe(asdict(bindings)),
            "composite_revision": bindings.composite_revision,
        },
        course,
        constraints,
        statistics,
        confirmations,
        bindings,
    )


def _assert_match(expected_revision: str, current_revision: str) -> None:
    if not expected_revision:
        raise TrailPlanServiceError(
            428,
            "TRAIL_IF_MATCH_REQUIRED",
            "An exact If-Match revision is required.",
        )
    if expected_revision != current_revision:
        raise TrailPlanServiceError(
            412,
            "TRAIL_REVISION_CONFLICT",
            "The Trail draft changed. Fetch the current revision before retrying.",
            current_revision=current_revision,
        )


def _athlete_today(value: date | None) -> date:
    return value if value is not None else datetime.now(timezone.utc).date()


def _validate_unavailable_date_horizon(
    request: Mapping[str, Any],
    *,
    block_start: date,
) -> None:
    unavailable = request["constraints"]["unavailable_dates"]
    if unavailable["state"] != "known":
        return
    horizon_end = block_start + timedelta(days=14)
    if any(
        item < block_start or item >= horizon_end
        for item in unavailable["value"]
    ):
        raise _invalid("constraints.unavailable_dates")


def read_trail_plan_draft(
    db: Session,
    *,
    user_id: str,
    athlete_today: date | None = None,
) -> dict[str, Any]:
    row = _row(db, user_id=user_id)
    state, *_ = _current(
        db,
        user_id=user_id,
        row=row,
        athlete_today=_athlete_today(athlete_today),
    )
    return state


def _begin_write(db: Session, *, user_id: str) -> UserConfig:
    db.rollback()
    begin_serialized_write(db)
    lock_revision_writes(db, user_id)
    return _row(db, user_id=user_id, for_update=True)


def _commit_namespace(
    db: Session,
    *,
    row: UserConfig,
    user_id: str,
    namespace: Any | None,
) -> None:
    goal = dict(row.goal or {})
    if namespace is None:
        goal.pop(TRAIL_PLAN_GOAL_NAMESPACE, None)
    else:
        goal[TRAIL_PLAN_GOAL_NAMESPACE] = namespace
    row.goal = goal
    bump_revisions(db, user_id, ("config", "goals"))
    db.commit()


def save_trail_plan_draft(
    db: Session,
    *,
    user_id: str,
    request: Any,
    expected_revision: str,
    athlete_today: date | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    normalized = validate_trail_draft_request(request)
    today = _athlete_today(athlete_today)
    _validate_unavailable_date_horizon(normalized, block_start=today)
    timestamp = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    try:
        row = _begin_write(db, user_id=user_id)
        current, old_course, old_constraints, statistics, old_confirmations, old_bindings = _current(
            db, user_id=user_id, row=row, athlete_today=today
        )
        _assert_match(expected_revision, current["composite_revision"])
        if current["state"] == "unknown_schema":
            raise _schema_mismatch("trail_plan")
        event_id = _current_goal_event_id(user_id=user_id, goal=dict(row.goal or {}))
        course, constraints = _build_models(
            normalized,
            event_id=event_id,
            now=timestamp,
            previous_course=old_course,
            previous_constraints=old_constraints,
        )
        statistics = statistics or _history_statistics(
            db,
            user_id=user_id,
            athlete_today=today,
            athlete_timezone=normalize_athlete_timezone(
                (row.source_options or {}).get("athlete_timezone")
            ),
        )
        provisional = _bindings(course, constraints, statistics, {})
        confirmations: dict[str, str | None] = {}
        old_by_key = {
            item.section_key: item for item in old_bindings.section_confirmations
        } if old_bindings is not None else {}
        new_by_key = {
            item.section_key: item for item in provisional.section_confirmations
        }
        for key in TRAIL_EDITABLE_SECTION_KEYS:
            old_item = old_by_key.get(key)
            confirmations[key] = (
                (old_confirmations or {}).get(key)
                if old_item is not None
                and old_item.current_revision == new_by_key[key].current_revision
                else None
            )
        bindings = _bindings(course, constraints, statistics, confirmations)
        namespace = _serialize_stored(course, constraints, confirmations, bindings)
        if (
            current["state"] == "current"
            and isinstance((row.goal or {}).get(TRAIL_PLAN_GOAL_NAMESPACE), Mapping)
            and namespace == (row.goal or {})[TRAIL_PLAN_GOAL_NAMESPACE]
        ):
            db.rollback()
            return current
        response = {
            "state": "current",
            "namespace_version": TRAIL_PLAN_NAMESPACE_VERSION,
            "course_demand": course.public_payload(),
            "constraints": constraints.public_payload(),
            "revision_bindings": _json_safe(asdict(bindings)),
            "composite_revision": bindings.composite_revision,
        }
        _commit_namespace(
            db,
            row=row,
            user_id=user_id,
            namespace=namespace,
        )
        return response
    except Exception:
        db.rollback()
        raise


def confirm_trail_plan_section(
    db: Session,
    *,
    user_id: str,
    section_key: str,
    section_revision: str,
    expected_revision: str,
    athlete_today: date | None = None,
) -> dict[str, Any]:
    if section_key not in TRAIL_EDITABLE_SECTION_KEYS:
        raise _invalid("section_key")
    if not _is_revision(section_revision):
        raise _invalid("section_revision")
    today = _athlete_today(athlete_today)
    try:
        row = _begin_write(db, user_id=user_id)
        current, course, constraints, statistics, confirmations, bindings = _current(
            db, user_id=user_id, row=row, athlete_today=today
        )
        _assert_match(expected_revision, current["composite_revision"])
        if current["state"] != "current" or None in (
            course,
            constraints,
            statistics,
            confirmations,
            bindings,
        ):
            raise _schema_mismatch("trail_plan")
        assert course is not None
        assert constraints is not None
        assert statistics is not None
        assert confirmations is not None
        assert bindings is not None
        target = next(
            item
            for item in bindings.section_confirmations
            if item.section_key == section_key
        )
        if section_revision != target.current_revision:
            raise TrailPlanServiceError(
                412,
                "TRAIL_SECTION_REVISION_CONFLICT",
                "The section changed before it was confirmed.",
                current_section_revision=target.current_revision,
            )
        assumption_updated = False
        if section_key == "section.optional-context":
            conditions = course.optional_context.environment.conditions_basis
            if (
                conditions.provenance == "explicit_assumption"
                and conditions.assumption_confirmed_revision
                != conditions.source_revision
            ):
                environment = replace(
                    course.optional_context.environment,
                    conditions_basis=replace(
                        conditions,
                        assumption_confirmed_revision=conditions.source_revision,
                    ),
                )
                course = replace(
                    course,
                    optional_context=replace(
                        course.optional_context,
                        environment=environment,
                    ),
                )
                assumption_updated = True
        if (
            not assumption_updated
            and target.confirmed_revision == target.current_revision
        ):
            db.rollback()
            return current
        provisional = _bindings(course, constraints, statistics, confirmations)
        next_target = next(
            item
            for item in provisional.section_confirmations
            if item.section_key == section_key
        )
        next_confirmations = dict(confirmations)
        next_confirmations[section_key] = next_target.current_revision
        next_bindings = _bindings(
            course,
            constraints,
            statistics,
            next_confirmations,
        )
        namespace = _serialize_stored(
            course,
            constraints,
            next_confirmations,
            next_bindings,
        )
        response = {
            "state": "current",
            "namespace_version": TRAIL_PLAN_NAMESPACE_VERSION,
            "course_demand": course.public_payload(),
            "constraints": constraints.public_payload(),
            "revision_bindings": _json_safe(asdict(next_bindings)),
            "composite_revision": next_bindings.composite_revision,
        }
        _commit_namespace(
            db,
            row=row,
            user_id=user_id,
            namespace=namespace,
        )
        return response
    except Exception:
        db.rollback()
        raise


def reset_trail_plan_draft(
    db: Session,
    *,
    user_id: str,
    expected_revision: str,
    athlete_today: date | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    today = _athlete_today(athlete_today)
    timestamp = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    try:
        row = _begin_write(db, user_id=user_id)
        current, *_ = _current(db, user_id=user_id, row=row, athlete_today=today)
        _assert_match(expected_revision, current["composite_revision"])
        event_id = _current_goal_event_id(user_id=user_id, goal=dict(row.goal or {}))
        course, constraints = _build_models(
            _reset_request(),
            event_id=event_id,
            now=timestamp,
            previous_course=None,
            previous_constraints=None,
            force_new=True,
        )
        statistics = _history_statistics(
            db,
            user_id=user_id,
            athlete_today=today,
            athlete_timezone=normalize_athlete_timezone(
                (row.source_options or {}).get("athlete_timezone")
            ),
        )
        confirmations = {key: None for key in TRAIL_EDITABLE_SECTION_KEYS}
        bindings = _bindings(course, constraints, statistics, confirmations)
        namespace = _serialize_stored(course, constraints, confirmations, bindings)
        response = {
            "state": "current",
            "namespace_version": TRAIL_PLAN_NAMESPACE_VERSION,
            "course_demand": course.public_payload(),
            "constraints": constraints.public_payload(),
            "revision_bindings": _json_safe(asdict(bindings)),
            "composite_revision": bindings.composite_revision,
            "reset_is_erasure": False,
        }
        _commit_namespace(db, row=row, user_id=user_id, namespace=namespace)
        return response
    except Exception:
        db.rollback()
        raise


def delete_trail_plan_draft(
    db: Session,
    *,
    user_id: str,
    expected_revision: str,
    athlete_today: date | None = None,
) -> dict[str, Any]:
    today = _athlete_today(athlete_today)
    try:
        row = _begin_write(db, user_id=user_id)
        current, *_ = _current(db, user_id=user_id, row=row, athlete_today=today)
        _assert_match(expected_revision, current["composite_revision"])
        if current["state"] == "absent":
            db.rollback()
            return {
                "status": "absent",
                "composite_revision": ABSENT_TRAIL_PLAN_REVISION,
            }
        _commit_namespace(db, row=row, user_id=user_id, namespace=None)
        return {
            "status": "deleted",
            "composite_revision": ABSENT_TRAIL_PLAN_REVISION,
        }
    except Exception:
        db.rollback()
        raise


def evaluate_trail_plan_readiness(
    db: Session,
    *,
    user_id: str,
    athlete_today: date | None = None,
) -> dict[str, Any]:
    """Evaluate the real inactive contract without writing or creating a plan."""
    today = _athlete_today(athlete_today)
    row = _row(db, user_id=user_id)
    current, course, constraints, statistics, _, bindings = _current(
        db,
        user_id=user_id,
        row=row,
        athlete_today=today,
    )
    if current["state"] != "current" or None in (
        course,
        constraints,
        statistics,
        bindings,
    ):
        if current["state"] == "unknown_schema":
            raise _schema_mismatch("trail_plan")
        raise TrailPlanServiceError(
            409,
            "TRAIL_DRAFT_REQUIRED",
            "Save a current Trail v2 draft before checking readiness.",
        )
    assert course is not None
    assert constraints is not None
    assert statistics is not None
    assert bindings is not None
    generation_input = NonUltraTrailGenerationInput(
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
        athlete_today=today,
        block_start=today,
        course_demand=course,
        history_statistics=statistics,
        constraints=constraints,
        revision_bindings=bindings,
        workload_request=None,
        synthetic_verification_only=False,
    )
    result = generate_non_ultra_trail_plan(generation_input)
    if result.plan is not None or result.inactive_dry_run:
        raise TrailPlanServiceError(
            500,
            "TRAIL_INACTIVE_INVARIANT_FAILED",
            "The inactive Trail policy attempted to return a proposal.",
        )
    return {
        "draft": current,
        "readiness": result.public_payload(),
    }
