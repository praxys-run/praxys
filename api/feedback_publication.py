"""Consent-bound, durable publication of scrubbed feedback to GitHub.

The outbox and attempt tables contain delivery metadata only. Publication
content remains in the private ``feedback`` row and is reconstructed,
re-scrubbed, and digest-checked immediately before a single external POST.
Ambiguous results enter reconciliation and are never blindly re-sent.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_
from sqlalchemy.orm import Session

from api import feedback_prompt, feedback_scrub, github_issues, telemetry
from api.optional_processing import (
    FEEDBACK_PUBLICATION_CONSENT_VERSION,
    feedback_has_publication_consent,
    feedback_publication_authorized,
)
from db.session import begin_serialized_write

logger = logging.getLogger(__name__)

MARKER_VERSION = "v2"
LEASE_SECONDS = 120
RETRY_DELAY_SECONDS = 60
RECONCILE_DELAY_SECONDS = 300
MAX_SEND_ATTEMPTS = 3
QUEUE_AGE_ALERT_SECONDS = 15 * 60
UNKNOWN_AGE_ALERT_SECONDS = 30 * 60
_SAFE_CODE = re.compile(r"[^a-z0-9_]+")
_LEGACY_SCREENSHOT_SECTION = re.compile(
    r"^[ \t]{0,3}#{1,6}[ \t]+screenshot(?:[ \t]+context)?[ \t]*\r?$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class PublicationPayload:
    """Ephemeral, twice-scrubbed GitHub payload and its canonical digest."""

    title: str
    body: str
    labels: tuple[str, ...]
    assignees: tuple[str, ...]
    marker: str
    digest: str
    public_content_sha256: str


class PublicationPayloadBlocked(ValueError):
    """Raised when private source content is unsafe or no longer canonical."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def generate_publication_id() -> str:
    """Return a public marker id with 128 bits from the OS CSPRNG."""
    return secrets.token_hex(16)


def _bounded_code(value: str | None, default: str) -> str:
    normalized = _SAFE_CODE.sub("_", (value or default).strip().lower())
    return (normalized.strip("_") or default)[:80]


def _with_entity_lock(db: Session, query, entity: object):
    """Apply an exact PostgreSQL entity lock while preserving SQLite behavior."""
    if db.get_bind().dialect.name == "postgresql":
        return query.with_for_update(of=entity)
    return query.with_for_update()


def feedback_owner_id(db: Session, feedback_id: int) -> str | None:
    """Resolve ownership without taking F so callers can enter through U."""
    from db.models import Feedback

    owner_id = (
        db.query(Feedback.user_id)
        .filter(Feedback.id == feedback_id)
        .scalar()
    )
    return str(owner_id) if owner_id is not None else None


def lock_feedback_user(db: Session, user_id: str):
    """Lock one owner by primary key, then let the caller validate activity."""
    from db.models import User

    query = (
        db.query(User)
        .populate_existing()
        .filter(User.id == user_id)
        .order_by(User.id.asc())
    )
    return _with_entity_lock(db, query, User).first()


def _feedback_lock_query(db: Session, feedback_ids: tuple[int, ...]):
    """Build a stable exact-F lock query for one or more rows."""
    from db.models import Feedback

    query = (
        db.query(Feedback)
        .populate_existing()
        .filter(Feedback.id.in_(feedback_ids))
        .order_by(Feedback.id.asc())
    )
    return _with_entity_lock(db, query, Feedback)


def lock_feedback(db: Session, feedback_id: int):
    """Lock one private feedback row after its caller owns U/O/A as required."""
    return _feedback_lock_query(db, (feedback_id,)).first()


def lock_feedback_outbox(db: Session, feedback_id: int):
    """Lock the unique publication row in stable O order before locking F."""
    from db.models import FeedbackPublicationOutbox

    query = (
        db.query(FeedbackPublicationOutbox)
        .populate_existing()
        .filter(FeedbackPublicationOutbox.feedback_id == feedback_id)
        .order_by(FeedbackPublicationOutbox.id.asc())
    )
    return _with_entity_lock(db, query, FeedbackPublicationOutbox).first()


def _feedback_for_outbox(db: Session, outbox: object) -> object | None:
    """Lock private feedback only after the caller has locked its Outbox."""
    feedback_id = getattr(outbox, "feedback_id", None)
    return lock_feedback(db, int(feedback_id)) if feedback_id is not None else None


def publication_marker(public_id: str, payload_digest: str) -> str:
    """Return the exact public idempotency marker for one publication."""
    return (
        "<!-- praxys-feedback-publication:"
        f"{MARKER_VERSION} id={public_id} payload={payload_digest} -->"
    )


def _publication_privacy_policy_digest() -> str:
    """Bind queued payloads to the exact final privacy-review policy."""
    return feedback_prompt.publication_privacy_review_digest()


def publication_review_token(feedback: object) -> str | None:
    """Bind an admin approval to the exact private draft and policy reviewed."""
    title = getattr(feedback, "ai_title", None)
    body = getattr(feedback, "ai_body", None)
    if not isinstance(title, str) or not title or not isinstance(body, str) or not body:
        return None
    consented_at = getattr(feedback, "publication_consented_at", None)
    canonical = json.dumps(
        {
            "body": body,
            "consent_version": getattr(
                feedback,
                "publication_consent_version",
                None,
            ),
            "consented_at": (
                consented_at.isoformat()
                if isinstance(consented_at, datetime)
                else None
            ),
            "image_keys": list(getattr(feedback, "image_keys", None) or []),
            "image_sensitive": getattr(feedback, "image_sensitive", None),
            "labels": list(getattr(feedback, "ai_labels", None) or []),
            "privacy_policy": _publication_privacy_policy_digest(),
            "title": title,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _canonical_digest(
    *,
    public_id: str,
    title: str,
    body: str,
    labels: tuple[str, ...],
    assignees: tuple[str, ...],
) -> str:
    canonical = json.dumps(
        {
            "assignees": list(assignees),
            "body": body,
            "labels": list(labels),
            "marker": {"id": public_id, "version": MARKER_VERSION},
            "privacy_policy": _publication_privacy_policy_digest(),
            "repository": github_issues.FEEDBACK_REPOSITORY,
            "title": title,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def build_publication_payload(feedback: object, public_id: str) -> PublicationPayload:
    """Rebuild and re-scrub the exact payload without persisting its content."""
    if not getattr(feedback, "ai_title", None) or not getattr(
        feedback, "ai_body", None
    ):
        raise PublicationPayloadBlocked("triage_output_missing")
    if getattr(feedback, "image_keys", None) and getattr(
        feedback, "image_sensitive", None
    ) is not False:
        raise PublicationPayloadBlocked("screenshot_unverified")
    title = feedback_scrub.scrub_text(str(feedback.ai_title))[:120].strip()
    body = feedback_scrub.scrub_text(str(feedback.ai_body)).strip()
    if not title or not body:
        raise PublicationPayloadBlocked("triage_output_missing")
    combined = title + "\n" + body
    if "[redacted" in combined.casefold():
        raise PublicationPayloadBlocked("redaction_marker_present")
    has_private_screenshot_context = bool(
        getattr(feedback, "image_keys", None)
        or getattr(feedback, "image_description", None)
    )
    if has_private_screenshot_context and _LEGACY_SCREENSHOT_SECTION.search(body):
        raise PublicationPayloadBlocked("screenshot_derived_text_present")

    labels = tuple(
        dict.fromkeys(
            str(value).strip()
            for value in [
                *(getattr(feedback, "ai_labels", None) or []),
                *github_issues.extra_labels(),
            ]
            if str(value).strip()
        )
    )
    assignees = tuple(dict.fromkeys(github_issues.assignees()))
    digest = _canonical_digest(
        public_id=public_id,
        title=title,
        body=body,
        labels=labels,
        assignees=assignees,
    )
    marker = publication_marker(public_id, digest)
    public_body = f"{body}\n\n{marker}"
    return PublicationPayload(
        title=title,
        body=public_body,
        labels=labels,
        assignees=assignees,
        marker=marker,
        digest=digest,
        public_content_sha256=github_issues.public_issue_content_sha256(
            title=title,
            body=public_body,
        ),
    )


def enqueue_publication(
    db: Session,
    feedback_id: int,
    *,
    now: datetime | None = None,
    locked_user: object | None = None,
    locked_feedback: object | None = None,
    human_review_approved: bool = False,
) -> object | None:
    """Atomically create at most one v2 outbox row for eligible feedback.

    The caller owns the transaction and commit so triage output, the Feedback
    publication outcome, and this row become visible together.
    """
    from db.models import (
        Feedback,
        FeedbackPublicationAttempt,
        FeedbackPublicationOutbox,
    )

    timestamp = now or datetime.utcnow()
    if (locked_user is None) != (locked_feedback is None):
        raise ValueError("locked_user and locked_feedback must be supplied together")
    if locked_user is None:
        owner_id = feedback_owner_id(db, feedback_id)
        if owner_id is None:
            return None
        user = lock_feedback_user(db, owner_id)
        if user is None or not user.is_active:
            return None
        row = lock_feedback(db, feedback_id)
    else:
        user = locked_user
        row = locked_feedback
    if row is None:
        return None
    if int(row.id) != feedback_id or str(row.user_id) != str(user.id):
        raise ValueError("locked feedback ownership does not match enqueue request")
    if not user.is_active:
        return None
    if user.is_demo:
        row.publication_status = "unavailable"
        return None
    existing_query = (
        db.query(FeedbackPublicationOutbox)
        .filter(FeedbackPublicationOutbox.feedback_id == feedback_id)
    )
    existing = _with_entity_lock(
        db,
        existing_query,
        FeedbackPublicationOutbox,
    ).first()
    supersede_existing = False
    if existing is not None and existing.state != "cancelled":
        if not human_review_approved or existing.state != "manual_review":
            return existing
        if existing.delivery_evidence != "not_sent":
            return existing
        ambiguous_attempt = (
            db.query(FeedbackPublicationAttempt.id)
            .filter(
                FeedbackPublicationAttempt.outbox_id == existing.id,
                FeedbackPublicationAttempt.outcome.in_(
                    ("in_flight", "unknown", "created", "reconciled")
                ),
            )
            .first()
        )
        multiple_match_attempt = (
            db.query(FeedbackPublicationAttempt.id)
            .filter(
                FeedbackPublicationAttempt.outbox_id == existing.id,
                FeedbackPublicationAttempt.error_code
                == "multiple_marker_matches",
            )
            .first()
        )
        if ambiguous_attempt is not None or multiple_match_attempt is not None:
            return existing
        supersede_existing = True
    active_for_user = (
        db.query(FeedbackPublicationOutbox.id)
        .join(Feedback, Feedback.id == FeedbackPublicationOutbox.feedback_id)
        .filter(
            Feedback.user_id == row.user_id,
            Feedback.id != row.id,
            FeedbackPublicationOutbox.state.notin_(("published", "cancelled")),
        )
        .first()
    )
    if active_for_user is not None:
        # A second v2 submission is not guessed eligible while the first is in
        # flight or ambiguous. It remains private for manual disposition.
        row.publication_status = "manual_required"
        row.status = "needs_review"
        row.error = "active_publication_candidate_exists"
        return None
    if (
        not feedback_has_publication_consent(row)
        or row.publication_consent_version
        != FEEDBACK_PUBLICATION_CONSENT_VERSION
        or row.publication_consented_at is None
        or row.github_issue_number is not None
        or row.status in ("rejected", "resolved")
    ):
        row.publication_status = "private"
        return None
    if not feedback_publication_authorized(
        db,
        user_id=row.user_id,
        submission_authorized=True,
    ) or not github_issues.is_configured():
        row.publication_status = "unavailable"
        return None

    public_id = (
        str(existing.public_id)
        if existing is not None and existing.state == "cancelled"
        else generate_publication_id()
    )
    try:
        payload = build_publication_payload(row, public_id)
    except PublicationPayloadBlocked as exc:
        row.publication_status = "manual_required"
        row.status = "needs_review"
        row.error = _bounded_code(exc.code, "payload_blocked")
        return None

    if supersede_existing and existing is not None:
        existing.state = "cancelled"
        existing.feedback_id = None
        existing.lease_token = None
        existing.lease_expires_at = None
        existing.last_error_code = "superseded_after_human_review"
        existing.updated_at = timestamp
        db.flush()
        existing = None

    if existing is not None:
        ambiguous_attempt = (
            db.query(FeedbackPublicationAttempt.id)
            .filter(
                FeedbackPublicationAttempt.outbox_id == existing.id,
                FeedbackPublicationAttempt.outcome.in_(
                    ("in_flight", "unknown", "created", "reconciled")
                ),
            )
            .first()
        )
        multiple_match_attempt = (
            db.query(FeedbackPublicationAttempt.id)
            .filter(
                FeedbackPublicationAttempt.outbox_id == existing.id,
                FeedbackPublicationAttempt.error_code
                == "multiple_marker_matches",
            )
            .first()
        )
        binding_matches = (
            existing.marker_version == MARKER_VERSION
            and existing.target_repo == github_issues.FEEDBACK_REPOSITORY
            and existing.consent_version == row.publication_consent_version
            and existing.consented_at == row.publication_consented_at
            and existing.payload_sha256 == payload.digest
            and existing.public_content_sha256
            == payload.public_content_sha256
            and existing.delivery_evidence == "not_sent"
            and existing.github_issue_number is None
            and existing.github_issue_url is None
        )
        if (
            ambiguous_attempt is not None
            or multiple_match_attempt is not None
            or not binding_matches
        ):
            row.publication_status = "manual_required"
            row.status = "needs_review"
            row.error = "cancelled_publication_evidence_mismatch"
            return None
        existing.state = "pending"
        existing.available_at = timestamp
        existing.lease_token = None
        existing.lease_expires_at = None
        existing.last_error_code = None
        existing.updated_at = timestamp
        row.publication_status = "queued"
        row.error = None
        return existing

    outbox = FeedbackPublicationOutbox(
        id=str(uuid4()),
        feedback_id=row.id,
        public_id=public_id,
        marker_version=MARKER_VERSION,
        target_repo=github_issues.FEEDBACK_REPOSITORY,
        consent_version=row.publication_consent_version,
        consented_at=row.publication_consented_at,
        payload_sha256=payload.digest,
        public_content_sha256=payload.public_content_sha256,
        state="pending",
        delivery_evidence="not_sent",
        attempt_count=0,
        reconcile_count=0,
        available_at=timestamp,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db.add(outbox)
    row.publication_status = "queued"
    row.error = None
    return outbox


def _claim_query(
    db: Session,
    *,
    states: tuple[str, ...],
    now: datetime,
    attached_only: bool = False,
    lease_available_only: bool = False,
):
    from db.models import FeedbackPublicationOutbox

    query = (
        db.query(FeedbackPublicationOutbox)
        .filter(
            FeedbackPublicationOutbox.state.in_(states),
            FeedbackPublicationOutbox.available_at <= now,
        )
        .order_by(
            FeedbackPublicationOutbox.available_at.asc(),
            FeedbackPublicationOutbox.created_at.asc(),
            FeedbackPublicationOutbox.id.asc(),
        )
    )
    if attached_only:
        query = query.filter(FeedbackPublicationOutbox.feedback_id.isnot(None))
    if lease_available_only:
        query = query.filter(
            or_(
                FeedbackPublicationOutbox.lease_token.is_(None),
                FeedbackPublicationOutbox.lease_expires_at <= now,
            )
        )
    if db.get_bind().dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    else:
        query = query.with_for_update()
    return query


def recover_expired_leases(
    db: Session, *, now: datetime | None = None
) -> int:
    """Move expired sends to reconciliation; they are never made pending."""
    from db.models import FeedbackPublicationAttempt, FeedbackPublicationOutbox

    timestamp = now or datetime.utcnow()
    begin_serialized_write(db)
    outbox_query = (
        db.query(FeedbackPublicationOutbox)
        .populate_existing()
        .filter(
            FeedbackPublicationOutbox.state == "sending",
            FeedbackPublicationOutbox.lease_expires_at.isnot(None),
            FeedbackPublicationOutbox.lease_expires_at <= timestamp,
        )
        .order_by(FeedbackPublicationOutbox.id.asc())
    )
    rows = _with_entity_lock(
        db,
        outbox_query,
        FeedbackPublicationOutbox,
    ).all()
    if not rows:
        db.commit()
        return 0

    outbox_ids = tuple(str(outbox.id) for outbox in rows)
    attempt_query = (
        db.query(FeedbackPublicationAttempt)
        .populate_existing()
        .filter(
            FeedbackPublicationAttempt.outbox_id.in_(outbox_ids),
            FeedbackPublicationAttempt.outcome == "in_flight",
        )
        .order_by(FeedbackPublicationAttempt.id.asc())
    )
    attempts = _with_entity_lock(
        db,
        attempt_query,
        FeedbackPublicationAttempt,
    ).all()
    attempts_by_lease = {
        (str(attempt.outbox_id), str(attempt.lease_token)): attempt
        for attempt in attempts
    }
    feedback_ids = tuple(
        sorted(
            int(outbox.feedback_id)
            for outbox in rows
            if outbox.feedback_id is not None
        )
    )
    feedback_by_id = {
        int(feedback.id): feedback
        for feedback in (
            _feedback_lock_query(db, feedback_ids).all()
            if feedback_ids
            else []
        )
    }
    for outbox in rows:
        attempt = attempts_by_lease.get(
            (str(outbox.id), str(outbox.lease_token))
        )
        if attempt is not None:
            attempt.outcome = "unknown"
            attempt.error_code = "lease_expired"
            attempt.finished_at = timestamp
        outbox.state = "reconciling"
        outbox.delivery_evidence = "ambiguous"
        outbox.available_at = timestamp
        outbox.last_error_code = "lease_expired"
        outbox.lease_token = None
        outbox.lease_expires_at = None
        outbox.updated_at = timestamp
        feedback = (
            feedback_by_id.get(int(outbox.feedback_id))
            if outbox.feedback_id is not None
            else None
        )
        if feedback is not None:
            feedback.publication_status = "unknown"
            feedback.error = "publication_outcome_unknown"
    db.commit()
    return len(rows)


def claim_next_send(
    db: Session, *, now: datetime | None = None
) -> tuple[str, str] | None:
    """Claim one due send with a committed random lease and attempt row."""
    from db.models import FeedbackPublicationAttempt, FeedbackPublicationOutbox

    # Runtime publication authority is checked before any durable send-state
    # mutation. Ambiguous historical attempts use the separate reconciliation
    # claim path and remain resolvable while this gate is ineffective.
    if not github_issues.publication_readiness()["effective"]:
        return None
    timestamp = now or datetime.utcnow()
    begin_serialized_write(db)
    outbox = (
        _claim_query(
            db,
            states=("pending", "retry_wait"),
            now=timestamp,
            attached_only=True,
        )
        .filter(
            FeedbackPublicationOutbox.marker_version == MARKER_VERSION,
            FeedbackPublicationOutbox.payload_sha256.isnot(None),
            FeedbackPublicationOutbox.public_content_sha256.isnot(None),
            FeedbackPublicationOutbox.delivery_evidence == "not_sent",
        )
        .first()
    )
    if outbox is None:
        db.rollback()
        return None
    lease = str(uuid4())
    outbox.state = "sending"
    outbox.delivery_evidence = "ambiguous"
    outbox.lease_token = lease
    outbox.lease_expires_at = timestamp + timedelta(seconds=LEASE_SECONDS)
    outbox.attempt_count += 1
    outbox.updated_at = timestamp
    db.add(
        FeedbackPublicationAttempt(
            id=str(uuid4()),
            outbox_id=outbox.id,
            attempt_no=outbox.attempt_count,
            lease_token=lease,
            target_repo=outbox.target_repo,
            payload_sha256=outbox.payload_sha256,
            started_at=timestamp,
            outcome="in_flight",
        )
    )
    db.commit()
    return str(outbox.id), lease


def _lock_claim(db: Session, outbox_id: str, lease: str):
    from db.models import FeedbackPublicationOutbox

    query = (
        db.query(FeedbackPublicationOutbox)
        .populate_existing()
        .filter(
            FeedbackPublicationOutbox.id == outbox_id,
            FeedbackPublicationOutbox.lease_token == lease,
        )
        .order_by(FeedbackPublicationOutbox.id.asc())
    )
    return _with_entity_lock(db, query, FeedbackPublicationOutbox).first()


def _finish_attempt(
    db: Session,
    *,
    outbox_id: str,
    lease: str,
    outcome: str,
    now: datetime,
    http_status: int | None,
    error_code: str | None,
) -> None:
    from db.models import FeedbackPublicationAttempt

    query = (
        db.query(FeedbackPublicationAttempt)
        .populate_existing()
        .filter(
            FeedbackPublicationAttempt.outbox_id == outbox_id,
            FeedbackPublicationAttempt.lease_token == lease,
            FeedbackPublicationAttempt.outcome == "in_flight",
        )
        .order_by(FeedbackPublicationAttempt.id.asc())
    )
    attempt = _with_entity_lock(db, query, FeedbackPublicationAttempt).first()
    if attempt is not None:
        attempt.outcome = outcome
        attempt.finished_at = now
        attempt.http_status = http_status
        attempt.error_code = (
            _bounded_code(error_code, "unknown") if error_code else None
        )


def _mark_published(
    db: Session,
    *,
    outbox: object,
    number: int,
    issue_url: str,
    now: datetime,
) -> None:
    if not github_issues.issue_url_allowed(number, issue_url):
        raise ValueError("unsafe_issue_url")
    feedback = _feedback_for_outbox(db, outbox)
    outbox.state = "published"
    outbox.delivery_evidence = "published"
    outbox.github_issue_number = number
    outbox.github_issue_url = issue_url
    outbox.published_at = now
    outbox.last_error_code = None
    outbox.lease_token = None
    outbox.lease_expires_at = None
    outbox.updated_at = now
    if feedback is not None:
        feedback.github_issue_number = number
        feedback.github_issue_url = issue_url
        feedback.publication_status = "published"
        feedback.status = "issue_created"
        feedback.error = None
        if "agent-ready" in (feedback.ai_labels or []):
            from db.agent_loop import latest_decision

            decision = latest_decision(
                db,
                loop="change",
                subject_type="feedback",
                subject_ref=str(feedback.id),
            )
            if decision is not None:
                decision.output_json = {
                    **(decision.output_json or {}),
                    "agent_ready_applied": True,
                }


def _hold_claim(
    db: Session,
    *,
    outbox: object,
    lease: str,
    code: str,
    publication_status: str,
    now: datetime,
    delivery_evidence: str = "not_sent",
) -> None:
    _finish_attempt(
        db,
        outbox_id=outbox.id,
        lease=lease,
        outcome="not_sent",
        now=now,
        http_status=None,
        error_code=code,
    )
    outbox.state = "manual_review" if publication_status == "manual_required" else "held"
    outbox.delivery_evidence = delivery_evidence
    outbox.last_error_code = _bounded_code(code, "held")
    outbox.lease_token = None
    outbox.lease_expires_at = None
    outbox.updated_at = now
    feedback = _feedback_for_outbox(db, outbox)
    if feedback is not None:
        feedback.publication_status = publication_status
        feedback.error = outbox.last_error_code
        if publication_status == "manual_required":
            feedback.status = "needs_review"


def send_claim(db: Session, outbox_id: str, lease: str) -> str:
    """Serialize one claimed send against deletion of its owning account."""
    from db.account_lifecycle import AccountLifecycleBusy, account_lifecycle_lease
    from db.models import Feedback, FeedbackPublicationOutbox

    snapshot = db.get(FeedbackPublicationOutbox, outbox_id)
    if (
        snapshot is None
        or snapshot.state != "sending"
        or snapshot.lease_token != lease
        or snapshot.feedback_id is None
    ):
        return "stale"
    feedback = db.get(Feedback, snapshot.feedback_id)
    if feedback is None:
        db.rollback()
        return "stale"
    user_id = str(feedback.user_id)
    db.rollback()
    try:
        with account_lifecycle_lease(user_id, timeout_seconds=60.0):
            db.expire_all()
            return _send_claim_locked(db, outbox_id, lease)
    except AccountLifecycleBusy:
        # No provider call occurred. Leave the committed send lease for normal
        # expiry recovery, which moves it to marker-only reconciliation.
        db.rollback()
        logger.warning(
            "feedback publication send lease blocked by account lifecycle"
        )
        return "stale"


def _send_claim_locked(db: Session, outbox_id: str, lease: str) -> str:
    """Recheck a claimed payload, POST once, and fence finalization."""
    from db.models import (
        Feedback,
        FeedbackPublicationAttempt,
        FeedbackPublicationOutbox,
    )

    snapshot = db.get(FeedbackPublicationOutbox, outbox_id)
    if (
        snapshot is None
        or snapshot.state != "sending"
        or snapshot.lease_token != lease
    ):
        return "stale"
    feedback = db.get(Feedback, snapshot.feedback_id)
    if feedback is None:
        db.rollback()
        begin_serialized_write(db)
        locked = _lock_claim(db, outbox_id, lease)
        if locked is None:
            db.rollback()
            return "stale"
        _hold_claim(
            db,
            outbox=locked,
            lease=lease,
            code="feedback_missing",
            publication_status="manual_required",
            now=datetime.utcnow(),
        )
        db.commit()
        return "manual_required"

    authorized = (
        feedback_has_publication_consent(feedback)
        and feedback.publication_consent_version == snapshot.consent_version
        and feedback.publication_consented_at == snapshot.consented_at
        and feedback_publication_authorized(
            db,
            user_id=feedback.user_id,
            submission_authorized=True,
        )
        and github_issues.is_configured()
        and snapshot.target_repo == github_issues.FEEDBACK_REPOSITORY
        and snapshot.marker_version == MARKER_VERSION
        and snapshot.delivery_evidence == "ambiguous"
        and snapshot.public_content_sha256 is not None
    )
    if not authorized:
        db.rollback()
        begin_serialized_write(db)
        locked = _lock_claim(db, outbox_id, lease)
        if locked is None:
            db.rollback()
            return "stale"
        _hold_claim(
            db,
            outbox=locked,
            lease=lease,
            code="publication_unavailable",
            publication_status="unavailable",
            now=datetime.utcnow(),
        )
        db.commit()
        return "unavailable"
    try:
        payload = build_publication_payload(feedback, snapshot.public_id)
    except PublicationPayloadBlocked as exc:
        db.rollback()
        begin_serialized_write(db)
        locked = _lock_claim(db, outbox_id, lease)
        if locked is None:
            db.rollback()
            return "stale"
        _hold_claim(
            db,
            outbox=locked,
            lease=lease,
            code=exc.code,
            publication_status="manual_required",
            now=datetime.utcnow(),
        )
        db.commit()
        return "manual_required"
    if (
        payload.digest != snapshot.payload_sha256
        or payload.public_content_sha256 != snapshot.public_content_sha256
    ):
        db.rollback()
        begin_serialized_write(db)
        locked = _lock_claim(db, outbox_id, lease)
        if locked is None:
            db.rollback()
            return "stale"
        _hold_claim(
            db,
            outbox=locked,
            lease=lease,
            code="payload_digest_mismatch",
            publication_status="manual_required",
            now=datetime.utcnow(),
        )
        db.commit()
        return "manual_required"

    prior_ambiguous = (
        db.query(FeedbackPublicationAttempt.id)
        .filter(
            FeedbackPublicationAttempt.outbox_id == snapshot.id,
            FeedbackPublicationAttempt.lease_token != lease,
            FeedbackPublicationAttempt.outcome.in_(
                ("in_flight", "unknown", "created", "reconciled")
            ),
        )
        .first()
        is not None
    )
    if prior_ambiguous:
        db.rollback()
        begin_serialized_write(db)
        locked = _lock_claim(db, outbox_id, lease)
        if locked is None:
            db.rollback()
            return "stale"
        _finish_attempt(
            db,
            outbox_id=outbox_id,
            lease=lease,
            outcome="not_sent",
            now=datetime.utcnow(),
            http_status=None,
            error_code="prior_ambiguous_attempt",
        )
        locked.state = "reconciling"
        locked.delivery_evidence = "ambiguous"
        locked.available_at = datetime.utcnow()
        locked.last_error_code = "prior_ambiguous_attempt"
        locked.lease_token = None
        locked.lease_expires_at = None
        current = _feedback_for_outbox(db, locked)
        if current is not None:
            current.publication_status = "unknown"
            current.error = "publication_outcome_unknown"
        db.commit()
        return "unknown"

    # The lease was committed before network I/O. Before the first POST (and
    # before any bounded retry proven not-sent/rejected), reconcile the exact
    # immutable marker. A single existing issue is adopted, multiple matches
    # require review, and provider failure prevents the POST.
    db.rollback()
    preflight = github_issues.reconcile_issue_marker(
        payload.marker,
        public_content_sha256=payload.public_content_sha256,
    )
    if preflight["outcome"] != "unknown":
        timestamp = datetime.utcnow()
        begin_serialized_write(db)
        outbox = _lock_claim(db, outbox_id, lease)
        if outbox is None or outbox.state != "sending":
            db.rollback()
            return "stale"
        if (
            preflight["outcome"] == "reconciled"
            and preflight["number"]
            and preflight["url"]
        ):
            _finish_attempt(
                db,
                outbox_id=outbox_id,
                lease=lease,
                outcome="reconciled",
                now=timestamp,
                http_status=preflight["http_status"],
                error_code=None,
            )
            _mark_published(
                db,
                outbox=outbox,
                number=preflight["number"],
                issue_url=preflight["url"],
                now=timestamp,
            )
            db.commit()
            return "published"
        if preflight["outcome"] == "multiple":
            _hold_claim(
                db,
                outbox=outbox,
                lease=lease,
                code="multiple_marker_matches",
                publication_status="manual_required",
                now=timestamp,
                delivery_evidence="ambiguous",
            )
            db.commit()
            return "manual_required"
        _finish_attempt(
            db,
            outbox_id=outbox_id,
            lease=lease,
            outcome="not_sent",
            now=timestamp,
            http_status=preflight["http_status"],
            error_code=preflight["error_code"],
        )
        retryable = outbox.attempt_count < MAX_SEND_ATTEMPTS
        outbox.state = "retry_wait" if retryable else "held"
        outbox.delivery_evidence = "not_sent"
        outbox.available_at = timestamp + timedelta(
            seconds=RETRY_DELAY_SECONDS
        )
        outbox.last_error_code = _bounded_code(
            preflight["error_code"], "preflight_failure"
        )
        outbox.lease_token = None
        outbox.lease_expires_at = None
        current = _feedback_for_outbox(db, outbox)
        if current is not None:
            current.publication_status = (
                "queued" if retryable else "unavailable"
            )
            current.error = outbox.last_error_code
        db.commit()
        telemetry.record_feedback_publication(
            status="provider_failure",
            reason="provider_failure",
        )
        return "retry_wait" if retryable else "unavailable"

    # ``unknown/not_indexed_or_absent`` is safe here only because the durable
    # history above proves every earlier attempt was definitely not sent or
    # rejected. Once any attempt is ambiguous, the code never reaches a POST.
    outcome = github_issues.create_issue_outcome(
        title=payload.title,
        body=payload.body,
        labels=list(payload.labels),
        assignees_override=list(payload.assignees),
        publication_authorized=True,
    )
    timestamp = datetime.utcnow()
    begin_serialized_write(db)
    outbox = _lock_claim(db, outbox_id, lease)
    if outbox is None or outbox.state != "sending":
        db.rollback()
        return "stale"
    result = outcome["outcome"]
    if result == "created" and outcome["number"] and outcome["url"]:
        _finish_attempt(
            db,
            outbox_id=outbox_id,
            lease=lease,
            outcome="created",
            now=timestamp,
            http_status=outcome["http_status"],
            error_code=None,
        )
        _mark_published(
            db,
            outbox=outbox,
            number=outcome["number"],
            issue_url=outcome["url"],
            now=timestamp,
        )
        final = "published"
    elif result == "unknown":
        _finish_attempt(
            db,
            outbox_id=outbox_id,
            lease=lease,
            outcome="unknown",
            now=timestamp,
            http_status=outcome["http_status"],
            error_code=outcome["error_code"],
        )
        outbox.state = "reconciling"
        outbox.delivery_evidence = "ambiguous"
        outbox.available_at = timestamp + timedelta(
            seconds=RECONCILE_DELAY_SECONDS
        )
        outbox.last_error_code = _bounded_code(
            outcome["error_code"], "publication_unknown"
        )
        outbox.lease_token = None
        outbox.lease_expires_at = None
        outbox.updated_at = timestamp
        feedback = _feedback_for_outbox(db, outbox)
        if feedback is not None:
            feedback.publication_status = "unknown"
            feedback.error = "publication_outcome_unknown"
        final = "unknown"
        telemetry.record_feedback_publication(
            status="provider_failure",
            reason=_bounded_code(outcome["error_code"], "unknown"),
        )
    else:
        _finish_attempt(
            db,
            outbox_id=outbox_id,
            lease=lease,
            outcome=result,
            now=timestamp,
            http_status=outcome["http_status"],
            error_code=outcome["error_code"],
        )
        retryable = (
            result in ("not_sent", "rejected")
            and outbox.attempt_count < MAX_SEND_ATTEMPTS
            and outcome["error_code"] not in (
                "auth_missing",
                "publication_not_authorized",
            )
        )
        outbox.state = "retry_wait" if retryable else "held"
        outbox.delivery_evidence = "not_sent"
        outbox.available_at = timestamp + timedelta(
            seconds=RETRY_DELAY_SECONDS
        )
        outbox.last_error_code = _bounded_code(
            outcome["error_code"], "publication_failed"
        )
        outbox.lease_token = None
        outbox.lease_expires_at = None
        outbox.updated_at = timestamp
        feedback = _feedback_for_outbox(db, outbox)
        if feedback is not None:
            feedback.publication_status = (
                "queued" if retryable else "unavailable"
            )
            feedback.error = outbox.last_error_code
        final = "retry_wait" if retryable else "unavailable"
    db.commit()
    if feedback is not None:
        telemetry.record_feedback(kind=feedback.kind, status=final)
    return final


def claim_next_reconciliation(
    db: Session, *, now: datetime | None = None
) -> tuple[str, str] | None:
    """Fence one due reconciliation without creating another send attempt.

    A committed lease remains exclusive through its expiry. At or after the
    expiry timestamp, the row lock serializes takeover and the replacement
    token fences the former owner from finalization.
    """
    timestamp = now or datetime.utcnow()
    begin_serialized_write(db)
    from db.models import FeedbackPublicationOutbox

    outbox = (
        _claim_query(
            db,
            states=("reconciling",),
            now=timestamp,
            lease_available_only=True,
        )
        .filter(
            FeedbackPublicationOutbox.delivery_evidence == "ambiguous",
        )
        .first()
    )
    if outbox is None:
        db.rollback()
        return None
    lease = str(uuid4())
    outbox.lease_token = lease
    outbox.lease_expires_at = timestamp + timedelta(seconds=LEASE_SECONDS)
    outbox.reconcile_count += 1
    outbox.updated_at = timestamp
    db.commit()
    return str(outbox.id), lease


def reconcile_claim(db: Session, outbox_id: str, lease: str) -> str:
    """Resolve one ambiguous send by its exact public marker."""
    from db.models import FeedbackPublicationAttempt, FeedbackPublicationOutbox

    snapshot = db.get(FeedbackPublicationOutbox, outbox_id)
    if (
        snapshot is None
        or snapshot.state != "reconciling"
        or snapshot.lease_token != lease
    ):
        return "stale"
    if (
        snapshot.marker_version != MARKER_VERSION
        or snapshot.payload_sha256 is None
        or snapshot.public_content_sha256 is None
    ):
        db.rollback()
        begin_serialized_write(db)
        outbox = _lock_claim(db, outbox_id, lease)
        if outbox is None or outbox.state != "reconciling":
            db.rollback()
            return "stale"
        outbox.state = "manual_review"
        outbox.delivery_evidence = "ambiguous"
        outbox.last_error_code = "marker_content_binding_missing"
        outbox.lease_token = None
        outbox.lease_expires_at = None
        outbox.updated_at = datetime.utcnow()
        feedback = _feedback_for_outbox(db, outbox)
        if feedback is not None:
            feedback.publication_status = "manual_required"
            feedback.status = "needs_review"
            feedback.error = outbox.last_error_code
        db.commit()
        return "manual_required"
    marker = publication_marker(snapshot.public_id, snapshot.payload_sha256)
    public_content_sha256 = snapshot.public_content_sha256
    db.rollback()
    outcome = github_issues.reconcile_issue_marker(
        marker,
        public_content_sha256=public_content_sha256,
    )
    timestamp = datetime.utcnow()
    begin_serialized_write(db)
    outbox = _lock_claim(db, outbox_id, lease)
    if outbox is None or outbox.state != "reconciling":
        db.rollback()
        return "stale"
    attempt_query = (
        db.query(FeedbackPublicationAttempt)
        .populate_existing()
        .filter(
            FeedbackPublicationAttempt.outbox_id == outbox.id,
            FeedbackPublicationAttempt.outcome == "unknown",
        )
        .order_by(
            FeedbackPublicationAttempt.attempt_no.desc(),
            FeedbackPublicationAttempt.id.asc(),
        )
    )
    attempt = _with_entity_lock(
        db,
        attempt_query,
        FeedbackPublicationAttempt,
    ).first()
    if (
        outcome["outcome"] == "reconciled"
        and outcome["number"]
        and outcome["url"]
    ):
        if attempt is not None:
            attempt.outcome = "reconciled"
            attempt.http_status = outcome["http_status"]
            attempt.error_code = None
            attempt.finished_at = timestamp
        _mark_published(
            db,
            outbox=outbox,
            number=outcome["number"],
            issue_url=outcome["url"],
            now=timestamp,
        )
        final = "published"
    elif outcome["outcome"] == "multiple":
        outbox.state = "manual_review"
        outbox.delivery_evidence = "ambiguous"
        outbox.last_error_code = "multiple_marker_matches"
        outbox.lease_token = None
        outbox.lease_expires_at = None
        outbox.updated_at = timestamp
        feedback = _feedback_for_outbox(db, outbox)
        if feedback is not None:
            feedback.publication_status = "manual_required"
            feedback.status = "needs_review"
            feedback.error = outbox.last_error_code
        final = "manual_required"
    else:
        # Zero exact matches may only mean the Search index has not caught up.
        outbox.delivery_evidence = "ambiguous"
        outbox.available_at = timestamp + timedelta(
            seconds=RECONCILE_DELAY_SECONDS
        )
        outbox.last_error_code = _bounded_code(
            outcome["error_code"], "reconciliation_unknown"
        )
        outbox.lease_token = None
        outbox.lease_expires_at = None
        outbox.updated_at = timestamp
        feedback = _feedback_for_outbox(db, outbox)
        if feedback is not None:
            feedback.publication_status = "unknown"
            feedback.error = "publication_outcome_unknown"
        final = "unknown"
        if outcome["outcome"] == "provider_failure":
            telemetry.record_feedback_publication(
                status="provider_failure",
                reason="provider_failure",
            )
    db.commit()
    return final


def process_publication_queue(*, limit: int = 10) -> dict[str, int]:
    """Recover, reconcile, and send a bounded batch using fresh sessions."""
    from db.session import SessionLocal

    counts = {"recovered": 0, "reconciled": 0, "sent": 0}
    if SessionLocal is None:
        return counts
    with SessionLocal() as db:
        _record_operational_state(db)
        counts["recovered"] = recover_expired_leases(db)
    for _ in range(max(0, limit)):
        with SessionLocal() as db:
            claim = claim_next_reconciliation(db)
            if claim is None:
                break
            reconcile_claim(db, *claim)
            counts["reconciled"] += 1
    for _ in range(max(0, limit)):
        with SessionLocal() as db:
            claim = claim_next_send(db)
            if claim is None:
                break
            send_claim(db, *claim)
            counts["sent"] += 1
    return counts


def safe_wake_publication_queue(*, limit: int = 1) -> dict[str, int]:
    """Run one background wake without letting worker failures escape."""
    try:
        return process_publication_queue(limit=limit)
    except Exception:
        logger.error("feedback publication wake failed")
        telemetry.record_feedback_publication(
            status="provider_failure",
            reason="provider_failure",
        )
        return {"recovered": 0, "reconciled": 0, "sent": 0}


def _record_operational_state(db: Session) -> None:
    """Emit only actionable config/provider and aggregate queue-age signals."""
    from sqlalchemy import func

    from db.models import FeedbackPublicationOutbox

    readiness = github_issues.publication_readiness()
    if (
        readiness["positive_enable"]
        and not readiness["kill_switch"]
        and not readiness["effective"]
    ):
        telemetry.record_feedback_publication(
            status="config_failure",
            reason=str(readiness["reason"]),
        )
    now = datetime.utcnow()
    oldest_queued = (
        db.query(func.min(FeedbackPublicationOutbox.created_at))
        .filter(
            FeedbackPublicationOutbox.state.in_(
                ("pending", "retry_wait", "held")
            )
        )
        .scalar()
    )
    if (
        oldest_queued is not None
        and (now - oldest_queued).total_seconds() >= QUEUE_AGE_ALERT_SECONDS
    ):
        telemetry.record_feedback_publication(
            status="queue_aged",
            reason="pending",
        )
    oldest_unknown = (
        db.query(func.min(FeedbackPublicationOutbox.created_at))
        .filter(FeedbackPublicationOutbox.state == "reconciling")
        .scalar()
    )
    if (
        oldest_unknown is not None
        and (now - oldest_unknown).total_seconds()
        >= UNKNOWN_AGE_ALERT_SECONDS
    ):
        telemetry.record_feedback_publication(
            status="unknown_aged",
            reason="reconciling",
        )


_stop_event = threading.Event()
_reconciler_thread: threading.Thread | None = None


def _reconciler_loop() -> None:
    while not _stop_event.is_set():
        safe_wake_publication_queue(limit=10)
        if _stop_event.wait(60):
            break


def start_publication_reconciler() -> None:
    """Start one best-effort periodic wakeup in this API process."""
    global _reconciler_thread
    if _reconciler_thread is not None and _reconciler_thread.is_alive():
        return
    _stop_event.clear()
    _reconciler_thread = threading.Thread(
        target=_reconciler_loop,
        name="feedback-publication-reconciler",
        daemon=True,
    )
    _reconciler_thread.start()


def stop_publication_reconciler() -> None:
    """Stop this process's periodic wakeup without mutating queued evidence."""
    global _reconciler_thread
    _stop_event.set()
    if _reconciler_thread is not None:
        _reconciler_thread.join(timeout=5)
    _reconciler_thread = None
