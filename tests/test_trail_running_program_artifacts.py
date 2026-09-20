"""Regression boundaries for the inactive Trail programme review artifacts.

These exercise the existing compiler and loader, not a runtime planner or an
independent scientific assessment of the proposed guardrails.
"""

from pathlib import Path
import shutil

import pytest
import yaml
from pydantic import ValidationError

from analysis.evidence_registry import (
    ScienceDecisionRecord,
    ScienceRegistry,
    load_science_registry,
)
from analysis.science_artifacts import (
    SciencePolicyContract,
    build_policy_contract,
    evidence_review_digest,
    expected_science_artifacts,
    load_policy_contract,
    render_policy_contract_json,
    science_decision_digest,
    sync_science_artifacts,
)


SCIENCE_DIR = Path(__file__).resolve().parents[1] / "data" / "science"
DECISION_ID = "sdr-trail-running-program-policy-v1"
EVIDENCE_ID = "evidence-trail-running-program-v1"


@pytest.fixture(scope="module")
def registry() -> ScienceRegistry:
    return load_science_registry()


@pytest.fixture(scope="module")
def contract(registry: ScienceRegistry) -> SciencePolicyContract:
    return build_policy_contract(registry, DECISION_ID)


@pytest.fixture
def isolated_science(tmp_path: Path) -> Path:
    """Use only the new records; predecessor approval must not be necessary."""
    root = tmp_path / "science"
    (root / "decisions").mkdir(parents=True)
    shutil.copyfile(
        SCIENCE_DIR / "decisions" / f"{DECISION_ID}.yaml",
        root / "decisions" / f"{DECISION_ID}.yaml",
    )
    shutil.copytree(
        SCIENCE_DIR / "evidence" / "trail-running-program",
        root / "evidence" / "trail-running-program",
    )
    sync_science_artifacts(load_science_registry(root), check=False)
    return root


def test_exact_contract_is_fully_reviewable_and_inactive(
    registry: ScienceRegistry, contract: SciencePolicyContract,
) -> None:
    artifacts = expected_science_artifacts(registry)
    packet = artifacts[
        Path("generated/review-packets") / f"{DECISION_ID}.md"
    ]
    evidence_packet = artifacts[
        Path("generated/review-packets") / f"{EVIDENCE_ID}.md"
    ]
    assert str(contract.decision_status) == "draft"
    assert str(contract.runtime_state) == "inactive"
    assert contract.source_decision_digest == science_decision_digest(
        registry.decisions[DECISION_ID]
    )
    assert contract.linked_evidence_digests == {
        EVIDENCE_ID: evidence_review_digest(registry.evidence_reviews[EVIDENCE_ID])
    }
    assert contract.linked_evidence_digests[EVIDENCE_ID] in evidence_packet
    assert contract.source_decision_digest in packet
    assert contract.contract_digest in packet
    assert "```json\n" + render_policy_contract_json(contract).rstrip() + "\n```" in packet
    assert packet.index("## Decision sheet") < packet.index("## Audit appendix")
    assert "**Decision approval:** _Pending_" in packet
    assert "**Implementation approval:** _Pending_" in packet
    assert registry.decisions[DECISION_ID].supersedes == []


def test_loader_rejects_draft_activation_and_payload_tampering(
    isolated_science: Path,
) -> None:
    contract = load_policy_contract(DECISION_ID, science_dir=isolated_science)
    with pytest.raises(ValueError, match="not accepted"):
        load_policy_contract(
            DECISION_ID, science_dir=isolated_science, require_active=True,
        )
    payload = contract.model_dump(mode="json")
    payload["runtime_state"] = "active"
    with pytest.raises(ValidationError, match="contract_digest does not match"):
        SciencePolicyContract.model_validate(payload)


@pytest.mark.parametrize("changed_subject", ["decision", "evidence"])
def test_loader_rejects_stale_source_bindings(
    isolated_science: Path, changed_subject: str,
) -> None:
    if changed_subject == "decision":
        path = isolated_science / "decisions" / f"{DECISION_ID}.yaml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        group = next(
            item for item in payload["model_parameters"]
            if item["name"] == "joint_schedule"
        )
        group["value"]["maximum_sessions_per_day"] = 3
    else:
        path = (
            isolated_science / "evidence" / "trail-running-program"
            / f"{EVIDENCE_ID}.yaml"
        )
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["title"] += " — revised applicability review"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="Generated science contract .* is stale"):
        load_policy_contract(DECISION_ID, science_dir=isolated_science)
    assert sync_science_artifacts(load_science_registry(isolated_science), check=True)


def test_review_cannot_hide_a_parameter_or_approve_deferrals(
    registry: ScienceRegistry,
) -> None:
    decision = registry.decisions[DECISION_ID]
    assert decision.decision_review is not None
    assert {
        name for item in decision.decision_review.items
        for name in item.parameter_names
    } == {parameter.name for parameter in decision.model_parameters}
    payload = decision.model_dump(mode="json")
    payload["decision_review"]["items"][0]["parameter_names"] = []
    with pytest.raises(ValidationError):
        ScienceDecisionRecord.model_validate(payload)

    payload = decision.model_dump(mode="json")
    for item in payload["decision_review"]["items"]:
        if "unresolved_modules_and_activation" in item["parameter_names"]:
            item["disposition"] = "approve"
    with pytest.raises(ValidationError, match="does not explicitly defer"):
        ScienceDecisionRecord.model_validate(payload)


def test_scope_and_provenance_do_not_authorize_complete_race_preparation(
    contract: SciencePolicyContract,
) -> None:
    values = contract.parameter_values
    assert {
        name for name, parameter in contract.parameters.items()
        if str(parameter.classification) == "published"
    } == {"published_reference_context"}
    assert len(contract.parameters) == 16
    scope = values["scope_and_authority"]
    assert scope["distance_meters"]["inclusive_maximum"] == 50000
    assert scope["distance_meters"]["exact_50000_supported_as_goal"] is True
    assert scope["distance_meters"]["distance_alone_is_admission"] is False
    assert scope["event_date_required_for_daily"] is False
    assert scope["gym_required"] is False
    assert scope["runtime_eligibility_from_candidate_state"] is False
    history = values["history_admission"]
    assert history["device_disconnection_means_zero"] is False
    assert history["client_can_assert_observed"] is False
    assert history["observed_general"]["unknown_week_counts_as_zero"] is False
    assert history["reported_bridge"]["athlete_reported_is_not_observed"] is True
    assert history["reported_bridge"]["successful_bridge_proves_race_readiness"] is False
    deferred = values["unresolved_modules_and_activation"]
    for key in (
        "first_50km_admission_for_complete_race_plan",
        "new_long_run_duration_distance_or_back_to_back_dose",
        "first_50km_vertical_and_descent_progression",
        "initial_outdoor_descent_without_comparable_exposure",
        "negative_incline_treadmill_prescription",
        "technical_terrain_skill_progression",
        "performance_quality_session_progression_and_race_pace",
        "full_event_day_nutrition_fluid_electrolyte_schedule",
        "heat_altitude_or_extreme_environment_specific_prescription",
        "runtime_activation", "production_schema_allocation",
        "provider_access_delivery_or_deployment",
    ):
        assert deferred[key] == "not_accepted"


def test_reviewed_running_example_preserves_two_budgets_and_original_lineage(
    contract: SciencePolicyContract,
) -> None:
    running = contract.parameter_values["basic_running"]
    example = running["budget_example"]
    transition = example["adopt_one_basic_running_transition"]
    increment = transition["P_after_minutes"] - example["P_before_minutes"]
    assert increment == 5
    assert sum(transition["session_total_minutes"]) == transition["total_minutes"]
    assert sum(transition["session_running_minutes"]) == transition["actual_running_minutes"]
    assert transition["total_ceiling_minutes"] == example["original_T0_minutes"] + increment
    assert transition["actual_running_ceiling_minutes"] == (
        example["original_R0_minutes"] + increment
    )
    assert transition["total_minutes"] > example["original_T0_minutes"]
    assert all(
        total - actual == example["walking_minutes_per_session"]
        for total, actual in zip(
            transition["session_total_minutes"],
            transition["session_running_minutes"], strict=True,
        )
    )
    state = running["original_reference_and_progression_state"]
    assert state["positive_offset_maximum_in_any_rolling_14_days"] == 10
    assert state["positive_offset_lifetime_maximum_minutes"] == 20
    assert state["new_14_day_block_or_7_day_review_resets_P"] is False
    assert state[
        "reconfirmation_history_refresh_restart_goal_edit_"
        "or_successor_proposal_resets_references_or_P"
    ] is False
    assert {"R0", "T0", "original_program_lineage"}.issubset(state["immutable_fields"])


def test_acquired_strength_cannot_reset_template_or_bypass_frequency_review(
    contract: SciencePolicyContract,
) -> None:
    strength = contract.parameter_values["strength_and_control"]
    selection = strength["admission_template_selection"]
    assert selection["completed_intro_sessions_select_familiar_template"] is False
    assert selection["athlete_familiarity_label_alone_selects_familiar"] is False
    assert selection[
        "new_proposal_restart_reconfirmation_or_history_refresh_reselects_template"
    ] is False
    assert strength["intro"]["sessions_in_each_of_first_two_seven_day_periods"] == 1
    review = contract.parameter_values["progression_and_review"]
    frequency = review["options"]["strength_frequency"]
    assert frequency["earliest_review_days_after_original_admission"] == 14
    assert frequency["dose_variant_running_incline_or_fuel_progression_at_same_review"] is False
    transition = review["authoritative_transition_rule"]
    assert transition["maximum_upward_transitions_in_any_rolling_seven_days"] == 1
    assert "frequency" in transition["includes"]
    assert transition["no_template_reset_bypass"] is True
    assert transition["repeat_proposal_or_retry_applies_transition_again"] is False
    assert transition["frequency_change_counts_as_weekly_volume_change"] is True


def test_indoor_step_totals_and_dual_session_spacing_remain_separate(
    contract: SciencePolicyContract,
) -> None:
    indoor = contract.parameter_values["uphill_indoor_modules"]
    treadmill = indoor["treadmill_intro"]
    warmup, repetitions, cooldown = treadmill["steps"]
    assert warmup["minutes"] + cooldown["minutes"] + repetitions["repeat"] * sum(
        step["minutes"] for step in repetitions["steps"]
    ) == treadmill["session_total_minutes"] == 20
    assert repetitions["repeat"] * sum(
        step["minutes"] for step in repetitions["steps"] if step["incline_pct"] > 0
    ) == treadmill["inclined_minutes"]
    stairs = indoor["stair_ascent_intro"]
    flat_seconds = 60 * (
        stairs["warmup_flat_walk_minutes"] + stairs["cooldown_flat_walk_minutes"]
    )
    repetition_seconds = stairs["repetitions"] * (
        stairs["ascent_seconds_per_repetition"]
        + stairs["flat_recovery_seconds_per_repetition"]
    )
    assert flat_seconds + repetition_seconds == 60 * stairs["session_total_minutes"]
    assert indoor["outdoor_ascent_descent_credit"] == 0
    joint = contract.parameter_values["joint_schedule"]
    assert joint["maximum_sessions_per_day"] == 2
    assert joint["independent_completion_and_feedback"] is True
    assert joint["minimum_end_to_start_gap_hours"] == 4
    assert joint["gap_is_not_exercise_minutes"] is True
    assert joint["mechanical_budgets_are_not_convertible"] is True
    assert joint["double_counting_multi_purpose_session"] is False
    assert {rule["minimum_hours"] for rule in joint["spacing_rules"]} == {48, 72}
    assert joint["spacing_semantics"]["interval"] == (
        "later_session_start_UTC_minus_earlier_session_end_UTC"
    )
    assert joint["spacing_semantics"]["direction"] == (
        "symmetric_for_every_listed_pair; apply_in_either_order"
    )
