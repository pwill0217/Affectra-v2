"""Persist minimized run evidence and produce privacy-safe health indicators."""

import argparse
import json
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.dashboard import DashboardConfig
from src.database import create_local_engine, persist_run
from src.monitoring import (
    MonitoringThresholds,
    build_health_report,
    load_operational_inputs,
    write_json_safely,
)

SAFE_LOG_FIELDS = {"component", "rows", "run_version", "status"}


class PrivacyJsonFormatter(logging.Formatter):
    """Emit allow-listed operational metadata, never arbitrary messages or records."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "event", "application_event"),
        }
        safe_fields = getattr(record, "safe_fields", {})
        payload.update({key: safe_fields[key] for key in SAFE_LOG_FIELDS if key in safe_fields})
        if record.exc_info:
            payload["error_type"] = record.exc_info[0].__name__
        return json.dumps(payload, sort_keys=True)


def configure_logging(level: str) -> logging.Logger:
    """Configure one stderr logger from a validated environment/CLI level."""
    normalized = level.upper()
    if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("AFFECTRA_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
    logger = logging.getLogger("affectra.operations")
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(PrivacyJsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(normalized)
    logger.propagate = False
    return logger


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Log only explicitly allow-listed operational fields."""
    safe = {key: value for key, value in fields.items() if key in SAFE_LOG_FIELDS}
    logger.info("operational event", extra={"event": event, "safe_fields": safe})


@dataclass(frozen=True)
class OperationsConfig:
    """Paths, version, and thresholds for one local operational snapshot."""

    run_version: str
    dashboard: DashboardConfig
    database_url: str
    output_dir: Path = Path("data/operations")
    baseline_path: Path = Path("data/operations/health_baseline.json")
    initialize_baseline: bool = False
    thresholds: MonitoringThresholds = MonitoringThresholds()


def run_operations(config: OperationsConfig, logger: logging.Logger) -> dict[str, Any]:
    """Validate inputs, save a minimized snapshot, and atomically write health evidence."""
    data = load_operational_inputs(config.dashboard)
    report, baseline = build_health_report(
        data,
        baseline_path=config.baseline_path,
        initialize_baseline=config.initialize_baseline,
        thresholds=config.thresholds,
    )
    engine = create_local_engine(config.database_url)
    run_id = persist_run(
        engine,
        run_version=config.run_version,
        scores=data.scores,
        feature_rows=len(data.features),
        quality_status=str(data.quality["status"]),
        training_manifest=data.training_manifest,
        evaluation=data.evaluation,
    )
    if baseline is not None:
        write_json_safely(config.baseline_path, baseline, overwrite=False)
    report["persistence"] = {
        "run_id": run_id,
        "run_version": config.run_version,
        "score_rows": len(data.scores),
        "privacy_minimized": True,
    }
    report_path = config.output_dir / "health_report.json"
    write_json_safely(report_path, report)
    log_event(
        logger,
        "operations_complete",
        component="operations",
        status=report["status"],
        rows=len(data.scores),
        run_version=config.run_version,
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-version", required=True)
    parser.add_argument("--scored-dir", type=Path, default=Path("data/scored"))
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--models-dir", type=Path, default=Path("models"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/operations"))
    parser.add_argument(
        "--baseline-path", type=Path, default=Path("data/operations/health_baseline.json")
    )
    parser.add_argument("--initialize-baseline", action="store_true")
    parser.add_argument("--mean-score-delta", type=float, default=10.0)
    parser.add_argument("--risk-share-delta", type=float, default=0.20)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logger = configure_logging(os.environ.get("AFFECTRA_LOG_LEVEL", "INFO"))
    config = OperationsConfig(
        run_version=args.run_version,
        dashboard=DashboardConfig(args.scored_dir, args.processed_dir, args.models_dir),
        database_url=os.environ.get("AFFECTRA_DATABASE_URL", "sqlite:///data/affectra.db"),
        output_dir=args.output_dir,
        baseline_path=args.baseline_path,
        initialize_baseline=args.initialize_baseline,
        thresholds=MonitoringThresholds(args.mean_score_delta, args.risk_share_delta),
    )
    try:
        report = run_operations(config, logger)
    except Exception:
        logger.error(
            "operational failure",
            exc_info=True,
            extra={
                "event": "operations_failed",
                "safe_fields": {
                    "component": "operations",
                    "run_version": config.run_version,
                    "status": "failed",
                },
            },
        )
        raise
    print("Affectra operational snapshot complete.")
    print(f"Run version: {config.run_version}")
    print(f"Health status: {report['status']}")
    print(f"Baseline status: {report['baseline_status']}")
    print(f"Alerts: {report['comparison']['alerts']}")
    print(f"Output: {config.output_dir / 'health_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
