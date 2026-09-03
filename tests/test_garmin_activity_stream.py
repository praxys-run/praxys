"""Tests for parse_activity_stream() in sync/garmin_sync.py."""
import pytest
from sync.garmin_sync import parse_activity_stream, parse_splits


STRYD_CONNECTIQ_APP_IDS = (
    "660a581e-5301-460c-8f2f-034c8b6dc90f",
    "18fb2cf0-1a4b-430d-ad66-988c847421f4",
)


def _make_details(
    n: int = 5,
    start_ms: int = 1_000_000_000_000,
    step_ms: int = 2000,
    include_gps: bool = True,
    include_dynamics: bool = True,
) -> dict:
    """Build a minimal get_activity_details() response with n rows."""
    descriptors = [
        {"metricsIndex": 0, "key": "directTimestamp"},
        {"metricsIndex": 1, "key": "directHeartRate"},
        {"metricsIndex": 2, "key": "directDoubleCadence"},
        {"metricsIndex": 3, "key": "directSpeed"},
        {"metricsIndex": 4, "key": "directElevation"},
        {"metricsIndex": 5, "key": "sumDistance"},
        {"metricsIndex": 6, "key": "directLatitude"},
        {"metricsIndex": 7, "key": "directLongitude"},
        {"metricsIndex": 8, "key": "directGroundContactTime"},
        {"metricsIndex": 9, "key": "directVerticalOscillation"},
        {"metricsIndex": 10, "key": "directVerticalRatio"},
    ]
    rows = []
    for i in range(n):
        ts = start_ms + i * step_ms
        metrics = [
            float(ts),          # 0 directTimestamp (ms)
            150.0 + i,          # 1 directHeartRate
            172.0,              # 2 directDoubleCadence
            3.5,                # 3 directSpeed (m/s)
            50.0 + i * 0.1,    # 4 directElevation
            i * 7.0,            # 5 sumDistance (cumulative m)
            31.18 + i * 0.001 if include_gps else None,  # 6 lat
            121.25 + i * 0.001 if include_gps else None, # 7 lng
            260.0 if include_dynamics else None,          # 8 ground_time
            7.2 if include_dynamics else None,            # 9 oscillation
            6.8 if include_dynamics else None,            # 10 vertical_ratio
        ]
        rows.append({"metrics": metrics})
    return {"metricDescriptors": descriptors, "activityDetailMetrics": rows}


def _add_metric(
    details: dict,
    *,
    key: str,
    values: list[object],
    app_id: str | None = None,
    developer_field_number: int | None = None,
) -> None:
    """Append one descriptor and its values to a synthetic details payload."""
    assert len(values) == len(details["activityDetailMetrics"])
    metrics_index = len(details["activityDetailMetrics"][0]["metrics"])
    descriptor = {"metricsIndex": metrics_index, "key": key}
    if app_id is not None:
        descriptor["appID"] = app_id
    if developer_field_number is not None:
        descriptor["developerFieldNumber"] = developer_field_number
    details["metricDescriptors"].append(descriptor)
    for row, value in zip(details["activityDetailMetrics"], values, strict=True):
        row["metrics"].append(value)


def test_returns_one_sample_per_row():
    """Each activityDetailMetrics row produces one sample."""
    details = _make_details(n=10)
    samples = parse_activity_stream("act-1", details)
    assert len(samples) == 10


def test_timestamp_converted_from_ms_to_sec():
    """directTimestamp (milliseconds) is divided by 1000 for t_sec."""
    details = _make_details(n=1, start_ms=1_777_540_905_000)
    samples = parse_activity_stream("act-2", details)
    assert samples[0]["t_sec"] == 1_777_540_905


def test_two_second_sampling_preserved():
    """2-second step between rows is reflected in consecutive t_sec values."""
    details = _make_details(n=3, start_ms=1_000_000_000_000, step_ms=2000)
    samples = parse_activity_stream("act-3", details)
    assert samples[1]["t_sec"] - samples[0]["t_sec"] == 2
    assert samples[2]["t_sec"] - samples[1]["t_sec"] == 2


def test_core_fields_mapped():
    """hr_bpm, cadence_spm, speed_ms, altitude_m, distance_m populated."""
    details = _make_details(n=1)
    s = parse_activity_stream("act-4", details)[0]
    assert s["source"] == "garmin"
    assert s["activity_id"] == "act-4"
    assert s["hr_bpm"] == 150.0
    assert s["cadence_spm"] == 172.0
    assert s["speed_ms"] == 3.5
    assert s["altitude_m"] == pytest.approx(50.0)
    assert s["distance_m"] == 0.0


def test_gps_fields_populated():
    """lat and lng extracted when directLatitude/directLongitude present."""
    details = _make_details(n=1, include_gps=True)
    s = parse_activity_stream("act-5", details)[0]
    assert s["lat"] == pytest.approx(31.18)
    assert s["lng"] == pytest.approx(121.25)


def test_gps_none_when_missing():
    """lat and lng are None when GPS metrics absent from row."""
    details = _make_details(n=1, include_gps=False)
    s = parse_activity_stream("act-6", details)[0]
    assert s["lat"] is None
    assert s["lng"] is None


def test_dynamics_populated():
    """ground_time_ms, oscillation_mm, vertical_ratio extracted."""
    details = _make_details(n=1, include_dynamics=True)
    s = parse_activity_stream("act-7", details)[0]
    assert s["ground_time_ms"] == 260.0
    assert s["oscillation_mm"] == 7.2
    assert s["vertical_ratio"] == pytest.approx(6.8)


def test_no_power_in_output_without_supported_descriptor():
    """A stream without a supported power descriptor remains power-empty."""
    details = _make_details(n=1)
    s = parse_activity_stream("act-8", details)[0]
    assert s["power_watts"] is None
    assert s["source"] == "garmin"


@pytest.mark.parametrize("app_id", STRYD_CONNECTIQ_APP_IDS)
def test_stryd_connectiq_record_power_is_mapped(app_id):
    """Both observed Stryd apps record watts in developer field 0."""
    details = _make_details(n=3)
    _add_metric(
        details,
        key="connectIQDeveloperField00",
        values=[240, 250, 260],
        app_id=app_id,
        developer_field_number=0,
    )

    samples = parse_activity_stream("stryd-run", details)

    assert [sample["power_watts"] for sample in samples] == [240, 250, 260]
    assert {sample["source"] for sample in samples} == {"stryd"}


@pytest.mark.parametrize(
    ("app_id", "field_number", "value"),
    [
        ("00000000-0000-0000-0000-000000000000", 0, 250),
        (STRYD_CONNECTIQ_APP_IDS[1], 8, 250),
        (STRYD_CONNECTIQ_APP_IDS[1], 0, "not-a-number"),
        (STRYD_CONNECTIQ_APP_IDS[1], 0, "nan"),
    ],
)
def test_unrelated_or_malformed_connectiq_power_is_ignored(
    app_id, field_number, value,
):
    details = _make_details(n=1)
    _add_metric(
        details,
        key="connectIQDeveloperField00",
        values=[value],
        app_id=app_id,
        developer_field_number=field_number,
    )

    sample = parse_activity_stream("untrusted-run", details)[0]

    assert sample["power_watts"] is None
    assert sample["source"] == "garmin"


def test_stream_power_fills_only_laps_without_native_power():
    """Record power is averaged into laps while native lap power stays first."""
    details = _make_details(
        n=4,
        start_ms=1_700_000_000_000,
        step_ms=2000,
    )
    _add_metric(
        details,
        key="connectIQDeveloperField00",
        values=[200, 220, 300, 320],
        app_id=STRYD_CONNECTIQ_APP_IDS[0],
        developer_field_number=0,
    )
    samples = parse_activity_stream("mixed-run", details)
    splits = parse_splits(
        "mixed-run",
        {
            "lapDTOs": [
                {
                    "startTimeGMT": "2023-11-14T22:13:20.0",
                    "duration": 4,
                    "averagePower": 250,
                },
                {
                    "startTimeGMT": "2023-11-14T22:13:24.0",
                    "duration": 4,
                },
            ],
        },
        activity_samples=samples,
    )

    assert splits[0]["avg_power"] == "250"
    assert splits[0]["power_source"] == "garmin"
    assert splits[1]["avg_power"] == "310"
    assert splits[1]["power_source"] == "stryd"


def test_dynamic_descriptor_order():
    """Index mapping is built from metricDescriptors regardless of order."""
    details = _make_details(n=1)
    # Shuffle the descriptor order
    details["metricDescriptors"] = list(reversed(details["metricDescriptors"]))
    # Metrics array order is still by metricsIndex, not descriptor list order
    samples = parse_activity_stream("act-9", details)
    assert len(samples) == 1
    assert samples[0]["hr_bpm"] == 150.0


def test_missing_timestamp_row_skipped():
    """Rows with None timestamp are skipped."""
    details = _make_details(n=3)
    details["activityDetailMetrics"][1]["metrics"][0] = None
    samples = parse_activity_stream("act-10", details)
    assert len(samples) == 2


def test_empty_payload_returns_empty():
    """Missing descriptors or rows returns empty list."""
    assert parse_activity_stream("act-11", {}) == []
    assert parse_activity_stream("act-12", {"metricDescriptors": [], "activityDetailMetrics": []}) == []


def test_missing_directtimestamp_descriptor_returns_empty():
    """Without directTimestamp in descriptors, cannot build samples."""
    details = _make_details(n=3)
    details["metricDescriptors"] = [
        m for m in details["metricDescriptors"] if m["key"] != "directTimestamp"
    ]
    assert parse_activity_stream("act-13", details) == []


def test_truncation_warning_logged(caplog):
    """Warning is logged when metricsCount < totalMetricsCount (response was capped)."""
    import logging
    details = _make_details(n=5)
    details["metricsCount"] = 5
    details["totalMetricsCount"] = 10  # pretend 10 rows exist but only 5 returned
    with caplog.at_level(logging.WARNING, logger="sync.garmin_sync"):
        samples = parse_activity_stream("act-14", details)
    assert len(samples) == 5  # returns what it got
    assert "truncated" in caplog.text
    assert "act-14" in caplog.text


def test_garmin_max_chart_size_covers_ultra_marathon():
    """GARMIN_MAX_CHART_SIZE is large enough for a 100-mile ultra at 2s sampling."""
    from sync.garmin_sync import GARMIN_MAX_CHART_SIZE
    # 100-mile ultra worst case: ~30 hours = 108,000 seconds / 2s = 54,000 rows
    assert GARMIN_MAX_CHART_SIZE >= 54_000
