# Sprint 3 Tutorial: Agent Metrics and Explainable Scoring

**Status:** Complete  
**Date:** 2026-09-04  
**Goal:** Convert cleaned calls, transcripts, baselines, and recovery context
into daily/rolling features and one transparent current score per agent.

## Why this sprint matters

Raw call rows answer questions about individual interactions. A manager needs a
different view: Is an agent handling more work than usual? Is work taking longer
than that person's own baseline? Has customer tone become more difficult? Does
the available recovery snapshot add context?

Sprint 3 turns clean records into that view without training a model or using
the synthetic generator's hidden answer:

```text
cleaned tables
    -> complete agent-day spine
    -> daily call and tone aggregates
    -> rolling means
    -> personal-baseline ratios
    -> four 0–100 components
    -> visible weighted sum
    -> latest score, review level, and explanations
```

The result is an auditable decision-support rule. It is not a medical test,
employee ranking, or proof that burnout can be predicted in the real world.

## Starting state

Sprint 2 already treats the five CSV inputs as untrusted. It parses types,
handles missing and invalid values, removes duplicate/orphan child rows,
preserves statistical outliers, and writes cleaned tables plus a quality report.

Sprint 3 begins only after those checks. It adds `src/features.py` and
`src/scoring.py`; scoring logic does not read raw CSV paths directly.

## Part 1: Building agent-day features

### A complete date spine

`build_agent_day_features()` uses only `agent_id` and `label_date` from
`daily_labels.csv` to create one row for every synthetic agent-day. This is
called a spine: other metrics attach to it.

Why not build rows only from calls? An agent with zero calls on a day would
disappear. The spine preserves that day and fills observable call metrics with
zero.

The function explicitly prohibits these target-generation fields:

- `latent_pressure_score`;
- `pressure_band`;
- `simulated_pressure_event`; and
- `synthetic_stress_label`.

Those columns helped generate the demo behavior. Using them in the operational
score would leak the answer and make the score circular.

### One-to-one call and transcript data

`aggregate_daily_calls()` joins calls and transcripts on both `call_id` and
`transcript_id`. Pandas receives `validate="one_to_one"`, so repeated or
mismatched identifiers fail instead of silently multiplying rows.

The joined rows are grouped by `agent_id` and `call_date`. Each group produces:

- call count;
- mean call duration;
- mean after-call work (ACW);
- mean hold seconds;
- mean transfers;
- mean sentiment score;
- percentage of calls labeled Negative; and
- mean negative-keyword count.

Aggregation means replacing many detailed rows with summary numbers for a
useful unit—in this case, one agent on one day.

### Rolling windows

One unusual day should not automatically represent a sustained pattern.
`_add_rolling_features()` sorts each agent's rows by date and uses
`rolling(..., min_periods=1).mean()`.

The default window is seven agent-days. On the first date, only one value is
available, so the first rolling mean equals that day's metric. On day two it is
the mean of two days. From day seven onward it is the mean of the current and
previous six rows. The CLI can select another positive integer window.

### Personal baselines

`_safe_ratio()` compares rolling calls, ACW, and duration with the agent's own
baseline:

```text
calls_vs_baseline = rolling calls / baseline calls
acw_vs_baseline = rolling ACW / baseline ACW
duration_vs_baseline = rolling duration / baseline duration
```

A value of `1.20` means 20% above that person's baseline. This is more useful
than treating every agent as identical, although production baselines would
still need policy review and periodic updating.

The function rejects zero, missing, or infinite baselines rather than creating
an invalid ratio.

### Recovery snapshot timing

The time-off table is one end-of-period snapshot, not a historical table. Sprint
3 records a `recovery_snapshot_date` and calculates days since PTO at that date.
It does not pretend those values were known on every earlier day.

The complete daily feature table is written for later trend analysis, but the
current score selects only each agent's latest row. This is a small but important
way to avoid time leakage.

## Part 2: Calculating the transparent score

### Normalizing different units

Calls are ratios, hold time is seconds, tone is a percentage, and PTO is hours.
They cannot be averaged directly. `_scale_high()` and `_scale_low()` map each
measure to the same 0–100 range.

For a higher-risk measure:

```text
normalized = (value - low boundary) / (high boundary - low boundary) × 100
```

The result is clipped: anything below the low boundary becomes 0, and anything
above the high boundary becomes 100. `_scale_low()` reverses that scale for
available recovery resources, where a smaller value contributes more risk.

All demonstration boundaries live in `SCORING_RANGES` and are copied into the
manifest. Read [the scoring methodology](../scoring.md) for the exact table.
These are engineering thresholds for a synthetic demonstration, not clinical
cutoffs.

### Four visible components

`calculate_component_scores()` produces:

1. `workload_score`: rolling call count compared with personal baseline;
2. `efficiency_friction_score`: the average normalized ACW ratio, duration
   ratio, hold time, and transfers;
3. `tone_score`: the average negative-call rate, negative sentiment magnitude,
   and negative-keyword rate; and
4. `recovery_context_score`: the average risk from PTO balance, vacation days,
   PTO used recently, and time since PTO.

Tone describes the customer interaction. It must not be described as direct
measurement of the agent's emotions.

### Configurable 40/20/25/15 weights

`ScoreWeights` is a frozen dataclass with these defaults:

- workload: 0.40;
- efficiency friction: 0.20;
- tone: 0.25; and
- recovery context: 0.15.

Its `__post_init__` method rejects text, booleans, negative values, infinity,
and totals that do not equal 1.0. The visible calculation is:

```text
risk = workload × 0.40
     + efficiency friction × 0.20
     + tone × 0.25
     + recovery context × 0.15
```

`score_agent_features()` saves the four weighted contributions as separate
columns before summing them. This makes the final number easy to audit.

### Levels and explanations

`risk_level()` maps scores below 35 to Low, 35 through below 65 to Moderate,
and 65 through 100 to High. Tests cover the exact boundaries.

Each output row includes:

- the four component values;
- the four weighted contributions;
- the overall score and level;
- a workload sentence showing the personal-baseline ratio;
- an efficiency sentence with ACW, duration, hold, and transfers;
- a tone sentence with negative-call rate, sentiment, and keywords;
- a recovery sentence with PTO evidence; and
- an overall explanation naming the largest component and repeating the
  supportive-use boundary.

## Part 3: Running the pipeline

`run_scoring()` deliberately rechecks the processed CSVs through Sprint 2's
loader and preprocessing logic. It then builds features, selects the latest row
per agent, calculates scores, and writes three files.

`agent_day_features.csv` contains every daily and rolling feature.
`risk_scores.csv` contains one current score per agent. `scoring_manifest.json`
records the feature window, weights, thresholds, row counts, risk levels, source
quality, leakage check, and responsible-use limitation.

## Files and functions changed

- `src/features.py`
  - `aggregate_daily_calls()` joins and groups call/tone records.
  - `_add_rolling_features()` creates configurable rolling means.
  - `_safe_ratio()` validates personal-baseline comparisons.
  - `build_agent_day_features()` coordinates the feature table and leakage
    guard.
  - `feature_summary()` creates small JSON-safe manifest evidence.
- `src/scoring.py`
  - `ScoreWeights` and `ScoringConfig` validate configuration.
  - `_scale_high()` and `_scale_low()` normalize measurements.
  - `calculate_component_scores()` creates the four 0–100 components.
  - `risk_level()` applies tested review boundaries.
  - `score_agent_features()` creates contributions, totals, levels, and text.
  - `write_scoring_outputs()` writes CSVs and the manifest.
  - `run_scoring()` and `main()` provide orchestration and the CLI.
- `tests/test_features.py`: spine, aggregation, rolling math, zero-call days,
  baseline ratios, leakage, relationship, and window tests.
- `tests/test_scoring.py`: weights, normalization bounds, level boundaries,
  latest-row selection, explanations, malformed inputs, outputs, and CLI tests.
- `docs/scoring.md`: exact formulas, boundaries, outputs, and limitations.
- `docs/architecture.md`, `README.md`, `SPRINT_LOG.md`, and the roadmap: current
  design, use, evidence, and next work.
- `docs/sprints/sprint-03-explainable-scoring.md`: this tutorial.

## Follow along as a complete beginner

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

On Windows PowerShell, activation is `.venv\Scripts\Activate.ps1`.

### 2. Create and clean synthetic data

```bash
python -m src.data_generator \
  --num-agents 10 \
  --start-date 2026-08-01 \
  --num-days 14 \
  --seed 303 \
  --output-dir data/tutorial-raw

python -m src.preprocessing \
  --input-dir data/tutorial-raw \
  --output-dir data/tutorial-processed
```

### 3. Create features and scores

```bash
python -m src.scoring \
  --input-dir data/tutorial-processed \
  --output-dir data/tutorial-scored \
  --rolling-window 7
```

Open `data/tutorial-scored/risk_scores.csv`. Pick one row and confirm that its
four contribution columns add to `risk_score` (small decimal differences can
come from rounding).

### 4. Try custom weights

The values must add to 1.0:

```bash
python -m src.scoring \
  --input-dir data/tutorial-processed \
  --output-dir data/tutorial-custom-score \
  --workload-weight 0.50 \
  --efficiency-weight 0.20 \
  --tone-weight 0.20 \
  --recovery-weight 0.10
```

Compare the two manifests and score files. The raw components do not change;
only their contributions and final score do.

### 5. Trace one agent by hand

1. Find the agent's final date in `agent_day_features.csv`.
2. Read `calls_vs_baseline` and the workload normalization range in the
   manifest.
3. Calculate the normalized workload value with the formula above and clip it
   to 0–100.
4. Multiply by the workload weight.
5. Repeat for the other components or inspect their saved contributions.
6. Add the four contributions and compare with `risk_score`.
7. Read the evidence sentences and verify they use the same row values.

### 6. Read tests as examples

Start with `test_daily_aggregation_and_rolling_average_are_mathematically_correct`.
It independently calculates a rolling mean and compares it with the production
function. Then read `test_component_scores_are_bounded_at_zero_and_one_hundred`,
which sends extreme inputs through every component.

`test_only_latest_agent_day_is_scored_and_explanations_show_evidence` proves
that an older, higher measurement does not replace the latest snapshot and that
the explanation includes the latest personal-baseline ratio.

### 7. Run all checks

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m ruff check src tests
python -m compileall -q src tests
python -m pytest -q --cov=src --cov-report=term-missing
```

Ruff checks common mistakes and style rules. `compileall` checks Python syntax.
Pytest executes behavioral examples. Coverage reports which source statements
were executed, but even high coverage cannot prove a product is correct or
fair.

## Verification evidence

- Dependency installation from runtime and development manifests: passed.
- Ruff: all checks passed.
- Python compilation: passed.
- Pytest: 60 tests passed with no warnings.
- Total source coverage: 93%.
- `src/features.py` coverage: 91%.
- `src/scoring.py` coverage: 99%.
- End-to-end flow: generation → preprocessing → feature engineering → scoring
  passed.
- Smoke data: 20 agents, 20 time-off rows, 9,232 calls, 9,232 one-to-one
  transcripts, and 280 agent-days across 14 days.
- Data quality: 0 corrections, 0 relationship warnings, all rows preserved, and
  349 non-destructive IQR outliers reported.
- Scoring: 280 agent-day feature rows and 20 latest-agent scores.
- Review distribution: 13 Low and 7 Moderate; scores ranged 16.59–50.17.
- Leakage guard: zero synthetic target-generation fields in the feature table.
- Output contract: feature CSV, score CSV, and JSON manifest written.
- Generated data, reports, environments, caches, and artifacts remained outside
  Git.

## Decisions and tradeoffs

- The synthetic label table supplies the date spine but none of its hidden state
  or target values. This preserves zero-call days without circular scoring.
- Rolling means use a clear row window with `min_periods=1`. Early days use less
  history, which is visible and preferable to deleting them.
- Personal baselines are used for call volume, ACW, and duration. Hold,
  transfers, tone, and recovery currently use visible demonstration ranges
  because no personal history exists for those fields yet.
- Static time-off context is used only for latest scores. A future production
  system should ingest time-versioned recovery data for historical scoring.
- Linear normalization is easier to explain than a hidden nonlinear formula.
  Clipping prevents one extreme value from making a component exceed 100.
- Fixed normalization ranges are versioned in the manifest. They are a demo
  policy, not scientifically validated thresholds.
- Weights are configurable but validated. Making every contribution visible
  prevents a weight change from silently altering the result.
- The current output uses Low, Moderate, and High review levels. These labels
  prioritize human inspection and never authorize automated action.
- Synthetic data remains sufficient for engineering tests, but synthetic score
  behavior cannot validate real-world burnout prediction.

## Blockers

None. The sprint required no credentials, private employee/customer data,
license decision, legal policy, or destructive product choice.

## Next sprint

Sprint 4 will build reusable analytics for team summaries, score/component
distributions, trends, and correlations. It will add at least three accessible,
well-labeled chart types based on processed features and scores and explain what
each visualization can—and cannot—prove.
