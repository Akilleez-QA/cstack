# foundation-robotics verification matrix

| Field | Value |
|---|---|
| Document ID | FROBO-VM |
| Version | 2.1 |
| Status | Draft |
| Owner | Akilleez-QA |
| Date | 2026-11-09 |
| Baseline commit | b4de079f2d99114e5efe6b204704df57d392e454 |
| Applies to | foundation-robotics main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

Trace check: `python -B tools/check_trace.py` (also run by `tests/test_docs.py::DocTests.test_trace_and_links_pass` in CI). It fails on a requirement with no row, a row naming a missing test or path, a `T` row with no test, a test that traces to nothing, an unallocated requirement, or a dead link. A test reference `file::Class` covers every test method in that class. Results come from the latest report in [reports/](reports/README.md).

| Requirement | Method | Test (file::Class.method) or inspection target | Acceptance observation / limit | Last result |
|---|---|---|---|---|
| REQ-ROB-001 | T | `tests/test_tools.py::ScaleTimingTests` | Giant (6000 mm) time factor = sqrt(3180 / 927.5); Froude preserved; strength-to-weight 292; preferred walk 2792 mm/s, 4825 mm, 1728 ms; fall time doubles for 4x height | STR (latest) |
| REQ-ROB-002 | T | `tests/test_tools.py::GaitTests` | Clean tracked walk passes with measured 1200 ms cycle; giant passes only with time scaled by sqrt(scale); skating foot fails slide; root outrunning feet fails kinematic mismatch; run duty 357 | STR (latest) |
| REQ-ROB-003 | T | `tests/test_tools.py::BalanceTests` | Static margin 100 mm inside, -200 mm leaning; ZMP within 10 mm or 10 % of the cart-table formula; floaty jump fails; moving stop fails capture | STR (latest) |
| REQ-ROB-004 | T | `tests/test_tools.py::IkTests` | Bent-leg tip equals closed-form FK; straight knee fails singular ratio; unreachable target fails reach and error; prismatic tip exact | STR (latest) |
| REQ-ROB-005 | T | `tests/test_tools.py::MechanismTests` | Screw rotor ratio -667 permille with sign checked; compound train speeds; mesh lock and slip; slider-crank stroke 120 mm; four-bar crank-rocker; strobe reads stationary, smeared, true motion | STR (latest) |
| REQ-ROB-006 | T | `tests/test_tools.py::SquashTests`, `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_a_verdict_with_evidence` | Volume 1086 permille fails over the bridge; a conserving frame passes | STR (latest) |
| REQ-ROB-007 | T | `tests/test_bridge.py::BridgeTests.test_source_manifest_lists_every_file` | Manifest file map equals a fresh hash of the tree under the same exclusions | STR (latest) |
| REQ-ROB-008 | T, I | `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_a_verdict_with_evidence`, `foundation_robotics/tools.py` | Test: receipt boundary equals the constant. Inspection: `run` sets `boundary` on every receipt; no module in `foundation_robotics/` writes files, opens sockets or starts processes | STR (latest); inspection in SAR 2026-11-08 |
| REQ-ROB-009 | T | `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_a_verdict_with_evidence`, `tests/test_bridge.py::BridgeTests.test_bad_arguments_are_a_tool_error_that_still_carries_evidence`, `tests/test_tools.py::InventoryTests` | Non-empty evidence on success and on every refusal for all six tools | STR (latest) |
| REQ-ROB-010 | T | `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_a_verdict_with_evidence` | `input_sha256` equals `input_sha256(arguments)` on a success receipt (error path: GAP-ROB-12) | STR (latest) |
| REQ-ROB-011 | I, T | `foundation_robotics_bridge/server.py`, `foundation_robotics/sources.py`, `tests/test_bridge.py::BridgeTests.test_wire_profile_fails_closed` | Test: `--root /` gives exit 2. Inspection: imports are standard library only; the only file read is the package's own `data/` | STR (latest); inspection in SAR 2026-11-08 |
| REQ-ROB-012 | T | `tests/test_bridge.py::BridgeTests.test_wire_profile_fails_closed` | Duplicate key, `1.5`, `NaN` give `-32700`; 33-deep nesting gives `-32002` | STR (latest) |
| REQ-ROB-013 | T | `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_a_verdict_with_evidence` | Protocol string echoed; `mcpCompatible` false | STR (latest) |
| REQ-ROB-014 | T | `tests/test_bridge.py::BridgeTests.test_handshake_catalog_and_a_verdict_with_evidence`, `tests/test_tools.py::InventoryTests` | Catalog equals `tool_definitions()`; names in `TOOL_NAMES` order | STR (latest) |
| REQ-ROB-015 | T | `tests/test_bridge.py::BridgeTests.test_bad_arguments_are_a_tool_error_that_still_carries_evidence`, `tests/test_tools.py::ScaleTimingTests.test_refusals`, `tests/test_tools.py::GaitTests.test_refusals`, `tests/test_tools.py::BalanceTests.test_refusals`, `tests/test_tools.py::IkTests.test_refusals`, `tests/test_tools.py::MechanismTests.test_refusals`, `tests/test_tools.py::SquashTests.test_volume_is_kept_or_not`, `tests/test_tools.py::InventoryTests` | `isError` true, assessment `tool_error`, status `error`, result null, evidence present | STR (latest) |
| REQ-ROB-016 | T | `tests/test_bridge.py::BridgeTests.test_wire_profile_fails_closed` | `tools/call` before `initialize` gives `-32000`; `drive_motor` gives `-32602` | STR (latest) |
| REQ-ROB-017 | T | `tests/test_tools.py::CalibrationTests.test_every_recorded_case_reaches_its_verdict` | 7 cases; verdict and failing-check set match; both known-good and known-bad labels present | STR (latest) |
| REQ-ROB-018 | T | `tests/test_tools.py::CalibrationTests.test_every_default_names_a_source_and_a_status` | Every default has status CHECK or RECORDED and a source key in `SOURCES` | STR (latest) |
| REQ-ROB-019 | T | `tests/test_tools.py::BalanceTests.test_blender_z_up_matches_three_y_up` | `worst` identical for y-up and z-up | STR (latest) |
| REQ-ROB-020 | T | `tests/test_tools.py::BalanceTests.test_flight_falls_at_g_and_a_floaty_jump_fails` | A 1625 mm/s² fall passes with `gravity_mm_s2` 1625 | STR (latest) |
| REQ-ROB-021 | T | `tests/test_tools.py::GaitTests.test_run_duty_and_unmeasured_checks`, `tests/test_tools.py::BalanceTests.test_static_com_inside_passes_and_a_lean_past_the_toes_fails`, `tests/test_tools.py::IkTests.test_forward_kinematics_of_a_bent_leg` | Speed alone gives `not_scored`; a failing margin gives `thresholds_not_met`; an all-pass pose gives `thresholds_met` | STR (latest) |
| REQ-ROB-022 | T | `tests/test_tools.py::ScaleTimingTests`, `tests/test_tools.py::GaitTests`, `tests/test_tools.py::BalanceTests`, `tests/test_tools.py::IkTests`, `tests/test_tools.py::MechanismTests`, `tests/test_tools.py::SquashTests`, `tests/test_tools.py::CalibrationTests.test_every_recorded_case_reaches_its_verdict` | `invoke()` validates arguments and receipts with `jsonschema` when importable. CI lacks `jsonschema`, so this runs only locally with `uv run --with jsonschema` | STR (latest) states whether validation was active |
| REQ-ROB-023 | T | `tests/test_docs.py::DocTests.test_catalog_documents_fields_inside_unions_and_maps`, `tests/test_docs.py::DocTests.test_catalog_documents_every_schema_field`, `tests/test_docs.py::DocTests.test_catalog_labels_each_union_variant` | Every schema field path appears in the catalog, including union branches, map values and nullable objects; multi-branch unions are labelled | STR (latest) |
| REQ-ROB-024 | T | `tests/test_docs.py::DocTests.test_report_parser_keeps_subtest_failures_and_skips`, `tests/test_docs.py::DocTests.test_report_does_not_call_skipped_tests_passed`, `tests/test_docs.py::DocTests.test_report_does_not_call_expected_failures_or_unexpected_successes_passed`, `tests/test_docs.py::DocTests.test_report_fails_on_failed_trace_gate`, `tests/test_docs.py::DocTests.test_report_fails_on_stale_manifest`, `tests/test_docs.py::DocTests.test_report_fails_when_outcomes_go_unparsed`, `tests/test_docs.py::DocTests.test_report_fails_on_nonzero_exit`, `tests/test_docs.py::DocTests.test_report_passes_only_when_every_gate_passes` | Fixture unittest output and gate inputs; the report is NOT PASSED for each failing case and passes only when every gate passes | STR (latest) |

## Tests without a requirement

| Test | Classification (supporting / infrastructure / candidate requirement) |
|---|---|
| `tests/test_docs.py::DocTests` | Infrastructure: runs the trace and link check and the generated-docs freshness check (the catalog-completeness and report-verdict methods also trace to REQ-ROB-023 and REQ-ROB-024), and the trace and link check in a copy holding only `SOURCE-MANIFEST.json` and its listed files, as a vendoring consumer such as Cstack runs it; links into `.github/`, which the manifest excludes, are skipped only when `.github/` is absent |

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-10-30 | d779a9f | Initial matrix | Initial commit |
| 1.1 | 2026-10-30 | 86f2280 | Inspection-only rows marked I | PR #4 |
| 2.0 | 2026-11-08 | b4de079 | Family standard. Method-level test references. Corrected REQ-ROB-012 evidence (was `tests/test_tools.py`; the test is in `tests/test_bridge.py`). Rows for REQ-ROB-013 to 022. "pass at baseline" replaced by pointers to the generated STR | docs/nasa-standard PR |
| 2.1 | 2026-11-09 | d5bbe35 | Rows for REQ-ROB-023 and REQ-ROB-024 | PR fixing the 2026-11-09 backfill-review findings |
