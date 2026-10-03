"""Pure, versioned post-run DFA α1. No provider, persistence or policy activation.

The exact method/guardrails are recorded in activity-dfa-alpha1-implementation.md.
All timestamps here are integer Unix milliseconds; RR values remain native ms.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
import hashlib
import json
import math
from statistics import median
from typing import Callable, Iterable

import numpy as np

METHOD_VERSION = "dfa-alpha1-raw120-v1"
STATEMENT_VERSION = "dfa-source-attestation-v1"
SOURCE_VERSION = "ecg-native-attestation-v1"
SDR_ID = "sdr-activity-dfa-alpha1-v1"
# Entire fixed recipe mapping; activation may change signed state, never this math.
POLICY_PARAMETER_DIGEST = "c9db9df13212d152c5a34ff4ddfb8f08ea5cb32dd98d14207ddbd0ef86386438"
WINDOW_MS = 120_000
STEP_MS = 5_000
MIN_BEATS = 200
MIN_SUPPORT_MS = 117_600
MAX_RR = 200_000
MAX_ELAPSED_MS = 48 * 3_600_000
FIT_UNIX_OFFSET_MS = 631_065_600_000
GARMIN_ECG = {
    1743: "Garmin HRM-Tri / HRM-Swim", 1752: "Garmin HRM-Run",
    2327: "Garmin HRM4-Run", 3299: "Garmin HRM-Dual", 3300: "Garmin HRM-Pro",
    4130: "Garmin HRM-Pro Plus", 4446: "Garmin HRM-Fit", 4606: "Garmin HRM-200",
}


class DFAError(ValueError):
    """Closed diagnostic code, never a FIT payload or device identifier."""


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


@dataclass
class Packet:
    frame: int
    values: list[int]
    a: int
    b: int
    broken_before: bool = False
    chain: int = -1
    cumulative: int = 0
    first_index: int = 0


@dataclass
class Block:
    start: int
    end: int
    packets: list[Packet] = field(default_factory=list)


@dataclass
class Recording:
    blocks: list[Block]
    sensors: list[dict]
    evidence_digest: str
    rr_count: int
    frame_count: int

    def preparation(self) -> dict:
        return {"sensors": self.sensors, "evidence_digest": self.evidence_digest,
                "statement_version": STATEMENT_VERSION, "rr_count": self.rr_count,
                "frame_count": self.frame_count, "time_alignment": "estimated"}


def sensor_evidence(messages: list[dict]) -> tuple[list[dict], str]:
    """Only native exact ECG identities; no serial/address is retained."""
    sensors: dict[str, dict] = {}
    seen: dict[int, tuple] = {}
    model_names: dict[int, set[str]] = {}
    for entry in messages:
        d = entry["values"]
        if entry["message"] != 23:
            continue
        manufacturer, product = d.get("manufacturer"), d.get("product")
        name = str(d.get("product_name") or "").strip(" \t\n\r\v\f").lower()
        # Polar's native H10 spelling variants identify one model; other native
        # names on the same recording-local handle are conflicting evidence.
        if name in {"h10", "polar h10"}:
            name = "h10"
        index = d.get("device_index")
        identity = (manufacturer, product, name)
        if isinstance(index, int):
            old = seen.get(index, (None, None, ""))
            names = model_names.setdefault(index, set())
            if name:
                names.add(name)
            for position in (0, 1):
                if old[position] is not None and identity[position] is not None and old[position] != identity[position]:
                    raise DFAError("source_contradiction")
            effective_manufacturer = manufacturer if manufacturer is not None else old[0]
            # Manufacturer may arrive after several partial descriptors. Keep
            # all nonempty native model names so delayed provenance cannot
            # erase an earlier optical/ECG identity contradiction.
            if effective_manufacturer == 123 and len(names) > 1:
                raise DFAError("source_contradiction")
            manufacturer, product, name = tuple(new if new not in (None, "") else prior
                                                for new, prior in zip(identity, old))
            seen[index] = (manufacturer, product, name)
        label = GARMIN_ECG.get(product) if manufacturer == 1 else None
        rule: object = [SOURCE_VERSION, manufacturer, product]
        if manufacturer == 123 and name in {"h10", "polar h10"}:
            label, rule = "Polar H10", [SOURCE_VERSION, 123, "h10"]
        if label:
            # Index if present is a recording-local handle, never an ANT serial.
            ref = digest([index if index is not None else entry["frame"], rule])[:32]
            sensors[ref] = {"sensor_ref": ref, "label": label, "rule_fingerprint": digest(rule)}
    result = sorted(sensors.values(), key=lambda v: v["sensor_ref"])
    return result, digest([SOURCE_VERSION, result])


def build_recording(messages: list[dict], frame_count: int = 0,
                    check: Callable[[], None] = lambda: None) -> Recording:
    """Turn a selective ordered FIT projection into bounded timing/QC input."""
    sessions = [m for m in messages if m["message"] == 18]
    if len(sessions) != 1 or sessions[0]["values"].get("sport") != 1:
        raise DFAError("activity_type_unsupported")
    if any(m["values"].get("sport", 1) != 1 for m in messages if m["message"] == 12):
        raise DFAError("activity_type_unsupported")
    # Keep the genuine v1 sensor/evidence representation, but enforce current
    # complete native integrity before either branch can prepare or compute.
    from analysis.dfa_source import require_native_integrity
    require_native_integrity(messages)
    sensors, evidence = sensor_evidence(messages)
    blocks: list[Block] = []
    current: Block | None = None
    pending: list[tuple[int, list[int], bool, int]] = []
    anchor = 0
    chain_break = False
    rr_count = 0
    original_index = 0

    def flush(timestamp: int) -> None:
        nonlocal chain_break
        if current is not None:
            for frame, values, broken, index in pending:
                if 0 <= timestamp - anchor <= 30_000:
                    current.packets.append(Packet(frame, values, anchor, timestamp,
                                                  broken, first_index=index))
                else:
                    chain_break = True
        pending.clear()

    for entry in messages:
        check()
        number, d = entry["message"], entry["values"]
        packet_index = original_index
        if number == 78:
            raw_values = d.get("time", [])
            if not isinstance(raw_values, (list, tuple)):
                raw_values = [raw_values]
            raw_values = list(raw_values)
            while raw_values and raw_values[-1] in (None, 0xFFFF):
                raw_values.pop()
            original_index += len(raw_values)
            if original_index > MAX_RR:
                raise DFAError("rr_limit")
        raw_ts = d.get("timestamp")
        timestamp = (raw_ts * 1000 + FIT_UNIX_OFFSET_MS
                     if isinstance(raw_ts, int) and raw_ts >= 0 else None)
        if number == 21 and d.get("event") == 0 and d.get("event_group", 0) in (0, None):
            if timestamp is None:
                raise DFAError("timer_invalid")
            kind = d.get("event_type")
            if kind == 0:
                if current is not None or (blocks and timestamp < blocks[-1].end):
                    raise DFAError("timer_invalid")
                current = Block(timestamp, timestamp)
                anchor = timestamp
                chain_break = True
            elif kind in (1, 4, 8, 9):
                if current is None or timestamp <= current.start or timestamp < anchor:
                    raise DFAError("timer_invalid")
                flush(timestamp)
                current.end = timestamp
                blocks.append(current)
                current = None
            else:
                raise DFAError("timer_invalid")
        elif number == 20 and current is not None and timestamp is not None:
            if timestamp < anchor:
                pending.clear()
                chain_break = True
            else:
                flush(timestamp)
            anchor = timestamp
        elif number == 78 and current is not None:
            values = d.get("time", [])
            if not isinstance(values, (list, tuple)):
                values = [values]
            values = list(values)
            while values and values[-1] in (None, 0xFFFF):
                values.pop()
            if not values:
                continue
            if any(not isinstance(v, int) or isinstance(v, bool) or v <= 0 or v >= 0xFFFF for v in values):
                # Earlier queued packets remain valid but the next packet starts
                # a new chain. Preserve the discontinuity even before next anchor.
                chain_break = True
                pending.append((entry["frame"], [], True, packet_index))
                continue
            rr_count += len(values)
            if rr_count > MAX_RR:
                raise DFAError("rr_limit")
            pending.append((entry["frame"], values, chain_break, packet_index))
            chain_break = False
    if current is not None or not blocks:
        raise DFAError("timer_invalid")
    if blocks[-1].end - blocks[0].start > MAX_ELAPSED_MS:
        raise DFAError("elapsed_limit")
    if not rr_count:
        raise DFAError("rr_missing")
    if not sensors:
        raise DFAError("source_unsupported")
    chain = -1
    for block in blocks:
        cumulative = 0
        previous: tuple[int, int] | None = None
        chain += 1
        retained = []
        broken = False
        for p in block.packets:
            if not p.values:
                broken = True
                continue
            prospective = cumulative + sum(p.values)
            offset_range = (p.a - prospective, p.b - prospective)
            distance = (max(0, offset_range[0] - previous[1], previous[0] - offset_range[1])
                        if previous else 0)
            if broken or p.broken_before or distance > 2000:
                chain += 1
                cumulative = 0
            cumulative += sum(p.values)
            p.chain, p.cumulative = chain, cumulative
            previous = (p.a - cumulative, p.b - cumulative)
            retained.append(p)
            broken = False
        block.packets = retained
    return Recording(blocks, sensors, evidence, rr_count, frame_count)


def dfa_alpha1(rr: Iterable[float]) -> tuple[float, float | None]:
    """Double-direction non-overlapping DFA, linear detrending, integer4..16."""
    values = np.asarray(list(rr), dtype=np.float64)
    if len(values) < 16 or not np.isfinite(values).all():
        raise DFAError("numerical_invalid")
    y = np.cumsum(values - values.mean())
    fluctuations = []
    for n in range(4, 17):
        q = len(y) // n
        boxes = np.concatenate((y[:q*n].reshape(q, n), y[len(y)-q*n:].reshape(q, n)))
        x = np.arange(n, dtype=np.float64)
        x -= x.mean()
        centered = boxes - boxes.mean(axis=1, keepdims=True)
        slope = (centered @ x) / (x @ x)
        residual = centered - slope[:, None] * x
        f = float(np.sqrt(np.mean(residual * residual)))
        if not math.isfinite(f) or f <= 1e-12:
            raise DFAError("numerical_invalid")
        fluctuations.append(f)
    x, y = np.log(np.arange(4, 17, dtype=np.float64)), np.log(fluctuations)
    xc, yc = x - x.mean(), y - y.mean()
    alpha = float((xc @ yc) / (xc @ xc))
    variance = float(yc @ yc)
    r2 = max(0., min(1., 1. - float(np.sum((yc - alpha*xc)**2)) / variance)) if variance else None
    if not math.isfinite(alpha):
        raise DFAError("numerical_invalid")
    return alpha, r2


def qc_reasons(values: list[int]) -> list[str | None]:
    usable = [i for i, value in enumerate(values) if 250 <= value <= 2000]
    results = []
    for i, value in enumerate(values):
        if not 250 <= value <= 2000:
            results.append("rr_out_of_range")
            continue
        before, after = bisect_left(usable, i), bisect_right(usable, i)
        neighbors = usable[max(0, before-5):before] + usable[after:after+5]
        if len(neighbors) < 5:
            results.append("qc_incomplete")
        else:
            center = median(values[j] for j in neighbors)
            results.append("rr_suspect" if abs(value-center)/center > .20 else None)
    return results


def union_support(intervals: Iterable[tuple[float, float]]) -> list[list[float]]:
    result: list[list[float]] = []
    for start, end in sorted(intervals):
        if result and start <= result[-1][1]:
            result[-1][1] = max(end, result[-1][1])
        else:
            result.append([start, end])
    return result


def compute(recording: Recording, check: Callable[[], None] = lambda: None, *, source_assurance: str = "user_confirmed") -> dict:
    """Preserve every scheduled window, including failed alignment/QC windows."""
    if source_assurance not in ("user_confirmed", "metadata_inferred"):
        raise DFAError("source_contradiction")
    chains: dict[int, dict] = {}
    for block in recording.blocks:
        for p in block.packets:
            chain = chains.setdefault(p.chain, {"values": [], "indices": [], "packet_frames": []})
            chain["values"].extend(p.values)
            chain["packet_frames"].extend([p.frame] * len(p.values))
            chain["indices"].extend(range(p.first_index, p.first_index + len(p.values)))
    for chain in chains.values():
        check()
        chain["ends"] = np.cumsum(chain["values"]).tolist()
        chain["starts"] = [0] + chain["ends"][:-1]
        chain["qc"] = qc_reasons(chain["values"])
    windows, support = [], []
    for block_id, block in enumerate(recording.blocks):
        for end in range(block.start + WINDOW_MS, block.end + 1, STEP_MS):
            check()
            start = end - WINDOW_MS
            window = {"index": len(windows), "block": block_id, "start_ms": start,
                      "end_ms": end, "alpha1": None, "r2": None, "hr_bpm": None,
                      "reasons": [], "flags": [], "beat_count": 0, "coverage_ms": 0,
                      "offset_ms": None, "offset_width_ms": None, "rr_index_start": None,
                      "rr_index_end": None}
            windows.append(window)
            packets = [p for p in block.packets if p.b >= start and p.a <= end]
            if not packets:
                window["reasons"] = ["alignment_missing"]
                continue
            if len({p.chain for p in packets}) != 1:
                window["reasons"] = ["rr_discontinuity"]
                continue
            low = max(p.a-p.cumulative-1000 for p in packets)
            high = min(p.b-p.cumulative+1000 for p in packets)
            if low > high or high-low > 5000:
                window["reasons"] = ["alignment_inconsistent" if low > high else "alignment_uncertain"]
                continue
            offset = min(high, max(low, median((p.a+p.b)/2-p.cumulative for p in packets)))
            chain = chains[packets[0].chain]
            first = bisect_left(chain["starts"], start-offset)
            last = bisect_right(chain["ends"], end-offset)
            gathered_frames = {p.frame for p in packets}
            selected = [i for i in range(first, last) if chain["packet_frames"][i] in gathered_frames]
            values = [chain["values"][i] for i in selected]
            window.update(offset_ms=offset, offset_width_ms=high-low,
                          beat_count=len(values), coverage_ms=sum(values))
            if values:
                window.update(rr_index_start=chain["indices"][selected[0]], rr_index_end=chain["indices"][selected[-1]])
            reasons = sorted({chain["qc"][i] for i in selected if chain["qc"][i]})
            if len(values) < MIN_BEATS:
                reasons.append("insufficient_beats")
            if sum(values) < MIN_SUPPORT_MS:
                reasons.append("insufficient_coverage")
            if reasons:
                window["reasons"] = reasons
                continue
            try:
                alpha, r2 = dfa_alpha1(values)
            except DFAError as exc:
                window["reasons"] = [str(exc)]
                continue
            window.update(alpha1=alpha, r2=r2, hr_bpm=60000/(sum(values)/len(values)))
            if alpha < 0 or alpha > 2:
                window["flags"].append("atypical_value")
            # Coalesce only adjacent selected intervals. Do not allocate one
            # support tuple per beat per overlapping window or bridge exclusions.
            segment = previous = selected[0]
            for i in selected[1:]:
                if i != previous + 1:
                    support.append((chain["starts"][segment]+offset, chain["ends"][previous]+offset))
                    segment = i
                previous = i
            support.append((chain["starts"][segment]+offset, chain["ends"][previous]+offset))
    union = union_support(support)
    valid = sum(w["alpha1"] is not None for w in windows)
    timer = sum(b.end-b.start for b in recording.blocks)
    reasons: dict[str, int] = {}
    for window in windows:
        for reason in window["reasons"]:
            reasons[reason] = reasons.get(reason, 0) + 1
    return {"method_version": METHOD_VERSION, "source_assurance": source_assurance,
            "time_alignment": "estimated", "availability": "available" if valid else "no_valid_windows",
            "summary": {"scheduled_windows": len(windows), "valid_windows": valid,
                        "window_success_rate": valid/len(windows) if windows else None,
                        "supported_time_ratio": sum(b-a for a, b in union)/timer if timer else None,
                        "short_blocks": sum(b.end-b.start < WINDOW_MS for b in recording.blocks),
                        "excluded_reasons": reasons},
            "navigation": {"start_ms": recording.blocks[0].start, "end_ms": recording.blocks[-1].end,
                           "timer_blocks": [[b.start, b.end] for b in recording.blocks],
                           "support": union, "page_size": 120,
                           "page_anchors": [{"offset": w["index"], "time_ms": w["end_ms"]} for w in windows[::120]]},
            "windows": windows}


def overlay(windows: list[dict], samples: list[dict]) -> list[dict]:
    """Time-weighted overlays on Unix time, with independent 80% support gates."""
    ordered = sorted(samples, key=lambda s: s["t_sec"])
    times = [s["t_sec"] * 1000 for s in ordered]
    result = []
    for window in windows:
        values = {"index": window["index"], "power_watts": None, "pace_sec_km": None}
        first = max(0, bisect_left(times, window["start_ms"]) - 1)
        last = bisect_left(times, window["end_ms"])
        for field, target in (("power_watts", "power_watts"), ("speed_ms", "pace_sec_km")):
            total = duration = 0.
            for i in range(first, last):
                v = ordered[i].get(field)
                if not isinstance(v, (float, int)) or not math.isfinite(v) or v < 0:
                    continue
                stop = min(times[i]+2000, times[i+1] if i+1 < len(times) else times[i]+2000, window["end_ms"])
                dt = max(0, stop-max(times[i], window["start_ms"]))
                total += v*dt
                duration += dt
            if duration >= 96000:
                mean = total/duration
                values[target] = mean if field == "power_watts" else (1000/mean if mean > 0 else None)
        result.append(values)
    return result
