# foundation-film configuration management plan

| Field | Value |
|---|---|
| Document ID | FFILM-SCMP |
| Version | 2.0 |
| Status | Draft |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 852f976aacaf8f08618bd0f37777f37822ce2614 |
| Applies to | foundation-film main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Organization and responsibilities

The maintainer (Akilleez-QA, Refrigeration.AI) owns the configuration, approves and merges every pull request, and is the only person who creates tags. Contributors and agent lanes work on branches and open pull requests. CODEOWNERS (`.github/CODEOWNERS`) assigns every path to the maintainer.

## 2. Configuration identification

| Item | Identity | Control point |
|---|---|---|
| Source tree (package, bridge, producer, tests, tools, docs, root files) | Commit SHA on `main`; `SOURCE-MANIFEST.json` SHA-256 | Pull request merge |
| Version | SemVer `0.1.0` in `SOURCE-MANIFEST.json` (written by `tools/build_manifest.py`) and `__version__` in both packages | Pull request; owner approval for a release |
| Tool inventory | SHA-256 of the canonical catalog (`tools/build_manifest.py --inventory`) | Pull request |
| Default rules, contract and thresholds | Module constants in `foundation_film/*.py`, covered by the manifest | Pull request; parity tests |
| Producer provenance | Endoforge main at `819fa8a6b3eea9cae5f1388eb67a78556ad65727`, `tools/film/filmstats.py`, adapted into `foundation_film/filmstats.py` | Pull request |
| Producer libraries | NumPy, opencv-python-headless, scenedetect; unpinned, installed by `uv` at run time; not shipped | Not under configuration control |
| CI and repository automation | `.github/` tree, outside the manifest | Pull request |
| Generated documents | See §6 | Regenerated, never hand-edited |
| Baselines | A commit on `main`; a tag once releases begin | Branch names are mutable and are never baselines |

### 2.1 Byte identities

`SOURCE-MANIFEST.json` is the digest table: it maps every covered file to its SHA-256. Regenerate it with `python -B tools/build_manifest.py`, which also prints the three pins (file count, manifest SHA-256, inventory SHA-256). The values for a given commit are in that commit's [version description](../releases/README.md). The manifest excludes the root `.github/` tree, `.git`, `__pycache__`, `.pyc` files, `PR_BODY.md` (an uncommitted review artifact) and itself. CI configuration changes alone therefore need no manifest regeneration and no consumer repin.

## 3. Change control

- Every change is a pull request to `main`, one concern, about 400 changed lines or fewer (larger documentation baselines say why in the PR). The maintainer merges after the CI jobs pass. Branches are kept after merge.
- `main` has no GitHub branch protection rule at the baseline (`gh api repos/Akilleez-QA/foundation-film/branches/main/protection` returns 404). Merge discipline is by convention.
- A change to any covered file needs a regenerated `SOURCE-MANIFEST.json` in the same pull request. CI regenerates it and fails on a diff.
- A host that vendors this repository repins from the manifest output in the same change that updates its copy.

## 4. Status accounting

- `CHANGELOG.md` (Keep a Changelog 1.1) records changes under `[Unreleased]` until a tag exists.
- `git log` on `main` and the merged pull requests record every change.
- Generated [version descriptions](../releases/README.md) record version, commit, pins and changes for each documented baseline.

## 5. Configuration audits

At each release, and for each documentation baseline, an audit entry in the [assurance record](../assurance/assurance-record.md) checks: the docs' baseline commit against the code, the manifest against the files (`tests/test_bridge.py::BridgeTests.test_source_manifest_lists_every_file` and the CI `manifest` job), and the VDD against the commit it names.

## 6. Generated outputs

| Output | Generator | Inputs | Check |
|---|---|---|---|
| `SOURCE-MANIFEST.json` | `tools/build_manifest.py` | the working tree | CI `manifest` job; manifest test |
| `docs/guides/reference/tool-catalog.md` | documentation generator (adapted copy of foundation-robotics `tools/gen_docs.py`) | `foundation_film_bridge/schemas.py`, `server.LIMITS` | none in CI; regenerate after a schema change |
| `docs/data/defaults.md` | same generator | module constants in `audio.py`, `drift.py`, `look.py`, `cinema.py` | none in CI; regenerate after a default change |
| `docs/verification/reports/STR-<label>.md`, `docs/releases/VDD-<label>.md` | documentation report generator (adapted copy of foundation-robotics `tools/gen_reports.py`) | test runs in both modes, git, `gh`, the manifest, the trace check | point-in-time records; regenerated, not edited |

The documentation generators are not yet in this repository: the documentation change that introduced these pages was docs-only, so they were run as adapted copies of the foundation-robotics tools. Adding them under `tools/` with a freshness test is an open item (SAR finding F-6). Generated files are committed and must not be edited by hand. There is no generated source code.

## 7. Release management and delivery

No release or tag exists yet. To cut one, with owner approval:

1. Update `CHANGELOG.md`: move `[Unreleased]` entries under the new version.
2. If the version changes, update `__version__` in both packages and the version in `tools/build_manifest.py`; run `python -B tools/build_manifest.py` and regenerate the tool catalog.
3. Merge; on the merge commit run the full suite, test plan TP-2 and the report generator with label `<tag>`, then `python -B tools/build_manifest.py`; merge the generated STR and VDD.
4. Tag that commit and create a GitHub release that links the STR and VDD.

Delivery is the public GitHub repository. There is no package registry.

## 8. Plan maintenance

This plan is updated in the same pull request as any change to CI, the manifest tool, the generators or the release steps.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-10-30 | 5c37f74 | Versioning, baseline, change control, pins | Initial commit |
| 1.1 | 2026-11-01 | e6e6405 | Producer provenance, optional dependencies, `PR_BODY.md` exclusion | PR #5 |
| 1.2 | 2026-11-04 | 42a5e27 | Manifest excludes the root `.github/` tree | PR #11 |
| 2.0 | 2026-11-08 | 852f976 | Family standard. Removed the claim that trufflehog runs before every push (no trufflehog configuration exists in the repository; CI runs gitleaks). Recorded that `main` has no branch protection. Added identification, status accounting, audits, generated outputs and release steps | docs/nasa-standard PR |
