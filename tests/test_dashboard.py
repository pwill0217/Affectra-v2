"""Tests for dashboard input validation, filtering, figures, and Streamlit pages."""

import json
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.dashboard import (
    DashboardConfig,
    DashboardError,
    agent_trend_chart,
    calibration_chart,
    component_chart,
    filter_dashboard_data,
    load_dashboard_data,
    model_metrics_table,
    quality_tables,
)


def feature_rows() -> pd.DataFrame:
    rows = []
    for agent_id, name, team in (
        (1, "Alex Demo", "Billing"),
        (2, "Blair Demo", "Support"),
        (3, "Casey Demo", "Billing"),
    ):
        for index, metric_date in enumerate(pd.date_range("2026-07-01", periods=3)):
            rows.append(
                {
                    "agent_id": agent_id,
                    "name": name,
                    "team": team,
                    "metric_date": metric_date,
                    "rolling_call_count": 30 + agent_id + index,
                    "calls_vs_baseline": 0.8 + 0.1 * agent_id + 0.05 * index,
                    "acw_vs_baseline": 0.9 + 0.1 * agent_id + 0.03 * index,
                    "duration_vs_baseline": 1.0 + 0.1 * agent_id + 0.02 * index,
                    "rolling_avg_hold_seconds": 20 + 10 * agent_id + index,
                    "rolling_avg_transfer_count": 0.1 * agent_id + 0.01 * index,
                    "rolling_avg_sentiment_score": 0.2 - 0.1 * agent_id,
                    "rolling_negative_call_rate": 0.02 * agent_id,
                    "rolling_avg_negative_keyword_count": 0.05 * agent_id,
                }
            )
    return pd.DataFrame(rows)


def score_rows() -> pd.DataFrame:
    rows = []
    for agent_id, name, team, score, level in (
        (1, "Alex Demo", "Billing", 20.0, "Low"),
        (2, "Blair Demo", "Support", 50.0, "Moderate"),
        (3, "Casey Demo", "Billing", 70.0, "High"),
    ):
        rows.append(
            {
                "agent_id": agent_id,
                "name": name,
                "team": team,
                "role": "Customer Service Agent",
                "risk_score": score,
                "risk_level": level,
                "workload_score": score,
                "efficiency_friction_score": score - 5,
                "tone_score": score + 5,
                "recovery_context_score": score,
                "explanation": f"{level} review level. Supportive review only.",
                "workload_explanation": "Calls compared with personal baseline.",
                "efficiency_explanation": "ACW, duration, hold, and transfers.",
                "tone_explanation": "Customer interaction tone indicators.",
                "recovery_explanation": "Current recovery snapshot context.",
            }
        )
    return pd.DataFrame(rows)


def quality_report() -> dict:
    return {
        "status": "passed_with_warnings",
        "totals": {
            "input_rows": 100,
            "output_rows": 99,
            "corrections": 1,
            "outliers_reported": 2,
            "relationship_warnings": 0,
        },
        "relationships": {"unmatched_calls_removed": 0},
        "tables": {
            "agents": {
                "input_rows": 3,
                "output_rows": 3,
                "exact_duplicates_removed": 1,
                "duplicate_key_rows_removed": 0,
                "orphan_rows_removed": 0,
                "rows_dropped_for_missing_keys": 0,
                "invalid_values_coerced": {"team": 1},
                "values_imputed": {"team": 1},
                "outliers": {"baseline": {"count": 2}},
            }
        },
    }


def evaluation_report() -> dict:
    metric = {
        "accuracy": 0.9,
        "balanced_accuracy": 0.8,
        "precision": 0.6,
        "recall": 0.7,
        "f1": 0.65,
        "roc_auc": 0.85,
        "brier_score": 0.12,
        "expected_calibration_error": 0.08,
        "confusion": {
            "true_negative": 8,
            "false_positive": 1,
            "false_negative": 1,
            "true_positive": 2,
        },
    }
    second = {**metric, "balanced_accuracy": 0.7, "roc_auc": 0.75}
    return {
        "model_metrics": {"random_forest": metric, "dummy_prior": second},
        "transparent_score_comparison": {
            "rows": 3,
            "review_flag_agreement": 0.67,
            "warning": "Descriptive only.",
        },
        "interpretation": "Synthetic metrics do not validate real-world burnout prediction.",
    }


def write_dashboard_fixture(root: Path) -> DashboardConfig:
    scored = root / "scored"
    processed = root / "processed"
    models = root / "models"
    scored.mkdir(parents=True)
    processed.mkdir(parents=True)
    models.mkdir(parents=True)
    feature_rows().to_csv(scored / "agent_day_features.csv", index=False)
    score_rows().to_csv(scored / "risk_scores.csv", index=False)
    (processed / "data_quality_report.json").write_text(json.dumps(quality_report()))
    (models / "evaluation.json").write_text(json.dumps(evaluation_report()))
    manifest = {
        "split": {"train_agents": 8, "test_agents": 3, "overlapping_agents": 0},
        "feature_allow_list": ["calls_vs_baseline"],
        "limitations": "Synthetic only.",
    }
    (models / "training_manifest.json").write_text(json.dumps(manifest))
    pd.DataFrame(
        {
            "model": ["random_forest", "random_forest", "dummy_prior"],
            "bin": [1, 2, 1],
            "mean_probability": [0.1, 0.7, 0.2],
            "positive_rate": [0.0, 0.5, 0.1],
            "rows": [8, 4, 12],
        }
    ).to_csv(models / "calibration.csv", index=False)
    pd.DataFrame(
        {
            "model": ["random_forest", "dummy_prior"],
            "team": ["Billing", "Billing"],
            "rows": [8, 8],
            "false_positives": [1, 0],
            "false_negatives": [1, 2],
            "accuracy": [0.75, 0.75],
        }
    ).to_csv(models / "team_error_analysis.csv", index=False)
    return DashboardConfig(scored, processed, models)


def test_loader_reads_and_validates_complete_bundle(tmp_path: Path) -> None:
    config = write_dashboard_fixture(tmp_path)

    data = load_dashboard_data(config)

    assert len(data.features) == 9
    assert len(data.scores) == 3
    assert data.quality["status"] == "passed_with_warnings"
    assert set(data.evaluation["model_metrics"]) == {"random_forest", "dummy_prior"}


def test_loader_reports_missing_invalid_json_and_supporting_schema(tmp_path: Path) -> None:
    with pytest.raises(DashboardError, match="Missing dashboard input"):
        load_dashboard_data(DashboardConfig(tmp_path, tmp_path, tmp_path))

    config = write_dashboard_fixture(tmp_path / "invalid-json")
    (config.models_dir / "evaluation.json").write_text("not json")
    with pytest.raises(DashboardError, match="valid JSON"):
        load_dashboard_data(config)

    config = write_dashboard_fixture(tmp_path / "invalid-schema")
    (config.models_dir / "evaluation.json").write_text(json.dumps({"model_metrics": {}}))
    with pytest.raises(DashboardError, match="missing required sections"):
        load_dashboard_data(config)


def test_filters_apply_team_risk_date_and_search(tmp_path: Path) -> None:
    data = load_dashboard_data(write_dashboard_fixture(tmp_path))

    scores, features = filter_dashboard_data(
        data,
        teams=["Billing"],
        risk_levels=["High"],
        start_date=pd.Timestamp("2026-07-02"),
        end_date=pd.Timestamp("2026-07-03"),
        search="casey",
    )

    assert scores["agent_id"].tolist() == [3]
    assert len(features) == 2
    assert features["metric_date"].min() == pd.Timestamp("2026-07-02")
    id_scores, _ = filter_dashboard_data(data, search="2")
    assert id_scores["agent_id"].tolist() == [2]


def test_accessible_dashboard_figures_and_tables(tmp_path: Path) -> None:
    data = load_dashboard_data(write_dashboard_fixture(tmp_path))
    score = data.scores.iloc[1]

    components = component_chart(score)
    assert components.data[0].type == "bar"
    assert all("/100" in label for label in components.data[0].text)
    assert components.layout.xaxis.title.text == "Component score (0–100)"

    trends = agent_trend_chart(data.features[data.features["agent_id"] == 1])
    assert {trace.line.dash for trace in trends.data} == {"solid", "dash", "dot"}
    assert len({trace.marker.symbol for trace in trends.data}) == 3
    with pytest.raises(DashboardError, match="at least one"):
        agent_trend_chart(data.features.iloc[0:0])

    calibration = calibration_chart(data.calibration, "random_forest")
    assert len(calibration.data) == 2
    assert calibration.data[0].text[0].startswith("n=")
    with pytest.raises(DashboardError, match="No calibration"):
        calibration_chart(data.calibration, "missing")

    metrics = model_metrics_table(data.evaluation)
    assert metrics.iloc[0]["model"] == "random_forest"
    quality = quality_tables(data.quality)
    assert quality.iloc[0]["corrections"] == 3
    assert quality.iloc[0]["outliers_reported"] == 2


def test_streamlit_all_four_pages_render_without_exceptions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = write_dashboard_fixture(tmp_path)
    monkeypatch.setenv("AFFECTRA_SCORED_DIR", str(config.scored_dir))
    monkeypatch.setenv("AFFECTRA_PROCESSED_DIR", str(config.processed_dir))
    monkeypatch.setenv("AFFECTRA_MODELS_DIR", str(config.models_dir))

    app_path = Path(__file__).parents[1] / "src" / "app.py"
    app = AppTest.from_file(app_path, default_timeout=20).run()

    assert not app.exception
    assert app.title[0].value == "Affectra"
    assert app.header[0].value == "Team overview"
    assert any("Decision support only" in warning.value for warning in app.warning)

    for page, expected_header in (
        ("Agent detail", "Agent detail"),
        ("Data quality", "Data quality"),
        ("Model evaluation", "Experimental model evaluation"),
    ):
        app.sidebar.radio[0].set_value(page)
        app.run()
        assert not app.exception
        assert any(header.value == expected_header for header in app.header)
