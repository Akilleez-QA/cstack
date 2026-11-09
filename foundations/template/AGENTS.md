# Working in Foundation Template

Read [README.md](README.md), [CONTRIBUTING.md](CONTRIBUTING.md), and the relevant
contract before editing. Use [SUPPORT.md](SUPPORT.md) for help and
[SECURITY.md](SECURITY.md) for private vulnerability reports.

## Scope and contracts

This is a Python source-tree project using only the standard library. No package
installation is needed for the documented workflow. The template currently exposes
one placeholder tool, `echo_observation`, through a stdio JSON-RPC bridge.

- `foundation_template/` holds pure domain functions over caller-supplied values.
- `foundation_template_bridge/` implements the bridge and its schemas.
- `foundation_template_bridge/schemas.py` defines the tool inventory and schemas.
- `tests/` contains unit, bridge, and input-limit tests using `unittest`.
- `tools/build_manifest.py` generates the source manifest and prints host pins.
- `tools/check_trace.py`, `tools/gen_docs.py` and `tools/gen_reports.py` check the
  requirement trace and generate the tool catalog, test report and version description.
- `docs/` contains the family documentation set that new Foundations copy.

Preserve read-only observations: a verdict is not an acceptance decision. Keep
`boundary.observation_only`, Evidence in `receipt.evidence`, and the request hash
in `receipt.input_sha256` on tool results, including tool errors. Keep execution
bounded, with no network or caller-controlled paths. Preserve rejection of inputs
that exceed frame, depth, node, string, or integer limits.

Read [requirements](docs/requirements/requirements.md),
[architecture](docs/architecture/architecture.md), and the
[Cstack interface contract](docs/icd/icd-cstack.md) for changes to these boundaries.
The bridge starts from the repository root with:

```sh
python -B -m foundation_template_bridge
```

Every new requirement needs an SRS entry, a row in
[the verification matrix](docs/verification/verification-matrix.md) and an SDD
allocation; `tests/test_docs_trace.py` fails otherwise. Keep schema, tool inventory, implementation, and
verification consistent when changing the interface.

## Verification

Run from the repository root after edits, in this order:

```sh
python -B tools/gen_docs.py
python -B tools/build_manifest.py
python -B -m unittest discover -s tests -t .
python -B -O -m unittest discover -s tests -t .
```

CI uses Python 3.12 through `uv run --no-project --python 3.12`, runs both test
modes, scans with Gitleaks, and regenerates the manifest to check for a diff.
See [the workflow](.github/workflows/ci.yml). Report the commands run, interpreter
version, outcomes, and any unrun checks. Missing or interrupted checks do not pass.
Do not weaken checks or edit expected test results to obtain a pass.

## Source and release boundaries

[SOURCE-MANIFEST.json](SOURCE-MANIFEST.json) records SHA-256 hashes for every
shipped source file outside the root `.github/` tree. Regenerate it with the
command above after any change to covered files, including documentation, and
include the updated manifest with the change. The inventory
includes files outside Git's tracked set; avoid leaving temporary artifacts in
the repository. The manifest excludes itself, the root `.github/` tree, `.git`,
`__pycache__`, and `.pyc` files. Tests compare its inventory and hashes with the working tree.

The manifest tool prints the manifest hash, file count, and canonical tool
inventory hash. Consumers must repin when updating their vendored copy, in the
same change. Follow
[configuration management](docs/configuration/configuration-management.md);
creating a release tag requires owner approval.

Open an issue first for work beyond a small fix. Keep each pull request to one
concern and about 400 changed lines or less. Use the
[pull request template](.github/pull_request_template.md). When committing, use
`type(scope): imperative summary` with a maximum 72-character summary and an
`Assisted-by: <tool>` trailer for AI-written changes.

Preserve GPL-3.0-only terms and [NOTICE.md](NOTICE.md). Keep secrets out of commits;
CI scans history with Gitleaks; scan locally before pushing.
Put rationale in `docs/`; add no code comments. Never edit expected test results;
if results must change, follow CONTRIBUTING.md's regeneration and PR disclosure
requirements.
