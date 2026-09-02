# Sprint 1 Tutorial: Reproducible Synthetic Data

**Status:** Complete  
**Date:** 2026-09-02  
**Goal:** Turn the original script into a configurable data pipeline that
creates the same valid dataset whenever the same settings and seed are used.

## Why this sprint matters

A machine-learning or analytics project needs trustworthy input before it
needs a model. The original generator created useful tables, but it used global
random state, depended on the moving calendar value `today`, and did not verify
its output. It also had no explicit target for later model experiments.

Sprint 1 makes data generation a repeatable pipeline:

```text
configuration -> seeded generators -> five tables -> validation -> CSV files + manifest
```

The output is still completely fictional. No Kaggle or real employee dataset
was needed.

## What was built

### `GenerationConfig`: one source of truth

`GenerationConfig` is a frozen Python `dataclass`. A dataclass is a compact way
to group related values. The configuration stores:

- number of agents;
- simulation start date and number of days;
- random seed;
- output directory;
- fraction of agents receiving a sustained pressure trend; and
- probability of a temporary pressure event.

Its `__post_init__` method rejects impossible settings, such as zero agents or
a probability greater than 1. Freezing the object prevents settings from being
silently changed halfway through generation.

### Local random generators instead of global state

The pipeline creates `numpy.random.Generator` and Faker instances using the
configured seed. Those instances are passed into the generation functions.

A random seed does not remove randomness. It chooses the starting point in a
deterministic sequence. Seed 42 always produces the same sequence; seed 43
produces a different sequence.

Dates are now calculated from the configured simulation period instead of the
computer's current date. This means a run next month can still reproduce a run
from today.

### Sustained pressure trajectories

`generate_daily_labels()` selects the configured fraction of fictional agents
for gradual pressure growth. For every agent-day, it combines:

1. the agent's starting pressure;
2. an optional upward trend;
3. occasional temporary pressure events;
4. a small weekend recovery effect;
5. random noise; and
6. part of the previous day's value.

Keeping part of yesterday's value is smoothing. It prevents the hidden state
from jumping randomly between extremes and models the idea that sustained
conditions usually develop across several days.

The result becomes `daily_labels.csv`. Its `synthetic_stress_label` is 1 when
the hidden pressure is at least 0.65. That threshold is a simulation rule, not
a medical threshold.

### Observable calls respond to hidden pressure

`generate_calls_and_transcripts()` looks up each agent's pressure for a date.
Higher pressure tends to create more calls and shifts the beta distribution
used for call difficulty. Difficulty then affects duration, after-call work,
hold time, and the transcript sentiment template.

This gives the later feature and model code a signal to discover, while noise
keeps the relationship from being perfectly deterministic.

### Schema and relationship validation

`collect_validation_errors()` checks all problems it can find instead of
stopping at the first one. It checks:

- all five tables and required columns exist;
- tables are not empty and contain no missing values;
- primary identifiers are unique;
- call, transcript, agent, time-off, and label keys match;
- one label exists for every simulated agent-day;
- numeric values stay inside allowed ranges;
- categories use allowed values; and
- date values can be parsed.

`validate_generated_data()` turns the error list into one readable
`DataValidationError`. The pipeline validates before writing anything, and
`write_dataset()` validates again at its boundary. This is defense in depth:
bad data should not quietly become an input to the next sprint.

### Command-line interface

`argparse` converts terminal options into Python values. Run:

```bash
python -m src.data_generator --help
```

Example custom run:

```bash
python -m src.data_generator \
  --num-agents 10 \
  --start-date 2026-04-01 \
  --num-days 14 \
  --seed 123 \
  --output-dir data/synthetic \
  --at-risk-fraction 0.25 \
  --pressure-event-probability 0.10
```

`python -m` runs the module as part of the `src` package. The backslashes mean
the macOS/Linux command continues on the next line. On Windows PowerShell, use
a backtick or put the command on one line.

### Generation manifest

`generation_manifest.json` records the schema version, synthetic-only flag,
configuration, filenames, and row counts. This answers an important data-
engineering question: “Exactly how was this dataset made?”

The manifest intentionally has no current timestamp. A timestamp would change
between otherwise identical runs and weaken byte-for-byte reproducibility.

## Files changed

- `src/data_generator.py`: configuration, pressure simulation, CLI, validation,
  writing, and manifest creation
- `tests/test_data_generator.py`: reproducibility, validation, CLI, pressure,
  relationships, configuration, and output tests
- `docs/data_dictionary.md`: every table, column, range, and relationship
- `docs/architecture.md`: pressure flow and leakage boundary
- `README.md`: current status and CLI instructions
- `SPRINT_LOG.md`: results and next step
- `docs/sprints/sprint-01-synthetic-data.md`: this walkthrough

## Follow along as a beginner

### 1. Install the project

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Windows PowerShell activation is `.venv\Scripts\Activate.ps1`.

### 2. Read the configuration class

Open `src/data_generator.py` and find `GenerationConfig`. Notice that defaults
make the simplest command work, while validation prevents invalid runs.

### 3. Trace one table through the pipeline

Start at `generate_dataset()`. Follow the `agents` variable from
`generate_agents()` into `generate_timeoff()`, `generate_daily_labels()`, and
`generate_calls_and_transcripts()`. The same `agent_id` is the thread connecting
those tables.

### 4. Create a tiny dataset

```bash
python -m src.data_generator --num-agents 2 --num-days 3 --output-dir data/tiny
```

Open the CSV files. You should see 2 agent rows, 2 time-off rows, 6 daily-label
rows, and a variable number of calls with the same number of transcripts.

### 5. Prove reproducibility

Run the same command twice with the same seed. The files will be the same.
Change `--seed 42` to `--seed 43`; the names and measurements will change while
the columns and relationships remain valid.

### 6. Run the tests

```bash
python -m ruff check src tests
python -m compileall -q src tests
python -m pytest --cov=src --cov-report=term-missing
```

Read the test named `test_validation_reports_an_orphan_call`. It deliberately
changes one call to an agent ID that does not exist. A good validator must
reject that broken relationship.

## Verification evidence

- Ruff: all checks passed.
- Python compilation: passed.
- Pytest: 16 tests passed.
- Source coverage: 90%.
- Default end-to-end generation and validation: passed.
- Default row counts: 50 agents, 50 time-off rows, 51,322 calls, 51,322
  transcripts, and 1,500 agent-day labels.
- Pressure bands: 1,204 Low, 274 Elevated, and 22 High.
- Synthetic positive labels: 22.
- Generated data, manifests, caches, and environments remained outside Git.

## Decisions and tradeoffs

- A fifth label table was added instead of hiding the research target in an
  operational table. This makes its synthetic status and leakage risk explicit.
- Pressure is smoothed across days to represent persistence without building a
  complicated time-series model too early.
- Validation uses pandas and readable functions instead of introducing a schema
  framework. Sprint 2 can evaluate stricter input boundaries separately.
- Versioned source plus a manifest is committed; generated CSV files are not.
- Kaggle was intentionally skipped because Sprint 1 needed controlled labels
  and privacy-safe relationships, not an unrelated dataset with uncertain fit.

## Blockers

None. No credentials, real data, licensing choice, or product-owner decision was
needed.

## Next sprint

Sprint 2 will treat CSV files as untrusted external inputs. It will add loaders,
type coercion, missing-value policy, duplicate and orphan detection, nonrecursive
IQR outlier reporting, cleaned outputs, a machine-readable quality report, and
tests using both valid and intentionally damaged fixtures.
