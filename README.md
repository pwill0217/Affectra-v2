# Affectra

Affectra is a standalone Python data product that analyzes customer-service
workload, call behavior, recovery patterns, and tone indicators to surface
possible signs of sustained stress or burnout.

The project is designed as decision support for managers and wellness teams.
It is **not** a medical diagnosis, an employee-performance score, or a reason
to take punitive action. Any alert should start a supportive human review.

## Current status

Sprints 0 through 2 are complete. Affectra now has a configurable, reproducible
synthetic-data pipeline plus an independent ingestion and cleaning boundary.
It validates files, schemas, types, ranges, duplicates, and relationships;
writes cleaned tables; and records every data-quality action and statistical
outlier in a JSON report. Sprint 3 will build agent-day metrics and the first
transparent stress-risk score.

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

Generate sample data, clean it, and run the tests:

```bash
python -m src.data_generator
python -m src.preprocessing
python -m pytest
```

Raw generated CSV files appear in `data/synthetic/`. Cleaned CSV files and
`data_quality_report.json` appear in `data/processed/`. Both directories are
generated locally and excluded from Git.

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
[Sprint 2: Data Quality](docs/sprints/sprint-02-data-quality.md). Follow the
roadmap in order. Every tutorial explains the goal, files changed, commands to
run, concepts learned, verification steps, and blockers.

## Core scoring plan

The first transparent risk score will use the agreed categories:

- Workload: 40%
- Efficiency friction: 20%
- Tone and sentiment: 25%
- Recovery and other context: 15%

The weights will remain configurable and visible to users. A later machine-
learning model will be evaluated separately and will not silently replace the
explainable score.
