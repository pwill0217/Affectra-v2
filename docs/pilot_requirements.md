# Real-world pilot requirements

Affectra 1.0 is not ready for real employee or customer data. This document is
the handoff checklist for deciding whether a governed pilot should ever begin.
Every item needs a named owner, an approved decision, evidence, and a stop/exit
condition. Software completion does not satisfy these gates.

## 1. Purpose, people, and governance

- Define one narrow supportive purpose and explicitly prohibit discipline,
  termination, compensation, covert monitoring, diagnosis, and treatment.
- Obtain review from legal, privacy, information security, HR, labor relations or
  works councils where applicable, accessibility experts, and employee voices.
- Document lawful basis, notice/consent obligations, jurisdictions, vendors,
  data-controller/processor roles, and a data-protection impact assessment.
- Create an accountable human review process, correction/appeal route, misuse
  reporting channel, oversight cadence, and authority to pause the pilot.
- Select an explicit source-code/deployment license with the repository owner.

## 2. Outcome definition and scientific validity

- Do not treat a generated label as ground truth. Define an ethical, measurable
  pilot outcome with qualified domain experts and affected employees.
- Pre-register the study design, inclusion/exclusion rules, primary metrics,
  acceptable precision/recall tradeoff, sample size, duration, and stopping rules.
- Establish prospective, representative evaluation with temporal and site/team
  holdouts; report uncertainty, PR-AUC, calibration, false positives/negatives,
  and operational consequences.
- Compare against a no-model process and the transparent score. Do not deploy an
  ML baseline merely because it beats a synthetic dummy model.
- Validate subgroup behavior for legally and ethically appropriate dimensions,
  language, shift, role, accessibility, call mix, and team context.
- Require independent review before any claim about burnout, wellbeing, safety,
  fairness, or generalization.

## 3. Data and privacy engineering

- Inventory every field, source, owner, purpose, lawful basis, accuracy risk,
  lineage, access group, retention period, deletion method, and backup behavior.
- Minimize collection; avoid audio/raw transcripts where aggregate measures work.
- Use scoped pseudonyms and keep identity mapping in a separate controlled system.
- Define minimum aggregation groups and protections against linkage/re-identification.
- Implement correction, access, portability, deletion, legal-hold, and pilot-exit
  procedures across primary storage, exports, caches, replicas, and backups.
- Prohibit portfolio/test environments from receiving production data.

## 4. Security and access enforcement

- Complete a security architecture and threat-model review.
- Use managed infrastructure, encryption in transit/at rest, managed keys and
  secrets, SSO, MFA, server-side least-privilege RBAC, and separation of duties.
- Add immutable audit logs, access reviews, offboarding, session controls,
  vulnerability/dependency scanning, artifact signing, backup restore tests,
  incident detection/response, and breach notification procedures.
- Never load untrusted joblib/pickle artifacts.
- Conduct penetration testing and remediate findings before pilot access.

## 5. Integration and data-quality controls

- Contract with approved source systems and document update frequency, latency,
  time zones, late/corrected records, outages, and ownership.
- Validate schemas, keys, units, ranges, completeness, duplication, and lineage at
  ingestion; quarantine failures instead of silently scoring partial data.
- Define service objectives and escalation for stale inputs, quality warnings,
  pipeline failures, and drift alerts.
- Confirm PTO, sentiment, call mix, and baseline definitions across actual sites.

## 6. Model and score operations

- Version data, code, features, thresholds, scores, models, and approvals.
- Approve monitoring metrics and thresholds using pilot evidence, not the demo
  defaults; include feature, prediction, calibration, error, and subgroup drift.
- Define retraining triggers, champion/challenger review, rollback, model/score
  retirement, incident response, and human alert disposition.
- Keep transparent components available even if experimental ML is evaluated.
- Prevent automated employment actions technically, not only through UI text.

## 7. User experience and pilot execution

- Co-design notices, explanations, actions, and appeals with agents and managers.
- Train reviewers to discuss working conditions supportively and to recognize
  uncertainty, customer-tone confounding, policy effects, and false alerts.
- Give participants a way to inspect and correct source facts where permitted.
- Start with a small, time-boxed, reversible pilot; monitor harms and workload as
  well as technical metrics; publish a closeout decision.
- Stop if prohibited use, unexpected harm, access failure, invalid evidence,
  unacceptable subgroup behavior, or unmanageable false alerts occur.

## Explicit human decisions still required

The repository intentionally does not choose the real pilot's jurisdiction,
lawful basis, label/outcome, acceptable error tradeoff, participating population,
retention schedule, production roles, hosting/vendor, license, monitoring limits,
or go/no-go authority. Those choices materially affect people and cannot be
filled in by a synthetic demonstration.
