# Sprint Log

This is the running, beginner-friendly record of Affectra's development. Each
row links to a detailed tutorial containing the code concepts, commands,
verification, decisions, and blockers for that day.

| Sprint | Status | Date | Outcome | Tutorial |
|---|---|---|---|---|
| 0 — Foundation | Complete | 2026-09-01 | Reproducible project foundation, requirements, roadmap, tests, and CI | [Open](docs/sprints/sprint-00-foundation.md) |
| 1 — Synthetic data | Complete | 2026-09-02 | Seeded CLI pipeline, sustained pressure simulation, research labels, validation, and manifest | [Open](docs/sprints/sprint-01-synthetic-data.md) |
| 2 — Data quality | Complete | 2026-09-03 | Defensive ingestion, typed cleaning, relationship repair, outlier reporting, and quality report | [Open](docs/sprints/sprint-02-data-quality.md) |
| 3 — Metrics and score | Planned | — | Agent features and transparent 40/20/25/15 score | — |
| 4 — Analytics | Planned | — | Analysis functions and accessible visualizations | — |
| 5 — ML baseline | Planned | — | Leakage-aware experimental model and evaluation | — |
| 6 — Dashboard | Planned | — | Interactive Streamlit product | — |
| 7 — Operations | Planned | — | Persistence, privacy, security, and monitoring | — |
| 8 — Release | Planned | — | Integrated QA, deployment docs, and final handoff | — |

## Current blockers

None. Repository creation required human interaction and was resolved before
Sprint 0 began. Future sprints must stop rather than guess if they require real
employee data, service credentials, legal policy, or a product-owner decision.

## Latest verification

Sprint 2 dependency installation, Ruff linting, and Python compilation passed.
All 28 tests passed with 91% total source coverage (`data_loader.py`: 86%,
`preprocessing.py`: 93%). The end-to-end smoke test generated and processed 8
agents across 5 days: 8 agent rows, 8 time-off rows, 1,530 calls, 1,530 matched
transcripts, and 40 daily labels. It preserved all 3,116 rows, made 0
corrections, found 0 relationship warnings, and reported 63 non-destructive IQR
outliers. Generated outputs remained excluded from Git.

## Next sprint

Sprint 3 — Agent metrics and explainable stress score. It will aggregate
agent-day features, compare agents with their own baselines, implement the
configurable 40/20/25/15 component weights, and explain every resulting risk
level in plain language.

## How to use this log

1. Find the first sprint marked `Planned`.
2. Read the detailed tutorial for the most recently completed sprint.
3. Complete exactly one sprint, including tests and documentation.
4. Change its status to `Complete`, add the date and tutorial link, and record
   anything that remains blocked.
5. Push the tested work before starting another sprint.
