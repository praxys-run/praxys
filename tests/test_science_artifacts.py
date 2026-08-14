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
    render_policy_contract_json,
    science_decision_digest,
    sync_science_artifacts,
)


_EVIDENCE_ID = "evidence-road-10k-plan-generation-policy-v1"
_SHARED_EVIDENCE_ID = "evidence-plan-generation-eligibility-safety-v1"
_DECISION_ID = "sdr-road-10k-plan-generation-policy-v1"


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
    decision = current.decisions[_DECISION_ID].model_copy(update={
        "status": status,
        "approval_mode": ApprovalMode.ARTIFACT,
        "human_reviewers": [],
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


def test_review_digests_ignore_lifecycle_but_change_reviewed_content() -> None:
    current = load_science_registry()
    review = current.evidence_reviews[_EVIDENCE_ID].model_copy(update={
        "approval_mode": ApprovalMode.ARTIFACT,
        "human_reviewers": [],
    })
    decision = current.decisions[_DECISION_ID].model_copy(update={
        "approval_mode": ApprovalMode.ARTIFACT,
        "human_reviewers": [],
        "artifact_policy": DecisionArtifactPolicy(),
    })

    assert evidence_review_digest(review) == evidence_review_digest(
        review.model_copy(update={
            "status": RecordStatus.DRAFT,
            "reviewed_on": None,
        })
    )
    assert science_decision_digest(decision) == science_decision_digest(
        decision.model_copy(update={"status": RecordStatus.DRAFT})
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


def test_repository_generated_science_artifacts_are_current() -> None:
    registry = load_science_registry()
    assert sync_science_artifacts(registry, check=True) == []
