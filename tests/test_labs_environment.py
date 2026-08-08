"""Backend contract tests for the Labs environmental-response experiment."""
from __future__ import annotations

import tempfile
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def labs_client(monkeypatch):
    """Yield an authenticated client backed by an isolated SQLite database."""
    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", tmpdir.name)
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv("PRAXYS_AUTH_RATE_LIMIT_DISABLED", "true")
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
        "process_environment_response_job",
        lambda *_args: None,
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
    return {
        "model_version": "within-athlete-ridge-mean-hr-v1-labs-v1",
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
        },
        "aggregate_curve_points": [
            {
                "wet_bulb_c": 20.0,
                "modeled_hr_bpm": 150.0,
                "relative_hr_bpm": 0.0,
                "relative_lower_bpm": 0.0,
                "relative_upper_bpm": 0.0,
                "reference_wet_bulb_c": 20.0,
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

    assert adult.status_code == 422
    assert adult.json()["detail"]["code"] == "adult_eligibility_not_confirmed"
    assert adult.json()["detail"]["correlation_id"]
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "consent_version_stale"


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
        row = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        args = (
            row.user_id,
            row.experiment_id,
            row.model_version,
            row.source_revision,
        )

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
    labs_environment.process_environment_response_job(*args)

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
    response = client.get("/api/labs/environment-response")
    assert response.status_code == 200
    assert response.json()["result"]["result_state"] == (
        "historical_association_only"
    )


def test_running_job_rechecks_withdrawal_before_persist(
    labs_client,
    monkeypatch,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsExperimentResult

    with db_session.SessionLocal() as db:
        row = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        args = (
            row.user_id,
            row.experiment_id,
            row.model_version,
            row.source_revision,
        )

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
    labs_environment.process_environment_response_job(*args)

    with db_session.SessionLocal() as db:
        assert db.get(
            LabsExperimentResult,
            (user_id, labs_environment.EXPERIMENT_ID),
        ) is None


def test_stale_source_revision_is_explicit_unavailable_state(
    labs_client,
    monkeypatch,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsExperimentEnrollment

    with db_session.SessionLocal() as db:
        row = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        args = (
            row.user_id,
            row.experiment_id,
            row.model_version,
            row.source_revision,
        )
    monkeypatch.setattr(
        labs_environment,
        "_build_private_dataset_bundle",
        lambda *_args: (_ for _ in ()).throw(
            labs_environment.StaleSourceRevision()
        ),
    )

    labs_environment.process_environment_response_job(*args)

    with db_session.SessionLocal() as db:
        row = db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        assert row.status == "stale"
        assert row.availability_reason["code"] == "stale_source_revision"
        assert row.availability_reason["correlation_id"] == row.correlation_id


def test_source_revision_change_during_analysis_withholds_result(
    labs_client,
    monkeypatch,
) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsExperimentEnrollment, LabsExperimentResult

    with db_session.SessionLocal() as db:
        row = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        args = (
            row.user_id,
            row.experiment_id,
            row.model_version,
            row.source_revision,
        )
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

    labs_environment.process_environment_response_job(*args)

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


def test_obsolete_worker_cannot_overwrite_newer_queue(labs_client) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsExperimentEnrollment

    with db_session.SessionLocal() as db:
        old = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        old_correlation = old.correlation_id
        newer = labs_environment.queue_recompute(db, user_id)
        labs_environment._persist_unavailable(
            db,
            user_id,
            labs_environment.EXPERIMENT_ID,
            newer.model_version,
            newer.source_revision,
            old_correlation,
            "analysis_failed",
            "failed",
        )

    with db_session.SessionLocal() as db:
        row = db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        assert row.status == "queued"
        assert row.correlation_id != old_correlation


def test_get_recovers_only_abandoned_processing_job(labs_client) -> None:
    client, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsExperimentEnrollment

    with db_session.SessionLocal() as db:
        row = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
        row.status = "processing"
        row.started_at = datetime.utcnow() - timedelta(minutes=31)
        db.commit()

    response = client.get("/api/labs/environment-response")

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    with db_session.SessionLocal() as db:
        row = db.get(
            LabsExperimentEnrollment,
            (user_id, labs_environment.EXPERIMENT_ID),
        )
        assert row.started_at is None


def test_tombstone_replay_preserves_newer_reconsent(labs_client) -> None:
    _, db_session, user_id = labs_client
    from api import labs_environment
    from db.models import LabsDeletionTombstone, LabsExperimentEnrollment

    with db_session.SessionLocal() as db:
        row = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
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
        row = labs_environment.enroll(
            db,
            user_id,
            adult_attested=True,
            consent_version=labs_environment.CONSENT_VERSION,
        )
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
    uncertainty = schema["components"]["schemas"]["EnvironmentUncertainty"]
    assert eligibility["additionalProperties"] is False
    assert uncertainty["additionalProperties"] is False
