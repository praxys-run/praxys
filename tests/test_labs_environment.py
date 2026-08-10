"""Backend contract tests for the Labs environmental-response experiment."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import types
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def labs_client(monkeypatch):
    """Yield an authenticated client backed by an isolated SQLite database."""
    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", tmpdir.name)
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv("PRAXYS_AUTH_RATE_LIMIT_DISABLED", "true")
    monkeypatch.setenv("PRAXYS_LABS_EXECUTION_MODE", "disabled")
    monkeypatch.setenv(
        "PRAXYS_LOCAL_ENCRYPTION_KEY",
        "JKkx_5SVHKQDr0HSMrwl0KQHcA0pl5pxsYSLEAQDB4o=",
    )

    from db import session as db_session

    db_session.engine = None
    db_session.SessionLocal = None
    db_session.async_engine = None
    db_session.AsyncSessionLocal = None
    db_session.init_db()

    from api.auth import get_current_user_id, require_write_access
    from api.main import app
    from api.routes import labs as labs_routes
    from db.models import User
    from db.session import get_db

    user_id = "labs-owner"
    with db_session.SessionLocal() as db:
        db.add(User(
            id=user_id,
            email="labs-owner@example.com",
            hashed_password="x",
        ))
        db.commit()

    def override_user() -> str:
        return user_id

    def override_db():
        db = db_session.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(
        labs_routes,
        "dispatch_job",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        labs_routes,
        "environment_response_preflight",
        lambda *_args: {
            "status": "likely_eligible",
            "can_start_analysis": True,
            "reason_code": None,
            "minimum_activity_count": 12,
            "observed": {
                "candidate_activity_count": 12,
                "temperature_activity_count": 12,
                "humidity_activity_count": 12,
                "environment_activity_count": 12,
                "power_activity_count": 12,
                "heart_rate_activity_count": 12,
                "complete_any_provider_activity_count": 12,
                "stryd_power_activity_count": 12,
                "complete_stryd_activity_count": 12,
                "provider_aligned_cp_activity_count": 12,
            },
            "full_analysis_still_required": True,
        },
    )
    app.dependency_overrides[get_current_user_id] = override_user
    app.dependency_overrides[require_write_access] = override_user
    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app), db_session, user_id
    finally:
        app.dependency_overrides.clear()
        if db_session.engine is not None:
            db_session.engine.dispose()
        db_session.engine = None
        db_session.SessionLocal = None
        db_session.async_engine = None
        db_session.AsyncSessionLocal = None
        tmpdir.cleanup()


def _aggregate_result() -> dict:
    from analysis.environment_response import LABS_ENVIRONMENT_MODEL_VERSION

    return {
        "model_version": LABS_ENVIRONMENT_MODEL_VERSION,
        "power_regime": "stryd_continuous_samples",
        "result_state": "historical_association_only",
        "prediction_status": "failed_research_diagnostics",
        "eligibility_counts": {
            "input_activity_count": 24,
            "input_segment_count": 96,
            "eligible_activity_count": 20,
            "eligible_segment_count": 80,
            "exclusion_reason_counts": {},
            "provider_regimes": [{
                "label": "power=stryd|heart_rate=stryd",
                "activity_count": 20,
                "segment_count": 80,
            }],
            "workload_support": {
                "policy": "training_median_centered_v1",
                "training_median_pct_cp": 74.8,
                "personal_display_pct_cp": [65.0, 84.8],
                "half_width_percentage_points": 10.0,
                "model_eligible_pct_cp": [65.0, 95.0],
                "display_filter_applied_to_model_rows": False,
            },
        },
        "aggregate_curve_points": [
            {
                "wet_bulb_c": 20.0,
                "modeled_hr_bpm": 150.0,
                "relative_hr_bpm": 0.0,
                "relative_lower_bpm": 0.0,
                "relative_upper_bpm": 0.0,
                "reference_wet_bulb_c": 20.0,
                "support_bin_index": 0,
                "section_index": 0,
            },
        ],
        "aggregate_uncertainty": {
            "estimate_bpm_per_c": 0.3,
            "interval_bpm_per_c": [0.1, 0.4],
        },
        "gate_statuses": {"minimum_activities": "pass"},
        "limitations": ["historical_association_not_causal"],
    }


def test_enrollment_requires_current_consent_and_adult_attestation(
    labs_client,
) -> None:
    client, _, _ = labs_client

    adult = client.post(
        "/api/labs/environment-response",
        json={
            "adult_attested": False,
            "consent_version": "environment-response-consent-v1",
        },
    )
    stale = client.post(
        "/api/labs/environment-response",
        json={
            "adult_attested": True,
            "consent_version": "old",
        },
    )
    coercive = client.post(
        "/api/labs/environment-response",
        json={
            "adult_attested": "true",
            "consent_version": "environment-response-consent-v1",
        },
    )

    assert adult.status_code == 422
    assert adult.json()["detail"]["code"] == "adult_eligibility_not_confirmed"
    assert adult.json()["detail"]["correlation_id"]
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "consent_version_stale"
    assert stale.json()["detail"]["current_consent_version"] == (
        "environment-response-consent-v1"
    )
    assert coercive.status_code == 422


def test_preflight_returns_aggregate_only_eligibility(labs_client) -> None:
    client, _, _ = labs_client

    response = client.get("/api/labs/environment-response/preflight")

    assert response.status_code == 200
    assert response.json()["status"] == "likely_eligible"
    assert response.json()["can_start_analysis"] is True
    assert response.json()["full_analysis_still_required"] is True
    assert "activity_id" not in json.dumps(response.json())


def test_ineligible_preflight_blocks_enrollment(
    labs_client,
    monkeypatch,
) -> None:
    client, _, _ = labs_client
    from api.routes import labs as labs_routes

    blocked = {
        "status": "ineligible",
        "can_start_analysis": False,
        "reason_code": "missing_temperature",
        "minimum_activity_count": 12,
        "observed": {
            "candidate_activity_count": 20,
            "temperature_activity_count": 4,
            "humidity_activity_count": 20,
            "environment_activity_count": 4,
            "power_activity_count": 20,
            "heart_rate_activity_count": 20,
            "complete_any_provider_activity_count": 4,
            "stryd_power_activity_count": 20,
            "complete_stryd_activity_count": 4,
            "provider_aligned_cp_activity_count": 20,
        },
        "full_analysis_still_required": True,
    }
    monkeypatch.setattr(
        labs_routes,
        "environment_response_preflight",
        lambda *_args: blocked,
    )

    response = client.post(
        "/api/labs/environment-response",
        json={
            "adult_attested": True,
            "consent_version": "environment-response-consent-v1",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == (
        "LABS_ENVIRONMENT_PREFLIGHT_INELIGIBLE"
    )
    assert response.json()["detail"]["preflight"] == blocked


def test_ineligible_preflight_blocks_recompute(
    labs_client,
    monkeypatch,
) -> None:
    client, db_session, user_id = labs_client
    from api.routes import labs as labs_routes
    from db.models import LabsAnalysisJob, LabsExperimentEnrollment

    enrolled = client.post(
        "/api/labs/environment-response",
        json={
            "adult_attested": True,
            "consent_version": "environment-response-consent-v1",
        },
    )
    preflight = client.get("/api/labs/environment-response/preflight")
    assert enrolled.status_code == 202
    assert enrolled.json()["consented_at"].endswith("+00:00")
    assert enrolled.json()["execution"]["requested_at"].endswith("+00:00")
    with db_session.SessionLocal() as db:
        job = db.query(LabsAnalysisJob).filter(
            LabsAnalysisJob.user_id == user_id,
        ).one()
        row = db.get(
            LabsExperimentEnrollment,
            (user_id, "environment-response-v1"),
        )
        job.status = "succeeded"
        row.status = "unavailable"
        db.commit()
    blocked = {
        "status": "ineligible",
        "can_start_analysis": False,
        "reason_code": "unsupported_power_provider",
        "minimum_activity_count": 12,
        "observed": preflight.json()["observed"],
        "full_analysis_still_required": True,
    }
    monkeypatch.setattr(
        labs_routes,
        "environment_response_preflight",
        lambda *_args: blocked,
    )

    response = client.post("/api/labs/environment-response/recompute")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == (
        "LABS_ENVIRONMENT_PREFLIGHT_INELIGIBLE"
    )


def test_recompute_not_enrolled_returns_structured_error(labs_client) -> None:
    client, _, _ = labs_client

    response = client.post("/api/labs/environment-response/recompute")

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "LABS_ENVIRONMENT_NOT_ENROLLED",
        "message": "Current experiment consent is required.",
    }


@pytest.mark.parametrize(
    "configured",
    [
        None,
        {"cooldown_hours": True, "window_hours": 24, "max_requests": 3},
        {"cooldown_hours": -1, "window_hours": 24, "max_requests": 3},
        {"cooldown_hours": 25, "window_hours": 24, "max_requests": 3},
        {"cooldown_hours": 6, "window_hours": 0, "max_requests": 3},
        {"cooldown_hours": 6, "window_hours": 24, "max_requests": 0},
    ],
)
def test_invalid_recompute_dynamic_config_uses_defaults(
    labs_client,
    monkeypatch,
    configured,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment

    monkeypatch.setattr(
        labs_environment,
        "get_config",
        lambda *_args: configured,
    )

    with db_session.SessionLocal() as db:
        policy = labs_environment._manual_recompute_policy(db, user_id)

    assert policy == labs_environment.DEFAULT_MANUAL_RECOMPUTE_POLICY


def test_recompute_dynamic_config_can_bypass_cooldown(
    labs_client,
    monkeypatch,
) -> None:
    client, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsAnalysisJob, LabsExperimentEnrollment

    monkeypatch.setattr(
        labs_environment,
        "get_config",
        lambda *_args: {
            "cooldown_hours": 0,
            "window_hours": 12,
            "max_requests": 10,
        },
    )
    enrolled = client.post(
        "/api/labs/environment-response",
        headers={"Idempotency-Key": "enroll-config-bypass-1"},
        json={
            "adult_attested": True,
            "consent_version": labs_environment.CONSENT_VERSION,
        },
    )
    assert enrolled.status_code == 202
    with db_session.SessionLocal() as db:
        job = db.query(LabsAnalysisJob).filter(
            LabsAnalysisJob.user_id == user_id,
        ).one()
        row = db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        job.status = "succeeded"
        job.completed_at = datetime.utcnow()
        row.status = "unavailable"
        row.completed_at = job.completed_at
        db.commit()

    first = client.post(
        "/api/labs/environment-response/recompute",
        headers={"Idempotency-Key": "config-bypass-manual-1"},
    )
    assert first.status_code == 202
    with db_session.SessionLocal() as db:
        job = db.query(LabsAnalysisJob).filter(
            LabsAnalysisJob.idempotency_key == "config-bypass-manual-1",
        ).one()
        row = db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        job.status = "succeeded"
        job.completed_at = datetime.utcnow()
        row.status = "unavailable"
        row.completed_at = job.completed_at
        db.commit()

    state = client.get("/api/labs/environment-response")
    policy = state.json()["execution"]["recompute"]
    assert policy == {
        "allowed": True,
        "reason": None,
        "available_at": None,
        "retry_after_seconds": None,
        "remaining_requests": 9,
        "window_hours": 12,
        "cooldown_hours": 0,
    }
    second = client.post(
        "/api/labs/environment-response/recompute",
        headers={"Idempotency-Key": "config-bypass-manual-2"},
    )
    assert second.status_code == 202


def test_recompute_api_returns_retry_after_during_cooldown(
    labs_client,
) -> None:
    client, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsAnalysisJob, LabsExperimentEnrollment

    enrolled = client.post(
        "/api/labs/environment-response",
        headers={"Idempotency-Key": "enroll-cooldown-1"},
        json={
            "adult_attested": True,
            "consent_version": labs_environment.CONSENT_VERSION,
        },
    )
    assert enrolled.status_code == 202
    with db_session.SessionLocal() as db:
        job = db.query(LabsAnalysisJob).filter(
            LabsAnalysisJob.user_id == user_id,
        ).one()
        row = db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        job.status = "succeeded"
        job.completed_at = datetime.utcnow()
        row.status = "unavailable"
        row.completed_at = job.completed_at
        db.commit()

    first = client.post(
        "/api/labs/environment-response/recompute",
        headers={"Idempotency-Key": "manual-cooldown-1"},
    )
    assert first.status_code == 202
    with db_session.SessionLocal() as db:
        job = db.query(LabsAnalysisJob).filter(
            LabsAnalysisJob.idempotency_key == "manual-cooldown-1",
        ).one()
        row = db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        job.status = "succeeded"
        job.completed_at = datetime.utcnow()
        row.status = "unavailable"
        row.completed_at = job.completed_at
        db.commit()

    limited = client.post(
        "/api/labs/environment-response/recompute",
        headers={"Idempotency-Key": "manual-cooldown-2"},
    )

    assert limited.status_code == 429
    assert limited.json()["detail"]["code"] == (
        "LABS_ENVIRONMENT_RECOMPUTE_COOLDOWN"
    )
    assert limited.json()["detail"]["available_at"].endswith("+00:00")
    assert int(limited.headers["retry-after"]) > 0


def test_labs_mutations_reject_malformed_idempotency_keys(
    labs_client,
) -> None:
    client, _, _ = labs_client
    from api import labs_environment

    enroll_response = client.post(
        "/api/labs/environment-response",
        headers={"Idempotency-Key": "invalid key"},
        json={
            "adult_attested": True,
            "consent_version": labs_environment.CONSENT_VERSION,
        },
    )
    recompute_response = client.post(
        "/api/labs/environment-response/recompute",
        headers={"Idempotency-Key": "invalid key"},
    )

    assert enroll_response.status_code == 422
    assert recompute_response.status_code == 422


def test_idempotent_replays_do_not_rerun_preflight(
    labs_client,
    monkeypatch,
) -> None:
    client, db_session, user_id = labs_client
    from api import labs_environment
    from api.routes import labs as labs_routes
    from db.models import LabsAnalysisJob, LabsExperimentEnrollment

    enroll_response = client.post(
        "/api/labs/environment-response",
        headers={"Idempotency-Key": "enroll-replay-1"},
        json={
            "adult_attested": True,
            "consent_version": labs_environment.CONSENT_VERSION,
        },
    )
    assert enroll_response.status_code == 202
    with db_session.SessionLocal() as db:
        enrollment_job = db.query(LabsAnalysisJob).filter(
            LabsAnalysisJob.trigger == "enrollment",
        ).one()
        row = db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        enrollment_job.status = "succeeded"
        row.status = "unavailable"
        db.commit()

    recompute_response = client.post(
        "/api/labs/environment-response/recompute",
        headers={"Idempotency-Key": "recompute-replay-1"},
    )
    assert recompute_response.status_code == 202

    blocked = {
        "status": "ineligible",
        "can_start_analysis": False,
        "reason_code": "unsupported_power_provider",
        "minimum_activity_count": 12,
        "observed": {},
        "full_analysis_still_required": True,
    }
    monkeypatch.setattr(
        labs_routes,
        "environment_response_preflight",
        lambda *_args: blocked,
    )

    replay_enroll = client.post(
        "/api/labs/environment-response",
        headers={"Idempotency-Key": "enroll-replay-1"},
        json={
            "adult_attested": True,
            "consent_version": labs_environment.CONSENT_VERSION,
        },
    )
    replay_recompute = client.post(
        "/api/labs/environment-response/recompute",
        headers={"Idempotency-Key": "recompute-replay-1"},
    )

    assert replay_enroll.status_code == 202
    assert replay_recompute.status_code == 202
    with db_session.SessionLocal() as db:
        assert db.query(LabsAnalysisJob).count() == 2


@pytest.mark.parametrize(
    ("counts", "expected_status", "expected_reason"),
    [
        (
            {"candidate_activity_count": 5},
            "ineligible",
            "insufficient_activities",
        ),
        (
            {
                "candidate_activity_count": 20,
                "temperature_activity_count": 20,
                "humidity_activity_count": 20,
                "environment_activity_count": 20,
                "power_activity_count": 20,
                "heart_rate_activity_count": 20,
                "stryd_power_activity_count": 20,
                "complete_any_provider_activity_count": 18,
                "complete_stryd_activity_count": 14,
                "provider_aligned_cp_activity_count": 14,
            },
            "needs_full_analysis",
            "provider_alignment_requires_full_analysis",
        ),
        (
            {
                "candidate_activity_count": 20,
                "temperature_activity_count": 20,
                "humidity_activity_count": 20,
                "environment_activity_count": 20,
                "power_activity_count": 20,
                "heart_rate_activity_count": 20,
                "stryd_power_activity_count": 20,
                "complete_any_provider_activity_count": 14,
                "complete_stryd_activity_count": 14,
                "provider_aligned_cp_activity_count": 14,
            },
            "likely_eligible",
            None,
        ),
    ],
)
def test_preflight_classifies_only_definite_blockers(
    counts,
    expected_status,
    expected_reason,
) -> None:
    from analysis.environment_response import (
        assess_environment_response_preflight,
    )

    result = assess_environment_response_preflight(counts)

    assert result["status"] == expected_status
    assert result["reason_code"] == expected_reason
    assert result["can_start_analysis"] is (
        expected_status != "ineligible"
    )
    assert result["full_analysis_still_required"] is True


@pytest.mark.parametrize(
    ("field", "value", "expected_reason"),
    [
        ("environment_activity_count", 11, "missing_environment_pairing"),
        ("power_activity_count", 11, "missing_continuous_sample_power"),
        ("heart_rate_activity_count", 11, "missing_continuous_heart_rate"),
        ("complete_any_provider_activity_count", 11, "insufficient_prerequisite_overlap"),
        ("stryd_power_activity_count", 11, "unsupported_power_provider"),
        ("complete_stryd_activity_count", 11, "insufficient_prerequisite_overlap"),
        ("provider_aligned_cp_activity_count", 11, "missing_provider_aligned_critical_power"),
    ],
)
def test_preflight_rejects_each_definite_prerequisite_failure(
    field,
    value,
    expected_reason,
) -> None:
    from analysis.environment_response import (
        assess_environment_response_preflight,
    )

    counts = {
        "candidate_activity_count": 20,
        "temperature_activity_count": 20,
        "humidity_activity_count": 20,
        "environment_activity_count": 20,
        "power_activity_count": 20,
        "heart_rate_activity_count": 20,
        "complete_any_provider_activity_count": 20,
        "stryd_power_activity_count": 20,
        "complete_stryd_activity_count": 20,
        "provider_aligned_cp_activity_count": 20,
    }
    counts[field] = value

    result = assess_environment_response_preflight(counts)

    assert result["status"] == "ineligible"
    assert result["reason_code"] == expected_reason


def test_preflight_loader_returns_only_aggregate_prerequisites(
    labs_client,
) -> None:
    _, db_session, user_id = labs_client
    from analysis.data_loader import load_environment_response_preflight_counts
    from analysis.heat_response_validation import HeatValidationConfig
    from db.models import Activity, ActivitySample, FitnessData

    with db_session.SessionLocal() as db:
        for index in range(12):
            activity_id = f"preflight-{index}"
            db.add(Activity(
                user_id=user_id,
                activity_id=activity_id,
                date=datetime(2026, 1, index + 1).date(),
                activity_type="running",
                temperature_c=20.0 + index,
                relative_humidity_pct=60.0,
                source="garmin",
            ))
            for sample_index in range(37):
                db.add(ActivitySample(
                    user_id=user_id,
                    activity_id=activity_id,
                    source="stryd",
                    t_sec=sample_index * 5,
                    power_watts=250.0,
                    hr_bpm=None,
                ))
                db.add(ActivitySample(
                    user_id=user_id,
                    activity_id=activity_id,
                    source="garmin",
                    t_sec=sample_index * 5 + 1,
                    power_watts=None,
                    hr_bpm=150.0,
                ))
        db.add(FitnessData(
            user_id=user_id,
            date=datetime(2025, 12, 31).date(),
            metric_type="cp_estimate",
            value=300.0,
            source="stryd",
            power_source="   ",
        ))
        db.commit()

        counts = load_environment_response_preflight_counts(
            user_id,
            db,
            eligible_activity_types=HeatValidationConfig().eligible_activity_types,
            minimum_segment_duration_sec=180.0,
            maximum_sample_interval_sec=5.0,
            minimum_heart_rate_coverage_ratio=0.8,
            maximum_power_watts=2500.0,
        )

        assert counts["candidate_activity_count"] == 12
        assert counts["complete_stryd_activity_count"] == 12
        assert counts["provider_aligned_cp_activity_count"] == 12
        assert "activity_id" not in counts

        db.query(FitnessData).delete()
        db.add(FitnessData(
            user_id=user_id,
            date=datetime(2026, 1, 6).date(),
            metric_type="cp_estimate",
            value=300.0,
            source="garmin",
            power_source="stryd",
        ))
        db.commit()
        chronological_counts = load_environment_response_preflight_counts(
            user_id,
            db,
            eligible_activity_types=HeatValidationConfig().eligible_activity_types,
            minimum_segment_duration_sec=180.0,
            maximum_sample_interval_sec=5.0,
            minimum_heart_rate_coverage_ratio=0.8,
            maximum_power_watts=2500.0,
        )

    assert chronological_counts["provider_aligned_cp_activity_count"] == 6


def test_preflight_loader_allows_one_final_sample_interval(
    labs_client,
) -> None:
    _, db_session, user_id = labs_client
    from analysis.data_loader import load_environment_response_preflight_counts
    from analysis.heat_response_validation import HeatValidationConfig
    from db.models import Activity, ActivitySample

    with db_session.SessionLocal() as db:
        for index in range(12):
            activity_id = f"boundary-preflight-{index}"
            db.add(Activity(
                user_id=user_id,
                activity_id=activity_id,
                date=datetime(2026, 1, index + 1).date(),
                activity_type="running",
                temperature_c=20.0,
                relative_humidity_pct=60.0,
                source="stryd",
            ))
            for sample_index in range(37):
                t_sec = sample_index * 5
                db.add(ActivitySample(
                    user_id=user_id,
                    activity_id=activity_id,
                    source="stryd",
                    t_sec=t_sec,
                    power_watts=250.0 if t_sec <= 175 else None,
                    hr_bpm=150.0 if t_sec <= 140 else None,
                ))
        db.commit()

        counts = load_environment_response_preflight_counts(
            user_id,
            db,
            eligible_activity_types=HeatValidationConfig().eligible_activity_types,
            minimum_segment_duration_sec=180.0,
            maximum_sample_interval_sec=5.0,
            minimum_heart_rate_coverage_ratio=0.8,
            maximum_power_watts=2500.0,
        )

    assert counts["power_activity_count"] == 12
    assert counts["heart_rate_activity_count"] == 12
    assert counts["complete_stryd_activity_count"] == 12


def test_preflight_loader_defers_fragmented_power_to_full_analysis(
    labs_client,
) -> None:
    _, db_session, user_id = labs_client
    from analysis.data_loader import load_environment_response_preflight_counts
    from analysis.heat_response_validation import HeatValidationConfig
    from db.models import Activity, ActivitySample

    with db_session.SessionLocal() as db:
        for index in range(12):
            activity_id = f"sparse-preflight-{index}"
            db.add(Activity(
                user_id=user_id,
                activity_id=activity_id,
                date=datetime(2026, 2, index + 1).date(),
                activity_type="running",
                temperature_c=20.0,
                relative_humidity_pct=60.0,
                source="garmin",
            ))
            for sample_index in range(21):
                for offset in (0, 300):
                    db.add(ActivitySample(
                        user_id=user_id,
                        activity_id=activity_id,
                        source="stryd",
                        t_sec=offset + sample_index * 5,
                        power_watts=250.0,
                        hr_bpm=150.0,
                    ))
        db.commit()

        counts = load_environment_response_preflight_counts(
            user_id,
            db,
            eligible_activity_types=HeatValidationConfig().eligible_activity_types,
            minimum_segment_duration_sec=180.0,
            maximum_sample_interval_sec=5.0,
            minimum_heart_rate_coverage_ratio=0.8,
            maximum_power_watts=2500.0,
        )

    assert counts["candidate_activity_count"] == 12
    assert counts["power_activity_count"] == 12
    assert counts["complete_stryd_activity_count"] == 12


def test_preflight_loader_defers_sample_overlap_to_full_analysis(
    labs_client,
) -> None:
    _, db_session, user_id = labs_client
    from analysis.data_loader import load_environment_response_preflight_counts
    from analysis.heat_response_validation import HeatValidationConfig
    from db.models import Activity, ActivitySample

    with db_session.SessionLocal() as db:
        for index in range(12):
            activity_id = f"nonoverlap-preflight-{index}"
            db.add(Activity(
                user_id=user_id,
                activity_id=activity_id,
                date=datetime(2026, 3, index + 1).date(),
                activity_type="running",
                temperature_c=20.0,
                relative_humidity_pct=60.0,
                source="garmin",
            ))
            for sample_index in range(37):
                db.add(ActivitySample(
                    user_id=user_id,
                    activity_id=activity_id,
                    source="stryd",
                    t_sec=sample_index * 5,
                    power_watts=250.0,
                ))
            for sample_index in range(30):
                db.add(ActivitySample(
                    user_id=user_id,
                    activity_id=activity_id,
                    source="garmin",
                    t_sec=300 + sample_index * 5,
                    hr_bpm=150.0,
                ))
        db.commit()

        counts = load_environment_response_preflight_counts(
            user_id,
            db,
            eligible_activity_types=HeatValidationConfig().eligible_activity_types,
            minimum_segment_duration_sec=180.0,
            maximum_sample_interval_sec=5.0,
            minimum_heart_rate_coverage_ratio=0.8,
            maximum_power_watts=2500.0,
        )

    assert counts["stryd_power_activity_count"] == 12
    assert counts["heart_rate_activity_count"] == 12
    assert counts["complete_stryd_activity_count"] == 12


def test_preflight_loader_defers_hr_window_coverage_to_full_analysis(
    labs_client,
) -> None:
    _, db_session, user_id = labs_client
    from analysis.data_loader import load_environment_response_preflight_counts
    from analysis.heat_response_validation import HeatValidationConfig
    from db.models import Activity, ActivitySample

    with db_session.SessionLocal() as db:
        for index in range(12):
            activity_id = f"distributed-hr-{index}"
            db.add(Activity(
                user_id=user_id,
                activity_id=activity_id,
                date=datetime(2026, 4, index + 1).date(),
                activity_type="running",
                temperature_c=20.0,
                relative_humidity_pct=60.0,
                source="garmin",
            ))
            for sample_index in range(121):
                db.add(ActivitySample(
                    user_id=user_id,
                    activity_id=activity_id,
                    source="stryd",
                    t_sec=sample_index * 5,
                    power_watts=250.0,
                ))
            for burst_index in range(15):
                for offset in (1, 6, 11):
                    db.add(ActivitySample(
                        user_id=user_id,
                        activity_id=activity_id,
                        source="garmin",
                        t_sec=burst_index * 40 + offset,
                        hr_bpm=150.0,
                    ))
        db.commit()

        counts = load_environment_response_preflight_counts(
            user_id,
            db,
            eligible_activity_types=HeatValidationConfig().eligible_activity_types,
            minimum_segment_duration_sec=180.0,
            maximum_sample_interval_sec=5.0,
            minimum_heart_rate_coverage_ratio=0.8,
            maximum_power_watts=2500.0,
        )

    assert counts["stryd_power_activity_count"] == 12
    assert counts["heart_rate_activity_count"] == 12
    assert counts["complete_stryd_activity_count"] == 12


@pytest.mark.parametrize("invalid_power_watts", [0.0, 3000.0])
def test_preflight_loader_defers_internal_sample_gaps_to_full_analysis(
    labs_client,
    invalid_power_watts,
) -> None:
    _, db_session, user_id = labs_client
    from analysis.data_loader import load_environment_response_preflight_counts
    from analysis.heat_response_validation import HeatValidationConfig
    from db.models import Activity, ActivitySample

    with db_session.SessionLocal() as db:
        for index in range(12):
            activity_id = f"invalid-samples-{index}"
            db.add(Activity(
                user_id=user_id,
                activity_id=activity_id,
                date=datetime(2026, 5, index + 1).date(),
                activity_type="running",
                temperature_c=20.0,
                relative_humidity_pct=60.0,
                source="garmin",
            ))
            for sample_index in range(37):
                db.add(ActivitySample(
                    user_id=user_id,
                    activity_id=activity_id,
                    source="stryd",
                    t_sec=sample_index * 5,
                    power_watts=(
                        invalid_power_watts if sample_index == 18 else 250.0
                    ),
                    hr_bpm=(
                        300.0 if sample_index % 3 == 2 else 150.0
                    ),
                ))
        db.commit()

        counts = load_environment_response_preflight_counts(
            user_id,
            db,
            eligible_activity_types=HeatValidationConfig().eligible_activity_types,
            minimum_segment_duration_sec=180.0,
            maximum_sample_interval_sec=5.0,
            minimum_heart_rate_coverage_ratio=0.8,
            maximum_power_watts=2500.0,
        )

    assert counts["power_activity_count"] == 12
    assert counts["heart_rate_activity_count"] == 12
    assert counts["complete_stryd_activity_count"] == 12


def test_preflight_loader_avoids_full_analysis_window_expansion() -> None:
    """The preflight must remain a single bounded sample aggregation."""
    from analysis.data_loader import load_environment_response_preflight_counts
    from analysis.heat_response_validation import HeatValidationConfig

    class _CapturedResult:
        def mappings(self):
            return self

        def one(self):
            return {
                "candidate_activity_count": 0,
                "temperature_activity_count": 0,
                "humidity_activity_count": 0,
                "environment_activity_count": 0,
                "power_activity_count": 0,
                "heart_rate_activity_count": 0,
                "complete_any_provider_activity_count": 0,
                "stryd_power_activity_count": 0,
                "complete_stryd_activity_count": 0,
                "provider_aligned_cp_activity_count": 0,
            }

    class _CapturingSession:
        statement = ""

        def execute(self, statement, _parameters):
            self.statement = str(statement)
            return _CapturedResult()

    db = _CapturingSession()
    load_environment_response_preflight_counts(
        "owner",
        db,  # type: ignore[arg-type]
        eligible_activity_types=HeatValidationConfig().eligible_activity_types,
        minimum_segment_duration_sec=180.0,
        maximum_sample_interval_sec=5.0,
        minimum_heart_rate_coverage_ratio=0.8,
        maximum_power_watts=2500.0,
    )

    assert db.statement.count("FROM activity_samples AS sample") == 1
    assert "LEAD(" not in db.statement
    assert "power_window" not in db.statement
    assert "coverage_intervals" not in db.statement


def test_wet_bulb_calculator_uses_versioned_stull_method(labs_client) -> None:
    client, _, _ = labs_client

    response = client.post(
        "/api/labs/environment-response/wet-bulb",
        json={"temperature_c": 25.0, "relative_humidity_pct": 60.0},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "temperature_c": 25.0,
        "relative_humidity_pct": 60.0,
        "wet_bulb_c": 19.5,
        "within_method_domain": True,
        "method": "stull_psychrometric",
        "source_url": "https://doi.org/10.1175/JAMC-D-11-0143.1",
        "limitation_code": "psychrometric_proxy_not_wbgt",
    }

    outside = client.post(
        "/api/labs/environment-response/wet-bulb",
        json={"temperature_c": -5.0, "relative_humidity_pct": 20.0},
    )
    assert outside.status_code == 200
    assert outside.json()["wet_bulb_c"] is None
    assert outside.json()["limitation_code"] == "outside_method_domain"

    string_input = client.post(
        "/api/labs/environment-response/wet-bulb",
        json={"temperature_c": "25", "relative_humidity_pct": 60.0},
    )
    assert string_input.status_code == 422

    from pydantic import ValidationError
    from api.routes.labs import EnvironmentWetBulbRequest

    with pytest.raises(ValidationError):
        EnvironmentWetBulbRequest.model_validate({
            "temperature_c": float("nan"),
            "relative_humidity_pct": 60.0,
        })


def test_enroll_get_withdraw_and_rejoin_lifecycle(labs_client) -> None:
    client, db_session, user_id = labs_client
    from db.models import (
        LabsDeletionTombstone,
        LabsExperimentEnrollment,
    )

    enrolled = client.post(
        "/api/labs/environment-response",
        json={
            "adult_attested": True,
            "consent_version": "environment-response-consent-v1",
        },
    )
    state = client.get("/api/labs/environment-response")
    withdrawn = client.delete("/api/labs/environment-response")

    assert enrolled.status_code == 202
    assert enrolled.json()["status"] == "queued"
    assert state.status_code == 200
    assert state.json()["enrolled"] is True
    assert withdrawn.status_code == 204
    with db_session.SessionLocal() as db:
        assert db.get(
            LabsExperimentEnrollment,
            (user_id, "environment-response-v1"),
        ) is None
        assert db.get(
            LabsDeletionTombstone,
            (user_id, "environment-response-v1"),
        ) is not None

    rejoined = client.post(
        "/api/labs/environment-response",
        json={
            "adult_attested": True,
            "consent_version": "environment-response-consent-v1",
        },
    )
    assert rejoined.status_code == 202
    assert rejoined.json()["enrolled"] is True


def test_withdrawal_wins_over_an_old_enrollment_replay(
    labs_client,
) -> None:
    client, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsAnalysisJob, LabsExperimentEnrollment

    headers = {"Idempotency-Key": "withdrawal-replay-key"}
    body = {
        "adult_attested": True,
        "consent_version": labs_environment.CONSENT_VERSION,
    }
    enrolled = client.post(
        "/api/labs/environment-response",
        headers=headers,
        json=body,
    )
    withdrawn = client.delete("/api/labs/environment-response")
    replay = client.post(
        "/api/labs/environment-response",
        headers=headers,
        json=body,
    )

    assert enrolled.status_code == 202
    assert withdrawn.status_code == 204
    assert replay.status_code == 202
    assert replay.json()["enrolled"] is False
    with db_session.SessionLocal() as db:
        assert db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        ) is None
        assert db.query(LabsAnalysisJob).filter(
            LabsAnalysisJob.user_id == user_id,
        ).count() == 1


def test_enqueue_is_idempotent_and_outbox_is_payload_free(
    labs_client,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import (
        LabsAnalysisJob,
        LabsAnalysisOutbox,
        LabsExperimentEnrollment,
    )

    base = datetime(2026, 8, 9, 0, 0, 0)
    with db_session.SessionLocal() as db:
        enrolled = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
            idempotency_key="shared-idempotency-1",
            now=base,
        )
        enrolled.job.status = "succeeded"
        enrolled.job.completed_at = base + timedelta(minutes=1)
        enrolled.enrollment.status = "unavailable"
        enrolled.enrollment.completed_at = enrolled.job.completed_at
        db.commit()
        first = labs_environment.queue_recompute(
            db,
            user_id,
            idempotency_key="shared-idempotency-1",
            now=base + timedelta(hours=7),
        )
        replay = labs_environment.queue_recompute(
            db,
            user_id,
            idempotency_key="shared-idempotency-1",
            now=base + timedelta(hours=8),
        )
        first_id = first.job.id
        replay_id = replay.job.id
        first_correlation_id = first.job.correlation_id

    with db_session.SessionLocal() as db:
        jobs = db.query(LabsAnalysisJob).filter(
            LabsAnalysisJob.user_id == user_id,
        ).all()
        outboxes = db.query(LabsAnalysisOutbox).all()
        row = db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        assert len(jobs) == 2
        assert len(outboxes) == 2
        assert first_id == replay_id
        assert replay.idempotent is True
        assert row.correlation_id == first_correlation_id
        assert not hasattr(outboxes[-1], "payload")


def test_repeat_enrollment_does_not_enqueue_another_job(
    labs_client,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsAnalysisJob

    base = datetime(2026, 8, 9, 0, 0, 0)
    with db_session.SessionLocal() as db:
        enrolled = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
            idempotency_key="initial-enrollment",
            now=base,
        )
        enrolled.job.status = "succeeded"
        enrolled.job.completed_at = base + timedelta(minutes=1)
        enrolled.enrollment.status = "unavailable"
        enrolled.enrollment.completed_at = enrolled.job.completed_at
        db.commit()

        replay = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
            idempotency_key="different-enrollment-key",
            now=base + timedelta(minutes=2),
        )

        assert replay.idempotent is True
        assert replay.job is None
        assert db.query(LabsAnalysisJob).filter(
            LabsAnalysisJob.user_id == user_id,
        ).count() == 1


def test_stale_stored_consent_requires_reconsent_and_cancels_old_job(
    labs_client,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsAnalysisJob, LabsAnalysisOutbox

    with db_session.SessionLocal() as db:
        enrolled = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
            idempotency_key="old-consent-job",
        )
        old_job_id = enrolled.job.id
        enrolled.enrollment.consent_version = "retired-consent-version"
        db.commit()

        stale_state = labs_environment.public_state(db, user_id)
        assert stale_state["enrolled"] is False
        assert stale_state["status"] == "not_enrolled"
        db.rollback()
        assert labs_environment.queue_recompute(db, user_id) is None

        renewed = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
            idempotency_key="renewed-consent-job",
        )

        old_job = db.get(LabsAnalysisJob, old_job_id)
        old_outbox = db.query(LabsAnalysisOutbox).filter(
            LabsAnalysisOutbox.job_id == old_job_id,
        ).one()
        assert renewed.created is True
        assert renewed.job.id != old_job_id
        assert old_job.status == "cancelled"
        assert old_outbox.status == "cancelled"
        assert renewed.enrollment.consent_version == (
            labs_environment.CONSENT_VERSION
        )
        assert db.query(LabsAnalysisJob).filter(
            LabsAnalysisJob.user_id == user_id,
        ).count() == 2


def test_manual_recompute_enforces_rolling_daily_limit(
    labs_client,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment

    base = datetime(2026, 8, 9, 0, 0, 0)
    with db_session.SessionLocal() as db:
        enrolled = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
            now=base - timedelta(hours=1),
        )
        enrolled.job.status = "succeeded"
        enrolled.enrollment.status = "unavailable"
        db.commit()
        for index, hour in enumerate((0, 6, 12), start=1):
            decision = labs_environment.queue_recompute(
                db,
                user_id,
                idempotency_key=f"manual-daily-{index}",
                now=base + timedelta(hours=hour),
            )
            decision.job.status = "succeeded"
            decision.job.completed_at = base + timedelta(
                hours=hour,
                minutes=1,
            )
            decision.enrollment.status = "unavailable"
            decision.enrollment.completed_at = decision.job.completed_at
            db.commit()

        with pytest.raises(
            labs_environment.RecomputeLimitError,
            match="daily_limit",
        ) as exc_info:
            labs_environment.queue_recompute(
                db,
                user_id,
                idempotency_key="manual-daily-4",
                now=base + timedelta(hours=17),
            )

        assert exc_info.value.available_at == base + timedelta(hours=24)
        policy = labs_environment.public_state(
            db,
            user_id,
            now=base + timedelta(hours=17),
        )["execution"]["recompute"]
        assert policy["allowed"] is False
        assert policy["reason"] == "daily_limit"
        assert policy["remaining_requests"] == 0


def test_withdrawal_fails_closed_when_tombstone_storage_is_unavailable(
    labs_client,
    monkeypatch,
) -> None:
    client, db_session, user_id = labs_client
    from api import labs_tombstone_storage
    from db.models import LabsExperimentEnrollment

    client.post(
        "/api/labs/environment-response",
        json={
            "adult_attested": True,
            "consent_version": "environment-response-consent-v1",
        },
    )
    monkeypatch.setattr(
        labs_tombstone_storage,
        "store",
        lambda *_args: (_ for _ in ()).throw(
            labs_tombstone_storage.TombstoneStorageError("unavailable")
        ),
    )

    response = client.delete("/api/labs/environment-response")

    assert response.status_code == 503
    assert response.json()["detail"] == "LABS_WITHDRAWAL_STORAGE_UNAVAILABLE"
    with db_session.SessionLocal() as db:
        assert db.get(
            LabsExperimentEnrollment,
            (user_id, "environment-response-v1"),
        ) is not None


def test_worker_persists_only_aggregate_result(labs_client, monkeypatch) -> None:
    client, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsExperimentResult

    with db_session.SessionLocal() as db:
        decision = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        job_id = decision.job.id

    monkeypatch.setattr(
        labs_environment,
        "_build_private_dataset_bundle",
        lambda *_args: {"private": "never persisted"},
    )
    monkeypatch.setattr(
        labs_environment,
        "build_environment_response_result",
        lambda *_args: _aggregate_result(),
    )
    outcome = labs_environment.process_environment_response_job(job_id)

    with db_session.SessionLocal() as db:
        result = db.get(
            LabsExperimentResult,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        assert result is not None
        assert result.result_state == "historical_association_only"
        serialized = json.dumps({
            "counts": result.eligibility_counts,
            "curve": result.aggregate_curve_points,
            "uncertainty": result.aggregate_uncertainty,
            "gates": result.gate_statuses,
        }, sort_keys=True)
        for forbidden in ("activity_id", "date", "route", "lat", "lng", "private"):
            assert f'"{forbidden}"' not in serialized
    assert outcome.outcome == "completed"
    response = client.get("/api/labs/environment-response")
    assert response.status_code == 200
    assert response.json()["result"]["result_state"] == (
        "historical_association_only"
    )
    assert response.json()["result"]["eligibility_counts"]["workload_support"] == {
        "policy": "training_median_centered_v1",
        "training_median_pct_cp": 74.8,
        "personal_display_pct_cp": [65.0, 84.8],
        "half_width_percentage_points": 10.0,
        "model_eligible_pct_cp": [65.0, 95.0],
        "display_filter_applied_to_model_rows": False,
    }


def test_worker_cancels_queued_job_from_an_old_model(
    labs_client,
    monkeypatch,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsAnalysisJob, LabsExperimentEnrollment

    with db_session.SessionLocal() as db:
        decision = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        job_id = decision.job.id
        decision.job.model_version = "retired-labs-model"
        decision.enrollment.model_version = "retired-labs-model"
        db.commit()

    monkeypatch.setattr(
        labs_environment,
        "_build_private_dataset_bundle",
        lambda *_args: pytest.fail("stale model job must not execute"),
    )

    outcome = labs_environment.process_environment_response_job(job_id)

    with db_session.SessionLocal() as db:
        job = db.get(LabsAnalysisJob, job_id)
        row = db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        assert job.status == "cancelled"
        assert job.failure_code == "model_version_mismatch"
        assert row.status == "stale"
        assert row.availability_reason["code"] == "stale_model_version"
    assert outcome.outcome == "cancelled"


def test_worker_withholds_aggregate_from_an_unexpected_model(
    labs_client,
    monkeypatch,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsExperimentEnrollment, LabsExperimentResult

    with db_session.SessionLocal() as db:
        decision = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        job_id = decision.job.id

    unexpected = _aggregate_result()
    unexpected["model_version"] = "unexpected-model"
    monkeypatch.setattr(
        labs_environment,
        "_build_private_dataset_bundle",
        lambda *_args: {},
    )
    monkeypatch.setattr(
        labs_environment,
        "build_environment_response_result",
        lambda *_args: unexpected,
    )

    outcome = labs_environment.process_environment_response_job(job_id)

    with db_session.SessionLocal() as db:
        row = db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        assert row.status == "stale"
        assert row.availability_reason["code"] == "stale_model_version"
        assert db.get(
            LabsExperimentResult,
            (user_id, labs_environment.EXPERIMENT_ID),
        ) is None
    assert outcome.outcome == "completed"


def test_public_state_hides_aggregate_from_an_old_model(
    labs_client,
    monkeypatch,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsExperimentResult

    with db_session.SessionLocal() as db:
        decision = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        job_id = decision.job.id
    monkeypatch.setattr(
        labs_environment,
        "_build_private_dataset_bundle",
        lambda *_args: {},
    )
    monkeypatch.setattr(
        labs_environment,
        "build_environment_response_result",
        lambda *_args: _aggregate_result(),
    )
    assert labs_environment.process_environment_response_job(
        job_id
    ).outcome == "completed"

    with db_session.SessionLocal() as db:
        result = db.get(
            LabsExperimentResult,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        result.model_version = "retired-labs-model"
        db.commit()
        state = labs_environment.public_state(db, user_id)

    assert state["status"] == "stale"
    assert state["availability_reason"]["code"] == "stale_model_version"
    assert state["result"] is None


def test_research_worker_context_does_not_query_training_plans(
    labs_client,
) -> None:
    _, db_session, user_id = labs_client
    from sqlalchemy import event
    from api.packs import RequestContext

    statements: list[str] = []
    with db_session.SessionLocal() as db:
        def capture_statement(
            _conn,
            _cursor,
            statement,
            _parameters,
            _context,
            _executemany,
        ) -> None:
            statements.append(statement)

        event.listen(
            db.get_bind(),
            "before_cursor_execute",
            capture_statement,
        )
        try:
            RequestContext(
                user_id=user_id,
                db=db,
                include_plan=False,
            )._data
        finally:
            event.remove(
                db.get_bind(),
                "before_cursor_execute",
                capture_statement,
            )

    assert not any(
        "training_plans" in statement.lower()
        for statement in statements
    )


def test_running_job_rechecks_withdrawal_before_persist(
    labs_client,
    monkeypatch,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsExperimentResult

    with db_session.SessionLocal() as db:
        decision = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        job_id = decision.job.id

    monkeypatch.setattr(
        labs_environment,
        "_build_private_dataset_bundle",
        lambda *_args: {},
    )

    def withdraw_during_analysis(_dataset):
        with db_session.SessionLocal() as other:
            labs_environment.withdraw(other, user_id)
        return _aggregate_result()

    monkeypatch.setattr(
        labs_environment,
        "build_environment_response_result",
        withdraw_during_analysis,
    )
    outcome = labs_environment.process_environment_response_job(job_id)

    with db_session.SessionLocal() as db:
        assert db.get(
            LabsExperimentResult,
            (user_id, labs_environment.EXPERIMENT_ID),
        ) is None
    assert outcome.outcome == "cancelled"


def test_stale_source_revision_is_explicit_unavailable_state(
    labs_client,
    monkeypatch,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsExperimentEnrollment

    with db_session.SessionLocal() as db:
        decision = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        job_id = decision.job.id
    monkeypatch.setattr(
        labs_environment,
        "_build_private_dataset_bundle",
        lambda *_args: (_ for _ in ()).throw(
            labs_environment.StaleSourceRevision()
        ),
    )

    outcome = labs_environment.process_environment_response_job(job_id)

    with db_session.SessionLocal() as db:
        row = db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        assert row.status == "stale"
        assert row.availability_reason["code"] == "stale_source_revision"
        assert row.availability_reason["correlation_id"] == row.correlation_id
    assert outcome.outcome == "completed"


def test_source_revision_change_during_analysis_withholds_result(
    labs_client,
    monkeypatch,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsExperimentEnrollment, LabsExperimentResult

    with db_session.SessionLocal() as db:
        decision = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        job_id = decision.job.id
    monkeypatch.setattr(
        labs_environment,
        "_build_private_dataset_bundle",
        lambda *_args: {},
    )
    monkeypatch.setattr(
        labs_environment,
        "build_environment_response_result",
        lambda *_args: _aggregate_result(),
    )
    monkeypatch.setattr(
        labs_environment,
        "source_revision",
        lambda *_args: "rev1:changed",
    )

    outcome = labs_environment.process_environment_response_job(job_id)

    with db_session.SessionLocal() as db:
        row = db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        assert row.status == "stale"
        assert row.availability_reason["code"] == "stale_source_revision"
        assert db.get(
            LabsExperimentResult,
            (user_id, labs_environment.EXPERIMENT_ID),
        ) is None
    assert outcome.outcome == "completed"


def test_transient_worker_failure_retries_then_dead_letters(
    labs_client,
    monkeypatch,
    caplog,
) -> None:
    _, db_session, user_id = labs_client
    from sqlalchemy.exc import OperationalError
    from api import labs_environment
    from db.models import LabsAnalysisJob, LabsExperimentEnrollment

    with db_session.SessionLocal() as db:
        decision = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        job_id = decision.job.id

    monkeypatch.setattr(
        labs_environment,
        "_build_private_dataset_bundle",
        lambda *_args: (_ for _ in ()).throw(
            OperationalError(
                "SELECT * FROM activity_samples WHERE lat = :lat",
                {"lat": "sensitive-athlete-coordinate"},
                Exception("database unavailable"),
            )
        ),
    )

    first = labs_environment.process_environment_response_job(job_id)
    second = labs_environment.process_environment_response_job(job_id)
    third = labs_environment.process_environment_response_job(job_id)

    assert first.outcome == "retry"
    assert second.outcome == "retry"
    assert third.outcome == "dead_lettered"
    with db_session.SessionLocal() as db:
        job = db.get(LabsAnalysisJob, job_id)
        row = db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        assert job.attempt_count == labs_environment.MAX_JOB_ATTEMPTS
        assert job.retryable_failure is True
        assert row.status == "failed"
        assert row.availability_reason["code"] == "analysis_retry_exhausted"
    assert "sensitive-athlete-coordinate" not in caplog.text


def test_processing_claim_at_attempt_cap_does_not_run_again(
    labs_client,
    monkeypatch,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsAnalysisJob, LabsExperimentEnrollment

    with db_session.SessionLocal() as db:
        decision = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        job_id = decision.job.id
        decision.job.status = "processing"
        decision.job.attempt_count = labs_environment.MAX_JOB_ATTEMPTS
        decision.enrollment.status = "processing"
        db.commit()

    monkeypatch.setattr(
        labs_environment,
        "_build_private_dataset_bundle",
        lambda *_args: pytest.fail("attempt cap must stop execution"),
    )

    outcome = labs_environment.process_environment_response_job(
        job_id,
        reclaim_processing=True,
    )

    with db_session.SessionLocal() as db:
        job = db.get(LabsAnalysisJob, job_id)
        row = db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        assert job.status == "dead_lettered"
        assert job.attempt_count == labs_environment.MAX_JOB_ATTEMPTS
        assert job.failure_code == "worker_attempt_limit_exhausted"
        assert row.status == "failed"
        assert row.availability_reason["code"] == "analysis_retry_exhausted"
    assert outcome.outcome == "dead_lettered"


def test_worker_message_settlement_uses_job_outcome(monkeypatch) -> None:
    from api import labs_worker
    from api.labs_environment import JobExecutionResult

    class Message:
        body = [b"72bc9e44-5baa-4b45-9a7d-57a7427d9ef4"]

    class Receiver:
        action = ""

        def complete_message(self, _message) -> None:
            self.action = "completed"

        def abandon_message(self, _message) -> None:
            self.action = "abandoned"

        def dead_letter_message(self, _message, **_kwargs) -> None:
            self.action = "dead_lettered"

    receiver = Receiver()
    monkeypatch.setattr(
        labs_worker,
        "process_environment_response_job",
        lambda *_args, **_kwargs: JobExecutionResult(
            "retry",
            attempt_count=1,
            failure_code="OperationalError",
        ),
    )

    settlement = labs_worker.settle_message(receiver, Message())

    assert settlement == "abandoned"
    assert receiver.action == "abandoned"


def test_worker_abandons_message_when_job_claim_raises(
    monkeypatch,
    caplog,
) -> None:
    from sqlalchemy.exc import OperationalError
    from api import labs_worker

    class Message:
        body = [b"72bc9e44-5baa-4b45-9a7d-57a7427d9ef4"]

    class Receiver:
        action = ""

        def abandon_message(self, _message) -> None:
            self.action = "abandoned"

    def fail_claim(*_args, **_kwargs):
        raise OperationalError(
            "SELECT * FROM activity_samples WHERE lat = :lat",
            {"lat": "sensitive-athlete-coordinate"},
            Exception("database unavailable"),
        )

    receiver = Receiver()
    monkeypatch.setattr(
        labs_worker,
        "process_environment_response_job",
        fail_claim,
    )

    settlement = labs_worker.settle_message(receiver, Message())

    assert settlement == "abandoned"
    assert receiver.action == "abandoned"
    assert "sensitive-athlete-coordinate" not in caplog.text


def test_worker_locks_delivery_before_database_initialization(
    monkeypatch,
    caplog,
) -> None:
    from api import labs_worker

    events: list[str] = []

    class Message:
        body = [b"72bc9e44-5baa-4b45-9a7d-57a7427d9ef4"]

    class Receiver:
        action = ""

        def __enter__(self) -> "Receiver":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def receive_messages(self, **_kwargs: object) -> list[Message]:
            events.append("receive")
            return [Message()]

        def abandon_message(self, _message: Message) -> None:
            self.action = "abandoned"

    receiver = Receiver()

    class Client:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> "Client":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def get_queue_receiver(
            self,
            _queue_name: str,
            **_kwargs: object,
        ) -> Receiver:
            return receiver

    class AutoLockRenewer:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def register(
            self,
            _receiver: Receiver,
            _message: Message,
        ) -> None:
            events.append("lock")
            return None

        def close(self) -> None:
            return None

    service_bus_module = types.ModuleType("azure.servicebus")
    service_bus_module.AutoLockRenewer = AutoLockRenewer
    service_bus_module.ServiceBusClient = Client
    monkeypatch.setitem(sys.modules, "azure.servicebus", service_bus_module)
    monkeypatch.setattr(labs_worker, "_azure_credential", object)

    def fail_database_initialization() -> None:
        events.append("database")
        raise RuntimeError("sensitive-database-detail")

    monkeypatch.setattr(
        labs_worker,
        "_initialize_database",
        fail_database_initialization,
    )
    monkeypatch.setenv("PRAXYS_LABS_EXECUTION_MODE", "service_bus")
    monkeypatch.setenv(
        "PRAXYS_LABS_SERVICE_BUS_FQDN",
        "sb-praxys-labs.servicebus.windows.net",
    )
    monkeypatch.setenv(
        "PRAXYS_LABS_SERVICE_BUS_QUEUE",
        "labs-environment-response",
    )

    assert labs_worker.run_once() is True
    assert receiver.action == "abandoned"
    assert events == ["receive", "lock", "database"]
    assert "sensitive-database-detail" not in caplog.text


def test_worker_startup_check_initializes_database_without_receiving(
    monkeypatch,
) -> None:
    from api import labs_worker

    events: list[str] = []
    monkeypatch.setenv("PRAXYS_SKIP_MIGRATIONS", "false")
    monkeypatch.setenv("PRAXYS_HIDE_SQL_PARAMETERS", "false")
    monkeypatch.setattr(
        labs_worker,
        "_configure_telemetry",
        lambda: events.append("telemetry"),
    )
    monkeypatch.setattr(
        labs_worker,
        "_initialize_database",
        lambda: events.append("database"),
    )
    monkeypatch.setattr(
        labs_worker,
        "_verify_database_connection",
        lambda: events.append("verify"),
    )
    monkeypatch.setattr(
        labs_worker,
        "run_once",
        lambda: pytest.fail("startup check must not receive a queue message"),
    )

    assert labs_worker.main(["--startup-check"]) == 0
    assert events == ["telemetry", "database", "verify"]


def test_worker_database_verification_checks_exact_grants(
    monkeypatch,
) -> None:
    from api import labs_worker, labs_worker_permissions
    from db import session as db_session

    checked: list[object] = []

    class Database:
        def __enter__(self) -> "Database":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    database = Database()
    monkeypatch.setattr(
        db_session,
        "SessionLocal",
        lambda: database,
    )
    monkeypatch.setattr(
        labs_worker_permissions,
        "verify_labs_worker_grants",
        lambda db: checked.append(db),
    )

    labs_worker._verify_database_connection()

    assert checked == [database]


def test_backend_deploy_supports_manual_cutover() -> None:
    import yaml

    workflow_path = (
        Path(__file__).parents[1]
        / ".github"
        / "workflows"
        / "deploy-backend.yml"
    )
    workflow = yaml.load(
        workflow_path.read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )

    assert "workflow_dispatch" in workflow["on"]
    runbook = (
        Path(__file__).parents[1]
        / "docs"
        / "ops"
        / "labs-analysis-worker.md"
    ).read_text(encoding="utf-8")
    assert "scripts/start_labs_worker_check.py" in runbook


def test_startup_check_override_preserves_live_job_configuration() -> None:
    from scripts.start_labs_worker_check import (
        build_startup_check_template,
    )

    template = {
        "containers": [{
            "name": "labs-worker",
            "image": "ghcr.io/praxys-run/praxys-labs-worker:sha",
            "env": [
                {
                    "name": "PRAXYS_DATABASE_URL",
                    "secretRef": "database-url",
                },
            ],
            "resources": {"cpu": 1, "memory": "2Gi"},
        }],
        "volumes": [{"name": "unchanged"}],
    }

    startup_template = build_startup_check_template(
        template,
        container_name="labs-worker",
    )

    assert startup_template["containers"][0]["command"] == ["python"]
    assert startup_template["containers"][0]["args"] == [
        "-m",
        "api.labs_worker",
        "--startup-check",
    ]
    assert startup_template["containers"][0]["env"] == (
        template["containers"][0]["env"]
    )
    assert startup_template["containers"][0]["resources"] == (
        template["containers"][0]["resources"]
    )
    assert startup_template["volumes"] == template["volumes"]
    assert "command" not in template["containers"][0]


def test_worker_sqlalchemy_engine_hides_parameters(monkeypatch) -> None:
    from db.session import _make_sync_engine

    monkeypatch.setenv("PRAXYS_HIDE_SQL_PARAMETERS", "true")
    engine = _make_sync_engine("sqlite://")
    try:
        assert engine.hide_parameters is True
    finally:
        engine.dispose()


def test_service_bus_credential_uses_effective_runtime_identity(
    monkeypatch,
) -> None:
    from api import labs_dispatch

    created: list[str | None] = []

    class Credential:
        def __init__(self, client_id: str | None = None) -> None:
            created.append(client_id)

    identity_module = types.ModuleType("azure.identity")
    identity_module.ManagedIdentityCredential = Credential
    identity_module.DefaultAzureCredential = Credential
    monkeypatch.setitem(sys.modules, "azure.identity", identity_module)
    monkeypatch.setenv("WEBSITE_SITE_NAME", "trainsight-app")
    monkeypatch.setenv("AZURE_CLIENT_ID", "general-backend-uami")
    monkeypatch.delenv(
        "PRAXYS_LABS_SERVICE_BUS_CLIENT_ID",
        raising=False,
    )

    labs_dispatch._azure_credential()
    monkeypatch.setenv(
        "PRAXYS_LABS_SERVICE_BUS_CLIENT_ID",
        "labs-sender-uami",
    )
    labs_dispatch._azure_credential()

    assert created == [None, "labs-sender-uami"]


def test_worker_receiver_disables_prefetch(monkeypatch) -> None:
    from api import labs_worker

    receiver_options: dict[str, object] = {}

    class Receiver:
        def __enter__(self) -> "Receiver":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def receive_messages(self, **_kwargs: object) -> list[object]:
            return []

    class Client:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def __enter__(self) -> "Client":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def get_queue_receiver(
            self,
            queue_name: str,
            **kwargs: object,
        ) -> Receiver:
            receiver_options["queue_name"] = queue_name
            receiver_options.update(kwargs)
            return Receiver()

    service_bus_module = types.ModuleType("azure.servicebus")
    service_bus_module.AutoLockRenewer = object
    service_bus_module.ServiceBusClient = Client
    monkeypatch.setitem(sys.modules, "azure.servicebus", service_bus_module)
    monkeypatch.setattr(labs_worker, "_azure_credential", object)
    monkeypatch.setenv("PRAXYS_LABS_EXECUTION_MODE", "service_bus")
    monkeypatch.setenv(
        "PRAXYS_LABS_SERVICE_BUS_FQDN",
        "sb-praxys-labs.servicebus.windows.net",
    )
    monkeypatch.setenv(
        "PRAXYS_LABS_SERVICE_BUS_QUEUE",
        "labs-environment-response",
    )

    assert labs_worker.run_once() is False
    assert receiver_options["queue_name"] == "labs-environment-response"
    assert receiver_options["prefetch_count"] == 0
    assert receiver_options["max_wait_time"] == 20


def test_claim_stage_database_error_is_not_converted_to_ignored(
    labs_client,
    monkeypatch,
) -> None:
    from sqlalchemy.exc import OperationalError
    from api import labs_environment

    def fail_claim(*_args, **_kwargs):
        raise OperationalError(
            "SELECT 1",
            {},
            Exception("database unavailable"),
        )

    monkeypatch.setattr(labs_environment, "_claim_job", fail_claim)

    with pytest.raises(OperationalError):
        labs_environment.process_environment_response_job(
            "72bc9e44-5baa-4b45-9a7d-57a7427d9ef4",
            reclaim_processing=True,
        )


@pytest.mark.parametrize("terminal_status", ["failed", "dead_lettered"])
def test_terminal_job_redelivery_preserves_dead_letter_settlement(
    labs_client,
    terminal_status,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsAnalysisJob

    with db_session.SessionLocal() as db:
        decision = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        job_id = decision.job.id
        job = db.get(LabsAnalysisJob, job_id)
        job.status = terminal_status
        job.failure_code = "OperationalError"
        job.attempt_count = labs_environment.MAX_JOB_ATTEMPTS
        db.commit()

    outcome = labs_environment.process_environment_response_job(
        job_id,
        reclaim_processing=True,
    )

    assert outcome.outcome == terminal_status
    assert outcome.failure_code == "OperationalError"


@pytest.mark.parametrize("outbox_status", ["pending", "dispatching"])
def test_recovery_preserves_dispatch_backoff_and_live_leases(
    labs_client,
    outbox_status,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsAnalysisOutbox

    available_at = datetime.utcnow() + timedelta(minutes=4)
    lease_expires_at = datetime.utcnow() + timedelta(minutes=2)
    with db_session.SessionLocal() as db:
        decision = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        outbox = db.query(LabsAnalysisOutbox).filter(
            LabsAnalysisOutbox.job_id == decision.job.id,
        ).one()
        outbox.status = outbox_status
        outbox.available_at = available_at
        outbox.lease_expires_at = (
            lease_expires_at if outbox_status == "dispatching" else None
        )
        outbox.last_error_code = "ServiceBusError"
        db.commit()

        assert labs_environment.recover_interrupted_jobs(db) == 0

        db.refresh(outbox)
        assert outbox.status == outbox_status
        assert outbox.available_at == available_at
        assert outbox.lease_expires_at == (
            lease_expires_at if outbox_status == "dispatching" else None
        )
        assert outbox.last_error_code == "ServiceBusError"


@pytest.mark.parametrize("job_status", ["dispatched", "retrying"])
def test_recovery_requeues_a_dispatched_job_that_never_started(
    labs_client,
    job_status,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import (
        LabsAnalysisJob,
        LabsAnalysisOutbox,
        LabsExperimentEnrollment,
    )

    with db_session.SessionLocal() as db:
        decision = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        job_id = decision.job.id
        stale_dispatch = (
            datetime.utcnow()
            - labs_environment.JOB_LEASE_DURATION
            - timedelta(minutes=1)
        )
        decision.job.status = job_status
        decision.job.dispatched_at = stale_dispatch
        outbox = db.query(LabsAnalysisOutbox).filter(
            LabsAnalysisOutbox.job_id == job_id,
        ).one()
        outbox.status = "dispatched"
        outbox.dispatched_at = stale_dispatch
        db.commit()

        assert labs_environment.recover_interrupted_jobs(db) == 1

        job = db.get(LabsAnalysisJob, job_id)
        enrollment = db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        outbox = db.query(LabsAnalysisOutbox).filter(
            LabsAnalysisOutbox.job_id == job_id,
        ).one()
        assert job.status == "retrying"
        assert job.failure_code == "worker_start_timeout"
        assert job.retryable_failure is True
        assert enrollment.status == "queued"
        assert outbox.status == "pending"
        assert outbox.available_at > stale_dispatch


def test_dispatch_recovery_only_requeues_the_global_head_of_line(
    labs_client,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsAnalysisJob, LabsAnalysisOutbox, User

    second_user_id = str(uuid4())
    base = datetime.utcnow() - labs_environment.JOB_LEASE_DURATION - timedelta(
        minutes=1,
    )
    with db_session.SessionLocal() as db:
        db.add(User(
            id=second_user_id,
            email="labs-second-user@example.test",
            hashed_password="not-used",
        ))
        db.commit()
        first = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
            now=base,
        )
        second = labs_environment.enroll(
            db,
            second_user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
            now=base + timedelta(seconds=1),
        )
        for decision in (first, second):
            decision.job.status = "dispatched"
            decision.job.dispatched_at = base
            outbox = db.query(LabsAnalysisOutbox).filter(
                LabsAnalysisOutbox.job_id == decision.job.id,
            ).one()
            outbox.status = "dispatched"
            outbox.dispatched_at = base
        db.commit()

        assert labs_environment.recover_interrupted_jobs(db) == 1

        first_job = db.get(LabsAnalysisJob, first.job.id)
        second_job = db.get(LabsAnalysisJob, second.job.id)
        first_outbox = db.query(LabsAnalysisOutbox).filter(
            LabsAnalysisOutbox.job_id == first.job.id,
        ).one()
        second_outbox = db.query(LabsAnalysisOutbox).filter(
            LabsAnalysisOutbox.job_id == second.job.id,
        ).one()
        assert first_job.status == "retrying"
        assert first_outbox.status == "pending"
        assert second_job.status == "dispatched"
        assert second_outbox.status == "dispatched"


def test_service_bus_mode_requires_complete_queue_configuration(
    monkeypatch,
) -> None:
    from api import labs_dispatch

    monkeypatch.setenv("PRAXYS_LABS_EXECUTION_MODE", "service_bus")
    monkeypatch.delenv("PRAXYS_LABS_SERVICE_BUS_FQDN", raising=False)
    monkeypatch.delenv("PRAXYS_LABS_SERVICE_BUS_QUEUE", raising=False)

    with pytest.raises(RuntimeError, match="configuration is incomplete"):
        labs_dispatch.validate_configuration()

    monkeypatch.setenv(
        "PRAXYS_LABS_SERVICE_BUS_FQDN",
        "sb-praxys-labs.servicebus.windows.net",
    )
    monkeypatch.setenv(
        "PRAXYS_LABS_SERVICE_BUS_QUEUE",
        "labs-environment-response",
    )
    labs_dispatch.validate_configuration()

    monkeypatch.setenv(
        "PRAXYS_LABS_SERVICE_BUS_FQDN",
        "sb-praxys-labs.servicebus.windows.net:443",
    )
    with pytest.raises(RuntimeError, match="must be a hostname"):
        labs_dispatch.validate_configuration()


def test_worker_grant_script_is_directly_invocable() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/provision_labs_worker_db.py",
            "--help",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--identity-name" in result.stdout


def test_service_bus_dispatch_failure_stays_durable_without_inline_fallback(
    labs_client,
    monkeypatch,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_dispatch, labs_environment
    from db.models import (
        LabsAnalysisJob,
        LabsAnalysisOutbox,
        LabsExperimentEnrollment,
    )

    with db_session.SessionLocal() as db:
        decision = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        job_id = decision.job.id

    monkeypatch.setenv("PRAXYS_LABS_EXECUTION_MODE", "service_bus")
    monkeypatch.setenv(
        "PRAXYS_LABS_SERVICE_BUS_FQDN",
        "sb-praxys-labs.servicebus.windows.net",
    )
    monkeypatch.setenv(
        "PRAXYS_LABS_SERVICE_BUS_QUEUE",
        "labs-environment-response",
    )
    monkeypatch.setattr(
        labs_dispatch,
        "_send_service_bus",
        lambda _job_id: (_ for _ in ()).throw(
            ConnectionError("service bus unavailable")
        ),
    )
    monkeypatch.setattr(
        labs_dispatch,
        "process_environment_response_job",
        lambda *_args, **_kwargs: pytest.fail(
            "configured Service Bus mode must never run analysis inline"
        ),
    )

    assert labs_dispatch.dispatch_job(job_id) is False

    with db_session.SessionLocal() as db:
        job = db.get(LabsAnalysisJob, job_id)
        outbox = db.query(LabsAnalysisOutbox).filter(
            LabsAnalysisOutbox.job_id == job_id,
        ).one()
        enrollment = db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        assert job.status == "queued"
        assert outbox.status == "pending"
        assert outbox.attempt_count == 1
        assert outbox.last_error_code == "ConnectionError"
        assert outbox.available_at > outbox.updated_at
        assert enrollment.status == "queued"


def test_inline_claim_failure_requeues_the_durable_outbox(
    labs_client,
    monkeypatch,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_dispatch, labs_environment
    from db.models import LabsAnalysisJob, LabsAnalysisOutbox

    with db_session.SessionLocal() as db:
        decision = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        job_id = decision.job.id

    monkeypatch.setenv("PRAXYS_LABS_EXECUTION_MODE", "inline")
    monkeypatch.setattr(
        labs_dispatch,
        "process_environment_response_job",
        lambda _job_id: (_ for _ in ()).throw(
            RuntimeError("claim unavailable")
        ),
    )

    assert labs_dispatch.dispatch_job(job_id) is False

    with db_session.SessionLocal() as db:
        job = db.get(LabsAnalysisJob, job_id)
        outbox = db.query(LabsAnalysisOutbox).filter(
            LabsAnalysisOutbox.job_id == job_id,
        ).one()
        assert job.status == "dispatched"
        assert outbox.status == "pending"
        assert outbox.last_error_code == "RuntimeError"
        assert outbox.available_at > outbox.updated_at


def test_service_bus_dispatch_marks_job_only_after_publish(
    labs_client,
    monkeypatch,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_dispatch, labs_environment
    from db.models import LabsAnalysisJob, LabsAnalysisOutbox

    with db_session.SessionLocal() as db:
        decision = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        job_id = decision.job.id

    published: list[str] = []
    monkeypatch.setenv("PRAXYS_LABS_EXECUTION_MODE", "service_bus")
    monkeypatch.setenv(
        "PRAXYS_LABS_SERVICE_BUS_FQDN",
        "sb-praxys-labs.servicebus.windows.net",
    )
    monkeypatch.setenv(
        "PRAXYS_LABS_SERVICE_BUS_QUEUE",
        "labs-environment-response",
    )
    monkeypatch.setattr(
        labs_dispatch,
        "_send_service_bus",
        published.append,
    )
    events: list[tuple[str, str]] = []
    monkeypatch.setattr(
        labs_dispatch,
        "_record_job_event",
        lambda job, **details: events.append(
            (job.trigger, details["outcome"])
        ),
    )

    assert labs_dispatch.dispatch_job(job_id) is True
    assert published == [job_id]
    assert events == [("enrollment", "service_bus")]

    with db_session.SessionLocal() as db:
        job = db.get(LabsAnalysisJob, job_id)
        outbox = db.query(LabsAnalysisOutbox).filter(
            LabsAnalysisOutbox.job_id == job_id,
        ).one()
        assert job.status == "dispatched"
        assert job.dispatched_at is not None
        assert outbox.status == "dispatched"
        assert outbox.dispatched_at is not None


def test_recompute_is_single_flight_while_job_is_active(labs_client) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsAnalysisJob

    with db_session.SessionLocal() as db:
        first = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        repeated = labs_environment.queue_recompute(db, user_id)
        first_job_id = first.job.id
        repeated_job_id = repeated.job.id

    with db_session.SessionLocal() as db:
        jobs = db.query(LabsAnalysisJob).filter(
            LabsAnalysisJob.user_id == user_id,
        ).all()
        assert len(jobs) == 1
        assert repeated.created is False
        assert repeated.idempotent is True
        assert repeated_job_id == first_job_id


def test_get_does_not_dispatch_or_recover_abandoned_job(labs_client) -> None:
    client, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import (
        LabsAnalysisJob,
        LabsAnalysisOutbox,
        LabsExperimentEnrollment,
    )

    with db_session.SessionLocal() as db:
        decision = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        row = decision.enrollment
        job = decision.job
        row.status = "processing"
        row.started_at = datetime.utcnow() - timedelta(minutes=31)
        job.status = "processing"
        job.attempt_count = 1
        job.started_at = row.started_at
        job.lease_expires_at = datetime.utcnow() - timedelta(minutes=1)
        outbox = db.query(LabsAnalysisOutbox).filter(
            LabsAnalysisOutbox.job_id == job.id,
        ).one()
        outbox.status = "dispatched"
        db.commit()

    response = client.get("/api/labs/environment-response")

    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    with db_session.SessionLocal() as db:
        row = db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        job = db.query(LabsAnalysisJob).filter(
            LabsAnalysisJob.user_id == user_id,
        ).one()
        assert row.started_at is not None
        assert job.status == "processing"
        assert labs_environment.recover_interrupted_jobs(db) == 1
        db.refresh(row)
        db.refresh(job)
        outbox = db.query(LabsAnalysisOutbox).filter(
            LabsAnalysisOutbox.job_id == job.id,
        ).one()
        assert row.status == "queued"
        assert job.status == "retrying"
        assert job.failure_code == "worker_lease_expired"
        assert job.retryable_failure is True
        assert outbox.status == "pending"


def test_tombstone_replay_preserves_newer_reconsent(labs_client) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsDeletionTombstone, LabsExperimentEnrollment

    with db_session.SessionLocal() as db:
        decision = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        row = decision.enrollment
        tombstone = LabsDeletionTombstone(
            user_id=user_id,
            experiment_id=labs_environment.EXPERIMENT_ID,
            deleted_at=datetime.utcnow() - timedelta(minutes=1),
        )
        db.add(tombstone)
        db.commit()
        assert row.consented_at > tombstone.deleted_at
        assert labs_environment.replay_deletion_tombstones(db) == 0
        assert db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        ) is not None


def test_external_tombstone_replays_after_database_restore(labs_client) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment, labs_tombstone_storage
    from db.models import LabsDeletionTombstone, LabsExperimentEnrollment

    with db_session.SessionLocal() as db:
        decision = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        row = decision.enrollment
        deleted_at = row.consented_at + timedelta(seconds=1)
        labs_tombstone_storage.store(
            user_id,
            labs_environment.EXPERIMENT_ID,
            deleted_at,
        )
        db.query(LabsDeletionTombstone).delete()
        db.commit()

        assert labs_environment.replay_deletion_tombstones(db) == 1
        assert db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        ) is None


@pytest.mark.parametrize(
    ("exclusion", "expected"),
    [
        ("power_missing_or_invalid", "missing_continuous_sample_power"),
        ("mean_hr_missing_or_invalid", "missing_continuous_heart_rate"),
        ("temperature_missing_or_invalid", "missing_temperature"),
        ("relative_humidity_missing_or_invalid", "missing_relative_humidity"),
        (
            "critical_power_value_missing_or_invalid",
            "missing_provider_aligned_critical_power",
        ),
        (
            "critical_power_provider_mismatch",
            "critical_power_provider_mismatch",
        ),
        ("segment_sample_coverage_low", "insufficient_sample_coverage"),
    ],
)
def test_availability_reason_preserves_data_quality_category(
    exclusion,
    expected,
) -> None:
    from api.labs_environment import availability_reason

    aggregate = {
        "result_state": "insufficient_data",
        "gate_statuses": {
            "minimum_activities": "fail",
            "stryd_power_regime": "pass",
        },
        "eligibility_counts": {
            "eligible_activity_count": 0,
            "eligible_segment_count": 0,
            "exclusion_reason_counts": {exclusion: 2},
        },
    }

    reason = availability_reason(
        aggregate,
        correlation_id="correlation",
    )

    assert reason["code"] == expected


def test_availability_reason_does_not_mask_failed_release_gate() -> None:
    """Excluded rows must not override the gate that withheld an ample dataset."""
    from api.labs_environment import availability_reason

    aggregate = {
        "result_state": "insufficient_data",
        "gate_statuses": {
            "complete_export": "pass",
            "minimum_activities": "pass",
            "minimum_segments": "pass",
            "environmental_spread": "pass",
            "chronological_holdout": "pass",
            "holdout_environmental_spread": "pass",
            "curve_bin_support": "fail",
            "stryd_power_regime": "pass",
        },
        "eligibility_counts": {
            "eligible_activity_count": 177,
            "eligible_segment_count": 738,
            "exclusion_reason_counts": {"power_missing_or_invalid": 3},
        },
    }

    reason = availability_reason(
        aggregate,
        correlation_id="correlation",
    )

    assert reason["code"] == "insufficient_curve_bin_support"


def test_openapi_exposes_strict_labs_response_schema(labs_client) -> None:
    client, _, _ = labs_client

    schema = client.get("/openapi.json").json()
    response = schema["paths"]["/api/labs/environment-response"]["get"][
        "responses"
    ]["200"]["content"]["application/json"]["schema"]

    assert response["$ref"].endswith("/EnvironmentResponseState")
    state = schema["components"]["schemas"]["EnvironmentResponseState"]
    assert state["additionalProperties"] is False
    assert "status" in state["properties"]
    assert "availability_reason" in state["properties"]
    assert "result" in state["properties"]
    eligibility = schema["components"]["schemas"][
        "EnvironmentEligibilityCounts"
    ]
    workload_support = schema["components"]["schemas"][
        "EnvironmentWorkloadSupport"
    ]
    uncertainty = schema["components"]["schemas"]["EnvironmentUncertainty"]
    assert eligibility["additionalProperties"] is False
    assert "workload_support" in eligibility["properties"]
    assert workload_support["additionalProperties"] is False
    assert uncertainty["additionalProperties"] is False
