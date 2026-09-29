"""Integration coverage for owner-only activity analysis APIs."""
from __future__ import annotations

import hashlib
import json
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
    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
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
            terms_version=TERMS_VERSION,
            terms_digest=TERMS_CONTENT_DIGEST,
        ),
        User(
            id=other_id,
            email="analysis-other@example.com",
            hashed_password="x",
            terms_version=TERMS_VERSION,
            terms_digest=TERMS_CONTENT_DIGEST,
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


def test_activity_detail_is_owner_scoped_and_excludes_location(analysis_client) -> None:
    from db import session as db_session
    from db.models import ActivitySplit

    db = db_session.SessionLocal()
    db.add(ActivitySplit(
        user_id=analysis_client["other_id"], activity_id="shared-activity",
        split_num=1, duration_sec=300, avg_power=112, avg_hr=104,
    ))
    db.commit()
    db.close()

    client = analysis_client["client"]
    owner = analysis_client["owner_headers"]
    unauthenticated = client.get("/api/history/shared-activity/detail")
    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["cache-control"] == "private, no-store"
    foreign = client.get(
        "/api/history/private-other/detail", headers=owner,
    )
    assert foreign.status_code == 404
    assert foreign.headers["cache-control"] == "private, no-store"
    rejected_method = client.post("/api/history/shared-activity/detail", headers=owner)
    assert rejected_method.status_code == 405
    assert rejected_method.headers["cache-control"] == "private, no-store"

    response = client.get("/api/history/shared-activity/detail", headers=owner)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    detail = response.json()
    assert detail["activity"]["distance_km"] == 10
    assert detail["sample_count"] == 601
    assert detail["activity"]["sample_coverage"]["sample_count"] == 601
    assert detail["activity"]["splits"][0]["avg_power"] == 250
    assert detail["samples"][0]["power_watts"] == 250
    assert detail["kilometer_unavailable_reason"] == "distance_trace_unavailable"
    assert detail["kilometer_splits"] == []
    assert detail["privacy"] == {
        "gps_included": False, "raw_distance_trace_included": False,
    }
    assert '"lat":' not in response.text
    assert "distance_m" not in detail["samples"][0]
    assert "start_offset_sec" not in detail["activity"]["splits"][0]

    other = client.get(
        "/api/history/shared-activity/detail",
        headers=analysis_client["other_headers"],
    ).json()
    assert other["activity"]["distance_km"] == 999
    assert other["activity"]["splits"][0]["avg_power"] == 112
    assert other["activity"]["sample_coverage"]["sample_count"] == 0
    assert other["samples"] == []


def test_activity_detail_unhandled_error_is_not_cached(analysis_client, monkeypatch) -> None:
    from fastapi.testclient import TestClient
    from api.main import app

    def fail_detail(_user_id, _db, _activity_id):
        raise RuntimeError("synthetic activity detail failure")

    monkeypatch.setattr("api.routes.history.get_activity_detail", fail_detail)
    client = TestClient(app, raise_server_exceptions=False)
    try:
        response = client.get(
            "/api/history/shared-activity/detail",
            headers=analysis_client["owner_headers"],
        )
    finally:
        client.close()

    assert response.status_code == 500
    assert response.headers["cache-control"] == "private, no-store"
    assert "synthetic activity detail failure" not in response.text
    with pytest.raises(RuntimeError, match="synthetic activity detail failure"):
        analysis_client["client"].get(
            "/api/history/shared-activity/detail",
            headers=analysis_client["owner_headers"],
        )


def test_activity_detail_does_not_disclose_owner_streams_to_demo(
    analysis_client, monkeypatch,
) -> None:
    from api.legal import TERMS_CONTENT_DIGEST, TERMS_VERSION
    from db import session as db_session
    from db.models import User

    db = db_session.SessionLocal()
    db.add(User(
        id="analysis-demo", email="analysis-demo@example.com", hashed_password="x",
        is_demo=True, demo_of=analysis_client["owner_id"],
        terms_version=TERMS_VERSION, terms_digest=TERMS_CONTENT_DIGEST,
    ))
    db.commit()
    db.close()

    token = jwt.encode({
        "sub": "analysis-demo", "aud": "fastapi-users:auth",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }, "activity-analysis-test-secret-with-adequate-length", algorithm="HS256")
    demo_response = analysis_client["client"].get(
        "/api/history/shared-activity/detail",
        headers={"Authorization": f"Bearer {token}"},
    )
    foreign_response = analysis_client["client"].get(
        "/api/history/private-other/detail",
        headers=analysis_client["owner_headers"],
    )
    assert demo_response.status_code == 404
    assert demo_response.headers["cache-control"] == "private, no-store"
    assert demo_response.json() == foreign_response.json()
    assert "power_watts" not in demo_response.text

    monkeypatch.setattr(
        "api.routes.history.stryd_connection_enabled",
        lambda _db, user_id: False,
    )
    owner_history = analysis_client["client"].get(
        "/api/history?limit=10", headers=analysis_client["owner_headers"],
    )
    demo_headers = {"Authorization": f"Bearer {token}"}
    demo_history = analysis_client["client"].get(
        "/api/history?limit=10",
        headers={**demo_headers, "If-None-Match": owner_history.headers["etag"]},
    )
    assert owner_history.status_code == 200
    assert owner_history.json()["activity_detail_available"] is True
    assert demo_history.status_code == 200
    assert demo_history.json()["activity_detail_available"] is False
    assert demo_history.json()["activities"] == owner_history.json()["activities"]
    assert demo_history.headers["etag"] != owner_history.headers["etag"]

    cached_demo = analysis_client["client"].get(
        "/api/history?limit=10",
        headers={**demo_headers, "If-None-Match": demo_history.headers["etag"]},
    )
    owner_from_demo_cache = analysis_client["client"].get(
        "/api/history?limit=10",
        headers={**analysis_client["owner_headers"], "If-None-Match": demo_history.headers["etag"]},
    )
    assert cached_demo.status_code == 304
    assert owner_from_demo_cache.status_code == 200

    other_from_owner_cache = analysis_client["client"].get(
        "/api/history?limit=10",
        headers={**analysis_client["other_headers"], "If-None-Match": owner_history.headers["etag"]},
    )
    assert other_from_owner_cache.status_code == 200
    assert other_from_owner_cache.json()["activity_detail_available"] is True
    assert other_from_owner_cache.headers["etag"] != owner_history.headers["etag"]


def test_activity_detail_keeps_missing_metric_segments_disconnected(analysis_client) -> None:
    from db.models import ActivitySample
    from db import session as db_session

    db = db_session.SessionLocal()
    target_epoch = int(datetime(2026, 7, 15, 6, tzinfo=timezone.utc).timestamp())
    db.query(ActivitySample).filter(
        ActivitySample.user_id == analysis_client["owner_id"],
        ActivitySample.activity_id == "shared-activity",
        ActivitySample.t_sec.between(target_epoch + 50, target_epoch + 52),
    ).update({ActivitySample.hr_bpm: None}, synchronize_session=False)
    db.commit()
    db.close()

    detail = analysis_client["client"].get(
        "/api/history/shared-activity/detail",
        headers=analysis_client["owner_headers"],
    ).json()
    points = {point["offset_sec"]: point for point in detail["samples"]}
    assert points[50]["hr_bpm"] is None
    assert points[51]["hr_bpm"] is None
    assert points[52]["hr_bpm"] is None
    assert points[53]["hr_bpm_break"] is True
    assert points[53]["power_watts_break"] is False


def test_activity_detail_includes_extended_samples_without_inventing_gaps(analysis_client) -> None:
    from db.models import ActivitySample
    from db import session as db_session

    target_epoch = int(datetime(2026, 7, 15, 6, tzinfo=timezone.utc).timestamp())
    db = db_session.SessionLocal()
    recorded = {
        ActivitySample.pace_sec_km: 335,
        ActivitySample.cadence_spm: 174,
        ActivitySample.speed_ms: 3.2,
        ActivitySample.altitude_m: -12,
        ActivitySample.grade_pct: -2.5,
        ActivitySample.temperature_c: 0,
        ActivitySample.ground_time_ms: 238,
        ActivitySample.oscillation_mm: 70,
        ActivitySample.vertical_ratio: 7.1,
        ActivitySample.leg_spring_kn_m: 10.2,
        ActivitySample.form_power_watts: 0,
        ActivitySample.respiration_rate: 22,
    }
    db.query(ActivitySample).filter(
        ActivitySample.user_id == analysis_client["owner_id"],
        ActivitySample.activity_id == "shared-activity",
        ActivitySample.t_sec.in_((target_epoch + 100, target_epoch + 102)),
    ).update(recorded, synchronize_session=False)
    db.commit()
    db.close()

    detail = analysis_client["client"].get(
        "/api/history/shared-activity/detail",
        headers=analysis_client["owner_headers"],
    ).json()
    points = {point["offset_sec"]: point for point in detail["samples"]}
    for field, value in (
        ("pace_sec_km", 335), ("cadence_spm", 174), ("speed_ms", 3.2),
        ("altitude_m", -12), ("grade_pct", -2.5), ("temperature_c", 0),
        ("ground_time_ms", 238), ("oscillation_mm", 70),
        ("vertical_ratio", 7.1), ("leg_spring_kn_m", 10.2),
        ("form_power_watts", 0), ("respiration_rate", 22),
    ):
        assert points[100][field] == value
        assert points[101][field] is None
        assert points[102][f"{field}_break"] is True
    assert points[102]["power_watts_break"] is False
    assert points[100]["source"] == "stryd"
    assert "distance_m" not in points[100]


def test_activity_detail_only_enables_kilometers_for_verified_distance_trace(analysis_client) -> None:
    from db.models import Activity, ActivitySample, ActivitySplit
    from db import session as db_session

    owner_id = analysis_client["owner_id"]
    target_epoch = int(datetime(2026, 7, 15, 6, tzinfo=timezone.utc).timestamp())
    db = db_session.SessionLocal()
    db.add(Activity(
        user_id=owner_id, activity_id="verified-2k", date=analysis_client["target_date"],
        start_time="2026-07-15T06:00:00Z", activity_type="running",
        duration_sec=720, distance_km=2.15, source="garmin",
    ))
    db.add(ActivitySplit(
        user_id=owner_id, activity_id="verified-2k", split_num=1,
        distance_km=0.88, duration_sec=300, avg_hr=145,
    ))
    db.add_all([
        ActivitySample(
            user_id=owner_id, activity_id="verified-2k", source="garmin",
            t_sec=target_epoch + second, distance_m=second * 2150 / 720,
            pace_sec_km=335, hr_bpm=145,
        )
        for second in range(721)
    ])
    db.commit()
    db.close()

    url = "/api/history/verified-2k/detail"
    client = analysis_client["client"]
    headers = analysis_client["owner_headers"]
    detail = client.get(url, headers=headers).json()
    assert detail["kilometer_unavailable_reason"] is None
    assert len(detail["kilometer_splits"]) == 3
    assert [part["split_num"] for part in detail["kilometer_splits"]] == [1, 2, 3]
    assert 0 < detail["kilometer_splits"][-1]["distance_km"] < 0.2
    assert detail["kilometer_splits"][0]["start_offset_sec"] == 0
    assert detail["kilometer_splits"][-1]["end_offset_sec"] == 720
    assert "start_offset_sec" not in detail["activity"]["splits"][0]

    db = db_session.SessionLocal()
    db.query(ActivitySample).filter(
        ActivitySample.user_id == owner_id,
        ActivitySample.activity_id == "verified-2k",
    ).update({ActivitySample.hr_bpm: None, ActivitySample.pace_sec_km: None}, synchronize_session=False)
    db.commit()
    db.close()
    distance_only = client.get(url, headers=headers).json()
    assert distance_only["sample_count"] == 721
    assert len(distance_only["kilometer_splits"]) == 3
    assert all(point["hr_bpm"] is None and point["pace_sec_km"] is None
               for point in distance_only["samples"])

    db = db_session.SessionLocal()
    db.query(ActivitySample).filter(
        ActivitySample.user_id == owner_id,
        ActivitySample.activity_id == "verified-2k",
        ActivitySample.t_sec == target_epoch + 300,
    ).update({ActivitySample.distance_m: None}, synchronize_session=False)
    db.commit()
    db.close()
    incomplete = client.get(url, headers=headers).json()
    assert incomplete["kilometer_splits"] == []
    assert incomplete["kilometer_unavailable_reason"] == "distance_trace_incomplete"


def test_activity_detail_downsampling_keeps_recorded_extrema_and_breaks() -> None:
    from api.activity_detail import _select_display_samples

    points = [{
        "offset_sec": second,
        "power_watts": None if 2000 <= second <= 2010 else (880 if second == 1555 else 210),
        "hr_bpm": 135,
        "pace_sec_km": None,
        "source": "garmin",
    } for second in range(12000)]
    displayed = _select_display_samples(points)
    assert len(displayed) <= 6000
    assert any(point["power_watts"] == 880 for point in displayed)
    following = next(point for point in displayed if point["offset_sec"] > 2010 and point["power_watts"] is not None)
    assert following["power_watts_break"] is True
    assert following["hr_bpm_break"] is False


def test_activity_detail_does_not_display_zero_distance_tail() -> None:
    from types import SimpleNamespace
    from api.activity_detail import _kilometer_splits

    epoch = int(datetime(2026, 7, 15, 6, tzinfo=timezone.utc).timestamp())
    rows = [SimpleNamespace(
        t_sec=epoch + second,
        distance_m=second * 2000 / 600 if second <= 600 else 2002,
    ) for second in range(602)]
    splits, reason = _kilometer_splits(
        rows, start_epoch=epoch, verified_start=True,
        distance_km=2.002, duration_sec=601,
    )
    assert reason is None
    assert len(splits) == 2
    assert splits[-1]["end_offset_sec"] == 601
    assert splits[-1]["distance_km"] > 0

    tiny_rows = [SimpleNamespace(t_sec=epoch, distance_m=0),
                 SimpleNamespace(t_sec=epoch + 1, distance_m=2)]
    tiny_splits, tiny_reason = _kilometer_splits(
        tiny_rows, start_epoch=epoch, verified_start=True,
        distance_km=0.002, duration_sec=1,
    )
    assert tiny_splits == []
    assert tiny_reason == "distance_below_display_precision"


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


def test_history_hides_stryd_source_selection_when_gate_is_off(
    analysis_client,
    monkeypatch,
) -> None:
    client = analysis_client["client"]
    headers = analysis_client["owner_headers"]
    monkeypatch.setattr(
        "api.statsig_client.check_gate",
        lambda _gate_name, _user: False,
    )

    hidden = client.get("/api/history?limit=10", headers=headers)
    explicit = client.get(
        "/api/history?limit=10&source=stryd",
        headers=headers,
    )

    assert hidden.status_code == 200, hidden.text
    assert hidden.json()["source_filter"] is None
    assert any(
        activity["source"] == "stryd"
        for activity in hidden.json()["activities"]
    ), "historical provenance should remain truthful"
    assert explicit.status_code == 404

    monkeypatch.setattr(
        "api.statsig_client.check_gate",
        lambda gate_name, _user: gate_name == "stryd_connection_enabled",
    )
    enabled = client.get(
        "/api/history?limit=10",
        headers={
            **headers,
            "If-None-Match": hidden.headers["etag"],
        },
    )

    assert enabled.status_code == 200
    assert enabled.headers["etag"] != hidden.headers["etag"]
    assert enabled.json()["source_filter"] == "stryd"


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
    assert "reference_power_support" not in payload
    assert payload["model_versions"]["stable_segments"] == (
        "stable-power-segments-v3"
    )
    activity = payload["activity"]
    assert activity["start_time"]["state"] == "available"
    assert activity["start_time"]["provenance"] == "sample_epoch_fallback"
    assert activity["start_time"]["timezone"] == "UTC"
    environment = activity["environment"]
    assert environment["state"] == "available"
    assert environment["model_version"] == (
        "environmental-performance-context-v2"
    )
    assert environment["science_decision_id"] == (
        "sdr-environmental-performance-v2"
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
    assert payload["stable_segments"]["model_version"] == (
        "stable-power-segments-v3"
    )
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
    assert first_payload["export_snapshot_id"]
    assert first_payload["export_snapshot_id"] == (
        second_payload["export_snapshot_id"]
    )
    assert first_payload["dataset_hash"] == second_payload["dataset_hash"]
    assert first_payload["privacy"] == {
        "precise_gps_included": False,
        "credentials_included": False,
        "raw_samples_included": False,
    }
    assert all(
        "reference_power_support" not in record
        for record in first_payload["records"]
    )
    serialized = first.text
    assert '"lat"' not in serialized
    assert '"lng"' not in serialized


def test_research_dataset_snapshot_is_page_independent_and_hash_covered(
    analysis_client,
) -> None:
    client = analysis_client["client"]
    headers = analysis_client["owner_headers"]
    page_zero = client.get(
        "/api/analysis/research-dataset?limit=1&offset=0",
        headers=headers,
    )
    page_one = client.get(
        "/api/analysis/research-dataset?limit=1&offset=1",
        headers=headers,
    )

    assert page_zero.status_code == page_one.status_code == 200
    first = page_zero.json()
    second = page_one.json()
    assert first["export_snapshot_id"] == second["export_snapshot_id"]
    assert page_zero.headers["etag"] != page_one.headers["etag"]

    core = {
        key: value
        for key, value in first.items()
        if key not in {"dataset_hash", "generated_at"}
    }
    encoded = json.dumps(
        core,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    assert first["dataset_hash"] == (
        "sha256:" + hashlib.sha256(encoded).hexdigest()
    )

    core["export_snapshot_id"] += "-different"
    changed = json.dumps(
        core,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    assert first["dataset_hash"] != (
        "sha256:" + hashlib.sha256(changed).hexdigest()
    )


def test_research_dataset_snapshot_fence_accepts_stable_page(
    analysis_client,
    monkeypatch,
) -> None:
    from api.routes import analysis as analysis_route

    computed_tokens: list[str] = []
    original_compute = analysis_route.compute_revision_token

    def _tracked_compute(*args, **kwargs) -> str:
        token = original_compute(*args, **kwargs)
        computed_tokens.append(token)
        return token

    monkeypatch.setattr(
        analysis_route,
        "compute_revision_token",
        _tracked_compute,
    )
    response = analysis_client["client"].get(
        "/api/analysis/research-dataset?limit=1&offset=0",
        headers=analysis_client["owner_headers"],
    )

    assert response.status_code == 200, response.text
    assert computed_tokens == [
        response.json()["export_snapshot_id"],
        response.json()["export_snapshot_id"],
    ]
    assert response.headers["etag"]
    assert response.json()["dataset_hash"]


def test_research_dataset_rejects_revision_change_during_pack_construction(
    analysis_client,
    monkeypatch,
) -> None:
    from api.routes import analysis as analysis_route
    from db import session as db_session
    from db.cache_revision import bump_revisions

    original_pack = analysis_route.get_activity_research_pack

    def _pack_with_concurrent_revision(*args, **kwargs) -> dict:
        payload = original_pack(*args, **kwargs)
        side = db_session.SessionLocal()
        try:
            bump_revisions(
                side,
                analysis_client["owner_id"],
                ["activities"],
            )
            side.commit()
        finally:
            side.close()
        return payload

    monkeypatch.setattr(
        analysis_route,
        "get_activity_research_pack",
        _pack_with_concurrent_revision,
    )
    response = analysis_client["client"].get(
        "/api/analysis/research-dataset?limit=1&offset=0",
        headers=analysis_client["owner_headers"],
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "ANALYSIS_EXPORT_SNAPSHOT_CHANGED_RESTART_EXPORT"
    }
    assert "etag" not in response.headers
    assert "dataset_hash" not in response.text
    assert "export_snapshot_id" not in response.text
    assert '"records"' not in response.text


def test_research_dataset_snapshot_changes_after_relevant_data_mutation(
    analysis_client,
) -> None:
    from db import session as db_session
    from db.cache_revision import bump_revisions
    from db.models import Activity

    client = analysis_client["client"]
    headers = analysis_client["owner_headers"]
    path = "/api/analysis/research-dataset?limit=1&offset=0"
    first = client.get(path, headers=headers)
    assert first.status_code == 200, first.text

    db = db_session.SessionLocal()
    activity = db.query(Activity).filter(
        Activity.user_id == analysis_client["owner_id"],
        Activity.activity_id == "shared-activity",
    ).one()
    activity.distance_km = 10.1
    bump_revisions(db, analysis_client["owner_id"], ["activities"])
    db.commit()
    db.close()

    second = client.get(path, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["export_snapshot_id"] != (
        first.json()["export_snapshot_id"]
    )


def test_research_dataset_hash_is_independent_of_split_insertion_order(
    analysis_client,
) -> None:
    from db import session as db_session
    from db.models import ActivitySplit

    def _replace_splits(split_numbers: list[int]) -> None:
        db = db_session.SessionLocal()
        db.query(ActivitySplit).filter(
            ActivitySplit.user_id == analysis_client["other_id"],
            ActivitySplit.activity_id == "private-other",
        ).delete()
        for split_num in split_numbers:
            db.add(ActivitySplit(
                user_id=analysis_client["other_id"],
                activity_id="private-other",
                split_num=split_num,
                duration_sec=150,
                distance_km=float(split_num),
                avg_power=200 + split_num,
                power_source="garmin",
                avg_hr=140 + split_num,
            ))
        db.commit()
        db.close()

    client = analysis_client["client"]
    headers = analysis_client["other_headers"]
    path = "/api/analysis/research-dataset?limit=20"

    _replace_splits([2, 1])
    first = client.get(path, headers=headers)
    assert first.status_code == 200, first.text

    _replace_splits([1, 2])
    second = client.get(path, headers=headers)
    assert second.status_code == 200, second.text

    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["dataset_hash"] == second_payload["dataset_hash"]
    first_record = next(
        record
        for record in first_payload["records"]
        if record["activity"]["activity_id"] == "private-other"
    )
    second_record = next(
        record
        for record in second_payload["records"]
        if record["activity"]["activity_id"] == "private-other"
    )
    assert first_record["activity"]["splits"] == (
        second_record["activity"]["splits"]
    )
    assert [
        split["split_num"]
        for split in first_record["activity"]["splits"]
    ] == [1, 2]


def test_record_hash_is_independent_of_same_date_heat_insertion_order(
    analysis_client,
) -> None:
    from db import session as db_session
    from db.models import Activity, ActivitySplit

    heat_activity_ids = ("heat-a", "heat-b")

    def _replace_heat_activities(activity_ids: tuple[str, str]) -> None:
        db = db_session.SessionLocal()
        db.query(ActivitySplit).filter(
            ActivitySplit.user_id == analysis_client["owner_id"],
            ActivitySplit.activity_id.in_(heat_activity_ids),
        ).delete(synchronize_session=False)
        db.query(Activity).filter(
            Activity.user_id == analysis_client["owner_id"],
            Activity.activity_id.in_(heat_activity_ids),
        ).delete(synchronize_session=False)
        for activity_id in activity_ids:
            db.add(Activity(
                user_id=analysis_client["owner_id"],
                activity_id=activity_id,
                date=analysis_client["target_date"] - timedelta(days=1),
                activity_type="running",
                duration_sec=3600,
                temperature_c=34,
                relative_humidity_pct=70,
                environment_source="stryd_activity_weather",
                source="stryd",
            ))
            db.add(ActivitySplit(
                user_id=analysis_client["owner_id"],
                activity_id=activity_id,
                split_num=1,
                duration_sec=3600,
                avg_power=220,
                power_source="stryd",
            ))
        db.commit()
        db.close()

    client = analysis_client["client"]
    headers = analysis_client["owner_headers"]
    path = "/api/analysis/activities/shared-activity"

    _replace_heat_activities(("heat-b", "heat-a"))
    first = client.get(path, headers=headers)
    assert first.status_code == 200, first.text

    _replace_heat_activities(("heat-a", "heat-b"))
    second = client.get(path, headers=headers)
    assert second.status_code == 200, second.text

    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["record_hash"] == second_payload["record_hash"]
    first_sessions = first_payload["pre_activity_context"][
        "heat_adaptation"
    ]["sessions"]
    second_sessions = second_payload["pre_activity_context"][
        "heat_adaptation"
    ]["sessions"]
    assert first_sessions == second_sessions


def test_research_pagination_canonicalizes_same_date_ties() -> None:
    from types import SimpleNamespace

    import pandas as pd

    from api.packs import _history_page

    activities = pd.DataFrame([
        {
            "activity_id": "same-date-b",
            "date": date(2026, 7, 15),
            "source": "stryd",
        },
        {
            "activity_id": "newer",
            "date": date(2026, 7, 16),
            "source": "stryd",
        },
        {
            "activity_id": "same-date-a",
            "date": date(2026, 7, 15),
            "source": "stryd",
        },
    ])

    page_orders = []
    for frame in (activities, activities.iloc[::-1].reset_index(drop=True)):
        ctx = SimpleNamespace(
            config=SimpleNamespace(
                preferences={"activities": "stryd"},
            ),
            merged_activities=frame,
            _data={"activities": frame},
        )
        page, total, _ = _history_page(ctx, limit=3)
        assert total == 3
        page_orders.append(page["activity_id"].tolist())

    assert page_orders == [
        ["newer", "same-date-a", "same-date-b"],
        ["newer", "same-date-a", "same-date-b"],
    ]


@pytest.mark.parametrize(
    "path",
    [
        "/api/analysis/activities/shared-activity",
        "/api/analysis/research-dataset?limit=20",
    ],
)
def test_analysis_etags_change_with_emitted_model_versions(
    analysis_client,
    monkeypatch,
    path: str,
) -> None:
    from api import packs

    client = analysis_client["client"]
    headers = analysis_client["owner_headers"]
    first = client.get(path, headers=headers)
    assert first.status_code == 200, first.text
    first_etag = first.headers["etag"]
    first_snapshot_id = first.json().get("export_snapshot_id")

    monkeypatch.setattr(
        packs,
        "STABLE_SEGMENT_MODEL_VERSION",
        "stable-power-segments-next",
    )
    second = client.get(
        path,
        headers={**headers, "If-None-Match": first_etag},
    )

    assert second.status_code == 200
    assert second.headers["etag"] != first_etag
    if first_snapshot_id is not None:
        assert second.json()["export_snapshot_id"] != first_snapshot_id
