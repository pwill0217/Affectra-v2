# Affectra 1.0 completion matrix

This matrix maps the planned work to implemented evidence. “Complete” means the
synthetic portfolio scope works and is documented; it does not mean the product
is validated or approved for real employees.

| Sprint | Status | Implemented outcome | Primary evidence |
|---|---|---|---|
| 0 — Foundation | Complete | Requirements, architecture, bounded dependencies, Git hygiene, tests, and CI | `pyproject.toml`, requirements, `.gitignore`, GitHub Actions, Sprint 0 tutorial |
| 1 — Synthetic data | Complete | Seeded five-table generator, sustained pressure simulation, schema/relationship validation, manifest | `src/data_generator.py`, data dictionary, Sprint 1 tutorial |
| 2 — Data quality | Complete | Defensive loading, type/range/missing/duplicate/orphan policies, non-destructive outliers, JSON report | `src/data_loader.py`, `src/preprocessing.py`, data-quality guide, Sprint 2 tutorial |
| 3 — Explainable scoring | Complete | Daily/rolling features, personal baselines, bounded 40/20/25/15 score, review levels and explanations | `src/features.py`, `src/scoring.py`, scoring guide, Sprint 3 tutorial |
| 4 — Analytics | Complete | Team summaries, distribution/trend/correlation tables, four accessible standalone charts | `src/analytics.py`, analytics guide, Sprint 4 tutorial |
| 5 — Experimental ML | Complete | Explicit feature allow-list, target-leakage protections, agent-group split, three baselines, classification/calibration/error evidence | `src/model_training.py`, `src/evaluation.py`, modeling guide, Sprint 5 tutorial |
| 6 — Dashboard | Complete | Overview, agent, quality, and model pages; shared filters/search; responsible-use notices; UI tests | `src/dashboard.py`, `src/app.py`, dashboard guide, Sprint 6 tutorial |
| 7 — Operations | Complete | Immutable minimized SQLite runs, privacy-safe logs, explicit health baseline, schema/distribution monitoring, threat/access/retention design | `src/database.py`, `src/monitoring.py`, `src/operations.py`, operations/privacy guides, Sprint 7 tutorial |
| 8 — Release | Complete | One-command integrated demo, artifact receipt, fresh-environment QA, stronger CI, deployment/demo/maintenance/troubleshooting handoff, pilot gates | `src/release.py`, release guide, this matrix, pilot requirements, Sprint 8 tutorial |

## Final automated gates

- Python 3.12 fresh-environment dependency installation and `pip check`
- Ruff lint over source, tests, and tooling
- Python compilation over source and tests
- Full tests with at least 90% total source coverage
- Complete generated-data-to-operations release integration test
- Four-page Streamlit `AppTest` verification
- Required-artifact contract and synthetic-only manifest check
- GitHub Actions on pushes and pull requests
- Post-run check that generated artifacts remain untracked

## Requirements coverage

| Requirement area | Status | Notes |
|---|---|---|
| Reproducible safe demo data | Complete | Generated only; no employee/customer data committed |
| Input validation and quality evidence | Complete | Explicit failures, corrections, relationships, and preserved outliers |
| Explainable decision-support score | Complete | Four visible components and contributions; no medical/performance claim |
| Interactive exploration | Complete | Team/date/review filters, agent search, sortable tables, four pages |
| Accessible analytics | Complete | Labels plus markers/dashes/text; no color-only encoding |
| Experimental ML evaluation | Complete for synthetic research | Leakage-aware and group-held-out; real-world validity remains unproven |
| Local persistence and monitoring | Complete | Minimized/additive SQLite and review-oriented health indicators |
| Privacy/security documentation | Complete as design | Production enforcement requires the pilot gates |
| Beginner reproducibility | Complete | README, eight implementation tutorials plus foundation tutorial, focused guides |
| Production readiness | Not claimed | Authentication, governance, real validation, and integrations intentionally absent |

## Known limitations

- The generated target reflects relationships intentionally encoded by the data
  generator; performance can vary substantially with the small positive class.
- Sentiment may represent customer behavior rather than agent wellbeing.
- PTO is a latest snapshot and is not presented as daily historical truth.
- The dashboard is a local app without production authentication/authorization.
- SQLite and readable drift thresholds are demonstration choices.
- No license has been selected; repository ownership does not automatically
  grant outside parties permission to reuse the code.
- Real-world use requires every gate in `docs/pilot_requirements.md`.
