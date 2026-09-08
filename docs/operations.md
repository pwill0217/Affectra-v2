# Local operations guide

## What Sprint 7 adds

The operations command turns a completed generated pipeline run into two kinds
of local evidence:

1. an immutable, privacy-minimized SQLite snapshot; and
2. a JSON health report covering schemas, core pipeline invariants, and changes
   in the aggregate score distribution.

It does not schedule jobs, authenticate users, upload data, or make employment
decisions. Generated databases, reports, baselines, and logs stay outside Git.

## Run it

First create every pipeline output described in the README. Initialize the
monitoring baseline once with an explicit version:

```bash
python -m src.operations \
  --run-version demo-2026-09-08 \
  --initialize-baseline
```

On a later completed pipeline run, choose a new immutable version and omit the
initialization flag:

```bash
python -m src.operations --run-version demo-2026-09-09
```

The command uses these safe local defaults:

- database: `sqlite:///data/affectra.db`;
- health report: `data/operations/health_report.json`;
- baseline: `data/operations/health_baseline.json`; and
- log level: `INFO`.

Override settings with environment variables, not source edits:

```bash
export AFFECTRA_DATABASE_URL=sqlite:///data/demo-affectra.db
export AFFECTRA_LOG_LEVEL=WARNING
```

The Sprint 7 implementation accepts local SQLite URLs only. Do not add a remote
database or credentials without a reviewed secrets manager, encryption,
authentication, authorization, backups, and incident-response design.

## Persistence contract

`src/database.py` safely creates three tables if they are missing. It never
drops tables, replaces existing rows, or silently reuses a run version.

- `pipeline_runs`: immutable version, UTC creation time, row counts, source
  quality status, dataset fingerprint, and best experimental baseline name;
- `score_snapshots`: numeric score/components, review level, agent ID, and
  snapshot date; and
- `model_metadata`: compact model-level evaluation JSON.

Names, team names, roles, explanations, transcript text, individual held-out
predictions, raw calls, and secrets are not in the database. A duplicate version
fails and leaves the earlier run untouched. All inserts for one run use a single
database transaction.

SQLite is a local demonstration boundary, not a production access-control
system. Protect the device and file permissions, and delete generated databases
when no longer needed.

## Health report

`health_report.json` records:

- required-column checks and SHA-256 fingerprints for feature and score schemas;
- data-quality status, score range and uniqueness, and agent-disjoint model split;
- identity-free score count, mean, standard deviation, quartiles, extrema, and
  Low/Moderate/High proportions; and
- changes from the explicit baseline.

The defaults flag an absolute mean-score change above 10 points or any review-
level proportion change above 0.20. Override them only as a deliberate review
choice:

```bash
python -m src.operations \
  --run-version demo-2026-09-10 \
  --mean-score-delta 8 \
  --risk-share-delta 0.15
```

An alert means “inspect the pipeline or generated population.” It does not mean
employee health changed. A clean health report also does not validate the score.

## Structured logging

The operations logger writes one JSON object per event to standard error. Its
allow-list contains only event, timestamp, level, component, row count, status,
and run version. On failure it records the exception type, not the exception
message. Do not expand the allow-list to names, transcript content, free-form
errors, database URLs, tokens, or input rows.

Redirecting logs to a file is an operator choice. `*.log` is ignored by Git.
Apply the same retention and access policy as other operational metadata.

## Troubleshooting and recovery

- **Missing dashboard input:** run generation, preprocessing, scoring,
  analytics, and model training first.
- **Baseline missing:** inspect the completed run, then use
  `--initialize-baseline` exactly once. Do not create a baseline from a known
  broken run.
- **Run version already exists:** choose a new meaningful version. Never delete
  evidence merely to reuse a name.
- **Health status `review`:** inspect each false check and comparison alert.
  Preserve the report before changing code or data.
- **Database damaged:** keep the broken file for investigation, recreate all
  generated inputs from their seeds/configuration, and write a new database.
- **Possible data or secret exposure:** stop processing, isolate the file,
  revoke exposed credentials, preserve audit evidence, notify the responsible
  owner, and follow the organization's incident process.

## Maintenance checklist

For each intentional run:

1. use generated or explicitly approved data;
2. run validation, scoring, model evaluation, and tests;
3. choose a unique version tied to its configuration/commit;
4. inspect health checks and distribution alerts;
5. verify the database/report are excluded from Git;
6. review access and retention obligations; and
7. document any alert disposition without adding sensitive details to logs.
