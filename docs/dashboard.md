# Streamlit dashboard guide

## Prepare and launch

The dashboard reads generated outputs; it does not silently generate, repair,
score, or train data. Complete the pipeline first:

```bash
python -m src.data_generator \
  --num-agents 30 \
  --num-days 30 \
  --seed 606 \
  --at-risk-fraction 0.5
python -m src.preprocessing
python -m src.scoring
python -m src.analytics
python -m src.model_training
python -m streamlit run src/app.py
```

Streamlit prints a local browser URL, normally `http://localhost:8501`. Stop the
server with Ctrl+C.

The normal inputs are `data/scored/`, `data/processed/`, and `models/`. Tests or
deployments can point to other generated directories without changing code:

```bash
export AFFECTRA_SCORED_DIR=data/demo/scored
export AFFECTRA_PROCESSED_DIR=data/demo/processed
export AFFECTRA_MODELS_DIR=data/demo/models
python -m streamlit run src/app.py
```

Use `$env:AFFECTRA_SCORED_DIR = "data/demo/scored"` syntax in Windows
PowerShell.

## Shared filters and queries

The sidebar provides page navigation, multi-select team and review-level
filters, and a feature-history date range. The overview also searches synthetic
agent names or IDs. Agent detail provides a single-agent selector. Model
evaluation provides a baseline-model selector. Tables are interactive and can
be sorted from their column headers.

Team and review filters select current score rows. Feature history is then
limited to those same agents and the chosen dates. Quality and model evidence
remain whole-run evidence; the sidebar says so explicitly to avoid suggesting
that a visual filter changed how the pipeline was validated or trained.

## Pages

### Overview

The overview shows current agent/team counts, Moderate-or-High review count,
average score, a labeled review-level distribution, a team box plot, and a
sortable score table. These views summarize the current generated population.
They cannot diagnose health, explain cause, establish fair team rankings, or
measure employee performance.

### Agent detail

Agent detail shows the selected synthetic agent's current score, level, team,
plain-language explanation, all four component values, four evidence sentences,
and observable calls/ACW/duration ratios over the selected dates. A 1.0 reference
means “at personal baseline.” Lines use distinct dashes and markers, while bars
print their values, so the views do not rely on color alone.

### Data quality

This page shows the overall status, row count, corrections, preserved outliers,
per-table evidence, and relationship checks. An outlier count is not an error
count: Sprint 2 intentionally reports unusual values without automatically
deleting them.

### Model evaluation

This page compares every baseline's classification and calibration evidence,
shows raw confusion counts, plots probability calibration with bin sizes,
displays synthetic-team errors, and exposes the latest-snapshot comparison with
the transparent score. It also states the agent-disjoint split counts. The
generated label is rare, so accuracy must never be read by itself.

## Responsible use

Every page begins with the same notice: Affectra is decision support, not a
diagnosis, performance rating, or basis for punitive action. The current app
uses generated synthetic data. Its model metrics demonstrate software behavior
and generator relationships; they do not validate real-world burnout prediction.

The dashboard intentionally does not include automated employment actions,
medical conclusions, raw transcript display, or live external integrations.

## Troubleshooting

- “Missing dashboard input file(s)” means a pipeline command has not produced
  one of the required score, quality, calibration, error, or manifest files.
  Run the five commands displayed by the app, in order.
- If model training cannot create a two-class agent-disjoint split, regenerate a
  larger synthetic population or raise the synthetic at-risk fraction. Do not
  weaken the split safeguard.
- If port 8501 is busy, run `python -m streamlit run src/app.py --server.port 8502`.
- Streamlit caches validated reads. Use its menu to rerun or clear cache after
  intentionally replacing generated files.
