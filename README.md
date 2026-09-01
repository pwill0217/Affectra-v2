# Affectra

Affectra is a standalone Python data product that analyzes customer-service
workload, call behavior, recovery patterns, and tone indicators to surface
possible signs of sustained stress or burnout.

The project is designed as decision support for managers and wellness teams.
It is **not** a medical diagnosis, an employee-performance score, or a reason
to take punitive action. Any alert should start a supportive human review.

## Current status

Sprint 0 is complete. The project foundation, requirements, architecture,
roadmap, automated tests, and beginner documentation are now in place. The
original synthetic-data generator has been preserved and is the starting point
for Sprint 1.

See [SPRINT_LOG.md](SPRINT_LOG.md) for completed work and
[docs/SPRINT_ROADMAP.md](docs/SPRINT_ROADMAP.md) for what comes next.

## Data model

The initial synthetic dataset contains four related tables:

- `agents.csv`: agent details and personal workload baselines
- `calls.csv`: duration, after-call work, hold time, and transfers
- `transcripts.csv`: synthetic call text and sentiment indicators
- `timeoff.csv`: PTO balance, recent PTO usage, and recovery indicators

Generated data is intentionally excluded from Git. Anyone can recreate it
from the source code.

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

Generate sample data and run the tests:

```bash
python -m src.data_generator
python -m pytest
```

The generated CSV files will appear in `data/synthetic/`.

## Learning path

Each sprint has a tutorial in `docs/sprints/`. Start with
[Sprint 0: Foundation](docs/sprints/sprint-00-foundation.md), then follow the
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
