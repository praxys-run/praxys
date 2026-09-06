"""Feedback endpoints — in-app bug reports / feature requests / general feedback.

POST   /api/feedback               — any authenticated user; stores + triages
POST   /api/me/feedback/status     — authenticated owner publication status
GET    /api/admin/feedback         — admin only; list submissions (status filter)
POST   /api/admin/feedback/sync    — admin only; sync status from linked issues
PATCH  /api/admin/feedback/{id}    — admin only; retry triage / reject / approve
PUT    /api/admin/feedback/{id}/agent-ready-adjudication
                                   — admin only; record readiness ground truth

The submit handler does the minimum synchronously (validate, persist, emit a
telemetry signal) and hands the slow work — AI rewrite + PII scrub + GitHub
issue creation — to a background task (:func:`api.feedback_triage.triage_and_publish`)
so the user gets an instant 200. See that module for the pipeline.
"""
from __future__ import annotations

import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from pydantic import BaseModel, Field, StrictBool, StrictInt
from sqlalchemy.orm import Session

from api import feedback_publication, feedback_storage, github_issues, telemetry
from api.auth import get_current_user_id
from api.feedback_triage import triage_and_wake_publication
from api.optional_processing import (
    FEEDBACK_PUBLICATION_CONSENT_VERSION,
    background_ai_authorized,
    feedback_has_publication_consent,
    feedback_publication_authorized,
)
from api.views import require_admin, utc_isoformat
from db.cache_revision import lock_revision_writes
from db.agent_loop import (
    latest_decision,
    latest_decisions_for_subjects,
    latest_outcomes_for_decisions,
    record_outcome,
)
from db.session import begin_serialized_write, get_db

if TYPE_CHECKING:
    from db.models import AgentDecision, AgentOutcome, Feedback

logger = logging.getLogger(__name__)

router = APIRouter()

_PUBLICATION_STATUSES = {
    "private",
    "queued",
    "published",
    "manual_required",
    "unknown",
    "unavailable",
}
_LEGACY_PUBLICATION_CONSENT_VERSION = "feedback-publication-v1"
PublicationConsentReceipt = Literal[
    "current",
    "legacy",
    "not_granted",
    "invalid",
]

# Lightweight anti-spam: cap submissions per user in a sliding window. The
# auth-rate-limit middleware guards the unauthenticated surface; this guards an
# authenticated user from flooding the triage pipeline (and our LLM/GitHub
# spend) by holding the submit button.
_MAX_PER_WINDOW = 5
_WINDOW = timedelta(minutes=5)
_AGENT_READY_ADJUDICATION_OUTCOME = "agent_ready_adjudicated"
_AGENT_READY_POSITIVE_REASON = "bounded_actionable_defect"
_AGENT_READY_NEGATIVE_REASONS = {
    "not_a_defect",
    "insufficient_detail",
    "needs_product_judgment",
    "sensitivity_or_privacy",
    "other",
}


@router.get("/me/feedback/{feedback_id}/image/{index}")
def get_own_feedback_image(
    feedback_id: int,
    index: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> Response:
    """Serve one private feedback image to its authenticated owner."""
    from db.models import Feedback

    row = (
        db.query(Feedback)
        .filter(
            Feedback.id == feedback_id,
            Feedback.user_id == user_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(404, "Feedback not found")
    keys = list(row.image_keys or [])
    if index < 0 or index >= len(keys):
        raise HTTPException(404, "Image not found")
    got = feedback_storage.load_image(
        keys[index],
        provenance=row.image_storage_provenance,
    )
    if got is None:
        raise HTTPException(404, "Image not found")
    data, content_type = got
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "private, no-store"},
    )


def _record_feedback_outcome(
    db: Session,
    feedback_id: int,
    *,
    outcome_type: str,
    source: str,
    payload: dict[str, Any],
    dedupe_key: str | None = None,
    observed_at: datetime | None = None,
) -> bool:
    """Append an outcome when the feedback row has a structured decision."""
    decision = latest_decision(
        db,
        loop="change",
        subject_type="feedback",
        subject_ref=str(feedback_id),
    )
    if decision is None:
        return False
    return (
        record_outcome(
            db,
            decision_id=decision.id,
            outcome_type=outcome_type,
            source=source,
            payload=payload,
            dedupe_key=dedupe_key,
            observed_at=observed_at,
        )
        is not None
    )


def _github_observed_at(value: str | None) -> datetime | None:
    """Parse a GitHub ISO timestamp into the database's naive UTC convention."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


class FeedbackRequest(BaseModel):
    """A single feedback submission."""

    kind: Literal["bug", "feature", "other"] = "other"
    message: str = Field(min_length=1, max_length=5000)
    # Free-form client diagnostic context (page, app_version, user_agent,
    # viewport, locale). Scrubbed to an allowlist before anything is published.
    context: dict[str, Any] | None = None
    locale: str = Field(default="", max_length=10)
    # Explicit grant for publishing this submission's scrubbed text to the
    # configured external issue tracker. False/missing remains private.
    external_publication_consent: StrictBool = False
    external_publication_consent_version: str = Field(
        default="",
        max_length=64,
    )
    # Optional screenshots (issue #337): base64 payloads (data-URL or raw). They
    # are validated, described + sensitivity-flagged by a vision model, and
    # stored privately — only a reference (blob key) is kept and the raw image
    # never reaches a public issue. Capped at MAX_IMAGE_COUNT.
    images: list[str] | None = Field(default=None, max_length=feedback_storage.MAX_IMAGE_COUNT)


class FeedbackStatusRequest(BaseModel):
    """Fixed-path owner lookup with a strict browser-safe integer body ID."""

    feedback_id: StrictInt = Field(gt=0, le=9_007_199_254_740_991)


def _decode_and_validate_images(images: Optional[list[str]]) -> list[bytes]:
    """Decode + validate base64 screenshots, raising HTTPException on any bad
    input. Returns the decoded bytes (possibly empty). The client validates
    too; this is the authoritative server-side backstop (issue #337).
    """
    if not images:
        return []
    if len(images) > feedback_storage.MAX_IMAGE_COUNT:
        raise HTTPException(400, detail="FEEDBACK_TOO_MANY_IMAGES")
    out: list[bytes] = []
    for raw in images:
        # Bound work before decoding: base64 is ~1.37x the raw size, so a
        # string well over 2x the byte cap can't be an in-cap image.
        if not isinstance(raw, str) or len(raw) > feedback_storage.MAX_IMAGE_BYTES * 2:
            raise HTTPException(413, detail="FEEDBACK_IMAGE_TOO_LARGE")
        data = feedback_storage.decode_base64_image(raw)
        if data is None:
            raise HTTPException(400, detail="FEEDBACK_IMAGE_DECODE_FAILED")
        if len(data) > feedback_storage.MAX_IMAGE_BYTES:
            raise HTTPException(413, detail="FEEDBACK_IMAGE_TOO_LARGE")
        if feedback_storage.sniff(data) is None:
            raise HTTPException(415, detail="FEEDBACK_IMAGE_UNSUPPORTED_TYPE")
        out.append(data)
    return out


def _safe_publication_result(row: Feedback) -> dict[str, Any]:
    """Serialize only a server-authoritative status and allowlisted issue URL."""
    status = (
        row.publication_status
        if row.publication_status in _PUBLICATION_STATUSES
        else "unknown"
    )
    issue_url = None
    if (
        status == "published"
        and row.github_issue_number is not None
        and github_issues.issue_url_allowed(
            row.github_issue_number, row.github_issue_url
        )
    ):
        issue_url = row.github_issue_url
    elif status == "published":
        status = "unknown"
    return {"status": status, "issue_url": issue_url}


def _publication_consent_receipt(row: Feedback) -> PublicationConsentReceipt:
    """Classify persisted receipt shape without exposing its raw fields."""
    if feedback_has_publication_consent(row):
        return "current"

    version = row.publication_consent_version
    consented_at = row.publication_consented_at
    if (
        version == _LEGACY_PUBLICATION_CONSENT_VERSION
        and consented_at is not None
    ):
        return "legacy"
    if version is None and consented_at is None:
        return "not_granted"
    return "invalid"


@router.get("/feedback/publication-readiness")
def feedback_publication_readiness(
    response: Response,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return user-bound, non-secret readiness for the optional checkbox."""
    response.headers["Cache-Control"] = "private, no-store"
    readiness = github_issues.publication_readiness()
    if readiness["effective"] and not feedback_publication_authorized(
        db,
        user_id=user_id,
        submission_authorized=True,
    ):
        return {"available": False, "reason": "auth_missing"}
    return {
        "available": bool(readiness["effective"]),
        "reason": readiness["reason"],
    }


@router.post("/feedback")
def submit_feedback(
    body: FeedbackRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """Record a feedback submission and schedule background triage."""
    from db.models import Feedback, User

    # Validate + decode screenshots up-front so a bad image is rejected before
    # we persist anything (issue #337).
    decoded_images = _decode_and_validate_images(body.images)
    if (
        body.external_publication_consent
        and body.external_publication_consent_version
        != FEEDBACK_PUBLICATION_CONSENT_VERSION
    ):
        raise HTTPException(
            409,
            detail="FEEDBACK_PUBLICATION_CONSENT_MISMATCH",
        )
    if (
        not body.external_publication_consent
        and "external_publication_consent_version" in body.model_fields_set
    ):
        raise HTTPException(
            409,
            detail="FEEDBACK_PUBLICATION_CONSENT_MISMATCH",
        )
    begin_serialized_write(db)
    lock_revision_writes(db, user_id)
    user = (
        db.query(User)
        .populate_existing()
        .with_for_update()
        .filter(User.id == user_id)
        .first()
    )
    if user is None or not user.is_active:
        db.rollback()
        raise HTTPException(409, detail="FEEDBACK_ACCOUNT_UNAVAILABLE")

    cutoff = datetime.utcnow() - _WINDOW
    recent = (
        db.query(Feedback)
        .filter(Feedback.user_id == user_id, Feedback.created_at >= cutoff)
        .count()
    )
    if recent >= _MAX_PER_WINDOW:
        db.rollback()
        raise HTTPException(429, detail="FEEDBACK_RATE_LIMITED")

    feedback_id: int | None = None
    keys: list[str] = []
    try:
        publication_granted = (
            body.external_publication_consent and not user.is_demo
        )
        if not body.external_publication_consent:
            initial_publication_status = "private"
        elif user.is_demo:
            initial_publication_status = "unavailable"
        elif not github_issues.is_configured():
            initial_publication_status = "unavailable"
        elif not background_ai_authorized(db, user_id=user_id):
            initial_publication_status = "manual_required"
        else:
            initial_publication_status = "queued"
        row = Feedback(
            user_id=user_id,
            kind=body.kind,
            message=body.message,
            context_json=body.context or None,
            locale=body.locale or None,
            publication_consent_version=(
                FEEDBACK_PUBLICATION_CONSENT_VERSION
                if publication_granted
                else None
            ),
            publication_consented_at=(
                datetime.utcnow()
                if publication_granted
                else None
            ),
            status="new",
            publication_status=initial_publication_status,
        )
        db.add(row)
        db.flush()
        feedback_id = int(row.id)
        storage_provenance = (
            feedback_storage.current_storage_provenance()
            if decoded_images
            else None
        )
        # Commit deterministic deletion locators before external storage I/O.
        # If the namespace itself cannot be identified, ``store_image`` is
        # guaranteed to reject before any external write. Do not persist a
        # locator that can never correspond to stored bytes and would later
        # block account deletion; the text feedback remains available.
        keys = (
            [
                feedback_storage.image_storage_key(
                    data,
                    feedback_id=feedback_id,
                    index=i,
                )
                for i, data in enumerate(decoded_images)
            ]
            if storage_provenance is not None
            else []
        )
        if decoded_images and storage_provenance is None:
            logger.warning(
                "feedback image attachment skipped because storage "
                "provenance is unavailable"
            )
        row.image_keys = keys or None
        row.image_storage_provenance = (
            storage_provenance if keys else None
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.error("feedback save failed")
        raise HTTPException(500, detail="FEEDBACK_SAVE_FAILED")

    if keys:
        # Reacquire the user write lock so deletion either wins before upload
        # or waits until every persisted locator has been attempted.
        begin_serialized_write(db)
        lock_revision_writes(db, user_id)
        user = (
            db.query(User)
            .populate_existing()
            .with_for_update()
            .filter(User.id == user_id)
            .first()
        )
        row = (
            db.query(Feedback)
            .populate_existing()
            .with_for_update()
            .filter(
                Feedback.id == feedback_id,
                Feedback.user_id == user_id,
            )
            .first()
        )
        if user is None or not user.is_active or row is None:
            db.rollback()
            raise HTTPException(409, detail="FEEDBACK_ACCOUNT_UNAVAILABLE")

        for i, (data, expected_key) in enumerate(zip(decoded_images, keys)):
            stored_key = feedback_storage.store_image(
                data,
                feedback_id=feedback_id,
                index=i,
                provenance=row.image_storage_provenance,
            )
            if stored_key != expected_key:
                logger.error(
                    "feedback image upload key verification failed",
                )
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.error(
                "feedback image upload finalization failed",
            )
            raise HTTPException(
                503,
                detail="FEEDBACK_IMAGE_FINALIZE_FAILED",
            )

    telemetry.record_feedback(kind=body.kind, status="new")
    background_tasks.add_task(triage_and_wake_publication, feedback_id)
    logger.info("feedback submitted: kind=%s", body.kind)
    return {
        "ok": True,
        "id": feedback_id,
        "status": "received",
        "publication": _safe_publication_result(row),
    }


@router.post("/me/feedback/status")
def get_own_feedback_status(
    body: FeedbackStatusRequest,
    response: Response,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return the current safe publication result for one owned submission."""
    from db.models import Feedback

    response.headers["Cache-Control"] = "private, no-store"
    feedback_id = body.feedback_id
    row = (
        db.query(Feedback)
        .filter(Feedback.id == feedback_id, Feedback.user_id == user_id)
        .first()
    )
    if row is None:
        raise HTTPException(404, "Feedback not found")
    return {"id": row.id, "publication": _safe_publication_result(row)}


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


def _serialize_agent_readiness(
    decision: AgentDecision | None,
    adjudication: AgentOutcome | None,
) -> dict | None:
    """Return privacy-safe decision and human-ground-truth metadata."""
    if decision is None:
        return None
    output = decision.output_json or {}
    challenger = output.get("challenger")
    challenger_view = None
    if isinstance(challenger, dict):
        challenger_view = {
            "prompt_version": challenger.get("prompt_version"),
            "prompt_hash": challenger.get("prompt_hash"),
            "model": challenger.get("model"),
            "available": bool(challenger.get("available")),
            "kind": challenger.get("kind"),
            "agent_eligible": challenger.get("agent_eligible"),
            "candidate": challenger.get("agent_ready_candidate"),
            "reason": challenger.get("agent_ready_reason"),
        }

    adjudication_view = None
    if adjudication is not None:
        payload = adjudication.payload_json or {}
        adjudication_view = {
            "expected": payload.get("expected"),
            "reason": payload.get("reason"),
            "label_sync": payload.get("label_sync"),
            "observed_at": utc_isoformat(adjudication.observed_at),
        }

    return {
        "decision_id": decision.id,
        "policy_name": decision.policy_name,
        "policy_version": decision.policy_version,
        "prompt_version": output.get("active_prompt_version"),
        "prompt_hash": decision.prompt_version,
        "model": decision.model,
        "mode": decision.mode,
        "kind": output.get("kind"),
        "agent_eligible": output.get("agent_eligible"),
        "candidate": output.get("agent_ready_candidate"),
        "applied": output.get("agent_ready_applied"),
        "reason": output.get("agent_ready_reason"),
        "challenger": challenger_view,
        "adjudication": adjudication_view,
        "created_at": utc_isoformat(decision.created_at),
    }


def _serialize_admin(
    row: Feedback,
    *,
    decision: AgentDecision | None = None,
    adjudication: AgentOutcome | None = None,
) -> dict:
    """Full serialization for the Admin view — includes the raw message so an
    admin can see exactly what was reported, alongside the scrubbed output."""
    return {
        "id": row.id,
        "user_id": row.user_id,
        "kind": row.kind,
        "message": row.message,
        "context": row.context_json or {},
        "locale": row.locale,
        "status": row.status,
        "ai_title": row.ai_title,
        "ai_body": row.ai_body,
        "ai_labels": row.ai_labels or [],
        "publication_review_token": (
            feedback_publication.publication_review_token(row)
        ),
        "priority": row.priority,
        "github_issue_number": row.github_issue_number,
        "github_issue_url": _safe_publication_result(row)["issue_url"],
        "publication_status": _safe_publication_result(row)["status"],
        "error": row.error,
        "external_publication_consent": feedback_has_publication_consent(row),
        "publication_consent_receipt": _publication_consent_receipt(row),
        # Screenshot attachment (issue #337): count + scrubbed vision outputs.
        # The raw image is served only via the admin image endpoint below.
        "image_count": len(row.image_keys or []),
        "image_description": row.image_description,
        "image_sensitive": row.image_sensitive,
        "agent_readiness": _serialize_agent_readiness(
            decision,
            adjudication,
        ),
        "created_at": utc_isoformat(row.created_at),
        "updated_at": utc_isoformat(row.updated_at),
    }


@router.get("/admin/feedback")
def list_feedback(
    status: Optional[str] = None,
    limit: int = 100,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[dict]:
    """List feedback submissions, newest first. Admin only."""
    require_admin(user_id, db)
    from db.models import Feedback

    q = db.query(Feedback)
    if status == "active":
        # Default admin view: in-flight tickets only — hide the terminal
        # resolved/rejected rows so the actionable ones aren't crowded out.
        q = q.filter(Feedback.status.notin_(("resolved", "rejected")))
    elif status:
        q = q.filter(Feedback.status == status)
    rows = q.order_by(Feedback.created_at.desc()).limit(min(max(limit, 1), 500)).all()
    decisions = latest_decisions_for_subjects(
        db,
        loop="change",
        subject_type="feedback",
        subject_refs=(str(row.id) for row in rows),
    )
    adjudications = latest_outcomes_for_decisions(
        db,
        decision_ids=(decision.id for decision in decisions.values()),
        outcome_types=(_AGENT_READY_ADJUDICATION_OUTCOME,),
    )
    return [
        _serialize_admin(
            row,
            decision=decisions.get(str(row.id)),
            adjudication=(
                adjudications.get(decisions[str(row.id)].id)
                if str(row.id) in decisions
                else None
            ),
        )
        for row in rows
    ]


@router.get("/admin/feedback/summary")
def feedback_summary(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """Counts by status for the admin notification badge. Admin only.

    ``actionable`` = needs_review + failed — the rows an admin should look at.
    Kept cheap (a single grouped count) so the sidebar can poll it.
    """
    require_admin(user_id, db)
    from sqlalchemy import func

    from db.models import Feedback

    rows = db.query(Feedback.status, func.count(Feedback.id)).group_by(Feedback.status).all()
    counts = {status: int(n) for status, n in rows}
    needs_review = counts.get("needs_review", 0)
    failed = counts.get("failed", 0)
    return {
        "needs_review": needs_review,
        "failed": failed,
        "new": counts.get("new", 0),
        "actionable": needs_review + failed,
        "total": sum(counts.values()),
    }


@router.get("/admin/feedback/publication-queue")
def feedback_publication_queue(
    response: Response,
    limit: int = 100,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return readiness and metadata-only durable publication state."""
    require_admin(user_id, db)
    from db.models import Feedback, FeedbackPublicationOutbox

    response.headers["Cache-Control"] = "private, no-store"
    rows = (
        db.query(FeedbackPublicationOutbox, Feedback)
        .outerjoin(
            Feedback, Feedback.id == FeedbackPublicationOutbox.feedback_id
        )
        .order_by(FeedbackPublicationOutbox.created_at.desc())
        .limit(min(max(limit, 1), 500))
        .all()
    )

    def _status(
        outbox: FeedbackPublicationOutbox,
        feedback: Feedback | None,
    ) -> str:
        if feedback is not None:
            return feedback.publication_status
        if outbox.state == "published":
            return "published"
        if outbox.state in ("sending", "reconciling"):
            return "unknown"
        if outbox.state in ("pending", "retry_wait"):
            return "queued"
        if outbox.state == "manual_review":
            return "manual_required"
        return "private" if outbox.state == "cancelled" else "unavailable"

    return {
        "readiness": github_issues.publication_readiness(),
        "items": [
            {
                "id": feedback.id if feedback is not None else None,
                "detached": feedback is None,
                "created_at": utc_isoformat(outbox.created_at),
                "status": _status(outbox, feedback),
                "outbox_state": outbox.state,
                "consent_valid": (
                    feedback is not None
                    and feedback_has_publication_consent(feedback)
                    and outbox.consent_version
                    == FEEDBACK_PUBLICATION_CONSENT_VERSION
                ),
                "issue_link_present": bool(
                    outbox.github_issue_number
                    and github_issues.issue_url_allowed(
                        outbox.github_issue_number,
                        outbox.github_issue_url,
                    )
                ),
                "triage_output_present": bool(
                    feedback is not None
                    and feedback.ai_title
                    and feedback.ai_body
                ),
                "attempt_count": outbox.attempt_count,
                "reconcile_count": outbox.reconcile_count,
                "delivery_evidence": outbox.delivery_evidence,
                "error_code": outbox.last_error_code,
            }
            for outbox, feedback in rows
        ],
    }


@router.post("/admin/feedback/sync")
def sync_feedback_status(
    limit: int = 200,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """Reconcile ticket status with each linked GitHub issue. Admin only.

    A ticket filed as a GitHub issue tracks that issue's lifecycle: when the
    issue is closed the row flips to ``resolved``; if it's reopened the row
    flips back to ``issue_created``. Only rows that already have a linked issue
    and sit in one of those two states are checked — triage-side statuses
    (new / needs_review / failed / rejected) are never touched.

    Privacy: read-only against GitHub, fetching only issue state, labels, and
    closing-PR state — no ticket/PR text, comments, commits, or reviews. A no-op
    (``configured: false``) when GitHub is unset.
    """
    require_admin(user_id, db)
    from api import github_issues
    from db.models import Feedback

    if not github_issues.is_configured():
        return {
            "configured": False,
            "checked": 0,
            "updated": 0,
            "repository_mismatches": 0,
        }

    rows = (
        db.query(Feedback)
        .filter(
            Feedback.github_issue_number.isnot(None),
            Feedback.status.in_(("issue_created", "resolved")),
        )
        .order_by(Feedback.updated_at.desc())
        .limit(min(max(limit, 1), 500))
        .all()
    )
    checked = updated = repository_mismatches = 0
    changed = False
    for row in rows:
        if not github_issues.issue_matches_configured_repo(
            row.github_issue_number,
            row.github_issue_url,
        ):
            repository_mismatches += 1
            logger.warning(
                "feedback sync skipped linked issue: stored repository "
                "metadata mismatch"
            )
            continue
        outcome = github_issues.get_issue_outcome(row.github_issue_number)
        if outcome is None:
            # Unreadable (deleted / transferred / transient error) — leave as-is.
            continue
        checked += 1
        new_status = (
            "resolved" if outcome["state"] == "closed" else "issue_created"
        )
        if new_status != row.status:
            prior_status = row.status
            row.status = new_status
            updated += 1
            changed = True
            changed = _record_feedback_outcome(
                db,
                row.id,
                outcome_type=(
                    "github_issue_closed"
                    if new_status == "resolved"
                    else "github_issue_reopened"
                ),
                source="github",
                payload={
                    "issue_number": row.github_issue_number,
                    "state": outcome["state"],
                    "state_reason": outcome["state_reason"],
                    "prior_status": prior_status,
                    "status": new_status,
                    "closed_at": outcome["closed_at"],
                    "updated_at": outcome["updated_at"],
                },
                dedupe_key=(
                    f"issue:{row.github_issue_number}:{outcome['state']}:"
                    f"{outcome['updated_at'] or outcome['closed_at'] or 'unknown'}"
                ),
                observed_at=_github_observed_at(
                    outcome["closed_at"] or outcome["updated_at"]
                ),
            ) or changed

        decision = latest_decision(
            db,
            loop="change",
            subject_type="feedback",
            subject_ref=str(row.id),
        )
        if (
            decision is not None
            and outcome["agent_ready"]
            and not bool((decision.output_json or {}).get("agent_ready_applied"))
        ):
            changed = _record_feedback_outcome(
                db,
                row.id,
                outcome_type="external_agent_ready",
                source="github",
                payload={"issue_number": row.github_issue_number},
                dedupe_key=f"issue:{row.github_issue_number}",
            ) or changed

        for pull in outcome["closing_pull_requests"]:
            pull_type = (
                "github_pull_merged"
                if pull["merged"]
                else (
                    "github_pull_closed"
                    if pull["state"] == "closed"
                    else "github_pull_open"
                )
            )
            if pull["merged"]:
                event_key = (
                    f"pull:{pull['number']}:merged:"
                    f"{pull['merged_at'] or 'unknown'}"
                )
                event_time = pull["merged_at"]
            elif pull["state"] == "closed":
                event_key = (
                    f"pull:{pull['number']}:closed:"
                    f"{pull['closed_at'] or 'unknown'}"
                )
                event_time = pull["closed_at"]
            else:
                event_key = (
                    f"pull:{pull['number']}:open:draft:{pull['is_draft']}"
                )
                event_time = pull["updated_at"]
            changed = _record_feedback_outcome(
                db,
                row.id,
                outcome_type=pull_type,
                source="github",
                payload={
                    "pull_number": pull["number"],
                    "state": pull["state"],
                    "is_draft": pull["is_draft"],
                    "merged": pull["merged"],
                    "updated_at": pull["updated_at"],
                    "merged_at": pull["merged_at"],
                    "closed_at": pull["closed_at"],
                    "url": pull["url"],
                },
                dedupe_key=event_key,
                observed_at=_github_observed_at(event_time),
            ) or changed
    if changed:
        db.commit()
    return {
        "configured": True,
        "checked": checked,
        "updated": updated,
        "repository_mismatches": repository_mismatches,
    }


@router.get("/admin/feedback/{feedback_id}/image/{index}")
def get_feedback_image(
    feedback_id: int,
    index: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> Response:
    """Serve one attached screenshot (raw bytes). Admin only, never cached.

    The image is private — deliberately NOT exposed on any public issue; admins
    view it here alongside the scrubbed report. Returns 404 when the row, index,
    or stored object is missing.
    """
    require_admin(user_id, db)
    from db.models import Feedback

    row = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if row is None:
        raise HTTPException(404, "Feedback not found")
    keys = list(row.image_keys or [])
    if index < 0 or index >= len(keys):
        raise HTTPException(404, "Image not found")
    got = feedback_storage.load_image(
        keys[index],
        provenance=row.image_storage_provenance,
    )
    if got is None:
        raise HTTPException(404, "Image not found")
    data, content_type = got
    # private, no-store: an admin's own browser may hold it; shared caches must not.
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "private, no-store"},
    )


class FeedbackAction(BaseModel):
    """Admin action on a feedback row."""

    action: Literal["retry", "reject", "approve"]
    review_token: str | None = Field(
        default=None,
        min_length=71,
        max_length=71,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )


class AgentReadyAdjudication(BaseModel):
    """Maintainer ground truth for one agent-ready decision."""

    decision_id: str = Field(min_length=1, max_length=64)
    expected: bool
    reason: Literal[
        "bounded_actionable_defect",
        "not_a_defect",
        "insufficient_detail",
        "needs_product_judgment",
        "sensitivity_or_privacy",
        "other",
    ]


@router.put("/admin/feedback/{feedback_id}/agent-ready-adjudication")
def adjudicate_agent_readiness(
    feedback_id: int,
    payload: AgentReadyAdjudication,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """Record readiness ground truth and synchronize the GitHub trigger label."""
    require_admin(user_id, db)
    from api import github_issues
    from db.models import Feedback

    row = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if row is None:
        raise HTTPException(404, "Feedback not found")
    decision = latest_decision(
        db,
        loop="change",
        subject_type="feedback",
        subject_ref=str(row.id),
    )
    if decision is None:
        raise HTTPException(409, "Feedback has no agent-ready decision")
    if decision.id != payload.decision_id:
        raise HTTPException(
            409,
            "Agent-ready decision changed; refresh before adjudicating",
        )
    if payload.expected and payload.reason != _AGENT_READY_POSITIVE_REASON:
        raise HTTPException(
            422,
            "A positive adjudication requires bounded_actionable_defect",
        )
    if not payload.expected and payload.reason not in _AGENT_READY_NEGATIVE_REASONS:
        raise HTTPException(
            422,
            "A negative adjudication requires a rejection reason",
        )

    label_sync = "not_linked"
    if row.github_issue_number is not None:
        if not github_issues.is_configured():
            label_sync = "github_unavailable"
        elif not github_issues.issue_matches_configured_repo(
            row.github_issue_number,
            row.github_issue_url,
        ):
            label_sync = "repository_mismatch"
        elif payload.expected:
            issue_state = github_issues.get_issue_state(
                row.github_issue_number
            )
            if issue_state is None:
                label_sync = "failed"
            elif issue_state["state"] != "open":
                label_sync = "issue_not_open"
            else:
                label_sync = (
                    "synced"
                    if github_issues.set_issue_label(
                        row.github_issue_number,
                        "agent-ready",
                        present=True,
                    )
                    else "failed"
                )
        else:
            label_sync = (
                "synced"
                if github_issues.set_issue_label(
                    row.github_issue_number,
                    "agent-ready",
                    present=False,
                )
                else "failed"
            )

    output = decision.output_json or {}
    challenger = output.get("challenger")
    challenger_candidate = (
        challenger.get("agent_ready_candidate")
        if isinstance(challenger, dict)
        else None
    )
    outcome = record_outcome(
        db,
        decision_id=decision.id,
        outcome_type=_AGENT_READY_ADJUDICATION_OUTCOME,
        source="admin",
        payload={
            "expected": payload.expected,
            "reason": payload.reason,
            "issue_number": row.github_issue_number,
            "active_candidate": output.get("agent_ready_candidate"),
            "challenger_candidate": challenger_candidate,
            "label_sync": label_sync,
        },
    )
    db.commit()
    return {
        "recorded": True,
        "expected": payload.expected,
        "reason": payload.reason,
        "label_sync": label_sync,
        "agent_readiness": _serialize_agent_readiness(decision, outcome),
    }


@router.patch("/admin/feedback/{feedback_id}")
def update_feedback(
    feedback_id: int,
    payload: FeedbackAction,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """Retry triage (re-publish) or reject a feedback row. Admin only."""
    require_admin(user_id, db)

    # Admin review competes with background workers and other submissions.
    # Upgrade SQLite to its serialized writer transaction before the row read;
    # PostgreSQL uses row locks plus enqueue's submitter lock.
    dialect_name = db.get_bind().dialect.name
    if dialect_name == "sqlite":
        db.rollback()
        begin_serialized_write(db)

    owner_id = feedback_publication.feedback_owner_id(db, feedback_id)
    if owner_id is None:
        db.rollback()
        raise HTTPException(404, "Feedback not found")
    owner = feedback_publication.lock_feedback_user(db, owner_id)
    if owner is None or not owner.is_active:
        db.rollback()
        raise HTTPException(409, "Feedback account is unavailable")

    outbox = None
    if payload.action == "reject":
        # U serializes every creator/admin path for this account. Lock the
        # existing O next, then F; no post-F O recheck is safe or necessary.
        outbox = feedback_publication.lock_feedback_outbox(db, feedback_id)
        if outbox is not None and (
            outbox.state in ("sending", "reconciling")
            or outbox.delivery_evidence != "not_sent"
        ):
            db.rollback()
            raise HTTPException(
                409,
                "Publication outcome is unresolved; reconcile before rejecting",
            )

    row = feedback_publication.lock_feedback(db, feedback_id)
    if not row:
        db.rollback()
        raise HTTPException(404, "Feedback not found")
    if str(row.user_id) != owner_id:
        db.rollback()
        raise HTTPException(409, "Feedback account changed")

    if payload.action == "reject":
        if outbox is not None and outbox.state in (
            "pending",
            "retry_wait",
            "held",
            "manual_review",
        ) and outbox.delivery_evidence == "not_sent":
            outbox.state = "cancelled"
            outbox.lease_token = None
            outbox.lease_expires_at = None
        row.status = "rejected"
        if row.publication_status != "published":
            row.publication_status = "private"
        row.error = None
        _record_feedback_outcome(
            db,
            row.id,
            outcome_type="human_rejected",
            source="admin",
            payload={"status": row.status},
        )
        db.commit()
        return _serialize_admin(row)

    if payload.action == "approve":
        # Human review may release only an already-consented safe draft into the
        # durable outbox. Admin authority never substitutes for v2 consent and
        # never calls GitHub directly.
        if row.github_issue_number is not None:
            raise HTTPException(409, "Already published to GitHub")
        if not row.ai_title or not row.ai_body:
            raise HTTPException(409, "Nothing to publish yet — run triage first")
        current_review_token = feedback_publication.publication_review_token(row)
        if (
            payload.review_token is None
            or current_review_token is None
            or not hmac.compare_digest(payload.review_token, current_review_token)
        ):
            db.rollback()
            raise HTTPException(
                409,
                "Feedback changed; review the current public draft before approving",
            )
        if (
            not github_issues.is_configured()
            or not feedback_publication_authorized(
                db,
                user_id=row.user_id,
                submission_authorized=(
                    row.status == "needs_review"
                    and feedback_has_publication_consent(row)
                ),
            )
        ):
            raise HTTPException(
                400,
                "Feedback publication is unavailable or unauthorized",
            )
        outbox = feedback_publication.enqueue_publication(
            db,
            row.id,
            locked_user=owner,
            locked_feedback=row,
            human_review_approved=True,
        )
        if outbox is None:
            db.commit()
            raise HTTPException(
                409,
                "Feedback could not enter the publication queue",
            )
        if (
            outbox.feedback_id != row.id
            or outbox.state not in ("pending", "retry_wait")
            or row.publication_status != "queued"
        ):
            db.rollback()
            raise HTTPException(
                409,
                "Publication outcome is unresolved; reconcile before approving",
            )
        row.status = "triaged"
        _record_feedback_outcome(
            db,
            row.id,
            outcome_type="human_approved_for_publication_queue",
            source="admin",
            payload={"status": row.status},
        )
        db.commit()
        background_tasks.add_task(
            feedback_publication.safe_wake_publication_queue,
            limit=1,
        )
        return _serialize_admin(row)

    # retry: reset to a re-triageable state and re-schedule. Guarded on a linked
    # issue (issue_created OR resolved) so an already-filed row isn't double-
    # filed — reopening a resolved ticket goes through GitHub + Sync instead.
    if row.github_issue_number is not None:
        raise HTTPException(409, "Already published to GitHub")
    row.status = "new"
    row.error = None
    _record_feedback_outcome(
        db,
        row.id,
        outcome_type="human_retry",
        source="admin",
        payload={"status": row.status},
    )
    db.commit()
    background_tasks.add_task(triage_and_wake_publication, row.id)
    return _serialize_admin(row)
