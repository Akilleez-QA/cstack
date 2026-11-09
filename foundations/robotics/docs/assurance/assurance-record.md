# foundation-robotics assurance record

| Field | Value |
|---|---|
| Document ID | FROBO-SAR |
| Version | 1.0 |
| Status | Draft |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | b4de079f2d99114e5efe6b204704df57d392e454 |
| Applies to | foundation-robotics main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

Rolling record, newest entry first (SWEHB 5.21, 5.22, 5.23, 5.25, 5.26 and the 5.03 summary, tailored).

## Entry 2026-11-08 — baseline b4de079 (docs/nasa-standard PR)

- Analyzed by: documentation lane N4, agent-assisted for the maintainer. Agent analysis is not independent.
- Inputs: all files at b4de079, the CI workflow, GitHub pull requests #1 to #10, the family documentation standard v1.0.
- Machine class for local runs: Linux x86_64 workstation; Python 3.12 (via uv) and 3.14.

### Requirements analysis

- Techniques: claim-by-claim comparison of every requirement with the code and tests; trace check (`python -B tools/check_trace.py`); testability review.
- Results: the 12 original requirements were all real behaviour, but REQ-ROB-012 claimed five limits while only the depth limit is tested, and its matrix row pointed at the wrong test file (F-1). REQ-ROB-012 was narrowed and the untested limits moved to SRS §8. Ten tested behaviours had no requirement and became REQ-ROB-013 to 022. Fourteen untested behaviours are listed as GAP-ROB-01 to 14 rather than stated as requirements.
- Trace check after the change: `{"components": 13, "matrix_rows": 22, "problems": 0, "requirements": 22, "tests": 36, "tests_traced": 36}`. All 22 requirements have a matrix row and a test. Of 36 test methods, 34 trace to requirements and the 2 `DocTests` methods are infrastructure.

### Design analysis

- Techniques: module-by-module reading against the design description; import inspection.
- Results: every module is now a component with requirement IDs (13 components; one infrastructure). Import inspection for REQ-ROB-011: the packages import only `__future__`, `copy`, `hashlib`, `json`, `math`, `pathlib`, `re` and `sys`; the only file read is `foundation_robotics/data/*.json` via `sources.py`; no socket, subprocess or file write exists in `foundation_robotics/` or `foundation_robotics_bridge/`. Inspection for REQ-ROB-008: `tools.run` sets `boundary` from the constant on every receipt.
- The input schemas do not express "exactly one of `leg_length_mm` and `height_mm`" (`scale_timing`, `gait_check`), so schema validity does not imply acceptance. Documented in the SDD and ICD; not a defect in behaviour.

### Testing analysis

- Techniques: matrix rows against test names; reading each assertion; running the suite with and without `jsonschema`.
- Results (commands run at b4de079 before this change):
  - `uv run --no-project --python 3.12 python -B -m unittest discover -s tests -t .`: 34 tests, OK.
  - same with `-O`: 34 tests, OK.
  - `uv run --no-project --python 3.12 --with jsonschema python -B -m unittest discover -s tests -t .`: 34 tests, OK.
- CI does not install `jsonschema`, so the output-schema validation in `tests/test_tools.py` is silently skipped in CI (F-3).
- Bridge error paths other than duplicate keys, floats, NaN, depth, uninitialized use, unknown tool and argv are untested (GAP-ROB-01 to 11). Caller thresholds are untested (GAP-ROB-13).

### Source code quality

| Tool | Command | Findings at b4de079 | Findings on this branch |
|---|---|---|---|
| Python compile | `compile()` over every `.py` file | 0 | 0 (22 files) |
| ruff 0.17.0, default rule set | `ruff check --isolated --select E4,E7,E9,F .` | 6 (3 E731 lambda assignment, 1 E741 name `l`, 2 E402 import after `sys.path` setup) | 11 (5 more E402 in the new `tools/gen_docs.py` and `tools/gen_reports.py`, same `sys.path` pattern as `tools/build_manifest.py`) |
| gitleaks 8.28 | `gitleaks git --redact --no-banner --exit-code 1 --config .gitleaks.toml .` | 0 leaks, 16 commits | rerun before merge, see the PR |

No pyflakes-class (F) findings. The E731/E741/E402 items are style, not defects.

### Configuration audit

- Manifest: `python -B tools/build_manifest.py` at b4de079 gave 41 files, manifest SHA-256 `8016db3af7ce606a4bfcd9cc952259ed3d3d4799e117fbdbaa956ba90df08e06`, inventory SHA-256 `037919a5b4d2305de5a18e7d26994df2871a766ba1c2df2c1b11778d959ca599`, and no diff. This change adds files, so the manifest SHA-256 changes; the inventory SHA-256 does not (no schema change).
- Docs vs code: the stale claims found and fixed are listed in the findings table. The docs baseline is b4de079; the only code-side files added after it are `tools/check_trace.py`, `tools/gen_docs.py`, `tools/gen_reports.py` and `tests/test_docs.py`.
- No release tag exists, so no release audit was possible.

### Peer review summary

`gh pr list --state all`: 10 pull requests, all merged (#1 to #10), 2 of them from Dependabot. One (#7) has a recorded GitHub review, an automated review comment; the others were reviewed only by the maintainer before merge, with no review record. No issues have been filed.

### Findings

| ID | Severity | Finding | Location | Issue | Status |
|---|---|---|---|---|---|
| F-1 | S4 | Matrix said REQ-ROB-012 is verified by `tests/test_tools.py`; the test is in `tests/test_bridge.py`, and only the depth limit is tested | verification matrix 1.1 | — | Closed in this PR |
| F-2 | S4 | Configuration document claimed gitleaks and trufflehog run before every push; the repository has no trufflehog configuration and CI runs gitleaks only | SCMP 1.1 | — | Closed in this PR |
| F-3 | S3 | CI does not install `jsonschema`, so REQ-ROB-022 (output-schema conformance) is never checked in CI | `.github/workflows/ci.yml` | none filed | Open (code/CI change, out of scope for a docs lane) |
| F-4 | S4 | ICD omitted `ping` and said decimal strings may cross the bridge; the bridge rejects all non-integer numbers and no schema uses decimal strings | ICD 1.1 | — | Closed in this PR |
| F-5 | S4 | Duplicated word "the the" in two Evidence/citation strings | `foundation_robotics/tools.py` (squash evidence), `foundation_robotics/sources.py` (`calibration` source) | none filed | Open (code change; alters tool output text) |
| F-6 | S3 | A test method name in `ScaleTimingTests` carries an internal project name; public code should use a generic name | `tests/test_tools.py` | none filed | Open (code change) |
| F-7 | S4 | `main` has no branch protection; change control is by convention | GitHub settings | none filed | Open (settings decision for the owner) |
| F-8 | S3 | Fourteen behaviours have no test (GAP-ROB-01 to 14), mostly bridge error paths | SRS §8 | none filed | Open |

### Overall assessment

The code matches its documentation after the corrections above. All 22 requirements trace to design, code and at least one passing test. The main verification weaknesses are untested bridge error paths and output-schema validation that CI never runs. Nothing found changes the classification.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | b4de079 | First entry | docs/nasa-standard PR |
