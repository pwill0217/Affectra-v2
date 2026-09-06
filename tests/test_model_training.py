"""Tests for leakage-aware grouped synthetic-label model training."""

import json
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from src.data_generator import GenerationConfig, generate_dataset, write_dataset
from src.data_loader import load_raw_tables
from src.model_training import (
    FORBIDDEN_MODEL_FEATURES,
    ML_FEATURE_COLUMNS,
    TARGET_COLUMN,
    ModelTrainingError,
    TrainingConfig,
    build_baseline_models,
    fit_and_predict,
    grouped_agent_split,
    main,
    prepare_training_data,
    run_training,
    transparent_score_comparison,
    validate_model_features,
)
from src.preprocessing import PreprocessingConfig, preprocess_tables, run_preprocessing


@pytest.fixture(scope="module")
def processed_fixture(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("ml-data")
    raw_dir = root / "raw"
    processed_dir = root / "processed"
    config = GenerationConfig(
        num_agents=24,
        start_date=date(2026, 6, 1),
        num_days=30,
        seed=77,
        output_dir=raw_dir,
        at_risk_fraction=0.5,
    )
    write_dataset(generate_dataset(config), config)
    run_preprocessing(PreprocessingConfig(raw_dir, processed_dir))
    return processed_dir


@pytest.fixture(scope="module")
def prepared(processed_fixture: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    tables, _ = preprocess_tables(
        load_raw_tables(processed_fixture),
        input_dir=processed_fixture,
        output_dir=processed_fixture.parent / "prepared-quality",
    )
    return prepare_training_data(tables, rolling_window=5)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rolling_window": 0},
        {"rolling_window": True},
        {"test_size": 0},
        {"test_size": 1},
        {"test_size": True},
        {"random_state": True},
        {"random_forest_estimators": 0},
        {"random_forest_estimators": True},
    ],
)
def test_training_config_rejects_invalid_settings(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        TrainingConfig(**kwargs)


def test_prepared_data_joins_only_target_and_uses_explicit_allow_list(
    prepared: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    features, dataset = prepared

    assert len(features) == len(dataset) == 720
    assert dataset[TARGET_COLUMN].isin([0, 1]).all()
    assert dataset[TARGET_COLUMN].sum() > 0
    assert set(ML_FEATURE_COLUMNS).isdisjoint(FORBIDDEN_MODEL_FEATURES)
    assert "latent_pressure_score" not in dataset.columns
    assert "pressure_band" not in dataset.columns
    assert "simulated_pressure_event" not in dataset.columns


def test_feature_validation_rejects_missing_and_nonfinite_values(
    prepared: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    features, _ = prepared
    with pytest.raises(ModelTrainingError, match="missing columns"):
        validate_model_features(features.drop(columns=ML_FEATURE_COLUMNS[0]))
    broken = features.copy()
    broken.loc[0, ML_FEATURE_COLUMNS[0]] = np.inf
    with pytest.raises(ModelTrainingError, match="finite"):
        validate_model_features(broken)


def test_target_validation_rejects_duplicates_missing_and_one_class(
    processed_fixture: Path,
) -> None:
    tables, _ = preprocess_tables(
        load_raw_tables(processed_fixture),
        input_dir=processed_fixture,
        output_dir=processed_fixture.parent / "target-quality",
    )
    duplicated = {name: table.copy() for name, table in tables.items()}
    duplicated["daily_labels"] = pd.concat(
        [duplicated["daily_labels"], duplicated["daily_labels"].iloc[[0]]],
        ignore_index=True,
    )
    with pytest.raises(ModelTrainingError, match="unique"):
        prepare_training_data(duplicated, rolling_window=5)

    missing = {name: table.copy() for name, table in tables.items()}
    missing["daily_labels"] = missing["daily_labels"].iloc[1:].copy()
    with pytest.raises(ModelTrainingError, match="complete agent-day grid"):
        prepare_training_data(missing, rolling_window=5)

    one_class = {name: table.copy() for name, table in tables.items()}
    one_class["daily_labels"][TARGET_COLUMN] = 0
    with pytest.raises(ModelTrainingError, match="both classes"):
        prepare_training_data(one_class, rolling_window=5)


def test_grouped_split_has_no_agent_overlap_and_both_classes(
    prepared: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    _, dataset = prepared
    train_index, test_index = grouped_agent_split(dataset, test_size=0.25, random_state=42)

    train = dataset.iloc[train_index]
    test = dataset.iloc[test_index]
    assert set(train["agent_id"]).isdisjoint(test["agent_id"])
    assert set(train[TARGET_COLUMN]) == {0, 1}
    assert set(test[TARGET_COLUMN]) == {0, 1}
    assert len(train) + len(test) == len(dataset)


def test_grouped_split_rejects_too_few_or_unsplittable_groups() -> None:
    too_small = pd.DataFrame(
        {
            "agent_id": [1, 2, 3],
            TARGET_COLUMN: [0, 1, 0],
            **{column: [1.0, 2.0, 3.0] for column in ML_FEATURE_COLUMNS},
        }
    )
    with pytest.raises(ModelTrainingError, match="at least four"):
        grouped_agent_split(too_small, test_size=0.25, random_state=1)

    impossible = pd.concat(
        [too_small, too_small.assign(agent_id=4, **{TARGET_COLUMN: 0})],
        ignore_index=True,
    )
    with pytest.raises(ModelTrainingError, match="generate more agents"):
        grouped_agent_split(impossible, test_size=0.25, random_state=1)


def test_models_fit_predict_and_compare_current_transparent_score(
    prepared: tuple[pd.DataFrame, pd.DataFrame],
) -> None:
    features, dataset = prepared
    config = TrainingConfig(random_forest_estimators=8)
    train_index, test_index = grouped_agent_split(dataset, test_size=0.25, random_state=42)
    models = build_baseline_models(config)
    predictions = fit_and_predict(dataset, train_index, test_index, models)

    assert set(predictions["model"]) == set(models)
    assert len(predictions) == len(test_index) * 3
    assert predictions["probability"].between(0, 1).all()
    comparison = transparent_score_comparison(
        features,
        dataset,
        test_index,
        predictions,
        "logistic_regression",
    )
    assert comparison["scope"] == "latest held-out agent snapshot only"
    assert comparison["rows"] == dataset.iloc[test_index]["agent_id"].nunique()
    assert 0 <= comparison["review_flag_agreement"] <= 1
    assert "not evidence" in comparison["warning"]


def test_run_training_writes_reproducible_models_and_evidence(
    processed_fixture: Path,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "models"
    config = TrainingConfig(
        processed_fixture,
        output_dir,
        rolling_window=5,
        test_size=0.25,
        random_state=42,
        random_forest_estimators=10,
    )

    manifest, evaluation = run_training(config)

    assert {path.name for path in output_dir.iterdir()} == {
        "calibration.csv",
        "dummy_prior.joblib",
        "evaluation.json",
        "logistic_regression.joblib",
        "random_forest.joblib",
        "team_error_analysis.csv",
        "test_predictions.csv",
        "training_manifest.json",
    }
    assert manifest["split"]["overlapping_agents"] == 0
    assert manifest["target_is_research_only"] is True
    assert set(manifest["feature_allow_list"]).isdisjoint(
        manifest["forbidden_feature_columns"]
    )
    assert len(manifest["dataset_fingerprint_sha256"]) == 64
    assert set(evaluation["model_metrics"]) == {
        "dummy_prior",
        "logistic_regression",
        "random_forest",
    }
    assert "not validate real-world" in evaluation["interpretation"]
    loaded = joblib.load(output_dir / "logistic_regression.joblib")
    assert hasattr(loaded, "predict_proba")


def test_cli_runs_end_to_end(
    processed_fixture: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_dir = tmp_path / "cli-models"

    exit_code = main(
        [
            "--input-dir",
            str(processed_fixture),
            "--output-dir",
            str(output_dir),
            "--rolling-window",
            "5",
            "--test-size",
            "0.25",
            "--random-state",
            "42",
            "--random-forest-estimators",
            "8",
        ]
    )

    assert exit_code == 0
    manifest = json.loads((output_dir / "training_manifest.json").read_text())
    assert manifest["rows"] == 720
    output = capsys.readouterr().out
    assert "Agent-disjoint split" in output
    assert "not real-world burnout validation" in output
