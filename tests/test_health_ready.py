"""DB-backed readiness probe /api/health/ready (issue #350).

Mirrors the fresh-DB TestClient setup used by tests/test_version.py.
"""
import json

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
        "PRAXYS_CN_APPROVED_RELEASES",
        "PRAXYS_DISABLE_CN_PROCESSING",
        "PRAXYS_ENABLE_BACKGROUND_AI",
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

    return TestClient(app), db_session


def test_health_ready_ok(ready_env):
    client, _ = ready_env
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    assert r.json() == {
        "status": "ready",
        "database": "ok",
        "optional_processing": {
            "background_ai_enabled": False,
            "background_ai_positive_enable": False,
            "background_ai_kill_switch": True,
            "feedback_publication_enabled": False,
            "feedback_publication_positive_enable": False,
            "feedback_publication_kill_switch": True,
        },
        "china_processing": {
            "enabled": False,
            "disabled": True,
            "registry_configured": False,
            "approved_release_count": 0,
            "registry_sha256": None,
            "notice_version": TERMS_VERSION,
            "legal_digest": TERMS_CONTENT_DIGEST,
            "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
        },
    }


def test_optional_processing_requires_explicit_negative_switch_release(
    ready_env,
    monkeypatch,
):
    client, _ = ready_env
    monkeypatch.setenv("PRAXYS_ENABLE_BACKGROUND_AI", "true")
    monkeypatch.delenv("PRAXYS_DISABLE_BACKGROUND_AI", raising=False)
    monkeypatch.setenv("PRAXYS_ENABLE_FEEDBACK_PUBLICATION", "true")
    monkeypatch.delenv("PRAXYS_DISABLE_FEEDBACK_PUBLICATION", raising=False)

    response = client.get("/api/health/ready")

    assert response.status_code == 200
    assert response.json()["optional_processing"] == {
        "background_ai_enabled": False,
        "background_ai_positive_enable": True,
        "background_ai_kill_switch": True,
        "feedback_publication_enabled": False,
        "feedback_publication_positive_enable": True,
        "feedback_publication_kill_switch": True,
    }


def test_health_ready_ignores_cn_registry_while_disabled(
    ready_env,
    monkeypatch,
):
    from api.china_client_boundary import (
        APPROVED_RELEASES_ENV,
        approved_release_registry_digest,
        CN_PRIVACY_CONTRACT_VERSION,
        DISABLE_CN_PROCESSING_ENV,
    )
    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION

    client, _ = ready_env
    source_commit = "a" * 40
    monkeypatch.setenv(
        APPROVED_RELEASES_ENV,
        json.dumps([
            {
                "channel": "cn-web",
                "client_version": source_commit[:12],
                "source_id": source_commit[:12],
                "source_commit": source_commit,
                "notice_version": TERMS_VERSION,
                "terms_digest": TERMS_CONTENT_DIGEST,
                "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
                "release_id": "edgeone:test",
            }
        ]),
    )
    monkeypatch.setenv(DISABLE_CN_PROCESSING_ENV, "true")

    r = client.get("/api/health/ready")

    assert r.status_code == 200
    assert r.json()["china_processing"] == {
        "enabled": False,
        "disabled": True,
        "registry_configured": False,
        "approved_release_count": 0,
        "registry_sha256": None,
        "notice_version": TERMS_VERSION,
        "legal_digest": TERMS_CONTENT_DIGEST,
        "api_contract_version": CN_PRIVACY_CONTRACT_VERSION,
    }
    assert approved_release_registry_digest().startswith("sha256:")
    assert source_commit not in r.text
    assert "edgeone:test" not in r.text


def test_health_ready_ignores_malformed_cn_registry_while_disabled(
    ready_env,
    monkeypatch,
):
    client, _ = ready_env
    monkeypatch.setenv("PRAXYS_CN_APPROVED_RELEASES", "stale-malformed-json")
    monkeypatch.setenv("PRAXYS_DISABLE_CN_PROCESSING", "true")

    r = client.get("/api/health/ready")

    assert r.status_code == 200
    assert r.json()["china_processing"]["enabled"] is False
    assert r.json()["china_processing"]["registry_configured"] is False
    assert r.json()["china_processing"]["approved_release_count"] == 0
    assert r.json()["china_processing"]["registry_sha256"] is None


def test_health_ready_rejects_enabled_cn_processing_without_registry(
    ready_env,
    monkeypatch,
):
    client, _ = ready_env
    monkeypatch.delenv("PRAXYS_CN_APPROVED_RELEASES", raising=False)
    monkeypatch.setenv("PRAXYS_DISABLE_CN_PROCESSING", "false")

    r = client.get("/api/health/ready")

    assert r.status_code == 503
    assert r.json() == {
        "status": "unavailable",
        "database": "ok",
        "privacy_controls": "invalid",
    }


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