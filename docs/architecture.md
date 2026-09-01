# Architecture

## Planned data flow

1. `data_generator.py` creates safe, reproducible demo data.
2. The ingestion layer reads the four inputs and validates their schemas.
3. Preprocessing cleans types and relationships and writes a quality report.
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
- `calls.call_id` uniquely identifies a call.
- `calls.transcript_id` links one call to one transcript.
- `transcripts.call_id` provides a second relationship check.
- Dates are normalized before time-window calculations.

## Design boundaries

- Raw inputs are never changed in place.
- Validation happens before feature calculation.
- Scoring functions accept prepared features, not raw CSV paths.
- The UI calls service functions; it does not contain training logic.
- Model artifacts include configuration and evaluation metadata.
- Sensitive text is not written to application logs.
