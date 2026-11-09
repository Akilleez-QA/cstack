# foundation-template configuration management plan

| Field | Value |
|---|---|
| Document ID | FTEMPLATE-SCMP |
| Version | 2.0 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | fb9993c55e9c708a3cfdd295b237466d4bef7ff1 |
| Applies to | foundation-template main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Organization and responsibilities

| Role | Who | Responsibility |
|---|---|---|
| Maintainer and approver | Refrigeration.AI (GitHub `Akilleez-QA`, the only code owner in `.github/CODEOWNERS`) | Approves and merges pull requests, creates tags |
| Contributors | Agent lanes and external contributors | Pull requests following [CONTRIBUTING.md](../../CONTRIBUTING.md) |
| Dependabot | GitHub | Weekly GitHub Actions updates (`.github/dependabot.yml`) |
| Host maintainers | Cstack | Repin the vendored copy after a covered change |

## 2. Configuration identification

| Item | Identity | Control point |
|---|---|---|
| Source tree (package, bridge, tests, tools, docs, root files) | Commit SHA; per-file SHA-256 in `SOURCE-MANIFEST.json` | Pull request to `main` |
| Version | SemVer `0.1.0` in `foundation_template/__init__.py` and in the manifest written by `tools/build_manifest.py` | Pull request |
| Tool inventory | Canonical inventory SHA-256, printed by `tools/build_manifest.py` | Pull request plus host repin |
| CI and repository automation | `.github/` tree, outside the manifest | Pull request |
| Baselines | Commits on `main`; tags when created | Owner approval for tags |

### 2.1 Byte identities

The full per-file table is `SOURCE-MANIFEST.json`, regenerated and never edited. The three pins for a commit are in the [version description](../releases/README.md) generated for it.

## 3. Change control

- Pull requests only, one concern each. The maintainer merges after checking the head commit; branches are kept.
- `main` has no branch protection or ruleset at this baseline (`gh api repos/Akilleez-QA/foundation-template/branches/main/protection` returns 404 "Branch not protected"); CI runs on every pull request and push but is not required for merge (SMP risk R-2).
- After any change to a covered file, run `python -B tools/build_manifest.py` and commit the new manifest. Consumers repin from its output.
- Secret scanning: CI runs gitleaks over the full history. Scanning locally before pushing is a contributor convention, not an enforced gate.

## 4. Status accounting

`CHANGELOG.md` (Keep a Changelog 1.1) records changes under `Unreleased` until a tag. Generated [version descriptions](../releases/README.md) record what a commit or tag contains.

## 5. Configuration audits

At each release and documentation baseline, an [assurance record](../assurance/assurance-record.md) entry checks: control documents name the audited commit; the manifest reproduces; the generated catalog is current (`python -B tools/gen_docs.py --check`); the version description matches the pins.

## 6. Generated outputs

| Output | Generator | Committed | Freshness check |
|---|---|---|---|
| `SOURCE-MANIFEST.json` | `tools/build_manifest.py` | Yes | CI manifest job; `tests/test_bridge.py` |
| `docs/guides/reference/tool-catalog.md` | `tools/gen_docs.py` | Yes | `tests/test_docs_trace.py` |
| `docs/verification/reports/STR-<label>.md`, `docs/releases/VDD-<label>.md` | `tools/gen_reports.py --label <label>` | Yes | Regenerated per baseline or tag |

No source code is generated.

## 7. Release management and delivery

No tags exist. A tag needs owner approval. Delivery is the public Git repository; Cstack vendors a byte-pinned copy. To release: update `CHANGELOG.md`, run TP-1 in the [test plan](../verification/test-plan.md) with the tag as label, regenerate the manifest, merge, tag the merge commit.

## 8. Plan maintenance

Reviewed in any pull request that changes CI, the manifest generator, the documentation tools or the release process. The manifest boundary is enforced in `tools/build_manifest.py` and `tests/test_bridge.py::BridgeTests.test_source_manifest_lists_every_file`; both exclude the root `.github/` tree, Git internals, Python caches and bytecode and the manifest itself, so CI-only changes need no repin.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-10-30 | fbfaadb | Versioning, baseline, change control, pins | Initial commit |
| 1.1 | 2026-11-03 | ab81203 | Manifest excludes the root `.github/` tree | PR #10 |
| 2.0 | 2026-11-08 | fb9993c | NASA-standard structure; generated outputs; branch-protection status; secret-scanning claim corrected to what CI enforces | PR adding the NASA-standard documentation set |
