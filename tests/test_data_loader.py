import os
import tempfile
from datetime import date

import pandas as pd
import pytest
from analysis.config import UserConfig
from analysis.data_loader import (
    discover_activity_types,
    load_all_data,
    load_data,
    load_heat_adaptation_inputs_from_files,
    match_activities,
)


def _write_csv(path, rows):
    if not rows:
        return
    import csv
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def test_load_all_data_empty_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        for sub in ["garmin", "stryd", "oura"]:
            os.makedirs(os.path.join(tmpdir, sub))
        data = load_all_data(tmpdir)
        assert data["garmin_activities"].empty
        assert data["oura_readiness"].empty


def test_load_all_data_with_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        for sub in ["garmin", "stryd", "oura"]:
            os.makedirs(os.path.join(tmpdir, sub))
        _write_csv(os.path.join(tmpdir, "oura", "readiness.csv"), [
            {"date": "2026-03-10", "readiness_score": "82", "hrv_avg": "45", "resting_hr": "52", "body_temperature_delta": "0.1"},
        ])
        data = load_all_data(tmpdir)
        assert len(data["oura_readiness"]) == 1
        assert data["oura_readiness"].iloc[0]["readiness_score"] == 82


class TestDiscoverActivityTypes:
    def test_returns_types_from_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "garmin"))
            _write_csv(os.path.join(tmpdir, "garmin", "activities.csv"), [
                {"activity_id": "1", "date": "2026-03-10", "activity_type": "running", "distance_km": 10},
                {"activity_id": "2", "date": "2026-03-11", "activity_type": "cycling", "distance_km": 30},
                {"activity_id": "3", "date": "2026-03-12", "activity_type": "running", "distance_km": 8},
            ])
            result = discover_activity_types(["garmin"], tmpdir)
            assert result == {"garmin": ["cycling", "running"]}

    def test_missing_csv_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = discover_activity_types(["garmin", "stryd"], tmpdir)
            assert result == {"garmin": [], "stryd": []}

    def test_csv_without_activity_type_column(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "garmin"))
            _write_csv(os.path.join(tmpdir, "garmin", "activities.csv"), [
                {"activity_id": "1", "date": "2026-03-10", "distance_km": 10},
            ])
            result = discover_activity_types(["garmin"], tmpdir)
            assert result == {"garmin": []}

    def test_unknown_provider_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = discover_activity_types(["oura"], tmpdir)
            assert result == {"oura": []}

    def test_multiple_providers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "garmin"))
            os.makedirs(os.path.join(tmpdir, "stryd"))
            _write_csv(os.path.join(tmpdir, "garmin", "activities.csv"), [
                {"activity_id": "1", "date": "2026-03-10", "activity_type": "running", "distance_km": 10},
                {"activity_id": "2", "date": "2026-03-11", "activity_type": "hiking", "distance_km": 5},
            ])
            _write_csv(os.path.join(tmpdir, "stryd", "power_data.csv"), [
                {"date": "2026-03-10", "activity_type": "running", "avg_power": 240},
            ])
            result = discover_activity_types(["garmin", "stryd"], tmpdir)
            assert result["garmin"] == ["hiking", "running"]
            assert result["stryd"] == ["running"]


    def test_empty_string_activity_types_excluded(self):
        """CSV rows with empty string activity_type should not appear in results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "garmin"))
            _write_csv(os.path.join(tmpdir, "garmin", "activities.csv"), [
                {"activity_id": "1", "date": "2026-03-10", "activity_type": "running", "distance_km": 10},
                {"activity_id": "2", "date": "2026-03-11", "activity_type": "", "distance_km": 5},
                {"activity_id": "3", "date": "2026-03-12", "activity_type": "hiking", "distance_km": 8},
            ])
            result = discover_activity_types(["garmin"], tmpdir)
            assert result == {"garmin": ["hiking", "running"]}


def test_match_activities():
    garmin = pd.DataFrame([
        {"activity_id": "1", "date": "2026-03-10", "start_time": "2026-03-10 07:00:00", "distance_km": 12.5},
        {"activity_id": "2", "date": "2026-03-11", "start_time": "2026-03-11 06:30:00", "distance_km": 8.0},
    ])
    stryd = pd.DataFrame([
        {
            "activity_id": "stryd-1",
            "date": "2026-03-10",
            "start_time": "2026-03-10T07:01:30Z",
            "activity_type": "running",
            "avg_power": 245.0,
            "rss": 85.0,
        },
    ])
    merged = match_activities(garmin, stryd)
    assert len(merged) == 2
    row1 = merged[merged["activity_id"] == "1"].iloc[0]
    assert row1["activity_id"] == "1"
    assert row1["avg_power"] == 245.0
    row2 = merged[merged["activity_id"] == "2"].iloc[0]
    assert pd.isna(row2["avg_power"])


def test_load_data_canonicalizes_legacy_stryd_environment(tmp_path):
    """CSV mode adds provenance only to complete outdoor Stryd weather."""
    for subdir in ("garmin", "stryd", "oura"):
        (tmp_path / subdir).mkdir()
    _write_csv(tmp_path / "garmin" / "activities.csv", [
        {
            "activity_id": "outdoor",
            "date": "2026-03-10",
            "start_time": "2026-03-10 07:00:00",
            "activity_type": "running",
            "distance_km": 10,
            "duration_sec": 3600,
        },
        {
            "activity_id": "indoor",
            "date": "2026-03-11",
            "start_time": "2026-03-11 07:00:00",
            "activity_type": "running",
            "distance_km": 10,
            "duration_sec": 3600,
        },
    ])
    _write_csv(tmp_path / "stryd" / "power_data.csv", [
        {
            "activity_id": "stryd-outdoor",
            "date": "2026-03-10",
            "start_time": "2026-03-10T07:01:00Z",
            "stryd_type": "run",
            "surface_type": "road",
            "temperature_c": 34,
            "humidity": 0.72,
        },
        {
            "activity_id": "stryd-indoor",
            "date": "2026-03-11",
            "start_time": "2026-03-11T07:01:00Z",
            "stryd_type": "run",
            "surface_type": "treadmill",
            "temperature_c": 34,
            "humidity": 0.72,
        },
    ])

    data = load_data(UserConfig(), str(tmp_path))
    activities = data["activities"].set_index("activity_id")

    assert activities.loc["outdoor", "temperature_c"] == 34
    assert activities.loc["outdoor", "relative_humidity_pct"] == 72
    assert (
        activities.loc["outdoor", "environment_source"]
        == "stryd_activity_weather"
    )
    assert pd.isna(activities.loc["indoor", "temperature_c"])
    assert pd.isna(activities.loc["indoor", "relative_humidity_pct"])
    assert pd.isna(activities.loc["indoor", "environment_source"])


def test_load_data_preserves_stryd_ids_when_stryd_is_primary(tmp_path):
    """Primary Stryd activity IDs stay joined to Stryd split evidence."""
    from analysis.metrics import compute_heat_adaptation

    for subdir in ("garmin", "stryd", "oura"):
        (tmp_path / subdir).mkdir()
    _write_csv(tmp_path / "garmin" / "activities.csv", [{
        "activity_id": "garmin-1",
        "date": "2026-03-10",
        "start_time": "2026-03-10 07:00:00",
        "activity_type": "running",
        "distance_km": 10,
        "duration_sec": 3600,
    }])
    _write_csv(tmp_path / "stryd" / "power_data.csv", [{
        "activity_id": "stryd-1",
        "date": "2026-03-10",
        "start_time": "2026-03-10T07:01:00Z",
        "stryd_type": "run",
        "surface_type": "road",
        "temperature_c": 40,
        "relative_humidity_pct": 5,
        "duration_sec": 3600,
    }])
    _write_csv(tmp_path / "stryd" / "activity_splits.csv", [{
        "activity_id": "stryd-1",
        "split_num": 1,
        "duration_sec": 3600,
        "avg_power": 180,
        "power_source": "stryd",
    }])
    config = UserConfig(
        preferences={
            "activities": "stryd",
            "recovery": "oura",
            "plan": "stryd",
        },
    )

    data = load_data(config, str(tmp_path))
    splits = data["splits"].rename(
        columns={"power_source": "power_provider"},
    )
    status = compute_heat_adaptation(
        data["activities"],
        splits,
        cp_watts=270,
        cp_source="stryd",
        current_date=date(2026, 3, 10),
    )

    assert data["activities"].iloc[0]["activity_id"] == "stryd-1"
    assert status["data_coverage"]["workload_supported_activities"] == 1
    assert status["effective_heat_minutes"] == 60.0


def test_file_heat_loader_aligns_stryd_activities_splits_and_cp(tmp_path):
    """CSV fallback selects evidence from the provider behind current CP."""
    from analysis.metrics import compute_heat_adaptation

    (tmp_path / "stryd").mkdir()
    _write_csv(tmp_path / "stryd" / "power_data.csv", [{
        "activity_id": "stryd-1",
        "date": "2026-03-10",
        "start_time": "2026-03-10T07:01:00Z",
        "stryd_type": "run",
        "surface_type": "road",
        "temperature_c": 40,
        "humidity": 0.05,
        "duration_sec": 3600,
    }])
    _write_csv(tmp_path / "stryd" / "activity_splits.csv", [{
        "activity_id": "stryd-1",
        "split_num": 1,
        "duration_sec": 3600,
        "avg_power": 180,
    }])

    activities, splits, samples = load_heat_adaptation_inputs_from_files(
        "stryd",
        str(tmp_path),
    )

    assert activities.iloc[0]["activity_type"] == "running"
    assert (
        activities.iloc[0]["environment_source"]
        == "stryd_activity_weather"
    )
    assert splits.iloc[0]["power_provider"] == "stryd"
    assert samples.empty
    status = compute_heat_adaptation(
        activities,
        splits,
        samples,
        cp_watts=270,
        cp_source="stryd",
        current_date=date(2026, 3, 10),
    )
    assert status["data_coverage"]["environment_supported_activities"] == 1
    assert status["data_coverage"]["workload_supported_activities"] == 1
    assert status["effective_heat_minutes"] == 60.0
