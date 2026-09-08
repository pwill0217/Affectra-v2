"""Tests for the operational CLI and privacy-safe structured logging."""

import json
import logging
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.dashboard import DashboardConfig
from src.database import PipelineRun, create_local_engine
from src.monitoring import MonitoringThresholds
from src.operations import (
    OperationsConfig,
    configure_logging,
    log_event,
    main,
    run_operations,
)
from tests.test_monitoring import dashboard_data


def test_structured_log_keeps_only_allowlisted_metadata(capsys: pytest.CaptureFixture) -> None:
    logger = configure_logging("info")
    log_event(
        logger,
        "pipeline_complete",
        component="monitoring",
        rows=3,
        status="healthy",
        run_version="demo",
        transcript="must not appear",
        name="must not appear",
        secret="must not appear",
    )
    payload = json.loads(capsys.readouterr().err)
    assert payload["event"] == "pipeline_complete"
    assert payload["level"] == "INFO"
    assert payload["rows"] == 3
    assert "transcript" not in payload
    assert "must not appear" not in json.dumps(payload)


def test_logger_rejects_unknown_level_and_formats_exception() -> None:
    with pytest.raises(ValueError, match="AFFECTRA_LOG_LEVEL"):
        configure_logging("verbose")
    logger = configure_logging("error")
    handler = logger.handlers[0]
    record = logging.LogRecord("test", logging.ERROR, "", 1, "sensitive", (), None)
    try:
        raise RuntimeError("private message")
    except RuntimeError:
        import sys

        record.exc_info = sys.exc_info()
    payload = json.loads(handler.formatter.format(record))  # type: ignore[union-attr]
    assert payload["error_type"] == "RuntimeError"
    assert "private message" not in json.dumps(payload)


def test_run_operations_persists_and_writes_health_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = dashboard_data()
    monkeypatch.setattr("src.operations.load_operational_inputs", lambda config: data)
    database_path = tmp_path / "affectra.sqlite3"
    config = OperationsConfig(
        run_version="sprint-7-test",
        dashboard=DashboardConfig(),
        database_url=f"sqlite:///{database_path}",
        output_dir=tmp_path / "operations",
        baseline_path=tmp_path / "operations" / "baseline.json",
        initialize_baseline=True,
        thresholds=MonitoringThresholds(),
    )

    report = run_operations(config, configure_logging("critical"))

    assert report["status"] == "healthy"
    assert report["persistence"] == {
        "run_id": 1,
        "run_version": "sprint-7-test",
        "score_rows": 3,
        "privacy_minimized": True,
    }
    assert (config.output_dir / "health_report.json").is_file()
    assert config.baseline_path.is_file()
    with Session(create_local_engine(config.database_url)) as session:
        assert session.scalar(select(PipelineRun.run_version)) == "sprint-7-test"


def test_main_builds_environment_aware_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    captured = {}

    def fake_run(config: OperationsConfig, logger: logging.Logger) -> dict:
        captured["config"] = config
        return {
            "status": "healthy",
            "baseline_status": "created",
            "comparison": {"alerts": []},
        }

    monkeypatch.setattr("src.operations.run_operations", fake_run)
    monkeypatch.setenv("AFFECTRA_DATABASE_URL", f"sqlite:///{tmp_path / 'custom.db'}")
    monkeypatch.setenv("AFFECTRA_LOG_LEVEL", "WARNING")
    result = main(
        [
            "--run-version",
            "cli-001",
            "--scored-dir",
            "custom/scored",
            "--processed-dir",
            "custom/processed",
            "--models-dir",
            "custom/models",
            "--output-dir",
            "custom/operations",
            "--baseline-path",
            "custom/baseline.json",
            "--initialize-baseline",
            "--mean-score-delta",
            "5",
            "--risk-share-delta",
            "0.1",
        ]
    )

    config = captured["config"]
    assert result == 0
    assert config.run_version == "cli-001"
    assert config.dashboard.scored_dir == Path("custom/scored")
    assert config.initialize_baseline is True
    assert config.thresholds == MonitoringThresholds(5.0, 0.1)
    assert config.database_url.endswith("custom.db")
    assert "Health status: healthy" in capsys.readouterr().out


def test_main_logs_only_failure_type_before_reraising(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    def fail(config: OperationsConfig, logger: logging.Logger) -> dict:
        raise RuntimeError("private filename and secret must not be logged")

    monkeypatch.setattr("src.operations.run_operations", fail)
    with pytest.raises(RuntimeError, match="private filename"):
        main(["--run-version", "failed-run"])
    payload = json.loads(capsys.readouterr().err)
    assert payload["event"] == "operations_failed"
    assert payload["error_type"] == "RuntimeError"
    assert payload["status"] == "failed"
    assert "private filename" not in json.dumps(payload)
