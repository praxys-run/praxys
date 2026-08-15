"""Backend-authoritative access control for the private Stryd integration."""
from __future__ import annotations

from typing import Any, Mapping

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

STRYD_CONNECTION_GATE = "stryd_connection_enabled"


def is_stryd_provider(value: object) -> bool:
    """Return whether a legacy provider value names Stryd."""
    return isinstance(value, str) and value.strip().casefold() == "stryd"


def stryd_connection_enabled(db: Session, *, user_id: str) -> bool:
    """Return whether one active, non-demo account may use Stryd."""
    from api import statsig_client
    from db.models import User, UserConfig

    user = db.execute(
        select(
            User.id,
            User.email,
            User.is_active,
            User.is_superuser,
            User.is_demo,
        ).where(User.id == user_id)
    ).one_or_none()
    if user is None or not user.is_active or user.is_demo:
        return False
    config = db.get(UserConfig, user_id)
    statsig_user = statsig_client.get_statsig_user(
        user_id=user_id,
        email=user.email,
        is_admin=user.is_superuser,
        is_demo=user.is_demo,
        training_base=(
            config.training_base if config is not None else None
        ),
        language=config.language if config is not None else None,
    )
    return statsig_client.check_gate(
        STRYD_CONNECTION_GATE,
        statsig_user,
    )


def require_stryd_connection_enabled(
    db: Session,
    *,
    user_id: str,
) -> None:
    """Return 404 unless the authenticated account may use Stryd."""
    if not stryd_connection_enabled(db, user_id=user_id):
        raise HTTPException(status_code=404, detail="Not found")


def without_stryd_plan_rows(plan: Any) -> Any:
    """Return a plan frame without private provider rows."""
    if plan is None or not hasattr(plan, "columns"):
        return plan
    if "source" not in plan.columns:
        return plan
    source_keys = (
        plan["source"]
        .astype("string")
        .str.strip()
        .str.casefold()
        .fillna("")
    )
    return plan.loc[source_keys.ne("stryd")].copy().reset_index(drop=True)


def without_stryd_delivery_metadata(
    delivery: object,
) -> dict[str, Any]:
    """Remove private provider identity from one historic delivery result."""
    if not isinstance(delivery, Mapping):
        return {}
    payload = dict(delivery)
    if not is_stryd_provider(payload.get("target")):
        return payload
    return {
        key: payload[key]
        for key in ("requested", "status", "window_start", "window_end")
        if key in payload
    }
