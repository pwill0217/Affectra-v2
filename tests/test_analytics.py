"""Tests for reproducible, accessible exploratory analytics."""

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.analytics import (
    AnalyticsConfig,
    AnalyticsError,
    baseline_trends_chart,
    build_correlation_matrix,
    build_daily_trends,
    build_risk_distribution,
    build_team_summary,
    correlation_chart,
    load_analytics_inputs,
    main,
    risk_distribution_chart,
    run_analytics,
    team_risk_box_chart,
    validate_analytics_inputs,
)
from src.data_generator import GenerationConfig, generate_dataset, write_dataset
from src.preprocessing import PreprocessingConfig, run_preprocessing
from src.scoring import ScoringConfig, run_scoring


def score_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "agent_id": 1,
                "team": "Billing",
                "risk_score": 20.0,
                "risk_level": "Low",
                "workload_score": 10.0,
                "efficiency_friction_score": 20.0,
                "tone_score": 30.0,
                "recovery_context_score": 40.0,
            },
            {
                "agent_id": 2,
                "team": "Billing",
                "risk_score": 50.0,
                "risk_level": "Moderate",
                "workload_score": 50.0,
                "efficiency_friction_score": 40.0,
                "tone_score": 60.0,
                "recovery_context_score": 70.0,
            },
            {
                "agent_id": 3,
                "team": "Support",
                "risk_score": 80.0,
                "risk_level": "High",
                "workload_score": 80.0,
                "efficiency_friction_score": 70.0,
                "tone_score": 90.0,
                "recovery_context_score": 60.0,
            },
        ]
    )


def feature_rows() -> pd.DataFrame:
    rows = []
    for agent_id, team in ((1, "Billing"), (2, "Billing"), (3, "Support")):
        for day, multiplier in (("2026-08-01", 1.0), ("2026-08-02", 1.2)):
            rows.append(
                {
                    "agent_id": agent_id,
                    "team": team,
                    "metric_date": pd.Timestamp(day),
                    "rolling_call_count": 10 * agent_id * multiplier,
                    "calls_vs_baseline": 0.8 + agent_id * 0.1 * multiplier,
                    "acw_vs_baseline": 0.9 + agent_id * 0.1 * multiplier,
                    "duration_vs_baseline": 1.0 + agent_id * 0.1 * multiplier,
                    "rolling_avg_hold_seconds": 20 + agent_id * 10 * multiplier,
                    "rolling_avg_transfer_count": 0.1 * agent_id * multiplier,
                    "rolling_avg_sentiment_score": 0.2 - agent_id * 0.1 * multiplier,
                    "rolling_negative_call_rate": 0.02 * agent_id * multiplier,
                    "rolling_avg_negative_keyword_count": 0.05 * agent_id * multiplier,
                }
            )
    return pd.DataFrame(rows)


def write_scored_fixture(input_dir: Path) -> None:
    raw_dir = input_dir.parent / "raw"
    processed_dir = input_dir.parent / "processed"
    config = GenerationConfig(
        num_agents=8,
        start_date=date(2026, 8, 1),
        num_days=12,
        seed=41,
        output_dir=raw_dir,
    )
    write_dataset(generate_dataset(config), config)
    run_preprocessing(PreprocessingConfig(raw_dir, processed_dir))
    run_scoring(ScoringConfig(processed_dir, input_dir, rolling_window=5))


def test_team_summary_calculates_counts_rates_and_component_means() -> None:
    summary = build_team_summary(score_rows())

    billing = summary.loc[summary["team"] == "Billing"].iloc[0]
    assert billing["agent_count"] == 2
    assert billing["mean_risk_score"] == 35
    assert billing["median_risk_score"] == 35
    assert billing["low_count"] == 1
    assert billing["moderate_count"] == 1
    assert billing["high_count"] == 0
    assert billing["review_count"] == 1
    assert billing["review_rate"] == 0.5
    assert billing["mean_workload_score"] == 30


def test_distribution_is_ordered_and_keeps_empty_levels() -> None:
    scores = score_rows().query("risk_level != 'High'")
    distribution = build_risk_distribution(scores)

    assert distribution["risk_level"].tolist() == ["Low", "Moderate", "High"]
    assert distribution["agent_count"].tolist() == [1, 1, 0]
    assert distribution["percentage"].sum() == 100


def test_daily_trends_are_sorted_aggregates_not_backdated_scores() -> None:
    trends = build_daily_trends(feature_rows())

    assert trends["metric_date"].tolist() == [
        pd.Timestamp("2026-08-01"),
        pd.Timestamp("2026-08-02"),
    ]
    assert trends["agent_days"].tolist() == [3, 3]
    assert trends.loc[0, "total_rolling_calls"] == 60
    assert "risk_score" not in trends.columns


def test_correlation_is_symmetric_and_drops_constant_columns() -> None:
    features = feature_rows()
    features["constant"] = 1.0
    correlations = build_correlation_matrix(
        features, ["rolling_call_count", "calls_vs_baseline", "constant"]
    )

    assert list(correlations) == ["rolling_call_count", "calls_vs_baseline"]
    assert np.allclose(correlations, correlations.T)
    assert np.allclose(np.diag(correlations), 1)


def test_correlation_requires_two_varying_finite_features() -> None:
    features = feature_rows()
    features["one"] = 1.0
    features["two"] = 2.0
    with pytest.raises(AnalyticsError, match="at least two varying"):
        build_correlation_matrix(features, ["one", "two"])
    features.loc[0, "calls_vs_baseline"] = np.inf
    with pytest.raises(AnalyticsError, match="finite"):
        build_correlation_matrix(features, ["calls_vs_baseline", "acw_vs_baseline"])


def test_validation_rejects_bad_dates_levels_ranges_duplicates_and_orphans() -> None:
    features = feature_rows()
    scores = score_rows()

    bad_date = features.astype({"metric_date": "object"})
    bad_date.loc[0, "metric_date"] = "not-a-date"
    with pytest.raises(AnalyticsError, match="invalid metric_date"):
        validate_analytics_inputs(bad_date, scores)

    bad_level = scores.copy()
    bad_level.loc[0, "risk_level"] = "Urgent"
    with pytest.raises(AnalyticsError, match="unknown risk_level"):
        validate_analytics_inputs(features, bad_level)

    bad_range = scores.copy()
    bad_range.loc[0, "risk_score"] = 101
    with pytest.raises(AnalyticsError, match="between 0 and 100"):
        validate_analytics_inputs(features, bad_range)

    duplicated = pd.concat([scores, scores.iloc[[0]]], ignore_index=True)
    with pytest.raises(AnalyticsError, match="one current row"):
        validate_analytics_inputs(features, duplicated)

    orphan = scores.copy()
    orphan.loc[0, "agent_id"] = 999
    with pytest.raises(AnalyticsError, match="missing from feature history"):
        validate_analytics_inputs(features, orphan)


def test_loader_reports_missing_and_invalid_files(tmp_path: Path) -> None:
    with pytest.raises(AnalyticsError, match="Missing analytics input"):
        load_analytics_inputs(tmp_path)

    feature_rows().drop(columns="team").to_csv(tmp_path / "agent_day_features.csv", index=False)
    score_rows().to_csv(tmp_path / "risk_scores.csv", index=False)
    with pytest.raises(AnalyticsError, match="missing columns: team"):
        load_analytics_inputs(tmp_path)


def test_charts_include_labels_and_non_color_accessibility_cues() -> None:
    distribution = build_risk_distribution(score_rows())
    trends = build_daily_trends(feature_rows())
    correlations = build_correlation_matrix(feature_rows())

    bars = risk_distribution_chart(distribution)
    assert bars.data[0].type == "bar"
    assert all("agents" in text for text in bars.data[0].text)
    assert bars.layout.yaxis.title.text == "Agent count"

    lines = baseline_trends_chart(trends)
    assert {trace.line.dash for trace in lines.data} == {"solid", "dash", "dot"}
    assert len({trace.marker.symbol for trace in lines.data}) == 3
    assert lines.layout.yaxis.title.text.startswith("Team average ratio")
    assert len(lines.layout.shapes) == 1

    boxes = team_risk_box_chart(score_rows())
    assert all(trace.type == "box" and trace.boxpoints == "all" for trace in boxes.data)
    assert boxes.layout.yaxis.title.text == "Decision-support score (0–100)"

    heatmap = correlation_chart(correlations)
    assert heatmap.data[0].type == "heatmap"
    assert heatmap.data[0].texttemplate == "%{text}"
    assert heatmap.data[0].zmin == -1 and heatmap.data[0].zmax == 1


def test_run_analytics_writes_reproducible_tables_charts_and_manifest(tmp_path: Path) -> None:
    input_dir = tmp_path / "scored"
    output_dir = tmp_path / "analytics"
    write_scored_fixture(input_dir)

    manifest = run_analytics(AnalyticsConfig(input_dir, output_dir))

    output_files = {
        str(path.relative_to(output_dir)) for path in output_dir.rglob("*") if path.is_file()
    }
    assert output_files == {
        "team_summary.csv",
        "risk_distribution.csv",
        "daily_trends.csv",
        "correlation_matrix.csv",
        "analytics_manifest.json",
        "charts/risk_distribution.html",
        "charts/baseline_trends.html",
        "charts/team_risk_box.html",
        "charts/feature_correlations.html",
    }
    assert len(manifest["charts"]) == 4
    assert all("cannot_prove" in details for details in manifest["charts"].values())
    assert "real-world burnout prediction" in manifest["responsible_use"]
    saved = json.loads((output_dir / "analytics_manifest.json").read_text())
    assert saved == manifest
    assert "Plotly.newPlot" in (output_dir / "charts" / "risk_distribution.html").read_text()


def test_cli_runs_end_to_end(tmp_path: Path, capsys) -> None:
    input_dir = tmp_path / "scored"
    output_dir = tmp_path / "analytics"
    write_scored_fixture(input_dir)

    exit_code = main(["--input-dir", str(input_dir), "--output-dir", str(output_dir)])

    assert exit_code == 0
    assert (output_dir / "analytics_manifest.json").is_file()
    output = capsys.readouterr().out
    assert "Agent-day rows analyzed: 96" in output
    assert "Current agent scores analyzed: 8" in output
