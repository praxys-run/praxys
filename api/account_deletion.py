"""Account deletion helpers shared by self-service and admin routes."""
from __future__ import annotations

import logging
import glob
import os
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.models import (
    Activity,
    ActivitySample,
    ActivitySplit,
    AgentDecision,
    AgentOutcome,
    AiInsight,
    AiInsightFeedback,
    AppConfig,
    CacheRevision,
    DashboardCache,
    Feedback,
    FitnessData,
    Invitation,
    LabsDeletionTombstone,
    LabsExperimentEnrollment,
    LabsExperimentResult,
    PlanDelivery,
    PlanDeliveryAttempt,
    PlanRevision,
    PlanTargetCalendarSync,
    PlanTargetWorkout,
    RecoveryData,
    TrainingPlan,
    User,
    UserConfig,
    UserConnection,
    WaitlistSignup,
)
from db.cache_revision import lock_revision_writes
from db.plan_ledger import legacy_stryd_status_lock, lock_plan_writes
from db.session import begin_serialized_write

logger = logging.getLogger(__name__)

_ACCOUNT_DELETION_GUARD_KEY = 0x5072617879734445


def begin_active_admin_guard(db: Session) -> None:
    """Serialize the active-admin guard across workers and database backends."""
    begin_serialized_write(db)
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": _ACCOUNT_DELETION_GUARD_KEY},
        )


@dataclass(frozen=True)
class AccountDeletionResult:
    """Summary returned after a committed account deletion."""

    email: str
    deleted_user_ids: list[str]


def _delete_user_owned_rows(db: Session, user_id: str) -> None:
    """Delete a user's owned rows and detach every remaining reference to them.

    Rows keyed by a NOT-NULL ``user_id`` FK are the user's own data and are
    deleted outright. References that other, surviving rows hold to this user are
    cleared so nothing dangles once the ``users`` row is gone — PostgreSQL
    enforces these foreign keys (SQLite historically did not, which is how issue
    #366's orphaned ``invitations.used_by`` rows accrued):

    * ``invitations.created_by`` (NOT NULL) — the invitation can't outlive its
      required creator, so it is deleted; any ``waitlist_signups.invitation_id``
      pointing at it is detached first so that FK doesn't dangle.
    * ``invitations.used_by`` (nullable) — the invitation is kept as a record of
      the creator's action, but the reference is nulled AND the code deactivated
      so a now-ownerless code can't be re-claimed (a claim only checks
      ``used_by IS NULL``; see api/invitations.py).
    * ``app_config.updated_by`` (nullable) — the operator flag row is kept; only
      the "who last changed this" reference is nulled.
    """
    feedback_refs = [
        str(feedback_id)
        for (feedback_id,) in db.query(Feedback.id)
        .filter(Feedback.user_id == user_id)
        .with_for_update()
        .all()
    ]
    delivery_ids = [
        delivery_id
        for (delivery_id,) in db.query(PlanDelivery.id)
        .filter(PlanDelivery.user_id == user_id)
        .all()
    ]
    if delivery_ids:
        db.query(PlanDeliveryAttempt).filter(
            PlanDeliveryAttempt.delivery_id.in_(delivery_ids)
        ).delete(synchronize_session=False)

    for model in (
        ActivitySample,
        ActivitySplit,
        Activity,
        RecoveryData,
        FitnessData,
        TrainingPlan,
        PlanTargetWorkout,
        PlanTargetCalendarSync,
        PlanDelivery,
        PlanRevision,
        UserConnection,
        UserConfig,
        AiInsightFeedback,
        AiInsight,
        CacheRevision,
        DashboardCache,
        LabsExperimentResult,
        LabsExperimentEnrollment,
        LabsDeletionTombstone,
        Feedback,
    ):
        db.query(model).filter(model.user_id == user_id).delete(synchronize_session=False)

    if feedback_refs:
        decision_ids = [
            decision_id
            for (decision_id,) in db.query(AgentDecision.id)
            .filter(
                AgentDecision.subject_type == "feedback",
                AgentDecision.subject_ref.in_(feedback_refs),
            )
            .all()
        ]
        if decision_ids:
            db.query(AgentOutcome).filter(
                AgentOutcome.decision_id.in_(decision_ids)
            ).delete(synchronize_session=False)
            db.query(AgentDecision).filter(
                AgentDecision.id.in_(decision_ids)
            ).delete(synchronize_session=False)

    # Invitations this user created (created_by is NOT NULL, so it can't be
    # nulled). Detach any waitlist signups linked to them first so that FK
    # doesn't dangle, then delete the invitations.
    created_invitation_ids = [
        inv_id
        for (inv_id,) in db.query(Invitation.id)
        .filter(Invitation.created_by == user_id)
        .all()
    ]
    if created_invitation_ids:
        db.query(WaitlistSignup).filter(
            WaitlistSignup.invitation_id.in_(created_invitation_ids)
        ).update({WaitlistSignup.invitation_id: None}, synchronize_session=False)
        db.query(Invitation).filter(
            Invitation.id.in_(created_invitation_ids)
        ).delete(synchronize_session=False)

    # Invitations merely used by this user are preserved (they record who issued
    # the code) but detached and deactivated so the freed code can't be redeemed.
    db.query(Invitation).filter(Invitation.used_by == user_id).update(
        {Invitation.used_by: None, Invitation.is_active: False},
        synchronize_session=False,
    )

    # Operator config records who last toggled a flag; keep the row, drop the ref.
    db.query(AppConfig).filter(AppConfig.updated_by == user_id).update(
        {AppConfig.updated_by: None}, synchronize_session=False
    )


def _clear_tokenstore(user_id: str) -> None:
    """Best-effort legacy cleanup and plaintext-token blocking after deletion."""
    from api.routes.sync import clear_garmin_tokens

    try:
        clear_garmin_tokens(user_id)
    except OSError:
        logger.exception(
            "User %s deleted but Garmin legacy-token cleanup failed.",
            user_id,
        )


def _clear_legacy_plan_status(db: Session, user_id: str) -> None:
    """Remove pre-ledger Stryd status files and quarantine/import archives."""
    from api.routes import plan as plan_route

    lock_plan_writes(db, user_id)
    path = plan_route._stryd_push_status_path(user_id)
    try:
        with legacy_stryd_status_lock(
            os.path.dirname(path),
            user_id,
        ):
            for candidate in [path, *glob.glob(f"{path}.*")]:
                try:
                    os.unlink(candidate)
                except FileNotFoundError:
                    continue
                except OSError:
                    logger.exception(
                        "User %s deleted but legacy plan-status cleanup failed for %s.",
                        user_id,
                        candidate,
                    )
    finally:
        db.rollback()


def delete_user_account(
    db: Session,
    user_id: str,
    *,
    enforce_last_admin_guard: bool = True,
) -> AccountDeletionResult:
    """Hard-delete a user account plus all directly owned rows.

    The operation commits before touching legacy token paths so a filesystem
    cleanup issue cannot roll back the database deletion. A last-admin guard is
    enforced for self-service deletion and kept enabled for admin deletion as a
    defense-in-depth check.
    """
    begin_active_admin_guard(db)
    lock_revision_writes(db, user_id)
    user = (
        db.query(User)
        .populate_existing()
        .with_for_update()
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        db.rollback()
        raise HTTPException(404, "USER_NOT_FOUND")

    email = user.email
    if user.is_active:
        if enforce_last_admin_guard and user.is_superuser:
            admin_count = db.query(User).filter(
                User.is_superuser == True,  # noqa: E712
                User.is_active == True,  # noqa: E712
            ).count()
            if admin_count <= 1:
                db.rollback()
                raise HTTPException(400, "LAST_ADMIN_CANNOT_DELETE_ACCOUNT")

        user.is_active = False
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to mark account deleting for user %s", user_id)
            raise HTTPException(500, "ACCOUNT_DELETE_FAILED")

        begin_serialized_write(db)
        lock_revision_writes(db, user_id)
        user = (
            db.query(User)
            .populate_existing()
            .with_for_update()
            .filter(User.id == user_id)
            .first()
        )
        if user is None:
            db.rollback()
            raise HTTPException(404, "USER_NOT_FOUND")

    deleted_user_ids: list[str] = []
    demo_users = (
        db.query(User)
        .populate_existing()
        .with_for_update()
        .filter(User.demo_of == user_id)
        .all()
    )
    for demo_user in demo_users:
        _delete_user_owned_rows(db, demo_user.id)
        db.delete(demo_user)
        deleted_user_ids.append(demo_user.id)

    _delete_user_owned_rows(db, user_id)
    db.delete(user)
    deleted_user_ids.append(user_id)

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Account deletion failed for user %s", user_id)
        raise HTTPException(500, "ACCOUNT_DELETE_FAILED")

    for deleted_user_id in deleted_user_ids:
        _clear_tokenstore(deleted_user_id)
        _clear_legacy_plan_status(db, deleted_user_id)

    return AccountDeletionResult(email=email, deleted_user_ids=deleted_user_ids)
