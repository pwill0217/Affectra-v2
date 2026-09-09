"""Release orchestration and end-to-end contract tests."""

import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from src.release import (
    EXPECTED_ARTIFACTS,
    RELEASE_VERSION,
    ReleaseConfig,
    ReleaseError,
    ReleasePaths,
    main,
    require_empty_destination,
    run_release_demo,
    validate_release_artifacts,
    verify_dashboard_pages,
)


def test_release_paths_are_self_contained(tmp_path: Path) -> None:
    paths = ReleasePaths.from_root(tmp_path / "demo")
    assert paths.synthetic == paths.root / "synthetic"
    assert paths.processed == paths.root / "processed"
    assert paths.scored == paths.root / "scored"
    assert paths.analytics == paths.root / "analytics"
    assert paths.models == paths.root / "models"
    assert paths.baseline == paths.root / "operations" / "health_baseline.json"
    assert paths.database == paths.root / "affectra.db"
    assert paths.manifest == paths.root / "release_manifest.json"


def test_release_destination_must_be_new_or_empty(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    require_empty_destination(missing)
    missing.mkdir()
    require_empty_destination(missing)
    (missing / "evidence.txt").write_text("keep me")
    with pytest.raises(ReleaseError, match="not empty.*nothing was deleted"):
        require_empty_destination(missing)
    assert (missing / "evidence.txt").read_text() == "keep me"
    file_path = tmp_path / "file"
    file_path.write_text("not a directory")
    with pytest.raises(ReleaseError, match="not a directory"):
        require_empty_destination(file_path)


@pytest.mark.parametrize("run_version", ["", " ", "bad\nversion"])
def test_release_version_must_be_visible(run_version: str, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="run_version"):
        ReleaseConfig(output_root=tmp_path, run_version=run_version)


def test_artifact_validation_reports_missing_and_non_synthetic(tmp_path: Path) -> None:
    paths = ReleasePaths.from_root(tmp_path)
    with pytest.raises(ReleaseError, match="missing artifacts"):
        validate_release_artifacts(paths)

    for relative in EXPECTED_ARTIFACTS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    (paths.synthetic / "generation_manifest.json").write_text("not json")
    with pytest.raises(ReleaseError, match="not valid JSON"):
        validate_release_artifacts(paths)
    (paths.synthetic / "generation_manifest.json").write_text(
        json.dumps({"synthetic_only": False})
    )
    with pytest.raises(ReleaseError, match="synthetic-only"):
        validate_release_artifacts(paths)
    (paths.synthetic / "generation_manifest.json").write_text(
        json.dumps({"synthetic_only": True})
    )
    assert validate_release_artifacts(paths) == sorted(EXPECTED_ARTIFACTS)


def test_dashboard_verification_requires_entrypoint(tmp_path: Path) -> None:
    with pytest.raises(ReleaseError, match="entrypoint is missing"):
        verify_dashboard_pages(ReleasePaths.from_root(tmp_path), tmp_path / "missing.py")


def test_complete_release_demo_runs_every_stage(tmp_path: Path) -> None:
    root = tmp_path / "release"
    manifest = run_release_demo(
        ReleaseConfig(
            output_root=root,
            run_version="automated-release-test",
            num_agents=30,
            start_date=date(2026, 8, 1),
            num_days=30,
            seed=606,
            at_risk_fraction=0.5,
            random_forest_estimators=25,
        )
    )

    saved = json.loads((root / "release_manifest.json").read_text())
    assert saved == manifest
    assert manifest["release_version"] == RELEASE_VERSION
    assert manifest["synthetic_only"] is True
    assert manifest["rows"]["agent_day_features"] == 900
    assert manifest["rows"]["current_scores"] == 30
    assert manifest["rows"]["dashboard_scores"] == 30
    assert manifest["dashboard"]["pages_verified"] == [
        "Overview",
        "Agent detail",
        "Data quality",
        "Model evaluation",
    ]
    assert manifest["quality"]["corrections"] == 0
    assert manifest["model"]["split"]["overlapping_agents"] == 0
    assert manifest["model"]["target_is_research_only"] is True
    assert manifest["operations"]["status"] == "healthy"
    assert all(manifest["operations"]["checks"].values())
    assert manifest["operations"]["alerts"] == []
    assert manifest["operations"]["privacy_minimized"] is True
    assert len(manifest["artifacts"]) == len(EXPECTED_ARTIFACTS)
    assert all((root / relative).is_file() for relative in manifest["artifacts"])

    with sqlite3.connect(root / "affectra.db") as database:
        assert database.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0] == 1
        assert database.execute("SELECT COUNT(*) FROM score_snapshots").fetchone()[0] == 30
        columns = {
            row[1] for row in database.execute("PRAGMA table_info(score_snapshots)")
        }
    assert not {"name", "team", "transcript", "explanation"} & columns

    with pytest.raises(ReleaseError, match="not empty"):
        run_release_demo(ReleaseConfig(output_root=root, run_version="no-overwrite"))


def test_release_cli_prints_compact_summary(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    result = main(
        [
            "--output-root",
            str(tmp_path / "cli-release"),
            "--run-version",
            "cli-release-test",
            "--num-agents",
            "30",
            "--num-days",
            "30",
            "--seed",
            "606",
            "--at-risk-fraction",
            "0.5",
            "--random-forest-estimators",
            "20",
        ]
    )
    output = capsys.readouterr().out
    assert result == 0
    assert "Affectra release demonstration complete" in output
    assert "Release: 1.0.0" in output
    assert "Current scores: 30" in output
    assert "Artifacts verified: 36" in output
    assert "not real-world burnout validation" in output
