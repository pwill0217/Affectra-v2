"""Tests for classification, calibration, and error-analysis evidence."""

import numpy as np
import pandas as pd
import pytest

from src.evaluation import (
    EvaluationError,
    calibration_table,
    choose_best_model,
    classification_metrics,
    evaluate_predictions,
    expected_calibration_error,
    team_error_analysis,
)


def prediction_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "model": ["a"] * 4 + ["b"] * 4,
            "team": ["Billing", "Billing", "Support", "Support"] * 2,
            "actual": [0, 0, 1, 1] * 2,
            "predicted": [0, 1, 0, 1, 0, 0, 1, 1],
            "probability": [0.1, 0.8, 0.4, 0.9, 0.2, 0.3, 0.7, 0.8],
        }
    )


def test_classification_metrics_include_confusion_and_calibration() -> None:
    metrics = classification_metrics(
        np.array([0, 0, 1, 1]),
        np.array([0, 1, 0, 1]),
        np.array([0.1, 0.8, 0.4, 0.9]),
    )

    assert metrics["accuracy"] == 0.5
    assert metrics["balanced_accuracy"] == 0.5
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == 0.5
    assert metrics["confusion"] == {
        "true_negative": 1,
        "false_positive": 1,
        "false_negative": 1,
        "true_positive": 1,
    }
    assert 0 <= metrics["brier_score"] <= 1
    assert 0 <= metrics["roc_auc"] <= 1


@pytest.mark.parametrize(
    ("actual", "predicted", "probability", "message"),
    [
        ([0, 1], [0], [0.2, 0.8], "equal nonzero"),
        ([0, 2], [0, 1], [0.2, 0.8], "binary"),
        ([0, 1], [0, 3], [0.2, 0.8], "binary"),
        ([0, 1], [0, 1], [0.2, 1.8], "between 0 and 1"),
        ([0, 1], [0, 1], [0.2, np.nan], "finite"),
        ([1, 1], [1, 1], [0.8, 0.9], "both target classes"),
    ],
)
def test_classification_metrics_reject_invalid_inputs(
    actual: list[float],
    predicted: list[float],
    probability: list[float],
    message: str,
) -> None:
    with pytest.raises(EvaluationError, match=message):
        classification_metrics(actual, predicted, probability)


def test_calibration_and_expected_error_are_weighted_by_rows() -> None:
    calibration = calibration_table(prediction_rows(), bins=5)
    errors = expected_calibration_error(calibration)

    assert set(calibration["model"]) == {"a", "b"}
    assert calibration.groupby("model")["rows"].sum().to_dict() == {"a": 4, "b": 4}
    assert all(0 <= value <= 1 for value in errors.values())


def test_calibration_validation_is_clear() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        calibration_table(prediction_rows(), bins=1)
    with pytest.raises(EvaluationError, match="missing columns"):
        calibration_table(pd.DataFrame({"model": ["a"]}))
    with pytest.raises(EvaluationError, match="missing columns"):
        expected_calibration_error(pd.DataFrame({"model": ["a"]}))


def test_team_error_analysis_reports_false_positives_and_negatives() -> None:
    errors = team_error_analysis(prediction_rows())

    first_model = errors[errors["model"] == "a"].set_index("team")
    assert first_model.loc["Billing", "false_positives"] == 1
    assert first_model.loc["Support", "false_negatives"] == 1
    assert first_model.loc["Billing", "recall"] is None or pd.isna(
        first_model.loc["Billing", "recall"]
    )
    with pytest.raises(EvaluationError, match="missing columns"):
        team_error_analysis(pd.DataFrame({"model": ["a"]}))


def test_evaluate_predictions_and_deterministic_model_choice() -> None:
    metrics, calibration = evaluate_predictions(prediction_rows())

    assert set(metrics) == {"a", "b"}
    assert "expected_calibration_error" in metrics["a"]
    assert not calibration.empty
    assert choose_best_model(metrics) == "b"
    tied = {"z": {"balanced_accuracy": 0.5}, "a": {"balanced_accuracy": 0.5}}
    assert choose_best_model(tied) == "a"
    with pytest.raises(EvaluationError, match="at least one"):
        choose_best_model({})
    with pytest.raises(EvaluationError, match="missing columns"):
        evaluate_predictions(pd.DataFrame({"model": ["a"]}))
