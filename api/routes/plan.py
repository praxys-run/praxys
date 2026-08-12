"""Upcoming training plan endpoint with Stryd push integration."""
import json
import logging
import math
import os
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Literal, Mapping

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from analysis.config import (
    LEGACY_PRAXYS_PLAN_SOURCE,
    PRAXYS_PLAN_SOURCE,
    PRAXYS_PLAN_SOURCES,
    effective_athlete_date,
    is_praxys_plan_source,
    load_config_from_db,
    normalize_workout_origin,
)
from analysis.metrics import is_rest_workout
from api import telemetry
from api.auth import (
    get_current_user_id,
    get_data_user_id,
    require_write_access,
)
from api.daily_brief_freshness import PLAN_RESPONSE_VERSION
from api.deps import get_dashboard_data
from api.etag import CACHE_CONTROL, ENDPOINT_SCOPES, ETagGuard, compute_etag
from api.packs import RequestContext
from api.plan_reconciliation import (
    build_plan_reconciliation,
    reconciliation_sync_state,
)
from api.plan_delivery import (
    DeliveryAccountMismatchError,
    DeliveryAccountVerificationError,
    DeliveryBusyError,
    DeliveryCredentialsInvalid,
    DeliveryCredentialsUnavailable,
    DeliveryFinalizationError,
    DeliveryMutationBlockedError,
    DeliveryNotFoundError,
    DeliveryRemovalFailedError,
    DeliveryStartError,
    PlanDeliveryService,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderRequestError,
    capture_delivery_connection_generation,
    guard_delivery_connection,
    load_plan_delivery_adapter,
)
from api.plan_reconciliation import load_plan_reconciliation_item
from api.plan_cleanup import (
    PlanCleanupAmbiguousTargets,
    PlanCleanupRequiresExternalMode,
    cleanup_future_plan_deliveries,
)
from api.plan_adjustments import (
    PlanAdjustmentConflictError,
    PlanAdjustmentNotFoundError,
    list_plan_adjustments,
    undo_plan_adjustment,
)
from api.plan_resolution import (
    PlanResolutionConflict,
    PlanResolutionProviderError,
    PlanResolutionRateLimitError,
    accept_target_version,
    completed_plan_resolution,
    resumable_plan_resolution,
    restore_praxys_version,
)
from db.cache_revision import bump_revisions
from db.models import PlanDelivery, PlanTargetCalendarSync
from db.plan_ledger import (
    delivery_status_for_snapshots,
    has_unresolved_legacy_stryd_corruption,
    import_legacy_stryd_status,
    legacy_stryd_status_path,
    lock_plan_writes,
    normalize_stryd_workout_id,
    plan_snapshot,
    remove_legacy_stryd_status,
    workout_version,
    write_legacy_stryd_status,
)
from db.session import get_db

router = APIRouter()


def _provider_mutation_guard(
    db: Session,
    *,
    user_id: str,
    target: str,
) -> Callable[[], None] | None:
    """Capture a live connection and return its just-in-time mutation fence."""
    try:
        # Pinned local-development credentials intentionally have no
        # UserConnection row; the credential resolver remains their gate.
        generation = capture_delivery_connection_generation(
            db,
            user_id=user_id,
            target=target,
            allow_missing=(target == "stryd"),
        )
    except DeliveryMutationBlockedError as exc:
        label = target.capitalize()
        raise HTTPException(
            status_code=409,
            detail=f"{label} is not actively connected. Reconnect {label} before changing workouts.",
        ) from exc
    if generation is None:
        return None
    return lambda: guard_delivery_connection(
        db,
        user_id=user_id,
        target=target,
        expected_generation=generation,
    )


def _guard_manual_delivery_target(
    db: Session,
    *,
    user_id: str,
    target: str,
) -> None:
    """Fence legacy/manual delivery paths to one configured target."""
    lock_plan_writes(db, user_id)
    config = load_config_from_db(
        user_id,
        db,
    )
    configured_target = config.plan_management.get("execution_target")
    current_date = effective_athlete_date(config)
    if configured_target and configured_target != target:
        raise DeliveryMutationBlockedError("execution_target_changed")
    other_target = db.execute(
        select(PlanDelivery.target).where(
            PlanDelivery.user_id == user_id,
            PlanDelivery.workout_date >= current_date,
            PlanDelivery.state != "removed",
            PlanDelivery.target != target,
        ).limit(1)
    ).scalar_one_or_none()
    if other_target is not None:
        raise DeliveryMutationBlockedError(
            "outstanding_other_execution_target"
        )


def _import_legacy_stryd_status_if_compatible(
    db: Session,
    *,
    user_id: str,
) -> str:
    """Import legacy Stryd state unless another target is selected."""
    from analysis.config import load_config_from_db

    configured_target = load_config_from_db(
        user_id,
        db,
    ).plan_management.get("execution_target")
    if configured_target not in {None, "stryd"}:
        return "target_mismatch"
    return import_legacy_stryd_status(
        db,
        user_id=user_id,
        status_dir=_STRYD_PUSH_STATUS_DIR,
    )


def _canonical_provider_mutation_guard(
    db: Session,
    *,
    user_id: str,
    target: str = "stryd",
    snapshot: Mapping[str, object],
    connection_guard: Callable[[], None] | None,
) -> Callable[[], None]:
    """Fence one provider write on the current canonical workout version."""
    raw_canonical_id = snapshot.get("canonical_id")
    canonical_id = (
        str(raw_canonical_id).strip()
        if raw_canonical_id is not None and pd.notna(raw_canonical_id)
        else ""
    )
    expected_date = date.fromisoformat(str(snapshot["date"]))
    expected_type = str(
        snapshot.get("workout_type") or ""
    ).strip().casefold()
    expected_version = workout_version(snapshot)

    def guard() -> None:
        if connection_guard is not None:
            connection_guard()
        else:
            lock_plan_writes(db, user_id)
        _guard_manual_delivery_target(
            db,
            user_id=user_id,
            target=target,
        )
        current_data = get_dashboard_data(user_id=user_id, db=db)
        all_plans = current_data.get("all_plans", pd.DataFrame())
        if (
            not isinstance(all_plans, pd.DataFrame)
            or all_plans.empty
            or "source" not in all_plans.columns
        ):
            raise DeliveryMutationBlockedError(
                "canonical_changed_during_delivery"
            )
        candidates = all_plans[_praxys_plan_mask(all_plans)]
        if canonical_id and "canonical_id" in candidates.columns:
            candidates = candidates[
                candidates["canonical_id"].fillna("").astype(str)
                == canonical_id
            ]
        else:
            candidates = candidates[
                candidates["date"].astype(str)
                == expected_date.isoformat()
            ]
        matching = [
            plan_snapshot(candidate)
            for _, candidate in candidates.iterrows()
            if (
                canonical_id
                or str(
                    candidate.get("workout_type") or ""
                ).strip().casefold() == expected_type
            )
            and workout_version(plan_snapshot(candidate)) == expected_version
        ]
        if len(matching) != 1:
            raise DeliveryMutationBlockedError(
                "canonical_changed_during_delivery"
            )

    return guard


def _praxys_plan_mask(frame: pd.DataFrame) -> pd.Series:
    """Return a compatibility mask for Praxys-owned plan rows."""
    sources = (
        frame["source"].fillna("").astype(str).str.strip().str.casefold()
    )
    return sources.isin(PRAXYS_PLAN_SOURCES)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_STRYD_PUSH_STATUS_DIR = os.path.join(_DATA_DIR, "ai", "stryd_push_status")


def _stryd_push_status_path(user_id: str) -> str:
    """Return the legacy per-user JSON path used by the one-time importer."""
    return legacy_stryd_status_path(_STRYD_PUSH_STATUS_DIR, user_id)


# Hard cap on how wide a window the client can request. Generous enough
# for any UI that wants a few months of plan view, tight enough that an
# abusive ``?end=2099-12-31`` can't force the server to ship years of rows.
_MAX_WINDOW_DAYS = 365
# Default forward offset when no ``end`` is supplied. ``end`` is
# inclusive, so a forward offset of 14 returns 15 calendar days
# ([today, today+14]) for backward compatibility. Named frontend windows
# send both bounds explicitly and use +6/+13/+27 for exact 7/14/28-day
# inclusive ranges.
_DEFAULT_FORWARD_DAYS = 14


def _resolve_window(
    start: str | None,
    end: str | None,
    *,
    default_start: date,
) -> tuple[date, date]:
    """Parse / default the ?start=&end= query window.

    Accepts ISO ``YYYY-MM-DD`` for both bounds. Either or both may be
    omitted: missing ``start`` defaults to the athlete's current date;
    missing ``end`` defaults to ``start + _DEFAULT_FORWARD_DAYS``. Inverted
    or oversized windows raise 400 — silently clamping would mask bad client
    input.
    """
    try:
        start_d = date.fromisoformat(start) if start else default_start
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid start date: {start!r}"
        ) from exc
    try:
        end_d = (
            date.fromisoformat(end) if end
            else start_d + timedelta(days=_DEFAULT_FORWARD_DAYS)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid end date: {end!r}"
        ) from exc
    if end_d < start_d:
        raise HTTPException(
            status_code=400, detail="Window end must be on or after start",
        )
    if (end_d - start_d).days > _MAX_WINDOW_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Window cannot exceed {_MAX_WINDOW_DAYS} days",
        )
    return start_d, end_d


def _compute_ai_sync_state(
    date_str: str, push_status: dict, stryd_by_date: dict,
) -> str:
    """Sync state of an AI plan row against the user's Stryd calendar.

    - ``synced``     — Either (a) a Stryd row exists at this date and
                       its ``external_id`` matches the ``workout_id`` we
                       logged on push, or (b) the push log has the
                       workout but the next Stryd sync hasn't pulled
                       the row back in yet. Both cases mean "Praxys's
                       version is on Stryd"; the latter is the brief
                       window after a successful POST /plan/push-stryd
                       and before the user's next Stryd sync, and a
                       consumer that doesn't share the frontend's
                       optimistic ``pushStatus`` map (mini-program,
                       MCP) would otherwise see ``not_synced`` and
                       offer to push again.
    - ``mismatch``   — A Stryd row exists at this date but its
                       ``external_id`` is unknown to us (user-edited on
                       Stryd, or we never pushed). The UI uses this to
                       warn before overwriting.
    - ``not_synced`` — No Stryd row, no push log entry: nothing has
                       ever pushed to Stryd for this date.
    """
    stryd_row = stryd_by_date.get(date_str)
    pushed_id = (push_status.get(date_str) or {}).get("workout_id")

    if stryd_row is None:
        return "synced" if pushed_id else "not_synced"

    stryd_external = stryd_row.get("external_id")
    if (
        pushed_id
        and stryd_external is not None
        and pd.notna(stryd_external)
        and str(stryd_external) == str(pushed_id)
    ):
        return "synced"
    return "mismatch"


def _resolve_sync_target(ctx: RequestContext) -> str | None:
    """Name of the platform Praxys plan rows get pushed to.

    Explicit managed-plan intent survives a temporary disconnect. Legacy
    users without that intent retain the existing connected-Stryd fallback.
    """
    configured = ctx.config.plan_management.get("execution_target")
    if configured in {"stryd", "garmin"}:
        return str(configured)
    if "stryd" in (ctx.config.connections or []):
        return "stryd"

    ledger_targets = {
        str(target)
        for target in ctx.db.execute(
            select(PlanDelivery.target).where(
                PlanDelivery.user_id == ctx.user_id,
                PlanDelivery.state != "removed",
            )
        ).scalars()
        if target in {"stryd", "garmin"}
    }
    ledger_targets.update({
        str(target)
        for target in ctx.db.execute(
            select(PlanTargetCalendarSync.target).where(
                PlanTargetCalendarSync.user_id == ctx.user_id,
            )
        ).scalars()
        if target in {"stryd", "garmin"}
    })
    if len(ledger_targets) == 1:
        return ledger_targets.pop()
    return None


@router.get("/plan")
def get_plan(
    request: Request,
    response: Response,
    start: str | None = Query(
        None,
        description="Window start (YYYY-MM-DD). Defaults to today.",
    ),
    end: str | None = Query(
        None,
        description="Window end (YYYY-MM-DD). Defaults to start + 14 days.",
    ),
    viewer_user_id: str = Depends(get_current_user_id),
    user_id: str = Depends(get_data_user_id),
    db: Session = Depends(get_db),
):
    """Return plan rows with stable provider reconciliation details.

    Provider observations are joined by delivery identity and normalized
    content, never collapsed by date. The legacy three-value ``sync_state``
    remains for current clients while ``reconciliation`` exposes the precise
    state and explicit resolution operations needed by managed-plan clients.

    Window framing is mixed into the ETag salt so two clients hitting
    different windows can't bleed cache into each other. The delivery ledger
    is authoritative. A legacy per-user Stryd JSON file,
    when present, is imported idempotently before the ETag is computed.
    """
    db.rollback()
    _import_legacy_stryd_status_if_compatible(
        db,
        user_id=user_id,
    )
    response_today = effective_athlete_date(load_config_from_db(user_id, db))
    start_d, end_d = _resolve_window(
        start,
        end,
        default_start=response_today,
    )
    can_write = viewer_user_id == user_id

    etag = compute_etag(
        db, user_id, ENDPOINT_SCOPES["plan"],
        salt=(
            f"v={PLAN_RESPONSE_VERSION}"
            f"&today={response_today.isoformat()}"
            f"&writable={int(can_write)}"
            f"&start={start_d.isoformat()}"
            f"&end={end_d.isoformat()}"
        ),
    )
    guard = ETagGuard(etag, request.headers.get("if-none-match"))
    if guard.is_match:
        return guard.not_modified()
    guard.apply(response)

    ctx = RequestContext(user_id=user_id, db=db)
    plan_df = ctx.all_plans
    sync_target = _resolve_sync_target(ctx)
    ledger_target = sync_target or "stryd"
    reconciliation = build_plan_reconciliation(
        db,
        user_id=user_id,
        target=ledger_target,
        start=start_d,
        end=end_d,
    )
    current_snapshots: dict[str, dict] = {}
    if not plan_df.empty and "date" in plan_df.columns:
        current_rows = (
            plan_df[_praxys_plan_mask(plan_df)]
            if "source" in plan_df.columns
            else plan_df
        )
        for _, current_row in current_rows.iterrows():
            snapshot = plan_snapshot(current_row)
            current_snapshots[str(snapshot["date"])] = snapshot
    push_status = delivery_status_for_snapshots(
        db,
        user_id=user_id,
        target="stryd",
        current_snapshots=current_snapshots,
    )
    current_delivery_status = delivery_status_for_snapshots(
        db,
        user_id=user_id,
        target=ledger_target,
        current_snapshots=current_snapshots,
        include_prior_versions=False,
    )

    workouts: list[dict] = []

    if not plan_df.empty and "date" in plan_df.columns:
        windowed = plan_df[
            (plan_df["date"] >= start_d) & (plan_df["date"] <= end_d)
        ]
        has_source = "source" in windowed.columns
        praxys_rows = (
            windowed[_praxys_plan_mask(windowed)]
            if has_source
            else windowed
        )
        target_rows = (
            windowed[windowed["source"] == ledger_target]
            if has_source else windowed.iloc[0:0]
        )
        owned_target_external_ids: set[str] = set()
        for raw_id in db.execute(
            select(PlanDelivery.external_id).where(
                PlanDelivery.user_id == user_id,
                PlanDelivery.target == ledger_target,
                PlanDelivery.state != "removed",
                PlanDelivery.external_id.is_not(None),
            )
        ).scalars():
            normalized_id = normalize_stryd_workout_id(raw_id)
            if normalized_id is not None:
                owned_target_external_ids.add(normalized_id)

        if reconciliation is not None:
            for _, row in praxys_rows.sort_values(["date", "id"]).iterrows():
                workout = _row_to_workout(
                    row,
                    source=LEGACY_PRAXYS_PLAN_SOURCE,
                    can_write=can_write,
                    response_today=response_today,
                )
                canonical_id = str(row.get("canonical_id") or "")
                item = reconciliation.canonical_items.get(canonical_id)
                if item is not None:
                    workout["sync_state"] = reconciliation_sync_state(
                        item.state
                    )
                    workout["reconciliation"] = item.to_dict()
                workouts.append(workout)
            for _, row in target_rows.iterrows():
                if normalize_stryd_workout_id(row.get("external_id")) is None:
                    workouts.append(
                        _row_to_workout(
                            row,
                            source=ledger_target,
                            can_write=can_write,
                            response_today=response_today,
                        )
                    )
        else:
            # Compatibility fallback until the first successful calendar
            # snapshot has populated the reconciliation observation ledger.
            stryd_by_date: dict[str, list[pd.Series]] = {}
            for _, srow in target_rows.iterrows():
                sd = srow["date"]
                key = sd.isoformat() if hasattr(sd, "isoformat") else str(sd)
                stryd_by_date.setdefault(key, []).append(srow)

            def _best_stryd_match(
                rows: list[pd.Series],
                wt: str,
            ) -> pd.Series:
                wt_lower = (wt or "").lower()
                for candidate in rows:
                    if (
                        str(candidate.get("workout_type", "")).lower()
                        == wt_lower
                    ):
                        return candidate
                return rows[0]

            for _, row in praxys_rows.sort_values("date").iterrows():
                workout = _row_to_workout(
                    row,
                    source=LEGACY_PRAXYS_PLAN_SOURCE,
                    can_write=can_write,
                    response_today=response_today,
                )
                praxys_workout_type = workout.get("workout_type", "")
                stryd_match_by_date = {
                    d: _best_stryd_match(rows, praxys_workout_type)
                    for d, rows in stryd_by_date.items()
                }
                workout["sync_state"] = _compute_ai_sync_state(
                    workout["date"],
                    current_delivery_status,
                    stryd_match_by_date,
                )
                workouts.append(workout)

            for srows in stryd_by_date.values():
                for srow in srows:
                    external_id = normalize_stryd_workout_id(
                        srow.get("external_id")
                    )
                    if external_id in owned_target_external_ids:
                        continue
                    workouts.append(
                        _row_to_workout(
                            srow,
                            source=ledger_target,
                            can_write=can_write,
                            response_today=response_today,
                        )
                    )

    if reconciliation is not None:
        for item in reconciliation.target_only_items:
            observation = item.observation
            assert observation is not None
            workout = _row_to_workout(
                observation.normalized_workout,
                source=ledger_target,
                can_write=can_write,
                response_today=response_today,
            )
            workout["reconciliation"] = item.to_dict()
            workouts.append(workout)

    workouts.sort(
        key=lambda workout: (
            workout["date"],
            0 if workout["owner"] == PRAXYS_PLAN_SOURCE else 1,
            str(
                (workout.get("reconciliation") or {}).get("id")
                or workout.get("canonical_id")
                or ""
            ),
        )
    )
    owners_by_date: dict[str, set[str]] = {}
    for workout in workouts:
        owners_by_date.setdefault(workout["date"], set()).add(
            workout["owner"]
        )
    overlap_dates = sorted(
        workout_date
        for workout_date, owners in owners_by_date.items()
        if owners == {PRAXYS_PLAN_SOURCE, "external"}
    )
    overlap_date_set = set(overlap_dates)
    for workout in workouts:
        workout["external_overlap"] = workout["date"] in overlap_date_set

    body = {
        "workouts": workouts,
        "stryd_status": push_status,
        "sync_target": sync_target,
        "window": {"start": start_d.isoformat(), "end": end_d.isoformat()},
        "management": {
            "mutation_api_version": 1,
            "can_write": can_write,
            "minimum_date": response_today.isoformat(),
            "external_overlap_dates": overlap_dates,
        },
        "adjustments": list_plan_adjustments(
            db,
            user_id=user_id,
            limit=20,
            start=start_d,
            end=end_d,
        )["items"],
    }
    return Response(
        content=json.dumps(body),
        media_type="application/json",
        headers={"ETag": guard.etag, "Cache-Control": CACHE_CONTROL},
    )


@router.get("/plan/adjustments")
def get_plan_adjustments(
    limit: int = Query(20, ge=1, le=50),
    user_id: str = Depends(get_data_user_id),
    db: Session = Depends(get_db),
) -> dict:
    """Return the user's durable automatic-change notices."""
    return list_plan_adjustments(
        db,
        user_id=user_id,
        limit=limit,
    )


@router.post("/plan/adjustments/{revision_id}/undo")
def restore_plan_adjustment(
    revision_id: str,
    user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    """Undo a supported revision only while its exact result remains current."""
    try:
        return undo_plan_adjustment(
            db,
            user_id=user_id,
            revision_id=revision_id,
        )
    except PlanAdjustmentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Reversible plan adjustment not found",
        ) from exc
    except PlanAdjustmentConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


def _row_to_workout(
    row,
    *,
    source: str,
    can_write: bool,
    response_today: date,
) -> dict:
    """Project a single plan_df row into the JSON shape the UI consumes."""
    row_date = row["date"]
    date_str = (
        row_date.isoformat() if hasattr(row_date, "isoformat") else str(row_date)
    )
    raw_workout_type = row.get("workout_type")
    owned_by_praxys = (
        is_praxys_plan_source(row.get("source"))
        or is_praxys_plan_source(source)
    )
    workout: dict = {
        "date": date_str,
        "source": source,
        "owner": (
            PRAXYS_PLAN_SOURCE
            if owned_by_praxys
            else "external"
        ),
        "origin": normalize_workout_origin(
            row.get("workout_origin"),
            source=row.get("source") or source,
        ),
        "workout_type": (
            "" if pd.isna(raw_workout_type) else str(raw_workout_type)
        ),
        "editable": (
            can_write
            and owned_by_praxys
            and row_date >= response_today
        ),
    }
    activity_type = row.get("activity_type")
    if pd.notna(activity_type) and activity_type != "":
        workout["activity_type"] = str(activity_type)
    structure_version = row.get("workout_structure_version")
    if pd.notna(structure_version) and structure_version != "":
        workout["workout_structure_version"] = str(structure_version)
    structure = row.get("workout_structure")
    if isinstance(structure, dict):
        workout["workout_structure"] = dict(structure)
    elif pd.notna(structure) and structure not in ("", None):
        try:
            parsed_structure = json.loads(str(structure))
        except (TypeError, ValueError):
            parsed_structure = None
        if isinstance(parsed_structure, dict):
            workout["workout_structure"] = parsed_structure
    canonical_id = row.get("canonical_id")
    if pd.notna(canonical_id) and canonical_id:
        workout["canonical_id"] = str(canonical_id)
    if owned_by_praxys:
        workout["workout_version"] = workout_version(plan_snapshot(row))
    st = row.get("start_time")
    if pd.notna(st) and st != "":
        # Absolute instant; client buckets the day in viewer tz.
        iso = st.isoformat() if hasattr(st, "isoformat") else str(st)
        workout["start_time"] = iso if iso.endswith("Z") or "+" in iso else iso + "Z"
    for field, csv_col in (
        ("duration_min", "planned_duration_min"),
        ("distance_km", "planned_distance_km"),
        ("power_min", "target_power_min"),
        ("power_max", "target_power_max"),
        ("hr_min", "target_hr_min"),
        ("hr_max", "target_hr_max"),
        ("pace_min", "target_pace_min"),
        ("pace_max", "target_pace_max"),
        ("description", "workout_description"),
    ):
        val = row.get(csv_col)
        if pd.notna(val) and val != "":
            workout[field] = (
                str(val)
                if field in {"description", "pace_min", "pace_max"}
                else float(val)
            )
    return workout


class PushStrydRequest(BaseModel):
    workout_dates: list[str]
    canonical_ids: list[str] | None = None


class ResolvePlanReconciliationRequest(BaseModel):
    reconciliation_id: str
    action: Literal["restore_praxys", "accept_target"]


class CleanupPlanDeliveriesRequest(BaseModel):
    scope: Literal["future"]
    intent: Literal[
        "leave_managed_mode",
        "switch_execution_target",
    ] = "leave_managed_mode"


def _resolve_stryd_delivery_cp(data: dict) -> float | None:
    """Resolve the CP value used to build Stryd workout blocks."""
    latest_cp = data.get("latest_cp")
    try:
        parsed_latest = float(latest_cp)
    except (TypeError, ValueError):
        parsed_latest = 0.0
    if math.isfinite(parsed_latest) and parsed_latest > 0:
        return parsed_latest

    activities = data.get("activities", pd.DataFrame())
    if not isinstance(activities, pd.DataFrame) or activities.empty:
        return None
    if "cp_estimate" not in activities.columns:
        return None
    valid_cp = activities["cp_estimate"].dropna()
    if valid_cp.empty:
        return None
    try:
        cp_watts = float(valid_cp.iloc[-1])
    except (TypeError, ValueError):
        return None
    return cp_watts if math.isfinite(cp_watts) and cp_watts > 0 else None


@router.post("/plan/push-stryd")
def push_plan_to_stryd(
    request: PushStrydRequest,
    current_user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    """Push selected Praxys plan workouts to Stryd calendar.

    Converts Praxys workouts to Stryd structured format and uploads them.
    """
    db.rollback()
    try:
        _guard_manual_delivery_target(
            db,
            user_id=current_user_id,
            target="stryd",
        )
    except DeliveryMutationBlockedError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Stryd is not the active execution target. "
                "Clean up the prior target before pushing."
            ),
        ) from exc
    _import_legacy_stryd_status_if_compatible(
        db,
        user_id=current_user_id,
    )
    mutation_guard = _provider_mutation_guard(
        db,
        user_id=current_user_id,
        target="stryd",
    )

    service = PlanDeliveryService(
        db=db,
        user_id=current_user_id,
        target="stryd",
        adapter_loader=lambda: load_plan_delivery_adapter(
            db,
            user_id=current_user_id,
            target="stryd",
        ),
    )
    try:
        service.authenticate()
    except DeliveryCredentialsUnavailable as exc:
        raise HTTPException(
            status_code=400,
            detail="No Stryd credentials. Connect Stryd in Settings first.",
        ) from exc
    except DeliveryCredentialsInvalid as exc:
        raise HTTPException(
            status_code=400,
            detail="Stored Stryd credentials are unavailable. Reconnect Stryd.",
        ) from exc
    except ProviderAuthenticationError as exc:
        logger.error("Stryd login failed for user=%s", current_user_id)
        raise HTTPException(
            status_code=502,
            detail="Stryd login failed. Reconnect Stryd and try again.",
        ) from exc

    # Analytical views use one preferred source, but pushing must always
    # select Praxys-owned rows from the complete source set.
    data = get_dashboard_data(user_id=current_user_id, db=db)
    all_plans: pd.DataFrame = data.get("all_plans", pd.DataFrame())
    if all_plans.empty:
        raise HTTPException(status_code=404, detail="No training plan found")
    if "source" not in all_plans.columns:
        raise HTTPException(
            status_code=409,
            detail="Training plan source is unavailable; sync or regenerate the Praxys plan before pushing.",
        )
    plan_df = all_plans[_praxys_plan_mask(all_plans)].copy()
    if plan_df.empty:
        raise HTTPException(status_code=404, detail="No Praxys training plan found")

    cp_watts = _resolve_stryd_delivery_cp(data)
    if not cp_watts:
        raise HTTPException(
            status_code=422,
            detail="Cannot determine Critical Power from your data. Ensure recent activities with power data are synced before pushing to Stryd.",
        )

    db.rollback()
    results = []
    requested_canonical_ids = set(request.canonical_ids or [])

    def _write_legacy_compat(
        workout_date: str,
        workout_id: str,
        delivered_at: datetime | None,
    ) -> None:
        timestamp = delivered_at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        try:
            write_legacy_stryd_status(
                db,
                status_dir=_STRYD_PUSH_STATUS_DIR,
                user_id=current_user_id,
                workout_date=workout_date,
                external_id=workout_id,
                pushed_at=timestamp.isoformat(),
            )
        except (
            OSError,
            ValueError,
            LookupError,
            json.JSONDecodeError,
            SQLAlchemyError,
        ):
            db.rollback()
            logger.exception(
                "Delivery persisted but legacy status dual-write failed for user=%s date=%s",
                current_user_id,
                workout_date,
            )

    for workout_date in request.workout_dates:
        try:
            lock_plan_writes(db, current_user_id)
            current_data = get_dashboard_data(user_id=current_user_id, db=db)
            current_all_plans = current_data.get("all_plans", pd.DataFrame())
            if not isinstance(current_all_plans, pd.DataFrame) or current_all_plans.empty:
                results.append({
                    "date": workout_date,
                    "status": "error",
                    "error": "No workout found for this date",
                })
                db.rollback()
                continue
            if "source" not in current_all_plans.columns:
                results.append({
                    "date": workout_date,
                    "status": "error",
                    "error": "Training plan source is unavailable",
                })
                db.rollback()
                continue
            current_plan = current_all_plans[
                _praxys_plan_mask(current_all_plans)
            ]
            matching = current_plan[
                current_plan["date"].astype(str) == workout_date
            ]
            if requested_canonical_ids:
                if "canonical_id" not in matching.columns:
                    results.append({
                        "date": workout_date,
                        "status": "error",
                        "error": "Canonical workout identity is unavailable",
                    })
                    db.rollback()
                    continue
                matching = matching[
                    matching["canonical_id"]
                    .fillna("")
                    .astype(str)
                    .isin(requested_canonical_ids)
                ]
            if matching.empty:
                results.append({
                    "date": workout_date,
                    "status": "error",
                    "error": (
                        "No requested workout found for this date"
                        if requested_canonical_ids
                        else "No workout found for this date"
                    ),
                })
                db.rollback()
                continue
            current_cp_watts = _resolve_stryd_delivery_cp(current_data)
            if not current_cp_watts:
                results.append({
                    "date": workout_date,
                    "status": "error",
                    "error": "Critical Power became unavailable before delivery",
                })
                db.rollback()
                continue

            sort_columns = [
                column
                for column in ("date", "id", "workout_type")
                if column in matching.columns
            ]
            matching = matching.sort_values(sort_columns)
            include_identity = (
                len(matching.index) > 1
                or bool(requested_canonical_ids)
            )
            for _, row in matching.iterrows():
                workout_type = str(row.get("workout_type", ""))
                identity = (
                    {
                        "canonical_id": str(row.get("canonical_id") or ""),
                        "workout_type": workout_type,
                    }
                    if include_identity
                    else {}
                )
                if is_rest_workout(workout_type):
                    results.append({
                        "date": workout_date,
                        "status": "error",
                        "error": "Rest day — nothing to push",
                        **identity,
                    })
                    continue
                workout = plan_snapshot(row)
                workout_guard = _canonical_provider_mutation_guard(
                    db,
                    user_id=current_user_id,
                    target="stryd",
                    snapshot=workout,
                    connection_guard=mutation_guard,
                )
                outcome = service.deliver(
                    workout,
                    threshold_value=current_cp_watts,
                    observed_external_ids=None,
                    mutation_guard=workout_guard,
                )
                result = {
                    "date": workout_date,
                    "status": outcome.status,
                    **identity,
                }
                if outcome.status == "success" and outcome.external_id:
                    result["workout_id"] = outcome.external_id
                    _write_legacy_compat(
                        workout_date,
                        outcome.external_id,
                        outcome.delivered_at,
                    )
                elif outcome.error:
                    result["error"] = outcome.error
                results.append(result)
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception(
                "Failed to read current plan for Stryd delivery user=%s date=%s",
                current_user_id,
                workout_date,
            )
            results.append({
                "date": workout_date,
                "status": "error",
                "error": f"Could not start delivery: {exc}",
            })
            continue

    return {"results": results}


@router.post("/plan/reconciliation/resolve")
def resolve_plan_reconciliation(
    request: ResolvePlanReconciliationRequest,
    current_user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    """Apply one explicit execution-target/Praxys conflict resolution."""
    db.rollback()
    context = RequestContext(user_id=current_user_id, db=db)
    target = _resolve_sync_target(context)
    if target is None:
        raise HTTPException(
            status_code=409,
            detail="Select a plan execution target before resolving conflicts",
        )
    provider_name = target.capitalize()
    if "@" not in request.reconciliation_id:
        raise HTTPException(
            status_code=400,
            detail="A generation-bearing reconciliation ID is required",
        )
    completed = completed_plan_resolution(
        db,
        user_id=current_user_id,
        target=target,
        reconciliation_id=request.reconciliation_id,
        action=request.action,
    )
    if completed is not None:
        return {
            "status": "resolved",
            "action": completed.action,
            "reconciliation_id": completed.reconciliation_id,
            "revision_id": completed.revision_id,
            "canonical_id": completed.canonical_id,
            "external_id": completed.external_id,
        }
    item = load_plan_reconciliation_item(
        db,
        user_id=current_user_id,
        target=target,
        reconciliation_id=request.reconciliation_id,
        allow_owned_removal_retry=(
            request.action == "restore_praxys"
            and resumable_plan_resolution(
                db,
                user_id=current_user_id,
                target=target,
                reconciliation_id=request.reconciliation_id,
                action=request.action,
            )
        ),
    )
    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Plan reconciliation item not found",
        )
    if request.action not in item.resolutions:
        raise HTTPException(
            status_code=409,
            detail="This resolution is not valid for the current conflict",
        )

    try:
        if request.action == "accept_target":
            result = accept_target_version(
                db,
                user_id=current_user_id,
                target=target,
                item=item,
            )
        else:
            mutation_guard = _provider_mutation_guard(
                db,
                user_id=current_user_id,
                target=target,
            )
            data = get_dashboard_data(user_id=current_user_id, db=db)
            cp_watts = _resolve_stryd_delivery_cp(data)
            if not cp_watts and target == "stryd":
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Cannot determine Critical Power from your data. "
                        "Sync recent power activities before restoring Stryd."
                    ),
                )
            result = restore_praxys_version(
                db,
                user_id=current_user_id,
                target=target,
                item=item,
                threshold_value=cp_watts or 1.0,
                adapter_loader=lambda: load_plan_delivery_adapter(
                    db,
                    user_id=current_user_id,
                    target=target,
                ),
                mutation_guard=mutation_guard,
            )
    except HTTPException:
        db.rollback()
        raise
    except PlanResolutionConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DeliveryMutationBlockedError as exc:
        db.rollback()
        if str(exc) in {
            "canonical_changed_during_restore",
            "reconciliation_changed_during_restore",
        }:
            raise HTTPException(
                status_code=409,
                detail=(
                    "The plan reconciliation changed during restore. "
                    "Refresh the plan and try again."
                ),
            ) from exc
        raise HTTPException(
            status_code=409,
            detail=(
                f"{provider_name} connection changed. "
                f"Reconnect {provider_name} and try again."
            ),
        ) from exc
    except (PlanResolutionRateLimitError, ProviderRateLimitError) as exc:
        db.rollback()
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except PlanResolutionProviderError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except DeliveryNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        DeliveryBusyError,
        DeliveryAccountMismatchError,
    ) as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DeliveryAccountVerificationError as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except DeliveryCredentialsUnavailable as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=(
                f"No {provider_name} credentials. "
                f"Connect {provider_name} in Settings first."
            ),
        ) from exc
    except DeliveryCredentialsInvalid as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=(
                f"Stored {provider_name} credentials are unavailable. "
                f"Reconnect {provider_name}."
            ),
        ) from exc
    except (ProviderAuthenticationError, ProviderRequestError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail=f"{provider_name} restore failed: {exc}",
        ) from exc
    except (
        DeliveryStartError,
        DeliveryFinalizationError,
    ) as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except DeliveryRemovalFailedError as exc:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail=f"{provider_name} delete failed: {exc}",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception(
            "Plan reconciliation resolution failed for user=%s item=%s",
            current_user_id,
            request.reconciliation_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Could not finalize plan reconciliation",
        ) from exc

    telemetry.record_managed_plan_event(
        category="resolution",
        action=request.action,
        outcome="success",
        user_id=current_user_id,
        target=target,
        trigger="user_resolution",
    )
    return {
        "status": "resolved",
        "action": result.action,
        "reconciliation_id": result.reconciliation_id,
        "revision_id": result.revision_id,
        "canonical_id": result.canonical_id,
        "external_id": result.external_id,
    }


@router.post("/plan/deliveries/cleanup")
def cleanup_plan_deliveries(
    request: CleanupPlanDeliveriesRequest,
    current_user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    """Remove future target workouts that belong to the caller's ledger."""
    db.rollback()
    legacy_import = _import_legacy_stryd_status_if_compatible(
        db,
        user_id=current_user_id,
    )
    if (
        legacy_import == "corrupt"
        or has_unresolved_legacy_stryd_corruption(
            db,
            user_id=current_user_id,
        )
    ):
        raise HTTPException(
            status_code=409,
            detail="Legacy Stryd delivery state requires review before cleanup",
        )
    try:
        result = cleanup_future_plan_deliveries(
            db,
            user_id=current_user_id,
            intent=request.intent,
        )
    except PlanCleanupRequiresExternalMode as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PlanCleanupAmbiguousTargets as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if result.target == "stryd":
        for item in result.items:
            if (
                item.status not in {"removed", "already_absent"}
                or not item.external_id
            ):
                continue
            try:
                remove_legacy_stryd_status(
                    db,
                    status_dir=_STRYD_PUSH_STATUS_DIR,
                    user_id=current_user_id,
                    external_id=item.external_id,
                )
            except (
                OSError,
                ValueError,
                LookupError,
                json.JSONDecodeError,
                SQLAlchemyError,
            ):
                db.rollback()
                logger.exception(
                    "Plan cleanup persisted but legacy status removal failed "
                    "user=%s workout=%s",
                    current_user_id,
                    item.external_id,
                )

    return result.to_dict()


@router.delete("/plan/stryd-workout/{workout_id}")
def delete_stryd_workout(
    workout_id: str,
    current_user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    """Delete a previously pushed workout from Stryd."""
    normalized_workout_id = normalize_stryd_workout_id(workout_id)
    if normalized_workout_id is None:
        raise HTTPException(status_code=400, detail="Invalid Stryd workout id")
    workout_id = normalized_workout_id

    db.rollback()
    _import_legacy_stryd_status_if_compatible(
        db,
        user_id=current_user_id,
    )
    mutation_guard = _provider_mutation_guard(
        db,
        user_id=current_user_id,
        target="stryd",
    )
    service = PlanDeliveryService(
        db=db,
        user_id=current_user_id,
        target="stryd",
        adapter_loader=lambda: load_plan_delivery_adapter(
            db,
            user_id=current_user_id,
            target="stryd",
        ),
    )
    try:
        service.remove(
            workout_id,
            mutation_guard=mutation_guard,
        )
    except DeliveryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DeliveryBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DeliveryMutationBlockedError as exc:
        raise HTTPException(
            status_code=409,
            detail="Stryd connection changed. Reconnect Stryd and try again.",
        ) from exc
    except DeliveryAccountMismatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DeliveryAccountVerificationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except DeliveryCredentialsUnavailable as exc:
        raise HTTPException(
            status_code=400,
            detail="No Stryd credentials. Connect Stryd in Settings first.",
        ) from exc
    except DeliveryCredentialsInvalid as exc:
        raise HTTPException(
            status_code=400,
            detail="Stored Stryd credentials are unavailable. Reconnect Stryd.",
        ) from exc
    except ProviderAuthenticationError as exc:
        logger.error("Stryd login failed for user=%s", current_user_id)
        raise HTTPException(
            status_code=502,
            detail="Stryd login failed. Reconnect Stryd and try again.",
        ) from exc
    except DeliveryStartError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc
    except DeliveryRemovalFailedError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Stryd delete failed: {exc}",
        ) from exc
    except DeliveryFinalizationError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    try:
        remove_legacy_stryd_status(
            db,
            status_dir=_STRYD_PUSH_STATUS_DIR,
            user_id=current_user_id,
            external_id=workout_id,
        )
    except (OSError, ValueError, json.JSONDecodeError):
        db.rollback()
        logger.exception(
            "Stryd removal persisted but legacy status dual-write failed for user=%s workout=%s",
            current_user_id,
            workout_id,
        )

    return {"deleted": True, "workout_id": workout_id}
