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
| 4 — Analytics | Complete | 2026-09-05 | Team summaries, daily trends, observable-feature correlations, and four accessible standalone charts | [Open](docs/sprints/sprint-04-analytics-visualizations.md) |
| 5 — ML baseline | Planned | — | Leakage-aware experimental model and evaluation | — |
| 6 — Dashboard | Planned | — | Interactive Streamlit product | — |
| 7 — Operations | Planned | — | Persistence, privacy, security, and monitoring | — |
| 8 — Release | Planned | — | Integrated QA, deployment docs, and final handoff | — |

## Current blockers

None. Repository creation required human interaction and was resolved before
Sprint 0 began. Future sprints must stop rather than guess if they require real
employee data, service credentials, legal policy, or a product-owner decision.

## Latest verification

Sprint 4 dependency installation, Ruff linting, and Python compilation passed.
All 70 tests passed with 93.50% total source coverage (`analytics.py`: 98%). The
end-to-end smoke test generated and processed 20 agents across 14 days using
seed 404: 20 agent rows, 20 time-off rows, 8,805 calls, 8,805 matched
transcripts, and 280 daily labels. Cleaning preserved all 17,930 rows with 0
corrections and 0 relationship warnings while reporting 327 non-destructive IQR
outliers. Scoring produced 280 agent-day rows and 20 current scores: 13 Low and
7 Moderate, ranging from 12.66 to 49.95. Analytics consumed all 280 feature
rows and 20 scores and created four tables, four standalone charts, and one
manifest. Generated outputs remained excluded from Git.

## Next sprint

Sprint 5 — Experimental machine-learning baseline. It will define a
leakage-aware synthetic feature/target strategy, train reproducible baselines,
report classification, calibration, and error evidence, and compare them with
the transparent score without claiming real-world validation.

## How to use this log

1. Find the first sprint marked `Planned`.
2. Read the detailed tutorial for the most recently completed sprint.
3. Complete exactly one sprint, including tests and documentation.
4. Change its status to `Complete`, add the date and tutorial link, and record
   anything that remains blocked.
5. Push the tested work before starting another sprint.
