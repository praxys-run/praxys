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
NATIVE_MESSAGES = {12, 18, 20, 21, 23, 78}
NATIVE_FIELDS = {"timestamp", "event", "event_type", "event_group", "sport", "sub_sport",
                 "time", "manufacturer", "product", "product_name", "device_index"}
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


def decode(raw: bytes, check: Callable[[], None] = lambda: None) -> Iterator[dict]:
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
                if frame.frame_type != fitdecode.FIT_FRAME_DATA or frame.global_mesg_num not in NATIVE_MESSAGES:
                    continue
                values = {("product" if frame.global_mesg_num == 23 and f.def_num == 4 else f.name): f.raw_value for f in frame.fields
                          if not f.is_expanded and not (f.field_def and f.field_def.is_dev)
                          and (f.name in NATIVE_FIELDS or (frame.global_mesg_num == 23 and f.def_num == 4))}
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
        db.execute(text("SET LOCAL statement_timeout = '30s'"))
        db.execute(text("SET LOCAL lock_timeout = '30s'"))
