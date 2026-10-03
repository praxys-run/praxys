"""Owner-exact raw RR reader over retained archives, independent of watch model."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import io
from typing import Callable, Iterator

import fitdecode
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from analysis.activity_dfa import DFAError, MAX_RR
from db.models import Activity, GarminFitSnapshot as Snapshot, GarminFitParse as Parse

MAX_FIT_BYTES = 64 * 1024 * 1024
MAX_FRAMES = 250_000
READ_TIMEOUT_SECONDS = 30
# FIT global message/field IDs and native base types, independent of rendered
# profile/subfield/developer names. Tuple: normalized name, base ID, scalar bytes.
NATIVE_FIELDS = {
    12: {0: ("sport", 0, 1), 1: ("sub_sport", 0, 1)},
    18: {5: ("sport", 0, 1), 6: ("sub_sport", 0, 1), 253: ("timestamp", 134, 4)},
    20: {253: ("timestamp", 134, 4)},
    21: {0: ("event", 0, 1), 1: ("event_type", 0, 1),
         4: ("event_group", 2, 1), 253: ("timestamp", 134, 4)},
    23: {0: ("device_index", 2, 1), 1: ("device_type", 2, 1), 25: ("source_type", 0, 1), 2: ("manufacturer", 132, 2),
         4: ("product", 132, 2), 27: ("product_name", 7, None)},
    78: {0: ("time", 132, None)},
}
NATIVE_MESSAGES = set(NATIVE_FIELDS)


def _validate_definition(frame) -> None:
    fields = NATIVE_FIELDS[frame.global_mesg_num]
    seen: set[int] = set()
    for field in frame.field_defs:
        if field.def_num not in fields or (frame.global_mesg_num == 23 and field.def_num in (1,25)):
            # New inventory diagnostics do not tighten the v1 numerical reader.
            # Ambiguous/malformed diagnostics are omitted below, forcing v2 to
            # unresolved while leaving existing genuine manual proof unchanged.
            continue
        _, base_type, scalar_size = fields[field.def_num]
        if field.def_num in seen or field.base_type.identifier != base_type:
            raise DFAError("fit_invalid")
        seen.add(field.def_num)
        if scalar_size is not None:
            valid_size = field.size == scalar_size
        elif frame.global_mesg_num == 78:
            valid_size = field.size >= 2 and field.size % 2 == 0
        else:
            valid_size = field.size >= 1  # native string, not a numeric array
        if not valid_size:
            raise DFAError("fit_invalid")


def _native_values(frame) -> dict:
    fields = NATIVE_FIELDS[frame.global_mesg_num]
    values = {}
    for field in frame.fields:
        definition = field.field_def
        if definition is None:
            # This is the parser's native compressed record-header timestamp,
            # not a developer or profile component expansion.
            if (frame.time_offset is not None and 253 in fields
                    and field.field is fitdecode.profile.FIELD_TYPE_TIMESTAMP
                    and field.base_type.identifier == 134):
                values["timestamp"] = field.raw_value
            continue
        if definition.is_dev or definition.def_num not in fields:
            continue
        name, base_type, scalar_size = fields[definition.def_num]
        if frame.global_mesg_num == 23 and definition.def_num in (1,25):
            native_defs=[f for f in frame.def_mesg.field_defs if f.def_num==definition.def_num]
            if len(native_defs)!=1 or definition.base_type.identifier!=base_type or definition.size!=scalar_size:
                continue
        values[name] = field.raw_value
    return values


# Native session.sport remains authoritative for new/unknown running subtypes.
# Stored metadata only excludes positively known contradictions.
NON_RUNNING_TYPES = {"cycling", "road_biking", "mountain_biking", "indoor_cycling",
                     "swimming", "lap_swimming", "open_water_swimming", "walking",
                     "hiking", "strength_training", "yoga", "rowing", "multisport",
                     "triathlon"}


@dataclass(frozen=True)
class RecordingRef:
    provider: str
    user_id: str
    account_id: str
    activity_id: str
    snapshot_id: str
    parse_id: str
    sha256: str
    parser_version: str

    def as_dict(self) -> dict:
        return asdict(self)


class RRRecordingReader:
    def __init__(self, db: Session):
        self.db = db

    def list_inputs(self, owner: str, activity_id: str) -> list[dict]:
        read_timeout(self.db)
        activity = self.db.query(Activity).filter_by(user_id=owner, activity_id=activity_id).first()
        if activity is None:
            raise DFAError("activity_not_found")
        if activity.source != "garmin":
            return []
        if activity.activity_type in NON_RUNNING_TYPES:
            raise DFAError("activity_type_unsupported")
        rows = self.db.query(Snapshot.id, Snapshot.account_id, Snapshot.sha256, Snapshot.created_at,
                             Parse.id.label("parse_id"), Parse.parser_version).join(
            Parse, (Parse.id == Snapshot.active_parse_id) & (Parse.snapshot_id == Snapshot.id)
            & (Parse.user_id == Snapshot.user_id)).filter(
            Snapshot.user_id == owner, Snapshot.activity_id == activity_id, Parse.status == "complete"
        ).order_by(Snapshot.created_at, Snapshot.id).all()
        return [{"input": RecordingRef("garmin", owner, r.account_id, activity_id, r.id,
                                       r.parse_id, r.sha256, r.parser_version).as_dict(),
                 "created_at": r.created_at.isoformat()} for r in rows]

    def raw(self, ref: RecordingRef) -> bytes:
        current = [v["input"] for v in self.list_inputs(ref.user_id, ref.activity_id)]
        if ref.as_dict() not in current:
            raise DFAError("input_changed")
        query = self.db.query(Snapshot).filter_by(id=ref.snapshot_id, user_id=ref.user_id,
            account_id=ref.account_id, activity_id=ref.activity_id, sha256=ref.sha256,
            active_parse_id=ref.parse_id)
        size = query.with_entities(func.length(Snapshot.raw_fit)).scalar()
        if size is None:
            raise DFAError("input_changed")
        if size > MAX_FIT_BYTES:
            raise DFAError("fit_too_large")
        raw = query.with_entities(Snapshot.raw_fit).scalar()
        if raw is None or len(raw) > MAX_FIT_BYTES or hashlib.sha256(raw).hexdigest() != ref.sha256:
            raise DFAError("input_integrity_failed")
        return raw

    def iter_recording(self, ref: RecordingRef, check: Callable[[], None] = lambda: None) -> Iterator[dict]:
        yield from decode(self.raw(ref), check)

    def iter_source_metadata(self, ref: RecordingRef, check: Callable[[], None] = lambda: None) -> Iterator[dict]:
        """Exact native device descriptors only; never project RR or samples."""
        yield from _decode(self.raw(ref),check,device_only=True)


def decode(raw: bytes, check: Callable[[], None] = lambda: None) -> Iterator[dict]:
    yield from _decode(raw,check)


def _decode(raw: bytes, check: Callable[[], None], *, device_only: bool = False) -> Iterator[dict]:
    if len(raw) > MAX_FIT_BYTES:
        raise DFAError("fit_too_large")
    try:
        rr_count = 0
        with fitdecode.FitReader(io.BytesIO(raw), processor=None,
                check_crc=fitdecode.CrcCheck.RAISE, error_handling=fitdecode.ErrorHandling.RAISE) as reader:
            for index, frame in enumerate(reader):
                check()
                if index >= MAX_FRAMES:
                    raise DFAError("frame_limit")
                if frame.frame_type == fitdecode.FIT_FRAME_DEFINITION and frame.global_mesg_num in ({23} if device_only else NATIVE_MESSAGES):
                    _validate_definition(frame)
                if frame.frame_type != fitdecode.FIT_FRAME_DATA or frame.global_mesg_num not in ({23} if device_only else NATIVE_MESSAGES):
                    continue
                values = _native_values(frame)
                if frame.global_mesg_num == 78:
                    rr = values.get("time", [])
                    rr = list(rr) if isinstance(rr, (tuple, list)) else [rr]
                    while rr and rr[-1] in (None, 65535):
                        rr.pop()
                    rr_count += len(rr)
                    if rr_count > MAX_RR:
                        raise DFAError("rr_limit")
                yield {"frame": index, "message": frame.global_mesg_num, "values": values}
    except DFAError:
        raise
    except fitdecode.FitError as exc:
        raise DFAError("fit_invalid") from exc


def read_timeout(db: Session) -> None:
    """Bound each current transaction, including reads after a heartbeat commit."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text(f"SET LOCAL statement_timeout = '{READ_TIMEOUT_SECONDS}s'"))
        db.execute(text("SET LOCAL lock_timeout = '30s'"))
