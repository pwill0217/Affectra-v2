"""Build leakage-safe daily and rolling features for Affectra agents."""

from typing import Any

import numpy as np
import pandas as pd

from src.data_loader import validate_required_columns

DAILY_CALL_METRICS = [
    "call_count",
    "avg_duration_seconds",
    "avg_acw_seconds",
    "avg_hold_seconds",
    "avg_transfer_count",
    "avg_sentiment_score",
    "negative_call_rate",
    "avg_negative_keyword_count",
]

ROLLING_FEATURES = {
    "call_count": "rolling_call_count",
    "avg_duration_seconds": "rolling_avg_duration_seconds",
    "avg_acw_seconds": "rolling_avg_acw_seconds",
    "avg_hold_seconds": "rolling_avg_hold_seconds",
    "avg_transfer_count": "rolling_avg_transfer_count",
    "avg_sentiment_score": "rolling_avg_sentiment_score",
    "negative_call_rate": "rolling_negative_call_rate",
    "avg_negative_keyword_count": "rolling_avg_negative_keyword_count",
}

TARGET_METADATA_COLUMNS = {
    "latent_pressure_score",
    "pressure_band",
    "simulated_pressure_event",
    "synthetic_stress_label",
}


class FeatureEngineeringError(ValueError):
    """Raised when related inputs cannot produce reliable agent features."""


def aggregate_daily_calls(
    calls: pd.DataFrame,
    transcripts: pd.DataFrame,
) -> pd.DataFrame:
    """Combine one-to-one call/tone records and aggregate them by agent-day."""
    transcript_fields = transcripts[
        [
            "call_id",
            "transcript_id",
            "sentiment_label",
            "sentiment_score",
            "negative_keyword_count",
        ]
    ]
    try:
        combined = calls.merge(
            transcript_fields,
            on=["call_id", "transcript_id"],
            how="inner",
            validate="one_to_one",
        )
    except pd.errors.MergeError as error:
        raise FeatureEngineeringError(
            "Calls and transcripts must have a one-to-one relationship"
        ) from error

    if len(combined) != len(calls) or len(combined) != len(transcripts):
        raise FeatureEngineeringError(
            "Every call must match exactly one transcript before feature engineering"
        )

    combined = combined.assign(
        is_negative=combined["sentiment_label"].eq("Negative").astype(float)
    )
    daily = (
        combined.groupby(["agent_id", "call_date"], as_index=False)
        .agg(
            call_count=("call_id", "size"),
            avg_duration_seconds=("duration_seconds", "mean"),
            avg_acw_seconds=("acw_seconds", "mean"),
            avg_hold_seconds=("hold_seconds", "mean"),
            avg_transfer_count=("transfer_count", "mean"),
            avg_sentiment_score=("sentiment_score", "mean"),
            negative_call_rate=("is_negative", "mean"),
            avg_negative_keyword_count=("negative_keyword_count", "mean"),
        )
        .rename(columns={"call_date": "metric_date"})
    )
    return daily


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = denominator.replace(0, np.nan)
    ratio = numerator / denominator
    if ratio.isna().any() or ~np.isfinite(ratio).all():
        raise FeatureEngineeringError("Personal baselines must be positive finite values")
    return ratio.astype(float)


def _add_rolling_features(
    features: pd.DataFrame,
    rolling_window: int,
) -> pd.DataFrame:
    result = features.sort_values(["agent_id", "metric_date"]).copy()
    grouped = result.groupby("agent_id", sort=False)
    for daily_column, rolling_column in ROLLING_FEATURES.items():
        result[rolling_column] = grouped[daily_column].transform(
            lambda values: values.rolling(rolling_window, min_periods=1).mean()
        )
    result["rolling_window_days"] = rolling_window
    return result


def build_agent_day_features(
    cleaned_tables: dict[str, pd.DataFrame],
    *,
    rolling_window: int = 7,
) -> pd.DataFrame:
    """Create one observable feature row for every cleaned agent-day."""
    if isinstance(rolling_window, bool) or not isinstance(rolling_window, int):
        raise ValueError("rolling_window must be an integer")
    if rolling_window < 1:
        raise ValueError("rolling_window must be at least 1")
    validate_required_columns(cleaned_tables)

    agents = cleaned_tables["agents"]
    timeoff = cleaned_tables["timeoff"]
    daily_labels = cleaned_tables["daily_labels"]
    if daily_labels.empty:
        raise FeatureEngineeringError("Daily label dates are required as the agent-day spine")

    daily_calls = aggregate_daily_calls(
        cleaned_tables["calls"],
        cleaned_tables["transcripts"],
    )
    spine = daily_labels[["agent_id", "label_date"]].rename(
        columns={"label_date": "metric_date"}
    )
    if spine.duplicated(["agent_id", "metric_date"]).any():
        raise FeatureEngineeringError("Agent-day rows must be unique")

    agent_fields = agents[
        [
            "agent_id",
            "name",
            "team",
            "role",
            "baseline_calls_per_day",
            "baseline_avg_acw",
            "baseline_avg_call_duration",
        ]
    ]
    timeoff_fields = timeoff[
        [
            "agent_id",
            "pto_balance_hours",
            "vacation_days_available",
            "pto_used_hours_30d",
            "last_pto_date",
        ]
    ]

    features = spine.merge(agent_fields, on="agent_id", how="left", validate="many_to_one")
    features = features.merge(
        daily_calls,
        on=["agent_id", "metric_date"],
        how="left",
        validate="one_to_one",
    )
    features = features.merge(timeoff_fields, on="agent_id", how="left", validate="many_to_one")

    required_context = [
        "name",
        "team",
        "role",
        "baseline_calls_per_day",
        "baseline_avg_acw",
        "baseline_avg_call_duration",
        "pto_balance_hours",
        "vacation_days_available",
        "pto_used_hours_30d",
        "last_pto_date",
    ]
    if features[required_context].isna().any().any():
        raise FeatureEngineeringError("Every agent-day needs agent and time-off context")

    features[DAILY_CALL_METRICS] = features[DAILY_CALL_METRICS].fillna(0.0)
    features = _add_rolling_features(features, rolling_window)
    features["calls_vs_baseline"] = _safe_ratio(
        features["rolling_call_count"], features["baseline_calls_per_day"]
    )
    features["acw_vs_baseline"] = _safe_ratio(
        features["rolling_avg_acw_seconds"], features["baseline_avg_acw"]
    )
    features["duration_vs_baseline"] = _safe_ratio(
        features["rolling_avg_duration_seconds"],
        features["baseline_avg_call_duration"],
    )

    snapshot_date = pd.Timestamp(features["metric_date"].max()).normalize()
    features["recovery_snapshot_date"] = snapshot_date
    last_pto = pd.to_datetime(features["last_pto_date"])
    features["days_since_pto_at_snapshot"] = (
        snapshot_date - last_pto
    ).dt.days.clip(lower=0)

    leaked = TARGET_METADATA_COLUMNS & set(features.columns)
    if leaked:
        raise FeatureEngineeringError(
            "Synthetic target metadata leaked into operational features: "
            + ", ".join(sorted(leaked))
        )

    return features.sort_values(["agent_id", "metric_date"]).reset_index(drop=True)


def feature_summary(features: pd.DataFrame) -> dict[str, Any]:
    """Return small JSON-safe evidence about one feature table."""
    return {
        "rows": len(features),
        "agents": int(features["agent_id"].nunique()),
        "start_date": pd.Timestamp(features["metric_date"].min()).date().isoformat(),
        "end_date": pd.Timestamp(features["metric_date"].max()).date().isoformat(),
        "rolling_window_days": int(features["rolling_window_days"].iloc[0]),
        "target_metadata_columns_present": sorted(TARGET_METADATA_COLUMNS & set(features.columns)),
    }
