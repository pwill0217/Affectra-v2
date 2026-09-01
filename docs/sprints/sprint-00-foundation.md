# Sprint 0 Tutorial: Project Foundation

**Status:** Complete  
**Date:** 2026-09-01  
**Goal:** Turn the original experiment into a reproducible project that a
beginner can install, test, understand, and extend safely.

## What existed before this sprint

The original repository had a useful synthetic-data generator, a short README,
a large environment export, an empty business-requirements document, and an
accidentally committed `.DS_Store` file. The generator imported Faker, but Faker
was missing from the requirements file. There were no automated tests, sprint
plan, architecture description, or continuous-integration workflow.

That is a normal prototype stage: the main idea works, but another developer
does not yet have a reliable path for reproducing it.

## What changed

### 1. The product was defined before adding more code

`docs/business_requirements.md` now states the problem, intended users,
functional and nonfunctional requirements, completion criteria, risks, and
explicit non-goals. This prevents the project from drifting into an employee
surveillance or medical-diagnosis tool.

Beginner lesson: requirements describe **what success means**. They let you
decide whether a feature belongs before spending time coding it.

### 2. The repository became reproducible

`requirements.txt` now lists direct runtime dependencies instead of every
transitive package installed on one computer. `requirements-dev.txt` separates
testing and linting tools. `.python-version` and `pyproject.toml` state the
supported Python version and shared tool settings.

Beginner lesson: a virtual environment isolates this project's packages from
other Python projects. A dependency manifest lets another machine install the
same categories of tools without copying your entire computer state.

### 3. The source became an importable package

`src/__init__.py` marks the source directory as a package. The existing data
generator was copied, formatted, typed, and given a Faker seed. Its business
behavior remains the starting point for the dedicated data sprint.

Beginner lesson: code inside functions can be imported and tested without
manually running the whole program. The final `if __name__ == "__main__"` block
still lets the file work as a script.

### 4. Tests protect the starting behavior

`tests/test_data_generator.py` checks:

- required agent columns and unique identifiers;
- valid time-off foreign keys and ranges;
- one-to-one call/transcript relationships;
- valid numeric ranges and sentiment categories; and
- correct sentiment behavior at low, middle, and high difficulty.

Beginner lesson: a unit test runs a small piece of code and compares the result
with an expectation. A relationship test is especially useful for data work:
two CSV files can each look valid while their keys fail to match.

### 5. GitHub Actions was added

`.github/workflows/tests.yml` creates a clean Python environment, installs the
dependencies, and runs tests for every push and pull request.

Beginner lesson: a test that only passes on your laptop may depend on an
unrecorded file or package. Continuous integration repeats the setup on a clean
machine and catches that problem early.

### 6. The work was divided into testable sprints

`docs/SPRINT_ROADMAP.md` defines Sprints 0 through 8 and gives every sprint the
same definition of done: implementation, tests, tutorial, log entry, and push.
`SPRINT_LOG.md` is the short index; this file is the detailed learning record.

## Follow along from a fresh clone

### Step 1: create an isolated environment

```bash
python -m venv .venv
```

This asks Python's built-in `venv` module to create a local environment in the
`.venv` folder. That folder is ignored by Git because it can be recreated.

### Step 2: activate it

macOS or Linux:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Your terminal should now show `(.venv)`. Commands such as `python` and `pip`
will use this project's environment.

### Step 3: install runtime and development packages

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Using `python -m pip` makes it clearer which Python interpreter receives the
packages.

### Step 4: run a small test suite

```bash
python -m pytest
```

Pytest discovers files named `test_*.py`, runs functions beginning with
`test_`, and reports a failure if an `assert` expression is false.

### Step 5: generate the demo data

```bash
python -m src.data_generator
```

Open `data/synthetic/` and inspect the four CSVs. They are not committed because
generated data should come from source and configuration, not duplicated files.

## Verification performed

- Ruff reported `All checks passed`.
- All 5 automated tests passed with 83% source-line coverage.
- The generator created all four expected CSV files: 50 agents, 50 time-off
  records, 58,998 calls, and 58,998 linked transcripts.
- Identifiers and table relationships were checked by automated tests.
- Python source was compiled to catch syntax errors.
- The repository excludes generated data, secrets, environments, and OS files.

## Decisions and tradeoffs

- Python 3.12 is the baseline because it is modern and broadly supported by the
  planned data stack.
- Version ranges are used for direct dependencies so the project is readable;
  a lock file can be introduced at release time for exact production builds.
- Synthetic data remains the default. Kaggle is not needed yet because using a
  third-party dataset would add licensing, schema, and domain-fit decisions
  without helping the foundation sprint.
- The explainable score and experimental ML model remain separate so users can
  see what drives a result.

## Blockers

The GitHub integration could not create a repository. The owner created the
empty `pwill0217/Affectra-v2` repository, resolving the only blocker before code
was pushed. No Sprint 0 blockers remain.

## Next sprint

Sprint 1 will turn `data_generator.py` into a configurable, reproducible data
pipeline. It will add a command-line interface, data dictionary, schema checks,
realistic multi-day pressure patterns, explicit synthetic research labels, and
deeper tests. It will not download real employee data.
