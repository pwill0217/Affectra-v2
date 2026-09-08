# Sprint 7 tutorial: persistence, privacy, security, and monitoring

## Goal

This sprint adds the operational guardrails around Affectra's generated
pipeline. A completed run can now be saved to a local database with a unique
version, checked against an explicit health baseline, and logged without
copying sensitive content into error records.

The important lesson is that “works on my machine” is not the end of a data
product. Operations also needs provenance, safe failure behavior, privacy
boundaries, health evidence, maintenance instructions, and an honest list of
controls that are still required before real use.

## Starting state

Sprint 6 connected generated score, feature, quality, and model-evaluation
files in a four-page Streamlit dashboard. Outputs were reproducible and
validated, but each run existed only as generated files. There was no database
record, monitoring baseline, structured operational logger, role/access design,
retention guidance, or threat analysis.

Sprint 7 preserves the synthetic-only boundary. It does not add a production
login, remote database, live integration, or real employee data.

## Files and functions changed

### `src/database.py`

This module defines three SQLAlchemy tables:

- `PipelineRun` stores an immutable run version, UTC creation time, quality
  status, row counts, source fingerprint, and best experimental baseline name.
- `PersistedScore` stores only agent ID, date, numeric score/components, and
  review level.
- `ModelMetadata` stores model-level evaluation JSON.

`create_local_engine()` accepts SQLite only, rejects URLs with credentials or a
host, and creates the database's parent directory. `initialize_database()` uses
SQLAlchemy's safe `create_all(..., checkfirst=True)` behavior; it never drops
tables. `persist_run()` validates every input and writes one run in a single
transaction. Duplicate run versions fail instead of replacing history.

The code selects an explicit score-column allow-list before persistence. Names,
teams, roles, explanation text, transcripts, raw calls, and held-out predictions
cannot enter the table accidentally just because a CSV gained a new column.

### `src/monitoring.py`

- `schema_indicators()` records required/extra columns and a SHA-256 fingerprint
  for the complete feature and score schemas.
- `score_distribution()` calculates identity-free count, mean, standard
  deviation, quartiles, extrema, and review-level proportions.
- `compare_with_baseline()` flags schema change, mean-score shift, and review-
  level proportion shift using visible thresholds.
- `build_health_report()` checks data quality, score range/uniqueness, required
  schemas, and zero agent overlap in model evaluation.
- `write_json_safely()` writes a temporary neighbor before an atomic replacement.

Creating the first baseline requires `--initialize-baseline`. This prevents a
missing file from silently making the latest run the definition of normal.

### `src/operations.py`

`OperationsConfig` holds all paths, thresholds, database URL, and run version.
`run_operations()` loads the same validated contract as the dashboard, builds
health evidence, persists the minimized snapshot, and writes JSON outputs.

`PrivacyJsonFormatter` emits JSON logs containing only timestamp, level, event,
component, row count, run version, and status. A failed command records the
exception class—not its potentially sensitive message. Settings come from CLI
arguments and `AFFECTRA_DATABASE_URL` / `AFFECTRA_LOG_LEVEL` environment
variables.

### Tests and documentation

- `tests/test_database.py` covers safe initialization, minimized fields,
  transactions, duplicates, validation, and unsafe URLs.
- `tests/test_monitoring.py` covers schema fingerprints, aggregate statistics,
  baseline creation/comparison, all drift alerts, thresholds, and atomic JSON.
- `tests/test_operations.py` covers allow-listed logs, failure redaction,
  orchestration, persistence, outputs, environment settings, and CLI behavior.
- `.env.example` documents non-secret local defaults.
- `docs/operations.md` provides run, monitoring, recovery, and maintenance steps.
- `docs/privacy_security.md` provides data minimization, role/access targets,
  retention decision guidance, a threat table, and residual limitations.

## Beginner concepts

### Database schema and ORM

A database schema defines tables, columns, keys, and relationships. SQLAlchemy's
ORM maps Python classes to those tables. Creating a `PipelineRun` object and
adding it to a session becomes an SQL insert; querying the class becomes a
select. The code still controls exactly which columns exist and which values are
copied into them.

### Transactions

A transaction groups multiple database changes into one unit. Sprint 7 inserts
the run, its score snapshots, and all model summaries inside one transaction. If
one insert fails, SQLAlchemy rolls the group back. This avoids a half-written
run that looks complete.

### Immutable versions

Changing historical evidence in place makes audits and debugging difficult.
`run_version` is unique, and duplicate insertion raises an error. A later
pipeline execution gets a new version. “Immutable” here means the application
does not expose an overwrite path; operating-system access to a local SQLite
file still needs protection.

### Schema drift and distribution drift

Schema drift means a table's columns changed. That might be a planned new
feature or a broken upstream contract. Distribution drift means aggregate values
changed—for example, average scores or the proportion in each review level.
Neither kind of drift proves a model is wrong or a person's health changed. It
only tells an operator what deserves investigation.

### Secrets and configuration

Configuration such as a local file location is not necessarily secret. Tokens,
passwords, private employee exports, and connection credentials are secrets or
sensitive data. They belong in an approved environment/vault, never committed
source. `.env.example` contains names and safe defaults only; `.env` remains
ignored.

### Threat modeling

A threat model asks what must be protected, who or what could cause harm, how it
could happen, what controls exist, and what risk remains. The Sprint 7 table
covers leaks, unauthorized access, device theft, re-identification, tampering,
unsafe serialized models, misuse, bias, drift, and availability.

## How data flows

```text
complete generated pipeline outputs
                |
                v
     dashboard contract validation
                |
        +-------+--------+
        |                |
        v                v
 schema/pipeline/    explicit score-
 distribution       distribution baseline
 indicators               |
        |                  |
        +--------+---------+
                 v
        health_report.json

validated current scores + quality/model manifests
                 |
      explicit persistence allow-list
                 |
                 v
 one SQL transaction: run + minimized scores + model metrics
                 |
                 v
        local affectra.db
```

The database, monitoring files, and any redirected logs are generated artifacts
and remain outside Git.

## Reproduce the work

Create and activate Python 3.12, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Generate the stable demonstration used in this sprint:

```bash
python -m src.data_generator \
  --num-agents 30 \
  --start-date 2026-08-01 \
  --num-days 30 \
  --seed 707 \
  --at-risk-fraction 0.5
python -m src.preprocessing
python -m src.scoring
python -m src.analytics
python -m src.model_training
```

Create and inspect the first operational baseline:

```bash
python -m src.operations \
  --run-version sprint-7-demo-707 \
  --initialize-baseline
```

After a later pipeline run, compare it with a new immutable version:

```bash
python -m src.operations --run-version sprint-7-demo-next
```

Run verification:

```bash
python -m ruff check .
python -m compileall -q src tests
python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=90
```

## Test and smoke evidence

Dependency installation, Ruff linting, Python compilation, and diff checks
passed. All 134 tests passed in 14.28 seconds with 94.98% total source coverage.
`database.py` reached 100%, `monitoring.py` 99%, and `operations.py` 99%.

The end-to-end smoke test used seed 707, 30 synthetic agents, 30 days, and a 0.5
synthetic at-risk fraction. It generated 31,388 calls, 31,388 transcripts, and
900 labels. Cleaning preserved all 63,736 input rows with zero corrections and
zero relationship warnings while reporting 1,199 non-destructive outliers.
Scoring created 900 feature rows and 30 current scores: 13 Low and 17 Moderate.
Analytics wrote all nine expected artifacts, and all four Streamlit pages
rendered with zero exceptions.

The model experiment held out complete agents: 660 rows from 22 training agents
and 240 rows from 8 test agents, with zero overlap. Test labels contained 237
negatives and 3 positives. The dummy prior ranked highest by balanced accuracy
only because all evaluated baselines tied at 0.5 for this generated seed. Its
98.75% accuracy but zero precision, recall, and F1 demonstrates why rare-class
accuracy cannot be interpreted alone. This is software evidence, not real-world
burnout validation.

The first operations run created a healthy baseline with all five health checks
true and no alerts. SQLite contained one run, 30 minimized score rows, and three
model summaries. A second uniquely versioned run compared with the existing
baseline, remained healthy, produced no alerts, and brought the counts to two
runs, 60 score rows, and six model summaries. Inspection confirmed that the
score table contains only run ID, agent ID, date, risk score/level, and the four
numeric components.

## Decisions and tradeoffs

- SQLite provides a portable local demonstration. It is deliberately rejected
  as a remote credentialed connection and is not called production storage.
- Individual IDs are retained so runs can be traced locally, but all direct
  identity and free text are removed. A real pilot still needs pseudonymization.
- Run versions are supplied by the operator instead of inferred from time. This
  makes the meaningful version explicit and avoids silent overwrites.
- Monitoring uses readable absolute thresholds. They are review aids, not
  statistically validated control limits.
- The baseline is explicit and generated, not committed. Different demo data
  should not inherit another machine's definition of normal.
- Production role enforcement and retention periods are documented but not
  faked inside a local unauthenticated app. Those require governance decisions
  and proper infrastructure before real data.
- Failure logs sacrifice detailed messages for privacy. Operators use the
  exception type and reproduce the failure in an appropriately controlled
  debugging environment.

## Blockers

None for the synthetic portfolio release. No real/private employee data,
credentials, legal policy decision, or destructive repository action was
required.

Real-world deployment remains intentionally out of scope. It would require the
human governance, retention, identity, access, validity, bias, consent/notice,
and incident-response decisions listed in `docs/privacy_security.md`.

## What comes next

Sprint 8 performs release hardening from a fresh setup, fixes integration or
duplicate-code issues, documents deployment/maintenance/demo workflows, creates
a final completion matrix, and identifies the exact requirements for a governed
real-world pilot.
