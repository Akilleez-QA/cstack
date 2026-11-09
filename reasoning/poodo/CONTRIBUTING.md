# Contributing to POODO

Describe the concrete problem, proposed behavior, and evidence that would distinguish improvement from extra ceremony. Small, reproducible examples are useful.

## Development

Python tooling depends only on the standard library and pinned PyYAML. You need Python 3.10 or newer; CI uses 3.10 and 3.14.

### Local checks

Run from the checkout root. These are the exact steps in [the CI workflow](.github/workflows/checks.yml). Use one virtual environment per Python version to match the CI matrix.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/validate_skill.py
python -m unittest discover -s evals -p 'test_*.py' -v
python scripts/check_capsule.py evals/fixtures/valid-capsule.yaml
python tools/check_trace.py
python -m unittest discover -s tools -p 'test_*.py' -v
```

These checks validate package and capsule structure, checker regressions and the documentation trace. They do not run a behavioral evaluation. The [test plan](docs/verification/test-plan.md) explains each one.

Preserve explicit invocation and the existing method and optional-mode boundary unless proposing a clearly identified method revision. Explain effects on evidence separation, authority, research, divergence, contradiction handling, and continuity. Keep client-specific capabilities conditional on actual availability.

For checker fixes, include a minimal failing input and a regression test with meaningful assertions. For behavioral claims, follow the [evaluation guide](docs/guides/how-to/evaluation.md); passing syntax checks is insufficient.

### Keeping the engineering records true

A change that alters behavior updates the [requirements](docs/requirements/requirements.md) and the [verification matrix](docs/verification/verification-matrix.md) in the same pull request. Add a test for a new rule, or register it as an untested gap. `python tools/check_trace.py` fails if a requirement has no matrix row, a matrix row names a missing test, a new test traces to nothing, or a relative link is dead. Release documents are generated, not edited; see TP-3 in the test plan.

## Issues and pull requests

Use the [problem report](.github/ISSUE_TEMPLATE/problem-report.md) or [change request](.github/ISSUE_TEMPLATE/change-request.md) template. Include the relevant version or commit, expected behavior, actual behavior, reproduction steps, and a sanitized fixture or trace. Separate observed failures from suspected causes. State which checks ran and which outcomes remain untested.

Every change goes through a pull request. The [pull request template](.github/pull_request_template.md) is the peer-review record: it lists the checks run, the reviewers (human or agent; agent review is not independent), the findings and the outcome. The maintainer merges after CI passes. A pull request that changes documentation also pastes and ticks the [documentation checklist](docs/rules/documentation-checklist.md).

Keep examples synthetic or explicitly authorized for publication. Remove secrets, private paths, customer details, and unrelated conversation records before sharing. Cite external foundations and preserve their licenses when including third-party material.

The existing behavioral thresholds are proposals. Any adopted thresholds and rubric applicability must be fixed before examining trial outcomes.
