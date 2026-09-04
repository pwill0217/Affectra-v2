# Explainable Scoring Methodology

Affectra's first score is a transparent 0-to-100 decision-support indicator. It
helps a reviewer inspect working conditions; it is not a diagnosis, performance
rating, or basis for automated employment action.

## Feature table

`src/features.py` produces one row for every cleaned agent and date. It uses only
the keys from `daily_labels.csv` to preserve a complete date spine. Hidden
pressure, band, event, and synthetic-label columns are prohibited from the
feature output.

Calls and transcripts are aggregated into daily call count, mean duration,
after-call work (ACW), hold, transfers, sentiment, negative-call percentage, and
negative-keyword count. Each metric then receives a configurable rolling mean
(seven agent-days by default). A zero-call day stays in the table with zero
observable call metrics.

Three rolling values are compared with the agent's own declared baseline:

```text
calls_vs_baseline = rolling call count / baseline calls per day
acw_vs_baseline = rolling average ACW / baseline average ACW
duration_vs_baseline = rolling average duration / baseline average duration
```

Time-off fields describe one end-of-period snapshot. To avoid pretending that
snapshot was known historically, `risk_scores.csv` scores only each agent's
latest feature row.

## Normalization

Every measure is linearly mapped between a low and high boundary and clipped to
0–100. A “higher” direction means values near the high boundary add more review
risk. A “lower” direction means low available/recent recovery adds more risk.

| Measure | Low | High | Risk direction |
|---|---:|---:|---|
| Calls ÷ personal baseline | 0.75 | 1.15 | Higher |
| ACW ÷ personal baseline | 1.00 | 1.35 | Higher |
| Duration ÷ personal baseline | 1.00 | 1.35 | Higher |
| Mean hold seconds | 40 | 120 | Higher |
| Mean transfers per call | 0.15 | 0.80 | Higher |
| Negative-call rate | 0% | 15% | Higher |
| Negative sentiment magnitude | 0.00 | 0.60 | Higher |
| Negative keywords per call | 0.00 | 0.50 | Higher |
| PTO balance hours | 0 | 80 | Lower |
| Vacation days available | 0 | 10 | Lower |
| PTO hours used in 30 days | 0 | 16 | Lower |
| Days since PTO | 14 | 120 | Higher |

These are transparent demonstration ranges, not medical thresholds. They are
stored in `scoring_manifest.json` so a result can be reproduced and reviewed.
Production adoption would require governance, workforce-policy context, bias
testing, and validation with consented data.

## Components and weights

- **Workload (40%)**: normalized calls compared with the personal baseline.
- **Efficiency friction (20%)**: mean of normalized ACW ratio, duration ratio,
  hold time, and transfers.
- **Tone (25%)**: mean of negative-call rate, negative sentiment magnitude, and
  negative-keyword indicators. These describe customer interactions, not the
  agent's emotions.
- **Recovery context (15%)**: mean of PTO balance, vacation availability,
  recent PTO use, and days since PTO.

The overall calculation is:

```text
risk score = workload × 0.40
           + efficiency friction × 0.20
           + tone × 0.25
           + recovery context × 0.15
```

Custom weights must be finite, nonnegative, and sum to exactly 1.0. The output
retains each component and its weighted contribution; no model hides the math.

## Review levels

| Score | Level | Meaning |
|---|---|---|
| 0 to below 35 | Low | No strong combined signal under the demonstration rules |
| 35 to below 65 | Moderate | Review workload/context and consider a supportive check-in |
| 65 to 100 | High | Prioritize human review of conditions; do not assume a diagnosis |

Each result includes four detailed evidence sentences and an overall explanation
naming the largest component. A reviewer should inspect the evidence and data-
quality report, not act on the label alone.

## Output contract

`agent_day_features.csv` contains daily and rolling observable features.
`risk_scores.csv` contains one latest row per agent with components,
contributions, score, level, and explanations. `scoring_manifest.json` records
the window, weights, normalization ranges, risk-level boundaries, source quality
status, row counts, leakage check, and responsible-use limitation.
