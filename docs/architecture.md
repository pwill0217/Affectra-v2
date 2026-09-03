# Architecture

## Data flow

1. `data_generator.py` creates safe, reproducible demo data, validates all
   relationships, and records the configuration in a manifest.
2. `data_loader.py` treats the five CSV inputs as untrusted, normalizes known
   missing markers, and validates files and required columns independently from
   the generator.
3. `preprocessing.py` coerces types, applies explicit cleaning policies,
   repairs relationships, reports IQR outliers without deleting them, and
   writes five cleaned CSVs plus `data_quality_report.json`.
4. Feature engineering aggregates calls into agent-day metrics.
5. The scoring layer calculates four explainable component scores.
6. The experimental model trains and evaluates against versioned data.
7. The Streamlit dashboard reads processed outputs and model artifacts.
8. Monitoring checks data drift, score distribution, and pipeline failures.

## Source layout

```text
src/
  data_generator.py       # Synthetic source data
  data_loader.py          # Sprint 2: reading and schema validation
  preprocessing.py        # Sprint 2: cleaning and quality reporting
  features.py             # Sprint 3: agent-day feature engineering
  scoring.py              # Sprint 3: explainable weighted score
  analytics.py            # Sprint 4: summaries for charts
  model_training.py       # Sprint 5: experimental ML pipeline
  evaluation.py           # Sprint 5: metrics and limitations
  database.py             # Sprint 7: persistence boundaries
  app.py                  # Sprint 6: Streamlit interface
tests/                    # Automated tests matching the source modules
docs/sprints/             # Beginner walkthrough and evidence for every sprint
data/                     # Generated locally and excluded from Git
models/                   # Generated locally and excluded from Git
```

Files listed for future sprints are design targets and will only be added when
their sprint is implemented and tested.

## Initial relationships

- `agents.agent_id` is the parent key for calls and time-off records.
- `daily_labels` contains exactly one `agent_id` and `label_date` row for every
  simulated agent-day.
- `calls.call_id` uniquely identifies a call.
- `calls.transcript_id` links one call to one transcript.
- `transcripts.call_id` provides a second relationship check.
- Dates are normalized before time-window calculations.

## Data-quality boundary

Raw CSVs are never edited in place. The loader intentionally reads cells as
untrusted objects so preprocessing can distinguish a missing value from a value
that failed conversion. Critical identifiers and date keys cannot be guessed,
so rows missing them are dropped. Recoverable non-key values use documented
median or mode imputation. Duplicate keys keep the first row, and child rows
with invalid relationships are removed before feature calculation.

IQR outlier detection is descriptive and runs once on the cleaned tables. It
does not recursively delete and recalculate extremes. Unusual workload may be
the signal Affectra needs to examine, so the report preserves those values for
human review. See [data_quality.md](data_quality.md) for every policy.

## Synthetic pressure design

`daily_labels.csv` contains the hidden state used to shape the demo data. A
seeded subset of agents receives a gradually increasing pressure trajectory.
Random pressure events can temporarily increase a day, weekends provide a
small recovery effect, and smoothing carries part of one day's pressure into
the next. Call volume and difficulty respond to that pressure, creating a
learnable but imperfect signal.

The `latent_pressure_score`, `pressure_band`, `simulated_pressure_event`, and
`synthetic_stress_label` columns are target-generation metadata. They must not
be used as input features in Sprint 5. Doing so would leak the answer into the
model and produce misleadingly high metrics.

## Design boundaries

- Raw inputs are never changed in place.
- Validation happens before feature calculation.
- Scoring functions accept prepared features, not raw CSV paths.
- The UI calls service functions; it does not contain training logic.
- Model artifacts include configuration and evaluation metadata.
- Sensitive text is not written to application logs.
