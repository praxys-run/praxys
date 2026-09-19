"""Offline Trail v3 review contracts; no scheduler, runtime eligibility or adoption.

Compilation is the explicit filesystem boundary. Every validation function is
pure and uses an injected trusted calendar plus the compiled immutable contract.
Clinical candidate values come exclusively from the pinned SDR parameters.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Literal
import unicodedata

import yaml

from analysis.science_artifacts import load_policy_contract


ONTOLOGY_ID = "sdr-trail-running-goal-ontology-v3"
POLICY_ID = "sdr-non-ultra-trail-plan-generation-policy-v3"
# Content identity pins, not a second source of prescription parameters.
CONTRACT_PINS = MappingProxyType({
    ONTOLOGY_ID: (
        "trail-course-demand-v3",
        "sha256:ce47bdf570a307d91e76ad229d48f88871ea49dd7d01f97fdcfac90feb40e301",
        "sha256:e7cd3b9e3d6503ca72008818072bb830bb6fea18df64c69813329afba4471abd",
    ),
    POLICY_ID: (
        "non-ultra-trail-plan-generation-policy-v3",
        "sha256:38e62a7634c4a174ec7d1af50e20ee403b65f790da9f7da31cc0f48c6a222d06",
        "sha256:9a2c669727ed5f5338f6fe63c99aa786cfd5ef547a12726f6f4c9cf7da3667c1",
    ),
})
PARAMETER_NAMES = {
    ONTOLOGY_ID: frozenset({
        "v3_inherited_course_boundary", "v3_course_materiality",
        "v3_resource_context_schema", "v3_untrusted_input_boundary",
        "v3_history_provenance", "v3_candidate_wire_boundary",
        "v3_ontology_authority_deferrals",
    }),
    POLICY_ID: frozenset({
        "v3_review_scope", "v3_basic_history_and_running_envelope",
        "v3_joint_schedule_and_recovery", "v3_schedule_capacity_tradeoff",
        "v3_gym_templates", "v3_treadmill_template", "v3_outdoor_exposure_budget",
        "v3_blockers_and_module_limits", "v3_published_reference_context",
        "v3_deferred_policy_and_authority",
    }),
}
REASONS = frozenset({
    "contract_unavailable", "invalid_json", "input_limit", "duplicate_key",
    "invalid_number", "invalid_shape", "invalid_value", "invalid_date",
    "invalid_calendar", "duplicate_resource", "invalid_weekly_pattern",
    "invalid_overrides", "invalid_slice", "resource_not_confirmed",
    "gym_familiarity_unknown", "gym_equipment_unknown_or_missing",
    "treadmill_capability_unknown_or_incompatible", "template_mismatch",
    "activity_type_mismatch", "candidate_outside_proposal", "multiple_workouts_on_day",
    "new_gym_and_incline_in_same_block", "context_unavailable",
})
LIMITATIONS = (
    "offline_review_only", "runtime_inactive", "history_and_course_not_evaluated",
    "schedule_and_exposure_budgets_not_evaluated", "adoption_not_authorized",
)


class ReviewValidationError(ValueError):
    """Closed first-party reason only; never include untrusted values or paths."""

    def __init__(self, reason: str) -> None:
        if reason not in REASONS:
            raise ValueError("invalid_reason_catalog")
        self.reason = reason
        super().__init__(reason)


def _require(condition: bool, reason: str = "invalid_value") -> None:
    if not condition:
        raise ReviewValidationError(reason)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True)
class ReviewContract:
    ontology: Mapping[str, Any]
    policy: Mapping[str, Any]
    contract_digest: str
    ontology_contract_digest: str


def _raw_contract(path: Path) -> Any:
    """Reject ambiguous JSON before the shared loader can normalize its types."""
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        normalized_keys: set[str] = set()
        for key, value in items:
            normalized = unicodedata.normalize("NFC", key)
            _require(normalized not in normalized_keys, "contract_unavailable")
            normalized_keys.add(normalized)
            result[key] = value
        return result

    def floating(token: str) -> float:
        value = float(token)
        _require(math.isfinite(value), "contract_unavailable")
        _require(Decimal(token) == Decimal(str(value)), "contract_unavailable")
        return value

    def constant(_token: str) -> Any:
        raise ReviewValidationError("contract_unavailable")

    return json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
        parse_float=floating, parse_constant=constant,
    )


def _same_json_value(raw: Any, canonical: Any) -> bool:
    """Compare JSON trees without Python's bool/int/float equality coercions."""
    if type(raw) is not type(canonical):
        return False
    if type(raw) is dict:
        return raw.keys() == canonical.keys() and all(
            _same_json_value(value, canonical[key]) for key, value in raw.items()
        )
    if type(raw) is list:
        return len(raw) == len(canonical) and all(
            _same_json_value(value, expected)
            for value, expected in zip(raw, canonical, strict=True)
        )
    return raw == canonical


def compile_review_contract(*, science_dir: str | Path | None = None) -> ReviewContract:
    """Load canonical, fresh, exactly pinned draft/inactive contracts explicitly.

    Merely importing this module does not load v3 into any runtime registry.
    Accepted/active/superseded transitions require a new compiler review.
    """
    values: dict[str, Any] = {}
    try:
        root = Path(science_dir) if science_dir is not None else Path(__file__).resolve().parents[1] / "data/science"
        for decision_id, (model, source_digest, contract_digest) in CONTRACT_PINS.items():
            raw = _raw_contract(root / "generated/contracts" / f"{decision_id}.json")
            contract = load_policy_contract(
                decision_id, science_dir=science_dir, require_active=False,
            )
            _require(
                _same_json_value(raw, contract.model_dump(mode="json"))
                and contract.schema_version == 1
                and contract.decision_id == decision_id
                and contract.decision_version == 3
                and contract.model_version == model
                and contract.source_decision_digest == source_digest
                and contract.contract_digest == contract_digest
                and contract.decision_status.value == "draft"
                and contract.runtime_state.value == "inactive"
                and set(contract.parameters) == PARAMETER_NAMES[decision_id],
                "contract_unavailable",
            )
            values[decision_id] = _freeze(contract.parameter_values)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ArithmeticError, RecursionError, yaml.YAMLError):
        raise ReviewValidationError("contract_unavailable") from None
    return ReviewContract(
        ontology=values[ONTOLOGY_ID], policy=values[POLICY_ID],
        contract_digest=CONTRACT_PINS[POLICY_ID][2],
        ontology_contract_digest=CONTRACT_PINS[ONTOLOGY_ID][2],
    )


@dataclass(frozen=True)
class TrustedCalendar:
    """First-party date input, never read from a client context body or wall clock."""

    today: date
    event_date: date | None = None


@dataclass(frozen=True)
class ReviewReceipt:
    schema_version: str
    review_state: Literal["review_valid", "review_limited", "review_invalid", "review_unavailable"]
    reasons: tuple[str, ...]
    limitations: tuple[str, ...]
    decision_id: str
    contract_digest: str


def _receipt(contract: ReviewContract, reason: str | None = None) -> ReviewReceipt:
    return ReviewReceipt(
        schema_version=contract.ontology["v3_candidate_wire_boundary"]["receipt_schema"],
        review_state="review_invalid" if reason else "review_valid",
        reasons=(reason,) if reason else (), limitations=LIMITATIONS,
        decision_id=POLICY_ID, contract_digest=contract.contract_digest,
    )


@dataclass(frozen=True)
class TrainingContext:
    values: Mapping[str, Any]
    calendar: TrustedCalendar
    ontology_contract_digest: str


@dataclass(frozen=True)
class ContextReview:
    receipt: ReviewReceipt
    context: TrainingContext | None


def _object(value: Any, keys: Any) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == set(keys), "invalid_shape")
    return value


def _list(value: Any) -> list[Any]:
    _require(type(value) is list, "invalid_shape")
    return value


def _enum(value: Any, choices: Any) -> str:
    _require(type(value) is str and value in choices)
    return value


def _number(value: Any, *, integer: bool = False) -> int | Decimal:
    _require(type(value) is int or (not integer and type(value) is Decimal), "invalid_number")
    return value


def _date(value: Any) -> date:
    _require(type(value) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is not None, "invalid_date")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ReviewValidationError("invalid_date") from None


def _calendar(calendar: TrustedCalendar) -> None:
    _require(isinstance(calendar, TrustedCalendar) and type(calendar.today) is date, "invalid_calendar")
    _require(calendar.event_date is None or type(calendar.event_date) is date, "invalid_calendar")


def _parse(raw: str | bytes, contract: ReviewContract) -> Any:
    """Bound raw UTF-8 JSON before returning any normalized client values."""
    limits = contract.ontology["v3_untrusted_input_boundary"]

    def string(value: str) -> str:
        value = unicodedata.normalize("NFC", value)
        _require(len(value) <= limits["maximum_string_codepoints"], "input_limit")
        _require(not any(0xD800 <= ord(char) <= 0xDFFF for char in value), "invalid_value")
        return value

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        _require(len(items) <= limits["maximum_object_fields"], "input_limit")
        result = {}
        for key, value in items:
            key = string(key)
            _require(key not in result, "duplicate_key")
            result[key] = value
        return result

    def numeric(token: str) -> int | Decimal:
        _require(len(token) <= limits["maximum_numeric_token_ascii_characters"] and token.isascii(), "invalid_number")
        _require(re.fullmatch(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?", token) is not None, "invalid_number")
        if "." in token:
            _require(len(token.rsplit(".", 1)[1]) <= limits["decimal_maximum_fractional_digits"], "invalid_number")
            number = Decimal(token)
            _require(abs(number) <= limits["decimal_maximum_absolute_value"], "invalid_number")
            return number
        number = int(token)
        _require(limits["integer_minimum"] <= number <= limits["integer_maximum"], "invalid_number")
        return number

    def walk(value: Any, depth: int = 1) -> Any:
        _require(depth <= limits["maximum_nesting_depth"], "input_limit")
        if type(value) is str:
            return string(value)
        if type(value) is dict:
            return {key: walk(item, depth + 1) for key, item in value.items()}
        if type(value) is list:
            _require(len(value) <= limits["maximum_array_items"], "input_limit")
            return [walk(item, depth + 1) for item in value]
        return value

    try:
        _require(type(raw) in (str, bytes), "invalid_json")
        body = raw.encode("utf-8") if type(raw) is str else raw
        _require(len(body) <= limits["maximum_utf8_bytes"], "input_limit")
        body_text = body.decode("utf-8", errors="strict")
        return walk(json.loads(body_text, object_pairs_hook=pairs, parse_int=numeric,
                               parse_float=numeric, parse_constant=numeric))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ReviewValidationError("invalid_json") from None


def _envelope(value: Any, schema: Mapping[str, Any]) -> Any:
    _require(type(value) is dict, "invalid_shape")
    if value.get("state") == schema["unknown_state"]:
        _object(value, schema["unknown_envelope_exact_keys"])
        return None
    _object(value, schema["known_envelope_exact_keys"])
    _require(value["state"] == schema["known_state"])
    _require(value["value"] is not None)
    return value["value"]


def _availability(value: Any, schema: Mapping[str, Any]) -> None:
    state = _envelope(value, schema)
    if state is not None:
        _enum(state, schema["resource_states"])


def _validate_context(raw: str | bytes, calendar: TrustedCalendar, contract: ReviewContract) -> TrainingContext:
    _calendar(calendar)
    schema = contract.ontology["v3_resource_context_schema"]
    values = _object(_parse(raw, contract), schema["exact_keys"])
    _require(values["schema_version"] == schema["schema_version"])
    _enum(values["preset"], schema["preset_values"])
    resources = _list(values["resources"])
    _require(len(resources) <= schema["resource_rules_maximum"], "input_limit")
    seen = set()
    latest = calendar.today.toordinal() + schema["validity_end_maximum_days_after_server_today"]
    for rule in resources:
        _object(rule, schema["resource_rule_exact_keys"])
        kind = _enum(rule["kind"], schema["resource_catalog"])
        _require(kind not in seen, "duplicate_resource")
        seen.add(kind)
        start, end = _date(rule["effective_from"]), _date(rule["effective_until"])
        _require(calendar.today <= start <= end and end.toordinal() <= latest, "invalid_calendar")
        _require(calendar.event_date is None or end <= calendar.event_date, "invalid_calendar")
        weekly = _list(rule["weekly_pattern"])
        _require(len(weekly) == schema["weekly_exact_count"], "invalid_weekly_pattern")
        weekdays = []
        for item in weekly:
            _object(item, schema["weekly_item_exact_keys"])
            weekdays.append(_number(item["weekday"], integer=True))
            _availability(item["availability"], schema)
        _require(weekdays == list(schema["weekday_values"]), "invalid_weekly_pattern")
        overrides = _list(rule["date_overrides"])
        _require(len(overrides) <= schema["override_maximum_per_resource"], "invalid_overrides")
        dates = []
        for item in overrides:
            _object(item, schema["override_exact_keys"])
            day = _date(item["date"])
            _require(start <= day <= end, "invalid_overrides")
            dates.append(day)
            _availability(item["availability"], schema)
        _require(dates == sorted(set(dates)), "invalid_overrides")
    familiarity = _envelope(values["gym_familiarity"], schema)
    if familiarity is not None:
        _enum(familiarity, schema["gym_familiarity_values"])
    equipment = _envelope(values["equipment"], schema)
    if equipment is not None:
        _list(equipment)
        _require(len(equipment) <= schema["equipment_maximum_count"], "input_limit")
        for item in equipment:
            _enum(item, schema["equipment_catalog"])
        _require(equipment == sorted(set(equipment)))
    capability = _envelope(values["treadmill_incline_capability"], schema)
    if capability is not None:
        _object(capability, schema["treadmill_capability_exact_keys"])
        low, high = (_number(capability[key]) for key in ("minimum_pct", "maximum_pct"))
        _require(schema["treadmill_capability_structural_minimum_pct"] <= low <= high <= schema["treadmill_capability_structural_maximum_pct"])
    return TrainingContext(_freeze(values), calendar, contract.ontology_contract_digest)


def validate_training_context(raw: str | bytes, trusted_calendar: TrustedCalendar, *, contract: ReviewContract) -> ContextReview:
    """Validate a new/edit context; expired stored data must use future raw rights paths."""
    try:
        context = _validate_context(raw, trusted_calendar, contract)
        return ContextReview(_receipt(contract), context)
    except ReviewValidationError as error:
        return ContextReview(_receipt(contract, error.reason), None)


def _context(context: TrainingContext, contract: ReviewContract) -> None:
    _require(isinstance(context, TrainingContext) and context.ontology_contract_digest == contract.ontology_contract_digest, "context_unavailable")


def _resource_state(context: TrainingContext, kind: str, day: date) -> str:
    for rule in context.values["resources"]:
        if rule["kind"] != kind:
            continue
        if not _date(rule["effective_from"]) <= day <= _date(rule["effective_until"]):
            return "unknown"
        for override in rule["date_overrides"]:
            if _date(override["date"]) == day:
                return override["availability"].get("value", "unknown")
        return rule["weekly_pattern"][day.isoweekday() - 1]["availability"].get("value", "unknown")
    return "unknown"


def resolve_resource_availability(context: TrainingContext, kind: str, start: date, days: int, *, contract: ReviewContract, purpose: Literal["proposal", "review"] = "proposal") -> tuple[str, ...]:
    """Expand only the requested bounded slice; absent/outside/unknown stay unknown."""
    _context(context, contract)
    schema = contract.ontology["v3_resource_context_schema"]
    _enum(kind, schema["resource_catalog"])
    _enum(purpose, ("proposal", "review"))
    _require(type(start) is date and type(days) is int and 1 <= days <= schema[f"{purpose}_expansion_days"], "invalid_slice")
    _require(start.toordinal() + days - 1 <= date.max.toordinal(), "invalid_slice")
    return tuple(_resource_state(context, kind, start + timedelta(days=index)) for index in range(days))


def _known(context: TrainingContext, key: str) -> Any:
    return context.values[key].get("value")


def _workout(raw: Any, context: TrainingContext, contract: ReviewContract, proposal_start: date) -> dict[str, Any]:
    wire = contract.ontology["v3_candidate_wire_boundary"]
    policy = contract.policy
    workout = _object(raw, wire["workout_exact_keys"])
    _require(workout["schema_version"] == wire["workout_schema"])
    module = _enum(workout["module"], wire["module_values"])
    resource = _enum(workout["resource"], wire["resource_values_by_module"][module])
    _require(workout["goal_activity_type"] == wire["goal_activity_type"] and workout["actual_activity_type"] == wire["actual_activity_type_by_module"][module], "activity_type_mismatch")
    day = _date(workout["date"])
    _require(type(proposal_start) is date and proposal_start >= context.calendar.today and 0 <= (day - proposal_start).days < policy["v3_review_scope"]["proposal_days"], "candidate_outside_proposal")
    _require(context.calendar.event_date is None or day < context.calendar.event_date, "candidate_outside_proposal")
    _require(_resource_state(context, resource, day) == contract.ontology["v3_resource_context_schema"]["dependency_satisfying_state"], "resource_not_confirmed")
    _enum(workout["template_id"], policy["v3_review_scope"]["candidate_template_bindings"][module])
    duration = _number(workout["duration_min"], integer=True)
    steps, exercises = _list(workout["steps"]), _list(workout["exercise_blocks"])
    for step in steps:
        _object(step, wire["step_exact_keys"])
        _number(step["duration_min"], integer=True)
        _number(step["incline_pct"])
        _require(type(step["effort_label"]) is str)
    for block in exercises:
        _object(block, wire["exercise_block_exact_keys"])
        for key in ("sets", "repetitions", "rest_seconds"):
            _number(block[key], integer=True)
        _require(type(block["per_side"]) is bool)
    if module == "gym_strength":
        gym = policy["v3_gym_templates"]
        familiarity = _known(context, "gym_familiarity")
        _require(familiarity is not None, "gym_familiarity_unknown")
        equipment = _known(context, "equipment")
        _require(equipment is not None and set(gym["required_equipment"]) <= set(equipment), "gym_equipment_unknown_or_missing")
        _require(workout["template_id"] == gym["template_ids"][familiarity] and duration == gym["reserved_session_minutes"][familiarity] and not steps, "template_mismatch")
        _require(len(exercises) == len(gym["exercises"]), "template_mismatch")
        for block, expected in zip(exercises, gym["exercises"], strict=True):
            _require(all((
                block["exercise_id"] == expected["exercise_id"],
                block["per_side"] is expected["per_side"],
                block["sets"] == gym["sets_per_exercise"][familiarity],
                block["repetitions"] == gym["repetitions_per_set"],
                block["rest_seconds"] == gym["rest_between_sets_or_exercises_seconds"],
                block["selection_rule_id"] == gym["selection_rule_ids"][familiarity],
                type(block["load_choice"]) is str and block["load_choice"] in gym["allowed_load_choices"][familiarity],
            )), "template_mismatch")
    elif module == "treadmill_intro":
        treadmill = policy["v3_treadmill_template"]
        capability = _known(context, "treadmill_incline_capability")
        _require(capability is not None and capability["minimum_pct"] <= treadmill["prescribed_incline_minimum_pct"] and capability["maximum_pct"] >= treadmill["prescribed_incline_maximum_pct"], "treadmill_capability_unknown_or_incompatible")
        _require(duration == treadmill["total_minutes"] and not exercises and len(steps) == len(treadmill["steps"]), "template_mismatch")
        _require(all(step == dict(expected) for step, expected in zip(steps, treadmill["steps"], strict=True)), "template_mismatch")
    else:
        _require(duration >= policy["v3_basic_history_and_running_envelope"]["minimum_basic_running_session_minutes"] and not steps and not exercises, "template_mismatch")
        if resource == "treadmill":
            capability = _known(context, "treadmill_incline_capability")
            _require(capability is not None and capability["minimum_pct"] <= 0 <= capability["maximum_pct"], "treadmill_capability_unknown_or_incompatible")
    return workout


def validate_workout_candidate(raw: str | bytes, context: TrainingContext, *, contract: ReviewContract, proposal_start: date) -> ReviewReceipt:
    """Check one structured module/date; this cannot verify a plan or history cap."""
    try:
        _context(context, contract)
        _workout(_parse(raw, contract), context, contract, proposal_start)
        return _receipt(contract)
    except ReviewValidationError as error:
        return _receipt(contract, error.reason)


def validate_workout_candidates(raw: str | bytes, context: TrainingContext, *, contract: ReviewContract, proposal_start: date) -> ReviewReceipt:
    """Check a bounded collection and two local invariants, never full scheduling."""
    try:
        _context(context, contract)
        workouts = [_workout(item, context, contract, proposal_start) for item in _list(_parse(raw, contract))]
        dates = [item["date"] for item in workouts]
        _require(len(dates) == len(set(dates)), "multiple_workouts_on_day")
        modules = {item["module"] for item in workouts}
        _require(not (_known(context, "gym_familiarity") == "not_practiced" and {"gym_strength", "treadmill_intro"} <= modules), "new_gym_and_incline_in_same_block")
        return _receipt(contract)
    except ReviewValidationError as error:
        return _receipt(contract, error.reason)
