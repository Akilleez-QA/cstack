# Changelog

Format: Keep a Changelog 1.1, SemVer.

## [Unreleased]

### Documentation

- NASA-standard documentation set (self-assessed Class E analog, not safety-critical): software management plan with classification statement, compliance matrix, requirements in record format (REQ-REF-001 to REQ-REF-036, untested behaviour listed as GAP-REF-001 to GAP-REF-008), design description, interface control document, data dictionary with the source, edition and units of every table, test plan, verification matrix, configuration management plan, assurance record, user manual map, tutorial, how-to guides and the "Limitations and safety-relevant use" page.
- Corrected REQ-REF-010: tool errors carry an empty Evidence list, as the code and tests always did.
- Corrected the interface document: `tools/build_manifest.py` does not print the inventory digest.
- Problem-report and change-request issue templates replace the bug template; the pull request template records peer review.

### Added

- `tools/check_trace.py` (requirement trace and link check), `tools/gen_docs.py` (generated tool catalog and reference data pages), `tools/gen_reports.py` (generated test report and version description) and `tests/test_docs_trace.py`, which runs the trace check and the generated-page check in the test suite.

### Fixed

- `tools/gen_reports.py` fails the report ("FAILED" conclusion, exit 1) when the manifest, generated-docs or Gitleaks gate fails, or when any test is skipped or unrecorded in the normal or optimized run; before, only unittest exit codes and trace problems counted. New requirement REQ-REF-037. Found by the 2026-11-09 backfill review.
- Exclude the root `.github/` automation and repository metadata tree from the source manifest so CI-only changes do not invalidate source pins.

### Added

- Initial release: Foundation package, stdio bridge, tests, and NASA-style docs under `docs/`.
