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
| 5 — ML baseline | Complete | 2026-09-06 | Agent-disjoint dummy, logistic, and forest baselines with classification, calibration, error, and score-comparison evidence | [Open](docs/sprints/sprint-05-experimental-ml.md) |
| 6 — Dashboard | Planned | — | Interactive Streamlit product | — |
| 7 — Operations | Planned | — | Persistence, privacy, security, and monitoring | — |
| 8 — Release | Planned | — | Integrated QA, deployment docs, and final handoff | — |

## Current blockers

None. Repository creation required human interaction and was resolved before
Sprint 0 began. Future sprints must stop rather than guess if they require real
employee data, service credentials, legal policy, or a product-owner decision.

## Latest verification

Sprint 5 dependency installation, Ruff linting, and Python compilation passed.
All 97 tests passed with 94.48% total source coverage (`evaluation.py`: 100%,
`model_training.py`: 98%). The seeded end-to-end smoke test generated 30 agents
over 30 days: 34,104 calls, 34,104 transcripts, and 900 daily labels. Cleaning
preserved all 69,168 rows with 0 corrections and 0 relationship warnings while
reporting 1,282 non-destructive IQR outliers. Scoring created 900 feature rows
and 30 current scores; analytics wrote all nine artifacts. Model evaluation used
660 rows from 22 training agents and 240 rows from 8 entirely held-out agents,
with 0 overlapping agents. The test target had 237 negatives and 3 positives.
Random forest ranked highest by balanced accuracy (0.808017), with 0.945833
accuracy, 0.142857 precision, 0.666667 recall, 0.235294 F1, 0.960619 ROC AUC,
0.031607 Brier score, and 0.050609 expected calibration error. The dummy model's
0.9875 accuracy but 0 recall demonstrates the class-imbalance warning. Generated
datasets and model artifacts remained excluded from Git.

## Next sprint

Sprint 6 — Interactive Streamlit dashboard. It will add overview, agent-detail,
data-quality, and model-evaluation pages with filters, explanations,
responsible-use notices, UI smoke tests, and launch instructions.

## How to use this log

1. Find the first sprint marked `Planned`.
2. Read the detailed tutorial for the most recently completed sprint.
3. Complete exactly one sprint, including tests and documentation.
4. Change its status to `Complete`, add the date and tutorial link, and record
   anything that remains blocked.
5. Push the tested work before starting another sprint.
