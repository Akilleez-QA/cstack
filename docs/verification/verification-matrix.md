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
| CS-REQ-020 | `tests/test_endoforge_port.py` | `EndoforgePortTests.test_protocol_surface`, `test_append_and_filter_preserve_evidence`, `test_reject_unbound_or_invalid_input` | Typed contract, preservation and binding in a fake; file adapter evidence is mapped under CS-REQ-024. |
| CS-REQ-021 | `tests/test_endoforge_port.py` | `EndoforgePortTests.test_corruption_fails_closed` | Fake rejects tampering; inspect ICD section 5; file I/O evidence is mapped under CS-REQ-025; independent witnessing pending; dispatch gating is mapped under CS-REQ-028. |
| CS-REQ-022 | `tests/test_endoforge_port.py` | `EndoforgePortTests.test_append_and_filter_preserve_evidence`, `test_reject_unbound_or_invalid_input` | Filters, ordering, detached reads and missing-filter rejection; file adapter retrieval evidence is mapped under CS-REQ-026. |
| CS-REQ-023 | `docs/icd/icd-endoforge.md`, `poodo_core/ports.py`, `cli.py` | Inspection | POODO policy / Endoforge storage allocation; configured CLI status and runtime evidence are mapped under CS-REQ-030. |

| CS-REQ-017 | `tests/test_cli_approver.py` | `CliApproverTests.test_approve_dispatches_through_core`, `test_deny_and_missing_approver_never_dispatch`, `test_missing_or_mismatched_file_answer_denies` | Exact approval dispatch and fail-closed refusal; core binding cases also covered in `tests/test_approval_policy.py`. |
| CS-REQ-018 | `tests/test_cli_approver.py` | `CliApproverTests.test_consumption_survives_new_adapter`, `test_terminal_answer_and_unavailable_terminal` | Single-use durable consumption, explicit terminal answer and missing terminal. Inspect expiry, grant restriction and host-only configuration. |
| CS-REQ-024 | `tests/test_endoforge_ledger.py` | `EndoforgeLedgerTests.test_protocol_and_reopen`, `test_unmatched_and_invalid_inputs_do_not_append`, `test_concurrent_writer_refused` | Durable reopen, envelope hashes, binding and process/hard-link exclusion; deployment qualification pending. |
| CS-REQ-025 | `tests/test_endoforge_ledger.py` | `EndoforgeLedgerTests.test_corruption_fails_closed`, `test_io_errors_and_uncertain_acknowledgement` | Whole-chain rejection, short writes, write/fsync/read errors and uncertain acknowledgement; external witnessing pending; dispatch gating is mapped under CS-REQ-028. |
| CS-REQ-026 | `tests/test_endoforge_ledger.py` | `EndoforgeLedgerTests.test_append_and_filter_preserve_evidence`, `test_unmatched_and_invalid_inputs_do_not_append` | Reused port conformance: filters, ordering, detached reads and missing-filter rejection. |

| CS-REQ-027 | `tests/test_endoforge_ledger.py`, `tests/test_endoforge_routing.py` | `test_protocol_and_reopen`, `test_unmatched_and_invalid_inputs_do_not_append`, `test_concurrent_writer_refused`, `test_precommit_before_dispatch_and_outcome_chain`, `test_approval_decisions_are_witnessed` | Durable ordering, outcomes, approval_id/verdicts, mixed-version chain verification and writer exclusion. |
| CS-REQ-028 | `tests/test_endoforge_ledger.py`, `tests/test_endoforge_routing.py` | `test_corruption_fails_closed`, `test_io_errors_and_uncertain_acknowledgement`, `test_storage_failures_block_dispatch_and_retry`, `test_failed_outcome_is_not_success_or_retried`, `test_failed_execution_preserves_uncertainty` | Chain rejection, storage failures blocking dispatch/completion, no implicit retry, unchanged uncertainty. |
| CS-REQ-029 | `tests/test_endoforge_ledger.py` | `EndoforgeLedgerTests.test_append_and_filter_preserve_evidence`, `test_unmatched_and_invalid_inputs_do_not_append` | Reused port conformance: filters, ordering, detached reads and missing-filter rejection. |
| CS-REQ-030 | `tests/test_endoforge_routing.py`, `docs/icd/icd-endoforge.md` | `test_cli_uses_only_host_config_and_closes_storage`; inspection | Trusted config, fresh sessions, request path rejection, configured status, chain reopen, failure without fallback. |

## Additional assertions and gaps

- CS-REQ-002: `tests/test_inventory_crosscheck.py`, `InventoryCrossCheckTests.test_adapter_missing_from_inventory_refuses_to_start` and `test_unmapped_capability_refuses_to_start` cover the other rejection cases.
- CS-REQ-003: `tests/test_math_adapter.py`, `MathAdapterTests.test_changed_file_after_manifest_is_detected` checks listed-file corruption. Inspection is still needed for verification placement before/after exchanges.
- CS-REQ-006: `MathAdapterTests.test_strict_json_and_distinct_response_budget` in the same file checks duplicate keys, nonfinite syntax and distinct request/response budgets.
- CS-REQ-007: `MathAdapterTests.test_malformed_partial_duplicate_and_oversized_output_quarantine` in the same file extends malformed-frame rejection evidence.
- CS-REQ-008 compares adapter output to the same bridge's direct output. This is preservation evidence, not independent mathematical corroboration.
- CS-REQ-014 tests in-process canonical path aliases. Cross-process exclusion is a separate host responsibility.

Every CS-REQ in the companion baseline has a mapping above. No independent verifier, safety analysis, structural coverage or deployment qualification is supplied by this matrix. Skipped SDK interoperability tests require their separately configured external SDK; a skip cannot establish interoperability.

The 2026-11-01 Foundation refresh retains all requirements and runtime behavior. Verify each copied manifest and listed file against its recorded upstream commit, rebuild each manifest without a byte change, and run `test_pins_match_the_foundation_and_contracts` in each of the four domain conformance suites through root discovery. The local CI wrapper runs root and Foundation suites normally and with optimization, plus documentation links.

The Endoforge repin is checked by `tests/test_endoforge_pin.py`:
`EndoforgePinTests.test_source_identity_and_exact_membership` verifies commit,
manifest digest, file count and every exported file hash;
`test_upstream_import_boundary` runs the selected upstream boundary suite.
Compare the selected upstream bytes separately before comment-token removal.
This establishes source identity and isolation for the lifecycle slice only.

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

## Refrigeration end-to-end acceptance (audit G3)

| Requirement | Evidence | Acceptance boundary |
|---|---|---|
| CS-REQ-031; CS-REQ-017; CS-REQ-027 | `tests/test_refrigeration_e2e.py`: `test_approved`, `test_denied`; `tools/e2e_refrigeration.sh` | Real CLI and Foundation, ask decision, exact durable approval identity and consumption, same-session precommit/outcome ordering, verified chain, configured implementation status, decline without dispatch or outcome. Synthetic host verdict; no plant or engineering acceptance. |
