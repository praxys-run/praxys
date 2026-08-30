"""Tests for authenticated science approval materialization."""

from datetime import date
import json
from pathlib import Path
import shutil

import pytest
import yaml

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
    load_science_registry,
    render_registry_index,
)
from analysis.science_approval_workflow import (
    approvals_from_github_comments,
    materialize_science_approvals,
    verify_science_approval_changes,
)
from analysis.science_artifacts import (
    ReviewRole,
    ReviewSubjectKind,
    ScienceApproval,
    approval_statement_for_subject,
    build_policy_contract,
    evidence_review_digest,
    load_science_approvals,
    render_approval_comment_template,
    required_review_scopes,
    science_decision_digest,
    sync_science_artifacts,
)


_EVIDENCE_ID = "evidence-road-10k-plan-generation-policy-v1"
_SHARED_EVIDENCE_ID = "evidence-plan-generation-eligibility-safety-v1"
_DECISION_ID = "sdr-road-10k-plan-generation-policy-v1"
_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW = _ROOT / ".github" / "workflows" / "science-approval-ledger.yml"
_SELECTIVE_REVIEW_WORKFLOW = (
    _ROOT / ".github" / "workflows" / "selective-review.yml"
)


def _write_yaml(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False),
        encoding="utf-8",
    )


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

    approved = [
        parameter.name
        for parameter in decision.model_parameters
        if not contains_not_accepted(parameter.value)
    ]
    deferred = [
        parameter.name
        for parameter in decision.model_parameters
        if contains_not_accepted(parameter.value)
    ]
    return DecisionReviewManifest(
        reviewer_task="Approve the decision sheet or request changes.",
        approval_statement=(
            "I approve the proposed decisions and explicit deferrals without "
            "approving implementation or runtime activation."
        ),
        items=[
            DecisionReviewItem(
                id="approved-boundary",
                title="Approve the bounded policy",
                disposition=DecisionReviewDisposition.APPROVE,
                question="Should Praxys accept this policy boundary?",
                proposed_decision="Accept the mapped policy groups.",
                approval_effect=["The mapped groups become accepted inputs."],
                does_not_authorize=["Runtime activation."],
                parameter_names=approved,
                evidence_claim_ids=[decision.evidence_claim_ids[0]],
            ),
            DecisionReviewItem(
                id="deferred-values",
                title="Keep unresolved values deferred",
                disposition=DecisionReviewDisposition.DEFER,
                question="Should unresolved values remain deferred?",
                proposed_decision="Keep the mapped values unresolved.",
                approval_effect=["No deferred value becomes a runtime input."],
                does_not_authorize=["Filling values from prose or defaults."],
                parameter_names=deferred,
                evidence_claim_ids=[],
            ),
        ],
    )


def _write_fixture_records(
    science_dir: Path,
) -> tuple[EvidenceReview, ScienceDecisionRecord]:
    current = load_science_registry()
    shared = current.evidence_reviews[_SHARED_EVIDENCE_ID]
    review = current.evidence_reviews[_EVIDENCE_ID].model_copy(update={
        "status": RecordStatus.DRAFT,
        "approval_mode": ApprovalMode.ARTIFACT,
        "human_reviewers": [],
        "reviewed_on": None,
    })
    base_decision = current.decisions[_DECISION_ID]
    decision = base_decision.model_copy(update={
        "status": RecordStatus.DRAFT,
        "approval_mode": ApprovalMode.ARTIFACT,
        "human_reviewers": [],
        "decision_review": _decision_review_manifest(base_decision),
        "artifact_policy": DecisionArtifactPolicy(
            runtime_state=ArtifactRuntimeState.INACTIVE,
        ),
        "supersedes": [],
        "superseded_by": None,
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
    registry = load_science_registry(science_dir)
    sync_science_artifacts(registry, check=False)
    (science_dir / "REGISTRY.md").write_text(
        render_registry_index(registry),
        encoding="utf-8",
    )
    return review, decision


def _approval(
    *,
    subject_kind: ReviewSubjectKind,
    subject_id: str,
    subject_digest: str,
    role: ReviewRole,
    source_ref: str,
) -> ScienceApproval:
    return ScienceApproval(
        schema_version=1,
        subject_kind=subject_kind,
        subject_id=subject_id,
        subject_digest=subject_digest,
        reviewer="github:dddtc2005",
        role=role,
        reviewed_on=date(2026, 8, 14),
        scopes=required_review_scopes(role),
        source_ref=source_ref,
    )


def _legacy_evidence_comment(digest: str) -> str:
    return (
        "Maintainer evidence review — **Approve Evidence Review** for "
        f"evidence digest `{digest}`.\n\n"
        "The reviewed evidence claims, verification limits, uncertainties, "
        "and non-inferences are accepted for this proposal. This approval "
        "does not approve implementation or runtime activation."
    )


def _legacy_decision_comment(digest: str) -> str:
    return (
        "Maintainer decision — **Approve decision sheet as a unit** for "
        f"decision digest `{digest}`.\n\n"
        "This approval covers the four proposed decisions "
        "(`supported-scope`, `evidence-use`, `hard-boundaries`, and "
        "`mostly-low-structure`) and agrees to the four explicit deferrals "
        "(`defer-baseline-history`, `defer-dose-taper`, `defer-fueling`, and "
        "`defer-pilot-activation`). The contract remains inactive. This "
        "comment does not approve implementation, runtime activation, or fill "
        "any deferred value."
    )


def test_github_comments_require_human_write_access_and_exact_marker(
    tmp_path: Path,
) -> None:
    science_dir = tmp_path / "science"
    review, _ = _write_fixture_records(science_dir)
    digest = evidence_review_digest(review)
    registry = load_science_registry(science_dir)
    body = render_approval_comment_template(
        subject_kind=ReviewSubjectKind.EVIDENCE_REVIEW,
        subject_id=review.id,
        subject_digest=digest,
        role=ReviewRole.EVIDENCE_REVIEWER,
        approval_statement=approval_statement_for_subject(
            registry,
            subject_kind=ReviewSubjectKind.EVIDENCE_REVIEW,
            subject_id=review.id,
            role=ReviewRole.EVIDENCE_REVIEWER,
        ),
    )
    comments = [
        {
            "id": 1,
            "body": body,
            "created_at": "2026-08-14T15:20:49Z",
            "html_url": "https://github.com/praxys-run/praxys/pull/1#issuecomment-1",
            "user": {"login": "reader", "type": "User"},
        },
        {
            "id": 2,
            "body": body,
            "created_at": "2026-08-14T15:21:49Z",
            "html_url": "https://github.com/praxys-run/praxys/pull/1#issuecomment-2",
            "user": {"login": "approval-bot[bot]", "type": "Bot"},
        },
        {
            "id": 3,
            "body": body,
            "created_at": "2026-08-14T15:22:49Z",
            "html_url": "https://github.com/praxys-run/praxys/pull/1#issuecomment-3",
            "user": {"login": "dddtc2005", "type": "User"},
        },
    ]

    approvals = approvals_from_github_comments(
        science_dir,
        comments,
        {
            "reader": "read",
            "approval-bot[bot]": "admin",
            "dddtc2005": "admin",
        },
    )

    assert len(approvals) == 1
    assert approvals[0].reviewer == "github:dddtc2005"
    assert approvals[0].subject_id == review.id
    assert str(approvals[0].source_ref).endswith("issuecomment-3")


def test_existing_digest_bound_pr_comments_remain_importable(
    tmp_path: Path,
) -> None:
    science_dir = tmp_path / "science"
    review, decision = _write_fixture_records(science_dir)
    comments = [
        {
            "id": 10,
            "body": _legacy_evidence_comment(
                evidence_review_digest(review)
            ),
            "created_at": "2026-08-14T15:20:49Z",
            "html_url": "https://github.com/praxys-run/praxys/pull/1#issuecomment-10",
            "user": {"login": "dddtc2005", "type": "User"},
        },
        {
            "id": 11,
            "body": _legacy_decision_comment(
                science_decision_digest(decision)
            ),
            "created_at": "2026-08-14T15:21:49Z",
            "html_url": "https://github.com/praxys-run/praxys/pull/1#issuecomment-11",
            "user": {"login": "dddtc2005", "type": "User"},
        },
    ]

    approvals = approvals_from_github_comments(
        science_dir,
        comments,
        {"dddtc2005": "write"},
    )

    assert [approval.role for approval in approvals] == [
        ReviewRole.EVIDENCE_REVIEWER,
        ReviewRole.DECISION_APPROVER,
    ]


def test_hidden_marker_without_visible_approval_is_rejected(
    tmp_path: Path,
) -> None:
    science_dir = tmp_path / "science"
    review, _ = _write_fixture_records(science_dir)
    marker = json.dumps({
        "role": ReviewRole.EVIDENCE_REVIEWER.value,
        "subject_digest": evidence_review_digest(review),
        "subject_id": review.id,
        "subject_kind": ReviewSubjectKind.EVIDENCE_REVIEW.value,
    }, separators=(",", ":"), sort_keys=True)
    comments = [{
        "id": 4,
        "body": f"<!-- praxys-science-approval:v1\n{marker}\n-->",
        "created_at": "2026-08-14T15:22:49Z",
        "html_url": (
            "https://github.com/praxys-run/praxys/pull/1#issuecomment-4"
        ),
        "user": {"login": "dddtc2005", "type": "User"},
    }]

    with pytest.raises(ValueError, match="explicit visible approval"):
        approvals_from_github_comments(
            science_dir,
            comments,
            {"dddtc2005": "admin"},
        )


def test_structured_comment_must_match_canonical_statement_exactly(
    tmp_path: Path,
) -> None:
    science_dir = tmp_path / "science"
    review, _ = _write_fixture_records(science_dir)
    registry = load_science_registry(science_dir)
    body = render_approval_comment_template(
        subject_kind=ReviewSubjectKind.EVIDENCE_REVIEW,
        subject_id=review.id,
        subject_digest=evidence_review_digest(review),
        role=ReviewRole.EVIDENCE_REVIEWER,
        approval_statement=approval_statement_for_subject(
            registry,
            subject_kind=ReviewSubjectKind.EVIDENCE_REVIEW,
            subject_id=review.id,
            role=ReviewRole.EVIDENCE_REVIEWER,
        ),
    )
    comment = {
        "id": 5,
        "body": body + "\n\nActually, do not approve this.",
        "created_at": "2026-08-14T15:22:49Z",
        "html_url": (
            "https://github.com/praxys-run/praxys/pull/1#issuecomment-5"
        ),
        "user": {"login": "dddtc2005", "type": "User"},
    }

    with pytest.raises(ValueError, match="canonical statement"):
        approvals_from_github_comments(
            science_dir,
            [comment],
            {"dddtc2005": "admin"},
        )


def test_negated_legacy_phrase_is_not_approval(tmp_path: Path) -> None:
    science_dir = tmp_path / "science"
    review, _ = _write_fixture_records(science_dir)
    comment = {
        "id": 6,
        "body": (
            "Do not record this: Maintainer evidence review — "
            "**Approve Evidence Review** for evidence digest "
            f"`{evidence_review_digest(review)}`."
        ),
        "created_at": "2026-08-14T15:22:49Z",
        "html_url": (
            "https://github.com/praxys-run/praxys/pull/1#issuecomment-6"
        ),
        "user": {"login": "dddtc2005", "type": "User"},
    }

    assert approvals_from_github_comments(
        science_dir,
        [comment],
        {"dddtc2005": "admin"},
    ) == []


def test_materialization_accepts_records_but_keeps_runtime_inactive(
    tmp_path: Path,
) -> None:
    science_dir = tmp_path / "science"
    review, decision = _write_fixture_records(science_dir)
    approvals = [
        _approval(
            subject_kind=ReviewSubjectKind.EVIDENCE_REVIEW,
            subject_id=review.id,
            subject_digest=evidence_review_digest(review),
            role=ReviewRole.EVIDENCE_REVIEWER,
            source_ref=(
                "https://github.com/praxys-run/praxys/pull/1"
                "#issuecomment-10"
            ),
        ),
        _approval(
            subject_kind=ReviewSubjectKind.SCIENCE_DECISION,
            subject_id=decision.id,
            subject_digest=science_decision_digest(decision),
            role=ReviewRole.DECISION_APPROVER,
            source_ref=(
                "https://github.com/praxys-run/praxys/pull/1"
                "#issuecomment-11"
            ),
        ),
    ]

    changed = materialize_science_approvals(science_dir, approvals)
    registry = load_science_registry(science_dir)
    contract = build_policy_contract(registry, decision.id)

    assert registry.evidence_reviews[review.id].status == RecordStatus.ACCEPTED
    assert registry.evidence_reviews[review.id].reviewed_on == date(2026, 8, 14)
    assert registry.decisions[decision.id].status == RecordStatus.ACCEPTED
    assert contract.runtime_state == ArtifactRuntimeState.INACTIVE
    assert {approval.role for approval in load_science_approvals(science_dir)} == {
        ReviewRole.EVIDENCE_REVIEWER,
        ReviewRole.DECISION_APPROVER,
    }
    assert Path("REGISTRY.md") in changed
    assert any(path.parts[0] == "approvals" for path in changed)
    assert materialize_science_approvals(science_dir, approvals) == []


def test_verifier_requires_new_artifacts_to_match_authenticated_comments(
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "base"
    review, decision = _write_fixture_records(base_dir)
    head_dir = tmp_path / "head"
    shutil.copytree(base_dir, head_dir)
    approvals = [
        _approval(
            subject_kind=ReviewSubjectKind.EVIDENCE_REVIEW,
            subject_id=review.id,
            subject_digest=evidence_review_digest(review),
            role=ReviewRole.EVIDENCE_REVIEWER,
            source_ref=(
                "https://github.com/praxys-run/praxys/pull/1"
                "#issuecomment-10"
            ),
        ),
        _approval(
            subject_kind=ReviewSubjectKind.SCIENCE_DECISION,
            subject_id=decision.id,
            subject_digest=science_decision_digest(decision),
            role=ReviewRole.DECISION_APPROVER,
            source_ref=(
                "https://github.com/praxys-run/praxys/pull/1"
                "#issuecomment-11"
            ),
        ),
    ]
    materialize_science_approvals(head_dir, approvals)
    comments = [
        {
            "id": 10,
            "body": _legacy_evidence_comment(
                evidence_review_digest(review)
            ),
            "created_at": "2026-08-14T15:20:49Z",
            "html_url": str(approvals[0].source_ref),
            "user": {"login": "dddtc2005", "type": "User"},
        },
        {
            "id": 11,
            "body": _legacy_decision_comment(
                science_decision_digest(decision)
            ),
            "created_at": "2026-08-14T15:21:49Z",
            "html_url": str(approvals[1].source_ref),
            "user": {"login": "dddtc2005", "type": "User"},
        },
    ]

    verify_science_approval_changes(
        base_dir,
        head_dir,
        comments,
        {"dddtc2005": "admin"},
    )
    with pytest.raises(ValueError, match="not backed by"):
        verify_science_approval_changes(
            base_dir,
            head_dir,
            [],
            {},
        )


def test_verifier_rejects_tampered_generated_packet(
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "base"
    review, decision = _write_fixture_records(base_dir)
    head_dir = tmp_path / "head"
    shutil.copytree(base_dir, head_dir)
    approvals = [
        _approval(
            subject_kind=ReviewSubjectKind.EVIDENCE_REVIEW,
            subject_id=review.id,
            subject_digest=evidence_review_digest(review),
            role=ReviewRole.EVIDENCE_REVIEWER,
            source_ref=(
                "https://github.com/praxys-run/praxys/pull/1"
                "#issuecomment-10"
            ),
        ),
        _approval(
            subject_kind=ReviewSubjectKind.SCIENCE_DECISION,
            subject_id=decision.id,
            subject_digest=science_decision_digest(decision),
            role=ReviewRole.DECISION_APPROVER,
            source_ref=(
                "https://github.com/praxys-run/praxys/pull/1"
                "#issuecomment-11"
            ),
        ),
    ]
    materialize_science_approvals(head_dir, approvals)
    packet = (
        head_dir
        / "generated"
        / "review-packets"
        / f"{decision.id}.md"
    )
    packet.write_text("tampered\n", encoding="utf-8")
    comments = [
        {
            "id": 10,
            "body": _legacy_evidence_comment(
                evidence_review_digest(review)
            ),
            "created_at": "2026-08-14T15:20:49Z",
            "html_url": str(approvals[0].source_ref),
            "user": {"login": "dddtc2005", "type": "User"},
        },
        {
            "id": 11,
            "body": _legacy_decision_comment(
                science_decision_digest(decision)
            ),
            "created_at": "2026-08-14T15:21:49Z",
            "html_url": str(approvals[1].source_ref),
            "user": {"login": "dddtc2005", "type": "User"},
        },
    ]

    with pytest.raises(ValueError, match="stale paths"):
        verify_science_approval_changes(
            base_dir,
            head_dir,
            comments,
            {"dddtc2005": "admin"},
        )


def test_verifier_blocks_unbound_implementation_approval(
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "base"
    review, decision = _write_fixture_records(base_dir)
    materialize_science_approvals(
        base_dir,
        [
            _approval(
                subject_kind=ReviewSubjectKind.EVIDENCE_REVIEW,
                subject_id=review.id,
                subject_digest=evidence_review_digest(review),
                role=ReviewRole.EVIDENCE_REVIEWER,
                source_ref=(
                    "https://github.com/praxys-run/praxys/pull/1"
                    "#issuecomment-10"
                ),
            ),
            _approval(
                subject_kind=ReviewSubjectKind.SCIENCE_DECISION,
                subject_id=decision.id,
                subject_digest=science_decision_digest(decision),
                role=ReviewRole.DECISION_APPROVER,
                source_ref=(
                    "https://github.com/praxys-run/praxys/pull/1"
                    "#issuecomment-11"
                ),
            ),
        ],
    )
    head_dir = tmp_path / "head"
    shutil.copytree(base_dir, head_dir)
    registry = load_science_registry(head_dir)
    contract = build_policy_contract(registry, decision.id)
    implementation = _approval(
        subject_kind=ReviewSubjectKind.IMPLEMENTATION_CONTRACT,
        subject_id=decision.id,
        subject_digest=contract.contract_digest,
        role=ReviewRole.IMPLEMENTATION_REVIEWER,
        source_ref=(
            "https://github.com/praxys-run/praxys/pull/1"
            "#issuecomment-12"
        ),
    )
    _write_yaml(
        head_dir / "approvals" / "implementation.yaml",
        implementation.model_dump(mode="json"),
    )
    load_science_registry(head_dir)

    with pytest.raises(ValueError, match="code-bound review mechanism"):
        verify_science_approval_changes(
            base_dir,
            head_dir,
            [],
            {},
        )


def test_materialization_is_atomic_when_digest_is_stale(
    tmp_path: Path,
) -> None:
    science_dir = tmp_path / "science"
    review, _ = _write_fixture_records(science_dir)
    stale = _approval(
        subject_kind=ReviewSubjectKind.EVIDENCE_REVIEW,
        subject_id=review.id,
        subject_digest=f"sha256:{'0' * 64}",
        role=ReviewRole.EVIDENCE_REVIEWER,
        source_ref=(
            "https://github.com/praxys-run/praxys/pull/1"
            "#issuecomment-10"
        ),
    )

    with pytest.raises(ValueError, match="stale"):
        materialize_science_approvals(science_dir, [stale])

    registry = load_science_registry(science_dir)
    assert registry.evidence_reviews[review.id].status == RecordStatus.DRAFT
    assert not (science_dir / "approvals").exists()


def test_decision_cannot_be_accepted_without_linked_evidence_approval(
    tmp_path: Path,
) -> None:
    science_dir = tmp_path / "science"
    _, decision = _write_fixture_records(science_dir)
    approval = _approval(
        subject_kind=ReviewSubjectKind.SCIENCE_DECISION,
        subject_id=decision.id,
        subject_digest=science_decision_digest(decision),
        role=ReviewRole.DECISION_APPROVER,
        source_ref=(
            "https://github.com/praxys-run/praxys/pull/1"
            "#issuecomment-11"
        ),
    )

    with pytest.raises(ValueError, match="uses non-accepted review"):
        materialize_science_approvals(science_dir, [approval])

    registry = load_science_registry(science_dir)
    assert registry.decisions[decision.id].status == RecordStatus.DRAFT


def test_workflow_uses_trusted_code_and_rechecks_the_exact_pr_head() -> None:
    workflow = _WORKFLOW.read_text(encoding="utf-8").replace("\r\n", "\n")

    assert "issue_comment:" in workflow
    assert "pull_request_target:" in workflow
    assert '"$GITHUB_EVENT_PATH"' in workflow
    assert "github.event_path" not in workflow
    assert "head.repo.full_name == $repository" in workflow
    assert 'any(.labels[]; .name == "science")' in workflow
    assert "compare/${default_sha}...${head_sha}" in workflow
    assert "waits until the PR contains current main" in workflow
    assert "path: trusted" in workflow
    assert "path: candidate" in workflow
    assert "actions/create-github-app-token@v3" in workflow
    assert "PRAXYS_REVIEW_POLICY_APP_SLUG" in workflow
    assert "verify_science_approval_sources.py" in workflow
    assert "python trusted/scripts/materialize_science_approvals.py" in workflow
    assert "python candidate/" not in workflow
    assert 'test "$(git -C candidate rev-parse HEAD)" = "$EXPECTED_HEAD_SHA"' in workflow
    assert 'current_head" != "$EXPECTED_HEAD_SHA"' in workflow
    assert "Approval automation changed disallowed path" in workflow
    assert "gh workflow run ci-premerge.yml" not in workflow
    assert "--force" not in workflow
    assert "--admin" not in workflow

    selective_review = _SELECTIVE_REVIEW_WORKFLOW.read_text(
        encoding="utf-8"
    ).replace("\r\n", "\n")
    assert "Verify authenticated science approvals" in selective_review
    assert "verify_science_approval_sources.py" in selective_review
    assert "path: approval-base" in selective_review
    assert "path: approval-head" in selective_review
