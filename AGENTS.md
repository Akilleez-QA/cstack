# Working on Cstack

Start with [README.md](README.md), [CONTRIBUTING.md](CONTRIBUTING.md) and the
[documentation index](docs/README.md). Keep claims tied to measured results or
cited sources; distinguish implemented behavior from plans and unverified outcomes.

## Layout

| Path | Purpose |
| --- | --- |
| `poodo_core/`, `contracts/`, `schemas/` | Control core and its contracts |
| `adapters/`, `extensions/` | Capability ports and domain composition |
| `aors/`, `tools/` | Fleet definitions, agent tooling and maintenance checks |
| `foundations/`, `vendor/`, `reasoning/` | Included domain packages and upstream snapshots |
| `examples/`, `products/`, `workshop/` | Example inputs and configuration material |
| `tests/` | Root unittest suite and synthetic fixtures |
| `docs/` | Engineering records, guides and rules |
| `ci/`, `.github/` | Local check scripts, CI and contribution templates |

Python entry points and composition stay at the root; see the
[layout exception](docs/README.md#repository-layout-exception). Respect the
[Foundation boundaries and source pins](docs/icd/icd-foundations.md) when changing
included packages. Do not refresh unrelated vendored files or pins.

## Local checks

Run from the checkout root. [CI](.github/workflows/ci.yml) sets up Python 3.12
with uv and installs the pinned root and CI dependencies:

```sh
uv venv --python 3.12 .venv
. .venv/bin/activate
uv pip install --python .venv -r requirements.txt -r ci/requirements.txt
npm ci --prefix adapters/workcell-toolchain --ignore-scripts --no-audit --no-fund
```

Run the same checks as CI (details in
[run CI checks locally](docs/guides/how-to/run-ci-locally.md)):

```sh
python -B -m unittest discover -s tests
bash ci/run-local.sh python links
bash ci/scan-secrets.sh
```

The local runner checks root and Foundation unittest suites in normal and optimized
modes, then documentation links. The secret scan requires TruffleHog; CI installs
version 3.99.7. Follow [Contributing](CONTRIBUTING.md) for the gitleaks pre-commit
hook. Report commands, exit codes, Python version and skipped or unverified checks
in the PR; passing tests do not establish engineering, safety or compliance approval.

## Change rules

- Subtract first: use existing documentation and checks before adding machinery.
- Keep each PR to one concern and about 400 changed lines maximum. Follow
  [Contributing](CONTRIBUTING.md) and the [PR template](.github/pull_request_template.md),
  including disclosure of AI assistance.
- Never edit expected test results to make tests pass. Fix the implementation;
  explain any independently justified expectation correction in the PR.
- Do not add code comments. Follow the [code comment rule](docs/rules/no-comments.md)
  and put durable rationale in documentation and the PR body.
- Never commit secrets or personal data. Use synthetic data only in examples,
  fixtures and published evidence; sanitize traces and paths. Use
  [Security](SECURITY.md) for vulnerability reporting.
- Make only measured or cited claims. Record the checked revision and scope with
  verification evidence; do not invent features or imply that a source pin proves
  correctness.

## Documentation

Use the [existing documentation layout](docs/README.md):

- `docs/requirements/`: requirements.
- `docs/architecture/`: design, components and boundaries.
- `docs/icd/`: interface contracts and source-pin boundaries.
- `docs/verification/`: coverage, measurements, results and limitations.
- `docs/configuration/`: versions, baselines and change control.
- `docs/guides/`: tutorials, how-to guides, reference and explanation. The reference pages
  (commands, configuration, environment) state defaults from code; update them with the code.

Add every new document to the [documentation index](docs/README.md). `tools/check_links.py`
checks links and backticked paths in the README, `docs/`, `contracts/` and the area READMEs.

Keep the root `EXPORT-MANIFEST.json` entry for each changed or added export file
accurate: regenerate it with `python -B tools/build_export_manifest.py`. Do not include local environments or generated runtime data in it.

## License

Contributions are licensed [GPL-3.0-only](LICENSE). As stated in the
[README](README.md#license), commercial licenses are available from
Refrigeration.AI via craig@nh3.biz.
