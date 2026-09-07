# Sprint 6 tutorial: interactive Streamlit dashboard

## Goal

This sprint turns Affectra's generated tables and reports into a local,
interactive product. The dashboard gives a learner four focused pages: a team
overview, one synthetic agent's explainable score, the data-quality evidence,
and the experimental model evaluation.

The interface keeps the same safety boundary as the pipeline. It is decision
support for a supportive human review, not a diagnosis, performance rating, or
automated employment decision. The displayed model results come from generated
data and do not validate real-world burnout prediction.

## Starting state

Sprint 5 already produced the facts the interface needs:

- `data/scored/agent_day_features.csv` contains observable daily history;
- `data/scored/risk_scores.csv` contains current transparent scores;
- `data/processed/data_quality_report.json` records cleaning evidence; and
- `models/` contains experimental metrics, calibration, team-error evidence,
  and an agent-disjoint split manifest.

There was no application for exploring those files together. A user had to
open CSV and JSON files individually. Sprint 6 adds a presentation layer while
leaving generation, cleaning, scoring, analytics, and training independent.

## Files and functions changed

### `src/dashboard.py`

This module contains testable dashboard logic without depending on Streamlit's
page state.

- `DashboardConfig` names the three generated input directories.
- `load_dashboard_data()` requires and reads seven files, parses dates, reuses
  analytics validation, and checks report, model, calibration, and error schemas.
- `filter_dashboard_data()` applies team, review-level, date, name, and ID
  queries consistently to current scores and feature history.
- `component_chart()` explains the four transparent score components.
- `agent_trend_chart()` compares observable trends with a personal-baseline
  reference of 1.0.
- `calibration_chart()` compares predicted probability with the observed
  synthetic-label rate and prints each bin's sample size.
- `model_metrics_table()` and `quality_tables()` turn nested JSON evidence into
  readable tables.

The chart designs use labels, markers, and line styles as well as color. That
makes the important meaning easier to read and avoids relying on color alone.

### `src/app.py`

This is the Streamlit presentation layer. It loads validated data once, creates
shared sidebar controls, and renders four pages:

- **Overview**: current population metrics, review-level distribution, team
  score spread, synthetic-agent search, and a sortable score table.
- **Agent detail**: current score, plain-language explanation, four components,
  supporting evidence, and personal-baseline trends.
- **Data quality**: run status, preserved rows, corrections, reported outliers,
  per-table details, and relationship checks.
- **Model evaluation**: baseline comparison, confusion counts, calibration,
  synthetic-team errors, transparent-score comparison, and split evidence.

Every page begins with the same responsible-use warning. Global filters affect
the score and feature views; the quality and model pages clearly say that they
show whole-run evidence. This prevents a visual filter from looking like it
changed the cleaning or model experiment.

### Configuration, documentation, and tests

- `.streamlit/config.toml` sets headless operation, disables telemetry, and
  uses an accessible application palette.
- `tests/test_dashboard.py` tests input validation, filtering, tables, charts,
  and all four pages with Streamlit's `AppTest` browser-free harness.
- `docs/dashboard.md` explains launch commands, pages, filters, responsible
  use, alternate data paths, and troubleshooting.
- README, architecture, business requirements, roadmap, and sprint log now
  describe the implemented dashboard and the next sprint.

## Beginner concepts

### Separate facts from presentation

`dashboard.py` decides how to load, validate, filter, and transform data.
`app.py` decides what controls and visual elements to show. This separation is
useful because the data behavior can be tested with ordinary Python tests, and
the interface can change without rewriting the underlying rules.

### Validate at a boundary

A CSV existing on disk does not mean it has the columns the app expects.
`load_dashboard_data()` treats the dashboard as a boundary: all required files
and schemas must pass before any page renders. If an input is missing or
invalid, the app explains which pipeline commands to run instead of showing a
partial, misleading result.

### Session state and widgets

Streamlit reruns the script from top to bottom whenever a user changes a widget.
The widget values act as the current application state. Cached file loading
avoids rereading unchanged generated outputs on every interaction. The sidebar
controls produce filtered data frames, and each page renders from those frames.

### Why filters do not retrain a model

Changing a team or date filter only changes what is displayed. It does not
clean the source again, recompute scores, or retrain a baseline. Model and
quality evidence therefore stays tied to the complete run that produced it.

## How data flows

```text
generated synthetic CSVs
        |
        v
cleaning --> data-quality JSON
        |
        +--> scoring --> features + current transparent scores
        |
        +--> model experiment --> metrics + calibration + error evidence
                                      |
                                      v
                         validated dashboard loader
                                      |
                           shared interactive filters
                 /             |             |             \
                v              v             v              v
            overview      agent detail   data quality   model evaluation
```

The interface displays no raw transcript text. Generated model files are not
loaded by the dashboard; only their minimized evaluation evidence is read.

## Reproduce the work

Create and activate a Python 3.12 environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

Create a stable generated demonstration and all dashboard inputs:

```bash
python -m src.data_generator \
  --num-agents 30 \
  --start-date 2026-08-01 \
  --num-days 30 \
  --seed 606 \
  --at-risk-fraction 0.5
python -m src.preprocessing
python -m src.scoring
python -m src.analytics
python -m src.model_training
```

Launch the application:

```bash
python -m streamlit run src/app.py
```

Open the local URL Streamlit prints, normally `http://localhost:8501`, and stop
the server with Ctrl+C. See `docs/dashboard.md` for alternate input directories
and troubleshooting.

Run verification:

```bash
python -m ruff check .
python -m compileall -q src tests
python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=90
```

## Test and smoke evidence

Dependency installation, Ruff linting, and Python compilation passed. All 102
tests passed with 94.17% total source coverage; `app.py` reached 93% and
`dashboard.py` reached 92%. Streamlit's `AppTest` rendered overview, agent
detail, data quality, and model evaluation from a complete generated run with
zero page exceptions. A headless Streamlit server also reached its started
state and printed its local URL.

The end-to-end smoke test used seed 606, 30 synthetic agents, 30 days, and a 0.5
synthetic at-risk fraction. It generated 33,151 calls, 33,151 transcripts, and
900 labels. Cleaning preserved all 67,262 rows with zero corrections and zero
relationship warnings while reporting 1,317 non-destructive outliers. Scoring
created 900 feature rows and 30 current scores: 13 Low and 17 Moderate.
Analytics wrote all nine expected artifacts.

The model experiment used 660 rows from 22 training agents and 240 rows from 8
held-out agents with zero overlap. The held-out labels contained 235 negatives
and 5 positives. Logistic regression ranked highest by balanced accuracy:

| Metric | Result |
|---|---:|
| Accuracy | 0.904167 |
| Balanced accuracy | 0.853191 |
| Precision | 0.153846 |
| Recall | 0.800000 |
| F1 | 0.258065 |
| ROC AUC | 0.957447 |
| Brier score | 0.058426 |
| Log loss | 0.170341 |
| Expected calibration error | 0.092672 |
| Confusion counts | TN 213, FP 22, FN 1, TP 4 |

These results verify that the software flows end to end. They describe a small,
generated experiment and are not evidence that Affectra predicts real-world
burnout, establishes cause, or is appropriate for employment decisions.

## Decisions and tradeoffs

- The dashboard reads existing artifacts instead of silently running expensive
  pipeline stages. This keeps provenance and failures visible.
- Schema checks are strict because an explicit error is safer than a plausible
  chart built from incompatible files.
- Global team and risk filters operate on current scores, then identify matching
  feature histories. This makes filter behavior predictable across pages.
- The app shows complete model and quality evidence rather than pretending a UI
  filter created a new evaluation.
- Agent identifiers and names are acceptable only because the current workflow
  is synthetic. A real deployment requires Sprint 7 privacy and access controls.
- The dashboard favors explanatory tables and charts over automated actions.

## Blockers

None. The sprint used generated data only and required no private employee data,
credentials, legal decision, or destructive product choice.

## What comes next

Sprint 7 adds operational safeguards: a persistence layer, configuration and
secrets practices, privacy and security guidance, structured logging, health
checks, and drift monitoring. It must preserve the dashboard's responsible-use
boundary and must not introduce real employee data without explicit approval.
