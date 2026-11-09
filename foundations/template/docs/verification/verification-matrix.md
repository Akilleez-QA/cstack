# foundation-template verification matrix

| Field | Value |
|---|---|
| Document ID | FTEMPLATE-VM |
| Version | 2.0 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | fb9993c55e9c708a3cfdd295b237466d4bef7ff1 |
| Applies to | foundation-template main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

This matrix maps each requirement in the [SRS](../requirements/requirements.md) to the tests or inspection that verify it. `python -B tools/check_trace.py` checks it: every requirement has a row, every referenced test exists, every test traces to a requirement or is listed under "Tests without a requirement", every requirement is allocated in the [SDD](../architecture/architecture.md), and no Markdown link is dead. `tests/test_docs_trace.py` runs that check in the normal test suite, so CI fails on a broken trace. A copy keeps this mechanism and replaces the rows.

Method: T test, I inspection.

| Requirement | Method | Test (file::Class.method) or inspection target | Acceptance observation / limit | Last result |
|---|---|---|---|---|
| REQ-TPL-001 | T | `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_echo_with_evidence` | `reading 7` is echoed with assessment `observation_echoed` through a real bridge process | [STR-unreleased](reports/STR-unreleased.md) |
| REQ-TPL-002 | T | `tests/test_bridge.py::BridgeTests.test_source_manifest_lists_every_file` | Manifest file map equals the recomputed map exactly | [STR-unreleased](reports/STR-unreleased.md) |
| REQ-TPL-003 | T | `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_echo_with_evidence` | `boundary` equals `tools.BOUNDARY` | [STR-unreleased](reports/STR-unreleased.md) |
| REQ-TPL-004 | T | `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_echo_with_evidence`<br>`tests/test_bridge.py::BridgeTests.test_bad_arguments_are_a_tool_error_that_still_carries_evidence` | Success has CHECK Evidence; five bad argument sets each return a tool error with non-empty Evidence | [STR-unreleased](reports/STR-unreleased.md) |
| REQ-TPL-005 | T | `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_echo_with_evidence` | `input_sha256` equals `tools.input_sha256` of the arguments | [STR-unreleased](reports/STR-unreleased.md) |
| REQ-TPL-006 | I | `foundation_template_bridge/server.py`, `foundation_template_bridge/__main__.py`, `foundation_template/tools.py` | Imports are standard library only (no `socket`, `urllib`, `http`, `subprocess`); no file reads or writes besides stdin, stdout and stderr | [STR-unreleased](reports/STR-unreleased.md) |
| REQ-TPL-006 | T | `tests/test_bridge.py::BridgeTests.test_wire_profile_fails_closed` | `--root /` is refused with exit 2 | [STR-unreleased](reports/STR-unreleased.md) |
| REQ-TPL-007 | T | `tests/test_input_limits.py::InputLimitTests.test_req_tpl_007_frame_bytes`<br>`tests/test_input_limits.py::InputLimitTests.test_req_tpl_007_stream_frame_bytes`<br>`tests/test_input_limits.py::InputLimitTests.test_req_tpl_007_depth`<br>`tests/test_input_limits.py::InputLimitTests.test_req_tpl_007_nodes`<br>`tests/test_input_limits.py::InputLimitTests.test_req_tpl_007_string_characters`<br>`tests/test_input_limits.py::InputLimitTests.test_req_tpl_007_integer_digits`<br>`tests/test_bridge.py::BridgeTests.test_wire_profile_fails_closed` | Each limit accepted at its value and refused one past it with `-32002` | [STR-unreleased](reports/STR-unreleased.md) |
| REQ-TPL-008 | T | `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_echo_with_evidence`<br>`tests/test_bridge.py::BridgeTests.test_wire_profile_fails_closed`<br>`tests/test_input_limits.py::InputLimitTests.test_req_tpl_007_stream_frame_bytes` | `initialize` result fields; `-32000` before initialize; `-32602` for `read_file`; `ping` returns `{}` | [STR-unreleased](reports/STR-unreleased.md) |
| REQ-TPL-009 | T | `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_echo_with_evidence` | `tools/list` equals `tool_definitions()` in `TOOL_NAMES` order | [STR-unreleased](reports/STR-unreleased.md) |
| REQ-TPL-010 | T | `tests/test_bridge.py::BridgeTests.test_wire_profile_fails_closed` | Duplicate `id`, `1.5` and `NaN` each give `-32700` | [STR-unreleased](reports/STR-unreleased.md) |
| REQ-TPL-011 | T | `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_echo_with_evidence`<br>`tests/test_bridge.py::BridgeTests.test_wire_profile_fails_closed`<br>`tests/test_input_limits.py::InputLimitTests.test_req_tpl_007_stream_frame_bytes` | Exit 0 after a complete session; exit 2 for an oversized frame and for `--root /` | [STR-unreleased](reports/STR-unreleased.md) |
| REQ-TPL-012 | T | `tests/test_bridge.py::BridgeTests.test_bad_arguments_are_a_tool_error_that_still_carries_evidence` | `{}`, empty string, integer, extra field and 257 characters are each a tool error | [STR-unreleased](reports/STR-unreleased.md) |

## Tests without a requirement

| Test | Classification (supporting / infrastructure / candidate requirement) |
|---|---|
| `tests/test_docs_trace.py::DocumentationTraceTests.test_requirements_trace_to_tests_design_and_live_links` | Infrastructure: documentation trace and link check |
| `tests/test_docs_trace.py::DocumentationTraceTests.test_generated_reference_documents_are_current` | Infrastructure: generated tool catalog matches the schemas |

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-10-30 | fbfaadb | Requirement to test-file table | Initial commit |
| 1.1 | 2026-10-30 | 96671fa | REQ-TPL-007 points at `tests/test_input_limits.py` | PR #3 |
| 2.0 | 2026-11-08 | fb9993c | Test-method references; rows for REQ-TPL-008 to REQ-TPL-012; results point to the generated test report | PR adding the NASA-standard documentation set |
