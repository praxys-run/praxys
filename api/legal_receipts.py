"""Version-bound, append-only Terms acceptance receipt helpers."""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.china_client_boundary import VERIFIED_CHINA_RELEASE_SCOPE_KEY
from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
from db.models import TermsAcceptanceReceipt


TERMS_ACCEPTANCE_ACTION = "accept_terms_and_acknowledge_privacy"


class TermsAcceptanceRequest(BaseModel):
    """Exact legal bundle presented by the accepting client."""

    terms_version: str = Field(..., min_length=1, max_length=20)
    terms_digest: str = Field(..., min_length=71, max_length=71)
    locale: str | None = Field(default=None, max_length=10)


def require_current_legal_bundle(
    terms_version: str,
    terms_digest: str,
) -> None:
    """Reject clients that did not present the exact current legal bundle."""
    if (
        terms_version != TERMS_VERSION
        or terms_digest != TERMS_CONTENT_DIGEST
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "TERMS_BUNDLE_MISMATCH",
                "terms_version": TERMS_VERSION,
                "terms_digest": TERMS_CONTENT_DIGEST,
            },
        )


def user_has_current_legal_bundle(db: Session, user_id: str) -> bool:
    """Return whether an active user has the exact checked-in legal bundle."""
    from db.models import User

    return (
        db.query(User.id)
        .filter(
            User.id == user_id,
            User.is_active == True,  # noqa: E712
            User.terms_version == TERMS_VERSION,
            User.terms_digest == TERMS_CONTENT_DIGEST,
        )
        .first()
        is not None
    )


def build_terms_receipt(
    *,
    user_id: str,
    request: Request,
    payload: TermsAcceptanceRequest,
    accepted_at: datetime,
) -> TermsAcceptanceReceipt:
    """Build an append-only receipt from server and bounded client context."""
    require_current_legal_bundle(
        payload.terms_version,
        payload.terms_digest,
    )
    state = request.scope.get("state")
    release_context = (
        state.get(VERIFIED_CHINA_RELEASE_SCOPE_KEY)
        if isinstance(state, dict)
        else None
    )
    if release_context is None:
        if request.url.path.startswith("/api/auth/wechat/"):
            raise HTTPException(
                status_code=503,
                detail="CLIENT_PROVENANCE_UNAVAILABLE",
            )
        channel = "web"
        client_version = None
        source_sha = None
        notice_version = None
        release_id = None
    else:
        channel = str(release_context["channel"])
        client_version = str(release_context["client_version"])
        source_sha = str(release_context["source_sha"])
        notice_version = str(release_context["notice_version"])
        release_id = str(release_context["release_id"])
    return TermsAcceptanceReceipt(
        user_id=user_id,
        action=TERMS_ACCEPTANCE_ACTION,
        terms_version=payload.terms_version,
        terms_digest=payload.terms_digest,
        locale=(payload.locale or "").strip() or None,
        channel=channel[:30],
        client_version=client_version,
        source_sha=source_sha,
        notice_version=notice_version,
        release_id=release_id,
        accepted_at=accepted_at,
    )
