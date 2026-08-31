"""Version-bound, append-only Terms acceptance receipt helpers."""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.china_client_boundary import (
    CHINA_CLIENT_CHANNELS,
    CHINA_CLIENT_CONTEXT_SCOPE_KEY,
    CN_WEB_CLIENT,
    MINIAPP_CLIENT,
    china_processing_enabled,
    miniapp_processing_enabled,
)
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


def request_china_channel(request: Request) -> str | None:
    """Return the validated server-classified China request channel."""

    state = request.scope.get("state")
    context = (
        state.get(CHINA_CLIENT_CONTEXT_SCOPE_KEY)
        if isinstance(state, dict)
        else None
    )
    channel = context.get("channel") if isinstance(context, dict) else None
    return channel if channel in CHINA_CLIENT_CHANNELS else None


def user_has_current_channel_receipt(
    db: Session,
    user_id: str,
    channel: str,
) -> bool:
    """Return whether the user explicitly acknowledged this China channel."""

    if channel not in CHINA_CLIENT_CHANNELS:
        return False
    return (
        db.query(TermsAcceptanceReceipt.id)
        .filter(
            TermsAcceptanceReceipt.user_id == user_id,
            TermsAcceptanceReceipt.terms_version == TERMS_VERSION,
            TermsAcceptanceReceipt.terms_digest == TERMS_CONTENT_DIGEST,
            TermsAcceptanceReceipt.channel == channel,
        )
        .first()
        is not None
    )


def user_has_current_legal_bundle_for_request(
    db: Session,
    user_id: str,
    request: Request,
) -> bool:
    """Require an explicit current receipt for a classified China channel."""

    if not user_has_current_legal_bundle(db, user_id):
        return False
    channel = request_china_channel(request)
    return (
        channel is None
        or user_has_current_channel_receipt(db, user_id, channel)
    )


def user_background_processing_authorized(
    db: Session,
    user_id: str,
) -> bool:
    """Require current Terms and an open switch for a China-channel user.

    Background work has no live browser request to classify. Any
    server-classified China receipt for the current bundle keeps that work
    behind the China switch, so a later direct-client receipt cannot bypass
    the stop. Existing users without a receipt retain the ``users`` projection
    compatibility path and ordinary-web-only receipts remain independent.
    """

    if not user_has_current_legal_bundle(db, user_id):
        return False
    current_channels = {
        str(channel)
        for channel, in db.query(TermsAcceptanceReceipt.channel)
        .filter(
            TermsAcceptanceReceipt.user_id == user_id,
            TermsAcceptanceReceipt.terms_version == TERMS_VERSION,
            TermsAcceptanceReceipt.terms_digest == TERMS_CONTENT_DIGEST,
            TermsAcceptanceReceipt.channel.in_(CHINA_CLIENT_CHANNELS),
        )
        .distinct()
        .all()
    }
    return not (
        (CN_WEB_CLIENT in current_channels and not china_processing_enabled())
        or (
            MINIAPP_CLIENT in current_channels
            and not miniapp_processing_enabled()
        )
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
    channel = request_china_channel(request)
    if channel is None:
        if request.url.path.startswith("/api/auth/wechat/"):
            raise HTTPException(
                status_code=503,
                detail="CLIENT_CONTEXT_UNAVAILABLE",
            )
        channel = "web"
        notice_version = None
    else:
        notice_version = TERMS_VERSION
    return TermsAcceptanceReceipt(
        user_id=user_id,
        action=TERMS_ACCEPTANCE_ACTION,
        terms_version=payload.terms_version,
        terms_digest=payload.terms_digest,
        locale=(payload.locale or "").strip() or None,
        channel=channel[:30],
        client_version=None,
        source_sha=None,
        notice_version=notice_version,
        release_id=None,
        accepted_at=accepted_at,
    )
