# foundation-refrigeration configuration management plan

| Field | Value |
|---|---|
| Document ID | FREFRIG-SCMP |
| Version | 2.0 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 62764c7526ce2bbf064ccf633d5295f4390fc984 |
| Applies to | foundation-refrigeration main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Organization and responsibilities

| Role | Who | Responsibility |
|---|---|---|
| Maintainer and approver | Refrigeration.AI (GitHub `Akilleez-QA`, the only code owner in `.github/CODEOWNERS`) | Approves and merges pull requests, creates tags |
| Contributors | Agent lanes and external contributors | Open pull requests following [CONTRIBUTING.md](../../CONTRIBUTING.md) |
| Dependabot | GitHub | Weekly GitHub Actions version updates (`.github/dependabot.yml`) |
| Host maintainers | Cstack | Repin the vendored copy after a covered change |

## 2. Configuration identification

| Item | Identity | Control point |
|---|---|---|
| Source tree (package, bridge, data, golden, tests, tools, docs, root files) | Commit SHA; per-file SHA-256 in `SOURCE-MANIFEST.json` | Pull request to `main` |
| Version | SemVer `0.1.0` in `foundation_refrigeration/__init__.py`, `foundation_refrigeration_bridge/schemas.py` (`VERSION`) and the manifest written by `tools/build_manifest.py` | Pull request |
| Tool inventory | Canonical inventory SHA-256 ([tool catalog](../guides/reference/tool-catalog.md)) | Pull request plus host repin |
| Data projections | SHA-256 per file ([reference data](../data/reference-data.md)), schema and SemVer `version` inside each file | Pull request |
| CI and repository automation | `.github/` tree, outside the source manifest | Pull request |
| Baselines | Commits on `main`; release tags when created | Owner approval for tags |

Branch names are mutable and are never used as an identity.

### 2.1 Byte identities

The full per-file table is `SOURCE-MANIFEST.json` itself. It is regenerated, never edited. The manifest SHA-256, file count and inventory SHA-256 for a given commit are in the [version description](../releases/README.md) generated for it.

## 3. Change control

- Pull requests only, one concern each, following [CONTRIBUTING.md](../../CONTRIBUTING.md). The maintainer merges after checking the head commit; branches are kept after merge.
- `main` has no branch protection or ruleset at this baseline (`gh api repos/Akilleez-QA/foundation-refrigeration/branches/main/protection` returns 404 "Branch not protected"). The CI workflow runs on every pull request and push to `main`, but merging does not require it to pass. This is risk R-3 in the [SMP](../plan/software-management-plan.md#12-risk-register).
- After any change to a covered file, run `python -B tools/build_manifest.py` and commit the new `SOURCE-MANIFEST.json`. Consumers repin from its output.
- `PR_BODY.md` is an uncommitted review handoff, excluded from the manifest and its inventory test.
- Secret scanning: CI runs gitleaks on the full history of every push and pull request. Contributors also scan locally before pushing (see [CONTRIBUTING.md](../../CONTRIBUTING.md)); that local step is a convention, not an enforced gate.

## 4. Status accounting

- `CHANGELOG.md` (Keep a Changelog 1.1) records changes under `Unreleased` until a tag.
- Generated version descriptions in [docs/releases/](../releases/README.md) record what a commit or tag contains.
- `git log` and the merged pull requests are the full change record.

## 5. Configuration audits

At each release, and at each documentation baseline, an audit entry in the [assurance record](../assurance/assurance-record.md) checks: control documents name the audited commit; `tools/build_manifest.py` reproduces the committed manifest; the generated documents are current (`python -B tools/gen_docs.py --check`); the version description matches the manifest and inventory digests.

## 6. Generated outputs

| Output | Generator | Inputs | Committed | Freshness check |
|---|---|---|---|---|
| `SOURCE-MANIFEST.json` | `tools/build_manifest.py` | Every covered file | Yes | CI manifest job; `tests/test_names_and_manifest.py` |
| `docs/guides/reference/tool-catalog.md`, `docs/data/reference-data.md` | `tools/gen_docs.py` | Schemas, tool and server source, data and golden files | Yes | `tests/test_docs_trace.py`; `python -B tools/gen_docs.py --check` |
| `docs/verification/reports/STR-<label>.md`, `docs/releases/VDD-<label>.md` | `tools/gen_reports.py --label <label>` | Test runs, trace check, git, `gh`, gitleaks | Yes | Regenerated per baseline or tag |
| `golden/coolprop-8.0.0-points.json` | `tools/compute_golden.py --date` | CoolProp 8.0.0 | Yes | Manual (TP-2 in the [test plan](../verification/test-plan.md)) |
| Saturation tables, `golden/generator-golden-points.json` | External generators (not shipped) | CoolProp 8.0.0 | Yes | Provenance recorded in each file |

Generated files are not edited by hand. No source code is generated (SWE-146 and SWE-206 analogs do not apply to code).

## 7. Release management and delivery

- No tags or releases exist at this baseline. A tag is created only with owner approval.
- Delivery is the public Git repository. There is no package registry upload. Cstack vendors a byte-pinned copy.
- To cut a release: update `CHANGELOG.md`, run TP-1 in the [test plan](../verification/test-plan.md) with `--label <tag>`, regenerate the manifest, merge, then tag the merge commit.

### 7.1 Invariant provenance

`foundation_refrigeration/invariants.py` was received from `Akilleez-QA/endoforge` main at `819fa8a6b3eea9cae5f1388eb67a78556ad65727`, source `tools/invariants/refrigeration.py` and its README. Imports and hash paths are local to this package; `LIBRARY_VERSION` binds the package Python and JSON data at import. Golden reference data was unchanged by the move.

## 8. Plan maintenance

This plan is reviewed in any pull request that changes the CI workflow, the manifest generator, the generated-document tools or the release process. The manifest boundary is enforced in two places that must agree: `tools/build_manifest.py` and `tests/test_names_and_manifest.py`. Both exclude the root `.github/` tree, Git internals, Python caches and bytecode, the manifest itself and `PR_BODY.md`. GitHub automation is therefore outside the source pin, and CI-only changes need no manifest regeneration or consumer repin.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-10-30 | 9b459ef | Versioning, baseline, change control, pins | Initial commit |
| 1.1 | 2026-11-01 | 4bd3311 | Invariant provenance | PR #3 |
| 1.2 | 2026-11-04 | f51290c | Manifest excludes the root `.github/` tree | PR #9 |
| 2.0 | 2026-11-08 | 62764c7 | NASA-standard structure; generated outputs; branch-protection status; secret-scanning claim corrected to what CI enforces | PR adding the NASA-standard documentation set |
