"""Unregistered private routes for the inactive Trail v2 draft slice."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import unicodedata
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from api.auth import get_authenticated_identity
from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
from api.legal_receipts import user_has_current_legal_bundle_for_request
from api.trail_plan_service import (
    TrailPlanServiceError,
    confirm_trail_plan_section,
    delete_trail_plan_draft,
    evaluate_trail_plan_readiness,
    read_trail_plan_draft,
    reset_trail_plan_draft,
    save_trail_plan_draft,
)
from db.session import get_db


MAX_TRAIL_REQUEST_BYTES = 32 * 1024
MAX_TRAIL_NESTING_DEPTH = 8
MAX_TRAIL_OBJECT_MEMBERS = 64
MAX_TRAIL_ARRAY_ENTRIES = 32
MAX_TRAIL_STRING_SCALARS = 128
MAX_TRAIL_NUMERIC_TOKEN_LENGTH = 16

_PRIVATE_HEADERS = {
    "Cache-Control": "private, no-store",
    "Pragma": "no-cache",
    "Vary": "Authorization",
}

router = APIRouter(prefix="/plan/trail", tags=["trail-plan"])


class _TrailJsonError(ValueError):
    pass


def _request_error(
    status_code: int,
    code: str,
    message: str,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
        headers=_PRIVATE_HEADERS,
    )


def _private_not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail="Not found",
        headers=_PRIVATE_HEADERS,
    )


def _trail_owner(request: Request, db: Session) -> str:
    """Authenticate before body I/O and reject every non-owner actor alike."""
    try:
        identity = get_authenticated_identity(request, db)
    except HTTPException as exc:
        # A valid context grant is rejected inside the generic identity helper
        # because this is not a personal-context path. It is nonetheless an
        # authenticated but ineligible Trail actor, so keep the private 404.
        if exc.status_code == 403:
            raise _private_not_found() from exc
        raise
    if (
        identity.credential_kind != "first_party_jwt"
        or not identity.user.is_active
        or identity.is_demo
        or identity.user.is_superuser
    ):
        raise _private_not_found()
    if not user_has_current_legal_bundle_for_request(
        db,
        identity.user_id,
        request,
    ):
        raise HTTPException(
            status_code=428,
            detail={
                "code": "TERMS_ACCEPTANCE_REQUIRED",
                "terms_version": TERMS_VERSION,
                "terms_digest": TERMS_CONTENT_DIGEST,
            },
            headers=_PRIVATE_HEADERS,
        )
    return identity.user_id


def _parse_int_token(token: str) -> int:
    if len(token) > MAX_TRAIL_NUMERIC_TOKEN_LENGTH:
        raise _TrailJsonError("numeric token too long")
    value = int(token)
    if not -(2**31) <= value <= 2**31 - 1:
        raise _TrailJsonError("integer outside structural range")
    return value


def _parse_decimal_token(token: str) -> Decimal:
    if (
        len(token) > MAX_TRAIL_NUMERIC_TOKEN_LENGTH
        or "e" in token.casefold()
    ):
        raise _TrailJsonError("invalid decimal token")
    try:
        value = Decimal(token)
    except InvalidOperation:
        raise _TrailJsonError("invalid decimal token") from None
    if (
        not value.is_finite()
        or abs(value) > Decimal("1000000")
        or value.as_tuple().exponent < -2
    ):
        raise _TrailJsonError("decimal outside structural range")
    return value


def _reject_constant(_token: str) -> None:
    raise _TrailJsonError("non-finite number")


def _normalize_string(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    if any(0xD800 <= ord(character) <= 0xDFFF for character in normalized):
        raise _TrailJsonError("string contains a non-scalar code point")
    if len(normalized) > MAX_TRAIL_STRING_SCALARS:
        raise _TrailJsonError("string too long")
    return normalized


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    if len(pairs) > MAX_TRAIL_OBJECT_MEMBERS:
        raise _TrailJsonError("too many object members")
    result: dict[str, Any] = {}
    for raw_key, value in pairs:
        key = _normalize_string(raw_key)
        if key in result:
            raise _TrailJsonError("duplicate object key")
        result[key] = value
    return result


def _normalize_structure(value: Any, *, depth: int = 1) -> Any:
    if depth > MAX_TRAIL_NESTING_DEPTH:
        raise _TrailJsonError("maximum nesting depth exceeded")
    if isinstance(value, dict):
        if len(value) > MAX_TRAIL_OBJECT_MEMBERS:
            raise _TrailJsonError("too many object members")
        return {
            key: _normalize_structure(item, depth=depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, list):
        if len(value) > MAX_TRAIL_ARRAY_ENTRIES:
            raise _TrailJsonError("too many array entries")
        return [
            _normalize_structure(item, depth=depth + 1) for item in value
        ]
    if isinstance(value, str):
        return _normalize_string(value)
    return value


async def read_trail_json_body(request: Request) -> dict[str, Any]:
    """Read one tightly bounded JSON object without framework body coercion."""
    content_encoding = request.headers.get("content-encoding", "").strip().casefold()
    if content_encoding not in {"", "identity"}:
        raise _request_error(
            415,
            "TRAIL_CONTENT_ENCODING_UNSUPPORTED",
            "Compressed Trail request bodies are not accepted.",
        )
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
    if content_type != "application/json":
        raise _request_error(
            415,
            "TRAIL_CONTENT_TYPE_UNSUPPORTED",
            "Trail request bodies must use application/json.",
        )
    declared_length: int | None = None
    raw_length = request.headers.get("content-length")
    if raw_length is not None:
        try:
            declared_length = int(raw_length)
        except ValueError:
            raise _request_error(
                400,
                "TRAIL_CONTENT_LENGTH_INVALID",
                "The Trail request Content-Length is invalid.",
            ) from None
        if declared_length < 0:
            raise _request_error(
                400,
                "TRAIL_CONTENT_LENGTH_INVALID",
                "The Trail request Content-Length is invalid.",
            )
        if declared_length > MAX_TRAIL_REQUEST_BYTES:
            raise _request_error(
                413,
                "TRAIL_REQUEST_TOO_LARGE",
                "The Trail request exceeds 32 KiB.",
            )
    body = bytearray()
    try:
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_TRAIL_REQUEST_BYTES:
                raise _request_error(
                    413,
                    "TRAIL_REQUEST_TOO_LARGE",
                    "The Trail request exceeds 32 KiB.",
                )
            body.extend(chunk)
    except HTTPException:
        raise
    except Exception:
        raise _request_error(
            400,
            "TRAIL_BODY_READ_FAILED",
            "The Trail request body could not be read.",
        ) from None
    if declared_length is not None and declared_length != len(body):
        raise _request_error(
            400,
            "TRAIL_CONTENT_LENGTH_MISMATCH",
            "The Trail request Content-Length does not match its body.",
        )
    try:
        text = bytes(body).decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise _request_error(
            400,
            "TRAIL_UTF8_INVALID",
            "The Trail request body is not valid UTF-8.",
        ) from None
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_object_pairs,
            parse_int=_parse_int_token,
            parse_float=_parse_decimal_token,
            parse_constant=_reject_constant,
        )
        parsed = _normalize_structure(parsed)
    except (
        json.JSONDecodeError,
        _TrailJsonError,
        RecursionError,
        ValueError,
    ):
        raise _request_error(
            400,
            "TRAIL_JSON_INVALID",
            "The Trail request body is not valid bounded JSON.",
        ) from None
    if not isinstance(parsed, dict):
        raise _request_error(
            400,
            "TRAIL_JSON_ROOT_INVALID",
            "The Trail request body must be an object.",
        )
    return parsed


def _if_match(request: Request) -> str:
    value = request.headers.get("if-match", "").strip()
    if value.startswith("W/"):
        raise _request_error(
            400,
            "TRAIL_IF_MATCH_INVALID",
            "Trail mutations require one strong revision.",
        )
    if len(value) >= 2 and value[0] == value[-1] == '"':
        value = value[1:-1]
    if not value:
        return ""
    if (
        "," in value
        or value == "*"
        or not value.startswith("sha256:")
        or len(value) != 71
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise _request_error(
            400,
            "TRAIL_IF_MATCH_INVALID",
            "Trail mutations require one exact revision.",
        )
    return value


def _service_error(exc: TrailPlanServiceError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail=exc.detail,
        headers=_PRIVATE_HEADERS,
    )


def _private(response: Response, payload: dict[str, Any]) -> dict[str, Any]:
    for key, value in _PRIVATE_HEADERS.items():
        response.headers[key] = value
    revision = payload.get("composite_revision")
    if isinstance(revision, str):
        response.headers["ETag"] = f'"{revision}"'
    return payload


@router.get("/draft", include_in_schema=False)
def get_trail_draft(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user_id = _trail_owner(request, db)
    try:
        payload = read_trail_plan_draft(db, user_id=user_id)
    except TrailPlanServiceError as exc:
        raise _service_error(exc) from exc
    return _private(response, payload)


@router.put("/draft", include_in_schema=False)
async def put_trail_draft(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user_id = _trail_owner(request, db)
    body = await read_trail_json_body(request)
    try:
        payload = save_trail_plan_draft(
            db,
            user_id=user_id,
            request=body,
            expected_revision=_if_match(request),
        )
    except TrailPlanServiceError as exc:
        raise _service_error(exc) from exc
    return _private(response, payload)


@router.post("/confirm", include_in_schema=False)
async def post_trail_confirmation(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user_id = _trail_owner(request, db)
    body = await read_trail_json_body(request)
    if set(body) != {"section_key", "section_revision"}:
        raise _request_error(
            400,
            "TRAIL_CONFIRMATION_INVALID",
            "The Trail confirmation request is invalid.",
        )
    try:
        payload = confirm_trail_plan_section(
            db,
            user_id=user_id,
            section_key=body["section_key"],
            section_revision=body["section_revision"],
            expected_revision=_if_match(request),
        )
    except TrailPlanServiceError as exc:
        raise _service_error(exc) from exc
    return _private(response, payload)


@router.post("/reset", include_in_schema=False)
def post_trail_reset(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user_id = _trail_owner(request, db)
    try:
        payload = reset_trail_plan_draft(
            db,
            user_id=user_id,
            expected_revision=_if_match(request),
        )
    except TrailPlanServiceError as exc:
        raise _service_error(exc) from exc
    return _private(response, payload)


@router.delete("/draft", include_in_schema=False)
def delete_trail_draft(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user_id = _trail_owner(request, db)
    try:
        payload = delete_trail_plan_draft(
            db,
            user_id=user_id,
            expected_revision=_if_match(request),
        )
    except TrailPlanServiceError as exc:
        raise _service_error(exc) from exc
    return _private(response, payload)


@router.post("/readiness", include_in_schema=False)
def post_trail_readiness(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user_id = _trail_owner(request, db)
    try:
        payload = evaluate_trail_plan_readiness(db, user_id=user_id)
    except TrailPlanServiceError as exc:
        raise _service_error(exc) from exc
    result = _private(response, payload)
    draft = payload.get("draft")
    if isinstance(draft, dict) and isinstance(draft.get("composite_revision"), str):
        response.headers["ETag"] = f'"{draft["composite_revision"]}"'
    return result
