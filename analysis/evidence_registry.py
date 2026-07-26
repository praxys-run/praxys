"""Versioned evidence reviews and science decision records.

The registry keeps literature interpretation separate from localized theory
prose and implementation code. YAML records are strict, immutable review
artifacts; cross-record validation resolves claims, citations, decisions, and
supersession links before a shipped model can consume them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
import re
from typing import Annotated, Any, Iterable, Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)
import yaml


_SCIENCE_DIR = Path(__file__).resolve().parents[1] / "data" / "science"
_DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.IGNORECASE)
_PMID_RE = re.compile(r"^\d{1,9}$")
_DOI_HOSTS = {"doi.org", "www.doi.org", "dx.doi.org"}

Identity = Annotated[
    str,
    Field(pattern=r"^(?:agent|github|orcid|team):[A-Za-z0-9_.:/-]+$"),
]
RecordId = Annotated[
    str,
    Field(pattern=r"^(?:evidence|sdr)-[a-z0-9]+(?:-[a-z0-9]+)*-v[1-9]\d*$"),
]
ClaimId = Annotated[
    str,
    Field(pattern=r"^[a-z0-9]+(?:[.-][a-z0-9]+)+$"),
]
SourceId = Annotated[
    str,
    Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)+$"),
]


class RegistryModel(BaseModel):
    """Strict base model shared by all registry records."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


class RecordStatus(StrEnum):
    """Lifecycle state for immutable registry records."""

    DRAFT = "draft"
    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class ReviewType(StrEnum):
    """Depth of the documented literature review."""

    RAPID = "rapid"
    RIGOROUS = "rigorous"


class EvidenceStrength(StrEnum):
    """Conservative confidence label for an evidence claim."""

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    VERY_LOW = "very_low"


class ParameterClassification(StrEnum):
    """Whether an implementation value is published or a Praxys choice."""

    PUBLISHED = "published"
    ESTIMATE = "estimate"
    GUARDRAIL = "guardrail"


class CitationSource(RegistryModel):
    """Bibliographic metadata with syntax-validated stable identifiers."""

    id: SourceId
    title: str = Field(min_length=1)
    authors: list[str] = Field(min_length=1)
    year: int = Field(ge=1800, le=2100)
    journal: str = Field(min_length=1)
    doi: str | None = None
    pmid: str | None = None
    url: AnyHttpUrl | None = None

    @field_validator("doi")
    @classmethod
    def validate_doi(cls, value: str | None) -> str | None:
        """Validate DOI syntax without claiming that the paper is correct."""
        if value is not None and not _DOI_RE.fullmatch(value):
            raise ValueError("doi must be a bare syntactically valid DOI")
        return value

    @field_validator("pmid")
    @classmethod
    def validate_pmid(cls, value: str | None) -> str | None:
        """Validate PMID syntax without performing an external lookup."""
        if value is not None and not _PMID_RE.fullmatch(value):
            raise ValueError("pmid must contain digits only")
        return value

    @model_validator(mode="after")
    def require_stable_identifier(self) -> "CitationSource":
        """Require one stable identifier and keep DOI URLs internally aligned."""
        if self.doi is None and self.pmid is None and self.url is None:
            raise ValueError("citation requires a DOI, PMID, or stable URL")
        if self.url is not None:
            host = (self.url.host or "").lower()
            if host in _DOI_HOSTS:
                if self.doi is None:
                    raise ValueError("doi.org URLs require the structured doi field")
                url_doi = self.url.path.lstrip("/")
                if url_doi.casefold() != self.doi.casefold():
                    raise ValueError("doi.org URL must match the doi field")
            path_parts = self.url.path.strip("/").split("/")
            is_pubmed_url = (
                host == "pubmed.ncbi.nlm.nih.gov"
                or (
                    host == "www.ncbi.nlm.nih.gov"
                    and path_parts[0] == "pubmed"
                )
            )
            if is_pubmed_url:
                url_pmid = (
                    path_parts[0]
                    if host == "pubmed.ncbi.nlm.nih.gov"
                    else path_parts[1]
                    if len(path_parts) == 2 and path_parts[0] == "pubmed"
                    else None
                )
                if url_pmid is None or not _PMID_RE.fullmatch(url_pmid):
                    raise ValueError("PubMed URLs must identify a numeric article")
                if self.pmid is None:
                    raise ValueError(
                        "PubMed URLs require the structured pmid field"
                    )
                if url_pmid != self.pmid:
                    raise ValueError("PubMed URL must match the pmid field")
        return self

    @property
    def stable_url(self) -> str:
        """Return the preferred stable URL for user-facing source links."""
        if self.doi is not None:
            return f"https://doi.org/{self.doi}"
        if self.pmid is not None:
            return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"
        if self.url is None:  # Protected by require_stable_identifier().
            raise ValueError(f"Citation {self.id} has no stable URL")
        return str(self.url)


class SearchSource(RegistryModel):
    """One database or source searched with its exact query."""

    name: str = Field(min_length=1)
    search_string: str = Field(min_length=1)


class ReviewMethod(RegistryModel):
    """Reproducible method metadata for rapid or rigorous reviews."""

    review_type: ReviewType
    search_date: date
    sources: list[SearchSource] = Field(min_length=1)
    inclusion_criteria: list[str] = Field(min_length=1)
    exclusion_criteria: list[str] = Field(min_length=1)
    quality_appraisal: str | None = None
    method_limitations: list[str] = Field(default_factory=list)


class EvidenceScope(RegistryModel):
    """Population, intervention/exposure, comparator, and outcomes."""

    population: list[str] = Field(min_length=1)
    intervention_or_exposure: list[str] = Field(min_length=1)
    comparator: list[str] = Field(min_length=1)
    outcomes: list[str] = Field(min_length=1)


class EffectEstimate(RegistryModel):
    """Structured effect estimate or range reported by a source."""

    metric: str = Field(min_length=1)
    estimate: float | None = None
    range_low: float | None = None
    range_high: float | None = None
    unit: str = Field(min_length=1)
    context: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_estimate(self) -> "EffectEstimate":
        """Require an estimate or complete, ordered range."""
        has_range = self.range_low is not None or self.range_high is not None
        if self.estimate is None and not has_range:
            raise ValueError("effect estimate requires an estimate or range")
        if has_range and (self.range_low is None or self.range_high is None):
            raise ValueError("effect range requires both low and high values")
        if (
            self.range_low is not None
            and self.range_high is not None
            and self.range_low > self.range_high
        ):
            raise ValueError("effect range low must not exceed high")
        return self


class EvidenceClaim(RegistryModel):
    """A bounded claim supported by identified sources."""

    id: ClaimId
    statement: str = Field(min_length=1)
    source_ids: list[SourceId] = Field(min_length=1)
    evidence_strength: EvidenceStrength
    effect_estimates: list[EffectEstimate] = Field(default_factory=list)
    applicable_population: list[str] = Field(min_length=1)
    domain: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)


class EvidenceReview(RegistryModel):
    """Versioned record of what a literature review supports."""

    schema_version: Literal[1]
    id: RecordId
    version: int = Field(ge=1)
    title: str = Field(min_length=1)
    research_question: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    status: RecordStatus
    authors: list[Identity] = Field(min_length=1)
    human_reviewers: list[Identity] = Field(default_factory=list)
    created_on: date
    reviewed_on: date | None = None
    intended_product_purpose: str = Field(min_length=1)
    scope: EvidenceScope
    method: ReviewMethod
    claims: list[EvidenceClaim] = Field(min_length=1)
    citations: list[CitationSource] = Field(min_length=1)
    known_gaps: list[str] = Field(default_factory=list)
    conflicting_findings: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    supersedes: list[RecordId] = Field(default_factory=list)
    superseded_by: RecordId | None = None
    review_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_record(self) -> "EvidenceReview":
        """Validate version identity, local uniqueness, and human acceptance."""
        if not self.id.startswith("evidence-"):
            raise ValueError("evidence review IDs must start with evidence-")
        if not self.id.endswith(f"-v{self.version}"):
            raise ValueError("record id suffix must match version")
        claim_ids = [claim.id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("evidence claim IDs must be unique within a review")
        source_ids = [source.id for source in self.citations]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("citation IDs must be unique within a review")
        if self.reviewed_on is not None and self.reviewed_on < self.created_on:
            raise ValueError("reviewed_on must not predate created_on")
        if self.status in {RecordStatus.ACCEPTED, RecordStatus.SUPERSEDED}:
            _require_human_review(self.human_reviewers, self.reviewed_on)
        if self.status == RecordStatus.SUPERSEDED and self.superseded_by is None:
            raise ValueError("superseded records require superseded_by")
        if self.status != RecordStatus.SUPERSEDED and self.superseded_by is not None:
            raise ValueError("only superseded records may set superseded_by")
        return self


class RejectedAlternative(RegistryModel):
    """A considered product interpretation that was not selected."""

    alternative: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class ParameterProvenance(RegistryModel):
    """Provenance for one model value, method, estimate, or guardrail."""

    name: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    value: JsonValue
    classification: ParameterClassification
    evidence_claim_ids: list[ClaimId] = Field(default_factory=list)
    rationale: str | None = None
    applies_to: str | None = None

    @model_validator(mode="after")
    def validate_provenance(self) -> "ParameterProvenance":
        """Require evidence for published values and rationale for Praxys choices."""
        if (
            self.classification == ParameterClassification.PUBLISHED
            and not self.evidence_claim_ids
        ):
            raise ValueError("published parameters require an evidence claim")
        if (
            self.classification
            in {ParameterClassification.ESTIMATE, ParameterClassification.GUARDRAIL}
            and not self.rationale
        ):
            raise ValueError("estimates and guardrails require an explicit rationale")
        return self


class AffectedSurfaces(RegistryModel):
    """Implementation and user-facing surfaces governed by a decision."""

    models: list[str] = Field(min_length=1)
    apis: list[str] = Field(default_factory=list)
    clients: list[str] = Field(default_factory=list)
    science_notes: list[str] = Field(default_factory=list)


class ScienceDecisionRecord(RegistryModel):
    """Versioned record of how Praxys interprets accepted evidence."""

    schema_version: Literal[1]
    id: RecordId
    version: int = Field(ge=1)
    title: str = Field(min_length=1)
    status: RecordStatus
    decision_date: date
    owners: list[Identity] = Field(min_length=1)
    human_reviewers: list[Identity] = Field(default_factory=list)
    model_version: str = Field(min_length=1)
    evidence_review_ids: list[RecordId] = Field(min_length=1)
    evidence_claim_ids: list[ClaimId] = Field(min_length=1)
    accepted_interpretation: str = Field(min_length=1)
    rejected_alternatives: list[RejectedAlternative] = Field(min_length=1)
    model_parameters: list[ParameterProvenance] = Field(default_factory=list)
    applicability: list[str] = Field(min_length=1)
    user_facing_claim_limits: list[str] = Field(min_length=1)
    safety_implications: list[str] = Field(min_length=1)
    privacy_implications: list[str] = Field(min_length=1)
    validation_plan: list[str] = Field(min_length=1)
    falsification_conditions: list[str] = Field(min_length=1)
    affected_surfaces: AffectedSurfaces
    supersedes: list[RecordId] = Field(default_factory=list)
    superseded_by: RecordId | None = None
    decision_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_record(self) -> "ScienceDecisionRecord":
        """Validate version identity, local uniqueness, and human acceptance."""
        if not self.id.startswith("sdr-"):
            raise ValueError("science decision IDs must start with sdr-")
        if not self.id.endswith(f"-v{self.version}"):
            raise ValueError("record id suffix must match version")
        parameter_names = [parameter.name for parameter in self.model_parameters]
        if len(parameter_names) != len(set(parameter_names)):
            raise ValueError("model parameter names must be unique")
        if len(self.evidence_review_ids) != len(set(self.evidence_review_ids)):
            raise ValueError("evidence review IDs must be unique")
        if len(self.evidence_claim_ids) != len(set(self.evidence_claim_ids)):
            raise ValueError("evidence claim IDs must be unique")
        if self.status in {RecordStatus.ACCEPTED, RecordStatus.SUPERSEDED}:
            _require_human_review(self.human_reviewers, self.decision_date)
        if self.status == RecordStatus.SUPERSEDED and self.superseded_by is None:
            raise ValueError("superseded records require superseded_by")
        if self.status != RecordStatus.SUPERSEDED and self.superseded_by is not None:
            raise ValueError("only superseded records may set superseded_by")
        return self


def _require_human_review(
    reviewers: list[str],
    reviewed_on: date | None,
) -> None:
    """Require an identified human reviewer for accepted lifecycle states."""
    if reviewed_on is None:
        raise ValueError("accepted records require a review date")
    if not any(
        reviewer.startswith(("github:", "orcid:"))
        for reviewer in reviewers
    ):
        raise ValueError("accepted records require an identified human reviewer")


@dataclass(frozen=True)
class ScienceRegistry:
    """Resolved evidence, claim, citation, and decision graph."""

    science_dir: Path
    evidence_reviews: dict[str, EvidenceReview]
    decisions: dict[str, ScienceDecisionRecord]
    claims: dict[str, EvidenceClaim]
    citations: dict[str, CitationSource]
    claim_review_ids: dict[str, str]
    review_paths: dict[str, Path]
    decision_paths: dict[str, Path]

    def citations_for_decision(
        self,
        decision_id: str,
    ) -> list[CitationSource]:
        """Resolve decision claims into a stable, de-duplicated citation list."""
        decision = self.decisions[decision_id]
        source_ids: list[str] = []
        for claim_id in decision.evidence_claim_ids:
            for source_id in self.claims[claim_id].source_ids:
                if source_id not in source_ids:
                    source_ids.append(source_id)
        return [self.citations[source_id] for source_id in source_ids]

    def source_links_for_decision(self, decision_id: str) -> list[dict[str, str]]:
        """Return compact citation links used by metric API payloads."""
        return [
            {"id": source.id, "url": source.stable_url}
            for source in self.citations_for_decision(decision_id)
        ]

    def validate_theory_link(
        self,
        *,
        decision_id: str,
        model_key: str,
        model_version: str,
        params: dict[str, Any],
    ) -> ScienceDecisionRecord:
        """Validate that a shipped theory matches its accepted decision record."""
        if decision_id not in self.decisions:
            raise ValueError(f"Unknown science decision: {decision_id}")
        decision = self.decisions[decision_id]
        if decision.status != RecordStatus.ACCEPTED:
            raise ValueError(
                f"Shipped model {model_key} must use an accepted decision"
            )
        if model_key not in decision.affected_surfaces.models:
            raise ValueError(
                f"Decision {decision_id} does not govern model {model_key}"
            )
        if model_version != decision.model_version:
            raise ValueError(
                f"Model version {model_version} does not match "
                f"{decision.model_version}"
            )
        provenance = {
            parameter.name: parameter for parameter in decision.model_parameters
        }
        missing = sorted(set(params) - set(provenance))
        if missing:
            raise ValueError(
                f"Decision {decision_id} lacks parameter provenance: {missing}"
            )
        mismatched = sorted(
            name
            for name, value in params.items()
            if provenance[name].value != value
        )
        if mismatched:
            raise ValueError(
                f"Decision {decision_id} parameter values differ: {mismatched}"
            )
        return decision


def _yaml_paths(directory: Path) -> list[Path]:
    """Return registry YAML files in deterministic path order."""
    if not directory.is_dir():
        return []
    return sorted(
        [*directory.rglob("*.yaml"), *directory.rglob("*.yml")],
        key=lambda path: path.as_posix(),
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load one YAML mapping with a path-specific error for malformed roots."""
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if not isinstance(raw, dict):
        raise ValueError(f"Registry record must be a mapping: {path}")
    return raw


def load_science_registry(
    science_dir: str | Path | None = None,
) -> ScienceRegistry:
    """Load the default cached registry or an uncached explicit registry path."""
    if science_dir is None:
        return _load_default_science_registry()
    return _load_science_registry(Path(science_dir))


@lru_cache(maxsize=1)
def _load_default_science_registry() -> ScienceRegistry:
    """Load the immutable application registry once per process."""
    return _load_science_registry(_SCIENCE_DIR)


def _load_science_registry(root: Path) -> ScienceRegistry:
    """Load and cross-validate all registry records beneath ``root``."""
    evidence_reviews: dict[str, EvidenceReview] = {}
    decisions: dict[str, ScienceDecisionRecord] = {}
    review_paths: dict[str, Path] = {}
    decision_paths: dict[str, Path] = {}

    for path in _yaml_paths(root / "evidence"):
        raw = _load_yaml(path)
        _validate_schema_version(raw, path)
        review = EvidenceReview.model_validate(raw)
        _add_record(evidence_reviews, review.id, review, path)
        _validate_record_filename(review.id, path)
        review_paths[review.id] = path

    for path in _yaml_paths(root / "decisions"):
        raw = _load_yaml(path)
        _validate_schema_version(raw, path)
        decision = ScienceDecisionRecord.model_validate(raw)
        _add_record(decisions, decision.id, decision, path)
        _validate_record_filename(decision.id, path)
        decision_paths[decision.id] = path

    claims: dict[str, EvidenceClaim] = {}
    citations: dict[str, CitationSource] = {}
    claim_review_ids: dict[str, str] = {}
    citation_identifiers: dict[str, str] = {}
    for review in evidence_reviews.values():
        for citation in review.citations:
            _add_citation(citations, citation, review_paths[review.id])
            for identifier in _citation_identifiers(citation):
                owner = citation_identifiers.get(identifier)
                if owner is not None and owner != citation.id:
                    raise ValueError(
                        f"Citation identifier {identifier} is duplicated by "
                        f"{owner} and {citation.id}"
                    )
                citation_identifiers[identifier] = citation.id
        for claim in review.claims:
            _add_record(claims, claim.id, claim, review_paths[review.id])
            claim_review_ids[claim.id] = review.id

    for review in evidence_reviews.values():
        local_source_ids = {
            citation.id for citation in review.citations
        }
        for claim in review.claims:
            for source_id in claim.source_ids:
                if source_id not in local_source_ids:
                    raise ValueError(
                        f"Claim {claim.id} references source {source_id} outside "
                        f"review {review.id}"
                    )

    for decision in decisions.values():
        _validate_decision_links(
            decision,
            evidence_reviews,
            claims,
            claim_review_ids,
        )

    _validate_supersession(evidence_reviews)
    _validate_supersession(decisions)

    return ScienceRegistry(
        science_dir=root,
        evidence_reviews=evidence_reviews,
        decisions=decisions,
        claims=claims,
        citations=citations,
        claim_review_ids=claim_review_ids,
        review_paths=review_paths,
        decision_paths=decision_paths,
    )


def _validate_schema_version(raw: dict[str, Any], path: Path) -> None:
    """Reject records whose schema is newer or older than this loader."""
    schema_version = raw.get("schema_version")
    if schema_version != 1:
        raise ValueError(
            f"Unsupported schema_version {schema_version!r} in {path}; "
            "this loader only understands version 1"
        )


def _add_record(
    records: dict[str, Any],
    record_id: str,
    record: Any,
    path: Path,
) -> None:
    """Add one globally unique record to a registry map."""
    if record_id in records:
        raise ValueError(f"Duplicate registry ID {record_id}: {path}")
    records[record_id] = record


def _add_citation(
    citations: dict[str, CitationSource],
    citation: CitationSource,
    path: Path,
) -> None:
    """Reuse identical sources across versioned reviews without ambiguity."""
    existing = citations.get(citation.id)
    if existing is None:
        citations[citation.id] = citation
    elif existing != citation:
        raise ValueError(
            f"Citation {citation.id} has conflicting metadata in {path}"
        )


def _validate_record_filename(record_id: str, path: Path) -> None:
    """Keep record paths stable and predictable from their IDs."""
    if path.stem != record_id:
        raise ValueError(
            f"Registry filename {path.name} must match record ID {record_id}"
        )


def _citation_identifiers(citation: CitationSource) -> Iterable[str]:
    """Yield normalized identifiers used to detect duplicate citations."""
    if citation.doi is not None:
        yield f"doi:{citation.doi.casefold()}"
    if citation.pmid is not None:
        yield f"pmid:{citation.pmid}"
    if citation.doi is None and citation.pmid is None and citation.url is not None:
        yield f"url:{str(citation.url).rstrip('/').casefold()}"


def _validate_decision_links(
    decision: ScienceDecisionRecord,
    reviews: dict[str, EvidenceReview],
    claims: dict[str, EvidenceClaim],
    claim_review_ids: dict[str, str],
) -> None:
    """Validate review, claim, and parameter links for one decision."""
    for review_id in decision.evidence_review_ids:
        if review_id not in reviews:
            raise ValueError(
                f"Decision {decision.id} references unknown review {review_id}"
            )
        if (
            decision.status == RecordStatus.ACCEPTED
            and reviews[review_id].status != RecordStatus.ACCEPTED
        ):
            raise ValueError(
                f"Accepted decision {decision.id} uses non-accepted review "
                f"{review_id}"
            )
    for claim_id in decision.evidence_claim_ids:
        if claim_id not in claims:
            raise ValueError(
                f"Decision {decision.id} references unknown claim {claim_id}"
            )
        review_id = claim_review_ids[claim_id]
        if review_id not in decision.evidence_review_ids:
            raise ValueError(
                f"Decision {decision.id} omits review {review_id} for "
                f"claim {claim_id}"
            )
    used_review_ids = {
        claim_review_ids[claim_id]
        for claim_id in decision.evidence_claim_ids
    }
    unused_review_ids = sorted(
        set(decision.evidence_review_ids) - used_review_ids
    )
    if unused_review_ids:
        raise ValueError(
            f"Decision {decision.id} lists reviews without using a claim: "
            f"{unused_review_ids}"
        )
    used_claim_ids = set(decision.evidence_claim_ids)
    for parameter in decision.model_parameters:
        for claim_id in parameter.evidence_claim_ids:
            if claim_id not in claims:
                raise ValueError(
                    f"Parameter {parameter.name} references unknown claim "
                    f"{claim_id}"
                )
            if claim_id not in used_claim_ids:
                raise ValueError(
                    f"Parameter {parameter.name} uses claim {claim_id} that is "
                    f"not listed by decision {decision.id}"
                )


def _validate_supersession(records: dict[str, Any]) -> None:
    """Require reciprocal, acyclic supersession links within one record type."""
    for record in records.values():
        for old_id in record.supersedes:
            if old_id not in records:
                raise ValueError(
                    f"Record {record.id} supersedes unknown record {old_id}"
                )
            if old_id == record.id:
                raise ValueError(f"Record {record.id} cannot supersede itself")
            old = records[old_id]
            if old.status != RecordStatus.SUPERSEDED:
                raise ValueError(
                    f"Superseded record {old_id} must have status superseded"
                )
            if old.superseded_by != record.id:
                raise ValueError(
                    f"Record {old_id} must link superseded_by to {record.id}"
                )
        if record.superseded_by is not None:
            if record.superseded_by not in records:
                raise ValueError(
                    f"Record {record.id} has unknown superseded_by "
                    f"{record.superseded_by}"
                )
            newer = records[record.superseded_by]
            if record.id not in newer.supersedes:
                raise ValueError(
                    f"Record {record.superseded_by} must supersede {record.id}"
                )

    for start_id in records:
        visited: set[str] = set()
        current_id: str | None = start_id
        while current_id is not None:
            if current_id in visited:
                raise ValueError(f"Supersession cycle includes {current_id}")
            visited.add(current_id)
            current_id = records[current_id].superseded_by


def render_registry_index(registry: ScienceRegistry) -> str:
    """Render the checked-in human-readable index from registry records."""
    lines = [
        "# Science evidence and decision registry",
        "",
        "> Generated by `python scripts/generate_science_registry_index.py`; "
        "do not edit by hand.",
        "",
        "Evidence reviews record what the literature supports. Science Decision "
        "Records (SDRs) record how Praxys interprets that evidence. Status syntax "
        "validation does not establish scientific correctness.",
        "",
    ]
    groups = (
        ("Current", {RecordStatus.ACCEPTED}),
        ("Pending", {RecordStatus.DRAFT}),
        ("Superseded", {RecordStatus.SUPERSEDED}),
        ("Retired", {RecordStatus.RETIRED}),
    )
    for heading, statuses in groups:
        lines.extend([f"## {heading}", ""])
        lines.extend(
            _render_record_table(
                "Evidence reviews",
                registry.evidence_reviews.values(),
                registry.review_paths,
                registry.science_dir,
                statuses,
            )
        )
        lines.extend(
            _render_record_table(
                "Science decisions",
                registry.decisions.values(),
                registry.decision_paths,
                registry.science_dir,
                statuses,
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_record_table(
    label: str,
    records: Iterable[EvidenceReview | ScienceDecisionRecord],
    paths: dict[str, Path],
    science_dir: Path,
    statuses: set[RecordStatus],
) -> list[str]:
    """Render one status-filtered evidence or decision table."""
    selected = sorted(
        (record for record in records if record.status in statuses),
        key=lambda record: record.id,
    )
    lines = [f"### {label}", ""]
    if not selected:
        return [*lines, "_None._", ""]
    lines.extend([
        "| Record | Version | Topic/model | Reviewed/decided |",
        "|---|---:|---|---|",
    ])
    for record in selected:
        relative = paths[record.id].relative_to(science_dir).as_posix()
        title = record.title.replace("|", r"\|")
        if isinstance(record, EvidenceReview):
            subject = record.topic
            record_date = record.reviewed_on or record.created_on
        else:
            subject = record.model_version
            record_date = record.decision_date
        lines.append(
            f"| [{record.id}]({relative}) — {title} | {record.version} | "
            f"{subject} | {record_date.isoformat()} |"
        )
    return [*lines, ""]
