"""HTTP-boundary tests for the deliberately unregistered Trail v2 router."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from api.routes import trail_plan as trail_routes
from db.session import get_db
from tests.test_trail_plan_service import _valid_request, trail_db


@pytest.fixture
def trail_route_client(trail_db, monkeypatch):
    app = FastAPI()
    app.include_router(trail_routes.router, prefix="/api")
    actor = {
        "credential_kind": "first_party_jwt",
        "is_demo": False,
        "is_active": True,
        "is_superuser": False,
    }

    def authenticate(request, _db):
        if request.headers.get("authorization") != "Bearer valid-owner":
            raise HTTPException(401, "Not authenticated")
        user = SimpleNamespace(
            is_active=actor["is_active"],
            is_superuser=actor["is_superuser"],
        )
        return SimpleNamespace(
            user_id="trail-owner",
            user=user,
            claims={},
            is_demo=actor["is_demo"],
            credential_kind=actor["credential_kind"],
        )

    def override_db():
        with trail_db.SessionLocal() as db:
            yield db

    monkeypatch.setattr(trail_routes, "get_authenticated_identity", authenticate)
    monkeypatch.setattr(
        trail_routes,
        "user_has_current_legal_bundle_for_request",
        lambda _db, _user_id, _request: True,
    )
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, actor


def _headers(**extra: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer valid-owner",
        "Content-Type": "application/json",
        **extra,
    }


def test_router_is_absent_from_main_and_every_isolated_route_is_hidden():
    from api.main import app as main_app

    assert all(
        "/plan/trail" not in getattr(route, "path", "")
        for route in main_app.routes
    )
    assert all(route.include_in_schema is False for route in trail_routes.router.routes)
    assert not any("trail" in path for path in main_app.openapi()["paths"])


@pytest.mark.parametrize(
    "change",
    [
        {"credential_kind": "mcp_session"},
        {"credential_kind": "context_grant"},
        {"is_demo": True},
        {"is_active": False},
        {"is_superuser": True},
    ],
)
def test_authenticated_ineligible_actors_get_private_404_before_body_io(
    trail_route_client,
    change,
):
    client, actor = trail_route_client
    actor.update(change)
    response = client.put(
        "/api/plan/trail/draft",
        content=b"not-json" * 5000,
        headers=_headers(**{"Content-Encoding": "gzip"}),
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}
    assert response.headers["cache-control"] == "private, no-store"


def test_missing_or_invalid_auth_stays_401_before_body_io(trail_route_client):
    client, _ = trail_route_client
    response = client.put(
        "/api/plan/trail/draft",
        content=b"not-json" * 5000,
        headers={"Content-Type": "application/json", "Content-Encoding": "gzip"},
    )
    assert response.status_code == 401


def test_manual_parser_rejects_compression_size_utf8_duplicates_and_exponents(
    trail_route_client,
):
    client, _ = trail_route_client

    compressed = client.put(
        "/api/plan/trail/draft",
        content=b"{}",
        headers=_headers(**{"Content-Encoding": "gzip"}),
    )
    assert compressed.status_code == 415

    oversized = client.put(
        "/api/plan/trail/draft",
        content=b"{" + (b" " * (trail_routes.MAX_TRAIL_REQUEST_BYTES + 1)),
        headers=_headers(),
    )
    assert oversized.status_code == 413

    exact = client.put(
        "/api/plan/trail/draft",
        content=b"{}" + b" " * (trail_routes.MAX_TRAIL_REQUEST_BYTES - 2),
        headers=_headers(),
    )
    assert exact.status_code == 400
    assert exact.json()["detail"]["code"] != "TRAIL_REQUEST_TOO_LARGE"

    invalid_utf8 = client.put(
        "/api/plan/trail/draft",
        content=b"\xff",
        headers=_headers(),
    )
    assert invalid_utf8.status_code == 400
    assert invalid_utf8.json()["detail"]["code"] == "TRAIL_UTF8_INVALID"

    duplicate = client.put(
        "/api/plan/trail/draft",
        content=(
            b'{"course_demand":{},"course_demand":{},"constraints":{}}'
        ),
        headers=_headers(),
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"]["code"] == "TRAIL_JSON_INVALID"

    exponential = client.put(
        "/api/plan/trail/draft",
        content=b'{"value":2.47e4}',
        headers=_headers(),
    )
    assert exponential.status_code == 400
    assert exponential.json()["detail"]["code"] == "TRAIL_JSON_INVALID"


def test_parser_rejects_deceptive_length_and_structural_depth():
    messages = [{"type": "http.request", "body": b"{}", "more_body": False}]

    async def receive():
        return messages.pop(0)

    request = Request({
        "type": "http",
        "method": "PUT",
        "path": "/api/plan/trail/draft",
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", b"1"),
        ],
    }, receive)
    with pytest.raises(HTTPException) as mismatch:
        asyncio.run(trail_routes.read_trail_json_body(request))
    assert mismatch.value.status_code == 400
    assert mismatch.value.detail["code"] == "TRAIL_CONTENT_LENGTH_MISMATCH"

    deep = "0"
    for _ in range(trail_routes.MAX_TRAIL_NESTING_DEPTH):
        deep = f'{{"x":{deep}}}'
    messages = [{
        "type": "http.request",
        "body": deep.encode(),
        "more_body": False,
    }]

    async def receive_deep():
        return messages.pop(0)

    deep_request = Request({
        "type": "http",
        "method": "PUT",
        "path": "/api/plan/trail/draft",
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(deep.encode())).encode()),
        ],
    }, receive_deep)
    with pytest.raises(HTTPException) as nested:
        asyncio.run(trail_routes.read_trail_json_body(deep_request))
    assert nested.value.detail["code"] == "TRAIL_JSON_INVALID"

    recursive = "[" * 15_000 + "0" + "]" * 15_000
    messages = [{
        "type": "http.request",
        "body": recursive.encode(),
        "more_body": False,
    }]

    async def receive_recursive():
        return messages.pop(0)

    recursive_request = Request({
        "type": "http",
        "method": "PUT",
        "path": "/api/plan/trail/draft",
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(recursive)).encode()),
        ],
    }, receive_recursive)
    with pytest.raises(HTTPException) as recursion:
        asyncio.run(trail_routes.read_trail_json_body(recursive_request))
    assert recursion.value.status_code == 400
    assert recursion.value.detail["code"] == "TRAIL_JSON_INVALID"


@pytest.mark.parametrize(
    "body",
    [
        "{" + ",".join(f'\"k{index}\":0' for index in range(65)) + "}",
        '{"values":[' + ",".join("0" for _ in range(33)) + "]}",
        '{"value":"' + ("x" * 129) + '"}',
        '{"value":2147483648}',
        '{"value":1.234}',
        '{"value":12345678901234567}',
    ],
)
def test_parser_rejects_every_structural_bound(trail_route_client, body):
    client, _ = trail_route_client
    response = client.put(
        "/api/plan/trail/draft",
        content=body.encode(),
        headers=_headers(),
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "TRAIL_JSON_INVALID"


def test_route_lifecycle_uses_strong_if_match_and_actual_inactive_readiness(
    trail_route_client,
):
    client, _ = trail_route_client
    initial = client.get("/api/plan/trail/draft", headers=_headers())
    assert initial.status_code == 200
    revision = initial.json()["composite_revision"]
    assert initial.headers["etag"] == f'"{revision}"'

    missing_precondition = client.put(
        "/api/plan/trail/draft",
        json=_valid_request(),
        headers=_headers(),
    )
    assert missing_precondition.status_code == 428

    saved = client.put(
        "/api/plan/trail/draft",
        json=_valid_request(),
        headers=_headers(**{"If-Match": f'"{revision}"'}),
    )
    assert saved.status_code == 200, saved.text
    saved_body = saved.json()
    assert saved_body["course_demand"]["fields"]["event_date"]["provenance"] == "athlete_stated"
    assert "owner_id" not in saved_body

    stale = client.put(
        "/api/plan/trail/draft",
        json=_valid_request(),
        headers=_headers(**{"If-Match": f'"{revision}"'}),
    )
    assert stale.status_code == 412

    readiness = client.post(
        "/api/plan/trail/readiness",
        headers=_headers(),
    )
    assert readiness.status_code == 200, readiness.text
    assert readiness.json()["readiness"]["detail_reason"] == "policy_inactive"
    assert readiness.json()["readiness"]["plan"] is None
    assert readiness.json()["readiness"]["inactive_dry_run"] is False


def test_client_cannot_submit_authority_fields(trail_route_client):
    client, _ = trail_route_client
    initial = client.get("/api/plan/trail/draft", headers=_headers()).json()
    body = _valid_request()
    body["owner_id"] = "another-owner"
    response = client.put(
        "/api/plan/trail/draft",
        json=body,
        headers=_headers(**{"If-Match": f'"{initial["composite_revision"]}"'}),
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "TRAIL_INVALID_FIELD_VALUE"


def test_legal_bundle_failure_remains_outside_product_readiness(
    trail_route_client,
    monkeypatch,
):
    client, _ = trail_route_client
    monkeypatch.setattr(
        trail_routes,
        "user_has_current_legal_bundle_for_request",
        lambda _db, _user_id, _request: False,
    )
    response = client.put(
        "/api/plan/trail/draft",
        content=b"not-json",
        headers=_headers(**{"Content-Encoding": "gzip"}),
    )
    assert response.status_code == 428
    assert response.json()["detail"]["code"] == "TERMS_ACCEPTANCE_REQUIRED"
