# Contributing

## Development setup

You need Python 3.11 or newer and Git. There is nothing to install: the package, bridge, tests and tools use the standard library only. CI uses Python 3.12 through `uv`; to match it locally, prefix commands with `uv run --no-project --python 3.12`.

## Rules

1. Open an issue first for anything beyond a small fix, using the problem-report or change-request template.
2. One concern per pull request, about 400 changed lines or less.
3. Conventional Commits: `type(scope): imperative summary`, 72 characters max. AI-written changes carry an `Assisted-by: <tool>` trailer.
4. Code contains no comments. Put rationale in `docs/` or the commit message.
5. Never edit expected test results by hand. If a result changes, regenerate it with the tool that produces it and say so in the PR.
6. Every new requirement gets an entry in `docs/requirements/requirements.md`, a row in `docs/verification/verification-matrix.md` and an allocation in `docs/architecture/architecture.md`. Behaviour without a test goes in the SRS gap table, not in a requirement.
7. Keep every result an observation with Evidence, including tool errors.

## Local checks (identical to CI)

Run from the repository root after edits, in this order:

```sh
python -B tools/gen_docs.py
python -B tools/build_manifest.py
python -B -m unittest discover -s tests -t .
python -B -O -m unittest discover -s tests -t .
```

`gen_docs.py` is only needed when schemas, tool code, error messages or limits change. `build_manifest.py` is needed after any change outside `.github/`. CI also runs gitleaks over the full history; run `gitleaks git --redact --no-banner --exit-code 1 --config .gitleaks.toml .` locally before pushing if you have it. The test suite includes `tests/test_docs_trace.py`, which fails on an untraced requirement, a dead Markdown link or a stale generated page.

## Pull requests and review

The [pull request template](.github/pull_request_template.md) is the peer-review record: it lists reviewers (agent review is labelled as not independent), findings and the outcome. The maintainer merges after checking the head commit. For documentation changes, use the family documentation checklist and keep the [docs index](docs/README.md) complete.

Contributions are accepted under GPL-3.0-only.
