# Working in Foundation Film

Read [README.md](README.md), [CONTRIBUTING.md](CONTRIBUTING.md), and the relevant
contract before editing. Use [SUPPORT.md](SUPPORT.md) for help and
[SECURITY.md](SECURITY.md) for private vulnerability reports.

## Scope and contracts

This is a Python source-tree project. The bridge and acceptance functions use only
the standard library; no package installation is needed for their local checks.
CI uses Python 3.12. Keep optional video dependencies outside the bridge.

- `foundation_film/` contains the six read-only tools and domain measurements.
- `foundation_film_bridge/` provides bounded, line-delimited stdio JSON-RPC;
  `schemas.py` defines the tool inventory and input/output contracts.
- `foundation_film/filmstats.py` is the optional offline video producer, with lazy
  NumPy, OpenCV and PySceneDetect imports; it opens local videos and retains frames.
- `tests/` uses Python's `unittest` runner, with optional producer tests.
- `tools/build_manifest.py` generates the source manifest and prints host pins.
- `docs/` holds requirements, architecture, interface, verification and guides.

Preserve integer milliseconds and milli-unit measurements, schema bounds, input
hashes, Evidence receipts and the `boundary.observation_only` marker. A verdict
is an observation, not an acceptance decision or formal proof. Keep the bridge
read-only, without network access or caller-controlled file paths. Its protocol
is JSON-RPC, not MCP. Evidence citation paths are references, not files to open.

Read [the interface contract](docs/icd/icd-cstack.md) for bridge or schema changes
and [the architecture](docs/architecture/architecture.md) for producer boundaries.
Keep requirements in [requirements.md](docs/requirements/requirements.md) aligned
with [the verification matrix](docs/verification/verification-matrix.md); every
new requirement needs a matrix row, and untested behaviour belongs in the
requirements' gap list. Documentation follows the family standard indexed in
[docs/README.md](docs/README.md). Keep changes to one concern, about 400 lines
or less; open an issue first for work beyond a small fix.

## Verification

Run from the repository root after edits, in this order:

```sh
python -B tools/build_manifest.py
python -B -m unittest discover -s tests -t .
python -B -O -m unittest discover -s tests -t .
```

For offline producer changes, also run both full-dependency checks from README:

```sh
uv run --no-project --python 3.12 --with numpy --with opencv-python-headless --with scenedetect python -B -m unittest discover -s tests -t .
uv run --no-project --python 3.12 --with numpy --with opencv-python-headless --with scenedetect python -B -O -m unittest discover -s tests -t .
```

CI runs normal and optimized tests through `uv` on Python 3.12, Gitleaks, and
manifest regeneration followed by `git diff --exit-code SOURCE-MANIFEST.json`.
See [the workflow](.github/workflows/ci.yml). Record the tested revision, commands,
exit statuses, failures, skips and unrun scope. Skipped optional tests do not
verify the video producer; interrupted or missing checks do not pass.

## Source and release boundaries

[SOURCE-MANIFEST.json](SOURCE-MANIFEST.json) records shipped paths and SHA-256
hashes outside the root `.github/` tree. Regenerate it after every change to
covered files, including documentation additions.
The inventory test checks file membership and bytes; the generator excludes
the root `.github/` tree, `.git`, `__pycache__`, `.pyc`, the manifest itself
and `PR_BODY.md`. Keep temporary
artifacts and dependency environments outside the checkout so they are not
included. Never hand-edit hashes or weaken the inventory test to obtain a pass.

Follow [configuration management](docs/configuration/configuration-management.md):
consumers must repin the manifest hash, file count and canonical tool inventory
hash when updating their vendored source. Tags require owner approval. CI runs
Gitleaks on the full history; run it locally before pushing when you can.

Preserve GPL-3.0-only terms, [NOTICE.md](NOTICE.md), and the documented Endoforge
producer provenance. Keep secrets and private media out of commits. Put rationale
in documentation; add no code comments. Never edit expected test results to
obtain a pass. Use Conventional Commit subjects of at most 72 characters and an
`Assisted-by: <tool>` trailer for AI-written changes, as CONTRIBUTING.md requires.
