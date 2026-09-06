"""Evaluation helpers for Affectra's synthetic-label ML experiment."""

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)


class EvaluationError(ValueError):
    """Raised when predictions cannot be evaluated reliably."""


def classification_metrics(
    actual: pd.Series | np.ndarray,
    predicted: pd.Series | np.ndarray,
    probability: pd.Series | np.ndarray,
) -> dict[str, Any]:
    """Return discrimination, calibration, and confusion evidence."""
    y_true = np.asarray(actual, dtype=int)
    y_pred = np.asarray(predicted, dtype=int)
    y_prob = np.asarray(probability, dtype=float)
    if not (len(y_true) == len(y_pred) == len(y_prob)) or len(y_true) == 0:
        raise EvaluationError("actual, predicted, and probability must have equal nonzero length")
    if not np.isin(y_true, [0, 1]).all() or not np.isin(y_pred, [0, 1]).all():
        raise EvaluationError("actual and predicted values must be binary")
    if not np.isfinite(y_prob).all() or ((y_prob < 0) | (y_prob > 1)).any():
        raise EvaluationError("probabilities must be finite and between 0 and 1")
    if np.unique(y_true).size != 2:
        raise EvaluationError("evaluation requires both target classes")

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {
        "rows": int(len(y_true)),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, y_pred)), 6),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 6),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 6),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 6),
        "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 6),
        "brier_score": round(float(brier_score_loss(y_true, y_prob)), 6),
        "log_loss": round(float(log_loss(y_true, y_prob, labels=[0, 1])), 6),
        "confusion": {
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
            "true_positive": int(tp),
        },
    }


def calibration_table(
    predictions: pd.DataFrame,
    *,
    bins: int = 5,
) -> pd.DataFrame:
    """Summarize predicted probability against observed synthetic frequency."""
    if isinstance(bins, bool) or not isinstance(bins, int) or bins < 2:
        raise ValueError("bins must be an integer of at least 2")
    required = {"model", "actual", "probability"}
    missing = sorted(required - set(predictions.columns))
    if missing:
        raise EvaluationError("predictions are missing columns: " + ", ".join(missing))

    rows: list[dict[str, Any]] = []
    edges = np.linspace(0, 1, bins + 1)
    for model, group in predictions.groupby("model", sort=True):
        bucket = np.minimum(np.digitize(group["probability"], edges[1:-1]), bins - 1)
        working = group.assign(calibration_bin=bucket)
        for bin_number, values in working.groupby("calibration_bin", sort=True):
            rows.append(
                {
                    "model": model,
                    "bin": int(bin_number) + 1,
                    "lower_bound": round(float(edges[bin_number]), 4),
                    "upper_bound": round(float(edges[bin_number + 1]), 4),
                    "rows": int(len(values)),
                    "mean_probability": round(float(values["probability"].mean()), 6),
                    "positive_rate": round(float(values["actual"].mean()), 6),
                }
            )
    return pd.DataFrame(rows)


def expected_calibration_error(calibration: pd.DataFrame) -> dict[str, float]:
    """Calculate a row-weighted probability-versus-frequency gap by model."""
    required = {"model", "rows", "mean_probability", "positive_rate"}
    missing = sorted(required - set(calibration.columns))
    if missing:
        raise EvaluationError("calibration table is missing columns: " + ", ".join(missing))
    result: dict[str, float] = {}
    for model, group in calibration.groupby("model", sort=True):
        total = group["rows"].sum()
        gaps = (group["mean_probability"] - group["positive_rate"]).abs()
        result[str(model)] = round(float((gaps * group["rows"] / total).sum()), 6)
    return result


def team_error_analysis(predictions: pd.DataFrame) -> pd.DataFrame:
    """Report model mistakes by synthetic team for inspection, not ranking."""
    required = {"model", "team", "actual", "predicted"}
    missing = sorted(required - set(predictions.columns))
    if missing:
        raise EvaluationError("predictions are missing columns: " + ", ".join(missing))

    rows: list[dict[str, Any]] = []
    for (model, team), group in predictions.groupby(["model", "team"], sort=True):
        actual = group["actual"].astype(int)
        predicted = group["predicted"].astype(int)
        positives = int(actual.sum())
        rows.append(
            {
                "model": model,
                "team": team,
                "rows": len(group),
                "positive_rows": positives,
                "false_positives": int(((actual == 0) & (predicted == 1)).sum()),
                "false_negatives": int(((actual == 1) & (predicted == 0)).sum()),
                "accuracy": round(float((actual == predicted).mean()), 6),
                "recall": (
                    round(float(((actual == 1) & (predicted == 1)).sum() / positives), 6)
                    if positives
                    else None
                ),
            }
        )
    return pd.DataFrame(rows)


def evaluate_predictions(predictions: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    """Evaluate every model and return metrics plus calibration rows."""
    required = {"model", "actual", "predicted", "probability"}
    missing = sorted(required - set(predictions.columns))
    if missing:
        raise EvaluationError("predictions are missing columns: " + ", ".join(missing))
    metrics: dict[str, Any] = {}
    for model, group in predictions.groupby("model", sort=True):
        metrics[str(model)] = classification_metrics(
            group["actual"], group["predicted"], group["probability"]
        )
    calibration = calibration_table(predictions)
    ece = expected_calibration_error(calibration)
    for model, value in ece.items():
        metrics[model]["expected_calibration_error"] = value
    return metrics, calibration


def choose_best_model(metrics: Mapping[str, Mapping[str, float]]) -> str:
    """Choose the strongest balanced-accuracy baseline with deterministic ties."""
    if not metrics:
        raise EvaluationError("at least one model metric set is required")
    return min(
        metrics,
        key=lambda name: (-float(metrics[name]["balanced_accuracy"]), str(name)),
    )
