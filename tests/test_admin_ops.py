"""Integration tests for the admin operations summary contract."""
from __future__ import annotations

import importlib
import tempfile
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    "reason",
    ["insufficient_detail", "sensitivity_or_privacy", "other"],
)
def test_semantic_eval_excludes_non_semantic_adjudication_reasons(
    reason: str,
) -> None:
    """Prompt comparison should not score privacy or evidence gate verdicts."""
    from api.admin_ops import _agent_eval_confusion

    row = SimpleNamespace(
        payload_json={
            "expected": False,
            "reason": reason,
        },
        output_json={
            "kind": "bug",
            "agent_ready_candidate": True,
            "gate_blocked": False,
        },
        input_json={
            "detail_word_count": 20,
            "detail_alnum_count": 100,
        },
    )

    assert _agent_eval_confusion(
        [row],
        challenger=False,
        semantic_only=False,
    ).evaluated == 1
    assert _agent_eval_confusion(
        [row],
        challenger=False,
        semantic_only=True,
    ).evaluated == 0


def test_semantic_eval_counts_prompt_kind_misclassification() -> None:
    """A positive defect reclassified as a feature remains a false negative."""
    from api.admin_ops import _agent_eval_confusion

    row = SimpleNamespace(
        payload_json={
            "expected": True,
            "reason": "bounded_actionable_defect",
        },
        output_json={
            "kind": "feature",
            "agent_ready_candidate": False,
            "gate_blocked": False,
        },
        input_json={
            "reported_kind": "bug",
            "detail_word_count": 20,
            "detail_alnum_count": 100,
        },
    )

    result = _agent_eval_confusion(
        [row],
        challenger=False,
        semantic_only=True,
    )
    assert result.evaluated == 1
    assert result.false_negatives == 1


def _build(monkeypatch, data_dir: str):
    monkeypatch.setenv("DATA_DIR", data_dir)
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )
    monkeypatch.setenv("PRAXYS_AUTH_RATE_LIMIT_DISABLED", "true")
    monkeypatch.delenv("PRAXYS_ADMIN_EMAIL", raising=False)

    from db import session as db_session

    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    import api.app_config
    import api.invitations
    import api.users

    importlib.reload(api.invitations)
    importlib.reload(api.app_config)
    importlib.reload(api.users)

    import api.main

    importlib.reload(api.main)
    return api.main, db_session


@pytest.fixture
def env(monkeypatch):
    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db_session = None
    try:
        main, db_session = _build(monkeypatch, tmp.name)
        with TestClient(main.app) as client:
            yield client, db_session
    finally:
        if db_session is not None:
            try:
                if db_session.engine is not None:
                    db_session.engine.dispose()
            except Exception:
                pass
        tmp.cleanup()


def _register(client, email: str, invitation_code: str = ""):
    return client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "pw123456",
            "accepted_terms": True,
            "invitation_code": invitation_code,
        },
    )


def _login(client, email: str) -> str:
    response = client.post(
        "/api/auth/login",
        data={"username": email, "password": "pw123456"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _admin_headers(client) -> dict[str, str]:
    response = _register(client, "admin@praxys.run")
    assert response.status_code == 200
    return {"Authorization": f"Bearer {_login(client, 'admin@praxys.run')}"}


def _collect_keys(value) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for child in value.values():
            keys.update(_collect_keys(child))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for child in value:
            keys.update(_collect_keys(child))
        return keys
    return set()


def _trusted_azure_snapshots():
    from api.admin_azure_monitor import AzureSectionSnapshot

    as_of = datetime.now(timezone.utc)
    return {
        "alerts": AzureSectionSnapshot(
            freshness="fresh",
            as_of=as_of,
            reason=None,
            data={
                "total": 2,
                "firing": 1,
                "resolved": 1,
                "severity": {"sev0": 0, "sev1": 0, "sev2": 2, "sev3": 0, "sev4": 0},
                "states": {"new": 1, "acknowledged": 0, "closed": 1},
                "rules": [
                    {
                        "rule": "praxys-sync-systemic-failures",
                        "severity": "Sev2",
                        "firing": 1,
                        "resolved": 1,
                        "last_changed_at": "2026-07-19T01:01:00Z",
                    }
                ],
            },
        ),
        "service": AzureSectionSnapshot(
            freshness="fresh",
            as_of=as_of,
            reason=None,
            data={
                "requests": 100,
                "failed_requests": 4,
                "server_errors": 2,
                "failed_request_rate": 0.04,
                "server_error_rate": 0.02,
                "p95_request_ms": 480.0,
                "availability_checks": 24,
                "failed_availability_checks": 1,
                "availability_rate": 23 / 24,
                "p95_availability_ms": 210.0,
                "database_health_failures": 0,
            },
        ),
        "product": AzureSectionSnapshot(
            freshness="fresh",
            as_of=as_of,
            reason=None,
            data={
                "surfaces": [
                    {
                        "surface": "web",
                        "app_users": 10,
                        "today_users": 8,
                        "today_reach_rate": 0.8,
                        "decision_prompts": 6,
                        "decision_responses": 4,
                        "decision_response_rate": 2 / 3,
                        "reported_value_rate": 0.75,
                        "repeated_users": 5,
                        "repeated_rate": 0.625,
                    }
                ],
                "coach": [
                    {
                        "insight_type": "daily_brief",
                        "useful_votes": 7,
                        "total_votes": 9,
                        "useful_rate": 7 / 9,
                    }
                ],
            },
        ),
        "platform": AzureSectionSnapshot(
            freshness="fresh",
            as_of=as_of,
            reason=None,
            data={
                "systemic_affected_users": 3,
                "sync": [
                    {
                        "platform": "garmin",
                        "attempts": 20,
                        "successes": 17,
                        "failures": 3,
                        "failure_rate": 0.15,
                    }
                ],
                "systemic_failures": [
                    {
                        "platform": "garmin",
                        "failure_class": "token_rejected",
                        "failures": 3,
                        "affected_users": 3,
                    }
                ],
                "connections": [
                    {
                        "platform": "garmin",
                        "flow": "mfa",
                        "stage": "mfa_verify",
                        "outcome": "connected",
                        "attempts": 4,
                    }
                ],
            },
        ),
        "managed": AzureSectionSnapshot(
            freshness="fresh",
            as_of=as_of,
            reason=None,
            data={
                "delivery_runs": 12,
                "complete_runs": 9,
                "partial_runs": 2,
                "blocked_runs": 1,
                "retry_runs": 3,
                "item_mutations": 18,
                "successful_mutations": 15,
                "failed_mutations": 3,
                "conflicts": 2,
                "provider_failures": 2,
                "auth_failures": 1,
                "praxys_failures": 0,
                "affected_users": 2,
                "p95_delivery_ms": 842.5,
                "adoptions": 4,
                "pauses": 1,
                "resumes": 1,
                "leaves": 0,
                "resolutions": 2,
                "cleanups": 1,
            },
        ),
    }


def test_ops_summary_admin_only_window_validation_and_no_store(env):
    client, _ = env
    assert client.get("/api/admin/ops/summary").status_code == 401

    admin_headers = _admin_headers(client)
    response = client.get("/api/admin/ops/summary?window=28d", headers=admin_headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["window"] == "28d"
    assert client.get(
        "/api/admin/ops/summary?window=30d", headers=admin_headers
    ).status_code == 422

    code = client.post("/api/admin/invitations", headers=admin_headers, json={}).json()["code"]
    assert _register(client, "runner@praxys.run", invitation_code=code).status_code == 200
    normal_headers = {"Authorization": f"Bearer {_login(client, 'runner@praxys.run')}"}
    assert client.get("/api/admin/ops/summary", headers=normal_headers).status_code == 403


def test_ops_summary_aggregates_attention_without_pii(env, monkeypatch):
    client, db_session = env
    admin_headers = _admin_headers(client)

    import api.admin_ops as admin_ops

    monkeypatch.setattr(
        admin_ops,
        "get_ops_telemetry",
        lambda window: _trusted_azure_snapshots(),
    )
    monkeypatch.setattr(
        admin_ops,
        "azure_portal_links",
        lambda: ("https://portal.azure.com/alerts", "https://portal.azure.com/logs"),
    )

    from db.agent_loop import record_decision, record_outcome
    from db.models import Feedback, ServiceIncident, User

    db = db_session.SessionLocal()
    admin = db.query(User).filter(User.email == "admin@praxys.run").one()
    db.add_all(
        [
            Feedback(
                user_id=admin.id,
                kind="bug",
                message="private critical feedback text",
                status="needs_review",
                priority="critical",
            ),
            Feedback(
                user_id=admin.id,
                kind="bug",
                message="private failed feedback text",
                status="failed",
                priority="high",
            ),
            Feedback(
                user_id=admin.id,
                kind="feature",
                message="private new feedback text",
                status="new",
            ),
            ServiceIncident(
                title="Elevated API latency",
                status="investigating",
                impact="critical",
                started_at=datetime.utcnow(),
            ),
        ]
    )
    decision = record_decision(
        db,
        loop="change",
        subject_type="feedback",
        subject_ref="123",
        policy_name="change.agent_ready",
        policy_version="agent-ready-v2",
        prompt_version="prompt-v1",
        model="test-model",
        mode="active",
        input_data={
            "message_sha256": "a" * 64,
            "detail_word_count": 8,
            "detail_alnum_count": 42,
        },
        output_data={
            "kind": "bug",
            "gate_blocked": False,
            "agent_ready_candidate": True,
            "agent_ready_applied": True,
            "challenger": {
                "available": True,
                "kind": "bug",
                "agent_ready_candidate": False,
            },
        },
    )
    record_outcome(
        db,
        decision_id=decision.id,
        outcome_type="human_rejected",
        source="admin",
        payload={"status": "rejected"},
    )
    record_outcome(
        db,
        decision_id=decision.id,
        outcome_type="github_pull_merged",
        source="github",
        payload={"pull_number": 42},
    )
    record_outcome(
        db,
        decision_id=decision.id,
        outcome_type="agent_ready_adjudicated",
        source="admin",
        payload={
            "expected": False,
            "reason": "not_a_defect",
            "active_candidate": True,
            "challenger_candidate": False,
            "label_sync": "synced",
        },
    )
    db.commit()
    admin_id = admin.id
    db.close()

    response = client.get("/api/admin/ops/summary?window=7d", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "generated_at",
        "window",
        "attention",
        "service_health",
        "product_value",
        "agent_learning",
        "service_telemetry",
        "product_telemetry",
        "azure_alerts",
        "platform_health",
        "managed_plan_telemetry",
        "managed_plans",
        "links",
    }

    attention = body["attention"]
    assert attention["source"] == "praxys_database"
    assert attention["window"] == "live"
    assert attention["freshness"] == "fresh"
    assert attention["as_of"]
    assert attention["data"]["incident_counts"] == {
        "total": 1,
        "minor": 0,
        "major": 0,
        "critical": 1,
    }
    assert attention["data"]["active_incidents"][0]["title"] == "Elevated API latency"
    assert attention["data"]["feedback"] == {
        "needs_review": 1,
        "failed": 1,
        "new": 1,
        "actionable": 2,
        "critical": 1,
        "high": 1,
        "total": 3,
    }

    assert body["service_health"]["freshness"] == "fresh"
    assert {c["key"] for c in body["service_health"]["data"]["components"]} == {
        "api",
        "database",
        "sync",
    }
    assert body["product_value"]["data"]["registered_users"] == 1
    assert body["product_value"]["data"]["directional"] is True
    assert body["agent_learning"]["data"] == {
        "decisions_total": 1,
        "outcomes_total": 3,
        "shadow_decisions": 0,
        "agent_ready_candidates": 1,
        "agent_ready_applied": 1,
        "human_overrides": 1,
        "merged_pull_requests": 1,
        "active_eval": {
            "evaluated": 1,
            "true_positives": 0,
            "true_negatives": 0,
            "false_positives": 1,
            "false_negatives": 0,
            "accuracy": 0.0,
        },
        "challenger_eval": {
            "evaluated": 1,
            "true_positives": 0,
            "true_negatives": 1,
            "false_positives": 0,
            "false_negatives": 0,
            "accuracy": 1.0,
        },
        "active_semantic_eval": {
            "evaluated": 1,
            "true_positives": 0,
            "true_negatives": 0,
            "false_positives": 1,
            "false_negatives": 0,
            "accuracy": 0.0,
        },
        "challenger_semantic_eval": {
            "evaluated": 1,
            "true_positives": 0,
            "true_negatives": 1,
            "false_positives": 0,
            "false_negatives": 0,
            "accuracy": 1.0,
        },
        "decision_policy_version": "agent-ready-v2",
        "review_policy_version": "selective-review-v2",
        "promoted_classes": [],
        "autonomy_level": "draft_with_review",
    }
    assert body["service_telemetry"]["data"]["server_error_rate"] == 0.02
    assert body["product_telemetry"]["data"]["surfaces"][0]["today_reach_rate"] == 0.8
    assert body["product_telemetry"]["window"] == "28d"
    assert body["product_telemetry"]["data"]["coach"][0]["useful_votes"] == 7
    assert body["azure_alerts"]["freshness"] == "fresh"
    assert body["azure_alerts"]["window"] == "7d"
    assert body["azure_alerts"]["data"]["firing"] == 1
    assert body["platform_health"]["freshness"] == "fresh"
    assert body["platform_health"]["data"]["systemic_affected_users"] == 3
    assert body["platform_health"]["data"]["systemic_failures"][0] == {
        "platform": "garmin",
        "failure_class": "token_rejected",
        "failures": 3,
        "affected_users": 3,
    }
    assert body["managed_plan_telemetry"]["freshness"] == "fresh"
    assert body["managed_plan_telemetry"]["data"]["delivery_runs"] == 12
    assert body["managed_plan_telemetry"]["data"]["p95_delivery_ms"] == 842.5
    assert body["managed_plans"]["source"] == "praxys_database"
    assert body["managed_plans"]["data"]["attention_required"] == 0
    assert body["links"]["azure_alerts"] == "https://portal.azure.com/alerts"
    assert body["links"]["azure_logs"] == "https://portal.azure.com/logs"
    assert body["links"]["telemetry_trust_issue"].endswith("/issues/417")

    forbidden_keys = {
        "email",
        "user_id",
        "user_id_hash",
        "message",
        "comment",
        "comment_excerpt",
        "invitation_code",
        "screenshot",
        "image_description",
    }
    assert not (forbidden_keys & _collect_keys(body))
    serialized = response.text
    assert "admin@praxys.run" not in serialized
    assert admin_id not in serialized
    assert "private critical feedback text" not in serialized


def test_ops_summary_partial_failure_isolated(env, monkeypatch):
    client, _ = env
    admin_headers = _admin_headers(client)

    import api.admin_ops as admin_ops

    def fail_attention(_db):
        raise RuntimeError("synthetic aggregate failure")

    monkeypatch.setattr(admin_ops, "_attention_data", fail_attention)
    response = client.get("/api/admin/ops/summary", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["attention"]["freshness"] == "unavailable"
    assert body["attention"]["data"] is None
    assert body["attention"]["reason"] == "section_refresh_failed"
    assert body["service_health"]["freshness"] == "fresh"
    assert body["product_value"]["freshness"] == "fresh"
    assert body["agent_learning"]["freshness"] == "fresh"
    assert body["service_telemetry"]["freshness"] == "unavailable"
    assert (
        body["service_telemetry"]["reason"]
        == "azure_telemetry_not_configured"
    )


def test_managed_plan_attention_is_admin_only_no_store_and_private(env):
    client, db_session = env
    admin_headers = _admin_headers(client)
    code = client.post(
        "/api/admin/invitations",
        headers=admin_headers,
        json={},
    ).json()["code"]
    assert _register(
        client,
        "runner@praxys.run",
        invitation_code=code,
    ).status_code == 200
    normal_headers = {
        "Authorization": f"Bearer {_login(client, 'runner@praxys.run')}"
    }

    from db.models import (
        PlanDelivery,
        PlanDeliveryAttempt,
        User,
    )

    db = db_session.SessionLocal()
    admin = db.query(User).filter(
        User.email == "admin@praxys.run"
    ).one()
    delivery = PlanDelivery(
        user_id=admin.id,
        canonical_key="ai:private-canonical-id",
        canonical_id="private-canonical-id",
        workout_date=date.today() + timedelta(days=1),
        workout_version="a" * 64,
        plan_version="a" * 64,
        target="stryd",
        state="conflict",
        external_id="private-provider-workout",
        provider_account_id="private-provider-account",
        last_error="runner@example.test private provider error",
    )
    db.add(delivery)
    db.flush()
    db.add(PlanDeliveryAttempt(
        delivery_id=delivery.id,
        attempt_number=1,
        operation="deliver",
        state="conflict",
        external_id="private-provider-workout",
        error="runner@example.test private attempt error",
        response={
            "managed_delivery": True,
            "retryable": False,
            "error_category": "provider_outcome_unknown",
        },
        completed_at=datetime.utcnow(),
    ))
    db.commit()
    admin_id = admin.id
    recovery_id = delivery.id
    db.close()

    assert client.get(
        "/api/admin/managed-plans/attention"
    ).status_code == 401
    assert client.get(
        "/api/admin/managed-plans/attention",
        headers=normal_headers,
    ).status_code == 403
    response = client.get(
        "/api/admin/managed-plans/attention",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    item = response.json()["items"][0]
    assert item["recovery_id"] == recovery_id
    assert item["issue"] == "provider_outcome_unknown"
    assert item["recovery_supported"] is False
    assert item["recovery_blocked_reason"] == "user_resolution_required"

    serialized = response.text
    assert admin_id not in serialized
    assert "private-canonical-id" not in serialized
    assert "private-provider-workout" not in serialized
    assert "private-provider-account" not in serialized
    assert "runner@example.test" not in serialized

    rejected = client.post(
        f"/api/admin/managed-plans/recover/{recovery_id}",
        headers=admin_headers,
        json={"expected_version": item["expected_version"]},
    )
    assert rejected.status_code == 409
    assert rejected.headers["cache-control"] == "private, no-store"
    assert rejected.json()["detail"] == {
        "code": "MANAGED_PLAN_RECOVERY_UNSUPPORTED",
        "message": "user_resolution_required",
    }


@pytest.mark.parametrize(
    ("error_type", "expected_code"),
    [
        (
            "busy",
            "MANAGED_PLAN_RECOVERY_BUSY",
        ),
        (
            "stale",
            "MANAGED_PLAN_RECOVERY_STALE",
        ),
        (
            "unsupported",
            "MANAGED_PLAN_RECOVERY_UNSUPPORTED",
        ),
    ],
)
def test_managed_plan_recovery_409_errors_are_discriminated(
    env,
    monkeypatch,
    error_type,
    expected_code,
):
    client, _ = env
    admin_headers = _admin_headers(client)

    from api.managed_plan_ops import (
        ManagedPlanRecoveryBusy,
        ManagedPlanRecoveryStale,
        ManagedPlanRecoveryUnsupported,
    )
    from api.routes import admin as admin_routes

    errors = {
        "busy": ManagedPlanRecoveryBusy("recovery busy"),
        "stale": ManagedPlanRecoveryStale("recovery stale"),
        "unsupported": ManagedPlanRecoveryUnsupported(
            "recovery unsupported"
        ),
    }

    def fail_recovery(*args, **kwargs):
        raise errors[error_type]

    monkeypatch.setattr(
        admin_routes,
        "recover_managed_plan_delivery",
        fail_recovery,
    )
    response = client.post(
        "/api/admin/managed-plans/recover/recovery-id",
        headers=admin_headers,
        json={"expected_version": "v" * 20},
    )

    assert response.status_code == 409
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["detail"]["code"] == expected_code
