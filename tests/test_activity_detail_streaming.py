"""Complete-response regressions captured from the pre-streaming implementation."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_activity_analysis_api import analysis_client


SCENARIOS = [
    (0, "regular"), (1, "regular"), (5999, "regular"), (6000, "regular"),
    (6001, "regular"), (12013, "regular"), (12013, "gaps"),
    (6001, "invalid_ranges"), (602, "tiny_tail"), (6001, "unverified"),
    (6001, "missing_distance"), (6001, "non_monotonic"),
]


def seed_stream_case(preview, count, variant):
    from db import session as db_session
    from db.models import Activity, ActivitySample
    from api.activity_detail import METRIC_FIELDS

    epoch = 1784095200
    duration = max(count - 1, 1) + (7 if variant == "gaps" else 0)
    distance = 2.002 if variant == "tiny_tail" else max(count - 1, 1) * 2 / 1000
    with db_session.SessionLocal() as db:
        db.add(Activity(
            user_id=preview["owner_id"], activity_id="stream-regression",
            date=preview["target_date"], source="garmin", activity_type="running",
            start_time=None if variant == "unverified" else "2026-07-15T06:00:00Z",
            distance_km=distance, duration_sec=duration, avg_power=240, avg_hr=150,
        ))
        for start in range(0, count, 512):
            rows = []
            for second in range(start, min(start + 512, count)):
                readings = {
                    field: float((second // 3 + field_index * 7) % 97 + 1)
                    for field_index, field in enumerate(METRIC_FIELDS)
                }
                if variant in ("gaps", "invalid_ranges"):
                    if 510 <= second <= 514 or second % 61 == 0:
                        readings["hr_bpm"] = None
                    if second % 31 == 0:
                        readings["power_watts"] = None
                    if variant == "invalid_ranges":
                        readings["speed_ms"] = [0, -1, float("inf"), 3][second % 4]
                        readings["grade_pct"] = [-5, 0, 7, float("nan")][second % 4]
                        readings["cadence_spm"] = [0, -2, float("inf"), 170][second % 4]
                meters = second * 2
                if variant == "tiny_tail":
                    meters = second * 2000 / 600 if second <= 600 else 2002
                if variant == "missing_distance" and second == 512:
                    meters = None
                if variant == "non_monotonic" and second == 512:
                    meters = 1000
                rows.append({
                    "user_id": preview["owner_id"], "activity_id": "stream-regression",
                    "source": "garmin" if second % 5 else "stryd",
                    "t_sec": epoch + second + (7 if variant == "gaps" and second >= 512 else 0),
                    "distance_m": meters, **readings,
                })
            db.execute(ActivitySample.__table__.insert(), rows)
        db.commit()


def response_digest(detail):
    return hashlib.sha256(json.dumps(detail, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@pytest.mark.parametrize("count,variant", SCENARIOS)
def test_complete_response_matches_pre_streaming_baseline(analysis_client, count, variant):
    from api.activity_detail import get_activity_detail
    from db import session as db_session
    from sqlalchemy import event

    seed_stream_case(analysis_client, count, variant)
    statements = []

    def capture_query(connection, cursor, statement, parameters, context, executemany):
        if "sample_count" in statement and "OVER ()" in statement:
            statements.append((statement, parameters, context.execution_options))

    event.listen(db_session.engine, "before_cursor_execute", capture_query)
    try:
        with db_session.SessionLocal() as db:
            detail = get_activity_detail(analysis_client["owner_id"], db, "stream-regression")
    finally:
        event.remove(db_session.engine, "before_cursor_execute", capture_query)
    expected = json.loads((Path(__file__).parent / "fixtures/activity-detail/streaming/baseline.json").read_text())
    assert response_digest(detail) == expected[f"{count}-{variant}"]
    assert detail["sample_count"] == count
    assert len(detail["samples"]) <= 6000
    assert len(statements) == 1
    statement, parameters, options = statements[0]
    assert "activity_samples.user_id =" in statement
    assert analysis_client["owner_id"] in parameters
    assert options["yield_per"] == 512
    assert options["stream_results"] is True


@pytest.mark.parametrize("distances,times,overrides,reason", [
    ([], [], {}, "samples_unavailable"),
    ([None, None], [0, 20], {"verified_start": False}, "distance_trace_unavailable"),
    ([0, None], [0, 20], {"verified_start": False}, "distance_trace_incomplete"),
    ([0, 2], [0, 20], {"verified_start": False}, "start_time_unverified"),
    ([0, 2], [0, 20], {"duration_sec": 0}, "duration_alignment_unverified"),
    ([0, 20, 10], [0, 1, 20], {"duration_sec": 1}, "duration_alignment_unverified"),
    ([0, 20, 10], [0, 1, 20], {}, "distance_trace_incomplete"),
    ([0, 200, 10], [0, 1, 2], {}, "distance_trace_non_monotonic"),
    ([0, 200], [0, 1], {}, "distance_trace_incomplete"),
    ([30, 32], [0, 1], {}, "distance_trace_incomplete"),
    ([0, 0], [0, 1], {}, "distance_trace_incomplete"),
    ([0, 20], [0, 1], {"distance_km": 2}, "activity_distance_mismatch"),
    ([0, 2], [0, 1], {}, "distance_below_display_precision"),
])
def test_kilometer_reason_precedence(distances, times, overrides, reason):
    from api.activity_detail import _kilometer_splits

    options = dict(start_epoch=0, verified_start=True, distance_km=.02, duration_sec=times[-1] if times else 1)
    options.update(overrides)
    rows = [SimpleNamespace(t_sec=timestamp, distance_m=distance) for timestamp, distance in zip(times, distances)]
    assert _kilometer_splits(rows, **options) == ([], reason)
