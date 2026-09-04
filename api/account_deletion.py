"""Account deletion helpers shared by self-service and admin routes."""
from __future__ import annotations

import logging
import glob
import os
from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.models import (
    AdaptivePlan,
    AdaptivePlanGoalSnapshot,
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
    FeedbackPublicationAttempt,
    FeedbackPublicationOutbox,
    FitnessData,
    GoalBaselineAssessment,
    GoalBaselineConfirmation,
    GoalBaselineSnapshot,
    GoalBaselineTestRecord,
    Outdoor5KPlanGeneration,
    Road10KBaselineConfirmation,
    Road10KBaselineSnapshot,
    Road10KPlanGeneration,
    Road10KTrainingPatternSnapshot,
    Invitation,
    LabsAnalysisJob,
    LabsAnalysisOutbox,
    LabsDeletionTombstone,
    LabsExperimentEnrollment,
    LabsExperimentResult,
    McpAccessHandoff,
    McpAccessToken,
    PlanDelivery,
    PlanDeliveryAttempt,
    PlanProposal,
    PlanRevision,
    PlanTargetCalendarSync,
    PlanTargetWorkout,
    PersonalContextConsentReceipt,
    PersonalContextDeletionJob,
    PersonalContextItem,
    PersonalContextUseReceipt,
    RecoveryData,
    TrainingPlan,
    TermsAcceptanceReceipt,
    User,
    UserConfig,
    UserConnection,
    WaitlistSignup,
)
from api import feedback_storage
from db.account_lifecycle import (
    AccountLifecycleBusy,
    account_lifecycle_lease,
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


def _cancel_active_labs_work(
    db: Session,
    user_id: str,
) -> int:
    """Cancel queued or running Labs work before account cleanup begins."""
    jobs = (
        db.query(LabsAnalysisJob)
        .filter(
            LabsAnalysisJob.user_id == user_id,
            LabsAnalysisJob.status.in_(
                ("queued", "dispatched", "processing", "retrying")
            ),
        )
        .with_for_update()
        .all()
    )
    if not jobs:
        return 0
    now = datetime.utcnow()
    job_ids = [job.id for job in jobs]
    outboxes = (
        db.query(LabsAnalysisOutbox)
        .filter(LabsAnalysisOutbox.job_id.in_(job_ids))
        .with_for_update()
        .all()
    )
    for job in jobs:
        job.status = "cancelled"
        job.completed_at = now
        job.lease_expires_at = None
        job.updated_at = now
    for outbox in outboxes:
        outbox.status = "cancelled"
        outbox.lease_expires_at = None
        outbox.updated_at = now
    return len(jobs)


def _delete_user_owned_rows(
    db: Session,
    user_id: str,
    *,
    feedback_ids: list[int],
    publication_outboxes_by_feedback_id: dict[int, FeedbackPublicationOutbox],
    publication_attempts_by_outbox_id: dict[
        str,
        list[FeedbackPublicationAttempt],
    ],
) -> None:
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
    * ``feedback_publication_outbox.feedback_id`` (nullable) — private feedback
      is deleted, while marker/digest delivery evidence is detached and retained.
    """
    feedback_refs = [str(feedback_id) for feedback_id in feedback_ids]
    _detach_feedback_publication_evidence(
        db,
        sorted(
            (
                publication_outboxes_by_feedback_id[feedback_id]
                for feedback_id in feedback_ids
                if feedback_id in publication_outboxes_by_feedback_id
            ),
            key=lambda outbox: str(outbox.id),
        ),
        publication_attempts_by_outbox_id,
    )
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
    labs_jobs = (
        db.query(LabsAnalysisJob)
        .filter(LabsAnalysisJob.user_id == user_id)
        .with_for_update()
        .all()
    )
    labs_job_ids = [job.id for job in labs_jobs]
    if labs_job_ids:
        (
            db.query(LabsAnalysisOutbox)
            .filter(LabsAnalysisOutbox.job_id.in_(labs_job_ids))
            .with_for_update()
            .all()
        )
        db.query(LabsAnalysisOutbox).filter(
            LabsAnalysisOutbox.job_id.in_(labs_job_ids)
        ).delete(synchronize_session=False)
        db.query(LabsAnalysisJob).filter(
            LabsAnalysisJob.id.in_(labs_job_ids)
        ).delete(synchronize_session=False)

    for model in (
        McpAccessToken,
        McpAccessHandoff,
        PersonalContextUseReceipt,
        PersonalContextConsentReceipt,
        PersonalContextItem,
        PersonalContextDeletionJob,
        TermsAcceptanceReceipt,
    ):
        db.query(model).filter(
            model.user_id == user_id
        ).delete(synchronize_session=False)

    for model in (
        ActivitySample,
        ActivitySplit,
        Outdoor5KPlanGeneration,
        Road10KPlanGeneration,
        Road10KTrainingPatternSnapshot,
        Activity,
        RecoveryData,
        FitnessData,
        PlanProposal,
        AdaptivePlan,
        AdaptivePlanGoalSnapshot,
        TrainingPlan,
        PlanTargetWorkout,
        PlanTargetCalendarSync,
        PlanDelivery,
        PlanRevision,
        UserConnection,
        UserConfig,
        AiInsightFeedback,
        AiInsight,
        GoalBaselineAssessment,
        GoalBaselineConfirmation,
        GoalBaselineSnapshot,
        GoalBaselineTestRecord,
        Road10KBaselineConfirmation,
        Road10KBaselineSnapshot,
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


def _feedback_publication_outbox_lock_query(
    db: Session,
    user_ids: tuple[str, ...],
) -> object:
    """Build the stable account-deletion Outbox lock query."""
    query = (
        db.query(FeedbackPublicationOutbox)
        .populate_existing()
        .join(Feedback, Feedback.id == FeedbackPublicationOutbox.feedback_id)
        .filter(
            Feedback.user_id.in_(user_ids),
            FeedbackPublicationOutbox.feedback_id.isnot(None),
        )
        .order_by(FeedbackPublicationOutbox.id.asc())
    )
    if db.get_bind().dialect.name == "postgresql":
        return query.with_for_update(of=FeedbackPublicationOutbox)
    return query.with_for_update()


def _feedback_publication_attempt_lock_query(
    db: Session,
    outbox_ids: tuple[str, ...],
) -> object:
    """Build the stable mutable-A lock query for account deletion."""
    query = (
        db.query(FeedbackPublicationAttempt)
        .populate_existing()
        .filter(
            FeedbackPublicationAttempt.outbox_id.in_(outbox_ids),
            FeedbackPublicationAttempt.outcome == "in_flight",
        )
        .order_by(FeedbackPublicationAttempt.id.asc())
    )
    if db.get_bind().dialect.name == "postgresql":
        return query.with_for_update(of=FeedbackPublicationAttempt)
    return query.with_for_update()


def _account_feedback_lock_query(
    db: Session,
    user_ids: tuple[str, ...],
) -> object:
    """Build the stable exact-F lock query after O and A are owned."""
    query = (
        db.query(Feedback)
        .populate_existing()
        .filter(Feedback.user_id.in_(user_ids))
        .order_by(Feedback.id.asc())
    )
    if db.get_bind().dialect.name == "postgresql":
        return query.with_for_update(of=Feedback)
    return query.with_for_update()


def _lock_feedback_publication_evidence(
    db: Session,
    user_ids: tuple[str, ...],
) -> dict[int, FeedbackPublicationOutbox]:
    """Lock every attached publication row before any private Feedback row."""
    if not user_ids:
        return {}
    outboxes = _feedback_publication_outbox_lock_query(db, user_ids).all()
    return {
        int(outbox.feedback_id): outbox
        for outbox in outboxes
        if outbox.feedback_id is not None
    }


def _lock_feedback_publication_attempts(
    db: Session,
    outboxes: tuple[FeedbackPublicationOutbox, ...],
) -> dict[str, list[FeedbackPublicationAttempt]]:
    """Lock all mutable attempt rows after O and before any F lock."""
    if not outboxes:
        return {}
    attempts = _feedback_publication_attempt_lock_query(
        db,
        tuple(str(outbox.id) for outbox in outboxes),
    ).all()
    by_outbox_id: dict[str, list[FeedbackPublicationAttempt]] = {}
    for attempt in attempts:
        by_outbox_id.setdefault(str(attempt.outbox_id), []).append(attempt)
    return by_outbox_id


def _detach_feedback_publication_evidence(
    db: Session,
    outboxes: list[FeedbackPublicationOutbox],
    attempts_by_outbox_id: dict[str, list[FeedbackPublicationAttempt]],
) -> None:
    """Detach already-locked O/A evidence without reversing the global order."""
    now = datetime.utcnow()
    for outbox in outboxes:
        if outbox.state in ("sending", "reconciling"):
            outbox.delivery_evidence = "ambiguous"
            for attempt in attempts_by_outbox_id.get(str(outbox.id), []):
                attempt.outcome = "unknown"
                attempt.error_code = "account_deleted_during_send"
                attempt.finished_at = now
        if (
            outbox.delivery_evidence == "not_sent"
            and outbox.state in ("pending", "retry_wait", "held", "manual_review")
        ):
            outbox.state = "cancelled"
            outbox.last_error_code = "account_deleted_before_send"
        elif outbox.state == "sending":
            outbox.state = "reconciling"
            outbox.available_at = now
            outbox.last_error_code = "account_deleted_during_send"
        elif outbox.state == "reconciling":
            # Fence a concurrent or abandoned marker lookup. Reconciliation can
            # resume from the immutable marker and digest after the private row
            # is gone, but no send path may run again.
            outbox.available_at = now
            if not outbox.last_error_code:
                outbox.last_error_code = "account_deleted_after_unknown"
        elif outbox.delivery_evidence == "ambiguous":
            # Manual ambiguity (notably multiple exact marker matches) cannot
            # be relabelled as "before send" merely because private source data
            # is being erased. Preserve it for operator investigation.
            outbox.state = "manual_review"
            if not outbox.last_error_code:
                outbox.last_error_code = "account_deleted_after_ambiguity"
        outbox.lease_token = None
        outbox.lease_expires_at = None
        outbox.updated_at = now
        outbox.feedback_id = None


def _delete_feedback_images(rows: list[Feedback]) -> None:
    """Delete exact screenshot keys from already-locked private rows."""
    for feedback in rows:
        for key in feedback.image_keys or []:
            feedback_storage.delete_image(
                key,
                feedback_id=feedback.id,
                provenance=feedback.image_storage_provenance,
            )


def _clear_tokenstore(user_id: str) -> None:
    """Best-effort legacy cleanup and plaintext-token blocking after deletion."""
    from api.routes.sync import clear_garmin_tokens

    try:
        clear_garmin_tokens(user_id)
    except OSError:
        logger.error("Account deletion Garmin legacy-token cleanup failed")


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
                    logger.error(
                        "Account deletion legacy plan-status cleanup failed"
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
    try:
        with account_lifecycle_lease(user_id, timeout_seconds=60.0):
            return _delete_user_account_locked(
                db,
                user_id,
                enforce_last_admin_guard=enforce_last_admin_guard,
            )
    except AccountLifecycleBusy as exc:
        db.rollback()
        logger.warning("Account deletion lease busy")
        raise HTTPException(503, "ACCOUNT_DELETE_BUSY") from exc


def _delete_user_account_locked(
    db: Session,
    user_id: str,
    *,
    enforce_last_admin_guard: bool,
) -> AccountDeletionResult:
    """Delete an account while its lifecycle lease is held."""
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

    demo_user_ids = sorted(
        str(demo_id)
        for (demo_id,) in db.query(User.id)
        .filter(User.demo_of == user_id)
        .all()
    )
    demo_users: list[User] = []
    for demo_user_id in demo_user_ids:
        lock_revision_writes(db, demo_user_id)
        demo_user = (
            db.query(User)
            .populate_existing()
            .with_for_update()
            .filter(User.id == demo_user_id)
            .one()
        )
        demo_users.append(demo_user)
    from api.personal_context import (
        PersonalContextDeletionError,
        stage_account_deletion_manifests,
    )

    try:
        context_manifests = stage_account_deletion_manifests(
            db,
            [user_id, *demo_user_ids],
        )
    except PersonalContextDeletionError:
        db.rollback()
        logger.error("Account context deletion manifest staging failed")
        raise HTTPException(503, "ACCOUNT_DELETE_STORAGE_UNAVAILABLE")

    user.is_active = False
    _cancel_active_labs_work(db, user_id)
    for demo_user in demo_users:
        demo_user.is_active = False
        _cancel_active_labs_work(db, demo_user.id)
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.error("Account deletion deactivation commit failed")
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
        .order_by(User.id.asc())
        .all()
    )
    scoped_user_ids = tuple(
        sorted([user_id, *(str(demo.id) for demo in demo_users)])
    )
    publication_outboxes_by_feedback_id = _lock_feedback_publication_evidence(
        db,
        scoped_user_ids,
    )
    locked_publication_outboxes = tuple(
        sorted(
            publication_outboxes_by_feedback_id.values(),
            key=lambda outbox: str(outbox.id),
        )
    )
    publication_attempts_by_outbox_id = _lock_feedback_publication_attempts(
        db,
        locked_publication_outboxes,
    )
    feedback_rows = _account_feedback_lock_query(db, scoped_user_ids).all()
    feedback_ids_by_user: dict[str, list[int]] = {
        scoped_user_id: [] for scoped_user_id in scoped_user_ids
    }
    for feedback in feedback_rows:
        feedback_ids_by_user.setdefault(str(feedback.user_id), []).append(
            int(feedback.id)
        )
    try:
        _delete_feedback_images(feedback_rows)
    except feedback_storage.FeedbackStorageDeletionError:
        db.rollback()
        logger.error("Account feedback screenshot deletion failed")
        raise HTTPException(503, "ACCOUNT_DELETE_STORAGE_UNAVAILABLE")

    for demo_user in demo_users:
        _delete_user_owned_rows(
            db,
            demo_user.id,
            feedback_ids=feedback_ids_by_user.get(str(demo_user.id), []),
            publication_outboxes_by_feedback_id=publication_outboxes_by_feedback_id,
            publication_attempts_by_outbox_id=(
                publication_attempts_by_outbox_id
            ),
        )
        db.delete(demo_user)
        deleted_user_ids.append(demo_user.id)

    _delete_user_owned_rows(
        db,
        user_id,
        feedback_ids=feedback_ids_by_user.get(user_id, []),
        publication_outboxes_by_feedback_id=publication_outboxes_by_feedback_id,
        publication_attempts_by_outbox_id=publication_attempts_by_outbox_id,
    )
    db.delete(user)
    deleted_user_ids.append(user_id)

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.error("Account deletion final commit failed")
        raise HTTPException(500, "ACCOUNT_DELETE_FAILED")

    from api.personal_context import complete_account_deletion_manifests

    complete_account_deletion_manifests(context_manifests)
    for deleted_user_id in deleted_user_ids:
        _clear_tokenstore(deleted_user_id)
        _clear_legacy_plan_status(db, deleted_user_id)

    return AccountDeletionResult(email=email, deleted_user_ids=deleted_user_ids)
