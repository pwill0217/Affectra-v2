# Affectra

Affectra is a standalone Python data product that analyzes customer-service
workload, call behavior, recovery patterns, and tone indicators to surface
possible signs of sustained stress or burnout.

The project is designed as decision support for managers and wellness teams.
It is **not** a medical diagnosis, an employee-performance score, or a reason
to take punitive action. Any alert should start a supportive human review.

## Current status

Sprints 0 through 8 are complete. Affectra 1.0 now provides one tested path from
reproducible synthetic data through cleaning, feature engineering, transparent
scoring, analytics, experimental model evaluation, a four-page Streamlit
dashboard, privacy-minimized persistence, and operational health evidence. The
release command verifies every stage and writes a machine-readable artifact
receipt. GitHub Actions repeats linting, compilation, coverage, and the complete
synthetic release smoke test on every push and pull request.

This is a **local, synthetic-data portfolio release**, not a production employee
monitoring system. Its scores and model metrics demonstrate software behavior;
they do not validate burnout prediction, diagnosis, causality, or employment use.
Do not load real employee/customer data or expose the local dashboard publicly.

See [SPRINT_LOG.md](SPRINT_LOG.md) for exact sprint evidence,
[the completion matrix](docs/completion_matrix.md) for requirement coverage,
[the release guide](docs/release_guide.md) for deployment and maintenance, and
[the pilot requirements](docs/pilot_requirements.md) for the human decisions and
controls required before any real-world evaluation.

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

Install the project and verify the fresh environment:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pip check
python -m ruff check .
python -m compileall -q src tests
python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=90
```

Run the complete generated-data-to-dashboard-and-operations demonstration with
one command:

```bash
python -m src.release
```

The command deliberately refuses to mix with a non-empty destination. For a
second run, supply a new `--output-root` and unique `--run-version`. Read
`data/release-demo/release_manifest.json` for the exact configuration, row
counts, checks, dashboard pages, and 36 verified artifacts.

Launch the dashboard against those release outputs:

```bash
export AFFECTRA_SCORED_DIR=data/release-demo/scored
export AFFECTRA_PROCESSED_DIR=data/release-demo/processed
export AFFECTRA_MODELS_DIR=data/release-demo/models
python -m streamlit run src/app.py
```

Open the local URL printed by Streamlit. See the
[release guide](docs/release_guide.md) for PowerShell commands, a five-minute
demo script, manual stage-by-stage commands, maintenance, recovery, and
troubleshooting. The [dashboard guide](docs/dashboard.md) explains every page.

Within the default self-contained release, raw generated CSV files appear in
`data/release-demo/synthetic/`. Cleaned CSV files and
`data_quality_report.json` appear in `data/release-demo/processed/`. All release
outputs are generated locally and excluded from Git.

`data/release-demo/scored/` contains:

- `agent_day_features.csv`: daily and rolling observable features;
- `risk_scores.csv`: the latest explainable score for each agent; and
- `scoring_manifest.json`: weights, thresholds, row counts, source quality, and
  responsible-use limitations.

`data/release-demo/analytics/` contains four aggregate CSV tables, an analytics
manifest, and four standalone HTML charts. Open a file in its `charts/`
directory to explore it without starting a server. See the
[analytics guide](docs/analytics.md) for definitions and interpretation limits.

`data/release-demo/models/` contains generated model pipelines, held-out
predictions, calibration and synthetic-team error tables, `evaluation.json`, and
a reproducibility manifest. Model artifacts are intentionally excluded from Git.
The research label is rare, so the release demonstration uses 30 agents and an
at-risk fraction of 0.5. See the
[modeling guide](docs/modeling.md) before interpreting any metric.

`data/release-demo/affectra.db` contains privacy-minimized, versioned run
evidence, while `data/release-demo/operations/` contains the generated monitoring
baseline and latest health report. These are local artifacts excluded from Git.
Use a new run version for every completed pipeline run. See the
[operations guide](docs/operations.md) and
[privacy/security design](docs/privacy_security.md) before using this layer.

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
[Sprint 6: Streamlit Dashboard](docs/sprints/sprint-06-streamlit-dashboard.md)
and [Sprint 7: Operations](docs/sprints/sprint-07-operations.md), then finish with
[Sprint 8: Release Handoff](docs/sprints/sprint-08-release-handoff.md). Every
tutorial explains the goal, files changed, commands to run, concepts learned,
verification steps, decisions, and blockers.

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
