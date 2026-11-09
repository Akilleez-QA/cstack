# Contributing

## Rules

1. Open an issue first for anything beyond a small fix. Use the problem-report or change-request template.
2. One concern per pull request, about 400 changed lines or less.
3. Conventional Commits: `type(scope): imperative summary`, 72 characters max. AI-written changes carry an `Assisted-by: <tool>` trailer.
4. Code contains no comments. Put rationale in `docs/`.
5. Never edit expected test results. If a result changes, regenerate it with the tool that produces it and say so in the PR.
6. Every new requirement gets an entry in `docs/requirements/requirements.md` and a row in `docs/verification/verification-matrix.md` in the same PR. Untested behaviour goes in the requirements' gap list.

Contributions are accepted under GPL-3.0-only.

## Development setup

Python 3.11 or newer, run from the repository root. Nothing is installed for the bridge and tools. The offline producer and its four video tests need NumPy, opencv-python-headless and scenedetect, which the README's `uv` commands fetch.

## Local checks (the same as CI)

Run after every change, in this order:

```sh
python -B tools/build_manifest.py
python -B -m unittest discover -s tests -t .
python -B -O -m unittest discover -s tests -t .
git diff --exit-code SOURCE-MANIFEST.json
```

CI runs the same commands with `uv run --no-project --python 3.12`, plus gitleaks (see the [test plan](docs/verification/test-plan.md#3-test-environment-and-exact-ci-commands)). For changes to `foundation_film/filmstats.py`, also run the two full-dependency commands in the README and expect no skips.

The manifest covers every file outside the root `.github/` tree, documentation included, so rebuild it after any such change.

## Pull requests and peer review

The pull request is the review record. Fill in the [template](.github/pull_request_template.md): requirement and interface impact, commands run with results, and reviewers. Agent review is not independent review. The maintainer merges after CI passes. For documentation baselines, paste the family documentation checklist into the PR and tick each line that was checked. Severity levels S1 to S4 are defined in the [software management plan](docs/plan/software-management-plan.md#9-problem-reporting-and-severity).
