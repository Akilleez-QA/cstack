# Working in Foundation Refrigeration

Read [README.md](README.md), [CONTRIBUTING.md](CONTRIBUTING.md), and the relevant
contract before editing. Use [SUPPORT.md](SUPPORT.md) for help and
[SECURITY.md](SECURITY.md) for private vulnerability reports.

## Scope and contracts

This is a Python 3.11+ source-tree project. The domain package, bridge, and local
checks use the standard library; no package installation is needed for them.

- `foundation_refrigeration/` contains domain functions, units, evidence, and data.
- `foundation_refrigeration/invariants.py` checks local Python claims and binds
  results to package source and data hashes captured at import.
- `foundation_refrigeration_bridge/` provides seven read-only tools over
  line-delimited stdio JSON-RPC; `schemas.py` defines their schemas.
- `foundation_refrigeration/data/` holds saturation tables, exposure limits,
  taxonomy, process-safety thresholds, and open decisions.
- `tests/` uses Python's `unittest` runner; `golden/` holds reference points.
- `tools/` contains the manifest, golden-reference, trace-check and documentation
  generators.

Preserve the distinction between observations and acceptance decisions. Results
do not authorize plant actions, establish compliance, or diagnose readings as
normal or abnormal. Keep cited exposure limits separate from caller policy set
points. Preserve Evidence on every successful result, and input hashes and the
boundary on every receipt, including tool errors (which carry empty Evidence).

Read [requirements](docs/requirements/requirements.md),
[architecture](docs/architecture/architecture.md), and the
[interface contract](docs/icd/icd-cstack.md) for changes in those areas. Keep the
local Python invariant API separate from bridge schemas and receipts. Preserve
bridge input bounds, the read-only effect, and execution without network access
or caller-controlled paths. Gauge pressure requires an explicit atmosphere;
blend saturation requires a bubble/dew side. Refuse extrapolation and retain
table provenance and error allowances. Restart invariant consumers after source
or data changes so their imported hashes match the new library.

## Verification

Run from the repository root after edits, in this order:

```sh
python -B tools/gen_docs.py
python -B tools/build_manifest.py
python -B -m unittest discover -s tests -t .
python -B -O -m unittest discover -s tests -t .
```

CI uses Python 3.12 and runs normal and optimized tests, Gitleaks, and manifest
regeneration followed by `git diff --exit-code SOURCE-MANIFEST.json`. See
[the workflow](.github/workflows/ci.yml). Report the commands, Python version,
exit statuses, failures, and unrun checks; do not report missing checks as passed.
Every new requirement needs an SRS entry, a row in the
[verification matrix](docs/verification/verification-matrix.md) and an SDD
allocation; `tools/check_trace.py` (run by `tests/test_docs_trace.py`) fails
otherwise. Exposure-limit and safety wording must stay consistent with
[Limitations and safety-relevant use](docs/guides/explanation/limitations.md).

## Source and release boundaries

[SOURCE-MANIFEST.json](SOURCE-MANIFEST.json) records shipped source-file SHA-256 hashes outside the root `.github/` tree.
[The generator](tools/build_manifest.py) includes new documentation such as this
file. Regenerate it after every change to covered files; never hand-edit hashes. It excludes the root `.github/` tree, Git
internals, Python caches and bytecode, itself, and `PR_BODY.md`. Avoid leaving
scratch files in the tree: other files enter the manifest, and tests compare its
inventory and hashes exactly. Consumers must repin when covered files change;
see [configuration management](docs/configuration/configuration-management.md).

Never edit expected test results or weaken checks to obtain a pass. Reference
changes must use the producing tool and be explained in the PR.
`tools/compute_golden.py` requires CoolProp 8.0.0 and a `--date` argument; it is
separate from the standard-library test workflow. Preserve data provenance;
agreement with an oracle is not experimental validation.

Open an issue before work beyond a small fix. Keep each PR to one concern and
about 400 changed lines or fewer. Follow Conventional Commits with
`type(scope): imperative summary`, at most 72 characters, and an
`Assisted-by: <tool>` trailer for AI-written changes. Tags require owner approval;
follow the documented secret-scanning policy before pushing.

Preserve GPL-3.0-only terms and [NOTICE.md](NOTICE.md). Keep secrets out of
commits. Put rationale in `docs/`; add no code comments.
