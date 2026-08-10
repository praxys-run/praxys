"""API contract coverage for owner-scoped adaptive-plan context."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import ModuleType
from unittest import mock

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
def test_delegated_claims_cannot_replace_server_grant_or_confirm(
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
    assert preview.status_code == 403

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
    assert listed.status_code == 403

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
    assert disclosed.status_code == 404

    detail = client.get(
        f"/api/personal-context/{owner_id}",
        headers=structured,
    )
    assert detail.status_code == 404

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


def test_context_pilot_api_requires_opt_in_and_never_auto_mutates(
    context_api,
    monkeypatch,
) -> None:
    client, db_session = context_api
    scenarios = client.get(
        "/api/personal-context/pilot/scenarios",
        headers=_headers(),
    )
    assert scenarios.status_code == 200, scenarios.text
    assert {
        scenario["expected_outcome"]
        for scenario in scenarios.json()["scenarios"]
    } == {
        "clarification",
        "no_change",
        "insufficient_evidence",
        "safety",
        "suggestion",
    }
    assert scenarios.headers["cache-control"] == "private, no-store"

    synthetic = client.post(
        "/api/personal-context/pilot/runs",
        headers={
            **_headers(),
            "Idempotency-Key": "pilot-api-synthetic",
        },
        json={
            "source": "synthetic",
            "scenario_id": "availability-suggestion",
        },
    )
    assert synthetic.status_code == 200, synthetic.text
    assert synthetic.json()["proposal"]["status"] == "synthetic_only"
    assert synthetic.json()["proposal"]["acceptance_available"] is False

    not_opted_in = client.post(
        "/api/personal-context/pilot/runs",
        headers={
            **_headers(),
            "Idempotency-Key": "pilot-api-not-opted-in",
        },
        json={
            "source": "opt_in",
            "purpose": "plan_adjustment",
        },
    )
    assert not_opted_in.status_code == 422
    assert not_opted_in.json() == {"detail": "CONTEXT_PILOT_INVALID"}

    from db.models import TrainingPlan

    now = datetime.now(timezone.utc)
    workout_date = (now + timedelta(days=2)).date()
    with db_session.SessionLocal() as db:
        workout = TrainingPlan(
            user_id="context-api-owner",
            date=workout_date,
            workout_type="easy",
            planned_duration_min=60,
            workout_description="Synthetic API workout",
            source="praxys",
            workout_origin="generated",
        )
        db.add(workout)
        db.commit()
        canonical_id = workout.canonical_id

    confirmed = _confirm(
        client,
        key="pilot-api-context",
        body={
            "kind": "temporary_constraint",
            "purpose": "plan_adjustment",
            "payload": {
                "category": "less_time",
                "fields": {
                    "affected_dates": [workout_date.isoformat()],
                    "maximum_available_minutes": 30,
                },
                "narrative": "Private API marker",
            },
            "starts_at": now.isoformat(),
            "expires_at": (now + timedelta(days=14)).isoformat(),
            "purge_after": (now + timedelta(days=44)).isoformat(),
            "narrative_purge_at": (now + timedelta(days=30)).isoformat(),
            "consent_text_version": "purpose-v1",
            "client": "web",
        },
    )
    assert confirmed.status_code == 201, confirmed.text

    run = client.post(
        "/api/personal-context/pilot/runs",
        headers={
            **_headers(),
            "Idempotency-Key": "pilot-api-opt-in",
        },
        json={
            "source": "opt_in",
            "purpose": "plan_adjustment",
            "confirmed_opt_in": True,
        },
    )
    assert run.status_code == 200, run.text
    proposal = run.json()["proposal"]
    assert run.json()["outcome"] == "suggestion"
    assert proposal["action"]["canonical_id"] == canonical_id
    assert proposal["acceptance_requires_athlete"] is True
    with db_session.SessionLocal() as db:
        assert (
            db.query(TrainingPlan)
            .filter(TrainingPlan.canonical_id == canonical_id)
            .one()
            .planned_duration_min
            == 60
        )

    monkeypatch.setattr(
        "api.routes.personal_context._trigger_managed_delivery",
        lambda *args, **kwargs: {"status": "disabled", "items": []},
        raising=False,
    )
    monkeypatch.setattr(
        "api.context_pilot._trigger_managed_delivery",
        lambda *args, **kwargs: {"status": "disabled", "items": []},
    )
    accepted = client.post(
        f"/api/personal-context/pilot/proposals/{proposal['id']}/responses",
        headers={
            **_headers(),
            "Idempotency-Key": "pilot-api-accept",
        },
        json={"response": "accept"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["athlete_approved"] is True
    with db_session.SessionLocal() as db:
        accepted_workout = (
            db.query(TrainingPlan)
            .filter(TrainingPlan.canonical_id == canonical_id)
            .one()
        )
        assert accepted_workout.planned_duration_min == 30
        assert accepted_workout.workout_origin == "accepted_target"


def test_context_pilot_evaluation_is_admin_only_and_aggregate(
    context_api,
) -> None:
    client, db_session = context_api
    denied = client.get(
        "/api/personal-context/pilot/evaluation",
        headers=_headers(),
    )
    assert denied.status_code == 403

    from db.models import User

    with db_session.SessionLocal() as db:
        owner = db.get(User, "context-api-owner")
        owner.is_superuser = True
        db.commit()

    report = client.get(
        "/api/personal-context/pilot/evaluation",
        headers=_headers(),
    )
    assert report.status_code == 200, report.text
    serialized = json.dumps(report.json())
    assert report.json()["checks"]["subgroup"]["state"] == "not_measured"
    assert "context_item_ids" not in serialized
    assert "Private API marker" not in serialized


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _issue_mcp_session(client) -> tuple[str, dict[str, str]]:
    created = client.post(
        "/api/auth/mcp/handoffs",
        json={"audience": "praxys-coach-plugin"},
    )
    assert created.status_code == 201, created.text
    handoff = created.json()
    approved = client.post(
        f"/api/auth/mcp/handoffs/{handoff['state']}/decision",
        headers=_headers(),
        json={"decision": "approved"},
    )
    assert approved.status_code == 204, approved.text
    exchanged = client.post(
        "/api/auth/mcp/handoffs/exchange",
        json={
            "state": handoff["state"],
            "exchange_secret": handoff["exchange_secret"],
        },
    )
    assert exchanged.status_code == 200, exchanged.text
    return exchanged.json()["access_token"], handoff


def _issue_context_grant(
    client,
    session_token: str,
    *,
    purpose: str = "plan_adjustment",
    kind: str = "temporary_constraint",
    access: list[str] | None = None,
) -> tuple[str, dict[str, str]]:
    requested = client.post(
        "/api/personal-context/scoped-access/requests",
        headers=_bearer(session_token),
        json={
            "audience": "praxys-coach-plugin",
            "purpose": purpose,
            "kind": kind,
            "access": access or ["read"],
        },
    )
    assert requested.status_code == 201, requested.text
    handoff = requested.json()
    approved = client.post(
        f"/api/auth/mcp/handoffs/{handoff['state']}/decision",
        headers=_headers(),
        json={"decision": "approved"},
    )
    assert approved.status_code == 204, approved.text
    exchanged = client.post(
        "/api/auth/mcp/handoffs/exchange",
        json={
            "state": handoff["state"],
            "exchange_secret": handoff["exchange_secret"],
        },
    )
    assert exchanged.status_code == 200, exchanged.text
    return exchanged.json()["access_token"], handoff


def test_mcp_login_uses_opaque_one_time_handoff_not_account_jwt(
    context_api,
) -> None:
    client, db_session = context_api
    created = client.post(
        "/api/auth/mcp/handoffs",
        json={"audience": "praxys-coach-plugin"},
    )
    assert created.status_code == 201, created.text
    handoff = created.json()
    assert handoff["authorize_path"] == (
        f"/mcp/authorize?state={handoff['state']}"
    )
    assert "token=" not in handoff["authorize_path"]
    assert not handoff["state"].startswith("eyJ")
    assert not handoff["exchange_secret"].startswith("eyJ")
    assert datetime.fromisoformat(
        handoff["expires_at"].replace("Z", "+00:00")
    ) <= datetime.now(timezone.utc) + timedelta(minutes=11)

    malformed_secret = "opaque-secret-must-not-echo"
    malformed_exchange = client.post(
        "/api/auth/mcp/handoffs/exchange",
        json={
            "state": handoff["state"],
            "exchange_secret": [malformed_secret],
        },
    )
    assert malformed_exchange.status_code == 422
    assert malformed_exchange.json() == {"detail": "MCP_AUTH_INVALID"}
    assert malformed_secret not in malformed_exchange.text
    assert malformed_exchange.headers["cache-control"] == "private, no-store"

    rejected_secret = "not-the-client-held-exchange-secret"
    rejected_exchange = client.post(
        "/api/auth/mcp/handoffs/exchange",
        json={
            "state": handoff["state"],
            "exchange_secret": rejected_secret,
        },
    )
    assert rejected_exchange.status_code == 404
    assert rejected_secret not in rejected_exchange.text
    assert handoff["state"] not in rejected_exchange.text

    pending = client.post(
        "/api/auth/mcp/handoffs/exchange",
        json={
            "state": handoff["state"],
            "exchange_secret": handoff["exchange_secret"],
        },
    )
    assert pending.status_code == 202
    assert pending.json() == {"status": "pending"}

    approved = client.post(
        f"/api/auth/mcp/handoffs/{handoff['state']}/decision",
        headers=_headers(),
        json={"decision": "approved"},
    )
    assert approved.status_code == 204, approved.text
    other_owner = client.get(
        f"/api/auth/mcp/handoffs/{handoff['state']}",
        headers=_headers("context-api-other"),
    )
    assert other_owner.status_code == 404

    exchanged = client.post(
        "/api/auth/mcp/handoffs/exchange",
        json={
            "state": handoff["state"],
            "exchange_secret": handoff["exchange_secret"],
        },
    )
    assert exchanged.status_code == 200, exchanged.text
    session = exchanged.json()
    assert session["access_token"].startswith("praxys_mcp_")
    assert session["access_token"].count(".") == 0
    assert session["audience"] == "praxys-coach-plugin"
    assert datetime.fromisoformat(
        session["expires_at"].replace("Z", "+00:00")
    ) <= datetime.now(timezone.utc) + timedelta(hours=25)

    replay = client.post(
        "/api/auth/mcp/handoffs/exchange",
        json={
            "state": handoff["state"],
            "exchange_secret": handoff["exchange_secret"],
        },
    )
    assert replay.status_code == 409
    me = client.get(
        "/api/auth/mcp/me",
        headers=_bearer(session["access_token"]),
    )
    assert me.status_code == 200, me.text
    assert me.json()["id"] == "context-api-owner"
    assert me.json()["actor_type"] == "mcp"

    bypass = client.post(
        "/api/personal-context/confirm",
        headers={
            **_bearer(session["access_token"]),
            "Idempotency-Key": "mcp-session-bypass",
        },
        json={
            **_draft(narrative=None),
            "consent_text_version": "purpose-v1",
            "client": "web",
        },
    )
    assert bypass.status_code == 403
    revoked = client.post(
        "/api/auth/mcp/revoke",
        headers=_bearer(session["access_token"]),
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json() == {"status": "revoked"}
    assert client.get(
        "/api/auth/mcp/me",
        headers=_bearer(session["access_token"]),
    ).status_code == 401

    from db.models import McpAccessHandoff, McpAccessToken, PersonalContextItem

    with db_session.SessionLocal() as db:
        row = db.query(McpAccessToken).one()
        assert row.token_digest not in {
            session["access_token"],
            handoff["exchange_secret"],
        }
        assert row.revoked_at is not None
        assert db.query(McpAccessHandoff).count() == 1
        assert db.query(PersonalContextItem).count() == 0


def test_context_scope_requires_first_party_approval_and_cannot_broaden(
    context_api,
) -> None:
    client, _ = context_api
    session_token, _ = _issue_mcp_session(client)
    invalid_audience = client.post(
        "/api/personal-context/scoped-access/requests",
        headers=_bearer(session_token),
        json={
            "audience": "another-client",
            "purpose": "plan_adjustment",
            "kind": "temporary_constraint",
            "access": ["read"],
        },
    )
    assert invalid_audience.status_code == 422
    assert invalid_audience.json() == {"detail": "PERSONAL_CONTEXT_INVALID"}
    invalid_pairing = client.post(
        "/api/personal-context/scoped-access/requests",
        headers=_bearer(session_token),
        json={
            "audience": "praxys-coach-plugin",
            "purpose": "plan_generation",
            "kind": "execution_explanation",
            "access": ["read"],
        },
    )
    assert invalid_pairing.status_code == 422
    assert invalid_pairing.json() == {"detail": "PERSONAL_CONTEXT_INVALID"}

    requested = client.post(
        "/api/personal-context/scoped-access/requests",
        headers=_bearer(session_token),
        json={
            "audience": "praxys-coach-plugin",
            "purpose": "plan_adjustment",
            "kind": "temporary_constraint",
            "access": ["read", "write"],
        },
    )
    assert requested.status_code == 201, requested.text
    handoff = requested.json()
    assert handoff["authorize_path"].startswith("/mcp/authorize?state=")
    assert datetime.fromisoformat(
        handoff["expires_at"].replace("Z", "+00:00")
    ) <= datetime.now(timezone.utc) + timedelta(minutes=11)

    self_grant = client.post(
        f"/api/auth/mcp/handoffs/{handoff['state']}/decision",
        headers=_bearer(session_token),
        json={"decision": "approved"},
    )
    assert self_grant.status_code == 403
    pending = client.post(
        "/api/auth/mcp/handoffs/exchange",
        json={
            "state": handoff["state"],
            "exchange_secret": handoff["exchange_secret"],
        },
    )
    assert pending.status_code == 202

    cross_athlete = client.post(
        f"/api/auth/mcp/handoffs/{handoff['state']}/decision",
        headers=_headers("context-api-other"),
        json={"decision": "approved"},
    )
    assert cross_athlete.status_code == 404
    approved = client.post(
        f"/api/auth/mcp/handoffs/{handoff['state']}/decision",
        headers=_headers(),
        json={"decision": "approved"},
    )
    assert approved.status_code == 204
    exchanged = client.post(
        "/api/auth/mcp/handoffs/exchange",
        json={
            "state": handoff["state"],
            "exchange_secret": handoff["exchange_secret"],
        },
    )
    assert exchanged.status_code == 200, exchanged.text
    grant = exchanged.json()
    assert grant["access_token"].startswith("praxys_ctx_")
    assert grant["purpose"] == "plan_adjustment"
    assert grant["kind"] == "temporary_constraint"
    assert grant["access"] == ["read", "write"]
    assert datetime.fromisoformat(
        grant["expires_at"].replace("Z", "+00:00")
    ) <= datetime.now(timezone.utc) + timedelta(minutes=16)

    broaden = client.post(
        "/api/personal-context/scoped-access/requests",
        headers=_bearer(grant["access_token"]),
        json={
            "audience": "praxys-coach-plugin",
            "purpose": "goal_review",
            "kind": "durable_preference",
            "access": ["read"],
        },
    )
    assert broaden.status_code == 403


def test_scoped_read_is_minimal_owner_purpose_expiry_and_revocation_bound(
    context_api,
) -> None:
    client, db_session = context_api
    owner_draft = _draft(
        narrative="Narrative must never cross the MCP boundary",
    )
    owner_draft["payload"]["fields"]["custom_private_detail"] = (
        "Must stay first party"
    )
    owner = _confirm(
        client,
        key="scoped-read-owner",
        body={
            **owner_draft,
            "consent_text_version": "purpose-v1",
            "client": "web",
        },
    )
    assert owner.status_code == 201
    other = _confirm(
        client,
        key="scoped-read-other",
        user_id="context-api-other",
        category="travel",
        narrative="Other athlete narrative",
    )
    assert other.status_code == 201

    session_token, _ = _issue_mcp_session(client)
    grant_token, _ = _issue_context_grant(
        client,
        session_token,
        access=["read"],
    )
    selected = client.get(
        "/api/personal-context/scoped/selection",
        headers=_bearer(grant_token),
    )
    assert selected.status_code == 200, selected.text
    assert len(selected.json()["items"]) == 1
    projection = selected.json()["items"][0]
    assert set(projection) == {
        "kind",
        "purpose",
        "category",
        "fields",
        "starts_at",
        "expires_at",
    }
    assert projection["category"] == "caregiving"
    serialized = json.dumps(selected.json())
    for forbidden in (
        "Narrative must never",
        "Must stay first party",
        "custom_private_detail",
        "Other athlete",
        "narrative",
        "id",
        "lineage",
        "source_actor",
        "processing_mode",
        "consent",
        "encrypted",
    ):
        assert forbidden not in serialized

    generic_metadata = client.get(
        "/api/personal-context",
        headers=_bearer(grant_token),
        params={
            "purpose": "plan_adjustment",
            "kind": "temporary_constraint",
        },
    )
    assert generic_metadata.status_code == 403
    direct_confirmation = client.post(
        "/api/personal-context/confirm",
        headers={
            **_bearer(grant_token),
            "Idempotency-Key": "context-grant-cannot-confirm",
        },
        json={
            **_draft(narrative=None),
            "consent_text_version": "purpose-v1",
            "client": "web",
        },
    )
    assert direct_confirmation.status_code == 403
    direct_correction = client.post(
        f"/api/personal-context/{owner.json()['item']['id']}/correct",
        headers={
            **_bearer(grant_token),
            "Idempotency-Key": "context-grant-cannot-correct",
        },
        json={
            "expected_version": 1,
            "payload": {
                "category": "less_time",
                "fields": {"maximum_available_minutes": 20},
            },
            "consent_text_version": "purpose-v1",
            "client": "web",
            **_lifecycle(),
        },
    )
    assert direct_correction.status_code == 404

    revoked = client.post(
        "/api/personal-context/scoped-access/revoke",
        headers=_bearer(grant_token),
    )
    assert revoked.status_code == 200
    assert revoked.json() == {"status": "revoked"}
    assert client.get(
        "/api/personal-context/scoped/selection",
        headers=_bearer(grant_token),
    ).status_code == 401

    fresh_token, _ = _issue_context_grant(
        client,
        session_token,
        access=["read"],
    )
    from db.models import McpAccessToken

    with db_session.SessionLocal() as db:
        row = (
            db.query(McpAccessToken)
            .filter(McpAccessToken.token_type == "context")
            .order_by(McpAccessToken.created_at.desc())
            .first()
        )
        row.expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.get(
        "/api/personal-context/scoped/selection",
        headers=_bearer(fresh_token),
    ).status_code == 401


def test_scoped_write_is_structured_preview_only_and_single_use(
    context_api,
) -> None:
    client, db_session = context_api
    session_token, _ = _issue_mcp_session(client)
    grant_token, _ = _issue_context_grant(
        client,
        session_token,
        access=["write"],
    )
    draft = _draft(narrative=None)
    narrative_attempt = {
        **draft,
        "payload": {
            **draft["payload"],
            "narrative": "The agent must not persist chat",
        },
    }
    rejected = client.post(
        "/api/personal-context/scoped/preview",
        headers=_bearer(grant_token),
        json=narrative_attempt,
    )
    assert rejected.status_code == 422
    assert rejected.json() == {"detail": "PERSONAL_CONTEXT_INVALID"}
    unbounded_field = {
        **draft,
        "payload": {
            **draft["payload"],
            "fields": {"custom_private_detail": "do not delegate"},
        },
    }
    rejected_field = client.post(
        "/api/personal-context/scoped/preview",
        headers=_bearer(grant_token),
        json=unbounded_field,
    )
    assert rejected_field.status_code == 422
    assert rejected_field.json() == {"detail": "PERSONAL_CONTEXT_INVALID"}
    assert "do not delegate" not in rejected_field.text
    unbounded_value = {
        **draft,
        "payload": {
            **draft["payload"],
            "fields": {"maximum_available_minutes": 1441},
        },
    }
    assert client.post(
        "/api/personal-context/scoped/preview",
        headers=_bearer(grant_token),
        json=unbounded_value,
    ).status_code == 422

    wrong_purpose = {
        **draft,
        "purpose": "goal_review",
    }
    assert client.post(
        "/api/personal-context/scoped/preview",
        headers=_bearer(grant_token),
        json=wrong_purpose,
    ).status_code == 403

    preview = client.post(
        "/api/personal-context/scoped/preview",
        headers=_bearer(grant_token),
        json=draft,
    )
    assert preview.status_code == 200, preview.text
    payload = preview.json()
    assert payload["confirmation_required"] is True
    assert payload["confirmation_path"] == "/training#plan-context"
    assert payload["miniapp_path"] == "/pages/training/index"
    assert payload["payload"]["category"] == "caregiving"
    assert "narrative" not in payload["payload"]

    from db.models import McpAccessToken, PersonalContextItem

    with db_session.SessionLocal() as db:
        assert db.query(PersonalContextItem).count() == 0
        grant = (
            db.query(McpAccessToken)
            .filter(McpAccessToken.token_type == "context")
            .one()
        )
        assert grant.write_consumed_at is not None

    replay = client.post(
        "/api/personal-context/scoped/preview",
        headers=_bearer(grant_token),
        json=draft,
    )
    assert replay.status_code == 409

    athlete_confirmed = _confirm(
        client,
        key="first-party-after-scoped-preview",
        narrative=None,
    )
    assert athlete_confirmed.status_code == 201
    assert athlete_confirmed.json()["item"]["source_actor_type"] == (
        "first_party_web"
    )


def _load_local_plugin_server() -> ModuleType:
    server_path = (
        Path(__file__).resolve().parents[1]
        / "plugins"
        / "praxys"
        / "mcp-server"
        / "server.py"
    )

    class FakeFastMCP:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def tool(self):
            return lambda function: function

    mcp_module = ModuleType("mcp")
    mcp_server_module = ModuleType("mcp.server")
    fastmcp_module = ModuleType("mcp.server.fastmcp")
    fastmcp_module.FastMCP = FakeFastMCP
    module_name = "praxys_host_local_context_contract"
    spec = importlib.util.spec_from_file_location(module_name, server_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with (
        mock.patch.dict(
            os.environ,
            {"PRAXYS_LOCAL": "1", "TRAINSIGHT_LOCAL": "0"},
        ),
        mock.patch.dict(
            sys.modules,
            {
                "mcp": mcp_module,
                "mcp.server": mcp_server_module,
                "mcp.server.fastmcp": fastmcp_module,
                module_name: module,
            },
        ),
    ):
        spec.loader.exec_module(module)
    return module


def test_scoped_write_grant_is_single_use_under_concurrency(
    context_api,
) -> None:
    client, db_session = context_api
    session_token, _ = _issue_mcp_session(client)
    grant_token, _ = _issue_context_grant(
        client,
        session_token,
        access=["write"],
    )
    barrier = threading.Barrier(2)

    def preview_once():
        barrier.wait()
        return client.post(
            "/api/personal-context/scoped/preview",
            headers=_bearer(grant_token),
            json=_draft(narrative=None),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: preview_once(), range(2)))

    assert sorted(response.status_code for response in responses) == [200, 409]
    from db.models import McpAccessToken, PersonalContextItem

    with db_session.SessionLocal() as db:
        assert db.query(PersonalContextItem).count() == 0
        grant = (
            db.query(McpAccessToken)
            .filter(McpAccessToken.token_type == "context")
            .one()
        )
        assert grant.write_consumed_at is not None


def test_local_mcp_uses_the_same_grant_projection_and_single_use_write(
    context_api,
) -> None:
    client, db_session = context_api
    created = _confirm(
        client,
        key="local-scoped-context",
        narrative="Local MCP must not receive this narrative",
    )
    assert created.status_code == 201
    server = _load_local_plugin_server()

    with mock.patch.object(
        server,
        "_local_user_id",
        return_value="context-api-owner",
    ):
        read_handoff = server._local_request_personal_context_access({
            "audience": "praxys-coach-plugin",
            "purpose": "plan_adjustment",
            "kind": "temporary_constraint",
            "access": ["read"],
        })
        assert client.post(
            f"/api/auth/mcp/handoffs/{read_handoff['state']}/decision",
            headers=_headers(),
            json={"decision": "approved"},
        ).status_code == 204
        read_exchange = server._local_exchange_personal_context_access({
            "state": read_handoff["state"],
            "exchange_secret": read_handoff["exchange_secret"],
        })
        with mock.patch.object(
            server,
            "get_context_token",
            return_value=read_exchange["access_token"],
        ):
            projection = server._local_read_personal_context()

        assert len(projection["items"]) == 1
        serialized = json.dumps(projection)
        assert "Local MCP must not receive" not in serialized
        assert "narrative" not in serialized
        assert "id" not in projection["items"][0]

        write_handoff = server._local_request_personal_context_access({
            "audience": "praxys-coach-plugin",
            "purpose": "plan_adjustment",
            "kind": "temporary_constraint",
            "access": ["write"],
        })
        assert client.post(
            f"/api/auth/mcp/handoffs/{write_handoff['state']}/decision",
            headers=_headers(),
            json={"decision": "approved"},
        ).status_code == 204
        write_exchange = server._local_exchange_personal_context_access({
            "state": write_handoff["state"],
            "exchange_secret": write_handoff["exchange_secret"],
        })
        local_draft = _draft(narrative=None)
        with mock.patch.object(
            server,
            "get_context_token",
            return_value=write_exchange["access_token"],
        ):
            preview = server._local_preview_personal_context(local_draft)
            with pytest.raises(RuntimeError, match="HTTP 409"):
                server._local_preview_personal_context(local_draft)

        assert preview["confirmation_required"] is True
        assert "narrative" not in preview["payload"]
        from db.models import PersonalContextItem

        with db_session.SessionLocal() as db:
            assert db.query(PersonalContextItem).count() == 1
