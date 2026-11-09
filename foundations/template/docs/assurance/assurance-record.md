# foundation-template assurance record

| Field | Value |
|---|---|
| Document ID | FTEMPLATE-SAR |
| Version | 1.0 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | fb9993c55e9c708a3cfdd295b237466d4bef7ff1 |
| Applies to | foundation-template main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

Rolling record, newest entry first. A copy replaces this entry with its own first baseline entry and keeps the format.

## Entry 2026-11-08 — baseline fb9993c (documentation baseline PR)

- Analyzed by: agent documentation lane N5 (agent analysis is not independent).
- Inputs: all source, tests, CI workflow and documentation at `fb9993c55e9c708a3cfdd295b237466d4bef7ff1`; git history; pull requests #1 to #10; the family documentation standard.
- Code under `foundation_template/` and `foundation_template_bridge/` was not changed. Added: `tools/check_trace.py`, `tools/gen_docs.py`, `tools/gen_reports.py`, `tests/test_docs_trace.py`.

### Requirements analysis

Techniques: every claim in the previous documents was checked against the code; every test was mapped; `tests/` was searched for each code path; the trace check was written and run. Results: seven requirements kept; REQ-TPL-008 to REQ-TPL-012 added for tested behaviour; six untested behaviours recorded as GAP-TPL-001 to GAP-TPL-006. Trace check: 12 requirements, 12 traced; counts in [STR-unreleased](../verification/reports/STR-unreleased.md). No TBDs.

### Design analysis

The previous SDD said the manifest tool prints "the three pins": confirmed (`files`, `sha256`, `inventory_sha256`). All components are now listed with requirement IDs; none is undocumented.

### Testing analysis

- 10 tests at the baseline, all mapped to requirements.
- Untested paths: GAP-TPL-001 to GAP-TPL-006.
- `tests/test_input_limits.py` checks each input limit at its value and one past it, a good pattern for copies.
- Coverage is not measured.

### Source code quality

| Tool | Command | Findings (new / total) |
|---|---|---|
| ruff 0.14.0 (ad hoc, not a CI gate) | `uvx ruff@0.14.0 check --no-cache --select F,E9 foundation_template foundation_template_bridge tools tests` | 0 / 0 ("All checks passed!") |
| gitleaks 8.28.0 | `gitleaks git --redact --no-banner --exit-code 1 --config .gitleaks.toml .` | 0 / 0 ("no leaks found") |
| Imports review (manual) | `grep -n import foundation_template/*.py foundation_template_bridge/*.py` | Standard library only |

### Configuration audit

- `tools/build_manifest.py` reproduces the committed manifest (CI manifest job; `tests/test_bridge.py::BridgeTests.test_source_manifest_lists_every_file`).
- The canonical inventory SHA-256 at the baseline, `2d15f784589a077908d1a8e79dc0350ec62c090f08cb25ef63b04d947ac0622f`, equals the `INVENTORY_SHA256` pinned in Cstack's `adapters/template_stdio.py` (Cstack main, 2026-11-08). Cstack pins a 35-file manifest; this PR changes the file count and manifest digest, so Cstack must repin (F-5).
- No tags exist.

### Peer review summary

`gh pr list --state merged`: 10 pull requests merged; one (#6) has a formal GitHub review. Review is by a single maintainer plus agents; it is not independent.

### Findings

| ID | Severity | Finding | Location | Issue | Status |
|---|---|---|---|---|---|
| F-1 | S4 | The ICD said "bounded decimal strings" cross the bridge; the template accepts integers only | `docs/icd/icd-cstack.md` | — | Closed: document corrected |
| F-2 | S4 | The SCMP and AGENTS.md said gitleaks and TruffleHog run before every push; only gitleaks runs, in CI | `docs/configuration/configuration-management.md`, `AGENTS.md` | — | Closed: documents corrected |
| F-3 | S4 | `tests/test_input_limits.py` has a class docstring, against the no-comments rule | `tests/test_input_limits.py` | — | Open |
| F-4 | S3 | Six untested behaviours (GAP-TPL-001 to GAP-TPL-006), inherited by every copy | `foundation_template_bridge/server.py`, `tools/build_manifest.py` | — | Open: candidates for tests |
| F-5 | S3 | Cstack's vendored copy pins an older manifest | Cstack `adapters/template_stdio.py` | — | Open: repin after merge |
| F-6 | S3 | `main` has no branch protection; no static analyzer in CI | GitHub settings, `.github/workflows/ci.yml` | — | Open: SMP risks R-2, R-3 |
| F-7 | S4 | Version `0.1.0` is written in `foundation_template/__init__.py` and `tools/build_manifest.py` with no check that they agree | those files | — | Open |

### Overall assessment

The code matches its documentation after the corrections above. The bridge's input limits are tested at every boundary. The main gaps are the untested error paths (inherited by copies), no static analyzer and no branch protection. The "Start a new Foundation" procedure (TP-3) has been run only in part (renames and checks); replacing the tool and rewriting documents has not been exercised.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | fb9993c | Initial baseline | PR adding the NASA-standard documentation set |
