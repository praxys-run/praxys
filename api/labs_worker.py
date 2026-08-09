"""One-message Azure Service Bus worker for isolated Labs analysis."""
from __future__ import annotations

import argparse
import logging
import os
from typing import Any
from uuid import UUID

from api.labs_service_bus import (
    azure_credential as _azure_credential,
    service_bus_namespace,
    service_bus_queue,
    validate_configuration,
)

logger = logging.getLogger(__name__)


def _configure_telemetry() -> None:
    if not os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(credential=_azure_credential())
    except Exception as exc:
        logger.error(
            "Labs worker telemetry initialization failed; continuing "
            "without export failure_class=%s",
            type(exc).__name__,
        )


def _message_body(message: Any) -> str:
    parts = []
    for part in message.body:
        parts.append(
            part
            if isinstance(part, bytes)
            else bytes(part)
        )
    return b"".join(parts).decode("ascii").strip()


def _initialize_database() -> None:
    from db.session import init_db

    init_db()


def _verify_database_connection() -> None:
    from db import session as db_session
    from api.labs_worker_permissions import verify_labs_worker_grants

    if db_session.SessionLocal is None:
        raise RuntimeError("Labs worker database session was not initialized")
    with db_session.SessionLocal() as db:
        verify_labs_worker_grants(db)


def startup_check() -> None:
    """Verify worker database startup without receiving a queue delivery."""
    _initialize_database()
    _verify_database_connection()
    logger.info("Labs worker startup check completed")


def process_environment_response_job(
    job_id: str,
    *,
    reclaim_processing: bool,
) -> Any:
    """Import the analysis runtime only after a broker delivery is locked."""
    from api.labs_environment import (
        process_environment_response_job as process_job,
    )

    return process_job(
        job_id,
        reclaim_processing=reclaim_processing,
    )


def settle_message(receiver: Any, message: Any) -> str:
    """Process and settle one received Service Bus message."""
    try:
        job_id = str(UUID(_message_body(message)))
    except (ValueError, UnicodeDecodeError, TypeError):
        receiver.dead_letter_message(
            message,
            reason="invalid_job_id",
            error_description="Message body must be one opaque UUID job id",
        )
        return "dead_lettered"

    try:
        result = process_environment_response_job(
            job_id,
            reclaim_processing=True,
        )
    except Exception as exc:
        logger.error(
            "Labs worker could not claim or persist job_id=%s; abandoning "
            "failure_class=%s",
            job_id,
            type(exc).__name__,
        )
        receiver.abandon_message(message)
        return "abandoned"
    if result.outcome == "retry":
        receiver.abandon_message(message)
        return "abandoned"
    if result.outcome in ("failed", "dead_lettered"):
        receiver.dead_letter_message(
            message,
            reason=result.failure_code or result.outcome,
            error_description="Labs analysis did not complete",
        )
        return "dead_lettered"
    receiver.complete_message(message)
    return "completed"


def run_once() -> bool:
    """Receive and settle at most one queue message."""
    from azure.servicebus import AutoLockRenewer, ServiceBusClient

    validate_configuration()
    with ServiceBusClient(
        fully_qualified_namespace=service_bus_namespace(),
        credential=_azure_credential(),
    ) as client:
        with client.get_queue_receiver(
            service_bus_queue(),
            prefetch_count=0,
            max_wait_time=20,
        ) as receiver:
            messages = receiver.receive_messages(
                max_message_count=1,
                max_wait_time=20,
            )
            if not messages:
                logger.info("Labs worker found no queue message")
                return False
            message = messages[0]
            renewer = AutoLockRenewer(max_lock_renewal_duration=1800)
            renewer.register(receiver, message)
            try:
                try:
                    _initialize_database()
                except Exception as exc:
                    logger.error(
                        "Labs worker database initialization failed; "
                        "abandoning failure_class=%s",
                        type(exc).__name__,
                    )
                    receiver.abandon_message(message)
                    return True
                settlement = settle_message(receiver, message)
                logger.info(
                    "Labs worker settled message as %s delivery_count=%s",
                    settlement,
                    getattr(message, "delivery_count", "unknown"),
                )
            finally:
                renewer.close()
    return True


def main(argv: list[str] | None = None) -> int:
    """Initialize the worker runtime and process one message."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--startup-check",
        action="store_true",
        help="Verify database initialization without receiving a queue message",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    os.environ["PRAXYS_SKIP_MIGRATIONS"] = "true"
    os.environ["PRAXYS_HIDE_SQL_PARAMETERS"] = "true"
    _configure_telemetry()
    if args.startup_check:
        try:
            startup_check()
        except Exception as exc:
            logger.error(
                "Labs worker startup check failed failure_class=%s",
                type(exc).__name__,
            )
            return 1
        return 0
    run_once()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
