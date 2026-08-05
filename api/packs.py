"""Per-endpoint dashboard packs (issue #146).

Each pack is a small, composable function returning only the data a single
endpoint actually serves. The 5 endpoints (`/api/today`, `/api/training`,
`/api/goal`, `/api/history`, `/api/science`) used to share a single
`get_dashboard_data()` that did ~22 top-level computations, then each
endpoint dropped 60-85% of the result. With packs, an endpoint pays only
for the work it actually consumes.

A `RequestContext` holds the request-scoped cache so that within a single
HTTP request, shared inputs (config, deduplicated activities, thresholds,
science, EWMA load series) are computed exactly once even when the route
calls multiple packs.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, time, timedelta, timezone
from functools import cached_property

import pandas as pd

from analysis.config import is_praxys_managed_plan, load_config_from_db
from analysis.data_loader import (
    load_activity_records,
    load_activity_sample_coverage,
    load_activity_samples,
    load_data_from_db,
    load_fitness_history,
    load_heat_adaptation_inputs,
    select_plan_for_analysis,
    select_preferred_source,
)
from analysis.metrics import (
    ACTIVITY_ANALYSIS_SCHEMA_VERSION,
    ACTIVITY_RESEARCH_SCHEMA_VERSION,
    ENVIRONMENT_CONTEXT_MODEL_VERSION,
    HEAT_ADAPTATION_MODEL_VERSION,
    HEAT_ELIGIBLE_ACTIVITY_TYPES,
    HEAT_LOOKBACK_DAYS,
    HEAT_SAMPLE_MAX_INTERVAL_SEC,
    PRE_ACTIVITY_LOAD_MODEL_VERSION,
    STABLE_SEGMENT_MODEL_VERSION,
    compute_heat_adaptation,
    compute_distribution_match_pct,
    compute_ewma_load,
    has_sufficient_load_history,
    compute_tsb,
    daily_training_signal,
    derive_stable_power_segments,
    get_distance_config,
    project_tsb,
)
from analysis.providers.models import ThresholdEstimate
from analysis.science import load_active_science
from analysis.training_base import get_display_config
from api.deps import (
    _build_activities_list,
    _build_compliance,
    _build_race_countdown,
    _build_sleep_perf,
    _build_threshold_trend_chart,
    _build_warnings,
    _build_workout_flags,
    _compute_daily_load,
    _compute_load_compliance_summary,
    _compute_diagnosis,
    _compute_recovery_analysis,
    _compute_threshold_data,
    _ensure_env,
    _estimate_plan_daily_loads,
    _get_todays_plan,
    _plan_row_duration_sec,
    _plan_workout_load,
    _sort_activity_splits,
    _resolve_thresholds,
    _recovery_for_guidance,
    _select_prediction_method,
)
from api.views import upcoming_workouts

logger = logging.getLogger(__name__)


def _dedup_activities_by_primary_source(
    activities: pd.DataFrame, primary_source: str | None,
) -> pd.DataFrame:
    """Drop secondary-source duplicates of the same activity.

    When two providers (Garmin + Stryd, COROS + Stryd, etc.) sync the
    same workout, the rows share a date and have ``duration_sec`` within
    10% of each other. Keep the row whose ``source`` matches
    ``primary_source`` — typically the user's ``preferences.activities``,
    but the /api/history route lets the request override it via a
    ``?source=`` query param, which is why this is a free function.

    No-op when ``primary_source`` is empty, the frame is empty, or the
    frame doesn't carry a ``source`` column (the rest of the app expects
    that column on real data, but tests and bare CSV imports may omit
    it). Index is reset on the way out so iloc-based pagination is
    contiguous.
    """
    if (
        not primary_source
        or activities.empty
        or "source" not in activities.columns
    ):
        return activities

    merged = activities.copy()
    merged["_date"] = pd.to_datetime(merged["date"]).dt.date
    merged["_dur"] = pd.to_numeric(
        merged.get("duration_sec", 0), errors="coerce",
    ).fillna(0)
    merged["_is_primary"] = merged["source"] == primary_source

    keep_mask = pd.Series(True, index=merged.index)
    for _dt, group in merged.groupby("_date"):
        if len(group) <= 1:
            continue
        primary = group[group["_is_primary"]]
        others = group[~group["_is_primary"]]
        for oidx, orow in others.iterrows():
            for _, prow in primary.iterrows():
                if prow["_dur"] > 0 and orow["_dur"] > 0:
                    ratio = abs(prow["_dur"] - orow["_dur"]) / max(
                        prow["_dur"], orow["_dur"]
                    )
                    if ratio < 0.10:
                        keep_mask[oidx] = False
                        break
    return (
        merged[keep_mask]
        .drop(columns=["_date", "_dur", "_is_primary"], errors="ignore")
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# Request-scoped cache
# ---------------------------------------------------------------------------


class RequestContext:
    """Request-scoped cache for inputs shared across packs.

    Each ``cached_property`` is computed at most once per ``RequestContext``
    instance, so a route calling multiple packs in the same request pays
    for shared work (config, deduplicated activities, thresholds, science,
    EWMA load series) only once. Construct one ``RequestContext`` per
    request and pass it to each pack the endpoint needs.
    """

    def __init__(self, user_id: str, db) -> None:
        _ensure_env()
        self.user_id = user_id
        self.db = db
        self.today = date.today()

    # --- raw inputs --------------------------------------------------------

    @cached_property
    def config(self):
        return load_config_from_db(self.user_id, self.db)

    @cached_property
    def _data(self) -> dict:
        return load_data_from_db(self.user_id, self.db)

    @cached_property
    def merged_activities(self) -> pd.DataFrame:
        """Activities deduplicated by primary-source preference."""
        return _dedup_activities_by_primary_source(
            self._data["activities"],
            self.config.preferences.get("activities"),
        )

    @cached_property
    def splits(self) -> pd.DataFrame:
        return self._data["splits"]

    @cached_property
    def samples(self) -> pd.DataFrame:
        """Per-second stream samples for recent activities (last 8 weeks).

        Returns an empty DataFrame when the activity_samples table has no rows
        for this user — gracefully degrades to split-based zone analysis.
        """
        from datetime import timedelta
        cutoff = self.today - timedelta(weeks=8)
        merged = self.merged_activities
        if merged.empty or "activity_id" not in merged.columns or "date" not in merged.columns:
            return pd.DataFrame()
        recent_aids = list(
            merged[pd.to_datetime(merged["date"]).dt.date >= cutoff]["activity_id"]
            .astype(str).unique()
        )
        if not recent_aids:
            return pd.DataFrame()
        return load_activity_samples(self.user_id, self.db, recent_aids)

    @cached_property
    def fitness_history(self) -> pd.DataFrame:
        """Dated fitness values with provider provenance intact."""
        return load_fitness_history(self.user_id, self.db)

    @cached_property
    def recovery_history(self) -> pd.DataFrame:
        """Return all dated recovery providers before canonical selection."""
        return self._data["recovery"]

    @cached_property
    def recovery(self) -> pd.DataFrame:
        return select_preferred_source(
            self.recovery_history,
            self.config.preferences.get("recovery"),
        )

    @cached_property
    def all_plans(self) -> pd.DataFrame:
        """All plan sources for management and sync-state comparisons."""
        return self._data["plan"]

    @cached_property
    def plan(self) -> pd.DataFrame:
        """Canonical plan source for analysis and same-day guidance."""
        return select_plan_for_analysis(self.all_plans, self.config)

    @cached_property
    def thresholds(self) -> ThresholdEstimate:
        return _resolve_thresholds(
            self.config, user_id=self.user_id, db=self.db,
        )

    @cached_property
    def latest_cp_watts(self) -> float | None:
        cp = self.thresholds.cp_watts
        return cp if cp and cp > 0 else None

    @cached_property
    def heat_adaptation(self) -> dict:
        """Qualitative heat-adaptation status from bounded recent evidence."""
        activities, splits, sample_power = load_heat_adaptation_inputs(
            self.user_id,
            self.db,
            activity_source=(
                self.config.preferences.get("activities")
                or "garmin"
            ),
            current_date=self.today,
            sample_max_interval_sec=HEAT_SAMPLE_MAX_INTERVAL_SEC,
            lookback_days=HEAT_LOOKBACK_DAYS,
            eligible_activity_types=HEAT_ELIGIBLE_ACTIVITY_TYPES,
        )
        return compute_heat_adaptation(
            activities,
            splits,
            sample_power,
            cp_watts=self.latest_cp_watts,
            cp_source=self.thresholds.cp_source,
            cp_power_provider=self.thresholds.cp_power_provider,
            current_date=self.today,
        )

    @cached_property
    def science(self) -> dict:
        locale = (
            self.config.language
            if self.config.language in {"en", "zh"}
            else None
        )
        return load_active_science(
            self.config.science, self.config.zone_labels, locale=locale,
        )

    @cached_property
    def display(self) -> dict:
        return get_display_config(self.config.training_base)

    # --- derived series ----------------------------------------------------

    @cached_property
    def _load_constants(self) -> tuple[int, int]:
        load_theory = self.science.get("load")
        params = load_theory.params if load_theory else {}
        return (
            int(params.get("ctl_time_constant", 42)),
            int(params.get("atl_time_constant", 7)),
        )

    @cached_property
    def fitness_series(self) -> dict:
        """Daily load + EWMA-derived CTL/ATL/TSB over the full data window."""
        merged = self.merged_activities
        ctl_tc, atl_tc = self._load_constants
        earliest = self.today - timedelta(days=365)
        if not merged.empty and "date" in merged.columns:
            first_date = pd.to_datetime(merged["date"]).min()
            if pd.notna(first_date):
                earliest = first_date.date()
        full_range = pd.date_range(earliest, self.today)
        daily_load = _compute_daily_load(
            merged, full_range, self.config, self.thresholds,
        )
        ctl = compute_ewma_load(daily_load, time_constant=ctl_tc)
        atl = compute_ewma_load(daily_load, time_constant=atl_tc)
        tsb = compute_tsb(ctl, atl)
        return {
            "daily_load": daily_load,
            "ctl": ctl,
            "atl": atl,
            "tsb": tsb,
            "earliest": earliest,
        }

    @cached_property
    def causal_load_history(self) -> dict:
        """Stored-load PMC series that can be sampled without future leakage.

        This intentionally never recomputes historical activity load from a
        later threshold. Power/HR/pace bases use their stored RSS/TRIMP/rTSS
        value, with ``load_score`` as the only fallback. The full causal series
        is built once per request; reading an earlier date cannot depend on
        later activities.
        """
        merged = self.merged_activities
        ctl_days, atl_days = self._load_constants
        empty = {
            "daily_load": pd.Series(dtype=float),
            "ctl": pd.Series(dtype=float),
            "atl": pd.Series(dtype=float),
            "tsb": pd.Series(dtype=float),
            "activity_dates": pd.Series(dtype=object),
            "primary_load_dates": pd.Series(dtype=object),
            "fallback_load_dates": pd.Series(dtype=object),
            "missing_load_dates": pd.Series(dtype=object),
            "primary_column": {
                "power": "rss",
                "hr": "trimp",
                "pace": "rtss",
            }.get(self.config.training_base, "load_score"),
            "ctl_days": ctl_days,
            "atl_days": atl_days,
        }
        if merged.empty or "date" not in merged.columns:
            return empty

        frame = merged.copy()
        frame["_analysis_date"] = pd.to_datetime(
            frame["date"],
            errors="coerce",
        ).dt.normalize()
        frame = frame[frame["_analysis_date"].notna()].copy()
        if frame.empty:
            return empty

        primary_column = empty["primary_column"]
        primary = pd.to_numeric(
            frame.get(
                primary_column,
                pd.Series(index=frame.index, dtype=float),
            ),
            errors="coerce",
        )
        fallback = pd.to_numeric(
            frame.get(
                "load_score",
                pd.Series(index=frame.index, dtype=float),
            ),
            errors="coerce",
        )
        primary_valid = primary.gt(0)
        fallback_valid = ~primary_valid & fallback.gt(0)
        frame["_analysis_load"] = primary.where(primary_valid)
        frame.loc[fallback_valid, "_analysis_load"] = fallback.loc[
            fallback_valid
        ]
        missing_load = ~primary_valid & ~fallback_valid

        first_date = frame["_analysis_date"].min()
        last_date = frame["_analysis_date"].max()
        date_range = pd.date_range(first_date, last_date, freq="D")
        daily_load = (
            frame.loc[frame["_analysis_load"].notna()]
            .groupby("_analysis_date")["_analysis_load"]
            .sum()
            .reindex(date_range, fill_value=0.0)
            .astype(float)
        )
        ctl = compute_ewma_load(daily_load, ctl_days)
        atl = compute_ewma_load(daily_load, atl_days)
        return {
            "daily_load": daily_load,
            "ctl": ctl,
            "atl": atl,
            "tsb": compute_tsb(ctl, atl),
            "activity_dates": frame["_analysis_date"],
            "primary_load_dates": frame.loc[
                primary_valid,
                "_analysis_date",
            ],
            "fallback_load_dates": frame.loc[
                fallback_valid,
                "_analysis_date",
            ],
            "missing_load_dates": frame.loc[
                missing_load,
                "_analysis_date",
            ],
            "primary_column": primary_column,
            "ctl_days": ctl_days,
            "atl_days": atl_days,
        }

    @cached_property
    def projection(self) -> dict:
        ctl_tc, atl_tc = self._load_constants
        fs = self.fitness_series
        days = 14
        future_loads = _estimate_plan_daily_loads(
            self.plan, self.today, days, self.thresholds,
            self.config.training_base,
        )
        current_ctl = float(fs["ctl"].iloc[-1]) if not fs["ctl"].empty else 0.0
        current_atl = float(fs["atl"].iloc[-1]) if not fs["atl"].empty else 0.0
        proj_ctl, proj_atl, proj_tsb = project_tsb(
            current_ctl, current_atl, future_loads,
            ctl_tc=ctl_tc, atl_tc=atl_tc,
        )
        proj_dates = [
            (self.today + timedelta(days=i + 1)).strftime("%Y-%m-%d")
            for i in range(days)
        ]
        return {
            "ctl": proj_ctl,
            "atl": proj_atl,
            "tsb": proj_tsb,
            "dates": proj_dates,
        }

    @cached_property
    def threshold_data(self) -> dict:
        # ``fitness_data`` is the wide-pivoted fitness frame already loaded
        # by ``self._data``. Passing it through keeps HR/pace requests off
        # a second ``load_data_from_db`` round-trip; power requests don't
        # consult it but the kwarg is still cheap to forward.
        latest, trend, cp_values, pairs = _compute_threshold_data(
            self.merged_activities, self.config,
            user_id=self.user_id, db=self.db,
            fitness_data=self._data.get("fitness"),
        )
        return {
            "latest": latest,
            "trend": trend,
            "cp_values": cp_values,
            "pairs": pairs,
        }

    @cached_property
    def cp_trend_chart(self) -> dict:
        return _build_threshold_trend_chart(
            self.merged_activities, self.config,
            user_id=self.user_id, db=self.db,
            fitness_data=self._data.get("fitness"),
        )

    @cached_property
    def recovery_analysis(self) -> dict:
        recovery_theory = self.science.get("recovery")
        analysis, _, _, _ = _compute_recovery_analysis(
            self.recovery,
            recovery_params=recovery_theory.params if recovery_theory else None,
            current_date=self.today,
        )
        return analysis

    @cached_property
    def data_as_of(self) -> str | None:
        """ISO-8601 timestamp of the newest recovery or activity row.

        This is deliberately source-data freshness, not sync-attempt or insight
        generation time. Neither a no-op sync nor a durable insight write may
        make yesterday's HRV, sleep, or activity look freshly synced.

        Date-only rows are anchored at noon UTC. Noon is the symmetry point for
        real-world timezones: unlike midnight or end-of-day UTC, it avoids
        shifting the displayed calendar date for almost every user.
        """
        candidates: list[datetime] = []
        date_anchor = time(12, 0, 0)

        recovery = self.recovery
        if (
            hasattr(recovery, "empty")
            and not recovery.empty
            and "date" in recovery.columns
        ):
            latest = pd.to_datetime(recovery["date"], errors="coerce").max()
            if pd.notna(latest):
                candidates.append(
                    datetime.combine(
                        latest.date(), date_anchor, tzinfo=timezone.utc
                    )
                )

        merged = self.merged_activities
        if not merged.empty and "date" in merged.columns:
            latest_a = pd.to_datetime(merged["date"], errors="coerce").max()
            if pd.notna(latest_a):
                candidates.append(
                    datetime.combine(
                        latest_a.date(), date_anchor, tzinfo=timezone.utc
                    )
                )

        if not candidates:
            return None
        out = max(candidates).astimezone(timezone.utc).replace(tzinfo=None)
        return out.isoformat() + "Z"

    @cached_property
    def data_meta(self) -> dict:
        merged = self.merged_activities
        recovery = self.recovery
        chart = self.cp_trend_chart
        activity_count = len(merged) if not merged.empty else 0
        data_days = (
            (self.today - self.fitness_series["earliest"]).days
            if not merged.empty else 0
        )
        cp_point_count = len(chart.get("dates", [])) if chart else 0
        has_recovery = (
            not recovery.empty if hasattr(recovery, "empty") else bool(recovery)
        )
        ctl_time_constant, _ = self._load_constants
        return {
            "activity_count": activity_count,
            "data_days": data_days,
            "cp_points": cp_point_count,
            "has_recovery": has_recovery,
            "load_time_constant_days": ctl_time_constant,
            "pmc_sufficient": has_sufficient_load_history(
                data_days, ctl_time_constant,
            ),
            "cp_trend_sufficient": cp_point_count >= 3,
        }

    @cached_property
    def science_notes(self) -> dict:
        return {
            pillar: {
                "name": theory.name,
                "description": getattr(theory, "simple_description", "") or "",
                "citations": [
                    {
                        "label": getattr(c, "title", getattr(c, "key", "")),
                        "url": getattr(c, "url", ""),
                    }
                    for c in (getattr(theory, "citations", None) or [])
                    if getattr(c, "url", None)
                ],
            }
            for pillar, theory in self.science.items()
            if theory and hasattr(theory, "name")
        }

    @cached_property
    def tsb_zones(self) -> list[dict]:
        load_theory = self.science.get("load")
        return [
            {"min": z.min, "max": z.max, "label": z.label, "color": z.color}
            for z in (load_theory.tsb_zones_labeled if load_theory else [])
        ]


# ---------------------------------------------------------------------------
# Local helpers (small enough to inline; not reused outside packs)
# ---------------------------------------------------------------------------


def _build_last_activity(merged: pd.DataFrame) -> dict | None:
    """Pull the single most recent activity for the Today widget.

    The Today page only renders the latest activity card, so building the
    full activities list (with splits) just to take ``activities[0]`` is
    wasted work. This helper returns the same shape ``api.views.last_activity``
    consumes, but skips the iteration over every activity and split.
    """
    if merged.empty or "date" not in merged.columns:
        return None
    sorted_m = merged.sort_values("date", ascending=False)
    if sorted_m.empty:
        return None
    row = sorted_m.iloc[0]
    if pd.isna(row.get("date")):
        return None
    return {
        "date": str(row["date"]),
        "activity_type": row.get("activity_type", "running"),
        "distance_km": (
            round(float(row.get("distance_km", 0)), 2)
            if pd.notna(row.get("distance_km")) else None
        ),
        "duration_sec": (
            int(row.get("duration_sec", 0))
            if pd.notna(row.get("duration_sec")) else None
        ),
        "avg_power": (
            round(float(row.get("avg_power", 0)), 1)
            if pd.notna(row.get("avg_power")) else None
        ),
        "avg_pace_min_km": (
            str(row.get("avg_pace_min_km", ""))
            if pd.notna(row.get("avg_pace_min_km")) else None
        ),
        "rss": (
            round(float(row.get("rss", 0)), 1)
            if pd.notna(row.get("rss")) else None
        ),
    }


def _current_week_load(
    daily_load: pd.Series, plan: pd.DataFrame, training_base: str,
    thresholds, today: date,
) -> dict | None:
    """Current ISO week's actual + planned load (single-week extract).

    Cheaper than ``_build_compliance`` for the 8-week chart when the caller
    (Today widget) only renders the latest entry. Uses ISO week numbers to
    match ``_build_compliance`` so the labels stay consistent.
    """
    if daily_load is None or daily_load.empty:
        return None
    today_ts = pd.Timestamp(today)
    week_year = today_ts.isocalendar().year
    week_num = today_ts.isocalendar().week

    df = daily_load.reset_index()
    df.columns = ["date", "load"]
    df["_d"] = pd.to_datetime(df["date"])
    df["_y"] = df["_d"].dt.isocalendar().year
    df["_w"] = df["_d"].dt.isocalendar().week
    actual_rows = df[(df["_y"] == week_year) & (df["_w"] == week_num)]
    if actual_rows.empty:
        return None
    actual = round(float(actual_rows["load"].sum()), 1)

    planned: float | None = None
    if not plan.empty and "date" in plan.columns:
        plan_copy = plan.copy()
        plan_copy["_d"] = pd.to_datetime(plan_copy["date"], errors="coerce")
        plan_copy = plan_copy.dropna(subset=["_d"])
        plan_copy["_y"] = plan_copy["_d"].dt.isocalendar().year
        plan_copy["_w"] = plan_copy["_d"].dt.isocalendar().week
        plan_week = plan_copy[
            (plan_copy["_y"] == week_year) & (plan_copy["_w"] == week_num)
        ]
        if not plan_week.empty:
            total = 0.0
            for _, row in plan_week.iterrows():
                dur_sec = _plan_row_duration_sec(row)
                total += _plan_workout_load(
                    row, dur_sec, training_base, thresholds,
                )
            planned = round(total, 1)

    return {
        "week_label": f"W{int(week_num)}",
        "actual": actual,
        "planned": planned,
    }


# ---------------------------------------------------------------------------
# Packs — each returns ONLY the keys its endpoint needs.
# ---------------------------------------------------------------------------


def get_signal_pack(ctx: RequestContext) -> dict:
    """Today's training signal + sparkline + recovery + warnings.

    Used by ``/api/today``. Pays for: full EWMA load (for current TSB),
    recovery analysis, warnings, projection (for sparkline tail). Does NOT
    pay for diagnosis, threshold trends, weekly compliance, full activity
    list, workout flags, or sleep-performance scatter.
    """
    fs = ctx.fitness_series
    proj = ctx.projection
    current_tsb = float(fs["tsb"].iloc[-1]) if not fs["tsb"].empty else 0.0
    guidance_tsb = current_tsb if ctx.data_meta["pmc_sufficient"] else None
    recovery_analysis = ctx.recovery_analysis
    guidance_recovery = _recovery_for_guidance(recovery_analysis)

    planned_today, planned_detail = _get_todays_plan(
        ctx.plan,
        ctx.today,
        fallback_plan=(
            None if is_praxys_managed_plan(ctx.config) else ctx.all_plans
        ),
    )
    load_theory = ctx.science.get("load")
    recovery_theory = ctx.science.get("recovery")
    recovery_params = recovery_theory.params if recovery_theory else {}
    signal = daily_training_signal(
        guidance_recovery, guidance_tsb, planned_today,
        planned_detail=planned_detail,
        signal_thresholds=load_theory.signal if load_theory else None,
        recovery_thresholds=recovery_params,
        hrv_only=True,
    )
    warnings = _build_warnings(
        guidance_recovery,
        guidance_tsb,
        ctx.config,
        data_dir=None,
        latest_cp_watts=ctx.latest_cp_watts,
        cv_threshold=float(recovery_params.get("cv_threshold", 10)),
        tsb_caution_threshold=float(
            (load_theory.signal if load_theory else {}).get("tsb_high_fatigue", -20)
        ),
    )

    # Sparkline uses the last 14 days of TSB. Take the tail directly
    # off the series (no synthetic date_range) so dates and values
    # always come from the same source — same fix as get_fitness_pack.
    tsb_window = fs["tsb"].iloc[-14:]
    ff_dates = [
        (d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d))
        for d in tsb_window.index
    ]
    tsb_sparkline = {
        "dates": ff_dates,
        "values": [round(float(v), 1) for v in tsb_window.values],
        "projected_dates": proj["dates"][:7],
        "projected_values": proj["tsb"][:7],
    }

    return {
        "signal": signal,
        "tsb_sparkline": tsb_sparkline,
        "recovery_analysis": recovery_analysis,
        "warnings": warnings,
    }


def get_today_widgets(ctx: RequestContext) -> dict:
    """Last activity + current-week load summary + upcoming workouts.

    Used by ``/api/today``. Skips the full activity-list build: only the
    most recent activity is rendered on the Today page, so we extract one
    row instead of formatting all of them with splits.
    """
    return {
        "last_activity": _build_last_activity(ctx.merged_activities),
        "week_load": _current_week_load(
            ctx.fitness_series["daily_load"], ctx.plan,
            ctx.config.training_base, ctx.thresholds, ctx.today,
        ),
        "upcoming": upcoming_workouts(ctx.plan, current_date=ctx.today),
    }


def get_diagnosis_pack(ctx: RequestContext) -> dict:
    """Zone-aware diagnosis + workout flags + sleep-performance scatter.

    Used by ``/api/training``. Pays for splits and threshold-trend data.
    """
    cp_trend = ctx.threshold_data["trend"]
    diagnosis = _compute_diagnosis(
        ctx.merged_activities, ctx.splits, cp_trend,
        ctx.config, ctx.thresholds, ctx.science,
        samples=ctx.samples, current_date=ctx.today,
    )
    return {
        "diagnosis": diagnosis,
        "distribution_match_pct": compute_distribution_match_pct(
            diagnosis.get("distribution", []),
            evidence_complete=diagnosis.get("data_meta", {}).get(
                "distribution_complete", False,
            ),
        ),
        "workout_flags": _build_workout_flags(
            ctx.merged_activities, ctx.recovery, ctx.config.training_base,
        ),
        "sleep_perf": _build_sleep_perf(
            ctx.merged_activities, ctx.recovery, ctx.config.training_base,
        ),
    }


def get_fitness_pack(ctx: RequestContext) -> dict:
    """60-day fitness/fatigue chart + 8-week compliance + threshold trend.

    Used by ``/api/training``.
    """
    fs = ctx.fitness_series
    proj = ctx.projection
    display_days = 60
    # Pair dates with values from the same source — fs["ctl"]'s own
    # index. The previous code took dates from a synthetic
    # ``pd.date_range(today-60d, today)`` (61 entries) and values
    # from ``fs["ctl"].iloc[-61:]`` — fine when the user has ≥61
    # days of data, but for users whose history is shorter the
    # dates list is longer than the values list and they get paired
    # off by index, dragging values 12+ days back in time. Visually
    # that showed up as the FF lines trailing off ~12 days before
    # today on a stale-data account. iloc-tail keeps the same
    # alignment guarantee without a date-vs-Timestamp comparison
    # that would throw on mixed-dtype indexes.
    ctl_window = fs["ctl"].iloc[-display_days:]
    atl_window = fs["atl"].iloc[-display_days:]
    tsb_window = fs["tsb"].iloc[-display_days:]
    ff_dates = [
        (d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d))
        for d in ctl_window.index
    ]
    fitness_fatigue = {
        "dates": ff_dates,
        "ctl": [round(float(v), 1) for v in ctl_window.values],
        "atl": [round(float(v), 1) for v in atl_window.values],
        "tsb": [round(float(v), 1) for v in tsb_window.values],
        "projected_dates": proj["dates"],
        "projected_ctl": proj["ctl"],
        "projected_atl": proj["atl"],
        "projected_tsb": proj["tsb"],
    }
    weekly_review = _build_compliance(
        ctx.merged_activities, ctx.plan, ctx.config.training_base,
        fs["daily_load"], ctx.thresholds, current_date=ctx.today,
    )

    return {
        "fitness_fatigue": fitness_fatigue,
        "cp_trend": ctx.cp_trend_chart,
        "weekly_review": weekly_review,
        "current_tsb": (
            fitness_fatigue["tsb"][-1]
            if fitness_fatigue["tsb"] and ctx.data_meta["pmc_sufficient"]
            else None
        ),
        "load_compliance_pct": _compute_load_compliance_summary(weekly_review),
    }


def get_race_pack(ctx: RequestContext) -> dict:
    """Race countdown + threshold trend chart and series for /api/goal."""
    td = ctx.threshold_data
    config = ctx.config
    race_date_str = str(config.goal.get("race_date", "")).strip()
    raw_target = (
        config.goal.get("target_time_sec")
        or config.goal.get("race_target_time_sec")
    )
    target_time_sec = int(raw_target) if raw_target else None
    distance_key = (
        str(config.goal.get("distance", "marathon")).strip() or "marathon"
    )
    dist_config = get_distance_config(distance_key)
    threshold_pace = ctx.thresholds.threshold_pace_sec_km

    prediction_theory = ctx.science.get("prediction")
    prediction_theory_id = config.science.get("prediction", "critical_power")
    theory_exponent = None
    if prediction_theory and prediction_theory.params:
        theory_fractions = prediction_theory.params.get(
            "distance_power_fractions", {},
        )
        theory_fraction = theory_fractions.get(distance_key)
        if theory_fraction:
            dist_config = {**dist_config, "power_fraction": theory_fraction}
        theory_exponent = prediction_theory.params.get("riegel_exponent")

    prediction_method = _select_prediction_method(
        config.training_base, prediction_theory_id,
        has_cp=bool(ctx.latest_cp_watts), has_pace=bool(threshold_pace),
    )

    race_countdown = _build_race_countdown(
        race_date_str, target_time_sec,
        latest_threshold=td["latest"],
        latest_cp_watts=ctx.latest_cp_watts,
        power_pace_pairs=td["pairs"],
        cp_trend_data=td["trend"],
        today=ctx.today,
        distance_km=dist_config["km"],
        power_fraction=dist_config["power_fraction"],
        distance_label=dist_config["label"],
        distance_key=distance_key,
        training_base=config.training_base,
        threshold_pace=threshold_pace,
        riegel_exponent=theory_exponent,
        prediction_method=prediction_method,
        prediction_theory_name=(
            prediction_theory.name if prediction_theory else None
        ),
    )

    return {
        "race_countdown": race_countdown,
        "cp_trend": ctx.cp_trend_chart,
        "cp_trend_data": td["trend"],
        "latest_cp": td["latest"],
    }


def _history_page(
    ctx: RequestContext,
    *,
    limit: int | None = None,
    offset: int = 0,
    source: str | None = None,
) -> tuple[pd.DataFrame, int, str | None]:
    """Return the deduplicated history page plus total/source metadata."""
    user_pref = ctx.config.preferences.get("activities")
    primary = source or user_pref

    if source and source != user_pref:
        merged = _dedup_activities_by_primary_source(
            ctx._data["activities"],
            primary,
        )
    else:
        merged = ctx.merged_activities

    if not merged.empty:
        sort_frame = merged.copy()
        sort_columns: list[str] = []
        ascending: list[bool] = []
        helper_columns: list[str] = []
        if "date" in sort_frame.columns:
            sort_frame["_history_date"] = pd.to_datetime(
                sort_frame["date"],
                errors="coerce",
            )
            sort_columns.append("_history_date")
            ascending.append(False)
            helper_columns.append("_history_date")
        for column in ("activity_id", "source"):
            if column in sort_frame.columns:
                helper = f"_history_{column}"
                sort_frame[helper] = (
                    sort_frame[column].fillna("").astype(str)
                )
                sort_columns.append(helper)
                ascending.append(True)
                helper_columns.append(helper)
        if sort_columns:
            merged = sort_frame.sort_values(
                sort_columns,
                ascending=ascending,
                kind="stable",
                na_position="last",
            ).drop(columns=helper_columns)
    total = len(merged)
    if limit is None:
        return merged, total, primary
    if merged.empty:
        return merged, total, primary
    return merged.iloc[offset : offset + limit], total, primary


def _page_splits(
    splits: pd.DataFrame,
    activities: pd.DataFrame,
) -> pd.DataFrame:
    """Restrict split rows to one selected activity page."""
    if (
        activities.empty
        or "activity_id" not in activities.columns
        or splits.empty
        or "activity_id" not in splits.columns
    ):
        return splits.iloc[0:0] if not splits.empty else splits
    activity_ids = set(activities["activity_id"].astype(str))
    page_splits = splits[
        splits["activity_id"].astype(str).isin(activity_ids)
    ]
    return _sort_activity_splits(page_splits)


def get_history_pack(
    ctx: RequestContext,
    *,
    limit: int | None = None,
    offset: int = 0,
    source: str | None = None,
) -> dict:
    """Activities (with provenance) for /api/history, paginated server-side.

    Pagination lives here, not in the route, so :func:`_build_activities_list`
    only ever formats the requested page. The previous shape built every
    activity (with its splits) and the route sliced afterwards; for a
    user with hundreds of activities the discarded work was the dominant
    cost on /api/history's cold path.

    Parameters
    ----------
    limit
        Page size. ``None`` (the default) returns every activity that
        survives dedup — kept as the legacy contract for skill-side and
        test callers that want the full list.
    offset
        Number of activities to skip from the start of the deduped,
        date-descending list.
    source
        Override for the dedup pivot. ``None`` falls back to the user's
        ``preferences.activities``. When the override differs from the
        user's setting, dedup re-runs from the raw activities frame so
        the wrong half of a duplicate pair isn't dropped.

    Returns
    -------
    dict
        ``{"activities": [...page], "total": <int>, "source_filter": <str|None>}``.
        ``total`` is the post-dedup count so the client can render
        "Showing 1-20 of N" without holding the full list itself.
    """
    page_merged, total, primary = _history_page(
        ctx,
        limit=limit,
        offset=offset,
        source=source,
    )
    page_splits = _page_splits(ctx.splits, page_merged)
    page_activity_ids = (
        page_merged["activity_id"].astype(str).tolist()
        if not page_merged.empty and "activity_id" in page_merged.columns
        else []
    )
    coverage = load_activity_sample_coverage(
        ctx.user_id,
        ctx.db,
        page_activity_ids,
        max_interval_sec=HEAT_SAMPLE_MAX_INTERVAL_SEC,
    )

    return {
        "activities": _build_activities_list(
            page_merged,
            page_splits,
            coverage,
        ),
        "total": total,
        "source_filter": primary,
    }


def _critical_power_before(
    ctx: RequestContext,
    activity_date: date,
) -> tuple[dict, float | None, str | None, str | None]:
    """Select the latest CP whose date is strictly before the activity."""
    frame = ctx.fitness_history
    if frame.empty:
        return (
            {
                "state": "unavailable",
                "value_watts": None,
                "effective_date": None,
                "source": None,
                "power_provider": None,
                "selection": "latest_strictly_before_activity_date",
                "reason_codes": ["critical_power_history_unavailable"],
            },
            None,
            None,
            None,
        )
    cp_rows = frame[
        frame["metric_type"].eq("cp_estimate")
        & pd.to_numeric(frame["value"], errors="coerce").gt(0)
        & frame["date"].map(
            lambda value: pd.notna(value) and value < activity_date
        )
    ].copy()
    if cp_rows.empty:
        return (
            {
                "state": "unavailable",
                "value_watts": None,
                "effective_date": None,
                "source": None,
                "power_provider": None,
                "selection": "latest_strictly_before_activity_date",
                "reason_codes": [
                    "critical_power_unavailable_before_activity",
                ],
            },
            None,
            None,
            None,
        )

    threshold_sources = ctx.config.preferences.get("threshold_sources") or {}
    if not isinstance(threshold_sources, dict):
        threshold_sources = {}
    preferred = (
        threshold_sources.get("cp_estimate")
        or ctx.config.preferences.get("activities")
    )
    preferred_rows = (
        cp_rows[cp_rows["source"].eq(preferred)]
        if preferred
        else pd.DataFrame()
    )
    selected = (
        preferred_rows.sort_values(["date", "id"], kind="stable").iloc[-1]
        if not preferred_rows.empty
        else cp_rows.sort_values(["date", "id"], kind="stable").iloc[-1]
    )
    value = float(selected["value"])
    source = (
        str(selected.get("source")).strip().casefold()
        if pd.notna(selected.get("source"))
        and str(selected.get("source")).strip()
        else None
    )
    power_provider = (
        str(selected.get("power_source")).strip().casefold()
        if pd.notna(selected.get("power_source"))
        and str(selected.get("power_source")).strip()
        else (source if source and source != "activities" else None)
    )
    reason_codes = (
        [] if power_provider else ["critical_power_provider_unavailable"]
    )
    return (
        {
            "state": "available" if power_provider else "partial",
            "value_watts": round(value, 1),
            "effective_date": selected["date"].isoformat(),
            "source": source,
            "power_provider": power_provider,
            "selection": "latest_strictly_before_activity_date",
            "reason_codes": reason_codes,
        },
        value,
        source,
        power_provider,
    )


def _pre_activity_recovery(
    ctx: RequestContext,
    activity_date: date,
) -> dict:
    """Return selected-source recovery available on or before activity day."""
    frame = ctx.recovery_history
    if frame.empty or "date" not in frame.columns:
        return {
            "state": "unavailable",
            "date": None,
            "source": None,
            "selection": "latest_on_or_before_activity_date",
            "values": {},
            "reason_codes": ["recovery_unavailable"],
        }
    normalized_dates = pd.to_datetime(
        frame["date"],
        errors="coerce",
    ).dt.date
    eligible = frame.loc[
        normalized_dates.map(
            lambda value: pd.notna(value) and value <= activity_date
        )
    ].copy()
    eligible["date"] = normalized_dates.loc[eligible.index]
    if eligible.empty:
        return {
            "state": "unavailable",
            "date": None,
            "source": None,
            "selection": "latest_on_or_before_activity_date",
            "values": {},
            "reason_codes": ["recovery_unavailable_before_activity"],
        }
    eligible = select_preferred_source(
        eligible,
        ctx.config.preferences.get("recovery"),
    ).sort_values("date", kind="stable")
    row = eligible.iloc[-1]
    fields = (
        "readiness_score",
        "hrv_avg",
        "resting_hr",
        "sleep_score",
        "total_sleep_sec",
    )
    values: dict[str, float | None] = {}
    missing: list[str] = []
    for field in fields:
        value = pd.to_numeric(
            pd.Series([row.get(field)]),
            errors="coerce",
        ).iloc[0]
        if pd.isna(value):
            values[field] = None
            missing.append(f"{field}_unavailable")
        else:
            values[field] = round(float(value), 1)
    available_count = sum(value is not None for value in values.values())
    state = (
        "unavailable"
        if available_count == 0
        else ("partial" if missing else "available")
    )
    source = (
        str(row.get("source")).strip().casefold()
        if pd.notna(row.get("source"))
        and str(row.get("source")).strip()
        else None
    )
    if source is None:
        missing.append("recovery_source_unavailable")
        if state == "available":
            state = "partial"
    return {
        "state": state,
        "date": row["date"].isoformat(),
        "source": source,
        "selection": "latest_on_or_before_activity_date",
        "values": values,
        "reason_codes": list(dict.fromkeys(missing)),
    }


def _pre_activity_load(
    ctx: RequestContext,
    activity_date: date,
) -> dict:
    """Compute previous-day PMC values from stored, prior activity loads.

    Missing activity loads make CTL/ATL known-load lower bounds. TSB is omitted
    in that state because unequal acute/chronic weighting makes its bias
    direction indeterminate.
    """
    as_of_date = activity_date - timedelta(days=1)
    history = ctx.causal_load_history
    ctl_days = int(history["ctl_days"])
    atl_days = int(history["atl_days"])
    activity_timestamp = pd.Timestamp(activity_date)
    missing_load_dates = history["missing_load_dates"]
    # Keep the whole prior history intentionally: EWMA influence approaches
    # zero but never reaches it, and an arbitrary hard cutoff would overstate
    # completeness. The public count makes this conservative choice explicit.
    missing_load_activity_count = int(
        missing_load_dates.lt(activity_timestamp).sum()
    )
    base = {
        "state": "unavailable",
        "as_of_date": as_of_date.isoformat(),
        "ctl": None,
        "atl": None,
        "tsb": None,
        "model_version": PRE_ACTIVITY_LOAD_MODEL_VERSION,
        "training_base": ctx.config.training_base,
        "load_sources": [],
        "time_constants_days": {
            "ctl": ctl_days,
            "atl": atl_days,
        },
        "data_days": 0,
        "observation_days": 0,
        "missing_load_activity_count": missing_load_activity_count,
        "reason_codes": [],
    }
    activity_dates = history["activity_dates"]
    if activity_dates.empty:
        return {
            **base,
            "reason_codes": ["prior_activity_load_unavailable"],
        }
    as_of_timestamp = pd.Timestamp(as_of_date)
    prior_dates = activity_dates[activity_dates.lt(activity_timestamp)]
    if prior_dates.empty:
        return {
            **base,
            "reason_codes": ["prior_activity_load_unavailable"],
        }

    first_date = prior_dates.min()
    data_days = (as_of_timestamp - first_date).days + 1
    daily_load = history["daily_load"].loc[:as_of_timestamp]
    if daily_load.empty or not daily_load.gt(0).any():
        reason_codes = ["historical_load_scores_unavailable"]
        if missing_load_activity_count:
            reason_codes.append("activity_load_observations_missing")
        return {
            **base,
            "data_days": data_days,
            "reason_codes": reason_codes,
        }

    load_sources: list[str] = []
    if history["primary_load_dates"].le(as_of_timestamp).any():
        load_sources.append(str(history["primary_column"]))
    if history["fallback_load_dates"].le(as_of_timestamp).any():
        load_sources.append("load_score")
    sufficient = has_sufficient_load_history(data_days, ctl_days)
    reason_codes = (
        [] if sufficient else ["load_history_insufficient"]
    )
    if missing_load_activity_count:
        reason_codes.append("activity_load_observations_missing")
    return {
        **base,
        "state": "available" if not reason_codes else "partial",
        "ctl": round(float(history["ctl"].loc[as_of_timestamp]), 2),
        "atl": round(float(history["atl"].loc[as_of_timestamp]), 2),
        "tsb": (
            None
            if missing_load_activity_count
            else round(float(history["tsb"].loc[as_of_timestamp]), 2)
        ),
        "load_sources": load_sources,
        "data_days": data_days,
        "observation_days": int(daily_load.gt(0).sum()),
        "reason_codes": reason_codes,
    }


def _load_heat_context_frames(
    ctx: RequestContext,
    activities: pd.DataFrame,
) -> dict[str, tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]]:
    """Load one bounded heat-evidence range per activity-summary provider."""
    result: dict[
        str,
        tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
    ] = {}
    if activities.empty or "source" not in activities.columns:
        return result
    prepared = activities.copy()
    prepared["_analysis_date"] = pd.to_datetime(
        prepared["date"], errors="coerce"
    ).dt.date
    prepared["_analysis_source"] = (
        prepared["source"].fillna("").astype(str).str.strip().str.casefold()
    )
    prepared = prepared[
        prepared["_analysis_date"].notna()
        & prepared["_analysis_source"].ne("")
    ]
    for source, group in prepared.groupby("_analysis_source", sort=False):
        earliest_target = min(group["_analysis_date"])
        latest_target = max(group["_analysis_date"])
        current_date = latest_target - timedelta(days=1)
        earliest_context = earliest_target - timedelta(
            days=HEAT_LOOKBACK_DAYS,
        )
        lookback_days = max(
            1,
            (current_date - earliest_context).days + 1,
        )
        result[source] = load_heat_adaptation_inputs(
            ctx.user_id,
            ctx.db,
            activity_source=source,
            current_date=current_date,
            sample_max_interval_sec=HEAT_SAMPLE_MAX_INTERVAL_SEC,
            lookback_days=lookback_days,
            eligible_activity_types=HEAT_ELIGIBLE_ACTIVITY_TYPES,
        )
    return result


def _pre_activity_heat(
    activity_row: pd.Series,
    *,
    cp_watts: float | None,
    cp_source: str | None,
    cp_power_provider: str | None,
    frames_by_source: dict[
        str,
        tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
    ],
) -> dict:
    """Compute heat evidence through the previous calendar day only."""
    activity_date = pd.to_datetime(activity_row["date"]).date()
    as_of_date = activity_date - timedelta(days=1)
    source = (
        str(activity_row.get("source")).strip().casefold()
        if pd.notna(activity_row.get("source"))
        and str(activity_row.get("source")).strip()
        else ""
    )
    loaded = frames_by_source.get(source)
    if loaded is None:
        return {
            "state": "unavailable",
            "as_of_date": as_of_date.isoformat(),
            "model_version": None,
            "reason_codes": ["heat_evidence_source_unavailable"],
        }
    activities, splits, sample_power = loaded
    cutoff = as_of_date - timedelta(days=HEAT_LOOKBACK_DAYS - 1)
    activity_dates = pd.to_datetime(
        activities.get("date", pd.Series(dtype=object)),
        errors="coerce",
    ).dt.date
    selected_activities = activities[
        activity_dates.notna()
        & activity_dates.map(
            lambda value: cutoff <= value <= as_of_date
        )
    ].copy()
    activity_ids = set(
        selected_activities.get(
            "activity_id", pd.Series(dtype=object),
        ).dropna().astype(str)
    )
    selected_splits = (
        splits[
            splits["activity_id"].astype(str).isin(activity_ids)
        ].copy()
        if activity_ids
        and not splits.empty
        and "activity_id" in splits.columns
        else splits.iloc[0:0].copy()
    )
    selected_samples = (
        sample_power[
            sample_power["activity_id"].astype(str).isin(activity_ids)
        ].copy()
        if activity_ids
        and not sample_power.empty
        and "activity_id" in sample_power.columns
        else sample_power.iloc[0:0].copy()
    )
    status = compute_heat_adaptation(
        selected_activities,
        selected_splits,
        selected_samples,
        cp_watts=cp_watts,
        cp_source=cp_source,
        cp_power_provider=cp_power_provider,
        current_date=as_of_date,
    )
    coverage = status.get("data_coverage") or {}
    if not coverage.get("recent_activities"):
        state = "unavailable"
    elif (
        not coverage.get("environment_supported_activities")
        or not coverage.get("workload_supported_activities")
    ):
        state = "partial"
    else:
        state = "available"
    return {
        "state": state,
        "as_of_date": as_of_date.isoformat(),
        "cutoff_policy": "strictly_before_activity_calendar_date",
        **status,
    }


def _build_activity_analysis_record(
    ctx: RequestContext,
    activity_row: pd.Series,
    *,
    samples: pd.DataFrame,
    coverage: pd.DataFrame,
    heat_frames: dict[
        str,
        tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame],
    ],
) -> dict:
    """Build one owner-scoped, analysis-ready activity record."""
    activity_id = str(activity_row["activity_id"])
    activity_date = pd.to_datetime(activity_row["date"]).date()
    split_frame = _page_splits(
        ctx.splits,
        pd.DataFrame([activity_row]),
    )
    coverage_frame = (
        coverage[coverage["activity_id"].astype(str).eq(activity_id)]
        if not coverage.empty and "activity_id" in coverage.columns
        else coverage
    )
    sample_frame = (
        samples[samples["activity_id"].astype(str).eq(activity_id)]
        if not samples.empty and "activity_id" in samples.columns
        else samples
    )
    activity_view = _build_activities_list(
        pd.DataFrame([activity_row]),
        split_frame,
        coverage_frame,
    )[0]
    (
        critical_power,
        cp_watts,
        cp_source,
        cp_power_provider,
    ) = _critical_power_before(ctx, activity_date)
    segments = derive_stable_power_segments(
        sample_frame,
        split_frame,
        activity_duration_sec=activity_view.get("duration_sec"),
        cp_watts=cp_watts,
        cp_source=cp_source,
        cp_power_provider=cp_power_provider,
        activity_provider=activity_view.get("source"),
    )
    return {
        "activity": activity_view,
        "stable_segments": segments,
        "pre_activity_context": {
            "cutoff_policy": (
                "load_and_heat_through_previous_calendar_day; "
                "recovery_on_or_before_activity_day; "
                "critical_power_strictly_before_activity_day"
            ),
            "load": _pre_activity_load(ctx, activity_date),
            "critical_power": critical_power,
            "recovery": _pre_activity_recovery(ctx, activity_date),
            "heat_adaptation": _pre_activity_heat(
                activity_row,
                cp_watts=cp_watts,
                cp_source=cp_source,
                cp_power_provider=cp_power_provider,
                frames_by_source=heat_frames,
            ),
        },
    }


def _analysis_versions(records: list[dict]) -> dict:
    heat_versions = sorted({
        record["pre_activity_context"]["heat_adaptation"].get(
            "model_version"
        )
        for record in records
        if record["pre_activity_context"]["heat_adaptation"].get(
            "model_version"
        )
    })
    return {
        "stable_segments": STABLE_SEGMENT_MODEL_VERSION,
        "environment": ENVIRONMENT_CONTEXT_MODEL_VERSION,
        "pre_activity_load": PRE_ACTIVITY_LOAD_MODEL_VERSION,
        "heat_adaptation": heat_versions,
    }


def get_analysis_response_version(schema_version: str) -> str:
    """Return the ETag salt for an analysis schema and its model manifest."""
    return _analysis_hash({
        "schema_version": schema_version,
        "model_versions": {
            "stable_segments": STABLE_SEGMENT_MODEL_VERSION,
            "environment": ENVIRONMENT_CONTEXT_MODEL_VERSION,
            "pre_activity_load": PRE_ACTIVITY_LOAD_MODEL_VERSION,
            "heat_adaptation": [HEAT_ADAPTATION_MODEL_VERSION],
        },
    })


def _analysis_hash(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def get_activity_analysis_pack(
    ctx: RequestContext,
    activity_id: str,
) -> dict | None:
    """Return one exact owner-scoped activity with derived research features."""
    activities = load_activity_records(
        ctx.user_id,
        ctx.db,
        [activity_id],
    )
    if activities.empty:
        return None
    row = activities.iloc[0]
    samples = load_activity_samples(
        ctx.user_id,
        ctx.db,
        [activity_id],
    )
    coverage = load_activity_sample_coverage(
        ctx.user_id,
        ctx.db,
        [activity_id],
        max_interval_sec=HEAT_SAMPLE_MAX_INTERVAL_SEC,
    )
    heat_frames = _load_heat_context_frames(ctx, activities)
    record = _build_activity_analysis_record(
        ctx,
        row,
        samples=samples,
        coverage=coverage,
        heat_frames=heat_frames,
    )
    core = {
        "schema_version": ACTIVITY_ANALYSIS_SCHEMA_VERSION,
        "model_versions": _analysis_versions([record]),
        **record,
        "privacy": {
            "precise_gps_included": False,
            "credentials_included": False,
            "raw_samples_included": False,
        },
    }
    return {
        **core,
        "record_hash": _analysis_hash(core),
    }


def get_activity_research_pack(
    ctx: RequestContext,
    *,
    limit: int = 20,
    offset: int = 0,
    source: str | None = None,
) -> dict:
    """Build a bounded, versioned retrospective activity research dataset."""
    activities, total, primary = _history_page(
        ctx,
        limit=limit,
        offset=offset,
        source=source,
    )
    activity_ids = (
        activities["activity_id"].astype(str).tolist()
        if not activities.empty and "activity_id" in activities.columns
        else []
    )
    samples = load_activity_samples(
        ctx.user_id,
        ctx.db,
        activity_ids,
    )
    coverage = load_activity_sample_coverage(
        ctx.user_id,
        ctx.db,
        activity_ids,
        max_interval_sec=HEAT_SAMPLE_MAX_INTERVAL_SEC,
    )
    heat_frames = _load_heat_context_frames(ctx, activities)
    records = [
        _build_activity_analysis_record(
            ctx,
            row,
            samples=samples,
            coverage=coverage,
            heat_frames=heat_frames,
        )
        for _, row in activities.iterrows()
    ]
    core = {
        "schema_version": ACTIVITY_RESEARCH_SCHEMA_VERSION,
        "model_versions": _analysis_versions(records),
        "records": records,
        "total": total,
        "limit": limit,
        "offset": offset,
        "source_filter": primary,
        "semantics": {
            "pre_activity_cutoff": (
                "previous calendar day for load and heat; same-day "
                "recovery may be selected because source rows are dated, "
                "not timestamped"
            ),
            "critical_power_cutoff": (
                "latest dated value strictly before activity date"
            ),
            "same_activity_leakage": False,
            "stable_segment_priority": "samples_then_explicit_split_fallback",
        },
        "privacy": {
            "precise_gps_included": False,
            "credentials_included": False,
            "raw_samples_included": False,
        },
    }
    return {
        **core,
        "dataset_hash": _analysis_hash(core),
        "generated_at": (
            datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        ),
    }


def get_science_pack(ctx: RequestContext) -> dict:
    """Active science theories + summarized notes + TSB zone bands."""
    return {
        "science": ctx.science,
        "science_notes": ctx.science_notes,
        "tsb_zones": ctx.tsb_zones,
    }


# NOTE: ``get_plan_pack`` was retired with the /api/plan reshape.
# The route now does its own (window-aware, source-filtered, sync-state-
# aware) projection of ``ctx.plan`` — see api/routes/plan.py. The pack
# only ever served two endpoints (this one) and its ``cp_current`` field
# was dead on the frontend, so the indirection wasn't earning its keep.
