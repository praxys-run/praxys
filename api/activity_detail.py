"""Owner-scoped, observation-only activity detail for the two clients."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from analysis.config import load_config_from_db
from analysis.data_loader import (
    load_activity_records,
    load_activity_sample_coverage,
)
from api.deps import _build_activities_list
from db.models import ActivitySample, ActivitySplit


MAX_CONTIGUOUS_INTERVAL_SEC = 5
MAX_DISPLAY_POINTS = 6000
MIN_SPLIT_DISPLAY_METERS = 10

METRIC_FIELDS = (
    "power_watts", "hr_bpm", "pace_sec_km", "cadence_spm", "speed_ms",
    "altitude_m", "grade_pct", "temperature_c", "ground_time_ms",
    "oscillation_mm", "vertical_ratio", "leg_spring_kn_m",
    "form_power_watts", "respiration_rate",
)
SIGNED_FIELDS = {"altitude_m", "grade_pct", "temperature_c"}
ZERO_FIELDS = {"power_watts", "form_power_watts", "speed_ms"}
_EXTREMA_KEYS = tuple((field, f"{field}_min", f"{field}_max") for field in METRIC_FIELDS)


def _observed(
    value: float | None, *, allow_zero: bool = False, allow_negative: bool = False,
) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    if (not allow_negative and value < 0) or (value == 0 and not allow_zero and not allow_negative):
        return None
    return round(float(value), 2)


class _DisplaySamples:
    """Retain only bucket endpoints/extrema and per-field continuity state."""

    def __init__(self, sample_count: int) -> None:
        bucket_count = max(1, MAX_DISPLAY_POINTS // (2 + 2 * len(METRIC_FIELDS)))
        self.bucket_size = (
            1 if sample_count <= MAX_DISPLAY_POINTS else math.ceil(sample_count / bucket_count)
        )
        self.segments = dict.fromkeys(METRIC_FIELDS, 0)
        self.last_times: dict[str, int | None] = dict.fromkeys(METRIC_FIELDS)
        self.previous_segments: dict[str, int | None] = dict.fromkeys(METRIC_FIELDS)
        self.candidates: dict[str, tuple[int, dict, dict]] = {}
        self.result: list[dict[str, Any]] = []
        self.count = 0

    def add(self, point: dict[str, Any]) -> None:
        """Consume one point, preserving earliest tied extrema and gap segments."""
        current_segments: dict[str, int | None] = {}
        for field in METRIC_FIELDS:
            if point.get(field) is None:
                current_segments[field] = None
                self.last_times[field] = None
            else:
                last_time = self.last_times[field]
                if last_time is None or point["offset_sec"] - last_time > MAX_CONTIGUOUS_INTERVAL_SEC:
                    self.segments[field] += 1
                current_segments[field] = self.segments[field]
                self.last_times[field] = point["offset_sec"]
        candidate = (self.count, point, current_segments)
        self.candidates.setdefault("first", candidate)
        self.candidates["last"] = candidate
        for field, minimum_key, maximum_key in _EXTREMA_KEYS:
            value = point.get(field)
            if value is None:
                continue
            minimum = self.candidates.get(minimum_key)
            maximum = self.candidates.get(maximum_key)
            if minimum is None or value < minimum[1][field]:
                self.candidates[minimum_key] = candidate
            if maximum is None or value > maximum[1][field]:
                self.candidates[maximum_key] = candidate
        self.count += 1
        if self.count % self.bucket_size == 0:
            self.flush()

    def flush(self) -> None:
        """Append this bucket's ordered unique candidates to the bounded output."""
        retained = {candidate[0]: candidate for candidate in self.candidates.values()}
        for index in sorted(retained):
            _, point, segments = retained[index]
            point = point.copy()
            for field in METRIC_FIELDS:
                point[f"{field}_break"] = (
                    segments[field] is not None
                    and segments[field] != self.previous_segments[field]
                )
            self.result.append(point)
            self.previous_segments = segments
        self.candidates.clear()


def _select_display_samples(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    display = _DisplaySamples(len(points))
    for point in points:
        display.add(point)
    display.flush()
    return display.result


def _kilometer_splits(
    rows: list[Any],
    *,
    start_epoch: int | None,
    verified_start: bool,
    distance_km: float | None,
    duration_sec: float | None,
) -> tuple[list[dict[str, Any]], str | None]:
    kilometers = _KilometerSplits(start_epoch, verified_start, distance_km, duration_sec)
    for row in rows:
        kilometers.add(row.t_sec, row.distance_m)
    return kilometers.finish()


class _KilometerSplits:
    """Validate the entire stream, retaining only split endpoints and output."""

    def __init__(
        self, start_epoch: int | None, verified_start: bool,
        distance_km: float | None, duration_sec: float | None,
    ) -> None:
        self.start_epoch = start_epoch
        self.verified_start = verified_start
        self.distance_km = distance_km
        self.duration_sec = duration_sec
        self.first: tuple[int, float | None] | None = None
        self.last: tuple[int, float | None] | None = None
        self.start: tuple[int, float | None] | None = None
        self.last_split_start: tuple[int, float | None] | None = None
        self.any_distance = False
        self.missing_distance = False
        self.time_gap = False
        self.non_monotonic = False
        self.distance_jump = False
        self.threshold = 1000
        self.splits: list[dict[str, Any]] = []

    def add(self, timestamp: int, raw_distance: float | None) -> None:
        """Accumulate validation facts and candidate split endpoints in order."""
        distance = _observed(raw_distance, allow_zero=True)
        endpoint = (timestamp, distance)
        self.any_distance |= distance is not None
        self.missing_distance |= distance is None
        if self.first is None:
            self.first = self.start = endpoint
        if self.last is not None:
            interval = timestamp - self.last[0]
            self.time_gap |= interval > MAX_CONTIGUOUS_INTERVAL_SEC
            if distance is not None and self.last[1] is not None:
                self.non_monotonic |= distance < self.last[1]
                self.distance_jump |= distance - self.last[1] > 20 * interval + 20
            if (not (self.missing_distance or self.time_gap or self.non_monotonic or self.distance_jump)
                    and self.start_epoch is not None and distance >= self.threshold):
                self.last_split_start = self.start
                self.splits.append(_kilometer_row(
                    self.start, endpoint, self.start_epoch, len(self.splits) + 1,
                ))
                self.start = endpoint
                self.threshold = (distance // 1000 + 1) * 1000
        self.last = endpoint

    def finish(self) -> tuple[list[dict[str, Any]], str | None]:
        """Apply the original rejection precedence before returning any splits."""
        if self.first is None:
            return [], "samples_unavailable"
        if not self.any_distance:
            return [], "distance_trace_unavailable"
        if self.missing_distance:
            return [], "distance_trace_incomplete"
        if not self.verified_start or self.start_epoch is None:
            return [], "start_time_unverified"
        duration = self.duration_sec
        if duration is None or duration <= 0:
            return [], "duration_alignment_unverified"
        if (abs(self.first[0] - self.start_epoch) > MAX_CONTIGUOUS_INTERVAL_SEC
                or abs(self.last[0] - self.start_epoch - duration) > max(10, duration * .01)):
            return [], "duration_alignment_unverified"
        if self.time_gap:
            return [], "distance_trace_incomplete"
        if self.non_monotonic:
            return [], "distance_trace_non_monotonic"
        if self.distance_jump or self.first[1] > 25 or self.last[1] <= 0:
            return [], "distance_trace_incomplete"
        if self.distance_km is None or self.distance_km <= 0 or abs(
            self.last[1] - self.distance_km * 1000
        ) > max(50, self.distance_km * 20):
            return [], "activity_distance_mismatch"
        remaining_meters = self.last[1] - self.start[1]
        if remaining_meters >= MIN_SPLIT_DISPLAY_METERS:
            self.splits.append(_kilometer_row(
                self.start, self.last, self.start_epoch, len(self.splits) + 1,
            ))
        elif remaining_meters > 0:
            if not self.splits:
                return [], "distance_below_display_precision"
            self.splits[-1] = _kilometer_row(
                self.last_split_start, self.last, self.start_epoch, len(self.splits),
            )
        return self.splits, None


def _kilometer_row(
    start: tuple[int, float], end: tuple[int, float],
    start_epoch: int, number: int,
) -> dict[str, Any]:
    distance = (end[1] - start[1]) / 1000
    duration = end[0] - start[0]
    return {
        "split_num": number,
        "start_offset_sec": start[0] - start_epoch,
        "end_offset_sec": end[0] - start_epoch,
        "distance_km": round(distance, 2),
        "duration_sec": duration,
        "pace_sec_km": round(duration / distance, 1) if distance > 0 else None,
    }


def get_activity_detail(user_id: str, db: Session, activity_id: str) -> dict | None:
    activities = load_activity_records(user_id, db, [activity_id])
    if activities.empty:
        return None

    splits = db.query(ActivitySplit).filter(
        ActivitySplit.user_id == user_id,
        ActivitySplit.activity_id == activity_id,
    ).order_by(ActivitySplit.split_num).all()
    split_frame = pd.DataFrame([{
        field: getattr(split, field) for field in (
            "activity_id", "split_num", "distance_km", "duration_sec",
            "avg_power", "power_source", "avg_hr", "max_hr",
            "avg_pace_min_km",
        )
    } for split in splits])
    coverage = load_activity_sample_coverage(
        user_id, db, [activity_id],
        max_interval_sec=MAX_CONTIGUOUS_INTERVAL_SEC,
    )
    activity = _build_activities_list(activities, split_frame, coverage)[0]
    rows = db.query(
        ActivitySample.t_sec, ActivitySample.source,
        *(getattr(ActivitySample, field) for field in METRIC_FIELDS),
        ActivitySample.distance_m,
        func.count().over().label("sample_count"),
    ).filter(
        ActivitySample.user_id == user_id,
        ActivitySample.activity_id == activity_id,
    ).order_by(ActivitySample.t_sec).yield_per(512)

    start_time = activity["start_time"]
    verified_start = start_time["provenance"] in (
        "activity_start_epoch", "activity_start_with_offset",
    )
    start_epoch = (
        int(datetime.fromisoformat(start_time["utc"]).timestamp())
        if start_time["utc"] is not None else None
    )
    origin_epoch = None
    sample_count = 0
    sample_sources: set[str] = set()
    display = _DisplaySamples(0)
    kilometer_stream = _KilometerSplits(
        start_epoch, verified_start, activity["distance_km"], activity["duration_sec"],
    )
    for row in rows:
        if origin_epoch is None:
            origin_epoch = (
                start_epoch if start_epoch is not None and start_epoch <= row.t_sec else row.t_sec
            )
            sample_count = row.sample_count
            display = _DisplaySamples(sample_count)
        if row.source:
            sample_sources.add(str(row.source))
        display.add({
            "offset_sec": row.t_sec - origin_epoch,
            "source": row.source,
            **{
                field: _observed(
                    getattr(row, field),
                    allow_zero=field in ZERO_FIELDS,
                    allow_negative=field in SIGNED_FIELDS,
                )
                for field in METRIC_FIELDS
            },
        })
        kilometer_stream.add(row.t_sec, row.distance_m)
    display.flush()
    kilometers, kilometer_reason = kilometer_stream.finish()
    return {
        "activity": activity,
        "training_base": load_config_from_db(user_id, db).training_base,
        "samples": display.result,
        "sample_count": sample_count,
        "sample_sources": sorted(sample_sources),
        "time_origin": (
            "none" if origin_epoch is None else
            "activity_start" if origin_epoch == start_epoch and verified_start else
            "sample_start"
        ),
        "kilometer_splits": kilometers,
        "kilometer_unavailable_reason": kilometer_reason,
        "privacy": {"gps_included": False, "raw_distance_trace_included": False},
    }
