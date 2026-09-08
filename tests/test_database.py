"""Tests for privacy-minimized, immutable local persistence."""

import json
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from src.database import (
    ModelMetadata,
    PersistedScore,
    PersistenceError,
    PipelineRun,
    create_local_engine,
    initialize_database,
    persist_run,
)


def scores() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "agent_id": [1, 2],
            "name": ["Alex Demo", "Blair Demo"],
            "metric_date": ["2026-09-01", "2026-09-01"],
            "risk_score": [25.0, 55.0],
            "risk_level": ["Low", "Moderate"],
            "workload_score": [20.0, 60.0],
            "efficiency_friction_score": [30.0, 50.0],
            "tone_score": [25.0, 55.0],
            "recovery_context_score": [25.0, 45.0],
            "explanation": ["private explanation", "private explanation"],
        }
    )


def manifest() -> dict:
    return {"dataset_fingerprint_sha256": "a" * 64}


def evaluation() -> dict:
    return {
        "best_baseline_by_balanced_accuracy": "logistic_regression",
        "model_metrics": {
            "dummy_prior": {"accuracy": 0.9},
            "logistic_regression": {"accuracy": 0.8, "recall": 0.7},
        },
    }


def test_initialize_is_idempotent_and_creates_parent(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "affectra.sqlite3"
    engine = create_local_engine(f"sqlite:///{path}")
    initialize_database(engine)
    initialize_database(engine)

    assert path.is_file()
    assert set(inspect(engine).get_table_names()) == {
        "model_metadata",
        "pipeline_runs",
        "score_snapshots",
    }


def test_persist_run_stores_only_minimized_versioned_evidence() -> None:
    engine = create_local_engine("sqlite:///:memory:")
    run_id = persist_run(
        engine,
        run_version="demo-001",
        scores=scores(),
        feature_rows=60,
        quality_status="passed_with_warnings",
        training_manifest=manifest(),
        evaluation=evaluation(),
    )

    with Session(engine) as session:
        run = session.get(PipelineRun, run_id)
        snapshots = session.scalars(select(PersistedScore)).all()
        models = session.scalars(select(ModelMetadata)).all()
    assert run is not None
    assert (run.run_version, run.feature_rows, run.score_rows) == ("demo-001", 60, 2)
    assert run.created_at is not None
    assert len(snapshots) == 2
    assert not {"name", "explanation", "transcript"} & {
        column.name for column in PersistedScore.__table__.columns
    }
    assert [model.model_name for model in models] == ["dummy_prior", "logistic_regression"]
    assert json.loads(models[1].metrics_json)["recall"] == 0.7


def test_duplicate_version_is_rejected_without_overwrite() -> None:
    engine = create_local_engine("sqlite:///:memory:")
    kwargs = {
        "run_version": "same-version",
        "scores": scores(),
        "feature_rows": 60,
        "quality_status": "passed",
        "training_manifest": manifest(),
        "evaluation": evaluation(),
    }
    first_id = persist_run(engine, **kwargs)
    with pytest.raises(PersistenceError, match="already exists"):
        persist_run(engine, **kwargs)
    with Session(engine) as session:
        assert session.scalar(select(PipelineRun.id)) == first_id
        assert len(session.scalars(select(PersistedScore)).all()) == 2


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"drop": "risk_score"}, "missing columns"),
        ({"empty": True}, "cannot be empty"),
        ({"duplicate": True}, "one row per agent"),
        ({"risk_score": float("nan")}, "finite numbers"),
        ({"risk_score": 101.0}, "between 0 and 100"),
        ({"risk_level": "Urgent"}, "unknown review level"),
        ({"metric_date": "not-a-date"}, "invalid metric date"),
    ],
)
def test_score_validation_rejects_bad_snapshots(change: dict, message: str) -> None:
    frame = scores()
    if "drop" in change:
        frame = frame.drop(columns=change["drop"])
    elif change.get("empty"):
        frame = frame.iloc[0:0]
    elif change.get("duplicate"):
        frame.loc[1, "agent_id"] = 1
    else:
        column, value = next(iter(change.items()))
        frame.loc[0, column] = value
    with pytest.raises(PersistenceError, match=message):
        persist_run(
            create_local_engine("sqlite:///:memory:"),
            run_version="bad",
            scores=frame,
            feature_rows=2,
            quality_status="passed",
            training_manifest=manifest(),
            evaluation=evaluation(),
        )


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"run_version": " "}, "run_version"),
        ({"run_version": "bad\nversion"}, "run_version"),
        ({"feature_rows": 0}, "feature_rows"),
        ({"training_manifest": {}}, "fingerprint"),
        ({"training_manifest": {"dataset_fingerprint_sha256": "Z" * 64}}, "fingerprint"),
        ({"evaluation": {"model_metrics": {}}}, "model metrics"),
    ],
)
def test_run_metadata_validation(updates: dict, message: str) -> None:
    kwargs = {
        "run_version": "demo",
        "scores": scores(),
        "feature_rows": 2,
        "quality_status": "passed",
        "training_manifest": manifest(),
        "evaluation": evaluation(),
    }
    kwargs.update(updates)
    with pytest.raises(PersistenceError, match=message):
        persist_run(create_local_engine("sqlite:///:memory:"), **kwargs)


def test_engine_rejects_invalid_remote_or_credentialed_urls() -> None:
    with pytest.raises(PersistenceError, match="valid database URL"):
        create_local_engine("not a url %")
    with pytest.raises(PersistenceError, match="local SQLite"):
        create_local_engine("postgresql://example/db")
    with pytest.raises(PersistenceError, match="credentials or a host"):
        create_local_engine("sqlite://user:password@example/test.db")
