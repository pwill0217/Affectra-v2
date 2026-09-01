# Affectra Sprint Roadmap

One sprint is completed and pushed per day. A sprint is complete only when its
code, tests, documentation, and verification evidence are committed. If a task
requires credentials, product policy, a real dataset, or another human decision,
work stops and the blocker is recorded instead of silently guessing.

## Sprint 0 — Foundation and product definition — Complete

- Copy and repair the original project foundation.
- Define product goals, limitations, requirements, and ethical boundaries.
- Replace the environment dump with understandable dependency manifests.
- Add the project layout, automated tests, CI, and beginner documentation.

## Sprint 1 — Reproducible synthetic-data pipeline — Next

- Move generator settings into a clear configuration/CLI.
- Guarantee reproducible output from a supplied random seed.
- Add realistic pressure patterns and an explicit synthetic target for research.
- Validate generated schemas and relationships.
- Add unit and integration tests plus a data dictionary.

## Sprint 2 — Ingestion, cleaning, and data quality

- Load all four tables with clear missing-file and schema errors.
- Parse dates and numeric values without recursive function calls.
- Detect missing values, invalid ranges, duplicates, orphan keys, and outliers.
- Produce cleaned outputs and a machine-readable quality report.
- Test valid and intentionally broken fixtures.

## Sprint 3 — Agent metrics and explainable stress score

- Aggregate calls and sentiment into daily and rolling agent features.
- Compare each agent with their personal baseline.
- Implement configurable component weights: 40/20/25/15.
- Produce risk levels and plain-language explanations.
- Test score bounds, edge cases, and weight validation.

## Sprint 4 — Exploratory analytics and visualizations

- Create team summaries, distributions, trends, and correlation analysis.
- Add at least three well-labeled chart types.
- Ensure charts use processed data and accessible labels.
- Document what each visualization can and cannot prove.

## Sprint 5 — Experimental machine-learning baseline

- Define a leakage-aware feature and target strategy for synthetic data.
- Build reproducible preprocessing and baseline models.
- Evaluate with classification metrics, calibration, and error analysis.
- Compare ML results with the transparent score.
- Clearly document why synthetic performance is not real-world validation.

## Sprint 6 — Interactive Streamlit dashboard

- Build overview, agent detail, data-quality, and model-evaluation pages.
- Add date, team, and risk filters plus interactive queries.
- Explain each score and display responsible-use notices.
- Add UI smoke tests and launch instructions.

## Sprint 7 — Persistence, privacy, security, and monitoring

- Add a local persistence layer with safe initialization.
- Keep secrets and sensitive data out of source control and logs.
- Add role/access design notes, retention guidance, and threat analysis.
- Track schema, drift, and score-distribution health indicators.

## Sprint 8 — Release hardening and final handoff

- Run the full test, lint, data, model, and dashboard workflow from a fresh setup.
- Fix integration failures and remove dead or duplicated code.
- Add deployment, maintenance, troubleshooting, and demo instructions.
- Produce a final completion matrix and identify real-world pilot requirements.

## Definition of done for every sprint

- Scope for that sprint is implemented rather than represented by placeholders.
- Relevant automated tests pass locally.
- The beginner walkthrough lists commands and explains the concepts.
- `SPRINT_LOG.md` includes results, blockers, and the next sprint.
- Changes are committed to the default branch of `pwill0217/Affectra-v2`.
