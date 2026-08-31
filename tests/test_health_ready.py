"""DB-backed readiness probe /api/health/ready (issue #350).

Mirrors the fresh-DB TestClient setup used by tests/test_version.py.
"""
import pytest

from api.china_client_boundary import CN_PRIVACY_CONTRACT_VERSION
from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION


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
    for name in (
        "PRAXYS_DISABLE_CN_PROCESSING",
        "PRAXYS_DISABLE_MINIAPP_PROCESSING",
        "PRAXYS_DISABLE_BACKGROUND_AI",
        "PRAXYS_ENABLE_FEEDBACK_PUBLICATION",
        "PRAXYS_DISABLE_FEEDBACK_PUBLICATION",
    ):
        monkeypatch.delenv(name, raising=False)

    from db import session as db_session

    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    from fastapi.testclient import TestClient
    from api.main import app

    with TestClient(app) as client:
        yield client, db_session


def test_health_ready_ok(ready_env):
    client, _ = ready_env
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    assert r.json() == {
        "status": "ready",
        "database": "ok",
        "optional_processing": {
            "background_ai_enabled": False,
            "background_ai_kill_switch": True,
            "feedback_publication_enabled": False,
            "feedback_publication_positive_enable": False,
            "feedback_publication_kill_switch": True,
        },
        "china_processing": {
            "enabled": False,
            "disabled": True,
            "notice_version": TERMS_VERSION,
            "legal_digest": TERMS_CONTENT_DIGEST,
            "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
        },
        "miniapp_processing": {
            "enabled": False,
            "disabled": True,
        },
    }


def test_ai_emergency_stop_does_not_fail_core_readiness(
    ready_env,
    monkeypatch,
):
    client, _ = ready_env
    monkeypatch.setenv("PRAXYS_DISABLE_BACKGROUND_AI", "true")

    response = client.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json()["optional_processing"]["background_ai_enabled"] is False
    assert response.json()["optional_processing"]["background_ai_kill_switch"] is True


def test_health_ready_reports_malformed_cn_switch_fail_closed(
    ready_env,
    monkeypatch,
):
    client, _ = ready_env
    monkeypatch.setenv("PRAXYS_DISABLE_CN_PROCESSING", "malformed")

    r = client.get("/api/health/ready")

    assert r.status_code == 200
    assert r.json()["status"] == "ready"
    assert r.json()["china_processing"]["enabled"] is False
    assert r.json()["china_processing"]["disabled"] is True


def test_health_ready_allows_cn_processing_without_registry(
    ready_env,
    monkeypatch,
):
    client, _ = ready_env
    monkeypatch.setenv("PRAXYS_DISABLE_CN_PROCESSING", "false")
    from api.channel_processing_authority import (
        reconcile_channel_processing_authority,
    )

    with ready_env[1].SessionLocal() as db:
        reconcile_channel_processing_authority(db)

    r = client.get("/api/health/ready")

    assert r.status_code == 200
    assert r.json()["china_processing"]["enabled"] is True
    assert r.json()["china_processing"]["disabled"] is False


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
