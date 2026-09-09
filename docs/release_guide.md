# Affectra 1.0 release, deployment, demo, and maintenance guide

## Supported release boundary

Affectra 1.0 is a local, synthetic-data portfolio demonstration. The supported
deployment is a trusted user's computer or isolated demonstration environment.
It has no production authentication, authorization, encryption-key management,
vendor integration, or approved real-data governance. Do not expose the local
Streamlit server to the public internet and do not load employee/customer data.

## Fresh setup and one-command verification

Install Python 3.12 or newer and Git. From a clean terminal:

```bash
git clone https://github.com/pwill0217/Affectra-v2.git
cd Affectra-v2
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pip check
python -m ruff check .
python -m compileall -q src tests
python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=90
python -m src.release
```

On Windows PowerShell, activation is `.venv\Scripts\Activate.ps1`. The release
command deliberately refuses a non-empty `data/release-demo/` destination. To
rerun, choose a new directory and version instead of deleting or overwriting
evidence:

```bash
python -m src.release \
  --output-root data/release-demo-2 \
  --run-version release-demo-2
```

`release_manifest.json` is the final machine-readable receipt. It records the
configuration, row counts, quality evidence, score distribution, agent-disjoint
split, operational checks, UI pages, and every required artifact.

## Launch the generated dashboard

Point the application at the release directory:

```bash
export AFFECTRA_SCORED_DIR=data/release-demo/scored
export AFFECTRA_PROCESSED_DIR=data/release-demo/processed
export AFFECTRA_MODELS_DIR=data/release-demo/models
python -m streamlit run src/app.py
```

On PowerShell:

```powershell
$env:AFFECTRA_SCORED_DIR = "data/release-demo/scored"
$env:AFFECTRA_PROCESSED_DIR = "data/release-demo/processed"
$env:AFFECTRA_MODELS_DIR = "data/release-demo/models"
python -m streamlit run src/app.py
```

Open the printed loopback URL, normally `http://localhost:8501`, and stop with
Ctrl+C. Keep the default loopback binding. If the port is occupied, add
`--server.port 8502`.

## Five-minute portfolio demo

1. **Set context (30 seconds).** Explain that Affectra studies generated call-
   center operating conditions and is decision support, not diagnosis or an
   employee-performance system.
2. **Overview (60 seconds).** Filter a synthetic team and review level. Point to
   current counts and score spread; explain why team charts cannot prove cause.
3. **Agent detail (90 seconds).** Select a synthetic agent. Walk through the
   0–100 score, four visible components, 40/20/25/15 contributions, evidence
   sentences, and personal-baseline ratios.
4. **Data quality (45 seconds).** Show preserved rows, corrections, relationship
   checks, and reported—not automatically deleted—outliers.
5. **Model evaluation (60 seconds).** Compare dummy, logistic, and forest
   baselines. Emphasize the agent-disjoint split, confusion counts, calibration,
   rare positive class, and why synthetic performance is not validation.
6. **Engineering close (45 seconds).** Show `release_manifest.json`, health
   report, minimized SQLite schema, tests/coverage, and GitHub Actions.

Useful interview summary: “I built the complete data-product path—safe synthetic
data, validation, feature engineering, explainable scoring, leakage-aware ML,
interactive UI, persistence, monitoring, testing, and CI—while documenting the
privacy and validity boundary.”

## Manual stage-by-stage workflow

Use this when teaching or diagnosing one stage:

```bash
python -m src.data_generator \
  --num-agents 30 --num-days 30 --seed 606 --at-risk-fraction 0.5
python -m src.preprocessing
python -m src.scoring
python -m src.analytics
python -m src.model_training
python -m src.operations --run-version manual-demo-001 --initialize-baseline
```

The one-command release uses isolated subdirectories so it cannot be confused
with these default stage paths.

## Maintenance routine

### Every code change

1. Review the diff for generated data, databases, models, logs, secrets, or OS
   files.
2. Run Ruff, compilation, all tests with the 90% coverage gate, and the release
   command in a new destination.
3. Inspect `release_manifest.json`, data quality, class counts, confusion counts,
   health checks, and every dashboard page.
4. Push only source, configuration examples, tests, and documentation.
5. Require a successful GitHub Actions run before treating the change as ready.

### Dependency maintenance

- Update within the bounded versions in `requirements*.txt` on a branch.
- Install into a new environment and run `python -m pip check`.
- Run the entire release gate; do not infer compatibility from installation.
- Review upstream security advisories and licenses before adding a dependency.
- Record intentional release changes in `CHANGELOG.md`.

### Generated evidence

- Use unique run versions; never overwrite historical operational rows.
- Create a monitoring baseline only from an inspected, known-good run.
- Investigate every schema/distribution alert before changing thresholds.
- Generated demo data is reproducible and may be removed when no longer needed.
- Do not back up synthetic artifacts as though they were production records.

## Troubleshooting

| Symptom | Likely reason | Safe response |
|---|---|---|
| Release destination is not empty | A previous run is present | Choose a new path/version; preserve existing evidence |
| Model cannot form a two-class grouped split | Too few generated positives across agents | Use the documented 30-agent, 0.5 at-risk demo settings; never allow agent overlap |
| Dashboard reports missing inputs | One pipeline stage did not finish or paths point elsewhere | Read the first failed stage and confirm all three dashboard environment paths |
| Health status is `review` | A core check failed or distribution/schema changed | Inspect individual checks and alerts; do not call it an employee-health change |
| Duplicate run version | Immutable evidence already uses the name | Select a new version; do not delete the earlier run to reuse it |
| Port 8501 is busy | Another process owns the port | Use `--server.port 8502` or stop the known process |
| Dependency behavior changes | A fresh install selected newer allowed packages | Recreate the environment, run `pip check` and the full gate, then narrow a bound if justified |
| Suspected secret/private-data exposure | Sensitive material may have entered a file or history | Stop, isolate, revoke credentials, preserve audit evidence, and follow an approved incident process |

## Backup and recovery

Source and documentation are recovered from Git. Synthetic data, models, charts,
databases, and monitoring outputs are regenerated from the recorded seed and
configuration. If an artifact is corrupt, preserve it for diagnosis and produce
a new release directory; do not silently patch generated evidence in place.

## Deployment beyond the local demo

A public or internal network deployment is not supported by version 1.0. Before
one exists, every gate in [pilot requirements](pilot_requirements.md) needs an
owner and evidence. In particular: approved purpose and policy, representative
data and real validation, SSO/MFA and server-side roles, encryption and secrets
management, retention/deletion, audit/incident response, subgroup analysis,
appeal/correction, and controlled pilot exit criteria.
