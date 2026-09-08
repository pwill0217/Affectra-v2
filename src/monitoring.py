"""Schema, pipeline, and score-distribution health checks for Affectra."""

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.analytics import REQUIRED_FEATURE_COLUMNS, REQUIRED_SCORE_COLUMNS, RISK_LEVELS
from src.dashboard import DashboardConfig, DashboardData, load_dashboard_data


class MonitoringError(ValueError):
    """Raised when a monitoring baseline or output is unsafe or invalid."""


@dataclass(frozen=True)
class MonitoringThresholds:
    """Review thresholds for descriptive score-distribution changes."""

    mean_score_delta: float = 10.0
    risk_share_delta: float = 0.20

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be numeric")
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")


def _fingerprint(columns: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(columns)).encode()).hexdigest()


def schema_indicators(data: DashboardData) -> dict[str, Any]:
    """Describe required, extra, and fingerprinted score/feature schemas."""
    tables = {}
    for name, frame, required in (
        ("agent_day_features", data.features, REQUIRED_FEATURE_COLUMNS),
        ("risk_scores", data.scores, REQUIRED_SCORE_COLUMNS),
    ):
        columns = sorted(map(str, frame.columns))
        tables[name] = {
            "column_count": len(columns),
            "columns_sha256": _fingerprint(columns),
            "missing_required": sorted(required - set(columns)),
            "extra_columns": sorted(set(columns) - required),
        }
    return tables


def score_distribution(scores: pd.DataFrame) -> dict[str, Any]:
    """Create compact, identity-free score distribution indicators."""
    values = pd.to_numeric(scores["risk_score"], errors="coerce")
    if values.empty or values.isna().any() or not np.isfinite(values.to_numpy()).all():
        raise MonitoringError("Risk scores must be a non-empty finite numeric series")
    shares = scores["risk_level"].value_counts(normalize=True)
    return {
        "rows": len(scores),
        "mean": round(float(values.mean()), 6),
        "standard_deviation": round(float(values.std(ddof=0)), 6),
        "minimum": round(float(values.min()), 6),
        "p25": round(float(values.quantile(0.25)), 6),
        "median": round(float(values.median()), 6),
        "p75": round(float(values.quantile(0.75)), 6),
        "maximum": round(float(values.max()), 6),
        "risk_level_shares": {
            level: round(float(shares.get(level, 0.0)), 6) for level in RISK_LEVELS
        },
    }


def _load_baseline(path: Path) -> dict[str, Any]:
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MonitoringError(f"Could not read valid monitoring baseline: {path}") from error
    if not isinstance(baseline, dict) or not {"schema", "score_distribution"}.issubset(baseline):
        raise MonitoringError("Monitoring baseline is missing schema or score_distribution")
    return baseline


def compare_with_baseline(
    current: dict[str, Any],
    baseline: dict[str, Any],
    thresholds: MonitoringThresholds,
) -> dict[str, Any]:
    """Compare contracts and aggregate scores without making health claims."""
    schema_changes = []
    for table, details in current["schema"].items():
        previous = baseline["schema"].get(table, {})
        if details["columns_sha256"] != previous.get("columns_sha256"):
            schema_changes.append(table)
    current_distribution = current["score_distribution"]
    previous_distribution = baseline["score_distribution"]
    mean_delta = abs(current_distribution["mean"] - previous_distribution["mean"])
    share_deltas = {
        level: round(
            abs(
                current_distribution["risk_level_shares"][level]
                - previous_distribution["risk_level_shares"].get(level, 0.0)
            ),
            6,
        )
        for level in RISK_LEVELS
    }
    alerts = []
    if schema_changes:
        alerts.append("schema_changed")
    if mean_delta > thresholds.mean_score_delta:
        alerts.append("mean_score_shift")
    if max(share_deltas.values(), default=0.0) > thresholds.risk_share_delta:
        alerts.append("risk_level_share_shift")
    return {
        "schema_changes": schema_changes,
        "mean_score_delta": round(float(mean_delta), 6),
        "risk_level_share_deltas": share_deltas,
        "thresholds": {
            "mean_score_delta": thresholds.mean_score_delta,
            "risk_share_delta": thresholds.risk_share_delta,
        },
        "alerts": alerts,
    }


def build_health_report(
    data: DashboardData,
    *,
    baseline_path: Path,
    initialize_baseline: bool = False,
    thresholds: MonitoringThresholds | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Build health evidence and optionally create an explicit first baseline."""
    thresholds = thresholds or MonitoringThresholds()
    schema = schema_indicators(data)
    distribution = score_distribution(data.scores)
    checks = {
        "data_quality_not_failed": data.quality.get("status") != "failed",
        "score_rows_match_agents": len(data.scores) == data.scores["agent_id"].nunique(),
        "scores_within_zero_to_one_hundred": bool(data.scores["risk_score"].between(0, 100).all()),
        "model_agent_overlap_is_zero": (
            data.training_manifest.get("split", {}).get("overlapping_agents") == 0
        ),
        "required_schema_present": all(
            not details["missing_required"] for details in schema.values()
        ),
    }
    current = {"schema": schema, "score_distribution": distribution}
    new_baseline = None
    if baseline_path.is_file():
        comparison = compare_with_baseline(current, _load_baseline(baseline_path), thresholds)
        baseline_status = "compared"
    elif initialize_baseline:
        new_baseline = current
        comparison = {
            "schema_changes": [],
            "mean_score_delta": 0.0,
            "risk_level_share_deltas": {level: 0.0 for level in RISK_LEVELS},
            "thresholds": {
                "mean_score_delta": thresholds.mean_score_delta,
                "risk_share_delta": thresholds.risk_share_delta,
            },
            "alerts": [],
        }
        baseline_status = "created"
    else:
        raise MonitoringError(
            "Monitoring baseline is missing; rerun once with --initialize-baseline"
        )
    status = "healthy" if all(checks.values()) and not comparison["alerts"] else "review"
    report = {
        "report_version": 1,
        "status": status,
        "checks": checks,
        "schema": schema,
        "score_distribution": distribution,
        "baseline_status": baseline_status,
        "comparison": comparison,
        "interpretation": (
            "Operational indicators detect pipeline or distribution changes for review. "
            "They do not measure employee health or validate burnout prediction."
        ),
    }
    return report, new_baseline


def write_json_safely(path: Path, value: dict[str, Any], *, overwrite: bool = True) -> None:
    """Write JSON through a temporary neighbor and atomic replace."""
    if path.exists() and not overwrite:
        raise MonitoringError(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_operational_inputs(config: DashboardConfig) -> DashboardData:
    """Reuse the dashboard's complete generated-output contract."""
    return load_dashboard_data(config)
