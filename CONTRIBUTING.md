# Contributing

1. Open an issue first for anything larger than a fix.
2. Keep each PR to one concern and about 400 changed lines.
3. List every local check you ran in the PR body, with a one-line result, for example `python -B -m unittest discover -s tests` and `Ran N tests, OK`. [Run CI checks locally](docs/guides/how-to/run-ci-locally.md) lists the checks CI runs.
4. Do not change expected results in tests to make them pass. Fix the code, or explain in the PR why the expectation was wrong.
5. Never commit secrets. Run `pre-commit install` once per clone; it runs gitleaks with `.gitleaks.toml`.
6. Put the reasoning in the PR body and commit message rather than in code comments.

## Agent branches

Each agent must use its own branch created from trunk (`main`). Never allow two
agents to push to the same branch. Integrate agent work by rebasing onto trunk
only; do not rebase onto another agent's branch or merge agent branches together.
Preserve published history: if rebasing would require a force-push, create a fresh
branch from trunk and replay the work before publishing it. Existing review and
branch protection requirements still apply.

See [the branch ownership proposal](https://github.com/Akilleez-QA/cstack/issues/40).

By contributing you agree your work is licensed under GPL-3.0-only.
