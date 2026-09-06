# Sprint 5 tutorial: experimental machine-learning baseline

## Goal

This sprint builds a careful machine-learning experiment around Affectra's
research-only synthetic label. It adds reproducible preprocessing, three
baselines, an agent-disjoint train/test split, classification and calibration
metrics, error analysis, and a comparison with the transparent score.

The most important result is not a model score. It is a workflow that makes
leakage, class imbalance, mistakes, and limitations visible. Synthetic
performance does not validate real-world burnout prediction.

## Starting state

Sprint 4 ended with clean agent-day features, current explainable scores, team
summaries, trends, correlations, and accessible charts. The generator also made
`synthetic_stress_label`, but the operational feature and scoring code correctly
kept it out. There was no trained model or held-out evaluation.

Sprint 5 preserves that boundary. It builds observable features first and joins
only the binary research target afterward. The hidden pressure value, pressure
band, and simulated event never become model inputs.

## Files and functions changed

### `src/model_training.py`

- `TrainingConfig` validates paths, rolling window, holdout fraction, seed, and
  random-forest tree count.
- `ML_FEATURE_COLUMNS` is the explicit eleven-column allow-list.
- `FORBIDDEN_MODEL_FEATURES` documents identity, context, target metadata, and
  invalid historical snapshot fields.
- `prepare_training_data()` checks a complete, unique binary target grid, builds
  leakage-safe features, and joins the target by agent and date.
- `grouped_agent_split()` searches deterministic candidate splits until both
  classes appear in train and test, while holding out complete agents.
- `build_baseline_models()` creates dummy-prior, scaled logistic-regression, and
  random-forest baselines.
- `fit_and_predict()` trains each model and returns the same privacy-minimized
  held-out evidence.
- `transparent_score_comparison()` compares the best model with the transparent
  score only on current held-out snapshots.
- `write_experiment_outputs()` saves models, predictions, metrics, calibration,
  team errors, configuration, a data fingerprint, and limitations.
- `run_training()` and `main()` connect the full Python and CLI workflows.

### `src/evaluation.py`

- `classification_metrics()` calculates accuracy, balanced accuracy, precision,
  recall, F1, ROC AUC, Brier score, log loss, and confusion counts.
- `calibration_table()` compares probability bins with synthetic positive rates.
- `expected_calibration_error()` summarizes the weighted calibration gap.
- `team_error_analysis()` exposes mistakes by synthetic team for inspection.
- `evaluate_predictions()` evaluates each baseline consistently.
- `choose_best_model()` uses balanced accuracy with a deterministic tie-break.

`tests/test_evaluation.py` and `tests/test_model_training.py` cover calculations,
bad inputs, leakage protections, split behavior, model fitting, generated files,
and the CLI. `joblib` is now an explicit dependency because the code directly
uses it to save model pipelines. README, architecture, business requirements,
roadmap, sprint log, and `docs/modeling.md` now describe the implemented system.

## Beginner concepts

### Features versus a target

Features are the columns a model can inspect. The target is the answer used
during supervised training. If a target or a hidden value used to create it is
included as a feature, the model can copy the answer. That is target leakage,
and it produces impressive but meaningless test results.

Affectra uses an allow-list instead of “all numeric columns.” Only rolling
observable call/tone metrics and personal-baseline ratios are allowed. Names,
IDs, teams, roles, dates, synthetic pressure metadata, and score outputs are not
features. PTO fields are also excluded because they describe one final snapshot,
not what was known on every historical day.

### Why split by agent

A random row split could put Monday for agent 7 in training and Tuesday for the
same agent in testing. The model may recognize that person's repeated pattern,
which makes the test easier than predicting for someone unseen.

`GroupShuffleSplit` treats all rows for an agent as one group. An agent is wholly
in training or wholly in testing. The manifest proves the overlap count is zero.

### Why use three baselines

The dummy model learns no feature pattern and provides a reality check.
Logistic regression learns a linear probability boundary and is easier to
inspect. Random forest combines decision trees to learn nonlinear boundaries.
Comparing them shows whether complexity helped on the same held-out data.

### Why accuracy is not enough

Suppose 99 of 100 rows are negative. A model that always predicts negative is
99% accurate but finds none of the positives. Recall would be zero. Balanced
accuracy gives both classes equal importance; precision describes how often a
positive flag was correct; the confusion matrix shows the raw mistakes.

Probability quality also matters. Brier score and log loss penalize poor
probabilities. Calibration asks whether rows predicted near 20% positive are
actually positive about 20% of the time. With a tiny positive sample, all of
these estimates are unstable and must be treated as demonstration evidence.

## How data flows

```text
five generated CSVs
        |
        v
Sprint 2 validation and cleaning
        |
        +--> observable feature builder --> eleven allowed model features
        |
        +--> synthetic_stress_label ------> research target only
                              |
                              v
                 complete agent-day table
                              |
                              v
             agent-disjoint train/test split
                    /          |          \
                   v           v           v
             dummy prior   logistic   random forest
                    \          |          /
                              v
       metrics + calibration + errors + predictions
                              |
                              v
   latest-snapshot comparison with transparent score
```

Names and transcript text are not written to prediction or error outputs.

## Reproduce the work

Create and activate a Python 3.12 environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

Generate a sufficiently large synthetic demonstration and run every stage:

```bash
python -m src.data_generator \
  --num-agents 30 \
  --start-date 2026-07-01 \
  --num-days 30 \
  --seed 505 \
  --at-risk-fraction 0.5 \
  --output-dir data/synthetic
python -m src.preprocessing \
  --input-dir data/synthetic \
  --output-dir data/processed
python -m src.scoring \
  --input-dir data/processed \
  --output-dir data/scored
python -m src.analytics \
  --input-dir data/scored \
  --output-dir data/analytics
python -m src.model_training \
  --input-dir data/processed \
  --output-dir models \
  --rolling-window 7 \
  --test-size 0.25 \
  --random-state 42
```

The research target is rare. If the program cannot create agent-disjoint train
and test partitions containing both classes, generate more agents or increase
the synthetic `--at-risk-fraction`; do not weaken the leakage safeguard.

Run verification:

```bash
python -m ruff check .
python -m compileall -q src tests
python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=90
```

## Test and smoke evidence

Dependency installation, Ruff linting, and Python compilation passed. All 97
tests passed with 94.48% total source coverage; `evaluation.py` reached 100%
and `model_training.py` reached 98%.

The end-to-end smoke test used seed 505, 30 agents, 30 days, and a 0.5 synthetic
at-risk fraction. It created 34,104 calls, 34,104 transcripts, and 900 agent-day
labels. Cleaning preserved all 69,168 rows with zero corrections and zero
relationship warnings while reporting 1,282 non-destructive outliers. Scoring
created 900 feature rows and 30 current scores, and analytics wrote nine files.

The model split used 660 rows from 22 training agents and 240 rows from 8 held-
out agents, with zero agent overlap. Test labels contained 237 negatives and 3
positives. Random forest ranked highest by balanced accuracy:

| Metric | Dummy prior | Logistic regression | Random forest |
|---|---:|---:|---:|
| Accuracy | 0.987500 | 0.916667 | 0.945833 |
| Balanced accuracy | 0.500000 | 0.793249 | 0.808017 |
| Precision | 0.000000 | 0.095238 | 0.142857 |
| Recall | 0.000000 | 0.666667 | 0.666667 |
| F1 | 0.000000 | 0.166667 | 0.235294 |
| ROC AUC | 0.500000 | 0.947961 | 0.960619 |
| Brier score | 0.012609 | 0.073344 | 0.031607 |
| Expected calibration error | 0.016288 | 0.126210 | 0.050609 |

The dummy's 98.75% accuracy and zero recall is the clearest lesson: high
accuracy can hide complete failure on a rare positive class. Only three positive
test rows also means the learned-model metrics have very high uncertainty.

On the eight held-out current snapshots, the random-forest probability and
transparent score had 0.756678 Pearson correlation and 75% review-flag
agreement. That comparison is descriptive and does not validate either method.

## Decisions and tradeoffs

- Complete agents are held out even though this reduces the effective sample.
  Honest generalization evidence matters more than an easier row-level result.
- Time-off snapshots are excluded from historical model features, while the
  transparent score comparison stays on latest snapshots only.
- Class weights help learned models pay attention to rare positives, but they do
  not create information or fix a tiny evaluation sample.
- Balanced accuracy selects the reported baseline. Every metric and raw
  confusion count remains visible so one ranking cannot hide tradeoffs.
- Model pipelines are stored with joblib for a later dashboard, but generated
  artifacts are not versioned in Git. Never load an untrusted joblib file.
- Synthetic team error rows help reveal uneven behavior; they are not a fairness
  audit or a basis for comparing teams.

## Blockers

None. The sprint used generated data only and required no private employee data,
credentials, policy choice, or external dataset.

## What comes next

Sprint 6 builds the Streamlit dashboard. It will connect the existing summaries,
agent details, quality report, explainable scores, and model evaluation into
interactive pages with date/team/risk filters, responsible-use notices, UI
smoke tests, and beginner launch instructions.
