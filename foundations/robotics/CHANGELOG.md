# Changelog

Format: Keep a Changelog 1.1, SemVer.

## [Unreleased]

### Added

- Initial release: Foundation package, stdio bridge, tests, and NASA-style docs under `docs/`.
- Documentation to the Cstack family standard (organized after NASA NPR 7150.2D and the NASA Software Engineering Handbook; self-assessed Class E analog, not safety-critical): software management plan, compliance matrix, data dictionary, test plan, test report, version description, assurance record, user manual map, tutorial, how-to guides, tool catalog, and a limitations and safety-relevant use page.
- `tools/check_trace.py` (requirement, test and design trace plus dead-link check), `tools/gen_docs.py` (tool catalog, defaults and calibration pages) and `tools/gen_reports.py` (test report and version description). `tests/test_docs.py` runs the trace check and the generated-docs check.
- Problem-report and change-request issue templates (replacing the bug template) and a peer-review pull request template.

### Changed

- Requirements: added REQ-ROB-013 to 022 for tested behaviour; narrowed REQ-ROB-012 to the tested depth limit and wire profile; listed untested behaviour as GAP-ROB-01 to 14.

### Fixed

- Documentation claims that did not match the code: REQ-ROB-012 evidence pointed at the wrong test file; the interface document omitted `ping` and mentioned decimal strings that the bridge never accepts; the configuration document claimed trufflehog runs before every push.
- Exclude `.github/` automation and repository metadata from the source manifest so CI-only changes do not invalidate source pins.

