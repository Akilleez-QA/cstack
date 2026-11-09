# foundation-robotics software test plan and procedures

| Field | Value |
|---|---|
| Document ID | FROBO-STP |
| Version | 1.0 |
| Status | Draft |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | b4de079f2d99114e5efe6b204704df57d392e454 |
| Applies to | foundation-robotics main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Scope and approach

All verification is automated with Python's `unittest`, run from the repository root. The executable tests are the procedures (SWEHB 5.14 tailored). Two manual procedures cover the tutorial and the generated reports. Formal witnessing is not applicable; the CI log or the generated report is the record.

## 2. Test levels

| Level | What it covers | Location | Command |
|---|---|---|---|
| Unit | Each tool's arithmetic, checks, verdicts and refusals; calibration replay; default provenance | `tests/test_tools.py` | `python -B -m unittest discover -s tests -t .` |
| Integration | The bridge as a subprocess: handshake, catalog, a tool call, tool errors, wire errors, argv refusal, source manifest | `tests/test_bridge.py` | same |
| Documentation | Trace check, dead links, generated-docs freshness | `tests/test_docs.py` | same |
| Regression | Full suite in normal and optimized (`-O`) mode on every push and pull request to `main` | `.github/workflows/ci.yml` job `tests` | both commands in §3 |
| Configuration | Manifest regenerated and compared; secret scan | CI jobs `manifest` and `gitleaks` | see §3 |

No performance or security penetration tests exist.

## 3. Test environment and exact CI commands

| Item | Values | Source |
|---|---|---|
| OS | `ubuntu-latest` GitHub-hosted runner | `.github/workflows/ci.yml` |
| Runtime | CPython 3.12 via `astral-sh/setup-uv@v7`; supported minimum 3.11 (README) | ci.yml |
| Dependencies | None. `jsonschema` is optional and not installed in CI | `tests/test_tools.py` |
| External services | None | — |

CI commands, copied from `.github/workflows/ci.yml`:

```sh
uv run --no-project --python 3.12 python -B -m unittest discover -s tests -t .
uv run --no-project --python 3.12 python -B -O -m unittest discover -s tests -t .
uv run --no-project --python 3.12 python -B tools/build_manifest.py
git diff --exit-code SOURCE-MANIFEST.json
gitleaks git --redact --no-banner --exit-code 1 --config .gitleaks.toml .
```

CI pins gitleaks 8.28.0. Locally, `python -B` with any Python 3.11 or newer is equivalent for the first two commands. To also run the output-schema checks (REQ-ROB-022):

```sh
uv run --no-project --python 3.12 --with jsonschema python -B -m unittest discover -s tests -t .
```

## 4. Pass criteria and acceptance

A change is acceptable when all CI jobs pass: every test passes in both modes, the regenerated manifest has no diff and gitleaks finds nothing. Because `tests/test_docs.py` runs inside the suite, this also requires zero trace problems, zero dead links and current generated docs. No known failure is accepted at the baseline.

## 5. Coverage

Not measured. No coverage tool is in CI, and the project uses the standard library only. Requirement coverage is measured instead: every requirement in the SRS has at least one test or inspection row, and every test traces to a requirement or is listed as supporting (`tools/check_trace.py`). Behaviour without a test is listed in SRS §8. MC/DC: not applicable (not safety-critical, SWE-219).

## 6. Test data and fixtures

- `foundation_robotics/data/calibration.json`: 7 recorded known-good, known-bad and finding cases, replayed by `CalibrationTests` ([table](../data/calibration-cases.md)).
- Constructed motion in `tests/test_tools.py`: a synthetic two-foot walk track (`walk_track`), a swaying COM over a fixed four-point support (`sway`), a two-link leg (`LEG`), gear trains, slider-cranks, four-bars and rotors computed in closed form.
- Bridge sessions run `python -B -m foundation_robotics_bridge` as a subprocess with a 30 s timeout.

## 7. Procedures

### TP-1 — Tutorial run

- Purpose / requirements: confirm the [first-check tutorial](../guides/tutorials/first-check.md) works as written (REQ-ROB-013, REQ-ROB-006).
- Preconditions: a clean clone; Python 3.11 or newer.
- Steps: run each command in the tutorial from the repository root.
- Expected result: the outputs shown in the tutorial (handshake protocol, `thresholds_not_met` with volume 1086, exit status 0).
- Last run: 2026-11-08, baseline b4de079 plus this documentation change, pass.

### TP-2 — Generated reports

- Purpose / requirements: produce the test report and version description from a real run (SWEHB 5.11, 5.16).
- Preconditions: committed tree; `gh` signed in to read issues and pull requests (optional; without it the counts say "not queried").
- Steps: `python -B tools/gen_reports.py --label <label>`, then `python -B tools/build_manifest.py`, then commit the two generated files and the manifest.
- Expected result: exit status 0; `docs/verification/reports/STR-<label>.md` and `docs/releases/VDD-<label>.md` written; every test `ok` in both modes.
- Last run: see the latest [report](reports/README.md).

## 8. Test risks and limitations

- CI does not install `jsonschema`, so REQ-ROB-022 is checked only in local runs that add it (SAR finding F-3).
- Many bridge error paths have no test (SRS §8, GAP-ROB-01 to 11).
- Calibration covers human-scale walks, one giant and one squash; thresholds for balance, IK and mechanisms are tried only on constructed cases. See [limitations](../guides/explanation/limitations.md).
- Tests use exact integer expectations; a change to rounding or a default changes them. Never edit an expected value to obtain a pass (CONTRIBUTING).

## 9. Traceability

See the [verification matrix](verification-matrix.md).

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | b4de079 | Initial baseline | docs/nasa-standard PR |
