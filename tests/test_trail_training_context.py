"""Executable review boundaries, not live readiness/efficacy/authorization tests."""
from copy import deepcopy
from dataclasses import asdict
from datetime import date, timedelta
import json
from pathlib import Path
import shutil

import pytest
import yaml

from analysis.science_artifacts import (
    build_policy_contract, load_policy_contract, render_policy_contract_json,
)
from analysis.evidence_registry import load_science_registry
from analysis.trail_training_context import (
    CONTRACT_PINS, ONTOLOGY_ID, POLICY_ID, REASONS, ReviewValidationError,
    TrustedCalendar, compile_review_contract, resolve_resource_availability,
    validate_training_context, validate_workout_candidate, validate_workout_candidates,
)


TODAY = date(2026, 9, 8)
RACE = date(2026, 11, 15)
CALENDAR = TrustedCalendar(TODAY, RACE)
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def contract():
    return compile_review_contract()


def known(value):
    return {"state": "known", "value": value}


def rule(kind="flat_running", end=RACE, state="confirmed"):
    return {
        "kind": kind, "effective_from": TODAY.isoformat(),
        "effective_until": end.isoformat(),
        "weekly_pattern": [
            {"weekday": day, "availability": known(state)} for day in range(1, 8)
        ],
        "date_overrides": [],
    }


def context_raw():
    return {
        "schema_version": "trail_training_context_v1",
        "preset": "city_occasional_trail",
        "resources": [rule(kind) for kind in (
            "flat_running", "gym_strength", "treadmill", "controlled_downhill",
        )],
        "gym_familiarity": known("not_practiced"),
        "equipment": known(["bench", "bodyweight_space", "stable_support"]),
        "treadmill_incline_capability": known({"minimum_pct": 0, "maximum_pct": 15}),
    }


def review(raw, contract, calendar=CALENDAR):
    return validate_training_context(json.dumps(raw), calendar, contract=contract)


def validated(contract, raw=None):
    result = review(raw or context_raw(), contract)
    assert result.receipt.review_state == "review_valid"
    assert result.context is not None
    return result.context


def workout(module="basic_running", day=TODAY):
    template, resource, actual, duration = {
        "basic_running": ("trail-basic-easy-v1", "flat_running", "running", 20),
        "gym_strength": ("trail-gym-introduction-v1", "gym_strength", "strength", 25),
        "treadmill_intro": ("trail-treadmill-easy-incline-introduction-v1", "treadmill", "running", 20),
        "observed_outdoor_trail": ("trail-observed-outdoor-v1", "controlled_downhill", "trail_running", 20),
    }[module]
    result = {
        "schema_version": "trail_workout_candidate_v1", "date": day.isoformat(),
        "module": module, "resource": resource, "template_id": template,
        "goal_activity_type": "trail_running", "actual_activity_type": actual,
        "duration_min": duration, "steps": [], "exercise_blocks": [],
    }
    if module == "gym_strength":
        result["exercise_blocks"] = [
            {
                "exercise_id": name, "per_side": name == "supported_split_squat",
                "sets": 1, "repetitions": 8, "rest_seconds": 120,
                "load_choice": "bodyweight",
                "selection_rule_id": "controlled-form-at-least-four-repetitions-in-reserve-v1",
            } for name in ("squat_to_bench", "glute_bridge", "supported_split_squat", "standing_calf_raise")
        ]
    if module == "treadmill_intro":
        result["steps"] = [
            {"duration_min": minutes, "incline_pct": grade, "effort_label": "easy_conversational"}
            for minutes, grade in ((5, 0), (3, 2), (2, 0), (3, 2), (2, 0), (5, 0))
        ]
    return result


def check_workout(raw, contract, context=None):
    return validate_workout_candidate(json.dumps(raw), context or validated(contract), contract=contract, proposal_start=TODAY)


def test_contract_is_draft_pinned_and_immutable(contract):
    assert contract.contract_digest == CONTRACT_PINS[POLICY_ID][2]
    assert contract.ontology_contract_digest == CONTRACT_PINS[ONTOLOGY_ID][2]
    assert contract.policy["v3_review_scope"]["runtime_state"] == "inactive"
    with pytest.raises(TypeError):
        contract.policy["v3_gym_templates"]["repetitions_per_set"] = 999
    for decision_id in CONTRACT_PINS:
        with pytest.raises(ValueError, match="not accepted"):
            load_policy_contract(decision_id, require_active=True)


@pytest.mark.parametrize("preset", ["frequent_trail", "city_occasional_trail", "road_gym"])
def test_presets_do_not_imply_resource_or_ability(contract, preset):
    raw = context_raw()
    raw.update(preset=preset, resources=[])
    raw["gym_familiarity"] = {"state": "unknown"}
    result = review(raw, contract)
    assert result.receipt.review_state == "review_valid"
    assert result.context.values["gym_familiarity"] == {"state": "unknown"}
    assert resolve_resource_availability(result.context, "flat_running", TODAY, 14, contract=contract) == ("unknown",) * 14


def test_calendar_can_store_68_days_to_known_race_and_expand_bounded_slices(contract):
    context = validated(contract)
    assert (RACE - TODAY).days == 68
    assert context.values["resources"][0]["effective_until"] == RACE.isoformat()
    assert len(resolve_resource_availability(context, "flat_running", TODAY, 14, contract=contract)) == 14
    assert len(resolve_resource_availability(context, "flat_running", TODAY, 56, purpose="review", contract=contract)) == 56
    assert resolve_resource_availability(context, "flat_running", RACE + timedelta(days=1), 1, contract=contract) == ("unknown",)
    assert resolve_resource_availability(context, "flat_running", TODAY - timedelta(days=1), 1, contract=contract) == ("unknown",)


@pytest.mark.parametrize(("days", "purpose"), [(15, "proposal"), (57, "review"), (0, "review"), (True, "proposal")])
def test_expansion_rejects_unbounded_or_boolean_slices(contract, days, purpose):
    with pytest.raises(ReviewValidationError, match="invalid_slice"):
        resolve_resource_availability(validated(contract), "flat_running", TODAY, days, purpose=purpose, contract=contract)


@pytest.mark.parametrize(("offset", "valid"), [(365, True), (366, False)])
def test_calendar_horizon_is_inclusive_and_not_a_56_day_storage_limit(contract, offset, valid):
    raw = context_raw()
    raw["resources"] = [rule(end=TODAY + timedelta(days=offset))]
    result = review(raw, contract, TrustedCalendar(TODAY))
    assert (result.context is not None) is valid


@pytest.mark.parametrize(("start", "end"), [
    (TODAY - timedelta(days=1), RACE), (RACE, TODAY), (TODAY, RACE + timedelta(days=1)),
])
def test_calendar_rejects_past_reversed_and_after_event(contract, start, end):
    raw = context_raw()
    raw["resources"][0].update(effective_from=start.isoformat(), effective_until=end.isoformat())
    assert review(raw, contract).receipt.reasons == ("invalid_calendar",)


def test_unknown_override_fully_replaces_confirmed_weekly(contract):
    raw = context_raw()
    raw["resources"][0]["date_overrides"] = [{"date": TODAY.isoformat(), "availability": {"state": "unknown"}}]
    context = validated(contract, raw)
    assert resolve_resource_availability(context, "flat_running", TODAY, 2, contract=contract) == ("unknown", "confirmed")
    assert check_workout(workout(), contract, context).reasons == ("resource_not_confirmed",)


@pytest.mark.parametrize("state", ["tentative", "unavailable"])
def test_only_confirmed_satisfies_candidate_resources(contract, state):
    raw = context_raw()
    raw["resources"][0] = rule(state=state)
    assert check_workout(workout(), contract, validated(contract, raw)).reasons == ("resource_not_confirmed",)


@pytest.mark.parametrize(("count", "valid"), [(14, True), (15, False)])
def test_resource_override_count(contract, count, valid):
    raw = context_raw()
    raw["resources"][0]["date_overrides"] = [
        {"date": (TODAY + timedelta(days=index)).isoformat(), "availability": known("unavailable")}
        for index in range(count)
    ]
    assert (review(raw, contract).context is not None) is valid


@pytest.mark.parametrize("mutation", ["resource", "weekday", "weekday_zero", "overrides", "unsorted_weekly", "unsorted_overrides", "equipment"])
def test_duplicate_and_noncanonical_sets_rejected(contract, mutation):
    raw = context_raw()
    first = raw["resources"][0]
    if mutation == "resource":
        raw["resources"].append(deepcopy(first))
    elif mutation == "weekday":
        first["weekly_pattern"][1]["weekday"] = 1
    elif mutation == "weekday_zero":
        first["weekly_pattern"][0]["weekday"] = 0
    elif mutation == "unsorted_weekly":
        first["weekly_pattern"].reverse()
    elif mutation in ("overrides", "unsorted_overrides"):
        days = [TODAY, TODAY] if mutation == "overrides" else [TODAY + timedelta(days=1), TODAY]
        first["date_overrides"] = [{"date": day.isoformat(), "availability": known("confirmed")} for day in days]
    else:
        raw["equipment"]["value"].append("bench")
    assert review(raw, contract).context is None


@pytest.mark.parametrize("field", ["owner_id", "provenance", "history", "revision", "receipt", "policy_result", "kg", "one_rm", "provider_id", "calendar_id", "location"])
def test_forged_metadata_never_enters_context_or_error(contract, field):
    raw = context_raw()
    raw[field] = "private-client-marker"
    result = review(raw, contract)
    assert result.receipt.reasons == ("invalid_shape",)
    assert "private-client-marker" not in json.dumps(asdict(result.receipt))
    assert field not in asdict(result.receipt)


def test_unknown_is_distinct_from_numeric_zero_and_malformed_known(contract):
    raw = context_raw()
    raw["treadmill_incline_capability"] = {"state": "unknown"}
    assert validated(contract, raw).values["treadmill_incline_capability"] == {"state": "unknown"}
    raw["treadmill_incline_capability"] = known({"minimum_pct": 0, "maximum_pct": 0})
    assert validated(contract, raw).values["treadmill_incline_capability"]["value"]["maximum_pct"] == 0
    raw["treadmill_incline_capability"] = known(None)
    assert review(raw, contract).context is None
    raw["treadmill_incline_capability"] = {"state": "unknown", "value": 0}
    assert review(raw, contract).context is None


@pytest.mark.parametrize("token", ["1e1", "NaN", "Infinity", "-Infinity", "2147483648", "-2147483649", "1000000.01", "0.001", "12345678901234567"])
def test_raw_number_tokens_rejected_before_field_parsing(contract, token):
    raw = json.dumps(context_raw()).replace('"maximum_pct": 15', '"maximum_pct": ' + token)
    result = validate_training_context(raw, CALENDAR, contract=contract)
    assert result.receipt.reasons == ("invalid_number",)


@pytest.mark.parametrize("value", [True, "15", -31, 41])
def test_treadmill_capability_requires_strict_bounded_numbers(contract, value):
    raw = context_raw()
    raw["treadmill_incline_capability"]["value"]["maximum_pct"] = value
    assert review(raw, contract).context is None


def test_structural_incline_range_and_two_decimals_are_not_prescription(contract):
    raw = context_raw()
    raw["treadmill_incline_capability"] = known({"minimum_pct": -30, "maximum_pct": 40})
    assert review(raw, contract).context is not None
    raw["treadmill_incline_capability"] = known({"minimum_pct": -0.25, "maximum_pct": 2.25})
    assert review(raw, contract).context is not None
    raw["treadmill_incline_capability"] = known({"minimum_pct": 5, "maximum_pct": 2})
    assert review(raw, contract).context is None


@pytest.mark.parametrize("raw", [
    '{"preset": 1, "preset": 2}', '{"\u00e9": 1, "e\\u0301": 2}',
])
def test_duplicate_raw_keys_including_nfc_collisions(contract, raw):
    assert validate_training_context(raw, CALENDAR, contract=contract).receipt.reasons == ("duplicate_key",)


@pytest.mark.parametrize(("raw", "reason"), [
    (b'\xff', "invalid_json"), ('"\\ud800"', "invalid_value"),
    (" " * 32769, "input_limit"), (json.dumps("x" * 129), "input_limit"),
    (json.dumps([0] * 33), "input_limit"), (json.dumps({str(i): 0 for i in range(65)}), "input_limit"),
    ('[' * 9 + '0' + ']' * 9, "input_limit"),
])
def test_raw_abuse_boundaries_produce_closed_errors(contract, raw, reason):
    receipt = validate_training_context(raw, CALENDAR, contract=contract).receipt
    assert receipt.reasons == (reason,)
    assert set(receipt.reasons) <= REASONS


def test_utf8_size_applies_to_bytes_and_exact_limit_can_parse(contract):
    body = json.dumps(context_raw(), ensure_ascii=False)
    at_limit = body + " " * (32768 - len(body.encode()))
    assert validate_training_context(at_limit, CALENDAR, contract=contract).context is not None
    assert validate_training_context(at_limit + " ", CALENDAR, contract=contract).context is None


@pytest.mark.parametrize("module", ["basic_running", "gym_strength", "treadmill_intro", "observed_outdoor_trail"])
def test_exact_structured_workout_types_are_review_only(contract, module):
    receipt = check_workout(workout(module), contract)
    assert receipt.review_state == "review_valid"
    assert "history_and_course_not_evaluated" in receipt.limitations
    assert "adoption_not_authorized" in receipt.limitations
    assert set(asdict(receipt)) == {"schema_version", "review_state", "reasons", "limitations", "decision_id", "contract_digest"}


@pytest.mark.parametrize("familiarity", ["not_practiced", "practiced_before"])
def test_gym_templates_match_familiarity_without_assuming_observed_dose(contract, familiarity):
    raw = context_raw()
    raw["gym_familiarity"] = known(familiarity)
    candidate = workout("gym_strength")
    if familiarity == "practiced_before":
        candidate.update(template_id="trail-gym-bounded-familiar-v1", duration_min=35)
        for block in candidate["exercise_blocks"]:
            block.update(sets=2, load_choice="athlete_selected_resistance", selection_rule_id="controlled-form-at-least-three-repetitions-in-reserve-v1")
    assert check_workout(candidate, contract, validated(contract, raw)).review_state == "review_valid"


@pytest.mark.parametrize("field", ["sets", "repetitions", "rest_seconds", "per_side", "load_choice", "selection_rule_id", "exercise_id"])
def test_gym_template_drift_is_rejected(contract, field):
    candidate = workout("gym_strength")
    candidate["exercise_blocks"][0][field] = {
        "sets": 2, "repetitions": 9, "rest_seconds": 119, "per_side": True,
        "load_choice": "athlete_selected_resistance", "selection_rule_id": "custom",
        "exercise_id": "box_jump",
    }[field]
    assert check_workout(candidate, contract).reasons == ("template_mismatch",)


@pytest.mark.parametrize("field", ["gym_familiarity", "equipment"])
def test_unknown_gym_input_does_not_become_novice_or_inferred_equipment(contract, field):
    raw = context_raw()
    raw[field] = {"state": "unknown"}
    assert check_workout(workout("gym_strength"), contract, validated(contract, raw)).review_state == "review_invalid"


@pytest.mark.parametrize("mutation", ["duration", "incline", "effort", "steps", "total", "boolean_numeric", "actual_type", "extra"])
def test_treadmill_exact_steps_and_actual_activity_reject_drift(contract, mutation):
    candidate = workout("treadmill_intro")
    if mutation == "duration":
        candidate["steps"][0]["duration_min"] = 6
    elif mutation == "incline":
        candidate["steps"][1]["incline_pct"] = 1
    elif mutation == "effort":
        candidate["steps"][0]["effort_label"] = "hard"
    elif mutation == "steps":
        candidate["steps"].pop()
    elif mutation == "total":
        candidate["duration_min"] = 21
    elif mutation == "boolean_numeric":
        candidate["steps"][0]["incline_pct"] = False
    elif mutation == "actual_type":
        candidate["actual_activity_type"] = "trail_running"
    else:
        candidate["steps"][0]["speed_kph"] = 10
    assert check_workout(candidate, contract).review_state == "review_invalid"


@pytest.mark.parametrize("capability", [{"state": "unknown"}, known({"minimum_pct": 0, "maximum_pct": 1}), known({"minimum_pct": 1, "maximum_pct": 15})])
def test_positive_incline_requires_explicit_compatible_machine(contract, capability):
    raw = context_raw()
    raw["treadmill_incline_capability"] = capability
    assert check_workout(workout("treadmill_intro"), contract, validated(contract, raw)).reasons == ("treadmill_capability_unknown_or_incompatible",)


def test_level_treadmill_running_is_distinct_from_positive_incline_module(contract):
    raw = context_raw()
    raw["treadmill_incline_capability"] = known({"minimum_pct": 0, "maximum_pct": 0})
    candidate = workout()
    candidate["resource"] = "treadmill"
    assert check_workout(candidate, contract, validated(contract, raw)).review_state == "review_valid"
    assert check_workout(workout("treadmill_intro"), contract, validated(contract, raw)).review_state == "review_invalid"


@pytest.mark.parametrize(("offset", "valid"), [(13, True), (14, False), (-1, False)])
def test_workout_date_must_be_in_exact_14_day_proposal(contract, offset, valid):
    receipt = check_workout(workout(day=TODAY + timedelta(days=offset)), contract)
    assert (receipt.review_state == "review_valid") is valid


def test_collection_prevents_same_day_sessions_and_simultaneous_new_exposures(contract):
    context = validated(contract)
    same_day = [workout(), workout("gym_strength")]
    receipt = validate_workout_candidates(json.dumps(same_day), context, contract=contract, proposal_start=TODAY)
    assert receipt.reasons == ("multiple_workouts_on_day",)
    new_exposures = [workout("gym_strength"), workout("treadmill_intro", TODAY + timedelta(days=2))]
    receipt = validate_workout_candidates(json.dumps(new_exposures), context, contract=contract, proposal_start=TODAY)
    assert receipt.reasons == ("new_gym_and_incline_in_same_block",)
    simple = [workout(), workout("gym_strength", TODAY + timedelta(days=1))]
    receipt = validate_workout_candidates(json.dumps(simple), context, contract=contract, proposal_start=TODAY)
    assert receipt.review_state == "review_valid"
    assert "schedule_and_exposure_budgets_not_evaluated" in receipt.limitations


@pytest.mark.parametrize("mutation", ["stale_source", "malformed_source", "tampered_contract", "missing_parameter", "accepted", "active", "model", "schema", "source_digest"])
def test_compiler_rejects_stale_tampered_missing_or_unreviewed_contract(tmp_path, mutation):
    science = tmp_path / "science"
    shutil.copytree(ROOT / "data/science", science)
    path = science / "decisions" / f"{ONTOLOGY_ID}.yaml"
    source = yaml.safe_load(path.read_text())
    target = science / "generated/contracts" / f"{ONTOLOGY_ID}.json"
    if mutation == "malformed_source":
        path.write_text("schema_version: [ private-source-marker\n")
    elif mutation in ("stale_source", "missing_parameter", "accepted", "active", "model"):
        if mutation == "stale_source":
            source["title"] += " changed"
        elif mutation == "missing_parameter":
            source["model_parameters"].pop()
        elif mutation == "accepted":
            source["status"] = "accepted"
        elif mutation == "active":
            source["artifact_policy"]["runtime_state"] = "active"
        else:
            source["model_version"] = "unreviewed-model"
        path.write_text(yaml.safe_dump(source, sort_keys=False))
        if mutation == "model":
            registry = load_science_registry(science)
            target.write_text(render_policy_contract_json(build_policy_contract(registry, ONTOLOGY_ID)))
    else:
        raw = json.loads(target.read_text())
        key = {"tampered_contract": "contract_digest", "schema": "schema_version", "source_digest": "source_decision_digest"}[mutation]
        raw[key] = 2 if mutation == "schema" else "sha256:" + "0" * 64
        target.write_text(json.dumps(raw))
    with pytest.raises(ReviewValidationError, match="^contract_unavailable$"):
        compile_review_contract(science_dir=science)


@pytest.mark.parametrize("source_kind", ["yaml", "json"])
def test_compiler_closes_recursion_errors_without_source_values(tmp_path, source_kind):
    science = tmp_path / "science"
    shutil.copytree(ROOT / "data/science", science)
    if source_kind == "yaml":
        target = science / "decisions" / f"{ONTOLOGY_ID}.yaml"
        target.write_text("schema_version: 1\nprivate: " + "[" * 2000 + "0" + "]" * 2000)
    else:
        target = science / "generated/contracts" / f"{ONTOLOGY_ID}.json"
        target.write_text("[" * 16383 + "0" + "]" * 16383)
    with pytest.raises(ReviewValidationError, match="^contract_unavailable$"):
        compile_review_contract(science_dir=science)


@pytest.mark.parametrize("decision_id", [ONTOLOGY_ID, POLICY_ID])
@pytest.mark.parametrize(("field", "value"), [
    ("schema_version", True), ("schema_version", 1.0),
    ("decision_version", "3"), ("decision_version", 3.0),
])
def test_compiler_rejects_raw_types_that_shared_loader_normalizes(tmp_path, decision_id, field, value):
    science = tmp_path / "science"
    shutil.copytree(ROOT / "data/science", science)
    target = science / "generated/contracts" / f"{decision_id}.json"
    raw = json.loads(target.read_text())
    raw[field] = value
    target.write_text(json.dumps(raw))
    # Reproduce the normalization seam without changing the shared v2 loader.
    assert load_policy_contract(decision_id, science_dir=science).contract_digest == CONTRACT_PINS[decision_id][2]
    with pytest.raises(ReviewValidationError, match="^contract_unavailable$"):
        compile_review_contract(science_dir=science)


@pytest.mark.parametrize("replacement", [
    '"schema_version": 1, "schema_version": 1',
    '"schema_version": 1, "\u00e9": 0, "e\\u0301": 0',
    '"schema_version": NaN', '"schema_version": Infinity',
    '"schema_version": 1e999', '"schema_version": 1e-99999999999999999999',
])
def test_compiler_rejects_ambiguous_or_nonfinite_raw_json(tmp_path, replacement):
    science = tmp_path / "science"
    shutil.copytree(ROOT / "data/science", science)
    target = science / "generated/contracts" / f"{ONTOLOGY_ID}.json"
    original = target.read_text()
    assert '"schema_version": 1' in original
    target.write_text(original.replace('"schema_version": 1', replacement, 1))
    with pytest.raises(ReviewValidationError, match="^contract_unavailable$"):
        compile_review_contract(science_dir=science)


def test_compiler_accepts_unchanged_generated_raw_contracts(tmp_path):
    science = tmp_path / "science"
    shutil.copytree(ROOT / "data/science", science)
    result = compile_review_contract(science_dir=science)
    assert result.ontology_contract_digest == CONTRACT_PINS[ONTOLOGY_ID][2]
    assert result.contract_digest == CONTRACT_PINS[POLICY_ID][2]


def test_compiler_rejects_float_rounding_that_would_hide_changed_parameter(tmp_path):
    science = tmp_path / "science"
    shutil.copytree(ROOT / "data/science", science)
    target = science / "generated/contracts" / f"{POLICY_ID}.json"
    original = target.read_text()
    assert '"minimum_low_intensity_running_fraction": 0.75' in original
    target.write_text(original.replace(
        '"minimum_low_intensity_running_fraction": 0.75',
        '"minimum_low_intensity_running_fraction": 0.75000000000000000001',
        1,
    ))
    assert load_policy_contract(POLICY_ID, science_dir=science).contract_digest == CONTRACT_PINS[POLICY_ID][2]
    with pytest.raises(ReviewValidationError, match="^contract_unavailable$"):
        compile_review_contract(science_dir=science)


def test_v3_has_no_runtime_importers_or_provider_access():
    import ast

    module = ROOT / "analysis/trail_training_context.py"
    tree = ast.parse(module.read_text())
    imports = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(name.startswith(("api", "db", "sync", "statsig", "analysis.non_ultra_trail")) for name in imports)
    for directory in ("api", "db", "sync", "web/src", "miniapp"):
        for file in (ROOT / directory).rglob("*"):
            if file.suffix in {".py", ".ts", ".tsx"}:
                assert "analysis.trail_training_context" not in file.read_text()
