# Contributing

1. Open an issue first for anything larger than a fix.
2. Keep each PR to one concern and about 400 changed lines.
3. List every local check you ran in the PR body, with a one-line result, for example `python -B -m unittest discover -s tests` and `Ran N tests, OK`.
4. Do not change expected results in tests to make them pass. Fix the code, or explain in the PR why the expectation was wrong.
5. Never commit secrets. Run `pre-commit install` once per clone; it runs gitleaks with `.gitleaks.toml`.
6. Put the reasoning in the PR body and commit message rather than in code comments.

By contributing you agree your work is licensed under GPL-3.0-only.
