"""Integration coverage for owner-only activity analysis APIs."""
from __future__ import annotations

import tempfile
from datetime import date, datetime, timedelta, timezone

import jwt
import pytest


@pytest.fixture
def analysis_client(monkeypatch):
    """Yield an isolated TestClient with two users and dated analysis inputs."""
    from fastapi.testclient import TestClient

    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    monkeypatch.setenv("DATA_DIR", tmpdir.name)
    monkeypatch.setenv("PRAXYS_SYNC_SCHEDULER", "false")
    monkeypatch.setenv(
        "PRAXYS_JWT_SECRET",
        "activity-analysis-test-secret-with-adequate-length",
    )
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

    from api.main import app
    from db.models import (
        Activity,
        ActivitySample,
        ActivitySplit,
        FitnessData,
        RecoveryData,
        User,
        UserConfig,
    )
    from db.session import get_db

    owner_id = "analysis-owner"
    other_id = "analysis-other"
    target_date = date(2026, 7, 15)
    target_epoch = int(
        datetime(
            2026,
            7,
            15,
            6,
            0,
            tzinfo=timezone.utc,
        ).timestamp()
    )

    db = db_session.SessionLocal()
    db.add_all([
        User(
            id=owner_id,
            email="analysis-owner@example.com",
            hashed_password="x",
        ),
        User(
            id=other_id,
            email="analysis-other@example.com",
            hashed_password="x",
        ),
        UserConfig(
            user_id=owner_id,
            training_base="power",
            preferences={
                "activities": "stryd",
                "recovery": "oura",
                "threshold_sources": {"cp_estimate": "stryd"},
            },
        ),
        UserConfig(
            user_id=other_id,
            training_base="power",
            preferences={"activities": "garmin", "recovery": "garmin"},
        ),
        Activity(
            user_id=owner_id,
            activity_id="prior-1",
            date=target_date - timedelta(days=3),
            activity_type="running",
            duration_sec=2400,
            rss=50,
            source="stryd",
        ),
        Activity(
            user_id=owner_id,
            activity_id="prior-2",
            date=target_date - timedelta(days=1),
            activity_type="running",
            duration_sec=2400,
            rss=60,
            source="stryd",
        ),
        Activity(
            user_id=owner_id,
            activity_id="shared-activity",
            date=target_date,
            start_time="2026-07-15 14:00:00",
            activity_type="running",
            distance_km=10,
            duration_sec=600,
            temperature_c=34,
            relative_humidity_pct=70,
            environment_source="stryd_activity_weather",
            avg_power=250,
            max_power=300,
            avg_hr=145,
            max_hr=160,
            rss=999,
            source="stryd",
        ),
        Activity(
            user_id=other_id,
            activity_id="shared-activity",
            date=target_date,
            activity_type="running",
            distance_km=999,
            duration_sec=300,
            source="garmin",
        ),
        Activity(
            user_id=other_id,
            activity_id="private-other",
            date=target_date,
            activity_type="running",
            duration_sec=300,
            source="garmin",
        ),
        ActivitySplit(
            user_id=owner_id,
            activity_id="shared-activity",
            split_num=1,
            duration_sec=600,
            avg_power=250,
            power_source="stryd",
            avg_hr=145,
        ),
        FitnessData(
            user_id=owner_id,
            date=target_date - timedelta(days=1),
            metric_type="cp_estimate",
            value=300,
            source="stryd",
            power_source="stryd",
        ),
        FitnessData(
            user_id=owner_id,
            date=target_date,
            metric_type="cp_estimate",
            value=999,
            source="stryd",
            power_source="stryd",
        ),
        RecoveryData(
            user_id=owner_id,
            date=target_date,
            readiness_score=82,
            hrv_avg=58,
            resting_hr=49,
            sleep_score=88,
            total_sleep_sec=28_800,
            source="oura",
        ),
        RecoveryData(
            user_id=owner_id,
            date=target_date + timedelta(days=1),
            readiness_score=10,
            hrv_avg=20,
            resting_hr=80,
            sleep_score=20,
            total_sleep_sec=10_000,
            source="oura",
        ),
    ])
    db.add_all([
        ActivitySample(
            user_id=owner_id,
            activity_id="shared-activity",
            source="stryd",
            t_sec=target_epoch + second,
            power_watts=250,
            hr_bpm=140 + second / 60,
        )
        for second in range(601)
    ])
    db.commit()
    db.close()

    def _override_db():
        session = db_session.SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)

    def _headers(user_id: str) -> dict[str, str]:
        token = jwt.encode(
            {
                "sub": user_id,
                "aud": "fastapi-users:auth",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
            "activity-analysis-test-secret-with-adequate-length",
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}

    try:
        yield {
            "client": client,
            "owner_headers": _headers(owner_id),
            "other_headers": _headers(other_id),
            "owner_id": owner_id,
            "other_id": other_id,
            "target_date": target_date,
        }
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


def test_activity_analysis_requires_authentication(analysis_client) -> None:
    response = analysis_client["client"].get(
        "/api/analysis/activities/shared-activity"
    )
    assert response.status_code == 401


def test_activity_analysis_is_owner_scoped(analysis_client) -> None:
    client = analysis_client["client"]
    owner_headers = analysis_client["owner_headers"]

    missing = client.get(
        "/api/analysis/activities/private-other",
        headers=owner_headers,
    )
    assert missing.status_code == 404

    owned = client.get(
        "/api/analysis/activities/shared-activity",
        headers=owner_headers,
    )
    assert owned.status_code == 200
    assert owned.json()["activity"]["distance_km"] == 10.0

    dataset = client.get(
        "/api/analysis/research-dataset?limit=20",
        headers=owner_headers,
    )
    assert dataset.status_code == 200
    assert {
        record["activity"]["activity_id"]
        for record in dataset.json()["records"]
    } == {"prior-1", "prior-2", "shared-activity"}


def test_analysis_exposes_provenance_segments_and_causal_context(
    analysis_client,
) -> None:
    client = analysis_client["client"]
    headers = analysis_client["owner_headers"]
    response = client.get(
        "/api/analysis/activities/shared-activity",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["schema_version"] == "activity-analysis-v1"
    activity = payload["activity"]
    assert activity["start_time"]["state"] == "available"
    assert activity["start_time"]["provenance"] == "sample_epoch_fallback"
    assert activity["start_time"]["timezone"] == "UTC"
    environment = activity["environment"]
    assert environment["state"] == "available"
    assert environment["model_version"] == (
        "environmental-performance-context-v1"
    )
    assert environment["science_decision_id"] == (
        "sdr-environmental-performance-v1"
    )
    assert environment["temperature_c"] == 34.0
    assert environment["relative_humidity_pct"] == 70.0
    assert environment["source"] == "stryd_activity_weather"
    assert environment["wet_bulb_c"] is not None
    assert environment["wet_bulb_method"] == "stull_psychrometric"
    assert environment["reason_codes"] == []
    assert any(
        source["id"] == "stull-2011"
        for source in environment["science_sources"]
    )
    assert "outdoor_wbgt_unavailable" in environment["limitations"]
    assert activity["sample_coverage"]["sample_coverage_ratio"] == 1.0
    assert activity["provenance"]["power"]["providers"] == ["stryd"]
    assert activity["provenance"]["heart_rate"]["providers"] == ["stryd"]

    segment = payload["stable_segments"]["segments"][0]
    assert segment["source"] == "samples"
    assert segment["mean_pct_cp"] == 83.3
    assert segment["power_cv_pct"] == 0.0
    assert segment["hr_slope_bpm_per_min"] == pytest.approx(1.0)

    context = payload["pre_activity_context"]
    assert context["critical_power"] == {
        "state": "available",
        "value_watts": 300.0,
        "effective_date": "2026-07-14",
        "source": "stryd",
        "power_provider": "stryd",
        "selection": "latest_strictly_before_activity_date",
        "reason_codes": [],
    }
    assert context["recovery"]["date"] == "2026-07-15"
    assert context["recovery"]["source"] == "oura"
    assert context["recovery"]["values"]["readiness_score"] == 82.0
    assert context["load"]["as_of_date"] == "2026-07-14"
    assert context["heat_adaptation"]["as_of_date"] == "2026-07-14"
    assert all(
        session["activity_id"] != "shared-activity"
        for session in context["heat_adaptation"].get("sessions", [])
    )

    from db import session as db_session
    from db.models import Activity

    db = db_session.SessionLocal()
    target = db.query(Activity).filter(
        Activity.user_id == analysis_client["owner_id"],
        Activity.activity_id == "shared-activity",
    ).one()
    target.rss = 1_000_000
    db.commit()
    db.close()

    after = client.get(
        "/api/analysis/activities/shared-activity",
        headers=headers,
    ).json()
    assert after["pre_activity_context"]["load"] == context["load"]

    history = client.get("/api/history?limit=10", headers=headers)
    assert history.status_code == 200
    history_activity = next(
        item
        for item in history.json()["activities"]
        if item["activity_id"] == "shared-activity"
    )
    assert history_activity["start_time"]["provenance"] == (
        "sample_epoch_fallback"
    )
    assert history_activity["temperature_c"] == 34.0
    assert history_activity["max_hr"] == 160


def test_missing_inputs_return_explicit_unavailable_states(
    analysis_client,
) -> None:
    response = analysis_client["client"].get(
        "/api/analysis/activities/private-other",
        headers=analysis_client["other_headers"],
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["activity"]["environment"]["state"] == "unavailable"
    assert payload["activity"]["sample_coverage"]["state"] == "unavailable"
    assert payload["stable_segments"]["status"] == "unavailable"
    assert (
        payload["pre_activity_context"]["critical_power"]["state"]
        == "unavailable"
    )
    assert (
        payload["pre_activity_context"]["recovery"]["state"]
        == "unavailable"
    )
    assert payload["pre_activity_context"]["load"] == {
        "state": "unavailable",
        "as_of_date": "2026-07-14",
        "ctl": None,
        "atl": None,
        "tsb": None,
        "model_version": "banister-pmc-causal-v2",
        "training_base": "power",
        "load_sources": [],
        "time_constants_days": {"ctl": 42, "atl": 7},
        "data_days": 0,
        "observation_days": 0,
        "missing_load_activity_count": 0,
        "reason_codes": ["prior_activity_load_unavailable"],
    }


def test_environment_context_rejects_corrupt_activity_weather(
    analysis_client,
) -> None:
    from db import session as db_session
    from db.models import Activity

    db = db_session.SessionLocal()
    activity = db.query(Activity).filter(
        Activity.user_id == analysis_client["other_id"],
        Activity.activity_id == "private-other",
    ).one()
    activity.temperature_c = 95.0
    activity.relative_humidity_pct = 140.0
    activity.environment_source = "garmin_activity_weather"
    db.commit()
    db.close()

    response = analysis_client["client"].get(
        "/api/analysis/activities/private-other",
        headers=analysis_client["other_headers"],
    )
    assert response.status_code == 200, response.text
    activity_payload = response.json()["activity"]
    environment = activity_payload["environment"]

    assert environment["state"] == "unavailable"
    assert environment["temperature_c"] is None
    assert environment["relative_humidity_pct"] is None
    assert environment["reason_codes"] == [
        "temperature_out_of_range",
        "relative_humidity_out_of_range",
    ]
    assert activity_payload["temperature_c"] is None
    assert activity_payload["relative_humidity_pct"] is None

    db = db_session.SessionLocal()
    activity = db.query(Activity).filter(
        Activity.user_id == analysis_client["other_id"],
        Activity.activity_id == "private-other",
    ).one()
    activity.temperature_c = 24.0
    activity.relative_humidity_pct = 50.0
    activity.environment_source = "weather_station_summary"
    db.commit()
    db.close()

    unsupported_response = analysis_client["client"].get(
        "/api/analysis/activities/private-other",
        headers=analysis_client["other_headers"],
    )
    assert unsupported_response.status_code == 200, unsupported_response.text
    unsupported_activity = unsupported_response.json()["activity"]
    unsupported_environment = unsupported_activity["environment"]

    assert unsupported_environment["state"] == "unavailable"
    assert unsupported_environment["temperature_c"] is None
    assert unsupported_environment["relative_humidity_pct"] is None
    assert unsupported_environment["source"] == "weather_station_summary"
    assert unsupported_environment["reason_codes"] == [
        "environment_source_unsupported"
    ]
    assert unsupported_activity["temperature_c"] is None
    assert unsupported_activity["relative_humidity_pct"] is None


def test_partial_context_and_provider_fallbacks_are_explicit(
    analysis_client,
) -> None:
    from db import session as db_session
    from db.models import Activity, FitnessData, RecoveryData

    target_date = analysis_client["target_date"]
    other_id = analysis_client["other_id"]
    db = db_session.SessionLocal()
    db.add_all([
        Activity(
            user_id=other_id,
            activity_id="other-prior",
            date=target_date - timedelta(days=1),
            activity_type="running",
            duration_sec=1800,
            load_score=40,
            source="garmin",
        ),
        FitnessData(
            user_id=other_id,
            date=target_date - timedelta(days=1),
            metric_type="cp_estimate",
            value=280,
            source="activities",
            power_source=None,
        ),
        RecoveryData(
            user_id=other_id,
            date=target_date,
            hrv_avg=55,
            source="garmin",
        ),
    ])
    db.commit()
    db.close()

    response = analysis_client["client"].get(
        "/api/analysis/activities/private-other",
        headers=analysis_client["other_headers"],
    )
    assert response.status_code == 200, response.text
    context = response.json()["pre_activity_context"]

    assert context["load"]["state"] == "partial"
    assert context["load"]["load_sources"] == ["load_score"]
    assert context["load"]["reason_codes"] == [
        "load_history_insufficient"
    ]
    assert context["critical_power"]["state"] == "partial"
    assert context["critical_power"]["value_watts"] == 280.0
    assert context["critical_power"]["power_provider"] is None
    assert context["critical_power"]["reason_codes"] == [
        "critical_power_provider_unavailable"
    ]
    assert context["recovery"]["state"] == "partial"
    assert context["recovery"]["values"]["hrv_avg"] == 55.0
    assert "readiness_score_unavailable" in (
        context["recovery"]["reason_codes"]
    )


def test_future_recovery_rows_do_not_change_historical_provider_selection(
    analysis_client,
) -> None:
    from db import session as db_session
    from db.models import RecoveryData

    target_date = analysis_client["target_date"]
    other_id = analysis_client["other_id"]
    db = db_session.SessionLocal()
    db.add_all([
        RecoveryData(
            user_id=other_id,
            date=target_date - timedelta(days=1),
            readiness_score=75,
            source="oura",
        ),
        RecoveryData(
            user_id=other_id,
            date=target_date + timedelta(days=1),
            readiness_score=99,
            source="garmin",
        ),
    ])
    db.commit()
    db.close()

    response = analysis_client["client"].get(
        "/api/analysis/activities/private-other",
        headers=analysis_client["other_headers"],
    )
    assert response.status_code == 200, response.text
    recovery = response.json()["pre_activity_context"]["recovery"]

    assert recovery["state"] == "partial"
    assert recovery["date"] == (target_date - timedelta(days=1)).isoformat()
    assert recovery["source"] == "oura"
    assert recovery["values"]["readiness_score"] == 75.0


def test_missing_prior_activity_load_marks_context_partial(
    analysis_client,
) -> None:
    from db import session as db_session
    from db.models import Activity

    target_date = analysis_client["target_date"]
    other_id = analysis_client["other_id"]
    db = db_session.SessionLocal()
    db.add_all([
        Activity(
            user_id=other_id,
            activity_id="other-old-load",
            date=target_date - timedelta(days=50),
            activity_type="running",
            duration_sec=1800,
            rss=40,
            source="garmin",
        ),
        Activity(
            user_id=other_id,
            activity_id="other-missing-load",
            date=target_date - timedelta(days=2),
            activity_type="running",
            duration_sec=1800,
            source="garmin",
        ),
    ])
    db.commit()
    db.close()

    response = analysis_client["client"].get(
        "/api/analysis/activities/private-other",
        headers=analysis_client["other_headers"],
    )
    assert response.status_code == 200, response.text
    load = response.json()["pre_activity_context"]["load"]

    assert load["state"] == "partial"
    assert load["missing_load_activity_count"] == 1
    assert load["ctl"] is not None
    assert load["atl"] is not None
    assert load["tsb"] is None
    assert load["reason_codes"] == [
        "activity_load_observations_missing"
    ]


def test_research_dataset_is_versioned_reproducible_and_gps_free(
    analysis_client,
) -> None:
    client = analysis_client["client"]
    headers = analysis_client["owner_headers"]
    first = client.get(
        "/api/analysis/research-dataset?limit=20",
        headers=headers,
    )
    second = client.get(
        "/api/analysis/research-dataset?limit=20",
        headers=headers,
    )
    assert first.status_code == second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()

    assert first_payload["schema_version"] == (
        "activity-research-dataset-v1"
    )
    assert first_payload["dataset_hash"] == second_payload["dataset_hash"]
    assert first_payload["privacy"] == {
        "precise_gps_included": False,
        "credentials_included": False,
        "raw_samples_included": False,
    }
    serialized = first.text
    assert '"lat"' not in serialized
    assert '"lng"' not in serialized
