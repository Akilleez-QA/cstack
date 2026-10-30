# Contributing

1. Open an issue first for anything beyond a small fix.
2. One concern per pull request, about 400 changed lines or less.
3. Conventional Commits: `type(scope): imperative summary`, 72 characters max. AI-written changes carry an `Assisted-by: <tool>` trailer.
4. Code contains no comments. Put rationale in `docs/`.
5. Never edit expected test results. If a result changes, regenerate it with the tool that produces it and say so in the PR.
6. After any change run `python -B tools/build_manifest.py`, then `python -B -m unittest discover -s tests -t .` and the same with `-O`.
7. Every new requirement gets a row in `docs/verification/verification-matrix.md`.

Contributions are accepted under GPL-3.0-only.
