# Cstack software test plan and procedures

| Field | Value |
|---|---|
| Document ID | CSTACK-STP |
| Version | 1.1 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | b7c64b19e3966baaf1aa6793491b454e28f51446 |
| Applies to | cstack main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see [SMP §1](../plan/software-management-plan.md#1-software-classification-self-assessed)) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Scope and approach

This plan covers every automated suite and every manual procedure used to verify Cstack. The executable tests are the procedures for automated checks (SWEHB 5.14 tailored): the command, environment and fixtures below are enough to rerun them and get the same verdict. Manual and live procedures are numbered in §7. The commands are copied from `.github/workflows/ci.yml` and `ci/run-local.sh`.

## 2. Test levels

| Level | What it covers | Location | Command |
|---|---|---|---|
| Unit | Core policy, ledgers, adapters, tools, each with fakes or fixtures | `tests/test_*.py` | `python -B -m unittest discover -s tests` |
| Integration | Adapters against the real vendored bridges; core with real adapters; workcells with the real pool, gates and ledger | `tests/test_*_conformance.py`, `tests/test_workcell_*.py`, `tests/test_forge_*.py` | as above |
| System / end-to-end | Real CLI process with host approval store and EndoForge ledger (CS-REQ-031) | `tests/test_refrigeration_e2e.py`, `tools/e2e_refrigeration.sh` | `bash ci/run-local.sh refrigeration` |
| Foundation suites | Each vendored Foundation's own tests, from its own directory | `foundations/*/tests` | `bash ci/run-local.sh python` |
| Optimized mode | Every Python suite again with `python -O`, so no check relies on `assert` | `ci/run-local.sh` | `bash ci/run-local.sh python` |
| Documentation and trace | Repository paths in docs; requirement ↔ design ↔ test trace; links and anchors in control documents | `tools/check_links.py`, `tools/check_trace.py` | `bash ci/run-local.sh links trace` |
| Security | Secret scans of the tree (and history, for TruffleHog) | `ci/scan-secrets.sh`, `.gitleaks.toml` | `bash ci/run-local.sh gitleaks trufflehog` |
| Regression | All of the above on every PR | CI and the PR's local checks | `bash ci/run-local.sh python links trace` (CI), `bash ci/run-local.sh` (all) |

No performance requirement exists. Route timings in [Foundation routes](foundation-routes.md) are measurements.

## 3. Test environment

| Item | Values | Source |
|---|---|---|
| OS | ubuntu-latest (CI); Linux locally. The spawn counter (`tools/spawncount.py`) needs Linux ptrace | `.github/workflows/ci.yml`, README |
| Python | 3.12 (CI, through `uv`); 3.12 or newer locally | `.github/workflows/ci.yml` |
| Node | 24 (CI); 22 or newer locally | `.github/workflows/ci.yml` |
| Python packages | `requirements.txt`, `ci/requirements.txt` (jsonschema, cryptography, pillow, numpy) | pinned versions in those files |
| Node packages | `npm ci --prefix adapters/workcell-toolchain --ignore-scripts --no-audit --no-fund` | `package-lock.json` |
| External services | None. Fleet mail tests use `tests/fake_gh.py`; forge tests use a stub model transport | test sources |

CI steps, verbatim:

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements.txt -r ci/requirements.txt
npm ci --prefix adapters/workcell-toolchain --ignore-scripts --no-audit --no-fund
python -B -m unittest discover -s tests
bash ci/run-local.sh python links trace
bash ci/scan-secrets.sh
```

## 4. Pass criteria and acceptance

- Every command in §3 exits 0.
- `tools/check_trace.py` reports 0 failures; every requirement either has a passing mapped test or appears in the matrix gap table.
- Skipped tests are allowed only for a named missing optional dependency (`cryptography`, a TypeScript MCP SDK, an EndoForge clone). A skip verifies nothing and is listed in the test report.
- No known failure is accepted at this baseline.

## 5. Coverage

Not measured. No coverage tool is in `ci/requirements.txt`, and no target is set. Requirement coverage is tracked instead by the trace check (every requirement mapped, every test file traced). MC/DC is not applicable (not safety-critical, SWE-219).

## 6. Test data and fixtures

Fixtures live under `tests/fixtures/`, shared helpers in `tests/helpers.py`, `tests/aor_fixtures.py` and `tests/forge_fixtures.py`, kernel reference vectors in `tests/kernels/`, and example inputs in `examples/`. Tests create their state (ledgers, approval stores, Git repositories) in temporary directories and never write to repository-local runtime configuration.

## 7. Procedures

Automated suites: the code is the procedure; run the command in §2. The numbered procedures below are manual or need something outside the repository.

### TP-1 — Refrigeration CLI acceptance

- Purpose / requirements: CS-REQ-031, CS-REQ-017, CS-REQ-027.
- Preconditions: setup in §3.
- Steps: `PYTHON=python3 bash tools/e2e_refrigeration.sh` (also `bash ci/run-local.sh refrigeration`).
- Inputs: `examples/refrigeration-e2e.json`; a disposable approval store and ledger created by the script.
- Expected result: exit 0; the approved case returns the Foundation outcome with a witnessed precommit before the outcome and a consumed `approval_id`; the declined case has no dispatch.
- Last run: recorded in [STR-baseline](reports/STR-baseline.md) (`refrigeration` suite).

### TP-2 — First-run tutorial on a fresh clone

- Purpose / requirements: validation of the user manual ([SUM map](../guides/SUM-MAP.md)).
- Preconditions: network access to clone; Python and Node per §3.
- Steps: follow [the tutorial](../guides/tutorials/first-run.md) verbatim in a new clone.
- Expected result: every command's output matches the page.
- Last run: 2026-11-08 on `main` at the previous documentation refresh (PR #74, before baseline 6ae5481), Python 3.12.14 and 3.14.9, outputs matched. Not rerun at this baseline; the tutorial did not change.

### TP-3 — POODO snapshot byte comparison

- Purpose / requirements: CS-REQ-019 (no automated test).
- Preconditions: a clone of https://github.com/Akilleez-QA/poodo checked out at the `poodo_skill.commit` in `contracts/SOURCE-PINS.json`.
- Steps: for every entry in `poodo_skill.files`, compare `reasoning/poodo/<file>` with the clone byte for byte; for every file under `TODELETE/reasoning/poodo/`, confirm it is absent from the clone.
- Expected result: every listed file identical; every archived path absent upstream.
- Last run: 2026-11-08 at baseline b7c64b1, commit `4a111aab0a51ec5fc4c611390e7ea8eee7d3a3a9`: 45 listed files, 0 mismatched; 10 archived paths, 0 present upstream.

### TP-4 — EndoForge pin against an upstream clone

- Purpose / requirements: CS-REQ-070.
- Preconditions: a fetched EndoForge clone.
- Steps: `CSTACK_ENDOFORGE_CLONE=<clone> python -B -m unittest tests.test_endoforge_pin`.
- Expected result: 4 tests OK, none skipped.
- Last run: 2026-11-08 at the previous documentation refresh (PR #74, pin `6dffea9`), 4 tests OK. Not rerun at this baseline; the pin did not change.

### TP-5 — README commands on a fresh clone

- Purpose / requirements: CS-REQ-073; README accuracy.
- Preconditions: network; optional `gh` and `claude` logins (commands needing them are reported as skipped).
- Steps: `python -B tools/check_readme.py` (or `bash ci/run-local.sh readme`).
- Expected result: every README command passes or is skipped with a stated reason; none uncovered.
- Last run: see the README "Measured" table.

### TP-6 — MCP TypeScript SDK interop

- Purpose / requirements: CS-REQ-053 (interop clause).
- Preconditions: an installed `@modelcontextprotocol/sdk` `dist/esm` directory and `node`.
- Steps: `CSTACK_MCP_SDK_ESM=<dir> python -B -m unittest tests.test_mcp_stdio_client`.
- Expected result: `test_interop_with_official_typescript_sdk_server` runs and passes.
- Last run: not run at this baseline; the test skipped in the recorded runs.

## 8. Test risks and limitations

- The local workstation is not the CI runner; both are recorded separately.
- Kill tests use real SIGKILL but not power loss; durability on power loss is not tested (SRS OI-2).
- Differential kernel vectors are samples, not proofs of equivalence.
- A workcell or process boundary is not a hostile-code sandbox; refusal tests use named hostile kernels only.
- Several hundred tests run in each mode; wall time on a loaded shared machine is long (about 20 minutes for `python links` at the previous refresh).

## 9. Traceability

See the [verification matrix](verification-matrix.md). Results per release are in [test reports](reports/).

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | 6ae5481fd302439dabb23044d1b715ac8c4a9bec | Initial baseline | docs/nasa-standard PR |
| 1.1 | 2026-11-08 | b7c64b19e3966baaf1aa6793491b454e28f51446 | TP-3 rerun against the repinned POODO commit | PR #78 |
