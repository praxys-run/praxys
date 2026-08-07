"""Owner-authenticated activity analysis and research dataset endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from analysis.metrics import (
    ACTIVITY_ANALYSIS_SCHEMA_VERSION,
    ACTIVITY_RESEARCH_SCHEMA_VERSION,
)
from api.auth import get_current_user_id
from api.etag import (
    ENDPOINT_SCOPES,
    ETagGuard,
    compute_etag,
    compute_revision_token,
    compute_variant_etag,
)
from api.packs import (
    RequestContext,
    get_activity_analysis_pack,
    get_analysis_response_version,
    get_activity_research_pack,
)
from db.session import get_db

router = APIRouter()

ANALYSIS_EXPORT_SNAPSHOT_CHANGED = (
    "ANALYSIS_EXPORT_SNAPSHOT_CHANGED_RESTART_EXPORT"
)


@router.get("/analysis/activities/{activity_id}")
def get_activity_analysis(
    activity_id: str,
    request: Request,
    response: Response,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Return one owned activity with stable segments and pre-run context."""
    etag = compute_etag(
        db,
        user_id,
        ENDPOINT_SCOPES["analysis"],
        salt=(
            "v="
            f"{get_analysis_response_version(ACTIVITY_ANALYSIS_SCHEMA_VERSION)}"
            f"&activity_id={activity_id}"
        ),
    )
    guard = ETagGuard(etag, request.headers.get("if-none-match"))
    if guard.is_match:
        return guard.not_modified()
    ctx = RequestContext(user_id=user_id, db=db)
    payload = get_activity_analysis_pack(ctx, activity_id)
    if payload is None:
        raise HTTPException(404, "Activity not found")
    guard.apply(response)
    return payload


@router.get("/analysis/research-dataset")
def get_activity_research_dataset(
    request: Request,
    response: Response,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    source: str | None = Query(
        None,
        description=(
            "Deduplication pivot for activity summaries. Defaults to the "
            "owner's configured activity provider."
        ),
    ),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Return a bounded, versioned owner-only retrospective research dataset."""
    response_version = get_analysis_response_version(
        ACTIVITY_RESEARCH_SCHEMA_VERSION
    )
    snapshot_salt = f"analysis-export&v={response_version}"
    export_snapshot_id = compute_revision_token(
        db,
        user_id,
        ENDPOINT_SCOPES["analysis"],
        salt=snapshot_salt,
    )
    etag = compute_variant_etag(
        export_snapshot_id,
        salt=f"limit={limit}&offset={offset}&source={source or ''}",
    )
    guard = ETagGuard(etag, request.headers.get("if-none-match"))
    if guard.is_match:
        return guard.not_modified()
    ctx = RequestContext(user_id=user_id, db=db)
    payload = get_activity_research_pack(
        ctx,
        export_snapshot_id=export_snapshot_id,
        limit=limit,
        offset=offset,
        source=source,
    )
    final_snapshot_id = compute_revision_token(
        db,
        user_id,
        ENDPOINT_SCOPES["analysis"],
        salt=snapshot_salt,
    )
    if final_snapshot_id != export_snapshot_id:
        raise HTTPException(
            status_code=409,
            detail=ANALYSIS_EXPORT_SNAPSHOT_CHANGED,
        )
    guard.apply(response)
    return payload
