# foundation-template software test plan and procedures

| Field | Value |
|---|---|
| Document ID | FTEMPLATE-STP |
| Version | 1.1 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-09 |
| Baseline commit | fb9993c55e9c708a3cfdd295b237466d4bef7ff1 |
| Applies to | foundation-template main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Scope and approach

All verification is automated with Python's `unittest`, plus two CI gates (secret scan, manifest check). The executable tests are the procedures. This plan gives the commands, environment, pass criteria and the manual procedures. A copy keeps the structure and the commands, and adds its domain tests.

## 2. Test levels

| Level | What it covers | Location | Command |
|---|---|---|---|
| Unit | Frame decoding at each input limit | `tests/test_input_limits.py` | `python -B -m unittest discover -s tests -t .` |
| Integration | `serve` over in-memory streams | `tests/test_input_limits.py::InputLimitTests.test_req_tpl_007_stream_frame_bytes` | same |
| System | The bridge as a real child process: handshake, catalog, tool call, refusals, exit status | `tests/test_bridge.py` | same |
| Configuration | Source manifest equals the tree | `tests/test_bridge.py::BridgeTests.test_source_manifest_lists_every_file` | same |
| Documentation | Requirement trace, dead links, generated catalog current | `tests/test_docs_trace.py` | same |
| Report generator | The test report fails on failed gates, skips and unparsed outcomes | `tests/test_gen_reports.py` | same |
| Optimized mode | Every test with `-O` | all | `python -B -O -m unittest discover -s tests -t .` |
| Regression | Full suite on every push to `main` and every pull request | `.github/workflows/ci.yml` | both commands |

## 3. Test environment

| Item | Values | Source |
|---|---|---|
| OS | `ubuntu-latest` GitHub-hosted runner | `.github/workflows/ci.yml` |
| Runtime | CPython 3.12 via `uv run --no-project --python 3.12` (CI); CPython 3.11+ locally | `.github/workflows/ci.yml` |
| Dependencies | None (standard library only) | imports |
| External services | None | `tests/` |
| Secret scan | gitleaks 8.28.0, default rules | `.github/workflows/ci.yml`, `.gitleaks.toml` |

CI commands, copied from `.github/workflows/ci.yml`:

```sh
uv run --no-project --python 3.12 python -B -m unittest discover -s tests -t .
uv run --no-project --python 3.12 python -B -O -m unittest discover -s tests -t .
gitleaks git --redact --no-banner --exit-code 1 --config .gitleaks.toml .
uv run --no-project --python 3.12 python -B tools/build_manifest.py
git diff --exit-code SOURCE-MANIFEST.json
```

## 4. Pass criteria and acceptance

At the head commit: both unittest commands exit 0 with no failures, errors or skips; `tools/build_manifest.py` leaves `SOURCE-MANIFEST.json` unchanged; gitleaks exits 0; `tests/test_docs_trace.py` passes. There are no known accepted failures.

## 5. Coverage

Not measured; no coverage tool is pinned. Known untested paths are gaps GAP-TPL-001 to GAP-TPL-006 in the [SRS](../requirements/requirements.md#9-untested-behaviour-gaps). MC/DC: not applicable (not safety-critical, SWE-219).

## 6. Test data and fixtures

Inline only: request frames and argument sets written in the tests. No fixture files.

## 7. Procedures

Automated suites: run the two unittest commands in §3 from the repository root. One test alone: `python -B -m unittest tests.test_bridge.BridgeTests.test_wire_profile_fails_closed`.

### TP-1 — Generate the test report and version description

- Purpose / requirements: record results for all requirements at one commit (SWEHB 5.11, 5.16).
- Preconditions: clean working tree; Python 3.12 (`uv`); `gh` authenticated (optional, for issue counts); `gitleaks` on `PATH` (without it the report fails).
- Steps: `uv run --no-project --python 3.12 python -B tools/gen_reports.py --label unreleased` (the tag name at a release); `python -B tools/build_manifest.py`; commit the two generated files and the manifest.
- Expected result and pass/fail criteria: exit 0; the report shows zero failures and zero trace problems. The tool exits 1 and the report concludes "FAILED" when a test run exits non-zero, runs no tests, or records any outcome other than ok (skipped, expected failure, unexpected success, failed or unparsed); when the trace check reports a problem; or when the manifest, generated-catalog or Gitleaks gate fails or did not run. Gitleaks is therefore required for a passing report.
- Last run: see the test log in [STR-unreleased](reports/STR-unreleased.md).

### TP-2 — First bridge session tutorial

- Purpose / requirements: the documented user path works (REQ-TPL-001, REQ-TPL-008).
- Steps: follow [the tutorial](../guides/tutorials/first-bridge-session.md).
- Expected result: the outputs match the tutorial.
- Last run: 2026-11-08 at the baseline commit, output pasted in the tutorial.

### TP-3 — Copy check for a new Foundation

- Purpose: show a copy keeps a passing, traced documentation set.
- Steps: follow [Start a new Foundation](../guides/how-to/start-a-new-foundation.md) in a scratch copy; run both unittest commands and `python -B tools/check_trace.py`.
- Expected result: tests pass; the trace check reports zero problems after the renames.
- Last run: 2026-11-08, partial, on the working tree before this baseline was committed: steps 1 and 4 (renames to `foundation-acoustics`, `gen_docs.py`, `build_manifest.py`, tests, trace check). The renamed bridge answered `initialize` as `foundation-acoustics-jsonrpc/1`; all tests passed except the trace test, which failed only because the generated test report and version description did not exist yet in that tree. Steps 2 and 3 (replacing the tool and rewriting documents) were not exercised.

## 8. Test risks and limitations

- No test drives a host adapter; that side is tested in Cstack against its vendored copy.
- The subprocess tests have a 30 s timeout; a heavily loaded machine could fail them without a defect.

## 9. Traceability

See the [verification matrix](verification-matrix.md).

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | fb9993c | Initial baseline | PR adding the NASA-standard documentation set |
| 1.1 | 2026-11-09 | 3814683 | Report-generator test level; TP-1 criteria name the gates, skips and unparsed outcomes that fail the report; Gitleaks required | PR fixing the 2026-11-09 backfill-review findings |
