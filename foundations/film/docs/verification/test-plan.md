# foundation-film software test plan and procedures

| Field | Value |
|---|---|
| Document ID | FFILM-STP |
| Version | 1.0 |
| Status | Draft |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 852f976aacaf8f08618bd0f37777f37822ce2614 |
| Applies to | foundation-film main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Scope and approach

All verification is automated with Python's `unittest`, run from the repository root. The executable tests are the procedures (SWEHB 5.14 tailored). Three manual procedures cover the tutorial, the optional video producer and the generated reports. Formal witnessing is not applicable; the CI log or the generated report is the record.

## 2. Test levels

| Level | What it covers | Location | Command |
|---|---|---|---|
| Unit | Each tool's arithmetic, checks, verdicts, refusals and parity with the reference rules | `tests/test_tools.py` | `python -B -m unittest discover -s tests -t .` |
| Integration | The bridge as a subprocess: handshake, catalog, a tool call, tool errors, wire errors, argv refusal, source manifest | `tests/test_bridge.py` | same |
| Interface limits | Each wire limit at and one past its bound; stream line limit | `tests/test_requirement_limits.py` | same |
| Producer | Rounding and import isolation always; video tests only with optional dependencies | `tests/test_filmstats.py` | same, and TP-2 |
| Regression | Full suite in normal and optimized (`-O`) mode on every push and pull request to `main` | `.github/workflows/ci.yml` job `tests` | both commands in §3 |
| Configuration | Manifest regenerated and compared; secret scan | CI jobs `manifest` and `gitleaks` | see §3 |

No performance or security penetration tests exist.

## 3. Test environment and exact CI commands

| Item | Values | Source |
|---|---|---|
| OS | `ubuntu-latest` GitHub-hosted runner | `.github/workflows/ci.yml` |
| Runtime | CPython 3.12 via `astral-sh/setup-uv@v7` | ci.yml |
| Dependencies | None in CI. NumPy, opencv-python-headless and scenedetect are optional, for the producer only | README |
| External services | None | — |

CI commands, copied from `.github/workflows/ci.yml`:

```sh
uv run --no-project --python 3.12 python -B -m unittest discover -s tests -t .
uv run --no-project --python 3.12 python -B -O -m unittest discover -s tests -t .
uv run --no-project --python 3.12 python -B tools/build_manifest.py
git diff --exit-code SOURCE-MANIFEST.json
gitleaks git --redact --no-banner --exit-code 1 --config .gitleaks.toml .
```

CI pins gitleaks 8.28.0. In CI the four tests in `FilmstatsVisionTests` are skipped because the optional dependencies are absent.

## 4. Pass criteria and acceptance

A change is acceptable when all CI jobs pass: every test passes in both modes, the regenerated manifest has no diff and gitleaks finds nothing. A change to `foundation_film/filmstats.py` must also pass TP-2 with no skips. No known failure is accepted at the baseline.

## 5. Coverage

Not measured. No coverage tool is in CI, and the bridge uses the standard library only. Requirement coverage is measured instead: every requirement has at least one test or inspection row, and every test traces to a requirement (manual trace check, recorded in the assurance record). Behaviour without a test is listed in SRS §8. MC/DC: not applicable (not safety-critical, SWE-219).

## 6. Test data and fixtures

- Seeded random films, bands, drift series and look frames in `tests/test_tools.py` (seeds 4377, 26, 90 and 74), compared with in-test reimplementations of the reference float rules.
- Fixed numeric cases for each tool in `tests/test_tools.py`, including a per-beat look table measured on one reference run.
- Synthetic images and a two-shot MJPG video written to a temporary directory by `tests/test_filmstats.py`.
- Bridge sessions run `python -B -m foundation_film_bridge` as a subprocess with a 30 s timeout.

## 7. Procedures

### TP-1 — Tutorial run

- Purpose / requirements: confirm the [first-check tutorial](../guides/tutorials/first-check.md) works as written (REQ-FILM-014, REQ-FILM-004, REQ-FILM-016).
- Preconditions: a clean clone; Python 3.11 or newer.
- Steps: run the commands in the tutorial from the repository root.
- Expected result: the outputs shown in the tutorial.
- Last run: 2026-11-08, baseline 852f976 plus this documentation change, pass.

### TP-2 — Optional producer, full dependencies

- Purpose / requirements: run the four producer tests that CI skips (REQ-FILM-013).
- Preconditions: network access for `uv` to fetch NumPy, opencv-python-headless and scenedetect, or a warm `uv` cache.
- Steps:

  ```sh
  uv run --no-project --python 3.12 --with numpy --with opencv-python-headless --with scenedetect python -B -m unittest discover -s tests -t .
  uv run --no-project --python 3.12 --with numpy --with opencv-python-headless --with scenedetect python -B -O -m unittest discover -s tests -t .
  ```

- Expected result: every test passes with no skips.
- Last run: see the latest [report](reports/README.md), which states whether the producer tests ran.

### TP-3 — Generated reports

- Purpose: produce the test report and version description from a real run (SWEHB 5.11, 5.16).
- Steps: run the documentation generator (an adapted copy of foundation-robotics `tools/gen_reports.py`; not yet in this repository), then `python -B tools/build_manifest.py`, and commit the two generated files and the manifest.
- Expected result: every test `ok` in both modes.
- Last run: see the latest [report](reports/README.md).

## 8. Test risks and limitations

- CI never runs the producer's video tests (TP-2 is manual).
- No test validates results against the output schemas (GAP-FILM-07).
- Several bridge error paths have no test (SRS §8).
- Default contracts and thresholds come from one reference run; the tests fix their current values, not their fitness for other films.
- Never edit an expected value to obtain a pass (CONTRIBUTING).

## 9. Traceability

See the [verification matrix](verification-matrix.md).

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | 852f976 | Initial baseline | docs/nasa-standard PR |
