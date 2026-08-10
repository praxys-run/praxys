"""Authenticated owner-scoped API for adaptive-plan personal context."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from api.context_pilot import (
    ContextPilotConflict,
    ContextPilotNotFound,
    ContextPilotValidationError,
    build_context_pilot_evaluation,
    get_context_pilot_proposal,
    list_context_pilot_scenarios,
    respond_to_context_pilot_proposal,
    run_context_pilot,
)
from api.auth import require_write_access
from api.personal_context import (
    ContextMutationResult,
    InspectedPersonalContext,
    PersonalContextAccessError,
    PersonalContextConflict,
    PersonalContextDeletionError,
    PersonalContextUnavailable,
    PersonalContextValidationError,
    build_personal_context_export,
    confirm_context_correction,
    confirm_context_item,
    decide_context_ai_consent,
    expire_context,
    inspect_context,
    inspect_contexts,
    linked_revision_ids,
    load_active_contexts,
    preview_context_item,
    withdraw_context,
)
from api.personal_context_auth import (
    CONTEXT_SCOPE_AI_CONSENT,
    CONTEXT_SCOPE_DELETE,
    CONTEXT_SCOPE_NARRATIVE_READ,
    CONTEXT_SCOPE_READ,
    CONTEXT_SCOPE_WRITE,
    ContextActor,
    authorize_context,
    get_context_actor,
)
from api.views import require_admin, utc_isoformat
from db.models import (
    PersonalContextConsentReceipt,
    PersonalContextItem,
    PersonalContextUseReceipt,
)
from db.plan_ledger import lock_plan_writes
from db.session import get_db

router = APIRouter(prefix="/personal-context", tags=["personal-context"])
_CONTEXT_EXCEPTIONS = (
    PersonalContextAccessError,
    PersonalContextConflict,
    PersonalContextDeletionError,
    PersonalContextUnavailable,
    PersonalContextValidationError,
)

ContextKind = Literal[
    "durable_preference",
    "temporary_constraint",
    "execution_explanation",
]
ContextPurpose = Literal[
    "plan_generation",
    "execution_interpretation",
    "plan_adjustment",
    "goal_review",
    "outcome_review",
]
ContextCategory = Literal[
    "less_time",
    "unavailable_day",
    "schedule_conflict",
    "caregiving",
    "travel",
    "fatigue",
    "motivation",
    "illness",
    "pain_or_injury",
    "red_flag_symptoms",
    "weather",
    "equipment_access",
    "other",
    "prefer_not_to_say",
]
ContextState = Literal["active", "expired", "withdrawn", "deleting"]
ContextClient = Literal["web", "miniapp"]
ContextLinkedSubject = Literal[
    "plan",
    "workout",
    "goal",
    "execution_event",
]
ContextScalar = str | int | float | bool | None
ContextFieldValue = ContextScalar | list[ContextScalar]
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
    ),
]


class ContextPayloadRequest(BaseModel):
    """Bounded sensitive payload accepted from a context command."""

    model_config = ConfigDict(extra="forbid")

    category: ContextCategory
    fields: dict[str, ContextFieldValue] = Field(
        default_factory=dict,
        max_length=20,
    )
    narrative: str | None = Field(default=None, min_length=1, max_length=280)


class ContextPayload(ContextPayloadRequest):
    """Normalized context payload returned with an explicit fields object."""

    fields: dict[str, ContextFieldValue] = Field(max_length=20)


class ContextDraftRequest(BaseModel):
    """Request-scoped draft shared by preview and confirmation."""

    model_config = ConfigDict(extra="forbid")

    kind: ContextKind
    purpose: ContextPurpose
    payload: ContextPayloadRequest
    linked_subject_type: ContextLinkedSubject | None = None
    linked_subject_id: str | None = Field(default=None, min_length=1, max_length=120)
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    purge_after: datetime | None = None
    narrative_purge_at: datetime | None = None


class ContextConfirmRequest(ContextDraftRequest):
    """Trusted athlete confirmation that creates a durable version."""

    consent_text_version: str = Field(min_length=1, max_length=64)
    client: ContextClient


class ContextCorrectionRequest(BaseModel):
    """Athlete-confirmed immutable correction of one exact version."""

    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    payload: ContextPayloadRequest
    consent_text_version: str = Field(min_length=1, max_length=64)
    client: ContextClient
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    purge_after: datetime | None = None
    narrative_purge_at: datetime | None = None


class ContextAiConsentRequest(BaseModel):
    """Athlete-only AI processing decision for one exact version."""

    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    decision: Literal["granted", "denied", "withdrawn"]
    provider: Literal["azure_openai"] | None = None
    disclosed_fields: list[str] = Field(default_factory=list, max_length=32)
    narrative_disclosed: bool = False
    consent_text_version: str = Field(min_length=1, max_length=64)
    client: ContextClient


class ContextExpireRequest(BaseModel):
    """Optimistic-concurrency fence for explicit expiry."""

    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)


class ContextSelectionRequest(BaseModel):
    """One non-persisted active-context selection with explicit exclusions."""

    model_config = ConfigDict(extra="forbid")

    purpose: ContextPurpose
    kind: ContextKind | None = None
    excluded_item_ids: list[str] = Field(default_factory=list, max_length=100)
    include_narrative: bool = False


class ContextPreviewResponse(BaseModel):
    """Normalized draft returned without creating a database row."""

    model_config = ConfigDict(extra="forbid")

    kind: ContextKind
    purpose: ContextPurpose
    payload: ContextPayload
    linked_subject_type: ContextLinkedSubject | None
    linked_subject_id: str | None
    starts_at: str
    expires_at: str | None
    purge_after: str | None
    narrative_purge_at: str | None
    payload_schema_version: Literal[1]
    processing_mode: Literal["deterministic_only"]
    confirmation_required: Literal[True]
    preview_actor_type: str


class ContextItemResponse(BaseModel):
    """One retained owner-visible context version."""

    model_config = ConfigDict(extra="forbid")

    id: str
    lineage_id: str
    version: int
    supersedes_id: str | None
    kind: ContextKind
    purpose: ContextPurpose
    state: ContextState
    payload: ContextPayload
    has_narrative: bool
    source_actor_type: str
    source_actor_id: str | None
    linked_subject_type: ContextLinkedSubject | None
    linked_subject_id: str | None
    processing_mode: Literal["deterministic_only", "ai_allowed"]
    consent_receipt_id: str | None
    starts_at: str
    expires_at: str | None
    narrative_purge_at: str | None
    narrative_purged_at: str | None
    purge_after: str | None
    created_at: str
    updated_at: str
    purpose_confirmed: bool
    latest_version: bool


class ContextConsentReceiptResponse(BaseModel):
    """Payload-free purpose or AI-processing consent receipt."""

    model_config = ConfigDict(extra="forbid")

    id: str
    context_item_id: str
    context_version: int
    purpose: ContextPurpose
    consent_scope: Literal["purpose_confirmation", "ai_processing"]
    provider: str | None
    disclosed_fields: list[str]
    narrative_disclosed: bool
    consent_text_version: str
    decision: Literal["granted", "denied", "withdrawn"]
    client: ContextClient
    decided_at: str


class ContextUseReceiptResponse(BaseModel):
    """Payload-free record of one bounded context use."""

    model_config = ConfigDict(extra="forbid")

    id: str
    context_item_id: str
    context_version: int
    purpose: ContextPurpose
    consumer_type: Literal[
        "deterministic_policy",
        "planning_ai",
        "provider_adapter",
    ]
    consumer_name: str
    disclosed_fields: list[str]
    narrative_disclosed: bool
    policy_version: str | None
    prompt_version: str | None
    consent_receipt_id: str | None
    used_at: str


class ContextListResponse(BaseModel):
    """Owner-scoped retained context list."""

    model_config = ConfigDict(extra="forbid")

    items: list[ContextItemResponse]


class ContextDetailResponse(BaseModel):
    """One context version plus private owner audit receipts."""

    model_config = ConfigDict(extra="forbid")

    item: ContextItemResponse
    consent_receipts: list[ContextConsentReceiptResponse]
    use_receipts: list[ContextUseReceiptResponse]
    linked_revision_ids: list[str]


class ContextMutationResponse(BaseModel):
    """Confirmed create/correction response with idempotency state."""

    model_config = ConfigDict(extra="forbid")

    item: ContextItemResponse
    purpose_receipt_id: str
    replayed: bool


class ContextAiConsentResponse(BaseModel):
    """Current item state plus the appended or replayed consent receipt."""

    model_config = ConfigDict(extra="forbid")

    item: ContextItemResponse
    receipt: ContextConsentReceiptResponse
    replayed: bool


class ContextSelectionItem(BaseModel):
    """Minimal active context selected for one bounded downstream use."""

    model_config = ConfigDict(extra="forbid")

    id: str
    lineage_id: str
    version: int
    kind: ContextKind
    purpose: ContextPurpose
    category: ContextCategory
    fields: dict[str, ContextFieldValue]
    narrative: str | None
    processing_mode: Literal["deterministic_only", "ai_allowed"]


class ContextSelectionResponse(BaseModel):
    """Non-persisted active selection after caller-requested exclusions."""

    model_config = ConfigDict(extra="forbid")

    items: list[ContextSelectionItem]


class ContextExportItemResponse(BaseModel):
    """Complete retained version included in the athlete's export."""

    model_config = ConfigDict(extra="forbid")

    id: str
    lineage_id: str
    version: int
    supersedes_id: str | None
    kind: ContextKind
    purpose: ContextPurpose
    state: ContextState
    payload_schema_version: Literal[1]
    payload: ContextPayload
    source_actor_type: str
    source_actor_id: str | None
    linked_subject_type: ContextLinkedSubject | None
    linked_subject_id: str | None
    processing_mode: Literal["deterministic_only", "ai_allowed"]
    consent_receipt_id: str | None
    starts_at: str
    expires_at: str | None
    narrative_purge_at: str | None
    narrative_purged_at: str | None
    purge_after: str | None
    created_at: str
    updated_at: str


class ContextLinkedRevisionResponse(BaseModel):
    """Plan revision references retained by the context export."""

    model_config = ConfigDict(extra="forbid")

    revision_id: str
    context_item_ids: list[str]


class PersonalContextExportResponse(BaseModel):
    """Versioned complete context export for the athlete."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    exported_at: str
    items: list[ContextExportItemResponse]
    consent_receipts: list[ContextConsentReceiptResponse]
    use_receipts: list[ContextUseReceiptResponse]
    linked_revisions: list[ContextLinkedRevisionResponse]


class ContextPilotScenarioResponse(BaseModel):
    """One fixed synthetic scenario in the reviewed pilot catalog."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title_code: str
    expected_outcome: Literal[
        "clarification",
        "no_change",
        "insufficient_evidence",
        "safety",
        "suggestion",
    ]


class ContextPilotScenarioListResponse(BaseModel):
    """Fixed synthetic scenarios available for deterministic replay."""

    model_config = ConfigDict(extra="forbid")

    scenarios: list[ContextPilotScenarioResponse]


class ContextPilotRunRequest(BaseModel):
    """One synthetic replay or explicit athlete opt-in pilot run."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["synthetic", "opt_in"]
    scenario_id: str | None = Field(default=None, max_length=64)
    purpose: Literal[
        "execution_interpretation",
        "plan_adjustment",
    ] | None = None
    confirmed_opt_in: bool = False
    allow_ai: bool = False


class ContextPilotSnapshotResponse(BaseModel):
    """Public workout fields in a reviewable pilot diff."""

    model_config = ConfigDict(extra="forbid")

    canonical_id: str | None
    date: str | None
    workout_type: str | None
    planned_duration_min: float | None
    planned_distance_km: float | None
    target_power_min: float | None
    target_power_max: float | None
    workout_description: str | None


class ContextPilotActionResponse(BaseModel):
    """The pilot's only accepted actionable mutation shape."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["shorten_workout_duration"]
    canonical_id: str
    planned_duration_min: int


class ContextPilotProposalResponse(BaseModel):
    """Non-canonical exact proposal awaiting an athlete response."""

    model_config = ConfigDict(extra="forbid")

    id: str | None
    status: Literal[
        "synthetic_only",
        "pending",
        "accepted",
        "rejected",
        "deferred",
        "reversed",
        "expired",
        "invalidated",
    ]
    action: ContextPilotActionResponse | None
    before: ContextPilotSnapshotResponse | None
    after: ContextPilotSnapshotResponse | None
    context_item_ids: list[str]
    allowed_responses: list[Literal["accept", "reject", "defer"]]
    acceptance_available: bool
    acceptance_requires_athlete: Literal[True]
    automatic_mutation: Literal[False]
    unknowns: list[Literal["training_response", "goal_effect"]]
    tradeoffs: list[
        Literal[
            "reduced_planned_duration",
            "session_not_completed_as_originally_planned",
        ]
    ]
    expected_goal_effect: Literal["not_estimated"]
    context_controls: list[
        Literal["inspect", "correct", "exclude", "delete"]
    ]
    expires_at: str | None
    accepted_revision_id: str | None = None


class ContextPilotRunResponse(BaseModel):
    """Stable five-outcome response from one bounded pilot run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str | None
    scenario_source: Literal["synthetic", "opt_in"]
    scenario_id: str | None
    outcome: Literal[
        "clarification",
        "no_change",
        "insufficient_evidence",
        "safety",
        "suggestion",
    ]
    reason_code: str
    processing_status: Literal["completed", "failed"]
    processing_mode: str
    policy_version: str
    uncertainty: Literal["moderate", "high"]
    proposal_scope: Literal["none", "workout"]
    clarification: dict[str, Any] | None
    no_change_comparator: dict[str, Any]
    safety: dict[str, Any]
    proposal: ContextPilotProposalResponse | None
    claim_limits: dict[str, bool]
    review_gate: dict[str, str]


class ContextPilotProposalDecisionRequest(BaseModel):
    """Athlete response to one exact pending pilot proposal."""

    model_config = ConfigDict(extra="forbid")

    response: Literal["accept", "reject", "defer"]


class ContextPilotProposalDecisionResponse(BaseModel):
    """Lifecycle result for one proposal response."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    status: Literal["accepted", "rejected", "deferred"]
    revision_id: str | None
    event_id: str
    undo_path: str | None
    canonical_plan_changed: bool
    athlete_approved: bool
    delivery: dict[str, Any] | None = None


class ContextPilotEvaluationResponse(BaseModel):
    """Aggregate-only operational pilot report."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    policy_version: str
    generated_at: str
    scope: dict[str, Any]
    operational_counts: dict[str, Any]
    proposal_responses: dict[str, int]
    checks: dict[str, Any]
    falsification: dict[str, Any]
    review_gate: dict[str, str]


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _private_no_content() -> Response:
    return Response(
        status_code=204,
        headers={"Cache-Control": "private, no-store"},
    )


def _iso(value: datetime | None) -> str | None:
    return utc_isoformat(value) if value is not None else None


def _purpose_confirmed_ids(
    db: Session,
    user_id: str,
    item_ids: set[str],
) -> set[str]:
    if not item_ids:
        return set()
    rows = (
        db.query(PersonalContextConsentReceipt.context_item_id)
        .filter(
            PersonalContextConsentReceipt.user_id == user_id,
            PersonalContextConsentReceipt.context_item_id.in_(item_ids),
            PersonalContextConsentReceipt.consent_scope
            == "purpose_confirmation",
            PersonalContextConsentReceipt.decision == "granted",
        )
        .all()
    )
    return {str(item_id) for (item_id,) in rows}


def _item_response(
    entry: InspectedPersonalContext,
    *,
    purpose_confirmed: bool,
    latest_version: bool,
) -> dict[str, Any]:
    item = entry.item
    payload: dict[str, Any] = {
        "category": entry.category,
        "fields": entry.fields,
    }
    if entry.narrative is not None:
        payload["narrative"] = entry.narrative
    return {
        "id": item.id,
        "lineage_id": item.lineage_id,
        "version": item.version,
        "supersedes_id": item.supersedes_id,
        "kind": item.kind,
        "purpose": item.purpose,
        "state": item.state,
        "payload": payload,
        "has_narrative": item.has_narrative,
        "source_actor_type": item.source_actor_type,
        "source_actor_id": item.source_actor_id,
        "linked_subject_type": item.linked_subject_type,
        "linked_subject_id": item.linked_subject_id,
        "processing_mode": item.processing_mode,
        "consent_receipt_id": item.consent_receipt_id,
        "starts_at": _iso(item.starts_at),
        "expires_at": _iso(item.expires_at),
        "narrative_purge_at": _iso(item.narrative_purge_at),
        "narrative_purged_at": _iso(item.narrative_purged_at),
        "purge_after": _iso(item.purge_after),
        "created_at": _iso(item.created_at),
        "updated_at": _iso(item.updated_at),
        "purpose_confirmed": purpose_confirmed,
        "latest_version": latest_version,
    }


def _is_latest_version(
    db: Session,
    item: PersonalContextItem,
) -> bool:
    latest_version = (
        db.query(PersonalContextItem.version)
        .filter(
            PersonalContextItem.user_id == item.user_id,
            PersonalContextItem.lineage_id == item.lineage_id,
        )
        .order_by(PersonalContextItem.version.desc())
        .limit(1)
        .scalar()
    )
    return item.version == latest_version


def _consent_response(receipt: PersonalContextConsentReceipt) -> dict[str, Any]:
    return {
        "id": receipt.id,
        "context_item_id": receipt.context_item_id,
        "context_version": receipt.context_version,
        "purpose": receipt.purpose,
        "consent_scope": receipt.consent_scope,
        "provider": receipt.provider,
        "disclosed_fields": list(receipt.disclosed_fields or []),
        "narrative_disclosed": receipt.narrative_disclosed,
        "consent_text_version": receipt.consent_text_version,
        "decision": receipt.decision,
        "client": receipt.client,
        "decided_at": _iso(receipt.decided_at),
    }


def _use_response(receipt: PersonalContextUseReceipt) -> dict[str, Any]:
    return {
        "id": receipt.id,
        "context_item_id": receipt.context_item_id,
        "context_version": receipt.context_version,
        "purpose": receipt.purpose,
        "consumer_type": receipt.consumer_type,
        "consumer_name": receipt.consumer_name,
        "disclosed_fields": list(receipt.disclosed_fields or []),
        "narrative_disclosed": receipt.narrative_disclosed,
        "policy_version": receipt.policy_version,
        "prompt_version": receipt.prompt_version,
        "consent_receipt_id": receipt.consent_receipt_id,
        "used_at": _iso(receipt.used_at),
    }


def _translate_context_error(
    db: Session,
    exc: PersonalContextAccessError
    | PersonalContextConflict
    | PersonalContextDeletionError
    | PersonalContextUnavailable
    | PersonalContextValidationError,
) -> None:
    db.rollback()
    if isinstance(exc, PersonalContextConflict):
        raise HTTPException(
            409,
            detail="PERSONAL_CONTEXT_VERSION_OR_IDEMPOTENCY_CONFLICT",
        ) from exc
    if isinstance(exc, PersonalContextUnavailable):
        raise HTTPException(404, detail="PERSONAL_CONTEXT_NOT_FOUND") from exc
    if isinstance(exc, PersonalContextValidationError):
        raise HTTPException(422, detail="PERSONAL_CONTEXT_INVALID") from exc
    if isinstance(exc, PersonalContextDeletionError):
        raise HTTPException(
            503,
            detail="PERSONAL_CONTEXT_DELETE_UNAVAILABLE",
        ) from exc
    if isinstance(exc, PersonalContextAccessError):
        raise HTTPException(
            503,
            detail="PERSONAL_CONTEXT_UNAVAILABLE",
        ) from exc


def _translate_pilot_error(
    db: Session,
    exc: ContextPilotValidationError
    | ContextPilotNotFound
    | ContextPilotConflict,
) -> None:
    db.rollback()
    if isinstance(exc, ContextPilotNotFound):
        raise HTTPException(
            404,
            detail="CONTEXT_PILOT_PROPOSAL_NOT_FOUND",
        ) from exc
    if isinstance(exc, ContextPilotConflict):
        raise HTTPException(
            409,
            detail="CONTEXT_PILOT_CONFLICT",
        ) from exc
    raise HTTPException(422, detail="CONTEXT_PILOT_INVALID") from exc


def _metadata(
    db: Session,
    actor: ContextActor,
    item_id: str,
    scope: str,
    *,
    athlete_only: bool = False,
    mutation: bool = False,
) -> PersonalContextItem:
    authorize_context(
        actor,
        scope,
        athlete_only=athlete_only,
        mutation=mutation,
        non_enumerating=True,
    )
    if mutation:
        lock_plan_writes(db, actor.user_id)
    item = (
        db.query(PersonalContextItem)
        .filter(
            PersonalContextItem.user_id == actor.user_id,
            PersonalContextItem.id == item_id,
        )
        .one_or_none()
    )
    if item is None:
        raise HTTPException(404, detail="PERSONAL_CONTEXT_NOT_FOUND")
    authorize_context(
        actor,
        scope,
        purpose=item.purpose,
        kind=item.kind,
        athlete_only=athlete_only,
        mutation=mutation,
        non_enumerating=True,
    )
    return item


def _mutation_response(
    db: Session,
    result: ContextMutationResult,
) -> dict[str, Any]:
    entry = inspect_context(
        db,
        user_id=result.item.user_id,
        item_id=result.item.id,
        include_narrative=True,
    )
    return {
        "item": _item_response(
            entry,
            purpose_confirmed=True,
            latest_version=_is_latest_version(db, result.item),
        ),
        "purpose_receipt_id": result.purpose_receipt.id,
        "replayed": result.replayed,
    }


@router.post("/preview", response_model=ContextPreviewResponse)
def preview_personal_context(
    body: ContextDraftRequest,
    response: Response,
    actor: ContextActor = Depends(get_context_actor),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Validate a bounded draft without persisting private context."""
    _private(response)
    authorize_context(
        actor,
        CONTEXT_SCOPE_WRITE,
        purpose=body.purpose,
        kind=body.kind,
        mutation=True,
    )
    try:
        preview = preview_context_item(
            db,
            user_id=actor.user_id,
            kind=body.kind,
            purpose=body.purpose,
            payload=body.payload.model_dump(exclude_none=True),
            linked_subject_type=body.linked_subject_type,
            linked_subject_id=body.linked_subject_id,
            starts_at=body.starts_at,
            expires_at=body.expires_at,
            purge_after=body.purge_after,
            narrative_purge_at=body.narrative_purge_at,
        )
    except _CONTEXT_EXCEPTIONS as exc:
        _translate_context_error(db, exc)
        raise
    return {
        "kind": preview.kind,
        "purpose": preview.purpose,
        "payload": preview.payload,
        "linked_subject_type": preview.linked_subject_type,
        "linked_subject_id": preview.linked_subject_id,
        "starts_at": _iso(preview.starts_at),
        "expires_at": _iso(preview.expires_at),
        "purge_after": _iso(preview.purge_after),
        "narrative_purge_at": _iso(preview.narrative_purge_at),
        "payload_schema_version": 1,
        "processing_mode": "deterministic_only",
        "confirmation_required": True,
        "preview_actor_type": actor.actor_type,
    }


@router.post(
    "/confirm",
    status_code=201,
    response_model=ContextMutationResponse,
)
def confirm_personal_context(
    body: ContextConfirmRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    actor: ContextActor = Depends(get_context_actor),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create one context version after trusted athlete confirmation."""
    _private(response)
    authorize_context(
        actor,
        CONTEXT_SCOPE_WRITE,
        purpose=body.purpose,
        kind=body.kind,
        athlete_only=True,
        mutation=True,
    )
    try:
        result = confirm_context_item(
            db,
            user_id=actor.user_id,
            kind=body.kind,
            purpose=body.purpose,
            payload=body.payload.model_dump(exclude_none=True),
            source_actor_type=(
                "first_party_web"
                if body.client == "web"
                else "first_party_miniapp"
            ),
            source_actor_id=actor.user_id,
            consent_text_version=body.consent_text_version,
            client=body.client,
            idempotency_key=idempotency_key,
            linked_subject_type=body.linked_subject_type,
            linked_subject_id=body.linked_subject_id,
            starts_at=body.starts_at,
            expires_at=body.expires_at,
            purge_after=body.purge_after,
            narrative_purge_at=body.narrative_purge_at,
        )
        db.commit()
        if result.replayed:
            response.status_code = 200
        return _mutation_response(db, result)
    except _CONTEXT_EXCEPTIONS as exc:
        _translate_context_error(db, exc)
        raise


@router.get("", response_model=ContextListResponse)
def list_personal_context(
    response: Response,
    purpose: ContextPurpose | None = Query(default=None),
    kind: ContextKind | None = Query(default=None),
    include_history: bool = Query(default=True),
    include_narrative: bool = Query(default=False),
    actor: ContextActor = Depends(get_context_actor),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Inspect retained owner context, optionally including prior versions."""
    _private(response)
    authorize_context(actor, CONTEXT_SCOPE_READ)
    if not actor.is_athlete and (purpose is None or kind is None):
        raise HTTPException(403, detail="PERSONAL_CONTEXT_SCOPE_REQUIRED")
    if purpose is not None or kind is not None:
        authorize_context(
            actor,
            CONTEXT_SCOPE_READ,
            purpose=purpose,
            kind=kind,
        )
    if include_narrative:
        authorize_context(
            actor,
            CONTEXT_SCOPE_NARRATIVE_READ,
            purpose=purpose,
            kind=kind,
        )
    try:
        entries = inspect_contexts(
            db,
            user_id=actor.user_id,
            purpose=purpose,
            kind=kind,
            include_history=include_history,
            include_narrative=include_narrative,
        )
    except _CONTEXT_EXCEPTIONS as exc:
        _translate_context_error(db, exc)
        raise
    item_ids = {entry.item.id for entry in entries}
    confirmed = _purpose_confirmed_ids(db, actor.user_id, item_ids)
    latest_by_lineage: dict[str, int] = {}
    for entry in entries:
        latest_by_lineage[entry.item.lineage_id] = max(
            latest_by_lineage.get(entry.item.lineage_id, 0),
            entry.item.version,
        )
    return {
        "items": [
            _item_response(
                entry,
                purpose_confirmed=entry.item.id in confirmed,
                latest_version=(
                    entry.item.version
                    == latest_by_lineage[entry.item.lineage_id]
                ),
            )
            for entry in entries
        ]
    }


@router.get("/export", response_model=PersonalContextExportResponse)
def export_personal_context(
    response: Response,
    actor: ContextActor = Depends(get_context_actor),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Export every retained item version and receipt for the athlete."""
    _private(response)
    authorize_context(
        actor,
        CONTEXT_SCOPE_READ,
        athlete_only=True,
    )
    try:
        return build_personal_context_export(db, user_id=actor.user_id)
    except _CONTEXT_EXCEPTIONS as exc:
        _translate_context_error(db, exc)
        raise


@router.post("/selection", response_model=ContextSelectionResponse)
def select_personal_context(
    body: ContextSelectionRequest,
    response: Response,
    actor: ContextActor = Depends(get_context_actor),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return one active selection while non-destructively excluding item IDs."""
    _private(response)
    authorize_context(
        actor,
        CONTEXT_SCOPE_READ,
        purpose=body.purpose,
        kind=body.kind,
    )
    if body.include_narrative:
        authorize_context(
            actor,
            CONTEXT_SCOPE_NARRATIVE_READ,
            purpose=body.purpose,
            kind=body.kind,
        )
    kinds = (
        [body.kind]
        if body.kind is not None
        else (None if actor.is_athlete else sorted(actor.kinds))
    )
    try:
        entries = load_active_contexts(
            db,
            user_id=actor.user_id,
            purpose=body.purpose,
            kinds=kinds,
            include_narrative=body.include_narrative,
        )
    except _CONTEXT_EXCEPTIONS as exc:
        _translate_context_error(db, exc)
        raise
    excluded = set(body.excluded_item_ids)
    return {
        "items": [
            {
                "id": entry.item_id,
                "lineage_id": entry.lineage_id,
                "version": entry.version,
                "kind": entry.kind,
                "purpose": entry.purpose,
                "category": entry.category,
                "fields": entry.fields,
                "narrative": entry.narrative,
                "processing_mode": entry.processing_mode,
            }
            for entry in entries
            if entry.item_id not in excluded
        ]
    }


@router.get(
    "/pilot/scenarios",
    response_model=ContextPilotScenarioListResponse,
)
def list_personal_context_pilot_scenarios(
    response: Response,
    actor: ContextActor = Depends(get_context_actor),
) -> dict[str, Any]:
    """Return the fixed, non-sensitive synthetic pilot scenarios."""
    _private(response)
    authorize_context(
        actor,
        CONTEXT_SCOPE_READ,
        athlete_only=True,
    )
    return {"scenarios": list_context_pilot_scenarios()}


@router.post("/pilot/runs", response_model=ContextPilotRunResponse)
def run_personal_context_pilot(
    body: ContextPilotRunRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    actor: ContextActor = Depends(get_context_actor),
    write_user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Run one synthetic replay or explicit first-party opt-in scenario."""
    _private(response)
    authorize_context(
        actor,
        CONTEXT_SCOPE_READ,
        purpose=body.purpose,
        athlete_only=True,
        mutation=True,
    )
    if write_user_id != actor.user_id:
        raise HTTPException(403, detail="PERSONAL_CONTEXT_SCOPE_REQUIRED")
    try:
        return run_context_pilot(
            db,
            user_id=actor.user_id,
            source=body.source,
            scenario_id=body.scenario_id,
            purpose=body.purpose,
            confirmed_opt_in=body.confirmed_opt_in,
            allow_ai=body.allow_ai,
            idempotency_key=idempotency_key,
        )
    except (
        ContextPilotValidationError,
        ContextPilotNotFound,
        ContextPilotConflict,
    ) as exc:
        _translate_pilot_error(db, exc)
        raise


@router.get(
    "/pilot/proposals/{proposal_id}",
    response_model=ContextPilotProposalResponse,
)
def inspect_personal_context_pilot_proposal(
    proposal_id: str,
    response: Response,
    actor: ContextActor = Depends(get_context_actor),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Inspect one owner-scoped pilot proposal and current lifecycle state."""
    _private(response)
    authorize_context(
        actor,
        CONTEXT_SCOPE_READ,
        athlete_only=True,
    )
    try:
        return get_context_pilot_proposal(
            db,
            user_id=actor.user_id,
            proposal_id=proposal_id,
        )
    except (
        ContextPilotValidationError,
        ContextPilotNotFound,
        ContextPilotConflict,
    ) as exc:
        _translate_pilot_error(db, exc)
        raise


@router.post(
    "/pilot/proposals/{proposal_id}/responses",
    response_model=ContextPilotProposalDecisionResponse,
)
def respond_to_personal_context_pilot_proposal(
    proposal_id: str,
    body: ContextPilotProposalDecisionRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    actor: ContextActor = Depends(get_context_actor),
    write_user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Record an athlete accept, reject, or defer response."""
    _private(response)
    authorize_context(
        actor,
        CONTEXT_SCOPE_WRITE,
        athlete_only=True,
        mutation=True,
    )
    if write_user_id != actor.user_id:
        raise HTTPException(403, detail="PERSONAL_CONTEXT_SCOPE_REQUIRED")
    try:
        return respond_to_context_pilot_proposal(
            db,
            user_id=actor.user_id,
            proposal_id=proposal_id,
            response=body.response,
            idempotency_key=idempotency_key,
        )
    except (
        ContextPilotValidationError,
        ContextPilotNotFound,
        ContextPilotConflict,
    ) as exc:
        _translate_pilot_error(db, exc)
        raise


@router.get(
    "/pilot/evaluation",
    response_model=ContextPilotEvaluationResponse,
)
def get_personal_context_pilot_evaluation(
    response: Response,
    actor: ContextActor = Depends(get_context_actor),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return the aggregate-only operational pilot evaluation."""
    _private(response)
    authorize_context(
        actor,
        CONTEXT_SCOPE_READ,
        athlete_only=True,
    )
    require_admin(actor.user_id, db)
    return build_context_pilot_evaluation(db)


@router.get("/{item_id}", response_model=ContextDetailResponse)
def get_personal_context(
    item_id: str,
    response: Response,
    include_narrative: bool = Query(default=False),
    actor: ContextActor = Depends(get_context_actor),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Inspect one retained owner context version without enumerating misses."""
    _private(response)
    metadata = _metadata(db, actor, item_id, CONTEXT_SCOPE_READ)
    if include_narrative:
        authorize_context(
            actor,
            CONTEXT_SCOPE_NARRATIVE_READ,
            purpose=metadata.purpose,
            kind=metadata.kind,
            non_enumerating=True,
        )
    try:
        entry = inspect_context(
            db,
            user_id=actor.user_id,
            item_id=item_id,
            include_narrative=include_narrative,
        )
    except _CONTEXT_EXCEPTIONS as exc:
        _translate_context_error(db, exc)
        raise
    confirmed = bool(
        _purpose_confirmed_ids(db, actor.user_id, {item_id})
    )
    latest_version = (
        db.query(PersonalContextItem.version)
        .filter(
            PersonalContextItem.user_id == actor.user_id,
            PersonalContextItem.lineage_id == metadata.lineage_id,
        )
        .order_by(PersonalContextItem.version.desc())
        .limit(1)
        .scalar()
    )
    consents: list[dict[str, Any]] = []
    uses: list[dict[str, Any]] = []
    revisions: list[str] = []
    if actor.is_athlete:
        consents = [
            _consent_response(receipt)
            for receipt in (
                db.query(PersonalContextConsentReceipt)
                .filter(
                    PersonalContextConsentReceipt.user_id == actor.user_id,
                    PersonalContextConsentReceipt.context_item_id == item_id,
                )
                .order_by(
                    PersonalContextConsentReceipt.decided_at,
                    PersonalContextConsentReceipt.id,
                )
                .all()
            )
        ]
        uses = [
            _use_response(receipt)
            for receipt in (
                db.query(PersonalContextUseReceipt)
                .filter(
                    PersonalContextUseReceipt.user_id == actor.user_id,
                    PersonalContextUseReceipt.context_item_id == item_id,
                )
                .order_by(
                    PersonalContextUseReceipt.used_at,
                    PersonalContextUseReceipt.id,
                )
                .all()
            )
        ]
        revisions = linked_revision_ids(
            db,
            user_id=actor.user_id,
            item_id=item_id,
        )
    return {
        "item": _item_response(
            entry,
            purpose_confirmed=confirmed,
            latest_version=metadata.version == latest_version,
        ),
        "consent_receipts": consents,
        "use_receipts": uses,
        "linked_revision_ids": revisions,
    }


@router.post(
    "/{item_id}/correct",
    status_code=201,
    response_model=ContextMutationResponse,
)
def correct_personal_context(
    item_id: str,
    body: ContextCorrectionRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    actor: ContextActor = Depends(get_context_actor),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Append one immutable correction after trusted athlete confirmation."""
    _private(response)
    _metadata(
        db,
        actor,
        item_id,
        CONTEXT_SCOPE_WRITE,
        athlete_only=True,
        mutation=True,
    )
    try:
        result = confirm_context_correction(
            db,
            user_id=actor.user_id,
            item_id=item_id,
            expected_version=body.expected_version,
            payload=body.payload.model_dump(exclude_none=True),
            source_actor_type=(
                "first_party_web"
                if body.client == "web"
                else "first_party_miniapp"
            ),
            source_actor_id=actor.user_id,
            consent_text_version=body.consent_text_version,
            client=body.client,
            idempotency_key=idempotency_key,
            starts_at=body.starts_at,
            expires_at=body.expires_at,
            purge_after=body.purge_after,
            narrative_purge_at=body.narrative_purge_at,
        )
        db.commit()
        if result.replayed:
            response.status_code = 200
        return _mutation_response(db, result)
    except _CONTEXT_EXCEPTIONS as exc:
        _translate_context_error(db, exc)
        raise


@router.post(
    "/{item_id}/ai-consent",
    response_model=ContextAiConsentResponse,
)
def decide_personal_context_ai_consent(
    item_id: str,
    body: ContextAiConsentRequest,
    response: Response,
    idempotency_key: IdempotencyKey,
    actor: ContextActor = Depends(get_context_actor),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Append an athlete-only AI-processing decision for one exact version."""
    _private(response)
    _metadata(
        db,
        actor,
        item_id,
        CONTEXT_SCOPE_AI_CONSENT,
        athlete_only=True,
        mutation=True,
    )
    try:
        result = decide_context_ai_consent(
            db,
            user_id=actor.user_id,
            item_id=item_id,
            expected_version=body.expected_version,
            decision=body.decision,
            provider=body.provider,
            disclosed_fields=body.disclosed_fields,
            narrative_disclosed=body.narrative_disclosed,
            consent_text_version=body.consent_text_version,
            client=body.client,
            idempotency_key=idempotency_key,
        )
        db.commit()
        entry = inspect_context(
            db,
            user_id=actor.user_id,
            item_id=item_id,
            include_narrative=False,
        )
        return {
            "item": _item_response(
                entry,
                purpose_confirmed=bool(
                    _purpose_confirmed_ids(db, actor.user_id, {item_id})
                ),
                latest_version=_is_latest_version(db, entry.item),
            ),
            "receipt": _consent_response(result.receipt),
            "replayed": result.replayed,
        }
    except _CONTEXT_EXCEPTIONS as exc:
        _translate_context_error(db, exc)
        raise


@router.post("/{item_id}/expire", response_model=ContextItemResponse)
def expire_personal_context(
    item_id: str,
    body: ContextExpireRequest,
    response: Response,
    actor: ContextActor = Depends(get_context_actor),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Explicitly expire the latest version without deleting retained history."""
    _private(response)
    _metadata(
        db,
        actor,
        item_id,
        CONTEXT_SCOPE_WRITE,
        athlete_only=True,
        mutation=True,
    )
    try:
        expire_context(
            db,
            user_id=actor.user_id,
            item_id=item_id,
            expected_version=body.expected_version,
        )
        db.commit()
        entry = inspect_context(
            db,
            user_id=actor.user_id,
            item_id=item_id,
            include_narrative=False,
        )
        return _item_response(
            entry,
            purpose_confirmed=bool(
                _purpose_confirmed_ids(db, actor.user_id, {item_id})
            ),
            latest_version=True,
        )
    except _CONTEXT_EXCEPTIONS as exc:
        _translate_context_error(db, exc)
        raise


@router.delete("/{item_id}", status_code=204)
def delete_personal_context(
    item_id: str,
    expected_version: int = Query(ge=1),
    actor: ContextActor = Depends(get_context_actor),
    db: Session = Depends(get_db),
) -> Response:
    """Withdraw one lineage; unknown IDs remain non-enumerating and idempotent."""
    authorize_context(
        actor,
        CONTEXT_SCOPE_DELETE,
        athlete_only=True,
        mutation=True,
        non_enumerating=True,
    )
    lock_plan_writes(db, actor.user_id)
    metadata = (
        db.query(PersonalContextItem)
        .filter(
            PersonalContextItem.user_id == actor.user_id,
            PersonalContextItem.id == item_id,
        )
        .one_or_none()
    )
    if metadata is None:
        return _private_no_content()
    authorize_context(
        actor,
        CONTEXT_SCOPE_DELETE,
        purpose=metadata.purpose,
        kind=metadata.kind,
        athlete_only=True,
        mutation=True,
        non_enumerating=True,
    )
    try:
        withdraw_context(
            db,
            user_id=actor.user_id,
            item_id=item_id,
            expected_version=expected_version,
        )
    except _CONTEXT_EXCEPTIONS as exc:
        _translate_context_error(db, exc)
        raise
    return _private_no_content()
