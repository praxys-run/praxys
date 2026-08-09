"""Encrypted persistence and deletion lifecycle for adaptive-plan context."""
from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from azure.core.exceptions import AzureError
from cryptography.fernet import InvalidToken
from sqlalchemy import or_
from sqlalchemy.orm import Session

from api import personal_context_deletion_storage
from db.crypto import get_vault
from db.models import (
    Activity,
    PersonalContextCommand,
    PersonalContextConsentReceipt,
    PersonalContextDeletionJob,
    PersonalContextItem,
    PersonalContextUseReceipt,
    PlanRevision,
    TrainingPlan,
    UserConfig,
    User,
)
from db.plan_ledger import lock_plan_writes

logger = logging.getLogger(__name__)

PAYLOAD_SCHEMA_VERSION = 1
MAX_NARRATIVE_CHARS = 280
MAX_PAYLOAD_BYTES = 16_384
NARRATIVE_RETENTION = timedelta(days=30)
TEMPORARY_ACTIVE_LIMIT = timedelta(days=90)
TEMPORARY_POST_EXPIRY_RETENTION = timedelta(days=30)
EXECUTION_TOTAL_RETENTION = timedelta(days=180)
DELETION_RETRY_AFTER = timedelta(minutes=30)

CONTEXT_KINDS = frozenset({
    "durable_preference",
    "temporary_constraint",
    "execution_explanation",
})
CONTEXT_PURPOSES = frozenset({
    "plan_generation",
    "execution_interpretation",
    "plan_adjustment",
    "goal_review",
    "outcome_review",
})
CONTEXT_CATEGORIES = frozenset({
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
})
SOURCE_ACTOR_TYPES = frozenset({
    "first_party_web",
    "first_party_miniapp",
    "plugin",
    "mcp",
    "delegated_agent",
    "migration",
    "system",
})
LINKED_SUBJECT_TYPES = frozenset({
    "plan",
    "workout",
    "goal",
    "execution_event",
})
CONSUMER_TYPES = frozenset({
    "deterministic_policy",
    "planning_ai",
    "provider_adapter",
})
_FIELD_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_DISCLOSED_FIELD_RE = re.compile(
    r"^(category|fields(?:\.[a-z][a-z0-9_]{0,63})?|narrative)$"
)
_IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
_PRIVATE_RATIONALE_REMOVED = "Personal context removed by athlete"


class PersonalContextError(RuntimeError):
    """Base error for personal-context lifecycle operations."""


class PersonalContextValidationError(PersonalContextError, ValueError):
    """Raised when context cannot be stored under the bounded contract."""


class PersonalContextAccessError(PersonalContextError):
    """Raised when encrypted context cannot be decoded safely."""


class PersonalContextUnavailable(PersonalContextError):
    """Raised when context is stale, inactive, expired, or not owner-matched."""


class PersonalContextConflict(PersonalContextUnavailable):
    """Raised when a command targets a stale version or reused request key."""


class PersonalContextDeletionError(PersonalContextError):
    """Raised when fail-closed context deletion cannot complete."""


@dataclass(frozen=True)
class LoadedPersonalContext:
    """Decrypted owner- and purpose-matched context returned by the data layer."""

    item_id: str
    lineage_id: str
    version: int
    kind: str
    purpose: str
    category: str
    fields: dict[str, Any]
    narrative: str | None
    starts_at: datetime
    expires_at: datetime | None
    processing_mode: str


@dataclass(frozen=True)
class RetentionResult:
    """Bounded counts from one personal-context retention pass."""

    expired: int = 0
    narratives_purged: int = 0
    versions_deleted: int = 0
    jobs_retried: int = 0
    jobs_failed: int = 0


@dataclass(frozen=True)
class AccountDeletionManifest:
    """External marker staged before account-owned context is removed."""

    job_id: str
    user_id: str
    requested_at: datetime


@dataclass(frozen=True)
class ContextPreview:
    """Validated request-scoped context that has not been persisted."""

    kind: str
    purpose: str
    payload: dict[str, Any]
    linked_subject_type: str | None
    linked_subject_id: str | None
    starts_at: datetime
    expires_at: datetime | None
    purge_after: datetime | None
    narrative_purge_at: datetime | None


@dataclass(frozen=True)
class ContextMutationResult:
    """Confirmed context version plus its purpose receipt and replay state."""

    item: PersonalContextItem
    purpose_receipt: PersonalContextConsentReceipt
    replayed: bool


@dataclass(frozen=True)
class ContextConsentMutationResult:
    """AI consent receipt plus its command replay state."""

    receipt: PersonalContextConsentReceipt
    replayed: bool


@dataclass(frozen=True)
class InspectedPersonalContext:
    """One retained owner-visible version and its decrypted bounded payload."""

    item: PersonalContextItem
    category: str
    fields: dict[str, Any]
    narrative: str | None


def preview_context_item(
    db: Session,
    *,
    user_id: str,
    kind: str,
    purpose: str,
    payload: Mapping[str, Any],
    linked_subject_type: str | None = None,
    linked_subject_id: str | None = None,
    starts_at: datetime | None = None,
    expires_at: datetime | None = None,
    purge_after: datetime | None = None,
    narrative_purge_at: datetime | None = None,
    now: datetime | None = None,
) -> ContextPreview:
    """Validate and normalize a request-scoped context draft without storing it."""
    current_time = _utc_naive(now or datetime.utcnow())
    normalized_payload = _normalize_payload(payload)
    _validate_metadata(
        kind=kind,
        purpose=purpose,
        source_actor_type="first_party_web",
        source_actor_id=None,
        linked_subject_type=linked_subject_type,
        linked_subject_id=linked_subject_id,
    )
    _validate_linked_subject(
        db,
        user_id=user_id,
        linked_subject_type=linked_subject_type,
        linked_subject_id=linked_subject_id,
    )
    active_from, active_until, retain_until, narrative_until = (
        _validate_lifetime(
            kind=kind,
            has_narrative="narrative" in normalized_payload,
            starts_at=starts_at or current_time,
            expires_at=expires_at,
            purge_after=purge_after,
            narrative_purge_at=narrative_purge_at,
            captured_at=current_time,
        )
    )
    return ContextPreview(
        kind=kind,
        purpose=purpose,
        payload=normalized_payload,
        linked_subject_type=linked_subject_type,
        linked_subject_id=linked_subject_id,
        starts_at=active_from,
        expires_at=active_until,
        purge_after=retain_until,
        narrative_purge_at=narrative_until,
    )


def confirm_context_item(
    db: Session,
    *,
    user_id: str,
    kind: str,
    purpose: str,
    payload: Mapping[str, Any],
    source_actor_type: str,
    source_actor_id: str | None,
    consent_text_version: str,
    client: str,
    idempotency_key: str,
    linked_subject_type: str | None = None,
    linked_subject_id: str | None = None,
    starts_at: datetime | None = None,
    expires_at: datetime | None = None,
    purge_after: datetime | None = None,
    narrative_purge_at: datetime | None = None,
    now: datetime | None = None,
) -> ContextMutationResult:
    """Create one confirmed item exactly once for an owner command key."""
    current_time = _utc_naive(now or datetime.utcnow())
    key = _validate_idempotency_key(idempotency_key)
    _validate_metadata(
        kind=kind,
        purpose=purpose,
        source_actor_type=source_actor_type,
        source_actor_id=source_actor_id,
        linked_subject_type=linked_subject_type,
        linked_subject_id=linked_subject_id,
    )
    lock_plan_writes(db, user_id)
    command = _context_command(
        db,
        user_id=user_id,
        idempotency_key=key,
        lock=True,
    )
    existing = (
        _command_target_item(
            db,
            command=command,
            operation="confirm",
        )
        if command is not None
        else None
    )
    preview = preview_context_item(
        db,
        user_id=user_id,
        kind=kind,
        purpose=purpose,
        payload=payload,
        linked_subject_type=linked_subject_type,
        linked_subject_id=linked_subject_id,
        starts_at=starts_at or (existing.starts_at if existing else None),
        expires_at=expires_at or (existing.expires_at if existing else None),
        purge_after=purge_after or (
            existing.purge_after if existing else None
        ),
        narrative_purge_at=narrative_purge_at or (
            existing.narrative_purge_at if existing else None
        ),
        now=current_time,
    )
    if existing is not None:
        _assert_context_command_matches(
            existing,
            preview=preview,
            source_actor_type=source_actor_type,
            source_actor_id=source_actor_id,
            supersedes_id=None,
        )
        receipt = _idempotent_purpose_receipt(
            db,
            item=existing,
            consent_text_version=consent_text_version,
            client=client,
            idempotency_key=key,
            decided_at=existing.created_at,
        )
        return ContextMutationResult(existing, receipt, True)

    item = create_context_item(
        db,
        user_id=user_id,
        kind=kind,
        purpose=purpose,
        payload=preview.payload,
        source_actor_type=source_actor_type,
        source_actor_id=source_actor_id,
        linked_subject_type=linked_subject_type,
        linked_subject_id=linked_subject_id,
        starts_at=preview.starts_at,
        expires_at=preview.expires_at,
        purge_after=preview.purge_after,
        narrative_purge_at=preview.narrative_purge_at,
        idempotency_key=key,
        now=current_time,
    )
    receipt = append_purpose_receipt(
        db,
        user_id=user_id,
        item_id=item.id,
        expected_version=item.version,
        consent_text_version=consent_text_version,
        client=client,
        idempotency_key=key,
        now=current_time,
    )
    _create_context_command(
        db,
        user_id=user_id,
        idempotency_key=key,
        operation="confirm",
        item=item,
        created_at=current_time,
    )
    return ContextMutationResult(item, receipt, False)


def create_context_item(
    db: Session,
    *,
    user_id: str,
    kind: str,
    purpose: str,
    payload: Mapping[str, Any],
    source_actor_type: str,
    source_actor_id: str | None = None,
    linked_subject_type: str | None = None,
    linked_subject_id: str | None = None,
    starts_at: datetime | None = None,
    expires_at: datetime | None = None,
    purge_after: datetime | None = None,
    narrative_purge_at: datetime | None = None,
    idempotency_key: str | None = None,
    now: datetime | None = None,
) -> PersonalContextItem:
    """Stage one encrypted version-1 context item in the caller's transaction."""
    current_time = _utc_naive(now or datetime.utcnow())
    normalized_payload = _normalize_payload(payload)
    _validate_metadata(
        kind=kind,
        purpose=purpose,
        source_actor_type=source_actor_type,
        source_actor_id=source_actor_id,
        linked_subject_type=linked_subject_type,
        linked_subject_id=linked_subject_id,
    )
    _validate_linked_subject(
        db,
        user_id=user_id,
        linked_subject_type=linked_subject_type,
        linked_subject_id=linked_subject_id,
    )
    active_from, active_until, retain_until, narrative_until = (
        _validate_lifetime(
            kind=kind,
            has_narrative="narrative" in normalized_payload,
            starts_at=starts_at or current_time,
            expires_at=expires_at,
            purge_after=purge_after,
            narrative_purge_at=narrative_purge_at,
            captured_at=current_time,
        )
    )
    encrypted_payload, wrapped_dek = _encrypt_payload(normalized_payload)
    command_key = (
        _validate_idempotency_key(idempotency_key)
        if idempotency_key is not None
        else None
    )

    lock_plan_writes(db, user_id)
    owner = (
        db.query(User.id)
        .filter(User.id == user_id, User.is_active == True)  # noqa: E712
        .one_or_none()
    )
    if owner is None:
        raise PersonalContextUnavailable("Personal context owner is unavailable")

    item_id = str(uuid4())
    row = PersonalContextItem(
        id=item_id,
        lineage_id=str(uuid4()),
        user_id=user_id,
        version=1,
        kind=kind,
        purpose=purpose,
        state="active",
        encrypted_payload=encrypted_payload,
        wrapped_dek=wrapped_dek,
        payload_schema_version=PAYLOAD_SCHEMA_VERSION,
        has_narrative="narrative" in normalized_payload,
        source_actor_type=source_actor_type,
        source_actor_id=source_actor_id,
        linked_subject_type=linked_subject_type,
        linked_subject_id=linked_subject_id,
        processing_mode="deterministic_only",
        idempotency_key=command_key,
        starts_at=active_from,
        expires_at=active_until,
        narrative_purge_at=narrative_until,
        purge_after=retain_until,
        created_at=current_time,
        updated_at=current_time,
    )
    db.add(row)
    db.flush()
    return row


def confirm_context_correction(
    db: Session,
    *,
    user_id: str,
    item_id: str,
    expected_version: int,
    payload: Mapping[str, Any],
    source_actor_type: str,
    source_actor_id: str | None,
    consent_text_version: str,
    client: str,
    idempotency_key: str,
    starts_at: datetime | None = None,
    expires_at: datetime | None = None,
    purge_after: datetime | None = None,
    narrative_purge_at: datetime | None = None,
    now: datetime | None = None,
) -> ContextMutationResult:
    """Append one athlete-confirmed correction exactly once."""
    current_time = _utc_naive(now or datetime.utcnow())
    key = _validate_idempotency_key(idempotency_key)
    lock_plan_writes(db, user_id)
    command = _context_command(
        db,
        user_id=user_id,
        idempotency_key=key,
        lock=True,
    )
    existing = (
        _command_target_item(
            db,
            command=command,
            operation="correct",
        )
        if command is not None
        else None
    )
    current = _owned_item(db, user_id, item_id, lock=True)
    if existing is not None:
        if (
            current is None
            or current.version != expected_version
            or existing.version != expected_version + 1
        ):
            raise PersonalContextConflict(
                "Personal context correction no longer matches"
            )
        preview = preview_context_item(
            db,
            user_id=user_id,
            kind=current.kind,
            purpose=current.purpose,
            payload=payload,
            linked_subject_type=current.linked_subject_type,
            linked_subject_id=current.linked_subject_id,
            starts_at=starts_at or existing.starts_at,
            expires_at=expires_at or existing.expires_at,
            purge_after=purge_after or existing.purge_after,
            narrative_purge_at=(
                narrative_purge_at or existing.narrative_purge_at
            ),
            now=current_time,
        )
        _assert_context_command_matches(
            existing,
            preview=preview,
            source_actor_type=source_actor_type,
            source_actor_id=source_actor_id,
            supersedes_id=item_id,
        )
        receipt = _idempotent_purpose_receipt(
            db,
            item=existing,
            consent_text_version=consent_text_version,
            client=client,
            idempotency_key=key,
            decided_at=existing.created_at,
        )
        return ContextMutationResult(existing, receipt, True)
    if current is None:
        raise PersonalContextUnavailable("Personal context is unavailable")

    successor = correct_context_item(
        db,
        user_id=user_id,
        item_id=item_id,
        expected_version=expected_version,
        payload=payload,
        source_actor_type=source_actor_type,
        source_actor_id=source_actor_id,
        starts_at=starts_at,
        expires_at=expires_at,
        purge_after=purge_after,
        narrative_purge_at=narrative_purge_at,
        idempotency_key=key,
        now=current_time,
    )
    receipt = append_purpose_receipt(
        db,
        user_id=user_id,
        item_id=successor.id,
        expected_version=successor.version,
        consent_text_version=consent_text_version,
        client=client,
        idempotency_key=key,
        now=current_time,
    )
    _create_context_command(
        db,
        user_id=user_id,
        idempotency_key=key,
        operation="correct",
        item=successor,
        created_at=current_time,
    )
    return ContextMutationResult(successor, receipt, False)


def correct_context_item(
    db: Session,
    *,
    user_id: str,
    item_id: str,
    expected_version: int,
    payload: Mapping[str, Any],
    source_actor_type: str,
    source_actor_id: str | None = None,
    starts_at: datetime | None = None,
    expires_at: datetime | None = None,
    purge_after: datetime | None = None,
    narrative_purge_at: datetime | None = None,
    idempotency_key: str | None = None,
    now: datetime | None = None,
) -> PersonalContextItem:
    """Append a corrected immutable version without rewriting its predecessor."""
    current_time = _utc_naive(now or datetime.utcnow())
    normalized_payload = _normalize_payload(payload)
    if expected_version < 1:
        raise PersonalContextValidationError("Context version must be positive")
    if source_actor_type not in SOURCE_ACTOR_TYPES:
        raise PersonalContextValidationError("Context source actor is invalid")
    _validate_opaque(source_actor_id, field="source_actor_id", maximum=120)

    lock_plan_writes(db, user_id)
    current = _owned_item(db, user_id, item_id, lock=True)
    if current is None:
        raise PersonalContextUnavailable("Personal context is unavailable")
    latest = (
        db.query(PersonalContextItem)
        .filter(
            PersonalContextItem.user_id == user_id,
            PersonalContextItem.lineage_id == current.lineage_id,
        )
        .order_by(PersonalContextItem.version.desc())
        .with_for_update()
        .first()
    )
    if (
        latest is None
        or latest.id != item_id
        or latest.version != expected_version
        or latest.state != "active"
        or _is_expired(latest, current_time)
    ):
        raise PersonalContextConflict(
            "Personal context version is no longer current"
        )

    active_from, active_until, retain_until, narrative_until = (
        _validate_lifetime(
            kind=latest.kind,
            has_narrative="narrative" in normalized_payload,
            starts_at=starts_at or latest.starts_at,
            expires_at=expires_at,
            purge_after=purge_after,
            narrative_purge_at=narrative_purge_at,
            captured_at=current_time,
        )
    )
    encrypted_payload, wrapped_dek = _encrypt_payload(normalized_payload)
    command_key = (
        _validate_idempotency_key(idempotency_key)
        if idempotency_key is not None
        else None
    )

    latest.state = "expired"
    latest.updated_at = current_time

    successor = PersonalContextItem(
        id=str(uuid4()),
        lineage_id=latest.lineage_id,
        user_id=user_id,
        version=latest.version + 1,
        supersedes_id=latest.id,
        kind=latest.kind,
        purpose=latest.purpose,
        state="active",
        encrypted_payload=encrypted_payload,
        wrapped_dek=wrapped_dek,
        payload_schema_version=PAYLOAD_SCHEMA_VERSION,
        has_narrative="narrative" in normalized_payload,
        source_actor_type=source_actor_type,
        source_actor_id=source_actor_id,
        linked_subject_type=latest.linked_subject_type,
        linked_subject_id=latest.linked_subject_id,
        processing_mode="deterministic_only",
        idempotency_key=command_key,
        starts_at=active_from,
        expires_at=active_until,
        narrative_purge_at=narrative_until,
        purge_after=retain_until,
        created_at=current_time,
        updated_at=current_time,
    )
    db.add(successor)
    db.flush()
    return successor


def load_active_contexts(
    db: Session,
    *,
    user_id: str,
    purpose: str,
    kinds: Sequence[str] | None = None,
    include_narrative: bool = False,
    require_purpose_confirmation: bool = False,
    now: datetime | None = None,
) -> list[LoadedPersonalContext]:
    """Load latest active owner-matched context, enforcing expiry on the read."""
    if purpose not in CONTEXT_PURPOSES:
        raise PersonalContextValidationError("Context purpose is invalid")
    if kinds is not None and (
        not kinds or not set(kinds).issubset(CONTEXT_KINDS)
    ):
        raise PersonalContextValidationError("Context kinds are invalid")
    current_time = _utc_naive(now or datetime.utcnow())
    query = db.query(PersonalContextItem).filter(
        PersonalContextItem.user_id == user_id,
        PersonalContextItem.purpose == purpose,
        PersonalContextItem.state == "active",
        PersonalContextItem.starts_at <= current_time,
        or_(
            PersonalContextItem.expires_at.is_(None),
            PersonalContextItem.expires_at > current_time,
        ),
    )
    if kinds is not None:
        query = query.filter(PersonalContextItem.kind.in_(kinds))
    if require_purpose_confirmation:
        purpose_confirmed = (
            db.query(PersonalContextConsentReceipt.id)
            .filter(
                PersonalContextConsentReceipt.user_id
                == PersonalContextItem.user_id,
                PersonalContextConsentReceipt.context_item_id
                == PersonalContextItem.id,
                PersonalContextConsentReceipt.context_version
                == PersonalContextItem.version,
                PersonalContextConsentReceipt.purpose
                == PersonalContextItem.purpose,
                PersonalContextConsentReceipt.consent_scope
                == "purpose_confirmation",
                PersonalContextConsentReceipt.decision == "granted",
            )
            .exists()
        )
        query = query.filter(purpose_confirmed)
    rows = (
        query
        .order_by(
            PersonalContextItem.lineage_id,
            PersonalContextItem.version.desc(),
        )
        .all()
    )
    loaded: list[LoadedPersonalContext] = []
    seen_lineages: set[str] = set()
    for row in rows:
        if row.lineage_id in seen_lineages:
            continue
        seen_lineages.add(row.lineage_id)
        payload = _decrypt_payload(row)
        narrative_available = (
            include_narrative
            and row.has_narrative
            and row.narrative_purge_at is not None
            and row.narrative_purge_at > current_time
        )
        loaded.append(LoadedPersonalContext(
            item_id=row.id,
            lineage_id=row.lineage_id,
            version=row.version,
            kind=row.kind,
            purpose=row.purpose,
            category=str(payload["category"]),
            fields=dict(payload["fields"]),
            narrative=(
                str(payload["narrative"])
                if narrative_available and "narrative" in payload
                else None
            ),
            starts_at=row.starts_at,
            expires_at=row.expires_at,
            processing_mode=row.processing_mode,
        ))
    return loaded


def inspect_contexts(
    db: Session,
    *,
    user_id: str,
    purpose: str | None = None,
    kind: str | None = None,
    include_history: bool = True,
    include_narrative: bool = False,
    now: datetime | None = None,
) -> list[InspectedPersonalContext]:
    """Return retained owner-matched versions for context management."""
    if purpose is not None and purpose not in CONTEXT_PURPOSES:
        raise PersonalContextValidationError("Context purpose is invalid")
    if kind is not None and kind not in CONTEXT_KINDS:
        raise PersonalContextValidationError("Context kind is invalid")
    current_time = _utc_naive(now or datetime.utcnow())
    query = db.query(PersonalContextItem).filter(
        PersonalContextItem.user_id == user_id,
    )
    if purpose is not None:
        query = query.filter(PersonalContextItem.purpose == purpose)
    if kind is not None:
        query = query.filter(PersonalContextItem.kind == kind)
    rows = query.order_by(
        PersonalContextItem.lineage_id,
        PersonalContextItem.version.desc(),
    ).all()
    inspected: list[InspectedPersonalContext] = []
    seen_lineages: set[str] = set()
    for row in rows:
        if not include_history and row.lineage_id in seen_lineages:
            continue
        seen_lineages.add(row.lineage_id)
        payload = _decrypt_payload(row)
        narrative_available = (
            include_narrative
            and row.has_narrative
            and row.narrative_purge_at is not None
            and row.narrative_purge_at > current_time
        )
        inspected.append(InspectedPersonalContext(
            item=row,
            category=str(payload["category"]),
            fields=dict(payload["fields"]),
            narrative=(
                str(payload["narrative"])
                if narrative_available and "narrative" in payload
                else None
            ),
        ))
    return inspected


def inspect_context(
    db: Session,
    *,
    user_id: str,
    item_id: str,
    include_narrative: bool = False,
    now: datetime | None = None,
) -> InspectedPersonalContext:
    """Return one retained owner-matched version without revealing misses."""
    current_time = _utc_naive(now or datetime.utcnow())
    item = _owned_item(db, user_id, item_id, lock=False)
    if item is None:
        raise PersonalContextUnavailable("Personal context is unavailable")
    payload = _decrypt_payload(item)
    narrative_available = (
        include_narrative
        and item.has_narrative
        and item.narrative_purge_at is not None
        and item.narrative_purge_at > current_time
    )
    return InspectedPersonalContext(
        item=item,
        category=str(payload["category"]),
        fields=dict(payload["fields"]),
        narrative=(
            str(payload["narrative"])
            if narrative_available and "narrative" in payload
            else None
        ),
    )


def expire_context(
    db: Session,
    *,
    user_id: str,
    item_id: str,
    expected_version: int,
    now: datetime | None = None,
) -> PersonalContextItem:
    """Synchronously make the latest owned context version unusable."""
    current_time = _utc_naive(now or datetime.utcnow())
    lock_plan_writes(db, user_id)
    item = _owned_item(db, user_id, item_id, lock=True)
    if item is None:
        raise PersonalContextUnavailable("Personal context is unavailable")
    latest = (
        db.query(PersonalContextItem)
        .filter(
            PersonalContextItem.user_id == user_id,
            PersonalContextItem.lineage_id == item.lineage_id,
        )
        .order_by(PersonalContextItem.version.desc())
        .with_for_update()
        .first()
    )
    if (
        latest is None
        or latest.id != item_id
        or latest.version != expected_version
    ):
        raise PersonalContextConflict(
            "Personal context version is no longer current"
        )
    if latest.state == "expired":
        return latest
    if latest.state != "active":
        raise PersonalContextConflict(
            "Personal context version is no longer active"
        )
    latest.state = "expired"
    latest.processing_mode = "deterministic_only"
    latest.consent_receipt_id = None
    latest.updated_at = current_time
    db.flush()
    return latest


def build_personal_context_export(
    db: Session,
    *,
    user_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the complete owner export for every retained context version."""
    current_time = _utc_naive(now or datetime.utcnow())
    inspected = inspect_contexts(
        db,
        user_id=user_id,
        include_history=True,
        include_narrative=True,
        now=current_time,
    )
    item_ids = {entry.item.id for entry in inspected}
    linked_revisions: list[dict[str, Any]] = []
    for revision in (
        db.query(PlanRevision)
        .filter(PlanRevision.user_id == user_id)
        .order_by(PlanRevision.created_at, PlanRevision.id)
        .all()
    ):
        details = revision.details if isinstance(revision.details, dict) else {}
        references = _revision_context_item_ids(details) & item_ids
        if references:
            linked_revisions.append({
                "revision_id": revision.id,
                "context_item_ids": sorted(references),
            })
    consents = (
        db.query(PersonalContextConsentReceipt)
        .filter(PersonalContextConsentReceipt.user_id == user_id)
        .order_by(
            PersonalContextConsentReceipt.decided_at,
            PersonalContextConsentReceipt.id,
        )
        .all()
    )
    uses = (
        db.query(PersonalContextUseReceipt)
        .filter(PersonalContextUseReceipt.user_id == user_id)
        .order_by(
            PersonalContextUseReceipt.used_at,
            PersonalContextUseReceipt.id,
        )
        .all()
    )
    return {
        "schema_version": 1,
        "exported_at": _export_datetime(current_time),
        "items": [
            {
                "id": entry.item.id,
                "lineage_id": entry.item.lineage_id,
                "version": entry.item.version,
                "supersedes_id": entry.item.supersedes_id,
                "kind": entry.item.kind,
                "purpose": entry.item.purpose,
                "state": entry.item.state,
                "payload_schema_version": entry.item.payload_schema_version,
                "payload": {
                    "category": entry.category,
                    "fields": entry.fields,
                    **(
                        {"narrative": entry.narrative}
                        if entry.narrative is not None
                        else {}
                    ),
                },
                "source_actor_type": entry.item.source_actor_type,
                "source_actor_id": entry.item.source_actor_id,
                "linked_subject_type": entry.item.linked_subject_type,
                "linked_subject_id": entry.item.linked_subject_id,
                "processing_mode": entry.item.processing_mode,
                "consent_receipt_id": entry.item.consent_receipt_id,
                "starts_at": _export_datetime(entry.item.starts_at),
                "expires_at": _export_datetime(entry.item.expires_at),
                "narrative_purge_at": _export_datetime(
                    entry.item.narrative_purge_at
                ),
                "narrative_purged_at": _export_datetime(
                    entry.item.narrative_purged_at
                ),
                "purge_after": _export_datetime(entry.item.purge_after),
                "created_at": _export_datetime(entry.item.created_at),
                "updated_at": _export_datetime(entry.item.updated_at),
            }
            for entry in inspected
        ],
        "consent_receipts": [
            {
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
                "decided_at": _export_datetime(receipt.decided_at),
            }
            for receipt in consents
        ],
        "use_receipts": [
            {
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
                "used_at": _export_datetime(receipt.used_at),
            }
            for receipt in uses
        ],
        "linked_revisions": linked_revisions,
    }


def linked_revision_ids(
    db: Session,
    *,
    user_id: str,
    item_id: str,
) -> list[str]:
    """Return owner-matched plan revisions that reference one context item."""
    revision_ids: list[str] = []
    for revision in (
        db.query(PlanRevision)
        .filter(PlanRevision.user_id == user_id)
        .order_by(PlanRevision.created_at, PlanRevision.id)
        .all()
    ):
        details = revision.details if isinstance(revision.details, dict) else {}
        if item_id in _revision_context_item_ids(details):
            revision_ids.append(revision.id)
    return revision_ids


def append_purpose_receipt(
    db: Session,
    *,
    user_id: str,
    item_id: str,
    expected_version: int,
    consent_text_version: str,
    client: str,
    idempotency_key: str,
    now: datetime | None = None,
) -> PersonalContextConsentReceipt:
    """Append an athlete purpose-confirmation receipt for one exact version."""
    current_time = _utc_naive(now or datetime.utcnow())
    key = _validate_idempotency_key(idempotency_key)
    _validate_opaque(
        consent_text_version,
        field="consent_text_version",
        maximum=64,
        required=True,
    )
    _validate_opaque(client, field="client", maximum=32, required=True)
    lock_plan_writes(db, user_id)
    item = _owned_item(db, user_id, item_id, lock=True)
    if item is None or item.version != expected_version:
        raise PersonalContextUnavailable("Personal context is unavailable")
    return _idempotent_purpose_receipt(
        db,
        item=item,
        consent_text_version=consent_text_version,
        client=client,
        idempotency_key=key,
        decided_at=current_time,
    )


def append_consent_receipt(
    db: Session,
    *,
    user_id: str,
    item_id: str,
    expected_version: int,
    decision: str,
    consent_text_version: str,
    client: str,
    provider: str | None = None,
    disclosed_fields: Sequence[str] = (),
    narrative_disclosed: bool = False,
    idempotency_key: str | None = None,
    now: datetime | None = None,
) -> PersonalContextConsentReceipt:
    """Append a payload-free AI consent decision for one exact item version."""
    if decision not in {"granted", "denied", "withdrawn"}:
        raise PersonalContextValidationError("Context consent decision is invalid")
    if decision == "granted" and provider != "azure_openai":
        raise PersonalContextValidationError(
            "Granted context AI consent requires Azure OpenAI disclosure"
        )
    _validate_opaque(
        consent_text_version,
        field="consent_text_version",
        maximum=64,
        required=True,
    )
    _validate_opaque(client, field="client", maximum=32, required=True)
    normalized_fields = _normalize_disclosed_fields(disclosed_fields)
    command_key = (
        _validate_idempotency_key(idempotency_key)
        if idempotency_key is not None
        else None
    )
    current_time = _utc_naive(now or datetime.utcnow())

    lock_plan_writes(db, user_id)
    item = _owned_item(db, user_id, item_id, lock=True)
    if item is None or item.version != expected_version:
        raise PersonalContextUnavailable("Personal context is unavailable")
    if command_key is not None:
        existing = (
            db.query(PersonalContextConsentReceipt)
            .filter(
                PersonalContextConsentReceipt.user_id == user_id,
                PersonalContextConsentReceipt.idempotency_key == command_key,
            )
            .with_for_update()
            .one_or_none()
        )
        if existing is not None:
            if not _consent_receipt_matches(
                existing,
                item=item,
                consent_scope="ai_processing",
                provider=provider,
                disclosed_fields=normalized_fields,
                narrative_disclosed=narrative_disclosed,
                consent_text_version=consent_text_version,
                decision=decision,
                client=client,
            ):
                raise PersonalContextConflict(
                    "Personal context idempotency key was reused"
                )
            return existing
    if item.state != "active" or _is_expired(item, current_time):
        raise PersonalContextUnavailable("Personal context is unavailable")
    if narrative_disclosed and (
        not item.has_narrative
        or item.narrative_purge_at is None
        or item.narrative_purge_at <= current_time
    ):
        raise PersonalContextValidationError(
            "Context narrative is unavailable for disclosure"
        )

    receipt = PersonalContextConsentReceipt(
        id=str(uuid4()),
        user_id=user_id,
        context_item_id=item.id,
        context_version=item.version,
        purpose=item.purpose,
        consent_scope="ai_processing",
        provider=provider,
        disclosed_fields=normalized_fields,
        narrative_disclosed=narrative_disclosed,
        consent_text_version=consent_text_version,
        decision=decision,
        client=client,
        idempotency_key=command_key,
        decided_at=current_time,
    )
    db.add(receipt)
    db.flush()
    if decision == "granted":
        item.processing_mode = "ai_allowed"
        item.consent_receipt_id = receipt.id
    else:
        item.processing_mode = "deterministic_only"
        item.consent_receipt_id = None
        if decision == "withdrawn":
            db.query(PersonalContextUseReceipt).filter(
                PersonalContextUseReceipt.user_id == user_id,
                PersonalContextUseReceipt.context_item_id == item.id,
            ).delete(synchronize_session=False)
    item.updated_at = current_time
    db.flush()
    return receipt


def decide_context_ai_consent(
    db: Session,
    *,
    user_id: str,
    item_id: str,
    expected_version: int,
    decision: str,
    consent_text_version: str,
    client: str,
    provider: str | None = None,
    disclosed_fields: Sequence[str] = (),
    narrative_disclosed: bool = False,
    idempotency_key: str,
    now: datetime | None = None,
) -> ContextConsentMutationResult:
    """Apply one serialized AI consent command and report exact retries."""
    key = _validate_idempotency_key(idempotency_key)
    lock_plan_writes(db, user_id)
    command = _context_command(
        db,
        user_id=user_id,
        idempotency_key=key,
        lock=True,
    )
    if command is not None:
        target = _command_target_item(
            db,
            command=command,
            operation="ai_consent",
        )
        if target.id != item_id:
            raise PersonalContextConflict(
                "Personal context idempotency key was reused"
            )
    receipt = append_consent_receipt(
        db,
        user_id=user_id,
        item_id=item_id,
        expected_version=expected_version,
        decision=decision,
        consent_text_version=consent_text_version,
        client=client,
        provider=provider,
        disclosed_fields=disclosed_fields,
        narrative_disclosed=narrative_disclosed,
        idempotency_key=key,
        now=now,
    )
    replayed = command is not None
    if not replayed:
        item = _owned_item(db, user_id, item_id, lock=True)
        if item is None:
            raise PersonalContextUnavailable(
                "Personal context is unavailable"
            )
        _create_context_command(
            db,
            user_id=user_id,
            idempotency_key=key,
            operation="ai_consent",
            item=item,
            created_at=_utc_naive(now or datetime.utcnow()),
        )
    return ContextConsentMutationResult(
        receipt=receipt,
        replayed=replayed,
    )


def record_context_use(
    db: Session,
    *,
    user_id: str,
    item_id: str,
    purpose: str,
    consumer_type: str,
    consumer_name: str,
    disclosed_fields: Sequence[str],
    narrative_disclosed: bool = False,
    policy_version: str | None = None,
    prompt_version: str | None = None,
    now: datetime | None = None,
) -> PersonalContextUseReceipt:
    """Stage one payload-free receipt after validating active use and consent."""
    if consumer_type not in CONSUMER_TYPES:
        raise PersonalContextValidationError("Context consumer type is invalid")
    _validate_opaque(
        consumer_name,
        field="consumer_name",
        maximum=100,
        required=True,
    )
    _validate_opaque(policy_version, field="policy_version", maximum=100)
    _validate_opaque(prompt_version, field="prompt_version", maximum=64)
    fields = _normalize_disclosed_fields(disclosed_fields)
    current_time = _utc_naive(now or datetime.utcnow())

    lock_plan_writes(db, user_id)
    item = _owned_item(db, user_id, item_id, lock=False)
    if (
        item is None
        or item.purpose != purpose
        or item.state != "active"
        or item.starts_at > current_time
        or _is_expired(item, current_time)
    ):
        raise PersonalContextUnavailable("Personal context is unavailable")

    consent: PersonalContextConsentReceipt | None = None
    if consumer_type in {"planning_ai", "provider_adapter"}:
        if item.processing_mode != "ai_allowed" or not item.consent_receipt_id:
            raise PersonalContextUnavailable("Context AI consent is unavailable")
        consent = (
            db.query(PersonalContextConsentReceipt)
            .filter(
                PersonalContextConsentReceipt.id
                == item.consent_receipt_id,
                PersonalContextConsentReceipt.user_id == user_id,
                PersonalContextConsentReceipt.context_item_id == item.id,
                PersonalContextConsentReceipt.context_version == item.version,
                PersonalContextConsentReceipt.purpose == purpose,
                PersonalContextConsentReceipt.consent_scope == "ai_processing",
                PersonalContextConsentReceipt.provider == "azure_openai",
                PersonalContextConsentReceipt.decision == "granted",
            )
            .one_or_none()
        )
        if consent is None or not set(fields).issubset(
            set(consent.disclosed_fields or [])
        ):
            raise PersonalContextUnavailable("Context AI consent is unavailable")
        if narrative_disclosed and not consent.narrative_disclosed:
            raise PersonalContextUnavailable(
                "Context narrative consent is unavailable"
            )
    elif narrative_disclosed:
        raise PersonalContextValidationError(
            "Deterministic context use cannot disclose narrative"
        )
    if narrative_disclosed and (
        not item.has_narrative
        or item.narrative_purge_at is None
        or item.narrative_purge_at <= current_time
    ):
        raise PersonalContextUnavailable("Context narrative is unavailable")

    receipt = PersonalContextUseReceipt(
        id=str(uuid4()),
        user_id=user_id,
        context_item_id=item.id,
        context_version=item.version,
        purpose=purpose,
        consumer_type=consumer_type,
        consumer_name=consumer_name,
        disclosed_fields=fields,
        narrative_disclosed=narrative_disclosed,
        policy_version=policy_version,
        prompt_version=prompt_version,
        consent_receipt_id=consent.id if consent is not None else None,
        used_at=current_time,
    )
    db.add(receipt)
    db.flush()
    return receipt


def withdraw_context(
    db: Session,
    *,
    user_id: str,
    item_id: str,
    expected_version: int | None = None,
    now: datetime | None = None,
) -> bool:
    """Delete every version in one owned lineage through a retryable workflow."""
    current_time = _utc_naive(now or datetime.utcnow())
    lock_plan_writes(db, user_id)
    item = _owned_item(db, user_id, item_id, lock=True)
    if item is None:
        db.rollback()
        return False
    if expected_version is not None:
        latest = (
            db.query(PersonalContextItem)
            .filter(
                PersonalContextItem.user_id == user_id,
                PersonalContextItem.lineage_id == item.lineage_id,
            )
            .order_by(PersonalContextItem.version.desc())
            .with_for_update()
            .first()
        )
        if (
            latest is None
            or latest.id != item_id
            or latest.version != expected_version
        ):
            raise PersonalContextConflict(
                "Personal context version is no longer current"
            )
    job = _queue_deletion_job(
        db,
        user_id=user_id,
        operation="delete_lineage",
        reason="withdrawal",
        lineage_id=item.lineage_id,
        target_item_id=None,
        requested_at=current_time,
    )
    if not _run_deletion_job(
        db,
        job.id,
        raise_on_failure=True,
        now=current_time,
    ):
        raise PersonalContextDeletionError(
            "Personal-context deletion did not complete"
        )
    return True


def retry_deletion_jobs(
    db: Session,
    *,
    now: datetime | None = None,
    limit: int = 100,
    raise_on_failure: bool = False,
) -> tuple[int, int]:
    """Retry bounded pending, failed, or abandoned context-deletion jobs."""
    current_time = _utc_naive(now or datetime.utcnow())
    rows = (
        db.query(PersonalContextDeletionJob.id)
        .filter(
            or_(
                PersonalContextDeletionJob.status.in_(("pending", "failed")),
                (
                    (PersonalContextDeletionJob.status == "running")
                    & (
                        (PersonalContextDeletionJob.started_at.is_(None))
                        | (
                            PersonalContextDeletionJob.started_at
                            <= current_time - DELETION_RETRY_AFTER
                        )
                    )
                ),
            )
        )
        .order_by(PersonalContextDeletionJob.requested_at)
        .limit(max(0, limit))
        .all()
    )
    job_ids = [str(job_id) for (job_id,) in rows]
    db.rollback()
    completed = 0
    failed = 0
    for job_id in job_ids:
        if _run_deletion_job(
            db,
            job_id,
            raise_on_failure=raise_on_failure,
            now=current_time,
        ):
            completed += 1
        else:
            failed += 1
    return completed, failed


def run_retention(
    db: Session,
    *,
    now: datetime | None = None,
    limit: int = 100,
    raise_on_failure: bool = False,
) -> RetentionResult:
    """Expire access and run bounded narrative/version purges.

    ``raise_on_failure`` is reserved for startup, where serving traffic while
    an overdue privacy deletion cannot complete would violate retention
    guarantees. The background scheduler keeps the default retryable behavior.
    """
    current_time = _utc_naive(now or datetime.utcnow())
    remaining = max(0, limit)
    retried, failed = retry_deletion_jobs(
        db,
        now=current_time,
        limit=remaining,
        raise_on_failure=raise_on_failure,
    )
    remaining = max(0, remaining - retried - failed)

    due_expiry = (
        db.query(PersonalContextItem.id, PersonalContextItem.user_id)
        .filter(
            PersonalContextItem.state == "active",
            PersonalContextItem.expires_at.is_not(None),
            PersonalContextItem.expires_at <= current_time,
        )
        .order_by(PersonalContextItem.expires_at)
        .limit(remaining)
        .all()
    )
    db.rollback()
    expired = 0
    for item_id, user_id in due_expiry:
        lock_plan_writes(db, str(user_id))
        item = _owned_item(db, str(user_id), str(item_id), lock=True)
        if (
            item is not None
            and item.state == "active"
            and _is_expired(item, current_time)
        ):
            item.state = "expired"
            item.updated_at = current_time
            db.commit()
            expired += 1
        else:
            db.rollback()
    remaining = max(0, remaining - expired)

    due_purge = (
        db.query(
            PersonalContextItem.id,
            PersonalContextItem.user_id,
            PersonalContextItem.lineage_id,
        )
        .filter(
            PersonalContextItem.state != "deleting",
            PersonalContextItem.purge_after.is_not(None),
            PersonalContextItem.purge_after <= current_time,
        )
        .order_by(PersonalContextItem.purge_after)
        .limit(remaining)
        .all()
    )
    db.rollback()
    versions_deleted = 0
    for item_id, user_id, lineage_id in due_purge:
        try:
            job = _queue_deletion_job(
                db,
                user_id=str(user_id),
                operation="delete_version",
                reason="expiry",
                lineage_id=str(lineage_id),
                target_item_id=str(item_id),
                requested_at=current_time,
            )
            if _run_deletion_job(
                db,
                job.id,
                raise_on_failure=raise_on_failure,
                now=current_time,
            ):
                versions_deleted += 1
            else:
                failed += 1
        except PersonalContextDeletionError:
            db.rollback()
            if raise_on_failure:
                raise
            failed += 1
    remaining = max(0, remaining - versions_deleted)

    due_narrative = (
        db.query(
            PersonalContextItem.id,
            PersonalContextItem.user_id,
            PersonalContextItem.lineage_id,
        )
        .filter(
            PersonalContextItem.state != "deleting",
            PersonalContextItem.has_narrative == True,  # noqa: E712
            PersonalContextItem.narrative_purge_at.is_not(None),
            PersonalContextItem.narrative_purge_at <= current_time,
        )
        .order_by(PersonalContextItem.narrative_purge_at)
        .limit(remaining)
        .all()
    )
    db.rollback()
    narratives_purged = 0
    for item_id, user_id, lineage_id in due_narrative:
        try:
            job = _queue_deletion_job(
                db,
                user_id=str(user_id),
                operation="purge_narrative",
                reason="retention",
                lineage_id=str(lineage_id),
                target_item_id=str(item_id),
                requested_at=current_time,
            )
            if _run_deletion_job(
                db,
                job.id,
                raise_on_failure=raise_on_failure,
                now=current_time,
            ):
                narratives_purged += 1
            else:
                failed += 1
        except PersonalContextDeletionError:
            db.rollback()
            if raise_on_failure:
                raise
            failed += 1

    return RetentionResult(
        expired=expired,
        narratives_purged=narratives_purged,
        versions_deleted=versions_deleted,
        jobs_retried=retried,
        jobs_failed=failed,
    )


def run_scheduled_retention() -> RetentionResult:
    """Run one retention pass from the process background scheduler."""
    from db.session import SessionLocal, init_db

    init_db()
    with SessionLocal() as db:
        return run_retention(db)


def replay_deletion_manifests(
    db: Session,
    *,
    now: datetime | None = None,
) -> int:
    """Reapply private deletion manifests after point-in-time database restore."""
    current_time = _utc_naive(now or datetime.utcnow())
    manifests = list(personal_context_deletion_storage.iter_active(current_time))
    affected = 0
    for manifest in manifests:
        user_id = str(manifest["user_id"])
        requested_at = _utc_naive(manifest["requested_at"])
        operation = str(manifest["operation"])
        owner_exists = db.get(User, user_id) is not None
        db.rollback()
        if not owner_exists:
            continue
        lock_plan_writes(db, user_id)
        if db.get(User, user_id) is None:
            db.rollback()
            continue
        job_id = str(manifest["job_id"])
        job = db.get(PersonalContextDeletionJob, job_id)
        if job is None:
            job = PersonalContextDeletionJob(
                id=job_id,
                user_id=user_id,
                operation=operation,
                lineage_id=_optional_str(manifest.get("lineage_id")),
                target_item_id=_optional_str(
                    manifest.get("target_item_id")
                ),
                reason=str(manifest["reason"]),
                status="running",
                attempts=1,
                requested_at=requested_at,
                started_at=current_time,
                updated_at=current_time,
            )
            db.add(job)
            db.flush()
        else:
            if (
                job.user_id != user_id
                or job.operation != operation
                or job.lineage_id
                != _optional_str(manifest.get("lineage_id"))
                or job.target_item_id
                != _optional_str(manifest.get("target_item_id"))
            ):
                db.rollback()
                raise PersonalContextDeletionError(
                    "Deletion manifest does not match its database job"
                )
            job.status = "running"
            job.attempts = (job.attempts or 0) + 1
            job.started_at = current_time
            job.updated_at = current_time
        try:
            affected += _apply_deletion_job(
                db,
                job,
                completed_at=current_time,
                created_before=(
                    None
                    if operation == "delete_owner_context"
                    else requested_at
                ),
            )
            job.status = "completed"
            job.failure_code = None
            job.completed_at = current_time
            job.updated_at = current_time
            manifest_values = _job_manifest_values(job)
            db.commit()
        except Exception as exc:
            db.rollback()
            raise PersonalContextDeletionError(
                "Could not replay a personal-context deletion manifest"
            ) from exc
        if manifest["status"] != "completed":
            _best_effort_mark_manifest_completed(
                manifest_values,
                current_time,
            )
    return affected


def stage_account_deletion_manifests(
    db: Session,
    user_ids: Sequence[str],
    *,
    now: datetime | None = None,
) -> list[AccountDeletionManifest]:
    """Write owner-wide restore markers before account context is deleted."""
    requested_at = _utc_naive(now or datetime.utcnow())
    manifests: list[AccountDeletionManifest] = []
    for user_id in dict.fromkeys(user_ids):
        lock_plan_writes(db, user_id)
        has_context = (
            db.query(PersonalContextItem.id)
            .filter(PersonalContextItem.user_id == user_id)
            .first()
            is not None
        )
        if not has_context:
            continue
        manifest = AccountDeletionManifest(
            job_id=str(uuid4()),
            user_id=user_id,
            requested_at=requested_at,
        )
        try:
            personal_context_deletion_storage.store_requested(
                job_id=manifest.job_id,
                user_id=user_id,
                operation="delete_owner_context",
                reason="account_deletion",
                requested_at=requested_at,
            )
        except personal_context_deletion_storage.DeletionManifestStorageError as exc:
            raise PersonalContextDeletionError(
                "Could not persist account context deletion manifest"
            ) from exc
        manifests.append(manifest)
    return manifests


def complete_account_deletion_manifests(
    manifests: Sequence[AccountDeletionManifest],
    *,
    now: datetime | None = None,
) -> None:
    """Best-effort completion update; requested markers already prevent restore."""
    completed_at = _utc_naive(now or datetime.utcnow())
    for manifest in manifests:
        try:
            personal_context_deletion_storage.mark_completed(
                job_id=manifest.job_id,
                user_id=manifest.user_id,
                operation="delete_owner_context",
                reason="account_deletion",
                requested_at=manifest.requested_at,
                completed_at=completed_at,
            )
        except personal_context_deletion_storage.DeletionManifestStorageError:
            logger.warning(
                "Account context deletion completed but its private manifest "
                "could not be marked complete"
            )


def _queue_deletion_job(
    db: Session,
    *,
    user_id: str,
    operation: str,
    reason: str,
    lineage_id: str | None,
    target_item_id: str | None,
    requested_at: datetime,
) -> PersonalContextDeletionJob:
    lock_plan_writes(db, user_id)
    query = db.query(PersonalContextDeletionJob).filter(
        PersonalContextDeletionJob.user_id == user_id,
        PersonalContextDeletionJob.operation == operation,
        PersonalContextDeletionJob.lineage_id == lineage_id,
        PersonalContextDeletionJob.target_item_id == target_item_id,
        PersonalContextDeletionJob.status != "completed",
    )
    job = query.with_for_update().first()
    if job is None:
        job = PersonalContextDeletionJob(
            id=str(uuid4()),
            user_id=user_id,
            operation=operation,
            lineage_id=lineage_id,
            target_item_id=target_item_id,
            reason=reason,
            status="pending",
            attempts=0,
            requested_at=requested_at,
            updated_at=requested_at,
        )
        db.add(job)
        db.flush()
    if operation != "purge_narrative":
        for item in _target_items(db, job, lock=True):
            item.state = "deleting"
            item.updated_at = requested_at
    try:
        _store_requested_manifest(job)
        db.commit()
    except personal_context_deletion_storage.DeletionManifestStorageError as exc:
        db.rollback()
        raise PersonalContextDeletionError(
            "Could not persist personal-context deletion manifest"
        ) from exc
    return job


def _run_deletion_job(
    db: Session,
    job_id: str,
    *,
    raise_on_failure: bool,
    now: datetime | None = None,
) -> bool:
    operation_time = _utc_naive(now or datetime.utcnow())
    db.rollback()
    job = db.get(PersonalContextDeletionJob, job_id)
    if job is None:
        return False
    if job.status == "completed":
        db.rollback()
        return True
    job_user_id = str(job.user_id)
    manifest_values = _job_manifest_values(job)
    try:
        personal_context_deletion_storage.store_requested(**manifest_values)
    except personal_context_deletion_storage.DeletionManifestStorageError as exc:
        _record_job_failure(db, job_id, exc, now=operation_time)
        if raise_on_failure:
            raise PersonalContextDeletionError(
                "Personal-context deletion manifest is unavailable"
            ) from exc
        return False

    db.rollback()
    lock_plan_writes(db, job_user_id)
    job = (
        db.query(PersonalContextDeletionJob)
        .filter(PersonalContextDeletionJob.id == job_id)
        .with_for_update()
        .one_or_none()
    )
    if job is None:
        db.rollback()
        return False
    if job.status == "completed":
        db.rollback()
        return True
    started_at = operation_time
    job.status = "running"
    job.attempts = (job.attempts or 0) + 1
    job.failure_code = None
    job.started_at = started_at
    job.updated_at = started_at
    if job.operation != "purge_narrative":
        for item in _target_items(db, job, lock=True):
            item.state = "deleting"
            item.updated_at = started_at
    job_user_id = str(job.user_id)
    db.commit()

    try:
        lock_plan_writes(db, job_user_id)
        job = (
            db.query(PersonalContextDeletionJob)
            .filter(PersonalContextDeletionJob.id == job_id)
            .with_for_update()
            .one()
        )
        completed_at = operation_time
        _apply_deletion_job(db, job, completed_at=completed_at)
        job.status = "completed"
        job.failure_code = None
        job.completed_at = completed_at
        job.updated_at = completed_at
        manifest_values = _job_manifest_values(job)
        db.commit()
    except Exception as exc:
        db.rollback()
        _record_job_failure(db, job_id, exc, now=operation_time)
        if raise_on_failure:
            raise PersonalContextDeletionError(
                "Personal-context dependency cleanup failed"
            ) from exc
        return False

    try:
        personal_context_deletion_storage.mark_completed(
            **manifest_values,
            completed_at=completed_at,
        )
    except personal_context_deletion_storage.DeletionManifestStorageError:
        logger.warning(
            "Personal-context deletion completed but its private manifest "
            "could not be marked complete"
        )
    return True


def _apply_deletion_job(
    db: Session,
    job: PersonalContextDeletionJob,
    *,
    completed_at: datetime,
    created_before: datetime | None = None,
) -> int:
    items = _target_items(
        db,
        job,
        lock=True,
        created_before=created_before,
    )
    if job.operation == "purge_narrative":
        if not items:
            return 0
        item = items[0]
        payload = _decrypt_payload(item)
        payload.pop("narrative", None)
        encrypted_payload, wrapped_dek = _encrypt_payload(payload)
        item.encrypted_payload = encrypted_payload
        item.wrapped_dek = wrapped_dek
        item.has_narrative = False
        item.narrative_purged_at = completed_at
        item.updated_at = completed_at
        _scrub_plan_revision_narrative(db, job.user_id, {item.id})
        return 1

    item_ids = {item.id for item in items}
    _retire_context_commands(
        db,
        job=job,
        item_ids=item_ids,
        retired_at=completed_at,
    )
    if not item_ids:
        return 0
    _scrub_plan_revision_context(db, job.user_id, item_ids)
    db.query(PersonalContextUseReceipt).filter(
        PersonalContextUseReceipt.user_id == job.user_id,
        PersonalContextUseReceipt.context_item_id.in_(item_ids),
    ).delete(synchronize_session=False)
    db.query(PersonalContextConsentReceipt).filter(
        PersonalContextConsentReceipt.user_id == job.user_id,
        PersonalContextConsentReceipt.context_item_id.in_(item_ids),
    ).delete(synchronize_session=False)
    db.query(PersonalContextItem).filter(
        PersonalContextItem.user_id == job.user_id,
        PersonalContextItem.id.in_(item_ids),
    ).delete(synchronize_session=False)
    return len(item_ids)


def _target_items(
    db: Session,
    job: PersonalContextDeletionJob,
    *,
    lock: bool,
    created_before: datetime | None = None,
) -> list[PersonalContextItem]:
    query = db.query(PersonalContextItem).filter(
        PersonalContextItem.user_id == job.user_id,
    )
    if job.operation == "delete_owner_context":
        pass
    elif job.operation == "delete_lineage":
        query = query.filter(
            PersonalContextItem.lineage_id == job.lineage_id,
        )
    else:
        query = query.filter(
            PersonalContextItem.lineage_id == job.lineage_id,
            PersonalContextItem.id == job.target_item_id,
        )
    if created_before is not None:
        query = query.filter(PersonalContextItem.created_at <= created_before)
    if lock:
        query = query.with_for_update()
    return query.order_by(PersonalContextItem.version.desc()).all()


def _record_job_failure(
    db: Session,
    job_id: str,
    exc: BaseException,
    *,
    now: datetime | None = None,
) -> None:
    try:
        db.rollback()
        job = db.get(PersonalContextDeletionJob, job_id)
        if job is None:
            return
        job_user_id = str(job.user_id)
        db.rollback()
        lock_plan_writes(db, job_user_id)
        job = (
            db.query(PersonalContextDeletionJob)
            .filter(PersonalContextDeletionJob.id == job_id)
            .with_for_update()
            .one_or_none()
        )
        if job is None or job.status == "completed":
            db.rollback()
            return
        job.status = "failed"
        job.failure_code = type(exc).__name__[:64]
        job.updated_at = _utc_naive(now or datetime.utcnow())
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Could not persist personal-context deletion failure state"
        )


def _scrub_plan_revision_context(
    db: Session,
    user_id: str,
    item_ids: set[str],
) -> None:
    rows = (
        db.query(PlanRevision)
        .filter(PlanRevision.user_id == user_id)
        .with_for_update()
        .all()
    )
    for revision in rows:
        details = revision.details
        if not isinstance(details, dict):
            continue
        updated = dict(details)
        references = updated.get("context_item_ids")
        referenced_ids = _revision_context_item_ids(updated)
        if not referenced_ids.intersection(item_ids):
            continue
        remaining = [
            str(value)
            for value in references
            if str(value) not in item_ids
        ] if isinstance(references, list) else []
        if remaining:
            updated["context_item_ids"] = remaining
        else:
            updated.pop("context_item_ids", None)
        updated.pop("context_use_receipt_ids", None)
        private_rationale = updated.pop("private_context_rationale", None)
        updated.pop("personal_context", None)
        rationale_is_private = updated.pop(
            "rationale_is_private",
            False,
        )
        if private_rationale is not None or rationale_is_private:
            updated["rationale"] = _PRIVATE_RATIONALE_REMOVED
        updated["personal_context_status"] = "removed_by_athlete"
        revision.details = updated


def _scrub_plan_revision_narrative(
    db: Session,
    user_id: str,
    item_ids: set[str],
) -> None:
    rows = (
        db.query(PlanRevision)
        .filter(PlanRevision.user_id == user_id)
        .with_for_update()
        .all()
    )
    for revision in rows:
        details = revision.details
        if not isinstance(details, dict):
            continue
        updated = dict(details)
        if not _revision_context_item_ids(updated).intersection(item_ids):
            continue
        private_rationale = updated.pop("private_context_rationale", None)
        rationale_is_private = updated.pop(
            "rationale_is_private",
            False,
        )
        if private_rationale is not None or rationale_is_private:
            updated["rationale"] = _PRIVATE_RATIONALE_REMOVED
        revision.details = updated


def _revision_context_item_ids(details: Mapping[str, Any]) -> set[str]:
    references = details.get("context_item_ids")
    item_ids = (
        {str(value) for value in references}
        if isinstance(references, list)
        else set()
    )
    envelope = details.get("personal_context")
    if isinstance(envelope, dict):
        envelope_refs = envelope.get("item_ids")
        if isinstance(envelope_refs, list):
            item_ids.update(str(value) for value in envelope_refs)
    return item_ids


def _owned_item(
    db: Session,
    user_id: str,
    item_id: str,
    *,
    lock: bool,
) -> PersonalContextItem | None:
    query = db.query(PersonalContextItem).filter(
        PersonalContextItem.user_id == user_id,
        PersonalContextItem.id == item_id,
    )
    if lock:
        query = query.with_for_update()
    return query.one_or_none()


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise PersonalContextValidationError("Context payload must be an object")
    unknown = set(payload) - {"category", "fields", "narrative"}
    if unknown:
        raise PersonalContextValidationError(
            "Context payload contains unsupported fields"
        )
    category = payload.get("category")
    if category not in CONTEXT_CATEGORIES:
        raise PersonalContextValidationError("Context category is invalid")
    raw_fields = payload.get("fields", {})
    if not isinstance(raw_fields, Mapping) or len(raw_fields) > 20:
        raise PersonalContextValidationError(
            "Context structured fields are invalid"
        )
    fields: dict[str, Any] = {}
    for key, value in raw_fields.items():
        if not isinstance(key, str) or not _FIELD_NAME_RE.fullmatch(key):
            raise PersonalContextValidationError(
                "Context structured field name is invalid"
            )
        fields[key] = _normalize_field_value(value)
    normalized: dict[str, Any] = {
        "category": category,
        "fields": fields,
    }
    narrative = payload.get("narrative")
    if narrative is not None:
        if not isinstance(narrative, str):
            raise PersonalContextValidationError(
                "Context narrative must be text"
            )
        if not narrative or len(narrative) > MAX_NARRATIVE_CHARS:
            raise PersonalContextValidationError(
                "Context narrative length is invalid"
            )
        normalized["narrative"] = narrative
    try:
        encoded = json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PersonalContextValidationError(
            "Context payload is not JSON-safe"
        ) from exc
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise PersonalContextValidationError("Context payload is too large")
    return normalized


def _normalize_field_value(value: Any, *, depth: int = 0) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        if abs(value) > 1_000_000:
            raise PersonalContextValidationError(
                "Context numeric field is out of range"
            )
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or abs(value) > 1_000_000:
            raise PersonalContextValidationError(
                "Context numeric field is out of range"
            )
        return value
    if isinstance(value, str):
        if len(value) > 120:
            raise PersonalContextValidationError(
                "Context structured text is too long"
            )
        return value
    if isinstance(value, (list, tuple)):
        if depth >= 1 or len(value) > 31:
            raise PersonalContextValidationError(
                "Context structured list is too long"
            )
        return [
            _normalize_field_value(item, depth=depth + 1)
            for item in value
        ]
    raise PersonalContextValidationError(
        "Context structured field type is invalid"
    )


def _validate_metadata(
    *,
    kind: str,
    purpose: str,
    source_actor_type: str,
    source_actor_id: str | None,
    linked_subject_type: str | None,
    linked_subject_id: str | None,
) -> None:
    if kind not in CONTEXT_KINDS:
        raise PersonalContextValidationError("Context kind is invalid")
    if purpose not in CONTEXT_PURPOSES:
        raise PersonalContextValidationError("Context purpose is invalid")
    if source_actor_type not in SOURCE_ACTOR_TYPES:
        raise PersonalContextValidationError("Context source actor is invalid")
    _validate_opaque(source_actor_id, field="source_actor_id", maximum=120)
    if linked_subject_type not in LINKED_SUBJECT_TYPES | {None}:
        raise PersonalContextValidationError(
            "Context linked subject type is invalid"
        )
    if (linked_subject_type is None) != (linked_subject_id is None):
        raise PersonalContextValidationError(
            "Context linked subject is incomplete"
        )
    _validate_opaque(linked_subject_id, field="linked_subject_id", maximum=120)


def _validate_linked_subject(
    db: Session,
    *,
    user_id: str,
    linked_subject_type: str | None,
    linked_subject_id: str | None,
) -> None:
    if linked_subject_type is None or linked_subject_id is None:
        return
    exists = False
    if linked_subject_type in {"plan", "workout"}:
        exists = (
            db.query(TrainingPlan.id)
            .filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.canonical_id == linked_subject_id,
            )
            .first()
            is not None
        )
    elif linked_subject_type == "execution_event":
        exists = (
            db.query(Activity.id)
            .filter(
                Activity.user_id == user_id,
                Activity.activity_id == linked_subject_id,
            )
            .first()
            is not None
        )
    elif linked_subject_type == "goal":
        exists = (
            db.query(UserConfig.user_id)
            .filter(UserConfig.user_id == user_id)
            .first()
            is not None
        )
    if not exists:
        raise PersonalContextUnavailable(
            "Personal context linked subject is unavailable"
        )


def _validate_idempotency_key(value: str) -> str:
    if not isinstance(value, str) or not _IDEMPOTENCY_KEY_RE.fullmatch(value):
        raise PersonalContextValidationError(
            "Personal context idempotency key is invalid"
        )
    return value


def _context_command(
    db: Session,
    *,
    user_id: str,
    idempotency_key: str,
    lock: bool,
) -> PersonalContextCommand | None:
    query = db.query(PersonalContextCommand).filter(
        PersonalContextCommand.user_id == user_id,
        PersonalContextCommand.idempotency_key == idempotency_key,
    )
    if lock:
        query = query.with_for_update()
    return query.one_or_none()


def _command_target_item(
    db: Session,
    *,
    command: PersonalContextCommand,
    operation: str,
) -> PersonalContextItem:
    if (
        command.status != "active"
        or command.operation != operation
        or command.target_item_id is None
        or command.lineage_id is None
    ):
        raise PersonalContextConflict(
            "Personal context command is no longer replayable"
        )
    item = _owned_item(
        db,
        str(command.user_id),
        str(command.target_item_id),
        lock=True,
    )
    if (
        item is None
        or item.lineage_id != command.lineage_id
        or item.state == "deleting"
    ):
        raise PersonalContextConflict(
            "Personal context command is no longer replayable"
        )
    return item


def _create_context_command(
    db: Session,
    *,
    user_id: str,
    idempotency_key: str,
    operation: str,
    item: PersonalContextItem,
    created_at: datetime,
) -> PersonalContextCommand:
    command = PersonalContextCommand(
        id=str(uuid4()),
        user_id=user_id,
        idempotency_key=idempotency_key,
        operation=operation,
        target_item_id=item.id,
        lineage_id=item.lineage_id,
        status="active",
        created_at=_utc_naive(created_at),
        retired_at=None,
    )
    db.add(command)
    db.flush()
    return command


def _retire_context_commands(
    db: Session,
    *,
    job: PersonalContextDeletionJob,
    item_ids: set[str],
    retired_at: datetime,
) -> None:
    query = db.query(PersonalContextCommand).filter(
        PersonalContextCommand.user_id == job.user_id,
        PersonalContextCommand.status == "active",
    )
    if item_ids:
        query = query.filter(
            PersonalContextCommand.target_item_id.in_(item_ids)
        )
    elif job.operation == "delete_owner_context":
        pass
    elif job.operation == "delete_lineage":
        query = query.filter(
            PersonalContextCommand.lineage_id == job.lineage_id
        )
    else:
        query = query.filter(
            PersonalContextCommand.target_item_id == job.target_item_id
        )
    for command in query.with_for_update().all():
        command.status = "retired"
        command.target_item_id = None
        command.lineage_id = None
        command.retired_at = _utc_naive(retired_at)


def _assert_context_command_matches(
    item: PersonalContextItem,
    *,
    preview: ContextPreview,
    source_actor_type: str,
    source_actor_id: str | None,
    supersedes_id: str | None,
) -> None:
    payload = _decrypt_payload(item)
    matches = (
        payload == preview.payload
        and item.kind == preview.kind
        and item.purpose == preview.purpose
        and item.source_actor_type == source_actor_type
        and item.source_actor_id == source_actor_id
        and item.linked_subject_type == preview.linked_subject_type
        and item.linked_subject_id == preview.linked_subject_id
        and item.supersedes_id == supersedes_id
        and _utc_naive(item.starts_at) == preview.starts_at
        and _optional_utc_naive(item.expires_at) == preview.expires_at
        and _optional_utc_naive(item.purge_after) == preview.purge_after
        and _optional_utc_naive(item.narrative_purge_at)
        == preview.narrative_purge_at
    )
    if not matches:
        raise PersonalContextConflict(
            "Personal context idempotency key was reused"
        )


def _idempotent_purpose_receipt(
    db: Session,
    *,
    item: PersonalContextItem,
    consent_text_version: str,
    client: str,
    idempotency_key: str,
    decided_at: datetime,
) -> PersonalContextConsentReceipt:
    existing = (
        db.query(PersonalContextConsentReceipt)
        .filter(
            PersonalContextConsentReceipt.user_id == item.user_id,
            PersonalContextConsentReceipt.idempotency_key == idempotency_key,
        )
        .with_for_update()
        .one_or_none()
    )
    if existing is not None:
        if not _consent_receipt_matches(
            existing,
            item=item,
            consent_scope="purpose_confirmation",
            provider=None,
            disclosed_fields=[],
            narrative_disclosed=False,
            consent_text_version=consent_text_version,
            decision="granted",
            client=client,
        ):
            raise PersonalContextConflict(
                "Personal context idempotency key was reused"
            )
        return existing
    receipt = PersonalContextConsentReceipt(
        id=str(uuid4()),
        user_id=item.user_id,
        context_item_id=item.id,
        context_version=item.version,
        purpose=item.purpose,
        consent_scope="purpose_confirmation",
        provider=None,
        disclosed_fields=[],
        narrative_disclosed=False,
        consent_text_version=consent_text_version,
        decision="granted",
        client=client,
        idempotency_key=idempotency_key,
        decided_at=_utc_naive(decided_at),
    )
    db.add(receipt)
    db.flush()
    return receipt


def _consent_receipt_matches(
    receipt: PersonalContextConsentReceipt,
    *,
    item: PersonalContextItem,
    consent_scope: str,
    provider: str | None,
    disclosed_fields: Sequence[str],
    narrative_disclosed: bool,
    consent_text_version: str,
    decision: str,
    client: str,
) -> bool:
    return (
        receipt.context_item_id == item.id
        and receipt.context_version == item.version
        and receipt.purpose == item.purpose
        and receipt.consent_scope == consent_scope
        and receipt.provider == provider
        and list(receipt.disclosed_fields or []) == list(disclosed_fields)
        and receipt.narrative_disclosed == narrative_disclosed
        and receipt.consent_text_version == consent_text_version
        and receipt.decision == decision
        and receipt.client == client
    )


def _validate_lifetime(
    *,
    kind: str,
    has_narrative: bool,
    starts_at: datetime,
    expires_at: datetime | None,
    purge_after: datetime | None,
    narrative_purge_at: datetime | None,
    captured_at: datetime,
) -> tuple[datetime, datetime | None, datetime | None, datetime | None]:
    active_from = _utc_naive(starts_at)
    active_until = _optional_utc_naive(expires_at)
    retain_until = _optional_utc_naive(purge_after)
    narrative_until = _optional_utc_naive(narrative_purge_at)
    if kind == "durable_preference":
        if active_until is not None or retain_until is not None or has_narrative:
            raise PersonalContextValidationError(
                "Durable context cannot use pilot expiry or narrative"
            )
    else:
        if active_until is None or retain_until is None:
            raise PersonalContextValidationError(
                "Non-durable context requires expiry and purge dates"
            )
        if active_until <= active_from or retain_until < active_until:
            raise PersonalContextValidationError(
                "Context lifetime order is invalid"
            )
        if kind == "temporary_constraint":
            if active_until - active_from > TEMPORARY_ACTIVE_LIMIT:
                raise PersonalContextValidationError(
                    "Temporary context exceeds the 90-day active limit"
                )
            if retain_until > (
                active_until + TEMPORARY_POST_EXPIRY_RETENTION
            ):
                raise PersonalContextValidationError(
                    "Temporary context exceeds post-expiry retention"
                )
        elif retain_until > captured_at + EXECUTION_TOTAL_RETENTION:
            raise PersonalContextValidationError(
                "Execution context exceeds total retention"
            )
    if has_narrative:
        maximum = captured_at + NARRATIVE_RETENTION
        narrative_until = narrative_until or maximum
        if narrative_until <= captured_at or narrative_until > maximum:
            raise PersonalContextValidationError(
                "Context narrative retention is invalid"
            )
    elif narrative_until is not None:
        raise PersonalContextValidationError(
            "Narrative purge date requires a narrative"
        )
    return active_from, active_until, retain_until, narrative_until


def _encrypt_payload(payload: Mapping[str, Any]) -> tuple[bytes, bytes]:
    try:
        vault = get_vault()
        if not vault.is_persistent:
            raise PersonalContextAccessError(
                "Persistent encryption is required for personal context"
            )
        serialized = json.dumps(
            dict(payload),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        return vault.encrypt(serialized)
    except PersonalContextAccessError:
        raise
    except (AzureError, InvalidToken, TypeError, ValueError) as exc:
        raise PersonalContextAccessError(
            "Personal context could not be encrypted"
        ) from exc


def _decrypt_payload(item: PersonalContextItem) -> dict[str, Any]:
    if item.payload_schema_version != PAYLOAD_SCHEMA_VERSION:
        raise PersonalContextAccessError(
            "Personal context payload schema is unsupported"
        )
    try:
        raw = get_vault().decrypt(
            bytes(item.encrypted_payload),
            bytes(item.wrapped_dek),
        )
        payload = json.loads(raw)
    except (
        AzureError,
        InvalidToken,
        json.JSONDecodeError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
    ) as exc:
        raise PersonalContextAccessError(
            "Personal context could not be decrypted"
        ) from exc
    if not isinstance(payload, dict):
        raise PersonalContextAccessError(
            "Personal context payload is malformed"
        )
    try:
        return _normalize_payload(payload)
    except PersonalContextValidationError as exc:
        raise PersonalContextAccessError(
            "Personal context payload is malformed"
        ) from exc


def _normalize_disclosed_fields(values: Sequence[str]) -> list[str]:
    if isinstance(values, (str, bytes)) or len(values) > 32:
        raise PersonalContextValidationError(
            "Context disclosed fields are invalid"
        )
    normalized: list[str] = []
    for value in values:
        if (
            not isinstance(value, str)
            or not _DISCLOSED_FIELD_RE.fullmatch(value)
        ):
            raise PersonalContextValidationError(
                "Context disclosed field is invalid"
            )
        if value not in normalized:
            normalized.append(value)
    return normalized


def _validate_opaque(
    value: str | None,
    *,
    field: str,
    maximum: int,
    required: bool = False,
) -> None:
    if value is None:
        if required:
            raise PersonalContextValidationError(f"{field} is required")
        return
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise PersonalContextValidationError(f"{field} is invalid")


def _is_expired(item: PersonalContextItem, now: datetime) -> bool:
    return item.expires_at is not None and item.expires_at <= now


def _utc_naive(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise PersonalContextValidationError("Context timestamp is invalid")
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _optional_utc_naive(value: datetime | None) -> datetime | None:
    return _utc_naive(value) if value is not None else None


def _optional_str(value: object) -> str | None:
    return str(value) if value is not None else None


def _export_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _utc_naive(value).replace(tzinfo=timezone.utc).isoformat()


def _store_requested_manifest(job: PersonalContextDeletionJob) -> None:
    personal_context_deletion_storage.store_requested(
        **_job_manifest_values(job)
    )


def _job_manifest_values(
    job: PersonalContextDeletionJob,
) -> dict[str, Any]:
    return {
        "job_id": job.id,
        "user_id": job.user_id,
        "operation": job.operation,
        "reason": job.reason,
        "requested_at": job.requested_at,
        "lineage_id": job.lineage_id,
        "target_item_id": job.target_item_id,
    }


def _best_effort_mark_manifest_completed(
    manifest_values: Mapping[str, Any],
    completed_at: datetime,
) -> None:
    try:
        personal_context_deletion_storage.mark_completed(
            **manifest_values,
            completed_at=completed_at,
        )
    except personal_context_deletion_storage.DeletionManifestStorageError:
        logger.warning(
            "Replayed context deletion but could not mark its manifest complete"
        )
