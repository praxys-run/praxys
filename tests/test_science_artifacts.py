"""Tests for generated science review packets, contracts, and approvals."""

from dataclasses import replace
from datetime import date
import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from analysis.evidence_registry import (
    ApprovalMode,
    ArtifactRuntimeState,
    DecisionArtifactPolicy,
    DecisionReviewDisposition,
    DecisionReviewItem,
    DecisionReviewManifest,
    EvidenceReview,
    RecordStatus,
    ScienceDecisionRecord,
    ScienceRegistry,
    load_science_registry,
)
from analysis.science_artifacts import (
    ReviewRole,
    ReviewScope,
    ReviewSubjectKind,
    ScienceApproval,
    SciencePolicyContract,
    build_policy_contract,
    evidence_review_digest,
    expected_science_artifacts,
    load_policy_contract,
    load_science_approvals,
    render_policy_contract_json,
    science_decision_digest,
    sync_science_artifacts,
)


_EVIDENCE_ID = "evidence-road-10k-plan-generation-policy-v1"
_SHARED_EVIDENCE_ID = "evidence-plan-generation-eligibility-safety-v1"
_DECISION_ID = "sdr-road-10k-plan-generation-policy-v1"


def _decision_review_manifest(
    decision: ScienceDecisionRecord,
) -> DecisionReviewManifest:
    def contains_not_accepted(value: object) -> bool:
        if isinstance(value, dict):
            return any(
                contains_not_accepted(nested)
                for nested in value.values()
            )
        if isinstance(value, list):
            return any(
                contains_not_accepted(nested)
                for nested in value
            )
        return value == "not_accepted"

    approved_parameters = [
        parameter.name
        for parameter in decision.model_parameters
        if not contains_not_accepted(parameter.value)
    ]
    deferred_parameters = [
        parameter.name
        for parameter in decision.model_parameters
        if contains_not_accepted(parameter.value)
    ]
    return DecisionReviewManifest(
        reviewer_task=(
            "Decide whether the proposed scope and explicit deferrals are "
            "acceptable. Do not review implementation code in this role."
        ),
        approval_statement=(
            "I approve every proposed decision and explicit deferral in this "
            "sheet as one inactive science decision. I am not approving "
            "implementation or runtime activation."
        ),
        items=[
            DecisionReviewItem(
                id="policy-boundary",
                title="Accept the policy boundary",
                disposition=DecisionReviewDisposition.APPROVE,
                question="Should Praxys accept this bounded policy?",
                proposed_decision=(
                    "Accept the stated scope, safety boundary, and claim limits."
                ),
                approval_effect=[
                    "The mapped contract groups become accepted decision inputs.",
                ],
                does_not_authorize=[
                    "Runtime activation or automatic plan adoption.",
                ],
                parameter_names=approved_parameters,
                evidence_claim_ids=[decision.evidence_claim_ids[0]],
            ),
            DecisionReviewItem(
                id="deferred-implementation-details",
                title="Keep implementation details deferred",
                disposition=DecisionReviewDisposition.DEFER,
                question="Should the remaining implementation details stay open?",
                proposed_decision=(
                    "Keep the mapped details unresolved until a later decision."
                ),
                approval_effect=[
                    "The mapped groups remain visible but do not activate code.",
                ],
                does_not_authorize=[
                    "Filling deferred values from prose, defaults, or AI.",
                ],
                parameter_names=deferred_parameters,
                evidence_claim_ids=[],
            ),
        ],
    )


def _write_yaml(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )


def _write_fixture_records(
    science_dir: Path,
    *,
    status: RecordStatus,
    runtime_state: ArtifactRuntimeState = ArtifactRuntimeState.INACTIVE,
) -> tuple[EvidenceReview, ScienceDecisionRecord]:
    current = load_science_registry()
    shared = current.evidence_reviews[_SHARED_EVIDENCE_ID]
    review = current.evidence_reviews[_EVIDENCE_ID].model_copy(update={
        "status": status,
        "approval_mode": ApprovalMode.ARTIFACT,
        "human_reviewers": [],
        "reviewed_on": date(2026, 8, 14)
        if status == RecordStatus.ACCEPTED
        else None,
    })
    base_decision = current.decisions[_DECISION_ID]
    decision = base_decision.model_copy(update={
        "status": status,
        "approval_mode": ApprovalMode.ARTIFACT,
        "human_reviewers": [],
        "decision_review": _decision_review_manifest(base_decision),
        "artifact_policy": DecisionArtifactPolicy(
            runtime_state=runtime_state,
        ),
    })
    _write_yaml(
        science_dir / "evidence" / "shared" / f"{shared.id}.yaml",
        shared.model_dump(mode="json"),
    )
    _write_yaml(
        science_dir / "evidence" / "pilot" / f"{review.id}.yaml",
        review.model_dump(mode="json"),
    )
    _write_yaml(
        science_dir / "decisions" / f"{decision.id}.yaml",
        decision.model_dump(mode="json"),
    )
    return review, decision


def _approval_payload(
    *,
    subject_kind: ReviewSubjectKind,
    subject_id: str,
    subject_digest: str,
    role: ReviewRole,
) -> dict[str, object]:
    scopes = {
        ReviewRole.EVIDENCE_REVIEWER: [
            ReviewScope.SEARCH_METHOD,
            ReviewScope.EVIDENCE_CLAIMS,
            ReviewScope.CITATION_VERIFICATION,
            ReviewScope.LIMITATIONS_AND_GAPS,
        ],
        ReviewRole.DECISION_APPROVER: [
            ReviewScope.DECISION_INTERPRETATION,
            ReviewScope.PARAMETERS,
            ReviewScope.APPLICABILITY,
            ReviewScope.CLAIM_LIMITS,
            ReviewScope.SAFETY_AND_PRIVACY,
            ReviewScope.ACTIVATION_BOUNDARY,
        ],
        ReviewRole.IMPLEMENTATION_REVIEWER: [
            ReviewScope.CONTRACT_MAPPING,
            ReviewScope.RUNTIME_DIFF,
            ReviewScope.VALIDATION,
        ],
    }[role]
    return {
        "schema_version": 1,
        "subject_kind": subject_kind.value,
        "subject_id": subject_id,
        "subject_digest": subject_digest,
        "reviewer": "github:reviewer",
        "role": role.value,
        "reviewed_on": "2026-08-14",
        "scopes": [scope.value for scope in scopes],
        "source_ref":
            "https://github.com/praxys-run/praxys/pull/1"
            "#pullrequestreview-1",
    }


def _write_acceptance_approvals(
    science_dir: Path,
    review: EvidenceReview,
    decision: ScienceDecisionRecord,
) -> None:
    _write_yaml(
        science_dir / "approvals" / "evidence.yaml",
        _approval_payload(
            subject_kind=ReviewSubjectKind.EVIDENCE_REVIEW,
            subject_id=_EVIDENCE_ID,
            subject_digest=evidence_review_digest(review),
            role=ReviewRole.EVIDENCE_REVIEWER,
        ),
    )
    _write_yaml(
        science_dir / "approvals" / "decision.yaml",
        _approval_payload(
            subject_kind=ReviewSubjectKind.SCIENCE_DECISION,
            subject_id=_DECISION_ID,
            subject_digest=science_decision_digest(decision),
            role=ReviewRole.DECISION_APPROVER,
        ),
    )


def test_draft_artifact_records_render_complete_review_and_contract(
    tmp_path: Path,
) -> None:
    science_dir = tmp_path / "science"
    _write_fixture_records(science_dir, status=RecordStatus.DRAFT)
    registry = load_science_registry(science_dir)

    expected = expected_science_artifacts(registry)
    evidence_packet_path = (
        Path("generated")
        / "review-packets"
        / f"{_EVIDENCE_ID}.md"
    )
    decision_packet_path = (
        Path("generated")
        / "review-packets"
        / f"{_DECISION_ID}.md"
    )
    contract_path = (
        Path("generated")
        / "contracts"
        / f"{_DECISION_ID}.json"
    )
    assert set(expected) == {
        evidence_packet_path,
        decision_packet_path,
        contract_path,
    }

    contract = SciencePolicyContract.model_validate_json(
        expected[contract_path]
    )
    exact_contract_block = (
        "```json\n"
        + render_policy_contract_json(contract).rstrip()
        + "\n```"
    )
    assert exact_contract_block in expected[decision_packet_path]
    assert contract.source_decision_digest in expected[decision_packet_path]
    assert contract.contract_digest in expected[decision_packet_path]
    assert "activity_avg_power" in expected[decision_packet_path]
    assert "Exact reviewed evidence payload" in expected[evidence_packet_path]
    assert "range -0.28 to 0.25" in expected[evidence_packet_path]
    packet = expected[decision_packet_path]
    assert packet.index("## Your task") < packet.index("## Decision sheet")
    assert packet.index("## Decision sheet") < packet.index(
        "## Audit appendix"
    )
    assert "Approve the decision sheet as a unit" in packet
    assert "Proposed decisions to approve" in packet
    assert "Decisions explicitly deferred" in packet
    assert "Do not approve merely because the audit appendix" in packet
    assert "I approve every proposed decision" in packet
    assert "human-authenticated PR comment" in packet
    assert "<!-- praxys-science-approval:v1" in packet
    assert "reviewers do not edit it by hand" in expected[evidence_packet_path]
    assert "<details><summary>Evidence, parameters" in packet
    assert "<details><summary>Traceability:" in packet

    assert sync_science_artifacts(registry, check=False)
    assert sync_science_artifacts(registry, check=True) == []
    with pytest.raises(ValueError, match="not accepted"):
        load_policy_contract(
            _DECISION_ID,
            science_dir=science_dir,
            require_active=True,
        )

    (science_dir / contract_path).write_text("{}\n", encoding="utf-8")
    assert sync_science_artifacts(registry, check=True) == [contract_path]


def test_artifact_decision_review_must_cover_every_contract_group(
    tmp_path: Path,
) -> None:
    science_dir = tmp_path / "science"
    _, decision = _write_fixture_records(
        science_dir,
        status=RecordStatus.DRAFT,
    )
    payload = decision.model_dump(mode="json")

    payload_without_review = {
        **payload,
        "decision_review": None,
    }
    with pytest.raises(
        ValidationError,
        match="require decision_review",
    ):
        ScienceDecisionRecord.model_validate(payload_without_review)

    missing_payload = json.loads(json.dumps(payload))
    missing_payload["decision_review"]["items"][0][
        "parameter_names"
    ].pop()
    with pytest.raises(
        ValidationError,
        match="does not cover parameters",
    ):
        ScienceDecisionRecord.model_validate(missing_payload)

    unknown_payload = json.loads(json.dumps(payload))
    unknown_payload["decision_review"]["items"][0][
        "parameter_names"
    ].append("unknown_contract_group")
    with pytest.raises(
        ValidationError,
        match="references unknown parameters",
    ):
        ScienceDecisionRecord.model_validate(unknown_payload)

    hidden_deferral_payload = json.loads(json.dumps(payload))
    hidden_deferral_payload["decision_review"]["items"][1][
        "disposition"
    ] = DecisionReviewDisposition.APPROVE.value
    with pytest.raises(
        ValidationError,
        match="does not explicitly defer unresolved parameters",
    ):
        ScienceDecisionRecord.model_validate(hidden_deferral_payload)


def test_review_digests_ignore_lifecycle_but_change_reviewed_content() -> None:
    current = load_science_registry()
    review = current.evidence_reviews[_EVIDENCE_ID].model_copy(update={
        "approval_mode": ApprovalMode.ARTIFACT,
        "human_reviewers": [],
    })
    base_decision = current.decisions[_DECISION_ID]
    decision = base_decision.model_copy(update={
        "approval_mode": ApprovalMode.ARTIFACT,
        "human_reviewers": [],
        "decision_review": _decision_review_manifest(base_decision),
        "artifact_policy": DecisionArtifactPolicy(),
    })

    assert evidence_review_digest(review) == evidence_review_digest(
        review.model_copy(update={
            "status": RecordStatus.DRAFT,
            "reviewed_on": None,
        })
    )
    assert evidence_review_digest(review) == evidence_review_digest(
        review.model_copy(update={
            "supersedes": [_SHARED_EVIDENCE_ID],
        })
    )
    assert science_decision_digest(decision) == science_decision_digest(
        decision.model_copy(update={"status": RecordStatus.DRAFT})
    )
    assert science_decision_digest(decision) == science_decision_digest(
        decision.model_copy(update={
            "supersedes": ["sdr-plan-generation-eligibility-safety-v1"],
        })
    )

    changed_parameters = list(decision.model_parameters)
    changed_parameters[0] = changed_parameters[0].model_copy(update={
        "value": {"changed": True},
    })
    changed = decision.model_copy(update={
        "model_parameters": changed_parameters,
    })
    assert science_decision_digest(changed) != science_decision_digest(
        decision
    )


def test_accepted_artifact_records_require_matching_role_approvals(
    tmp_path: Path,
) -> None:
    science_dir = tmp_path / "science"
    review, decision = _write_fixture_records(
        science_dir,
        status=RecordStatus.ACCEPTED,
    )

    with pytest.raises(
        ValueError,
        match="requires an evidence_reviewer approval",
    ):
        load_science_registry(science_dir)

    _write_acceptance_approvals(science_dir, review, decision)
    registry = load_science_registry(science_dir)
    assert registry.evidence_reviews[_EVIDENCE_ID].human_reviewers == []
    assert registry.decisions[_DECISION_ID].human_reviewers == []

    decision_path = science_dir / "decisions" / f"{_DECISION_ID}.yaml"
    raw = yaml.safe_load(decision_path.read_text(encoding="utf-8"))
    raw["accepted_interpretation"] += " Changed after approval."
    _write_yaml(decision_path, raw)
    with pytest.raises(ValueError, match="is stale"):
        load_science_registry(science_dir)


def test_active_contract_requires_implementation_approval(
    tmp_path: Path,
) -> None:
    science_dir = tmp_path / "science"
    review, decision = _write_fixture_records(
        science_dir,
        status=RecordStatus.ACCEPTED,
    )
    _write_acceptance_approvals(science_dir, review, decision)
    inactive_registry = load_science_registry(science_dir)

    active_decision = decision.model_copy(update={
        "artifact_policy": DecisionArtifactPolicy(
            runtime_state=ArtifactRuntimeState.ACTIVE,
        ),
    })
    active_registry = replace(
        inactive_registry,
        decisions={
            **inactive_registry.decisions,
            _DECISION_ID: active_decision,
        },
    )
    active_contract = build_policy_contract(active_registry, _DECISION_ID)
    _write_yaml(
        science_dir / "decisions" / f"{_DECISION_ID}.yaml",
        active_decision.model_dump(mode="json"),
    )
    _write_yaml(
        science_dir / "approvals" / "decision.yaml",
        _approval_payload(
            subject_kind=ReviewSubjectKind.SCIENCE_DECISION,
            subject_id=_DECISION_ID,
            subject_digest=science_decision_digest(active_decision),
            role=ReviewRole.DECISION_APPROVER,
        ),
    )

    with pytest.raises(
        ValueError,
        match="requires an implementation_reviewer approval",
    ):
        load_science_registry(science_dir)

    _write_yaml(
        science_dir / "approvals" / "implementation.yaml",
        _approval_payload(
            subject_kind=ReviewSubjectKind.IMPLEMENTATION_CONTRACT,
            subject_id=_DECISION_ID,
            subject_digest=active_contract.contract_digest,
            role=ReviewRole.IMPLEMENTATION_REVIEWER,
        ),
    )
    registry = load_science_registry(science_dir)
    sync_science_artifacts(registry, check=False)
    loaded = load_policy_contract(
        _DECISION_ID,
        science_dir=science_dir,
        require_active=True,
    )
    assert loaded.runtime_state == ArtifactRuntimeState.ACTIVE
    assert loaded.parameter_values


def test_approval_roles_require_complete_scopes() -> None:
    payload = _approval_payload(
        subject_kind=ReviewSubjectKind.SCIENCE_DECISION,
        subject_id=_DECISION_ID,
        subject_digest="sha256:" + "0" * 64,
        role=ReviewRole.DECISION_APPROVER,
    )
    payload["scopes"] = [ReviewScope.PARAMETERS.value]
    with pytest.raises(ValidationError, match="missing scopes"):
        ScienceApproval.model_validate(payload)

    payload = _approval_payload(
        subject_kind=ReviewSubjectKind.SCIENCE_DECISION,
        subject_id=_DECISION_ID,
        subject_digest="sha256:" + "0" * 64,
        role=ReviewRole.DECISION_APPROVER,
    )
    payload["reviewer"] = "agent:copilot"
    with pytest.raises(ValidationError, match="identified human reviewer"):
        ScienceApproval.model_validate(payload)


def test_adaptive_plan_packet_contains_exact_accepted_inactive_contract() -> None:
    registry = load_science_registry()
    decision_id = "sdr-adaptive-plan-feasibility-and-adjustment-v1"
    decision = registry.decisions[decision_id]
    expected_contract = build_policy_contract(registry, decision_id)
    generated_contract = SciencePolicyContract.model_validate_json(
        (
            Path("data/science/generated/contracts")
            / f"{decision_id}.json"
        ).read_text(encoding="utf-8")
    )
    packet = (
        Path("data/science/generated/review-packets")
        / f"{decision_id}.md"
    ).read_text(encoding="utf-8")

    assert decision.status == RecordStatus.ACCEPTED
    assert decision.approval_mode == ApprovalMode.ARTIFACT
    assert decision.human_reviewers == []
    assert decision.artifact_policy is not None
    assert (
        decision.artifact_policy.runtime_state
        == ArtifactRuntimeState.INACTIVE
    )
    assert generated_contract == expected_contract
    assert generated_contract.decision_status == RecordStatus.ACCEPTED
    assert generated_contract.runtime_state == ArtifactRuntimeState.INACTIVE

    exact_contract_block = (
        "```json\n"
        + render_policy_contract_json(expected_contract).rstrip()
        + "\n```"
    )
    assert exact_contract_block in packet
    assert expected_contract.source_decision_digest in packet
    assert expected_contract.contract_digest in packet
    assert packet.index("## Your task") < packet.index("## Decision sheet")
    assert packet.index("## Decision sheet") < packet.index(
        "## Audit appendix"
    )
    assert "**Decision approval:** _Pending_" not in packet
    assert (
        "**Decision approval:** `github:dddtc2005` on `2026-08-16`"
        in packet
    )
    assert packet.count("**Implementation approval:** _Pending_") == 1
    assert "Approve the decision sheet as a unit" in packet
    assert "request changes by item ID" in packet

    assert decision.decision_review is not None
    approve_ids = [
        item.id
        for item in decision.decision_review.items
        if item.disposition == DecisionReviewDisposition.APPROVE
    ]
    defer_ids = [
        item.id
        for item in decision.decision_review.items
        if item.disposition == DecisionReviewDisposition.DEFER
    ]
    assert approve_ids == [
        "actionable-position",
        "bounded-science",
        "athlete-controlled-loop",
        "hard-boundaries",
        "shared-policy-alignment",
    ]
    assert defer_ids == [
        "defer-selection-and-update",
        "defer-distance-rules-and-autonomy",
        "defer-implementation-and-activation",
    ]
    for item_id in [*approve_ids, *defer_ids]:
        assert packet.count(f"#### `{item_id}`") == 1

    assert expected_contract.parameters[
        "actionable_recommendation_contract"
    ].value["disclaimer_only_output_allowed"] is False
    assert expected_contract.parameters[
        "recommendation_loop_state_machine"
    ].value["deterministic_replay_required"] is True
    assert expected_contract.parameters[
        "privacy_and_traceability"
    ].value["sensitive_trait_inference_allowed"] is False
    assert expected_contract.parameters[
        "implementation_pilot_and_activation"
    ].value["active_behavior"] is False

    subject_ids = {decision_id, *decision.evidence_review_ids}
    approvals = [
        approval
        for approval in load_science_approvals(Path("data/science"))
        if approval.subject_id in subject_ids
    ]
    assert {
        (approval.subject_id, approval.role, approval.reviewer)
        for approval in approvals
    } == {
        *{
            (
                evidence_id,
                ReviewRole.EVIDENCE_REVIEWER,
                "github:dddtc2005",
            )
            for evidence_id in decision.evidence_review_ids
        },
        (
            decision_id,
            ReviewRole.DECISION_APPROVER,
            "github:dddtc2005",
        ),
    }

    for evidence_id in decision.evidence_review_ids:
        review = registry.evidence_reviews[evidence_id]
        evidence_packet = (
            Path("data/science/generated/review-packets")
            / f"{evidence_id}.md"
        ).read_text(encoding="utf-8")
        assert review.status == RecordStatus.ACCEPTED
        assert review.approval_mode == ApprovalMode.ARTIFACT
        assert "- **Review mode:** `artifact`" in evidence_packet
        assert (
            "- **Approval:** `github:dddtc2005` on `2026-08-16`"
            in evidence_packet
        )
        assert evidence_review_digest(review) in evidence_packet


def test_population_routing_packet_contains_exact_accepted_inactive_contract() -> None:
    registry = load_science_registry()
    expected = expected_science_artifacts(registry)
    evidence_id = "evidence-adult-running-plan-population-routing-v1"
    decision_id = "sdr-adult-running-plan-population-routing-v1"
    evidence_packet_path = (
        Path("generated") / "review-packets" / f"{evidence_id}.md"
    )
    decision_packet_path = (
        Path("generated") / "review-packets" / f"{decision_id}.md"
    )
    contract_path = (
        Path("generated") / "contracts" / f"{decision_id}.json"
    )

    contract = SciencePolicyContract.model_validate_json(
        expected[contract_path]
    )
    packet = expected[decision_packet_path]
    evidence_packet = expected[evidence_packet_path]
    exact_contract_block = (
        "```json\n"
        + render_policy_contract_json(contract).rstrip()
        + "\n```"
    )

    assert contract.decision_status == RecordStatus.ACCEPTED
    assert contract.runtime_state == ArtifactRuntimeState.INACTIVE
    assert contract.linked_evidence_digests[evidence_id] == (
        "sha256:2b64d44749b4318cade113134a599f3646cb25805abed0f56728d9959c2ef0c8"
    )
    assert contract.parameter_values[
        "first_completion_applicability"
    ]["permanent_identity_established"] is False
    assert contract.parameter_values[
        "history_and_detraining_inference"
    ]["sparse_or_missing_records_establish_detraining"] is False
    assert contract.parameter_values[
        "masters_applicability"
    ]["universal_age_exclusion_established"] is False
    assert contract.parameter_values[
        "construct_specific_profile_evidence"
    ]["general_plan_family_validated"] is False
    assert contract.parameter_values[
        "strength_and_cross_training_evidence"
    ]["running_equivalence_established"] is False
    assert contract.parameter_values[
        "adult_nonclinical_scope"
    ]["activity_average_power_valid_for_intensity"] is False
    assert set(
        contract.parameter_values["exact_values"].values()
    ) == {"not_accepted"}

    def mapping_keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value) | {
                key
                for nested in value.values()
                for key in mapping_keys(nested)
            }
        if isinstance(value, list):
            return {
                key
                for nested in value
                for key in mapping_keys(nested)
            }
        return set()

    forbidden_product_fields = {
        "goal_capture_independent_from_plan_availability",
        "prior_goal_distance_completion_required",
        "route_state",
        "goal_intent",
        "automatic_intent_coercion",
        "no_matching_policy_result",
        "history_states",
        "returning_state_requires_athlete_confirmation",
        "returning_to_consistency_intent_user_selectable",
        "provider_profile_requires_source_label_and_user_confirmation",
        "future_field_requirements",
        "shared_policy",
        "population_policy_may_define_second_feedback_engine",
        "accepted_distance_policy_alignment",
        "capability_registry_mapping",
        "policy_router_logic",
        "persistence_schema",
        "api_contracts",
        "web_and_miniapp_clients",
        "plugin_and_mcp_contracts",
        "profile_collection_and_privacy_operations",
        "primary_and_guardrail_metrics",
        "implementation_approval",
        "runtime_activation",
    }
    assert forbidden_product_fields.isdisjoint(
        mapping_keys(contract.parameter_values)
    )
    serialized_contract = render_policy_contract_json(contract)
    for route_result_or_dependency in (
        "completion_policy_unavailable",
        "readiness_only",
        "insufficient_recent_history_anchor",
        "clarification_required",
        "sdr-adaptive-plan-feasibility-and-adjustment-v1",
    ):
        assert route_result_or_dependency not in serialized_contract

    decision = registry.decisions[decision_id]
    assert decision.decision_review is not None
    assert [
        item.id
        for item in decision.decision_review.items
        if item.disposition == DecisionReviewDisposition.APPROVE
    ] == [
        "first-completion-applicability",
        "history-detraining-inference",
        "masters-applicability",
        "construct-specific-profile-evidence",
        "strength-cross-training-evidence",
        "adult-nonclinical-scope",
    ]
    assert [
        item.id
        for item in decision.decision_review.items
        if item.disposition == DecisionReviewDisposition.DEFER
    ] == [
        "all-exact-values",
        "all-non-science-decisions",
    ]

    assert exact_contract_block in packet
    assert (
        "**Decision approval:** `github:dddtc2005` on `2026-08-18`"
        in packet
    )
    assert "**Implementation approval:** _Pending_" in packet
    assert packet.index("## Your task") < packet.index("## Decision sheet")
    assert packet.index("## Decision sheet") < packet.index(
        "## Audit appendix"
    )
    assert "Approve the decision sheet as a unit" in packet
    assert "distinct evidence and applicability family" in packet
    assert "do not prove cessation or detraining" in packet
    assert "no universal age exclusion" in packet
    assert "construct-specific" in packet
    assert "does not establish injury prevention" in packet
    assert "outside Science authority" in packet
    assert "Review this packet, not the raw YAML" in evidence_packet
    assert (
        "- **Approval:** `github:dddtc2005` on `2026-08-17`"
        in evidence_packet
    )
    assert evidence_review_digest(
        registry.evidence_reviews[evidence_id]
    ) in evidence_packet


def test_road_10k_v2_packet_contains_generator_ready_inactive_contract() -> None:
    registry = load_science_registry()
    expected = expected_science_artifacts(registry)
    decision_id = "sdr-road-10k-plan-generation-policy-v2"
    decision_packet_path = (
        Path("generated") / "review-packets" / f"{decision_id}.md"
    )
    contract_path = (
        Path("generated") / "contracts" / f"{decision_id}.json"
    )

    contract = SciencePolicyContract.model_validate_json(
        expected[contract_path]
    )
    packet = expected[decision_packet_path]
    exact_contract_block = (
        "```json\n"
        + render_policy_contract_json(contract).rstrip()
        + "\n```"
    )

    assert contract.decision_status == RecordStatus.DRAFT
    assert contract.runtime_state == ArtifactRuntimeState.INACTIVE
    assert contract.parameter_values[
        "road_10k_v2_execution_window_and_reassessment"
    ]["committed_proposal_days"] == 14
    assert contract.parameter_values[
        "road_10k_v2_execution_window_and_reassessment"
    ]["advisory_reassessment_after_completed_days"] == 7
    assert contract.parameter_values[
        "road_10k_v2_schedule_construction"
    ]["quality_sessions_per_7_day_unit"] == 1
    assert [
        item["template_id"]
        for item in contract.parameter_values[
            "road_10k_v2_workout_templates"
        ]["templates"]
    ] == [
        "road-10k-controlled-threshold-quality-v1",
        "road-10k-specific-interval-quality-v1",
    ]
    assert contract.parameter_values[
        "road_10k_v2_event_benchmark_and_taper"
    ]["race_dense"]["full_proposal_allowed"] is False
    assert contract.parameter_values[
        "road_10k_v2_event_benchmark_and_taper"
    ]["single_target"]["target_fewer_than_8_days_after_start"] == (
        "limited_near_term_guidance"
    )
    assert contract.parameter_values[
        "road_10k_v2_typed_outcomes"
    ]["outcomes"]["safety_stop"]["route_state"] == "readiness_only"
    assert contract.parameter_values[
        "road_10k_v2_intensity_quality_and_spacing"
    ]["activity_average_power_allowed_for_intensity_analysis"] is False
    assert set(
        contract.parameter_values["road_10k_v2_deferred_scope"].values()
    ) == {"not_accepted"}

    assert exact_contract_block in packet
    assert contract.source_decision_digest in packet
    assert contract.contract_digest in packet
    assert "**Decision approval:** _Pending_" in packet
    assert "**Implementation approval:** _Pending_" in packet
    assert packet.count("_Pending_") == 3
    assert packet.index("## Your task") < packet.index("## Decision sheet")
    assert packet.index("## Decision sheet") < packet.index(
        "## Audit appendix"
    )
    for item_id in (
        "supported-capability",
        "rolling-execution",
        "deterministic-schedule",
        "event-and-taper",
        "hard-boundaries",
        "evaluation-gates",
        "broader-capabilities",
        "implementation-and-activation",
    ):
        assert packet.count(f"#### `{item_id}`") == 1
    assert "Praxys science approval" in packet
    assert "road-10k-controlled-threshold-quality-v1" in packet
    assert "road-10k-specific-interval-quality-v1" in packet
    assert "activity_avg_power" in packet


def test_half_marathon_packet_contains_exact_inactive_contract() -> None:
    registry = load_science_registry()
    expected = expected_science_artifacts(registry)
    evidence_id = (
        "evidence-road-half-marathon-plan-generation-policy-v1"
    )
    decision_id = "sdr-road-half-marathon-plan-generation-policy-v1"
    evidence_packet_path = (
        Path("generated") / "review-packets" / f"{evidence_id}.md"
    )
    decision_packet_path = (
        Path("generated") / "review-packets" / f"{decision_id}.md"
    )
    contract_path = (
        Path("generated") / "contracts" / f"{decision_id}.json"
    )

    contract = SciencePolicyContract.model_validate_json(
        expected[contract_path]
    )
    packet = expected[decision_packet_path]
    exact_contract_block = (
        "```json\n"
        + render_policy_contract_json(contract).rstrip()
        + "\n```"
    )

    assert contract.decision_status == RecordStatus.ACCEPTED
    assert contract.runtime_state == ArtifactRuntimeState.INACTIVE
    assert contract.parameter_values[
        "road_half_marathon_baseline_freshness"
    ]["exact_current_through_completed_days"] == "not_accepted"
    assert contract.parameter_values[
        "road_half_marathon_direct_baseline_hierarchy"
    ]["baseline_qualification_algorithm"] == "not_accepted"
    assert contract.parameter_values[
        "road_half_marathon_selected_taper_guardrail"
    ]["target_event_elapsed_time_included_in_training_minutes"] == (
        "not_accepted"
    )
    assert contract.parameter_values[
        "road_half_marathon_fueling_practice_policy"
    ]["product_glycogen_loading_duration_threshold"] == "not_accepted"
    assert contract.parameter_values[
        "road_half_marathon_open_decisions"
    ]["exact_workout_templates"] == "not_accepted"
    assert exact_contract_block in packet
    assert (
        "**Decision approval:** `github:dddtc2005` on `2026-08-14`"
        in packet
    )
    assert packet.count("_Pending_") == 1
    assert packet.index("## Your task") < packet.index("## Decision sheet")
    assert packet.index("## Decision sheet") < packet.index(
        "## Audit appendix"
    )
    assert "`supported-scope`" in packet
    assert "`evidence-use`" in packet
    assert "`hard-boundaries`" in packet
    assert "`mostly-low-structure`" in packet
    assert "`defer-baseline-history`" in packet
    assert "`defer-dose-taper`" in packet
    assert "`defer-fueling`" in packet
    assert "`defer-pilot-activation`" in packet
    assert "Exact machine contract — code consumption audit" in packet
    assert "<details><summary>Traceability:" in packet
    assert "activity_avg_power" in packet
    assert "Review this packet, not the raw YAML" in expected[
        evidence_packet_path
    ]


def test_marathon_packet_contains_exact_accepted_inactive_contract() -> None:
    registry = load_science_registry()
    expected = expected_science_artifacts(registry)
    evidence_id = "evidence-road-marathon-plan-generation-policy-v1"
    decision_id = "sdr-road-marathon-plan-generation-policy-v1"
    evidence_packet_path = (
        Path("generated") / "review-packets" / f"{evidence_id}.md"
    )
    decision_packet_path = (
        Path("generated") / "review-packets" / f"{decision_id}.md"
    )
    contract_path = (
        Path("generated") / "contracts" / f"{decision_id}.json"
    )

    contract = SciencePolicyContract.model_validate_json(
        expected[contract_path]
    )
    packet = expected[decision_packet_path]
    exact_contract_block = (
        "```json\n"
        + render_policy_contract_json(contract).rstrip()
        + "\n```"
    )

    assert contract.decision_status == RecordStatus.ACCEPTED
    assert contract.runtime_state == ArtifactRuntimeState.INACTIVE
    assert contract.parameter_values[
        "road_marathon_direct_baseline_hierarchy"
    ]["baseline_qualification_algorithm"] == "not_accepted"
    assert contract.parameter_values[
        "road_marathon_readiness_and_history_qualification"
    ]["minimum_usable_weeks"] == "not_accepted"
    assert contract.parameter_values[
        "road_marathon_history_anchored_load_policy"
    ]["plan_length_days"] == "not_accepted"
    assert contract.parameter_values[
        "road_marathon_long_run_and_durability_policy"
    ]["exact_long_run_distance"] == "not_accepted"
    assert contract.parameter_values[
        "road_marathon_intensity_and_race_specific_policy"
    ]["marathon_pace_or_race_specific_dose"] == "not_accepted"
    assert contract.parameter_values[
        "road_marathon_intensity_and_race_specific_policy"
    ]["mostly_low_intensity_organization_required"] is False
    assert contract.parameter_values[
        "road_marathon_intensity_and_race_specific_policy"
    ]["mostly_low_organization_is_candidate_scientific_prior"] is True
    assert contract.parameter_values[
        "road_marathon_intensity_and_race_specific_policy"
    ]["training_organization_selected_by_shared_adaptive_policy"] is True
    assert contract.parameter_values[
        "road_marathon_activation_and_dependency"
    ]["shared_adaptive_policy_dependency"]["sdr_id"] == (
        "sdr-adaptive-plan-feasibility-and-adjustment-v1"
    )
    assert contract.parameter_values[
        "road_marathon_taper_and_recovery_policy"
    ]["target_event_elapsed_time_included_in_training_minutes"] == (
        "not_accepted"
    )
    assert contract.parameter_values[
        "road_marathon_fueling_and_hydration_policy"
    ]["fluid_millilitres_per_hour_rule"] == "not_accepted"
    assert contract.parameter_values[
        "road_marathon_fueling_and_hydration_policy"
    ]["missing_material_context_outcome"] == "fueling_module_limited"
    assert contract.parameter_values[
        "road_marathon_fueling_and_hydration_policy"
    ]["missing_context_blocks_independent_plan_modules"] is False
    assert contract.parameter_values[
        "road_marathon_environment_and_altitude_policy"
    ]["personal_altitude_pace_or_finish_time_correction"] == "not_accepted"
    assert contract.parameter_values[
        "road_marathon_environment_and_altitude_policy"
    ]["incomplete_material_context_outcome"] == (
        "environment_module_limited"
    )
    assert contract.parameter_values[
        "road_marathon_environment_and_altitude_policy"
    ]["missing_context_blocks_independent_plan_modules"] is False
    assert contract.parameter_values[
        "road_marathon_reassessment_and_outcome_policy"
    ]["exact_post_marathon_outcome_window"] == "not_accepted"
    assert contract.parameter_values[
        "road_marathon_reassessment_and_outcome_policy"
    ]["feedback_update_algorithm_owned_by_shared_adaptive_policy"] is True
    assert contract.parameter_values[
        "road_marathon_validation_privacy_and_open_decisions"
    ]["shared_adaptive_policy_contract_required_before_activation"] is True
    assert contract.parameter_values[
        "road_marathon_validation_privacy_and_open_decisions"
    ]["runtime_activation_criteria"] == "not_accepted"
    typed_outcomes = contract.parameter_values[
        "road_marathon_typed_outcomes_and_suggestion_only_state"
    ]["outcomes"]
    assert typed_outcomes["fueling_module_limited"]["plan_returned"] is True
    assert typed_outcomes["environment_module_limited"][
        "plan_returned"
    ] is True

    decision = registry.decisions[decision_id]
    assert decision.decision_review is not None
    assert [
        item.id
        for item in decision.decision_review.items
        if item.disposition == DecisionReviewDisposition.APPROVE
    ] == [
        "narrow-modular-scope",
        "evidence-use",
        "hard-boundaries",
        "shared-adaptive-policy-dependency",
    ]
    assert [
        item.id
        for item in decision.decision_review.items
        if item.disposition == DecisionReviewDisposition.DEFER
    ] == [
        "defer-baseline-history",
        "defer-dose-specific-work",
        "defer-taper-recovery",
        "defer-fueling-hydration-environment",
        "defer-secondary-rollout",
    ]

    assert exact_contract_block in packet
    assert (
        "**Decision approval:** `github:dddtc2005` on `2026-08-16`"
        in packet
    )
    assert "**Implementation approval:** _Pending_" in packet
    assert packet.count("_Pending_") == 1
    assert packet.index("## Your task") < packet.index("## Decision sheet")
    assert packet.index("## Decision sheet") < packet.index(
        "## Audit appendix"
    )
    assert (
        packet.index(decision.decision_review.reviewer_task)
        < packet.index("## Audit appendix")
    )
    assert "Exact machine contract — code consumption audit" in packet
    assert "activity_avg_power" in packet
    assert "goal_recorded_plan_policy_unavailable" in packet
    assert "fueling_module_limited" in packet
    assert "environment_module_limited" in packet
    assert "candidate context" in packet
    assert "sdr-adaptive-plan-feasibility-and-adjustment-v1" in packet
    assert "shared managed-plan policy" in packet
    assert "Review this packet, not the raw YAML" in expected[
        evidence_packet_path
    ]


def test_repository_generated_science_artifacts_are_current() -> None:
    registry = load_science_registry()
    assert sync_science_artifacts(registry, check=True) == []
