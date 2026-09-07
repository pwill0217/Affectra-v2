"""Validated data access, filtering, and figures for the Affectra dashboard."""

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go

from src.analytics import BLUE, GREEN, ORANGE, VERMILION, validate_analytics_inputs

PAGES = ["Overview", "Agent detail", "Data quality", "Model evaluation"]
RISK_LEVELS = ["Low", "Moderate", "High"]
MODEL_METRICS = [
    "accuracy",
    "balanced_accuracy",
    "precision",
    "recall",
    "f1",
    "roc_auc",
    "brier_score",
    "expected_calibration_error",
]


class DashboardError(ValueError):
    """Raised when dashboard inputs are missing or invalid."""


@dataclass(frozen=True)
class DashboardConfig:
    """Locations of generated dashboard inputs."""

    scored_dir: Path = Path("data/scored")
    processed_dir: Path = Path("data/processed")
    models_dir: Path = Path("models")


@dataclass
class DashboardData:
    """Validated tables and manifests used by all four pages."""

    features: pd.DataFrame
    scores: pd.DataFrame
    quality: dict[str, Any]
    evaluation: dict[str, Any]
    training_manifest: dict[str, Any]
    calibration: pd.DataFrame
    team_errors: pd.DataFrame


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DashboardError(f"Could not read valid JSON from {path}") from error
    if not isinstance(value, dict):
        raise DashboardError(f"Expected a JSON object in {path}")
    return value


def _require_files(config: DashboardConfig) -> dict[str, Path]:
    paths = {
        "features": config.scored_dir / "agent_day_features.csv",
        "scores": config.scored_dir / "risk_scores.csv",
        "quality": config.processed_dir / "data_quality_report.json",
        "evaluation": config.models_dir / "evaluation.json",
        "training_manifest": config.models_dir / "training_manifest.json",
        "calibration": config.models_dir / "calibration.csv",
        "team_errors": config.models_dir / "team_error_analysis.csv",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise DashboardError("Missing dashboard input file(s): " + ", ".join(missing))
    return paths


def _validate_supporting_inputs(data: DashboardData) -> None:
    if not {"status", "totals", "tables"}.issubset(data.quality):
        raise DashboardError("Data-quality report is missing status, totals, or tables")
    if not {"model_metrics", "transparent_score_comparison", "interpretation"}.issubset(
        data.evaluation
    ):
        raise DashboardError("Model evaluation is missing required sections")
    if not data.evaluation["model_metrics"]:
        raise DashboardError("Model evaluation must contain at least one model")
    if not {"split", "feature_allow_list", "limitations"}.issubset(data.training_manifest):
        raise DashboardError("Training manifest is missing required sections")
    calibration_columns = {"model", "bin", "mean_probability", "positive_rate", "rows"}
    if not calibration_columns.issubset(data.calibration.columns):
        raise DashboardError("Calibration table is missing required columns")
    error_columns = {
        "model",
        "team",
        "rows",
        "false_positives",
        "false_negatives",
        "accuracy",
    }
    if not error_columns.issubset(data.team_errors.columns):
        raise DashboardError("Team error table is missing required columns")


def load_dashboard_data(config: DashboardConfig) -> DashboardData:
    """Load and validate every generated input required by the dashboard."""
    paths = _require_files(config)
    try:
        features = pd.read_csv(paths["features"])
        scores = pd.read_csv(paths["scores"])
        calibration = pd.read_csv(paths["calibration"])
        team_errors = pd.read_csv(paths["team_errors"])
    except (OSError, pd.errors.ParserError) as error:
        raise DashboardError("Could not read a dashboard CSV input") from error
    features["metric_date"] = pd.to_datetime(features["metric_date"], errors="coerce")
    try:
        validate_analytics_inputs(features, scores)
    except ValueError as error:
        raise DashboardError(str(error)) from error
    data = DashboardData(
        features=features,
        scores=scores,
        quality=_read_json(paths["quality"]),
        evaluation=_read_json(paths["evaluation"]),
        training_manifest=_read_json(paths["training_manifest"]),
        calibration=calibration,
        team_errors=team_errors,
    )
    _validate_supporting_inputs(data)
    return data


def filter_dashboard_data(
    data: DashboardData,
    *,
    teams: list[str] | None = None,
    risk_levels: list[str] | None = None,
    start_date: date | pd.Timestamp | None = None,
    end_date: date | pd.Timestamp | None = None,
    search: str = "",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply shared interactive filters to current scores and feature history."""
    scores = data.scores.copy()
    if teams is not None:
        scores = scores[scores["team"].isin(teams)]
    if risk_levels is not None:
        scores = scores[scores["risk_level"].isin(risk_levels)]
    query = search.strip()
    if query:
        name_match = scores["name"].astype(str).str.contains(query, case=False, na=False)
        id_match = scores["agent_id"].astype(str).str.contains(query, case=False, na=False)
        scores = scores[name_match | id_match]

    features = data.features[data.features["agent_id"].isin(scores["agent_id"])].copy()
    if start_date is not None:
        features = features[features["metric_date"] >= pd.Timestamp(start_date)]
    if end_date is not None:
        features = features[features["metric_date"] <= pd.Timestamp(end_date)]
    return scores.reset_index(drop=True), features.reset_index(drop=True)


def component_chart(score: pd.Series) -> go.Figure:
    """Show one agent's four transparent components with numeric labels."""
    labels = ["Workload", "Efficiency friction", "Customer tone", "Recovery context"]
    values = [
        score["workload_score"],
        score["efficiency_friction_score"],
        score["tone_score"],
        score["recovery_context_score"],
    ]
    figure = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            text=[f"{value:.1f}/100" for value in values],
            textposition="outside",
            marker_color=[BLUE, ORANGE, VERMILION, GREEN],
            hovertemplate="%{y}: %{x:.1f}/100<extra></extra>",
        )
    )
    figure.update_layout(
        title="Transparent score components",
        xaxis={"title": "Component score (0–100)", "range": [0, 110]},
        yaxis_title="Component",
    )
    return figure


def agent_trend_chart(features: pd.DataFrame) -> go.Figure:
    """Show an agent's observable ratios with markers and distinct line styles."""
    if features.empty:
        raise DashboardError("Agent trend requires at least one filtered date")
    figure = go.Figure()
    series = [
        ("calls_vs_baseline", "Calls", BLUE, "solid", "circle"),
        ("acw_vs_baseline", "After-call work", ORANGE, "dash", "square"),
        ("duration_vs_baseline", "Call duration", GREEN, "dot", "diamond"),
    ]
    ordered = features.sort_values("metric_date")
    for column, label, color, dash, symbol in series:
        figure.add_trace(
            go.Scatter(
                x=ordered["metric_date"],
                y=ordered[column],
                name=label,
                mode="lines+markers",
                line={"color": color, "dash": dash},
                marker={"symbol": symbol},
                hovertemplate=f"%{{x|%Y-%m-%d}}<br>{label}: %{{y:.2f}}×<extra></extra>",
            )
        )
    figure.add_hline(y=1.0, line_dash="dash", line_color="#555555", annotation_text="Baseline")
    figure.update_layout(
        title="Observable metrics relative to personal baselines",
        xaxis_title="Metric date",
        yaxis_title="Ratio (1.0 = personal baseline)",
        legend_title="Metric",
    )
    return figure


def calibration_chart(calibration: pd.DataFrame, model: str) -> go.Figure:
    """Plot one model's calibration with a labeled ideal reference."""
    selected = calibration[calibration["model"] == model].sort_values("bin")
    if selected.empty:
        raise DashboardError(f"No calibration rows are available for {model}")
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=selected["mean_probability"],
            y=selected["positive_rate"],
            mode="lines+markers+text",
            text=[f"n={rows}" for rows in selected["rows"]],
            textposition="top center",
            name="Observed synthetic rate",
            line={"color": BLUE},
            marker={"symbol": "circle", "size": 9},
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode="lines",
            name="Ideal reference",
            line={"color": "#555555", "dash": "dash"},
        )
    )
    figure.update_layout(
        title=f"Synthetic-label calibration: {model}",
        xaxis={"title": "Mean predicted probability", "range": [0, 1]},
        yaxis={"title": "Observed synthetic positive rate", "range": [0, 1]},
    )
    return figure


def model_metrics_table(evaluation: dict[str, Any]) -> pd.DataFrame:
    """Turn nested model metrics into a readable comparison table."""
    rows = []
    for model, metrics in evaluation["model_metrics"].items():
        rows.append({"model": model, **{name: metrics.get(name) for name in MODEL_METRICS}})
    return pd.DataFrame(rows).sort_values("balanced_accuracy", ascending=False).reset_index(
        drop=True
    )


def quality_tables(quality: dict[str, Any]) -> pd.DataFrame:
    """Flatten per-table quality totals for the UI."""
    rows = []
    for table, details in quality["tables"].items():
        direct_corrections = sum(
            int(details.get(name, 0))
            for name in [
                "duplicate_key_rows_removed",
                "exact_duplicates_removed",
                "orphan_rows_removed",
                "rows_dropped_for_missing_keys",
            ]
        )
        nested_corrections = sum(
            int(value)
            for section in ["invalid_values_coerced", "values_imputed"]
            for value in details.get(section, {}).values()
        )
        outliers = sum(
            int(values.get("count", 0)) for values in details.get("outliers", {}).values()
        )
        rows.append(
            {
                "table": table,
                "input_rows": details.get("input_rows", 0),
                "output_rows": details.get("output_rows", 0),
                "corrections": direct_corrections + nested_corrections,
                "outliers_reported": outliers,
            }
        )
    return pd.DataFrame(rows).sort_values("table").reset_index(drop=True)
