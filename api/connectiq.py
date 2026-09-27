"""Owner-only Connect IQ archives and durable original-download orchestration."""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
import time
from datetime import date, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import or_, case
from sqlalchemy.orm import Session, defer, aliased
from sqlalchemy.exc import IntegrityError

from db.models import (GarminConnectIQJob as Job, GarminConnectIQItem as Item,
    GarminFitSnapshot as Snapshot, GarminFitParse as Parse, GarminFitChunk as Chunk,
    User, UserConnection)
from db.connection_credentials import connection_credentials_generation, require_connection_generation
from db import sync_writer

logger = logging.getLogger(__name__)
LEASE_SECONDS = 600
BATCH_SIZE = 10


def current_region(user_id: str, db: Session, creds: dict | None = None) -> str:
    from analysis.config import load_config_from_db
    region = load_config_from_db(user_id, db).source_options.get("garmin_region")
    if region not in ("cn", "international") and creds is None:
        from db.connection_credentials import load_connection_credentials
        creds = load_connection_credentials(db, user_id=user_id, platform="garmin")
    return region if region in ("cn", "international") else ("cn" if (creds or {}).get("is_cn") else "international")


def _connection(user_id: str, db: Session) -> UserConnection:
    connection = db.query(UserConnection).filter_by(user_id=user_id, platform="garmin").first()
    if connection is None or connection.status not in ("connected", "error"):
        raise HTTPException(409, "GARMIN_CONNECTION_REQUIRED")
    return connection


def create_backfill(user_id: str, from_date: date, to_date: date, db: Session) -> Job:
    """Persist an explicitly requested, inclusive-date archive job."""
    from api.legal_receipts import user_background_processing_authorized
    from db.connection_credentials import load_connection_credentials
    if from_date > to_date or to_date > date.today():
        raise HTTPException(422, "INVALID_DATE_RANGE")
    if not user_background_processing_authorized(db, user_id):
        raise HTTPException(403, "BACKGROUND_PROCESSING_NOT_AUTHORIZED")
    user = db.query(User).filter_by(id=user_id, is_active=True).with_for_update().first()
    if user is None:
        raise HTTPException(403, "USER_NOT_ACTIVE")
    connection = _connection(user_id, db)
    creds = load_connection_credentials(db, user_id=user_id, platform="garmin")
    job = Job(user_id=user_id, credential_generation=connection_credentials_generation(connection),
        region=current_region(user_id, db, creds), kind="backfill", from_date=from_date,
        to_date=to_date, discovery_date=from_date)
    db.add(job)
    from api.routes.sync import _ensure_user_active_for_sync
    _ensure_user_active_for_sync(user_id, db)
    db.commit(); db.refresh(job)
    return job


def owned_job(user_id: str, job_id: str, db: Session) -> Job:
    """Resolve a job strictly within the authenticated owner."""
    job = db.query(Job).filter_by(id=job_id, user_id=user_id).first()
    if job is None:
        raise HTTPException(404, "CONNECTIQ_JOB_NOT_FOUND")
    return job


def job_view(job: Job, db: Session) -> dict:
    """Expose progress without credentials or lease tokens."""
    from sqlalchemy import func
    counts = dict(db.query(Item.status, func.count(Item.id)).filter_by(job_id=job.id).group_by(Item.status).all())
    return {"id": job.id, "kind": job.kind, "status": job.status,
        "from_date": job.from_date, "to_date": job.to_date,
        "discovery_complete": job.discovery_complete, "counts": counts,
        "error_code": job.error_code, "next_retry_at": job.next_retry_at,
        "created_at": job.created_at, "updated_at": job.updated_at}


def change_job(user_id: str, job_id: str, action: str, db: Session) -> dict:
    """Cancel or explicitly resume a durable owner job."""
    user = db.query(User).filter_by(id=user_id, is_active=True).with_for_update().first()
    if user is None:
        raise HTTPException(403, "USER_NOT_ACTIVE")
    job = owned_job(user_id, job_id, db)
    if action == "cancel":
        job.status = "cancelled"
    else:
        from api.legal_receipts import user_background_processing_authorized
        from db.connection_credentials import load_connection_credentials
        if not user_background_processing_authorized(db, user_id):
            raise HTTPException(403, "BACKGROUND_PROCESSING_NOT_AUTHORIZED")
        connection = _connection(user_id, db)
        # Account identity is revalidated by the authenticated worker BEFORE
        # discovery/download, against the immutable account already on the job.
        job.credential_generation = connection_credentials_generation(connection)
        creds = load_connection_credentials(db, user_id=user_id, platform="garmin")
        if current_region(user_id, db, creds) != job.region:
            raise HTTPException(409, "GARMIN_ACCOUNT_REGION_CHANGED")
        job.status = "queued"
        job.error_code = None
        job.next_retry_at = None
        for item in db.query(Item).filter(Item.job_id == job.id, Item.status != "complete"):
            item.status = "queued"; item.error_code = None
    job.lease_token = None; job.lease_until = None; job.updated_at = datetime.utcnow()
    db.commit()
    return job_view(job, db)


def archive_catalog(user_id: str, activity_id: str, db: Session) -> dict:
    """Return acquisition status and immutable archive versions."""
    snapshots = db.query(Snapshot).options(defer(Snapshot.raw_fit)).filter_by(user_id=user_id, activity_id=activity_id).order_by(Snapshot.created_at, Snapshot.id).all()
    items = db.query(Item).filter_by(user_id=user_id, activity_id=activity_id).order_by(Item.id.desc()).limit(20).all()
    if not snapshots and not items:
        from db.models import Activity
        if not db.query(Activity.id).filter_by(user_id=user_id, activity_id=activity_id).first():
            raise HTTPException(404, "ACTIVITY_NOT_FOUND")
    return {"activity_id": activity_id, "collection_status": items[0].status if items else "not_collected",
        "error_code": items[0].error_code if items else None,
        "snapshots": [snapshot_view(s, db) for s in snapshots]}


def snapshot_view(snapshot: Snapshot, db: Session) -> dict:
    """Describe the active projection and most recent parse attempt."""
    parsed = db.query(Parse).filter_by(id=snapshot.active_parse_id, user_id=snapshot.user_id).first() if snapshot.active_parse_id else None
    latest = db.query(Parse).filter_by(snapshot_id=snapshot.id, user_id=snapshot.user_id).order_by(Parse.created_at.desc()).first()
    return {"snapshot_id": snapshot.id, "account_id": snapshot.account_id,
        "sha256": snapshot.sha256, "created_at": snapshot.created_at,
        "parse_id": parsed.id if parsed else None, "status": latest.status if latest else "stored",
        "error_code": latest.error_code if latest else None,
        "parser_version": parsed.parser_version if parsed else None,
        "frame_count": parsed.frame_count if parsed else 0,
        "developer_field_count": parsed.developer_field_count if parsed else 0,
        "fields": parsed.catalog if parsed else [],
        "original_url": f"/api/activities/{snapshot.activity_id}/connectiq/original/{snapshot.id}"}


def owned_parse(user_id: str, activity_id: str, parse_id: str, db: Session) -> Parse:
    """Resolve a completed, owner-bound immutable projection."""
    result = db.query(Parse).join(Snapshot, Snapshot.id == Parse.snapshot_id).filter(
        Parse.id == parse_id, Parse.user_id == user_id, Snapshot.user_id == user_id,
        Snapshot.activity_id == activity_id, Parse.status == "complete").first()
    if result is None:
        raise HTTPException(404, "CONNECTIQ_PARSE_NOT_FOUND")
    return result


def messages(user_id: str, activity_id: str, parse_id: str, offset: int, limit: int, db: Session) -> dict:
    """Read one stable projection page without loading the full activity."""
    from sync.garmin_fit import CHUNK_FRAMES
    parsed = owned_parse(user_id, activity_id, parse_id, db)
    chunks = db.query(Chunk).filter(Chunk.user_id == user_id, Chunk.parse_id == parsed.id,
        Chunk.chunk_index >= offset // CHUNK_FRAMES,
        Chunk.chunk_index <= (offset + limit - 1) // CHUNK_FRAMES).order_by(Chunk.chunk_index).all()
    frames = [frame for chunk in chunks for frame in chunk.frames if offset <= frame["index"] < offset + limit]
    return {"parse_id": parsed.id, "snapshot_id": parsed.snapshot_id, "frames": frames,
        "next_offset": offset + len(frames) if offset + len(frames) < parsed.frame_count else None,
        "total": parsed.frame_count}


def account_export(user_id: str, db: Session) -> Iterator[dict]:
    """Lazily export every owner snapshot/version while holding one SQL chunk."""
    def frames(parse_id: str) -> Iterator[dict]:
        from api.data_export import ExportJSONValue
        chunks = db.query(Chunk).filter_by(user_id=user_id, parse_id=parse_id).order_by(Chunk.chunk_index)
        for chunk in chunks.yield_per(1):
            for frame in chunk.frames:
                yield ExportJSONValue(frame)

    def parses(snapshot_id: str) -> Iterator[dict]:
        query = db.query(Parse).filter_by(user_id=user_id, snapshot_id=snapshot_id).order_by(Parse.created_at, Parse.id)
        for parsed in query.yield_per(1):
            yield {"parse_id": parsed.id, "status": parsed.status,
                "parser_version": parsed.parser_version, "error_code": parsed.error_code,
                "fields": parsed.catalog, "frames": frames(parsed.id)}

    snapshots = db.query(Snapshot).options(defer(Snapshot.raw_fit)).filter_by(user_id=user_id).order_by(Snapshot.created_at, Snapshot.id)
    for snapshot in snapshots.yield_per(1):
        yield {"activity_id": snapshot.activity_id, **snapshot_view(snapshot, db),
               "parses": parses(snapshot.id)}


def _fence(db: Session, job_id: str, token: str) -> Job:
    # User-before-connection-before-job order matches account deletion fencing.
    job = db.query(Job).filter_by(id=job_id).first()
    if job is None:
        raise RuntimeError("job_gone")
    user = db.query(User).filter_by(id=job.user_id, is_active=True).with_for_update().first()
    if user is None:
        raise RuntimeError("user_gone")
    require_connection_generation(db, user_id=job.user_id, platform="garmin",
        expected_generation=job.credential_generation, allowed_statuses=("connected", "error"), lock=True)
    db.refresh(job, with_for_update=True)
    if job.status != "running" or job.lease_token != token or job.lease_until < datetime.utcnow():
        raise RuntimeError("lease_lost")
    from api.legal_receipts import user_background_processing_authorized
    if not user_background_processing_authorized(db, job.user_id):
        raise RuntimeError("processing_not_authorized")
    if current_region(job.user_id, db) != job.region:
        raise RuntimeError("region_changed")
    return job


def _claim(db: Session) -> tuple[str, str] | None:
    now = datetime.utcnow()
    running = aliased(Job)
    occupied = db.query(running.id).filter(running.user_id == Job.user_id,
        running.status == "running", running.lease_until >= now).exists()
    candidate = db.query(Job).filter(~occupied,
        or_(Job.status.in_(("queued", "retry")), (Job.status == "running") & (Job.lease_until < now)),
        or_(Job.next_retry_at.is_(None), Job.next_retry_at <= now)).order_by(case((Job.status == "running", 0), else_=1), Job.updated_at, Job.created_at).first()
    if candidate is None:
        return None
    # One account per process lease is not sufficient: CAS prevents duplicate
    # claims across app workers and the token fences every subsequent commit.
    token = str(uuid4())
    try:
        return _claim_candidate(db, candidate.id, token, now)
    except IntegrityError:
        db.rollback()
        return None


def _claim_candidate(db: Session, job_id: str, token: str, now: datetime) -> tuple[str, str] | None:
    changed = db.query(Job).filter(Job.id == job_id,
        or_(Job.status.in_(("queued", "retry")), (Job.status == "running") & (Job.lease_until < now)),
        or_(Job.next_retry_at.is_(None), Job.next_retry_at <= now)).update(
        {Job.status: "running", Job.lease_token: token, Job.lease_until: now + timedelta(seconds=LEASE_SECONDS), Job.updated_at: now}, synchronize_session=False)
    db.commit()
    return (job_id, token) if changed else None


def _client(db: Session, job: Job) -> object:
    from sync.garmin_original import GarminOriginalClient
    from db.connection_credentials import load_connection_credentials
    from db.garmin_tokens import load_garmin_tokens
    from api.routes.sync import _login_garmin_with_cn_fallback
    creds = load_connection_credentials(db, user_id=job.user_id, platform="garmin")
    if not creds:
        raise RuntimeError("credentials_unavailable")
    client = GarminOriginalClient(creds["email"], creds["password"], is_cn=job.region == "cn")
    tokens = load_garmin_tokens(db, user_id=job.user_id, expected_generation=job.credential_generation,
        allowed_statuses=("connected", "error"))
    db.rollback()  # Never hold a row lock over provider requests.
    _login_garmin_with_cn_fallback(client, creds, tokens)
    return client


def run_job(db: Session, job_id: str, token: str, client_factory: Callable | None = None) -> None:
    """Execute one bounded discovery/download batch under an expiring claim."""
    from sync.garmin_sync import garmin_user_profile_id, garmin_profile_account_id, RATE_LIMIT_DELAY
    from sync.garmin_fit import extract_fit_files, PARSER_VERSION
    from db.garmin_tokens import stage_garmin_tokens
    from api.routes.sync import _serialize_garmin_tokens
    job = _fence(db, job_id, token)
    connection = _connection(job.user_id, db)
    if connection.next_retry_at and connection.next_retry_at > datetime.utcnow():
        job.status = "retry"; job.next_retry_at = connection.next_retry_at; db.commit(); return
    user_id, region = job.user_id, job.region
    client = (client_factory or _client)(db, job)
    _fence(db, job_id, token)
    db.rollback()
    account_id = garmin_profile_account_id(user_id=user_id, is_cn=region == "cn", garmin_user_profile_id=garmin_user_profile_id(client))
    job = _fence(db, job_id, token)
    if job.account_id and job.account_id != account_id:
        raise RuntimeError("account_changed")
    job.account_id = account_id
    if client_factory is None:
        stage_garmin_tokens(db, user_id=user_id, serialized_tokens=_serialize_garmin_tokens(client),
            expected_generation=job.credential_generation, allowed_statuses=("connected", "error"))
    db.commit()
    job = _fence(db, job_id, token)
    if not job.discovery_complete:
        # Bounded page checkpoints over the inclusive range; empty days need no requests.
        start, end, offset = job.from_date, job.to_date, job.discovery_offset
        if offset >= 200_000:
            raise RuntimeError("discovery_limit")
        db.rollback()
        batch = client.connectapi("/activitylist-service/activities/search/activities", params={
            "start": offset, "limit": 100, "startDate": start.isoformat(), "endDate": end.isoformat(), "sortOrder": "asc"})
        if not isinstance(batch, list) or len(batch) > 100:
            raise RuntimeError("invalid_activity_page")
        ids = [str(a["activityId"]) for a in batch]
        job = _fence(db, job_id, token)
        sync_writer.write_connectiq_items(job, ids, db)
        if len(batch) == 100:
            job.discovery_offset += 100
        else:
            job.discovery_complete = True
        db.commit(); time.sleep(RATE_LIMIT_DELAY)
    for _ in range(BATCH_SIZE):
        job = _fence(db, job_id, token)
        item = db.query(Item).filter_by(job_id=job.id, status="queued").order_by(Item.id).first()
        if item is None:
            break
        item_id, aid = item.id, item.activity_id
        # Reparse retained originals locally; retry downloads only when absent.
        snapshots = db.query(Snapshot).filter_by(user_id=user_id, account_id=account_id, activity_id=aid).all()
        raw_files = None
        if not snapshots:
            db.rollback()
            from garminconnect import Garmin
            try:
                payload = client.download_activity(aid, dl_fmt=Garmin.ActivityDownloadFormat.ORIGINAL)
                raw_files = extract_fit_files(payload)
            except Exception as exc:
                from sync.garmin_errors import garmin_http_status
                from sync.garmin_fit import FitArchiveError
                if garmin_http_status(exc) not in (404, 410) and not isinstance(exc, FitArchiveError):
                    _fence(db, job_id, token)
                    item = db.get(Item, item_id)
                    item.attempts += 1
                    item.error_code = "download_failed"
                    # Queued means eligible for automatic retry, not never attempted.
                    db.commit()
                    raise
                job = _fence(db, job_id, token)
                item = db.get(Item, item_id)
                item.status = "unavailable" if garmin_http_status(exc) in (404, 410) or str(exc) == "original_unavailable" else "download_failed"
                item.error_code = str(exc) if isinstance(exc, FitArchiveError) else "original_unavailable"
                item.attempts += 1; db.commit(); continue
        job = _fence(db, job_id, token)
        item = db.get(Item, item_id)
        if raw_files is not None:
            snapshots = [sync_writer.write_garmin_fit_snapshot(user_id, account_id, aid, raw, db) for raw in raw_files]
            item.snapshot_id = snapshots[0].id
            db.commit()  # Original survives parse failure/process interruption.
        success = True
        for snapshot in snapshots:
            job = _fence(db, job_id, token)
            parsed = db.query(Parse).filter_by(id=snapshot.active_parse_id, parser_version=PARSER_VERSION, status="complete").first() if snapshot.active_parse_id else None
            if parsed is None:
                parsed = sync_writer.write_garmin_fit_parse(snapshot, db)
            success = success and parsed.status == "complete"
            _fence(db, job_id, token)
            db.commit()
        job = _fence(db, job_id, token)
        item = db.get(Item, item_id)
        item.status = "complete" if success else "parse_failed"
        item.error_code = None if success else "invalid_fit"
        item.attempts += 1; db.commit(); time.sleep(RATE_LIMIT_DELAY)
    job = _fence(db, job_id, token)
    remaining = db.query(Item.id).filter_by(job_id=job.id, status="queued").first()
    failed = db.query(Item.id).filter(Item.job_id == job.id, Item.status != "complete").first()
    job.status = ("completed_with_errors" if failed else "complete") if job.discovery_complete and not remaining else "queued"
    # A successful batch has consumed its retry deadline. Preserve unresolved
    # activity diagnostics, but clear the job error once those failures recover.
    job.next_retry_at = None
    unresolved_error = db.query(Item.id).filter(
        Item.job_id == job.id, Item.error_code.is_not(None)).first()
    if unresolved_error is None:
        job.error_code = None
    job.lease_token = None; job.lease_until = None; job.updated_at = datetime.utcnow(); db.commit()


def run_tick(session_factory: Callable | None = None) -> None:
    """Claim one durable batch and record sanitized retry state."""
    from db import session as sessions
    from db.sync_scheduler import backoff_seconds, classify_sync_failure
    from db.connection_credentials import ConnectionGenerationChanged
    factory = session_factory or sessions.SessionLocal
    if factory is None:
        return
    with factory() as db:
        claimed = _claim(db)
        if claimed is None:
            return
        job_id, token = claimed
        try:
            from api.routes.sync import _garmin_tokenstore_lease
            user_id = db.get(Job, job_id).user_id
            db.rollback()
            with _garmin_tokenstore_lease(user_id):
                run_job(db, job_id, token)
        except Exception as exc:
            db.rollback()
            reference = db.query(Job).filter_by(id=job_id).first()
            if reference is None:
                return
            user = db.query(User).filter_by(id=reference.user_id).with_for_update().first()
            if user is None:
                return
            connection = db.query(UserConnection).filter_by(user_id=reference.user_id,
                platform="garmin").populate_existing().with_for_update().first()
            job = db.query(Job).filter(Job.id == job_id, Job.lease_token == token,
                Job.status == "running", Job.lease_until >= datetime.utcnow()).populate_existing().with_for_update().first()
            if job is None:
                return
            error = str(exc)
            terminal = isinstance(exc, ConnectionGenerationChanged) or error in {
                "account_changed", "region_changed", "processing_not_authorized", "credentials_unavailable", "user_gone", "discovery_limit"}
            status, auth_terminal = classify_sync_failure(exc)
            terminal = terminal or auth_terminal
            job.attempts += 1
            job.status = "paused" if terminal else "retry"
            job.error_code = error if error in {"account_changed", "region_changed", "processing_not_authorized", "credentials_unavailable", "user_gone", "discovery_limit"} else ("connection_changed" if isinstance(exc, ConnectionGenerationChanged) else "download_failed")
            job.next_retry_at = None if terminal else datetime.utcnow() + timedelta(seconds=backoff_seconds(job.attempts))
            job.lease_token = None; job.lease_until = None
            # Only a still-current connection may receive shared failure state.
            if connection and connection_credentials_generation(connection) == job.credential_generation and connection.status in ("connected", "error"):
                connection.status = status if auth_terminal else connection.status
                connection.next_retry_at = job.next_retry_at
            db.commit()
            logger.info("Connect IQ job stopped: job=%s code=%s", job_id, job.error_code)


def reparse_snapshot(user_id: str, activity_id: str, snapshot_id: str, db: Session) -> dict:
    """Reproject retained bytes without a provider request or live connection."""
    from api.legal_receipts import user_background_processing_authorized
    user = db.query(User).filter_by(id=user_id, is_active=True).with_for_update().first()
    if user is None or not user_background_processing_authorized(db, user_id):
        raise HTTPException(403, "BACKGROUND_PROCESSING_NOT_AUTHORIZED")
    snapshot = db.query(Snapshot).filter_by(id=snapshot_id, user_id=user_id, activity_id=activity_id).with_for_update().first()
    if snapshot is None:
        raise HTTPException(404, "CONNECTIQ_SNAPSHOT_NOT_FOUND")
    parsed = sync_writer.write_garmin_fit_parse(snapshot, db)
    if not user_background_processing_authorized(db, user_id):
        db.rollback()
        raise HTTPException(403, "BACKGROUND_PROCESSING_NOT_AUTHORIZED")
    db.commit()
    return {"snapshot_id": snapshot.id, "parse_id": parsed.id,
            "status": parsed.status, "error_code": parsed.error_code}


def job_items(user_id: str, job_id: str, offset: int, limit: int, db: Session) -> dict:
    """Expose bounded checkpoints so an owner can identify unavailable activities."""
    owned_job(user_id, job_id, db)
    query = db.query(Item).filter_by(user_id=user_id, job_id=job_id)
    total = query.count()
    rows = query.order_by(Item.id).offset(offset).limit(limit).all()
    return {"job_id": job_id, "total": total,
        "next_offset": offset + len(rows) if offset + len(rows) < total else None,
        "items": [{"activity_id": row.activity_id, "status": row.status,
                   "error_code": row.error_code, "attempts": row.attempts,
                   "snapshot_id": row.snapshot_id} for row in rows]}
