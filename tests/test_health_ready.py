"""DB-backed readiness probe /api/health/ready (issue #350).

Mirrors the fresh-DB TestClient setup used by tests/test_version.py.
"""
import pytest
from sqlalchemy import text


@pytest.fixture
def ready_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )
    monkeypatch.delenv("PRAXYS_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)

    from db import session as db_session

    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    from fastapi.testclient import TestClient
    from api.main import app

    return TestClient(app), db_session


def test_health_ready_ok(ready_env):
    client, _ = ready_env
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready", "database": "ok"}


def test_health_live_does_not_touch_db(ready_env):
    client, _ = ready_env
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_ready_503_when_db_unavailable(ready_env, monkeypatch):
    client, db_session = ready_env

    class _BrokenSession:
        def execute(self, *args, **kwargs):
            raise RuntimeError("simulated database outage")

        def close(self):
            pass

    monkeypatch.setattr(db_session, "SessionLocal", lambda: _BrokenSession())
    r = client.get("/api/health/ready")
    assert r.status_code == 503
    assert r.json() == {"status": "unavailable", "database": "error"}


def test_health_ready_503_for_inconsistent_existing_road_obligation(
    ready_env,
):
    client, db_session = ready_env
    from db.models import Road10KStageCounter

    with db_session.SessionLocal() as db:
        db.add(
            Road10KStageCounter(
                stage_id="road-10k-controlled-opt-in-v1",
                schema_version=2,
                capability_id="outdoor_road_10k_performance_v1",
                invitation_slots_consumed=1,
                distinct_exposed_owners_consumed=0,
                invitation_ceiling=60,
                exposure_ceiling=30,
            )
        )
        db.commit()

    response = client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "database": "error",
    }


def test_health_ready_503_when_road_deletion_replay_becomes_blocked(
    ready_env,
    monkeypatch,
):
    client, _ = ready_env
    from api import road_10k_deletion_storage

    monkeypatch.setattr(
        road_10k_deletion_storage,
        "replay_status",
        lambda: "blocked",
    )

    response = client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "database": "error",
    }


def test_health_ready_503_for_partial_road_schema(ready_env):
    client, db_session = ready_env
    from db.models import Road10KStageCounter

    with db_session.SessionLocal() as db:
        db.add(
            Road10KStageCounter(
                stage_id="road-10k-controlled-opt-in-v1",
                schema_version=2,
                capability_id="outdoor_road_10k_performance_v1",
                invitation_slots_consumed=0,
                distinct_exposed_owners_consumed=0,
                invitation_ceiling=60,
                exposure_ceiling=30,
            )
        )
        db.commit()
        db.execute(text("DROP TABLE road_10k_owner_stage_receipts"))
        db.commit()

    response = client.get("/api/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "database": "error",
    }