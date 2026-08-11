"""Adaptive plan proposal API contract tests."""
from __future__ import annotations

import csv
import importlib
import io
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
    from api.routes import ai as ai_route
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
    delivery_calls: list[tuple[str, str]] = []

    def _record_delivery(user_id: str, *, trigger: str) -> dict:
        delivery_calls.append((user_id, trigger))
        return {
            "status": "skipped",
            "target": None,
            "reason": trigger,
            "items": [],
        }

    monkeypatch.setattr(
        adaptive_plan_route,
        "_trigger_managed_delivery",
        _record_delivery,
    )
    monkeypatch.setattr(
        ai_route,
        "_trigger_managed_delivery",
        lambda user_id, *, trigger: {"status": "skipped", "target": None, "reason": trigger, "items": []},
    )
    client = TestClient(app)
    client.current_user_id = current_user_id  # type: ignore[attr-defined]
    client.delivery_calls = delivery_calls  # type: ignore[attr-defined]
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


def _adopt_payload(client: TestClient, payload: dict, *, key: str) -> dict:
    created = client.post("/api/plan/proposals", json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    adopted = client.post(
        f"/api/plan/proposals/{body['id']}/adopt",
        json={
            "expected_proposal_version": body["version"],
            "expected_plan_version": body["adaptive_plan"]["version"],
            "idempotency_key": key,
        },
    )
    assert adopted.status_code == 200, adopted.text
    return adopted.json()


def _csv_for(workouts: list[dict]) -> str:
    fields = [
        "date",
        "workout_type",
        "planned_duration_min",
        "planned_distance_km",
        "target_power_min",
        "target_power_max",
        "target_hr_min",
        "target_hr_max",
        "target_pace_min",
        "target_pace_max",
        "workout_description",
    ]
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for workout in workouts:
        writer.writerow({field: workout.get(field, "") for field in fields})
    return out.getvalue()


def test_http_validation_errors_use_typed_proposal_contract(proposal_client):
    client, _, _ = proposal_client
    unsupported = _proposal_payload(key="unsupported-field")
    unsupported["workouts"][0]["avg_power"] = 200

    extra_field = client.post("/api/plan/proposals", json=unsupported)
    assert extra_field.status_code == 422
    assert extra_field.json()["detail"] == {
        "code": "PLAN_PROPOSAL_UNSUPPORTED_FIELD",
        "message": "Unsupported proposal field supplied.",
        "errors": [
            {
                "field": "workouts.0.avg_power",
                "type": "extra_forbidden",
            }
        ],
        "fields": ["workouts.0.avg_power"],
    }

    empty = _proposal_payload(key="empty-workouts")
    empty["workouts"] = []
    invalid_body = client.post("/api/plan/proposals", json=empty)
    assert invalid_body.status_code == 422
    assert invalid_body.json()["detail"]["code"] == (
        "PLAN_PROPOSAL_VALIDATION_FAILED"
    )
    assert invalid_body.json()["detail"]["errors"][0]["field"] == "workouts"

    invalid_path = client.post(
        "/api/plan/proposals/not-a-uuid/adopt",
        json={
            "expected_proposal_version": 1,
            "expected_plan_version": 0,
            "idempotency_key": "invalid-path",
        },
    )
    assert invalid_path.status_code == 422
    assert invalid_path.json()["detail"]["code"] == (
        "PLAN_PROPOSAL_VALIDATION_FAILED"
    )
    assert invalid_path.json()["detail"]["errors"][0]["field"] == "proposal_id"


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
    assert "delivery" not in body
    assert client.delivery_calls == [  # type: ignore[attr-defined]
        ("proposal-owner", "plan_proposal_adopt")
    ]
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
    retry_body = retry.json()
    assert retry_body["status"] == "already_adopted"
    assert retry_body["proposal"] == body["proposal"]
    assert retry_body["revision_id"] == body["revision_id"]
    assert retry_body["workouts"] == body["workouts"]
    assert "delivery" not in retry_body
    assert client.delivery_calls == [  # type: ignore[attr-defined]
        ("proposal-owner", "plan_proposal_adopt")
    ]

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


def test_new_draft_after_adoption_replaces_full_future_owned_scope(proposal_client):
    client, db_session, _ = proposal_client
    start = date.today() + timedelta(days=2)
    initial = _adopt_payload(
        client,
        _proposal_payload(
            key="replace-scope-initial",
            workouts=[
                {
                    "date": (start + timedelta(days=offset)).isoformat(),
                    "workout_type": "easy",
                    "planned_duration_min": 40 + offset,
                }
                for offset in range(3)
            ],
        ),
        key="replace-scope-adopt-initial",
    )
    assert len(initial["workouts"]) == 3

    replacement = client.post(
        "/api/plan/proposals",
        json=_proposal_payload(
            key="replace-scope-draft",
            workouts=[
                {
                    "date": start.isoformat(),
                    "workout_type": "tempo",
                    "planned_duration_min": 55,
                }
            ],
        ),
    )
    assert replacement.status_code == 201, replacement.text
    draft = replacement.json()
    assert draft["version"] == 2
    assert draft["adaptive_plan"]["version"] == 1
    assert draft["adaptive_plan_id"] == initial["proposal"]["adaptive_plan_id"]

    adopt = client.post(
        f"/api/plan/proposals/{draft['id']}/adopt",
        json={
            "expected_proposal_version": draft["version"],
            "expected_plan_version": draft["adaptive_plan"]["version"],
            "idempotency_key": "replace-scope-adopt-replacement",
        },
    )
    assert adopt.status_code == 200, adopt.text
    assert [row["date"] for row in adopt.json()["workouts"]] == [start.isoformat()]

    initial_replay = client.post(
        f"/api/plan/proposals/{initial['proposal']['id']}/adopt",
        json={
            "expected_proposal_version": initial["proposal"]["version"],
            "expected_plan_version": 0,
            "idempotency_key": "replace-scope-adopt-initial",
        },
    )
    assert initial_replay.status_code == 200, initial_replay.text
    replay_body = initial_replay.json()
    assert replay_body["status"] == "already_adopted"
    assert replay_body["proposal"] == initial["proposal"]
    assert replay_body["revision_id"] == initial["revision_id"]
    assert [row["date"] for row in replay_body["workouts"]] == [
        (start + timedelta(days=offset)).isoformat()
        for offset in range(3)
    ]

    from db.models import (
        AdaptivePlan,
        AdaptivePlanGoalSnapshot,
        PlanRevision,
        TrainingPlan,
    )

    db = db_session.SessionLocal()
    try:
        plans = (
            db.query(TrainingPlan)
            .filter(TrainingPlan.user_id == "proposal-owner")
            .order_by(TrainingPlan.date)
            .all()
        )
        assert [plan.date for plan in plans] == [start]
        assert all(plan.adaptive_plan_id == draft["adaptive_plan_id"] for plan in plans)
        revision = (
            db.query(PlanRevision)
            .filter(PlanRevision.idempotency_key == "replace-scope-adopt-replacement")
            .one()
        )
        assert len(revision.before_snapshot) == 3
        assert len(revision.after_snapshot) == 1
        aggregate = db.query(AdaptivePlan).filter(
            AdaptivePlan.id == draft["adaptive_plan_id"]
        ).one()
        assert aggregate.goal_snapshot_id == draft["goal_snapshot_id"]
        assert db.query(AdaptivePlanGoalSnapshot).filter(
            AdaptivePlanGoalSnapshot.id == initial["proposal"]["goal_snapshot_id"]
        ).one().state == "superseded"
        assert db.query(AdaptivePlanGoalSnapshot).filter(
            AdaptivePlanGoalSnapshot.id == draft["goal_snapshot_id"]
        ).one().state == "active"
    finally:
        db.close()


@pytest.mark.parametrize("mutation", ["upload", "upsert", "delete", "reconciliation"])
def test_canonical_mutation_between_draft_and_adoption_stales_proposal(
    proposal_client,
    mutation: str,
):
    client, db_session, _ = proposal_client
    start = date.today() + timedelta(days=2)
    _adopt_payload(
        client,
        _proposal_payload(
            key=f"{mutation}-stale-initial",
            workouts=[
                {
                    "date": start.isoformat(),
                    "workout_type": "easy",
                    "planned_duration_min": 45,
                }
            ],
        ),
        key=f"{mutation}-stale-adopt-initial",
    )
    draft_response = client.post(
        "/api/plan/proposals",
        json=_proposal_payload(
            key=f"{mutation}-stale-draft",
            workouts=[
                {
                    "date": start.isoformat(),
                    "workout_type": "tempo",
                    "planned_duration_min": 50,
                }
            ],
        ),
    )
    assert draft_response.status_code == 201, draft_response.text
    draft = draft_response.json()
    expected_plan_version = draft["adaptive_plan"]["version"]

    if mutation == "upload":
        changed = client.post(
            "/api/plan/upload?mode=merge",
            json={
                "csv": _csv_for(
                    [
                        {
                            "date": start.isoformat(),
                            "workout_type": "easy",
                            "planned_duration_min": 35,
                            "workout_description": "Uploaded edit",
                        }
                    ]
                )
            },
        )
        assert changed.status_code == 200, changed.text
    elif mutation == "upsert":
        changed = client.put(
            f"/api/plan/{start.isoformat()}",
            json={"workout_type": "easy", "planned_duration_min": 35},
        )
        assert changed.status_code == 200, changed.text
    elif mutation == "delete":
        changed = client.delete(f"/api/plan/{start.isoformat()}")
        assert changed.status_code == 200, changed.text
        assert changed.json()["rows"] == 1
    else:
        from db.plan_ledger import lock_plan_writes, record_plan_revision

        db = db_session.SessionLocal()
        try:
            db.rollback()
            lock_plan_writes(db, "proposal-owner")
            record_plan_revision(
                db,
                user_id="proposal-owner",
                operation="accept_target",
                actor_type="user",
                actor_id="proposal-owner",
                origin="api.plan.reconciliation.accept",
                before=[],
                after=[],
                details={"target": "garmin", "test": mutation},
            )
            db.commit()
        finally:
            db.close()

    adopt = client.post(
        f"/api/plan/proposals/{draft['id']}/adopt",
        json={
            "expected_proposal_version": draft["version"],
            "expected_plan_version": expected_plan_version,
            "idempotency_key": f"{mutation}-stale-adopt-draft",
        },
    )
    assert adopt.status_code == 409, adopt.text
    assert adopt.json()["detail"]["code"] == "ADAPTIVE_PLAN_VERSION_CONFLICT"

    from db.models import PlanProposal

    db = db_session.SessionLocal()
    try:
        proposal = db.query(PlanProposal).filter(PlanProposal.id == draft["id"]).one()
        assert proposal.state == "draft"
    finally:
        db.close()


@pytest.mark.parametrize("terminal_state", ["rejected", "expired"])
def test_first_proposal_with_canonical_history_can_be_replaced(
    proposal_client,
    terminal_state: str,
):
    client, db_session, _ = proposal_client
    start = date.today() + timedelta(days=2)
    upload = client.post(
        "/api/plan/upload?mode=merge",
        json={
            "csv": _csv_for(
                [
                    {
                        "date": start.isoformat(),
                        "workout_type": "easy",
                        "planned_duration_min": 35,
                    }
                ]
            )
        },
    )
    assert upload.status_code == 200, upload.text

    payload = _proposal_payload(key=f"history-{terminal_state}-initial")
    if terminal_state == "expired":
        payload["expires_at"] = (
            datetime.utcnow() - timedelta(minutes=5)
        ).isoformat()
    created = client.post("/api/plan/proposals", json=payload)
    assert created.status_code == 201, created.text
    first = created.json()
    assert first["adaptive_plan"]["version"] == 1
    assert first["adaptive_plan"]["lifecycle"] == "draft"

    if terminal_state == "rejected":
        terminal = client.post(
            f"/api/plan/proposals/{first['id']}/reject",
            json={
                "expected_version": first["version"],
                "idempotency_key": "history-reject-decision",
            },
        )
        assert terminal.status_code == 200, terminal.text

    replacement = client.post(
        "/api/plan/proposals",
        json=_proposal_payload(key=f"history-{terminal_state}-replacement"),
    )
    assert replacement.status_code == 201, replacement.text
    assert replacement.json()["adaptive_plan_id"] != first["adaptive_plan_id"]

    from db.models import AdaptivePlan, TrainingPlan

    db = db_session.SessionLocal()
    try:
        prior = db.query(AdaptivePlan).filter(
            AdaptivePlan.id == first["adaptive_plan_id"]
        ).one()
        assert prior.lifecycle == "archived"
        assert db.query(TrainingPlan).filter(
            TrainingPlan.user_id == "proposal-owner"
        ).count() == 1
    finally:
        db.close()


def test_expired_replacement_on_active_plan_allows_fresh_draft(
    proposal_client,
):
    client, db_session, _ = proposal_client
    initial = _adopt_payload(
        client,
        _proposal_payload(key="active-expiry-initial"),
        key="active-expiry-adopt-initial",
    )
    adaptive_plan_id = initial["proposal"]["adaptive_plan_id"]
    active_goal_id = initial["proposal"]["goal_snapshot_id"]

    expired_payload = _proposal_payload(key="active-expiry-draft")
    expired_payload["expires_at"] = (
        datetime.utcnow() - timedelta(minutes=5)
    ).isoformat()
    expired = client.post(
        "/api/plan/proposals",
        json=expired_payload,
    )
    assert expired.status_code == 201, expired.text
    expired_body = expired.json()
    assert expired_body["adaptive_plan_id"] == adaptive_plan_id
    assert expired_body["version"] == 2
    assert client.get("/api/plan/proposals/current").status_code == 404

    fresh = client.post(
        "/api/plan/proposals",
        json=_proposal_payload(key="active-expiry-fresh"),
    )
    assert fresh.status_code == 201, fresh.text
    fresh_body = fresh.json()
    assert fresh_body["adaptive_plan_id"] == adaptive_plan_id
    assert fresh_body["version"] == 3
    assert fresh_body["adaptive_plan"]["lifecycle"] == "active"

    from db.models import AdaptivePlan, AdaptivePlanGoalSnapshot

    db = db_session.SessionLocal()
    try:
        aggregate = db.query(AdaptivePlan).filter(
            AdaptivePlan.id == adaptive_plan_id
        ).one()
        assert aggregate.goal_snapshot_id == active_goal_id
        assert db.query(AdaptivePlanGoalSnapshot).filter(
            AdaptivePlanGoalSnapshot.id == active_goal_id
        ).one().state == "active"
        assert db.query(AdaptivePlanGoalSnapshot).filter(
            AdaptivePlanGoalSnapshot.id == expired_body["goal_snapshot_id"]
        ).one().state == "draft"
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
    retry = client.post(
        f"/api/plan/proposals/{created['id']}/adopt",
        json={
            "expected_proposal_version": 1,
            "expected_plan_version": 0,
            "idempotency_key": "expired-adopt",
        },
    )
    assert retry.status_code == 409
    assert retry.json()["detail"]["code"] == "PLAN_PROPOSAL_EXPIRED"
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
    edit_retry = client.post(
        f"/api/plan/proposals/{created_body['id']}/edits",
        json=edit_payload,
    )
    assert edit_retry.status_code == 409
    assert edit_retry.json()["detail"]["code"] == "PLAN_PROPOSAL_EXPIRED"

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
    retry = client.post(
        f"/api/plan/proposals/{created['id']}/reject",
        json={"expected_version": 1, "idempotency_key": "reject-expired"},
    )
    assert retry.status_code == 409
    assert retry.json()["detail"]["code"] == "PLAN_PROPOSAL_EXPIRED"


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
