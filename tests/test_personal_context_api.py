"""API contract coverage for owner-scoped adaptive-plan context."""
from __future__ import annotations

import json
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import jwt
import pytest


@pytest.fixture
def context_api(monkeypatch):
    """Yield an authenticated TestClient backed by an isolated encrypted DB."""
    from fastapi.testclient import TestClient

    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", tmpdir.name)
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv("PRAXYS_JWT_SECRET", "context-api-test-secret")
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )
    monkeypatch.delenv("PRAXYS_FEEDBACK_BLOB_CONTAINER", raising=False)
    monkeypatch.delenv(
        "PRAXYS_FEEDBACK_BLOB_CONNECTION_STRING",
        raising=False,
    )
    monkeypatch.delenv(
        "PRAXYS_FEEDBACK_BLOB_ACCOUNT_URL",
        raising=False,
    )

    from db import crypto, session as db_session

    crypto._vault = None
    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    from db.models import User

    with db_session.SessionLocal() as db:
        db.add_all([
            User(
                id="context-api-owner",
                email="context-api-owner@example.test",
                hashed_password="x",
                is_active=True,
            ),
            User(
                id="context-api-other",
                email="context-api-other@example.test",
                hashed_password="x",
                is_active=True,
            ),
        ])
        db.commit()

    from api.main import app

    app.dependency_overrides.clear()
    with TestClient(app) as client:
        yield client, db_session

    app.dependency_overrides.clear()
    if db_session.engine is not None:
        db_session.engine.dispose()
    if db_session.async_engine is not None:
        import asyncio

        try:
            asyncio.run(db_session.async_engine.dispose())
        except RuntimeError:
            pass
    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    crypto._vault = None
    tmpdir.cleanup()


def _token(user_id: str, **claims) -> str:
    payload = {
        "sub": user_id,
        "aud": "fastapi-users:auth",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        **claims,
    }
    return jwt.encode(
        payload,
        "context-api-test-secret",
        algorithm="HS256",
    )


def _headers(user_id: str = "context-api-owner", **claims) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(user_id, **claims)}"}


def _lifecycle() -> dict[str, str]:
    now = datetime.now(timezone.utc)
    return {
        "starts_at": now.isoformat(),
        "expires_at": (now + timedelta(days=14)).isoformat(),
        "purge_after": (now + timedelta(days=44)).isoformat(),
    }


def _draft(
    *,
    category: str = "caregiving",
    narrative: str | None = "Short private planning detail",
) -> dict:
    payload = {
        "category": category,
        "fields": {
            "maximum_available_minutes": 30,
            "affected_days": ["monday", "wednesday"],
        },
    }
    if narrative is not None:
        payload["narrative"] = narrative
    return {
        "kind": "temporary_constraint",
        "purpose": "plan_adjustment",
        "payload": payload,
        **_lifecycle(),
    }


def _confirm(
    client,
    *,
    key: str,
    user_id: str = "context-api-owner",
    category: str = "caregiving",
    narrative: str | None = "Short private planning detail",
    body: dict | None = None,
):
    return client.post(
        "/api/personal-context/confirm",
        headers={
            **_headers(user_id),
            "Idempotency-Key": key,
        },
        json=body or {
            **_draft(category=category, narrative=narrative),
            "consent_text_version": "purpose-v1",
            "client": "web",
        },
    )


@pytest.mark.parametrize(
    ("actor_type", "actor_id"),
    [
        ("plugin", "plugin:test"),
        ("mcp", "mcp:test"),
        ("delegated_agent", "agent:test"),
    ],
)
def test_delegated_preview_is_scoped_but_confirmation_is_athlete_only(
    context_api,
    actor_type: str,
    actor_id: str,
) -> None:
    client, db_session = context_api
    plan_read = _headers(
        praxys_actor_type=actor_type,
        praxys_actor_id=actor_id,
        scope="plan:read",
        context_purposes=["plan_adjustment"],
        context_kinds=["temporary_constraint"],
    )
    assert client.post(
        "/api/personal-context/preview",
        headers=plan_read,
        json=_draft(),
    ).status_code == 403
    assert client.get(
        "/api/personal-context",
        headers=plan_read,
        params={
            "purpose": "plan_adjustment",
            "kind": "temporary_constraint",
        },
    ).status_code == 403

    delegated = _headers(
        praxys_actor_type=actor_type,
        praxys_actor_id=actor_id,
        scope="plan:context:write",
        context_purposes=["plan_adjustment"],
        context_kinds=["temporary_constraint"],
    )
    preview = client.post(
        "/api/personal-context/preview",
        headers=delegated,
        json=_draft(),
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["confirmation_required"] is True
    assert preview.json()["preview_actor_type"] == actor_type

    rejected = client.post(
        "/api/personal-context/confirm",
        headers={**delegated, "Idempotency-Key": "delegated-confirm-1"},
        json={
            **_draft(),
            "consent_text_version": "purpose-v1",
            "client": "web",
        },
    )
    assert rejected.status_code == 403

    from db.models import PersonalContextItem

    with db_session.SessionLocal() as db:
        assert db.query(PersonalContextItem).count() == 0


def test_confirm_is_encrypted_idempotent_and_has_purpose_receipt(
    context_api,
) -> None:
    client, db_session = context_api

    confirmation = {
        **_draft(),
        "consent_text_version": "purpose-v1",
        "client": "web",
    }
    created = _confirm(
        client,
        key="context-create-1",
        body=confirmation,
    )
    assert created.status_code == 201, created.text
    body = created.json()
    item_id = body["item"]["id"]
    assert body["item"]["purpose_confirmed"] is True
    assert body["item"]["payload"]["narrative"] == (
        "Short private planning detail"
    )
    assert body["replayed"] is False

    replayed = _confirm(
        client,
        key="context-create-1",
        body=confirmation,
    )
    assert replayed.status_code == 200, replayed.text
    assert replayed.json()["item"]["id"] == item_id
    assert replayed.json()["replayed"] is True

    conflict = _confirm(
        client,
        key="context-create-1",
        category="travel",
    )
    assert conflict.status_code == 409

    from db.models import (
        PersonalContextConsentReceipt,
        PersonalContextItem,
    )

    with db_session.SessionLocal() as db:
        item = db.get(PersonalContextItem, item_id)
        assert b"caregiving" not in bytes(item.encrypted_payload)
        assert b"Short private planning detail" not in bytes(
            item.encrypted_payload
        )
        receipts = db.query(PersonalContextConsentReceipt).all()
        assert len(receipts) == 1
        assert receipts[0].consent_scope == "purpose_confirmation"


def test_concurrent_confirmation_replays_instead_of_leaking_sqlite_lock(
    context_api,
) -> None:
    client, _ = context_api
    confirmation = {
        **_draft(narrative=None),
        "consent_text_version": "purpose-v1",
        "client": "web",
    }
    barrier = threading.Barrier(2)

    def submit():
        barrier.wait()
        return _confirm(
            client,
            key="context-concurrent-create",
            body=confirmation,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: submit(), range(2)))

    assert sorted(response.status_code for response in responses) == [200, 201]
    assert len({
        response.json()["item"]["id"]
        for response in responses
    }) == 1
    assert sorted(response.json()["replayed"] for response in responses) == [
        False,
        True,
    ]


def test_private_validation_errors_do_not_echo_context(context_api) -> None:
    client, _ = context_api
    private_value = "private-" + ("x" * 280)
    invalid = _draft(narrative=private_value)

    response = client.post(
        "/api/personal-context/preview",
        headers=_headers(),
        json=invalid,
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "PERSONAL_CONTEXT_INVALID"}
    assert private_value not in response.text
    assert response.headers["cache-control"] == "private, no-store"

    unauthenticated = client.post(
        "/api/personal-context/preview",
        json=_draft(narrative=None),
    )
    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["cache-control"] == "private, no-store"


def test_reads_require_exact_scopes_and_do_not_enumerate_other_owners(
    context_api,
) -> None:
    client, _ = context_api
    owner = _confirm(client, key="context-read-owner")
    other = _confirm(
        client,
        key="context-read-other",
        user_id="context-api-other",
        category="travel",
        narrative="Other athlete private detail",
    )
    owner_id = owner.json()["item"]["id"]
    other_id = other.json()["item"]["id"]

    structured = _headers(
        praxys_actor_type="delegated_agent",
        praxys_actor_id="agent:test",
        scope="plan:context:read",
        context_purposes=["plan_adjustment"],
        context_kinds=["temporary_constraint"],
    )
    listed = client.get(
        "/api/personal-context",
        headers=structured,
        params={
            "purpose": "plan_adjustment",
            "kind": "temporary_constraint",
        },
    )
    assert listed.status_code == 200, listed.text
    assert [row["id"] for row in listed.json()["items"]] == [owner_id]
    assert listed.json()["items"][0]["payload"]["narrative"] is None

    assert client.get(
        "/api/personal-context",
        headers=structured,
        params={
            "purpose": "plan_adjustment",
            "kind": "temporary_constraint",
            "include_narrative": "true",
        },
    ).status_code == 403

    narrative = _headers(
        praxys_actor_type="delegated_agent",
        praxys_actor_id="agent:test",
        scope=(
            "plan:context:read "
            "plan:context:narrative:read"
        ),
        context_purposes=["plan_adjustment"],
        context_kinds=["temporary_constraint"],
    )
    disclosed = client.get(
        f"/api/personal-context/{owner_id}",
        headers=narrative,
        params={"include_narrative": "true"},
    )
    assert disclosed.status_code == 200
    assert disclosed.json()["item"]["payload"]["narrative"] == (
        "Short private planning detail"
    )

    detail = client.get(
        f"/api/personal-context/{owner_id}",
        headers=structured,
    )
    assert detail.status_code == 200
    assert detail.json()["consent_receipts"] == []
    assert detail.json()["use_receipts"] == []

    other_miss = client.get(
        f"/api/personal-context/{other_id}",
        headers=_headers(),
    )
    random_miss = client.get(
        "/api/personal-context/00000000-0000-0000-0000-000000000000",
        headers=_headers(),
    )
    assert other_miss.status_code == random_miss.status_code == 404
    assert other_miss.json() == random_miss.json()


def test_correction_appends_and_stale_versions_conflict(context_api) -> None:
    client, db_session = context_api
    confirmation = {
        **_draft(),
        "consent_text_version": "purpose-v1",
        "client": "web",
    }
    created = _confirm(
        client,
        key="context-correct-create",
        body=confirmation,
    )
    original = created.json()["item"]
    lifecycle = _lifecycle()
    request = {
        "expected_version": 1,
        "payload": {
            "category": "less_time",
            "fields": {"maximum_available_minutes": 20},
            "narrative": "A corrected private detail",
        },
        "consent_text_version": "purpose-v1",
        "client": "web",
        **lifecycle,
    }
    corrected = client.post(
        f"/api/personal-context/{original['id']}/correct",
        headers={
            **_headers(),
            "Idempotency-Key": "context-correction-1",
        },
        json=request,
    )
    assert corrected.status_code == 201, corrected.text
    successor = corrected.json()["item"]
    assert successor["version"] == 2
    assert successor["supersedes_id"] == original["id"]

    replayed = client.post(
        f"/api/personal-context/{original['id']}/correct",
        headers={
            **_headers(),
            "Idempotency-Key": "context-correction-1",
        },
        json=request,
    )
    assert replayed.status_code == 200
    assert replayed.json()["item"]["id"] == successor["id"]
    assert replayed.json()["replayed"] is True

    original_replay = _confirm(
        client,
        key="context-correct-create",
        body=confirmation,
    )
    assert original_replay.status_code == 200
    assert original_replay.json()["item"]["id"] == original["id"]
    assert original_replay.json()["item"]["latest_version"] is False

    stale = client.post(
        f"/api/personal-context/{original['id']}/correct",
        headers={
            **_headers(),
            "Idempotency-Key": "context-correction-2",
        },
        json=request,
    )
    assert stale.status_code == 409

    from db.models import PersonalContextItem

    with db_session.SessionLocal() as db:
        rows = (
            db.query(PersonalContextItem)
            .order_by(PersonalContextItem.version)
            .all()
        )
        assert [(row.version, row.state) for row in rows] == [
            (1, "expired"),
            (2, "active"),
        ]


def test_only_athlete_can_grant_ai_consent_and_retries_are_idempotent(
    context_api,
) -> None:
    client, _ = context_api
    created = _confirm(
        client,
        key="context-consent-create",
        narrative=None,
    ).json()["item"]
    delegated = _headers(
        praxys_actor_type="delegated_agent",
        praxys_actor_id="agent:test",
        scope="plan:context:ai-consent plan:context:read",
        context_purposes=["plan_adjustment"],
        context_kinds=["temporary_constraint"],
    )
    consent_body = {
        "expected_version": 1,
        "decision": "granted",
        "provider": "azure_openai",
        "disclosed_fields": [
            "category",
            "fields.maximum_available_minutes",
        ],
        "narrative_disclosed": False,
        "consent_text_version": "ai-context-v1",
        "client": "web",
    }
    assert client.post(
        f"/api/personal-context/{created['id']}/ai-consent",
        headers={**delegated, "Idempotency-Key": "context-ai-consent-1"},
        json=consent_body,
    ).status_code == 404

    granted = client.post(
        f"/api/personal-context/{created['id']}/ai-consent",
        headers={
            **_headers(),
            "Idempotency-Key": "context-ai-consent-1",
        },
        json=consent_body,
    )
    assert granted.status_code == 200, granted.text
    assert granted.json()["item"]["processing_mode"] == "ai_allowed"
    assert granted.json()["receipt"]["consent_scope"] == "ai_processing"
    assert granted.json()["replayed"] is False

    replayed = client.post(
        f"/api/personal-context/{created['id']}/ai-consent",
        headers={
            **_headers(),
            "Idempotency-Key": "context-ai-consent-1",
        },
        json=consent_body,
    )
    assert replayed.status_code == 200
    assert replayed.json()["replayed"] is True

    changed = dict(consent_body)
    changed["decision"] = "denied"
    changed["provider"] = None
    assert client.post(
        f"/api/personal-context/{created['id']}/ai-consent",
        headers={
            **_headers(),
            "Idempotency-Key": "context-ai-consent-1",
        },
        json=changed,
    ).status_code == 409


def test_selection_excludes_without_mutation_and_expiry_blocks_use(
    context_api,
) -> None:
    client, _ = context_api
    first = _confirm(
        client,
        key="context-selection-1",
        narrative=None,
    ).json()["item"]
    second = _confirm(
        client,
        key="context-selection-2",
        category="travel",
        narrative=None,
    ).json()["item"]

    selected = client.post(
        "/api/personal-context/selection",
        headers=_headers(),
        json={
            "purpose": "plan_adjustment",
            "excluded_item_ids": [first["id"]],
        },
    )
    assert selected.status_code == 200, selected.text
    assert [item["id"] for item in selected.json()["items"]] == [second["id"]]

    expired = client.post(
        f"/api/personal-context/{second['id']}/expire",
        headers=_headers(),
        json={"expected_version": 1},
    )
    assert expired.status_code == 200
    assert expired.json()["state"] == "expired"

    selected = client.post(
        "/api/personal-context/selection",
        headers=_headers(),
        json={
            "purpose": "plan_adjustment",
            "excluded_item_ids": [first["id"]],
        },
    )
    assert selected.status_code == 200
    assert selected.json()["items"] == []

    inspected = client.get(
        "/api/personal-context",
        headers=_headers(),
    )
    states = {item["id"]: item["state"] for item in inspected.json()["items"]}
    assert states[first["id"]] == "active"
    assert states[second["id"]] == "expired"


def test_export_includes_all_versions_and_receipts_but_no_other_owner(
    context_api,
) -> None:
    client, db_session = context_api
    created = _confirm(
        client,
        key="context-export-owner",
        narrative=None,
    ).json()["item"]
    _confirm(
        client,
        key="context-export-other",
        user_id="context-api-other",
        category="travel",
        narrative="Other athlete export secret",
    )
    consent = client.post(
        f"/api/personal-context/{created['id']}/ai-consent",
        headers={
            **_headers(),
            "Idempotency-Key": "context-export-ai",
        },
        json={
            "expected_version": 1,
            "decision": "granted",
            "provider": "azure_openai",
            "disclosed_fields": ["category"],
            "consent_text_version": "ai-context-v1",
            "client": "web",
        },
    )
    assert consent.status_code == 200

    from api.personal_context import record_context_use

    with db_session.SessionLocal() as db:
        record_context_use(
            db,
            user_id="context-api-owner",
            item_id=created["id"],
            purpose="plan_adjustment",
            consumer_type="planning_ai",
            consumer_name="adaptive-plan-v1",
            disclosed_fields=["category"],
        )
        db.commit()

    correction = client.post(
        f"/api/personal-context/{created['id']}/correct",
        headers={
            **_headers(),
            "Idempotency-Key": "context-export-correction",
        },
        json={
            "expected_version": 1,
            "payload": {
                "category": "less_time",
                "fields": {"maximum_available_minutes": 25},
            },
            "consent_text_version": "purpose-v1",
            "client": "web",
            **_lifecycle(),
        },
    )
    assert correction.status_code == 201, correction.text
    successor = correction.json()["item"]

    dedicated = client.get(
        "/api/personal-context/export",
        headers=_headers(),
    )
    assert dedicated.status_code == 200, dedicated.text
    payload = dedicated.json()
    assert {item["id"] for item in payload["items"]} == {
        created["id"],
        successor["id"],
    }
    assert {item["version"] for item in payload["items"]} == {1, 2}
    assert {
        receipt["consent_scope"]
        for receipt in payload["consent_receipts"]
    } == {"purpose_confirmation", "ai_processing"}
    assert len(payload["use_receipts"]) == 1
    assert "Other athlete export secret" not in json.dumps(payload)

    complete = client.get("/api/me/export", headers=_headers())
    assert complete.status_code == 200, complete.text
    assert complete.json()["schema_version"] == 2
    assert {
        item["id"]
        for item in complete.json()["personal_context"]["items"]
    } == {created["id"], successor["id"]}


def test_delete_is_non_enumerating_and_stale_lineage_delete_conflicts(
    context_api,
) -> None:
    client, db_session = context_api
    confirmation = {
        **_draft(narrative=None),
        "consent_text_version": "purpose-v1",
        "client": "web",
    }
    created = _confirm(
        client,
        key="context-delete-create",
        body=confirmation,
    ).json()["item"]
    consent = client.post(
        f"/api/personal-context/{created['id']}/ai-consent",
        headers={
            **_headers(),
            "Idempotency-Key": "context-delete-ai",
        },
        json={
            "expected_version": 1,
            "decision": "granted",
            "provider": "azure_openai",
            "disclosed_fields": ["category"],
            "consent_text_version": "ai-context-v1",
            "client": "web",
        },
    )
    assert consent.status_code == 200
    from api.personal_context import record_context_use

    with db_session.SessionLocal() as db:
        record_context_use(
            db,
            user_id="context-api-owner",
            item_id=created["id"],
            purpose="plan_adjustment",
            consumer_type="planning_ai",
            consumer_name="adaptive-plan-v1",
            disclosed_fields=["category"],
        )
        db.commit()

    request = {
        "expected_version": 1,
        "payload": {
            "category": "less_time",
            "fields": {"maximum_available_minutes": 15},
        },
        "consent_text_version": "purpose-v1",
        "client": "web",
        **_lifecycle(),
    }
    corrected = client.post(
        f"/api/personal-context/{created['id']}/correct",
        headers={
            **_headers(),
            "Idempotency-Key": "context-delete-correction",
        },
        json=request,
    ).json()["item"]

    stale = client.delete(
        f"/api/personal-context/{created['id']}",
        headers=_headers(),
        params={"expected_version": 1},
    )
    assert stale.status_code == 409

    deleted = client.delete(
        f"/api/personal-context/{corrected['id']}",
        headers=_headers(),
        params={"expected_version": 2},
    )
    assert deleted.status_code == 204
    assert deleted.headers["cache-control"] == "private, no-store"
    assert client.delete(
        f"/api/personal-context/{corrected['id']}",
        headers=_headers(),
        params={"expected_version": 2},
    ).status_code == 204
    assert client.delete(
        "/api/personal-context/00000000-0000-0000-0000-000000000000",
        headers=_headers(),
        params={"expected_version": 1},
    ).status_code == 204
    replay_after_deletion = _confirm(
        client,
        key="context-delete-create",
        body=confirmation,
    )
    assert replay_after_deletion.status_code == 409

    from db.models import (
        PersonalContextCommand,
        PersonalContextConsentReceipt,
        PersonalContextItem,
        PersonalContextUseReceipt,
    )

    with db_session.SessionLocal() as db:
        assert db.query(PersonalContextItem).count() == 0
        assert db.query(PersonalContextConsentReceipt).count() == 0
        assert db.query(PersonalContextUseReceipt).count() == 0
        commands = db.query(PersonalContextCommand).all()
        assert commands
        assert all(command.status == "retired" for command in commands)
        assert all(command.target_item_id is None for command in commands)
        assert all(command.lineage_id is None for command in commands)
