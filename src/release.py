"""Build and verify a complete synthetic Affectra release demonstration."""

import argparse
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from streamlit.testing.v1 import AppTest

from src.analytics import AnalyticsConfig, run_analytics
from src.dashboard import DashboardConfig, load_dashboard_data
from src.data_generator import GenerationConfig, generate_and_write
from src.model_training import TrainingConfig, run_training
from src.monitoring import write_json_safely
from src.operations import OperationsConfig, configure_logging, run_operations
from src.preprocessing import PreprocessingConfig, run_preprocessing
from src.scoring import ScoringConfig, run_scoring

RELEASE_VERSION = "1.0.0"
EXPECTED_ARTIFACTS = {
    "synthetic/agents.csv",
    "synthetic/calls.csv",
    "synthetic/daily_labels.csv",
    "synthetic/generation_manifest.json",
    "synthetic/timeoff.csv",
    "synthetic/transcripts.csv",
    "processed/agents.csv",
    "processed/calls.csv",
    "processed/daily_labels.csv",
    "processed/data_quality_report.json",
    "processed/timeoff.csv",
    "processed/transcripts.csv",
    "scored/agent_day_features.csv",
    "scored/risk_scores.csv",
    "scored/scoring_manifest.json",
    "analytics/analytics_manifest.json",
    "analytics/correlation_matrix.csv",
    "analytics/daily_trends.csv",
    "analytics/risk_distribution.csv",
    "analytics/team_summary.csv",
    "analytics/charts/baseline_trends.html",
    "analytics/charts/feature_correlations.html",
    "analytics/charts/risk_distribution.html",
    "analytics/charts/team_risk_box.html",
    "models/calibration.csv",
    "models/dummy_prior.joblib",
    "models/evaluation.json",
    "models/logistic_regression.joblib",
    "models/random_forest.joblib",
    "models/team_error_analysis.csv",
    "models/test_predictions.csv",
    "models/training_manifest.json",
    "operations/health_baseline.json",
    "operations/health_report.json",
    "affectra.db",
}


class ReleaseError(ValueError):
    """Raised when a release demo destination or artifact set is unsafe."""


@dataclass(frozen=True)
class ReleaseConfig:
    """Reproducible configuration for one complete synthetic demonstration."""

    output_root: Path = Path("data/release-demo")
    run_version: str = "release-demo-606"
    num_agents: int = 30
    start_date: date = date(2026, 8, 1)
    num_days: int = 30
    seed: int = 606
    at_risk_fraction: float = 0.5
    rolling_window: int = 7
    test_size: float = 0.25
    random_state: int = 42
    random_forest_estimators: int = 100

    def __post_init__(self) -> None:
        if not self.run_version.strip() or not self.run_version.isprintable():
            raise ValueError("run_version must be non-empty printable text")


@dataclass(frozen=True)
class ReleasePaths:
    """All generated directories for a self-contained release demonstration."""

    root: Path
    synthetic: Path
    processed: Path
    scored: Path
    analytics: Path
    models: Path
    operations: Path
    baseline: Path
    database: Path
    manifest: Path

    @classmethod
    def from_root(cls, root: Path) -> "ReleasePaths":
        return cls(
            root=root,
            synthetic=root / "synthetic",
            processed=root / "processed",
            scored=root / "scored",
            analytics=root / "analytics",
            models=root / "models",
            operations=root / "operations",
            baseline=root / "operations" / "health_baseline.json",
            database=root / "affectra.db",
            manifest=root / "release_manifest.json",
        )


def require_empty_destination(path: Path) -> None:
    """Refuse to mix a release demo with an existing file or directory."""
    if path.exists() and not path.is_dir():
        raise ReleaseError(f"Release destination is not a directory: {path}")
    if path.is_dir() and any(path.iterdir()):
        raise ReleaseError(
            f"Release destination is not empty: {path}. Choose a new path; nothing was deleted."
        )


def validate_release_artifacts(paths: ReleasePaths) -> list[str]:
    """Require every versioned output contract and reject a non-synthetic manifest."""
    missing = sorted(
        relative for relative in EXPECTED_ARTIFACTS if not (paths.root / relative).is_file()
    )
    if missing:
        raise ReleaseError("Release demo is missing artifacts: " + ", ".join(missing))
    try:
        generation = json.loads(
            (paths.synthetic / "generation_manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseError("Release generation manifest is not valid JSON") from error
    if generation.get("synthetic_only") is not True:
        raise ReleaseError("Release demo must be explicitly marked synthetic-only")
    return sorted(EXPECTED_ARTIFACTS)


def _database_url(path: Path) -> str:
    return f"sqlite:///{path.resolve()}"


def verify_dashboard_pages(paths: ReleasePaths, app_path: Path = Path("src/app.py")) -> list[str]:
    """Render every dashboard page against this release's generated outputs."""
    resolved_app_path = app_path.resolve()
    if not resolved_app_path.is_file():
        raise ReleaseError(f"Dashboard entrypoint is missing: {app_path}")
    variables = {
        "AFFECTRA_SCORED_DIR": str(paths.scored.resolve()),
        "AFFECTRA_PROCESSED_DIR": str(paths.processed.resolve()),
        "AFFECTRA_MODELS_DIR": str(paths.models.resolve()),
    }
    previous = {name: os.environ.get(name) for name in variables}
    pages = ["Overview", "Agent detail", "Data quality", "Model evaluation"]
    try:
        os.environ.update(variables)
        for page in pages:
            app = AppTest.from_file(resolved_app_path, default_timeout=30).run()
            if page != "Overview":
                app.sidebar.radio[0].set_value(page).run()
            if app.exception:
                raise ReleaseError(f"Dashboard page failed to render: {page}")
            if not app.warning:
                raise ReleaseError(f"Dashboard page is missing responsible-use warning: {page}")
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    return pages


def run_release_demo(config: ReleaseConfig) -> dict[str, Any]:
    """Run all stages once and write a compact final verification manifest."""
    paths = ReleasePaths.from_root(config.output_root)
    require_empty_destination(paths.root)

    generation_config = GenerationConfig(
        num_agents=config.num_agents,
        start_date=config.start_date,
        num_days=config.num_days,
        seed=config.seed,
        output_dir=paths.synthetic,
        at_risk_fraction=config.at_risk_fraction,
    )
    generated = generate_and_write(generation_config)
    cleaned, quality = run_preprocessing(PreprocessingConfig(paths.synthetic, paths.processed))
    features, scores, _ = run_scoring(
        ScoringConfig(paths.processed, paths.scored, config.rolling_window)
    )
    analytics = run_analytics(AnalyticsConfig(paths.scored, paths.analytics))
    training, evaluation = run_training(
        TrainingConfig(
            input_dir=paths.processed,
            output_dir=paths.models,
            rolling_window=config.rolling_window,
            test_size=config.test_size,
            random_state=config.random_state,
            random_forest_estimators=config.random_forest_estimators,
        )
    )
    dashboard = load_dashboard_data(DashboardConfig(paths.scored, paths.processed, paths.models))
    health = run_operations(
        OperationsConfig(
            run_version=config.run_version,
            dashboard=DashboardConfig(paths.scored, paths.processed, paths.models),
            database_url=_database_url(paths.database),
            output_dir=paths.operations,
            baseline_path=paths.baseline,
            initialize_baseline=True,
        ),
        configure_logging("WARNING"),
    )
    artifacts = validate_release_artifacts(paths)
    dashboard_pages = verify_dashboard_pages(paths)
    risk_counts = {
        level: int((scores["risk_level"] == level).sum())
        for level in ("Low", "Moderate", "High")
    }
    manifest: dict[str, Any] = {
        "release_version": RELEASE_VERSION,
        "manifest_version": 1,
        "synthetic_only": True,
        "run_version": config.run_version,
        "configuration": {
            "num_agents": config.num_agents,
            "start_date": config.start_date.isoformat(),
            "num_days": config.num_days,
            "seed": config.seed,
            "at_risk_fraction": config.at_risk_fraction,
            "rolling_window": config.rolling_window,
            "test_size": config.test_size,
            "random_state": config.random_state,
            "random_forest_estimators": config.random_forest_estimators,
        },
        "rows": {
            "generated": {name: len(table) for name, table in generated.items()},
            "cleaned": {name: len(table) for name, table in cleaned.items()},
            "agent_day_features": len(features),
            "current_scores": len(scores),
            "dashboard_features": len(dashboard.features),
            "dashboard_scores": len(dashboard.scores),
        },
        "dashboard": {"pages_verified": dashboard_pages},
        "quality": {
            "status": quality["status"],
            "corrections": quality["totals"]["corrections"],
            "relationship_warnings": quality["totals"]["relationship_warnings"],
            "outliers_reported": quality["totals"]["outliers_reported"],
        },
        "scores": {"risk_level_counts": risk_counts},
        "analytics": {"generated_files": analytics["outputs"]},
        "model": {
            "best_baseline_by_balanced_accuracy": evaluation[
                "best_baseline_by_balanced_accuracy"
            ],
            "split": training["split"],
            "target_is_research_only": training["target_is_research_only"],
        },
        "operations": {
            "status": health["status"],
            "checks": health["checks"],
            "alerts": health["comparison"]["alerts"],
            "privacy_minimized": health["persistence"]["privacy_minimized"],
        },
        "artifacts": artifacts,
        "limitations": (
            "This release verifies a synthetic software workflow. It does not validate "
            "real-world burnout prediction, diagnosis, or employment decisions."
        ),
    }
    write_json_safely(paths.manifest, manifest, overwrite=False)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("data/release-demo"))
    parser.add_argument("--run-version", default="release-demo-606")
    parser.add_argument("--num-agents", type=int, default=30)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2026, 8, 1))
    parser.add_argument("--num-days", type=int, default=30)
    parser.add_argument("--seed", type=int, default=606)
    parser.add_argument("--at-risk-fraction", type=float, default=0.5)
    parser.add_argument("--rolling-window", type=int, default=7)
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--random-forest-estimators", type=int, default=100)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = run_release_demo(
        ReleaseConfig(
            output_root=args.output_root,
            run_version=args.run_version,
            num_agents=args.num_agents,
            start_date=args.start_date,
            num_days=args.num_days,
            seed=args.seed,
            at_risk_fraction=args.at_risk_fraction,
            rolling_window=args.rolling_window,
            test_size=args.test_size,
            random_state=args.random_state,
            random_forest_estimators=args.random_forest_estimators,
        )
    )
    print("Affectra release demonstration complete.")
    print(f"Release: {manifest['release_version']}")
    print(f"Synthetic agents: {manifest['configuration']['num_agents']}")
    print(f"Current scores: {manifest['rows']['current_scores']}")
    print(f"Operational health: {manifest['operations']['status']}")
    print(f"Artifacts verified: {len(manifest['artifacts']) + 1}")
    print(f"Manifest: {args.output_root / 'release_manifest.json'}")
    print("Synthetic workflow evidence is not real-world burnout validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
