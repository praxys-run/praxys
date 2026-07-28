"""Upcoming training plan endpoint with Stryd push integration."""
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Mapping

import pandas as pd
import requests
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from analysis.metrics import is_rest_workout
from api.auth import get_data_user_id, require_write_access
from api.daily_brief_freshness import PLAN_RESPONSE_VERSION
from api.deps import get_dashboard_data
from api.etag import CACHE_CONTROL, ENDPOINT_SCOPES, ETagGuard, compute_etag
from api.packs import RequestContext
from db.cache_revision import bump_revisions
from db.plan_ledger import (
    begin_delivery_attempt,
    complete_delivery_attempt,
    delivery_status_for_snapshots,
    find_delivery_by_external_id,
    find_unverified_delivery_for_date,
    get_or_create_delivery,
    import_legacy_stryd_status,
    legacy_stryd_status_path,
    lock_plan_writes,
    normalize_stryd_workout_id,
    plan_snapshot,
    remove_legacy_stryd_status,
    write_legacy_stryd_status,
)
from db.models import TrainingPlan
from db.session import get_db

router = APIRouter()

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
# ([today, today+14]). Frontend pills mirror this offset semantic
# (1wk = +6, 2wk = +13, 4wk = +27 if exact 7/14/28-day inclusive
# windows are needed; current frontend uses +N which yields N+1 days
# inclusive — accepted for the eyebrow's "≈ N weeks" framing).
_DEFAULT_FORWARD_DAYS = 14


def _resolve_window(start: str | None, end: str | None) -> tuple[date, date]:
    """Parse / default the ?start=&end= query window.

    Accepts ISO ``YYYY-MM-DD`` for both bounds. Either or both may be
    omitted: missing ``start`` defaults to today; missing ``end`` defaults
    to ``start + _DEFAULT_FORWARD_DAYS``. Inverted or oversized windows
    raise 400 — silently clamping would mask bad client input.
    """
    today = date.today()
    try:
        start_d = date.fromisoformat(start) if start else today
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
    """Name of the platform AI plan rows get pushed to.

    Today only Stryd is wired up as a write target; surfacing it as a
    derived field (rather than free-form preference) lets the UI decide
    whether to even render sync chrome without sniffing connections.
    """
    return "stryd" if "stryd" in (ctx.config.connections or []) else None


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
    user_id: str = Depends(get_data_user_id),
    db: Session = Depends(get_db),
):
    """Return all plan rows in a window with per-row sync state.

    Each workout carries its ``source`` (``ai`` | ``stryd``). When a date
    has both an AI and a Stryd row, the AI row wins and the Stryd row is
    used purely to derive ``sync_state`` (synced / mismatch / not_synced)
    — that surfaces "did your Praxys-authored plan land on Stryd?" while
    still showing the user every scheduled workout.

    Stryd-only rows surface with ``source='stryd'`` and no ``sync_state``:
    they live natively on Stryd, so the AI-vs-Stryd sync question doesn't
    apply. The UI labels them by source so users who imported a coach's
    plan from Stryd still see something here.

    Window framing is mixed into the ETag salt so two clients hitting
    different windows can't bleed cache into each other. The delivery ledger
    is authoritative. A legacy per-user Stryd JSON file,
    when present, is imported idempotently before the ETag is computed.
    """
    start_d, end_d = _resolve_window(start, end)
    db.rollback()
    import_legacy_stryd_status(
        db,
        user_id=user_id,
        status_dir=_STRYD_PUSH_STATUS_DIR,
    )

    etag = compute_etag(
        db, user_id, ENDPOINT_SCOPES["plan"],
        salt=f"v={PLAN_RESPONSE_VERSION}&start={start_d.isoformat()}&end={end_d.isoformat()}",
    )
    guard = ETagGuard(etag, request.headers.get("if-none-match"))
    if guard.is_match:
        return guard.not_modified()
    guard.apply(response)

    ctx = RequestContext(user_id=user_id, db=db)
    plan_df = ctx.all_plans
    sync_target = _resolve_sync_target(ctx)
    current_snapshots: dict[str, dict] = {}
    if not plan_df.empty and "date" in plan_df.columns:
        current_rows = (
            plan_df[plan_df["source"] == "ai"]
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
        target="stryd",
        current_snapshots=current_snapshots,
        include_prior_versions=False,
    )

    workouts: list[dict] = []

    if not plan_df.empty and "date" in plan_df.columns:
        windowed = plan_df[
            (plan_df["date"] >= start_d) & (plan_df["date"] <= end_d)
        ]
        has_source = "source" in windowed.columns
        ai_rows = (
            windowed[windowed["source"] == "ai"] if has_source else windowed
        )
        stryd_rows = (
            windowed[windowed["source"] == "stryd"]
            if has_source else windowed.iloc[0:0]
        )

        # Stryd allows multiple workouts on the same date (AM run +
        # PM strides, race + shakeout). Group rows-per-date so the
        # AI sync_state derivation can pick the best match by
        # workout_type instead of arbitrarily collapsing to the
        # last-iterated row.
        stryd_by_date: dict[str, list[pd.Series]] = {}
        for _, srow in stryd_rows.iterrows():
            sd = srow["date"]
            key = sd.isoformat() if hasattr(sd, "isoformat") else str(sd)
            stryd_by_date.setdefault(key, []).append(srow)

        def _best_stryd_match(rows: list[pd.Series], wt: str) -> pd.Series:
            """Pick the Stryd row whose workout_type matches ``wt``,
            falling back to the first row when nothing matches. AI
            plans are typically one-per-date, so a match means we're
            comparing apples to apples."""
            wt_lower = (wt or "").lower()
            for r in rows:
                if str(r.get("workout_type", "")).lower() == wt_lower:
                    return r
            return rows[0]

        ai_dates: set[str] = set()
        for _, row in ai_rows.sort_values("date").iterrows():
            workout = _row_to_workout(row, source="ai")
            ai_wt = workout.get("workout_type", "")
            stryd_match_by_date = {
                d: _best_stryd_match(rows, ai_wt)
                for d, rows in stryd_by_date.items()
            }
            workout["sync_state"] = _compute_ai_sync_state(
                workout["date"], current_delivery_status, stryd_match_by_date,
            )
            ai_dates.add(workout["date"])
            workouts.append(workout)

        # Stryd rows on dates the AI plan doesn't cover — show them
        # all (each as its own row) so the user still sees their
        # imported / coach-authored Stryd workouts.
        for date_str, srows in stryd_by_date.items():
            if date_str in ai_dates:
                continue
            for srow in srows:
                workouts.append(_row_to_workout(srow, source="stryd"))

        workouts.sort(key=lambda w: w["date"])

    body = {
        "workouts": workouts,
        "stryd_status": push_status,
        "sync_target": sync_target,
        "window": {"start": start_d.isoformat(), "end": end_d.isoformat()},
    }
    return Response(
        content=json.dumps(body),
        media_type="application/json",
        headers={"ETag": guard.etag, "Cache-Control": CACHE_CONTROL},
    )


def _row_to_workout(row, *, source: str) -> dict:
    """Project a single plan_df row into the JSON shape the UI consumes."""
    row_date = row["date"]
    date_str = (
        row_date.isoformat() if hasattr(row_date, "isoformat") else str(row_date)
    )
    raw_workout_type = row.get("workout_type")
    workout: dict = {
        "date": date_str,
        "source": source,
        "workout_type": (
            "" if pd.isna(raw_workout_type) else str(raw_workout_type)
        ),
    }
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
        ("description", "workout_description"),
    ):
        val = row.get(csv_col)
        if pd.notna(val) and val != "":
            workout[field] = str(val) if field == "description" else float(val)
    return workout


class PushStrydRequest(BaseModel):
    workout_dates: list[str]


@router.post("/plan/push-stryd")
def push_plan_to_stryd(
    request: PushStrydRequest,
    current_user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    """Push selected AI plan workouts to Stryd calendar.

    Converts AI plan workouts to Stryd structured format and uploads them.
    """
    from sync.stryd_sync import (
        _login_api,
        _STRYD_WORKOUT_TYPES,
        build_workout_blocks,
        create_workout_api,
    )

    db.rollback()
    import_legacy_stryd_status(
        db,
        user_id=current_user_id,
        status_dir=_STRYD_PUSH_STATUS_DIR,
    )

    # Load Stryd credentials
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "sync", ".env"))
    email = os.environ.get("STRYD_EMAIL")
    password = os.environ.get("STRYD_PASSWORD")
    if not email or not password:
        raise HTTPException(status_code=400, detail="STRYD_EMAIL / STRYD_PASSWORD not configured")

    # Login to Stryd
    try:
        stryd_user_id, token = _login_api(email, password)
    except Exception as e:
        logger.error("Stryd login failed: %s", e)
        raise HTTPException(status_code=502, detail="Stryd login failed. Check your credentials in sync/.env")

    # Analytical views use one preferred plan source, but pushing must always
    # select the AI-authored rows from the complete source set.
    data = get_dashboard_data(user_id=current_user_id, db=db)
    all_plans: pd.DataFrame = data.get("all_plans", pd.DataFrame())
    if all_plans.empty:
        raise HTTPException(status_code=404, detail="No training plan found")
    if "source" not in all_plans.columns:
        raise HTTPException(
            status_code=409,
            detail="Training plan source is unavailable; sync or regenerate the AI plan before pushing.",
        )
    source = all_plans["source"].fillna("").astype(str).str.strip().str.casefold()
    plan_df = all_plans[source == "ai"].copy()
    if plan_df.empty:
        raise HTTPException(status_code=404, detail="No AI-authored training plan found")

    # Get current CP for block building
    cp_watts = None
    latest_cp = data.get("latest_cp")
    if latest_cp and float(latest_cp) > 0:
        cp_watts = float(latest_cp)
    # Fallback: try from latest activities
    if not cp_watts:
        activities = data.get("activities", pd.DataFrame())
        if not isinstance(activities, pd.DataFrame) or activities.empty:
            pass
        else:
            cp_col = "cp_estimate" if "cp_estimate" in activities.columns else None
            if cp_col:
                valid_cp = activities[cp_col].dropna()
                if not valid_cp.empty:
                    cp_watts = float(valid_cp.iloc[-1])
    if not cp_watts:
        raise HTTPException(
            status_code=422,
            detail="Cannot determine Critical Power from your data. Ensure recent activities with power data are synced before pushing to Stryd.",
        )

    db.rollback()
    results = []

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
        except Exception:
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
            current_source = (
                current_all_plans["source"]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.casefold()
            )
            current_plan = current_all_plans[current_source == "ai"]
            matching = current_plan[
                current_plan["date"].astype(str) == workout_date
            ]
            if matching.empty:
                results.append({
                    "date": workout_date,
                    "status": "error",
                    "error": "No workout found for this date",
                })
                db.rollback()
                continue

            row = matching.iloc[0]
            workout_type = str(row.get("workout_type", ""))
            if is_rest_workout(workout_type):
                results.append({
                    "date": workout_date,
                    "status": "error",
                    "error": "Rest day — nothing to push",
                })
                db.rollback()
                continue
            workout = plan_snapshot(row)

            delivery, delivery_created = get_or_create_delivery(
                db,
                user_id=current_user_id,
                target="stryd",
                snapshot=workout,
            )
            existing_stryd_rows = current_all_plans[
                (current_source == "stryd")
                & (current_all_plans["date"].astype(str) == workout_date)
            ]
            if (
                not existing_stryd_rows.empty
                and not (delivery.state == "synced" and delivery.external_id)
            ):
                results.append({
                    "date": workout_date,
                    "status": "error",
                    "error": (
                        "A Stryd workout already exists on this date and must "
                        "be reconciled before delivery"
                    ),
                })
                if delivery_created:
                    db.delete(delivery)
                    db.commit()
                else:
                    db.rollback()
                continue
            unverified = find_unverified_delivery_for_date(
                db,
                user_id=current_user_id,
                target="stryd",
                workout_date=date.fromisoformat(workout_date),
            )
            if unverified is not None:
                results.append({
                    "date": workout_date,
                    "status": "error",
                    "error": (
                        "Delivery outcome is uncertain; sync Stryd before retrying"
                    ),
                })
                if delivery_created:
                    db.delete(delivery)
                    db.commit()
                else:
                    db.rollback()
                continue
            delivery, attempt, disposition = begin_delivery_attempt(
                db,
                delivery,
                operation="deliver",
            )
            if disposition == "already_complete":
                external_id = str(delivery.external_id)
                delivered_at = delivery.delivered_at
                db.rollback()
                _write_legacy_compat(
                    workout_date,
                    external_id,
                    delivered_at,
                )
                results.append({
                    "date": workout_date,
                    "status": "success",
                    "workout_id": external_id,
                })
                continue
            if disposition == "reconciliation_required":
                results.append({
                    "date": workout_date,
                    "status": "error",
                    "error": (
                        "Delivery outcome is uncertain; sync Stryd before retrying"
                    ),
                })
                if delivery_created:
                    db.delete(delivery)
                    db.commit()
                else:
                    db.rollback()
                continue
            assert attempt is not None
            delivery_id = delivery.id
            attempt_id = attempt.id
            bump_revisions(db, current_user_id, ["plans"])
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.exception(
                "Failed to start Stryd delivery for user=%s date=%s",
                current_user_id,
                workout_date,
            )
            results.append({
                "date": workout_date,
                "status": "error",
                "error": f"Could not start delivery: {exc}",
            })
            continue

        def _record_failure(message: str) -> None:
            try:
                complete_delivery_attempt(
                    db,
                    user_id=current_user_id,
                    delivery_id=delivery_id,
                    attempt_id=attempt_id,
                    attempt_state="failed",
                    error=message,
                )
                bump_revisions(db, current_user_id, ["plans"])
                db.commit()
            except Exception:
                db.rollback()
                logger.exception(
                    "Failed to persist Stryd delivery failure for user=%s date=%s",
                    current_user_id,
                    workout_date,
                )

        def _record_conflict(detail: str) -> None:
            message = (
                "Stryd delivery outcome is uncertain; sync Stryd before retrying"
            )
            try:
                complete_delivery_attempt(
                    db,
                    user_id=current_user_id,
                    delivery_id=delivery_id,
                    attempt_id=attempt_id,
                    attempt_state="conflict",
                    error=f"{message}: {detail}",
                )
                bump_revisions(db, current_user_id, ["plans"])
                db.commit()
            except Exception:
                db.rollback()
                logger.exception(
                    "Failed to persist ambiguous Stryd delivery for user=%s date=%s",
                    current_user_id,
                    workout_date,
                )

        try:
            blocks = build_workout_blocks(workout, cp_watts)
            stryd_type = _STRYD_WORKOUT_TYPES.get(workout_type.lower(), "")
            title = f"{workout_type.replace('_', ' ').title()}"
            description = str(workout.get("workout_description") or "")
        except Exception as exc:
            logger.error(
                "Failed to prepare Stryd workout for %s: %s: %s",
                workout_date,
                type(exc).__name__,
                exc,
            )
            _record_failure(str(exc))
            results.append({
                "date": workout_date,
                "status": "error",
                "error": str(exc),
            })
            continue

        try:
            result = create_workout_api(
                user_id=stryd_user_id,
                token=token,
                workout_date=workout_date,
                title=title,
                blocks=blocks,
                workout_type=stryd_type,
                description=description,
            )
        except (requests.Timeout, requests.ConnectionError) as e:
            _record_conflict(str(e))
            results.append({
                "date": workout_date,
                "status": "error",
                "error": (
                    "Stryd delivery outcome is uncertain; sync Stryd before retrying"
                ),
            })
            continue
        except requests.HTTPError as e:
            detail = str(e)
            status_code = e.response.status_code if e.response is not None else None
            if e.response is not None:
                try:
                    detail = e.response.json().get("message", detail)
                except (ValueError, AttributeError):
                    pass
            if status_code is None or status_code == 408 or status_code >= 500:
                _record_conflict(detail)
                results.append({
                    "date": workout_date,
                    "status": "error",
                    "error": (
                        "Stryd delivery outcome is uncertain; sync Stryd before retrying"
                    ),
                })
                continue
            message = f"Stryd API error: {detail}"
            _record_failure(message)
            results.append({"date": workout_date, "status": "error", "error": message})
            continue
        except Exception as e:
            logger.error(
                "Ambiguous Stryd response for %s: %s: %s",
                workout_date,
                type(e).__name__,
                e,
            )
            _record_conflict(str(e))
            results.append({
                "date": workout_date,
                "status": "error",
                "error": (
                    "Stryd delivery outcome is uncertain; sync Stryd before retrying"
                ),
            })
            continue

        raw_workout_id = result.get("id") if isinstance(result, Mapping) else None
        workout_id = normalize_stryd_workout_id(raw_workout_id)
        if not workout_id:
            _record_conflict("Stryd response did not include a workout id")
            results.append({
                "date": workout_date,
                "status": "error",
                "error": (
                    "Stryd delivery outcome is uncertain; sync Stryd before retrying"
                ),
            })
            continue
        try:
            complete_delivery_attempt(
                db,
                user_id=current_user_id,
                delivery_id=delivery_id,
                attempt_id=attempt_id,
                attempt_state="synced",
                external_id=workout_id,
                response=result,
            )
            bump_revisions(db, current_user_id, ["plans"])
            db.commit()
        except Exception:
            db.rollback()
            logger.exception(
                "Stryd accepted workout but ledger commit failed for user=%s date=%s id=%s",
                current_user_id,
                workout_date,
                workout_id,
            )
            results.append({
                "date": workout_date,
                "status": "error",
                "error": "Stryd accepted the workout, but delivery state could not be finalized",
            })
            continue
        results.append({
            "date": workout_date,
            "status": "success",
            "workout_id": workout_id,
        })
        _write_legacy_compat(
            workout_date,
            workout_id,
            datetime.now(timezone.utc),
        )

    return {"results": results}


@router.delete("/plan/stryd-workout/{workout_id}")
def delete_stryd_workout(
    workout_id: str,
    current_user_id: str = Depends(require_write_access),
    db: Session = Depends(get_db),
) -> dict:
    """Delete a previously pushed workout from Stryd."""
    from sync.stryd_sync import _login_api, delete_workout_api

    normalized_workout_id = normalize_stryd_workout_id(workout_id)
    if normalized_workout_id is None:
        raise HTTPException(status_code=400, detail="Invalid Stryd workout id")
    workout_id = normalized_workout_id

    db.rollback()
    import_legacy_stryd_status(
        db,
        user_id=current_user_id,
        status_dir=_STRYD_PUSH_STATUS_DIR,
    )
    lock_plan_writes(db, current_user_id)
    delivery = find_delivery_by_external_id(
        db,
        user_id=current_user_id,
        target="stryd",
        external_id=workout_id,
    )
    if delivery is None:
        db.rollback()
        raise HTTPException(
            status_code=404,
            detail="No Stryd delivery found for this user and workout",
        )

    previous_state = delivery.state
    if previous_state == "delivering" and delivery.external_id:
        # A stale remove attempt can be retried after its lease expires.
        # Restore the known pre-remove state if the repeated DELETE fails.
        previous_state = "synced"
    try:
        delivery, attempt, disposition = begin_delivery_attempt(
            db,
            delivery,
            operation="remove",
        )
        if disposition == "already_complete":
            db.rollback()
            try:
                remove_legacy_stryd_status(
                    db,
                    status_dir=_STRYD_PUSH_STATUS_DIR,
                    user_id=current_user_id,
                    external_id=workout_id,
                )
            except Exception:
                logger.exception(
                    "Legacy removal cleanup failed for user=%s workout=%s",
                    current_user_id,
                    workout_id,
                )
            return {"deleted": True, "workout_id": workout_id}
        if disposition == "reconciliation_required":
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Stryd workout delivery is already being updated",
            )
        assert attempt is not None
        delivery_id = delivery.id
        attempt_id = attempt.id
        bump_revisions(db, current_user_id, ["plans"])
        db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception(
            "Failed to start Stryd removal for user=%s workout=%s",
            current_user_id,
            workout_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Could not start Stryd workout removal",
        ) from exc

    def _record_removal_failure(message: str) -> bool:
        try:
            updated = complete_delivery_attempt(
                db,
                user_id=current_user_id,
                delivery_id=delivery_id,
                attempt_id=attempt_id,
                attempt_state="failed",
                delivery_state=previous_state,
                error=message,
            )
            current_delivery = find_delivery_by_external_id(
                db,
                user_id=current_user_id,
                target="stryd",
                external_id=workout_id,
            )
            removed_won = (
                not updated
                and current_delivery is not None
                and current_delivery.state == "removed"
            )
            bump_revisions(db, current_user_id, ["plans"])
            db.commit()
            return removed_won
        except Exception:
            db.rollback()
            logger.exception(
                "Failed to persist Stryd removal failure for user=%s workout=%s",
                current_user_id,
                workout_id,
            )
            return False

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", "sync", ".env"))
    email = os.environ.get("STRYD_EMAIL")
    password = os.environ.get("STRYD_PASSWORD")
    if not email or not password:
        _record_removal_failure("STRYD_EMAIL / STRYD_PASSWORD not configured")
        raise HTTPException(
            status_code=400,
            detail="STRYD_EMAIL / STRYD_PASSWORD not configured",
        )

    try:
        stryd_user_id, token = _login_api(email, password)
    except Exception as e:
        logger.error("Stryd login failed: %s", e)
        if _record_removal_failure(str(e)):
            return {"deleted": True, "workout_id": workout_id}
        raise HTTPException(
            status_code=502,
            detail="Stryd login failed. Check your credentials in sync/.env",
        )

    already_absent = False
    try:
        delete_workout_api(stryd_user_id, token, workout_id)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            already_absent = True
        else:
            if _record_removal_failure(str(e)):
                return {"deleted": True, "workout_id": workout_id}
            raise HTTPException(status_code=502, detail=f"Stryd delete failed: {e}")
    except Exception as e:
        logger.error("Stryd delete failed: %s", e)
        if _record_removal_failure(str(e)):
            return {"deleted": True, "workout_id": workout_id}
        raise HTTPException(status_code=502, detail="Failed to delete from Stryd")

    try:
        complete_delivery_attempt(
            db,
            user_id=current_user_id,
            delivery_id=delivery_id,
            attempt_id=attempt_id,
            attempt_state="removed",
            external_id=workout_id,
            response={"already_absent": already_absent},
        )
        db.query(TrainingPlan).filter(
            TrainingPlan.user_id == current_user_id,
            TrainingPlan.source == "stryd",
            TrainingPlan.external_id == workout_id,
        ).delete(synchronize_session=False)
        bump_revisions(db, current_user_id, ["plans"])
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception(
            "Stryd workout deleted but ledger finalization failed for user=%s workout=%s",
            current_user_id,
            workout_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Stryd workout was deleted, but delivery state could not be finalized",
        ) from exc
    try:
        remove_legacy_stryd_status(
            db,
            status_dir=_STRYD_PUSH_STATUS_DIR,
            user_id=current_user_id,
            external_id=workout_id,
        )
    except Exception:
        logger.exception(
            "Stryd removal persisted but legacy status dual-write failed for user=%s workout=%s",
            current_user_id,
            workout_id,
        )

    return {"deleted": True, "workout_id": workout_id}
