"""Stryd provider — power overlay for activities, training plan, fitness (CP)."""
import os
from datetime import date

import numpy as np
import pandas as pd

from analysis.data_loader import _read_csv_safe
from analysis.providers.base import ActivityProvider, FitnessProvider, PlanProvider
from analysis.providers.models import ThresholdEstimate
from analysis.providers import register_activity, register_fitness, register_plan


def _humidity_percent(values: pd.Series) -> pd.Series:
    """Normalize legacy Stryd humidity fractions or percentages."""
    humidity = pd.to_numeric(values, errors="coerce")
    humidity = humidity.where(np.isfinite(humidity))
    fractions = humidity.between(0, 1, inclusive="both")
    humidity = humidity.where(~fractions, humidity * 100)
    return humidity.where(humidity.between(0, 100, inclusive="both"))


def _canonicalize_environment(df: pd.DataFrame) -> pd.DataFrame:
    """Add conservative outdoor provenance to legacy Stryd CSV weather."""
    if df.empty:
        return df

    result = df.copy()
    temperature_values = (
        result["temperature_c"]
        if "temperature_c" in result.columns
        else pd.Series(np.nan, index=result.index, dtype=float)
    )
    temperature = pd.to_numeric(temperature_values, errors="coerce")
    temperature = temperature.where(np.isfinite(temperature))

    humidity = pd.Series(np.nan, index=result.index, dtype=float)
    if "relative_humidity_pct" in result.columns:
        humidity = _humidity_percent(result["relative_humidity_pct"])
    if "humidity" in result.columns:
        humidity = humidity.fillna(_humidity_percent(result["humidity"]))

    indoor = pd.Series(False, index=result.index)
    for column in ("stryd_type", "surface_type"):
        if column in result.columns:
            indoor |= (
                result[column]
                .fillna("")
                .astype(str)
                .str.contains("indoor|treadmill", case=False, regex=True)
            )

    supported = temperature.notna() & humidity.notna() & ~indoor
    result["activity_type"] = "running"
    result["temperature_c"] = temperature.where(supported)
    result["relative_humidity_pct"] = humidity.where(supported)
    result["environment_source"] = pd.Series(
        pd.NA,
        index=result.index,
        dtype="object",
    )
    result.loc[supported, "environment_source"] = "stryd_activity_weather"
    return result


class StrydActivityProvider(ActivityProvider):
    """Load Stryd power data as an activity overlay (merged onto primary source)."""

    name = "stryd"

    def load_activities(
        self, data_dir: str, since: date | None = None
    ) -> pd.DataFrame:
        df = _read_csv_safe(os.path.join(data_dir, "stryd", "power_data.csv"))
        df = _canonicalize_environment(df)
        if since and not df.empty and "date" in df.columns:
            df = df[df["date"] >= since]
        return df

    def load_splits(
        self, data_dir: str, activity_ids: list[str] | None = None
    ) -> pd.DataFrame:
        df = _read_csv_safe(
            os.path.join(data_dir, "stryd", "activity_splits.csv")
        )
        if activity_ids and not df.empty and "activity_id" in df.columns:
            df = df[df["activity_id"].astype(str).isin(activity_ids)]
        return df


class StrydFitnessProvider(FitnessProvider):
    """Load Stryd fitness data (CP estimates) and detect CP threshold."""

    name = "stryd"

    def load_fitness(
        self, data_dir: str, since: date | None = None
    ) -> pd.DataFrame:
        df = _read_csv_safe(os.path.join(data_dir, "stryd", "power_data.csv"))
        if df.empty:
            return df
        # Extract fitness-relevant columns from Stryd power data
        fitness_cols = ["date", "cp_estimate", "leg_spring_stiffness", "avg_oscillation", "avg_stride_length"]
        available = [c for c in fitness_cols if c in df.columns]
        df = df[available].copy()
        if since and "date" in df.columns:
            df = df[df["date"] >= since]
        return df

    def detect_thresholds(self, data_dir: str) -> ThresholdEstimate:
        df = _read_csv_safe(os.path.join(data_dir, "stryd", "power_data.csv"))
        if df.empty or "cp_estimate" not in df.columns:
            return ThresholdEstimate(source="auto")

        cp_vals = pd.to_numeric(df["cp_estimate"], errors="coerce").dropna()
        cp_vals = cp_vals[cp_vals > 0]
        if cp_vals.empty:
            return ThresholdEstimate(source="auto")

        latest_idx = cp_vals.index[-1]
        return ThresholdEstimate(
            cp_watts=float(cp_vals.iloc[-1]),
            source="auto",
            detected_date=df.loc[latest_idx, "date"] if "date" in df.columns else None,
        )


class StrydPlanProvider(PlanProvider):
    """Load Stryd training plan from CSV."""

    name = "stryd"

    def load_plan(
        self, data_dir: str, since: date | None = None
    ) -> pd.DataFrame:
        df = _read_csv_safe(
            os.path.join(data_dir, "stryd", "training_plan.csv")
        )
        if since and not df.empty and "date" in df.columns:
            df = df[df["date"] >= since]
        return df


# Register providers
register_activity("stryd", StrydActivityProvider)
register_fitness("stryd", StrydFitnessProvider)
register_plan("stryd", StrydPlanProvider)
