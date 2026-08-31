"""Durable replay for external data left after account deletion."""
from __future__ import annotations

from datetime import datetime, timezone
import glob
import logging
import os
import re
from typing import Callable, Iterable
from uuid import uuid4

from sqlalchemy.orm import Session

from db.models import AccountDeletionCleanupObligation

logger = logging.getLogger(__name__)

GARMIN_TOKENS = "garmin_tokens"
LEGACY_PLAN_STATUS = "legacy_plan_status"
CLEANUP_KINDS = (GARMIN_TOKENS, LEGACY_PLAN_STATUS)
_SAFE_USER_ID = re.compile(r"^[A-Za-z0-9_-]{1,36}$")


class AccountDeletionCleanupError(RuntimeError):
    """One or more durable external cleanup obligations remain pending."""


def _now(value: datetime | None = None) -> datetime:
    timestamp = value or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).replace(tzinfo=None)


def record_cleanup_obligations(
    db: Session,
    user_ids: Iterable[str],
    *,
    now: datetime | None = None,
) -> None:
    """Stage the complete external-cleanup set in the deletion transaction."""
    requested_at = _now(now)
    for user_id in dict.fromkeys(str(value) for value in user_ids):
        if _SAFE_USER_ID.fullmatch(user_id) is None:
            raise AccountDeletionCleanupError("invalid_cleanup_locator")
        for cleanup_kind in CLEANUP_KINDS:
            db.add(
                AccountDeletionCleanupObligation(
                    id=str(uuid4()),
                    user_id=user_id,
                    cleanup_kind=cleanup_kind,
                    status="pending",
                    requested_at=requested_at,
                )
            )


def _mark_completed(
    db: Session,
    obligation: AccountDeletionCleanupObligation,
    *,
    completed_at: datetime,
) -> None:
    """Atomically complete a pending row and tolerate an exact lost race."""
    updated = (
        db.query(AccountDeletionCleanupObligation)
        .filter(
            AccountDeletionCleanupObligation.id == obligation.id,
            AccountDeletionCleanupObligation.user_id == obligation.user_id,
            AccountDeletionCleanupObligation.cleanup_kind
            == obligation.cleanup_kind,
            AccountDeletionCleanupObligation.status == "pending",
        )
        .update(
            {
                AccountDeletionCleanupObligation.status: "completed",
                AccountDeletionCleanupObligation.completed_at: completed_at,
            },
            synchronize_session=False,
        )
    )
    if updated == 1:
        db.commit()
        return
    db.rollback()
    current = (
        db.query(AccountDeletionCleanupObligation)
        .populate_existing()
        .filter(
            AccountDeletionCleanupObligation.id == obligation.id,
            AccountDeletionCleanupObligation.user_id == obligation.user_id,
            AccountDeletionCleanupObligation.cleanup_kind
            == obligation.cleanup_kind,
        )
        .one_or_none()
    )
    if (
        current is None
        or current.status != "completed"
        or current.completed_at is None
    ):
        raise AccountDeletionCleanupError("cleanup_completion_conflict")


def _cleanup_handlers() -> dict[str, Callable[[str], None]]:
    # Import lazily so startup and unit tests can initialize models without
    # importing provider clients.
    from api.account_deletion import (
        _clear_legacy_plan_status,
        _clear_tokenstore,
    )
    from db.session import SessionLocal

    def clear_legacy_plan_status(user_id: str) -> None:
        with SessionLocal() as db:
            _clear_legacy_plan_status(db, user_id)

    return {
        GARMIN_TOKENS: _clear_tokenstore,
        LEGACY_PLAN_STATUS: clear_legacy_plan_status,
    }


def _legacy_artifact_absent(user_id: str, cleanup_kind: str) -> bool:
    """Confirm the exact external locator is absent after its handler."""
    if cleanup_kind == GARMIN_TOKENS:
        from api.routes.sync import _garmin_token_root

        root = _garmin_token_root()
        for candidate_root in (root, root + ".migration"):
            candidate = os.path.normpath(
                os.path.join(candidate_root, user_id)
            )
            if (
                os.path.dirname(candidate) != candidate_root
                or os.path.lexists(candidate)
            ):
                return False
        return True
    if cleanup_kind == LEGACY_PLAN_STATUS:
        from api.routes import plan as plan_route

        path = plan_route._stryd_push_status_path(user_id)
        return not any(
            os.path.lexists(candidate)
            for candidate in (
                path,
                *glob.glob(f"{path}.*"),
            )
        )
    return False


def replay_cleanup_obligations(
    db: Session,
    *,
    user_ids: Iterable[str] | None = None,
    raise_on_failure: bool = False,
    handlers: dict[str, Callable[[str], None]] | None = None,
) -> int:
    """Replay pending rows idempotently; failures remain durable."""
    query = db.query(AccountDeletionCleanupObligation).filter(
        AccountDeletionCleanupObligation.status == "pending"
    )
    if user_ids is not None:
        selected = tuple(dict.fromkeys(str(value) for value in user_ids))
        if not selected:
            return 0
        query = query.filter(
            AccountDeletionCleanupObligation.user_id.in_(selected)
        )
    pending = query.order_by(
        AccountDeletionCleanupObligation.requested_at.asc(),
        AccountDeletionCleanupObligation.user_id.asc(),
        AccountDeletionCleanupObligation.cleanup_kind.asc(),
    ).all()
    if not pending:
        return 0
    cleanup_handlers = handlers or _cleanup_handlers()
    completed = 0
    failures = 0
    for obligation in pending:
        handler = cleanup_handlers.get(obligation.cleanup_kind)
        if handler is None:
            failures += 1
            logger.error(
                "Unknown account deletion cleanup kind %s",
                obligation.cleanup_kind,
            )
            continue
        try:
            from db.models import User

            if db.query(User.id).filter(
                User.id == obligation.user_id
            ).first() is not None:
                raise AccountDeletionCleanupError(
                    "cleanup_owner_present"
                )
            handler(obligation.user_id)
            if handlers is None and not _legacy_artifact_absent(
                obligation.user_id,
                obligation.cleanup_kind,
            ):
                raise AccountDeletionCleanupError(
                    "cleanup_not_confirmed"
                )
            _mark_completed(db, obligation, completed_at=_now())
            completed += 1
        except Exception:
            failures += 1
            db.rollback()
            logger.error(
                "Account deletion external cleanup remains pending: kind=%s",
                obligation.cleanup_kind,
            )
    if failures and raise_on_failure:
        raise AccountDeletionCleanupError(
            f"{failures} account deletion cleanup obligation(s) remain pending"
        )
    return completed


def pending_cleanup_exists(
    db: Session,
    *,
    user_ids: Iterable[str] | None = None,
) -> bool:
    query = db.query(AccountDeletionCleanupObligation.user_id).filter(
        AccountDeletionCleanupObligation.status == "pending"
    )
    if user_ids is not None:
        selected = tuple(dict.fromkeys(str(value) for value in user_ids))
        if not selected:
            return False
        query = query.filter(
            AccountDeletionCleanupObligation.user_id.in_(selected)
        )
    return query.first() is not None


def require_cleanup_owners_absent(db: Session) -> None:
    """Stop before filesystem migration if a pending locator is live."""
    from db.models import User

    conflict = db.query(AccountDeletionCleanupObligation.id).join(
        User,
        User.id == AccountDeletionCleanupObligation.user_id,
    ).filter(
        AccountDeletionCleanupObligation.status == "pending"
    ).first()
    if conflict is not None:
        raise AccountDeletionCleanupError("cleanup_owner_present")


def run_scheduled_cleanup() -> None:
    """Scheduler entry point: one failure never stops later retries."""
    from db.session import SessionLocal, init_db

    init_db()
    with SessionLocal() as db:
        garmin_pending = db.query(
            AccountDeletionCleanupObligation.user_id
        ).filter(
            AccountDeletionCleanupObligation.status == "pending",
            AccountDeletionCleanupObligation.cleanup_kind == GARMIN_TOKENS,
        ).first() is not None
        if garmin_pending:
            # Repair an interrupted legacy-root cutover before retrying a
            # per-user obligation. This path runs only while cleanup is due.
            from api.routes.sync import migrate_legacy_garmin_tokenstores

            require_cleanup_owners_absent(db)
            migrate_legacy_garmin_tokenstores()
        replay_cleanup_obligations(db)


def run_startup_cleanup() -> None:
    """Reconcile external cleanup before the API serves traffic."""
    from db.session import SessionLocal

    with SessionLocal() as db:
        require_cleanup_owners_absent(db)
    from api.routes.sync import migrate_legacy_garmin_tokenstores

    migrate_legacy_garmin_tokenstores()
    with SessionLocal() as db:
        replay_cleanup_obligations(db, raise_on_failure=True)
