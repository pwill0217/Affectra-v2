"""Tests for operational health and drift indicators."""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.analytics import REQUIRED_FEATURE_COLUMNS, REQUIRED_SCORE_COLUMNS
from src.dashboard import DashboardData
from src.monitoring import (
    MonitoringError,
    MonitoringThresholds,
    build_health_report,
    compare_with_baseline,
    schema_indicators,
    score_distribution,
    write_json_safely,
)


def dashboard_data() -> DashboardData:
    features = pd.DataFrame(
        [
            {
                **{column: 1.0 for column in REQUIRED_FEATURE_COLUMNS},
                "agent_id": agent_id,
                "team": "Demo",
                "metric_date": "2026-09-01",
                "name": f"Agent {agent_id}",
            }
            for agent_id in (1, 2, 3)
        ]
    )
    scores = pd.DataFrame(
        [
            {
                **{column: 20.0 for column in REQUIRED_SCORE_COLUMNS},
                "agent_id": 1,
                "team": "Demo",
                "risk_score": 20.0,
                "risk_level": "Low",
                "metric_date": "2026-09-01",
            },
            {
                **{column: 50.0 for column in REQUIRED_SCORE_COLUMNS},
                "agent_id": 2,
                "team": "Demo",
                "risk_score": 50.0,
                "risk_level": "Moderate",
                "metric_date": "2026-09-01",
            },
            {
                **{column: 80.0 for column in REQUIRED_SCORE_COLUMNS},
                "agent_id": 3,
                "team": "Demo",
                "risk_score": 80.0,
                "risk_level": "High",
                "metric_date": "2026-09-01",
            },
        ]
    )
    return DashboardData(
        features=features,
        scores=scores,
        quality={"status": "passed", "totals": {}, "tables": {}},
        evaluation={
            "model_metrics": {"demo": {"accuracy": 0.5}},
            "best_baseline_by_balanced_accuracy": "demo",
            "transparent_score_comparison": {},
            "interpretation": "Synthetic only",
        },
        training_manifest={
            "dataset_fingerprint_sha256": "a" * 64,
            "split": {"overlapping_agents": 0},
            "feature_allow_list": [],
            "limitations": "Synthetic only",
        },
        calibration=pd.DataFrame(),
        team_errors=pd.DataFrame(),
    )


def test_schema_and_distribution_are_aggregate_and_reproducible() -> None:
    data = dashboard_data()
    schema = schema_indicators(data)
    distribution = score_distribution(data.scores)

    assert schema["agent_day_features"]["missing_required"] == []
    assert schema["risk_scores"]["missing_required"] == []
    assert "name" in schema["agent_day_features"]["extra_columns"]
    assert len(schema["risk_scores"]["columns_sha256"]) == 64
    assert distribution["rows"] == 3
    assert distribution["mean"] == 50.0
    assert distribution["median"] == 50.0
    assert distribution["risk_level_shares"] == {
        "Low": 0.333333,
        "Moderate": 0.333333,
        "High": 0.333333,
    }
    assert "name" not in json.dumps(distribution)


def test_distribution_rejects_empty_or_nonfinite_scores() -> None:
    with pytest.raises(MonitoringError, match="non-empty finite"):
        score_distribution(pd.DataFrame({"risk_score": []}))
    with pytest.raises(MonitoringError, match="non-empty finite"):
        score_distribution(pd.DataFrame({"risk_score": [float("inf")]}))


@pytest.mark.parametrize("value", [-1, float("inf"), True, "ten"])
def test_thresholds_must_be_finite_nonnegative_numbers(value: object) -> None:
    with pytest.raises(ValueError):
        MonitoringThresholds(mean_score_delta=value)  # type: ignore[arg-type]


def test_explicit_baseline_creation_and_clean_comparison(tmp_path: Path) -> None:
    data = dashboard_data()
    baseline_path = tmp_path / "baseline.json"
    report, baseline = build_health_report(
        data, baseline_path=baseline_path, initialize_baseline=True
    )

    assert report["status"] == "healthy"
    assert report["baseline_status"] == "created"
    assert report["comparison"]["alerts"] == []
    assert baseline == {
        "schema": report["schema"],
        "score_distribution": report["score_distribution"],
    }
    write_json_safely(baseline_path, baseline, overwrite=False)
    compared, new_baseline = build_health_report(data, baseline_path=baseline_path)
    assert compared["baseline_status"] == "compared"
    assert compared["status"] == "healthy"
    assert new_baseline is None


def test_drift_alerts_and_failed_health_check_require_review(tmp_path: Path) -> None:
    data = dashboard_data()
    baseline_path = tmp_path / "baseline.json"
    _, baseline = build_health_report(data, baseline_path=baseline_path, initialize_baseline=True)
    assert baseline is not None
    write_json_safely(baseline_path, baseline)

    data.scores["risk_score"] = [80.0, 85.0, 90.0]
    data.scores["risk_level"] = "High"
    data.training_manifest["split"]["overlapping_agents"] = 1
    data.features["new_column"] = 1
    report, _ = build_health_report(data, baseline_path=baseline_path)

    assert report["status"] == "review"
    assert report["checks"]["model_agent_overlap_is_zero"] is False
    assert set(report["comparison"]["alerts"]) == {
        "schema_changed",
        "mean_score_shift",
        "risk_level_share_shift",
    }
    assert report["comparison"]["schema_changes"] == ["agent_day_features"]


def test_compare_uses_strict_threshold_and_handles_missing_previous_table() -> None:
    current = {
        "schema": {"scores": {"columns_sha256": "new"}},
        "score_distribution": {
            "mean": 20.0,
            "risk_level_shares": {"Low": 1.0, "Moderate": 0.0, "High": 0.0},
        },
    }
    baseline = {
        "schema": {},
        "score_distribution": {
            "mean": 10.0,
            "risk_level_shares": {"Low": 0.8},
        },
    }
    result = compare_with_baseline(current, baseline, MonitoringThresholds(10.0, 0.2))
    assert result["alerts"] == ["schema_changed"]
    assert result["risk_level_share_deltas"]["Moderate"] == 0.0


def test_missing_or_invalid_baseline_and_safe_write_errors(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    with pytest.raises(MonitoringError, match="rerun once"):
        build_health_report(dashboard_data(), baseline_path=path)

    path.write_text("not json")
    with pytest.raises(MonitoringError, match="valid monitoring baseline"):
        build_health_report(dashboard_data(), baseline_path=path)

    path.write_text(json.dumps({"schema": {}}))
    with pytest.raises(MonitoringError, match="missing schema"):
        build_health_report(dashboard_data(), baseline_path=path)

    output = tmp_path / "nested" / "report.json"
    write_json_safely(output, {"status": "healthy"})
    assert json.loads(output.read_text()) == {"status": "healthy"}
    assert not output.with_suffix(".json.tmp").exists()
    with pytest.raises(MonitoringError, match="Refusing to overwrite"):
        write_json_safely(output, {}, overwrite=False)
