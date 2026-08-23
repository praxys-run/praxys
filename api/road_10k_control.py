"""Road-10K-specific control ledger and transaction-time gate.

This module is the only place that mutates the Road 10K control tables.  It
does not call provider, AI, MCP, plugin, or automatic-adoption code.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import re
from typing import Any, Mapping
from uuid import uuid4

from sqlalchemy.exc import (
    DBAPIError,
    IntegrityError,
    NoSuchTableError,
    OperationalError,
    ProgrammingError,
)
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from api.road_10k_deletion_storage import (
    Road10KDeletionStorageError,
    confirm_replay_ready,
    iter_active,
    mark_committed,
    mark_completed,
    manifest_intent_digest,
    private_marker_store_available,
    replay_manifests,
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
    Road10KDeletionObligation,
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
_ROAD_10K_INVITATION_KEY = re.compile(r"^inv_[0-9a-f]{32}$")
_ROAD_10K_CONTROL_TABLES = frozenset({
    "road_10k_stage_counters",
    "road_10k_owner_stage_receipts",
    "road_10k_exposure_receipts",
    "road_10k_evaluations",
    "road_10k_screenshot_references",
    "road_10k_deletion_obligations",
})
_ROAD_10K_SCHEMA_ERROR_MARKERS = (
    "no such table",
    "no such column",
    "no column named",
    "undefined table",
    "undefined column",
    "unknown column",
    "does not exist",
)


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


def _is_schema_unavailable_error(exc: BaseException) -> bool:
    if isinstance(exc, NoSuchTableError):
        return True
    if isinstance(exc, (OperationalError, ProgrammingError, DBAPIError)):
        message = str(exc).lower()
        return any(marker in message for marker in _ROAD_10K_SCHEMA_ERROR_MARKERS)
    return False


def coerce_road_10k_control_error(exc: Exception) -> Exception:
    """Normalize known fail-closed schema/read errors to the control boundary."""
    if isinstance(exc, Road10KControlError):
        return exc
    if _is_schema_unavailable_error(exc):
        return Road10KControlUnavailable("schema_unavailable")
    return exc


def receipt_matches_authority(
    receipt: Road10KOwnerStageReceipt,
    authority: Road10KStageAuthority,
) -> bool:
    """Validate the stable receipt contract at every control boundary.

    ``authority_digest`` records the authority that consumed the slot.  It is
    immutable evidence, not a pointer to the latest heartbeat/lifecycle
    artifact, so a compatible refresh must not invalidate an existing receipt.
    """
    return (
        receipt.stage_id == authority.stage_id
        and receipt.capability_id == authority.capability_id
        and receipt.notice_digest == authority.notice_digest
        and receipt.cohort_rule_digest == authority.cohort_rule_digest
        and receipt.sampling_run_evidence_digest
        == authority.sampling_run_evidence_digest
        and receipt.schema_version == authority.control_schema_version
        == ROAD_10K_CONTROL_SCHEMA_VERSION
        and receipt.policy_version == ROAD_10K_POLICY_VERSION
    )


def _now(now: datetime | None = None) -> datetime:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _has_road_10k_runtime_obligation(db: Session) -> bool:
    """Whether a committed private-object deletion still needs replay."""
    try:
        return (
            db.query(Road10KDeletionObligation.id)
            .filter(Road10KDeletionObligation.status == "committed")
            .limit(1)
            .first()
            is not None
        )
    except Exception as exc:
        if _is_schema_unavailable_error(exc):
            return False
        raise


def validate_road_10k_runtime_obligations(db: Session) -> bool:
    """Validate durable counters and receipts before traffic is ready.

    Returns whether any Road control/evaluation obligation exists.  A wholly
    absent schema remains a healthy rolling-deploy/dormant state.
    """
    table_names = set(inspect(db.get_bind()).get_table_names())
    present_tables = table_names & _ROAD_10K_CONTROL_TABLES
    if not present_tables:
        return False
    if present_tables != _ROAD_10K_CONTROL_TABLES:
        raise Road10KControlUnavailable("schema_unavailable")

    counters = db.query(Road10KStageCounter).all()
    owner_receipts = db.query(Road10KOwnerStageReceipt).all()
    exposure_receipts = db.query(Road10KExposureReceipt).all()
    evaluations = db.query(Road10KEvaluation).all()
    screenshots = db.query(Road10KScreenshotReference).all()
    deletion_obligations = db.query(Road10KDeletionObligation).all()
    has_payload_obligation = bool(evaluations or screenshots)
    has_pending_deletion = any(
        row.status == "committed" for row in deletion_obligations
    )

    has_obligation = bool(
        owner_receipts
        or exposure_receipts
        or has_payload_obligation
        or any(
            row.invitation_slots_consumed > 0
            or row.distinct_exposed_owners_consumed > 0
            for row in counters
        )
    )
    if not has_obligation:
        return has_pending_deletion

    counters_by_stage = {row.stage_id: row for row in counters}
    owner_by_id = {row.id: row for row in owner_receipts}
    evaluation_by_id = {row.id: row for row in evaluations}
    validation_time = datetime.utcnow()
    stages = {
        *(row.stage_id for row in owner_receipts),
        *(row.stage_id for row in exposure_receipts),
        *(row.stage_id for row in evaluations),
        *counters_by_stage,
    }
    if stages != set(counters_by_stage):
        raise Road10KControlUnavailable("counter_mismatch")

    for stage_id in stages:
        counter = counters_by_stage[stage_id]
        stage_owners = [
            row for row in owner_receipts if row.stage_id == stage_id
        ]
        stage_exposures = [
            row for row in exposure_receipts if row.stage_id == stage_id
        ]
        if (
            counter.schema_version != ROAD_10K_CONTROL_SCHEMA_VERSION
            or counter.capability_id
            != "outdoor_road_10k_performance_v1"
            or not 0
            <= counter.invitation_slots_consumed
            <= counter.invitation_ceiling
            <= ROAD_10K_INVITATION_CEILING
            or counter.invitation_ceiling != ROAD_10K_INVITATION_CEILING
            or not 0
            <= counter.distinct_exposed_owners_consumed
            <= counter.exposure_ceiling
            <= ROAD_10K_EXPOSURE_CEILING
            or counter.exposure_ceiling != ROAD_10K_EXPOSURE_CEILING
            or counter.invitation_slots_consumed != len(stage_owners)
            or counter.distinct_exposed_owners_consumed
            != len(stage_exposures)
        ):
            raise Road10KControlUnavailable("counter_mismatch")
        for exposure in stage_exposures:
            owner_receipt = owner_by_id.get(exposure.owner_stage_receipt_id)
            first_evaluation = evaluation_by_id.get(exposure.evaluation_id)
            live_first_result_candidates = [
                row
                for row in evaluations
                if row.stage_id == exposure.stage_id
                and row.user_id == exposure.user_id
                and row.created_at == exposure.exposed_at
            ]
            if (
                owner_receipt is None
                or owner_receipt.stage_id != stage_id
                or owner_receipt.state
                not in {"exposed", "withdrawn", "deleted"}
                or owner_receipt.first_exposed_at is None
                or exposure.user_id != owner_receipt.user_id
                or exposure.authority_digest != owner_receipt.authority_digest
                or exposure.exposed_at != owner_receipt.first_exposed_at
                or (
                    first_evaluation is not None
                    and (
                        first_evaluation.stage_id != exposure.stage_id
                        or first_evaluation.user_id != exposure.user_id
                        or first_evaluation.created_at != exposure.exposed_at
                        or first_evaluation.expires_at
                        != exposure.evaluation_expires_at
                    )
                )
                or exposure.evaluation_expires_at < exposure.exposed_at
                or exposure.evaluation_expires_at > (
                    exposure.exposed_at
                    + timedelta(days=ROAD_10K_EVALUATION_RETENTION_DAYS)
                )
                or (
                    first_evaluation is None
                    and (
                        bool(live_first_result_candidates)
                        or (
                            owner_receipt.state not in {"withdrawn", "deleted"}
                            and exposure.evaluation_expires_at > validation_time
                        )
                    )
                )
            ):
                raise Road10KControlUnavailable("receipt_mismatch")
    for evaluation in evaluations:
        if (
            evaluation.expires_at < evaluation.created_at
            or evaluation.expires_at
            > evaluation.created_at
            + timedelta(days=ROAD_10K_EVALUATION_RETENTION_DAYS)
        ):
            raise Road10KControlUnavailable("retention_mismatch")
    evaluation_ids = {row.id for row in evaluations}
    if any(
        row.evaluation_id not in evaluation_ids
        for row in screenshots
    ):
        raise Road10KControlUnavailable("receipt_mismatch")
    return has_pending_deletion


def road_10k_requires_replay_ready(
    db: Session,
    *,
    authority: Road10KStageAuthority | None = None,
) -> bool:
    """Whether a DB-durable private-object deletion still needs replay."""
    # Authority is intentionally irrelevant: this must not read an environment
    # artifact merely to decide a hard-off deletion obligation.
    del authority
    return _has_road_10k_runtime_obligation(db)


def require_road_10k_replay_ready(
    db: Session,
    *,
    authority: Road10KStageAuthority | None = None,
) -> None:
    """Fail closed unless replay-capable marker storage is available and ready."""
    if not road_10k_requires_replay_ready(db, authority=authority):
        return
    if not private_marker_store_available():
        raise Road10KControlUnavailable("deletion_storage_unavailable")
    # Process-local replay status is diagnostic only.  The durable obligation
    # row is the cross-worker source of truth, and replay is idempotent.
    replay_road_10k_deletion_manifests(db)
    if _has_road_10k_runtime_obligation(db):
        raise Road10KControlUnavailable("replay_not_ready")


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
        or counter.invitation_slots_consumed > counter.invitation_ceiling
        or counter.invitation_slots_consumed > ROAD_10K_INVITATION_CEILING
        or counter.distinct_exposed_owners_consumed < 0
        or counter.distinct_exposed_owners_consumed > counter.exposure_ceiling
        or counter.distinct_exposed_owners_consumed > ROAD_10K_EXPOSURE_CEILING
        or counter.invitation_slots_consumed
        != db.query(Road10KOwnerStageReceipt.id)
        .filter(Road10KOwnerStageReceipt.stage_id == authority.stage_id)
        .count()
        or counter.distinct_exposed_owners_consumed
        != db.query(Road10KExposureReceipt.id)
        .filter(Road10KExposureReceipt.stage_id == authority.stage_id)
        .count()
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


def _transaction_authority(
    expected: Road10KStageAuthority,
    *,
    lifecycle: bool = False,
) -> Road10KStageAuthority:
    """Reload external authority after the database write lock is held."""
    current = _authority(lifecycle=lifecycle)
    if current.authority_digest != expected.authority_digest:
        raise Road10KControlUnavailable("authority_changed")
    return current


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


def _fixed_owner_receipt(
    db: Session,
    *,
    user_id: str,
    lock: bool = True,
) -> Road10KOwnerStageReceipt:
    """Find one fixed-contract receipt for authority-independent owner rights."""
    _assert_owner(db, user_id)
    receipt = _receipt(
        db,
        user_id=user_id,
        stage_id=ROAD_10K_STAGE_ID,
        lock=lock,
    )
    if receipt is None:
        raise Road10KControlDenied("participation_required")
    digests = (
        receipt.authority_digest,
        receipt.notice_digest,
        receipt.cohort_rule_digest,
        receipt.sampling_run_evidence_digest,
    )
    invitation_issued_at = receipt.invitation_issued_at
    try:
        chronology_is_valid = (
            invitation_issued_at is not None
            and receipt.created_at == invitation_issued_at
            and receipt.updated_at is not None
            and receipt.updated_at >= invitation_issued_at
            and (
                receipt.enrolled_at is None
                or receipt.enrolled_at >= invitation_issued_at
            )
            and (
                receipt.first_exposed_at is None
                or (
                    receipt.enrolled_at is not None
                    and receipt.first_exposed_at >= receipt.enrolled_at
                )
            )
            and (
                receipt.withdrawn_at is None
                or (
                    receipt.withdrawn_at >= invitation_issued_at
                    and (
                        receipt.enrolled_at is None
                        or receipt.withdrawn_at >= receipt.enrolled_at
                    )
                    and (
                        receipt.first_exposed_at is None
                        or receipt.withdrawn_at >= receipt.first_exposed_at
                    )
                )
            )
            and (
                receipt.deleted_at is None
                or (
                    receipt.deleted_at >= invitation_issued_at
                    and (
                        receipt.enrolled_at is None
                        or receipt.deleted_at >= receipt.enrolled_at
                    )
                    and (
                        receipt.first_exposed_at is None
                        or receipt.deleted_at >= receipt.first_exposed_at
                    )
                    and (
                        receipt.withdrawn_at is None
                        or receipt.deleted_at >= receipt.withdrawn_at
                    )
                )
            )
        )
    except TypeError:
        chronology_is_valid = False
    lifecycle_is_valid = (
        (
            receipt.state == "invited_only"
            and receipt.enrolled_at is None
            and receipt.first_exposed_at is None
            and receipt.withdrawn_at is None
            and receipt.deleted_at is None
            and receipt.updated_at == receipt.invitation_issued_at
        )
        or (
            receipt.state == "enrolled_unexposed"
            and receipt.enrolled_at is not None
            and receipt.first_exposed_at is None
            and receipt.withdrawn_at is None
            and receipt.deleted_at is None
            and receipt.updated_at == receipt.enrolled_at
        )
        or (
            receipt.state == "exposed"
            and receipt.enrolled_at is not None
            and receipt.first_exposed_at is not None
            and receipt.withdrawn_at is None
            and receipt.deleted_at is None
            and receipt.first_exposed_at >= receipt.enrolled_at
            and receipt.updated_at == receipt.first_exposed_at
        )
        or (
            receipt.state == "withdrawn"
            and receipt.withdrawn_at is not None
            and receipt.deleted_at is None
            and receipt.updated_at == receipt.withdrawn_at
        )
    )
    if (
        receipt.capability_id != "outdoor_road_10k_performance_v1"
        or receipt.schema_version != ROAD_10K_CONTROL_SCHEMA_VERSION
        or receipt.policy_version != ROAD_10K_POLICY_VERSION
        or receipt.state not in {"invited_only", "enrolled_unexposed", "exposed", "withdrawn"}
        or any(not isinstance(value, str) or len(value) != 64 for value in digests)
        or not chronology_is_valid
        or not lifecycle_is_valid
    ):
        raise Road10KControlDenied("receipt_contract_mismatch")
    return receipt


def _persist_deletion_obligation(
    db: Session,
    manifest: Mapping[str, object],
    *,
    committed_at: datetime,
) -> None:
    """Persist replay authority in the same transaction as DB deletion."""
    job_id = str(manifest["job_id"])
    digest = manifest_intent_digest(manifest)
    requested_at = datetime.fromisoformat(
        str(manifest["requested_at"]).replace("Z", "+00:00")
    ).astimezone(timezone.utc).replace(tzinfo=None)
    existing = db.get(Road10KDeletionObligation, job_id)
    if existing is not None:
        if (
            existing.status != "committed"
            or existing.stage_id != str(manifest["stage_id"])
            or existing.reason != str(manifest["reason"])
            or existing.manifest_digest != digest
        ):
            raise Road10KDeletionFailed("deletion_obligation_conflict")
        return
    db.add(
        Road10KDeletionObligation(
            id=job_id,
            stage_id=str(manifest["stage_id"]),
            reason=str(manifest["reason"]),
            manifest_digest=digest,
            status="committed",
            requested_at=requested_at,
            committed_at=committed_at,
        )
    )


def _complete_deletion_obligation(
    db: Session,
    manifest: Mapping[str, object],
    *,
    completed_at: datetime,
) -> None:
    obligation = db.get(Road10KDeletionObligation, str(manifest["job_id"]))
    if obligation is None:
        raise Road10KDeletionFailed("deletion_obligation_missing")
    if obligation.status == "completed":
        return
    obligation.status = "completed"
    obligation.completed_at = completed_at


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
    require_road_10k_replay_ready(db, authority=authority)
    if _ROAD_10K_INVITATION_KEY.fullmatch(idempotency_key) is None:
        raise Road10KControlDenied("invalid_idempotency_key")
    if (
        notice_digest != authority.notice_digest
        or cohort_rule_digest != authority.cohort_rule_digest
    ):
        raise Road10KControlUnavailable("authority_digest_mismatch")
    db.rollback()
    _begin_control_write(db)
    try:
        authority = _transaction_authority(authority)
        require_road_10k_replay_ready(db, authority=authority)
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
            if by_key.user_id != user_id:
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
            sampling_run_evidence_digest=(
                authority.sampling_run_evidence_digest
            ),
            invitation_idempotency_key=idempotency_key,
            state="invited_only",
            invitation_issued_at=timestamp,
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
    require_road_10k_replay_ready(db, authority=authority)
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
    if preflight.state in {"deleted", "withdrawn"}:
        raise Road10KControlDenied("same_stage_reenrollment_denied")
    db.rollback()
    _begin_control_write(db)
    try:
        authority = _transaction_authority(authority)
        require_road_10k_replay_ready(db, authority=authority)
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
        if receipt.state in {"deleted", "withdrawn"}:
            raise Road10KControlDenied("same_stage_reenrollment_denied")
        if receipt.state in {"enrolled_unexposed", "exposed"}:
            db.commit()
            return receipt
        existing_exposure = (
            db.query(Road10KExposureReceipt)
            .filter(
                Road10KExposureReceipt.stage_id == authority.stage_id,
                Road10KExposureReceipt.user_id == user_id,
                Road10KExposureReceipt.owner_stage_receipt_id == receipt.id,
            )
            .first()
        )
        timestamp = _now(now)
        receipt.state = (
            "exposed" if existing_exposure is not None else "enrolled_unexposed"
        )
        receipt.enrolled_at = receipt.enrolled_at or timestamp
        receipt.withdrawn_at = None
        receipt.updated_at = timestamp
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
    """Reject the removed standalone pre-result exposure transition."""
    del db, user_id, now
    raise Road10KControlDenied("first_exposure_requires_durable_result")


def _record_first_exposure_locked(
    db: Session,
    *,
    authority: Road10KStageAuthority,
    user_id: str,
    counter: Road10KStageCounter,
    evaluation: Road10KEvaluation,
    timestamp: datetime,
) -> Road10KExposureReceipt:
    """Create the first-result receipt inside the result transaction only."""
    receipt = _receipt(db, user_id=user_id, stage_id=authority.stage_id)
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
        return existing
    if counter.distinct_exposed_owners_consumed >= counter.exposure_ceiling:
        raise Road10KControlDenied("exposure_cap")
    first_exposed_at = receipt.first_exposed_at or timestamp
    receipt.state = "exposed"
    receipt.first_exposed_at = first_exposed_at
    receipt.updated_at = first_exposed_at
    counter.distinct_exposed_owners_consumed += 1
    counter.updated_at = timestamp

    # The insert trigger reads the owner receipt. Flush its exposed lifecycle
    # first, then insert the exactly matching receipt in the same transaction.
    db.flush()
    exposure = Road10KExposureReceipt(
        id=str(uuid4()),
        stage_id=receipt.stage_id,
        user_id=receipt.user_id,
        owner_stage_receipt_id=receipt.id,
        authority_digest=receipt.authority_digest,
        evaluation_id=evaluation.id,
        evaluation_expires_at=evaluation.expires_at,
        exposed_at=first_exposed_at,
    )
    db.add(exposure)
    db.flush()
    return exposure


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
    require_road_10k_replay_ready(db, authority=authority)
    if expose:
        # Evaluation may be read, but exposure is committed only with its
        # first durable successful result in record_result.
        require_road_10k_participation(db, user_id=user_id)
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
    if exposure is None:
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
    require_road_10k_replay_ready(db, authority=authority)
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
    timestamp = _now(now)
    db.rollback()
    _begin_control_write(db)
    try:
        authority = _transaction_authority(authority)
        require_road_10k_replay_ready(db, authority=authority)
        _assert_owner(db, user_id)
        counter = _counter(db, authority)
        evaluation = Road10KEvaluation(
            id=str(uuid4()),
            user_id=user_id,
            stage_id=authority.stage_id,
            result_code=result_code,
            payload=dict(payload),
            created_at=timestamp,
            expires_at=(
                timestamp
                + timedelta(days=ROAD_10K_EVALUATION_RETENTION_DAYS)
            ),
        )
        # The exposure insert trigger requires the exact durable first result.
        # Insert it first, then bind the immutable receipt and counter in this
        # same serialized transaction. Nothing can commit independently.
        db.add(evaluation)
        db.flush()
        _record_first_exposure_locked(
            db,
            authority=authority,
            user_id=user_id,
            counter=counter,
            evaluation=evaluation,
            timestamp=timestamp,
        )
        db.commit()
        return evaluation
    except Exception:
        db.rollback()
        raise


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


def _evaluation_expiry(row: Road10KEvaluation) -> datetime:
    """Return the DB-immutable authoritative retention deadline."""
    return row.expires_at


def _owner_deletion_manifest(
    db: Session,
    *,
    user_id: str,
    stage_id: str,
    reason: str,
    now: datetime,
    evaluation_ids: list[str] | None = None,
) -> dict[str, object] | None:
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
    if not evaluation_ids and not screenshot_keys:
        return None
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


def _manifest_is_replayable(
    db: Session,
    manifest: Mapping[str, object],
) -> bool:
    """A private marker replays only with its DB-committed obligation."""
    obligation = db.get(Road10KDeletionObligation, str(manifest["job_id"]))
    return bool(
        obligation is not None
        and obligation.status == "committed"
        and obligation.stage_id == str(manifest["stage_id"])
        and obligation.reason == str(manifest["reason"])
        and obligation.manifest_digest == manifest_intent_digest(manifest)
    )


def commit_deletion_manifests(
    manifests: list[dict[str, object]],
    *,
    now: datetime | None = None,
) -> list[dict[str, object]]:
    """Promote prepared markers to replayable committed intent after DB commit."""
    timestamp = _now(now)
    return [mark_committed(manifest, timestamp) for manifest in manifests]


def withdraw_owner(
    db: Session,
    *,
    user_id: str,
    now: datetime | None = None,
) -> Road10KOwnerStageReceipt:
    """Withdraw a first-party owner without consulting stage authority."""
    timestamp = _now(now)
    db.rollback()
    _begin_control_write(db)
    try:
        receipt = _fixed_owner_receipt(db, user_id=user_id)
        if receipt.state == "withdrawn":
            pending_replay = (
                db.query(Road10KDeletionObligation.id)
                .filter(Road10KDeletionObligation.status == "committed")
                .first()
            )
            if pending_replay is not None:
                raise Road10KDeletionFailed("deletion_replay_pending")
            db.commit()
            return receipt
        # Stage and persist the payload-free marker in this same DB
        # transaction.  A crash after commit leaves a cross-worker replay
        # obligation even when User, Feedback, and Road rows are all gone.
        marker = _owner_deletion_manifest(
            db,
            user_id=user_id,
            stage_id=ROAD_10K_STAGE_ID,
            reason="withdrawal",
            now=timestamp,
        )
        if marker is not None:
            _persist_deletion_obligation(db, marker, committed_at=timestamp)
        _delete_evaluation_rows(
            db,
            [
                row.id
                for row in db.query(Road10KEvaluation)
                .filter(
                    Road10KEvaluation.user_id == user_id,
                    Road10KEvaluation.stage_id == ROAD_10K_STAGE_ID,
                )
                .all()
            ],
            reason="withdrawal",
        )
        receipt.state = "withdrawn"
        receipt.withdrawn_at = timestamp
        receipt.updated_at = timestamp
        db.commit()
    except Exception:
        db.rollback()
        raise
    if marker is not None:
        try:
            committed = commit_deletion_manifests([marker], now=timestamp)
            complete_deletion_manifests(committed, db=db, now=timestamp)
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
    manifests: list[dict[str, object]] = []
    # Feedback image keys share the existing private deletion-manifest seam.
    # Stage them before Feedback rows are removed by account deletion.
    feedback_keys = [
        str(key)
        for (keys,) in db.query(Feedback.image_keys)
        .filter(Feedback.user_id == user_id)
        .all()
        for key in (keys or [])
        if isinstance(key, str) and key.startswith("feedback/")
    ]
    if feedback_keys:
        try:
            manifests.append(
                stage_manifest(
                    owner_id=user_id,
                    stage_id=ROAD_10K_STAGE_ID,
                    reason="account_deletion",
                    evaluation_ids=[],
                    screenshot_keys=sorted(set(feedback_keys)),
                    requested_at=timestamp,
                )
            )
        except Road10KDeletionStorageError as exc:
            raise Road10KDeletionFailed(
                "deletion_storage_unavailable"
            ) from exc
    for stage_id in sorted(stage_ids):
        manifest = _owner_deletion_manifest(
            db,
            user_id=user_id,
            stage_id=stage_id,
            reason="account_deletion",
            now=timestamp,
        )
        if manifest is not None:
            manifests.append(manifest)
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


def record_deletion_obligations(
    db: Session,
    manifests: list[dict[str, object]],
    *,
    now: datetime | None = None,
) -> None:
    """Record prepared marker replay obligations in the final DB transaction."""
    timestamp = _now(now)
    for manifest in manifests:
        _persist_deletion_obligation(db, manifest, committed_at=timestamp)


def complete_deletion_manifests(
    manifests: list[dict[str, object]],
    *,
    db: Session | None = None,
    now: datetime | None = None,
) -> None:
    if not manifests:
        return
    timestamp = _now(now)
    for manifest in manifests:
        for object_key in manifest["screenshot_keys"]:
            delete_manifest_object(str(object_key))
        mark_completed(manifest, timestamp)
        if db is not None:
            _complete_deletion_obligation(db, manifest, completed_at=timestamp)
    if db is not None:
        db.commit()
    # This is an in-process diagnostic only; readiness is derived from the DB.
    confirm_replay_ready(timestamp.replace(tzinfo=timezone.utc))


def purge_expired_evaluations(
    db: Session,
    *,
    now: datetime | None = None,
) -> int:
    """Explicit maintenance primitive; no scheduler invokes it in production."""
    timestamp = _now(now)
    rows = (
        db.query(Road10KEvaluation)
        .filter(
            Road10KEvaluation.deleted_at.is_(None),
            Road10KEvaluation.expires_at <= timestamp,
        )
        .all()
    )
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
        if marker is None:
            raise Road10KDeletionFailed("deletion_manifest_missing")
        _persist_deletion_obligation(db, marker, committed_at=timestamp)
        _delete_evaluation_rows(db, [row.id], reason="retention")
        db.commit()
        committed = commit_deletion_manifests([marker], now=timestamp)
        complete_deletion_manifests(committed, db=db, now=timestamp)
        count += 1
    return count


def export_owner_records(db: Session, *, user_id: str) -> dict[str, object]:
    """Return fixed-contract records without stage authority."""
    receipt = _fixed_owner_receipt(db, user_id=user_id, lock=False)
    timestamp = _now()
    evaluations = (
        db.query(Road10KEvaluation)
        .filter(
            Road10KEvaluation.user_id == user_id,
            Road10KEvaluation.stage_id == ROAD_10K_STAGE_ID,
            Road10KEvaluation.deleted_at.is_(None),
        )
        .order_by(Road10KEvaluation.created_at.asc())
        .all()
    )
    evaluations = [
        row for row in evaluations if _evaluation_expiry(row) > timestamp
    ]
    return {
        "stage_id": ROAD_10K_STAGE_ID,
        "receipt": {
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
        },
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
    """Replay every DB-committed private deletion obligation idempotently."""
    pending = {
        row.id
        for row in db.query(Road10KDeletionObligation)
        .filter(Road10KDeletionObligation.status == "committed")
        .all()
    }
    if not pending:
        return 0
    active = list(iter_active())
    active_by_id = {
        str(manifest["job_id"]): manifest
        for manifest in active
    }
    if pending - set(active_by_id):
        raise Road10KDeletionFailed("deletion_marker_missing")
    if any(
        not _manifest_is_replayable(db, active_by_id[job_id])
        for job_id in pending
    ):
        raise Road10KDeletionFailed("deletion_marker_mismatch")

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

    count = replay_manifests(
        delete_object=delete_manifest_object,
        delete_evaluation=delete_evaluation,
        should_replay=lambda manifest: _manifest_is_replayable(db, manifest),
    )
    completed = {
        str(manifest["job_id"])
        for manifest in iter_active()
        if manifest["status"] == "completed"
    }
    for obligation in (
        db.query(Road10KDeletionObligation)
        .filter(
            Road10KDeletionObligation.id.in_(pending & completed),
            Road10KDeletionObligation.status == "committed",
        )
        .all()
    ):
        obligation.status = "completed"
        obligation.completed_at = _now()
    db.commit()
    return count


def initialize_road_10k_runtime(db: Session) -> int:
    """Touch private storage only for a durable historical obligation.

    Dormant startup must return before constructing, probing, listing, creating,
    downloading, or deleting through the private-store seam.
    """
    has_obligation = validate_road_10k_runtime_obligations(db)
    if not has_obligation:
        return 0
    if not private_marker_store_available():
        raise Road10KDeletionFailed("deletion_storage_unavailable")
    return replay_road_10k_deletion_manifests(db)


def road_10k_runtime_snapshot(db: Session) -> dict[str, object]:
    """Report only hard-off status and DB-durable replay state."""
    try:
        pending = validate_road_10k_runtime_obligations(db)
        counter = (
            db.query(Road10KStageCounter)
            .filter(Road10KStageCounter.stage_id == ROAD_10K_STAGE_ID)
            .first()
        )
    except Exception:
        return {
            "authority": "counter_mismatch",
            "stage": ROAD_10K_STAGE_ID,
            "invitation_slots_consumed": 0,
            "distinct_exposed_owners_consumed": 0,
            "invitation_ceiling": ROAD_10K_INVITATION_CEILING,
            "exposure_ceiling": ROAD_10K_EXPOSURE_CEILING,
            "deletion_replay_status": "blocked",
            "ready": False,
        }
    return {
        "authority": "inactive_revision",
        "stage": counter.stage_id if counter is not None else None,
        "invitation_slots_consumed": (
            counter.invitation_slots_consumed if counter is not None else 0
        ),
        "distinct_exposed_owners_consumed": (
            counter.distinct_exposed_owners_consumed if counter is not None else 0
        ),
        "invitation_ceiling": ROAD_10K_INVITATION_CEILING,
        "exposure_ceiling": ROAD_10K_EXPOSURE_CEILING,
        "deletion_replay_status": "pending" if pending else "not_required",
        "ready": not pending,
    }
