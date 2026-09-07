"""Interactive Streamlit dashboard for Affectra's generated decision-support outputs."""

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src.analytics import build_risk_distribution, risk_distribution_chart, team_risk_box_chart
from src.dashboard import (
    PAGES,
    RISK_LEVELS,
    DashboardConfig,
    DashboardData,
    DashboardError,
    agent_trend_chart,
    calibration_chart,
    component_chart,
    filter_dashboard_data,
    load_dashboard_data,
    model_metrics_table,
    quality_tables,
)

RESPONSIBLE_USE = (
    "Decision support only. Affectra is not a diagnosis, employee-performance rating, "
    "or basis for punitive action. This demo uses synthetic data, and its model metrics "
    "do not validate real-world burnout prediction."
)


@st.cache_data(show_spinner="Loading validated Affectra outputs…")
def cached_dashboard_data(config: DashboardConfig) -> DashboardData:
    """Cache validated generated inputs between Streamlit reruns."""
    return load_dashboard_data(config)


def default_config() -> DashboardConfig:
    """Use normal project paths while allowing safe test/deployment overrides."""
    return DashboardConfig(
        scored_dir=Path(os.environ.get("AFFECTRA_SCORED_DIR", "data/scored")),
        processed_dir=Path(os.environ.get("AFFECTRA_PROCESSED_DIR", "data/processed")),
        models_dir=Path(os.environ.get("AFFECTRA_MODELS_DIR", "models")),
    )


def _global_filters(data: DashboardData) -> tuple[str, list[str], list[str], tuple]:
    st.sidebar.header("Explore")
    page = st.sidebar.radio("Page", PAGES, key="page")
    teams = sorted(data.scores["team"].astype(str).unique())
    selected_teams = st.sidebar.multiselect("Teams", teams, default=teams, key="teams")
    selected_risks = st.sidebar.multiselect(
        "Review levels", RISK_LEVELS, default=RISK_LEVELS, key="risk_levels"
    )
    minimum = data.features["metric_date"].min().date()
    maximum = data.features["metric_date"].max().date()
    date_range = st.sidebar.date_input(
        "Feature date range",
        value=(minimum, maximum),
        min_value=minimum,
        max_value=maximum,
        key="date_range",
    )
    st.sidebar.caption(
        "Filters affect overview and agent history; quality/model evidence remains whole-run."
    )
    return page, selected_teams, selected_risks, date_range


def render_overview(
    data: DashboardData,
    teams: list[str],
    risks: list[str],
    date_range: tuple,
) -> None:
    st.header("Team overview")
    search = st.text_input("Search synthetic agent name or ID", key="agent_search")
    start, end = date_range if len(date_range) == 2 else (None, None)
    scores, features = filter_dashboard_data(
        data,
        teams=teams,
        risk_levels=risks,
        start_date=start,
        end_date=end,
        search=search,
    )
    if scores.empty:
        st.warning("No current agent scores match these filters.")
        return
    columns = st.columns(4)
    columns[0].metric("Current agents", len(scores))
    columns[1].metric("Teams", scores["team"].nunique())
    columns[2].metric("Moderate / High", scores["risk_level"].isin(["Moderate", "High"]).sum())
    columns[3].metric("Average score", f"{scores['risk_score'].mean():.1f}/100")

    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            risk_distribution_chart(build_risk_distribution(scores)),
            width="stretch",
        )
        st.caption("Shows current review-level counts; cannot show cause, health, or performance.")
    with right:
        st.plotly_chart(team_risk_box_chart(scores), width="stretch")
        st.caption("Shows within-team spread; it is not a fair team ranking or causal comparison.")

    st.subheader("Current explainable scores")
    table = scores[
        ["agent_id", "name", "team", "role", "risk_score", "risk_level", "explanation"]
    ].sort_values(["risk_score", "agent_id"], ascending=[False, True])
    st.dataframe(table, width="stretch", hide_index=True)
    st.caption(f"Feature-history rows in the selected dates: {len(features):,}")


def render_agent_detail(
    data: DashboardData,
    teams: list[str],
    risks: list[str],
    date_range: tuple,
) -> None:
    st.header("Agent detail")
    start, end = date_range if len(date_range) == 2 else (None, None)
    scores, features = filter_dashboard_data(
        data,
        teams=teams,
        risk_levels=risks,
        start_date=start,
        end_date=end,
    )
    if scores.empty:
        st.warning("No agents match the team and review-level filters.")
        return
    options = {
        f"{row.name} — ID {row.agent_id}": int(row.agent_id)
        for row in scores.sort_values(["name", "agent_id"]).itertuples(index=False)
    }
    selected_label = st.selectbox("Synthetic agent", list(options), key="agent")
    agent_id = options[selected_label]
    score = scores.loc[scores["agent_id"] == agent_id].iloc[0]
    agent_features = features[features["agent_id"] == agent_id]

    columns = st.columns(3)
    columns[0].metric("Decision-support score", f"{score['risk_score']:.1f}/100")
    columns[1].metric("Review level", score["risk_level"])
    columns[2].metric("Team", score["team"])
    st.info(score["explanation"])
    st.plotly_chart(component_chart(score), width="stretch")

    with st.expander("Why this score?", expanded=True):
        st.write(score["workload_explanation"])
        st.write(score["efficiency_explanation"])
        st.write(score["tone_explanation"])
        st.write(score["recovery_explanation"])
    if agent_features.empty:
        st.warning("No feature history remains inside the selected date range.")
    else:
        st.plotly_chart(agent_trend_chart(agent_features), width="stretch")
        st.caption(
            "Ratios describe observable work patterns; they cannot diagnose an agent's wellbeing."
        )


def render_data_quality(data: DashboardData) -> None:
    st.header("Data quality")
    totals = data.quality["totals"]
    columns = st.columns(4)
    columns[0].metric("Status", data.quality["status"])
    columns[1].metric("Output rows", f"{totals.get('output_rows', 0):,}")
    columns[2].metric("Corrections", totals.get("corrections", 0))
    columns[3].metric("Outliers reported", totals.get("outliers_reported", 0))
    st.dataframe(quality_tables(data.quality), width="stretch", hide_index=True)
    st.subheader("Relationship checks")
    relationships = pd.DataFrame(
        sorted(data.quality.get("relationships", {}).items()),
        columns=["check", "count"],
    )
    st.dataframe(relationships, width="stretch", hide_index=True)
    st.info(
        "Outliers are reported, not automatically deleted. Review the source quality "
        "evidence before interpreting scores."
    )


def render_model_evaluation(data: DashboardData) -> None:
    st.header("Experimental model evaluation")
    st.warning(data.evaluation["interpretation"])
    metrics_table = model_metrics_table(data.evaluation)
    st.dataframe(metrics_table, width="stretch", hide_index=True)
    model = st.selectbox("Baseline model", metrics_table["model"].tolist(), key="model")
    metrics = data.evaluation["model_metrics"][model]
    columns = st.columns(4)
    columns[0].metric("Balanced accuracy", f"{metrics['balanced_accuracy']:.3f}")
    columns[1].metric("Precision", f"{metrics['precision']:.3f}")
    columns[2].metric("Recall", f"{metrics['recall']:.3f}")
    columns[3].metric("ROC AUC", f"{metrics['roc_auc']:.3f}")

    confusion = pd.DataFrame([metrics["confusion"]]).rename(
        columns=lambda name: name.replace("_", " ").title()
    )
    st.subheader("Confusion counts")
    st.dataframe(confusion, width="stretch", hide_index=True)
    st.plotly_chart(calibration_chart(data.calibration, model), width="stretch")
    st.caption("Calibration uses generated labels and cannot establish real-world validity.")

    st.subheader("Errors by synthetic team")
    team_errors = data.team_errors[data.team_errors["model"] == model]
    st.dataframe(team_errors, width="stretch", hide_index=True)
    st.caption("Use this to inspect uneven errors, not to rank teams or claim a fairness audit.")

    st.subheader("Transparent score comparison")
    st.json(data.evaluation["transparent_score_comparison"])
    split = data.training_manifest["split"]
    st.caption(
        f"Agent-disjoint holdout: {split['train_agents']} train agents, "
        f"{split['test_agents']} test agents, {split['overlapping_agents']} overlapping."
    )


def main() -> None:
    st.set_page_config(page_title="Affectra", page_icon="🫶", layout="wide")
    st.title("Affectra")
    st.caption("Explainable workload and stress-risk decision support")
    st.warning(RESPONSIBLE_USE)
    try:
        data = cached_dashboard_data(default_config())
    except DashboardError as error:
        st.error(str(error))
        st.code(
            "python -m src.data_generator\n"
            "python -m src.preprocessing\n"
            "python -m src.scoring\n"
            "python -m src.analytics\n"
            "python -m src.model_training"
        )
        st.stop()

    page, teams, risks, date_range = _global_filters(data)
    if page == "Overview":
        render_overview(data, teams, risks, date_range)
    elif page == "Agent detail":
        render_agent_detail(data, teams, risks, date_range)
    elif page == "Data quality":
        render_data_quality(data)
    else:
        render_model_evaluation(data)


if __name__ == "__main__":
    main()
