"""Training analysis endpoint."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from api.auth import get_current_user_id, get_data_user_id
from api.dashboard_cache import cached_or_compute
from api.etag import CACHE_CONTROL, ETagGuard, compute_endpoint_etag
from api.packs import (
    RequestContext,
    get_diagnosis_pack,
    get_fitness_pack,
    get_signal_pack,
)
from api.stryd_access import stryd_connection_enabled
from analysis.metrics import apply_heat_adaptation_guidance
from db.session import get_db

router = APIRouter()


def _build_training_payload(
    user_id: str,
    db: Session,
    *,
    include_stryd_plan: bool = True,
) -> dict:
    """Compute the /api/training response from L1 packs (cache miss path)."""
    ctx = RequestContext(
        user_id=user_id,
        db=db,
        include_stryd_plan=include_stryd_plan,
    )
    diagnosis = get_diagnosis_pack(ctx)
    fitness = get_fitness_pack(ctx)
    signal = get_signal_pack(ctx)
    heat_adaptation = apply_heat_adaptation_guidance(
        ctx.heat_adaptation,
        signal["signal"].get("recommendation"),
    )
    return {
        "diagnosis": diagnosis["diagnosis"],
        "fitness_fatigue": fitness["fitness_fatigue"],
        "cp_trend": fitness["cp_trend"],
        "weekly_review": fitness["weekly_review"],
        "summary": {
            "current_tsb": fitness["current_tsb"],
            "distribution_match_pct": diagnosis["distribution_match_pct"],
            "load_compliance_pct": fitness["load_compliance_pct"],
        },
        "workout_flags": diagnosis["workout_flags"],
        "sleep_perf": diagnosis["sleep_perf"],
        "heat_adaptation": heat_adaptation,
        "training_base": ctx.config.training_base,
        "display": ctx.display,
        "data_meta": ctx.data_meta,
        "science_notes": ctx.science_notes,
    }


@router.get("/training")
def get_training(
    request: Request,
    viewer_user_id: str = Depends(get_current_user_id),
    user_id: str = Depends(get_data_user_id),
    db: Session = Depends(get_db),
):
    stryd_enabled = stryd_connection_enabled(
        db,
        user_id=viewer_user_id,
    )
    guard = ETagGuard(
        compute_endpoint_etag(
            db,
            user_id,
            "training",
            variant="stryd-on" if stryd_enabled else "stryd-off",
        ),
        request.headers.get("if-none-match"),
    )
    if guard.is_match:
        return guard.not_modified()
    compute = lambda: _build_training_payload(
        user_id,
        db,
        include_stryd_plan=stryd_enabled,
    )
    body = cached_or_compute(
        db,
        user_id,
        "training",
        compute=compute,
        use_cache=not stryd_enabled,
    )
    return Response(
        content=body,
        media_type="application/json",
        headers={"ETag": guard.etag, "Cache-Control": CACHE_CONTROL},
    )
