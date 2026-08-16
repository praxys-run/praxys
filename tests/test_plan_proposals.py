"""Adaptive plan proposal API contract tests."""
from __future__ import annotations

import csv
import copy
import importlib
import io
import os
import tempfile
from datetime import date, datetime, timedelta, timezone
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


def _none_target() -> dict:
    return {
        "metric": "none",
        "unit": "none",
        "reference": "none",
    }


def _target(
    metric: str,
    unit: str,
    reference: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> dict:
    payload = {
        "metric": metric,
        "unit": unit,
        "reference": reference,
    }
    if minimum is not None:
        payload["min"] = minimum
    if maximum is not None:
        payload["max"] = maximum
    return payload


def _time_step(
    minutes: int,
    *,
    phase: str = "other",
    target: dict | None = None,
    label: str | None = None,
    instructions: str | None = None,
) -> dict:
    step = {
        "type": "step",
        "phase": phase,
        "termination": {
            "type": "time",
            "seconds": minutes * 60,
        },
        "target": target or _none_target(),
    }
    if label is not None:
        step["label"] = label
    if instructions is not None:
        step["instructions"] = instructions
    return step


def _repeat_group(
    repetitions: int,
    *steps: dict,
    label: str | None = None,
) -> dict:
    group = {
        "type": "repeat",
        "repetitions": repetitions,
        "steps": list(steps),
    }
    if label is not None:
        group["label"] = label
    return group


def _structure(*steps: dict) -> dict:
    return {"steps": list(steps)}


def _proposal_workout_defaults(workout: dict) -> dict:
    normalized = dict(workout)
    workout_type = str(normalized.get("workout_type") or "")
    if "activity_type" not in normalized:
        normalized["activity_type"] = (
            "rest" if workout_type == "rest" else "running"
        )
    if "workout_structure_version" not in normalized:
        normalized["workout_structure_version"] = "v1"
    if "workout_structure" not in normalized:
        if normalized["activity_type"] == "rest" or workout_type == "rest":
            normalized["workout_structure"] = _structure()
        else:
            target = _none_target()
            if (
                normalized.get("target_power_min") is not None
                or normalized.get("target_power_max") is not None
            ):
                target = _target(
                    "power",
                    "watts",
                    "absolute",
                    minimum=normalized.get("target_power_min"),
                    maximum=normalized.get("target_power_max"),
                )
            duration_min = normalized.get("planned_duration_min")
            if duration_min:
                normalized["workout_structure"] = _structure(
                    _time_step(
                        int(duration_min),
                        target=target,
                    )
                )
            else:
                normalized["workout_structure"] = {
                    "steps": [
                        {
                            "type": "step",
                            "phase": "other",
                            "termination": {"type": "open"},
                            "target": target,
                        }
                    ]
                }
    return normalized


def _proposal_payload(
    *,
    key: str = "proposal-create",
    discipline: str = "running",
    workouts: list[dict] | None = None,
) -> dict:
    start = date.today() + timedelta(days=1)
    return {
        "goal": _goal_payload(start, start + timedelta(days=7)),
        "discipline": discipline,
        "workouts": [
            _proposal_workout_defaults(workout)
            for workout in (
                workouts
                if workouts is not None
                else [
            {
                "date": start.isoformat(),
                "activity_type": "running",
                "workout_type": "easy",
                "planned_duration_min": 45,
                "target_power_min": 200,
                "target_power_max": 240,
                "workout_description": "Aerobic run",
                "workout_structure_version": "v1",
                "workout_structure": _structure(
                    _time_step(
                        45,
                        target=_target(
                            "power",
                            "watts",
                            "absolute",
                            minimum=200,
                            maximum=240,
                        ),
                    )
                ),
            },
            {
                "date": (start + timedelta(days=1)).isoformat(),
                "activity_type": "rest",
                "workout_type": "rest",
                "planned_duration_min": 30,
                "planned_distance_km": 5,
                "workout_structure_version": "v1",
                "workout_structure": _structure(),
            },
                ]
            )
        ],
        "idempotency_key": key,
        "origin": "api.plan.proposals.test",
        "policy_version": "structured-only-v1",
        "assumptions": [{"kind": "schedule", "value": "weekday mornings"}],
        "unknowns": ["preferred long-run day"],
        "warnings": [],
        "alternatives": [],
    }


def _save_current_goal(db_session, goal: dict) -> None:
    from db.models import UserConfig

    db = db_session.SessionLocal()
    try:
        row = (
            db.query(UserConfig)
            .filter(UserConfig.user_id == "proposal-owner")
            .one_or_none()
        )
        if row is None:
            row = UserConfig(user_id="proposal-owner")
            db.add(row)
        row.goal = goal
        db.commit()
    finally:
        db.close()


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
    assert current.headers["cache-control"] == "private, no-store"

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


def test_proposal_idempotency_binds_the_complete_create_request(proposal_client):
    """A reused proposal key cannot replay a changed immutable request."""
    client, _, _ = proposal_client
    payload = _proposal_payload(key="proposal-fingerprint")
    created = client.post("/api/plan/proposals", json=payload)
    assert created.status_code == 201, created.text

    changed = copy.deepcopy(payload)
    changed["workouts"][0]["workout_description"] = "Different private request"
    conflict = client.post("/api/plan/proposals", json=changed)

    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["code"] == "PLAN_PROPOSAL_IDEMPOTENCY_CONFLICT"


def test_proposal_expiry_is_normalized_to_utc_before_naive_storage(proposal_client):
    """An offset-aware expiry cannot shift the persisted proposal lifetime."""
    client, db_session, current_user = proposal_client
    payload = _proposal_payload(key="proposal-offset-expiry")
    payload["expires_at"] = "2030-01-02T09:30:00+08:00"
    created = client.post("/api/plan/proposals", json=payload)
    assert created.status_code == 201, created.text

    from db.models import PlanProposal

    db = db_session.SessionLocal()
    try:
        proposal = db.query(PlanProposal).filter(
            PlanProposal.user_id == current_user["value"]
        ).one()
        assert proposal.expires_at == datetime(
            2030,
            1,
            2,
            1,
            30,
            tzinfo=timezone.utc,
        ).replace(tzinfo=None)
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


def test_adopt_replay_normalizes_legacy_goal_provenance(proposal_client):
    client, db_session, _ = proposal_client
    start = date.today() + timedelta(days=2)
    created = client.post(
        "/api/plan/proposals",
        json=_proposal_payload(
            key="legacy-adoption-snapshot-create",
            workouts=[
                {
                    "date": start.isoformat(),
                    "workout_type": "easy",
                    "planned_duration_min": 40,
                }
            ],
        ),
    ).json()
    adoption_payload = {
        "expected_proposal_version": created["version"],
        "expected_plan_version": created["adaptive_plan"]["version"],
        "idempotency_key": "legacy-adoption-snapshot-adopt",
    }
    adopted = client.post(
        f"/api/plan/proposals/{created['id']}/adopt",
        json=adoption_payload,
    )
    assert adopted.status_code == 200, adopted.text

    from db.models import PlanRevision

    db = db_session.SessionLocal()
    try:
        revision = db.get(PlanRevision, adopted.json()["revision_id"])
        assert revision is not None
        details = copy.deepcopy(revision.details)
        legacy_goal = details["proposal_snapshot"]["goal"]
        for field in (
            "purpose_source",
            "source_goal_id",
            "source_goal_revision",
        ):
            legacy_goal.pop(field)
        revision.details = details
        db.commit()
    finally:
        db.close()

    replay = client.post(
        f"/api/plan/proposals/{created['id']}/adopt",
        json=adoption_payload,
    )
    assert replay.status_code == 200, replay.text
    replay_goal = replay.json()["proposal"]["goal"]
    assert replay_goal["purpose_source"] is None
    assert replay_goal["source_goal_id"] is None
    assert replay_goal["source_goal_revision"] is None


def test_generic_current_goal_provenance_fences_retries_and_adoption(
    proposal_client,
):
    client, db_session, _ = proposal_client
    from api.plan_generation_capabilities import current_goal_reference

    first_goal = {
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": 1500,
    }
    _save_current_goal(db_session, first_goal)
    first_reference = current_goal_reference(
        user_id="proposal-owner",
        goal=first_goal,
    )
    assert first_reference is not None
    payload = _proposal_payload(key="generic-current-goal")
    payload["goal"].update({
        "goal_kind": "performance_5k",
        "target": {
            "distance": "5k",
            "target_time_sec": 1500,
        },
        "purpose_source": "current_goal",
        "source_goal_id": first_reference.goal_id,
        "source_goal_revision": first_reference.revision,
    })
    created = client.post("/api/plan/proposals", json=payload)
    assert created.status_code == 201, created.text
    created_body = created.json()

    next_goal = {
        **first_goal,
        "target_time_sec": 1440,
    }
    _save_current_goal(db_session, next_goal)
    next_reference = current_goal_reference(
        user_id="proposal-owner",
        goal=next_goal,
    )
    assert next_reference is not None

    changed_retry = copy.deepcopy(payload)
    changed_retry["goal"].update({
        "source_goal_id": next_reference.goal_id,
        "source_goal_revision": next_reference.revision,
    })
    retry = client.post("/api/plan/proposals", json=changed_retry)
    assert retry.status_code == 409, retry.text
    assert retry.json()["detail"]["code"] == (
        "PLAN_PROPOSAL_IDEMPOTENCY_CONFLICT"
    )

    stale_create = copy.deepcopy(payload)
    stale_create["idempotency_key"] = "generic-current-goal-stale"
    stale = client.post("/api/plan/proposals", json=stale_create)
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["code"] == (
        "PLAN_PURPOSE_REASSESSMENT_REQUIRED"
    )

    adopted = client.post(
        f"/api/plan/proposals/{created_body['id']}/adopt",
        json={
            "expected_proposal_version": created_body["version"],
            "expected_plan_version": created_body["adaptive_plan"]["version"],
            "idempotency_key": "generic-current-goal-adopt",
        },
    )
    assert adopted.status_code == 409, adopted.text
    assert adopted.json()["detail"]["code"] == (
        "PLAN_PURPOSE_REASSESSMENT_REQUIRED"
    )


def test_generic_current_goal_provenance_rejects_mismatched_goal(
    proposal_client,
):
    client, db_session, _ = proposal_client
    from api.plan_generation_capabilities import current_goal_reference

    current_goal = {
        "goal_kind": "performance_5k",
        "distance": "5k",
        "target_time_sec": 1500,
    }
    _save_current_goal(db_session, current_goal)
    reference = current_goal_reference(
        user_id="proposal-owner",
        goal=current_goal,
    )
    assert reference is not None
    payload = _proposal_payload(key="generic-current-goal-mismatch")
    payload["goal"].update({
        "purpose_source": "current_goal",
        "source_goal_id": reference.goal_id,
        "source_goal_revision": reference.revision,
    })

    response = client.post("/api/plan/proposals", json=payload)

    assert response.status_code == 400, response.text
    assert response.json()["detail"]["code"] == "PLAN_PURPOSE_INVALID"


def test_generic_proposal_rejects_unvalidated_capability_purpose(
    proposal_client,
):
    client, _, _ = proposal_client
    payload = _proposal_payload(key="generic-capability-purpose")
    payload["goal"]["purpose_source"] = "capability"

    response = client.post("/api/plan/proposals", json=payload)

    assert response.status_code == 400, response.text
    assert response.json()["detail"]["code"] == "PLAN_PURPOSE_UNSUPPORTED"


def test_road_and_trail_proposals_remain_distinguishable(proposal_client):
    client, _, _ = proposal_client
    start = date.today() + timedelta(days=2)
    road_workout = {
        "date": start.isoformat(),
        "activity_type": "running",
        "workout_type": "easy",
        "planned_duration_min": 60,
        "workout_structure_version": "v1",
        "workout_structure": _structure(_time_step(60)),
    }
    trail_workout = {
        **road_workout,
        "activity_type": "trail_running",
    }

    road = client.post(
        "/api/plan/proposals",
        json=_proposal_payload(
            key="road-proposal",
            discipline="running",
            workouts=[road_workout],
        ),
    )
    assert road.status_code == 201, road.text
    road_body = road.json()
    assert road_body["discipline"] == "running"
    assert road_body["workouts"][0]["activity_type"] == "running"

    rejected = client.post(
        f"/api/plan/proposals/{road_body['id']}/reject",
        json={"expected_version": 1, "idempotency_key": "road-reject"},
    )
    assert rejected.status_code == 200, rejected.text

    trail = client.post(
        "/api/plan/proposals",
        json=_proposal_payload(
            key="trail-proposal",
            discipline="trail_running",
            workouts=[trail_workout],
        ),
    )
    assert trail.status_code == 201, trail.text
    trail_body = trail.json()
    assert trail_body["discipline"] == "trail_running"
    assert trail_body["workouts"][0]["activity_type"] == "trail_running"
    assert road_body["workouts"][0]["planned_duration_min"] == (
        trail_body["workouts"][0]["planned_duration_min"]
    )


def test_structured_workout_round_trips_through_adoption_and_replay(proposal_client):
    client, db_session, _ = proposal_client
    start = date.today() + timedelta(days=3)
    trail_structure = _structure(
        _time_step(
            15,
            phase="warmup",
            label="Trail warm-up",
            instructions="Stay relaxed on the first climb.",
        ),
        _repeat_group(
            3,
            _time_step(
                4,
                phase="work",
                label="Uphill power",
                instructions="Strong form—quick feet, quiet shoulders.",
                target=_target(
                    "power",
                    "percent_cp",
                    "critical_power",
                    minimum=90,
                    maximum=95,
                ),
            ),
            _time_step(
                3,
                phase="recovery",
                label="Float down",
                instructions="Keep moving; do not chase pace.",
            ),
            label="Main set",
        ),
        _time_step(
            10,
            phase="cooldown",
            label="Easy finish",
            instructions="Let effort fall naturally.",
        ),
    )
    payload = _proposal_payload(
        key="trail-structured-create",
        discipline="trail_running",
        workouts=[
            {
                "date": start.isoformat(),
                "activity_type": "trail_running",
                "workout_type": "interval",
                "workout_description": "Trail hill session",
                "workout_structure_version": "v1",
                "workout_structure": trail_structure,
            },
            {
                "date": (start + timedelta(days=1)).isoformat(),
                "activity_type": "rest",
                "workout_type": "rest",
                "workout_structure_version": "v1",
                "workout_structure": _structure(),
            },
        ],
    )
    created = client.post("/api/plan/proposals", json=payload)

    assert created.status_code == 201, created.text
    created_body = created.json()
    assert created_body["discipline"] == "trail_running"
    assert created_body["adaptive_plan"]["discipline"] == "trail_running"
    assert created_body["workouts"][0]["activity_type"] == "trail_running"
    assert created_body["workouts"][0]["workout_structure_version"] == "v1"
    assert created_body["workouts"][0]["workout_structure"] == trail_structure
    assert created_body["workouts"][0]["planned_duration_min"] == 46
    assert created_body["workouts"][0]["planned_distance_km"] is None
    assert created_body["workouts"][0]["target_power_min"] is None
    assert created_body["workouts"][1]["activity_type"] == "rest"
    assert created_body["workouts"][1]["workout_structure"]["steps"] == []
    assert created_body["workouts"][1]["planned_duration_min"] is None

    current = client.get("/api/plan/proposals/current")
    assert current.status_code == 200, current.text
    assert current.json()["workouts"][0]["workout_structure"] == trail_structure

    edited_structure = copy.deepcopy(trail_structure)
    edited_structure["steps"][1]["label"] = "Main set — revised"
    edited_structure["steps"][1]["steps"][0]["instructions"] = (
        "Strong form—quick feet, quiet shoulders; hold back on rep one."
    )
    edit_payload = copy.deepcopy(payload)
    edit_payload["idempotency_key"] = "trail-structured-edit"
    edit_payload["expected_version"] = created_body["version"]
    edit_payload["workouts"][0]["workout_structure"] = edited_structure
    edited = client.post(
        f"/api/plan/proposals/{created_body['id']}/edits",
        json=edit_payload,
    )
    assert edited.status_code == 201, edited.text
    edited_body = edited.json()
    assert edited_body["version"] == created_body["version"] + 1
    assert edited_body["workouts"][0]["workout_structure"] == edited_structure
    assert created_body["workouts"][0]["workout_structure"] == trail_structure

    adopted = client.post(
        f"/api/plan/proposals/{edited_body['id']}/adopt",
        json={
            "expected_proposal_version": edited_body["version"],
            "expected_plan_version": edited_body["adaptive_plan"]["version"],
            "idempotency_key": "trail-structured-adopt",
        },
    )

    assert adopted.status_code == 200, adopted.text
    adopt_body = adopted.json()
    assert adopt_body["status"] == "adopted"
    assert adopt_body["proposal"]["discipline"] == "trail_running"
    assert adopt_body["workouts"][0]["activity_type"] == "trail_running"
    assert adopt_body["workouts"][0]["workout_structure_version"] == "v1"
    assert adopt_body["workouts"][0]["workout_structure"] == edited_structure
    assert adopt_body["workouts"][1]["workout_structure"]["steps"] == []

    from db.models import PlanProposal, PlanRevision, TrainingPlan
    from db.plan_ledger import workout_version

    db = db_session.SessionLocal()
    try:
        plans = (
            db.query(TrainingPlan)
            .filter(TrainingPlan.user_id == "proposal-owner")
            .order_by(TrainingPlan.date)
            .all()
        )
        assert plans[0].activity_type == "trail_running"
        assert plans[0].workout_structure_version == "v1"
        assert plans[0].workout_structure == edited_structure
        assert plans[1].activity_type == "rest"
        assert plans[1].workout_structure == {"steps": []}
        immutable_parent = db.query(PlanProposal).filter(
            PlanProposal.id == created_body["id"]
        ).one()
        assert (
            immutable_parent.workout_snapshot[0]["workout_structure"]
            == trail_structure
        )
        revision = (
            db.query(PlanRevision)
            .filter(PlanRevision.idempotency_key == "trail-structured-adopt")
            .one()
        )
        assert revision.after_snapshot[0]["activity_type"] == "trail_running"
        assert revision.after_snapshot[0]["workout_structure_version"] == "v1"
        assert (
            revision.after_snapshot[0]["workout_structure"]
            == edited_structure
        )
        assert workout_version(revision.after_snapshot[0]) == workout_version(
            adopt_body["workouts"][0]
        )
    finally:
        db.close()

    replacement = client.post(
        "/api/plan/proposals",
        json=_proposal_payload(
            key="trail-structured-replacement",
            discipline="running",
            workouts=[
                {
                    "date": start.isoformat(),
                    "activity_type": "running",
                    "workout_type": "easy",
                    "workout_structure_version": "v1",
                    "workout_structure": _structure(_time_step(30)),
                }
            ],
        ),
    )
    assert replacement.status_code == 201, replacement.text
    replacement_body = replacement.json()

    replacement_adopt = client.post(
        f"/api/plan/proposals/{replacement_body['id']}/adopt",
        json={
            "expected_proposal_version": replacement_body["version"],
            "expected_plan_version": replacement_body["adaptive_plan"]["version"],
            "idempotency_key": "trail-structured-replacement-adopt",
        },
    )
    assert replacement_adopt.status_code == 200, replacement_adopt.text

    replay = client.post(
        f"/api/plan/proposals/{edited_body['id']}/adopt",
        json={
            "expected_proposal_version": edited_body["version"],
            "expected_plan_version": 0,
            "idempotency_key": "trail-structured-adopt",
        },
    )
    assert replay.status_code == 200, replay.text
    replay_body = replay.json()
    assert replay_body["status"] == "already_adopted"
    assert replay_body["proposal"]["discipline"] == "trail_running"
    assert replay_body["workouts"][0]["activity_type"] == "trail_running"
    assert replay_body["workouts"][0]["workout_structure"] == edited_structure
    assert replay_body["workouts"][1]["workout_structure"] == {"steps": []}


def test_workout_wording_normalization_limits_and_openapi_are_private(
    proposal_client,
):
    client, _, _ = proposal_client
    from api.plan_workout_structure import (
        WORKOUT_INSTRUCTIONS_MAX_LENGTH,
        WORKOUT_LABEL_MAX_LENGTH,
    )

    start = date.today() + timedelta(days=2)
    blank_structure = _structure(
        _time_step(
            5,
            phase="work",
            label=" \t ",
            instructions="\n ",
        ),
        _repeat_group(
            2,
            _time_step(1, phase="recovery"),
            label="  ",
        ),
    )
    blank = client.post(
        "/api/plan/proposals",
        json=_proposal_payload(
            key="blank-wording",
            workouts=[{
                "date": start.isoformat(),
                "workout_type": "interval",
                "workout_structure_version": "v1",
                "workout_structure": blank_structure,
            }],
        ),
    )
    assert blank.status_code == 201, blank.text
    normalized_nodes = blank.json()["workouts"][0]["workout_structure"]["steps"]
    assert "label" not in normalized_nodes[0]
    assert "instructions" not in normalized_nodes[0]
    assert "label" not in normalized_nodes[1]

    too_long_cases = [
        (
            "step-label",
            _structure(_time_step(
                5,
                phase="work",
                label="private-label-" + "界" * WORKOUT_LABEL_MAX_LENGTH,
            )),
            "private-label-",
        ),
        (
            "step-instructions",
            _structure(_time_step(
                5,
                phase="work",
                instructions=(
                    "private-instructions-"
                    + "界" * WORKOUT_INSTRUCTIONS_MAX_LENGTH
                ),
            )),
            "private-instructions-",
        ),
        (
            "repeat-label",
            _structure(_repeat_group(
                2,
                _time_step(1, phase="work"),
                label=(
                    "private-repeat-"
                    + "界" * WORKOUT_LABEL_MAX_LENGTH
                ),
            )),
            "private-repeat-",
        ),
    ]
    for suffix, structure, private_marker in too_long_cases:
        response = client.post(
            "/api/plan/proposals",
            json=_proposal_payload(
                key=f"overlong-{suffix}",
                workouts=[{
                    "date": start.isoformat(),
                    "workout_type": "interval",
                    "workout_structure_version": "v1",
                    "workout_structure": structure,
                }],
            ),
        )
        assert response.status_code == 422, response.text
        detail = response.json()["detail"]
        assert detail["code"] == "PLAN_PROPOSAL_VALIDATION_FAILED"
        assert any(
            error["type"] == "string_too_long"
            and "workout_structure" in error["field"]
            for error in detail["errors"]
        )
        assert private_marker not in response.text

    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    step_schema = schemas["StructuredWorkoutStepV1"]["properties"]
    repeat_schema = schemas["StructuredWorkoutRepeatGroupV1"]["properties"]

    def _string_limit(schema: dict) -> int | None:
        candidates = schema.get("anyOf", [schema])
        return next(
            (
                candidate.get("maxLength")
                for candidate in candidates
                if candidate.get("type") == "string"
            ),
            None,
        )

    assert _string_limit(step_schema["label"]) == WORKOUT_LABEL_MAX_LENGTH
    assert (
        _string_limit(step_schema["instructions"])
        == WORKOUT_INSTRUCTIONS_MAX_LENGTH
    )
    assert _string_limit(repeat_schema["label"]) == WORKOUT_LABEL_MAX_LENGTH
    assert set(step_schema["phase"]["enum"]) == {
        "warmup",
        "work",
        "recovery",
        "rest",
        "cooldown",
        "other",
    }


def test_proposal_validation_rejects_invalid_structure_and_target_units(proposal_client):
    client, _, _ = proposal_client
    start = date.today() + timedelta(days=2)

    missing_steps = client.post(
        "/api/plan/proposals",
        json=_proposal_payload(
            key="missing-steps",
            workouts=[
                {
                    "date": start.isoformat(),
                    "activity_type": "running",
                    "workout_type": "easy",
                    "workout_structure_version": "v1",
                    "workout_structure": _structure(),
                }
            ],
        ),
    )
    assert missing_steps.status_code == 422
    missing_steps_detail = missing_steps.json()["detail"]
    assert missing_steps_detail["code"] == "PLAN_PROPOSAL_VALIDATION_FAILED"
    assert all(set(item) == {"field", "type"} for item in missing_steps_detail["errors"])
    assert any(
        item["field"].startswith("workouts.0.workout_structure")
        for item in missing_steps_detail["errors"]
    )

    invalid_target = client.post(
        "/api/plan/proposals",
        json=_proposal_payload(
            key="invalid-target-combo",
            workouts=[
                {
                    "date": start.isoformat(),
                    "activity_type": "running",
                    "workout_type": "easy",
                    "workout_structure_version": "v1",
                    "workout_structure": _structure(
                        _time_step(
                            20,
                            target={
                                "metric": "power",
                                "unit": "bpm",
                                "reference": "absolute",
                                "min": 180,
                            },
                        )
                    ),
                }
            ],
        ),
    )
    assert invalid_target.status_code == 422
    invalid_target_detail = invalid_target.json()["detail"]
    assert invalid_target_detail["code"] == "PLAN_PROPOSAL_VALIDATION_FAILED"
    assert all(set(item) == {"field", "type"} for item in invalid_target_detail["errors"])
    assert any(
        item["field"].startswith("workouts.0.workout_structure")
        for item in invalid_target_detail["errors"]
    )


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


@pytest.mark.parametrize(
    "mutation",
    ["upload", "upsert", "delete", "reconciliation", "wording_update"],
)
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
            json={
                "workout_type": "easy",
                "planned_duration_min": 45,
                "workout_description": "Upserted note",
            },
        )
        assert changed.status_code == 200, changed.text
    elif mutation == "delete":
        changed = client.delete(f"/api/plan/{start.isoformat()}")
        assert changed.status_code == 200, changed.text
        assert changed.json()["rows"] == 1
    elif mutation == "reconciliation":
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
    else:
        from db.models import TrainingPlan
        from db.plan_ledger import plan_snapshot, workout_version

        db = db_session.SessionLocal()
        try:
            canonical = db.query(TrainingPlan).filter(
                TrainingPlan.user_id == "proposal-owner",
                TrainingPlan.date == start,
            ).one()
            canonical_id = canonical.canonical_id
            expected_workout_version = workout_version(
                plan_snapshot(canonical)
            )
            structure = copy.deepcopy(canonical.workout_structure)
        finally:
            db.close()
        structure["steps"][0]["label"] = "Updated athlete label"
        structure["steps"][0]["instructions"] = (
            "Preserve this exact coaching cue."
        )
        changed = client.put(
            f"/api/plan/workouts/{canonical_id}",
            json={
                "expected_version": expected_workout_version,
                "workout_structure_version": "v1",
                "workout_structure": structure,
            },
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["workout_version"] != expected_workout_version

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
