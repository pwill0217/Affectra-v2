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
| 8 — Release | Complete | 2026-09-09 | One-command synthetic release, 36-artifact receipt, fresh-environment QA, stronger CI, final operating handoff, and real-pilot gates | [Open](docs/sprints/sprint-08-release-handoff.md) |

## Current blockers

None for the completed synthetic portfolio scope. Repository creation required
human interaction and was resolved before Sprint 0 began.

Real-world use remains intentionally gated, not silently treated as finished.
It requires named owners and evidence for purpose, jurisdiction/lawful basis,
valid outcomes, acceptable errors, representative evaluation, privacy,
retention, production access/security, licensing, appeals, monitoring, and
go/no-go authority. See [pilot requirements](docs/pilot_requirements.md).

## Latest verification

Sprint 8 used a fresh Python 3.12.14 virtual environment. Bounded runtime and
development dependencies installed successfully, and `pip check` reported no
broken requirements. Git diff validation, Ruff linting, and Python compilation
passed. All 145 tests passed in 26.55 seconds with 95.18% total source coverage,
above the 90% gate (`release.py`: 97%).

The default one-command Sprint 8 smoke used Python 3.12, seed 606, 30 synthetic
agents, 30 days, and a 0.5 generated at-risk fraction. It created 30 agent rows,
30 time-off rows, 33,151 calls, 33,151 transcripts, and 900 daily labels.
Cleaning preserved all 67,262 source rows with 0 corrections and 0 relationship
warnings and reported 1,317 non-destructive outliers. Scoring created 900 feature
rows and 30 current scores: 13 Low, 17 Moderate, and 0 High. Analytics produced
all nine outputs, including four standalone charts.

The model experiment used 660 rows/22 complete training agents and 240 rows/8
held-out agents, with 0 overlap. Test labels had 235 negatives and 5 positives.
Logistic regression ranked highest by balanced accuracy: 0.9042 accuracy, 0.8532
balanced accuracy, 0.1538 precision, 0.8000 recall, 0.2581 F1, 0.9574 ROC AUC,
0.0584 Brier score, 0.1703 log loss, and 0.0927 expected calibration error. Its
confusion counts were 213 true negatives, 22 false positives, 1 false negative,
and 4 true positives. All five operational checks passed, health was `healthy`,
and there were no alerts. SQLite contained 1 run, 30 minimized score snapshots,
and 3 model summaries. All four dashboard pages rendered with the responsible-
use warning, and all 36 release artifacts were verified. Generated evidence
remained excluded from Git. These results verify synthetic workflow behavior
only, not real-world burnout prediction.

A separate live Streamlit server check returned `ok` from its health endpoint
and HTTP 200 with HTML from the application root before clean shutdown.

## Next sprint

None. All planned Sprints 0 through 8 are complete. Normal maintenance follows
the release guide and CI gate. Any real-data or pilot proposal begins with the
human-owned pilot requirements and a newly approved scope.

## How to use this log

1. Find the first sprint marked `Planned`.
2. Read the detailed tutorial for the most recently completed sprint.
3. Complete exactly one sprint, including tests and documentation.
4. Change its status to `Complete`, add the date and tutorial link, and record
   anything that remains blocked.
5. Push the tested work before starting another sprint.
