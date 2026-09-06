"""Train reproducible ML baselines against Affectra's research-only synthetic label."""

import argparse
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import ClassifierMixin
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.data_loader import load_raw_tables
from src.evaluation import (
    choose_best_model,
    evaluate_predictions,
    team_error_analysis,
)
from src.features import TARGET_METADATA_COLUMNS, build_agent_day_features
from src.preprocessing import preprocess_tables
from src.scoring import score_agent_features

TARGET_COLUMN = "synthetic_stress_label"
ML_FEATURE_COLUMNS = [
    "rolling_call_count",
    "rolling_avg_duration_seconds",
    "rolling_avg_acw_seconds",
    "rolling_avg_hold_seconds",
    "rolling_avg_transfer_count",
    "rolling_avg_sentiment_score",
    "rolling_negative_call_rate",
    "rolling_avg_negative_keyword_count",
    "calls_vs_baseline",
    "acw_vs_baseline",
    "duration_vs_baseline",
]
IDENTITY_OR_CONTEXT_COLUMNS = {
    "agent_id",
    "name",
    "team",
    "role",
    "metric_date",
    "recovery_snapshot_date",
    "last_pto_date",
}
SNAPSHOT_COLUMNS = {
    "pto_balance_hours",
    "vacation_days_available",
    "pto_used_hours_30d",
    "days_since_pto_at_snapshot",
}
FORBIDDEN_MODEL_FEATURES = (
    TARGET_METADATA_COLUMNS | IDENTITY_OR_CONTEXT_COLUMNS | SNAPSHOT_COLUMNS
)


class ModelTrainingError(ValueError):
    """Raised when a leakage-safe model experiment cannot be run."""


@dataclass(frozen=True)
class TrainingConfig:
    """Locations and reproducibility controls for one model experiment."""

    input_dir: Path = Path("data/processed")
    output_dir: Path = Path("models")
    rolling_window: int = 7
    test_size: float = 0.25
    random_state: int = 42
    random_forest_estimators: int = 100

    def __post_init__(self) -> None:
        if isinstance(self.rolling_window, bool) or not isinstance(self.rolling_window, int):
            raise ValueError("rolling_window must be an integer")
        if self.rolling_window < 1:
            raise ValueError("rolling_window must be at least 1")
        if isinstance(self.test_size, bool) or not isinstance(self.test_size, (int, float)):
            raise ValueError("test_size must be a number")
        if not 0 < self.test_size < 1:
            raise ValueError("test_size must be between 0 and 1")
        if isinstance(self.random_state, bool) or not isinstance(self.random_state, int):
            raise ValueError("random_state must be an integer")
        if (
            isinstance(self.random_forest_estimators, bool)
            or not isinstance(self.random_forest_estimators, int)
            or self.random_forest_estimators < 1
        ):
            raise ValueError("random_forest_estimators must be a positive integer")


def validate_model_features(features: pd.DataFrame) -> None:
    """Enforce the explicit numeric feature allow-list and leakage deny-list."""
    missing = sorted(set(ML_FEATURE_COLUMNS) - set(features.columns))
    if missing:
        raise ModelTrainingError("feature table is missing columns: " + ", ".join(missing))
    selected_forbidden = sorted(set(ML_FEATURE_COLUMNS) & FORBIDDEN_MODEL_FEATURES)
    if selected_forbidden:
        raise ModelTrainingError(
            "model feature allow-list contains forbidden columns: "
            + ", ".join(selected_forbidden)
        )
    numeric = features[ML_FEATURE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy()).all():
        raise ModelTrainingError("model features must contain finite numeric values")


def prepare_training_data(
    cleaned_tables: dict[str, pd.DataFrame],
    *,
    rolling_window: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build observable features, then join only the research target by key."""
    labels = cleaned_tables["daily_labels"][[
        "agent_id",
        "label_date",
        TARGET_COLUMN,
    ]].rename(columns={"label_date": "metric_date"})
    if labels.duplicated(["agent_id", "metric_date"]).any():
        raise ModelTrainingError("synthetic target rows must be unique by agent and date")
    expected_rows = (
        cleaned_tables["agents"]["agent_id"].nunique() * labels["metric_date"].nunique()
    )
    if len(labels) != expected_rows:
        raise ModelTrainingError("research targets must form a complete agent-day grid")
    if not labels[TARGET_COLUMN].isin([0, 1]).all():
        raise ModelTrainingError("research target must contain only 0 and 1")
    if labels[TARGET_COLUMN].nunique() != 2:
        raise ModelTrainingError("research target must contain both classes")

    features = build_agent_day_features(cleaned_tables, rolling_window=rolling_window)
    validate_model_features(features)
    dataset = features.merge(
        labels,
        on=["agent_id", "metric_date"],
        how="left",
        validate="one_to_one",
    )
    if dataset[TARGET_COLUMN].isna().any():
        raise ModelTrainingError("every feature row must have one research target")
    return features, dataset


def grouped_agent_split(
    dataset: pd.DataFrame,
    *,
    test_size: float,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Hold out complete agents and require both classes in each partition."""
    if dataset["agent_id"].nunique() < 4:
        raise ModelTrainingError("grouped evaluation requires at least four agents")
    splitter = GroupShuffleSplit(
        n_splits=100,
        test_size=test_size,
        random_state=random_state,
    )
    x = dataset[ML_FEATURE_COLUMNS]
    y = dataset[TARGET_COLUMN]
    groups = dataset["agent_id"]
    for train_index, test_index in splitter.split(x, y, groups):
        train_classes = set(y.iloc[train_index])
        test_classes = set(y.iloc[test_index])
        if train_classes == {0, 1} and test_classes == {0, 1}:
            return train_index, test_index
    raise ModelTrainingError(
        "could not create an agent-disjoint split with both classes; generate more agents"
    )


def build_baseline_models(config: TrainingConfig) -> dict[str, ClassifierMixin]:
    """Create deterministic naive, linear, and nonlinear comparison models."""
    return {
        "dummy_prior": DummyClassifier(strategy="prior"),
        "logistic_regression": Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "classify",
                    LogisticRegression(
                        class_weight="balanced",
                        max_iter=1_000,
                        random_state=config.random_state,
                    ),
                ),
            ]
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=config.random_forest_estimators,
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            random_state=config.random_state,
            n_jobs=1,
        ),
    }


def fit_and_predict(
    dataset: pd.DataFrame,
    train_index: np.ndarray,
    test_index: np.ndarray,
    models: dict[str, ClassifierMixin],
) -> pd.DataFrame:
    """Fit each baseline and return privacy-minimized held-out predictions."""
    train = dataset.iloc[train_index]
    test = dataset.iloc[test_index]
    rows: list[pd.DataFrame] = []
    for name, model in models.items():
        model.fit(train[ML_FEATURE_COLUMNS], train[TARGET_COLUMN])
        predicted = model.predict(test[ML_FEATURE_COLUMNS]).astype(int)
        positive_index = list(model.classes_).index(1)
        probability = model.predict_proba(test[ML_FEATURE_COLUMNS])[:, positive_index]
        rows.append(
            pd.DataFrame(
                {
                    "model": name,
                    "agent_id": test["agent_id"].to_numpy(),
                    "metric_date": test["metric_date"].to_numpy(),
                    "team": test["team"].to_numpy(),
                    "actual": test[TARGET_COLUMN].astype(int).to_numpy(),
                    "predicted": predicted,
                    "probability": np.round(probability, 8),
                }
            )
        )
    return pd.concat(rows, ignore_index=True)


def transparent_score_comparison(
    features: pd.DataFrame,
    dataset: pd.DataFrame,
    test_index: np.ndarray,
    predictions: pd.DataFrame,
    model_name: str,
) -> dict[str, Any]:
    """Compare model probability with the transparent current-snapshot score."""
    test_agents = set(dataset.iloc[test_index]["agent_id"])
    held_out_features = features[features["agent_id"].isin(test_agents)]
    scored = score_agent_features(held_out_features, latest_only=True)
    latest_model = (
        predictions[
            (predictions["model"] == model_name)
            & (predictions["agent_id"].isin(test_agents))
        ]
        .sort_values(["agent_id", "metric_date"])
        .groupby("agent_id", as_index=False)
        .tail(1)[["agent_id", "probability"]]
    )
    comparison = scored[["agent_id", "risk_score", "risk_level"]].merge(
        latest_model,
        on="agent_id",
        validate="one_to_one",
    )
    score_probability = comparison["risk_score"] / 100
    model_review = comparison["probability"] >= 0.5
    score_review = comparison["risk_level"].isin(["Moderate", "High"])
    correlation = comparison[["probability", "risk_score"]].corr().iloc[0, 1]
    return {
        "model": model_name,
        "rows": len(comparison),
        "scope": "latest held-out agent snapshot only",
        "mean_model_probability": round(float(comparison["probability"].mean()), 6),
        "mean_transparent_score_0_to_1": round(float(score_probability.mean()), 6),
        "mean_absolute_gap": round(
            float((comparison["probability"] - score_probability).abs().mean()), 6
        ),
        "pearson_correlation": (
            round(float(correlation), 6) if np.isfinite(correlation) else None
        ),
        "review_flag_agreement": round(float((model_review == score_review).mean()), 6),
        "thresholds": "model probability >= 0.5; transparent score >= 35",
        "warning": (
            "Agreement is descriptive, not evidence that either method measures real burnout."
        ),
    }


def _dataset_fingerprint(dataset: pd.DataFrame) -> str:
    ordered = dataset.sort_values(["agent_id", "metric_date"])[
        ["agent_id", "metric_date", *ML_FEATURE_COLUMNS, TARGET_COLUMN]
    ]
    hashed = pd.util.hash_pandas_object(ordered, index=False).to_numpy().tobytes()
    return hashlib.sha256(hashed).hexdigest()


def _split_summary(
    dataset: pd.DataFrame,
    train_index: np.ndarray,
    test_index: np.ndarray,
) -> dict[str, Any]:
    train = dataset.iloc[train_index]
    test = dataset.iloc[test_index]
    return {
        "strategy": "GroupShuffleSplit with complete agent groups",
        "train_rows": len(train),
        "test_rows": len(test),
        "train_agents": int(train["agent_id"].nunique()),
        "test_agents": int(test["agent_id"].nunique()),
        "overlapping_agents": int(len(set(train["agent_id"]) & set(test["agent_id"]))),
        "train_target_counts": {
            str(key): int(value)
            for key, value in train[TARGET_COLUMN].value_counts().sort_index().items()
        },
        "test_target_counts": {
            str(key): int(value)
            for key, value in test[TARGET_COLUMN].value_counts().sort_index().items()
        },
    }


def write_experiment_outputs(
    *,
    config: TrainingConfig,
    models: dict[str, ClassifierMixin],
    predictions: pd.DataFrame,
    metrics: dict[str, Any],
    calibration: pd.DataFrame,
    team_errors: pd.DataFrame,
    transparent_metrics: dict[str, Any],
    dataset: pd.DataFrame,
    train_index: np.ndarray,
    test_index: np.ndarray,
    source_quality_status: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Persist generated models and machine-readable experiment evidence."""
    config.output_dir.mkdir(parents=True, exist_ok=True)
    for name, model in models.items():
        joblib.dump(model, config.output_dir / f"{name}.joblib")
    predictions.to_csv(config.output_dir / "test_predictions.csv", index=False)
    calibration.to_csv(config.output_dir / "calibration.csv", index=False)
    team_errors.to_csv(config.output_dir / "team_error_analysis.csv", index=False)

    best_model = choose_best_model(metrics)
    evaluation = {
        "model_metrics": metrics,
        "best_baseline_by_balanced_accuracy": best_model,
        "transparent_score_comparison": transparent_metrics,
        "interpretation": (
            "Metrics measure recovery of a generated research label. They do not validate "
            "real-world burnout prediction, diagnosis, or employment decisions."
        ),
    }
    (config.output_dir / "evaluation.json").write_text(
        json.dumps(evaluation, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "manifest_version": 1,
        "dataset_fingerprint_sha256": _dataset_fingerprint(dataset),
        "rows": len(dataset),
        "agents": int(dataset["agent_id"].nunique()),
        "date_range": {
            "start": pd.Timestamp(dataset["metric_date"].min()).date().isoformat(),
            "end": pd.Timestamp(dataset["metric_date"].max()).date().isoformat(),
        },
        "target": TARGET_COLUMN,
        "target_is_research_only": True,
        "feature_allow_list": ML_FEATURE_COLUMNS,
        "forbidden_feature_columns": sorted(FORBIDDEN_MODEL_FEATURES),
        "snapshot_features_excluded": sorted(SNAPSHOT_COLUMNS),
        "split": _split_summary(dataset, train_index, test_index),
        "random_state": config.random_state,
        "rolling_window_days": config.rolling_window,
        "random_forest_estimators": config.random_forest_estimators,
        "models": sorted(models),
        "source_quality_status": source_quality_status,
        "generated_outputs": [
            "calibration.csv",
            "dummy_prior.joblib",
            "evaluation.json",
            "logistic_regression.joblib",
            "random_forest.joblib",
            "team_error_analysis.csv",
            "test_predictions.csv",
            "training_manifest.json",
        ],
        "limitations": (
            "This experiment uses generated labels and synthetic operational patterns. Strong "
            "metrics may reflect the generator design and cannot establish real-world validity."
        ),
    }
    (config.output_dir / "training_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest, evaluation


def run_training(config: TrainingConfig) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run the cleaned-data-to-evaluation ML experiment."""
    raw_tables = load_raw_tables(config.input_dir)
    cleaned_tables, quality_report = preprocess_tables(
        raw_tables,
        input_dir=config.input_dir,
        output_dir=config.output_dir,
    )
    features, dataset = prepare_training_data(
        cleaned_tables,
        rolling_window=config.rolling_window,
    )
    train_index, test_index = grouped_agent_split(
        dataset,
        test_size=config.test_size,
        random_state=config.random_state,
    )
    models = build_baseline_models(config)
    predictions = fit_and_predict(dataset, train_index, test_index, models)
    metrics, calibration = evaluate_predictions(predictions)
    team_errors = team_error_analysis(predictions)
    best_model = choose_best_model(metrics)
    transparent_metrics = transparent_score_comparison(
        features,
        dataset,
        test_index,
        predictions,
        best_model,
    )
    return write_experiment_outputs(
        config=config,
        models=models,
        predictions=predictions,
        metrics=metrics,
        calibration=calibration,
        team_errors=team_errors,
        transparent_metrics=transparent_metrics,
        dataset=dataset,
        train_index=train_index,
        test_index=test_index,
        source_quality_status=quality_report["status"],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--output-dir", type=Path, default=Path("models"))
    parser.add_argument("--rolling-window", type=int, default=7)
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--random-forest-estimators", type=int, default=100)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = TrainingConfig(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        rolling_window=args.rolling_window,
        test_size=args.test_size,
        random_state=args.random_state,
        random_forest_estimators=args.random_forest_estimators,
    )
    manifest, evaluation = run_training(config)
    split = manifest["split"]
    print("Affectra synthetic-label model experiment complete.")
    print(f"Rows: {manifest['rows']:,}; agents: {manifest['agents']:,}")
    print(
        f"Agent-disjoint split: {split['train_agents']} train / "
        f"{split['test_agents']} test; overlap: {split['overlapping_agents']}"
    )
    print(f"Best baseline by balanced accuracy: {evaluation['best_baseline_by_balanced_accuracy']}")
    print("Synthetic performance is not real-world burnout validation.")
    print(f"Outputs: {config.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
