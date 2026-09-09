# Sprint 8 tutorial: release hardening and final handoff

## Goal

This final planned sprint turns eight working layers into one reproducible
release. A beginner can now create a clean environment, run one command, verify
the full generated-data workflow, open every dashboard page, understand the
artifact trail, demonstrate the project, and distinguish completed portfolio
scope from the work required for a real-world pilot.

The central lesson is that a release is more than a version number. It needs an
integrated entrypoint, a visible output contract, clean-environment evidence,
continuous integration, safe failure behavior, operating instructions, and an
honest boundary around what has not been validated.

## Starting state

Sprint 7 completed every individual layer: synthetic generation, defensive
cleaning, explainable scoring, analytics, experimental ML, the Streamlit UI,
privacy-minimized SQLite persistence, safe logging, and monitoring. The test
suite had 134 passing tests and 94.98% coverage.

Those stages still had to be launched separately. There was no single release
receipt proving that all expected artifacts came from one isolated run, no CI
step exercising the complete workflow, and no final deployment, demo,
maintenance, troubleshooting, completion, or real-pilot handoff.

## Files and functions changed

### `src/release.py`

`ReleaseConfig` collects all settings for a stable demonstration: destination,
unique run version, dates, seed, synthetic at-risk fraction, rolling window,
model split, and forest size. `ReleasePaths.from_root()` keeps every stage under
one self-contained directory.

`require_empty_destination()` is the safety gate. A new or empty directory is
accepted; an existing file or non-empty directory is rejected. The function
does not delete anything. This makes reruns explicit and preserves evidence.

`run_release_demo()` calls the existing stage APIs in order:

1. generate five consistent synthetic tables;
2. clean and validate those tables;
3. build daily features and current explainable scores;
4. create analytics tables and charts;
5. train/evaluate three synthetic-label baselines with held-out agents;
6. validate the dashboard data contract;
7. create an operational baseline, health report, and minimized database run;
8. verify the artifact set and render all four dashboard pages; and
9. write `release_manifest.json`.

The orchestrator reuses production functions instead of copying their logic.
One correction therefore benefits a manual stage, tests, the UI, and the release
path together.

`validate_release_artifacts()` requires 35 stage artifacts and checks that the
generation manifest says `synthetic_only: true`. The release manifest is the
36th artifact. `verify_dashboard_pages()` supplies absolute generated-data paths
to Streamlit's `AppTest`, renders Overview, Agent detail, Data quality, and Model
evaluation, rejects exceptions, and requires the responsible-use warning on
every page.

### Tests and automation

`tests/test_release.py` checks path isolation, no-overwrite behavior, run-version
validation, missing/corrupt/non-synthetic artifacts, a missing UI entrypoint,
the complete pipeline and database contract, and the command-line summary.

`tests/test_documentation.py` catches broken local Markdown links and prevents
the README, sprint ledger, roadmap, package version, and runtime release version
from disagreeing about the final status.

`.github/workflows/tests.yml` now installs dependencies, compiles Python, runs
Ruff, enforces at least 90% total source coverage, executes a complete synthetic
release, and confirms that generated outputs remain untracked.

### Release and handoff documentation

- `README.md` makes the one-command workflow and synthetic-only boundary the
  front door.
- `CHANGELOG.md` records version 1.0.0.
- `docs/release_guide.md` covers clean setup, dashboard launch, a five-minute
  demonstration, manual stages, maintenance, recovery, and troubleshooting.
- `docs/completion_matrix.md` maps all nine sprints and product requirements to
  implementation evidence.
- `docs/pilot_requirements.md` lists the governance, validity, privacy, security,
  integration, operations, and participant protections required before real use.
- Architecture, business requirements, roadmap, and sprint log now agree on the
  supported release boundary and completion state.

## Beginner concepts

### Orchestration

Orchestration means coordinating existing tasks in the correct order. The
release module does not recalculate features or scores itself. It provides the
inputs and output paths to the modules that already own those responsibilities,
then checks their results. This keeps one source of truth for each calculation.

### Artifact contract

An artifact is an output file such as a cleaned CSV, chart, model, or health
report. An artifact contract is the precise set a successful release promises.
Checking only that “some files exist” can hide a skipped stage. Checking all 35
stage paths makes an incomplete run fail visibly.

### Manifest

A manifest is a machine-readable receipt. Affectra's final JSON manifest records
the release/configuration versions, seed, row counts, quality totals, score
distribution, held-out model split, operational checks, rendered UI pages,
artifact paths, and limitation. A reviewer can inspect it without reading logs.

### Safe reruns and idempotency

An idempotent operation can be repeated without accumulating an unintended
effect. Affectra's immutable database versions and no-overwrite JSON writers
make accidental repetition fail. At the release-directory level, the safe rule
is even simpler: choose a new destination and version for every run. Existing
evidence is never silently merged or deleted.

### Continuous integration

Continuous integration (CI) runs the same quality gates on a clean hosted
machine after a push or pull request. It catches missing local assumptions such
as an untracked input file or dependency. Local success and CI success are both
recorded because they answer different questions.

### Release readiness versus pilot readiness

Release readiness here means the synthetic portfolio works as specified. Pilot
readiness would mean real people, data, policies, infrastructure, and impacts
have been governed and evaluated. A strong synthetic metric cannot cross that
gap. `docs/pilot_requirements.md` keeps those unresolved decisions explicit.

## How data flows

```text
ReleaseConfig + new output directory
                 |
                 v
       seeded synthetic generator
                 |
                 v
   validation/cleaning + quality report
                 |
                 v
 daily features + transparent current scores
          |                      |
          v                      v
 aggregate analytics      grouped ML evaluation
          |                      |
          +-----------+----------+
                      v
        dashboard contract + four-page render
                      |
                      v
       minimized persistence + health checks
                      |
                      v
   artifact/synthetic-only verification (35 files)
                      |
                      v
            release_manifest.json (#36)
```

Every branch uses generated data. The ML target joins only after observable
features are built, and complete agents—not random rows—are held out for testing.

## Reproduce the work

Create a fresh Python 3.12 environment from a clone:

```bash
git clone https://github.com/pwill0217/Affectra-v2.git
cd Affectra-v2
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pip check
```

Run all code-quality gates:

```bash
python -m ruff check .
python -m compileall -q src tests
python -m pytest --cov=src --cov-report=term-missing --cov-fail-under=90
```

Run the complete release once:

```bash
python -m src.release
```

If `data/release-demo/` already contains evidence, preserve it and select new
names:

```bash
python -m src.release \
  --output-root data/release-demo-2 \
  --run-version release-demo-2
```

Launch the release dashboard locally:

```bash
export AFFECTRA_SCORED_DIR=data/release-demo/scored
export AFFECTRA_PROCESSED_DIR=data/release-demo/processed
export AFFECTRA_MODELS_DIR=data/release-demo/models
python -m streamlit run src/app.py
```

Read `docs/release_guide.md` for Windows commands and the complete demonstration
and maintenance workflow.

## Test and smoke evidence

A fresh Python 3.12.14 environment installed the bounded runtime and development
dependencies. `pip check` reported no broken requirements. Git diff validation,
Ruff linting, and compilation of `src` and `tests` passed. All 145 tests passed
in 26.55 seconds with 95.18% total source coverage, above the required 90% gate;
`release.py` reached 97% coverage. The suite includes two actual full release
runs as well as focused unit, contract, documentation, and UI tests.

The default release smoke used Python 3.12, seed 606, 30 synthetic agents, 30
days, and a 0.5 generated at-risk fraction. It created 30 agent rows, 30 time-off
rows, 33,151 calls, 33,151 transcripts, and 900 daily labels. Cleaning preserved
all 67,262 source rows with zero corrections and zero relationship warnings; it
reported 1,317 IQR outliers without deleting them. Scoring produced 900
agent-day rows and 30 latest scores: 13 Low, 17 Moderate, and 0 High. Analytics
created all nine outputs, including four standalone charts.

The model split used 660 rows/22 complete training agents and 240 rows/8 held-out
agents with zero overlap. Test labels contained 235 negatives and 5 positives.
Logistic regression ranked highest by balanced accuracy: 0.9042 accuracy,
0.8532 balanced accuracy, 0.1538 precision, 0.8000 recall, 0.2581 F1, 0.9574
ROC AUC, 0.0584 Brier score, 0.1703 log loss, and 0.0927 expected calibration
error. Its confusion counts were 213 true negatives, 22 false positives, 1 false
negative, and 4 true positives. The tiny generated positive count makes these
metrics unstable; they demonstrate evaluation code, not real-world validity.

All five operational checks were true, status was healthy, and no drift alerts
appeared against the newly inspected synthetic baseline. SQLite stored one run,
30 minimized score snapshots, and three model summaries. All four UI pages
rendered with their responsible-use warning. The artifact contract found all 35
stage files and the final manifest brought the verified total to 36. Generated
datasets, databases, models, charts, health evidence, and logs remained ignored
by Git.

A separate live-server check started Streamlit on loopback, received `ok` from
`/_stcore/health`, and received HTTP 200 with HTML from the application root.
The server was then stopped cleanly.

## Decisions and tradeoffs

- A direct Python API orchestrator is easier to test and safer to refactor than
  a shell script that only checks process exit codes.
- One self-contained release directory prevents default manual-stage files from
  being mixed with release evidence.
- The command refuses non-empty destinations instead of offering a destructive
  cleanup flag. Preserving evidence is worth requiring an explicit new name.
- Streamlit page tests are part of the release, even though they make it slower,
  because a data pipeline is not complete if its user-facing pages cannot load.
- The artifact list is explicit. Adding or intentionally removing an output
  requires a reviewed contract change instead of passing silently.
- Dependency ranges remain bounded rather than fully locked across platforms.
  A fresh install plus CI tests actual compatibility; a production deployment
  would normally add a reviewed lock file and software supply-chain controls.
- The local Streamlit/SQLite deployment remains the supported demonstration.
  Authentication and network hosting are not simulated because fake controls
  could encourage unsafe use.
- Generated metrics are documented precisely but never promoted as evidence of
  human burnout detection.

## Blockers

None for the synthetic portfolio release. No real/private employee data,
credential, destructive repository operation, or unresolved policy decision was
needed to complete Sprints 0 through 8.

A real-world pilot remains blocked by decisions that software cannot safely
guess: purpose and prohibited uses, jurisdiction/lawful basis, an ethical real
outcome, acceptable error tradeoffs, participating population, retention,
production roles, hosting/vendors, licensing, monitoring limits, appeals, and
go/no-go authority. These are listed in `docs/pilot_requirements.md` and are not
claimed as completed work.

## What comes next

There is no Sprint 9 in the agreed roadmap. The synthetic portfolio is complete.
Normal maintenance can use the release guide and CI gate. Any proposal to handle
real data or support a pilot starts with the human-owned pilot checklist, not
with model deployment. Only after those gates are approved should a new,
explicitly scoped backlog be created.
