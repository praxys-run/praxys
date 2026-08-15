"""Activity history endpoint."""
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
)
from sqlalchemy.orm import Session

from api.auth import get_current_user_id, get_data_user_id
from api.etag import ENDPOINT_SCOPES, ETagGuard, compute_etag
from api.packs import RequestContext, get_history_pack
from api.stryd_access import stryd_connection_enabled
from db.session import get_db

router = APIRouter()


@router.get("/history")
def get_history(
    request: Request,
    response: Response,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    source: str | None = Query(
        None,
        description="Filter by an available activity source. Defaults to the primary source.",
    ),
    viewer_user_id: str = Depends(get_current_user_id),
    user_id: str = Depends(get_data_user_id),
    db: Session = Depends(get_db),
):
    stryd_enabled = stryd_connection_enabled(
        db,
        user_id=viewer_user_id,
    )
    if (
        not stryd_enabled
        and str(source or "").strip().casefold() == "stryd"
    ):
        raise HTTPException(status_code=404, detail="Not found")

    # Pagination changes the body, so query params must be salted into the
    # ETag. Otherwise ?offset=0 and ?offset=20 would share an ETag and the
    # browser would replay the wrong cached page on a matching 304.
    etag = compute_etag(
        db, user_id, ENDPOINT_SCOPES["history"],
        salt=(
            f"limit={limit}&offset={offset}&source={source or ''}"
            f"&stryd={int(stryd_enabled)}"
        ),
    )
    guard = ETagGuard(etag, request.headers.get("if-none-match"))
    if guard.is_match:
        return guard.not_modified()
    guard.apply(response)
    ctx = RequestContext(user_id=user_id, db=db)
    if (
        not stryd_enabled
        and str(
            ctx.config.preferences.get("activities") or ""
        ).strip().casefold() == "stryd"
    ):
        # Keep truthful historical provenance, but do not let a hidden
        # connection preference select or prioritize the private provider.
        ctx.config.preferences = dict(ctx.config.preferences)
        ctx.config.preferences.pop("activities", None)
    pack = get_history_pack(ctx, limit=limit, offset=offset, source=source)
    return {
        "activities": pack["activities"],
        "total": pack["total"],
        "limit": limit,
        "offset": offset,
        "source_filter": pack["source_filter"],
        "training_base": ctx.config.training_base,
        "display": ctx.display,
    }
