# Privacy, access, retention, and threat analysis

## Current boundary

Affectra's repository and default workflow contain generated synthetic data
only. The local Streamlit application has no authentication or production
authorization layer. Therefore, real employee or customer data must not be
loaded into this release.

Before a real pilot, the organization must obtain appropriate legal, HR,
security, privacy, labor/works-council, and employee input. It must define a
lawful purpose, consent/notice, an appeal and correction process, prohibited
uses, retention, access, incident response, and independent bias/validity tests.

## Data minimization

Collect only data necessary to examine working conditions. Prefer aggregate
numeric call measures over recordings or text. The operational database omits
names, teams, roles, explanations, raw calls, transcripts, predictions, and
secrets. Logs contain allow-listed operational metadata only.

IDs are still potentially identifying and must be treated as sensitive in a
real system. Replace direct workforce IDs with scoped pseudonyms and keep the
mapping in a separately controlled system. Aggregates can also re-identify
people in small teams, so enforce minimum group sizes before production display.

## Role and access design target

The local demo does not implement these roles. They are requirements for a real
pilot, ideally enforced by a central identity provider and server-side policy:

| Role | Minimum access | Explicitly prohibited |
|---|---|---|
| Agent | Their own trends, components, source corrections, and appeal status | Other agents or hidden employment actions |
| Manager | Authorized team workload and supportive-review evidence | Exporting raw text, punitive ranking, unrelated teams |
| Wellness/HR reviewer | Approved cases and aggregate patterns for a documented purpose | Unbounded browsing or clinical diagnosis |
| Data steward | Quality, lineage, retention, correction, and deletion operations | Using records for performance evaluation |
| Model/risk reviewer | De-identified evaluation, drift, bias, and audit evidence | Re-identification or operational employment decisions |
| System administrator | Availability and security metadata | Score content unless separately authorized and audited |

Use least privilege, separation of duties, periodic access review, immediate
offboarding, multi-factor authentication, and immutable audit records. Do not
rely on hidden dashboard controls; authorize every server-side query.

## Retention decision guidance

No production retention period is selected in code because that is a policy and
legal decision, not a safe programming default. Before any real pilot, owners
must create a record for each data class with purpose, owner, legal basis,
minimum retention, deletion method, backup behavior, and litigation-hold rules.

Use these principles:

- do not retain audio or raw transcript text when aggregate features suffice;
- keep raw operational inputs for the shortest approved troubleshooting window;
- retain derived individual scores only while the supportive-review purpose is
  active and allow correction/deletion where legally required;
- use longer-lived de-identified aggregates only after re-identification review;
- rotate or delete logs and backups with the records they describe; and
- test deletion across primary storage, replicas, exports, caches, and backups.

Synthetic demo artifacts may be deleted at any time and can be recreated from
their recorded seed and configuration.

## Threat analysis

| Threat | Example impact | Current controls | Required before a real pilot |
|---|---|---|---|
| Repository or secret leak | Credentials or employee export becomes public | `.env`, databases, data, models, logs, and Streamlit secrets are ignored; `.env.example` contains no secret | Secret scanning, managed vault, rotation, reviewed CI permissions |
| Unauthorized dashboard access | Person views individual scores | Synthetic-only local boundary | SSO/MFA, server-side RBAC, session controls, access reviews, audit trail |
| Device/database theft | Local SQLite file reveals IDs and scores | Minimized tables; local-only URL validation | Encryption at rest, managed keys, endpoint security, backup controls |
| Log leakage | Error contains text, name, path, or token | Allow-listed JSON fields; failure logs exception type only | Central access controls, redaction tests, retention and monitoring |
| Re-identification | Small team or stable ID identifies a person | Names/teams excluded from persistence | Pseudonymization, minimum group sizes, separate mapping, privacy review |
| Data/model tampering | Changed inputs create misleading scores | Schema checks, fingerprints, immutable versions, transactions | Signed provenance, restricted writes, audit logs, integrity verification |
| Unsafe model artifact | Untrusted joblib executes code | Models generated locally and excluded from Git | Artifact signing/scanning; never load untrusted serialized objects |
| Misuse of score | Score drives discipline or diagnosis | Visible responsible-use notices and explainable components | Enforce prohibited-use policy, training, human review, appeal and oversight |
| Bias or context omission | Teams/groups receive uneven false flags | Synthetic-team error evidence and personal baselines | Representative pilot, subgroup validity/fairness tests, accommodations review |
| Silent drift or schema change | Dashboard remains plausible after upstream change | Required columns, schema hashes, aggregate score alerts | Alert routing, owners, service objectives, investigated dispositions |
| Denial of service or corrupt input | App unavailable or partial | Strict validation and atomic JSON writes | Resource limits, isolated ingestion, backups, recovery exercises |

## Residual limitations

Schema and distribution monitoring can identify change, not explain it. The
chosen thresholds are demonstration review thresholds, not statistically or
clinically validated limits. A stable distribution can hide harmful behavior,
and a changed distribution can be legitimate. Human investigation is always
required.

Synthetic model performance mainly reflects relationships designed into the
generator. Nothing in persistence, logging, health checks, or access design
turns that performance into evidence of real-world burnout prediction.
