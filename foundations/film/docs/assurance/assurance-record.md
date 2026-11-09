# foundation-film assurance record

| Field | Value |
|---|---|
| Document ID | FFILM-SAR |
| Version | 1.0 |
| Status | Draft |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 852f976aacaf8f08618bd0f37777f37822ce2614 |
| Applies to | foundation-film main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

Rolling record, newest entry first (SWEHB 5.21, 5.22, 5.23, 5.25, 5.26 and the 5.03 summary, tailored).

## Entry 2026-11-08 — baseline 852f976 (docs/nasa-standard PR)

- Analyzed by: documentation lane N4, agent-assisted for the maintainer. Agent analysis is not independent.
- Inputs: all files at 852f976, the CI workflow, GitHub pull requests #1 to #11, the family documentation standard v1.0.
- Scope limit: this change was docs-only. No code, test or tool was changed; findings that need code changes are listed, not fixed.
- Machine class for local runs: Linux x86_64 workstation; Python 3.11 and 3.12 (via uv).

### Requirements analysis

- Techniques: claim-by-claim comparison of every requirement with the code and tests; trace check; testability review.
- Results: the 13 original requirements were all real behaviour. Nine tested behaviours had no requirement and became REQ-FILM-014 to 022. Ten untested behaviours are listed as GAP-FILM-01 to 10 rather than stated as requirements.
- Trace check: an adapted copy of foundation-robotics `tools/check_trace.py` (same rules: every requirement has a matrix row and a test or inspection target, every referenced test exists, every test traces to a requirement, every requirement is allocated to a design component that lists it, no dead links or anchors), run against this tree: `{"components": 11, "matrix_rows": 22, "problems": 0, "requirements": 22, "tests": 31, "tests_traced": 31}`. The tool is not committed here because the change was docs-only (F-6).

### Design analysis

- Techniques: module-by-module reading against the design description; import inspection.
- Results: every module is now a component with requirement IDs (11 components). Import inspection for REQ-FILM-011: the bridge and tool modules import only `__future__`, `copy`, `hashlib`, `json`, `math`, `os`, `re` and `sys`; the producer imports `argparse`, `decimal`, `json` and `math` at module level and NumPy, OpenCV and PySceneDetect only inside functions. `os` is used only to read the two citation environment variables. No socket, subprocess or file write exists in the bridge or tool modules. Inspection for REQ-FILM-008: `tools.run` sets `boundary` from the constant on every receipt.

### Testing analysis

- Techniques: matrix rows against test names; reading each assertion; running the suite with and without the optional libraries.
- Results (commands run at 852f976 before this change):
  - `uv run --no-project --python 3.12 python -B -m unittest discover -s tests -t .`: 31 tests, OK (4 skipped).
  - same with `-O`: 31 tests, OK (4 skipped).
  - `uv run --no-project --python 3.12 --with numpy --with opencv-python-headless --with scenedetect python -B -m unittest discover -s tests -t .`: 31 tests, OK, no skips.
  - `uv run --no-project --python 3.11 python -B -m unittest discover -s tests -t .`: 31 tests, OK (4 skipped), run on the documentation branch, which changes no code.
- The old matrix cited `tests/test_bridge.py` as evidence for REQ-FILM-002, 003, 005 and 006; that test only sends bad arguments to those tools (F-1).
- No test validates any result against its output schema (F-4, GAP-FILM-07). CI skips the four producer video tests (F-5).

### Source code quality

| Tool | Command | Findings at 852f976 |
|---|---|---|
| Python compile | `compile()` over every `.py` file | 0 |
| ruff 0.17.0, default rule set | `ruff check --isolated --select E4,E7,E9,F .` | 5 (3 E731 lambda assignment, 2 E402 import after `sys.path` setup); no F findings |
| gitleaks 8.28 | `gitleaks git --redact --no-banner --exit-code 1 --config .gitleaks.toml .` | 0 leaks |

Running the producer on a synthetic video printed two scenedetect deprecation warnings for `get_seconds()` (F-7).

### Configuration audit

- Manifest: `python -B tools/build_manifest.py` at 852f976 gave 40 files, manifest SHA-256 `2898f80467b4bf2436fa2296ea183ad5ae9ecd66ac9f9e7f2dfe0fe5b1342ded`, inventory SHA-256 `4432e0305a84ed9aa1b269f2378f869b5b36850001e503ed1ffc0e018dd17558`, and no diff. This change adds documents, so the manifest SHA-256 changes; the inventory SHA-256 does not.
- No release tag exists, so no release audit was possible.

### Peer review summary

`gh pr list --state all`: 11 pull requests, all merged. Three (#5, #6, #8) have a recorded GitHub review; the others were reviewed only by the maintainer before merge. No issues have been filed.

### Findings

| ID | Severity | Finding | Location | Issue | Status |
|---|---|---|---|---|---|
| F-1 | S4 | Matrix cited the bridge test for the behaviour of four tools it only refuses | verification matrix 1.2 | — | Closed in this PR |
| F-2 | S4 | Configuration document and AGENTS.md claimed trufflehog runs before every push; no trufflehog configuration exists; CI runs gitleaks | SCMP 1.2, `AGENTS.md` | — | Closed in this PR |
| F-3 | S4 | ICD omitted `ping` and said decimal strings may cross the bridge; the bridge rejects all non-integer numbers | ICD 1.2 | — | Closed in this PR |
| F-4 | S3 | No test validates results against the published output schemas | `tests/` | none filed | Open (test change, out of scope for a docs-only change) |
| F-5 | S3 | CI never runs the producer's four video tests | `.github/workflows/ci.yml` | none filed | Open (CI change) |
| F-6 | S4 | The trace check and the documentation generators are not in the repository, so generated pages have no freshness test | `tools/` | none filed | Open (add the foundation-robotics tools in a follow-up) |
| F-7 | S3 | scenedetect warns that `get_seconds()` is deprecated; a future release may break the producer | `foundation_film/filmstats.py` lines 91 and 96 | none filed | Open (code change) |
| F-8 | S4 | `main` has no branch protection | GitHub settings | none filed | Open (owner decision) |
| F-9 | S3 | Ten behaviours have no test (GAP-FILM-01 to 10) | SRS §8 | none filed | Open |

### Overall assessment

The code matches its documentation after the corrections above. All 22 requirements trace to design, code and at least one passing test. The main verification weaknesses are the missing output-schema checks and the producer tests that CI skips. Nothing found changes the classification.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | 852f976 | First entry | docs/nasa-standard PR |
