"""Bounded owner-only DFA work, immutable source assurance and lifecycle fencing."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timedelta
import json
import logging
import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session, defer

from analysis.activity_dfa import (DFAError, METHOD_VERSION, SOURCE_VERSION, STATEMENT_VERSION,
                                  SDR_ID, GARMIN_ECG, POLICY_PARAMETER_DIGEST, Recording, build_recording, compute, digest, overlay)
from api import activity_dfa_storage as storage
from db.account_lifecycle import account_lifecycle_lease
from db.models import (ActivityDFARun as Run, ActivityDFAConfirmation as Confirmation,
                       ActivityDFAExecutionSlot as Slot, User, Activity, ActivitySample, CacheRevision)
from db.session import begin_serialized_write
from sync.rr_recording import RRRecordingReader, RecordingRef, read_timeout

logger = logging.getLogger(__name__)
ACTIVE = ("queued", "running")
MAX_RESULT_BYTES = 8 * 1024 * 1024
OWNER_QUOTA = 256 * 1024 * 1024
LEASE_SECONDS = 180
MAX_EXECUTION_SECONDS = 120
MAX_ACTIVE_GLOBAL = 20
SAFE_INPUT_ERRORS = {"activity_type_unsupported", "source_unsupported", "source_contradiction", "rr_missing",
                     "timer_invalid", "fit_invalid", "fit_too_large", "rr_limit", "frame_limit", "elapsed_limit",
                     "input_changed", "input_integrity_failed"}


def require_policy() -> str:
    from api.dfa_policy import validated_contract
    try:
        contract = validated_contract(SDR_ID)
        parameters = {k: v.value for k, v in contract.parameters.items()}
        if contract.model_version != METHOD_VERSION or digest(parameters) != POLICY_PARAMETER_DIGEST:
            raise ValueError("DFA implementation does not match the active method")
        return contract.contract_digest
    except Exception as exc:
        raise HTTPException(503, "DFA_SCIENCE_POLICY_INACTIVE") from exc


def require_historical_v1_policy() -> str:
    """Historical callable remains permanently denied after terminal V1 STOP."""
    raise HTTPException(503, "DFA_SCIENCE_POLICY_INACTIVE")


def require_authority(db: Session, owner: str) -> str:
    from api.dfa_rights import processing_receipt
    processing_receipt(db, owner)
    return require_policy()


@contextmanager
def owner_write(db: Session, owner: str):
    # Auth readers are over before this point. Serialize SQLite and PostgreSQL
    # read/modify/write and share the cross-worker account deletion fence.
    db.rollback()
    with account_lifecycle_lease(owner, timeout_seconds=30):
        begin_serialized_write(db)
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SET LOCAL statement_timeout = '30s'"))
            db.execute(text("SET LOCAL lock_timeout = '30s'"))
        db.query(User).filter_by(id=owner).with_for_update().first()
        try:
            yield
        except Exception:
            db.rollback()
            raise


def _error(exc: DFAError) -> HTTPException:
    return HTTPException(404 if str(exc) == "activity_not_found" else 409, str(exc))


def _inputs(db: Session, owner: str, activity: str) -> list[dict]:
    try:
        return RRRecordingReader(db).list_inputs(owner, activity)
    except DFAError as exc:
        raise _error(exc) from exc


def _current_rule(proof: Confirmation) -> bool:
    rules = {digest([SOURCE_VERSION, 1, p]) for p in GARMIN_ECG}
    rules.add(digest([SOURCE_VERSION, 123, "h10"]))
    return proof.statement_version == STATEMENT_VERSION and proof.rule_fingerprint in rules


def proof_current(proof: Confirmation, candidates: list[dict]) -> bool:
    return _current_rule(proof) and any(proof.recording_ref == v["input"] for v in candidates)


def proof_view(proof: Confirmation) -> dict:
    return {"id": proof.id, "snapshot_id": proof.snapshot_id, "parse_id": proof.parse_id,
            "sensor_ref": proof.sensor_ref, "sensor_label": proof.sensor_label,
            "statement_version": proof.statement_version, "created_at": proof.created_at,
            "source_assurance": "user_confirmed"}


def catalog(db: Session, owner: str, activity: str) -> dict:
    ensure_replayed(db, owner)
    availability = "ready"
    try:
        candidates = _inputs(db, owner, activity)
    except HTTPException as exc:
        if exc.detail != "activity_type_unsupported":
            raise
        candidates, availability = [], "activity_type_unsupported"
    source = db.query(Activity.source).filter_by(user_id=owner, activity_id=activity).scalar()
    if availability == "ready" and not candidates:
        availability = "original_unavailable" if source == "garmin" else "provider_unsupported"
    proofs = db.query(Confirmation).filter_by(user_id=owner, activity_id=activity).all()
    proofs = [p for p in proofs if proof_current(p, candidates)]
    run = db.query(Run).options(defer(Run.result)).filter(Run.user_id == owner, Run.activity_id == activity,
        or_(Run.expires_at.is_(None), Run.expires_at > datetime.utcnow())).order_by(Run.created_at.desc()).first()
    active_policy = True
    try:
        require_policy()
    except HTTPException:
        active_policy = False
    from api.legal_receipts import user_background_processing_authorized
    user = db.query(User).filter_by(id=owner).first()
    from api import dfa_rights
    try:
        dfa_rights.processing_receipt(db, owner)
        processing_authorized = True
    except HTTPException:
        processing_authorized = False
    from db.models import ActivityDFASyncReceipt
    receipt = db.query(ActivityDFASyncReceipt).filter_by(user_id=owner).filter(
        ActivityDFASyncReceipt.recording_ref["activity_id"].as_string() == activity).order_by(ActivityDFASyncReceipt.created_at.desc()).first()
    automatic_availability = "science_inactive" if not active_policy else "rights_missing" if not processing_authorized else (
        "gate_denied" if not dfa_rights.automatic_gate(db, owner) else receipt.disposition if receipt else "no_new_sync")
    origin_runs = []
    for origin in ("manual", "automatic"):
        latest = db.query(Run).options(defer(Run.result)).filter_by(user_id=owner, activity_id=activity, origin=origin).filter(
            or_(Run.expires_at.is_(None), Run.expires_at > datetime.utcnow())).order_by(Run.created_at.desc()).first()
        if latest:
            origin_runs.append(view(latest, db, include_result=False))
    current_runs = [item for item in origin_runs if item["freshness"] == "current"]
    return {"activity_id": activity, "inputs": candidates, "catalog_revision": digest(candidates),
            "source_confirmations": [proof_view(p) for p in proofs],
            "latest_run": current_runs[0] if current_runs else (origin_runs[0] if origin_runs else None),
            "origin_runs": origin_runs, "automatic_availability": automatic_availability,
            "availability": availability, "policy_active": active_policy,
            "processing_authorized": processing_authorized, "statement_version": STATEMENT_VERSION}


def _owned(db: Session, owner: str, activity: str, run_id: str, *, metadata_only: bool = False) -> Run:
    read_timeout(db)
    query = db.query(Run).filter_by(id=run_id, user_id=owner, activity_id=activity)
    run = (query.options(defer(Run.result)) if metadata_only else query).first()
    if run is None:
        raise HTTPException(404, "DFA_RUN_NOT_FOUND")
    if run.expires_at and run.expires_at <= datetime.utcnow():
        raise HTTPException(410, "DFA_RESULT_EXPIRED")
    return run


def _current(db: Session, run: Run) -> bool:
    if run.freshness != "current" or run.method_version != METHOD_VERSION:
        return False
    try:
        if require_authority(db, run.user_id) != run.science_contract_digest:
            return False
    except HTTPException:
        return False
    from api.dfa_rights import grant_current
    return grant_current(db, run) and _source_current(db, run)


def _source_current(db: Session, run: Run) -> bool:
    """Source proof/current archive facts, independent of processing or math."""
    try:
        candidates = _inputs(db, run.user_id, run.activity_id)
    except HTTPException:
        return False
    if not any(c["input"] == run.recording_ref for c in candidates):
        return False
    if run.phase == "compute" and run.origin == "manual":
        proof = db.query(Confirmation).filter_by(id=run.confirmation_id, user_id=run.user_id).first()
        return bool(proof and proof_current(proof, candidates))
    return True


def _run_metadata(run: Run, current: bool) -> dict:
    return {"id": run.id, "origin": run.origin, "source_assurance": "metadata_inferred" if run.origin == "automatic" else "user_confirmed" if run.confirmation_id else None,
            "admission_id": run.admission_id, "accepted_at": run.accepted_at, "phase": run.phase, "status": run.status, "generation": run.generation,
            "freshness": "current" if current else "stale", "progress": run.progress,
            "error_code": run.error_code, "created_at": run.created_at, "completed_at": run.completed_at,
            "expires_at": run.expires_at, "method_version": run.method_version,
            "science_contract_digest": run.science_contract_digest,
            "source_rule_version": "dfa-native-ecg-metadata-v1",
            "metadata_projection_version": "rr-native-source-metadata-v2",
            "statement_version": STATEMENT_VERSION,
            "snapshot_id": run.snapshot_id, "parse_id": run.parse_id, "source_confirmation_id": run.confirmation_id,
            "result_revision": run.result_revision if current else None}


def _metadata(db: Session, run: Run, current: bool) -> dict:
    from db.models import ActivityDFAControl
    value = _run_metadata(run, current)
    control = db.query(ActivityDFAControl).filter_by(id=1).first()
    actor = control.actor if control else None
    if actor and actor.get("binding", {}).get("input") == run.input_digest and actor.get("state") != "idle":
        value["physical_state"] = actor.get("state")
        if run.status == "cancelled":
            value["status"] = "cancellation_requested"
    else:
        value["physical_state"] = "idle"
    return value


def view(run: Run, db: Session, offset: int = 0, limit: int = 120, include_result: bool = True) -> dict:
    current = _current(db, run)
    base = _metadata(db, run, current)
    if include_result and current and run.result:
        value = run.result
        base.update({k: v for k, v in value.items() if k != "windows"})
        windows = value.get("windows", [])
        base["windows"] = windows[offset:offset+limit]
        base["page"] = {"offset": offset, "limit": limit, "total": len(windows),
                        "next_offset": offset+limit if offset+limit < len(windows) else None}
    return base


def read_run(db: Session, owner: str, activity: str, run_id: str, offset: int, limit: int) -> dict:
    ensure_replayed(db, owner)
    with owner_write(db, owner):
        result = view(_owned(db, owner, activity, run_id, metadata_only=True), db, offset, limit)
        db.commit()
        return result


def _slot(db: Session) -> Slot:
    slot = db.query(Slot).filter_by(id=1).with_for_update().first()
    if slot is None:
        # Startup creates this under a database lock. Tests may create_all only.
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("INSERT INTO activity_dfa_execution_slot(id) VALUES(1) ON CONFLICT(id) DO NOTHING"))
        else:
            db.execute(text("INSERT OR IGNORE INTO activity_dfa_execution_slot(id) VALUES(1)"))
        slot = db.query(Slot).filter_by(id=1).with_for_update().one()
    return slot


def _delete_runs(db: Session, query) -> None:
    ids = [r[0] for r in query.with_entities(Run.id).all()]
    if ids:
        query.delete(synchronize_session=False)


def cleanup(db: Session, owner: str | None = None) -> None:
    query = db.query(Run).filter(Run.status.notin_(ACTIVE), Run.expires_at <= datetime.utcnow())
    if owner:
        query = query.filter(Run.user_id == owner)
    _delete_runs(db, query)


def _reserve(db: Session, owner: str, retry_run: Run | None = None) -> None:
    _slot(db)  # global queue admission lock, after owner lock
    cleanup(db, owner)
    if db.query(Run.id).filter(Run.user_id == owner, Run.origin == "manual", Run.status.in_(ACTIVE)).first():
        raise HTTPException(429, "DFA_OWNER_QUEUE_FULL", headers={"Retry-After": "5"})
    if db.query(Run.id).filter(Run.status.in_(ACTIVE)).count() >= MAX_ACTIVE_GLOBAL:
        raise HTTPException(429, "DFA_QUEUE_FULL", headers={"Retry-After": "5"})
    used = db.query(func.coalesce(func.sum(Run.retained_bytes), 0)).filter_by(user_id=owner).scalar()
    if retry_run:
        used -= retry_run.retained_bytes
    if used + MAX_RESULT_BYTES > OWNER_QUOTA:
        evictable = db.query(Run).options(defer(Run.result)).filter(Run.user_id == owner, Run.status.notin_(ACTIVE))
        if retry_run:
            evictable = evictable.filter(Run.id != retry_run.id)
        for candidate in evictable.order_by(Run.completed_at, Run.id).all():
            used -= candidate.retained_bytes
            _delete_runs(db, db.query(Run).filter_by(id=candidate.id))
            if used + MAX_RESULT_BYTES <= OWNER_QUOTA:
                break
    if used + MAX_RESULT_BYTES > OWNER_QUOTA:
        raise HTTPException(429, "DFA_RESULT_QUOTA", headers={"Retry-After": "5"})


def submit(db: Session, owner: str, activity: str, selected: dict, revision: str, confirmation_id: str | None) -> tuple[dict, int]:
    ensure_replayed(db, owner)
    with owner_write(db, owner):
        policy_digest = require_authority(db, owner)
        candidates = _inputs(db, owner, activity)
        if revision != digest(candidates):
            raise HTTPException(409, "DFA_CATALOG_CHANGED")
        matches = [r["input"] for r in candidates if all(r["input"].get(k) == selected.get(k) for k in ("provider", "snapshot_id", "parse_id"))]
        if len(matches) != 1:
            raise HTTPException(409, "DFA_INPUT_UNAVAILABLE")
        ref = matches[0]
        proof = None
        if confirmation_id:
            proof = db.query(Confirmation).filter_by(id=confirmation_id, user_id=owner, activity_id=activity).first()
            if proof is None or proof.recording_ref != ref or not proof_current(proof, candidates):
                raise HTTPException(409, "DFA_SOURCE_CONFIRMATION_CHANGED")
        phase = "compute" if proof else "prepare"
        from api import dfa_rights
        grant = dfa_rights.create_grant(db, dfa_rights.binding(db, owner, ref, "manual", policy_digest, proof))
        identity = digest(["manual", grant.id, ref, METHOD_VERSION, policy_digest, phase, proof.id if proof else None,
                           proof.evidence_digest if proof else None, STATEMENT_VERSION])
        run = db.query(Run).filter_by(user_id=owner, input_digest=identity).first()
        if run and (run.expires_at is None or run.expires_at > datetime.utcnow()):
            result, code = view(run, db), 202 if run.status in ACTIVE else 200
            db.commit()
            return result, code
        if run:
            _delete_runs(db, db.query(Run).filter_by(id=run.id))
        _reserve(db, owner)
        from api.dfa_supervisor import manual_admission
        admission_id, accepted_at, epoch = manual_admission(db)
        run = Run(origin="manual", grant_id=grant.id, admission_id=admission_id, accepted_at=accepted_at, execution_epoch=epoch,
                  user_id=owner, activity_id=activity, snapshot_id=ref["snapshot_id"], parse_id=ref["parse_id"],
                  confirmation_id=proof.id if proof else None, recording_ref=ref, input_digest=identity,
                  method_version=METHOD_VERSION, science_contract_digest=policy_digest, phase=phase, retained_bytes=MAX_RESULT_BYTES)
        db.add(run)
        db.flush()
        result = view(run, db)
        db.commit()
    from api.activity_dfa_dispatch import wake
    wake()
    return result, 202


def confirm(db: Session, owner: str, activity: str, payload: dict) -> dict:
    ensure_replayed(db, owner)
    manifest = None
    with owner_write(db, owner):
        require_authority(db, owner)
        run = _owned(db, owner, activity, payload["run_id"])
        if run.phase != "prepare" or run.status != "awaiting_source_confirmation" or not _current(db, run):
            raise HTTPException(409, "DFA_PREPARATION_CHANGED")
        result = run.result or {}
        sensors = [s for s in result.get("sensors", []) if s["sensor_ref"] == payload["sensor_ref"]]
        if payload["confirmed"] is not True or payload["statement_version"] != STATEMENT_VERSION or payload["evidence_digest"] != result.get("evidence_digest") or len(sensors) != 1:
            raise HTTPException(409, "DFA_SOURCE_EVIDENCE_CHANGED")
        sensor = sensors[0]
        existing = db.query(Confirmation).filter_by(user_id=owner, snapshot_id=run.snapshot_id, parse_id=run.parse_id).first()
        if existing and existing.sensor_ref == sensor["sensor_ref"] and existing.evidence_digest == result["evidence_digest"] and _current_rule(existing):
            return proof_view(existing)
        if existing:
            manifest = storage.request(owner, "confirmation", existing.id, "source_changed")
            _erase(db, manifest)
            db.flush()
        proof = Confirmation(user_id=owner, activity_id=activity, snapshot_id=run.snapshot_id, parse_id=run.parse_id,
            recording_ref=run.recording_ref, sensor_ref=sensor["sensor_ref"], sensor_label=sensor["label"],
            evidence_digest=result["evidence_digest"], rule_fingerprint=sensor["rule_fingerprint"], statement_version=STATEMENT_VERSION)
        db.add(proof)
        db.flush()
        response = proof_view(proof)
        db.commit()
    if manifest:
        _complete_manifest(manifest)
    return response


def change_run(db: Session, owner: str, activity: str, run_id: str, action: str, expected_generation: int | None = None) -> dict:
    if action == "retry":
        ensure_replayed(db, owner)
    with owner_write(db, owner):
        run = _owned(db, owner, activity, run_id, metadata_only=action == "cancel")
        if action == "retry":
            require_authority(db, owner)
            if expected_generation != run.generation or run.status not in ("failed", "cancelled", "unavailable") or not _current(db, run):
                raise HTTPException(409, "DFA_RETRY_CHANGED")
            if run.origin != "manual":
                raise HTTPException(409, "DFA_EXPLICIT_MANUAL_RETRY_REQUIRED")
            _reserve(db, owner, retry_run=run)
            from api.dfa_supervisor import manual_admission
            run.admission_id, run.accepted_at, run.execution_epoch = manual_admission(db)
            run.status, run.progress, run.error_code = "queued", "queued", None
            run.retained_bytes = MAX_RESULT_BYTES
            run.completed_at = run.expires_at = None
            run.recoveries = 0
        elif run.status in ACTIVE:
            state = storage.record_negative(owner, "cancel", "run", run.id)
            run.generation = max(run.generation, state["sequence"])
            if run.origin == "automatic":
                from db.models import ActivityDFASyncReceipt, ActivityDFAOriginGrant
                grant = db.get(ActivityDFAOriginGrant, run.grant_id)
                completion = db.get(ActivityDFASyncReceipt, grant.binding.get("completion_id")) if grant else None
                if completion:
                    storage.record_negative(owner, "automatic_cancel", "completion", completion.id)
                    completion.disposition = "cancelled"
            run.status, run.progress = "cancelled", "cancelled"
            run.completed_at = datetime.utcnow()
            run.expires_at = run.completed_at + timedelta(days=7)
            run.retained_bytes = 0
        run.generation += 1
        run.lease_until = run.lease_token = None
        run.updated_at = datetime.utcnow()
        # Cancellation is an exempt rights operation: never read or return
        # result payloads, even for terminal rows or unavailable private storage.
        result = _metadata(db, run, False) if action == "cancel" else view(run, db)
        db.commit()
    from api.activity_dfa_dispatch import wake
    wake()
    return result


def _erase(db: Session, value: dict) -> None:
    cutoff = datetime.fromisoformat(value["requested_at"])
    from db.models import ActivityDFAOriginGrant, ActivityDFASyncReceipt, ActivityDFASyncGrant
    query = db.query(Run).filter(Run.user_id == value["user_id"], Run.created_at <= cutoff)
    proofs = db.query(Confirmation).filter(Confirmation.user_id == value["user_id"], Confirmation.created_at <= cutoff)
    scope, target = value["scope"], value["target_id"]
    if scope == "activity":
        query, proofs = query.filter(Run.activity_id == target), proofs.filter(Confirmation.activity_id == target)
    elif scope == "snapshot":
        query, proofs = query.filter(Run.snapshot_id == target), proofs.filter(Confirmation.snapshot_id == target)
    elif scope == "confirmation":
        query, proofs = query.filter(Run.confirmation_id == target), proofs.filter(Confirmation.id == target)
    affected = query.with_entities(Run.grant_id).all()
    grant_ids = [row[0] for row in affected if row[0]]
    _delete_runs(db, query)
    if grant_ids:
        db.query(ActivityDFAOriginGrant).filter(ActivityDFAOriginGrant.id.in_(grant_ids)).delete(synchronize_session=False)
    if scope == "owner":
        db.query(ActivityDFAOriginGrant).filter_by(user_id=value["user_id"]).delete(synchronize_session=False)
        db.query(ActivityDFASyncReceipt).filter_by(user_id=value["user_id"]).delete(synchronize_session=False)
        if value.get("reason") == "account_deletion":
            db.query(ActivityDFASyncGrant).filter_by(user_id=value["user_id"]).delete(synchronize_session=False)
    proofs.delete(synchronize_session=False)


def _complete_manifest(value: dict) -> None:
    try:
        storage.complete(value)
    except storage.StorageError:
        # Pending durable manifest remains fail-safe and is retried by replay.
        logger.warning("DFA erasure completion pending")


def erase(db: Session, owner: str, activity: str, confirmation_id: str | None = None) -> dict:
    with owner_write(db, owner):
        scope, target = ("confirmation", confirmation_id) if confirmation_id else ("activity", activity)
        runs = db.query(Run.created_at).filter_by(user_id=owner, activity_id=activity)
        proofs = db.query(Confirmation.created_at).filter_by(user_id=owner, activity_id=activity)
        if confirmation_id:
            runs = runs.filter(Run.confirmation_id == confirmation_id)
            proofs = proofs.filter(Confirmation.id == confirmation_id)
        created = [r[0] for r in runs.all()] + [r[0] for r in proofs.all()]
        eligible = bool(created) or (not confirmation_id and db.query(Activity.id).filter_by(
            user_id=owner, activity_id=activity).first() is not None)
        if not eligible:
            # No new arbitrary targets. Existing durable requests remain intact,
            # even when restored SQL has no corresponding rows yet.
            return {"deleted": True}
        try:
            previous = [v for v in storage.iter_active(owner)
                        if v["scope"] == scope and v["target_id"] == target]
        except storage.StorageError:
            # Rights writes do not depend on successful restore replay/listing.
            # A successful durable request is still mandatory before SQL erase.
            previous = []
        value = max(previous, key=lambda v: v["requested_at"], default=None)
        if value is None or (created and max(created) > datetime.fromisoformat(value["requested_at"])):
            try:
                value = storage.request(owner, scope, target, "withdrawal")
            except storage.StorageError as exc:
                raise HTTPException(503, "DFA_DELETE_STORAGE_UNAVAILABLE") from exc
        _erase(db, value)
        db.commit()
        if value["completed_at"] is None:
            _complete_manifest(value)
    return {"deleted": True}


def replay_manifest(db: Session, value: dict) -> None:
    if storage.expired(value):
        storage.discard(value)
        return
    with owner_write(db, value["user_id"]):
        _erase(db, value)
        db.commit()
        if value["completed_at"] is None:
            storage.complete(value)


def ensure_replayed(db: Session, owner: str) -> None:
    try:
        state = storage.authority_state(owner)
        if state["deleted"]:
            with owner_write(db, owner):
                user = db.query(User).filter_by(id=owner).first()
                if user:
                    user.is_active = False
                _erase(db, {"user_id": owner, "scope": "owner", "target_id": owner,
                            "requested_at": datetime.max.isoformat()})
                db.commit()
            raise HTTPException(403, "DFA_OWNER_DELETED")
        for value in storage.iter_active(owner):
            replay_manifest(db, value)
    except Exception as exc:
        db.rollback()
        raise HTTPException(503, "DFA_RESTORE_REPLAY_UNAVAILABLE") from exc


def invalidate_snapshot(db: Session, owner: str, snapshot_id: str) -> None:
    """Called inside source writer's owner transaction before switching parse."""
    runs = db.query(Run).filter_by(user_id=owner, snapshot_id=snapshot_id).all()
    # Journal every prior source generation, even when no DFA rows exist.
    # A restored archive must not revive a former grant or proof.
    storage.request(owner, "snapshot", snapshot_id, "source_changed")
    for run in runs:
        run.freshness = "stale"
        run.generation += 1
        run.lease_token = run.lease_until = None
        run.result = run.result_revision = None
        run.retained_bytes = 0
        run.confirmation_id = None
        if run.status in ACTIVE:
            run.status = run.progress = "cancelled"
            run.completed_at = datetime.utcnow()
            run.expires_at = run.completed_at + timedelta(days=7)
    db.flush()
    db.query(Confirmation).filter_by(user_id=owner, snapshot_id=snapshot_id).delete(synchronize_session=False)


def export(db: Session, owner: str) -> dict:
    ensure_replayed(db, owner)
    def runs():
        from api.data_export import ExportJSONValue
        from fastapi.encoders import jsonable_encoder
        last_id = ""
        while True:
            # Keyset metadata reads avoid retaining a server cursor across the
            # owner transaction used for each disclosure decision.
            next_id = db.query(Run.id).filter(Run.user_id == owner, Run.id > last_id,
                or_(Run.expires_at.is_(None), Run.expires_at > datetime.utcnow())).order_by(Run.id).first()
            if not next_id:
                break
            last_id = next_id[0]
            with owner_write(db, owner):
                run = db.query(Run).options(defer(Run.result)).filter_by(id=last_id, user_id=owner).first()
                if run is None:
                    continue
                current = _current(db, run)
                metadata = _metadata(db, run, current)
                encoded = ExportJSONValue(jsonable_encoder({**metadata,
                    "recording_ref": run.recording_ref, "result": run.result if current else None}))
                db.commit()
            # Authorization linearizes while the current owner/source/rights
            # transaction holds its locks; the already encoded value is released.
            yield encoded
    return {"schema_version": 1,
            "confirmations": [{**proof_view(p), "recording_ref": p.recording_ref, "evidence_digest": p.evidence_digest,
                               "rule_fingerprint": p.rule_fingerprint}
                              for p in db.query(Confirmation).filter_by(user_id=owner).all()],
            "runs": runs()}


def _context(db: Session, owner: str, activity: str, run_id: str, offset: int, limit: int,
            result_revision: str, expected_samples_revision: str | None) -> dict:
    run = _owned(db, owner, activity, run_id, metadata_only=True)
    if not _current(db, run) or run.status != "complete" or run.result_revision != result_revision:
        raise HTTPException(409, "DFA_RESULT_CHANGED")
    windows = (run.result or {}).get("windows", [])[offset:offset+limit]
    def revision():
        value = db.query(CacheRevision.revision).filter_by(user_id=owner, scope="samples").scalar()
        return str(value or 0)
    for attempt in range(2):
        before = revision()
        if expected_samples_revision is not None and before != expected_samples_revision:
            raise HTTPException(409, "context_changed")
        samples = []
        if windows:
            samples = [dict(r._mapping) for r in db.query(ActivitySample.t_sec, ActivitySample.power_watts, ActivitySample.speed_ms).filter(
                ActivitySample.user_id == owner, ActivitySample.activity_id == activity,
                ActivitySample.t_sec >= windows[0]["start_ms"]//1000-2,
                ActivitySample.t_sec <= windows[-1]["end_ms"]//1000).order_by(ActivitySample.t_sec).all()]
        db.expire_all()
        after = revision()
        if before == after:
            return {"result_revision": result_revision, "samples_revision": after, "overlay_version": "held2s-support80-v1",
                    "offset": offset, "windows": overlay(windows, samples)}
    raise HTTPException(409, "context_changed")


def context(db: Session, owner: str, activity: str, run_id: str, offset: int, limit: int,
            result_revision: str, expected_samples_revision: str | None) -> dict:
    ensure_replayed(db, owner)
    with owner_write(db, owner):
        value = _context(db, owner, activity, run_id, offset, limit, result_revision, expected_samples_revision)
        db.commit()
        return value


def claim(db: Session):
    """API workers have no physical launch authority."""
    raise HTTPException(503, "DFA_SUPERVISOR_REQUIRED")


def execute(*args, **kwargs):
    raise HTTPException(503, "DFA_SUPERVISOR_REQUIRED")
