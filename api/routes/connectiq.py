"""Authenticated first-party access to the caller's private FIT archives."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.auth import get_current_user_id, require_write_access
from api import connectiq
from db.models import GarminFitSnapshot
from db.session import get_db

router = APIRouter(tags=["connectiq"])


class BackfillRequest(BaseModel):
    from_date: date
    to_date: date


@router.get("/activities/{activity_id}/connectiq")
def catalog(activity_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return connectiq.archive_catalog(user_id, activity_id, db)


@router.get("/activities/{activity_id}/connectiq/messages")
def messages(activity_id: str, parse_id: str, offset: int = Query(0, ge=0),
             limit: int = Query(128, ge=1, le=512),
             user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return connectiq.messages(user_id, activity_id, parse_id, offset, limit, db)


@router.get("/activities/{activity_id}/connectiq/export")
def export(activity_id: str, parse_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    import json
    from fastapi.responses import StreamingResponse
    parsed = connectiq.owned_parse(user_id, activity_id, parse_id, db)
    total = parsed.frame_count
    header = {"schema_version": 1, "parse_id": parsed.id, "snapshot_id": parsed.snapshot_id,
              "parser_version": parsed.parser_version, "fields": parsed.catalog}

    def stream():
        yield json.dumps(jsonable_encoder(header), ensure_ascii=False)[:-1] + ', "frames":['
        first = True
        for offset in range(0, total, 128):
            page = connectiq.messages(user_id, activity_id, parse_id, offset, 128, db)
            for frame in page["frames"]:
                yield ("" if first else ",") + json.dumps(frame, ensure_ascii=False)
                first = False
        yield "]}"
    return StreamingResponse(stream(), media_type="application/json", headers={
        "Content-Disposition": f'attachment; filename="connectiq-{parsed.id}.json"',
        "Cache-Control": "private, no-store"})


@router.get("/activities/{activity_id}/connectiq/original/{snapshot_id}")
def original(activity_id: str, snapshot_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    snapshot = db.query(GarminFitSnapshot).filter_by(id=snapshot_id, user_id=user_id, activity_id=activity_id).first()
    if snapshot is None:
        raise HTTPException(404, "CONNECTIQ_SNAPSHOT_NOT_FOUND")
    return Response(snapshot.raw_fit, media_type="application/octet-stream", headers={
        "Content-Disposition": f'attachment; filename="{snapshot.id}.fit"',
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "ETag": f'"{snapshot.sha256}"'})


@router.post("/sync/garmin/connectiq-backfills", status_code=202)
def create(body: BackfillRequest, user_id: str = Depends(require_write_access), db: Session = Depends(get_db)):
    return connectiq.job_view(connectiq.create_backfill(user_id, body.from_date, body.to_date, db), db)


@router.get("/sync/garmin/connectiq-backfills/{job_id}")
def status(job_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return connectiq.job_view(connectiq.owned_job(user_id, job_id, db), db)


@router.post("/sync/garmin/connectiq-backfills/{job_id}/resume", status_code=202)
def resume(job_id: str, user_id: str = Depends(require_write_access), db: Session = Depends(get_db)):
    return connectiq.change_job(user_id, job_id, "resume", db)


@router.post("/sync/garmin/connectiq-backfills/{job_id}/cancel")
def cancel(job_id: str, user_id: str = Depends(require_write_access), db: Session = Depends(get_db)):
    return connectiq.change_job(user_id, job_id, "cancel", db)


@router.post("/activities/{activity_id}/connectiq/original/{snapshot_id}/reparse")
def reparse(activity_id: str, snapshot_id: str, user_id: str = Depends(require_write_access), db: Session = Depends(get_db)):
    return connectiq.reparse_snapshot(user_id, activity_id, snapshot_id, db)


@router.get("/sync/garmin/connectiq-backfills/{job_id}/items")
def items(job_id: str, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200),
          user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    return connectiq.job_items(user_id, job_id, offset, limit, db)
