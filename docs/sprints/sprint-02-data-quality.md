# Sprint 2 Tutorial: Ingestion, Cleaning, and Data Quality

**Status:** Complete  
**Date:** 2026-09-03  
**Goal:** Turn five CSV files into typed, internally consistent tables while
recording every repair, warning, and preserved outlier in a JSON report.

## Why this sprint matters

Sprint 1 can generate perfect synthetic inputs, but a useful data product must
not assume every future file is perfect. A missing column, the text `unknown`
in a number field, or a call linked to an agent who does not exist can otherwise
produce a believable but wrong score.

Sprint 2 creates a boundary between raw input and later analysis:

```text
five raw CSVs
    -> file and schema checks
    -> type conversion and cleaning
    -> cross-table relationship repair
    -> one-pass outlier detection
    -> five cleaned CSVs + data_quality_report.json
```

The sprint uses only generated synthetic data and deliberately damaged test
copies. It does not need Kaggle or real employee data.

## Starting state

At the end of Sprint 1, `src/data_generator.py` created and validated:

- fictional agents and personal baselines;
- one time-off snapshot per agent;
- calls and one-to-one synthetic transcripts;
- daily hidden pressure states and research-only labels; and
- a generation manifest that makes a run reproducible.

That validation protects data made by Affectra. This sprint adds an independent
boundary for data arriving from CSV files.

## What was built

### 1. Defensive loading in `src/data_loader.py`

`find_input_files()` constructs the expected path for each table. If the input
directory is missing, is actually a file, or lacks CSVs, it raises
`DataLoadError` with the affected paths. It reports all missing files together
so a beginner does not have to fix and rerun five times.

`load_raw_tables()` reads every column with `dtype=object`. An object is a
general Python/pandas value. This is intentional: the loader does not silently
decide that one column is a number while reading it. The cleaning stage can
then count every conversion failure.

Pandas recognizes its normal missing values plus `?`, `-`, and `N/A`.
`validate_required_columns()` checks all required tables and columns while
allowing extra columns. Extra data is preserved and named in the report.

### 2. Explicit rules in `src/preprocessing.py`

The constants near the top group columns by their intended type and rule:

- `DATE_COLUMNS`, `INTEGER_COLUMNS`, `FLOAT_COLUMNS`, `TEXT_COLUMNS`, and
  `BOOLEAN_COLUMNS` control conversion;
- `PRIMARY_KEYS` and `SECONDARY_UNIQUE_KEYS` control uniqueness;
- `CRITICAL_COLUMNS` lists values that must not be guessed;
- `NUMERIC_BOUNDS` and `ALLOWED_VALUES` define valid values; and
- `OUTLIER_COLUMNS` chooses measurements for statistical review.

Keeping these rules together makes the policy reviewable. A future schema
change should update the constants, tests, data dictionary, and report version.

### 3. Type conversion without recursion

`_coerce_types()` loops once through the documented columns. `pd.to_numeric()`
parses integers and decimals, while `pd.to_datetime(..., format="ISO8601")`
parses dates consistently. Invalid values become missing values and are counted
under `invalid_values_coerced`.

Boolean values accept common forms such as `true`, `false`, `1`, `0`, `yes`,
and `no`. Anything else becomes missing and follows the documented missing-
value policy.

There are no recursive function calls. Recursion means a function calls itself.
It is useful for tree-shaped problems, but simple table conversion is clearer
and safer as finite loops.

### 4. Missing and invalid values

`_replace_invalid_ranges()` converts impossible measurements or categories to
missing values. `_drop_missing_critical_rows()` then drops a row when a critical
key, key date, or research target is unavailable. Guessing those values could
connect a call to the wrong person or train against a made-up answer.

`_impute_known_values()` repairs recoverable fields:

- non-key numbers use the column median;
- text and booleans use the mode, or a documented fallback if no known values
  exist; and
- noncritical dates use the median known date when one exists.

Imputation means filling a missing value using a reproducible rule. It does not
recover the true unknown value, so the report always records the count, method,
and fill value.

### 5. Duplicates and relationships

`_drop_duplicate_keys()` first removes byte-for-byte duplicate rows, then keeps
the first row for a repeated business key. This order distinguishes exact
copies from conflicting rows that reuse an identifier.

`_drop_orphans()` checks relationships after every table is typed and cleaned:

- time-off, call, and daily-label rows must reference an existing agent;
- a call and transcript must share the exact `(call_id, transcript_id)` pair;
- missing agent-day labels are counted; and
- agents without time-off records are counted.

Bad child rows are removed. Parent rows are preserved because deleting an agent
could cascade into the loss of many otherwise usable calls.

### 6. Non-destructive IQR outlier reporting

`iqr_outlier_summary()` calculates the first quartile (`Q1`), third quartile
(`Q3`), and interquartile range (`IQR = Q3 - Q1`). With the default multiplier:

```text
lower bound = Q1 - 1.5 × IQR
upper bound = Q3 + 1.5 × IQR
```

The function counts values outside the bounds and records their percentage. It
does not change the DataFrame. It also runs only once; deleting extremes and
recalculating repeatedly can eventually label ordinary observations as
outliers.

Preserving extremes is especially important here. A long call or unusually
high after-call work could be valid workload information. IQR is a statistical
flag, not proof that a value is wrong.

### 7. Outputs and the quality report

`preprocess_tables()` coordinates in-memory cleaning and builds the report.
`write_processed_outputs()` writes the five cleaned CSVs and formatted JSON.
`run_preprocessing()` joins loading, cleaning, and writing for the CLI.

The report contains:

- versions and input/output locations;
- the policy applied during the run;
- per-table row counts and quality actions;
- cross-table relationship results; and
- totals for corrections, outliers, and relationship warnings.

`passed_with_warnings` does not mean the pipeline failed. It means the data was
usable but at least one action or review flag was recorded. The clean smoke
test, for example, made no corrections but reported natural IQR extremes.

## Files and functions changed

- `src/data_loader.py`: `find_input_files()`,
  `validate_required_columns()`, and `load_raw_tables()`
- `src/preprocessing.py`: configuration, coercion, range rules, missing-value
  handling, duplicate and relationship checks, outlier reporting, writing,
  orchestration, and CLI
- `tests/test_data_loader.py`: valid loading, missing paths/files/columns,
  missing markers, and extra columns
- `tests/test_preprocessing.py`: valid pipeline, deliberately broken fixtures,
  IQR preservation, invalid settings, unusable output, and CLI smoke behavior
- `docs/data_quality.md`: the operator-facing policy and report guide
- `docs/architecture.md`: the implemented ingestion and cleaning boundary
- `README.md`: new commands and current status
- `SPRINT_LOG.md` and `docs/SPRINT_ROADMAP.md`: completion evidence and next work
- `docs/sprints/sprint-02-data-quality.md`: this tutorial

## Follow along as a complete beginner

### 1. Prepare Python

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

### 2. Generate a small synthetic input

```bash
python -m src.data_generator \
  --num-agents 5 \
  --start-date 2026-06-01 \
  --num-days 7 \
  --seed 42 \
  --output-dir data/tutorial-raw
```

Open `data/tutorial-raw/agents.csv`. The first line contains column names; every
later line is one row. Follow an `agent_id` into `calls.csv` and `timeoff.csv`,
then follow one call's two identifiers into `transcripts.csv`.

### 3. Run preprocessing

```bash
python -m src.preprocessing \
  --input-dir data/tutorial-raw \
  --output-dir data/tutorial-processed
```

The terminal prints cleaned row counts, status, correction count, outlier count,
and the report path. Source CSVs in `data/tutorial-raw` remain unchanged.

### 4. Read the report from the outside inward

Open `data/tutorial-processed/data_quality_report.json` and read:

1. `status` for the high-level result;
2. `totals` for a small summary;
3. `relationships` for cross-table integrity;
4. `tables.agents` for one detailed example; and
5. `policy` to see exactly what the program did.

JSON is a text format made of objects (`{}`), lists (`[]`), names, and values.
Python dictionaries become JSON objects when the report is written.

### 5. Trace one bad value through the code

Read `test_broken_fixture_is_cleaned_and_each_problem_is_reported` in
`tests/test_preprocessing.py`. It changes a baseline number to
`not-a-number`. Follow this path:

```text
_coerce_types
    -> failed conversion becomes missing
_replace_invalid_ranges
    -> range rules run on the typed column
_drop_missing_critical_rows
    -> row stays because this field is not a key
_impute_known_values
    -> missing number receives the median
quality report
    -> conversion and imputation are both visible
```

The test also injects duplicate keys, invalid ranges, orphan agents, a broken
call/transcript pair, and an invalid research label.

### 6. Run the verification commands

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m ruff check src tests
python -m compileall -q src tests
python -m pytest -q --cov=src --cov-report=term-missing
```

- Ruff checks common Python mistakes and style rules.
- `compileall` proves each Python file has valid syntax.
- Pytest runs the behaviors described by test functions.
- Coverage measures which source statements the tests executed. High coverage
  is useful evidence, but it is not proof that no bugs exist.

## Verification evidence

- Dependency installation from both requirement files: passed.
- Ruff: all checks passed.
- Python compilation: passed.
- Pytest: 28 tests passed with no warnings.
- Total source coverage: 91%.
- `src/data_loader.py` coverage: 86%.
- `src/preprocessing.py` coverage: 93%.
- End-to-end smoke test: generated, loaded, cleaned, and reported successfully.
- Smoke input: 8 agents, 8 time-off rows, 1,530 calls, 1,530 one-to-one
  transcripts, and 40 daily labels across 5 days (3,116 total rows).
- Smoke output: all 3,116 rows preserved, 0 corrections, 0 relationship
  warnings, and 63 IQR outliers reported without deletion.
- Generated datasets, reports, caches, environments, and model artifacts
  remained outside Git.

## Decisions and tradeoffs

- Required columns are strict, but extra columns are allowed and reported. This
  catches broken contracts without discarding potentially useful source data.
- Critical keys are never imputed. Losing a bad row is safer than silently
  attaching it to the wrong agent, call, date, or target.
- Median and mode imputation are simple and explainable. They can compress
  variation, so every use is visible and later monitoring can set thresholds.
- Duplicate conflicts keep the first row. This is deterministic, but a real
  source system should eventually provide timestamps or precedence rules.
- Orphan child rows are dropped instead of deleting their parent population.
- Outliers remain in the data because unusual workload can be meaningful.
- A JSON report supports programs and dashboards; the tutorial and policy make
  the same information understandable to a person.
- Synthetic fixtures remain preferable at this stage. They exercise every rule
  without privacy, consent, licensing, or employment-policy risk.

## Responsible-use boundary

This sprint validates table structure and data mechanics. It does not validate
whether any metric represents burnout, does not make a medical diagnosis, and
does not justify employment action. Synthetic model performance later in the
roadmap will not establish real-world validity.

## Blockers

None. No credentials, private data, license choice, legal policy, or ambiguous
product decision was required.

## Next sprint

Sprint 3 will transform clean calls, transcripts, time-off values, and personal
baselines into daily and rolling agent features. It will implement the visible
40% workload, 20% efficiency-friction, 25% tone/sentiment, and 15% recovery/
context score, validate custom weights, bound every score, assign readable risk
levels, and explain which components affected each result.
