"""Tests for Sprint 3 agent-day and rolling feature engineering."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.data_generator import GenerationConfig, generate_dataset
from src.features import (
    TARGET_METADATA_COLUMNS,
    FeatureEngineeringError,
    aggregate_daily_calls,
    build_agent_day_features,
    feature_summary,
)
from src.preprocessing import preprocess_tables


def cleaned_tables(tmp_path: Path, *, agents: int = 4, days: int = 5):
    config = GenerationConfig(
        num_agents=agents,
        start_date=date(2026, 7, 1),
        num_days=days,
        seed=91,
        output_dir=tmp_path,
    )
    generated = generate_dataset(config)
    return preprocess_tables(generated)[0]


def test_features_have_one_row_per_agent_day_without_target_leakage(tmp_path: Path) -> None:
    tables = cleaned_tables(tmp_path, agents=4, days=5)

    features = build_agent_day_features(tables, rolling_window=3)

    assert len(features) == 20
    assert not features.duplicated(["agent_id", "metric_date"]).any()
    assert TARGET_METADATA_COLUMNS.isdisjoint(features.columns)
    assert set(features["rolling_window_days"]) == {3}
    assert features["recovery_snapshot_date"].nunique() == 1
    assert features["recovery_snapshot_date"].iloc[0] == pd.Timestamp("2026-07-05")


def test_daily_aggregation_and_rolling_average_are_mathematically_correct(
    tmp_path: Path,
) -> None:
    tables = cleaned_tables(tmp_path)
    daily = aggregate_daily_calls(tables["calls"], tables["transcripts"])
    features = build_agent_day_features(tables, rolling_window=3)
    agent_id = int(features["agent_id"].iloc[0])
    agent_rows = features.loc[features["agent_id"] == agent_id].reset_index(drop=True)
    daily_rows = daily.loc[daily["agent_id"] == agent_id].sort_values("metric_date")

    assert agent_rows.loc[0, "call_count"] == daily_rows.iloc[0]["call_count"]
    assert agent_rows.loc[0, "rolling_call_count"] == agent_rows.loc[0, "call_count"]
    assert agent_rows.loc[1, "rolling_call_count"] == pytest.approx(
        agent_rows.loc[:1, "call_count"].mean()
    )
    assert agent_rows.loc[3, "rolling_call_count"] == pytest.approx(
        agent_rows.loc[1:3, "call_count"].mean()
    )
    assert agent_rows.loc[3, "calls_vs_baseline"] == pytest.approx(
        agent_rows.loc[3, "rolling_call_count"]
        / agent_rows.loc[3, "baseline_calls_per_day"]
    )


def test_agent_day_with_no_calls_receives_zero_observable_call_metrics(
    tmp_path: Path,
) -> None:
    tables = cleaned_tables(tmp_path)
    removed_agent = int(tables["agents"]["agent_id"].iloc[0])
    keep_calls = tables["calls"]["agent_id"].astype(int).ne(removed_agent)
    kept_call_ids = set(tables["calls"].loc[keep_calls, "call_id"].astype(int))
    tables["calls"] = tables["calls"].loc[keep_calls].reset_index(drop=True)
    tables["transcripts"] = tables["transcripts"].loc[
        tables["transcripts"]["call_id"].astype(int).isin(kept_call_ids)
    ].reset_index(drop=True)

    features = build_agent_day_features(tables)
    no_call_rows = features.loc[features["agent_id"] == removed_agent]

    assert (no_call_rows["call_count"] == 0).all()
    assert (no_call_rows["rolling_call_count"] == 0).all()
    assert (no_call_rows["calls_vs_baseline"] == 0).all()
    assert (no_call_rows["rolling_negative_call_rate"] == 0).all()


def test_mismatched_call_and_transcript_is_rejected(tmp_path: Path) -> None:
    tables = cleaned_tables(tmp_path)
    transcripts = tables["transcripts"].iloc[1:].reset_index(drop=True)

    with pytest.raises(FeatureEngineeringError, match="Every call must match"):
        aggregate_daily_calls(tables["calls"], transcripts)


def test_duplicate_agent_day_is_rejected(tmp_path: Path) -> None:
    tables = cleaned_tables(tmp_path)
    tables["daily_labels"] = pd.concat(
        [tables["daily_labels"], tables["daily_labels"].iloc[[0]]],
        ignore_index=True,
    )

    with pytest.raises(FeatureEngineeringError, match="Agent-day rows must be unique"):
        build_agent_day_features(tables)


@pytest.mark.parametrize("value", [0, -1, 1.5, True])
def test_rolling_window_must_be_a_positive_integer(tmp_path: Path, value) -> None:
    tables = cleaned_tables(tmp_path)

    with pytest.raises(ValueError, match="rolling_window"):
        build_agent_day_features(tables, rolling_window=value)


def test_feature_summary_is_small_and_json_safe(tmp_path: Path) -> None:
    features = build_agent_day_features(cleaned_tables(tmp_path), rolling_window=2)

    summary = feature_summary(features)

    assert summary == {
        "rows": 20,
        "agents": 4,
        "start_date": "2026-07-01",
        "end_date": "2026-07-05",
        "rolling_window_days": 2,
        "target_metadata_columns_present": [],
    }
