# foundation-refrigeration software test plan and procedures

| Field | Value |
|---|---|
| Document ID | FREFRIG-STP |
| Version | 1.1 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-09 |
| Baseline commit | 62764c7526ce2bbf064ccf633d5295f4390fc984 |
| Applies to | foundation-refrigeration main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Scope and approach

All verification is automated with Python's `unittest`, plus two CI gates (secret scan, manifest check). The executable tests are the procedures: each test's code states its inputs, steps and expected result. This plan gives the commands, environment, pass criteria and the few manual procedures.

## 2. Test levels

| Level | What it covers | Location | Command |
|---|---|---|---|
| Unit | Units, Evidence, saturation lookup, data content, taxonomy, process-safety screens, invariant evaluator | `tests/test_evidence_units.py`, `tests/test_thermo.py`, `tests/test_domain_data.py`, `tests/test_process_safety.py`, `tests/test_invariants.py` | `python -B -m unittest discover -s tests -t .` |
| Integration | Tool dispatch and receipts through `Bridge.dispatch`; frame decoding; `serve` over in-memory streams | `tests/test_bridge.py` | same |
| System | The bridge as a real child process (`python -B -m foundation_refrigeration_bridge`) with a two-message session | `tests/test_bridge.py::TransportTests.test_real_process_round_trip_without_options` | same |
| Configuration | Source manifest equals the tree | `tests/test_names_and_manifest.py` | same |
| Documentation | Requirement trace, dead links, generated documents current | `tests/test_docs_trace.py` | same |
| Optimized mode | Every test again with assertions stripped from the code under test (`-O`), to show no behaviour depends on `assert` | all | `python -B -O -m unittest discover -s tests -t .` |
| Regression | Full suite on every push to `main` and every pull request | `.github/workflows/ci.yml` | both commands above |

There are no performance or load tests.

## 3. Test environment

| Item | Values | Source |
|---|---|---|
| OS | `ubuntu-latest` GitHub-hosted runner | `.github/workflows/ci.yml` |
| Runtime | CPython 3.12 via `uv run --no-project --python 3.12` (CI); any CPython 3.11+ locally | `.github/workflows/ci.yml`, README |
| Dependencies | None at test time (standard library only) | `tools/` and `tests/` imports |
| External services | None. Tests read repository files and start the bridge as a child process | `tests/` |
| Secret scan | gitleaks 8.28.0, default rules (`.gitleaks.toml` extends the defaults) | `.github/workflows/ci.yml` |

The CI commands, copied from `.github/workflows/ci.yml`:

```sh
uv run --no-project --python 3.12 python -B -m unittest discover -s tests -t .
uv run --no-project --python 3.12 python -B -O -m unittest discover -s tests -t .
gitleaks git --redact --no-banner --exit-code 1 --config .gitleaks.toml .
uv run --no-project --python 3.12 python -B tools/build_manifest.py
git diff --exit-code SOURCE-MANIFEST.json
```

## 4. Pass criteria and acceptance

A change is accepted when, at its head commit:

1. both unittest commands exit 0 with no failures, errors or skips;
2. `tools/build_manifest.py` leaves `SOURCE-MANIFEST.json` unchanged;
3. gitleaks exits 0;
4. `tests/test_docs_trace.py` passes, so the trace check, link check and generated documents are clean.

There are no known accepted failures.

## 5. Coverage

Not measured. The project pins no coverage tool and the runtime is standard library only. Known untested code paths are listed as gaps GAP-REF-001 to GAP-REF-008 in the [SRS](../requirements/requirements.md#9-untested-behaviour-gaps). MC/DC is not applicable: the software is not safety-critical (SWE-219 applies only to safety-critical software).

## 6. Test data and fixtures

| Data | Use | Origin |
|---|---|---|
| `golden/coolprop-8.0.0-points.json` | 56 independent saturation points (by temperature, by pressure, ammonia anchor points) | `tools/compute_golden.py`, CoolProp 8.0.0, 2026-10-24 |
| `golden/generator-golden-points.json` | 171 off-grid points from the table generator | External generator run, 2026-10-24 |
| `foundation_refrigeration/data/*.json` | The shipped data under test | See the [data dictionary](../data/data-dictionary.md#4-reference-data-provenance) |
| Inline cases | Tool arguments (`tests/test_bridge.py` `CASES`), inventory and selection records (`tests/test_process_safety.py`) | Written in the tests |

Golden files are never edited by hand. A change uses the producing tool and is explained in the pull request.

## 7. Procedures

Automated suites: run the two unittest commands in §3 from the repository root. Each test can also be run alone, for example `python -B -m unittest tests.test_bridge.ReceiptTests.test_tool_errors_are_errors_not_results`.

### TP-1 — Generate the test report and version description

- Purpose / requirements: record results for all requirements at one commit (SWEHB 5.11, 5.16).
- Preconditions: clean working tree at the commit to report; Python 3.12 (`uv`); `gh` authenticated for issue counts (optional); `gitleaks` on `PATH` (optional).
- Steps: `uv run --no-project --python 3.12 python -B tools/gen_reports.py --label unreleased` (use the tag name at a release); then `python -B tools/build_manifest.py`; commit the two generated files and the manifest.
- Inputs: the repository at HEAD.
- Expected result and pass/fail criteria: exit 0; `docs/verification/reports/STR-<label>.md` reports zero failures and zero trace problems. The tool exits 1 and the report concludes "FAILED" when a test run exits non-zero, runs no tests, or records a skipped, failed or unparsed outcome; when the normal and optimized runs record different tests; when the trace check reports a problem; or when the manifest, generated-docs or Gitleaks gate fails. A gate that did not run (Gitleaks not installed) is listed as "not run, so not passed" in the report, but does not by itself change the exit status.
- Last run: see the test log in [STR-unreleased](reports/STR-unreleased.md).

### TP-2 — Regenerate the golden CoolProp points (manual, offline)

- Purpose / requirements: refresh the independent reference for REQ-REF-020 after a deliberate oracle change.
- Preconditions: network access to install CoolProp 8.0.0.
- Steps: `uvx --from CoolProp==8.0.0 python -I tools/compute_golden.py --date YYYY-MM-DD`; review the diff; run both unittest commands; explain the change in the pull request.
- Inputs: CoolProp 8.0.0.
- Expected result and pass/fail criteria: the script refuses any CoolProp version other than 8.0.0; the suites pass.
- Last run: 2026-10-24 according to the file's `generated_on`; not re-run for this baseline.

### TP-3 — First bridge session tutorial

- Purpose / requirements: show the documented user path works (REQ-REF-001, REQ-REF-017).
- Preconditions: Python 3.11+.
- Steps: follow [the tutorial](../guides/tutorials/first-bridge-session.md).
- Expected result and pass/fail criteria: the two responses match the tutorial output.
- Last run: 2026-11-08 at the baseline commit, output pasted in the tutorial.

## 8. Test risks and limitations

- The golden files and the tables both come from CoolProp 8.0.0. Agreement shows consistency with that oracle, not accuracy against measurements or REFPROP.
- No test drives the Cstack adapter; that side is tested in the Cstack repository against its vendored copy.
- The real-process test has a 30 s timeout; a heavily loaded machine could make it fail without a defect.
- Untested paths (§5) could change without a failing test.

## 9. Traceability

See the [verification matrix](verification-matrix.md).

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | 62764c7 | Initial baseline | PR adding the NASA-standard documentation set |
| 1.1 | 2026-11-09 | e58a71c | TP-1 pass/fail criteria name the gates, skips and run mismatches that fail the report | PR fixing the 2026-11-09 backfill-review findings |
