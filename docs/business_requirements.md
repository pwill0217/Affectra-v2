# Affectra Business Requirements

## 1. Purpose

Customer-service teams often notice burnout only after absenteeism, declining
quality, or employee turnover. Affectra combines workload, call-friction,
customer-tone, and recovery indicators so a manager can notice sustained
pressure earlier and begin a supportive conversation.

Affectra provides decision support. It does not diagnose a medical condition,
measure an employee's worth, or automatically make employment decisions.

## 2. Intended users

- Customer-service managers reviewing team workload
- Workforce-management teams planning staffing and recovery time
- Employee-wellness teams looking for aggregate trends
- Analysts studying operational conditions that may contribute to stress

Individual agents may eventually receive access to their own trends and the
factors contributing to an alert.

## 3. Product goals

1. Combine data that normally lives in separate call, transcript, and time-off
   systems.
2. Compare an agent primarily with their own baseline, not only with peers.
3. Produce an explainable 0-to-100 risk indicator and show its components.
4. Display team and individual trends through interactive visualizations.
5. Let a user filter, search, and inspect the evidence behind an alert.
6. Protect employee privacy and minimize the stored data.
7. Create reproducible synthetic data so the portfolio project contains no
   real employee or customer information.

## 4. Functional requirements

### Data generation and ingestion

- Generate internally consistent agents, calls, transcripts, time-off, and
  synthetic daily-label CSVs.
- Accept those five datasets from a configured directory or upload flow.
- Validate required columns, data types, ranges, uniqueness, and relationships.
- Produce a human-readable data-quality report.

### Analytics

- Aggregate raw calls into daily and rolling agent metrics.
- Compare current behavior with each agent's baseline.
- Calculate four visible score components using the initial weights:
  workload 40%, efficiency friction 20%, tone 25%, and recovery context 15%.
- Show the exact factors that increased or decreased a score.
- Train and evaluate a separate experimental machine-learning baseline.
- Keep agents disjoint between training and testing, prohibit target-generation
  metadata from inputs, and report class-sensitive and calibration metrics.
- Never present synthetic-label model accuracy as clinical validation.

### User experience

- Show team overview metrics and a sortable risk table.
- Provide individual trends and component explanations.
- Include at least three useful chart types.
- Support interactive team, date, and risk-level filters.
- Let users search/select synthetic agents and compare experimental models.
- Explain limitations and appropriate use inside the application.

### Reliability and operations

- Store processed records and model metadata with reproducible versions.
- Test core generation, validation, transformation, scoring, and prediction code.
- Log failures without logging transcript content or other sensitive fields.
- Document local setup, use, maintenance, and troubleshooting.

## 5. Nonfunctional requirements

- **Explainability:** every risk result must expose its component scores.
- **Privacy:** use synthetic data by default and collect the minimum necessary
  information when integrating real systems.
- **Security:** do not commit secrets, raw customer data, or employee exports.
- **Reproducibility:** fixed seeds and recorded configuration must recreate a run.
- **Maintainability:** separate data, analytics, model, and interface code.
- **Accessibility:** charts must include labels and not rely on color alone.
- **Performance:** the local demo should load and filter the default dataset in a
  few seconds on a typical laptop.

## 6. Success criteria

The portfolio release is complete when:

- A fresh clone can install, generate data, run tests, and launch the dashboard.
- Invalid inputs fail with a clear explanation instead of silently changing data.
- Every displayed risk score can be traced to the four component categories.
- The dashboard supports meaningful team and agent-level exploration.
- Model evaluation reports appropriate metrics, limitations, and leakage checks.
- Documentation lets a beginner reproduce every sprint.
- Automated tests pass in GitHub Actions.

## 7. Out of scope for the first release

- Medical diagnosis or treatment recommendations
- Automated discipline, termination, scheduling, or compensation decisions
- Live call recording or covert employee monitoring
- Production integrations with a specific contact-center vendor
- Claims that the score has been clinically validated

## 8. Assumptions and risks

- Synthetic data can demonstrate engineering behavior but cannot prove that the
  score predicts real human burnout.
- Sentiment may reflect customer behavior rather than an agent's mental state.
- Team, shift, language, accessibility, and call-type differences can create bias.
- PTO data may be incomplete or affected by company policy.
- A production pilot would require consent, governance, retention rules, access
  controls, bias testing, and review by legal and HR specialists.
