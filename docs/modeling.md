# Experimental modeling guide

## Purpose and boundary

Sprint 5 is a reproducible software experiment against Affectra's generated
`synthetic_stress_label`. It asks whether ordinary classifiers can recover a
pattern deliberately placed in synthetic operational data. It does **not** show
that the label, features, transparent score, or models measure burnout in real
people.

Run this only after generating and cleaning the five synthetic tables:

```bash
python -m src.model_training \
  --input-dir data/processed \
  --output-dir models \
  --rolling-window 7 \
  --test-size 0.25 \
  --random-state 42
```

## Leakage-aware feature and target strategy

`src/features.py` first builds observable agent-day features without any target
metadata. `prepare_training_data()` then joins only the binary research target
by `(agent_id, metric_date)`. It requires a complete, unique target grid.

The eleven allowed model inputs are rolling call count, duration, ACW, hold,
transfers, sentiment, negative-call rate, negative-keyword count, and the calls,
ACW, and duration ratios to personal baselines.

The model cannot use:

- the target itself, latent pressure, pressure band, or simulated event;
- agent name or ID, team, role, or dates;
- score components, contributions, levels, or explanations; or
- PTO/recovery snapshot values, because one end-of-period snapshot is not valid
  historical information for every agent-day.

The manifest records both the allow-list and deny-list so the boundary is
auditable.

## Split and reproducibility

`GroupShuffleSplit` holds out complete agents. If agent 12 is in the test set,
none of agent 12's dates may be used for training. This is stricter than a
random row split, which could let a model learn an agent's recurring pattern and
then appear to generalize to another day from that same agent.

The configured random state controls the split and both learned classifiers.
The manifest records configuration, row/class counts, zero-overlap evidence,
date range, and a SHA-256 fingerprint of the ordered experiment table.

## Baselines

- `dummy_prior` always uses the training-set class frequency. It tells us what
  happens without learning feature relationships.
- `logistic_regression` standardizes numeric features and learns a linear
  probability boundary. Class balancing gives rare positive rows more weight.
- `random_forest` combines many decision trees and can represent nonlinear
  relationships. Its seed, tree count, class balancing, and leaf size are fixed.

All three models receive the same training rows and are measured on the same
held-out agents. “Best” means highest balanced accuracy in this one synthetic
run, with an alphabetical tie-break—not approval for production use.

## Evaluation evidence

`evaluation.json` reports:

- accuracy: overall fraction correct;
- balanced accuracy: average recall across both classes;
- precision: fraction of positive predictions that were positive labels;
- recall: fraction of positive labels found;
- F1: balance of precision and recall;
- ROC AUC: probability ranking across the two classes;
- Brier score and log loss: probability-quality penalties;
- expected calibration error: weighted gap between probability and observed
  synthetic frequency; and
- true/false positive and true/false negative counts.

Accuracy can be dangerously reassuring when the positive label is rare. A model
that predicts zero for every row may be almost perfectly accurate while having
zero recall. Always read class counts, balanced accuracy, recall, calibration,
and confusion counts together.

`calibration.csv` groups probabilities into bins. `team_error_analysis.csv`
shows mistakes by synthetic team so uneven behavior can be noticed; it is not a
team ranking or a fairness certification. `test_predictions.csv` contains
privacy-minimized held-out evidence without names or transcript text.

## Transparent score comparison

The best baseline's probability is compared with the explainable 0–100 score on
each held-out agent's latest snapshot only. The report includes mean values,
absolute gap, Pearson correlation, and agreement between a 0.5 model flag and a
Moderate-or-High score. This preserves the score's time-off boundary. Agreement
does not prove that either method measures burnout, and the model never replaces
the transparent score.

## Generated outputs

The `models/` directory contains three `.joblib` pipelines plus
`test_predictions.csv`, `calibration.csv`, `team_error_analysis.csv`,
`evaluation.json`, and `training_manifest.json`. All are generated, excluded
from Git, and must be recreated in the target environment. Loading a joblib file
from an untrusted source can execute code; load only artifacts you generated or
otherwise trust.

## Real-world requirements

Before any real pilot, the team would need consent, a lawful purpose, data
minimization, retention/access rules, security review, stakeholder and legal/HR
review, representative data, bias and subgroup analysis, external validation,
drift monitoring, and a documented human appeal/review process. Synthetic
metrics cannot substitute for any of these requirements.
