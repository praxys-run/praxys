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
    from analysis.science_artifacts import load_policy_contract
    try:
        contract = load_policy_contract(SDR_ID, require_active=True)
        parameters = {k: v.value for k, v in contract.parameters.items()}
        if contract.model_version != METHOD_VERSION or digest(parameters) != POLICY_PARAMETER_DIGEST:
            raise ValueError("DFA implementation does not match the active method")
        return contract.contract_digest
    except Exception as exc:
        raise HTTPException(503, "DFA_SCIENCE_POLICY_INACTIVE") from exc


def require_authority(db: Session, owner: str) -> str:
    from api.legal_receipts import user_background_processing_authorized
    user = db.query(User).filter_by(id=owner).first()
    if user is None or not user.is_active or user.is_demo or not user_background_processing_authorized(db, owner):
        raise HTTPException(403, "DFA_PROCESSING_NOT_AUTHORIZED")
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
    processing_authorized = bool(user and user.is_active and not user.is_demo and user_background_processing_authorized(db, owner))
    return {"activity_id": activity, "inputs": candidates, "catalog_revision": digest(candidates),
            "source_confirmations": [proof_view(p) for p in proofs],
            "latest_run": view(run, db, include_result=False) if run else None,
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
    return _source_current(db, run)


def _source_current(db: Session, run: Run) -> bool:
    """Source proof/current archive facts, independent of processing or math."""
    try:
        candidates = _inputs(db, run.user_id, run.activity_id)
    except HTTPException:
        return False
    if not any(c["input"] == run.recording_ref for c in candidates):
        return False
    if run.phase == "compute":
        proof = db.query(Confirmation).filter_by(id=run.confirmation_id, user_id=run.user_id).first()
        return bool(proof and proof_current(proof, candidates))
    return True


def _run_metadata(run: Run, current: bool) -> dict:
    return {"id": run.id, "phase": run.phase, "status": run.status, "generation": run.generation,
            "freshness": "current" if current else "stale", "progress": run.progress,
            "error_code": run.error_code, "created_at": run.created_at, "completed_at": run.completed_at,
            "expires_at": run.expires_at, "method_version": run.method_version,
            "science_contract_digest": run.science_contract_digest,
            "snapshot_id": run.snapshot_id, "parse_id": run.parse_id, "source_confirmation_id": run.confirmation_id,
            "result_revision": run.result_revision if current else None}


def view(run: Run, db: Session, offset: int = 0, limit: int = 120, include_result: bool = True) -> dict:
    current = _current(db, run)
    base = _run_metadata(run, current)
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
    return view(_owned(db, owner, activity, run_id), db, offset, limit)


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
        db.query(Slot).filter(Slot.run_id.in_(ids)).update({Slot.run_id: None, Slot.lease_token: None, Slot.lease_until: None}, synchronize_session=False)
        query.delete(synchronize_session=False)


def cleanup(db: Session, owner: str | None = None) -> None:
    query = db.query(Run).filter(Run.status.notin_(ACTIVE), Run.expires_at <= datetime.utcnow())
    if owner:
        query = query.filter(Run.user_id == owner)
    _delete_runs(db, query)


def _reserve(db: Session, owner: str, retry_run: Run | None = None) -> None:
    _slot(db)  # global queue admission lock, after owner lock
    cleanup(db, owner)
    if db.query(Run.id).filter(Run.user_id == owner, Run.status.in_(ACTIVE)).first():
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
        identity = digest([ref, METHOD_VERSION, policy_digest, phase, proof.id if proof else None,
                           proof.evidence_digest if proof else None, STATEMENT_VERSION])
        run = db.query(Run).filter_by(user_id=owner, input_digest=identity).first()
        if run and (run.expires_at is None or run.expires_at > datetime.utcnow()):
            result, code = view(run, db), 202 if run.status in ACTIVE else 200
            db.commit()
            return result, code
        if run:
            _delete_runs(db, db.query(Run).filter_by(id=run.id))
        _reserve(db, owner)
        run = Run(user_id=owner, activity_id=activity, snapshot_id=ref["snapshot_id"], parse_id=ref["parse_id"],
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
            _reserve(db, owner, retry_run=run)
            run.status, run.progress, run.error_code = "queued", "queued", None
            run.retained_bytes = MAX_RESULT_BYTES
            run.completed_at = run.expires_at = None
            run.recoveries = 0
        elif run.status in ACTIVE:
            run.status, run.progress = "cancelled", "cancelled"
            run.completed_at = datetime.utcnow()
            run.expires_at = run.completed_at + timedelta(days=7)
            run.retained_bytes = 0
        run.generation += 1
        run.lease_until = run.lease_token = None
        db.query(Slot).filter_by(run_id=run.id).update({Slot.run_id: None, Slot.lease_token: None, Slot.lease_until: None}, synchronize_session=False)
        run.updated_at = datetime.utcnow()
        # Cancellation is an exempt rights operation: never read or return
        # result payloads, even for terminal rows or unavailable private storage.
        result = _run_metadata(run, False) if action == "cancel" else view(run, db)
        db.commit()
    from api.activity_dfa_dispatch import wake
    wake()
    return result


def _erase(db: Session, value: dict) -> None:
    cutoff = datetime.fromisoformat(value["requested_at"])
    query = db.query(Run).filter(Run.user_id == value["user_id"], Run.created_at <= cutoff)
    proofs = db.query(Confirmation).filter(Confirmation.user_id == value["user_id"], Confirmation.created_at <= cutoff)
    scope, target = value["scope"], value["target_id"]
    if scope == "activity":
        query, proofs = query.filter(Run.activity_id == target), proofs.filter(Confirmation.activity_id == target)
    elif scope == "snapshot":
        query, proofs = query.filter(Run.snapshot_id == target), proofs.filter(Confirmation.snapshot_id == target)
    elif scope == "confirmation":
        query, proofs = query.filter(Run.confirmation_id == target), proofs.filter(Confirmation.id == target)
    _delete_runs(db, query)
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
        for value in storage.iter_active(owner):
            replay_manifest(db, value)
    except Exception as exc:
        db.rollback()
        raise HTTPException(503, "DFA_RESTORE_REPLAY_UNAVAILABLE") from exc


def invalidate_snapshot(db: Session, owner: str, snapshot_id: str) -> None:
    """Called inside source writer's owner transaction before switching parse."""
    runs = db.query(Run).filter_by(user_id=owner, snapshot_id=snapshot_id).all()
    if runs or db.query(Confirmation.id).filter_by(user_id=owner, snapshot_id=snapshot_id).first():
        # A pre-reparse backup must not revive the previous proof. Leave this
        # requested until reconciliation erases the cutoff and commits; never
        # mark completion inside the caller's still-uncommitted parse transaction.
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
    ids = [r.id for r in runs]
    db.query(Slot).filter(Slot.run_id.in_(ids)).update({Slot.run_id: None, Slot.lease_until: None, Slot.lease_token: None}, synchronize_session=False)
    db.query(Confirmation).filter_by(user_id=owner, snapshot_id=snapshot_id).delete(synchronize_session=False)


def export(db: Session, owner: str) -> dict:
    ensure_replayed(db, owner)
    def runs():
        from api.data_export import ExportJSONValue
        from fastapi.encoders import jsonable_encoder
        read_timeout(db)
        query = db.query(Run).filter(Run.user_id == owner,
            or_(Run.expires_at.is_(None), Run.expires_at > datetime.utcnow())).order_by(Run.created_at, Run.id)
        for run in query.yield_per(1):
            source_valid = _source_current(db, run)
            method_current = False
            try:
                method_current = (run.freshness == "current" and run.method_version == METHOD_VERSION
                                  and require_policy() == run.science_contract_digest)
            except HTTPException:
                pass
            # Export is a rights operation: retained data remains portable after
            # processing withdrawal, stale Terms or ordinary numerical updates.
            # Source revocation/reparse/erasure still removes or withholds it.
            metadata = _run_metadata(run, source_valid and method_current)
            metadata["result_revision"] = run.result_revision if source_valid else None
            yield ExportJSONValue(jsonable_encoder({**metadata,
                "recording_ref": run.recording_ref, "result": run.result if source_valid else None}))
    return {"schema_version": 1,
            "confirmations": [{**proof_view(p), "recording_ref": p.recording_ref, "evidence_digest": p.evidence_digest,
                               "rule_fingerprint": p.rule_fingerprint}
                              for p in db.query(Confirmation).filter_by(user_id=owner).all()],
            "runs": runs()}


def context(db: Session, owner: str, activity: str, run_id: str, offset: int, limit: int,
            result_revision: str, expected_samples_revision: str | None) -> dict:
    ensure_replayed(db, owner)
    run = _owned(db, owner, activity, run_id)
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


def claim(db: Session) -> tuple[str, int, str] | None:
    """Global slot lock + generation fencing; owner lock is acquired first."""
    now = datetime.utcnow()
    read_timeout(db)
    candidate = db.query(Run.id, Run.user_id).filter(or_(Run.status == "queued", (Run.status == "running") & (Run.lease_until < now))).order_by(Run.created_at).first()
    db.rollback()
    if candidate is None:
        return None
    ensure_replayed(db, candidate.user_id)
    with owner_write(db, candidate.user_id):
        slot = _slot(db)
        if slot.lease_until and slot.lease_until >= now:
            return None
        run = db.query(Run).filter_by(id=candidate.id).populate_existing().first()
        if run is None or run.status not in ACTIVE or (run.lease_until and run.lease_until >= now):
            return None
        if run.status == "running":
            if run.recoveries >= 1:
                run.status, run.error_code = "failed", "lease_recovery_exhausted"
                run.completed_at = now
                run.expires_at = now + timedelta(days=7)
                run.retained_bytes = 0
                run.lease_until = run.lease_token = None
                db.commit()
                return None
            run.recoveries += 1
            run.generation += 1
        token = str(uuid4())
        run.status, run.progress = "running", "reading"
        run.lease_token, run.lease_until = token, now + timedelta(seconds=LEASE_SECONDS)
        slot.run_id, slot.lease_token, slot.lease_until = run.id, token, run.lease_until
        result = (run.id, run.generation, token)
        db.commit()
        return result


def execute(session_factory, run_id: str, generation: int, token: str) -> None:
    started, renewed = time.monotonic(), 0.
    with session_factory() as db:
        initial = db.query(Run).filter_by(id=run_id).first()
        if initial is None:
            return
        owner, ref, phase = initial.user_id, RecordingRef(**initial.recording_ref), initial.phase
        db.rollback()
        ensure_replayed(db, owner)

        def fence(progress: str | None = None) -> Run:
            require_authority(db, owner)
            run = db.query(Run).filter(Run.id == run_id, Run.user_id == owner, Run.generation == generation,
                Run.lease_token == token, Run.status == "running", Run.lease_until >= datetime.utcnow()).populate_existing().first()
            slot = db.query(Slot).filter_by(id=1, run_id=run_id, lease_token=token).first()
            if run is None or slot is None or not _current(db, run):
                raise DFAError("lease_lost")
            if progress:
                until = datetime.utcnow() + timedelta(seconds=LEASE_SECONDS)
                run.lease_until = slot.lease_until = until
                run.progress = progress
            return run

        def check():
            nonlocal renewed
            now = time.monotonic()
            if now-started > MAX_EXECUTION_SECONDS:
                raise DFAError("execution_time_limit")
            if now-renewed >= 15:
                with owner_write(db, owner):
                    fence("reading" if phase == "prepare" else "computing")
                    db.commit()
                renewed = now

        try:
            check()
            messages = list(RRRecordingReader(db).iter_recording(ref, check))
            db.rollback()  # no long transaction while doing numerical work
            recording = build_recording(messages, (messages[-1]["frame"]+1) if messages else 0, check)
            if phase == "prepare":
                output, status = recording.preparation(), "awaiting_source_confirmation"
            else:
                with owner_write(db, owner):
                    run = fence()
                    proof = db.query(Confirmation).filter_by(id=run.confirmation_id, user_id=owner).first()
                    if proof is None or proof.evidence_digest != recording.evidence_digest or not any(
                        s["sensor_ref"] == proof.sensor_ref and s["rule_fingerprint"] == proof.rule_fingerprint for s in recording.sensors):
                        raise DFAError("source_contradiction")
                    db.commit()
                output, status = compute(recording, check), "complete"
            encoded = json.dumps(output, separators=(",", ":"), allow_nan=False).encode()
            if len(encoded) > MAX_RESULT_BYTES:
                raise DFAError("result_limit")
            check()
            with owner_write(db, owner):
                fence()
                now = datetime.utcnow()
                changed = db.query(Run).filter_by(id=run_id, user_id=owner, generation=generation, lease_token=token, status="running").update(
                    {Run.status: status, Run.progress: status, Run.result: output, Run.result_revision: digest(output),
                     Run.retained_bytes: len(encoded), Run.completed_at: now, Run.updated_at: now,
                     Run.expires_at: now + timedelta(days=30 if status == "complete" else 1),
                     Run.lease_until: None, Run.lease_token: None}, synchronize_session=False)
                if changed:
                    db.query(Slot).filter_by(id=1, run_id=run_id, lease_token=token).update(
                        {Slot.run_id: None, Slot.lease_token: None, Slot.lease_until: None}, synchronize_session=False)
                db.commit()
        except Exception as exc:
            db.rollback()
            error = str(exc) if isinstance(exc, DFAError) else ("processing_not_authorized" if isinstance(exc, HTTPException) else "computation_failed")
            if error not in SAFE_INPUT_ERRORS | {"execution_time_limit", "result_limit", "lease_lost", "processing_not_authorized"}:
                error = "computation_failed"
            with owner_write(db, owner):
                now = datetime.utcnow()
                status = "unavailable" if error in SAFE_INPUT_ERRORS else "failed"
                changed = db.query(Run).filter(Run.id == run_id, Run.user_id == owner, Run.generation == generation,
                    Run.lease_token == token, Run.status == "running", Run.lease_until >= now).update(
                    {Run.status: status, Run.progress: status, Run.error_code: error,
                     Run.result: None, Run.retained_bytes: 0, Run.completed_at: now,
                     Run.expires_at: now + timedelta(days=1 if status == "unavailable" else 7),
                     Run.lease_until: None, Run.lease_token: None}, synchronize_session=False)
                if changed:
                    db.query(Slot).filter_by(run_id=run_id, lease_token=token).update(
                        {Slot.run_id: None, Slot.lease_token: None, Slot.lease_until: None}, synchronize_session=False)
                db.commit()
            logger.info("DFA task ended: state=%s reason=%s", status, error)
