# Cstack assurance record

| Field | Value |
|---|---|
| Document ID | CSTACK-SAR |
| Version | 1.0 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 6ae5481fd302439dabb23044d1b715ac8c4a9bec |
| Applies to | cstack main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see [SMP §1](../plan/software-management-plan.md#1-software-classification-self-assessed)) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

Rolling record of requirements, design, testing, code-quality and configuration analyses (SWEHB 5.21, 5.22, 5.23, 5.25, 5.26) and the peer-review summary (5.03). Newest entry first.

## Entry 2026-11-08 — baseline 6ae5481 (documentation standard PR)

- Analyzed by: an agent documentation session working for the maintainer (agent analysis is not independent).
- Inputs: the code, tests, schemas, CI workflow and Git history at `6ae5481fd302439dabb23044d1b715ac8c4a9bec`; the earlier accuracy audit merged in PRs #74 to #76 (not redone); the family standard in [`docs/standards/`](../standards/family-doc-standard.md).

### Requirements analysis

- Techniques: inventory of every test file and method name against the 35 existing requirements; reading the code each test exercises; writing a requirement only where code does something a test checks; `tools/check_trace.py`.
- Result: 42 requirements added (CS-REQ-036 to CS-REQ-077), 77 in total. Before this entry, the matrix named 22 test files and 52 of the 74 test files traced to no requirement; now every test file (76, with the two added here) traces. TBDs: 0. One requirement (CS-REQ-019) has no automated test and is listed as a gap; its manual procedure TP-3 passed (45 files identical, 10 archived paths absent upstream).
- Three draft requirement statements were narrowed during analysis because the tests check less than the wording claimed: fleet-mail string handling (refuses rather than strips mentions), CLI input rejection (no "profiles" check exists), and the export manifest (see F-3).
- CS-REQ-027 to CS-REQ-030 repeated the port wording of CS-REQ-020 to CS-REQ-023 word for word; they were restated as the runtime obligations their tests check, keeping their IDs.

### Design analysis

- Techniques: component table built from the directory tree; each requirement allocated to one component; allocation checked in both directions by `tools/check_trace.py`.
- Result: 24 components. Three are infrastructure with no requirement: vendored backends (requirements live upstream), operator tools without tests, and examples. The earlier design omitted the AOR, MCP, fleet mail, memory, read model, provider policy, snapshot and repository-tool components; they are now described.

### Testing analysis

- Techniques: matrix rows resolved to existing test files, classes and methods by `tools/check_trace.py`; skip conditions read from the test sources.
- Result: 77 requirements, 76 with tests, 1 gap; 76 of 76 test files traced (74 existing plus 2 new). Skips occur only for a missing optional dependency (`cryptography`, a TypeScript MCP SDK, an EndoForge clone). Run results are in [STR-baseline](../verification/reports/STR-baseline.md). Coverage is not measured.

### Source code quality

| Tool | Command | Findings |
|---|---|---|
| pyflakes 3.4.0 (one-off; not configured in CI) | `uvx --from pyflakes==3.4.0 pyflakes adapters poodo_core extensions tools tests bootstrap.py cli.py` | 349 total. 326 in `tests/`, almost all "may be undefined, or defined from star imports" from deliberate `from poodo_core import *` and fixture star imports. 23 outside tests: 21 unused imports (12 of them package re-exports in `poodo_core/__init__.py` and `adapters/memory/__init__.py`), 1 shadowed import in `poodo_core/models.py`, and 1 star-import notice in `poodo_core/__init__.py`. No undefined name outside star-import cases. None in the new tools |
| gitleaks | `bash ci/run-local.sh gitleaks` | See STR-baseline |
| TruffleHog | `bash ci/run-local.sh trufflehog` | See STR-baseline |

### Configuration audit

- Source-manifest digests in the [configuration management plan](../configuration/configuration-management.md#manifest-byte-identities) were recomputed with `sha256sum` and match for all seven manifests.
- `EXPORT-MANIFEST.json` listed every tracked file except itself at the baseline; it is regenerated in this PR after the new files are added.
- Vendored trees (`foundations/`, `vendor/`, `reasoning/`) are unchanged by this PR.
- No release tag exists, so no release audit applies. The generated [VDD-baseline](../releases/VDD-baseline.md) records the manifest digests and the control-document baselines at its commit.

### Peer review summary

`gh pr list --state merged --limit 1000` at the baseline: 70 merged PRs (#3 to #76). 4 have a recorded GitHub review and 59 have PR comments; the rest were merged by the maintainer on the strength of the local checks listed in each PR body. `main` has no branch protection rule. One issue exists (#40, closed).

### Findings

| ID | Severity | Finding | Location | Issue | Status |
|---|---|---|---|---|---|
| F-1 | S4 | No static analyzer or linter runs in CI (SWE-135); the one-off pyflakes run above is the only static-analysis evidence | `.github/workflows/ci.yml` | Not filed | Open |
| F-2 | S4 | CS-REQ-019 has no automated test; the POODO comparison needs an upstream checkout | `contracts/SOURCE-PINS.json` | Not filed | Open; TP-3 passed by hand |
| F-3 | S4 | `tests/test_readme_tools.py::ExportManifest.test_it_lists_exactly_the_tracked_files` checks only that `.venv/` and `node_modules` paths are absent and one file is present, not that the list equals `git ls-files` | `tests/test_readme_tools.py` | Not filed | Open; CS-REQ-073 narrowed to what is checked |
| F-4 | S4 | `ci/requirements.txt` installs pillow and numpy for a hillclimb pixel-diff script under a `forge/` directory that does not exist in this repository; no tracked Python file imports either package | `ci/requirements.txt` | Not filed | Open |
| F-5 | S4 | `tools/check_links.py` scans `forge/endoforge/docs/*.md` and its docstring describes that area; the path does not exist | `tools/check_links.py` | Not filed | Open |
| F-6 | S4 | Operator tools have no tests: `tools/agent_profiles.py`, `tools/generate_aors.py`, `tools/measure_foundation_routes.py`, `tools/measure_routes_pyodide.mjs`, `tools/tty_approve.py`, `tools/gen_release_docs.py` | SDD-C23 | Not filed | Open; recorded as infrastructure |
| F-7 | S4 | The README "Measured" table cites runs at older commits and an unmerged branch; it is not regenerated | `README.md` | Not filed | Open |
| F-8 | Observation | No branch protection on `main`; CI results are not required to merge | GitHub settings | - | Recorded |

### Overall assessment

The documentation set now meets the family standard's required and tailored documents for a host repository, with a machine-checked trace from every requirement to tests and design. The code findings above are minor (S4) and none were fixed in this documentation PR. The main assurance limits remain the absence of independent review and of a configured static analyzer.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | 6ae5481fd302439dabb23044d1b715ac8c4a9bec | First entry | docs/nasa-standard PR |
