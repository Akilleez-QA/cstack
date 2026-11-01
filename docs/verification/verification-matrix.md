# Cstack verification matrix

Status: reusable documentation baseline; approval is through repository review. This document describes inspected implementation, not a NASA compliance determination or certification.

Organization follows the requirements, design, traceability and configuration-control concerns of [NPR 7150.2](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all) and [NASA-STD-8739.8](https://standards.nasa.gov/standard/nasa/nasa-std-87398). No NASA software classification, hazard analysis or independent verification is asserted.

Requirements: [requirements.md](../requirements/requirements.md). Review requirements and verification evidence together.

## Reasoning snapshot verification

CS-REQ-019: compare every `poodo_skill.files` entry byte-for-byte with its pinned upstream checkout, require every archived path to be absent upstream and its content unchanged, then run the POODO structural validator, capsule checker regressions, root unittest suite and `bash ci/run-local.sh python links`. Deferred README/license and additional upstream records remain outside the verified subset; structural checks do not establish behavioral improvement.

## Method and evidence

The entries below name existing unittest methods inspected at the baseline. They are traceability selections, not new tests or a claim of exhaustive coverage. Run results belong to the candidate commit record; this matrix does not embed historical pass counts. Source inspection complements behavioral tests for conditions that a single assertion does not exercise.

| Requirement | Existing test file | Class.method | Acceptance observation / limit |
|---|---|---|---|
| CS-REQ-001 | `tests/test_bootstrap.py` | `LedgerBindingTests.test_registry_is_the_one_source_and_unknown_domains_never_fall_back` | Composition; inspect `bootstrap.py` for the full stated obligation. |
| CS-REQ-002 | `tests/test_inventory_crosscheck.py` | `InventoryCrossCheckTests.test_wrong_lane_refuses_to_start` | Authority lanes; inspect `bootstrap.py; contracts/ADAPTERS.json` for the full stated obligation. |
| CS-REQ-003 | `tests/test_math_adapter.py` | `MathAdapterTests.test_source_and_live_inventory_exact` | Math source identity; inspect `adapters/math_stdio.py` for the full stated obligation. |
| CS-REQ-004 | `tests/test_math_adapter.py` | `MathAdapterTests.test_source_missing_or_manifest_changed_fails_closed` | Source rejection; inspect `adapters/math_stdio.py` for the full stated obligation. |
| CS-REQ-005 | `tests/test_math_adapter.py` | `MathAdapterTests.test_wrong_inventory_never_dispatches_math` | Catalog identity; inspect `adapters/math_stdio.py; schemas/math-v014-tools.json` for the full stated obligation. |
| CS-REQ-006 | `tests/test_math_adapter.py` | `MathAdapterTests.test_exact_input_controls_do_not_dispatch` | Input admission; inspect `adapters/math_stdio.py; adapters/wire.py` for the full stated obligation. |
| CS-REQ-007 | `tests/test_math_adapter.py` | `MathAdapterTests.test_schema_flags_tool_and_envelope_mutations_quarantine` | Response admission; inspect `adapters/math_stdio.py` for the full stated obligation. |
| CS-REQ-008 | `tests/test_math_adapter.py` | `MathAdapterTests.test_real_all_nineteen_through_inherited_core_and_differential` | Evidence ceiling; inspect `extensions/foundation_math.py; adapters/math_stdio.py` for the full stated obligation. |
| CS-REQ-009 | `tests/test_process_and_cli.py` | `ExecutorTests.test_timeout_terminates_and_unknown_execution` | Deadline; inspect `adapters/execution.py` for the full stated obligation. |
| CS-REQ-010 | `tests/test_process_and_cli.py` | `ExecutorTests.test_cancellation_terminates_and_no_partial_evidence` | Cancellation; inspect `adapters/execution.py` for the full stated obligation. |
| CS-REQ-011 | `tests/test_process_and_cli.py` | `ExecutorTests.test_bounded_stdout_and_stderr_overflow` | Output bounds; inspect `adapters/execution.py` for the full stated obligation. |
| CS-REQ-012 | `tests/test_core.py` | `CoreTests.test_decision_identity_is_consumed_not_automatic_retry` | Decision consumption; inspect `poodo_core/` for the full stated obligation. |
| CS-REQ-013 | `tests/test_core.py` | `CoreTests.test_stale_revision_denies_and_keeps_history` | Goal revision; inspect `poodo_core/` for the full stated obligation. |
| CS-REQ-014 | `tests/test_bootstrap.py` | `LedgerBindingTests.test_distinct_ports_over_same_canonical_path_are_refused_before_construction` | Ledger ownership; inspect `bootstrap.py` for the full stated obligation. |
| CS-REQ-015 | `tests/test_math_adapter.py` | `MathAdapterTests.test_unknown_or_formal_capability_is_not_dispatched` | Unavailable engine; inspect `extensions/foundation_math.py; adapters/math_stdio.py` for the full stated obligation. |
| CS-REQ-016 | `tests/test_claim_gate.py` | `Cli.test_unavailable_atom_registry_fails_closed` | Empty and nonempty atom references yield exit status 2, a structured Registry error on stderr and empty stdout. |
| CS-REQ-020 | `tests/test_endoforge_port.py` | `EndoforgePortTests.test_protocol_surface`, `test_append_and_filter_preserve_evidence`, `test_reject_unbound_or_invalid_input` | Typed contract, preservation and binding in a fake; durable append pending. |
| CS-REQ-021 | `tests/test_endoforge_port.py` | `EndoforgePortTests.test_corruption_fails_closed` | Fake rejects tampering; inspect ICD section 5; I/O failure, witness and dispatch gating pending. |
| CS-REQ-022 | `tests/test_endoforge_port.py` | `EndoforgePortTests.test_append_and_filter_preserve_evidence`, `test_reject_unbound_or_invalid_input` | Filters, ordering, detached reads and missing-filter rejection; adapter isolation pending. |
| CS-REQ-023 | `docs/icd/icd-endoforge.md`, `poodo_core/ports.py`, `cli.py` | Inspection | POODO policy / Endoforge storage allocation; CLI still reports unimplemented; no integration claim. |

| CS-REQ-017 | `tests/test_cli_approver.py` | `CliApproverTests.test_approve_dispatches_through_core`, `test_deny_and_missing_approver_never_dispatch`, `test_missing_or_mismatched_file_answer_denies` | Exact approval dispatch and fail-closed refusal; core binding cases also covered in `tests/test_approval_policy.py`. |
| CS-REQ-018 | `tests/test_cli_approver.py` | `CliApproverTests.test_consumption_survives_new_adapter`, `test_terminal_answer_and_unavailable_terminal` | Single-use durable consumption, explicit terminal answer and missing terminal. Inspect expiry, grant restriction and host-only configuration. |

## Additional assertions and gaps

- CS-REQ-002: `tests/test_inventory_crosscheck.py`, `InventoryCrossCheckTests.test_adapter_missing_from_inventory_refuses_to_start` and `test_unmapped_capability_refuses_to_start` cover the other rejection cases.
- CS-REQ-003: `tests/test_math_adapter.py`, `MathAdapterTests.test_changed_file_after_manifest_is_detected` checks listed-file corruption. Inspection is still needed for verification placement before/after exchanges.
- CS-REQ-006: `MathAdapterTests.test_strict_json_and_distinct_response_budget` in the same file checks duplicate keys, nonfinite syntax and distinct request/response budgets.
- CS-REQ-007: `MathAdapterTests.test_malformed_partial_duplicate_and_oversized_output_quarantine` in the same file extends malformed-frame rejection evidence.
- CS-REQ-008 compares adapter output to the same bridge's direct output. This is preservation evidence, not independent mathematical corroboration.
- CS-REQ-014 tests in-process canonical path aliases. Cross-process exclusion is a separate host responsibility.

Every CS-REQ in the companion baseline has a mapping above. No independent verifier, safety analysis, structural coverage or deployment qualification is supplied by this matrix. Skipped SDK interoperability tests require their separately configured external SDK; a skip cannot establish interoperability.

The 2026-11-01 Foundation refresh retains all requirements and runtime behavior. Verify each copied manifest and listed file against its recorded upstream commit, rebuild each manifest without a byte change, and run `test_pins_match_the_foundation_and_contracts` in each of the four domain conformance suites through root discovery. The local CI wrapper runs root and Foundation suites normally and with optimization, plus documentation links.

## Reproduction and disposition

From the repository root, use an isolated Python environment with `requirements.txt` and `ci/requirements.txt`, then run:

```sh
python -B -m unittest discover -s tests
```

For each of film, math, refrigeration, robotics and template, run from its corresponding `foundations/` subdirectory:

```sh
python -B -m unittest discover -s tests -t .
```

Record command, interpreter, candidate commit, exit status, test count, skips and failures. Run `python -B tools/check_links.py` separately. If the local CI wrapper refuses missing host-only paths, record that failure separately from direct test results. Review changed assertions and assumptions before closing a failed requirement; do not replace a failed test with a prose waiver.

## Licensing

GPL-3.0-only. Commercial licenses under different terms are available from Refrigeration.AI; contact craig@nh3.biz. See the repository LICENSE and NOTICE.md for bundled notices.
