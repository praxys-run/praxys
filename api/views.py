"""Shared view-model helpers for API routes and CLI scripts.

These functions extract presentation-ready data from get_dashboard_data().
Both web API routes and CLI skill scripts import from here to stay in sync.
"""
from datetime import date, datetime, timezone

import pandas as pd


def require_admin(user_id: str, db, *, lock: bool = False) -> None:
    """Raise HTTP 403 if the user is not an active superuser.

    Shared guard used by admin-only routes in api/routes/admin.py and
    api/routes/announcements.py. Lives here per the shared-helpers convention.
    """
    from fastapi import HTTPException
    from db.models import User
    query = db.query(User).populate_existing()
    if lock:
        query = query.with_for_update()
    user = query.filter(User.id == user_id).first()
    if not user or not user.is_active or not user.is_superuser:
        raise HTTPException(403, "Admin access required")


def utc_isoformat(dt: datetime | None) -> str | None:
    """Serialize a UTC datetime as an ISO-8601 string with a UTC offset.

    DB-stored timestamps (``User.created_at``, ``UserConnection.last_sync``,
    etc.) are naive ``datetime.utcnow()`` values — no tzinfo, just the wall
    clock in UTC. Calling ``.isoformat()`` on those produces a string like
    ``"2026-04-18T12:34:56"``. Per the ECMAScript spec, browsers parse such
    strings as *local* time, which makes the UI display a time that differs
    from the server's actual UTC moment by the viewer's UTC offset.

    Treat naive inputs as UTC and always emit the ``+00:00`` suffix so
    ``new Date()`` on the frontend lands on the correct instant regardless of
    the viewer's timezone.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def normalize_activity_start_time(
    raw_start_time: object,
    *,
    sample_start_epoch: object = None,
) -> dict:
    """Return an explicit UTC activity-start contract without guessing offsets.

    Connector timestamps that carry ``Z`` or an offset are normalized directly.
    Naive/local activity strings are never relabeled as UTC; when timestamped
    samples exist, their first epoch supplies a safe UTC fallback. Otherwise
    the result is explicitly unavailable with a stable reason code.
    """
    raw_text = ""
    if raw_start_time is not None and not pd.isna(raw_start_time):
        raw_text = str(raw_start_time).strip()

    reason_codes: list[str] = []
    parsed: datetime | None = None
    provenance: str | None = None
    if raw_text:
        try:
            raw_epoch = float(raw_text)
        except (TypeError, ValueError):
            raw_epoch = None
        if (
            raw_epoch is not None
            and 315532800 <= raw_epoch <= 4102444800
        ):
            parsed = datetime.fromtimestamp(raw_epoch, tz=timezone.utc)
            provenance = "activity_start_epoch"
        else:
            normalized = (
                raw_text[:-1] + "+00:00"
                if raw_text.endswith("Z")
                else raw_text
            )
            try:
                candidate = datetime.fromisoformat(normalized)
            except ValueError:
                candidate = None
                reason_codes.append("activity_start_unparseable")
            if candidate is not None:
                if candidate.tzinfo is None:
                    reason_codes.append("activity_start_timezone_unknown")
                else:
                    parsed = candidate.astimezone(timezone.utc)
                    provenance = "activity_start_with_offset"
    else:
        reason_codes.append("activity_start_missing")

    if parsed is None:
        try:
            sample_epoch = float(sample_start_epoch)
        except (TypeError, ValueError):
            sample_epoch = None
        if (
            sample_epoch is not None
            and 315532800 <= sample_epoch <= 4102444800
        ):
            parsed = datetime.fromtimestamp(sample_epoch, tz=timezone.utc)
            provenance = "sample_epoch_fallback"
        else:
            reason_codes.append("sample_start_unavailable")

    if parsed is None:
        return {
            "state": "unavailable",
            "utc": None,
            "timezone": None,
            "provenance": provenance or "none",
            "reason_codes": list(dict.fromkeys(reason_codes)),
        }
    return {
        "state": "available",
        "utc": parsed.isoformat().replace("+00:00", "Z"),
        "timezone": "UTC",
        "provenance": provenance,
        "reason_codes": list(dict.fromkeys(reason_codes)),
    }


def last_activity(activities: list[dict]) -> dict | None:
    """Extract the most recent activity summary."""
    if not activities:
        return None
    act = activities[0]  # already sorted descending by date
    if not act.get("date"):
        return None
    return {
        "date": act["date"],
        "activity_type": act.get("activity_type", ""),
        "distance_km": act.get("distance_km"),
        "duration_sec": act.get("duration_sec"),
        "avg_power": act.get("avg_power"),
        "avg_pace_min_km": act.get("avg_pace_min_km"),
        "rss": act.get("rss"),
    }


def upcoming_workouts(
    plan_df: pd.DataFrame | None, limit: int = 3, *, current_date: date | None = None,
) -> list[dict]:
    """Extract next N planned workouts after the request date."""
    if plan_df is None or plan_df.empty:
        return []
    if "date" not in plan_df.columns:
        return []
    today_str = (current_date or date.today()).isoformat()
    df = plan_df.copy()
    df["_date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["_date"])
    if df.empty:
        return []
    df["date_str"] = df["_date"].dt.strftime("%Y-%m-%d")
    future = df[df["date_str"] > today_str].sort_values("date_str").head(limit)
    result = []
    for _, row in future.iterrows():
        dur = row.get("planned_duration_min")
        if pd.isna(dur) or dur == "":
            dur = row.get("duration_min")
        try:
            duration_min = float(dur) if pd.notna(dur) and dur != "" else None
        except (ValueError, TypeError):
            duration_min = None
        st = row.get("start_time")
        st_iso = None
        if hasattr(st, "isoformat"):
            st_iso = st.isoformat()
            st_iso = st_iso if st_iso.endswith("Z") or "+" in st_iso else st_iso + "Z"
        elif pd.notna(st) and st != "":
            st_iso = str(st)
        result.append({
            "date": row["date_str"],
            "workout_type": str(row.get("workout_type", "")),
            "duration_min": duration_min,
            "description": str(row.get("workout_description", "")),
            "start_time": st_iso,
        })
    return result


def week_load(weekly_review: dict) -> dict | None:
    """Extract current week load vs plan."""
    weeks = weekly_review.get("weeks", [])
    actual = weekly_review.get("actual_load", [])
    planned = weekly_review.get("planned_load", [])
    if not weeks or not actual:
        return None
    return {
        "week_label": weeks[-1],
        "actual": actual[-1],
        "planned": planned[-1] if planned else None,
    }


def science_context(science: dict) -> dict:
    """Extract active science theory metadata for display.

    Returns a dict with theory name, simple description, and key citation
    for each active pillar. Used to show methodology in both web and CLI.
    """
    result: dict = {}
    for pillar in ("load", "recovery", "prediction", "zones", "heat"):
        theory = science.get(pillar)
        if theory is None:
            continue
        citations = []
        for c in getattr(theory, "citations", []):
            cite = {"title": getattr(c, "title", "")}
            year = getattr(c, "year", None)
            if year:
                cite["year"] = year
            url = getattr(c, "url", None)
            if url:
                cite["url"] = url
            citations.append(cite)
        result[pillar] = {
            "id": getattr(theory, "id", "unknown"),
            "name": getattr(theory, "name", "Unknown Theory"),
            "simple_description": getattr(theory, "simple_description", ""),
            "citations": citations,
        }
    return result


def fitness_summary(fitness_fatigue: dict) -> dict:
    """Extract latest CTL/ATL/TSB values from fitness_fatigue arrays."""
    ctl = fitness_fatigue.get("ctl", [])
    atl = fitness_fatigue.get("atl", [])
    tsb = fitness_fatigue.get("tsb", [])
    return {
        "ctl": ctl[-1] if ctl else None,
        "atl": atl[-1] if atl else None,
        "tsb": tsb[-1] if tsb else None,
    }
