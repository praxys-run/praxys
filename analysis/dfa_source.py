"""Pure native source qualification; metadata never establishes per-beat attribution."""
from analysis.activity_dfa import GARMIN_ECG, SOURCE_VERSION, DFAError, digest, sensor_evidence

AUTO_SDR_ID = "sdr-activity-dfa-alpha1-v2"
SOURCE_RULE_VERSION = "dfa-native-ecg-metadata-v1"
METADATA_PROJECTION_VERSION = "rr-native-source-metadata-v2"


def _name(value):
    name = str(value or "").strip(" \t\n\r\v\f").lower()
    return "h10" if name in ("h10", "polar h10") else name


def source_inventory(messages: list[dict], recording_ref: dict) -> dict:
    """Merge partial native descriptors by recording-local handle, retaining conflicts.

    Only opaque candidate handles and supported model labels leave this function.
    Native device names are used only for identity matching and evidence hashing.
    """
    handles = {}
    for message in messages:
        if message["message"] != 23:
            continue
        values = message["values"]
        index = values.get("device_index")
        if type(index) is not int:
            index = ("missing", message["frame"])
        facts = handles.setdefault(index, {})
        for field in ("manufacturer", "product", "product_name", "source_type", "device_type"):
            value = values.get(field)
            if field == "product_name":
                value = _name(value) or None
            if value is not None:
                facts.setdefault(field, set()).add(value)

    unresolved, contradiction = False, False
    candidates, rules, evidence = [], set(), []
    for handle, facts in sorted(handles.items(), key=lambda row: str(row[0])):
        row = {key: next(iter(values)) for key, values in facts.items()}
        manufacturer, product = row.get("manufacturer"), row.get("product")
        name = row.get("product_name", "")
        label = GARMIN_ECG.get(product) if manufacturer == 1 else (
            "Polar H10" if manufacturer == 123 and name == "h10" else None)
        pairs = {(a, b) for a in facts.get("source_type", {None})
                 for b in facts.get("device_type", {None})}
        # A generic watch is not an HR inventory declaration. Explicit local
        # wrist inventory is unresolved, never itself positive optical RR.
        relevant = bool(label or pairs & {(1, 120), (3, 1), (5, 10)}
                        or row.get("source_type") in (1, 3) and row.get("device_type") is None
                        or row.get("device_type") == 120 and row.get("source_type") is None)
        if not relevant:
            continue
        conflicts = {key for key, values in facts.items() if len(values) > 1}
        if conflicts & {"manufacturer", "product", "product_name"}:
            contradiction = True
        # Native model text explicitly identifying optical external HR is
        # positive inventory evidence, rather than a generic watch capability.
        optical = any(token in name for token in ("optical", "oh1", "verity sense", "scosche", "mio link"))
        if optical and pairs & {(1, 120), (3, 1)}:
            contradiction = True
        if conflicts or not label or not pairs <= {(1, 120), (3, 1)} or type(handle) is not int:
            unresolved = True
        opaque = digest([recording_ref, METADATA_PROJECTION_VERSION, handle])[:32]
        evidence.append([opaque, {key: sorted(values) for key, values in facts.items()}])
        if label:
            rule = digest([SOURCE_VERSION, manufacturer, "h10" if manufacturer == 123 else product])
            rules.add(rule)
            candidates.append({"sensor_ref": opaque, "label": label, "rule_fingerprint": rule,
                               "transport": "ANT+" if pairs == {(1, 120)} else "BLE" if pairs == {(3, 1)} else None})
    try:
        sensor_evidence(messages)
    except DFAError:
        contradiction = True
    sessions = [m for m in messages if m["message"] == 18]
    native = len(sessions) == 1 and sessions[0]["values"].get("sport") == 1
    native = native and any(m["message"] == 78 and m["values"].get("time") for m in messages)
    if not native:
        outcome, reason = "source_ineligible", "native_running_rr_required"
    elif contradiction:
        outcome, reason = "source_ineligible", "source_contradiction"
    elif unresolved or len(rules) != 1 or not candidates:
        outcome, reason = "source_unresolved", "source_unresolved"
    else:
        outcome, reason = "eligible_metadata_inferred", None
    return {"outcome": outcome, "reason": reason, "candidates": [] if contradiction else candidates,
            "source_rule_version": SOURCE_RULE_VERSION, "metadata_projection_version": METADATA_PROJECTION_VERSION,
            "source_evidence_digest": digest([recording_ref, SOURCE_RULE_VERSION, METADATA_PROJECTION_VERSION, evidence])}


def require_native_integrity(messages: list[dict], recording_ref: dict) -> dict:
    inventory = source_inventory(messages, recording_ref)
    if inventory["outcome"] == "source_ineligible":
        raise DFAError("source_contradiction")
    return inventory
