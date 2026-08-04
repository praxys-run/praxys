"""Owner-authenticated activity analysis and research dataset endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from api.auth import get_current_user_id
from api.etag import ENDPOINT_SCOPES, ETagGuard, compute_etag
from api.packs import (
    RequestContext,
    get_activity_analysis_pack,
    get_activity_research_pack,
)
from db.session import get_db

router = APIRouter()


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
        salt=f"v=activity-analysis-v1&activity_id={activity_id}",
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
    etag = compute_etag(
        db,
        user_id,
        ENDPOINT_SCOPES["analysis"],
        salt=(
            "v=activity-research-dataset-v1"
            f"&limit={limit}&offset={offset}&source={source or ''}"
        ),
    )
    guard = ETagGuard(etag, request.headers.get("if-none-match"))
    if guard.is_match:
        return guard.not_modified()
    guard.apply(response)
    ctx = RequestContext(user_id=user_id, db=db)
    return get_activity_research_pack(
        ctx,
        limit=limit,
        offset=offset,
        source=source,
    )
