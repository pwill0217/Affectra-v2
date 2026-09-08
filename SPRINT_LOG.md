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
| 7 — Operations | Complete | 2026-09-08 | Immutable privacy-minimized SQLite runs, safe configuration/logging, explicit monitoring baseline, health/drift evidence, and privacy/security design | [Open](docs/sprints/sprint-07-operations.md) |
| 8 — Release | Planned | — | Integrated QA, deployment docs, and final handoff | — |

## Current blockers

None. Repository creation required human interaction and was resolved before
Sprint 0 began. Future sprints must stop rather than guess if they require real
employee data, service credentials, legal policy, or a product-owner decision.

## Latest verification

Sprint 7 dependency installation, Ruff linting, Python compilation, and diff
checks passed. All 134 tests passed in 14.28 seconds with 94.98% total source
coverage (`database.py`: 100%, `monitoring.py`: 99%, `operations.py`: 99%). The
seeded end-to-end smoke generated 30 agents over 30 days: 31,388 calls, 31,388
transcripts, and 900 labels. Cleaning preserved all 63,736 rows with 0
corrections and 0 relationship warnings while reporting 1,199 non-destructive
outliers. Scoring created 900 feature rows and 30 current scores: 13 Low and 17
Moderate. Analytics wrote all nine artifacts, and all four dashboard pages
rendered without exceptions. Model evaluation used 660 rows/22 train agents and
240 rows/8 held-out agents with 0 overlap; the test target had 237 negatives and
3 positives. The dummy prior's 0.9875 accuracy but 0 precision, recall, and F1
reinforces the rare-class warning. Operations created and then compared an
explicit healthy baseline: all five checks passed with no alerts. Two immutable
runs stored 60 minimized scores and six model summaries. Generated databases,
reports, baselines, logs, datasets, and models remained excluded from Git. These
results verify synthetic workflow behavior only, not real-world burnout
prediction.

## Next sprint

Sprint 8 — Release hardening and final handoff. It will verify the complete
workflow from a fresh setup, fix integration issues, add deployment/maintenance/
demo guidance, and identify real-world pilot requirements.

## How to use this log

1. Find the first sprint marked `Planned`.
2. Read the detailed tutorial for the most recently completed sprint.
3. Complete exactly one sprint, including tests and documentation.
4. Change its status to `Complete`, add the date and tutorial link, and record
   anything that remains blocked.
5. Push the tested work before starting another sprint.
