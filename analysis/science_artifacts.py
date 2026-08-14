"""Deterministic human-review and machine-contract science artifacts."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Annotated, Any, Literal

from pydantic import AnyHttpUrl, Field, JsonValue, model_validator
import yaml

from analysis.evidence_registry import (
    ApprovalMode,
    ArtifactRuntimeState,
    ClaimId,
    DecisionReviewDisposition,
    EvidenceReview,
    Identity,
    ParameterClassification,
    RecordId,
    RecordStatus,
    RegistryModel,
    ScienceDecisionRecord,
    ScienceRegistry,
)


_SCIENCE_DIR = Path(__file__).resolve().parents[1] / "data" / "science"
_REVIEW_PACKET_DIR = Path("generated") / "review-packets"
_CONTRACT_DIR = Path("generated") / "contracts"
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

Digest = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]


class ReviewSubjectKind(StrEnum):
    """Artifact type covered by one human attestation."""

    EVIDENCE_REVIEW = "evidence_review"
    SCIENCE_DECISION = "science_decision"
    IMPLEMENTATION_CONTRACT = "implementation_contract"


class ReviewRole(StrEnum):
    """Distinct responsibility carried by one human reviewer."""

    EVIDENCE_REVIEWER = "evidence_reviewer"
    DECISION_APPROVER = "decision_approver"
    IMPLEMENTATION_REVIEWER = "implementation_reviewer"


class ReviewScope(StrEnum):
    """Review surfaces that may be attested independently."""

    SEARCH_METHOD = "search_method"
    EVIDENCE_CLAIMS = "evidence_claims"
    CITATION_VERIFICATION = "citation_verification"
    LIMITATIONS_AND_GAPS = "limitations_and_gaps"
    DECISION_INTERPRETATION = "decision_interpretation"
    PARAMETERS = "parameters"
    APPLICABILITY = "applicability"
    CLAIM_LIMITS = "claim_limits"
    SAFETY_AND_PRIVACY = "safety_and_privacy"
    ACTIVATION_BOUNDARY = "activation_boundary"
    CONTRACT_MAPPING = "contract_mapping"
    RUNTIME_DIFF = "runtime_diff"
    VALIDATION = "validation"


_ROLE_SUBJECTS = {
    ReviewRole.EVIDENCE_REVIEWER: ReviewSubjectKind.EVIDENCE_REVIEW,
    ReviewRole.DECISION_APPROVER: ReviewSubjectKind.SCIENCE_DECISION,
    ReviewRole.IMPLEMENTATION_REVIEWER:
        ReviewSubjectKind.IMPLEMENTATION_CONTRACT,
}
_REQUIRED_SCOPES = {
    ReviewRole.EVIDENCE_REVIEWER: {
        ReviewScope.SEARCH_METHOD,
        ReviewScope.EVIDENCE_CLAIMS,
        ReviewScope.CITATION_VERIFICATION,
        ReviewScope.LIMITATIONS_AND_GAPS,
    },
    ReviewRole.DECISION_APPROVER: {
        ReviewScope.DECISION_INTERPRETATION,
        ReviewScope.PARAMETERS,
        ReviewScope.APPLICABILITY,
        ReviewScope.CLAIM_LIMITS,
        ReviewScope.SAFETY_AND_PRIVACY,
        ReviewScope.ACTIVATION_BOUNDARY,
    },
    ReviewRole.IMPLEMENTATION_REVIEWER: {
        ReviewScope.CONTRACT_MAPPING,
        ReviewScope.RUNTIME_DIFF,
        ReviewScope.VALIDATION,
    },
}


class ScienceApproval(RegistryModel):
    """One role-scoped human attestation bound to an immutable digest."""

    schema_version: Literal[1]
    subject_kind: ReviewSubjectKind
    subject_id: RecordId
    subject_digest: Digest
    reviewer: Identity
    role: ReviewRole
    reviewed_on: date
    scopes: list[ReviewScope] = Field(min_length=1)
    source_ref: AnyHttpUrl

    @model_validator(mode="after")
    def validate_role_and_scope(self) -> "ScienceApproval":
        """Require the role's exact subject type and complete review scope."""
        if not self.reviewer.startswith(("github:", "orcid:")):
            raise ValueError(
                "science approvals require an identified human reviewer"
            )
        if _ROLE_SUBJECTS[self.role] != self.subject_kind:
            raise ValueError(
                f"{self.role} cannot approve {self.subject_kind}"
            )
        missing = _REQUIRED_SCOPES[self.role] - set(self.scopes)
        if missing:
            raise ValueError(
                f"{self.role} approval is missing scopes: "
                f"{sorted(scope.value for scope in missing)}"
            )
        if len(self.scopes) != len(set(self.scopes)):
            raise ValueError("approval scopes must be unique")
        return self


class ContractParameter(RegistryModel):
    """Machine-consumable projection of one reviewed SDR parameter."""

    classification: ParameterClassification
    value: JsonValue
    evidence_claim_ids: list[ClaimId] = Field(default_factory=list)
    applies_to: str | None = None


class SciencePolicyContract(RegistryModel):
    """Generated policy contract consumed by implementation code."""

    schema_version: Literal[1]
    decision_id: RecordId
    decision_version: int = Field(ge=1)
    decision_status: RecordStatus
    model_version: str = Field(min_length=1)
    runtime_state: ArtifactRuntimeState
    source_decision_digest: Digest
    linked_evidence_digests: dict[str, Digest]
    evidence_review_ids: list[RecordId] = Field(min_length=1)
    evidence_claim_ids: list[ClaimId] = Field(min_length=1)
    affected_models: list[str] = Field(min_length=1)
    parameters: dict[str, ContractParameter]
    contract_digest: Digest

    @model_validator(mode="after")
    def validate_contract_digest(self) -> "SciencePolicyContract":
        """Reject a contract whose embedded digest does not match its payload."""
        payload = self.model_dump(
            mode="json",
            exclude={"contract_digest"},
        )
        expected = digest_payload(payload)
        if self.contract_digest != expected:
            raise ValueError("contract_digest does not match contract payload")
        return self

    @property
    def parameter_values(self) -> dict[str, JsonValue]:
        """Return the exact reviewed parameter values for code consumption."""
        return {
            name: parameter.value
            for name, parameter in self.parameters.items()
        }


def digest_payload(payload: Any) -> str:
    """Return a stable SHA-256 digest for canonical JSON-compatible data."""
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{sha256(canonical).hexdigest()}"


def evidence_review_payload(review: EvidenceReview) -> dict[str, Any]:
    """Return the complete human-reviewed evidence content without lifecycle."""
    return review.model_dump(
        mode="json",
        exclude={
            "approval_mode",
            "human_reviewers",
            "reviewed_on",
            "status",
            "superseded_by",
        },
    )


def science_decision_payload(
    decision: ScienceDecisionRecord,
) -> dict[str, Any]:
    """Return the complete human-reviewed decision content without lifecycle."""
    return decision.model_dump(
        mode="json",
        exclude={
            "approval_mode",
            "human_reviewers",
            "status",
            "superseded_by",
        },
    )


def evidence_review_digest(review: EvidenceReview) -> str:
    """Return the digest a human evidence review attestation must bind."""
    return digest_payload(evidence_review_payload(review))


def science_decision_digest(decision: ScienceDecisionRecord) -> str:
    """Return the digest a human decision approval must bind."""
    return digest_payload(science_decision_payload(decision))


def build_policy_contract(
    registry: ScienceRegistry,
    decision_id: str,
) -> SciencePolicyContract:
    """Compile one artifact-mode SDR into a deterministic machine contract."""
    decision = registry.decisions[decision_id]
    if decision.approval_mode != ApprovalMode.ARTIFACT:
        raise ValueError(
            f"Decision {decision_id} does not use artifact review mode"
        )
    if decision.artifact_policy is None:
        raise ValueError(f"Decision {decision_id} lacks artifact_policy")

    payload = {
        "schema_version": 1,
        "decision_id": decision.id,
        "decision_version": decision.version,
        "decision_status": decision.status.value,
        "model_version": decision.model_version,
        "runtime_state": decision.artifact_policy.runtime_state.value,
        "source_decision_digest": science_decision_digest(decision),
        "linked_evidence_digests": {
            review_id: evidence_review_digest(
                registry.evidence_reviews[review_id]
            )
            for review_id in decision.evidence_review_ids
        },
        "evidence_review_ids": decision.evidence_review_ids,
        "evidence_claim_ids": decision.evidence_claim_ids,
        "affected_models": decision.affected_surfaces.models,
        "parameters": {
            parameter.name: {
                "classification": parameter.classification.value,
                "value": parameter.value,
                "evidence_claim_ids": parameter.evidence_claim_ids,
                "applies_to": parameter.applies_to,
            }
            for parameter in decision.model_parameters
        },
    }
    return SciencePolicyContract.model_validate({
        **payload,
        "contract_digest": digest_payload(payload),
    })


def render_policy_contract_json(contract: SciencePolicyContract) -> str:
    """Render one contract as stable, pretty JSON."""
    return json.dumps(
        contract.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def load_science_approvals(
    science_dir: str | Path,
) -> list[ScienceApproval]:
    """Load role-scoped approval artifacts in deterministic path order."""
    approval_dir = Path(science_dir) / "approvals"
    if not approval_dir.is_dir():
        return []
    approvals: list[ScienceApproval] = []
    for path in sorted(
        [*approval_dir.rglob("*.yaml"), *approval_dir.rglob("*.yml")],
        key=lambda item: item.as_posix(),
    ):
        with path.open(encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
        if not isinstance(raw, dict):
            raise ValueError(f"Science approval must be a mapping: {path}")
        approvals.append(ScienceApproval.model_validate(raw))
    return approvals


def validate_registry_approvals(registry: ScienceRegistry) -> None:
    """Validate approval subjects, roles, scopes, and bound digests."""
    approvals = load_science_approvals(registry.science_dir)
    seen: set[tuple[str, str, str]] = set()
    for approval in approvals:
        key = (
            approval.subject_kind.value,
            approval.subject_id,
            f"{approval.role.value}:{approval.reviewer}",
        )
        if key in seen:
            raise ValueError(
                "Duplicate science approval for "
                f"{approval.subject_id}, {approval.role}, {approval.reviewer}"
            )
        seen.add(key)
        expected = _approval_subject_digest(registry, approval)
        if approval.subject_digest != expected:
            raise ValueError(
                f"Science approval for {approval.subject_id} is stale: "
                f"expected {expected}, got {approval.subject_digest}"
            )

    for review in registry.evidence_reviews.values():
        if (
            review.approval_mode == ApprovalMode.ARTIFACT
            and review.status in {RecordStatus.ACCEPTED, RecordStatus.SUPERSEDED}
            and not _has_approval(
                approvals,
                ReviewSubjectKind.EVIDENCE_REVIEW,
                review.id,
                ReviewRole.EVIDENCE_REVIEWER,
            )
        ):
            raise ValueError(
                f"Accepted evidence review {review.id} requires an "
                "evidence_reviewer approval artifact"
            )

    for decision in registry.decisions.values():
        if decision.approval_mode != ApprovalMode.ARTIFACT:
            continue
        if (
            decision.status in {RecordStatus.ACCEPTED, RecordStatus.SUPERSEDED}
            and not _has_approval(
                approvals,
                ReviewSubjectKind.SCIENCE_DECISION,
                decision.id,
                ReviewRole.DECISION_APPROVER,
            )
        ):
            raise ValueError(
                f"Accepted science decision {decision.id} requires a "
                "decision_approver approval artifact"
            )
        if (
            decision.artifact_policy is not None
            and decision.artifact_policy.runtime_state
            == ArtifactRuntimeState.ACTIVE
            and not _has_approval(
                approvals,
                ReviewSubjectKind.IMPLEMENTATION_CONTRACT,
                decision.id,
                ReviewRole.IMPLEMENTATION_REVIEWER,
            )
        ):
            raise ValueError(
                f"Active implementation contract {decision.id} requires an "
                "implementation_reviewer approval artifact"
            )


def _approval_subject_digest(
    registry: ScienceRegistry,
    approval: ScienceApproval,
) -> str:
    """Resolve the current digest for one approval subject."""
    if approval.subject_kind == ReviewSubjectKind.EVIDENCE_REVIEW:
        if approval.subject_id not in registry.evidence_reviews:
            raise ValueError(
                f"Approval references unknown evidence review "
                f"{approval.subject_id}"
            )
        review = registry.evidence_reviews[approval.subject_id]
        if review.approval_mode != ApprovalMode.ARTIFACT:
            raise ValueError(
                f"Approval subject {approval.subject_id} uses legacy review mode"
            )
        if review.status not in {RecordStatus.ACCEPTED, RecordStatus.SUPERSEDED}:
            raise ValueError(
                f"Evidence approval subject {approval.subject_id} is not accepted"
            )
        if approval.reviewed_on < review.created_on:
            raise ValueError(
                f"Evidence approval for {approval.subject_id} predates the record"
            )
        return evidence_review_digest(review)

    if approval.subject_id not in registry.decisions:
        raise ValueError(
            f"Approval references unknown science decision {approval.subject_id}"
        )
    decision = registry.decisions[approval.subject_id]
    if decision.approval_mode != ApprovalMode.ARTIFACT:
        raise ValueError(
            f"Approval subject {approval.subject_id} uses legacy review mode"
        )
    if decision.status not in {RecordStatus.ACCEPTED, RecordStatus.SUPERSEDED}:
        raise ValueError(
            f"Decision approval subject {approval.subject_id} is not accepted"
        )
    if approval.reviewed_on < decision.decision_date:
        raise ValueError(
            f"Science approval for {approval.subject_id} predates the decision"
        )
    if approval.subject_kind == ReviewSubjectKind.SCIENCE_DECISION:
        return science_decision_digest(decision)
    return build_policy_contract(registry, decision.id).contract_digest


def _has_approval(
    approvals: list[ScienceApproval],
    subject_kind: ReviewSubjectKind,
    subject_id: str,
    role: ReviewRole,
) -> bool:
    """Return whether the exact role has approved the exact subject."""
    return any(
        approval.subject_kind == subject_kind
        and approval.subject_id == subject_id
        and approval.role == role
        for approval in approvals
    )


def render_evidence_review_packet(
    registry: ScienceRegistry,
    review_id: str,
) -> str:
    """Render all evidence-review content into a human review packet."""
    review = registry.evidence_reviews[review_id]
    digest = evidence_review_digest(review)
    approvals = load_science_approvals(registry.science_dir)
    lines = [
        f"# Evidence review packet: {review.title}",
        "",
        "> Generated from the canonical Evidence Review. Review this packet, "
        "not the raw YAML. Any source change invalidates the digest below.",
        "",
        f"- **Record:** `{review.id}`",
        f"- **Lifecycle:** `{review.status.value}`",
        f"- **Review mode:** `{review.approval_mode.value}`",
        f"- **Reviewed content digest:** `{digest}`",
        f"- **Required role:** `{ReviewRole.EVIDENCE_REVIEWER.value}`",
        f"- **Approval:** {_approval_label(approvals, review.id, ReviewRole.EVIDENCE_REVIEWER)}",
        "",
        "## Approval artifact template",
        "",
        "Create this only after a human completes the packet review:",
        "",
        "```yaml",
        _render_approval_template(
            subject_kind=ReviewSubjectKind.EVIDENCE_REVIEW,
            subject_id=review.id,
            subject_digest=digest,
            role=ReviewRole.EVIDENCE_REVIEWER,
        ),
        "```",
        "",
        "## Question and product purpose",
        "",
        review.research_question,
        "",
        review.intended_product_purpose,
        "",
        "## Scope",
        "",
    ]
    lines.extend(_render_named_lists({
        "Population": review.scope.population,
        "Intervention or exposure": review.scope.intervention_or_exposure,
        "Comparator": review.scope.comparator,
        "Outcomes": review.scope.outcomes,
    }))
    lines.extend([
        "## Review method",
        "",
        f"- **Type:** `{review.method.review_type.value}`",
        f"- **Search date:** `{review.method.search_date.isoformat()}`",
        "",
        "### Exact searches",
        "",
    ])
    for source in review.method.sources:
        lines.extend([
            f"- **{source.name}**",
            f"  - `{source.search_string}`",
        ])
    lines.extend([""])
    lines.extend(_render_named_lists({
        "Inclusion criteria": review.method.inclusion_criteria,
        "Exclusion criteria": review.method.exclusion_criteria,
        "Method limitations": review.method.method_limitations,
    }))
    if review.method.quality_appraisal:
        lines.extend([
            "### Quality appraisal",
            "",
            review.method.quality_appraisal,
            "",
        ])

    lines.extend(["## Claims", ""])
    for claim in review.claims:
        lines.extend([
            f"### `{claim.id}` — {claim.evidence_strength.value}",
            "",
            claim.statement,
            "",
            f"- **Sources:** {', '.join(f'`{item}`' for item in claim.source_ids)}",
            f"- **Population:** {'; '.join(claim.applicable_population)}",
            f"- **Domain:** {'; '.join(claim.domain)}",
            "- **Limitations:**",
        ])
        lines.extend(f"  - {item}" for item in claim.limitations)
        if claim.effect_estimates:
            lines.extend(["- **Verified effect estimates:**"])
            for estimate in claim.effect_estimates:
                lines.append(
                    "  - "
                    + _render_effect_estimate(estimate.model_dump(mode="json"))
                )
        lines.extend([""])

    verification = _verification_levels(review)
    lines.extend([
        "## Citations and verification level",
        "",
        "| ID | Verification | Stable identifier | Citation |",
        "|---|---|---|---|",
    ])
    for citation in review.citations:
        identifier = (
            f"DOI `{citation.doi}`"
            if citation.doi
            else f"PMID `{citation.pmid}`"
            if citation.pmid
            else str(citation.url)
        )
        title = citation.title.replace("|", r"\|")
        lines.append(
            f"| `{citation.id}` | `{verification.get(citation.id, 'missing')}` "
            f"| {identifier} | {title} ({citation.year}) |"
        )
    lines.extend([""])
    lines.extend(_render_named_lists({
        "Known gaps": review.known_gaps,
        "Conflicting findings": review.conflicting_findings,
        "Follow-up questions": review.follow_up_questions,
    }))
    lines.extend(_render_exact_payload(
        "Exact reviewed evidence payload",
        evidence_review_payload(review),
    ))
    return "\n".join(lines).rstrip() + "\n"


def render_decision_review_packet(
    registry: ScienceRegistry,
    decision_id: str,
) -> str:
    """Render an action-oriented decision sheet plus a complete audit appendix."""
    decision = registry.decisions[decision_id]
    if decision.decision_review is None:
        raise ValueError(
            f"Artifact decision {decision_id} has no decision review manifest"
        )
    contract = build_policy_contract(registry, decision_id)
    approvals = load_science_approvals(registry.science_dir)
    lines = [
        f"# Science decision review packet: {decision.title}",
        "",
        "> Start with the decision sheet. The audit appendix preserves every "
        "code-consumed field, but it is not the reviewer's primary task.",
        "",
        f"- **Record:** `{decision.id}`",
        f"- **Lifecycle:** `{decision.status.value}`",
        f"- **Model version:** `{decision.model_version}`",
        f"- **Runtime state:** `{contract.runtime_state.value}`",
        f"- **Decision digest:** `{contract.source_decision_digest}`",
        f"- **Contract digest:** `{contract.contract_digest}`",
        f"- **Required decision role:** `{ReviewRole.DECISION_APPROVER.value}`",
        "- **Decision approval:** "
        + _approval_label(
            approvals,
            decision.id,
            ReviewRole.DECISION_APPROVER,
        ),
        f"- **Required activation role:** `{ReviewRole.IMPLEMENTATION_REVIEWER.value}`",
        "- **Implementation approval:** "
        + _approval_label(
            approvals,
            decision.id,
            ReviewRole.IMPLEMENTATION_REVIEWER,
        ),
        "",
        "## Your task",
        "",
        decision.decision_review.reviewer_task,
        "",
        "Choose one outcome:",
        "",
        "1. **Approve the decision sheet as a unit.** This accepts both the "
        "proposed decisions and the explicit deferrals below.",
        "2. **Request changes by item ID.** Do this when any proposal, effect, "
        "or non-authorization is unclear or wrong.",
        "",
        "Do not approve merely because the audit appendix looks reasonable or "
        "because you found no obvious problem while skimming it.",
        "",
        "## Decision sheet",
        "",
    ]
    section_headings = {
        DecisionReviewDisposition.APPROVE:
            "Proposed decisions to approve",
        DecisionReviewDisposition.DEFER:
            "Decisions explicitly deferred",
    }
    for disposition, heading in section_headings.items():
        items = [
            item
            for item in decision.decision_review.items
            if item.disposition == disposition
        ]
        if not items:
            continue
        lines.extend([f"### {heading}", ""])
        for item in items:
            lines.extend([
                f"#### `{item.id}` — {item.title}",
                "",
                f"- **Question:** {item.question}",
                f"- **Proposed decision:** {item.proposed_decision}",
                "- **Approval means:**",
            ])
            lines.extend(
                f"  - {effect}"
                for effect in item.approval_effect
            )
            lines.append("- **This does not authorize:**")
            lines.extend(
                f"  - {boundary}"
                for boundary in item.does_not_authorize
            )
            lines.extend([
                "",
                "<details><summary>Traceability: "
                f"{len(item.parameter_names)} contract groups, "
                f"{len(item.evidence_claim_ids)} evidence claims</summary>",
                "",
                "- **Contract groups covered:** "
                + ", ".join(
                    f"`{parameter_name}`"
                    for parameter_name in item.parameter_names
                ),
                "- **Evidence claims:** "
                + (
                    ", ".join(
                        f"`{claim_id}`"
                        for claim_id in item.evidence_claim_ids
                    )
                    or "_None; product or lifecycle boundary only_"
                ),
                "",
                "</details>",
                "",
            ])

    lines.extend([
        "## Approval statement",
        "",
        "A decision approval bound to the displayed digest attests:",
        "",
        f"> {decision.decision_review.approval_statement}",
        "",
        f"- **Decision approval:** {_approval_label(approvals, decision.id, ReviewRole.DECISION_APPROVER)}",
        "",
        "### Decision approval artifact template",
        "",
        "Create this only after a human can make the approval statement above:",
        "",
        "```yaml",
        _render_approval_template(
            subject_kind=ReviewSubjectKind.SCIENCE_DECISION,
            subject_id=decision.id,
            subject_digest=contract.source_decision_digest,
            role=ReviewRole.DECISION_APPROVER,
        ),
        "```",
        "",
        "## Audit appendix",
        "",
        "<details><summary>Evidence, parameters, alternatives, limits, and validation</summary>",
        "",
        "### Accepted interpretation",
        "",
        decision.accepted_interpretation,
        "",
        "### Linked evidence",
        "",
    ])
    for claim_id in decision.evidence_claim_ids:
        claim = registry.claims[claim_id]
        review_id = registry.claim_review_ids[claim_id]
        lines.extend([
            f"#### `{claim.id}` — {claim.evidence_strength.value}",
            "",
            claim.statement,
            "",
            f"- **Evidence Review:** `{review_id}`",
            f"- **Sources:** {', '.join(f'`{item}`' for item in claim.source_ids)}",
            f"- **Limitations:** {'; '.join(claim.limitations)}",
            "",
        ])

    lines.extend(["### Reviewed parameters", ""])
    for parameter in decision.model_parameters:
        lines.extend([
            f"#### `{parameter.name}` — {parameter.classification.value}",
            "",
            f"- **Applies to:** {parameter.applies_to or '_Not specified_'}",
            "- **Evidence claims:** "
            + (
                ", ".join(
                    f"`{item}`"
                    for item in parameter.evidence_claim_ids
                )
                or "_None; product rationale only_"
            ),
            f"- **Rationale:** {parameter.rationale or '_Published value; see linked claims_'}",
            "- **Exact value:**",
            "",
            "```json",
            json.dumps(
                parameter.value,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
        ])

    lines.extend(["### Rejected alternatives", ""])
    for alternative in decision.rejected_alternatives:
        lines.extend([
            f"#### {alternative.alternative}",
            "",
            alternative.rationale,
            "",
        ])
    lines.extend(_render_named_lists({
        "Applicability": decision.applicability,
        "User-facing claim limits": decision.user_facing_claim_limits,
        "Safety implications": decision.safety_implications,
        "Privacy implications": decision.privacy_implications,
        "Validation plan": decision.validation_plan,
        "Falsification conditions": decision.falsification_conditions,
        "Decision notes": decision.decision_notes,
    }, heading_level=3))
    lines.extend([
        "</details>",
        "",
    ])
    lines.extend(_render_exact_payload(
        "Exact machine contract — code consumption audit",
        contract.model_dump(mode="json"),
    ))
    lines.extend([
        "<details><summary>Implementation approval template — not part of decision approval</summary>",
        "",
        "Create this only after code matches an accepted contract and runtime "
        "activation is separately approved:",
        "",
        "```yaml",
        _render_approval_template(
            subject_kind=ReviewSubjectKind.IMPLEMENTATION_CONTRACT,
            subject_id=decision.id,
            subject_digest=contract.contract_digest,
            role=ReviewRole.IMPLEMENTATION_REVIEWER,
        ),
        "```",
        "",
        "</details>",
        "",
    ])
    lines.extend(_render_exact_payload(
        "Exact reviewed decision payload",
        science_decision_payload(decision),
    ))
    return "\n".join(lines).rstrip() + "\n"


def expected_science_artifacts(
    registry: ScienceRegistry,
) -> dict[Path, str]:
    """Return every generated artifact required by artifact-mode records."""
    expected: dict[Path, str] = {}
    for review in sorted(
        registry.evidence_reviews.values(),
        key=lambda item: item.id,
    ):
        if review.approval_mode != ApprovalMode.ARTIFACT:
            continue
        expected[_REVIEW_PACKET_DIR / f"{review.id}.md"] = (
            render_evidence_review_packet(registry, review.id)
        )
    for decision in sorted(
        registry.decisions.values(),
        key=lambda item: item.id,
    ):
        if decision.approval_mode != ApprovalMode.ARTIFACT:
            continue
        contract = build_policy_contract(registry, decision.id)
        expected[_REVIEW_PACKET_DIR / f"{decision.id}.md"] = (
            render_decision_review_packet(registry, decision.id)
        )
        expected[_CONTRACT_DIR / f"{decision.id}.json"] = (
            render_policy_contract_json(contract)
        )
    return expected


def sync_science_artifacts(
    registry: ScienceRegistry,
    *,
    check: bool,
) -> list[Path]:
    """Write generated artifacts or return stale paths in check mode."""
    expected = expected_science_artifacts(registry)
    science_dir = registry.science_dir
    existing = {
        path.relative_to(science_dir)
        for directory, suffix in (
            (science_dir / _REVIEW_PACKET_DIR, ".md"),
            (science_dir / _CONTRACT_DIR, ".json"),
        )
        if directory.is_dir()
        for path in directory.glob(f"*{suffix}")
    }
    stale: list[Path] = []
    for relative, content in expected.items():
        target = science_dir / relative
        current = target.read_text(encoding="utf-8") if target.exists() else None
        if current != content:
            stale.append(relative)
            if not check:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8", newline="\n")
    for relative in sorted(existing - set(expected)):
        stale.append(relative)
        if not check:
            (science_dir / relative).unlink()
    return sorted(set(stale), key=lambda path: path.as_posix())


def load_policy_contract(
    decision_id: str,
    *,
    science_dir: str | Path | None = None,
    require_active: bool = False,
) -> SciencePolicyContract:
    """Load a generated contract and verify it against its canonical source."""
    root = Path(science_dir) if science_dir is not None else _SCIENCE_DIR
    path = root / _CONTRACT_DIR / f"{decision_id}.json"
    with path.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    contract = SciencePolicyContract.model_validate(raw)

    from analysis.evidence_registry import load_science_registry

    registry = load_science_registry(root)
    expected = build_policy_contract(registry, decision_id)
    if contract != expected:
        raise ValueError(
            f"Generated science contract {decision_id} is stale"
        )
    if require_active:
        if contract.decision_status != RecordStatus.ACCEPTED:
            raise ValueError(
                f"Science contract {decision_id} is not accepted"
            )
        if contract.runtime_state != ArtifactRuntimeState.ACTIVE:
            raise ValueError(
                f"Science contract {decision_id} is not active"
            )
    return contract


def _approval_label(
    approvals: list[ScienceApproval],
    subject_id: str,
    role: ReviewRole,
) -> str:
    matches = [
        approval
        for approval in approvals
        if approval.subject_id == subject_id and approval.role == role
    ]
    if not matches:
        return "_Pending_"
    return "; ".join(
        f"`{item.reviewer}` on `{item.reviewed_on.isoformat()}` "
        f"([source]({item.source_ref}))"
        for item in matches
    )


def _verification_levels(review: EvidenceReview) -> dict[str, str]:
    levels: dict[str, str] = {}
    for note in review.review_notes:
        if not note.startswith("Verification: "):
            continue
        prefix = note.split(";", 1)[0]
        marker = prefix.removeprefix("Verification: ")
        citation_id, separator, level = marker.partition(" - ")
        if separator:
            levels[citation_id] = level
    return levels


def _render_named_lists(
    sections: dict[str, list[str]],
    *,
    heading_level: int = 2,
) -> list[str]:
    lines: list[str] = []
    for heading, values in sections.items():
        lines.extend([f"{'#' * heading_level} {heading}", ""])
        if values:
            lines.extend(f"- {value}" for value in values)
        else:
            lines.append("_None recorded._")
        lines.extend([""])
    return lines


def _render_effect_estimate(estimate: dict[str, Any]) -> str:
    if estimate.get("estimate") is not None:
        value = str(estimate["estimate"])
        if (
            estimate.get("range_low") is not None
            and estimate.get("range_high") is not None
        ):
            value += (
                f" (range {estimate['range_low']} to "
                f"{estimate['range_high']})"
            )
    else:
        value = f"{estimate['range_low']} to {estimate['range_high']}"
    return (
        f"{estimate['metric']}: {value} {estimate['unit']} "
        f"({estimate['context']})"
    )


def _render_exact_payload(
    title: str,
    payload: dict[str, Any],
) -> list[str]:
    return [
        f"<details><summary>{title}</summary>",
        "",
        "```json",
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        "```",
        "",
        "</details>",
        "",
    ]


def _render_approval_template(
    *,
    subject_kind: ReviewSubjectKind,
    subject_id: str,
    subject_digest: str,
    role: ReviewRole,
) -> str:
    payload = {
        "schema_version": 1,
        "subject_kind": subject_kind.value,
        "subject_id": subject_id,
        "subject_digest": subject_digest,
        "reviewer": "github:<reviewer>",
        "role": role.value,
        "reviewed_on": "<YYYY-MM-DD>",
        "scopes": [
            scope.value
            for scope in sorted(
                _REQUIRED_SCOPES[role],
                key=lambda item: item.value,
            )
        ],
        "source_ref": "<GitHub review URL>",
    }
    return yaml.safe_dump(payload, sort_keys=False).rstrip()


def is_digest(value: str) -> bool:
    """Return whether a value uses the canonical digest representation."""
    return _DIGEST_RE.fullmatch(value) is not None
