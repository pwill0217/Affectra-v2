"""Tests for bounded, configurable, and explainable Affectra scores."""

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.data_generator import GenerationConfig, generate_dataset, write_dataset
from src.preprocessing import PreprocessingConfig, run_preprocessing
from src.scoring import (
    COMPONENT_COLUMNS,
    ScoreWeights,
    ScoringConfig,
    ScoringError,
    calculate_component_scores,
    main,
    risk_level,
    run_scoring,
    score_agent_features,
)


def feature_row(**overrides) -> dict[str, object]:
    row: dict[str, object] = {
        "agent_id": 1,
        "name": "Demo Agent",
        "team": "Billing",
        "role": "Customer Service Agent",
        "metric_date": pd.Timestamp("2026-07-01"),
        "calls_vs_baseline": 1.0,
        "acw_vs_baseline": 1.0,
        "duration_vs_baseline": 1.0,
        "rolling_avg_hold_seconds": 30.0,
        "rolling_avg_transfer_count": 0.2,
        "rolling_avg_sentiment_score": 0.0,
        "rolling_negative_call_rate": 0.0,
        "rolling_avg_negative_keyword_count": 0.0,
        "pto_balance_hours": 80.0,
        "vacation_days_available": 10.0,
        "pto_used_hours_30d": 16.0,
        "days_since_pto_at_snapshot": 14.0,
    }
    row.update(overrides)
    return row


def write_processed_fixture(input_dir: Path) -> None:
    raw_dir = input_dir.parent / "raw"
    config = GenerationConfig(
        num_agents=4,
        start_date=date(2026, 8, 1),
        num_days=5,
        seed=37,
        output_dir=raw_dir,
    )
    write_dataset(generate_dataset(config), config)
    run_preprocessing(PreprocessingConfig(raw_dir, input_dir))


def test_default_weights_match_documented_40_20_25_15_plan() -> None:
    assert ScoreWeights().as_dict() == {
        "workload": 0.40,
        "efficiency_friction": 0.20,
        "tone": 0.25,
        "recovery_context": 0.15,
    }


@pytest.mark.parametrize(
    "values",
    [
        {"workload": -0.1, "efficiency_friction": 0.3, "tone": 0.5, "recovery_context": 0.3},
        {"workload": 0.4, "efficiency_friction": 0.2, "tone": 0.2, "recovery_context": 0.1},
        {"workload": np.inf, "efficiency_friction": 0.0, "tone": 0.0, "recovery_context": 0.0},
        {"workload": True, "efficiency_friction": 0.2, "tone": 0.25, "recovery_context": 0.15},
    ],
)
def test_invalid_weights_are_rejected(values: dict[str, float]) -> None:
    with pytest.raises(ValueError, match="weight|sum"):
        ScoreWeights(**values)


def test_component_scores_are_bounded_at_zero_and_one_hundred() -> None:
    low = feature_row(
        calls_vs_baseline=0.0,
        acw_vs_baseline=0.0,
        duration_vs_baseline=0.0,
        rolling_avg_hold_seconds=0.0,
        rolling_avg_transfer_count=0.0,
    )
    high = feature_row(
        agent_id=2,
        calls_vs_baseline=3.0,
        acw_vs_baseline=3.0,
        duration_vs_baseline=3.0,
        rolling_avg_hold_seconds=400.0,
        rolling_avg_transfer_count=3.0,
        rolling_avg_sentiment_score=-1.0,
        rolling_negative_call_rate=1.0,
        rolling_avg_negative_keyword_count=8.0,
        pto_balance_hours=0.0,
        vacation_days_available=0.0,
        pto_used_hours_30d=0.0,
        days_since_pto_at_snapshot=365.0,
    )

    scored = calculate_component_scores(pd.DataFrame([low, high]))

    assert (scored.loc[0, COMPONENT_COLUMNS] == 0).all()
    assert (scored.loc[1, COMPONENT_COLUMNS] == 100).all()
    assert scored[COMPONENT_COLUMNS].min().min() >= 0
    assert scored[COMPONENT_COLUMNS].max().max() <= 100


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, "Low"),
        (34.99, "Low"),
        (35, "Moderate"),
        (64.99, "Moderate"),
        (65, "High"),
        (100, "High"),
    ],
)
def test_risk_level_boundaries(score: float, expected: str) -> None:
    assert risk_level(score) == expected


@pytest.mark.parametrize("score", [-0.01, 100.01, np.nan, np.inf])
def test_invalid_risk_scores_are_rejected(score: float) -> None:
    with pytest.raises(ValueError, match="between 0 and 100"):
        risk_level(score)


def test_only_latest_agent_day_is_scored_and_explanations_show_evidence() -> None:
    rows = [
        feature_row(metric_date=pd.Timestamp("2026-07-01"), calls_vs_baseline=3.0),
        feature_row(metric_date=pd.Timestamp("2026-07-02"), calls_vs_baseline=0.95),
        feature_row(agent_id=2, name="Second Agent", metric_date=pd.Timestamp("2026-07-02")),
    ]

    scored = score_agent_features(pd.DataFrame(rows))

    assert len(scored) == 2
    assert set(scored["metric_date"]) == {pd.Timestamp("2026-07-02")}
    agent_one = scored.loc[scored["agent_id"] == 1].iloc[0]
    assert agent_one["workload_score"] == 50
    assert "0.95×" in agent_one["workload_explanation"]
    assert "supportive conversation" in agent_one["explanation"]
    assert agent_one["risk_score"] == pytest.approx(
        agent_one[
            [
                "workload_contribution",
                "efficiency_friction_contribution",
                "tone_contribution",
                "recovery_context_contribution",
            ]
        ].sum()
    )


def test_custom_weights_change_the_result_transparently() -> None:
    features = pd.DataFrame([feature_row(calls_vs_baseline=0.95)])
    workload_only = ScoreWeights(
        workload=1.0,
        efficiency_friction=0.0,
        tone=0.0,
        recovery_context=0.0,
    )

    scored = score_agent_features(features, weights=workload_only)

    assert scored.loc[0, "workload_score"] == 50
    assert scored.loc[0, "risk_score"] == 50
    assert scored.loc[0, "risk_level"] == "Moderate"
    assert scored.loc[0, "workload_contribution"] == 50
    assert scored.loc[0, "tone_contribution"] == 0


def test_missing_or_nonfinite_features_are_rejected() -> None:
    missing = pd.DataFrame([feature_row()]).drop(columns="calls_vs_baseline")
    with pytest.raises(ScoringError, match="missing columns"):
        score_agent_features(missing)

    nonfinite = pd.DataFrame([feature_row(calls_vs_baseline=np.nan)])
    with pytest.raises(ScoringError, match="finite numeric"):
        score_agent_features(nonfinite)


def test_scoring_config_validates_rolling_window() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        ScoringConfig(rolling_window=0)
    with pytest.raises(ValueError, match="integer"):
        ScoringConfig(rolling_window=True)


def test_run_scoring_writes_reproducible_outputs(tmp_path: Path) -> None:
    input_dir = tmp_path / "processed"
    output_dir = tmp_path / "scored"
    write_processed_fixture(input_dir)

    features, scores, quality = run_scoring(
        ScoringConfig(input_dir, output_dir, rolling_window=3)
    )

    assert len(features) == 20
    assert len(scores) == 4
    assert quality["status"] in {"passed", "passed_with_warnings"}
    assert {path.name for path in output_dir.iterdir()} == {
        "agent_day_features.csv",
        "risk_scores.csv",
        "scoring_manifest.json",
    }
    manifest = json.loads((output_dir / "scoring_manifest.json").read_text())
    assert manifest["weights"] == ScoreWeights().as_dict()
    assert manifest["normalization_ranges"]["calls_vs_baseline"] == {
        "low": 0.75,
        "high": 1.15,
        "direction": "higher",
    }
    assert manifest["feature_summary"]["rolling_window_days"] == 3
    assert manifest["feature_summary"]["target_metadata_columns_present"] == []
    assert manifest["decision_support_only"] is True


def test_cli_accepts_custom_weights_and_runs_end_to_end(tmp_path: Path, capsys) -> None:
    input_dir = tmp_path / "processed"
    output_dir = tmp_path / "scored"
    write_processed_fixture(input_dir)

    exit_code = main(
        [
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--rolling-window",
            "2",
            "--workload-weight",
            "0.5",
            "--efficiency-weight",
            "0.2",
            "--tone-weight",
            "0.2",
            "--recovery-weight",
            "0.1",
        ]
    )

    assert exit_code == 0
    assert (output_dir / "risk_scores.csv").is_file()
    manifest = json.loads((output_dir / "scoring_manifest.json").read_text())
    assert manifest["weights"]["workload"] == 0.5
    assert "Latest agent scores: 4" in capsys.readouterr().out
