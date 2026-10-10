"""Credential-free numerical child. Receives private bytes; has no DB imports."""
from __future__ import annotations
import base64
import json
import sys

INPUT_LIMIT = 90 * 1024 * 1024
OUTPUT_LIMIT = 8 * 1024 * 1024


def main():
    # The launcher blocks here until durable acknowledgement and authorization.
    raw = sys.stdin.buffer.readline(INPUT_LIMIT + 1)
    if len(raw) > INPUT_LIMIT or not raw.endswith(b"\n"):
        raise ValueError("ipc_input_invalid")
    from api import dfa_ipc
    payload = dfa_ipc.loads(raw)
    dfa_ipc.binding(payload.get("binding"))
    if set(payload) != {"binding", "actor_token", "phase", "raw_fit", "recording_ref", "manual_proof", "origin"}:
        raise ValueError("ipc_schema_invalid")
    if payload["phase"] not in ("prepare", "compute"):
        raise ValueError("ipc_phase_invalid")
    from analysis.activity_dfa import build_recording, compute
    from analysis.dfa_source import require_native_integrity
    from sync.rr_recording import decode
    messages = list(decode(base64.b64decode(payload["raw_fit"], validate=True)))
    inventory = require_native_integrity(messages, payload["recording_ref"])
    recording = build_recording(messages, messages[-1]["frame"] + 1 if messages else 0)
    if payload["phase"] == "compute":
        if payload["origin"] == "automatic":
            if inventory["outcome"] != "eligible_metadata_inferred" or payload["manual_proof"] is not None:
                raise ValueError("automatic_source_changed")
        elif payload["origin"] == "manual":
            proof = payload["manual_proof"]
            if not proof or proof["evidence_digest"] != recording.evidence_digest or not any(
                s["sensor_ref"] == proof["sensor_ref"] and s["rule_fingerprint"] == proof["rule_fingerprint"]
                for s in recording.sensors):
                raise ValueError("manual_source_changed")
        else:
            raise ValueError("origin_invalid")
    result = recording.preparation() if payload["phase"] == "prepare" else compute(recording)
    output = json.dumps({"binding": payload["binding"], "actor_token": payload["actor_token"],
                         "inventory": inventory, "result": result}, separators=(",", ":"), allow_nan=False).encode()
    if len(output) > OUTPUT_LIMIT:
        raise ValueError("ipc_result_limit")
    sys.stdout.buffer.write(output + b"\n")
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
