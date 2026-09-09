"""Release-handoff documentation contract tests."""

import re
from pathlib import Path

from src.release import RELEASE_VERSION

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def test_local_markdown_links_resolve() -> None:
    """Keep beginner documentation links usable as the project evolves."""
    missing: list[str] = []
    for document in sorted(ROOT.rglob("*.md")):
        if any(part.startswith(".venv") for part in document.parts):
            continue
        for raw_target in MARKDOWN_LINK.findall(document.read_text(encoding="utf-8")):
            target = raw_target.strip().split("#", maxsplit=1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (document.parent / target).resolve().exists():
                missing.append(f"{document.relative_to(ROOT)} -> {raw_target}")
    assert missing == [], "Broken local Markdown links:\n" + "\n".join(missing)


def test_final_release_status_is_consistent() -> None:
    """The version, roadmap, README, and sprint ledger must agree."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    sprint_log = (ROOT / "SPRINT_LOG.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs" / "SPRINT_ROADMAP.md").read_text(encoding="utf-8")
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert RELEASE_VERSION == "1.0.0"
    assert 'version = "1.0.0"' in project
    assert "Sprints 0 through 8 are complete" in readme
    assert "| 8 — Release | Complete | 2026-09-09 |" in sprint_log
    assert "## Sprint 8 — Release hardening and final handoff — Complete" in roadmap
    tutorial = (
        ROOT / "docs" / "sprints" / "sprint-08-release-handoff.md"
    ).read_text(encoding="utf-8")
    assert all("FINAL_" not in document for document in (sprint_log, tutorial))
