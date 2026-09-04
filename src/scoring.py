"""Calculate Affectra's transparent, configurable decision-support score."""

import argparse
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data_loader import load_raw_tables
from src.features import build_agent_day_features, feature_summary
from src.preprocessing import preprocess_tables

COMPONENT_COLUMNS = [
    "workload_score",
    "efficiency_friction_score",
    "tone_score",
    "recovery_context_score",
]

SCORING_RANGES = {
    "calls_vs_baseline": {"low": 0.75, "high": 1.15, "direction": "higher"},
    "acw_vs_baseline": {"low": 1.0, "high": 1.35, "direction": "higher"},
    "duration_vs_baseline": {"low": 1.0, "high": 1.35, "direction": "higher"},
    "rolling_avg_hold_seconds": {"low": 40.0, "high": 120.0, "direction": "higher"},
    "rolling_avg_transfer_count": {"low": 0.15, "high": 0.80, "direction": "higher"},
    "rolling_negative_call_rate": {"low": 0.0, "high": 0.15, "direction": "higher"},
    "negative_sentiment_magnitude": {"low": 0.0, "high": 0.60, "direction": "higher"},
    "rolling_avg_negative_keyword_count": {
        "low": 0.0,
        "high": 0.50,
        "direction": "higher",
    },
    "pto_balance_hours": {"low": 0.0, "high": 80.0, "direction": "lower"},
    "vacation_days_available": {"low": 0.0, "high": 10.0, "direction": "lower"},
    "pto_used_hours_30d": {"low": 0.0, "high": 16.0, "direction": "lower"},
    "days_since_pto_at_snapshot": {"low": 14.0, "high": 120.0, "direction": "higher"},
}

REQUIRED_FEATURE_COLUMNS = {
    "agent_id",
    "name",
    "team",
    "role",
    "metric_date",
    "calls_vs_baseline",
    "acw_vs_baseline",
    "duration_vs_baseline",
    "rolling_avg_hold_seconds",
    "rolling_avg_transfer_count",
    "rolling_avg_sentiment_score",
    "rolling_negative_call_rate",
    "rolling_avg_negative_keyword_count",
    "pto_balance_hours",
    "vacation_days_available",
    "pto_used_hours_30d",
    "days_since_pto_at_snapshot",
}


class ScoringError(ValueError):
    """Raised when prepared features cannot be scored safely."""


@dataclass(frozen=True)
class ScoreWeights:
    """Visible component weights; all four values must sum to one."""

    workload: float = 0.40
    efficiency_friction: float = 0.20
    tone: float = 0.25
    recovery_context: float = 0.15

    def __post_init__(self) -> None:
        values = self.as_dict()
        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} weight must be a number")
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} weight must be finite and nonnegative")
        if not math.isclose(sum(values.values()), 1.0, abs_tol=1e-9):
            raise ValueError("score weights must sum to 1.0")

    def as_dict(self) -> dict[str, float]:
        return {
            "workload": self.workload,
            "efficiency_friction": self.efficiency_friction,
            "tone": self.tone,
            "recovery_context": self.recovery_context,
        }


@dataclass(frozen=True)
class ScoringConfig:
    """Input, output, and rolling-window settings for one scoring run."""

    input_dir: Path = Path("data/processed")
    output_dir: Path = Path("data/scored")
    rolling_window: int = 7

    def __post_init__(self) -> None:
        if isinstance(self.rolling_window, bool) or not isinstance(self.rolling_window, int):
            raise ValueError("rolling_window must be an integer")
        if self.rolling_window < 1:
            raise ValueError("rolling_window must be at least 1")


def _scale_high(values: pd.Series, low: float, high: float) -> pd.Series:
    return ((values.astype(float) - low) / (high - low) * 100).clip(0, 100)


def _scale_low(values: pd.Series, low: float, high: float) -> pd.Series:
    return (100 - _scale_high(values, low, high)).clip(0, 100)


def _range(metric: str) -> tuple[float, float]:
    settings = SCORING_RANGES[metric]
    return float(settings["low"]), float(settings["high"])


def _validate_features(features: pd.DataFrame) -> None:
    missing = sorted(REQUIRED_FEATURE_COLUMNS - set(features.columns))
    if missing:
        raise ScoringError("Feature table is missing columns: " + ", ".join(missing))
    if features.empty:
        raise ScoringError("Feature table cannot be empty")
    numeric_columns = sorted(REQUIRED_FEATURE_COLUMNS - {"name", "team", "role", "metric_date"})
    numeric = features[numeric_columns].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise ScoringError("Scoring features must contain finite numeric values")


def calculate_component_scores(features: pd.DataFrame) -> pd.DataFrame:
    """Add four bounded 0-to-100 component scores to prepared features."""
    _validate_features(features)
    scored = features.copy()

    scored["workload_score"] = _scale_high(
        scored["calls_vs_baseline"], *_range("calls_vs_baseline")
    )

    efficiency_inputs = pd.concat(
        [
            _scale_high(scored["acw_vs_baseline"], *_range("acw_vs_baseline")),
            _scale_high(
                scored["duration_vs_baseline"], *_range("duration_vs_baseline")
            ),
            _scale_high(
                scored["rolling_avg_hold_seconds"], *_range("rolling_avg_hold_seconds")
            ),
            _scale_high(
                scored["rolling_avg_transfer_count"], *_range("rolling_avg_transfer_count")
            ),
        ],
        axis=1,
    )
    scored["efficiency_friction_score"] = efficiency_inputs.mean(axis=1)

    tone_inputs = pd.concat(
        [
            _scale_high(
                scored["rolling_negative_call_rate"], *_range("rolling_negative_call_rate")
            ),
            _scale_high(
                -scored["rolling_avg_sentiment_score"],
                *_range("negative_sentiment_magnitude"),
            ),
            _scale_high(
                scored["rolling_avg_negative_keyword_count"],
                *_range("rolling_avg_negative_keyword_count"),
            ),
        ],
        axis=1,
    )
    scored["tone_score"] = tone_inputs.mean(axis=1)

    recovery_inputs = pd.concat(
        [
            _scale_low(scored["pto_balance_hours"], *_range("pto_balance_hours")),
            _scale_low(
                scored["vacation_days_available"], *_range("vacation_days_available")
            ),
            _scale_low(scored["pto_used_hours_30d"], *_range("pto_used_hours_30d")),
            _scale_high(
                scored["days_since_pto_at_snapshot"],
                *_range("days_since_pto_at_snapshot"),
            ),
        ],
        axis=1,
    )
    scored["recovery_context_score"] = recovery_inputs.mean(axis=1)
    scored[COMPONENT_COLUMNS] = scored[COMPONENT_COLUMNS].clip(0, 100).round(2)
    return scored


def risk_level(score: float) -> str:
    """Translate a bounded numeric score into a readable review level."""
    if not math.isfinite(score) or not 0 <= score <= 100:
        raise ValueError("risk score must be finite and between 0 and 100")
    if score < 35:
        return "Low"
    if score < 65:
        return "Moderate"
    return "High"


def _format_component_explanations(row: pd.Series) -> dict[str, str]:
    return {
        "workload_explanation": (
            f"Rolling calls are {row['calls_vs_baseline']:.2f}× the agent's personal baseline."
        ),
        "efficiency_explanation": (
            f"Rolling ACW is {row['acw_vs_baseline']:.2f}× baseline, duration is "
            f"{row['duration_vs_baseline']:.2f}× baseline, hold time is "
            f"{row['rolling_avg_hold_seconds']:.0f}s, and transfers average "
            f"{row['rolling_avg_transfer_count']:.2f} per call."
        ),
        "tone_explanation": (
            f"Negative calls are {row['rolling_negative_call_rate']:.0%}, average sentiment is "
            f"{row['rolling_avg_sentiment_score']:.2f}, and negative keywords average "
            f"{row['rolling_avg_negative_keyword_count']:.2f} per call."
        ),
        "recovery_explanation": (
            f"The snapshot shows {row['pto_balance_hours']:.0f} PTO hours, "
            f"{row['vacation_days_available']:.0f} vacation days, "
            f"{row['pto_used_hours_30d']:.0f} PTO hours used in 30 days, and "
            f"{row['days_since_pto_at_snapshot']:.0f} days since PTO."
        ),
    }


def _overall_explanation(row: pd.Series) -> str:
    readable = {
        "workload_score": "workload",
        "efficiency_friction_score": "efficiency friction",
        "tone_score": "customer tone",
        "recovery_context_score": "recovery context",
    }
    top_column = max(COMPONENT_COLUMNS, key=lambda column: float(row[column]))
    return (
        f"{row['risk_level']} review level ({row['risk_score']:.1f}/100). "
        f"The largest component is {readable[top_column]} at {row[top_column]:.1f}/100. "
        "Use this result to review working conditions and start a supportive conversation; "
        "it is not a diagnosis or performance rating."
    )


def score_agent_features(
    features: pd.DataFrame,
    *,
    weights: ScoreWeights | None = None,
    latest_only: bool = True,
) -> pd.DataFrame:
    """Calculate weighted scores, levels, contributions, and explanations."""
    weights = weights or ScoreWeights()
    _validate_features(features)
    selected = features.sort_values(["agent_id", "metric_date"])
    if latest_only:
        selected = selected.groupby("agent_id", as_index=False).tail(1)

    scored = calculate_component_scores(selected)
    weight_map = weights.as_dict()
    scored["workload_contribution"] = scored["workload_score"] * weight_map["workload"]
    scored["efficiency_friction_contribution"] = (
        scored["efficiency_friction_score"] * weight_map["efficiency_friction"]
    )
    scored["tone_contribution"] = scored["tone_score"] * weight_map["tone"]
    scored["recovery_context_contribution"] = (
        scored["recovery_context_score"] * weight_map["recovery_context"]
    )
    contribution_columns = [
        "workload_contribution",
        "efficiency_friction_contribution",
        "tone_contribution",
        "recovery_context_contribution",
    ]
    scored[contribution_columns] = scored[contribution_columns].round(2)
    scored["risk_score"] = scored[contribution_columns].sum(axis=1).clip(0, 100).round(2)
    scored["risk_level"] = scored["risk_score"].map(risk_level)

    explanation_rows = scored.apply(_format_component_explanations, axis=1)
    for column in explanation_rows.iloc[0]:
        scored[column] = explanation_rows.map(
            lambda explanations, key=column: explanations[key]
        )
    scored["explanation"] = scored.apply(_overall_explanation, axis=1)
    return scored.sort_values(["risk_score", "agent_id"], ascending=[False, True]).reset_index(
        drop=True
    )


def write_scoring_outputs(
    features: pd.DataFrame,
    scores: pd.DataFrame,
    *,
    output_dir: Path | str,
    weights: ScoreWeights,
    source_quality_status: str,
) -> Path:
    """Write feature/score CSVs and a reproducibility and safety manifest."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    features.to_csv(output_path / "agent_day_features.csv", index=False)
    scores.to_csv(output_path / "risk_scores.csv", index=False)
    manifest: dict[str, Any] = {
        "manifest_version": 1,
        "feature_summary": feature_summary(features),
        "score_rows": len(scores),
        "weights": weights.as_dict(),
        "normalization_ranges": SCORING_RANGES,
        "risk_levels": {"Low": "0 to <35", "Moderate": "35 to <65", "High": "65 to 100"},
        "latest_snapshot_only": True,
        "source_quality_status": source_quality_status,
        "decision_support_only": True,
        "limitations": (
            "The score is an explainable review aid, not a medical diagnosis, performance "
            "rating, or validation of real-world burnout prediction."
        ),
    }
    manifest_path = output_path / "scoring_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest_path


def run_scoring(
    config: ScoringConfig,
    *,
    weights: ScoreWeights | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Load processed CSVs, rebuild quality checks, engineer features, and score."""
    weights = weights or ScoreWeights()
    raw_tables = load_raw_tables(config.input_dir)
    cleaned_tables, quality_report = preprocess_tables(
        raw_tables,
        input_dir=config.input_dir,
        output_dir=config.output_dir,
    )
    features = build_agent_day_features(cleaned_tables, rolling_window=config.rolling_window)
    scores = score_agent_features(features, weights=weights, latest_only=True)
    write_scoring_outputs(
        features,
        scores,
        output_dir=config.output_dir,
        weights=weights,
        source_quality_status=quality_report["status"],
    )
    return features, scores, quality_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/scored"))
    parser.add_argument("--rolling-window", type=int, default=7)
    parser.add_argument("--workload-weight", type=float, default=0.40)
    parser.add_argument("--efficiency-weight", type=float, default=0.20)
    parser.add_argument("--tone-weight", type=float, default=0.25)
    parser.add_argument("--recovery-weight", type=float, default=0.15)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run feature engineering and scoring from a terminal command."""
    args = build_parser().parse_args(argv)
    config = ScoringConfig(args.input_dir, args.output_dir, args.rolling_window)
    weights = ScoreWeights(
        workload=args.workload_weight,
        efficiency_friction=args.efficiency_weight,
        tone=args.tone_weight,
        recovery_context=args.recovery_weight,
    )
    features, scores, quality_report = run_scoring(config, weights=weights)
    distribution = scores["risk_level"].value_counts().sort_index().to_dict()
    print("Affectra observable features and explainable scores created.")
    print(f"Agent-day feature rows: {len(features):,}")
    print(f"Latest agent scores: {len(scores):,}")
    print(f"Source quality status: {quality_report['status']}")
    print(f"Risk levels: {distribution}")
    print(f"Outputs: {config.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
