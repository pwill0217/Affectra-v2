# Synthetic Data Dictionary

This document describes schema version 1 produced by `src/data_generator.py`.
Every record is fictional. The CSV files are generated locally and excluded
from Git.

## Relationships

- One agent has one time-off snapshot.
- One agent has many calls.
- One call has exactly one transcript.
- One agent has one daily-label row for every simulated date.

## `agents.csv`

One row represents one fictional customer-service employee.

| Column | Type | Meaning | Rule |
|---|---|---|---|
| `agent_id` | integer | Stable synthetic agent key | Unique, starts at 1 |
| `name` | text | Faker-generated display name | Never empty |
| `team` | category | Assigned support team | One of the configured teams |
| `role` | category | Assigned job role | One of the configured roles |
| `start_date` | date | Fictional employment start | 30 days to 5 years before simulation start |
| `baseline_calls_per_day` | integer | Agent's normal daily call count | 25 through 54 |
| `baseline_avg_acw` | integer | Normal after-call work in seconds | 90 through 239 |
| `baseline_avg_call_duration` | integer | Normal call length in seconds | 300 through 749 |

## `timeoff.csv`

One row represents the recovery/time-off snapshot available for one agent at
the end of the simulated period.

| Column | Type | Meaning | Rule |
|---|---|---|---|
| `timeoff_id` | integer | Time-off record key | Unique, starts at 1 |
| `agent_id` | integer | Links to `agents.agent_id` | Exactly one row per agent |
| `pto_balance_hours` | integer | Remaining paid-time-off hours | 0 through 119 |
| `vacation_days_available` | integer | Available vacation days | 0 through 14 |
| `pto_used_hours_30d` | integer | PTO used in the previous 30 days | 0 through 31 |
| `last_pto_date` | date | Most recent fictional PTO date | Within 180 days of simulation end |

## `calls.csv`

One row represents one fictional customer interaction. Daily call volume and
difficulty are influenced by the hidden simulated pressure trajectory.

| Column | Type | Meaning | Rule |
|---|---|---|---|
| `call_id` | integer | Call key | Unique, starts at 1 |
| `agent_id` | integer | Links to `agents.agent_id` | Must reference an agent |
| `call_date` | date | Day of the call | Within configured simulation period |
| `duration_seconds` | integer | Total call duration | At least 120 |
| `acw_seconds` | integer | After-call work duration | At least 30 |
| `hold_seconds` | integer | Customer hold duration | At least 0 |
| `transfer_count` | integer | Number of transfers | 0, 1, 2, or 3 |
| `transcript_id` | integer | Links to `transcripts.transcript_id` | Unique and one-to-one |

## `transcripts.csv`

One row contains safe template text and sentiment metadata for one call. It is
not a real transcript and contains no customer information.

| Column | Type | Meaning | Rule |
|---|---|---|---|
| `transcript_id` | integer | Transcript key | Unique, matches one call |
| `call_id` | integer | Links to `calls.call_id` | Unique and one-to-one |
| `transcript_text` | text | Selected fictional call summary | Never empty |
| `sentiment_label` | category | Customer interaction tone | Positive, Neutral, or Negative |
| `sentiment_score` | decimal | Numeric tone indicator | -1.0 through 1.0 |
| `negative_keyword_count` | integer | Matched words from a small demo list | At least 0 |

## `daily_labels.csv`

One row represents the hidden synthetic state for one agent on one day. This
table supports later pipeline and model demonstrations; it does not represent
a diagnosis or a label collected from a real person.

| Column | Type | Meaning | Rule |
|---|---|---|---|
| `agent_id` | integer | Links to `agents.agent_id` | One row per agent/date |
| `label_date` | date | Simulated day | Within configured period |
| `latent_pressure_score` | decimal | Hidden smoothed simulation value | 0.0 through 1.0 |
| `pressure_band` | category | Readable form of latent pressure | Low, Elevated, or High |
| `simulated_pressure_event` | boolean | Whether a temporary event was injected | True or False |
| `synthetic_stress_label` | integer | Research-only binary target | 1 at pressure 0.65 or above, otherwise 0 |

### Leakage warning

Do not use any `daily_labels.csv` column except `synthetic_stress_label` as a
model feature. The pressure fields created the behavior in the other tables.
Feeding them into a model would reveal the answer and make the model look far
more accurate than it really is.

## `generation_manifest.json`

The manifest records:

- `schema_version`: format version for future migrations;
- `synthetic_only`: a permanent reminder that the dataset is fictional;
- `configuration`: command inputs needed to reproduce the run;
- `row_counts`: output size for every table; and
- `files`: table-to-filename mapping.

No generation timestamp is included because a moving timestamp would make two
otherwise identical runs produce different manifest bytes.
