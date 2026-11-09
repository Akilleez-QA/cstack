# foundation-robotics configuration management plan

| Field | Value |
|---|---|
| Document ID | FROBO-SCMP |
| Version | 2.0 |
| Status | Draft |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | b4de079f2d99114e5efe6b204704df57d392e454 |
| Applies to | foundation-robotics main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Organization and responsibilities

The maintainer (Akilleez-QA, Refrigeration.AI) owns the configuration, approves and merges every pull request, and is the only person who creates tags. Contributors and agent lanes work on branches and open pull requests. CODEOWNERS (`.github/CODEOWNERS`) assigns every path to the maintainer.

## 2. Configuration identification

| Item | Identity | Control point |
|---|---|---|
| Source tree (package, bridge, data, tests, tools, docs, root files) | Commit SHA on `main`; `SOURCE-MANIFEST.json` SHA-256 | Pull request merge |
| Version | SemVer `0.1.0` in `SOURCE-MANIFEST.json` (written by `tools/build_manifest.py`) and `__version__` in both packages | Pull request; owner approval for a release |
| Tool inventory | SHA-256 of the canonical catalog (`tools/build_manifest.py --inventory`) | Pull request |
| Default and calibration data | `foundation_robotics/data/*.json`, covered by the manifest | Pull request; calibration replay test |
| CI and repository automation | `.github/` tree, outside the manifest | Pull request |
| Generated documents | See §6 | Regenerated, never hand-edited |
| Baselines | A commit on `main`; a tag once releases begin | Branch names are mutable and are never baselines |

### 2.1 Byte identities

`SOURCE-MANIFEST.json` is the digest table: it maps every covered file to its SHA-256. Regenerate it with `python -B tools/build_manifest.py`, which also prints the three pins (file count, manifest SHA-256, inventory SHA-256). The values for a given commit are in that commit's [version description](../releases/README.md). The manifest excludes the root `.github/` tree, `.git`, `__pycache__`, `.pyc` files and itself. CI configuration changes alone therefore need no manifest regeneration and no consumer repin.

## 3. Change control

- Every change is a pull request to `main`, one concern, about 400 changed lines or fewer (larger documentation baselines say why in the PR). The maintainer merges after the CI jobs pass. Branches are kept after merge.
- `main` has no GitHub branch protection rule at the baseline (`gh api repos/Akilleez-QA/foundation-robotics/branches/main/protection` returns 404). Merge discipline is by convention.
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
| `docs/guides/reference/tool-catalog.md` | `tools/gen_docs.py` | `foundation_robotics_bridge/schemas.py`, `server.LIMITS` | `tests/test_docs.py::DocTests.test_generated_docs_are_current` |
| `docs/data/defaults.md` | `tools/gen_docs.py` | `foundation_robotics/data/defaults.json` | same test |
| `docs/data/calibration-cases.md` | `tools/gen_docs.py` | `foundation_robotics/data/calibration.json` | same test |
| `docs/verification/reports/STR-<label>.md`, `docs/releases/VDD-<label>.md` | `tools/gen_reports.py --label <label>` | test runs in both modes, git, `gh`, the manifest, the trace check | point-in-time records; regenerated, not edited |

All generators use the standard library only and run on the same Python as the tests. Generated files are committed. They must not be edited by hand. There is no generated source code.

## 7. Release management and delivery

No release or tag exists yet. To cut one, with owner approval:

1. Update `CHANGELOG.md`: move `[Unreleased]` entries under the new version.
2. If the version changes, update `__version__` in both packages and the version in `tools/build_manifest.py`; run `python -B tools/build_manifest.py` and `python -B tools/gen_docs.py`.
3. Merge; on the merge commit run `python -B tools/gen_reports.py --label <tag>` and `python -B tools/build_manifest.py`; merge the generated STR and VDD.
4. Tag that commit and create a GitHub release that links the STR and VDD.

Delivery is the public GitHub repository. There is no package registry.

## 8. Plan maintenance

This plan is updated in the same pull request as any change to CI, the manifest tool, the generators or the release steps.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-10-30 | d779a9f | Versioning, baseline, change control, pins | Initial commit |
| 1.1 | 2026-11-04 | 8bc1227 | Manifest excludes the root `.github/` tree | PR #10 |
| 2.0 | 2026-11-08 | b4de079 | Family standard. Removed the claim that trufflehog runs before every push (no trufflehog configuration exists in the repository; CI runs gitleaks). Recorded that `main` has no branch protection. Added identification, status accounting, audits, generated outputs and release steps | docs/nasa-standard PR |
