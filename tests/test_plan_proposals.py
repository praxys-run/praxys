"""Adaptive plan proposal API contract tests."""
from __future__ import annotations

import importlib
import os
import tempfile
from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def proposal_client(monkeypatch):
    """Authenticated TestClient with a fresh SQLite DB and switchable user."""
    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", os.path.join(tmpdir.name, "data"))
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )
    monkeypatch.setenv("PRAXYS_AUTH_RATE_LIMIT_DISABLED", "true")

    from db import session as db_session

    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    import api.main

    importlib.reload(api.main)
    app = api.main.app

    current_user_id = {"value": "proposal-owner"}

    def _override_user() -> str:
        return current_user_id["value"]

    def _override_db():
        db = db_session.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    from api.auth import get_current_user_id, get_data_user_id, require_write_access
    from api.routes import adaptive_plan as adaptive_plan_route
    from db.models import User
    from db.session import get_db

    db = db_session.SessionLocal()
    try:
        db.add_all([
            User(id="proposal-owner", email="proposal-owner@test.local", hashed_password="x"),
            User(id="proposal-other", email="proposal-other@test.local", hashed_password="x"),
        ])
        db.commit()
    finally:
        db.close()

    app.dependency_overrides[get_current_user_id] = _override_user
    app.dependency_overrides[get_data_user_id] = _override_user
    app.dependency_overrides[require_write_access] = _override_user
    app.dependency_overrides[get_db] = _override_db
    monkeypatch.setattr(
        adaptive_plan_route,
        "_trigger_managed_delivery",
        lambda user_id, *, trigger: {"status": "skipped", "target": None, "reason": trigger, "items": []},
    )
    client = TestClient(app)
    client.current_user_id = current_user_id  # type: ignore[attr-defined]
    try:
        yield client, db_session, current_user_id
    finally:
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
        tmpdir.cleanup()


def _goal_payload(start: date | None = None, end: date | None = None) -> dict:
    start = start or date.today() + timedelta(days=1)
    end = end or start + timedelta(days=13)
    return {
        "goal_kind": "race",
        "target": {"distance": "10k", "target_label": "spring 10k"},
        "horizon_start": start.isoformat(),
        "horizon_end": end.isoformat(),
    }


def _proposal_payload(*, key: str = "proposal-create", workouts: list[dict] | None = None) -> dict:
    start = date.today() + timedelta(days=1)
    return {
        "goal": _goal_payload(start, start + timedelta(days=7)),
        "workouts": workouts or [
            {
                "date": start.isoformat(),
                "workout_type": "easy",
                "planned_duration_min": 45,
                "target_power_min": 200,
                "target_power_max": 240,
                "workout_description": "Aerobic run",
            },
            {
                "date": (start + timedelta(days=1)).isoformat(),
                "workout_type": "rest",
                "planned_duration_min": 30,
                "planned_distance_km": 5,
            },
        ],
        "idempotency_key": key,
        "origin": "api.plan.proposals.test",
        "policy_version": "structured-only-v1",
        "assumptions": [{"kind": "schedule", "value": "weekday mornings"}],
        "unknowns": ["preferred long-run day"],
        "warnings": [],
        "alternatives": [],
    }


def _training_plans(db_session, user_id: str = "proposal-owner"):
    from db.models import TrainingPlan

    db = db_session.SessionLocal()
    try:
        return db.query(TrainingPlan).filter(TrainingPlan.user_id == user_id).order_by(TrainingPlan.date).all()
    finally:
        db.close()


def test_create_read_successor_and_reject_preserve_noncanonical_history(proposal_client):
    client, db_session, _ = proposal_client

    create = client.post("/api/plan/proposals", json=_proposal_payload())

    assert create.status_code == 201, create.text
    first = create.json()
    assert first["version"] == 1
    assert first["state"] == "draft"
    assert first["adaptive_plan"]["version"] == 0
    assert first["workouts"][1]["workout_type"] == "rest"
    assert first["workouts"][1]["planned_duration_min"] is None
    assert _training_plans(db_session) == []

    retry = client.post("/api/plan/proposals", json=_proposal_payload())
    assert retry.status_code == 201, retry.text
    assert retry.json()["id"] == first["id"]

    current = client.get("/api/plan/proposals/current")
    assert current.status_code == 200, current.text
    assert current.json()["id"] == first["id"]

    edited_workouts = first["workouts"]
    edited_workouts[0] = {**edited_workouts[0], "workout_description": "Edited aerobic run"}
    edit_payload = _proposal_payload(key="proposal-edit", workouts=edited_workouts)
    edit_payload["expected_version"] = 1
    edit = client.post(f"/api/plan/proposals/{first['id']}/edits", json=edit_payload)

    assert edit.status_code == 201, edit.text
    successor = edit.json()
    assert successor["version"] == 2
    assert successor["supersedes_proposal_id"] == first["id"]
    assert successor["workouts"][0]["canonical_id"] == first["workouts"][0]["canonical_id"]

    reject = client.post(
        f"/api/plan/proposals/{successor['id']}/reject",
        json={"expected_version": 2, "idempotency_key": "reject-successor"},
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["state"] == "rejected"
    assert client.get("/api/plan/proposals/current").status_code == 404
    assert _training_plans(db_session) == []
    fresh = client.post(
        "/api/plan/proposals",
        json=_proposal_payload(key="proposal-after-reject"),
    )
    assert fresh.status_code == 201, fresh.text

    from db.models import PlanProposal

    db = db_session.SessionLocal()
    try:
        parent = db.query(PlanProposal).filter(PlanProposal.id == first["id"]).one()
        child = db.query(PlanProposal).filter(PlanProposal.id == successor["id"]).one()
        assert parent.state == "superseded"
        assert parent.workout_snapshot[0]["workout_description"] == "Aerobic run"
        assert child.workout_snapshot[0]["workout_description"] == "Edited aerobic run"
    finally:
        db.close()


def test_adopt_exact_version_is_atomic_idempotent_and_preserves_workout_ids(proposal_client):
    client, db_session, _ = proposal_client
    canonical_id = str(uuid4())
    start = date.today() + timedelta(days=2)
    payload = _proposal_payload(
        key="proposal-adopt-create",
        workouts=[
            {
                "canonical_id": canonical_id,
                "date": start.isoformat(),
                "workout_type": "tempo",
                "planned_duration_min": 50,
                "target_power_min": 250,
                "target_power_max": 280,
            }
        ],
    )
    created = client.post("/api/plan/proposals", json=payload).json()

    adopt = client.post(
        f"/api/plan/proposals/{created['id']}/adopt",
        json={
            "expected_proposal_version": 1,
            "expected_plan_version": 0,
            "idempotency_key": "adopt-once",
        },
    )

    assert adopt.status_code == 200, adopt.text
    body = adopt.json()
    assert body["status"] == "adopted"
    assert body["workouts"][0]["canonical_id"] == canonical_id
    assert body["delivery"]["status"] == "skipped"
    assert client.get("/api/plan/proposals/current").status_code == 404

    retry = client.post(
        f"/api/plan/proposals/{created['id']}/adopt",
        json={
            "expected_proposal_version": 1,
            "expected_plan_version": 0,
            "idempotency_key": "adopt-once",
        },
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["status"] == "already_adopted"

    different_key = client.post(
        f"/api/plan/proposals/{created['id']}/adopt",
        json={
            "expected_proposal_version": 1,
            "expected_plan_version": 0,
            "idempotency_key": "adopt-different",
        },
    )
    assert different_key.status_code == 409
    assert different_key.json()["detail"]["code"] == "PLAN_PROPOSAL_ALREADY_ADOPTED"

    from db.models import AdaptivePlan, PlanProposal, PlanRevision, TrainingPlan

    db = db_session.SessionLocal()
    try:
        plans = db.query(TrainingPlan).filter(TrainingPlan.user_id == "proposal-owner").all()
        assert len(plans) == 1
        assert plans[0].canonical_id == canonical_id
        assert plans[0].adaptive_plan_id == created["adaptive_plan_id"]
        aggregate = db.query(AdaptivePlan).filter(AdaptivePlan.id == created["adaptive_plan_id"]).one()
        assert aggregate.lifecycle == "active"
        assert aggregate.version == 1
        proposal = db.query(PlanProposal).filter(PlanProposal.id == created["id"]).one()
        assert proposal.state == "adopted"
        revision = db.query(PlanRevision).filter(PlanRevision.idempotency_key == "adopt-once").one()
        assert revision.details["proposal_id"] == created["id"]
    finally:
        db.close()


def test_cross_user_and_conflict_failures_leave_canonical_plan_unchanged(proposal_client):
    client, db_session, current_user_id = proposal_client
    created = client.post("/api/plan/proposals", json=_proposal_payload(key="owner-only")).json()

    stale = client.post(
        f"/api/plan/proposals/{created['id']}/adopt",
        json={
            "expected_proposal_version": 1,
            "expected_plan_version": 1,
            "idempotency_key": "stale-adopt",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "ADAPTIVE_PLAN_VERSION_CONFLICT"
    assert _training_plans(db_session) == []

    duplicate = client.post("/api/plan/proposals", json=_proposal_payload(key="duplicate-active"))
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "ADAPTIVE_PLAN_ACTIVE_EXISTS"

    current_user_id["value"] = "proposal-other"
    assert client.get("/api/plan/proposals/current").status_code == 404
    cross_adopt = client.post(
        f"/api/plan/proposals/{created['id']}/adopt",
        json={
            "expected_proposal_version": 1,
            "expected_plan_version": 0,
            "idempotency_key": "cross-adopt",
        },
    )
    assert cross_adopt.status_code == 404
    assert cross_adopt.json()["detail"]["code"] == "PLAN_PROPOSAL_NOT_FOUND"
    assert _training_plans(db_session, "proposal-other") == []


def test_expired_proposal_adoption_rolls_back_without_delivery(proposal_client):
    client, db_session, _ = proposal_client
    payload = _proposal_payload(key="expired-create")
    payload["expires_at"] = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
    created = client.post("/api/plan/proposals", json=payload).json()

    adopt = client.post(
        f"/api/plan/proposals/{created['id']}/adopt",
        json={
            "expected_proposal_version": 1,
            "expected_plan_version": 0,
            "idempotency_key": "expired-adopt",
        },
    )

    assert adopt.status_code == 409
    assert adopt.json()["detail"]["code"] == "PLAN_PROPOSAL_EXPIRED"
    assert _training_plans(db_session) == []
    fresh = client.post(
        "/api/plan/proposals",
        json=_proposal_payload(key="proposal-after-expiry"),
    )
    assert fresh.status_code == 201, fresh.text


def test_expired_current_proposal_does_not_block_new_draft(proposal_client):
    client, db_session, _ = proposal_client
    payload = _proposal_payload(key="expired-current-create")
    payload["expires_at"] = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
    created = client.post("/api/plan/proposals", json=payload)
    assert created.status_code == 201, created.text
    created_body = created.json()

    edit_payload = _proposal_payload(key="edit-expired-parent")
    edit_payload["expected_version"] = 1
    edit = client.post(
        f"/api/plan/proposals/{created_body['id']}/edits",
        json=edit_payload,
    )
    assert edit.status_code == 409
    assert edit.json()["detail"]["code"] == "PLAN_PROPOSAL_EXPIRED"

    retry = client.post("/api/plan/proposals", json=payload)
    assert retry.status_code == 201, retry.text
    assert retry.json()["state"] == "expired"

    current = client.get("/api/plan/proposals/current")
    assert current.status_code == 404

    fresh = client.post(
        "/api/plan/proposals",
        json=_proposal_payload(key="fresh-after-current-expiry"),
    )
    assert fresh.status_code == 201, fresh.text
    assert _training_plans(db_session) == []


def test_expired_proposal_reject_returns_expired(proposal_client):
    client, _, _ = proposal_client
    payload = _proposal_payload(key="expired-reject-create")
    payload["expires_at"] = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
    created = client.post("/api/plan/proposals", json=payload).json()

    reject = client.post(
        f"/api/plan/proposals/{created['id']}/reject",
        json={"expected_version": 1, "idempotency_key": "reject-expired"},
    )

    assert reject.status_code == 409
    assert reject.json()["detail"]["code"] == "PLAN_PROPOSAL_EXPIRED"


def test_expired_successor_idempotent_retry_returns_expired(proposal_client):
    client, _, _ = proposal_client
    created = client.post(
        "/api/plan/proposals",
        json=_proposal_payload(key="successor-expiry-parent"),
    ).json()
    edit_payload = _proposal_payload(key="successor-expiry-edit")
    edit_payload["expected_version"] = 1
    edit_payload["expires_at"] = (
        datetime.utcnow() - timedelta(minutes=5)
    ).isoformat()
    edited = client.post(
        f"/api/plan/proposals/{created['id']}/edits",
        json=edit_payload,
    )
    assert edited.status_code == 201, edited.text
    assert edited.json()["state"] == "draft"

    retry = client.post(
        f"/api/plan/proposals/{created['id']}/edits",
        json=edit_payload,
    )
    assert retry.status_code == 201, retry.text
    assert retry.json()["state"] == "expired"
    assert client.get("/api/plan/proposals/current").status_code == 404
