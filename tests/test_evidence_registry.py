"""Tests for the versioned science evidence and decision registry."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

import analysis.metrics as metrics
from analysis.evidence_registry import (
    CitationSource,
    EffectEstimate,
    EvidenceReview,
    ParameterProvenance,
    RecordStatus,
    _validate_supersession,
    load_science_registry,
    render_registry_index,
)
from analysis.metrics import compute_heat_adaptation
from analysis.science import load_theory


def _assert_exact_verification_notes(review: EvidenceReview) -> None:
    """Require one recognized verification level for every cited source."""
    allowed_levels = {"full-text", "abstract", "metadata", "inaccessible"}
    notes = [
        note
        for note in review.review_notes
        if note.startswith("Verification:")
    ]

    assert len(notes) == len(review.citations)
    for citation in review.citations:
        marker = f"Verification: {citation.id} - "
        matches = [note for note in notes if note.startswith(marker)]
        assert len(matches) == 1
        level = matches[0].split(";", 1)[0].removeprefix(marker).strip()
        assert level in allowed_levels


def test_shipped_registry_is_valid_and_heat_migration_is_complete() -> None:
    registry = load_science_registry()

    assert set(registry.evidence_reviews) == {
        "evidence-adaptive-training-load-v1",
        "evidence-environmental-performance-v1",
        "evidence-environmental-response-workload-support-v1",
        "evidence-heat-adaptation-v1",
        "evidence-heat-decay-v1",
        "evidence-individual-goal-feasibility-v1",
        "evidence-plan-outcome-interpretation-v1",
        "evidence-personal-environment-response-v1",
        "evidence-preplan-baseline-policy-v1",
        "evidence-outdoor-5k-plan-generation-policy-v1",
        "evidence-plan-generation-eligibility-safety-v1",
        "evidence-road-10k-plan-generation-policy-v1",
        "evidence-running-field-tests-v1",
        "evidence-short-interruption-detraining-v1",
    }
    assert set(registry.decisions) == {
        "sdr-adaptive-plan-feasibility-and-adjustment-v1",
        "sdr-environmental-performance-v1",
        "sdr-environmental-performance-v2",
        "sdr-environmental-performance-v3",
        "sdr-environmental-performance-v4",
        "sdr-heat-adaptation-v1",
        "sdr-outdoor-5k-plan-generation-policy-v1",
        "sdr-plan-generation-eligibility-safety-v1",
        "sdr-preplan-baseline-policy-v1",
        "sdr-road-10k-plan-generation-policy-v1",
    }
    assert registry.evidence_reviews[
        "evidence-personal-environment-response-v1"
    ].status == "accepted"
    assert registry.decisions["sdr-environmental-performance-v2"].status == (
        "superseded"
    )
    assert registry.decisions["sdr-environmental-performance-v3"].status == (
        "superseded"
    )
    workload_review = registry.evidence_reviews[
        "evidence-environmental-response-workload-support-v1"
    ]
    assert workload_review.status == "accepted"
    assert workload_review.human_reviewers == ["github:dddtc2005"]
    assert workload_review.reviewed_on == date(2026, 8, 10)
    workload_decision = registry.decisions["sdr-environmental-performance-v4"]
    assert workload_decision.status == "accepted"
    assert workload_decision.human_reviewers == ["github:dddtc2005"]
    assert registry.decisions[
        "sdr-adaptive-plan-feasibility-and-adjustment-v1"
    ].status == "draft"
    assert registry.evidence_reviews[
        "evidence-preplan-baseline-policy-v1"
    ].status == "accepted"
    assert registry.decisions["sdr-preplan-baseline-policy-v1"].status == (
        "accepted"
    )
    baseline_review = registry.evidence_reviews[
        "evidence-preplan-baseline-policy-v1"
    ]
    baseline_decision = registry.decisions[
        "sdr-preplan-baseline-policy-v1"
    ]
    assert baseline_review.human_reviewers == ["github:dddtc2005"]
    assert baseline_review.reviewed_on == date(2026, 8, 10)
    assert baseline_decision.human_reviewers == ["github:dddtc2005"]
    assert baseline_decision.decision_date == date(2026, 8, 10)
    baseline_parameters = {
        parameter.name: parameter
        for parameter in baseline_decision.model_parameters
    }
    baseline_claims = {claim.id: claim for claim in baseline_review.claims}
    assert baseline_parameters["personal_success_probability"].value == (
        "disabled"
    )
    assert baseline_parameters["initial_scope"].value["age"] == "18_plus"
    assert (
        "baseline.current-capability-not-change-comparability"
        in baseline_claims
    )
    hierarchy = baseline_parameters["baseline_evidence_hierarchy"].value
    assert hierarchy["direct_current_capability"] == [
        "verified_measured_5_km_race",
        "explicitly_confirmed_intentional_all_out_5_km_effort_with_sufficient_distance_timing_and_provenance",
    ]
    assert hierarchy["direct_longitudinal_change"] == [
        "same_protocol_5_km_observations_with_comparable_route_environment_recovery_timing_and_assistance"
    ]
    assert (
        "arbitrary_5_km_segment_or_best_split_inside_another_workout"
        in hierarchy["insufficient"]
    )
    history_qualification = baseline_parameters[
        "history_first_qualification"
    ].value
    assert history_qualification["order"][0] == (
        "search_existing_athlete_history_before_any_test_offer"
    )
    assert history_qualification["candidate_unit"] == (
        "complete_activity_or_verified_race_result"
    )
    assert history_qualification["athlete_confirmation"] == {
        "required_for_nonrace_all_out_effort": True,
        "must_be_explicit": True,
        "infer_from_pace_power_or_ranking": "prohibited",
        "absent_or_ambiguous_response": "insufficient_evidence",
    }
    assert history_qualification["segment_and_sample_use"][
        "arbitrary_5_km_segment_or_best_split_as_baseline"
    ] == "prohibited"
    assert history_qualification["segment_and_sample_use"][
        "create_or_infer_performance_intent"
    ] == "prohibited"
    assert history_qualification["power_source"]["prohibited"] == [
        "activity_avg_power"
    ]
    assert history_qualification["power_source"]["allowed"] == [
        "activity_splits",
        "activity_samples",
    ]
    pilot_offer = baseline_parameters["pilot_offer_policy"].value
    assert pilot_offer["offer_only_when_current_capability_status"] == [
        "missing",
        "stale",
        "incomparable",
    ]
    assert pilot_offer["participation"] == "explicit_opt_in"
    assert pilot_offer["account_access"] == "never_blocked"
    freshness = baseline_parameters["freshness_age_calculation"].value
    assert freshness["current_through_day"] == 42
    assert freshness["stale_from_day"] == 43
    assert freshness["stale_retention"] == "preserve_as_supporting_history"
    comparability = baseline_parameters[
        "longitudinal_change_comparability"
    ].value
    assert comparability["directly_comparable"] == (
        "same_protocol_and_comparable_route_environment_recovery_timing_and_assistance"
    )
    assert comparability["supporting"] == (
        "qualified_5_km_results_with_incomplete_change_comparability_but_no_known_material_mismatch"
    )
    assert comparability["incomparable"] == (
        "protocol_or_material_conditions_prevent_before_after_interpretation"
    )
    assert baseline_parameters["safety_stop_path"].value[
        "feasibility_assessment"
    ] == "insufficient_evidence"
    intensity_sources = baseline_parameters["intensity_evidence_source"].value
    assert intensity_sources["allowed"] == [
        "activity_splits",
        "activity_samples",
    ]
    assert intensity_sources["prohibited"] == ["activity_avg_power"]
    assert set(intensity_sources["allowed"]).isdisjoint(
        intensity_sources["prohibited"]
    )
    assert all(
        parameter.classification.value in {
            "published",
            "estimate",
            "guardrail",
        }
        for parameter in baseline_parameters.values()
    )

    five_km_review = registry.evidence_reviews[
        "evidence-outdoor-5k-plan-generation-policy-v1"
    ]
    five_km_decision = registry.decisions[
        "sdr-outdoor-5k-plan-generation-policy-v1"
    ]
    assert five_km_review.status == "accepted"
    assert five_km_review.human_reviewers == ["github:dddtc2005"]
    assert five_km_review.reviewed_on == date(2026, 8, 13)
    assert five_km_review.supersedes == []
    assert five_km_review.superseded_by is None
    assert five_km_review.method.review_type.value == "rigorous"
    assert len(five_km_review.citations) >= 9
    assert {
        "outdoor-5k-plan.structured-periodization-bounded-benefit",
        "outdoor-5k-plan.mostly-low-intensity-no-universal-winner",
        "outdoor-5k-plan.one-to-two-quality-sessions-indirect",
        "outdoor-5k-plan.taper-volume-reduction-supported",
        "outdoor-5k-plan.fixed-progression-not-safety-threshold",
        "outdoor-5k-plan.individual-outcomes-require-error-aware-validation",
    } <= {claim.id for claim in five_km_review.claims}
    assert {
        "Verification: boullosa-2020 - full-text",
        "Verification: wang-2023 - full-text",
        "Verification: bonafiglia-2021 - full-text",
    } <= {
        note.split(";", 1)[0] for note in five_km_review.review_notes
    }
    assert five_km_decision.status == "accepted"
    assert five_km_decision.human_reviewers == ["github:dddtc2005"]
    assert five_km_decision.decision_date == date(2026, 8, 13)
    assert five_km_decision.supersedes == []
    assert five_km_decision.superseded_by is None
    assert five_km_decision.evidence_review_ids == [
        "evidence-preplan-baseline-policy-v1",
        five_km_review.id,
    ]
    assert {
        claim.id for claim in five_km_review.claims
    } <= set(five_km_decision.evidence_claim_ids)
    five_km_parameters = {
        parameter.name: parameter
        for parameter in five_km_decision.model_parameters
    }
    assert five_km_parameters["activation_and_authority"].value[
        "active_behavior"
    ] is True
    assert five_km_parameters["plan_horizon_and_reassessment"].value[
        "block_days"
    ] == 28
    assert five_km_parameters["recent_history_prerequisite"].value[
        "minimum_usable_completed_weeks"
    ] == 3
    assert five_km_parameters["goal_target_and_feasibility_handling"].value[
        "target_time_can_increase_frequency_minutes_or_intensity"
    ] is False
    assert five_km_parameters["planned_intensity_distribution"].value[
        "minimum_low_intensity_running_minutes_fraction"
    ] == 0.70
    assert five_km_parameters["quality_day_spacing"].value[
        "maximum_quality_days_per_7_days"
    ] == 2
    assert five_km_parameters["weekly_running_minutes"].value[
        "fixed_10_percent_rule_allowed"
    ] is False
    assert five_km_parameters["power_and_zone_targets"].value[
        "generic_threshold_percentage_range_allowed"
    ] is False
    assert five_km_parameters[
        "deterministic_generation_and_optional_ai"
    ].value["complete_non_ai_path_required"] is True
    assert five_km_parameters["planned_intensity_distribution"].value[
        "prohibited_historical_intensity_source"
    ] == ["activity_avg_power"]
    assert any(
        "authorizes bounded implementation work" in note
        for note in five_km_decision.decision_notes
    )
    assert {
        parameter.classification.value
        for parameter in five_km_parameters.values()
    } <= {"published", "estimate", "guardrail"}

    decision = registry.decisions["sdr-heat-adaptation-v1"]
    assert decision.status == "accepted"
    assert decision.model_version == "heat-adaptation-v8"
    assert decision.model_version == metrics._HEAT_MODEL_VERSION
    assert set(decision.evidence_review_ids) == {
        "evidence-environmental-performance-v1",
        "evidence-heat-adaptation-v1",
        "evidence-heat-decay-v1",
    }
    assert decision.human_reviewers == ["github:dddtc2005"]


def test_plan_generation_eligibility_policy_is_accepted_but_inactive_and_cross_cutting() -> None:
    registry = load_science_registry()
    review = registry.evidence_reviews[
        "evidence-plan-generation-eligibility-safety-v1"
    ]
    decision = registry.decisions[
        "sdr-plan-generation-eligibility-safety-v1"
    ]

    assert review.status == "accepted"
    assert review.human_reviewers == ["github:dddtc2005"]
    assert review.reviewed_on == date(2026, 8, 14)
    assert review.method.review_type.value == "rigorous"
    assert len(review.citations) >= 17
    assert {
        "eligibility.novice-recreational-different-evidence-family",
        "eligibility.recent-history-anchor-without-universal-threshold",
        "eligibility.goal-relevant-current-capability-task-specific",
        "eligibility.masters-age-change-not-automatic-exclusion",
        "eligibility.current-symptoms-support-stop-not-clearance",
        "eligibility.evidence-quality-no-personal-probability",
    } <= {claim.id for claim in review.claims}
    assert {
        "Verification: videbaek-2015 - full-text",
        "Verification: correia-2024 - full-text",
        "Verification: boullosa-2020 - full-text",
    } <= {note.split(";", 1)[0] for note in review.review_notes}
    _assert_exact_verification_notes(review)

    assert decision.status == "accepted"
    assert decision.human_reviewers == ["github:dddtc2005"]
    assert decision.evidence_review_ids == [review.id]
    assert {claim.id for claim in review.claims} == set(
        decision.evidence_claim_ids
    )
    parameters = {
        parameter.name: parameter
        for parameter in decision.model_parameters
    }
    assert parameters["activation_and_authority"].value[
        "active_behavior"
    ] is False
    assert parameters["activation_and_authority"].value[
        "goal_capture_is_independent_from_plan_availability"
    ] is True
    goal_routing = parameters["goal_intent_and_policy_separation"].value
    assert goal_routing[
        "goal_may_be_recorded_without_matching_plan_policy"
    ] is True
    assert set(goal_routing["intent_states"]) == {
        "completion",
        "performance",
        "continuous_development",
        "unknown",
    }
    assert goal_routing["unavailable_policy_result"] == (
        "goal_recorded_plan_policy_unavailable"
    )
    alignment = parameters["existing_policy_alignment_gate"].value
    assert alignment[
        "accepted_records_requiring_successor_alignment_before_activation"
    ] == [
        "sdr-preplan-baseline-policy-v1",
        "sdr-outdoor-5k-plan-generation-policy-v1",
    ]
    assert alignment["draft_records_requiring_alignment_before_activation"] == [
        "sdr-adaptive-plan-feasibility-and-adjustment-v1",
    ]
    assert alignment[
        "accepted_records_remain_unchanged_in_this_decision"
    ] is True
    assert alignment[
        "shared_router_activation_before_successor_acceptance"
    ] is False
    assert parameters["capability_and_history_routing"].value[
        "first_distance_completion"
    ] == "separate_accepted_completion_policy_required"
    assert parameters["capability_and_history_routing"].value[
        "goal_distance_novel_performance"
    ] == "conservative_separate_policy_route_pending_validation"
    assert parameters["capability_and_history_routing"].value[
        "masters_or_older_adult"
    ] == "modifier_not_exclusion"
    assert parameters["capability_and_history_routing"].value[
        "static_identity_labels_used_for_routing"
    ] is False
    assert parameters["history_depth_states"].value[
        "cross_cutting_minimum_weeks"
    ] == "none_defined"
    assert parameters["history_depth_states"].value["states"] == [
        "no_usable_history",
        "sparse_history",
        "history_rich",
        "unknown",
    ]
    assert parameters["history_depth_states"].value[
        "first_attempt_or_goal_distance_novel_is_history_state"
    ] is False
    patterns = parameters["dynamic_training_context_patterns"].value
    assert patterns["pattern_is_person_identity"] is False
    assert patterns["time_bounded"] is True
    assert patterns["same_athlete_may_change_patterns"] is True
    assert patterns["correction_changes_provenance_not_observed_history"] is True
    assert "race_dense" in patterns["pattern_axes"]["event_context"]
    event_context = parameters["event_context_and_calendar"].value
    assert event_context["no_calendar_records_means_no_events"] is False
    assert event_context[
        "provider_import_requires_athlete_confirmation"
    ] is True
    assert event_context["no_event_completion_route"] == (
        "separately_accepted_controlled_goal_activity"
    )
    assert event_context["no_event_performance_route"] == (
        "separately_accepted_opt_in_benchmark"
    )
    assert event_context[
        "race_or_maximal_effort_counts_as_training_load"
    ] is True
    assert event_context[
        "race_or_maximal_effort_counts_as_quality_session"
    ] is True
    outcomes = parameters["eligibility_outcomes"].value
    assert outcomes["goal_recorded_plan_policy_unavailable"] == (
        "valid_goal_without_matching_accepted_policy"
    )
    assert outcomes["unresolved_event_context"] == (
        "material_race_or_maximal_effort_context_unknown"
    )
    assert parameters["cross_cutting_schedule_values"].value[
        "accepted_5_km_values_are_defaults"
    ] is False
    assert parameters["progression_and_workload_rules"].value[
        "fixed_10_percent_rule_allowed"
    ] is False
    assert parameters["progression_and_workload_rules"].value[
        "acwr_prescription_zones_allowed"
    ] is False
    assert parameters["historical_intensity_evidence_source"].value[
        "prohibited"
    ] == ["activity_avg_power"]
    profile = parameters["profile_fields_and_missingness"].value
    assert profile[
        "provider_technical_access_is_blanket_product_consent"
    ] is False
    assert profile["exact_birth_date_storage_required"] is False
    assert profile["optional_physiological_sex"][
        "unknown_may_default_to_male"
    ] is False
    assert profile["missing_field_policy"]["age_modifier"] == (
        "continue_without_age_adjustment"
    )
    assert profile["missing_field_policy"]["physiological_sex_modifier"] == (
        "disable_dependent_metric_or_use_separately_accepted_neutral_method"
    )
    assert profile["missing_field_policy"][
        "unrelated_optional_profile_field"
    ] == "does_not_block_plan"
    assert parameters["validation_order"].value[0] == (
        "goal_recorded_and_normalized"
    )
    assert "material_event_context_and_schedule_conflicts" in parameters[
        "validation_order"
    ].value
    replay_fields = set(parameters["replay_and_audit_record"].value["persist"])
    assert {
        "goal_record_state",
        "dynamic_pattern_snapshot",
        "event_context_state",
        "profile_field_provenance",
        "missing_field_effects",
    } <= replay_fields
    assert parameters["personal_success_probability"].value == "disabled"
    assert parameters["deterministic_matching_and_optional_ai"].value[
        "complete_non_ai_path_required"
    ] is True
    assert {
        "broaden_population",
        "assign_static_runner_identity",
        "invent_history_or_personal_context",
        "invent_or_confirm_event_context",
        "confirm_or_overwrite_provider_profile",
        "diagnose_or_clear",
    } <= set(
        parameters["deterministic_matching_and_optional_ai"].value[
            "ai_prohibited"
        ]
    )
    assert parameters["context_provenance_and_privacy"].value[
        "missed_training_reason_inference"
    ] == "prohibited"
    assert parameters["context_provenance_and_privacy"].value[
        "imported_event_or_profile_candidate_is_confirmed"
    ] is False
    assert parameters["athlete_reported_safety_stop"].value[
        "diagnosis_treatment_or_clearance"
    ] == "prohibited"
    assert parameters["athlete_reported_safety_stop"].value[
        "absent_report_means_risk_free"
    ] is False
    assert "chest_pain_or_pressure" in parameters[
        "athlete_reported_safety_stop"
    ].value["stop_reasons"]
    assert any(
        "Human acceptance for issue #685" in note
        for note in decision.decision_notes
    )


def test_road_10k_policy_is_accepted_distance_specific_and_inactive() -> None:
    registry = load_science_registry()
    review = registry.evidence_reviews[
        "evidence-road-10k-plan-generation-policy-v1"
    ]
    decision = registry.decisions[
        "sdr-road-10k-plan-generation-policy-v1"
    ]

    assert review.status == "accepted"
    assert review.human_reviewers == ["github:dddtc2005"]
    assert review.reviewed_on == date(2026, 8, 14)
    assert review.method.review_type.value == "rigorous"
    assert len(review.citations) >= 19
    assert {
        "road-10k-plan.task-specific-capability-not-single-marker",
        "road-10k-plan.mostly-low-intensity-no-universal-winner",
        "road-10k-plan.one-to-two-quality-sessions-indirect",
        "road-10k-plan.volume-frequency-associated-not-prescriptive",
        "road-10k-plan.fixed-progression-not-safety-law",
        "road-10k-plan.taper-volume-reduction-supported",
        "road-10k-baseline.same-distance-direct-capability",
        "road-10k-baseline.comparability-time-of-day-matters",
        "road-10k-baseline.freshness-cutoff-not-validated",
        "road-10k-plan.individual-outcomes-require-error-aware-validation",
        "road-10k-plan.symptom-based-test-stop-boundary",
    } <= {claim.id for claim in review.claims}
    assert {
        "Verification: boullosa-2020 - full-text",
        "Verification: wang-2023 - full-text",
        "Verification: bonafiglia-2021 - full-text",
    } <= {note.split(";", 1)[0] for note in review.review_notes}
    _assert_exact_verification_notes(review)

    assert decision.status == "accepted"
    assert decision.human_reviewers == ["github:dddtc2005"]
    assert decision.evidence_review_ids == [
        "evidence-plan-generation-eligibility-safety-v1",
        review.id,
    ]
    assert {claim.id for claim in review.claims} <= set(
        decision.evidence_claim_ids
    )
    parameters = {
        parameter.name: parameter
        for parameter in decision.model_parameters
    }
    activation = parameters["road_10k_activation_and_dependency"].value
    assert activation["active_behavior"] is False
    assert activation["shared_policy_dependency"] == {
        "sdr_id": "sdr-plan-generation-eligibility-safety-v1",
        "required_status_before_activation": "accepted",
    }
    assert activation["distance_policy_required_status_before_activation"] == (
        "accepted"
    )
    assert activation["human_science_acceptance_recorded"] is True
    assert activation[
        "implementation_review_required_before_activation"
    ] is True
    assert activation["capability_registry_entry_default_enabled"] is False
    assert activation[
        "generator_api_web_and_miniapp_activation_in_this_record"
    ] is False
    assert parameters["road_10k_goal_tuple"].value["goal_kind"] == (
        "distance_10k"
    )
    assert parameters["road_10k_goal_tuple"].value["goal_intent"] == (
        "performance"
    )
    assert parameters["road_10k_goal_tuple"].value["distance_m"] == 10000
    assert parameters["road_10k_goal_tuple"].value["surface"] == (
        "outdoor_road"
    )
    assert parameters["road_10k_goal_tuple"].value[
        "target_time_optional"
    ] is True
    assert parameters["road_10k_goal_tuple"].value[
        "no_event_performance_goal_supported"
    ] is True
    pattern = parameters["road_10k_supported_training_pattern"].value
    assert pattern["adult_scope"] == "confirmed"
    assert pattern["capability_pattern"] == "currently_capable"
    assert pattern["history_pattern"] == "stable"
    assert pattern["load_pattern"] == "within_recent"
    assert pattern["event_context"] == [
        "confirmed_none",
        "single_target",
        "race_dense",
    ]
    assert pattern["race_dense_requires_resolved_conflicts"] is True
    assert pattern["evidence_directness"] == ["direct", "supporting"]
    assert pattern[
        "recreational_serious_professional_or_elite_identity_used"
    ] is False
    assert parameters["road_10k_direct_baseline_hierarchy"].value[
        "excluded_as_direct_baseline"
    ][0] == "five_k_result_or_conversion"
    baseline = parameters["road_10k_direct_baseline_hierarchy"].value
    assert baseline["accepted_evidence_order"] == [
        "organized_outdoor_road_10k_race_with_elapsed_time",
        "explicit_all_out_standardized_outdoor_road_or_track_10k_time_trial",
    ]
    assert "standardized_laboratory_10k_time_trial" in baseline[
        "supporting_only"
    ]
    assert parameters["road_10k_baseline_freshness"].value[
        "current_through_completed_days"
    ] == 56
    history = parameters["road_10k_recent_history_prerequisite"].value
    assert history["completed_weeks_lookback"] == 8
    assert history["minimum_usable_completed_weeks"] == 4
    assert history["minimum_runs_per_usable_week"] == 3
    assert history["latest_run_within_completed_days"] == 10
    assert history["intensity_usable_when_any"] == [
        "activity_splits_available",
        "activity_samples_available",
    ]
    assert history["disallowed_intensity_source"] == [
        "activity_avg_power"
    ]
    rolling = parameters[
        "road_10k_rolling_planning_and_reassessment"
    ].value
    assert rolling["fixed_full_block_days"] == "none_defined"
    assert rolling["fixed_horizon_eligibility_gate"] is False
    assert rolling["exact_committed_execution_window_days"] == (
        "not_accepted"
    )
    assert {
        "new_or_changed_confirmed_event",
        "material_training_pattern_change",
        "athlete_requested_review",
    } <= set(rolling["reassessment_triggers"])
    target_routing = parameters["road_10k_target_date_routing"].value
    assert target_routing["no_target_date"] == (
        "rolling_performance_plan_with_optional_opt_in_benchmark"
    )
    assert target_routing["target_within_8_to_14_completed_days"] == (
        "taper_or_maintain_only_if_all_other_inputs_pass"
    )
    assert target_routing["short_horizon_invalidates_goal"] is False
    event_context = parameters[
        "road_10k_event_and_benchmark_context"
    ].value
    assert event_context["imported_event_must_be_athlete_confirmed"] is True
    assert event_context["every_race_or_maximal_effort"] == {
        "counts_as_quality_session": True,
        "counts_as_training_load": True,
        "requires_recovery_and_spacing_validation": True,
    }
    assert event_context["no_event_performance_goal"][
        "optional_benchmark"
    ]["never_auto_schedule"] is True
    assert event_context["no_event_completion_goal"] == (
        "route_to_separate_completion_policy"
    )
    assert parameters["road_10k_running_frequency"].value[
        "minimum_running_days_per_7_day_unit"
    ] == 3
    assert parameters["road_10k_running_frequency"].value[
        "maximum_running_days_per_7_day_unit"
    ] == 6
    assert parameters["road_10k_running_frequency"].value[
        "higher_requested_frequency_outcome"
    ] == "cap_to_policy_history_and_availability"
    session_mix = parameters["road_10k_session_taxonomy_and_mix"].value
    assert session_mix["exact_step_templates"][
        "inherited_from_outdoor_5k"
    ] is False
    assert parameters["road_10k_quality_spacing"].value[
        "maximum_quality_sessions_per_7_day_unit"
    ] == 2
    assert parameters["road_10k_quality_spacing"].value[
        "consecutive_quality_running_days_allowed"
    ] is False
    assert parameters["road_10k_low_intensity_floor"].value[
        "minimum_planned_low_intensity_fraction"
    ] == 0.75
    assert parameters["road_10k_history_anchored_load"].value[
        "planned_progression_above_recent_typical_in_v1"
    ] is False
    assert parameters["road_10k_history_anchored_load"].value[
        "every_non_taper_weekly_minutes_must_not_exceed"
    ] == [
        "recent_median_usable_weekly_running_minutes",
        "athlete_stated_weekly_time_limit",
    ]
    assert parameters["road_10k_longest_easy_boundary"].value[
        "mandatory_long_run"
    ] is False
    assert parameters["road_10k_power_and_intensity_targets"].value[
        "generic_percent_of_threshold_or_cp_targets"
    ] is False
    assert parameters["road_10k_selected_taper_guardrail"].value[
        "planned_volume_reduction_percent"
    ] == 50
    taper = parameters["road_10k_selected_taper_guardrail"].value
    assert taper["rounding_note"] == (
        "rounded_product_guardrail_from_50_5_percent_range_midpoint"
    )
    assert taper["reference_minutes_for_window"] == (
        "reference_daily_running_minutes_times_actual_taper_window_days"
    )
    assert taper[
        "target_event_elapsed_time_included_in_planned_training_minutes"
    ] is False
    comparability = parameters["road_10k_protocol_comparability"].value
    assert comparability["missing_metadata_outcome"] == (
        "outcome_comparison_unavailable"
    )
    assert comparability["plan_generation_eligibility_affected"] is False
    assert parameters["road_10k_goal_and_probability_limits"].value[
        "personal_goal_achievement_probability"
    ] == "disabled"
    typed_outcomes = parameters["road_10k_typed_outcomes"].value
    assert typed_outcomes["unsupported_distance_fallback"] == "none"
    assert {
        name
        for name, outcome in typed_outcomes["outcomes"].items()
        if outcome["plan_returned"] is False
    } == {
        "intent_requires_separate_policy",
        "training_pattern_outside_current_policy",
        "adult_scope_unconfirmed",
        "safety_stop",
        "insufficient_direct_baseline",
        "stale_direct_baseline",
        "insufficient_recent_history",
        "insufficient_history_rich_frequency",
        "unresolved_event_context",
        "limited_guidance_event_conflict",
        "contradictory_input",
        "unsupported_capability",
    }
    assert typed_outcomes["outcomes"]["eligible_rolling_proposal"][
        "plan_returned"
    ] is True
    assert typed_outcomes["outcomes"]["eligible_taper_or_event_adjustment"][
        "plan_returned"
    ] is True
    assert all(
        outcome.get("goal_remains_recorded") is True
        for outcome in typed_outcomes["outcomes"].values()
        if outcome["plan_returned"] is False
    )
    assert typed_outcomes["outcomes"]["limited_guidance_event_conflict"][
        "limited_guidance_returned"
    ] is True
    assert parameters["road_10k_suggestion_only_state_transition"].value[
        "generator_may_not"
    ] == [
        "write_adopted_plan_without_consent",
        "deliver_or_publish_without_consent",
        "overwrite_adopted_future_days_at_reassessment",
        "schedule_a_missed_workout_makeup",
        "infer_why_a_workout_was_missed",
        "auto_schedule_a_benchmark_or_change_event_priority",
    ]
    assert set(
        parameters["road_10k_suggestion_only_state_transition"].value[
            "AI_may_not"
        ]
    ) == {
        "widen_eligibility",
        "assign_recreational_serious_professional_or_elite_identity",
        "invent_missing_context",
        "invent_or_confirm_event_context",
        "confirm_or_overwrite_profile_fields",
        "reinterpret_unknown_as_safe_or_eligible",
        "override_deterministic_validation",
        "adopt_deliver_or_publish",
    }
    thresholds = parameters[
        "road_10k_pilot_falsification_thresholds"
    ].value
    assert thresholds["deterministic_invariant_breach_tolerance"] == 0
    assert thresholds["dry_run"][
        "maximum_single_guardrail_exclusion_fraction"
    ] == 0.50
    assert thresholds["opt_in_pilot"]["maximum_major_edit_fraction"] == 0.30
    assert thresholds["opt_in_pilot"]["major_edit_definition"][
        "evaluation_window"
    ] == "one_versioned_committed_execution_window"
    assert thresholds["opt_in_pilot"][
        "maximum_taper_vs_non_taper_rejection_or_major_edit_gap"
    ] == 0.15
    assert thresholds["opt_in_pilot"][
        "serious_adverse_events_triggering_immediate_pause"
    ] == 1
    assert parameters["road_10k_published_taper_findings"].classification.value == (
        "published"
    )
    assert any(
        "Human acceptance for issue #686" in note
        for note in decision.decision_notes
    )


def test_environmental_performance_decision_preserves_product_boundaries() -> None:
    registry = load_science_registry()
    decision = registry.decisions["sdr-environmental-performance-v1"]
    review = registry.evidence_reviews["evidence-environmental-performance-v1"]

    assert decision.status == "superseded"
    assert decision.model_version == "environmental-performance-context-v1"
    assert decision.superseded_by == "sdr-environmental-performance-v2"
    assert decision.evidence_review_ids == [review.id]
    assert decision.model_parameters == []
    assert {
        "environment.marathon-wbgt-performance-level",
        "environment.humidity-fixed-temperature-capacity",
        "environment.solar-radiation-first-order",
        "environment.wet-bulb-not-safety-boundary",
        "environment.morphology-not-sex-coefficient",
    } <= set(decision.evidence_claim_ids)

    limits = " ".join(decision.user_facing_claim_limits)
    privacy = " ".join(decision.privacy_implications)
    assert "Never call psychrometric wet bulb WBGT" in limits
    assert "counterfactual finish time" in limits
    assert "Do not infer core temperature" in limits
    assert "never send or store a route trace" in privacy
    assert "Do not infer home or training locations" in privacy


def test_environment_response_decision_preserves_lifecycle_and_limits() -> None:
    registry = load_science_registry()
    original = registry.decisions["sdr-environmental-performance-v1"]
    predecessor = registry.decisions["sdr-environmental-performance-v2"]
    partial_display = registry.decisions["sdr-environmental-performance-v3"]
    accepted = registry.decisions["sdr-environmental-performance-v4"]
    review = registry.evidence_reviews[
        "evidence-personal-environment-response-v1"
    ]

    assert original.status == "superseded"
    assert original.superseded_by == predecessor.id
    assert predecessor.status == "superseded"
    assert predecessor.superseded_by == partial_display.id
    assert partial_display.status == "superseded"
    assert partial_display.superseded_by == accepted.id
    assert accepted.status == "accepted"
    assert accepted.supersedes == [partial_display.id]
    assert accepted.human_reviewers == ["github:dddtc2005"]
    assert review.status == "accepted"
    assert review.human_reviewers == ["github:dddtc2005"]
    assert review.supersedes == []

    interpretation = predecessor.accepted_interpretation
    limits = " ".join(predecessor.user_facing_claim_limits)
    privacy = " ".join(predecessor.privacy_implications)
    assert "historical association; not predictively validated" in (
        interpretation
    )
    assert "not a causal effect" in interpretation
    assert "every user an explicit opt-in" in interpretation
    assert "Never call psychrometric wet bulb WBGT" in limits
    assert "Do not call the cross-activity curve heart-rate drift" in limits
    assert "unavailable or unevaluable" in limits
    assert "Cross-user contribution is excluded" in privacy
    assert "Do not persist activity IDs" in privacy
    assert "external weather or route enrichment is prohibited" in privacy
    assert "encrypted temporary storage" in privacy
    assert "14-day PostgreSQL retention window" in privacy
    assert "Queue payloads contain only owner ID" in privacy
    assert "Caches must not retain raw exports" in privacy
    assert "running work must re-check active consent" in privacy

    parameters = {
        parameter.name: parameter for parameter in predecessor.model_parameters
    }
    assert parameters["primary_model"].value == {
        "method": "ridge",
        "alpha": 4.0,
        "outcome": "steady_segment_mean_hr_bpm",
        "required_predictors": [
            "wet_bulb_c",
            "mean_pct_cp",
            "start_offset_min",
            "duration_min",
        ],
        "optional_complete_case_predictors": [
            "terrain_gain_m_per_km",
            "pre_activity_tsb",
            "recovery_readiness_score",
        ],
        "weighting": "equal_activity_weight_within_partition",
        "predictor_standardization": "training_rows_only",
        "intercept_penalized": False,
    }
    assert parameters["predictive_unavailable_behavior"].value == (
        "withhold_curve"
    )
    assert parameters["enrollment_scope"].value == (
        "all_users_explicit_opt_in"
    )
    assert parameters["power_source"].value == [
        "stryd_continuous_samples",
    ]
    assert parameters["candidate_power_regimes"].value == [
        "garmin_native_wrist_only_continuous_samples",
    ]
    assert parameters["garmin_power_provenance"].value == (
        "required_before_provider_qualification"
    )
    assert parameters["power_regime_isolation"].value == (
        "provider_device_and_algorithm_era"
    )
    assert parameters["pace_workload_fallback"].value == "prohibited_in_v1"
    assert parameters["multiple_power_regime_behavior"].value == (
        "separate_results_no_outcome_based_selection"
    )
    assert parameters["adult_eligibility"].value == (
        "explicit_18_plus_attestation_required"
    )
    assert parameters["availability_reason_shape"].value == [
        "code",
        "category",
        "public_message_key",
        "observed_aggregate",
        "required_guardrail",
        "user_actionable",
        "suggested_action_key",
        "analysis_stage",
        "power_regime",
        "model_version",
        "correlation_id",
    ]
    assert "unverified_garmin_wrist_power" in parameters[
        "availability_reason_codes"
    ].value
    assert "prediction_unavailable" in parameters[
        "availability_reason_codes"
    ].value
    assert {
        "missing_continuous_sample_power",
        "missing_continuous_heart_rate",
        "missing_temperature",
        "missing_relative_humidity",
        "missing_provider_aligned_critical_power",
        "adult_eligibility_not_confirmed",
    } <= set(parameters["availability_reason_codes"].value)
    assert parameters["processing_failure_behavior"].value == (
        "explicit_error_with_correlation_id"
    )
    assert parameters["labs_backup_maximum_retention_days"].value == 14
    assert parameters["curve_environment_domain_percentiles"].value == [
        10,
        90,
    ]
    assert parameters["curve_support_bin_count"].value == 5
    assert parameters["minimum_activities_per_curve_bin"].value == 5
    assert parameters["minimum_segments_per_curve_bin"].value == 10
    assert parameters["curve_reference_power_pct_cp"].value == [75.0, 85.0]
    assert parameters[
        "minimum_reference_power_activities_per_curve_bin"
    ].value == 5
    assert parameters["bootstrap_interval_must_exclude_zero"].value is True
    assert parameters[
        "maximum_bootstrap_interval_width_to_absolute_estimate_ratio"
    ].value == 1.0
    assert parameters[
        "leave_one_activity_out_minimum_sign_agreement"
    ].value == 0.8
    assert parameters[
        "leave_one_activity_out_maximum_relative_coefficient_change"
    ].value == 0.5
    assert parameters["planned_sensitivity_variants"].value == [
        "wider_power_band_60_to_100_pct_cp",
        "narrower_power_band_70_to_90_pct_cp",
        "warmup_exclusion_300_sec",
        "warmup_exclusion_900_sec",
        "minimum_segment_duration_120_sec",
        "minimum_segment_duration_300_sec",
        "temperature_only",
        "critical_power_minus_5_pct",
        "critical_power_plus_5_pct",
    ]
    assert parameters["minimum_available_sensitivity_variants"].value == 8
    assert all(
        parameter.classification.value == "guardrail"
        for parameter in accepted.model_parameters
        if isinstance(parameter.value, (int, float))
        and not isinstance(parameter.value, bool)
    )


def test_environmental_sources_record_verified_identifiers_and_review_depth() -> None:
    review = load_science_registry().evidence_reviews[
        "evidence-environmental-performance-v1"
    ]
    sources = {source.id: source for source in review.citations}

    expected = {
        "ely-2007": ("10.1249/mss.0b013e31802d3aba", "17473775"),
        "maughan-otani-watson-2012": (
            "10.1007/s00421-011-2206-7",
            "22012542",
        ),
        "otani-2016": ("10.1007/s00421-016-3335-9", "26842928"),
        "vecellio-2022": (
            "10.1152/japplphysiol.00738.2021",
            "34913738",
        ),
        "notley-2017": ("10.1113/EP086112", "28231604"),
    }
    assert {
        source_id: (sources[source_id].doi, sources[source_id].pmid)
        for source_id in expected
    } == expected

    notes = " ".join(review.review_notes)
    limitations = " ".join(review.method.method_limitations)
    assert "PubMed abstracts" in notes
    assert "PubMed Central full text" in notes
    assert "only the Vecellio 2022 claim received a full-text check" in limitations


def test_heat_retention_copy_rejects_a_fixed_plateau() -> None:
    root = Path(__file__).resolve().parents[1]
    source_paths = [
        root / "web" / "src" / "components" / "HeatAdaptationPanel.tsx",
        root / "miniapp" / "utils" / "heat-adaptation.ts",
        root / "data" / "science" / "heat" / "praxys_heat_evidence.yaml",
        root / "data" / "science" / "zh" / "heat" / "praxys_heat_evidence.yaml",
    ]
    copy = "\n".join(path.read_text(encoding="utf-8") for path in source_paths)

    assert "likely still retained" not in copy
    assert "operational retention window" not in copy
    assert "initial retention window" not in copy
    assert "response-specific" in copy
    assert "may already be declining" in copy


def test_heat_theory_links_to_accepted_decision_and_shared_citations() -> None:
    registry = load_science_registry()
    decision = registry.decisions["sdr-heat-adaptation-v1"]
    en = load_theory("heat", "praxys_heat_evidence")
    zh = load_theory("heat", "praxys_heat_evidence", locale="zh")

    assert en.science_decision_id == decision.id
    assert en.model_version == decision.model_version
    assert en.evidence_review_ids == decision.evidence_review_ids
    assert zh.science_decision_id == decision.id
    assert zh.model_version == decision.model_version
    assert zh.evidence_review_ids == decision.evidence_review_ids
    assert [citation.key for citation in en.citations] == [
        citation.key for citation in zh.citations
    ]
    assert [citation.url for citation in en.citations] == [
        citation.url for citation in zh.citations
    ]
    assert en.citations


def test_every_heat_theory_parameter_has_decision_provenance() -> None:
    registry = load_science_registry()
    decision = registry.decisions["sdr-heat-adaptation-v1"]
    theory = load_theory("heat", "praxys_heat_evidence")
    provenance = {
        parameter.name: parameter for parameter in decision.model_parameters
    }

    assert set(theory.params) <= set(provenance)
    for name, value in theory.params.items():
        parameter = provenance[name]
        assert parameter.value == value
        if parameter.classification == "published":
            assert parameter.evidence_claim_ids
        else:
            assert parameter.rationale

    assert any(
        parameter.classification == "published"
        for parameter in decision.model_parameters
    )
    assert any(
        parameter.classification == "estimate"
        for parameter in decision.model_parameters
    )
    assert any(
        parameter.classification == "guardrail"
        for parameter in decision.model_parameters
    )


def test_heat_code_guardrails_have_decision_provenance() -> None:
    decision = load_science_registry().decisions["sdr-heat-adaptation-v1"]
    provenance = {
        parameter.name: parameter.value
        for parameter in decision.model_parameters
    }

    scalars = {
        "wet_bulb_method": metrics._HEAT_WET_BULB_METHOD,
        "wet_bulb_cold_corner_temperature_below_c": (
            metrics._HEAT_WET_BULB_COLD_CORNER_TEMPERATURE_BELOW_C
        ),
        "wet_bulb_cold_corner_humidity_below_pct": (
            metrics._HEAT_WET_BULB_COLD_CORNER_HUMIDITY_BELOW_PCT
        ),
        "value_precision_decimals": metrics._HEAT_VALUE_PRECISION_DECIMALS,
        "active_window_days": metrics._HEAT_ACTIVE_WINDOW_DAYS,
        "minimum_power_fraction_cp": metrics._HEAT_MIN_POWER_FRACTION_CP,
        "sample_coverage_ratio": metrics._HEAT_SAMPLE_COVERAGE_RATIO,
        "qualifying_effective_minutes": metrics._HEAT_QUALIFYING_EFFECTIVE_MIN,
        "building_days": metrics._HEAT_BUILDING_MIN_DAYS,
        "building_effective_minutes": metrics._HEAT_BUILDING_EFFECTIVE_MIN,
        "likely_adapted_days": metrics._HEAT_ADAPTED_MIN_DAYS,
        "likely_adapted_effective_minutes": metrics._HEAT_ADAPTED_EFFECTIVE_MIN,
        "wet_bulb_reference_c": metrics._HEAT_REFERENCE_WET_BULB_C,
        "wet_bulb_full_weight_c": metrics._HEAT_FULL_WEIGHT_WET_BULB_C,
        "dry_bulb_reference_c": metrics._HEAT_REFERENCE_DRY_BULB_C,
        "dry_bulb_full_weight_c": metrics._HEAT_FULL_WEIGHT_DRY_BULB_C,
        "decay_start_days": metrics._HEAT_DECAY_START_DAYS,
        "decay_end_days": metrics._HEAT_DECAY_END_DAYS,
        "environment_weight_combination": (
            metrics._HEAT_ENVIRONMENT_WEIGHT_COMBINATION
        ),
        "lookback_days": metrics.HEAT_LOOKBACK_DAYS,
        "sample_max_interval_sec": metrics.HEAT_SAMPLE_MAX_INTERVAL_SEC,
        "confidence_moderate_activity_count": (
            metrics._HEAT_CONFIDENCE_MODERATE_ACTIVITY_COUNT
        ),
        "confidence_high_activity_count": (
            metrics._HEAT_CONFIDENCE_HIGH_ACTIVITY_COUNT
        ),
        "public_session_limit": metrics._HEAT_PUBLIC_SESSION_LIMIT,
        "provider_alignment_required": metrics._HEAT_PROVIDER_ALIGNMENT_REQUIRED,
        "reacclimation_min_post_gap_sessions": (
            metrics._HEAT_REACCLIMATION_MIN_POST_GAP_SESSIONS
        ),
    }
    ordered_ranges = {
        "wet_bulb_valid_temperature_c": (
            metrics._HEAT_WET_BULB_VALID_TEMPERATURE_C
        ),
        "wet_bulb_valid_relative_humidity_pct": (
            metrics._HEAT_WET_BULB_VALID_RELATIVE_HUMIDITY_PCT
        ),
        "activity_environment_temperature_c": (
            metrics._HEAT_ACTIVITY_ENVIRONMENT_TEMPERATURE_C
        ),
        "activity_environment_relative_humidity_pct": (
            metrics._HEAT_ACTIVITY_ENVIRONMENT_RELATIVE_HUMIDITY_PCT
        ),
    }
    sets = {
        "supported_environment_sources": (
            metrics._HEAT_SUPPORTED_ENVIRONMENT_SOURCES
        ),
        "eligible_activity_types": metrics.HEAT_ELIGIBLE_ACTIVITY_TYPES,
        "restrictive_today_recommendations": (
            metrics._HEAT_RESTRICTIVE_TODAY_RECOMMENDATIONS
        ),
        "heat_exposure_actions": metrics._HEAT_EXPOSURE_ACTIONS,
    }

    assert set(provenance) == set(scalars) | set(ordered_ranges) | set(sets)
    for name, value in scalars.items():
        assert provenance[name] == value
    for name, value in ordered_ranges.items():
        assert tuple(provenance[name]) == value
    for name, value in sets.items():
        assert set(provenance[name]) == set(value)


def test_linked_heat_theory_does_not_duplicate_registry_data() -> None:
    root = Path(__file__).resolve().parents[1] / "data" / "science"
    en = yaml.safe_load(
        (root / "heat" / "praxys_heat_evidence.yaml").read_text(
            encoding="utf-8",
        )
    )
    zh = yaml.safe_load(
        (root / "zh" / "heat" / "praxys_heat_evidence.yaml").read_text(
            encoding="utf-8",
        )
    )

    assert en["science_decision_id"] == metrics._HEAT_SCIENCE_DECISION_ID
    assert "citations" not in en
    assert "citations" not in zh
    assert "params" not in zh
    assert "science_decision_id" not in zh


def test_theory_link_rejects_parameter_drift() -> None:
    registry = load_science_registry()
    theory = load_theory("heat", "praxys_heat_evidence")
    changed = {**theory.params, "active_window_days": 13}

    with pytest.raises(ValueError, match="parameter values differ"):
        registry.validate_theory_link(
            decision_id=theory.science_decision_id or "",
            model_key="heat/praxys_heat_evidence",
            model_version=theory.model_version or "",
            params=changed,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("doi", "not-a-doi"),
        ("pmid", "PMID-123"),
        ("url", "ftp://example.com/paper"),
    ],
)
def test_citation_identifier_syntax_is_validated(
    field: str,
    value: str,
) -> None:
    raw = {
        "id": "source-2026",
        "title": "Example source",
        "authors": ["Example, A."],
        "year": 2026,
        "journal": "Example Journal",
        "doi": "10.1000/example",
    }
    raw[field] = value

    with pytest.raises(ValidationError):
        CitationSource.model_validate(raw)


def test_citation_requires_a_stable_identifier() -> None:
    with pytest.raises(ValidationError):
        CitationSource.model_validate({
            "id": "source-2026",
            "title": "Example source",
            "authors": ["Example, A."],
            "year": 2026,
            "journal": "Example Journal",
        })


@pytest.mark.parametrize(
    "url",
    [
        "https://doi.org/10.1000/example",
        "https://pubmed.ncbi.nlm.nih.gov/12345678/",
        "https://www.ncbi.nlm.nih.gov/pubmed/12345678/",
    ],
)
def test_citation_resolver_urls_require_structured_identifiers(
    url: str,
) -> None:
    with pytest.raises(ValidationError, match="structured"):
        CitationSource.model_validate({
            "id": "example-2026",
            "title": "Example source",
            "authors": ["Example, A."],
            "year": 2026,
            "journal": "Example Journal",
            "url": url,
        })


def test_pubmed_url_must_match_structured_identifier() -> None:
    with pytest.raises(ValidationError, match="must match"):
        CitationSource.model_validate({
            "id": "example-2026",
            "title": "Example source",
            "authors": ["Example, A."],
            "year": 2026,
            "journal": "Example Journal",
            "pmid": "87654321",
            "url": "https://pubmed.ncbi.nlm.nih.gov/12345678/",
        })


@pytest.mark.parametrize(
    "raw",
    [
        {
            "name": "published_value",
            "value": 1,
            "classification": "published",
            "rationale": "A rationale cannot replace a source claim.",
        },
        {
            "name": "estimated_value",
            "value": 1,
            "classification": "estimate",
            "evidence_claim_ids": ["claim.support"],
        },
        {
            "name": "guardrail_value",
            "value": 1,
            "classification": "guardrail",
        },
    ],
)
def test_parameter_provenance_requires_claims_or_rationale(raw: dict) -> None:
    with pytest.raises(ValidationError):
        ParameterProvenance.model_validate(raw)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_registry_rejects_non_finite_numbers(value: float) -> None:
    with pytest.raises(ValidationError):
        EffectEstimate.model_validate({
            "metric": "Example",
            "estimate": value,
            "unit": "units",
            "context": "Synthetic fixture",
        })

    with pytest.raises(ValidationError):
        ParameterProvenance.model_validate({
            "name": "example",
            "value": value,
            "classification": "guardrail",
            "rationale": "Synthetic fixture.",
        })


def test_accepted_review_requires_human_review_metadata() -> None:
    with pytest.raises(ValidationError):
        EvidenceReview.model_validate({
            "schema_version": 1,
            "id": "evidence-example-v1",
            "version": 1,
            "title": "Example",
            "research_question": "What does the evidence support?",
            "topic": "example",
            "status": "accepted",
            "authors": ["agent:copilot"],
            "created_on": "2026-07-25",
            "intended_product_purpose": "Test validation.",
            "scope": {
                "population": ["Adults"],
                "intervention_or_exposure": ["Example exposure"],
                "comparator": ["Control"],
                "outcomes": ["Example outcome"],
            },
            "method": {
                "review_type": "rapid",
                "search_date": "2026-07-25",
                "sources": [{
                    "name": "PubMed",
                    "search_string": "example query",
                }],
                "inclusion_criteria": ["Peer-reviewed human research"],
                "exclusion_criteria": ["Non-human research"],
            },
            "claims": [{
                "id": "example.support",
                "statement": "The example supports the test fixture.",
                "source_ids": ["example-2026"],
                "evidence_strength": "low",
                "applicable_population": ["Adults"],
                "domain": ["Example"],
                "limitations": ["Synthetic fixture"],
            }],
            "citations": [{
                "id": "example-2026",
                "title": "Example source",
                "authors": ["Example, A."],
                "year": 2026,
                "journal": "Example Journal",
                "doi": "10.1000/example",
            }],
            "known_gaps": [],
            "conflicting_findings": [],
            "follow_up_questions": [],
        })


def test_registry_rejects_unknown_claim_reference(tmp_path: Path) -> None:
    science_dir = tmp_path / "science"
    evidence_dir = science_dir / "evidence" / "example"
    decisions_dir = science_dir / "decisions"
    evidence_dir.mkdir(parents=True)
    decisions_dir.mkdir(parents=True)

    review = {
        "schema_version": 1,
        "id": "evidence-example-v1",
        "version": 1,
        "title": "Example evidence",
        "research_question": "What does the evidence support?",
        "topic": "example",
        "status": "accepted",
        "authors": ["agent:copilot"],
        "human_reviewers": ["github:reviewer"],
        "created_on": "2026-07-25",
        "reviewed_on": "2026-07-25",
        "intended_product_purpose": "Exercise cross-record validation.",
        "scope": {
            "population": ["Adults"],
            "intervention_or_exposure": ["Example exposure"],
            "comparator": ["Control"],
            "outcomes": ["Example outcome"],
        },
        "method": {
            "review_type": "rapid",
            "search_date": "2026-07-25",
            "sources": [{
                "name": "PubMed",
                "search_string": "example query",
            }],
            "inclusion_criteria": ["Peer-reviewed human research"],
            "exclusion_criteria": ["Non-human research"],
        },
        "claims": [{
            "id": "example.support",
            "statement": "The example supports the test fixture.",
            "source_ids": ["example-2026"],
            "evidence_strength": "low",
            "applicable_population": ["Adults"],
            "domain": ["Example"],
            "limitations": ["Synthetic fixture"],
        }],
        "citations": [{
            "id": "example-2026",
            "title": "Example source",
            "authors": ["Example, A."],
            "year": 2026,
            "journal": "Example Journal",
            "doi": "10.1000/example",
        }],
        "known_gaps": [],
        "conflicting_findings": [],
        "follow_up_questions": [],
    }
    decision = {
        "schema_version": 1,
        "id": "sdr-example-v1",
        "version": 1,
        "title": "Example decision",
        "status": "accepted",
        "decision_date": "2026-07-25",
        "owners": ["team:praxys"],
        "human_reviewers": ["github:reviewer"],
        "model_version": "example-v1",
        "evidence_review_ids": ["evidence-example-v1"],
        "evidence_claim_ids": ["missing.claim"],
        "accepted_interpretation": "Use the example.",
        "rejected_alternatives": [{
            "alternative": "Do not use the example.",
            "rationale": "It would not exercise the registry.",
        }],
        "model_parameters": [],
        "applicability": ["Example domain"],
        "user_facing_claim_limits": ["Do not overclaim."],
        "safety_implications": ["None identified."],
        "privacy_implications": ["No personal data."],
        "validation_plan": ["Validate the example."],
        "falsification_conditions": ["Contradictory evidence."],
        "affected_surfaces": {
            "models": ["example/model"],
            "apis": [],
            "clients": [],
            "science_notes": [],
        },
    }
    (evidence_dir / "evidence-example-v1.yaml").write_text(
        yaml.safe_dump(review, sort_keys=False),
        encoding="utf-8",
    )
    (decisions_dir / "sdr-example-v1.yaml").write_text(
        yaml.safe_dump(decision, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing.claim"):
        load_science_registry(science_dir)


def test_registry_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "science" / "evidence" / "example"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "evidence-example-v2.yaml").write_text(
        "schema_version: 2\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="only understands version 1"):
        load_science_registry(tmp_path / "science")


def test_supersession_links_must_be_reciprocal_and_acyclic() -> None:
    registry = load_science_registry()
    current = registry.evidence_reviews["evidence-heat-decay-v1"]
    old = current.model_copy(update={
        "status": RecordStatus.SUPERSEDED,
        "superseded_by": "evidence-heat-decay-v2",
    })
    new = current.model_copy(update={
        "id": "evidence-heat-decay-v2",
        "version": 2,
        "supersedes": [old.id],
    })

    _validate_supersession({old.id: old, new.id: new})

    broken = new.model_copy(update={"supersedes": []})
    with pytest.raises(ValueError, match="must supersede"):
        _validate_supersession({old.id: old, broken.id: broken})


def test_superseding_review_can_reuse_identical_citations(
    tmp_path: Path,
) -> None:
    current = load_science_registry().evidence_reviews[
        "evidence-heat-decay-v1"
    ]
    old = current.model_dump(mode="json")
    old["status"] = "superseded"
    old["superseded_by"] = "evidence-heat-decay-v2"

    new = current.model_dump(mode="json")
    new["id"] = "evidence-heat-decay-v2"
    new["version"] = 2
    new["supersedes"] = ["evidence-heat-decay-v1"]
    for claim in new["claims"]:
        claim["id"] = claim["id"].replace("heat-decay.", "heat-decay-v2.")

    evidence_dir = tmp_path / "science" / "evidence" / "heat-decay"
    evidence_dir.mkdir(parents=True)
    for record in (old, new):
        (evidence_dir / f"{record['id']}.yaml").write_text(
            yaml.safe_dump(record, sort_keys=False),
            encoding="utf-8",
        )

    registry = load_science_registry(tmp_path / "science")

    assert set(registry.evidence_reviews) == {
        "evidence-heat-decay-v1",
        "evidence-heat-decay-v2",
    }
    assert len(registry.citations) == len(current.citations)


def test_registry_index_is_generated_from_current_records() -> None:
    root = Path(__file__).resolve().parents[1]
    registry = load_science_registry()

    assert (root / "data" / "science" / "REGISTRY.md").read_text(
        encoding="utf-8",
    ) == render_registry_index(registry)


def test_metric_science_links_match_the_registry() -> None:
    registry = load_science_registry()
    expected = registry.source_links_for_decision(
        metrics._HEAT_SCIENCE_DECISION_ID
    )
    status = compute_heat_adaptation(
        pd.DataFrame(),
        pd.DataFrame(),
        cp_watts=None,
        current_date=date(2026, 7, 25),
    )

    assert status["science_sources"] == expected
    environment = metrics.build_activity_environment_context(
        None,
        None,
        None,
    )
    assert environment["science_sources"] == (
        registry.source_links_for_decision(
            "sdr-environmental-performance-v1"
        )
    )
    accepted_environment_sources = {
        source["id"]
        for source in registry.source_links_for_decision(
            metrics.ENVIRONMENT_CONTEXT_SCIENCE_DECISION_ID
        )
    }
    assert {
        source["id"] for source in environment["science_sources"]
    } < accepted_environment_sources
