"""GET /api/plan window-framing + sync_state derivation.

Covers the contract change in the Plan reshape:

- The canonical plan is the Praxys-owned one; Stryd plan
  rows in the same window become `sync_state` flags on Praxys rows that share
  a date and `stryd_only_dates` for orphan Stryd rows.
- ``?start=&end=`` clamps the response window and is salted into the
  ETag so two clients on different windows can't bleed cache.
- ``cp_current`` was retired — its presence here would mean a partial
  revert of the reshape.
"""
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest

from analysis.config import (
    PRAXYS_PLAN_SOURCE,
    PRAXYS_PLAN_SOURCES,
    PRAXYS_PLAN_WRITE_SOURCE,
)


@pytest.fixture
def api_client(monkeypatch):
    from fastapi.testclient import TestClient

    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", tmpdir.name)
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv(
        "PRAXYS_GARMIN_PLAN_DELIVERY_ENABLED",
        "true",
    )
    monkeypatch.setattr(
        "api.statsig_client.check_gate",
        lambda gate_name, _user: gate_name
        == "garmin_plan_delivery_eligible",
    )
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )
    monkeypatch.setenv("PRAXYS_JWT_SECRET", "test-secret-plan-sync-state")

    from db import session as db_session
    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    from api.routes import plan as plan_mod
    scratch_root = os.path.join(tmpdir.name, "ai", "stryd_push_status")
    monkeypatch.setattr(plan_mod, "_DATA_DIR", tmpdir.name)
    monkeypatch.setattr(plan_mod, "_STRYD_PUSH_STATUS_DIR", scratch_root)

    from api.main import app
    from api.auth import (
        get_current_user_id, get_data_user_id, require_write_access,
    )
    from db.session import get_db

    user_id = "test-user-plan-sync-state"
    from db.models import User

    seed_db = db_session.SessionLocal()
    try:
        seed_db.add(User(
            id=user_id,
            email="plan-sync-state@example.test",
            hashed_password="test",
        ))
        seed_db.commit()
    finally:
        seed_db.close()

    def _override_user():
        return user_id

    def _override_db():
        db = db_session.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_current_user_id] = _override_user
    app.dependency_overrides[get_data_user_id] = _override_user
    app.dependency_overrides[require_write_access] = _override_user
    app.dependency_overrides[get_db] = _override_db

    client = TestClient(app)
    try:
        yield client, user_id
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


def _seed_rows(user_id: str, rows: list[dict]) -> None:
    """Insert TrainingPlan rows. Each dict needs date/source/workout_type."""
    from db import session as db_session
    from db.models import TrainingPlan

    db = db_session.SessionLocal()
    try:
        for r in rows:
            db.add(TrainingPlan(
                user_id=user_id,
                date=r["date"],
                source=r["source"],
                workout_type=r.get("workout_type", ""),
                workout_description=r.get("workout_description", ""),
                external_id=r.get("external_id"),
                planned_duration_min=r.get("planned_duration_min"),
            ))
        db.commit()
    finally:
        db.close()


def _seed_synced_delivery(
    user_id: str,
    workout_date: date,
    workout_type: str,
    external_id: str,
    *,
    workout_description: str = "",
    provider_content_version: str | None = None,
    provider_account_id: str | None = None,
    canonical_id: str | None = None,
    target: str = "stryd",
) -> str:
    """Persist one successful delivery for the current Praxys version."""
    from db import session as db_session
    from db.plan_ledger import (
        begin_delivery_attempt,
        complete_delivery_attempt,
        get_or_create_delivery,
    )

    db = db_session.SessionLocal()
    try:
        delivery, _ = get_or_create_delivery(
            db,
            user_id=user_id,
            target=target,
            snapshot={
                "canonical_id": canonical_id,
                "date": workout_date,
                "source": "ai",
                "workout_type": workout_type,
                "workout_description": workout_description,
            },
        )
        delivery.provider_content_version = provider_content_version
        delivery, attempt, disposition = begin_delivery_attempt(
            db,
            delivery,
            operation="deliver",
        )
        assert disposition == "started"
        assert attempt is not None
        complete_delivery_attempt(
            db,
            user_id=user_id,
            delivery_id=delivery.id,
            attempt_id=attempt.id,
            attempt_state="synced",
            external_id=external_id,
            provider_account_id=provider_account_id,
        )
        db.commit()
        delivery_id = delivery.id
    finally:
        db.close()
    return delivery_id


def test_plan_exposes_adjustment_history_and_exact_undo(api_client):
    client, user_id = api_client
    from db import session as db_session
    from db.models import TrainingPlan
    from db.plan_ledger import plan_snapshot, record_plan_revision

    today = date.today()
    db = db_session.SessionLocal()
    try:
        plan = TrainingPlan(
            user_id=user_id,
            date=today,
            source="praxys",
            workout_origin="generated",
            workout_type="threshold",
            planned_duration_min=50,
            workout_description="Threshold repeats",
        )
        db.add(plan)
        db.flush()
        before = plan_snapshot(plan)
        plan.workout_type = "rest"
        plan.planned_duration_min = None
        plan.workout_description = "Rest after current HRV caution"
        after = plan_snapshot(plan)
        revision = record_plan_revision(
            db,
            user_id=user_id,
            operation="auto_adjustment",
            actor_type="system",
            actor_id="conservative-adjustment-v1",
            origin="api.plan_adjustments",
            before=[before],
            after=[after],
            details={
                "rule": {
                    "id": "hrv_below_hard_to_rest",
                    "version": "1",
                },
                "reason_code": "hrv_below_hard",
                "rationale": "Current HRV crossed the personal caution band.",
                "evidence": {"hrv_latest_date": today.isoformat()},
                "bounds": {"workouts_changed": 1},
                "citations": [],
                "delivery": {"status": "pending"},
            },
            idempotency_key=f"auto-adjust:1:{plan.canonical_id}:{today}",
        )
        db.commit()
        revision_id = revision.id
    finally:
        db.close()

    plan_response = client.get(
        f"/api/plan?start={today.isoformat()}&end={today.isoformat()}"
    )
    history_response = client.get("/api/plan/adjustments")
    undo_response = client.post(
        f"/api/plan/adjustments/{revision_id}/undo"
    )

    assert plan_response.status_code == 200, plan_response.text
    assert plan_response.json()["adjustments"][0]["id"] == revision_id
    assert history_response.status_code == 200, history_response.text
    assert history_response.json()["items"][0]["can_undo"] is True
    assert undo_response.status_code == 200, undo_response.text
    assert undo_response.json()["status"] == "undone"

    db = db_session.SessionLocal()
    try:
        restored = db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
        ).one()
        assert restored.workout_type == "threshold"
        assert restored.planned_duration_min == 50
    finally:
        db.close()


def _seed_target_snapshot(
    user_id: str,
    rows: list[dict],
    *,
    provider_account_id: str = "stryd-account",
    target: str = "stryd",
) -> None:
    """Persist one authoritative execution-target calendar snapshot."""
    from db import session as db_session
    from db.plan_reconciliation import record_target_calendar_sync

    db = db_session.SessionLocal()
    try:
        record_target_calendar_sync(
            db,
            user_id=user_id,
            target=target,
            provider_account_id=provider_account_id,
            rows=rows,
            window_start=date.today() - timedelta(days=1),
            window_end=date.today() + timedelta(days=30),
            observed_at=datetime.utcnow(),
        )
        db.commit()
    finally:
        db.close()


def test_get_plan_returns_window_with_source_tag(api_client):
    """Both AI and Stryd plan rows in the window come back, each tagged
    with its ``source`` so the UI can label them. Past and far-future
    rows are clipped by the default [today, +14d] window.
    """
    client, user_id = api_client
    today = date.today()
    ai_day = today + timedelta(days=2)
    stryd_day = today + timedelta(days=4)
    out_of_window = today + timedelta(days=30)

    _seed_rows(user_id, [
        {"date": ai_day, "source": "ai", "workout_type": "easy"},
        {"date": stryd_day, "source": "stryd", "workout_type": "tempo"},
        # Past AI row — out of the default forward window.
        {"date": today - timedelta(days=2), "source": "ai", "workout_type": "rest"},
        # Future AI row beyond the default 14-day window.
        {"date": out_of_window, "source": "ai", "workout_type": "long_run"},
    ])

    res = client.get("/api/plan")
    assert res.status_code == 200, res.text
    body = res.json()
    workouts = body["workouts"]
    # Both in-window rows surface, sorted by date and tagged by source.
    assert [(w["date"], w["source"]) for w in workouts] == [
        (ai_day.isoformat(), "ai"),
        (stryd_day.isoformat(), "stryd"),
    ]
    assert [(w["owner"], w["origin"]) for w in workouts] == [
        ("praxys", "legacy"),
        ("external", "imported"),
    ]
    # The retired ``cp_current`` field must not return.
    assert "cp_current" not in body
    # Window echo helps clients page without restating the math themselves.
    assert body["window"] == {
        "start": today.isoformat(),
        "end": (today + timedelta(days=14)).isoformat(),
    }


def test_ai_row_takes_precedence_when_date_collides(api_client):
    """An unowned same-date target row remains visible as an overlap."""
    client, user_id = api_client
    target = date.today() + timedelta(days=2)
    _seed_rows(user_id, [
        {"date": target, "source": "ai", "workout_type": "threshold"},
        {"date": target, "source": "stryd", "workout_type": "tempo_stryd"},
    ])
    body = client.get("/api/plan").json()
    workouts = body["workouts"]
    assert [(row["owner"], row["workout_type"]) for row in workouts] == [
        ("praxys", "threshold"),
        ("external", "tempo_stryd"),
    ]
    assert all(row["external_overlap"] is True for row in workouts)
    assert body["management"]["external_overlap_dates"] == [
        target.isoformat(),
    ]


def test_sync_state_synced_when_external_id_matches_push_log(api_client):
    """An AI row + Stryd row at the same date with matching ids → ``synced``."""
    client, user_id = api_client
    target = date.today() + timedelta(days=3)
    _seed_synced_delivery(user_id, target, "threshold", "stryd-abc")
    _seed_rows(user_id, [
        {"date": target, "source": "ai", "workout_type": "threshold"},
        {
            "date": target, "source": "stryd",
            "workout_type": "threshold", "external_id": "stryd-abc",
        },
    ])

    body = client.get("/api/plan").json()
    assert body["workouts"][0]["sync_state"] == "synced"


def test_fallback_keeps_conflict_delivery_target_owned(api_client):
    """A non-removed delivery external ID never becomes an external overlap."""
    client, user_id = api_client
    target = date.today() + timedelta(days=3)
    _seed_synced_delivery(user_id, target, "threshold", "stryd-ambiguous")

    from db import session as db_session
    from db.models import PlanDelivery

    db = db_session.SessionLocal()
    try:
        delivery = db.query(PlanDelivery).filter(
            PlanDelivery.user_id == user_id,
            PlanDelivery.external_id == "stryd-ambiguous",
        ).one()
        delivery.state = "conflict"
        db.commit()
    finally:
        db.close()

    _seed_rows(user_id, [
        {"date": target, "source": "ai", "workout_type": "threshold"},
        {
            "date": target,
            "source": "stryd",
            "workout_type": "threshold",
            "external_id": "stryd-ambiguous",
        },
    ])

    body = client.get("/api/plan").json()
    assert len(body["workouts"]) == 1
    assert body["workouts"][0]["owner"] == "praxys"
    assert body["workouts"][0]["external_overlap"] is False
    assert body["management"]["external_overlap_dates"] == []


def test_fallback_keeps_moved_delivery_target_owned_across_window(
    api_client,
):
    """Delivery identity stays owned when the provider moves its date."""
    client, user_id = api_client
    visible_date = date.today() + timedelta(days=3)
    original_date = date.today() + timedelta(days=30)
    _seed_synced_delivery(
        user_id,
        original_date,
        "threshold",
        "stryd-moved-across-window",
    )
    _seed_rows(user_id, [
        {
            "date": visible_date,
            "source": "ai",
            "workout_type": "easy",
        },
        {
            "date": visible_date,
            "source": "stryd",
            "workout_type": "threshold",
            "external_id": "stryd-moved-across-window",
        },
    ])

    body = client.get(
        "/api/plan",
        params={
            "start": visible_date.isoformat(),
            "end": visible_date.isoformat(),
        },
    ).json()

    assert len(body["workouts"]) == 1
    assert body["workouts"][0]["owner"] == "praxys"
    assert body["workouts"][0]["external_overlap"] is False
    assert body["management"]["external_overlap_dates"] == []


def test_sync_state_mismatch_when_external_id_diverges(api_client):
    """Stryd row exists but its id doesn't match the push log → ``mismatch``.

    This is the case the UI must catch before re-pushing — typically the
    user edited the workout directly inside Stryd's calendar.
    """
    client, user_id = api_client
    target = date.today() + timedelta(days=4)
    _seed_synced_delivery(user_id, target, "intervals", "stryd-old")
    _seed_rows(user_id, [
        {"date": target, "source": "ai", "workout_type": "intervals"},
        {
            "date": target, "source": "stryd",
            "workout_type": "intervals", "external_id": "stryd-edited",
        },
    ])

    body = client.get("/api/plan").json()
    assert body["workouts"][0]["sync_state"] == "mismatch"


def test_sync_state_synced_when_pushed_but_stryd_not_yet_resynced(api_client):
    """The brief window after a successful push but before the next
    Stryd sync pulls the row back in: push log has the workout_id but
    no Stryd row exists yet. Must read as ``synced`` for consumers
    that don't share the frontend's optimistic ``pushStatus`` map
    (mini-program, MCP). Otherwise they'd offer to push again.
    """
    client, user_id = api_client
    target = date.today() + timedelta(days=6)
    _seed_synced_delivery(user_id, target, "easy", "stryd-just-pushed")
    _seed_rows(user_id, [
        {"date": target, "source": "ai", "workout_type": "easy"},
    ])
    body = client.get("/api/plan").json()
    assert body["workouts"][0]["sync_state"] == "synced"


def test_sync_state_uses_workout_type_match_when_multiple_stryd_rows(api_client):
    """Stryd allows multiple workouts on the same date (AM run + PM
    strides, race + shakeout). The AI sync_state derivation must
    pick the row whose ``workout_type`` matches the AI row, not
    arbitrarily the last-iterated one.
    """
    client, user_id = api_client
    target = date.today() + timedelta(days=2)
    _seed_synced_delivery(user_id, target, "threshold", "stryd-threshold")
    _seed_rows(user_id, [
        # AI plan: a threshold workout.
        {"date": target, "source": "ai", "workout_type": "threshold"},
        # Stryd has *both* the matched threshold (with our pushed id)
        # AND an unrelated easy run added by the user. Without the
        # workout_type-match, the easy row could collapse the threshold
        # row in stryd_by_date and the AI row would mis-read mismatch.
        {
            "date": target, "source": "stryd",
            "workout_type": "easy", "external_id": "stryd-other-easy",
        },
        {
            "date": target, "source": "stryd",
            "workout_type": "threshold", "external_id": "stryd-threshold",
        },
    ])
    body = client.get("/api/plan").json()
    ai_row = next(w for w in body["workouts"] if w["source"] == "ai")
    assert ai_row["sync_state"] == "synced"
    external_rows = [
        workout
        for workout in body["workouts"]
        if workout["owner"] == "external"
    ]
    assert [row["workout_type"] for row in external_rows] == ["easy"]
    assert ai_row["external_overlap"] is True
    assert external_rows[0]["external_overlap"] is True
    assert body["management"]["external_overlap_dates"] == [
        target.isoformat(),
    ]


def test_sync_state_not_synced_when_no_stryd_row(api_client):
    client, user_id = api_client
    target = date.today() + timedelta(days=5)
    _seed_rows(user_id, [
        {"date": target, "source": "ai", "workout_type": "easy"},
    ])
    body = client.get("/api/plan").json()
    assert body["workouts"][0]["sync_state"] == "not_synced"


def test_changed_workout_version_preserves_prior_external_id_for_replacement(
    api_client,
):
    client, user_id = api_client
    target = date.today() + timedelta(days=5)
    _seed_synced_delivery(
        user_id,
        target,
        "easy",
        "stryd-old-version",
        workout_description="Original prescription",
    )
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "easy",
        "workout_description": "Adjusted prescription",
    }])

    body = client.get("/api/plan").json()
    assert body["workouts"][0]["sync_state"] == "not_synced"
    assert body["stryd_status"][target.isoformat()]["workout_id"] == "stryd-old-version"


def test_stryd_only_row_surfaces_with_source_tag(api_client):
    """A Stryd row with no AI counterpart still appears in ``workouts``
    so the user sees their imported / coach-authored workouts. It carries
    ``source='stryd'`` and no ``sync_state`` (it lives natively on Stryd
    so the AI-vs-Stryd sync question doesn't apply).
    """
    client, user_id = api_client
    ai_day = date.today() + timedelta(days=2)
    orphan_day = date.today() + timedelta(days=4)
    _seed_rows(user_id, [
        {"date": ai_day, "source": "ai", "workout_type": "easy"},
        {"date": orphan_day, "source": "stryd", "workout_type": "race"},
    ])
    workouts = client.get("/api/plan").json()["workouts"]
    by_date = {w["date"]: w for w in workouts}
    assert by_date[ai_day.isoformat()]["source"] == "ai"
    stryd_row = by_date[orphan_day.isoformat()]
    assert stryd_row["source"] == "stryd"
    assert "sync_state" not in stryd_row


def test_legacy_stryd_row_without_external_id_survives_reconciliation(
    api_client,
):
    client, user_id = api_client
    target = date.today() + timedelta(days=4)
    _seed_rows(user_id, [{
        "date": target,
        "source": "stryd",
        "workout_type": "legacy coach workout",
    }])
    _seed_target_snapshot(user_id, [])

    workouts = client.get("/api/plan").json()["workouts"]

    assert len(workouts) == 1
    assert workouts[0]["source"] == "stryd"
    assert workouts[0]["workout_type"] == "legacy coach workout"
    assert "reconciliation" not in workouts[0]


def test_window_query_params_clamp_response(api_client):
    client, user_id = api_client
    today = date.today()
    near = today + timedelta(days=2)
    far = today + timedelta(days=20)
    _seed_rows(user_id, [
        {"date": near, "source": "ai", "workout_type": "easy"},
        {"date": far, "source": "ai", "workout_type": "long_run"},
    ])

    res = client.get(
        f"/api/plan?start={today.isoformat()}&end={(today + timedelta(days=7)).isoformat()}"
    )
    assert res.status_code == 200
    near_only = res.json()
    assert [w["date"] for w in near_only["workouts"]] == [near.isoformat()]

    res = client.get(
        f"/api/plan?start={today.isoformat()}&end={far.isoformat()}"
    )
    assert res.status_code == 200
    both = res.json()
    assert [w["date"] for w in both["workouts"]] == [
        near.isoformat(), far.isoformat(),
    ]


def test_window_etag_does_not_collide_across_windows(api_client):
    """Different windows must hash to different ETags — otherwise a 304
    revalidation would replay the wrong window's body."""
    client, _ = api_client
    today = date.today()
    a = client.get(f"/api/plan?start={today.isoformat()}&end={(today + timedelta(days=7)).isoformat()}")
    b = client.get(f"/api/plan?start={today.isoformat()}&end={(today + timedelta(days=21)).isoformat()}")
    assert a.headers["etag"] != b.headers["etag"]


def test_invalid_window_returns_400(api_client):
    client, _ = api_client
    today = date.today()
    inverted = client.get(
        f"/api/plan?start={today.isoformat()}&end={(today - timedelta(days=1)).isoformat()}"
    )
    assert inverted.status_code == 400

    bad_format = client.get("/api/plan?start=not-a-date")
    assert bad_format.status_code == 400


def test_oversized_window_returns_400(api_client):
    """Cap is 365 days. ``?end=2099-12-31`` against today shouldn't
    force the server to ship a multi-year payload — the cap should
    reject it with a clear 400 instead of silently clamping."""
    client, _ = api_client
    today = date.today()
    huge = client.get(
        f"/api/plan?start={today.isoformat()}&end={(today + timedelta(days=400)).isoformat()}"
    )
    assert huge.status_code == 400, huge.text
    assert "365" in huge.text


def test_nullable_workout_type_serializes_as_empty_string(api_client):
    """Legacy nullable plan rows preserve the non-null API contract."""
    client, user_id = api_client
    target = date.today() + timedelta(days=2)
    _seed_rows(user_id, [{
        "date": target,
        "source": "stryd",
        "workout_type": None,
    }])

    body = client.get("/api/plan").json()
    assert body["workouts"][0]["workout_type"] == ""



def test_sync_target_reflects_connection_and_invalidates_etag(api_client):
    """A real connection mutation updates both Plan content and its ETag."""
    client, _ = api_client

    cold = client.get("/api/plan")
    assert cold.status_code == 200
    assert cold.json()["sync_target"] is None
    cold_etag = cold.headers["etag"]

    connected = client.post(
        "/api/settings/connections/stryd",
        json={"email": "runner@example.com", "password": "test-password"},
    )
    assert connected.status_code == 200
    assert connected.json()["status"] == "connected"

    after_connect = client.get(
        "/api/plan", headers={"If-None-Match": cold_etag},
    )
    assert after_connect.status_code == 200
    assert after_connect.headers["etag"] != cold_etag
    assert after_connect.json()["sync_target"] == "stryd"

    disconnected = client.delete("/api/settings/connections/stryd")
    assert disconnected.status_code == 200

    after_disconnect = client.get(
        "/api/plan",
        headers={"If-None-Match": after_connect.headers["etag"]},
    )
    assert after_disconnect.status_code == 200
    assert after_disconnect.headers["etag"] != after_connect.headers["etag"]
    assert after_disconnect.json()["sync_target"] is None


def test_reconciliation_matches_external_id_and_content(api_client):
    client, user_id = api_client
    target = date.today() + timedelta(days=2)
    fingerprint = "a" * 64
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "threshold",
    }])
    _seed_synced_delivery(
        user_id,
        target,
        "threshold",
        "stryd-match",
        provider_content_version=fingerprint,
        provider_account_id="stryd-account",
    )
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "threshold",
        "external_id": "stryd-match",
        "provider_content_fingerprint": fingerprint,
        "provider_payload_fingerprint": "b" * 64,
    }])

    workout = client.get("/api/plan").json()["workouts"][0]
    assert workout["sync_state"] == "synced"
    assert workout["reconciliation"]["state"] == "matching"
    assert workout["reconciliation"]["conflict"] is False
    assert workout["reconciliation"]["match_basis"] == "external_id"


def test_reconciliation_uses_configured_garmin_execution_target(api_client):
    client, user_id = api_client
    target_date = date.today() + timedelta(days=2)
    fingerprint = "a" * 64
    _seed_rows(user_id, [{
        "date": target_date,
        "source": "praxys",
        "workout_type": "easy",
    }])

    from analysis.config import load_config_from_db, save_config_to_db
    from db import session as db_session

    db = db_session.SessionLocal()
    try:
        config = load_config_from_db(user_id, db)
        config.plan_management = {
            "mode": "praxys",
            "execution_target": "garmin",
            "delivery_enabled": False,
            "adjustment_policy": "suggest_only",
        }
        save_config_to_db(user_id, config, db)
    finally:
        db.close()

    _seed_synced_delivery(
        user_id,
        target_date,
        "easy",
        "garmin-schedule-7001",
        provider_content_version=fingerprint,
        provider_account_id="garmin-account",
        target="garmin",
    )
    _seed_synced_delivery(
        user_id,
        target_date,
        "easy",
        "stryd-workout-41",
        target="stryd",
    )
    _seed_target_snapshot(
        user_id,
        [{
            "date": target_date.isoformat(),
            "workout_type": "easy",
            "external_id": "garmin-schedule-7001",
            "provider_references": {"template_id": "9001"},
            "provider_content_fingerprint": fingerprint,
            "provider_payload_fingerprint": "b" * 64,
        }],
        provider_account_id="garmin-account",
        target="garmin",
    )

    body = client.get("/api/plan").json()

    assert body["sync_target"] == "garmin"
    assert body["workouts"][0]["reconciliation"]["state"] == "matching"
    assert body["workouts"][0]["reconciliation"]["target"] == "garmin"
    assert (
        body["stryd_status"][target_date.isoformat()]["workout_id"]
        == "stryd-workout-41"
    )

    from db.models import PlanTargetWorkout

    db = db_session.SessionLocal()
    try:
        observation = db.query(PlanTargetWorkout).filter_by(
            user_id=user_id,
            target="garmin",
            external_id="garmin-schedule-7001",
        ).one()
        observation.content_fingerprint = None
        observation.payload_fingerprint = "c" * 64
        db.commit()
    finally:
        db.close()

    compatibility_body = client.get("/api/plan").json()
    reconciliation = compatibility_body["workouts"][0]["reconciliation"]
    assert reconciliation["state"] == "pending_observation"
    assert reconciliation["reason"] == "content_unverified"


def test_reconciliation_flags_owned_workout_scheduled_on_wrong_date(
    api_client,
):
    client, user_id = api_client
    target_date = date.today() + timedelta(days=2)
    observed_date = target_date + timedelta(days=1)
    fingerprint = "a" * 64
    _seed_rows(user_id, [{
        "date": target_date,
        "source": "praxys",
        "workout_type": "easy",
    }])
    _seed_synced_delivery(
        user_id,
        target_date,
        "easy",
        "garmin-schedule-7001",
        provider_content_version=fingerprint,
        provider_account_id="garmin-account",
        target="garmin",
    )
    _seed_target_snapshot(
        user_id,
        [{
            "date": observed_date.isoformat(),
            "workout_type": "easy",
            "external_id": "garmin-schedule-7001",
            "provider_references": {"template_id": "9001"},
            "provider_content_fingerprint": fingerprint,
        }],
        provider_account_id="garmin-account",
        target="garmin",
    )

    from analysis.config import load_config_from_db, save_config_to_db
    from db import session as db_session

    db = db_session.SessionLocal()
    try:
        config = load_config_from_db(user_id, db)
        config.plan_management = {
            "mode": "praxys",
            "execution_target": "garmin",
            "delivery_enabled": False,
            "adjustment_policy": "suggest_only",
        }
        save_config_to_db(user_id, config, db)
    finally:
        db.close()

    body = client.get("/api/plan").json()
    owned = next(
        workout
        for workout in body["workouts"]
        if workout["date"] == target_date.isoformat()
    )

    assert owned["reconciliation"]["state"] == "target_edited"
    assert (
        owned["reconciliation"]["reason"]
        == "scheduled_date_changed"
    )


def test_garmin_compatibility_rows_keep_their_source_without_snapshot(
    api_client,
):
    client, user_id = api_client
    target_date = date.today() + timedelta(days=2)
    _seed_rows(user_id, [{
        "date": target_date,
        "source": "garmin",
        "workout_type": "easy",
        "external_id": "garmin-schedule-7002",
    }])

    from analysis.config import load_config_from_db, save_config_to_db
    from db import session as db_session

    db = db_session.SessionLocal()
    try:
        config = load_config_from_db(user_id, db)
        config.plan_management = {
            "mode": "praxys",
            "execution_target": "garmin",
            "delivery_enabled": False,
            "adjustment_policy": "suggest_only",
        }
        save_config_to_db(user_id, config, db)
    finally:
        db.close()

    body = client.get("/api/plan").json()

    assert body["sync_target"] == "garmin"
    assert len(body["workouts"]) == 1
    assert body["workouts"][0]["source"] == "garmin"


def test_modern_delivery_never_transfers_to_replacement_canonical(api_client):
    client, user_id = api_client
    target = date.today() + timedelta(days=2)
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "easy",
        "workout_description": "Same content",
    }])

    from db import session as db_session
    from db.models import TrainingPlan

    db = db_session.SessionLocal()
    try:
        original = db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
        ).one()
        original_id = original.canonical_id
    finally:
        db.close()
    _seed_synced_delivery(
        user_id,
        target,
        "easy",
        "deleted-canonical-id",
        workout_description="Same content",
        provider_content_version="a" * 64,
        provider_account_id="stryd-account",
        canonical_id=original_id,
    )

    db = db_session.SessionLocal()
    try:
        db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.canonical_id == original_id,
        ).delete(synchronize_session=False)
        replacement = TrainingPlan(
            user_id=user_id,
            date=target,
            source="ai",
            workout_type="easy",
            workout_description="Same content",
        )
        db.add(replacement)
        db.commit()
        replacement_id = replacement.canonical_id
    finally:
        db.close()
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "easy",
        "workout_description": "Same content",
        "external_id": "deleted-canonical-id",
        "provider_content_fingerprint": "a" * 64,
        "provider_payload_fingerprint": "b" * 64,
    }])

    workouts = client.get("/api/plan").json()["workouts"]
    assert len(workouts) == 1
    assert workouts[0]["canonical_id"] == replacement_id
    assert workouts[0]["reconciliation"]["state"] == "not_delivered"
    db = db_session.SessionLocal()
    try:
        from api.plan_reconciliation import PlanReconciliationItem
        from db.models import PlanTargetWorkout

        observation = db.query(PlanTargetWorkout).filter(
            PlanTargetWorkout.user_id == user_id,
            PlanTargetWorkout.external_id == "deleted-canonical-id",
        ).one()
        stale_reconciliation_id = PlanReconciliationItem(
            id=f"target:{observation.id}",
            state="target_only",
            target=observation.target,
            canonical=None,
            observation=observation,
            delivery=None,
        ).opaque_id
    finally:
        db.close()
    stale_accept = client.post(
        "/api/plan/reconciliation/resolve",
        json={
            "reconciliation_id": stale_reconciliation_id,
            "action": "accept_target",
        },
    )
    assert stale_accept.status_code == 404


def test_reconciliation_detects_same_id_target_edit(api_client):
    client, user_id = api_client
    target = date.today() + timedelta(days=3)
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "intervals",
    }])
    _seed_synced_delivery(
        user_id,
        target,
        "intervals",
        "stryd-edited",
        provider_content_version="a" * 64,
        provider_account_id="stryd-account",
    )
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "intervals",
        "workout_description": "Edited on Stryd",
        "external_id": "stryd-edited",
        "provider_content_fingerprint": "c" * 64,
        "provider_payload_fingerprint": "d" * 64,
    }])

    workout = client.get("/api/plan").json()["workouts"][0]
    reconciliation = workout["reconciliation"]
    assert workout["sync_state"] == "mismatch"
    assert reconciliation["state"] == "target_edited"
    assert reconciliation["reason"] == "content_changed"
    assert reconciliation["resolutions"] == [
        "restore_praxys",
        "accept_target",
    ]
    assert reconciliation["target_workout"]["workout_description"] == (
        "Edited on Stryd"
    )
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "intervals",
        "workout_description": "Edited on Stryd",
        "external_id": "stryd-edited",
        "provider_content_fingerprint": "c" * 64,
        "provider_payload_fingerprint": "d" * 64,
    }])
    repeated = client.get("/api/plan").json()["workouts"][0][
        "reconciliation"
    ]
    assert repeated["id"] == reconciliation["id"]
    assert repeated["state"] == "target_edited"


def test_reconciliation_detects_confirmed_target_deletion(api_client):
    client, user_id = api_client
    target = date.today() + timedelta(days=4)
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "easy",
    }])
    _seed_synced_delivery(
        user_id,
        target,
        "easy",
        "stryd-deleted",
        provider_content_version="a" * 64,
        provider_account_id="stryd-account",
    )
    _seed_target_snapshot(user_id, [])

    workout = client.get("/api/plan").json()["workouts"][0]
    assert workout["sync_state"] == "mismatch"
    assert workout["reconciliation"]["state"] == "target_deleted"
    assert workout["reconciliation"]["resolutions"] == ["restore_praxys"]


def test_fetch_started_before_delivery_cannot_confirm_target_deletion(
    api_client,
):
    client, user_id = api_client
    target = date.today() + timedelta(days=4)
    fetch_started_at = datetime.utcnow() - timedelta(minutes=1)
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "easy",
    }])
    _seed_synced_delivery(
        user_id,
        target,
        "easy",
        "post-fetch-delivery",
        provider_content_version="a" * 64,
        provider_account_id="stryd-account",
    )

    from db import session as db_session
    from db.plan_reconciliation import record_target_calendar_sync

    db = db_session.SessionLocal()
    try:
        record_target_calendar_sync(
            db,
            user_id=user_id,
            target="stryd",
            provider_account_id="stryd-account",
            rows=[],
            window_start=date.today(),
            window_end=date.today() + timedelta(days=14),
            observed_at=fetch_started_at,
        )
        db.commit()
    finally:
        db.close()

    reconciliation = client.get("/api/plan").json()["workouts"][0][
        "reconciliation"
    ]
    assert reconciliation["state"] == "pending_observation"
    assert reconciliation["reason"] == "awaiting_calendar_sync"


def test_sync_does_not_delete_known_workout_moved_outside_window(api_client):
    client, user_id = api_client
    original_date = date.today() + timedelta(days=4)
    moved_date = date.today() + timedelta(days=45)
    _seed_rows(user_id, [{
        "date": original_date,
        "source": "ai",
        "workout_type": "easy",
    }])
    _seed_synced_delivery(
        user_id,
        original_date,
        "easy",
        "moved-owned-id",
        provider_content_version="a" * 64,
        provider_account_id="stryd-account",
    )

    from db import session as db_session
    from db.models import PlanTargetWorkout
    from db.plan_reconciliation import record_target_calendar_sync

    db = db_session.SessionLocal()
    try:
        record_target_calendar_sync(
            db,
            user_id=user_id,
            target="stryd",
            provider_account_id="stryd-account",
            rows=[{
                "date": moved_date.isoformat(),
                "workout_type": "easy",
                "external_id": "moved-owned-id",
                "provider_content_fingerprint": "b" * 64,
                "provider_payload_fingerprint": "c" * 64,
            }],
            window_start=date.today(),
            window_end=date.today() + timedelta(days=60),
            observed_at=datetime.utcnow(),
        )
        db.commit()
        record_target_calendar_sync(
            db,
            user_id=user_id,
            target="stryd",
            provider_account_id="stryd-account",
            rows=[],
            window_start=date.today(),
            window_end=date.today() + timedelta(days=14),
            observed_at=datetime.utcnow(),
        )
        db.commit()
        observation = db.query(PlanTargetWorkout).filter(
            PlanTargetWorkout.user_id == user_id,
            PlanTargetWorkout.external_id == "moved-owned-id",
        ).one()
        assert observation.present is True
        assert observation.workout_date == moved_date
    finally:
        db.close()

    reconciliation = client.get("/api/plan").json()["workouts"][0][
        "reconciliation"
    ]
    assert reconciliation["state"] == "target_edited"
    assert reconciliation["reason"] == "content_changed"


def test_older_calendar_fetch_cannot_overwrite_newer_snapshot(api_client):
    _, user_id = api_client
    target = date.today() + timedelta(days=6)
    newer_time = datetime.utcnow()
    older_time = newer_time - timedelta(minutes=5)

    from db import session as db_session
    from db.models import PlanTargetCalendarSync, PlanTargetWorkout
    from db.plan_reconciliation import record_target_calendar_sync

    db = db_session.SessionLocal()
    try:
        applied = record_target_calendar_sync(
            db,
            user_id=user_id,
            target="stryd",
            provider_account_id="stryd-account",
            rows=[{
                "date": target.isoformat(),
                "workout_type": "easy",
                "external_id": "newer-snapshot-id",
                "provider_content_fingerprint": "a" * 64,
                "provider_payload_fingerprint": "b" * 64,
            }],
            window_start=date.today(),
            window_end=date.today() + timedelta(days=14),
            observed_at=newer_time,
        )
        assert applied is not None
        db.commit()

        stale = record_target_calendar_sync(
            db,
            user_id=user_id,
            target="stryd",
            provider_account_id="stryd-account",
            rows=[],
            window_start=date.today(),
            window_end=date.today() + timedelta(days=14),
            observed_at=older_time,
        )
        assert stale is None
        db.commit()

        observation = db.query(PlanTargetWorkout).filter(
            PlanTargetWorkout.user_id == user_id,
            PlanTargetWorkout.external_id == "newer-snapshot-id",
        ).one()
        calendar_sync = db.query(PlanTargetCalendarSync).filter(
            PlanTargetCalendarSync.user_id == user_id,
            PlanTargetCalendarSync.target == "stryd",
        ).one()
        assert observation.present is True
        assert calendar_sync.synced_at == newer_time
    finally:
        db.close()


def test_windowed_view_cannot_reclassify_moved_owned_workout_as_target_only(
    api_client,
):
    client, user_id = api_client
    original_date = date.today() + timedelta(days=3)
    moved_date = date.today() + timedelta(days=20)
    _seed_rows(user_id, [{
        "date": original_date,
        "source": "ai",
        "workout_type": "easy",
    }])

    from db import session as db_session
    from db.models import PlanDelivery, PlanTargetWorkout, TrainingPlan

    db = db_session.SessionLocal()
    try:
        canonical_id = db.query(TrainingPlan.canonical_id).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
        ).scalar()
    finally:
        db.close()
    _seed_synced_delivery(
        user_id,
        original_date,
        "easy",
        "moved-window-id",
        provider_content_version="a" * 64,
        provider_account_id="stryd-account",
        canonical_id=canonical_id,
    )
    _seed_target_snapshot(user_id, [{
        "date": moved_date.isoformat(),
        "workout_type": "easy",
        "external_id": "moved-window-id",
        "provider_content_fingerprint": "b" * 64,
        "provider_payload_fingerprint": "c" * 64,
    }])

    windowed = client.get(
        f"/api/plan?start={moved_date.isoformat()}&end={moved_date.isoformat()}"
    )
    assert windowed.status_code == 200, windowed.text
    assert windowed.json()["workouts"] == []

    db = db_session.SessionLocal()
    try:
        from api.plan_reconciliation import PlanReconciliationItem

        observation = db.query(PlanTargetWorkout).filter(
            PlanTargetWorkout.user_id == user_id,
            PlanTargetWorkout.external_id == "moved-window-id",
        ).one()
        stale_reconciliation_id = PlanReconciliationItem(
            id=f"target:{observation.id}",
            state="target_only",
            target=observation.target,
            canonical=None,
            observation=observation,
            delivery=None,
        ).opaque_id
    finally:
        db.close()
    stale_accept = client.post(
        "/api/plan/reconciliation/resolve",
        json={
            "reconciliation_id": stale_reconciliation_id,
            "action": "accept_target",
        },
    )
    assert stale_accept.status_code == 404

    db = db_session.SessionLocal()
    try:
        assert db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
        ).count() == 1
        assert db.query(PlanDelivery).filter(
            PlanDelivery.user_id == user_id,
            PlanDelivery.state == "synced",
        ).count() == 1
    finally:
        db.close()


def test_target_only_workout_coexists_with_ai_workout_on_same_date(api_client):
    client, user_id = api_client
    target = date.today() + timedelta(days=5)
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "easy",
    }])
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "strides",
        "external_id": "manual-strides",
        "provider_content_fingerprint": "a" * 64,
        "provider_payload_fingerprint": "b" * 64,
    }])

    body = client.get("/api/plan").json()
    workouts = body["workouts"]
    assert [(row["source"], row["workout_type"]) for row in workouts] == [
        ("ai", "easy"),
        ("stryd", "strides"),
    ]
    assert workouts[0]["reconciliation"]["state"] == "not_delivered"
    assert workouts[1]["reconciliation"]["state"] == "target_only"
    assert all(workout["external_overlap"] is True for workout in workouts)
    assert body["management"]["external_overlap_dates"] == [
        target.isoformat(),
    ]


def test_multiple_same_type_target_workouts_keep_distinct_identity(api_client):
    client, user_id = api_client
    target = date.today() + timedelta(days=6)
    _seed_target_snapshot(user_id, [
        {
            "date": target.isoformat(),
            "workout_type": "easy run",
            "external_id": "easy-am",
            "provider_content_fingerprint": "a" * 64,
            "provider_payload_fingerprint": "b" * 64,
        },
        {
            "date": target.isoformat(),
            "workout_type": "easy run",
            "external_id": "easy-pm",
            "provider_content_fingerprint": "c" * 64,
            "provider_payload_fingerprint": "d" * 64,
        },
    ])

    workouts = client.get("/api/plan").json()["workouts"]
    assert len(workouts) == 2
    ids = {
        row["reconciliation"]["external_id"]
        for row in workouts
    }
    assert ids == {"easy-am", "easy-pm"}
    assert all(
        row["reconciliation"]["state"] == "target_only"
        for row in workouts
    )


def test_reconciliation_detects_canonical_change_after_delivery(api_client):
    client, user_id = api_client
    target = date.today() + timedelta(days=7)
    fingerprint = "a" * 64
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "tempo",
        "workout_description": "Original",
    }])
    _seed_synced_delivery(
        user_id,
        target,
        "tempo",
        "stryd-original",
        workout_description="Original",
        provider_content_version=fingerprint,
        provider_account_id="stryd-account",
    )
    from db import session as db_session
    from db.models import TrainingPlan

    db = db_session.SessionLocal()
    try:
        row = db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
            TrainingPlan.date == target,
        ).one()
        row.workout_description = "Adjusted in Praxys"
        db.commit()
    finally:
        db.close()
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "tempo",
        "external_id": "stryd-original",
        "provider_content_fingerprint": fingerprint,
        "provider_payload_fingerprint": "b" * 64,
    }])

    reconciliation = client.get("/api/plan").json()["workouts"][0][
        "reconciliation"
    ]
    assert reconciliation["state"] == "canonical_changed"
    assert reconciliation["reason"] == "praxys_content_changed"


def test_account_switch_does_not_infer_target_deletion(api_client):
    client, user_id = api_client
    target = date.today() + timedelta(days=8)
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "long_run",
    }])
    _seed_synced_delivery(
        user_id,
        target,
        "long_run",
        "old-account-workout",
        provider_content_version="a" * 64,
        provider_account_id="old-account",
    )
    _seed_target_snapshot(
        user_id,
        [],
        provider_account_id="new-account",
    )

    reconciliation = client.get("/api/plan").json()["workouts"][0][
        "reconciliation"
    ]
    assert reconciliation["state"] == "delivery_failed"
    assert reconciliation["reason"] == "provider_account_changed"


def test_reconciliation_uses_immutable_profile_across_display_change():
    from api.plan_reconciliation import classify_plan_delivery_snapshot
    from db.models import (
        PlanDelivery,
        PlanTargetCalendarSync,
        PlanTargetWorkout,
        TrainingPlan,
    )
    from db.plan_ledger import plan_snapshot, workout_version

    workout_date = date.today() + timedelta(days=8)
    canonical = TrainingPlan(
        user_id="profile-alias-user",
        canonical_id="93ce56c3-7135-4874-9c73-85038ef92857",
        date=workout_date,
        source="praxys",
        workout_type="easy",
        planned_duration_min=45,
    )
    version = workout_version(plan_snapshot(canonical))
    delivery = PlanDelivery(
        user_id="profile-alias-user",
        canonical_key=f"ai:{canonical.canonical_id}",
        workout_date=workout_date,
        workout_version=version,
        plan_version=version,
        provider_content_version="a" * 64,
        target="garmin",
        state="synced",
        external_id="schedule-1",
        provider_account_id="international:old-display",
        provider_references={
            "profile_account_id": "international:stable-profile",
        },
    )
    observation = PlanTargetWorkout(
        user_id="profile-alias-user",
        target="garmin",
        provider_account_id="international:new-display",
        external_id="schedule-1",
        provider_references={
            "profile_account_id": "international:stable-profile",
        },
        workout_date=workout_date,
        normalized_workout={},
        content_fingerprint="a" * 64,
        present=True,
        observed_at=datetime.utcnow(),
    )
    calendar_sync = PlanTargetCalendarSync(
        user_id="profile-alias-user",
        target="garmin",
        provider_account_id="international:new-display",
        window_start=date.today(),
        window_end=date.today() + timedelta(days=30),
        synced_at=datetime.utcnow(),
    )

    state, reason, matched = classify_plan_delivery_snapshot(
        canonical=canonical,
        delivery=delivery,
        calendar_sync=calendar_sync,
        observations=[observation],
    )

    assert state == "matching"
    assert reason is None
    assert matched is observation
    observation.provider_references = {
        "profile_account_id": "international:different-profile",
    }
    state, reason, _ = classify_plan_delivery_snapshot(
        canonical=canonical,
        delivery=delivery,
        calendar_sync=calendar_sync,
        observations=[observation],
    )
    assert state == "delivery_failed"
    assert reason == "provider_account_changed"


def test_empty_snapshot_does_not_erase_another_immutable_profile(api_client):
    _, user_id = api_client
    from sqlalchemy import select

    from db import session as db_session
    from db.models import PlanTargetWorkout
    from db.plan_reconciliation import record_target_calendar_sync

    workout_date = date.today() + timedelta(days=5)
    db = db_session.SessionLocal()
    try:
        record_target_calendar_sync(
            db,
            user_id=user_id,
            target="garmin",
            provider_account_id="international:same-display",
            provider_references={
                "profile_account_id": "international:profile-a",
            },
            rows=[{
                "external_id": "schedule-a",
                "date": workout_date.isoformat(),
                "workout_type": "easy",
                "provider_references": {
                    "profile_account_id": "international:profile-a",
                },
            }],
            window_start=date.today(),
            window_end=date.today() + timedelta(days=30),
            observed_at=datetime.utcnow() - timedelta(minutes=1),
        )
        db.commit()

        record_target_calendar_sync(
            db,
            user_id=user_id,
            target="garmin",
            provider_account_id="international:same-display",
            provider_references={
                "profile_account_id": "international:profile-b",
            },
            rows=[],
            window_start=date.today(),
            window_end=date.today() + timedelta(days=30),
            observed_at=datetime.utcnow(),
        )
        db.commit()

        observation = db.execute(
            select(PlanTargetWorkout).where(
                PlanTargetWorkout.user_id == user_id,
                PlanTargetWorkout.external_id == "schedule-a",
            )
        ).scalar_one()
        assert observation.present is True
    finally:
        db.close()


def test_empty_snapshot_bridges_display_change_for_same_profile(api_client):
    _, user_id = api_client
    from sqlalchemy import select

    from db import session as db_session
    from db.models import PlanTargetWorkout
    from db.plan_reconciliation import record_target_calendar_sync

    workout_date = date.today() + timedelta(days=5)
    profile_references = {
        "profile_account_id": "international:stable-profile",
    }
    db = db_session.SessionLocal()
    try:
        record_target_calendar_sync(
            db,
            user_id=user_id,
            target="garmin",
            provider_account_id="international:old-display",
            provider_references=profile_references,
            rows=[{
                "external_id": "schedule-a",
                "date": workout_date.isoformat(),
                "workout_type": "easy",
                "provider_references": profile_references,
            }],
            window_start=date.today(),
            window_end=date.today() + timedelta(days=30),
            observed_at=datetime.utcnow() - timedelta(minutes=1),
        )
        db.commit()

        record_target_calendar_sync(
            db,
            user_id=user_id,
            target="garmin",
            provider_account_id="international:new-display",
            provider_references=profile_references,
            rows=[],
            window_start=date.today(),
            window_end=date.today() + timedelta(days=30),
            observed_at=datetime.utcnow(),
        )
        db.commit()

        observation = db.execute(
            select(PlanTargetWorkout).where(
                PlanTargetWorkout.user_id == user_id,
                PlanTargetWorkout.external_id == "schedule-a",
            )
        ).scalar_one()
        assert observation.present is False
    finally:
        db.close()


def test_locked_generation_includes_same_profile_display_alias(api_client):
    _, user_id = api_client
    from sqlalchemy import select

    from api.plan_reconciliation import plan_target_calendar_generation
    from api.plan_resolution import _locked_target_calendar_generation
    from db import session as db_session
    from db.models import PlanTargetCalendarSync, PlanTargetWorkout
    from db.plan_reconciliation import record_target_calendar_sync

    workout_date = date.today() + timedelta(days=5)
    profile_references = {
        "profile_account_id": "international:stable-profile",
    }
    row = {
        "external_id": "schedule-a",
        "date": workout_date.isoformat(),
        "workout_type": "easy",
        "provider_references": profile_references,
    }
    db = db_session.SessionLocal()
    try:
        record_target_calendar_sync(
            db,
            user_id=user_id,
            target="garmin",
            provider_account_id="international:old-display",
            provider_references=profile_references,
            rows=[row],
            window_start=date.today(),
            window_end=date.today() + timedelta(days=30),
            observed_at=datetime.utcnow() - timedelta(minutes=1),
        )
        db.commit()
        record_target_calendar_sync(
            db,
            user_id=user_id,
            target="garmin",
            provider_account_id="international:new-display",
            provider_references=profile_references,
            rows=[row],
            window_start=date.today(),
            window_end=date.today() + timedelta(days=30),
            observed_at=datetime.utcnow(),
        )
        db.commit()

        calendar_sync = db.execute(
            select(PlanTargetCalendarSync).where(
                PlanTargetCalendarSync.user_id == user_id,
                PlanTargetCalendarSync.target == "garmin",
            )
        ).scalar_one()
        observation = db.execute(
            select(PlanTargetWorkout).where(
                PlanTargetWorkout.user_id == user_id,
                PlanTargetWorkout.external_id == "schedule-a",
            )
        ).scalar_one()
        assert observation.provider_account_id == "international:old-display"
        expected = plan_target_calendar_generation(
            calendar_sync,
            [observation],
        )

        actual = _locked_target_calendar_generation(
            db,
            user_id=user_id,
            target="garmin",
        )

        assert actual == expected
    finally:
        db.close()


def test_reconciliation_surfaces_delivery_failure(api_client):
    client, user_id = api_client
    target = date.today() + timedelta(days=8)
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "tempo",
    }])
    from db import session as db_session
    from db.plan_ledger import get_or_create_delivery

    db = db_session.SessionLocal()
    try:
        delivery, _ = get_or_create_delivery(
            db,
            user_id=user_id,
            target="stryd",
            snapshot={
                "date": target,
                "source": "ai",
                "workout_type": "tempo",
            },
            provider_content_version_override="a" * 64,
        )
        delivery.state = "failed"
        delivery.provider_account_id = "stryd-account"
        delivery.last_error = "Provider rejected workout"
        db.commit()
    finally:
        db.close()
    _seed_target_snapshot(user_id, [])

    reconciliation = client.get("/api/plan").json()["workouts"][0][
        "reconciliation"
    ]
    assert reconciliation["state"] == "delivery_failed"
    assert reconciliation["last_error"] == "Provider rejected workout"


def test_stale_external_id_uses_unique_fingerprint_candidate(api_client):
    client, user_id = api_client
    target = date.today() + timedelta(days=9)
    fingerprint = "a" * 64
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "threshold",
    }])
    _seed_synced_delivery(
        user_id,
        target,
        "threshold",
        "stale-id",
        provider_content_version=fingerprint,
        provider_account_id="stryd-account",
    )
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "threshold",
        "external_id": "replacement-id",
        "provider_content_fingerprint": fingerprint,
        "provider_payload_fingerprint": "b" * 64,
    }])

    workouts = client.get("/api/plan").json()["workouts"]
    assert len(workouts) == 1
    reconciliation = workouts[0]["reconciliation"]
    assert reconciliation["state"] == "target_edited"
    assert reconciliation["reason"] == "external_id_changed_same_content"
    assert reconciliation["match_basis"] == "fingerprint"
    assert reconciliation["external_id"] == "replacement-id"


def test_accept_target_is_transactional_and_records_provenance(api_client):
    client, user_id = api_client
    target = date.today() + timedelta(days=10)
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "coach workout",
        "planned_duration_min": "52",
        "workout_description": "Imported coach session",
        "external_id": "coach-target",
        "provider_references": {"template_id": "coach-template"},
        "provider_content_fingerprint": "a" * 64,
        "provider_payload_fingerprint": "b" * 64,
    }])
    target_workout = client.get("/api/plan").json()["workouts"][0]
    reconciliation_id = target_workout["reconciliation"]["id"]
    bare_retry = client.post(
        "/api/plan/reconciliation/resolve",
        json={
            "reconciliation_id": reconciliation_id.split("@", 1)[0],
            "action": "accept_target",
        },
    )
    assert bare_retry.status_code == 400

    response = client.post(
        "/api/plan/reconciliation/resolve",
        json={
            "reconciliation_id": reconciliation_id,
            "action": "accept_target",
        },
    )
    assert response.status_code == 200, response.text
    canonical_id = response.json()["canonical_id"]
    retry = client.post(
        "/api/plan/reconciliation/resolve",
        json={
            "reconciliation_id": reconciliation_id,
            "action": "accept_target",
        },
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["revision_id"] == response.json()["revision_id"]
    assert retry.json()["canonical_id"] == canonical_id
    assert retry.json()["external_id"] == "coach-target"

    from db import session as db_session
    from db.models import (
        PlanDelivery,
        PlanDeliveryAttempt,
        PlanRevision,
        TrainingPlan,
    )

    db = db_session.SessionLocal()
    try:
        canonical = db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.canonical_id == canonical_id,
        ).one()
        assert canonical.source == PRAXYS_PLAN_WRITE_SOURCE
        assert canonical.workout_origin == "accepted_target"
        assert canonical.workout_description == "Imported coach session"
        assert canonical.meta["accepted_from_target"]["external_id"] == (
            "coach-target"
        )
        revision = db.query(PlanRevision).filter(
            PlanRevision.user_id == user_id,
            PlanRevision.operation == "accept_target",
        ).one()
        delivery = db.query(PlanDelivery).filter(
            PlanDelivery.user_id == user_id,
            PlanDelivery.external_id == "coach-target",
            PlanDelivery.state == "synced",
        ).one()
        assert delivery.provider_references == {
            "template_id": "coach-template",
        }
        attempt = db.query(PlanDeliveryAttempt).filter(
            PlanDeliveryAttempt.delivery_id == delivery.id,
        ).one()
        assert attempt.operation == "import"
        assert attempt.response["revision_id"] == revision.id
    finally:
        db.close()

    body = client.get("/api/plan").json()
    assert body["workouts"][0]["reconciliation"]["state"] == "matching"
    assert target.isoformat() not in body["stryd_status"]


def test_accept_target_failure_rolls_back_canonical_and_ledger(
    api_client,
    monkeypatch,
):
    client, user_id = api_client
    target = date.today() + timedelta(days=10)
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "coach workout",
        "external_id": "rollback-target",
        "provider_content_fingerprint": "a" * 64,
        "provider_payload_fingerprint": "b" * 64,
    }])
    reconciliation_id = client.get("/api/plan").json()["workouts"][0][
        "reconciliation"
    ]["id"]

    def _fail_event(*args, **kwargs):
        raise RuntimeError("delivery event failed")

    monkeypatch.setattr(
        "api.plan_resolution.append_delivery_event",
        _fail_event,
    )
    with pytest.raises(RuntimeError, match="delivery event failed"):
        client.post(
            "/api/plan/reconciliation/resolve",
            json={
                "reconciliation_id": reconciliation_id,
                "action": "accept_target",
            },
        )

    from db import session as db_session
    from db.models import PlanDelivery, PlanRevision, TrainingPlan

    db = db_session.SessionLocal()
    try:
        assert db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
        ).count() == 0
        assert db.query(PlanRevision).filter(
            PlanRevision.user_id == user_id,
        ).count() == 0
        assert db.query(PlanDelivery).filter(
            PlanDelivery.user_id == user_id,
        ).count() == 0
    finally:
        db.close()


def test_accept_target_can_be_reapplied_after_canonical_edit(api_client):
    client, user_id = api_client
    target = date.today() + timedelta(days=10)
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "coach workout",
        "planned_duration_min": "52",
        "workout_description": "Imported coach session",
        "external_id": "repeat-coach-target",
        "provider_content_fingerprint": "a" * 64,
        "provider_payload_fingerprint": "b" * 64,
    }])
    target_item = client.get("/api/plan").json()["workouts"][0]
    first = client.post(
        "/api/plan/reconciliation/resolve",
        json={
            "reconciliation_id": target_item["reconciliation"]["id"],
            "action": "accept_target",
        },
    )
    assert first.status_code == 200, first.text

    edited = client.put(f"/api/plan/{target.isoformat()}", json={
        "workout_type": "coach workout",
        "planned_duration_min": 52,
        "workout_description": "Later Praxys edit",
    })
    assert edited.status_code == 200, edited.text
    changed = client.get("/api/plan").json()["workouts"][0]
    assert changed["reconciliation"]["state"] == "canonical_changed"

    second = client.post(
        "/api/plan/reconciliation/resolve",
        json={
            "reconciliation_id": changed["reconciliation"]["id"],
            "action": "accept_target",
        },
    )
    assert second.status_code == 200, second.text

    from db import session as db_session
    from db.models import PlanRevision, TrainingPlan

    db = db_session.SessionLocal()
    try:
        canonical = db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.canonical_id == first.json()["canonical_id"],
        ).one()
        assert canonical.workout_description == "Imported coach session"
        assert db.query(PlanRevision).filter(
            PlanRevision.user_id == user_id,
            PlanRevision.operation == "accept_target",
        ).count() == 2
    finally:
        db.close()


def test_accept_target_exact_retry_reuses_revision(api_client):
    client, user_id = api_client
    target = date.today() + timedelta(days=10)
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "tempo",
        "workout_description": "Original Praxys version",
    }])
    _seed_synced_delivery(
        user_id,
        target,
        "tempo",
        "retry-accept-id",
        workout_description="Original Praxys version",
        provider_content_version="a" * 64,
        provider_account_id="stryd-account",
    )
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "tempo",
        "workout_description": "Edited on Stryd",
        "external_id": "retry-accept-id",
        "provider_content_fingerprint": "b" * 64,
        "provider_payload_fingerprint": "c" * 64,
    }])
    reconciliation_id = client.get("/api/plan").json()["workouts"][0][
        "reconciliation"
    ]["id"]

    from api.plan_reconciliation import load_plan_reconciliation_item
    from api.plan_resolution import accept_target_version
    from db import session as db_session
    from db.models import PlanRevision

    db = db_session.SessionLocal()
    try:
        item = load_plan_reconciliation_item(
            db,
            user_id=user_id,
            target="stryd",
            reconciliation_id=reconciliation_id,
        )
        assert item is not None
        first = accept_target_version(
            db,
            user_id=user_id,
            target="stryd",
            item=item,
        )
        second = accept_target_version(
            db,
            user_id=user_id,
            target="stryd",
            item=item,
        )
        assert second.revision_id == first.revision_id
        assert db.query(PlanRevision).filter(
            PlanRevision.user_id == user_id,
            PlanRevision.operation == "accept_target",
        ).count() == 1
    finally:
        db.close()


def test_accept_target_rejects_concurrent_canonical_edit(api_client):
    client, user_id = api_client
    target = date.today() + timedelta(days=10)
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "tempo",
        "workout_description": "Original Praxys version",
    }])
    _seed_synced_delivery(
        user_id,
        target,
        "tempo",
        "concurrent-accept-id",
        workout_description="Original Praxys version",
        provider_content_version="a" * 64,
        provider_account_id="stryd-account",
    )
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "tempo",
        "workout_description": "Edited on Stryd",
        "external_id": "concurrent-accept-id",
        "provider_content_fingerprint": "b" * 64,
        "provider_payload_fingerprint": "c" * 64,
    }])
    reconciliation_id = client.get("/api/plan").json()["workouts"][0][
        "reconciliation"
    ]["id"]

    from api.plan_reconciliation import load_plan_reconciliation_item
    from api.plan_resolution import PlanResolutionConflict, accept_target_version
    from db import session as db_session
    from db.models import PlanRevision, TrainingPlan

    db = db_session.SessionLocal()
    try:
        item = load_plan_reconciliation_item(
            db,
            user_id=user_id,
            target="stryd",
            reconciliation_id=reconciliation_id,
        )
        assert item is not None
        other_db = db_session.SessionLocal()
        try:
            canonical = other_db.query(TrainingPlan).filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
            ).one()
            canonical.workout_description = "Concurrent Praxys edit"
            other_db.commit()
        finally:
            other_db.close()

        with pytest.raises(
            PlanResolutionConflict,
            match="changed before acceptance",
        ):
            accept_target_version(
                db,
                user_id=user_id,
                target="stryd",
                item=item,
            )
        db.rollback()
        canonical = db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
        ).one()
        assert canonical.workout_description == "Concurrent Praxys edit"
        assert db.query(PlanRevision).filter(
            PlanRevision.user_id == user_id,
        ).count() == 0
    finally:
        db.close()


def test_accept_target_rejects_concurrent_normalized_snapshot_change(api_client):
    client, user_id = api_client
    target = date.today() + timedelta(days=10)
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "tempo",
        "workout_description": "Original Praxys version",
    }])
    _seed_synced_delivery(
        user_id,
        target,
        "tempo",
        "concurrent-target-snapshot",
        workout_description="Original Praxys version",
        provider_content_version="a" * 64,
        provider_account_id="stryd-account",
    )
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "tempo",
        "target_power_min": "250",
        "external_id": "concurrent-target-snapshot",
        "provider_content_fingerprint": "b" * 64,
        "provider_payload_fingerprint": "c" * 64,
    }])
    reconciliation_id = client.get("/api/plan").json()["workouts"][0][
        "reconciliation"
    ]["id"]

    from api.plan_reconciliation import load_plan_reconciliation_item
    from api.plan_resolution import PlanResolutionConflict, accept_target_version
    from db import session as db_session
    from db.models import PlanRevision, PlanTargetWorkout

    db = db_session.SessionLocal()
    try:
        item = load_plan_reconciliation_item(
            db,
            user_id=user_id,
            target="stryd",
            reconciliation_id=reconciliation_id,
        )
        assert item is not None
        other_db = db_session.SessionLocal()
        try:
            observation = other_db.query(PlanTargetWorkout).filter(
                PlanTargetWorkout.user_id == user_id,
                PlanTargetWorkout.external_id
                == "concurrent-target-snapshot",
            ).one()
            changed_snapshot = dict(observation.normalized_workout)
            changed_snapshot["target_power_min"] = 275.0
            observation.normalized_workout = changed_snapshot
            other_db.commit()
        finally:
            other_db.close()

        with pytest.raises(
            PlanResolutionConflict,
            match="changed before acceptance",
        ):
            accept_target_version(
                db,
                user_id=user_id,
                target="stryd",
                item=item,
            )
        db.rollback()
        assert db.query(PlanRevision).filter(
            PlanRevision.user_id == user_id,
        ).count() == 0
    finally:
        db.close()


def test_restore_rebinds_exact_stale_id_without_provider_write(
    api_client,
    monkeypatch,
):
    from api.plan_delivery.base import (
        PreparedWorkoutDelivery,
        ProviderCreateResult,
        ProviderRemoveResult,
    )

    client, user_id = api_client
    target = date.today() + timedelta(days=11)
    content_version = "a" * 64
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "easy",
    }])
    _seed_synced_delivery(
        user_id,
        target,
        "easy",
        "stale-owned-id",
        provider_content_version=content_version,
        provider_account_id="stryd-account",
    )
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "easy",
        "external_id": "same-content-new-id",
        "provider_references": {"template_id": "same-content-template"},
        "provider_content_fingerprint": content_version,
        "provider_payload_fingerprint": "b" * 64,
    }])
    reconciliation_id = client.get("/api/plan").json()["workouts"][0][
        "reconciliation"
    ]["id"]
    calls = {"create": 0, "delete": 0}

    class FakeAdapter:
        target = "stryd"
        display_name = "Stryd"
        account_id = "stryd-account"

        def authenticate(self):
            return None

        def prepare_workout(self, workout, *, threshold_value):
            return PreparedWorkoutDelivery(
                version="c" * 64,
                request={},
                content_version=content_version,
            )

        def create_workout(self, prepared, *, hooks):
            hooks.before_mutation()
            calls["create"] += 1
            return ProviderCreateResult(
                external_id="unexpected",
                provider_account_id=self.account_id,
                response={},
            )

        def delete_workout(self, external_id, *, hooks):
            hooks.before_mutation()
            calls["delete"] += 1
            return ProviderRemoveResult()

        def fetch_calendar(self, **kwargs):
            return []

    from api.routes import plan as plan_mod

    monkeypatch.setattr(
        plan_mod,
        "_resolve_stryd_delivery_cp",
        lambda data: 280.0,
    )
    monkeypatch.setattr(
        plan_mod,
        "load_plan_delivery_adapter",
        lambda *args, **kwargs: FakeAdapter(),
    )
    response = client.post(
        "/api/plan/reconciliation/resolve",
        json={
            "reconciliation_id": reconciliation_id,
            "action": "restore_praxys",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["external_id"] == "same-content-new-id"
    assert calls == {"create": 0, "delete": 0}
    retry = client.post(
        "/api/plan/reconciliation/resolve",
        json={
            "reconciliation_id": reconciliation_id,
            "action": "restore_praxys",
        },
    )
    assert retry.status_code == 200, retry.text
    assert retry.json()["revision_id"] == response.json()["revision_id"]
    assert retry.json()["external_id"] == "same-content-new-id"
    from db import session as db_session
    from db.models import PlanDelivery

    db = db_session.SessionLocal()
    try:
        rebound = db.query(PlanDelivery).filter(
            PlanDelivery.user_id == user_id,
            PlanDelivery.external_id == "same-content-new-id",
            PlanDelivery.state == "synced",
        ).one()
        assert rebound.provider_references == {
            "template_id": "same-content-template",
        }
    finally:
        db.close()


def test_restore_distinct_stale_ids_record_distinct_audit_events(
    api_client,
    monkeypatch,
):
    from api.plan_delivery.base import (
        PreparedWorkoutDelivery,
        ProviderCreateResult,
        ProviderRemoveResult,
    )

    client, user_id = api_client
    target = date.today() + timedelta(days=11)
    content_version = "a" * 64
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "easy",
    }])
    _seed_synced_delivery(
        user_id,
        target,
        "easy",
        "stale-id-a",
        provider_content_version=content_version,
        provider_account_id="stryd-account",
    )

    class FakeAdapter:
        target = "stryd"
        display_name = "Stryd"
        account_id = "stryd-account"

        def authenticate(self):
            return None

        def prepare_workout(self, workout, *, threshold_value):
            return PreparedWorkoutDelivery(
                version="d" * 64,
                request={},
                content_version=content_version,
            )

        def create_workout(self, prepared, *, hooks):
            hooks.before_mutation()
            return ProviderCreateResult(
                external_id="unexpected",
                provider_account_id=self.account_id,
                response={},
            )

        def delete_workout(self, external_id, *, hooks):
            hooks.before_mutation()
            return ProviderRemoveResult()

        def fetch_calendar(self, **kwargs):
            return []

    from api.routes import plan as plan_mod

    monkeypatch.setattr(
        plan_mod,
        "_resolve_stryd_delivery_cp",
        lambda data: 280.0,
    )
    monkeypatch.setattr(
        plan_mod,
        "load_plan_delivery_adapter",
        lambda *args, **kwargs: FakeAdapter(),
    )

    for external_id in ("stale-id-b", "stale-id-c"):
        _seed_target_snapshot(user_id, [{
            "date": target.isoformat(),
            "workout_type": "easy",
            "external_id": external_id,
            "provider_content_fingerprint": content_version,
            "provider_payload_fingerprint": "e" * 64,
        }])
        reconciliation = client.get("/api/plan").json()["workouts"][0][
            "reconciliation"
        ]
        assert reconciliation["reason"] == "external_id_changed_same_content"
        response = client.post(
            "/api/plan/reconciliation/resolve",
            json={
                "reconciliation_id": reconciliation["id"],
                "action": "restore_praxys",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["external_id"] == external_id

    from db import session as db_session
    from db.models import PlanDeliveryAttempt, PlanRevision

    db = db_session.SessionLocal()
    try:
        revisions = db.query(PlanRevision).filter(
            PlanRevision.user_id == user_id,
            PlanRevision.operation == "restore_target",
        ).all()
        assert len(revisions) == 2
        confirmed_imports = [
            attempt
            for attempt in db.query(PlanDeliveryAttempt).filter(
                PlanDeliveryAttempt.operation == "import",
            ).all()
            if isinstance(attempt.response, dict)
            and attempt.response.get("confirmed_existing") is True
        ]
        assert len(confirmed_imports) == 2
        assert len({
            attempt.response["target_workout_id"]
            for attempt in confirmed_imports
        }) == 2
    finally:
        db.close()


def test_restore_rebind_rejects_concurrent_canonical_edit(
    api_client,
    monkeypatch,
):
    from api.plan_delivery.base import (
        PreparedWorkoutDelivery,
        ProviderCreateResult,
        ProviderRemoveResult,
    )

    client, user_id = api_client
    target = date.today() + timedelta(days=11)
    content_version = "a" * 64
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "easy",
        "workout_description": "Original canonical",
    }])
    _seed_synced_delivery(
        user_id,
        target,
        "easy",
        "concurrent-stale-id",
        provider_content_version=content_version,
        provider_account_id="stryd-account",
    )
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "easy",
        "external_id": "concurrent-new-id",
        "provider_content_fingerprint": content_version,
        "provider_payload_fingerprint": "b" * 64,
    }])
    reconciliation_id = client.get("/api/plan").json()["workouts"][0][
        "reconciliation"
    ]["id"]
    calls = {"create": 0, "delete": 0}

    class ConcurrentEditAdapter:
        target = "stryd"
        display_name = "Stryd"
        account_id = "stryd-account"

        def authenticate(self):
            return None

        def prepare_workout(self, workout, *, threshold_value):
            from db import session as db_session
            from db.models import TrainingPlan

            other_db = db_session.SessionLocal()
            try:
                canonical = other_db.query(TrainingPlan).filter(
                    TrainingPlan.user_id == user_id,
                    TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
                ).one()
                canonical.workout_description = "Concurrent Praxys edit"
                other_db.commit()
            finally:
                other_db.close()
            return PreparedWorkoutDelivery(
                version="c" * 64,
                request={},
                content_version=content_version,
            )

        def create_workout(self, prepared, *, hooks):
            hooks.before_mutation()
            calls["create"] += 1
            return ProviderCreateResult(
                external_id="unexpected",
                provider_account_id=self.account_id,
                response={},
            )

        def delete_workout(self, external_id, *, hooks):
            hooks.before_mutation()
            calls["delete"] += 1
            return ProviderRemoveResult()

        def fetch_calendar(self, **kwargs):
            return []

    from api.routes import plan as plan_mod

    monkeypatch.setattr(
        plan_mod,
        "_resolve_stryd_delivery_cp",
        lambda data: 280.0,
    )
    monkeypatch.setattr(
        plan_mod,
        "load_plan_delivery_adapter",
        lambda *args, **kwargs: ConcurrentEditAdapter(),
    )
    response = client.post(
        "/api/plan/reconciliation/resolve",
        json={
            "reconciliation_id": reconciliation_id,
            "action": "restore_praxys",
        },
    )

    assert response.status_code == 409, response.text
    assert "changed before provider mutation" in response.json()["detail"]
    assert calls == {"create": 0, "delete": 0}
    reconciliation = client.get("/api/plan").json()["workouts"][0][
        "reconciliation"
    ]
    assert reconciliation["state"] != "matching"


@pytest.mark.parametrize(
    "changed_generation",
    ["canonical", "observation", "inserted_observation"],
)
def test_restore_revalidates_before_delete_create_provider_mutation(
    api_client,
    monkeypatch,
    changed_generation,
):
    from api.plan_delivery.base import (
        PreparedWorkoutDelivery,
        ProviderCreateResult,
        ProviderRemoveResult,
    )

    client, user_id = api_client
    target = date.today() + timedelta(days=11)
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "easy",
        "workout_description": "Original canonical",
    }])
    _seed_synced_delivery(
        user_id,
        target,
        "easy",
        "owned-edited-id",
        workout_description="Original canonical",
        provider_content_version="a" * 64,
        provider_account_id="stryd-account",
    )
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "easy",
        "workout_description": "Edited on Stryd",
        "external_id": "owned-edited-id",
        "provider_content_fingerprint": "b" * 64,
        "provider_payload_fingerprint": "c" * 64,
    }])
    reconciliation_id = client.get("/api/plan").json()["workouts"][0][
        "reconciliation"
    ]["id"]
    calls = {"create": 0, "delete": 0}

    class ConcurrentEditAdapter:
        target = "stryd"
        display_name = "Stryd"
        account_id = "stryd-account"

        def authenticate(self):
            return None

        def prepare_workout(self, workout, *, threshold_value):
            return PreparedWorkoutDelivery(
                version="d" * 64,
                request={},
                content_version="e" * 64,
            )

        def create_workout(self, prepared, *, hooks):
            hooks.before_mutation()
            calls["create"] += 1
            return ProviderCreateResult(
                external_id="unexpected",
                provider_account_id=self.account_id,
                response={},
            )

        def delete_workout(self, external_id, *, hooks):
            hooks.before_mutation()
            calls["delete"] += 1
            return ProviderRemoveResult()

        def fetch_calendar(self, **kwargs):
            return []

    from api.routes import plan as plan_mod

    guard_calls = {"count": 0}

    def _provider_guard(*args, **kwargs):
        def guard():
            guard_calls["count"] += 1
            if guard_calls["count"] != 2:
                return
            from db import session as db_session
            from db.models import PlanTargetWorkout, TrainingPlan

            other_db = db_session.SessionLocal()
            try:
                if changed_generation == "canonical":
                    canonical = other_db.query(TrainingPlan).filter(
                        TrainingPlan.user_id == user_id,
                        TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
                    ).one()
                    canonical.workout_description = "Concurrent Praxys edit"
                elif changed_generation == "observation":
                    observation = other_db.query(PlanTargetWorkout).filter(
                        PlanTargetWorkout.user_id == user_id,
                        PlanTargetWorkout.external_id == "owned-edited-id",
                    ).one()
                    changed = dict(observation.normalized_workout)
                    changed["workout_description"] = "New target edit"
                    observation.normalized_workout = changed
                    observation.content_fingerprint = "f" * 64
                else:
                    from db.plan_reconciliation import (
                        record_target_calendar_sync,
                    )

                    record_target_calendar_sync(
                        other_db,
                        user_id=user_id,
                        target="stryd",
                        provider_account_id="stryd-account",
                        rows=[
                            {
                                "date": target.isoformat(),
                                "workout_type": "easy",
                                "workout_description": "Edited on Stryd",
                                "external_id": "owned-edited-id",
                                "provider_content_fingerprint": "b" * 64,
                                "provider_payload_fingerprint": "c" * 64,
                            },
                            {
                                "date": target.isoformat(),
                                "workout_type": "easy",
                                "workout_description": "Matching replacement",
                                "external_id": "concurrent-match-id",
                                "provider_content_fingerprint": "a" * 64,
                                "provider_payload_fingerprint": "9" * 64,
                            },
                        ],
                        window_start=target - timedelta(days=2),
                        window_end=target + timedelta(days=2),
                        observed_at=datetime.utcnow() + timedelta(seconds=1),
                    )
                other_db.commit()
            finally:
                other_db.close()

        return guard

    monkeypatch.setattr(
        plan_mod,
        "_resolve_stryd_delivery_cp",
        lambda data: 280.0,
    )
    monkeypatch.setattr(
        plan_mod,
        "_provider_mutation_guard",
        _provider_guard,
    )
    monkeypatch.setattr(
        plan_mod,
        "load_plan_delivery_adapter",
        lambda *args, **kwargs: ConcurrentEditAdapter(),
    )
    response = client.post(
        "/api/plan/reconciliation/resolve",
        json={
            "reconciliation_id": reconciliation_id,
            "action": "restore_praxys",
        },
    )

    assert response.status_code == 409, response.text
    assert "changed during restore" in response.json()["detail"]
    assert calls == {"create": 0, "delete": 0}
    assert guard_calls["count"] == 2


def test_restore_retries_conflict_after_newer_sync_confirms_absence(
    api_client,
    monkeypatch,
):
    from api.plan_delivery.base import (
        PreparedWorkoutDelivery,
        ProviderCreateResult,
        ProviderRemoveResult,
    )
    from db import session as db_session
    from db.models import TrainingPlan
    from db.plan_ledger import (
        begin_delivery_attempt,
        complete_delivery_attempt,
        get_or_create_delivery,
        plan_snapshot,
    )

    client, user_id = api_client
    target = date.today() + timedelta(days=12)
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "tempo",
    }])

    db = db_session.SessionLocal()
    try:
        canonical = db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
        ).one()
        delivery, _ = get_or_create_delivery(
            db,
            user_id=user_id,
            target="stryd",
            snapshot=plan_snapshot(canonical),
        )
        content_version = "a" * 64
        delivery.provider_content_version = content_version
        payload_version = delivery.workout_version
        delivery, attempt, disposition = begin_delivery_attempt(
            db,
            delivery,
            operation="deliver",
        )
        assert disposition == "started"
        assert attempt is not None
        complete_delivery_attempt(
            db,
            user_id=user_id,
            delivery_id=delivery.id,
            attempt_id=attempt.id,
            attempt_state="conflict",
            error="Provider outcome unknown",
        )
        db.commit()
    finally:
        db.close()

    from db.plan_reconciliation import record_target_calendar_sync

    db = db_session.SessionLocal()
    try:
        record_target_calendar_sync(
            db,
            user_id=user_id,
            target="stryd",
            provider_account_id="stryd-account",
            rows=[],
            window_start=date.today(),
            window_end=date.today() + timedelta(days=30),
            observed_at=datetime.utcnow() + timedelta(seconds=1),
        )
        db.commit()
    finally:
        db.close()

    calls = {"create": 0, "delete": 0}

    class RetryAdapter:
        target = "stryd"
        display_name = "Stryd"
        account_id = "stryd-account"

        def authenticate(self):
            return None

        def prepare_workout(self, workout, *, threshold_value):
            return PreparedWorkoutDelivery(
                version=payload_version,
                request={},
                content_version=content_version,
            )

        def create_workout(self, prepared, *, hooks):
            hooks.before_mutation()
            calls["create"] += 1
            return ProviderCreateResult(
                external_id="confirmed-retry-id",
                provider_account_id=self.account_id,
                response={},
            )

        def delete_workout(self, external_id, *, hooks):
            hooks.before_mutation()
            calls["delete"] += 1
            return ProviderRemoveResult()

        def fetch_calendar(self, **kwargs):
            return []

    from api.routes import plan as plan_mod

    monkeypatch.setattr(
        plan_mod,
        "_resolve_stryd_delivery_cp",
        lambda data: 280.0,
    )
    monkeypatch.setattr(
        plan_mod,
        "load_plan_delivery_adapter",
        lambda *args, **kwargs: RetryAdapter(),
    )
    reconciliation = client.get("/api/plan").json()["workouts"][0][
        "reconciliation"
    ]
    assert reconciliation["state"] == "delivery_failed"
    assert reconciliation["reason"] == "conflict"
    response = client.post(
        "/api/plan/reconciliation/resolve",
        json={
            "reconciliation_id": reconciliation["id"],
            "action": "restore_praxys",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["external_id"] == "confirmed-retry-id"
    assert calls == {"create": 1, "delete": 0}


def test_restore_conflict_checks_original_uncertain_fingerprint(
    api_client,
    monkeypatch,
):
    from api.plan_delivery.base import (
        PreparedWorkoutDelivery,
        ProviderCreateResult,
        ProviderRemoveResult,
    )
    from db import session as db_session
    from db.models import TrainingPlan
    from db.plan_ledger import (
        begin_delivery_attempt,
        complete_delivery_attempt,
        get_or_create_delivery,
        plan_snapshot,
    )

    client, user_id = api_client
    target = date.today() + timedelta(days=12)
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "tempo",
        "workout_description": "Version A",
    }])

    db = db_session.SessionLocal()
    try:
        canonical = db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
        ).one()
        delivery, _ = get_or_create_delivery(
            db,
            user_id=user_id,
            target="stryd",
            snapshot=plan_snapshot(canonical),
        )
        uncertain_content = "a" * 64
        delivery.provider_content_version = uncertain_content
        delivery, attempt, disposition = begin_delivery_attempt(
            db,
            delivery,
            operation="deliver",
        )
        assert disposition == "started"
        assert attempt is not None
        complete_delivery_attempt(
            db,
            user_id=user_id,
            delivery_id=delivery.id,
            attempt_id=attempt.id,
            attempt_state="conflict",
            error="Provider outcome unknown",
        )
        canonical.workout_description = "Version B"
        db.commit()
    finally:
        db.close()
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "tempo",
        "workout_description": "Version A",
        "external_id": "uncertain-version-a",
        "provider_content_fingerprint": uncertain_content,
        "provider_payload_fingerprint": "b" * 64,
    }])

    calls = {"create": 0}

    class ChangedAdapter:
        target = "stryd"
        display_name = "Stryd"
        account_id = "stryd-account"

        def authenticate(self):
            return None

        def prepare_workout(self, workout, *, threshold_value):
            return PreparedWorkoutDelivery(
                version="c" * 64,
                request={},
                content_version="d" * 64,
            )

        def create_workout(self, prepared, *, hooks):
            hooks.before_mutation()
            calls["create"] += 1
            return ProviderCreateResult(
                external_id="duplicate-version-b",
                provider_account_id=self.account_id,
                response={},
            )

        def delete_workout(self, external_id, *, hooks):
            hooks.before_mutation()
            return ProviderRemoveResult()

        def fetch_calendar(self, **kwargs):
            return []

    from api.routes import plan as plan_mod

    monkeypatch.setattr(
        plan_mod,
        "_resolve_stryd_delivery_cp",
        lambda data: 280.0,
    )
    monkeypatch.setattr(
        plan_mod,
        "load_plan_delivery_adapter",
        lambda *args, **kwargs: ChangedAdapter(),
    )
    reconciliation = client.get("/api/plan").json()["workouts"][0][
        "reconciliation"
    ]
    response = client.post(
        "/api/plan/reconciliation/resolve",
        json={
            "reconciliation_id": reconciliation["id"],
            "action": "restore_praxys",
        },
    )

    assert response.status_code == 409, response.text
    assert "still present" in response.json()["detail"]
    assert calls["create"] == 0


def test_restore_conflict_falls_back_to_original_payload_fingerprint(
    api_client,
    monkeypatch,
):
    from api.plan_delivery.base import (
        PreparedWorkoutDelivery,
        ProviderCreateResult,
        ProviderRemoveResult,
    )
    from db import session as db_session
    from db.models import TrainingPlan
    from db.plan_ledger import (
        begin_delivery_attempt,
        complete_delivery_attempt,
        get_or_create_delivery,
        plan_snapshot,
    )

    client, user_id = api_client
    target = date.today() + timedelta(days=12)
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "tempo",
        "workout_description": "Version A",
    }])
    db = db_session.SessionLocal()
    try:
        canonical = db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
        ).one()
        delivery, _ = get_or_create_delivery(
            db,
            user_id=user_id,
            target="stryd",
            snapshot=plan_snapshot(canonical),
            workout_version_override="f" * 64,
        )
        delivery.provider_content_version = None
        delivery, attempt, disposition = begin_delivery_attempt(
            db,
            delivery,
            operation="deliver",
        )
        assert disposition == "started"
        assert attempt is not None
        complete_delivery_attempt(
            db,
            user_id=user_id,
            delivery_id=delivery.id,
            attempt_id=attempt.id,
            attempt_state="conflict",
            error="Provider outcome unknown",
        )
        canonical.workout_description = "Version B"
        db.commit()
    finally:
        db.close()
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "tempo",
        "external_id": "payload-version-a",
        "provider_content_fingerprint": "a" * 64,
        "provider_payload_fingerprint": "f" * 64,
    }])

    calls = {"create": 0}

    class ChangedAdapter:
        target = "stryd"
        display_name = "Stryd"
        account_id = "stryd-account"

        def authenticate(self):
            return None

        def prepare_workout(self, workout, *, threshold_value):
            return PreparedWorkoutDelivery(
                version="g" * 64,
                request={},
                content_version="h" * 64,
            )

        def create_workout(self, prepared, *, hooks):
            hooks.before_mutation()
            calls["create"] += 1
            return ProviderCreateResult(
                external_id="duplicate-version-b",
                provider_account_id=self.account_id,
                response={},
            )

        def delete_workout(self, external_id, *, hooks):
            hooks.before_mutation()
            return ProviderRemoveResult()

        def fetch_calendar(self, **kwargs):
            return []

    from api.routes import plan as plan_mod

    monkeypatch.setattr(
        plan_mod,
        "_resolve_stryd_delivery_cp",
        lambda data: 280.0,
    )
    monkeypatch.setattr(
        plan_mod,
        "load_plan_delivery_adapter",
        lambda *args, **kwargs: ChangedAdapter(),
    )
    reconciliation = client.get("/api/plan").json()["workouts"][0][
        "reconciliation"
    ]
    response = client.post(
        "/api/plan/reconciliation/resolve",
        json={
            "reconciliation_id": reconciliation["id"],
            "action": "restore_praxys",
        },
    )

    assert response.status_code == 409, response.text
    assert "still present" in response.json()["detail"]
    assert calls["create"] == 0


def test_accept_import_does_not_complete_restore_receipt(api_client):
    _, user_id = api_client
    target = date.today() + timedelta(days=12)
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "easy",
    }])

    from api.plan_resolution import (
        _resolution_key,
        completed_plan_resolution,
    )
    from db import session as db_session
    from db.models import TrainingPlan
    from db.plan_ledger import (
        append_delivery_event,
        get_or_create_delivery,
        plan_snapshot,
        record_plan_revision_idempotent,
    )

    resolution_identity = "receipt-test-generation"
    reconciliation_id = f"delivery:receipt-test@{resolution_identity}"
    db = db_session.SessionLocal()
    try:
        canonical = db.query(TrainingPlan).filter(
            TrainingPlan.user_id == user_id,
            TrainingPlan.source.in_(PRAXYS_PLAN_SOURCES),
        ).one()
        snapshot = plan_snapshot(canonical)
        revision, _ = record_plan_revision_idempotent(
            db,
            user_id=user_id,
            operation="restore_target",
            actor_type="user",
            actor_id=user_id,
            origin="api.plan.reconciliation.restore",
            before=[snapshot],
            after=[snapshot],
            details={},
            idempotency_key=_resolution_key(
                "restore_praxys",
                resolution_identity,
            ),
        )
        db.commit()
        delivery, _ = get_or_create_delivery(
            db,
            user_id=user_id,
            target="stryd",
            snapshot=snapshot,
        )
        delivery.state = "synced"
        delivery.external_id = "accepted-target-id"
        append_delivery_event(
            db,
            delivery,
            operation="import",
            state="synced",
            external_id="accepted-target-id",
            response={
                "resolution": "accept_target",
                "revision_id": revision.id,
            },
        )
        db.commit()

        assert completed_plan_resolution(
            db,
            user_id=user_id,
            target="stryd",
            reconciliation_id=reconciliation_id,
            action="restore_praxys",
        ) is None
    finally:
        db.close()


def test_restore_wrong_date_removes_owned_instance_before_recreate(
    api_client,
    monkeypatch,
):
    from api.plan_delivery.base import (
        PreparedWorkoutDelivery,
        ProviderCreateResult,
        ProviderRemoveResult,
    )
    from db import session as db_session
    from db.models import PlanDelivery

    client, user_id = api_client
    target_date = date.today() + timedelta(days=11)
    observed_date = target_date + timedelta(days=1)
    fingerprint = "a" * 64
    _seed_rows(user_id, [{
        "date": target_date,
        "source": "praxys",
        "workout_type": "tempo",
    }])
    delivery_id = _seed_synced_delivery(
        user_id,
        target_date,
        "tempo",
        "wrong-date-owned-id",
        provider_content_version=fingerprint,
        provider_account_id="stryd-account",
    )
    db = db_session.SessionLocal()
    try:
        delivery_version = db.get(
            PlanDelivery,
            delivery_id,
        ).workout_version
    finally:
        db.close()
    _seed_target_snapshot(user_id, [{
        "date": observed_date.isoformat(),
        "workout_type": "tempo",
        "external_id": "wrong-date-owned-id",
        "provider_content_fingerprint": fingerprint,
    }])
    plan_body = client.get("/api/plan").json()
    owned = next(
        workout
        for workout in plan_body["workouts"]
        if workout["date"] == target_date.isoformat()
    )
    reconciliation_id = owned["reconciliation"]["id"]
    calls = {"create": 0, "delete": 0}

    class WrongDateAdapter:
        target = "stryd"
        display_name = "Stryd"
        account_id = "stryd-account"

        def authenticate(self):
            return None

        def prepare_workout(self, workout, *, threshold_value):
            return PreparedWorkoutDelivery(
                version=delivery_version,
                request={},
                content_version=fingerprint,
            )

        def create_workout(self, prepared, *, hooks):
            hooks.before_mutation()
            calls["create"] += 1
            return ProviderCreateResult(
                external_id="restored-correct-date",
                provider_account_id=self.account_id,
                response={"id": "restored-correct-date"},
            )

        def delete_workout(self, external_id, *, hooks):
            assert external_id == "wrong-date-owned-id"
            hooks.before_mutation()
            calls["delete"] += 1
            return ProviderRemoveResult()

        def fetch_calendar(self, **kwargs):
            return []

    adapter = WrongDateAdapter()
    from api.routes import plan as plan_mod

    monkeypatch.setattr(
        plan_mod,
        "_resolve_stryd_delivery_cp",
        lambda data: 280.0,
    )
    monkeypatch.setattr(
        plan_mod,
        "load_plan_delivery_adapter",
        lambda *args, **kwargs: adapter,
    )

    response = client.post(
        "/api/plan/reconciliation/resolve",
        json={
            "reconciliation_id": reconciliation_id,
            "action": "restore_praxys",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["external_id"] == "restored-correct-date"
    assert calls == {"create": 1, "delete": 1}


def test_restore_matching_garmin_schedule_is_noop_without_checkpoint_id(
    api_client,
    monkeypatch,
):
    from api.plan_delivery.base import PreparedWorkoutDelivery
    from api.plan_delivery.capabilities import plan_delivery_consent_token
    from db import session as db_session
    from db.models import (
        PlanDelivery,
        UserConfig,
        UserConnection,
    )

    client, user_id = api_client
    target_date = date.today() + timedelta(days=10)
    fingerprint = "c" * 64
    profile_references = {
        "template_id": "template-7",
        "profile_account_id": "international:profile",
    }
    _seed_rows(user_id, [{
        "date": target_date,
        "source": "praxys",
        "workout_type": "easy",
    }])
    delivery_id = _seed_synced_delivery(
        user_id,
        target_date,
        "easy",
        "schedule-42",
        provider_content_version=fingerprint,
        provider_account_id="garmin-account",
        target="garmin",
    )
    with db_session.SessionLocal() as db:
        delivery = db.get(PlanDelivery, delivery_id)
        delivery.state = "conflict"
        delivery.provider_references = dict(profile_references)
        delivery_version = delivery.workout_version
        db.add(UserConfig(
            user_id=user_id,
            source_options={"garmin_region": "international"},
            plan_management={
                "mode": "praxys",
                "execution_target": "garmin",
                "delivery_enabled": True,
                "adjustment_policy": "suggest_only",
            },
        ))
        connection = UserConnection(
            user_id=user_id,
            platform="garmin",
            status="connected",
            encrypted_credentials=b"garmin-credentials",
            wrapped_dek=b"garmin-dek",
        )
        db.add(connection)
        db.flush()
        connection.plan_delivery_consent = plan_delivery_consent_token(
            connection,
            region="international",
        )
        db.commit()
    _seed_target_snapshot(
        user_id,
        [{
            "date": target_date.isoformat(),
            "workout_type": "easy",
            "external_id": "schedule-42",
            "provider_content_fingerprint": fingerprint,
            "provider_references": profile_references,
        }],
        provider_account_id="garmin-account",
        target="garmin",
    )
    plan_body = client.get("/api/plan").json()
    owned = next(
        workout
        for workout in plan_body["workouts"]
        if workout["date"] == target_date.isoformat()
        and workout["source"] in PRAXYS_PLAN_SOURCES
    )
    reconciliation_id = owned["reconciliation"]["id"]
    calls = {"create": 0, "delete": 0}

    class Adapter:
        target = "garmin"
        display_name = "Garmin"
        account_id = "garmin-account"

        def authenticate(self):
            return None

        def prepare_workout(self, workout, *, threshold_value):
            return PreparedWorkoutDelivery(
                version=delivery_version,
                request={},
                content_version=fingerprint,
            )

        def create_workout(self, prepared, *, hooks):
            calls["create"] += 1
            raise AssertionError("matching schedule must not be recreated")

        def delete_workout(self, external_id, *, hooks):
            calls["delete"] += 1
            raise AssertionError("matching schedule must not be removed")

        def fetch_calendar(self, **kwargs):
            return []

    from api.routes import plan as plan_mod

    monkeypatch.setattr(
        plan_mod,
        "load_plan_delivery_adapter",
        lambda *args, **kwargs: Adapter(),
    )

    response = client.post(
        "/api/plan/reconciliation/resolve",
        json={
            "reconciliation_id": reconciliation_id,
            "action": "restore_praxys",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["external_id"] == "schedule-42"
    assert calls == {"create": 0, "delete": 0}
    with db_session.SessionLocal() as db:
        delivery = db.get(PlanDelivery, delivery_id)
        assert delivery.state == "synced"
        assert delivery.provider_references["schedule_id"] == "schedule-42"
        assert delivery.provider_references["template_id"] == "template-7"


@pytest.mark.parametrize(
    ("scenario", "expected_status"),
    [
        ("safe", 200),
        ("preexisting", 409),
        ("unexpected_date", 409),
        ("mismatched_observation", 409),
    ],
)
def test_restore_returned_garmin_schedule_requires_new_checkpoint(
    api_client,
    monkeypatch,
    scenario: str,
    expected_status: int,
):
    from api.plan_delivery.base import PreparedWorkoutDelivery
    from api.plan_delivery.capabilities import plan_delivery_consent_token
    from db import session as db_session
    from db.models import (
        PlanDelivery,
        UserConfig,
        UserConnection,
    )

    client, user_id = api_client
    target_date = date.today() + timedelta(days=10)
    fingerprint = "d" * 64
    external_id = "returned-schedule-42"
    profile_references = {
        "template_id": "template-7",
        "profile_account_id": "international:profile",
    }
    _seed_rows(user_id, [{
        "date": target_date,
        "source": "praxys",
        "workout_type": "easy",
    }])
    delivery_id = _seed_synced_delivery(
        user_id,
        target_date,
        "easy",
        external_id,
        provider_content_version=fingerprint,
        provider_account_id="garmin-account",
        target="garmin",
    )
    with db_session.SessionLocal() as db:
        delivery = db.get(PlanDelivery, delivery_id)
        delivery.state = "conflict"
        delivery.external_id = None
        delivery.provider_references = {
            **profile_references,
            "preexisting_schedule_ids": (
                [external_id] if scenario == "preexisting" else []
            ),
            "schedule_started": True,
            "returned_schedule_id": external_id,
            **(
                {
                    "unexpected_schedule_date": (
                        target_date + timedelta(days=1)
                    ).isoformat()
                }
                if scenario == "unexpected_date"
                else {}
            ),
        }
        delivery_version = delivery.workout_version
        db.add(UserConfig(
            user_id=user_id,
            source_options={"garmin_region": "international"},
            plan_management={
                "mode": "praxys",
                "execution_target": "garmin",
                "delivery_enabled": True,
                "adjustment_policy": "suggest_only",
            },
        ))
        connection = UserConnection(
            user_id=user_id,
            platform="garmin",
            status="connected",
            encrypted_credentials=b"garmin-credentials",
            wrapped_dek=b"garmin-dek",
        )
        db.add(connection)
        db.flush()
        connection.plan_delivery_consent = plan_delivery_consent_token(
            connection,
            region="international",
        )
        db.commit()
    _seed_target_snapshot(
        user_id,
        [{
            "date": target_date.isoformat(),
            "workout_type": "easy",
            "external_id": (
                "different-schedule"
                if scenario == "mismatched_observation"
                else external_id
            ),
            "provider_content_fingerprint": fingerprint,
            "provider_references": profile_references,
        }],
        provider_account_id="garmin-account",
        target="garmin",
    )
    plan_body = client.get("/api/plan").json()
    owned = next(
        workout
        for workout in plan_body["workouts"]
        if workout["date"] == target_date.isoformat()
        and workout["source"] in PRAXYS_PLAN_SOURCES
    )
    reconciliation_id = owned["reconciliation"]["id"]
    calls = {"create": 0, "delete": 0}

    class Adapter:
        target = "garmin"
        display_name = "Garmin"
        account_id = "garmin-account"

        def authenticate(self):
            return None

        def prepare_workout(self, workout, *, threshold_value):
            return PreparedWorkoutDelivery(
                version=delivery_version,
                request={},
                content_version=fingerprint,
            )

        def create_workout(self, prepared, *, hooks):
            calls["create"] += 1
            raise AssertionError("matching schedule must not be recreated")

        def delete_workout(self, external_id, *, hooks):
            calls["delete"] += 1
            raise AssertionError("matching schedule must not be removed")

        def fetch_calendar(self, **kwargs):
            return []

    from api.routes import plan as plan_mod

    monkeypatch.setattr(
        plan_mod,
        "load_plan_delivery_adapter",
        lambda *args, **kwargs: Adapter(),
    )

    response = client.post(
        "/api/plan/reconciliation/resolve",
        json={
            "reconciliation_id": reconciliation_id,
            "action": "restore_praxys",
        },
    )

    assert response.status_code == expected_status, response.text
    assert calls == {"create": 0, "delete": 0}
    with db_session.SessionLocal() as db:
        delivery = db.get(PlanDelivery, delivery_id)
        if scenario != "safe":
            assert "still present" in response.json()["detail"]
            assert delivery.state == "conflict"
            assert delivery.external_id is None
            assert "schedule_id" not in delivery.provider_references
        else:
            assert response.json()["external_id"] == external_id
            assert delivery.state == "synced"
            assert delivery.external_id == external_id
            assert (
                delivery.provider_references["schedule_id"]
                == external_id
            )


def test_restore_does_not_claim_unowned_garmin_fingerprint_candidate(
    api_client,
    monkeypatch,
):
    from api.plan_delivery.base import PreparedWorkoutDelivery
    from api.plan_delivery.capabilities import plan_delivery_consent_token
    from db import session as db_session
    from db.models import (
        PlanDelivery,
        TrainingPlan,
        UserConfig,
        UserConnection,
    )
    from db.plan_ledger import get_or_create_delivery, plan_snapshot

    client, user_id = api_client
    target_date = date.today() + timedelta(days=10)
    fingerprint = "a" * 64
    _seed_rows(user_id, [{
        "date": target_date,
        "source": "praxys",
        "workout_type": "easy",
    }])
    db = db_session.SessionLocal()
    try:
        canonical = db.query(TrainingPlan).filter_by(
            user_id=user_id,
            date=target_date,
            source="praxys",
        ).one()
        delivery, _ = get_or_create_delivery(
            db,
            user_id=user_id,
            target="garmin",
            snapshot=plan_snapshot(canonical),
        )
        delivery.state = "conflict"
        delivery.provider_account_id = "garmin-account"
        delivery.provider_content_version = fingerprint
        delivery.provider_references = {
            "candidate_schedule_ids": ["manual-schedule-42"],
            "profile_account_id": "international:profile",
        }
        db.add(UserConfig(
            user_id=user_id,
            source_options={"garmin_region": "international"},
            plan_management={
                "mode": "praxys",
                "execution_target": "garmin",
                "delivery_enabled": True,
                "adjustment_policy": "suggest_only",
            },
        ))
        connection = UserConnection(
            user_id=user_id,
            platform="garmin",
            status="connected",
            encrypted_credentials=b"garmin-credentials",
            wrapped_dek=b"garmin-dek",
        )
        db.add(connection)
        db.flush()
        connection.plan_delivery_consent = plan_delivery_consent_token(
            connection,
            region="international",
        )
        db.commit()
        delivery_version = delivery.workout_version
    finally:
        db.close()
    _seed_target_snapshot(
        user_id,
        [{
            "date": target_date.isoformat(),
            "workout_type": "easy",
            "external_id": "manual-schedule-42",
            "provider_content_fingerprint": fingerprint,
        }],
        provider_account_id="garmin-account",
        target="garmin",
    )
    plan_body = client.get("/api/plan").json()
    owned = next(
        workout
        for workout in plan_body["workouts"]
        if workout["date"] == target_date.isoformat()
        and workout["source"] in PRAXYS_PLAN_SOURCES
    )
    reconciliation_id = owned["reconciliation"]["id"]
    calls = {"create": 0, "delete": 0}

    class CandidateAdapter:
        target = "garmin"
        display_name = "Garmin"
        account_id = "garmin-account"

        def authenticate(self):
            return None

        def prepare_workout(self, workout, *, threshold_value):
            return PreparedWorkoutDelivery(
                version=delivery_version,
                request={},
                content_version=fingerprint,
            )

        def create_workout(self, prepared, *, hooks):
            calls["create"] += 1
            raise AssertionError("unowned candidate must not be created")

        def delete_workout(self, external_id, *, hooks):
            calls["delete"] += 1
            raise AssertionError("unowned candidate must not be deleted")

        def fetch_calendar(self, **kwargs):
            return []

    from api.routes import plan as plan_mod

    monkeypatch.setattr(
        plan_mod,
        "load_plan_delivery_adapter",
        lambda *args, **kwargs: CandidateAdapter(),
    )

    response = client.post(
        "/api/plan/reconciliation/resolve",
        json={
            "reconciliation_id": reconciliation_id,
            "action": "restore_praxys",
        },
    )

    assert response.status_code == 409, response.text
    assert calls == {"create": 0, "delete": 0}
    db = db_session.SessionLocal()
    try:
        delivery = db.query(PlanDelivery).filter_by(
            user_id=user_id,
            target="garmin",
        ).one()
        assert delivery.external_id is None
        assert delivery.state == "conflict"
    finally:
        db.close()


def test_confirmed_absence_ignores_same_template_on_another_date(
    api_client,
):
    from api.plan_resolution import _release_conflict_after_confirmed_absence
    from db import session as db_session
    from db.models import PlanDelivery
    from db.plan_reconciliation import record_target_calendar_sync

    _, user_id = api_client
    target_date = date.today() + timedelta(days=9)
    fingerprint = "b" * 64
    _seed_rows(user_id, [{
        "date": target_date,
        "source": "praxys",
        "workout_type": "easy",
    }])
    delivery_id = _seed_synced_delivery(
        user_id,
        target_date,
        "easy",
        "owned-schedule",
        provider_content_version=fingerprint,
        provider_account_id="garmin-account",
        target="garmin",
    )

    class Adapter:
        account_id = "garmin-account"

    with db_session.SessionLocal() as db:
        delivery = db.get(PlanDelivery, delivery_id)
        delivery.state = "conflict"
        delivery.updated_at = datetime.utcnow() - timedelta(minutes=1)
        record_target_calendar_sync(
            db,
            user_id=user_id,
            target="garmin",
            provider_account_id="garmin-account",
            rows=[{
                "date": (target_date + timedelta(days=1)).isoformat(),
                "workout_type": "easy",
                "external_id": "other-schedule",
                "provider_content_fingerprint": fingerprint,
            }],
            window_start=date.today(),
            window_end=date.today() + timedelta(days=30),
            observed_at=datetime.utcnow(),
        )
        db.commit()

        _release_conflict_after_confirmed_absence(
            db,
            user_id=user_id,
            target="garmin",
            delivery_id=delivery_id,
            adapter=Adapter(),
            revision_id="test-revision",
        )

        assert db.get(PlanDelivery, delivery_id).state == "failed"


def test_confirmed_absence_blocks_when_exact_schedule_moved_dates(
    api_client,
):
    from api.plan_resolution import (
        PlanResolutionConflict,
        _release_conflict_after_confirmed_absence,
    )
    from db import session as db_session
    from db.models import PlanDelivery
    from db.plan_reconciliation import record_target_calendar_sync

    _, user_id = api_client
    target_date = date.today() + timedelta(days=9)
    _seed_rows(user_id, [{
        "date": target_date,
        "source": "praxys",
        "workout_type": "easy",
    }])
    delivery_id = _seed_synced_delivery(
        user_id,
        target_date,
        "easy",
        "owned-schedule",
        provider_content_version="b" * 64,
        provider_account_id="garmin-account",
        target="garmin",
    )

    class Adapter:
        account_id = "garmin-account"

    with db_session.SessionLocal() as db:
        delivery = db.get(PlanDelivery, delivery_id)
        delivery.state = "conflict"
        delivery.updated_at = datetime.utcnow() - timedelta(minutes=1)
        record_target_calendar_sync(
            db,
            user_id=user_id,
            target="garmin",
            provider_account_id="garmin-account",
            rows=[{
                "date": (target_date + timedelta(days=1)).isoformat(),
                "workout_type": "easy",
                "external_id": "owned-schedule",
                "provider_content_fingerprint": "c" * 64,
            }],
            window_start=date.today(),
            window_end=date.today() + timedelta(days=30),
            observed_at=datetime.utcnow(),
        )
        db.commit()

        with pytest.raises(PlanResolutionConflict, match="still present"):
            _release_conflict_after_confirmed_absence(
                db,
                user_id=user_id,
                target="garmin",
                delivery_id=delivery_id,
                adapter=Adapter(),
                revision_id="test-revision",
            )

        assert db.get(PlanDelivery, delivery_id).state == "conflict"


@pytest.mark.parametrize("reuse_delivery", [False, True])
def test_restore_retry_after_create_failure_is_idempotent(
    api_client,
    monkeypatch,
    reuse_delivery,
):
    from api.plan_delivery.base import (
        PreparedWorkoutDelivery,
        ProviderCreateResult,
        ProviderRejectedError,
        ProviderRemoveResult,
    )

    client, user_id = api_client
    target = date.today() + timedelta(days=12)
    _seed_rows(user_id, [{
        "date": target,
        "source": "ai",
        "workout_type": "tempo",
    }])
    delivery_id = _seed_synced_delivery(
        user_id,
        target,
        "tempo",
        "edited-owned-id",
        provider_content_version="a" * 64,
        provider_account_id="stryd-account",
    )
    from db import session as db_session
    from db.models import PlanDelivery

    db = db_session.SessionLocal()
    try:
        seeded_delivery_version = db.get(
            PlanDelivery,
            delivery_id,
        ).workout_version
    finally:
        db.close()
    _seed_target_snapshot(user_id, [{
        "date": target.isoformat(),
        "workout_type": "tempo",
        "external_id": "edited-owned-id",
        "provider_content_fingerprint": "b" * 64,
        "provider_payload_fingerprint": "c" * 64,
    }])
    reconciliation_id = client.get("/api/plan").json()["workouts"][0][
        "reconciliation"
    ]["id"]
    calls = {"create": 0, "delete": 0}

    class RetryAdapter:
        target = "stryd"
        display_name = "Stryd"
        account_id = "stryd-account"

        def authenticate(self):
            return None

        def prepare_workout(self, workout, *, threshold_value):
            return PreparedWorkoutDelivery(
            version=(
                seeded_delivery_version
                if reuse_delivery
                else "d" * 64
            ),
                request={},
                content_version="e" * 64,
            )

        def create_workout(self, prepared, *, hooks):
            hooks.before_mutation()
            calls["create"] += 1
            if calls["create"] == 1:
                raise ProviderRejectedError("temporary provider rejection")
            return ProviderCreateResult(
                external_id="restored-id",
                provider_account_id=self.account_id,
                response={"id": "restored-id"},
            )

        def delete_workout(self, external_id, *, hooks):
            hooks.before_mutation()
            calls["delete"] += 1
            return ProviderRemoveResult()

        def fetch_calendar(self, **kwargs):
            return []

    adapter = RetryAdapter()
    from api.routes import plan as plan_mod

    monkeypatch.setattr(
        plan_mod,
        "_resolve_stryd_delivery_cp",
        lambda data: 280.0,
    )
    monkeypatch.setattr(
        plan_mod,
        "load_plan_delivery_adapter",
        lambda *args, **kwargs: adapter,
    )
    payload = {
        "reconciliation_id": reconciliation_id,
        "action": "restore_praxys",
    }
    first = client.post("/api/plan/reconciliation/resolve", json=payload)
    assert first.status_code == 502, first.text
    second = client.post("/api/plan/reconciliation/resolve", json=payload)
    assert second.status_code == 200, second.text
    assert second.json()["external_id"] == "restored-id"
    assert calls == {"create": 2, "delete": 1}

    from db import session as db_session
    from db.models import PlanRevision

    db = db_session.SessionLocal()
    try:
        revisions = db.query(PlanRevision).filter(
            PlanRevision.user_id == user_id,
            PlanRevision.operation == "restore_target",
        ).all()
        assert len(revisions) == 1
    finally:
        db.close()
