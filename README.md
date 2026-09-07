# Affectra

Affectra is a standalone Python data product that analyzes customer-service
workload, call behavior, recovery patterns, and tone indicators to surface
possible signs of sustained stress or burnout.

The project is designed as decision support for managers and wellness teams.
It is **not** a medical diagnosis, an employee-performance score, or a reason
to take punitive action. Any alert should start a supportive human review.

## Current status

Sprints 0 through 6 are complete. Affectra now generates and cleans reproducible
synthetic data, builds daily and rolling agent features, compares current
behavior with each agent's personal baseline, and produces a transparent
0-to-100 decision-support score. Every result exposes its four component scores,
weighted contributions, evidence, and plain-language explanation. It also creates
team summaries, time trends, feature correlations, and four accessible standalone
charts. A separate leakage-aware experiment trains dummy, logistic-regression,
and random-forest baselines with agent-disjoint evaluation. An interactive
Streamlit dashboard now connects overview, agent-detail, data-quality, and model-
evaluation pages. Sprint 7 will add persistence, privacy/security guidance, and
monitoring.

See [SPRINT_LOG.md](SPRINT_LOG.md) for completed work and
[docs/SPRINT_ROADMAP.md](docs/SPRINT_ROADMAP.md) for what comes next.

## Data model

The synthetic dataset contains five related tables and a manifest:

- `agents.csv`: agent details and personal workload baselines
- `calls.csv`: duration, after-call work, hold time, and transfers
- `transcripts.csv`: synthetic call text and sentiment indicators
- `timeoff.csv`: PTO balance, recent PTO usage, and recovery indicators
- `daily_labels.csv`: hidden simulated pressure trajectories and research-only
  labels for later model experiments
- `generation_manifest.json`: the exact settings, filenames, and row counts for
  the run

Generated data is intentionally excluded from Git. Anyone can recreate it
from the source code. See [the data dictionary](docs/data_dictionary.md) for
column definitions and relationships.

## Quick start

You need Python 3.12 or newer.

```bash
git clone https://github.com/pwill0217/Affectra-v2.git
cd Affectra-v2
python -m venv .venv
```

Activate the environment on macOS or Linux:

```bash
source .venv/bin/activate
```

Activate it on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install the project:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Generate sample data, clean it, score the latest agent snapshots, build the
analytics, train the synthetic-label baselines, and run the tests:

```bash
python -m src.data_generator
python -m src.preprocessing
python -m src.scoring
python -m src.analytics
python -m src.model_training
python -m pytest
```

Launch the dashboard after the generated outputs exist:

```bash
python -m streamlit run src/app.py
```

Open the local URL printed by Streamlit. See the
[dashboard guide](docs/dashboard.md) for page behavior, filters, alternate data
paths, and troubleshooting.

Raw generated CSV files appear in `data/synthetic/`. Cleaned CSV files and
`data_quality_report.json` appear in `data/processed/`. Both directories are
generated locally and excluded from Git.

`data/scored/` contains:

- `agent_day_features.csv`: daily and rolling observable features;
- `risk_scores.csv`: the latest explainable score for each agent; and
- `scoring_manifest.json`: weights, thresholds, row counts, source quality, and
  responsible-use limitations.

`data/analytics/` contains four aggregate CSV tables, an analytics manifest, and
four standalone HTML charts. Open a file in `data/analytics/charts/` in a browser
to explore it without starting a server. See the
[analytics guide](docs/analytics.md) for definitions and interpretation limits.

`models/` contains generated model pipelines, held-out predictions, calibration
and synthetic-team error tables, `evaluation.json`, and a reproducibility
manifest. Model artifacts are intentionally excluded from Git. The default
research label is rare, so for a stable demonstration generate at least 30
agents and use `--at-risk-fraction 0.5`. See the
[modeling guide](docs/modeling.md) before interpreting any metric.

Use command-line options to create a smaller or different reproducible run:

```bash
python -m src.data_generator \
  --num-agents 10 \
  --start-date 2026-04-01 \
  --num-days 14 \
  --seed 123 \
  --output-dir data/synthetic
```

Run `python -m src.data_generator --help` to see every setting. Reusing the
same settings and seed produces the same tables. A different seed produces a
different, but still structurally valid, synthetic population.

Process a custom input directory without changing the source files:

```bash
python -m src.preprocessing \
  --input-dir data/synthetic \
  --output-dir data/processed \
  --iqr-multiplier 1.5
```

The loader expects all five CSV files documented in the
[data dictionary](docs/data_dictionary.md). See the
[data-quality policy](docs/data_quality.md) before using non-generated input.

## Learning path

Each sprint has a tutorial in `docs/sprints/`. Start with
[Sprint 0: Foundation](docs/sprints/sprint-00-foundation.md), continue to
[Sprint 1: Synthetic Data](docs/sprints/sprint-01-synthetic-data.md), and then
[Sprint 2: Data Quality](docs/sprints/sprint-02-data-quality.md) and
[Sprint 3: Explainable Scoring](docs/sprints/sprint-03-explainable-scoring.md),
followed by [Sprint 4: Analytics and Visualizations](docs/sprints/sprint-04-analytics-visualizations.md)
and [Sprint 5: Experimental ML](docs/sprints/sprint-05-experimental-ml.md), then
[Sprint 6: Streamlit Dashboard](docs/sprints/sprint-06-streamlit-dashboard.md).
Follow the roadmap in order. Every tutorial explains the goal, files changed,
commands to run, concepts learned, verification steps, and blockers.

## Core scoring plan

The transparent score uses the agreed categories:

- Workload: 40%
- Efficiency friction: 20%
- Tone and sentiment: 25%
- Recovery and other context: 15%

The weights are configurable and visible, must be finite and nonnegative, and
must sum to 1.0. See [the scoring methodology](docs/scoring.md) for feature
definitions, normalization ranges, risk levels, and limitations. The experimental
machine-learning models are evaluated separately and do not silently replace the
explainable score. Synthetic-label performance demonstrates the pipeline only;
it does not validate real-world burnout prediction.
