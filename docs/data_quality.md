# Data-Quality Policy

Sprint 2 treats every CSV cell as untrusted input. The pipeline makes cleaning
decisions explicit and records them in `data_quality_report.json`. It never
modifies the source files.

## Expected inputs and outputs

The input directory must contain `agents.csv`, `timeoff.csv`, `calls.csv`,
`transcripts.csv`, and `daily_labels.csv` with the required columns from the
[data dictionary](data_dictionary.md). Extra columns are preserved and listed
in the report. Missing files or required columns stop the run with one readable
error that identifies the problem.

The output directory receives cleaned versions of the same five files and one
machine-readable report. Generated input and output directories are excluded
from version control.

## Cleaning decisions

| Problem | Policy | Reason |
|---|---|---|
| `?`, `-`, or `N/A` | Read as missing | Common external missing-value markers |
| Invalid number, date, or boolean | Convert to missing and count it | Failed parsing must be visible |
| Missing critical ID, date key, or target | Drop the row | A relationship key or target cannot be safely guessed |
| Missing non-key number | Fill with that column's median | The median is less sensitive to extremes |
| Missing text or boolean | Fill with the mode | Uses the most common known category |
| Missing noncritical date | Fill with the median date | Keeps a plausible central date without using today |
| Exact duplicate or duplicate key | Keep the first row | Makes the result deterministic |
| Orphan child key | Drop the child row | Prevents features for nonexistent agents or calls |
| Numeric IQR outlier | Report and preserve | Extreme workload may be meaningful, not erroneous |

The generator's schema bounds still apply. For example, call duration must be
at least 120 seconds, sentiment must be between -1 and 1, and the synthetic
label must be 0 or 1. An invalid non-key measurement becomes missing and can be
imputed. An invalid critical value causes its row to be dropped.

## How IQR detection works

IQR means interquartile range. Sort the values, find the first quartile (`Q1`)
and third quartile (`Q3`), then calculate:

```text
IQR = Q3 - Q1
lower bound = Q1 - 1.5 × IQR
upper bound = Q3 + 1.5 × IQR
```

Values outside those bounds are counted. The multiplier is configurable with
`--iqr-multiplier`. Detection runs once and never removes or recursively
rechecks rows, avoiding a loop that can progressively classify ordinary values
as outliers.

## Reading the report

The top-level `status` is `passed` or `passed_with_warnings`. A warning can mean
the pipeline took a cleaning action, detected a statistical outlier, or found
an incomplete expected relationship such as an agent without time-off data.

Each entry under `tables` contains input/output row counts, missing values,
failed conversions, invalid ranges, duplicates, imputations, orphan removals,
and per-column outlier bounds. `relationships` summarizes cross-table checks.
`totals` makes monitoring easier without hiding the detailed evidence.

This report describes data mechanics, not employee health. It does not show
that a model can predict real-world stress or burnout.
