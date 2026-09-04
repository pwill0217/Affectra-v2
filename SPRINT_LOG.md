# Sprint Log

This is the running, beginner-friendly record of Affectra's development. Each
row links to a detailed tutorial containing the code concepts, commands,
verification, decisions, and blockers for that day.

| Sprint | Status | Date | Outcome | Tutorial |
|---|---|---|---|---|
| 0 — Foundation | Complete | 2026-09-01 | Reproducible project foundation, requirements, roadmap, tests, and CI | [Open](docs/sprints/sprint-00-foundation.md) |
| 1 — Synthetic data | Complete | 2026-09-02 | Seeded CLI pipeline, sustained pressure simulation, research labels, validation, and manifest | [Open](docs/sprints/sprint-01-synthetic-data.md) |
| 2 — Data quality | Complete | 2026-09-03 | Defensive ingestion, typed cleaning, relationship repair, outlier reporting, and quality report | [Open](docs/sprints/sprint-02-data-quality.md) |
| 3 — Metrics and score | Complete | 2026-09-04 | Leakage-safe daily/rolling features, personal-baseline ratios, and explainable 40/20/25/15 scoring | [Open](docs/sprints/sprint-03-explainable-scoring.md) |
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

Sprint 3 dependency installation, Ruff linting, and Python compilation passed.
All 60 tests passed with 93% total source coverage (`features.py`: 91%,
`scoring.py`: 99%). The end-to-end smoke test generated and processed 20 agents
across 14 days: 20 agent rows, 20 time-off rows, 9,232 calls, 9,232 matched
transcripts, and 280 daily labels. Cleaning made 0 corrections, found 0
relationship warnings, and preserved all rows while reporting 349 IQR outliers.
Scoring produced 280 agent-day feature rows and 20 latest-agent scores: 13 Low
and 7 Moderate, ranging from 16.59 to 50.17. No hidden synthetic target metadata
entered the feature table. Generated outputs remained excluded from Git.

## Next sprint

Sprint 4 — Exploratory analytics and visualizations. It will create team
summaries, distributions, trends, correlations, and at least three accessible,
well-labeled chart types using processed features and scores.

## How to use this log

1. Find the first sprint marked `Planned`.
2. Read the detailed tutorial for the most recently completed sprint.
3. Complete exactly one sprint, including tests and documentation.
4. Change its status to `Complete`, add the date and tutorial link, and record
   anything that remains blocked.
5. Push the tested work before starting another sprint.
