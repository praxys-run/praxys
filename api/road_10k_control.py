"""Road-10K-specific control ledger and transaction-time gate.

This module is the only place that mutates the Road 10K control tables.  It
does not call provider, AI, MCP, plugin, or automatic-adoption code.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from typing import Any, Mapping
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.road_10k_deletion_storage import (
    Road10KDeletionStorageError,
    mark_completed,
    replay_manifests,
    replay_status,
    stage_manifest,
)
from api.road_10k_screenshot_storage import delete_manifest_object
from api.road_10k_stage_authority import (
    Road10KStageAuthority,
    authority_denial_reason,
    load_stage_authority,
)
from db.models import (
    Feedback,
    Road10KEvaluation,
    Road10KExposureReceipt,
    Road10KOwnerStageReceipt,
    Road10KStageCounter,
    Road10KScreenshotReference,
    User,
)
from db.session import begin_serialized_write

logger = logging.getLogger(__name__)

ROAD_10K_STAGE_ID = "road-10k-controlled-opt-in-v1"
ROAD_10K_POLICY_VERSION = "road-10k-plan-generation-policy-v2"
ROAD_10K_CONTROL_SCHEMA_VERSION = 2
ROAD_10K_INVITATION_CEILING = 60
ROAD_10K_EXPOSURE_CEILING = 30
ROAD_10K_EVALUATION_RETENTION_DAYS = 30
_ROAD_10K_STAGE_LOCK_KEY = 0x524F414431304B


class Road10KControlError(RuntimeError):
    """Base class for fail-closed control errors."""


class Road10KControlUnavailable(Road10KControlError):
    """Authority, runtime, provider fence, or schema is unavailable."""


class Road10KControlConflict(Road10KControlError):
    """An idempotency key or owner/stage request conflicts."""


class Road10KControlDenied(Road10KControlError):
    """The current owner or cumulative ceiling cannot perform the action."""


class Road10KDeletionFailed(Road10KControlError):
    """Deletion could not be staged or completed authoritatively."""


def receipt_matches_authority(
    receipt: Road10KOwnerStageReceipt,
    authority: Road10KStageAuthority,
) -> bool:
    """Validate the complete receipt contract at every control boundary."""
    return (
        receipt.stage_id == authority.stage_id
        and receipt.capability_id == authority.capability_id
        and receipt.authority_digest == authority.authority_digest
        and receipt.notice_digest == authority.notice_digest
        and receipt.cohort_rule_digest == authority.cohort_rule_digest
        and receipt.schema_version == ROAD_10K_CONTROL_SCHEMA_VERSION
        and receipt.policy_version == ROAD_10K_POLICY_VERSION
    )


def _now(now: datetime | None = None) -> datetime:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _fingerprint(operation: str, **values: object) -> str:
    payload = json.dumps(
        {"operation": operation, **values},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _authority(*, lifecycle: bool = False) -> Road10KStageAuthority:
    authority = load_stage_authority()
    if authority is None:
        raise Road10KControlUnavailable("authority_missing_or_malformed")
    if authority.lifecycle_status is None or (
        authority.lifecycle_status != "active" and not lifecycle
    ):
        raise Road10KControlUnavailable(
            authority_denial_reason(authority)
        )
    if authority.stage_id != ROAD_10K_STAGE_ID:
        raise Road10KControlUnavailable("stage_mismatch")
    return authority


def _counter(
    db: Session,
    authority: Road10KStageAuthority,
    *,
    create: bool = True,
) -> Road10KStageCounter:
    counter = (
        db.query(Road10KStageCounter)
        .with_for_update()
        .filter(Road10KStageCounter.stage_id == authority.stage_id)
        .first()
    )
    if counter is None and create:
        counter = Road10KStageCounter(
            stage_id=authority.stage_id,
            schema_version=ROAD_10K_CONTROL_SCHEMA_VERSION,
            capability_id=authority.capability_id,
            invitation_ceiling=authority.invitation_ceiling,
            exposure_ceiling=authority.exposure_ceiling,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(counter)
        db.flush()
    if counter is None:
        raise Road10KControlUnavailable("counter_missing")
    if (
        counter.schema_version != ROAD_10K_CONTROL_SCHEMA_VERSION
        or counter.capability_id != authority.capability_id
        or counter.invitation_ceiling != authority.invitation_ceiling
        or counter.exposure_ceiling != authority.exposure_ceiling
        or counter.invitation_slots_consumed < 0
        or counter.invitation_slots_consumed > ROAD_10K_INVITATION_CEILING
        or counter.distinct_exposed_owners_consumed < 0
        or counter.distinct_exposed_owners_consumed > ROAD_10K_EXPOSURE_CEILING
    ):
        raise Road10KControlUnavailable("counter_mismatch")
    return counter


def _begin_control_write(db: Session) -> None:
    """Serialize the singleton counter on both supported primary dialects."""
    begin_serialized_write(db)
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:road_10k_lock)"),
            {"road_10k_lock": _ROAD_10K_STAGE_LOCK_KEY},
        )


def _assert_owner(db: Session, user_id: str) -> User:
    if not isinstance(user_id, str) or not user_id:
        raise Road10KControlDenied("owner_required")
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .with_for_update()
        .first()
    )
    if user is None or not user.is_active or user.is_demo:
        raise Road10KControlDenied("first_party_owner_required")
    return user


def _receipt(
    db: Session,
    *,
    user_id: str,
    stage_id: str,
    lock: bool = True,
) -> Road10KOwnerStageReceipt | None:
    query = db.query(Road10KOwnerStageReceipt).filter(
        Road10KOwnerStageReceipt.user_id == user_id,
        Road10KOwnerStageReceipt.stage_id == stage_id,
    )
    if lock:
        query = query.with_for_update()
    return query.first()


def issue_invitation(
    db: Session,
    *,
    user_id: str,
    idempotency_key: str,
    notice_digest: str,
    cohort_rule_digest: str,
    now: datetime | None = None,
) -> Road10KOwnerStageReceipt:
    """Consume one cumulative invitation, idempotently, under the counter lock."""
    authority = _authority()
    if not 8 <= len(idempotency_key) <= 128:
        raise Road10KControlDenied("invalid_idempotency_key")
    if (
        notice_digest != authority.notice_digest
        or cohort_rule_digest != authority.cohort_rule_digest
    ):
        raise Road10KControlUnavailable("authority_digest_mismatch")
    fingerprint = _fingerprint(
        "invitation",
        user_id=user_id,
        stage_id=authority.stage_id,
        notice_digest=notice_digest,
        cohort_rule_digest=cohort_rule_digest,
    )
    db.rollback()
    _begin_control_write(db)
    try:
        _assert_owner(db, user_id)
        counter = _counter(db, authority)
        existing = _receipt(
            db,
            user_id=user_id,
            stage_id=authority.stage_id,
        )
        if existing is not None:
            if not receipt_matches_authority(existing, authority):
                raise Road10KControlUnavailable("receipt_contract_mismatch")
            if existing.request_fingerprint != fingerprint:
                raise Road10KControlConflict("owner_stage_conflict")
            db.commit()
            return existing
        by_key = (
            db.query(Road10KOwnerStageReceipt)
            .with_for_update()
            .filter(
                Road10KOwnerStageReceipt.stage_id == authority.stage_id,
                Road10KOwnerStageReceipt.invitation_idempotency_key
                == idempotency_key,
            )
            .first()
        )
        if by_key is not None:
            if by_key.request_fingerprint != fingerprint:
                raise Road10KControlConflict("idempotency_conflict")
            db.commit()
            return by_key
        if counter.invitation_slots_consumed >= counter.invitation_ceiling:
            raise Road10KControlDenied("invitation_cap")
        timestamp = _now(now)
        receipt = Road10KOwnerStageReceipt(
            id=str(uuid4()),
            user_id=user_id,
            stage_id=authority.stage_id,
            capability_id=authority.capability_id,
            schema_version=ROAD_10K_CONTROL_SCHEMA_VERSION,
            policy_version=ROAD_10K_POLICY_VERSION,
            authority_digest=authority.authority_digest,
            notice_digest=notice_digest,
            cohort_rule_digest=cohort_rule_digest,
            invitation_idempotency_key=idempotency_key,
            state="invited_only",
            invitation_issued_at=timestamp,
            request_fingerprint=fingerprint,
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(receipt)
        counter.invitation_slots_consumed += 1
        counter.updated_at = timestamp
        db.commit()
        return receipt
    except Exception:
        db.rollback()
        raise


def enroll_owner(
    db: Session,
    *,
    user_id: str,
    notice_digest: str,
    now: datetime | None = None,
) -> Road10KOwnerStageReceipt:
    """Move an invited owner to enrolled_unexposed without consuming exposure."""
    authority = _authority()
    if notice_digest != authority.notice_digest:
        raise Road10KControlUnavailable("notice_mismatch")
    preflight = _receipt(
        db,
        user_id=user_id,
        stage_id=authority.stage_id,
        lock=False,
    )
    if preflight is None:
        raise Road10KControlDenied("invitation_required")
    if not receipt_matches_authority(preflight, authority):
        raise Road10KControlUnavailable("receipt_contract_mismatch")
    if preflight.state in {"withdrawn", "deleted"}:
        raise Road10KControlDenied("same_stage_reenrollment_denied")
    db.rollback()
    _begin_control_write(db)
    try:
        _assert_owner(db, user_id)
        _counter(db, authority)
        receipt = _receipt(
            db,
            user_id=user_id,
            stage_id=authority.stage_id,
        )
        if receipt is None:
            raise Road10KControlDenied("invitation_required")
        if not receipt_matches_authority(receipt, authority):
            raise Road10KControlUnavailable("receipt_contract_mismatch")
        if receipt.state in {"withdrawn", "deleted"}:
            raise Road10KControlDenied("same_stage_reenrollment_denied")
        if receipt.state in {"enrolled_unexposed", "exposed"}:
            db.commit()
            return receipt
        receipt.state = "enrolled_unexposed"
        receipt.enrolled_at = _now(now)
        receipt.updated_at = _now(now)
        db.commit()
        return receipt
    except Exception:
        db.rollback()
        raise


def authorize_first_exposure(
    db: Session,
    *,
    user_id: str,
    now: datetime | None = None,
) -> Road10KExposureReceipt:
    """Commit the first exposure receipt before a result can be serialized."""
    authority = _authority()
    if not isinstance(user_id, str) or not user_id:
        raise Road10KControlDenied("owner_required")
    preflight_user = db.query(User).filter(User.id == user_id).first()
    preflight_receipt = _receipt(
        db,
        user_id=user_id,
        stage_id=authority.stage_id,
        lock=False,
    )
    if (
        preflight_user is None
        or not preflight_user.is_active
        or preflight_user.is_demo
        or preflight_receipt is None
        or preflight_receipt.state not in {"enrolled_unexposed", "exposed"}
    ):
        raise Road10KControlDenied("enrollment_required")
    db.rollback()
    _begin_control_write(db)
    try:
        _assert_owner(db, user_id)
        counter = _counter(db, authority)
        receipt = _receipt(
            db,
            user_id=user_id,
            stage_id=authority.stage_id,
        )
        if receipt is None or receipt.state not in {"enrolled_unexposed", "exposed"}:
            raise Road10KControlDenied("enrollment_required")
        if not receipt_matches_authority(receipt, authority):
            raise Road10KControlUnavailable("receipt_contract_mismatch")
        existing = (
            db.query(Road10KExposureReceipt)
            .with_for_update()
            .filter(
                Road10KExposureReceipt.stage_id == authority.stage_id,
                Road10KExposureReceipt.user_id == user_id,
            )
            .first()
        )
        if existing is not None:
            db.commit()
            return existing
        if counter.distinct_exposed_owners_consumed >= counter.exposure_ceiling:
            raise Road10KControlDenied("exposure_cap")
        timestamp = _now(now)
        exposure = Road10KExposureReceipt(
            id=str(uuid4()),
            stage_id=authority.stage_id,
            user_id=user_id,
            owner_stage_receipt_id=receipt.id,
            authority_digest=authority.authority_digest,
            exposed_at=timestamp,
        )
        db.add(exposure)
        receipt.state = "exposed"
        receipt.first_exposed_at = timestamp
        receipt.updated_at = timestamp
        counter.distinct_exposed_owners_consumed += 1
        counter.updated_at = timestamp
        db.commit()
        return exposure
    except IntegrityError as exc:
        db.rollback()
        raise Road10KControlUnavailable("exposure_reconciliation_required") from exc
    except Exception:
        db.rollback()
        raise


def require_road_10k_gate(
    db: Session,
    *,
    user_id: str,
    expose: bool,
    allow_lifecycle: bool = False,
    allow_withdrawn: bool = False,
) -> Road10KStageAuthority:
    """Apply the shared owner/authority gate before a Road 10K service read.

    New readiness/result requests use ``expose=True`` so the serialized
    exposure receipt and cap counter commit before any policy data is read.
    Adoption revalidation uses ``expose=False`` inside the existing plan
    transaction and therefore only accepts an already-exposed owner.
    """
    authority = _authority(lifecycle=allow_lifecycle)
    if expose:
        authorize_first_exposure(db, user_id=user_id)
        return authority
    if not isinstance(user_id, str) or not user_id:
        raise Road10KControlDenied("owner_required")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active or user.is_demo:
        raise Road10KControlDenied("first_party_owner_required")
    receipt = _receipt(
        db,
        user_id=user_id,
        stage_id=authority.stage_id,
        lock=False,
    )
    if (
        receipt is None
        or receipt.state
        not in ({"exposed", "withdrawn"} if allow_withdrawn else {"exposed"})
        or not receipt_matches_authority(receipt, authority)
    ):
        raise Road10KControlDenied("road_10k_exposure_required")
    exposure = (
        db.query(Road10KExposureReceipt)
        .filter(
            Road10KExposureReceipt.stage_id == authority.stage_id,
            Road10KExposureReceipt.user_id == user_id,
        )
        .first()
    )
    if exposure is None or exposure.authority_digest != authority.authority_digest:
        raise Road10KControlDenied("road_10k_exposure_required")
    counter = _counter(db, authority, create=False)
    if counter.distinct_exposed_owners_consumed > authority.exposure_ceiling:
        raise Road10KControlUnavailable("exposure_cap_mismatch")
    return authority


def require_road_10k_participation(
    db: Session,
    *,
    user_id: str,
    allow_withdrawn: bool = False,
    lifecycle: bool = False,
) -> Road10KStageAuthority:
    """Check owner participation without creating an exposure receipt."""
    authority = _authority(lifecycle=lifecycle)
    if not isinstance(user_id, str) or not user_id:
        raise Road10KControlDenied("owner_required")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active or user.is_demo:
        raise Road10KControlDenied("first_party_owner_required")
    states = {"invited_only", "enrolled_unexposed", "exposed"}
    if allow_withdrawn:
        states.add("withdrawn")
    receipt = _receipt(
        db,
        user_id=user_id,
        stage_id=authority.stage_id,
        lock=False,
    )
    if (
        receipt is None
        or receipt.state not in states
        or not receipt_matches_authority(receipt, authority)
    ):
        raise Road10KControlDenied("participation_required")
    return authority


def record_result(
    db: Session,
    *,
    user_id: str,
    result_code: str,
    payload: dict[str, Any],
    now: datetime | None = None,
) -> Road10KEvaluation:
    """Record a deletable result only after the exposure receipt is committed."""
    authority = _authority()
    if result_code not in {
        "eligible_rolling_proposal",
        "eligible_taper_proposal",
        "missing_or_stale_direct_baseline",
        "insufficient_recent_history",
        "limited_guidance_event_conflict",
        "limited_near_term_guidance",
        "safety_stop",
        "adult_scope_or_constraints_unconfirmed",
        "contradictory_input",
        "unsupported_intent_distance_surface_or_population",
        "no_schedule_within_envelope",
        "validation_failed",
    }:
        raise Road10KControlDenied("invalid_result_code")
    authorize_first_exposure(db, user_id=user_id, now=now)
    timestamp = _now(now)
    db.add(
        evaluation := Road10KEvaluation(
            id=str(uuid4()),
            user_id=user_id,
            stage_id=authority.stage_id,
            result_code=result_code,
            payload=dict(payload),
            created_at=timestamp,
            expires_at=timestamp + timedelta(days=ROAD_10K_EVALUATION_RETENTION_DAYS),
        )
    )
    db.commit()
    return evaluation


def _delete_evaluation_rows(
    db: Session,
    evaluation_ids: list[str],
    *,
    reason: str,
) -> None:
    if not evaluation_ids:
        return
    rows = (
        db.query(Road10KEvaluation)
        .filter(Road10KEvaluation.id.in_(evaluation_ids))
        .with_for_update()
        .all()
    )
    for row in rows:
        row.payload = {}
        row.deleted_at = datetime.utcnow()
        row.deletion_reason = reason
        db.query(Road10KScreenshotReference).filter(
            Road10KScreenshotReference.evaluation_id == row.id
        ).delete(synchronize_session=False)
        db.delete(row)


def _delete_feedback_for_manifest(
    db: Session,
    manifest: dict[str, object] | Mapping[str, object],
) -> None:
    """Remove restored feedback links covered by an account-deletion marker."""
    keys = {
        str(key)
        for key in manifest["screenshot_keys"]
        if isinstance(key, str) and key.startswith("feedback/")
    }
    if not keys:
        return
    owner_id = str(manifest["owner_id"])
    rows = (
        db.query(Feedback)
        .filter(Feedback.user_id == owner_id)
        .with_for_update()
        .all()
    )
    for row in rows:
        image_keys = row.image_keys
        if not isinstance(image_keys, list):
            continue
        remaining = [
            key
            for key in image_keys
            if not (isinstance(key, str) and key in keys)
        ]
        if len(remaining) == len(image_keys):
            continue
        if remaining:
            row.image_keys = remaining
        else:
            # Account deletion already removes the row in the live path.  If
            # the primary DB is restored independently, delete the resurrected
            # row instead of allowing its screenshot linkage to return.
            db.delete(row)


def _evaluation_expiry(row: Road10KEvaluation) -> datetime:
    """Return the immutable creation-based retention deadline."""
    return row.created_at + timedelta(days=ROAD_10K_EVALUATION_RETENTION_DAYS)


def _owner_deletion_manifest(
    db: Session,
    *,
    user_id: str,
    stage_id: str,
    reason: str,
    now: datetime,
    evaluation_ids: list[str] | None = None,
    include_feedback: bool = False,
) -> dict[str, object]:
    if evaluation_ids is None:
        evaluations = (
            db.query(Road10KEvaluation)
            .filter(
                Road10KEvaluation.user_id == user_id,
                Road10KEvaluation.stage_id == stage_id,
                Road10KEvaluation.deleted_at.is_(None),
            )
            .all()
        )
        evaluation_ids = [row.id for row in evaluations]
    screenshot_keys = [
        key
        for (key,) in db.query(Road10KScreenshotReference.object_key)
        .filter(Road10KScreenshotReference.evaluation_id.in_(evaluation_ids))
        .all()
    ] if evaluation_ids else []
    if include_feedback:
        feedback_rows = (
            db.query(Feedback.image_keys)
            .filter(Feedback.user_id == user_id)
            .all()
        )
        for (image_keys,) in feedback_rows:
            if isinstance(image_keys, list):
                screenshot_keys.extend(
                    str(key) for key in image_keys if isinstance(key, str)
                )
    try:
        return stage_manifest(
            owner_id=user_id,
            stage_id=stage_id,
            reason=reason,
            evaluation_ids=evaluation_ids,
            screenshot_keys=screenshot_keys,
            requested_at=now,
        )
    except Road10KDeletionStorageError as exc:
        raise Road10KDeletionFailed("deletion_storage_unavailable") from exc


def withdraw_owner(
    db: Session,
    *,
    user_id: str,
    now: datetime | None = None,
) -> Road10KOwnerStageReceipt:
    """Revoke current evaluation access without decrementing either counter."""
    authority = _authority(lifecycle=True)
    require_road_10k_participation(
        db,
        user_id=user_id,
        allow_withdrawn=True,
        lifecycle=True,
    )
    timestamp = _now(now)
    db.rollback()
    # Stage the marker before destructive work.  This read is intentionally
    # owner-scoped and does not emit any data.
    marker = _owner_deletion_manifest(
        db,
        user_id=user_id,
        stage_id=authority.stage_id,
        reason="withdrawal",
        now=timestamp,
    )
    _begin_control_write(db)
    try:
        _assert_owner(db, user_id)
        _counter(db, authority)
        receipt = _receipt(db, user_id=user_id, stage_id=authority.stage_id)
        if receipt is None:
            raise Road10KControlDenied("enrollment_required")
        if receipt.state in {"withdrawn", "deleted"}:
            db.commit()
            return receipt
        _delete_evaluation_rows(
            db,
            [row.id for row in db.query(Road10KEvaluation).filter(
                Road10KEvaluation.user_id == user_id,
                Road10KEvaluation.stage_id == authority.stage_id,
            ).all()],
            reason="withdrawal",
        )
        receipt.state = "withdrawn"
        receipt.withdrawn_at = timestamp
        receipt.updated_at = timestamp
        db.commit()
    except Exception:
        db.rollback()
        raise
    try:
        complete_deletion_manifests([marker], db=db, now=timestamp)
    except Exception as exc:
        raise Road10KDeletionFailed("deletion_marker_completion_failed") from exc
    return receipt


def prepare_account_deletion(
    db: Session,
    *,
    user_id: str,
    now: datetime | None = None,
) -> list[dict[str, object]]:
    """Stage markers before account deletion and unlink Road 10K owner rows."""
    timestamp = _now(now)
    stage_ids = {
        stage_id
        for (stage_id,) in db.query(Road10KOwnerStageReceipt.stage_id)
        .filter(Road10KOwnerStageReceipt.user_id == user_id)
        .distinct()
        .all()
    }
    stage_ids.update(
        stage_id
        for (stage_id,) in db.query(Road10KEvaluation.stage_id)
        .filter(
            Road10KEvaluation.user_id == user_id,
            Road10KEvaluation.deleted_at.is_(None),
        )
        .distinct()
        .all()
    )
    feedback_has_objects = any(
        isinstance(image_keys, list) and any(
            isinstance(key, str) and key for key in image_keys
        )
        for (image_keys,) in db.query(Feedback.image_keys)
        .filter(Feedback.user_id == user_id)
        .all()
    )
    if feedback_has_objects and not stage_ids:
        stage_ids.add(ROAD_10K_STAGE_ID)
    manifests: list[dict[str, object]] = []
    for index, stage_id in enumerate(sorted(stage_ids)):
        manifests.append(
            _owner_deletion_manifest(
                db,
                user_id=user_id,
                stage_id=stage_id,
                reason="account_deletion",
                now=timestamp,
                include_feedback=feedback_has_objects and index == 0,
            )
        )
    evaluation_ids = [
        row.id
        for row in db.query(Road10KEvaluation)
        .filter(Road10KEvaluation.user_id == user_id)
        .all()
    ]
    _delete_evaluation_rows(db, evaluation_ids, reason="account_deletion")
    db.query(Road10KExposureReceipt).filter(
        Road10KExposureReceipt.user_id == user_id
    ).update({Road10KExposureReceipt.user_id: None}, synchronize_session=False)
    db.query(Road10KOwnerStageReceipt).filter(
        Road10KOwnerStageReceipt.user_id == user_id
    ).update(
        {
            Road10KOwnerStageReceipt.user_id: None,
            Road10KOwnerStageReceipt.state: "deleted",
            Road10KOwnerStageReceipt.deleted_at: timestamp,
            Road10KOwnerStageReceipt.updated_at: timestamp,
        },
        synchronize_session=False,
    )
    return manifests


def complete_deletion_manifests(
    manifests: list[dict[str, object]],
    *,
    db: Session | None = None,
    now: datetime | None = None,
) -> None:
    timestamp = _now(now)
    for manifest in manifests:
        for object_key in manifest["screenshot_keys"]:
            delete_manifest_object(str(object_key))
        if db is not None:
            _delete_feedback_for_manifest(db, manifest)
            db.commit()
        mark_completed(manifest, timestamp)


def purge_expired_evaluations(
    db: Session,
    *,
    now: datetime | None = None,
) -> int:
    """Explicit maintenance primitive; no scheduler invokes it in production."""
    timestamp = _now(now)
    rows = [
        row
        for row in db.query(Road10KEvaluation)
        .filter(Road10KEvaluation.deleted_at.is_(None))
        .all()
        if _evaluation_expiry(row) <= timestamp
    ]
    count = 0
    for row in rows:
        marker = _owner_deletion_manifest(
            db,
            user_id=row.user_id or "",
            stage_id=row.stage_id,
            reason="retention",
            now=timestamp,
            evaluation_ids=[row.id],
        )
        _delete_evaluation_rows(db, [row.id], reason="retention")
        db.commit()
        complete_deletion_manifests([marker], db=db, now=timestamp)
        count += 1
    return count


def export_owner_records(db: Session, *, user_id: str) -> dict[str, object]:
    """Return only the authenticated owner's current Road 10K records."""
    authority = _authority(lifecycle=True)
    require_road_10k_participation(
        db,
        user_id=user_id,
        allow_withdrawn=True,
        lifecycle=True,
    )
    timestamp = _now()
    receipt = _receipt(
        db,
        user_id=user_id,
        stage_id=authority.stage_id,
        lock=False,
    )
    evaluations = (
        db.query(Road10KEvaluation)
        .filter(
            Road10KEvaluation.user_id == user_id,
            Road10KEvaluation.deleted_at.is_(None),
        )
        .order_by(Road10KEvaluation.created_at.asc())
        .all()
    )
    evaluations = [
        row for row in evaluations if _evaluation_expiry(row) > timestamp
    ]
    return {
        "stage_id": authority.stage_id,
        "receipt": (
            {
                "state": receipt.state,
                "invitation_issued_at": receipt.invitation_issued_at.isoformat(),
                "enrolled_at": (
                    receipt.enrolled_at.isoformat() if receipt.enrolled_at else None
                ),
                "first_exposed_at": (
                    receipt.first_exposed_at.isoformat()
                    if receipt.first_exposed_at
                    else None
                ),
            }
            if receipt is not None
            else None
        ),
        "evaluations": [
            {
                "id": row.id,
                "stage_id": row.stage_id,
                "result_code": row.result_code,
                "payload": row.payload,
                "created_at": row.created_at.isoformat(),
                "expires_at": row.expires_at.isoformat(),
            }
            for row in evaluations
        ],
    }


def replay_road_10k_deletion_manifests(db: Session) -> int:
    """Replay markers with idempotent DB and private-object deletion."""
    def delete_evaluation(
        evaluation_id: str,
        manifest: dict[str, object],
    ) -> None:
        row = db.query(Road10KEvaluation).filter(
            Road10KEvaluation.id == evaluation_id
        ).first()
        if row is not None:
            if (
                row.user_id != manifest["owner_id"]
                or row.stage_id != manifest["stage_id"]
            ):
                raise Road10KDeletionFailed("deletion_marker_owner_mismatch")
            db.query(Road10KScreenshotReference).filter(
                Road10KScreenshotReference.evaluation_id == evaluation_id
            ).delete(synchronize_session=False)
            db.delete(row)
        else:
            db.query(Road10KScreenshotReference).filter(
                Road10KScreenshotReference.evaluation_id == evaluation_id
            ).delete(synchronize_session=False)
        db.commit()

    def delete_feedback(manifest: dict[str, object]) -> None:
        _delete_feedback_for_manifest(db, manifest)
        db.commit()

    count = replay_manifests(
        delete_object=delete_manifest_object,
        delete_evaluation=delete_evaluation,
        delete_feedback=delete_feedback,
    )
    return count


def road_10k_runtime_snapshot(db: Session) -> dict[str, object]:
    """Low-cardinality restricted status; never includes owner dimensions."""
    authority = load_stage_authority()
    if authority is None:
        return {
            "authority": "missing_or_malformed",
            "stage": None,
            "invitation_slots_consumed": 0,
            "distinct_exposed_owners_consumed": 0,
            "deletion_replay_status": replay_status(),
            "ready": False,
        }
    counter = (
        db.query(Road10KStageCounter)
        .filter(Road10KStageCounter.stage_id == authority.stage_id)
        .first()
    )
    counter_valid = bool(
        counter is not None
        and counter.schema_version == ROAD_10K_CONTROL_SCHEMA_VERSION
        and counter.capability_id == authority.capability_id
        and 0 <= counter.invitation_slots_consumed <= ROAD_10K_INVITATION_CEILING
        and 0 <= counter.distinct_exposed_owners_consumed <= ROAD_10K_EXPOSURE_CEILING
        and counter.invitation_ceiling == authority.invitation_ceiling
        and counter.exposure_ceiling == authority.exposure_ceiling
    )
    return {
        "authority": (
            authority_denial_reason(authority)
            if counter_valid
            else "counter_mismatch"
        ),
        "stage": authority.stage_id,
        "invitation_slots_consumed": counter.invitation_slots_consumed if counter else 0,
        "distinct_exposed_owners_consumed": (
            counter.distinct_exposed_owners_consumed if counter else 0
        ),
        "invitation_ceiling": authority.invitation_ceiling,
        "exposure_ceiling": authority.exposure_ceiling,
        "deletion_replay_status": replay_status(),
        "ready": bool(
            authority.is_usable
            and counter_valid
            and replay_status() == "ready"
        ),
    }
