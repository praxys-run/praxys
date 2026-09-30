"""Lossless FIT archive projection. No metric here changes training analysis."""
from __future__ import annotations

import base64
import io
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from typing import Any, Iterator

import fitdecode

PARSER_VERSION = "fitdecode-0.11.0/praxys-1"
MAPPING_VERSION = "stryd-1"
MAX_ORIGINAL_BYTES = 64 * 1024 * 1024
MAX_FIT_BYTES = 64 * 1024 * 1024
MAX_FRAMES = 2_000_000
MAX_DESCRIPTORS = 16384
MAX_PARSE_SECONDS = 120
CHUNK_FRAMES = 128
STRYD_APPLICATIONS = {
    "660a581e-5301-460c-8f2f-034c8b6dc90f": "Stryd legacy",
    "18fb2cf0-1a4b-430d-ad66-988c847421f4": "Stryd Power Zone",
}


class FitArchiveError(ValueError):
    """Safe, bounded error code, never provider payload or filename."""


def extract_fit_files(payload: bytes) -> list[bytes]:
    if not payload:
        raise FitArchiveError("original_unavailable")
    if len(payload) > MAX_ORIGINAL_BYTES:
        raise FitArchiveError("original_too_large")
    if payload[8:12] == b".FIT":
        return [payload]
    if not zipfile.is_zipfile(io.BytesIO(payload)):
        raise FitArchiveError("invalid_original_archive")
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
            if len(entries) > 128:
                raise FitArchiveError("archive_entry_limit")
            selected = [e for e in entries if not e.is_dir() and e.filename.lower().endswith(".fit")]
            if not selected:
                raise FitArchiveError("original_unavailable")
            if sum(e.file_size for e in selected) > MAX_FIT_BYTES:
                raise FitArchiveError("fit_too_large")
            result = []
            for entry in selected:
                # Never extract paths to disk, including traversal/symlink names.
                if entry.flag_bits & 1:
                    raise FitArchiveError("encrypted_archive")
                with archive.open(entry) as source:
                    raw = source.read(MAX_FIT_BYTES + 1)
                if len(raw) > MAX_FIT_BYTES:
                    raise FitArchiveError("fit_too_large")
                result.append(raw)
            return result
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise FitArchiveError("invalid_original_archive") from exc


def typed(value: Any) -> dict[str, Any]:
    """Explicit scalar encoding; integer decimal and float hex are lossless."""
    if value is None:
        return {"type": "invalid", "value": None}
    if isinstance(value, bytes):
        return {"type": "bytes", "value": base64.b64encode(value).decode("ascii")}
    if isinstance(value, (tuple, list)):
        return {"type": "array", "value": [typed(v) for v in value]}
    if isinstance(value, bool):
        return {"type": "boolean", "value": value}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value.hex()}
    if isinstance(value, str):
        return {"type": "string", "value": value}
    raise FitArchiveError("unsupported_decoded_type")


def _application_id(value: Any) -> str | None:
    try:
        return str(uuid.UUID(bytes=bytes(value)))
    except (ValueError, TypeError):
        return None


def _scaled(value: Any, scale: Any, offset: Any) -> Any:
    if isinstance(value, (tuple, list)):
        return [_scaled(v, scale, offset) for v in value]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if scale not in (None, 0, 1):
            value = value / scale
        return value - offset if offset else value
    return value


def normalized_metric(app: str | None, number: int, message: int, descriptor: dict, raw: Any) -> dict | None:
    # Proven mappings only; field names alone never establish application identity.
    if app not in STRYD_APPLICATIONS:
        return None
    # Verified against the two pinned GoldenCheetah real-file samples in
    # docs/dev/stryd-connectiq-coverage.md. Unseen fields remain uninterpreted.
    record = {
        0: ("power", "W", {"watts", "watt", "w"}, 1),
        2: ("cadence", "rpm", {"rpm"}, 1),
        3: ("ground_contact_time", "ms", {"milliseconds"}, 1),
        4: ("vertical_oscillation", "mm", {"centimeters"}, 10),
        8: ("form_power", "W", {"watts"}, 1),
        9: ("leg_spring_stiffness", "kN/m", {"kn/m"}, 1),
    }
    if app == "660a581e-5301-460c-8f2f-034c8b6dc90f":
        record[7] = ("elevation", "m", {"meters"}, 1)
    else:
        record.update({11: ("air_power", "W", {"watts"}, 1),
                       15: ("humidity", "%", {"%"}, 1),
                       16: ("temperature", "degC", {"c"}, 1)})
    mapping = record.get(number) if message == 20 else None
    if app == "18fb2cf0-1a4b-430d-ad66-988c847421f4":
        if message == 19 and number == 10:
            mapping = ("lap_average_power", "W", {"watts"}, 1)
        if message == 18:
            mapping = {
                99: ("critical_power", "W", {"watts"}, 1),
                100: ("baseline_humidity", "%", {"%"}, 1),
                101: ("baseline_temperature", "degC", {"degrees c"}, 1),
                17: ("weight", "kg", {"kg"}, 1),
                18: ("height", "cm", {"cm"}, 1),
            }.get(number)
    if mapping is None:
        return None
    metric, unit, accepted_units, factor = mapping
    if str(descriptor.get("units") or "").strip().lower() not in accepted_units:
        return None
    value = _scaled(raw, descriptor.get("scale"), descriptor.get("offset"))
    def convert(v):
        if isinstance(v, (tuple, list)):
            return [convert(element) for element in v]
        return v * factor if isinstance(v, (int, float)) else v
    return {"metric": metric, "unit": unit, "value": typed(convert(value)), "mapping_version": MAPPING_VERSION}



@dataclass
class FitProjection:
    catalog: list[dict] = field(default_factory=list)
    frame_count: int = 0
    developer_field_count: int = 0

    def chunks(self, raw: bytes) -> Iterator[list[dict]]:
        if len(raw) > MAX_FIT_BYTES:
            raise FitArchiveError("fit_too_large")
        started = time.monotonic()
        identities: dict[int, tuple[int, str | None]] = {}
        descriptors: dict[tuple[int, int], tuple[int, dict]] = {}
        definitions: dict[int, int] = {}
        bindings: dict[int, dict] = {}
        chunk: list[dict] = []
        # No default processor: timestamps/invalids remain raw FIT values.
        with fitdecode.FitReader(io.BytesIO(raw), processor=None,
                                 check_crc=fitdecode.CrcCheck.RAISE,
                                 error_handling=fitdecode.ErrorHandling.RAISE,
                                 keep_raw_chunks=True) as reader:
            for frame in reader:
                index = self.frame_count
                self.frame_count += 1
                if time.monotonic() - started > MAX_PARSE_SECONDS:
                    raise FitArchiveError("parse_time_limit")
                if self.frame_count > MAX_FRAMES:
                    raise FitArchiveError("frame_limit")
                record = {"index": index, "frame_type": frame.frame_type,
                          "offset": frame.chunk.offset, "raw": typed(frame.chunk.bytes)}
                if frame.frame_type == fitdecode.FIT_FRAME_HEADER:
                    identities.clear(); descriptors.clear(); definitions.clear(); bindings.clear()
                if frame.frame_type in (fitdecode.FIT_FRAME_DEFINITION, fitdecode.FIT_FRAME_DATA):
                    record.update(message_number=frame.global_mesg_num, message_name=frame.name,
                                  local_message_number=frame.local_mesg_num)
                if frame.frame_type == fitdecode.FIT_FRAME_DEFINITION:
                    definitions[frame.local_mesg_num] = index
                    bindings[frame.local_mesg_num] = {
                        (f.dev_data_index, f.def_num): (
                            descriptors.get((f.dev_data_index, f.def_num), (None, {})),
                            identities.get(f.dev_data_index, (None, None)),
                        ) for f in frame.dev_field_defs
                    }
                    record["endian"] = frame.endian
                    record["fields"] = [{"number": f.def_num, "size": f.size,
                        "base_type": f.base_type.identifier, "developer_index": getattr(f, "dev_data_index", None)}
                        for f in frame.all_field_defs]
                if frame.frame_type == fitdecode.FIT_FRAME_DATA:
                    record["definition_index"] = definitions[frame.local_mesg_num]
                    values = {f.name: f.raw_value for f in frame.fields if not f.is_expanded}
                    if frame.global_mesg_num == 207:
                        developer_index = values.get("developer_data_index")
                        identities[developer_index] = (index, _application_id(values.get("application_id")))
                        descriptors = {key: val for key, val in descriptors.items() if key[0] != developer_index}
                    if frame.global_mesg_num == 206:
                        key = (values.get("developer_data_index"), values.get("field_definition_number"))
                        descriptors[key] = (index, values)
                        identity_index, app = identities.get(key[0], (None, None))
                        if len(self.catalog) >= MAX_DESCRIPTORS:
                            raise FitArchiveError("descriptor_limit")
                        self.catalog.append({"descriptor_index": index, "identity_index": identity_index,
                            "application_id": app, "application": STRYD_APPLICATIONS.get(app, "unknown"),
                            "developer_index": key[0], "number": key[1],
                            "metadata": [{"name": f.name, "number": f.def_num, "value": typed(f.raw_value)} for f in frame.fields]})
                    fields = []
                    for f in frame.fields:
                        fd = f.field_def
                        dev = fd is not None and fd.is_dev
                        field_record = {"number": f.def_num, "name": f.name,
                            "base_type": f.base_type.identifier, "raw_value": typed(f.raw_value),
                            "value": typed(f.value), "units": f.units, "expanded": f.is_expanded,
                            "developer_index": getattr(fd, "dev_data_index", None)}
                        if dev:
                            self.developer_field_count += 1
                            (desc_index, desc), (identity_index, app) = bindings[frame.local_mesg_num][(fd.dev_data_index, f.def_num)]
                            field_record.update(descriptor_index=desc_index, identity_index=identity_index,
                                application_id=app, interpreted=False)
                            if desc:
                                field_record["value"] = typed(_scaled(f.raw_value, desc.get("scale"), desc.get("offset")))
                            normalized = normalized_metric(app, f.def_num, frame.global_mesg_num, desc, f.raw_value)
                            if normalized is not None:
                                field_record.update(normalized=normalized, interpreted=True)
                        fields.append(field_record)
                    record["fields"] = fields
                chunk.append(record)
                if len(chunk) >= CHUNK_FRAMES:
                    yield chunk
                    chunk = []
            if chunk:
                yield chunk
