"""Build reproducible summaries and accessible charts from scored Affectra data."""

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

RISK_LEVELS = ["Low", "Moderate", "High"]
COMPONENT_COLUMNS = [
    "workload_score",
    "efficiency_friction_score",
    "tone_score",
    "recovery_context_score",
]
CORRELATION_COLUMNS = [
    "rolling_call_count",
    "calls_vs_baseline",
    "acw_vs_baseline",
    "duration_vs_baseline",
    "rolling_avg_hold_seconds",
    "rolling_avg_transfer_count",
    "rolling_avg_sentiment_score",
    "rolling_negative_call_rate",
    "rolling_avg_negative_keyword_count",
]
REQUIRED_FEATURE_COLUMNS = {
    "agent_id",
    "team",
    "metric_date",
    "rolling_call_count",
    "calls_vs_baseline",
    "acw_vs_baseline",
    "duration_vs_baseline",
    "rolling_avg_hold_seconds",
    "rolling_avg_transfer_count",
    "rolling_avg_sentiment_score",
    "rolling_negative_call_rate",
    "rolling_avg_negative_keyword_count",
}
REQUIRED_SCORE_COLUMNS = {
    "agent_id",
    "team",
    "risk_score",
    "risk_level",
    *COMPONENT_COLUMNS,
}

BLUE = "#0072B2"
ORANGE = "#E69F00"
GREEN = "#009E73"
VERMILION = "#D55E00"
PURPLE = "#CC79A7"


class AnalyticsError(ValueError):
    """Raised when scored inputs cannot be analyzed safely."""


@dataclass(frozen=True)
class AnalyticsConfig:
    """Input and output locations for one analytics run."""

    input_dir: Path = Path("data/scored")
    output_dir: Path = Path("data/analytics")


def _require_columns(table: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(table.columns))
    if missing:
        raise AnalyticsError(f"{name} is missing columns: {', '.join(missing)}")
    if table.empty:
        raise AnalyticsError(f"{name} cannot be empty")


def validate_analytics_inputs(features: pd.DataFrame, scores: pd.DataFrame) -> None:
    """Validate the two processed inputs before calculating any output."""
    _require_columns(features, REQUIRED_FEATURE_COLUMNS, "agent_day_features.csv")
    _require_columns(scores, REQUIRED_SCORE_COLUMNS, "risk_scores.csv")

    numeric_feature_columns = sorted(REQUIRED_FEATURE_COLUMNS - {"team", "metric_date"})
    numeric_score_columns = ["agent_id", "risk_score", *COMPONENT_COLUMNS]
    for table, columns, name in (
        (features, numeric_feature_columns, "agent_day_features.csv"),
        (scores, numeric_score_columns, "risk_scores.csv"),
    ):
        numeric = table[columns].apply(pd.to_numeric, errors="coerce")
        if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy()).all():
            raise AnalyticsError(f"{name} must contain finite numeric values")

    dates = pd.to_datetime(features["metric_date"], errors="coerce", format="mixed")
    if dates.isna().any():
        raise AnalyticsError("agent_day_features.csv contains invalid metric_date values")
    if not scores["risk_level"].isin(RISK_LEVELS).all():
        raise AnalyticsError("risk_scores.csv contains an unknown risk_level")
    bounded = scores[["risk_score", *COMPONENT_COLUMNS]].apply(pd.to_numeric)
    if not bounded.ge(0).all().all() or not bounded.le(100).all().all():
        raise AnalyticsError("risk and component scores must be between 0 and 100")
    if scores["agent_id"].duplicated().any():
        raise AnalyticsError("risk_scores.csv must contain one current row per agent")
    if not set(scores["agent_id"]).issubset(set(features["agent_id"])):
        raise AnalyticsError("risk_scores.csv contains agents missing from feature history")


def load_analytics_inputs(input_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load and validate Sprint 3 feature history and current scores."""
    paths = {
        "features": input_dir / "agent_day_features.csv",
        "scores": input_dir / "risk_scores.csv",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise AnalyticsError("Missing analytics input file(s): " + ", ".join(missing))
    features = pd.read_csv(paths["features"])
    scores = pd.read_csv(paths["scores"])
    features["metric_date"] = pd.to_datetime(features["metric_date"], errors="coerce")
    validate_analytics_inputs(features, scores)
    return features, scores


def build_team_summary(scores: pd.DataFrame) -> pd.DataFrame:
    """Summarize current review scores by team without exposing agent names."""
    validate_columns = REQUIRED_SCORE_COLUMNS
    _require_columns(scores, validate_columns, "risk scores")
    grouped = scores.groupby("team", sort=True)
    summary = grouped["risk_score"].agg(
        agent_count="size", mean_risk_score="mean", median_risk_score="median", max_risk_score="max"
    )
    counts = pd.crosstab(scores["team"], scores["risk_level"]).reindex(
        columns=RISK_LEVELS, fill_value=0
    )
    counts.columns = [f"{level.lower()}_count" for level in RISK_LEVELS]
    component_means = grouped[COMPONENT_COLUMNS].mean().add_prefix("mean_")
    result = summary.join(counts).join(component_means).reset_index()
    result["review_count"] = result["moderate_count"] + result["high_count"]
    result["review_rate"] = result["review_count"] / result["agent_count"]
    numeric = result.select_dtypes(include="number").columns
    result[numeric] = result[numeric].round(4)
    return result


def build_risk_distribution(scores: pd.DataFrame) -> pd.DataFrame:
    """Count current agents in every ordered review level, including empty levels."""
    _require_columns(scores, {"risk_level"}, "risk scores")
    counts = scores["risk_level"].value_counts().reindex(RISK_LEVELS, fill_value=0)
    return pd.DataFrame(
        {
            "risk_level": RISK_LEVELS,
            "agent_count": counts.to_numpy(),
            "percentage": (counts.to_numpy() / len(scores) * 100).round(2),
        }
    )


def build_daily_trends(features: pd.DataFrame) -> pd.DataFrame:
    """Aggregate observable rolling features by day; these are not historical scores."""
    required = {
        "metric_date",
        "agent_id",
        "rolling_call_count",
        "calls_vs_baseline",
        "acw_vs_baseline",
        "duration_vs_baseline",
        "rolling_negative_call_rate",
        "rolling_avg_sentiment_score",
    }
    _require_columns(features, required, "agent-day features")
    trends = (
        features.groupby("metric_date", sort=True)
        .agg(
            agent_days=("agent_id", "size"),
            total_rolling_calls=("rolling_call_count", "sum"),
            mean_calls_vs_baseline=("calls_vs_baseline", "mean"),
            mean_acw_vs_baseline=("acw_vs_baseline", "mean"),
            mean_duration_vs_baseline=("duration_vs_baseline", "mean"),
            mean_negative_call_rate=("rolling_negative_call_rate", "mean"),
            mean_sentiment_score=("rolling_avg_sentiment_score", "mean"),
        )
        .reset_index()
    )
    numeric = trends.select_dtypes(include="number").columns
    trends[numeric] = trends[numeric].round(4)
    return trends


def build_correlation_matrix(
    features: pd.DataFrame, columns: Sequence[str] = CORRELATION_COLUMNS
) -> pd.DataFrame:
    """Calculate Pearson correlations between nonconstant observable features."""
    requested = list(columns)
    _require_columns(features, set(requested), "agent-day features")
    numeric = features[requested].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy()).all():
        raise AnalyticsError("correlation features must contain finite numeric values")
    usable = [column for column in requested if numeric[column].nunique() > 1]
    if len(usable) < 2:
        raise AnalyticsError("correlation analysis requires at least two varying features")
    return numeric[usable].corr(method="pearson").round(4)


def risk_distribution_chart(distribution: pd.DataFrame) -> go.Figure:
    labels = [f"{count} agents ({percentage:.1f}%)" for count, percentage in zip(
        distribution["agent_count"], distribution["percentage"], strict=True
    )]
    figure = go.Figure(
        go.Bar(
            x=distribution["risk_level"],
            y=distribution["agent_count"],
            text=labels,
            textposition="outside",
            marker_color=[BLUE, ORANGE, VERMILION],
            hovertemplate="%{x}: %{text}<extra></extra>",
        )
    )
    figure.update_layout(
        title="Current agents by review level",
        xaxis_title="Review level",
        yaxis_title="Agent count",
    )
    return figure


def baseline_trends_chart(trends: pd.DataFrame) -> go.Figure:
    figure = go.Figure()
    series = [
        ("mean_calls_vs_baseline", "Calls vs personal baseline", BLUE, "solid", "circle"),
        ("mean_acw_vs_baseline", "ACW vs personal baseline", ORANGE, "dash", "square"),
        ("mean_duration_vs_baseline", "Duration vs personal baseline", GREEN, "dot", "diamond"),
    ]
    for column, label, color, dash, symbol in series:
        figure.add_trace(
            go.Scatter(
                x=trends["metric_date"],
                y=trends[column],
                name=label,
                mode="lines+markers",
                line={"color": color, "dash": dash},
                marker={"symbol": symbol, "size": 7},
                hovertemplate=f"%{{x|%Y-%m-%d}}<br>{label}: %{{y:.2f}}×<extra></extra>",
            )
        )
    figure.add_hline(y=1.0, line_dash="dash", line_color="#555555", annotation_text="Baseline")
    figure.update_layout(
        title="Daily average workload and efficiency relative to personal baselines",
        xaxis_title="Metric date",
        yaxis_title="Team average ratio (1.0 = personal baseline)",
        legend_title="Observable metric",
    )
    return figure


def team_risk_box_chart(scores: pd.DataFrame) -> go.Figure:
    figure = go.Figure()
    colors = [BLUE, ORANGE, GREEN, PURPLE]
    for index, (team, group) in enumerate(scores.groupby("team", sort=True)):
        figure.add_trace(
            go.Box(
                x=[team] * len(group),
                y=group["risk_score"],
                name=str(team),
                boxpoints="all",
                jitter=0.25,
                pointpos=0,
                marker={"color": colors[index % len(colors)]},
                hovertemplate=f"Team: {team}<br>Score: %{{y:.1f}}/100<extra></extra>",
            )
        )
    figure.update_layout(
        title="Current decision-support score distribution by team",
        xaxis_title="Team",
        yaxis_title="Decision-support score (0–100)",
        showlegend=False,
    )
    return figure


def correlation_chart(correlations: pd.DataFrame) -> go.Figure:
    text_values = correlations.map(lambda value: f"{value:.2f}").to_numpy()
    figure = go.Figure(
        go.Heatmap(
            z=correlations.to_numpy(),
            x=correlations.columns,
            y=correlations.index,
            zmin=-1,
            zmax=1,
            zmid=0,
            colorscale="RdBu_r",
            text=text_values,
            texttemplate="%{text}",
            colorbar={"title": "Pearson r"},
            hovertemplate="%{y} vs %{x}<br>Pearson r: %{z:.2f}<extra></extra>",
        )
    )
    figure.update_layout(
        title="Linear correlations among observable agent-day features",
        xaxis_title="Observable feature",
        yaxis_title="Observable feature",
    )
    return figure


def _manifest(
    features: pd.DataFrame, scores: pd.DataFrame, correlations: pd.DataFrame
) -> dict[str, Any]:
    return {
        "input_rows": {"agent_day_features": len(features), "risk_scores": len(scores)},
        "outputs": [
            "team_summary.csv",
            "risk_distribution.csv",
            "daily_trends.csv",
            "correlation_matrix.csv",
            "charts/risk_distribution.html",
            "charts/baseline_trends.html",
            "charts/team_risk_box.html",
            "charts/feature_correlations.html",
        ],
        "correlation_method": "Pearson correlation among varying observable features only",
        "correlation_columns": list(correlations.columns),
        "charts": {
            "risk_distribution": {
                "accessible_cues": "bar positions plus count and percentage labels",
                "can_show": "the current number of agents in each review level",
                "cannot_prove": "change over time, cause, health status, or performance",
            },
            "baseline_trends": {
                "accessible_cues": "distinct line dashes, markers, labels, and a 1.0 reference",
                "can_show": "daily averages relative to agents' personal baselines",
                "cannot_prove": "individual experience, causation, or a diagnosis",
            },
            "team_risk_box": {
                "accessible_cues": "labeled axes, boxes, and visible individual points",
                "can_show": "the spread of current scores within each synthetic team",
                "cannot_prove": "fair team comparison, cause, or employee performance",
            },
            "feature_correlations": {
                "accessible_cues": "color plus a numeric value in every matrix cell",
                "can_show": "linear association between observable synthetic features",
                "cannot_prove": "causality, model validity, or real-world burnout prediction",
            },
        },
        "responsible_use": (
            "Exploratory decision support using synthetic data only. These summaries are not a "
            "diagnosis, performance rating, or validation of real-world burnout prediction."
        ),
    }


def run_analytics(config: AnalyticsConfig) -> dict[str, Any]:
    """Build tables, charts, and a manifest from processed Sprint 3 outputs."""
    features, scores = load_analytics_inputs(config.input_dir)
    team_summary = build_team_summary(scores)
    distribution = build_risk_distribution(scores)
    trends = build_daily_trends(features)
    correlations = build_correlation_matrix(features)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    chart_dir = config.output_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)

    tables = {
        "team_summary.csv": team_summary,
        "risk_distribution.csv": distribution,
        "daily_trends.csv": trends,
        "correlation_matrix.csv": correlations,
    }
    for filename, table in tables.items():
        table.to_csv(config.output_dir / filename, index=filename != "correlation_matrix.csv")

    charts = {
        "risk_distribution.html": risk_distribution_chart(distribution),
        "baseline_trends.html": baseline_trends_chart(trends),
        "team_risk_box.html": team_risk_box_chart(scores),
        "feature_correlations.html": correlation_chart(correlations),
    }
    for filename, figure in charts.items():
        pio.write_html(figure, chart_dir / filename, include_plotlyjs=True, full_html=True)

    manifest = _manifest(features, scores, correlations)
    (config.output_dir / "analytics_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/scored"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/analytics"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = run_analytics(AnalyticsConfig(args.input_dir, args.output_dir))
    print(f"Agent-day rows analyzed: {manifest['input_rows']['agent_day_features']}")
    print(f"Current agent scores analyzed: {manifest['input_rows']['risk_scores']}")
    print(f"Analytics written to: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
