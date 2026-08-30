"""Transactional dispatch for isolated Labs analysis jobs."""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

from sqlalchemy import or_

from api.labs_environment import (
    ACTIVE_JOB_STATUSES,
    _authorize_job_dispatch,
    _record_job_event,
    process_environment_response_job,
    recover_interrupted_jobs,
)
from api.labs_service_bus import (
    azure_credential as _azure_credential,
    execution_mode,
    service_bus_namespace,
    service_bus_queue,
    validate_configuration,
)
from db.models import LabsAnalysisJob, LabsAnalysisOutbox
from db.session import begin_serialized_write

logger = logging.getLogger(__name__)

DISPATCH_INTERVAL_SEC = 30
DISPATCH_LEASE = timedelta(minutes=2)
DISPATCH_BATCH_SIZE = 10
_dispatcher_thread: threading.Thread | None = None
_stop_event = threading.Event()
_wake_event = threading.Event()


def _claim_outbox(
    job_id: str | None = None,
) -> tuple[str, str] | None:
    from db import session as db_session

    with db_session.SessionLocal() as db:
        begin_serialized_write(db)
        now = datetime.utcnow()
        query = (
            db.query(LabsAnalysisOutbox)
            .join(
                LabsAnalysisJob,
                LabsAnalysisJob.id == LabsAnalysisOutbox.job_id,
            )
            .filter(
                LabsAnalysisJob.status.in_(ACTIVE_JOB_STATUSES),
                LabsAnalysisOutbox.available_at <= now,
                or_(
                    LabsAnalysisOutbox.status == "pending",
                    (
                        (LabsAnalysisOutbox.status == "dispatching")
                        & (
                            (LabsAnalysisOutbox.lease_expires_at.is_(None))
                            | (LabsAnalysisOutbox.lease_expires_at <= now)
                        )
                    ),
                ),
            )
            .order_by(LabsAnalysisOutbox.available_at)
        )
        if job_id is not None:
            query = query.filter(LabsAnalysisOutbox.job_id == job_id)
        outbox = query.with_for_update(of=LabsAnalysisOutbox).first()
        if outbox is None:
            db.rollback()
            return None
        outbox.status = "dispatching"
        outbox.attempt_count = (outbox.attempt_count or 0) + 1
        outbox.lease_expires_at = now + DISPATCH_LEASE
        outbox.last_error_code = None
        outbox.updated_at = now
        claimed = (outbox.id, outbox.job_id)
        db.commit()
        return claimed


def _mark_dispatched(
    outbox_id: str,
    job_id: str,
    *,
    outcome: str,
) -> bool:
    from db import session as db_session

    with db_session.SessionLocal() as db:
        begin_serialized_write(db)
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
        if outbox is None or job is None or outbox.status != "dispatching":
            db.rollback()
            return False
        now = datetime.utcnow()
        outbox.status = "dispatched"
        outbox.dispatched_at = now
        outbox.lease_expires_at = None
        outbox.updated_at = now
        if job.status == "queued":
            job.status = "dispatched"
        if job.dispatched_at is None:
            job.dispatched_at = now
        job.updated_at = now
        db.commit()
        _record_job_event(job, event="dispatched", outcome=outcome)
        return True


def _mark_dispatch_failure(
    outbox_id: str,
    job_id: str,
    exc: Exception,
) -> None:
    from db import session as db_session

    with db_session.SessionLocal() as db:
        begin_serialized_write(db)
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
        if outbox is None or outbox.status != "dispatching":
            db.rollback()
            return
        now = datetime.utcnow()
        delay_seconds = min(300, 5 * (2 ** min(outbox.attempt_count - 1, 6)))
        outbox.status = "pending"
        outbox.available_at = now + timedelta(seconds=delay_seconds)
        outbox.lease_expires_at = None
        outbox.last_error_code = type(exc).__name__[:64]
        outbox.updated_at = now
        db.commit()
        if job is not None:
            _record_job_event(
                job,
                event="dispatch_failed",
                outcome="retry",
                failure_class=type(exc).__name__[:64],
            )


def _requeue_inline_retry(
    outbox_id: str,
    *,
    failure_code: str | None = None,
) -> None:
    from db import session as db_session

    with db_session.SessionLocal() as db:
        begin_serialized_write(db)
        outbox = (
            db.query(LabsAnalysisOutbox)
            .filter(LabsAnalysisOutbox.id == outbox_id)
            .with_for_update()
            .one_or_none()
        )
        if outbox is None or outbox.status == "cancelled":
            db.rollback()
            return
        now = datetime.utcnow()
        outbox.status = "pending"
        outbox.available_at = now + timedelta(seconds=5)
        outbox.lease_expires_at = None
        if failure_code is not None:
            outbox.last_error_code = failure_code[:64]
        outbox.updated_at = now
        db.commit()


def _send_service_bus(job_id: str) -> None:
    from azure.servicebus import ServiceBusClient, ServiceBusMessage

    with ServiceBusClient(
        fully_qualified_namespace=service_bus_namespace(),
        credential=_azure_credential(),
    ) as client:
        with client.get_queue_sender(service_bus_queue()) as sender:
            sender.send_messages(
                ServiceBusMessage(
                    job_id,
                    message_id=job_id,
                    content_type="text/plain",
                    subject="environment-response-v1",
                )
            )


def _dispatch_claim(outbox_id: str, job_id: str) -> bool:
    from db import session as db_session

    with db_session.SessionLocal() as db:
        if not _authorize_job_dispatch(
            db,
            outbox_id=outbox_id,
            job_id=job_id,
        ):
            return False
    mode = execution_mode()
    try:
        if mode == "service_bus":
            _send_service_bus(job_id)
        elif mode == "inline":
            pass
        else:
            return False
    except Exception as exc:
        logger.error(
            "Labs outbox dispatch failed job_id=%s failure_class=%s",
            job_id,
            type(exc).__name__,
        )
        _mark_dispatch_failure(outbox_id, job_id, exc)
        return False

    if not _mark_dispatched(outbox_id, job_id, outcome=mode):
        return False
    if mode == "inline":
        try:
            result = process_environment_response_job(job_id)
        except Exception as exc:
            logger.error(
                "Labs inline dispatch failed job_id=%s failure_class=%s",
                job_id,
                type(exc).__name__,
            )
            _requeue_inline_retry(
                outbox_id,
                failure_code=type(exc).__name__,
            )
            return False
        if result.outcome == "retry":
            _requeue_inline_retry(outbox_id)
    return True


def dispatch_job(job_id: str) -> bool:
    """Dispatch one outbox row without falling back across execution modes."""
    if execution_mode() == "disabled":
        return False
    claimed = _claim_outbox(job_id)
    if claimed is None:
        return False
    return _dispatch_claim(*claimed)


def dispatch_pending_jobs(limit: int = DISPATCH_BATCH_SIZE) -> int:
    """Dispatch a bounded set of pending outbox rows."""
    if execution_mode() == "disabled":
        return 0
    dispatched = 0
    for _ in range(max(0, limit)):
        claimed = _claim_outbox()
        if claimed is None:
            break
        if _dispatch_claim(*claimed):
            dispatched += 1
    return dispatched


def notify_dispatcher() -> None:
    """Wake the periodic outbox reconciler."""
    _wake_event.set()


def _dispatcher_loop() -> None:
    while not _stop_event.is_set():
        try:
            from db import session as db_session

            with db_session.SessionLocal() as db:
                recover_interrupted_jobs(db)
            dispatch_pending_jobs()
        except Exception as exc:
            logger.error(
                "Labs dispatcher reconciliation failed failure_class=%s",
                type(exc).__name__,
            )
        _wake_event.wait(DISPATCH_INTERVAL_SEC)
        _wake_event.clear()


def start_dispatcher() -> None:
    """Start the lightweight outbox reconciliation thread."""
    global _dispatcher_thread
    validate_configuration()
    if execution_mode() == "disabled":
        logger.info("Labs dispatcher disabled by configuration")
        return
    if _dispatcher_thread is not None and _dispatcher_thread.is_alive():
        return
    _stop_event.clear()
    _wake_event.clear()
    _dispatcher_thread = threading.Thread(
        target=_dispatcher_loop,
        name="labs-outbox-dispatcher",
        daemon=True,
    )
    _dispatcher_thread.start()
    logger.info("Labs dispatcher started mode=%s", execution_mode())


def stop_dispatcher() -> None:
    """Stop the outbox reconciliation thread."""
    _stop_event.set()
    _wake_event.set()
    if _dispatcher_thread is not None:
        _dispatcher_thread.join(timeout=5)
    logger.info("Labs dispatcher stopped")
