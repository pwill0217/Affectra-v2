"""Privacy-minimized local persistence for versioned Affectra run evidence."""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


class PersistenceError(ValueError):
    """Raised when local persistence would be unsafe or ambiguous."""


class Base(DeclarativeBase):
    """SQLAlchemy metadata shared by the local tables."""


class PipelineRun(Base):
    """One immutable, reproducibly named pipeline run."""

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_version: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quality_status: Mapped[str] = mapped_column(String(50), nullable=False)
    feature_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    score_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    dataset_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    best_model: Mapped[str] = mapped_column(String(100), nullable=False)
    scores: Mapped[list["PersistedScore"]] = relationship(cascade="all, delete-orphan")
    models: Mapped[list["ModelMetadata"]] = relationship(cascade="all, delete-orphan")


class PersistedScore(Base):
    """A minimized score snapshot with no name, text, or explanation fields."""

    __tablename__ = "score_snapshots"

    run_id: Mapped[int] = mapped_column(ForeignKey("pipeline_runs.id"), primary_key=True)
    agent_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    workload_score: Mapped[float] = mapped_column(Float, nullable=False)
    efficiency_friction_score: Mapped[float] = mapped_column(Float, nullable=False)
    tone_score: Mapped[float] = mapped_column(Float, nullable=False)
    recovery_context_score: Mapped[float] = mapped_column(Float, nullable=False)


class ModelMetadata(Base):
    """Model-level evaluation metadata, stored without predictions or identities."""

    __tablename__ = "model_metadata"

    run_id: Mapped[int] = mapped_column(ForeignKey("pipeline_runs.id"), primary_key=True)
    model_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False)


PERSISTED_SCORE_COLUMNS = {
    "agent_id",
    "metric_date",
    "risk_score",
    "risk_level",
    "workload_score",
    "efficiency_friction_score",
    "tone_score",
    "recovery_context_score",
}
NUMERIC_SCORE_COLUMNS = sorted(
    PERSISTED_SCORE_COLUMNS - {"metric_date", "risk_level"}
)


def create_local_engine(database_url: str) -> Engine:
    """Create a SQLite engine and its parent folder without exposing credentials."""
    try:
        url = make_url(database_url)
    except Exception as error:
        raise PersistenceError("AFFECTRA_DATABASE_URL is not a valid database URL") from error
    if url.get_backend_name() != "sqlite":
        raise PersistenceError("Sprint 7 supports local SQLite persistence only")
    if url.password or url.username or url.host:
        raise PersistenceError("Local SQLite URLs must not contain credentials or a host")
    if url.database and url.database != ":memory:":
        Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, future=True)


def initialize_database(engine: Engine) -> None:
    """Create missing tables safely; existing tables and rows are never dropped."""
    Base.metadata.create_all(engine, checkfirst=True)


def _validate_snapshot(scores: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(PERSISTED_SCORE_COLUMNS - set(scores.columns))
    if missing:
        raise PersistenceError("Score snapshot is missing columns: " + ", ".join(missing))
    if scores.empty:
        raise PersistenceError("Score snapshot cannot be empty")
    safe = scores[sorted(PERSISTED_SCORE_COLUMNS)].copy()
    if safe["agent_id"].duplicated().any():
        raise PersistenceError("Score snapshot must contain one row per agent")
    numeric = safe[NUMERIC_SCORE_COLUMNS].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise PersistenceError("Persisted score values must be finite numbers")
    if not numeric["risk_score"].between(0, 100).all():
        raise PersistenceError("Persisted risk scores must be between 0 and 100")
    if not safe["risk_level"].isin({"Low", "Moderate", "High"}).all():
        raise PersistenceError("Persisted score snapshot contains an unknown review level")
    dates = pd.to_datetime(safe["metric_date"], errors="coerce", format="mixed")
    if dates.isna().any():
        raise PersistenceError("Persisted score snapshot contains an invalid metric date")
    safe["metric_date"] = dates.dt.date
    safe[NUMERIC_SCORE_COLUMNS] = numeric
    return safe


def persist_run(
    engine: Engine,
    *,
    run_version: str,
    scores: pd.DataFrame,
    feature_rows: int,
    quality_status: str,
    training_manifest: dict[str, Any],
    evaluation: dict[str, Any],
) -> int:
    """Atomically save one immutable run and privacy-minimized evidence."""
    version = run_version.strip()
    if not version or len(version) > 100 or not version.isprintable():
        raise PersistenceError("run_version must contain 1 to 100 visible characters")
    if feature_rows < 1:
        raise PersistenceError("feature_rows must be positive")
    fingerprint = str(training_manifest.get("dataset_fingerprint_sha256", ""))
    if len(fingerprint) != 64 or any(
        character not in "0123456789abcdef" for character in fingerprint
    ):
        raise PersistenceError("Training manifest must contain a lowercase SHA-256 fingerprint")
    metrics = evaluation.get("model_metrics")
    best_model = evaluation.get("best_baseline_by_balanced_accuracy")
    if not isinstance(metrics, dict) or not metrics or best_model not in metrics:
        raise PersistenceError("Evaluation must contain model metrics and a valid best model")
    safe_scores = _validate_snapshot(scores)

    initialize_database(engine)
    try:
        with Session(engine) as session, session.begin():
            run = PipelineRun(
                run_version=version,
                created_at=datetime.now(UTC),
                quality_status=str(quality_status),
                feature_rows=int(feature_rows),
                score_rows=len(safe_scores),
                dataset_fingerprint=fingerprint,
                best_model=str(best_model),
            )
            session.add(run)
            session.flush()
            session.add_all(
                PersistedScore(run_id=run.id, **row)
                for row in safe_scores.to_dict(orient="records")
            )
            session.add_all(
                ModelMetadata(
                    run_id=run.id,
                    model_name=str(model_name),
                    metrics_json=json.dumps(model_metrics, sort_keys=True, separators=(",", ":")),
                )
                for model_name, model_metrics in sorted(metrics.items())
            )
            run_id = run.id
    except IntegrityError as error:
        raise PersistenceError(
            f"Run version {version!r} already exists; existing evidence was not overwritten"
        ) from error
    return run_id
