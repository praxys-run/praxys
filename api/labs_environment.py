"""Consent, aggregate persistence, and private processing for Labs V1."""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import and_, or_
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import Session

from analysis.environment_response import (
    LABS_ENVIRONMENT_MODEL_VERSION,
    POWER_REGIME,
    assess_environment_response_preflight,
    build_environment_response_result,
)
from analysis.data_loader import load_environment_response_preflight_counts
from analysis.heat_response_validation import build_research_dataset_bundle
from analysis.heat_response_validation import HeatValidationConfig
from analysis.metrics import (
    ACTIVITY_RESEARCH_SCHEMA_VERSION,
    ENVIRONMENT_RESPONSE_MAX_POWER_WATTS,
    ENVIRONMENT_RESPONSE_MINIMUM_HR_COVERAGE,
    ENVIRONMENT_RESPONSE_SAMPLE_MAX_INTERVAL_SEC,
)
from api.etag import ENDPOINT_SCOPES, compute_revision_token
from api.packs import (
    RequestContext,
    get_activity_research_pack,
    get_analysis_response_version,
)
from api.statsig_client import get_config, get_statsig_user_for_account
from api.views import utc_isoformat
from api import labs_tombstone_storage
from db.cache_revision import lock_revision_writes
from db.models import (
    LabsAnalysisJob,
    LabsAnalysisOutbox,
    LabsDeletionTombstone,
    LabsExperimentEnrollment,
    LabsExperimentResult,
    User,
    UserConfig,
)
from db.session import begin_serialized_write

logger = logging.getLogger(__name__)

EXPERIMENT_ID = "environment-response-v1"
CONSENT_VERSION = "environment-response-consent-v1"
ACTIVE_JOB_STATUSES = ("queued", "dispatched", "processing", "retrying")
MANUAL_RECOMPUTE_CONFIG_NAME = "labs_environment_recompute_policy"
MANUAL_RECOMPUTE_DEFAULT_COOLDOWN_HOURS = 6
MANUAL_RECOMPUTE_DEFAULT_WINDOW_HOURS = 24
MANUAL_RECOMPUTE_DEFAULT_LIMIT = 3
JOB_LEASE_DURATION = timedelta(minutes=30)
MAX_JOB_ATTEMPTS = 3
PROCESSING_NOT_AUTHORIZED_CODE = "processing_not_authorized"
_IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
_SNAPSHOT_SALT = (
    "analysis-export&v="
    f"{get_analysis_response_version(ACTIVITY_RESEARCH_SCHEMA_VERSION)}"
)


class StaleSourceRevision(RuntimeError):
    """Raised when source data changes during private snapshot construction."""


class ProcessingNotAuthorized(RuntimeError):
    """Raised when a Labs worker crosses the background-processing fence."""


def _require_processing_authorized(db: Session, user_id: str) -> None:
    """Stop private Labs work as soon as current authority is withdrawn."""
    from api.legal_receipts import user_background_processing_authorized

    if not user_background_processing_authorized(db, user_id):
        raise ProcessingNotAuthorized(PROCESSING_NOT_AUTHORIZED_CODE)


class RecomputeLimitError(RuntimeError):
    """Raised when a manual Labs recompute is not currently permitted."""

    def __init__(
        self,
        code: Literal["cooldown", "daily_limit"],
        available_at: datetime,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.available_at = available_at


@dataclass(frozen=True)
class ManualRecomputePolicy:
    """Validated per-user Labs manual recompute limits."""

    cooldown: timedelta
    window: timedelta
    limit: int


DEFAULT_MANUAL_RECOMPUTE_POLICY = ManualRecomputePolicy(
    cooldown=timedelta(hours=MANUAL_RECOMPUTE_DEFAULT_COOLDOWN_HOURS),
    window=timedelta(hours=MANUAL_RECOMPUTE_DEFAULT_WINDOW_HOURS),
    limit=MANUAL_RECOMPUTE_DEFAULT_LIMIT,
)


def _manual_recompute_policy(
    db: Session,
    user_id: str,
) -> ManualRecomputePolicy:
    config_row = db.get(UserConfig, user_id)
    statsig_user = get_statsig_user_for_account(
        db,
        user_id=user_id,
        training_base=(
            config_row.training_base if config_row is not None else None
        ),
        language=config_row.language if config_row is not None else None,
    )
    fallback = {
        "cooldown_hours": MANUAL_RECOMPUTE_DEFAULT_COOLDOWN_HOURS,
        "window_hours": MANUAL_RECOMPUTE_DEFAULT_WINDOW_HOURS,
        "max_requests": MANUAL_RECOMPUTE_DEFAULT_LIMIT,
    }
    configured = get_config(
        MANUAL_RECOMPUTE_CONFIG_NAME,
        statsig_user,
        fallback,
    )
    if not isinstance(configured, dict):
        logger.warning(
            "Invalid Labs recompute config; using defaults: config=%s",
            MANUAL_RECOMPUTE_CONFIG_NAME,
        )
        return DEFAULT_MANUAL_RECOMPUTE_POLICY
    cooldown_hours = configured.get("cooldown_hours")
    window_hours = configured.get("window_hours")
    limit = configured.get("max_requests")
    valid = (
        type(cooldown_hours) is int
        and type(window_hours) is int
        and type(limit) is int
        and 0 <= cooldown_hours <= 168
        and 1 <= window_hours <= 168
        and cooldown_hours <= window_hours
        and 1 <= limit <= 100
    )
    if not valid:
        logger.warning(
            "Invalid Labs recompute config values; using defaults: config=%s",
            MANUAL_RECOMPUTE_CONFIG_NAME,
        )
        return DEFAULT_MANUAL_RECOMPUTE_POLICY
    return ManualRecomputePolicy(
        cooldown=timedelta(hours=cooldown_hours),
        window=timedelta(hours=window_hours),
        limit=limit,
    )


@dataclass(frozen=True)
class QueueDecision:
    """Result of an idempotent enqueue attempt."""

    enrollment: LabsExperimentEnrollment | None
    job: LabsAnalysisJob | None
    created: bool
    idempotent: bool = False


@dataclass(frozen=True)
class JobExecutionResult:
    """Settlement decision returned to the Service Bus worker."""

    outcome: Literal[
        "completed",
        "ignored",
        "cancelled",
        "retry",
        "failed",
        "dead_lettered",
    ]
    attempt_count: int = 0
    failure_code: str | None = None


def _locked_enrollment(
    db: Session,
    user_id: str,
    experiment_id: str,
) -> LabsExperimentEnrollment | None:
    return (
        db.query(LabsExperimentEnrollment)
        .filter(
            LabsExperimentEnrollment.user_id == user_id,
            LabsExperimentEnrollment.experiment_id == experiment_id,
        )
        .with_for_update()
        .one_or_none()
    )


def _active_job(
    db: Session,
    user_id: str,
    experiment_id: str,
    *,
    lock: bool = False,
) -> LabsAnalysisJob | None:
    query = (
        db.query(LabsAnalysisJob)
        .filter(
            LabsAnalysisJob.user_id == user_id,
            LabsAnalysisJob.experiment_id == experiment_id,
            LabsAnalysisJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .order_by(LabsAnalysisJob.requested_at.desc())
    )
    if lock:
        query = query.with_for_update()
    return query.first()


def _has_worker_predecessor(
    db: Session,
    job: LabsAnalysisJob,
) -> bool:
    """Return whether another active job should consume the global slot first."""
    any_processing = (
        db.query(LabsAnalysisJob.id)
        .filter(
            LabsAnalysisJob.id != job.id,
            LabsAnalysisJob.status == "processing",
        )
        .first()
    )
    if any_processing is not None:
        return True
    return (
        db.query(LabsAnalysisJob.id)
        .filter(
            LabsAnalysisJob.id != job.id,
            LabsAnalysisJob.status.in_(ACTIVE_JOB_STATUSES),
            or_(
                LabsAnalysisJob.requested_at < job.requested_at,
                and_(
                    LabsAnalysisJob.requested_at == job.requested_at,
                    LabsAnalysisJob.id < job.id,
                ),
            ),
        )
        .first()
        is not None
    )


def _latest_job(
        db: Session,
        user_id: str,
        experiment_id: str,
) -> LabsAnalysisJob | None:
    return (
        db.query(LabsAnalysisJob)
        .filter(
            LabsAnalysisJob.user_id == user_id,
            LabsAnalysisJob.experiment_id == experiment_id,
        )
        .order_by(LabsAnalysisJob.requested_at.desc())
        .first()
    )


def _job_identity(db: Session, job_id: str) -> tuple[str, str] | None:
    identity = (
        db.query(
            LabsAnalysisJob.user_id,
            LabsAnalysisJob.experiment_id,
        )
        .filter(LabsAnalysisJob.id == job_id)
        .first()
    )
    db.rollback()
    if identity is None:
        return None
    return str(identity[0]), str(identity[1])


def _execution_result_for_job(
    job: LabsAnalysisJob | None,
) -> JobExecutionResult:
    if job is None:
        return JobExecutionResult("ignored")
    if job.status in ACTIVE_JOB_STATUSES:
        outcome = "retry"
    elif job.status == "succeeded":
        outcome = "completed"
    elif job.status == "cancelled":
        outcome = "cancelled"
    elif job.status == "dead_lettered":
        outcome = "dead_lettered"
    elif job.status == "failed":
        outcome = "failed"
    else:
        outcome = "ignored"
    return JobExecutionResult(
        outcome,
        attempt_count=job.attempt_count or 0,
        failure_code=job.failure_code,
    )


def _existing_job_execution_result(
    db: Session,
    job_id: str,
) -> JobExecutionResult:
    job = (
        db.query(LabsAnalysisJob)
        .filter(LabsAnalysisJob.id == job_id)
        .one_or_none()
    )
    result = _execution_result_for_job(job)
    db.rollback()
    return result


def _job_for_idempotency_key(
    db: Session,
    user_id: str,
    experiment_id: str,
    trigger: Literal["enrollment", "manual_recompute"],
    idempotency_key: str | None,
) -> LabsAnalysisJob | None:
    if idempotency_key is None:
        return None
    return (
        db.query(LabsAnalysisJob)
        .filter(
            LabsAnalysisJob.user_id == user_id,
            LabsAnalysisJob.experiment_id == experiment_id,
            LabsAnalysisJob.trigger == trigger,
            LabsAnalysisJob.idempotency_key == idempotency_key,
        )
        .first()
    )


def _normalize_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not _IDEMPOTENCY_KEY_RE.fullmatch(normalized):
        raise ValueError("invalid_idempotency_key")
    return normalized


def _has_current_consent(
        row: LabsExperimentEnrollment | None,
) -> bool:
        return (
            row is not None
            and row.consent_version == CONSENT_VERSION
            and row.adult_attested_at is not None
        )


def _uses_current_model(
    row: LabsExperimentEnrollment | None,
    job: LabsAnalysisJob,
) -> bool:
    return (
        row is not None
        and row.model_version == LABS_ENVIRONMENT_MODEL_VERSION
        and job.model_version == LABS_ENVIRONMENT_MODEL_VERSION
        and row.model_version == job.model_version
    )


def _same_job_generation(
    row: LabsExperimentEnrollment | None,
    job: LabsAnalysisJob,
) -> bool:
    return (
        row is not None
        and row.user_id == job.user_id
        and row.experiment_id == job.experiment_id
        and row.source_revision == job.source_revision
        and row.correlation_id == job.correlation_id
    )


def _cancel_model_mismatch(
    db: Session,
    row: LabsExperimentEnrollment | None,
    job: LabsAnalysisJob,
) -> None:
    completed_at = datetime.utcnow()
    job.status = "cancelled"
    job.failure_code = "model_version_mismatch"
    job.retryable_failure = False
    job.completed_at = completed_at
    job.lease_expires_at = None
    job.updated_at = completed_at
    if _same_job_generation(row, job):
        assert row is not None
        row.status = "stale"
        row.availability_reason = _reason(
            "stale_model_version",
            correlation_id=job.correlation_id,
        )
        row.completed_at = completed_at
        row.updated_at = completed_at
    db.commit()


def _cancel_processing_not_authorized(
    db: Session,
    row: LabsExperimentEnrollment | None,
    job: LabsAnalysisJob,
    *,
    outbox: LabsAnalysisOutbox | None = None,
) -> JobExecutionResult:
    """Persist the single terminal state for lost processing authority."""
    completed_at = datetime.utcnow()
    job.status = "cancelled"
    job.failure_code = PROCESSING_NOT_AUTHORIZED_CODE
    job.retryable_failure = False
    job.completed_at = completed_at
    job.lease_expires_at = None
    job.updated_at = completed_at
    if outbox is None:
        outbox = (
            db.query(LabsAnalysisOutbox)
            .filter(LabsAnalysisOutbox.job_id == job.id)
            .with_for_update()
            .one_or_none()
        )
    if outbox is not None:
        outbox.status = "cancelled"
        outbox.lease_expires_at = None
        outbox.last_error_code = PROCESSING_NOT_AUTHORIZED_CODE
        outbox.updated_at = completed_at
    if _same_job_generation(row, job):
        assert row is not None
        row.status = "unavailable"
        row.availability_reason = None
        row.started_at = None
        row.completed_at = completed_at
        row.updated_at = completed_at
    db.commit()
    _record_job_event(
        job,
        event="cancelled",
        outcome=PROCESSING_NOT_AUTHORIZED_CODE,
        failure_class=PROCESSING_NOT_AUTHORIZED_CODE,
    )
    return JobExecutionResult(
        "cancelled",
        attempt_count=job.attempt_count or 0,
        failure_code=PROCESSING_NOT_AUTHORIZED_CODE,
    )


def _persist_processing_not_authorized(
    db: Session,
    job_id: str,
) -> JobExecutionResult:
    """Lock and terminally cancel a claimed job after an execution fence."""
    db.rollback()
    db.expire_all()
    identity = _job_identity(db, job_id)
    if identity is None:
        return JobExecutionResult("cancelled")
    begin_serialized_write(db)
    lock_revision_writes(db, identity[0])
    row = _locked_enrollment(db, identity[0], identity[1])
    job = (
        db.query(LabsAnalysisJob)
        .filter(LabsAnalysisJob.id == job_id)
        .with_for_update()
        .one_or_none()
    )
    if job is None or job.status != "processing":
        result = _execution_result_for_job(job)
        db.rollback()
        return result
    return _cancel_processing_not_authorized(db, row, job)


def _authorize_job_dispatch(
    db: Session,
    *,
    outbox_id: str,
    job_id: str,
) -> bool:
    """Authorize a claimed outbox row under the durable job locks."""
    identity = _job_identity(db, job_id)
    if identity is None:
        return False
    begin_serialized_write(db)
    lock_revision_writes(db, identity[0])
    row = _locked_enrollment(db, identity[0], identity[1])
    job = (
        db.query(LabsAnalysisJob)
        .filter(LabsAnalysisJob.id == job_id)
        .with_for_update()
        .one_or_none()
    )
    outbox = (
        db.query(LabsAnalysisOutbox)
        .filter(LabsAnalysisOutbox.id == outbox_id)
        .with_for_update()
        .one_or_none()
    )
    if (
        job is None
        or outbox is None
        or job.status not in ACTIVE_JOB_STATUSES
        or outbox.job_id != job.id
        or outbox.status != "dispatching"
    ):
        db.rollback()
        return False
    from api.legal_receipts import user_background_processing_authorized

    if user_background_processing_authorized(db, job.user_id):
        db.rollback()
        return True
    _cancel_processing_not_authorized(
        db,
        row,
        job,
        outbox=outbox,
    )
    return False


def _ensure_outbox(
        db: Session,
        job: LabsAnalysisJob,
        *,
        available_at: datetime,
        force_pending: bool = False,
) -> LabsAnalysisOutbox:
    outbox = (
        db.query(LabsAnalysisOutbox)
        .filter(LabsAnalysisOutbox.job_id == job.id)
        .with_for_update()
        .one_or_none()
    )
    if outbox is None:
        outbox = LabsAnalysisOutbox(
            id=str(uuid4()),
            job_id=job.id,
            status="pending",
            attempt_count=0,
            available_at=available_at,
            created_at=available_at,
            updated_at=available_at,
        )
        db.add(outbox)
        return outbox
    lease_expired = (
        outbox.status == "dispatching"
        and (
            outbox.lease_expires_at is None
            or outbox.lease_expires_at <= available_at
        )
    )
    should_reset = (
        force_pending
        or lease_expired
        or outbox.status not in ("pending", "dispatching", "dispatched")
    )
    if should_reset:
        outbox.status = "pending"
        outbox.available_at = available_at
        outbox.lease_expires_at = None
        outbox.last_error_code = None
        outbox.updated_at = available_at
    return outbox


def _create_job(
        db: Session,
        row: LabsExperimentEnrollment,
        *,
        trigger: Literal["enrollment", "manual_recompute"],
        idempotency_key: str | None,
        requested_at: datetime,
) -> LabsAnalysisJob:
    job = LabsAnalysisJob(
        id=str(uuid4()),
        user_id=row.user_id,
        experiment_id=row.experiment_id,
        trigger=trigger,
        status="queued",
        model_version=row.model_version,
        source_revision=row.source_revision,
        correlation_id=row.correlation_id,
        idempotency_key=idempotency_key,
        attempt_count=0,
        retryable_failure=False,
        requested_at=requested_at,
        updated_at=requested_at,
    )
    db.add(job)
    db.flush()
    _ensure_outbox(db, job, available_at=requested_at)
    return job


def source_revision(db: Session, user_id: str) -> str:
    """Return the owner-bound source revision used to fence one computation."""
    return compute_revision_token(
        db,
        user_id,
        ENDPOINT_SCOPES["analysis"],
        salt=_SNAPSHOT_SALT,
    )


def environment_response_preflight(
    db: Session,
    user_id: str,
) -> dict[str, Any]:
    """Return a fast aggregate-only eligibility estimate without persistence."""
    config = HeatValidationConfig()
    counts = load_environment_response_preflight_counts(
        user_id,
        db,
        eligible_activity_types=config.eligible_activity_types,
        minimum_segment_duration_sec=config.minimum_segment_duration_sec,
        maximum_sample_interval_sec=(
            ENVIRONMENT_RESPONSE_SAMPLE_MAX_INTERVAL_SEC
        ),
        minimum_heart_rate_coverage_ratio=(
            ENVIRONMENT_RESPONSE_MINIMUM_HR_COVERAGE
        ),
        maximum_power_watts=ENVIRONMENT_RESPONSE_MAX_POWER_WATTS,
    )
    return assess_environment_response_preflight(
        counts,
        validation_config=config,
    )


def _record_job_event(
    job: LabsAnalysisJob,
    *,
    event: str,
    outcome: str,
    failure_class: str = "none",
    duration_ms: int | None = None,
) -> None:
    try:
        from api import telemetry

        telemetry.record_labs_job(
            event=event,
            outcome=outcome,
            trigger=job.trigger,
            attempt=job.attempt_count,
            failure_class=failure_class,
            user_id=job.user_id,
            queue_delay_ms=(
                int((job.started_at - job.requested_at).total_seconds() * 1000)
                if job.started_at is not None
                else None
            ),
            duration_ms=duration_ms,
        )
    except Exception:
        logger.debug("Labs job telemetry failed", exc_info=True)


def enroll(
    db: Session,
    user_id: str,
    *,
    adult_attested: bool,
    consent_version: str,
    idempotency_key: str | None = None,
    eligibility_check: Callable[[], None] | None = None,
    now: datetime | None = None,
) -> QueueDecision:
    """Record explicit consent and atomically enqueue one analysis job."""
    if not adult_attested:
        raise ValueError("adult_eligibility_not_confirmed")
    if consent_version != CONSENT_VERSION:
        raise ValueError("consent_version_stale")
    key = _normalize_idempotency_key(idempotency_key)
    current_time = now or datetime.utcnow()
    begin_serialized_write(db)
    lock_revision_writes(db, user_id)
    row = _locked_enrollment(db, user_id, EXPERIMENT_ID)
    existing = _job_for_idempotency_key(
        db,
        user_id,
        EXPERIMENT_ID,
        "enrollment",
        key,
    )
    if existing is not None:
        db.commit()
        return QueueDecision(row, existing, False, idempotent=True)
    if row is not None:
        if _has_current_consent(row):
            active = _active_job(db, user_id, EXPERIMENT_ID, lock=True)
            db.commit()
            return QueueDecision(
                row,
                active,
                False,
                idempotent=True,
            )
        if eligibility_check is not None:
            try:
                eligibility_check()
            except Exception:
                db.rollback()
                raise
        replaced_job = _active_job(
            db,
            user_id,
            EXPERIMENT_ID,
            lock=True,
        )
        if replaced_job is not None:
            replaced_job.status = "cancelled"
            replaced_job.completed_at = current_time
            replaced_job.lease_expires_at = None
            replaced_job.updated_at = current_time
            replaced_outbox = (
                db.query(LabsAnalysisOutbox)
                .filter(LabsAnalysisOutbox.job_id == replaced_job.id)
                .with_for_update()
                .one_or_none()
            )
            if replaced_outbox is not None:
                replaced_outbox.status = "cancelled"
                replaced_outbox.lease_expires_at = None
                replaced_outbox.updated_at = current_time
            db.flush()
        row.consent_version = CONSENT_VERSION
        row.consented_at = current_time
        row.adult_attested_at = current_time
        row.status = "queued"
        row.model_version = LABS_ENVIRONMENT_MODEL_VERSION
        row.source_revision = source_revision(db, user_id)
        row.correlation_id = str(uuid4())
        row.availability_reason = None
        row.queued_at = current_time
        row.started_at = None
        row.completed_at = None
        row.updated_at = current_time
        db.query(LabsExperimentResult).filter(
            LabsExperimentResult.user_id == user_id,
            LabsExperimentResult.experiment_id == EXPERIMENT_ID,
        ).delete(synchronize_session=False)
        job = _create_job(
            db,
            row,
            trigger="enrollment",
            idempotency_key=key,
            requested_at=current_time,
        )
        db.commit()
        db.refresh(row)
        db.refresh(job)
        if replaced_job is not None:
            _record_job_event(
                replaced_job,
                event="cancelled",
                outcome="consent_replaced",
            )
        _record_job_event(job, event="enqueued", outcome="queued")
        return QueueDecision(row, job, True)

    if eligibility_check is not None:
        try:
            eligibility_check()
        except Exception:
            db.rollback()
            raise
    revision = source_revision(db, user_id)
    row = LabsExperimentEnrollment(
        user_id=user_id,
        experiment_id=EXPERIMENT_ID,
        consent_version=CONSENT_VERSION,
        consented_at=current_time,
        adult_attested_at=current_time,
        status="queued",
        model_version=LABS_ENVIRONMENT_MODEL_VERSION,
        source_revision=revision,
        correlation_id=str(uuid4()),
        queued_at=current_time,
        updated_at=current_time,
    )
    db.add(row)
    db.flush()
    job = _create_job(
        db,
        row,
        trigger="enrollment",
        idempotency_key=key,
        requested_at=current_time,
    )
    db.commit()
    db.refresh(row)
    db.refresh(job)
    _record_job_event(job, event="enqueued", outcome="queued")
    return QueueDecision(row, job, True)


def _manual_recompute_limit(
    db: Session,
    user_id: str,
    *,
    now: datetime,
    policy: ManualRecomputePolicy,
) -> RecomputeLimitError | None:
    jobs = (
        db.query(LabsAnalysisJob)
        .filter(
            LabsAnalysisJob.user_id == user_id,
            LabsAnalysisJob.experiment_id == EXPERIMENT_ID,
            LabsAnalysisJob.trigger == "manual_recompute",
            LabsAnalysisJob.requested_at > now - policy.window,
        )
        .order_by(LabsAnalysisJob.requested_at)
        .all()
    )
    code: Literal["cooldown", "daily_limit"] | None = None
    available_at: datetime | None = None
    if jobs:
        cooldown_at = jobs[-1].requested_at + policy.cooldown
        if cooldown_at > now:
            code = "cooldown"
            available_at = cooldown_at
    if len(jobs) >= policy.limit:
        daily_at = _rolling_limit_available_at(jobs, policy)
        if daily_at > now and (
            available_at is None or daily_at > available_at
        ):
            code = "daily_limit"
            available_at = daily_at
    return (
        None
        if code is None or available_at is None
        else RecomputeLimitError(code, available_at)
    )


def _rolling_limit_available_at(
    jobs: list[LabsAnalysisJob],
    policy: ManualRecomputePolicy,
) -> datetime:
    return jobs[len(jobs) - policy.limit].requested_at + policy.window


def queue_recompute(
    db: Session,
    user_id: str,
    *,
    idempotency_key: str | None = None,
    eligibility_check: Callable[[], None] | None = None,
    now: datetime | None = None,
) -> QueueDecision | None:
    """Atomically queue an idempotent, rate-limited manual recompute."""
    key = _normalize_idempotency_key(idempotency_key)
    current_time = now or datetime.utcnow()
    begin_serialized_write(db)
    policy = _manual_recompute_policy(db, user_id)
    lock_revision_writes(db, user_id)
    row = _locked_enrollment(db, user_id, EXPERIMENT_ID)
    if not _has_current_consent(row):
        db.rollback()
        return None
    assert row is not None
    existing = _job_for_idempotency_key(
        db,
        user_id,
        EXPERIMENT_ID,
        "manual_recompute",
        key,
    )
    if existing is not None:
        db.commit()
        return QueueDecision(row, existing, False, idempotent=True)
    active = _active_job(db, user_id, EXPERIMENT_ID, lock=True)
    if active is not None:
        db.commit()
        return QueueDecision(row, active, False, idempotent=True)
    limited = _manual_recompute_limit(
        db,
        user_id,
        now=current_time,
        policy=policy,
    )
    if limited is not None:
        db.rollback()
        raise limited
    if eligibility_check is not None:
        try:
            eligibility_check()
        except Exception:
            db.rollback()
            raise

    row.status = "queued"
    row.model_version = LABS_ENVIRONMENT_MODEL_VERSION
    row.source_revision = source_revision(db, user_id)
    row.correlation_id = str(uuid4())
    row.availability_reason = None
    row.queued_at = current_time
    row.started_at = None
    row.completed_at = None
    row.updated_at = current_time
    db.query(LabsExperimentResult).filter(
        LabsExperimentResult.user_id == user_id,
        LabsExperimentResult.experiment_id == EXPERIMENT_ID,
    ).delete(synchronize_session=False)
    job = _create_job(
        db,
        row,
        trigger="manual_recompute",
        idempotency_key=key,
        requested_at=current_time,
    )
    db.commit()
    db.refresh(row)
    db.refresh(job)
    _record_job_event(job, event="enqueued", outcome="queued")
    return QueueDecision(row, job, True)


def recover_interrupted_jobs(
    db: Session,
    *,
    user_id: str | None = None,
    all_processing: bool = False,
) -> int:
    """Recover legacy queued rows and expired isolated-worker leases."""
    now = datetime.utcnow()
    query = db.query(LabsExperimentEnrollment).filter(
        LabsExperimentEnrollment.experiment_id == EXPERIMENT_ID,
        LabsExperimentEnrollment.status.in_(("queued", "processing")),
    )
    if user_id is not None:
        query = query.filter(LabsExperimentEnrollment.user_id == user_id)
    identities = query.with_entities(
        LabsExperimentEnrollment.user_id,
        LabsExperimentEnrollment.experiment_id,
    ).all()
    db.rollback()
    recovered = 0
    for row_user_id, experiment_id in identities:
        begin_serialized_write(db)
        lock_revision_writes(db, str(row_user_id))
        row = _locked_enrollment(
            db,
            str(row_user_id),
            str(experiment_id),
        )
        if row is None or row.status not in ("queued", "processing"):
            db.rollback()
            continue
        if not _has_current_consent(row):
            stale_job = _active_job(
                db,
                row.user_id,
                row.experiment_id,
                lock=True,
            )
            if stale_job is not None:
                stale_job.status = "cancelled"
                stale_job.completed_at = now
                stale_job.lease_expires_at = None
                stale_job.updated_at = now
                stale_outbox = (
                    db.query(LabsAnalysisOutbox)
                    .filter(LabsAnalysisOutbox.job_id == stale_job.id)
                    .with_for_update()
                    .one_or_none()
                )
                if stale_outbox is not None:
                    stale_outbox.status = "cancelled"
                    stale_outbox.lease_expires_at = None
                    stale_outbox.updated_at = now
            row.status = "unavailable"
            row.availability_reason = None
            row.started_at = None
            row.completed_at = now
            row.updated_at = now
            recovered += 1
            db.commit()
            if stale_job is not None:
                _record_job_event(
                    stale_job,
                    event="cancelled",
                    outcome="consent_version_stale",
                )
            continue
        job = _active_job(
            db,
            row.user_id,
            row.experiment_id,
            lock=True,
        )
        if job is None:
            if row.status == "processing" and not all_processing:
                cutoff = now - JOB_LEASE_DURATION
                if row.started_at is not None and row.started_at > cutoff:
                    db.rollback()
                    continue
            row.status = "queued"
            row.started_at = None
            row.completed_at = None
            row.updated_at = now
            _create_job(
                db,
                row,
                trigger="enrollment",
                idempotency_key=None,
                requested_at=row.queued_at or now,
            )
            recovered += 1
            db.commit()
            continue
        dispatch_outbox = None
        if job.status in ("dispatched", "retrying"):
            dispatch_outbox = (
                db.query(LabsAnalysisOutbox)
                .filter(LabsAnalysisOutbox.job_id == job.id)
                .with_for_update()
                .one_or_none()
            )
        if (
            dispatch_outbox is not None
            and dispatch_outbox.status == "dispatched"
            and dispatch_outbox.dispatched_at is not None
            and dispatch_outbox.dispatched_at <= now - JOB_LEASE_DURATION
            and not _has_worker_predecessor(db, job)
        ):
            job.status = "retrying"
            job.failure_code = "worker_start_timeout"
            job.retryable_failure = True
            job.dispatched_at = None
            job.updated_at = now
            row.status = "queued"
            row.availability_reason = None
            row.started_at = None
            row.completed_at = None
            row.updated_at = now
            _ensure_outbox(
                db,
                job,
                available_at=now,
                force_pending=True,
            )
            recovered += 1
            db.commit()
            _record_job_event(
                job,
                event="retry_scheduled",
                outcome="worker_start_timeout",
                failure_class="worker_start_timeout",
            )
            continue
        if job.status != "processing":
            _ensure_outbox(db, job, available_at=now)
            db.commit()
            continue
        lease_expired = (
            all_processing
            or job.lease_expires_at is None
            or job.lease_expires_at <= now
        )
        if not lease_expired:
            db.rollback()
            continue
        if job.attempt_count >= MAX_JOB_ATTEMPTS:
            job.status = "dead_lettered"
            job.retryable_failure = True
            job.failure_code = job.failure_code or "worker_lease_expired"
            job.completed_at = now
            job.updated_at = now
            row.status = "failed"
            row.availability_reason = _reason(
                "analysis_retry_exhausted",
                correlation_id=row.correlation_id,
            )
            row.completed_at = now
            row.updated_at = now
            recovered += 1
            db.commit()
            _record_job_event(
                job,
                event="dead_lettered",
                outcome="worker_lease_expired",
                failure_class=job.failure_code,
            )
            continue
        job.status = "retrying"
        job.retryable_failure = True
        job.failure_code = "worker_lease_expired"
        job.dispatched_at = None
        job.started_at = None
        job.lease_expires_at = None
        job.updated_at = now
        row.status = "queued"
        row.availability_reason = None
        row.queued_at = now
        row.started_at = None
        row.completed_at = None
        row.updated_at = now
        _ensure_outbox(
            db,
            job,
            available_at=now,
            force_pending=True,
        )
        recovered += 1
        db.commit()
        _record_job_event(
            job,
            event="retry_scheduled",
            outcome="worker_lease_expired",
            failure_class="worker_lease_expired",
        )
    return recovered


def withdraw(db: Session, user_id: str) -> bool:
    """Delete consent/result, cancel active jobs, and retain a tombstone."""
    begin_serialized_write(db)
    lock_revision_writes(db, user_id)
    enrollment = _locked_enrollment(db, user_id, EXPERIMENT_ID)
    deleted_at = datetime.utcnow()
    labs_tombstone_storage.store(
        user_id,
        EXPERIMENT_ID,
        deleted_at,
    )
    existed = enrollment is not None or (
        db.get(LabsExperimentResult, (user_id, EXPERIMENT_ID)) is not None
    )
    cancelled_jobs = (
        db.query(LabsAnalysisJob)
        .filter(
            LabsAnalysisJob.user_id == user_id,
            LabsAnalysisJob.experiment_id == EXPERIMENT_ID,
            LabsAnalysisJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .with_for_update()
        .all()
    )
    for job in cancelled_jobs:
        job.status = "cancelled"
        job.completed_at = deleted_at
        job.lease_expires_at = None
        job.updated_at = deleted_at
        outbox = (
            db.query(LabsAnalysisOutbox)
            .filter(LabsAnalysisOutbox.job_id == job.id)
            .with_for_update()
            .one_or_none()
        )
        if outbox is not None:
            outbox.status = "cancelled"
            outbox.lease_expires_at = None
            outbox.updated_at = deleted_at
    db.query(LabsExperimentResult).filter(
        LabsExperimentResult.user_id == user_id,
        LabsExperimentResult.experiment_id == EXPERIMENT_ID,
    ).delete(synchronize_session=False)
    db.query(LabsExperimentEnrollment).filter(
        LabsExperimentEnrollment.user_id == user_id,
        LabsExperimentEnrollment.experiment_id == EXPERIMENT_ID,
    ).delete(synchronize_session=False)
    tombstone = db.get(LabsDeletionTombstone, (user_id, EXPERIMENT_ID))
    if tombstone is None:
        db.add(LabsDeletionTombstone(
            user_id=user_id,
            experiment_id=EXPERIMENT_ID,
            deleted_at=deleted_at,
        ))
    else:
        tombstone.deleted_at = deleted_at
    db.commit()
    for job in cancelled_jobs:
        _record_job_event(job, event="cancelled", outcome="withdrawn")
    return existed


def replay_deletion_tombstones(db: Session) -> int:
    """Reapply withdrawals after a point-in-time database restore."""
    for external in labs_tombstone_storage.iter_active():
        identity = (
            str(external["user_id"]),
            str(external["experiment_id"]),
        )
        if db.get(User, identity[0]) is None:
            continue
        tombstone = db.get(LabsDeletionTombstone, identity)
        deleted_at = external["deleted_at"]
        if tombstone is None:
            db.add(LabsDeletionTombstone(
                user_id=identity[0],
                experiment_id=identity[1],
                deleted_at=deleted_at,
            ))
        elif tombstone.deleted_at < deleted_at:
            tombstone.deleted_at = deleted_at
    db.flush()
    deleted = 0
    for tombstone in db.query(LabsDeletionTombstone).all():
        deleted += db.query(LabsExperimentResult).filter(
            LabsExperimentResult.user_id == tombstone.user_id,
            LabsExperimentResult.experiment_id == tombstone.experiment_id,
            LabsExperimentResult.computed_at <= tombstone.deleted_at,
        ).delete(synchronize_session=False)
        jobs = (
            db.query(LabsAnalysisJob)
            .filter(
                LabsAnalysisJob.user_id == tombstone.user_id,
                LabsAnalysisJob.experiment_id == tombstone.experiment_id,
                LabsAnalysisJob.requested_at <= tombstone.deleted_at,
                LabsAnalysisJob.status.in_(ACTIVE_JOB_STATUSES),
            )
            .with_for_update()
            .all()
        )
        for job in jobs:
            job.status = "cancelled"
            job.completed_at = tombstone.deleted_at
            job.lease_expires_at = None
            job.updated_at = tombstone.deleted_at
            outbox = (
                db.query(LabsAnalysisOutbox)
                .filter(LabsAnalysisOutbox.job_id == job.id)
                .with_for_update()
                .one_or_none()
            )
            if outbox is not None:
                outbox.status = "cancelled"
                outbox.lease_expires_at = None
                outbox.updated_at = tombstone.deleted_at
        deleted += db.query(LabsExperimentEnrollment).filter(
            LabsExperimentEnrollment.user_id == tombstone.user_id,
            LabsExperimentEnrollment.experiment_id == tombstone.experiment_id,
            LabsExperimentEnrollment.consented_at <= tombstone.deleted_at,
        ).delete(synchronize_session=False)
    db.commit()
    return deleted


def _claim_job(
    db: Session,
    job_id: str,
    *,
    reclaim_processing: bool,
) -> tuple[LabsAnalysisJob, LabsExperimentEnrollment] | None:
    identity = _job_identity(db, job_id)
    if identity is None:
        return None
    from api.stryd_access import stryd_connection_enabled

    access_enabled = stryd_connection_enabled(db, user_id=identity[0])
    begin_serialized_write(db)
    lock_revision_writes(db, identity[0])
    row = _locked_enrollment(db, identity[0], identity[1])
    job = (
        db.query(LabsAnalysisJob)
        .filter(LabsAnalysisJob.id == job_id)
        .with_for_update()
        .one_or_none()
    )
    if job is None:
        db.rollback()
        return None
    claimable = job.status in ("queued", "dispatched", "retrying")
    if job.status == "processing" and reclaim_processing:
        claimable = True
    if not claimable:
        db.rollback()
        return None
    if not access_enabled:
        completed_at = datetime.utcnow()
        job.status = "cancelled"
        job.failure_code = "stryd_access_revoked"
        job.retryable_failure = False
        job.completed_at = completed_at
        job.lease_expires_at = None
        job.updated_at = completed_at
        outbox = (
            db.query(LabsAnalysisOutbox)
            .filter(LabsAnalysisOutbox.job_id == job.id)
            .with_for_update()
            .one_or_none()
        )
        if outbox is not None:
            outbox.status = "cancelled"
            outbox.lease_expires_at = None
            outbox.updated_at = completed_at
        if _same_job_generation(row, job):
            assert row is not None
            row.status = "unavailable"
            row.availability_reason = None
            row.started_at = None
            row.completed_at = completed_at
            row.updated_at = completed_at
        db.commit()
        _record_job_event(
            job,
            event="cancelled",
            outcome="access_revoked",
        )
        return None
    if _same_job_generation(row, job) and not _uses_current_model(row, job):
        _cancel_model_mismatch(db, row, job)
        return None
    if (
        row is None
        or not _has_current_consent(row)
        or row.user_id != job.user_id
        or row.experiment_id != job.experiment_id
        or row.model_version != job.model_version
        or row.source_revision != job.source_revision
        or row.correlation_id != job.correlation_id
        or row.status not in ("queued", "processing")
    ):
        job.status = "cancelled"
        job.completed_at = datetime.utcnow()
        job.lease_expires_at = None
        job.updated_at = job.completed_at
        db.commit()
        return None
    tombstone = db.get(
        LabsDeletionTombstone,
        (job.user_id, job.experiment_id),
    )
    if tombstone is not None and tombstone.deleted_at >= row.consented_at:
        job.status = "cancelled"
        job.completed_at = datetime.utcnow()
        job.lease_expires_at = None
        job.updated_at = job.completed_at
        db.commit()
        return None
    from api.legal_receipts import user_background_processing_authorized

    if not user_background_processing_authorized(db, job.user_id):
        _cancel_processing_not_authorized(db, row, job)
        return None
    if (job.attempt_count or 0) >= MAX_JOB_ATTEMPTS:
        completed_at = datetime.utcnow()
        job.status = "dead_lettered"
        job.failure_code = "worker_attempt_limit_exhausted"
        job.retryable_failure = True
        job.completed_at = completed_at
        job.lease_expires_at = None
        job.updated_at = completed_at
        row.status = "failed"
        row.availability_reason = _reason(
            "analysis_retry_exhausted",
            correlation_id=job.correlation_id,
        )
        row.completed_at = completed_at
        row.updated_at = completed_at
        db.commit()
        return None
    started_at = datetime.utcnow()
    job.status = "processing"
    job.attempt_count = (job.attempt_count or 0) + 1
    job.failure_code = None
    job.retryable_failure = False
    job.started_at = started_at
    job.lease_expires_at = started_at + JOB_LEASE_DURATION
    job.updated_at = started_at
    row.status = "processing"
    row.started_at = started_at
    row.completed_at = None
    row.updated_at = started_at
    db.commit()
    return job, row


def _is_retryable_job_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (OperationalError, InterfaceError, TimeoutError, ConnectionError),
    )


def _persist_job_failure(
    db: Session,
    job_id: str,
    exc: Exception,
) -> JobExecutionResult:
    db.rollback()
    db.expire_all()
    identity = _job_identity(db, job_id)
    if identity is None:
        return JobExecutionResult("ignored")
    begin_serialized_write(db)
    lock_revision_writes(db, identity[0])
    row = _locked_enrollment(db, identity[0], identity[1])
    job = (
        db.query(LabsAnalysisJob)
        .filter(LabsAnalysisJob.id == job_id)
        .with_for_update()
        .one_or_none()
    )
    if job is None:
        db.rollback()
        return JobExecutionResult("ignored")
    if job.status != "processing":
        result = _execution_result_for_job(job)
        db.rollback()
        return result
    from api.legal_receipts import user_background_processing_authorized

    if not user_background_processing_authorized(db, job.user_id):
        return _cancel_processing_not_authorized(db, row, job)
    if not _has_current_consent(row):
        now = datetime.utcnow()
        job.status = "cancelled"
        job.completed_at = now
        job.lease_expires_at = None
        job.updated_at = now
        db.commit()
        _record_job_event(
            job,
            event="cancelled",
            outcome="consent_version_stale",
        )
        return JobExecutionResult(
            "cancelled",
            attempt_count=job.attempt_count,
        )
    if _same_job_generation(row, job) and not _uses_current_model(row, job):
        _cancel_model_mismatch(db, row, job)
        return JobExecutionResult(
            "cancelled",
            attempt_count=job.attempt_count,
            failure_code="model_version_mismatch",
        )
    failure_code = type(exc).__name__[:64]
    retryable = _is_retryable_job_error(exc)
    exhausted = retryable and job.attempt_count >= MAX_JOB_ATTEMPTS
    now = datetime.utcnow()
    job.failure_code = failure_code
    job.retryable_failure = retryable
    job.lease_expires_at = None
    job.updated_at = now
    if retryable and not exhausted:
        job.status = "retrying"
        if row is not None and row.correlation_id == job.correlation_id:
            row.status = "queued"
            row.availability_reason = None
            row.started_at = None
            row.completed_at = None
            row.updated_at = now
        db.commit()
        _record_job_event(
            job,
            event="retry_scheduled",
            outcome="retry",
            failure_class=failure_code,
        )
        return JobExecutionResult(
            "retry",
            attempt_count=job.attempt_count,
            failure_code=failure_code,
        )

    job.status = "dead_lettered" if exhausted else "failed"
    job.completed_at = now
    if row is not None and row.correlation_id == job.correlation_id:
        row.status = "failed"
        row.availability_reason = _reason(
            "analysis_retry_exhausted" if exhausted else "analysis_failed",
            correlation_id=job.correlation_id,
        )
        row.completed_at = now
        row.updated_at = now
    db.commit()
    outcome = "dead_lettered" if exhausted else "failed"
    _record_job_event(
        job,
        event=outcome,
        outcome=outcome,
        failure_class=failure_code,
    )
    return JobExecutionResult(
        outcome,
        attempt_count=job.attempt_count,
        failure_code=failure_code,
    )


def process_environment_response_job(
    job_id: str,
    *,
    reclaim_processing: bool = False,
) -> JobExecutionResult:
    """Run one durable Labs job and return its queue settlement outcome."""
    from db import session as db_session

    db = db_session.SessionLocal()
    claimed: tuple[LabsAnalysisJob, LabsExperimentEnrollment] | None = None
    try:
        claimed = _claim_job(
            db,
            job_id,
            reclaim_processing=reclaim_processing,
        )
        if claimed is None:
            return _existing_job_execution_result(db, job_id)
        job, _row = claimed
        _require_processing_authorized(db, job.user_id)
        _record_job_event(job, event="started", outcome="processing")
        try:
            bundle = _build_private_dataset_bundle(
                db,
                job.user_id,
                job.source_revision,
            )
        except StaleSourceRevision:
            return _persist_unavailable(
                db,
                job.id,
                "stale_source_revision",
                "stale",
            )
        if source_revision(db, job.user_id) != job.source_revision:
            return _persist_unavailable(
                db,
                job.id,
                "stale_source_revision",
                "stale",
            )
        _require_processing_authorized(db, job.user_id)
        aggregate = build_environment_response_result(bundle)
        if aggregate.get("model_version") != LABS_ENVIRONMENT_MODEL_VERSION:
            return _persist_unavailable(
                db,
                job.id,
                "stale_model_version",
                "stale",
            )
        if source_revision(db, job.user_id) != job.source_revision:
            return _persist_unavailable(
                db,
                job.id,
                "stale_source_revision",
                "stale",
            )

        db.rollback()
        db.expire_all()
        identity = _job_identity(db, job_id)
        if identity is None:
            return JobExecutionResult("cancelled")
        begin_serialized_write(db)
        lock_revision_writes(db, identity[0])
        row = _locked_enrollment(db, identity[0], identity[1])
        job = (
            db.query(LabsAnalysisJob)
            .filter(LabsAnalysisJob.id == job_id)
            .with_for_update()
            .one_or_none()
        )
        if job is None or job.status != "processing":
            db.rollback()
            return JobExecutionResult("cancelled")
        if (
            row is None
            or not _has_current_consent(row)
            or row.user_id != job.user_id
            or row.experiment_id != job.experiment_id
            or row.status != "processing"
            or not _uses_current_model(row, job)
            or row.source_revision != job.source_revision
            or row.correlation_id != job.correlation_id
            or aggregate.get("model_version") != job.model_version
        ):
            if _same_job_generation(row, job) and not _uses_current_model(
                row,
                job,
            ):
                _cancel_model_mismatch(db, row, job)
            else:
                job.status = "cancelled"
                job.completed_at = datetime.utcnow()
                job.lease_expires_at = None
                job.updated_at = job.completed_at
                db.commit()
            return JobExecutionResult(
                "cancelled",
                attempt_count=job.attempt_count,
            )
        tombstone = db.get(
            LabsDeletionTombstone,
            (job.user_id, job.experiment_id),
        )
        if tombstone is not None and tombstone.deleted_at >= row.consented_at:
            job.status = "cancelled"
            job.completed_at = datetime.utcnow()
            job.lease_expires_at = None
            job.updated_at = job.completed_at
            db.commit()
            return JobExecutionResult(
                "cancelled",
                attempt_count=job.attempt_count,
            )
        from api.legal_receipts import user_background_processing_authorized

        if not user_background_processing_authorized(db, job.user_id):
            return _cancel_processing_not_authorized(db, row, job)
        if source_revision(db, job.user_id) != job.source_revision:
            db.rollback()
            return _persist_unavailable(
                db,
                job.id,
                "stale_source_revision",
                "stale",
            )
        result = db.get(
            LabsExperimentResult,
            (job.user_id, job.experiment_id),
        )
        if result is None:
            result = LabsExperimentResult(
                user_id=job.user_id,
                experiment_id=job.experiment_id,
            )
            db.add(result)
        result.model_version = aggregate["model_version"]
        result.source_revision = job.source_revision
        result.result_state = aggregate["result_state"]
        result.eligibility_counts = aggregate["eligibility_counts"]
        result.aggregate_curve_points = aggregate["aggregate_curve_points"]
        result.aggregate_uncertainty = aggregate["aggregate_uncertainty"]
        result.gate_statuses = aggregate["gate_statuses"]
        result.prediction_status = aggregate["prediction_status"]
        result.power_regime = aggregate["power_regime"]
        completed_at = datetime.utcnow()
        result.computed_at = completed_at
        row.status = (
            "available"
            if aggregate["aggregate_curve_points"]
            else "unavailable"
        )
        row.availability_reason = (
            None
            if row.status == "available"
            else availability_reason(
                aggregate,
                correlation_id=job.correlation_id,
            )
        )
        row.completed_at = completed_at
        row.updated_at = completed_at
        job.status = "succeeded"
        job.completed_at = completed_at
        job.lease_expires_at = None
        job.updated_at = completed_at
        _require_processing_authorized(db, job.user_id)
        db.commit()
        duration_ms = (
            int((completed_at - job.started_at).total_seconds() * 1000)
            if job.started_at is not None
            else None
        )
        _record_job_event(
            job,
            event="completed",
            outcome=row.status,
            duration_ms=duration_ms,
        )
        return JobExecutionResult(
            "completed",
            attempt_count=job.attempt_count,
        )
    except ProcessingNotAuthorized:
        return _persist_processing_not_authorized(db, job_id)
    except Exception as exc:
        db.rollback()
        job = claimed[0] if claimed is not None else None
        logger.error(
            "Labs environment-response processing failed "
            "job_id=%s correlation_id=%s stage=analysis model=%s "
            "regime=%s failure_class=%s",
            job_id,
            "unknown" if job is None else job.correlation_id,
            "unknown" if job is None else job.model_version,
            POWER_REGIME,
            type(exc).__name__,
        )
        if claimed is None:
            raise
        try:
            return _persist_job_failure(db, job_id, exc)
        except Exception as persistence_exc:
            db.rollback()
            logger.error(
                "Labs failure state persistence failed job_id=%s "
                "failure_class=%s",
                job_id,
                type(persistence_exc).__name__,
            )
            raise
    finally:
        db.close()


def _build_private_dataset_bundle(
    db: Session,
    user_id: str,
    expected_source_revision: str,
) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    offset = 0
    limit = 50
    ctx = RequestContext(user_id=user_id, db=db, include_plan=False)
    while True:
        _require_processing_authorized(db, user_id)
        if source_revision(db, user_id) != expected_source_revision:
            raise StaleSourceRevision
        page = get_activity_research_pack(
            ctx,
            export_snapshot_id=expected_source_revision,
            limit=limit,
            offset=offset,
        )
        _require_processing_authorized(db, user_id)
        pages.append(page)
        offset += limit
        if offset >= page["total"]:
            break
    _require_processing_authorized(db, user_id)
    return build_research_dataset_bundle(pages)


def _persist_unavailable(
    db: Session,
    job_id: str,
    code: str,
    status: str,
) -> JobExecutionResult:
    db.rollback()
    db.expire_all()
    identity = _job_identity(db, job_id)
    if identity is None:
        return JobExecutionResult("cancelled")
    begin_serialized_write(db)
    lock_revision_writes(db, identity[0])
    row = _locked_enrollment(db, identity[0], identity[1])
    job = (
        db.query(LabsAnalysisJob)
        .filter(LabsAnalysisJob.id == job_id)
        .with_for_update()
        .one_or_none()
    )
    if job is None or job.status != "processing":
        result = _execution_result_for_job(job)
        db.rollback()
        return result
    if (
        row is None
        or not _has_current_consent(row)
        or row.user_id != job.user_id
        or row.experiment_id != job.experiment_id
        or not _uses_current_model(row, job)
        or row.source_revision != job.source_revision
        or row.correlation_id != job.correlation_id
        or row.status != "processing"
    ):
        if _same_job_generation(row, job) and not _uses_current_model(
            row,
            job,
        ):
            _cancel_model_mismatch(db, row, job)
        else:
            job.status = "cancelled"
            job.completed_at = datetime.utcnow()
            job.lease_expires_at = None
            job.updated_at = job.completed_at
            db.commit()
        return JobExecutionResult(
            "cancelled",
            attempt_count=job.attempt_count,
            failure_code=job.failure_code,
        )
    from api.legal_receipts import user_background_processing_authorized

    if not user_background_processing_authorized(db, job.user_id):
        return _cancel_processing_not_authorized(db, row, job)
    completed_at = datetime.utcnow()
    row.status = status
    row.availability_reason = _reason(
        code,
        correlation_id=job.correlation_id,
    )
    row.completed_at = completed_at
    row.updated_at = completed_at
    job.status = "succeeded"
    job.completed_at = completed_at
    job.lease_expires_at = None
    job.updated_at = completed_at
    db.commit()
    duration_ms = (
        int((completed_at - job.started_at).total_seconds() * 1000)
        if job.started_at is not None
        else None
    )
    _record_job_event(
        job,
        event="completed",
        outcome=status,
        duration_ms=duration_ms,
    )
    return JobExecutionResult(
        "completed",
        attempt_count=job.attempt_count,
    )


def availability_reason(
    aggregate: dict[str, Any],
    *,
    correlation_id: str,
) -> dict[str, Any]:
    """Map aggregate gate failures to the stable public diagnostic taxonomy."""
    gates = aggregate["gate_statuses"]
    exclusions = aggregate.get("eligibility_counts", {}).get(
        "exclusion_reason_counts",
        {},
    )
    exclusion_priority = (
        (
            (
                "power_missing_or_invalid",
                "split_fallback_excluded",
                "stable_segments_unavailable",
            ),
            "missing_continuous_sample_power",
        ),
        (
            ("mean_hr_missing_or_invalid", "heart_rate_provider_missing"),
            "missing_continuous_heart_rate",
        ),
        (
            ("temperature_missing_or_invalid",),
            "missing_temperature",
        ),
        (
            ("relative_humidity_missing_or_invalid",),
            "missing_relative_humidity",
        ),
        (
            (
                "critical_power_contract_missing",
                "critical_power_unavailable",
                "critical_power_value_missing_or_invalid",
                "critical_power_provider_missing",
            ),
            "missing_provider_aligned_critical_power",
        ),
        (
            (
                "critical_power_provider_mismatch",
                "mean_pct_cp_critical_power_mismatch",
                "provider_mismatch_reason_code",
            ),
            "critical_power_provider_mismatch",
        ),
        (
            (
                "activity_sample_coverage_missing",
                "activity_sample_coverage_low",
                "segment_sample_coverage_missing",
                "segment_sample_coverage_low",
            ),
            "insufficient_sample_coverage",
        ),
    )
    priority = (
        ("complete_export", "incomplete_export"),
        ("minimum_activities", "insufficient_activities"),
        ("minimum_segments", "insufficient_segments"),
        ("environmental_spread", "insufficient_environmental_spread"),
        ("chronological_holdout", "insufficient_holdout"),
        ("holdout_environmental_spread", "insufficient_holdout"),
        ("curve_bin_support", "insufficient_curve_bin_support"),
        ("reference_power_overlap", "insufficient_reference_power_overlap"),
        ("provider_regime_consistency", "mixed_power_regime"),
        ("bootstrap_interval_excludes_zero", "bootstrap_unstable"),
        ("bootstrap_interval_width", "bootstrap_unstable"),
        ("sensitivity_analysis_coverage", "sensitivity_unstable"),
        ("coefficient_stability", "sensitivity_unstable"),
        ("leave_one_activity_out_influence", "influential_activity"),
    )
    exclusion_code = next(
        (
            mapped
            for reason_names, mapped in exclusion_priority
            if any(exclusions.get(name, 0) for name in reason_names)
        ),
        None,
    )
    minimum_support_failed = any(
        gates.get(gate_name) != "pass"
        for gate_name in ("minimum_activities", "minimum_segments")
    )
    if exclusion_code is not None and minimum_support_failed:
        code = exclusion_code
    elif gates.get("stryd_power_regime") == "fail":
        combinations = aggregate.get("eligibility_counts", {}).get(
            "provider_regimes",
            [],
        )
        code = (
            "unverified_garmin_wrist_power"
            if any("power=garmin|" in str(item) for item in combinations)
            else "unsupported_power_provider"
        )
    elif aggregate["result_state"] == "prediction_unavailable":
        code = "prediction_unavailable"
    else:
        code = next(
            (
                mapped
                for gate_name, mapped in priority
                if gates.get(gate_name) != "pass"
            ),
            "analysis_failed",
        )
    counts = aggregate.get("eligibility_counts", {})
    observed = {
        key: counts[key]
        for key in (
            "eligible_activity_count",
            "eligible_segment_count",
            "observed_wet_bulb_domain_c",
        )
        if key in counts
    }
    return _reason(
        code,
        correlation_id=correlation_id,
        observed_aggregate=observed or None,
    )


def _reason(
    code: str,
    *,
    correlation_id: str,
    observed_aggregate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    category = (
        "processing"
        if code.startswith("analysis_")
        else "eligibility"
        if code == "adult_eligibility_not_confirmed"
        else "data_support"
    )
    return {
        "code": code,
        "category": category,
        "public_message_key": f"labs.environment.reason.{code}",
        "observed_aggregate": observed_aggregate,
        "required_guardrail": code,
        "user_actionable": code not in {
            "analysis_failed",
            "bootstrap_unstable",
            "sensitivity_unstable",
            "influential_activity",
        },
        "suggested_action_key": f"labs.environment.action.{code}",
        "analysis_stage": "environment_response",
        "power_regime": POWER_REGIME,
        "model_version": LABS_ENVIRONMENT_MODEL_VERSION,
        "correlation_id": correlation_id,
    }


def adult_eligibility_reason() -> dict[str, Any]:
    """Return a structured diagnostic for a rejected adult attestation."""
    return _reason(
        "adult_eligibility_not_confirmed",
        correlation_id=str(uuid4()),
    )


def _recompute_policy_state(
    db: Session,
    user_id: str,
    row: LabsExperimentEnrollment | None,
    *,
    now: datetime,
) -> dict[str, Any]:
    policy = _manual_recompute_policy(db, user_id)
    active = _active_job(db, user_id, EXPERIMENT_ID)
    window_jobs = (
        db.query(LabsAnalysisJob)
        .filter(
            LabsAnalysisJob.user_id == user_id,
            LabsAnalysisJob.experiment_id == EXPERIMENT_ID,
            LabsAnalysisJob.trigger == "manual_recompute",
            LabsAnalysisJob.requested_at > now - policy.window,
        )
        .order_by(LabsAnalysisJob.requested_at)
        .all()
    )
    remaining = max(0, policy.limit - len(window_jobs))
    reason: str | None = None
    available_at: datetime | None = None
    if row is None:
        reason = "not_enrolled"
    elif active is not None:
        reason = "active_job"
    else:
        if window_jobs:
            cooldown_at = (
                window_jobs[-1].requested_at + policy.cooldown
            )
            if cooldown_at > now:
                reason = "cooldown"
                available_at = cooldown_at
        if len(window_jobs) >= policy.limit:
            daily_at = _rolling_limit_available_at(window_jobs, policy)
            if daily_at > now and (
                available_at is None or daily_at > available_at
            ):
                reason = "daily_limit"
                available_at = daily_at
    retry_after_seconds = (
        max(0, int((available_at - now).total_seconds() + 0.999))
        if available_at is not None
        else None
    )
    return {
        "allowed": reason is None,
        "reason": reason,
        "available_at": utc_isoformat(available_at),
        "retry_after_seconds": retry_after_seconds,
        "remaining_requests": remaining,
        "window_hours": int(policy.window.total_seconds() / 3600),
        "cooldown_hours": int(policy.cooldown.total_seconds() / 3600),
    }


def public_state(
    db: Session,
    user_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return the authenticated, aggregate-only experiment state."""
    current_time = now or datetime.utcnow()
    row = db.get(LabsExperimentEnrollment, (user_id, EXPERIMENT_ID))
    current_consent = _has_current_consent(row)
    latest_job = _latest_job(db, user_id, EXPERIMENT_ID)
    result = (
        db.get(LabsExperimentResult, (user_id, EXPERIMENT_ID))
        if current_consent
        else None
    )
    enrollment_model_current = (
        current_consent
        and row is not None
        and row.model_version == LABS_ENVIRONMENT_MODEL_VERSION
    )
    aggregate_model_current = (
        result is not None
        and enrollment_model_current
        and result.model_version == LABS_ENVIRONMENT_MODEL_VERSION
        and row is not None
        and result.source_revision == row.source_revision
    )
    stored_status = None if row is None else row.status
    published_status = (
        "not_enrolled"
        if not current_consent
        else (
            "stale"
            if (
                not enrollment_model_current
                or (stored_status == "available" and not aggregate_model_current)
            )
            else stored_status
        )
    )
    published_reason = (
        _reason(
            "stale_model_version",
            correlation_id=None if row is None else row.correlation_id,
        )
        if current_consent
        and (
            not enrollment_model_current
            or (stored_status == "available" and not aggregate_model_current)
        )
        else (None if not current_consent else row.availability_reason)
    )
    base = {
        "experiment_id": EXPERIMENT_ID,
        "consent_version": CONSENT_VERSION,
        "model_version": LABS_ENVIRONMENT_MODEL_VERSION,
        "enrolled": current_consent,
        "status": published_status,
        "adult_attestation_required": True,
        "power_regime": POWER_REGIME,
        "availability_reason": published_reason,
        "result": None,
        "execution": {
            "job_status": None if latest_job is None else latest_job.status,
            "attempt_count": (
                0 if latest_job is None else latest_job.attempt_count
            ),
            "retryable_failure": (
                False
                if latest_job is None
                else latest_job.retryable_failure
            ),
            "requested_at": (
                None
                if latest_job is None
                else utc_isoformat(latest_job.requested_at)
            ),
            "dispatched_at": (
                None
                if latest_job is None
                else utc_isoformat(latest_job.dispatched_at)
            ),
            "recompute": _recompute_policy_state(
                db,
                user_id,
                row if current_consent else None,
                now=current_time,
            ),
        },
    }
    if not current_consent:
        return base
    assert row is not None
    base.update({
        "consented_at": utc_isoformat(row.consented_at),
        "adult_attested_at": utc_isoformat(row.adult_attested_at),
        "source_revision": row.source_revision,
        "correlation_id": row.correlation_id,
        "queued_at": utc_isoformat(row.queued_at),
        "started_at": utc_isoformat(row.started_at),
        "completed_at": utc_isoformat(row.completed_at),
    })
    if result is not None and aggregate_model_current:
        base["result"] = {
            "result_state": result.result_state,
            "prediction_status": result.prediction_status,
            "eligibility_counts": result.eligibility_counts,
            "aggregate_curve_points": result.aggregate_curve_points,
            "aggregate_uncertainty": result.aggregate_uncertainty,
            "gate_statuses": result.gate_statuses,
            "computed_at": utc_isoformat(result.computed_at),
            "source_revision": result.source_revision,
            "model_version": result.model_version,
            "power_regime": result.power_regime,
        }
    return base
