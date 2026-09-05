# Analytics and visualization guide

Sprint 4 turns Sprint 3's processed outputs into exploratory tables and charts.
It does not read raw CSVs, hidden synthetic pressure values, or transcript text.
Run it after scoring:

```bash
python -m src.analytics \
  --input-dir data/scored \
  --output-dir data/analytics
```

## Output tables

- `team_summary.csv` contains current counts, mean/median/maximum scores, review
  rates, and mean component scores by synthetic team.
- `risk_distribution.csv` counts Low, Moderate, and High review levels. Empty
  levels remain visible with a zero.
- `daily_trends.csv` summarizes observable rolling workload, baseline ratios,
  customer tone, and sentiment by day. It deliberately does not invent
  historical risk scores from a current time-off snapshot.
- `correlation_matrix.csv` contains Pearson correlations among varying,
  observable agent-day features. Constant features are omitted.
- `analytics_manifest.json` records row counts, outputs, accessibility cues,
  analysis choices, and the limits of every chart.

## Chart catalog

### Current agents by review level

The bar chart shows how many current agent snapshots fall in each review level.
Each bar includes a count and percentage, so color is not the only cue. It cannot
show change over time, explain why a score changed, diagnose health, or measure
performance.

### Baseline trends

The line chart shows team-wide daily averages for calls, after-call work (ACW),
and call duration relative to each agent's personal baseline. The lines use
different markers and dash styles, and a labeled 1.0 reference means “at personal
baseline.” Aggregation can hide individual differences, and a trend does not
prove a cause or diagnosis.

### Team score box plots

The box plots show the current score spread within each synthetic team. All
points remain visible, and agent names are not included. Different team mixes,
roles, call types, policies, or small sample sizes can make comparisons unfair.
The chart cannot establish a cause or support employment decisions.

### Observable-feature correlations

The heatmap reports Pearson's *r*, from -1 to 1, with a numeric label in every
cell. Pearson correlation describes linear association; it does not establish
causality. Score components and synthetic targets are excluded to keep the view
focused on observable inputs rather than formula-driven or leaked relationships.

## Responsible interpretation

All current evidence comes from generated synthetic data. Successful execution
shows that the software behaves as designed; it does not validate real-world
burnout prediction. These outputs are prompts for supportive human review, not a
medical diagnosis, performance rating, or basis for punitive action. A real
pilot requires consent, governance, privacy review, bias testing, and validation
with appropriately collected data.
