# Sprint 4 tutorial: analytics and accessible visualizations

## Goal

This sprint turns the feature history and current explainable scores from Sprint
3 into summaries that a person can explore. It adds team summaries,
distributions, daily trends, Pearson correlations, and four chart types. Every
chart includes non-color cues and written limits.

This is exploratory decision support built with synthetic data. Passing tests
does not prove that Affectra predicts real-world burnout.

## Starting state

At the end of Sprint 3, the pipeline could generate safe demo data, clean five
related tables, calculate agent-day features, and score each agent's latest
snapshot. The score was transparent, but a learner still had to inspect CSV
rows directly. There was no reusable analytics module or chart output.

The two Sprint 3 inputs used here are:

- `data/scored/agent_day_features.csv`: one row per agent and simulated day;
- `data/scored/risk_scores.csv`: one current, explainable score per agent.

Using these files matters because analytics should not quietly bypass the
cleaning, relationship checks, feature safeguards, or scoring rules.

## Files and functions changed

### `src/analytics.py`

This new module contains the full analytics workflow:

- `AnalyticsConfig` stores input and output paths.
- `load_analytics_inputs()` reads the two expected CSVs.
- `validate_analytics_inputs()` checks schemas, dates, finite numbers, score
  ranges, known review levels, duplicate scores, and agent relationships.
- `build_team_summary()` groups current scores by team.
- `build_risk_distribution()` counts every ordered review level, including
  levels with zero agents.
- `build_daily_trends()` groups observable feature history by date.
- `build_correlation_matrix()` calculates Pearson correlations after removing
  constant columns.
- Four chart functions build a bar chart, multi-line trend chart, box plot, and
  annotated heatmap.
- `run_analytics()` writes the tables, standalone charts, and JSON manifest.
- `main()` exposes the workflow as `python -m src.analytics`.

### Tests and documentation

`tests/test_analytics.py` checks calculations, invalid inputs, accessibility
cues, all generated files, the manifest, and the command-line path. `README.md`,
`docs/architecture.md`, `docs/business_requirements.md`, the sprint roadmap, and
`docs/analytics.md` now describe the implemented flow and responsible use.

## Beginner concepts

### Grouping and aggregation

An aggregation turns many rows into a smaller summary. For example,
`groupby("team")` gathers score rows for the same team. Operations such as
`mean`, `median`, `max`, and `size` then answer different questions:

- mean is the arithmetic average;
- median is the middle value and is less sensitive to extremes;
- maximum is the largest current value;
- size is the number of rows, which here equals current agents.

The review rate is `(Moderate count + High count) / agent count`. It is a prompt
for review, not a claim about how many people have a medical condition.

### A personal-baseline ratio

A ratio of 1.0 means the rolling metric equals that agent's baseline. A value of
1.2 means 20% above baseline; 0.8 means 20% below it. The trend chart averages
these ratios across agent-days. This preserves the personal comparison created
in Sprint 3 while giving a team-level overview.

### Pearson correlation

Pearson's *r* summarizes a linear relationship between two numeric columns:

- near `1`: they tend to rise together;
- near `-1`: one tends to fall as the other rises;
- near `0`: no strong linear relationship is visible.

Correlation is not causation. Two columns can move together because one affects
the other, because a third factor affects both, or by chance. Constant columns
cannot have a meaningful correlation and are removed. Synthetic target metadata
and formula-derived score components are excluded from this view.

### Accessible charts

Color can help, but it cannot be the only way to understand a chart. This sprint
pairs color with other signals:

- bar labels state the count and percentage;
- trend lines use different dashes and marker shapes;
- box plots show every point and label both axes;
- heatmap cells print their numeric correlation.

Standalone HTML includes the Plotly JavaScript needed to pan, zoom, and inspect
values without an internet connection.

## How data flows

```text
five synthetic CSVs
        |
        v
Sprint 2 cleaning and validation
        |
        v
Sprint 3 agent-day features + latest scores
        |
        v
Sprint 4 input validation
        |
        +--> team summary + risk distribution
        |
        +--> daily observable trends
        |
        +--> observable-feature correlations
        |
        v
four standalone HTML charts + analytics manifest
```

No chart reads raw transcript text, shows an agent name, or uses the hidden
synthetic pressure values.

## Reproduce the sprint

From a fresh clone with Python 3.12 or newer:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

On Windows PowerShell, activation is `.venv\Scripts\Activate.ps1`.

Run the full data flow:

```bash
python -m src.data_generator \
  --num-agents 20 \
  --start-date 2026-08-01 \
  --num-days 14 \
  --seed 404 \
  --output-dir data/synthetic
python -m src.preprocessing \
  --input-dir data/synthetic \
  --output-dir data/processed
python -m src.scoring \
  --input-dir data/processed \
  --output-dir data/scored \
  --rolling-window 7
python -m src.analytics \
  --input-dir data/scored \
  --output-dir data/analytics
```

Open any `.html` file under `data/analytics/charts/` in a browser. The generated
data and chart files are intentionally ignored by Git.

Run the same verification used for this sprint:

```bash
python -m ruff check .
python -m compileall -q src tests
python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=90
```

## Test evidence

Dependency installation, Ruff linting, and Python compilation passed. All 70
tests passed with 93.50% total source coverage; `analytics.py` reached 98%.
Tests cover exact team counts and rates, ordered distributions, sorted daily
aggregates, symmetric correlation matrices, invalid files and values, accessible
chart encodings, all nine generated artifacts, and the CLI.

The seeded end-to-end smoke test generated 20 agents across 14 days: 20 agent
rows, 20 time-off rows, 8,805 calls, 8,805 transcripts, and 280 daily labels.
Cleaning preserved all 17,930 rows with 0 corrections and 0 relationship
warnings while reporting 327 outliers without deleting them. Scoring produced
280 feature rows and 20 current scores (13 Low and 7 Moderate, from 12.66 to
49.95). Analytics consumed every row and wrote four CSV tables, four standalone
HTML charts, and one manifest. All generated outputs remained excluded from Git.

## Decisions and tradeoffs

- Trends show observable features, not backfilled risk scores. PTO is only an
  end-of-period snapshot, so pretending it existed on every past date would be
  misleading.
- Correlations exclude target metadata and score components. This avoids target
  leakage and formula-driven patterns that can look more meaningful than they
  are.
- Team views are aggregate, but small synthetic teams may still be unstable.
  The charts are not rankings and must not support punitive action.
- Plotly HTML files are larger because the JavaScript is embedded. The benefit
  is a reproducible chart that works offline; generated files remain out of Git.
- The pipeline fails on invalid scored inputs instead of silently filling or
  dropping values. Data repair belongs in Sprint 2, where it is documented.

## Blockers

None. Sprint 4 uses only generated synthetic data and requires no private data,
external service, legal decision, or product-owner choice.

## What comes next

Sprint 5 builds a reproducible, leakage-aware experimental machine-learning
baseline. It will compare models with the transparent score, report
classification, calibration, and error evidence, and repeat the critical
warning: performance on generated labels is a software experiment, not
validation of real-world burnout prediction.
