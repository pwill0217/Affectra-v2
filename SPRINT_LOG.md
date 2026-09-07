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
| 6 — Dashboard | Complete | 2026-09-07 | Four-page Streamlit product with shared filters, score explanations, data-quality and model evidence, accessible charts, and responsible-use guidance | [Open](docs/sprints/sprint-06-streamlit-dashboard.md) |
| 7 — Operations | Planned | — | Persistence, privacy, security, and monitoring | — |
| 8 — Release | Planned | — | Integrated QA, deployment docs, and final handoff | — |

## Current blockers

None. Repository creation required human interaction and was resolved before
Sprint 0 began. Future sprints must stop rather than guess if they require real
employee data, service credentials, legal policy, or a product-owner decision.

## Latest verification

Sprint 6 dependency installation, Ruff linting, and Python compilation passed.
All 102 tests passed with 94.17% total source coverage (`app.py`: 93%,
`dashboard.py`: 92%). Streamlit `AppTest` rendered all four pages from complete
generated outputs with zero exceptions, and a headless Streamlit server reached
its started state. The seeded end-to-end smoke test generated 30 agents over 30
days: 33,151 calls, 33,151 transcripts, and 900 labels. Cleaning preserved all
67,262 rows with 0 corrections and 0 relationship warnings while reporting
1,317 non-destructive outliers. Scoring created 900 feature rows and 30 current
scores: 13 Low and 17 Moderate. Analytics wrote all nine artifacts. Model
evaluation used 660 rows from 22 training agents and 240 rows from 8 entirely
held-out agents, with 0 overlapping agents. The test target had 235 negatives
and 5 positives. Logistic regression ranked highest by balanced accuracy
(0.853191), with 0.904167 accuracy, 0.153846 precision, 0.800000 recall,
0.258065 F1, 0.957447 ROC AUC, 0.058426 Brier score, 0.170341 log loss, and
0.092672 expected calibration error. These generated results verify workflow
behavior only; they do not validate real-world burnout prediction. Generated
datasets and model artifacts remained excluded from Git.

## Next sprint

Sprint 7 — Operations. It will add persistence, configuration and secrets
practices, privacy and security guidance, structured logging, health checks, and
drift monitoring.

## How to use this log

1. Find the first sprint marked `Planned`.
2. Read the detailed tutorial for the most recently completed sprint.
3. Complete exactly one sprint, including tests and documentation.
4. Change its status to `Complete`, add the date and tutorial link, and record
   anything that remains blocked.
5. Push the tested work before starting another sprint.
