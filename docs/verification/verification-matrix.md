# Cstack verification matrix

| Field | Value |
|---|---|
| Document ID | CSTACK-VM |
| Version | 2.0 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 6ae5481fd302439dabb23044d1b715ac8c4a9bec |
| Applies to | cstack main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see [SMP §1](../plan/software-management-plan.md#1-software-classification-self-assessed)) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

Requirements: [requirements.md](../requirements/requirements.md). Design allocation: [SDD §4](../architecture/architecture.md#4-decomposition-and-allocation). Test plan: [test-plan.md](test-plan.md).

## How to read and check this matrix

Each row maps one requirement to the tests that check it. A test reference is `tests/<file>.py` (every test in the file), `tests/<file>.py::Class` (every test in the class) or `tests/<file>.py::Class.method`. Method is T (test), A (analysis), I (inspection) or D (demonstration). "Last result" points to the test report that recorded the run.

```sh
python -B tools/check_trace.py
```

The check parses this file, the requirements and the design description. It fails when a requirement has no row, a requirement has no test and is not in the gap table, a named test file, class or method does not exist, a test file under `tests/` is neither traced nor classified, a requirement's allocation disagrees with the design, or a link in a control document is dead. It runs in `bash ci/run-local.sh trace` and in CI.

The matrix does not embed pass counts. A mapped test shows the requirement is exercised; it does not prove every clause. Where a clause needs inspection, the row says what to inspect.

## Requirement to test

| Requirement | Method | Tests | Acceptance observation / limit | Last result |
|---|---|---|---|---|
| CS-REQ-001 | T, I | `tests/test_bootstrap.py::LedgerBindingTests.test_registry_is_the_one_source_and_unknown_domains_never_fall_back`; `tests/test_bootstrap.py::LedgerBindingTests.test_production_builders_use_registry_and_fresh_memory_ledgers` | Inspect `bootstrap.py` for the full obligation | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-002 | T | `tests/test_inventory_crosscheck.py` | Wrong lane, adapter missing from inventory and unmapped capability each refuse to start | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-003 | T, I | `tests/test_math_adapter.py::MathAdapterTests.test_source_and_live_inventory_exact`; `tests/test_math_adapter.py::MathAdapterTests.test_changed_file_after_manifest_is_detected` | Inspect `adapters/math_stdio.py` for check placement before and after exchanges | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-004 | T | `tests/test_math_adapter.py::MathAdapterTests.test_source_missing_or_manifest_changed_fails_closed` | No dispatch with a missing or changed manifest | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-005 | T | `tests/test_math_adapter.py::MathAdapterTests.test_wrong_inventory_never_dispatches_math`; `tests/test_math_adapter.py::MathAdapterTests.test_both_semantic_schemas_are_valid_and_closed` | Catalog mismatch blocks dispatch | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-006 | T | `tests/test_math_adapter.py::MathAdapterTests.test_exact_input_controls_do_not_dispatch`; `tests/test_math_adapter.py::MathAdapterTests.test_strict_json_and_distinct_response_budget`; `tests/test_math_adapter.py::MathAdapterTests.test_z_division_and_malformed_denominator_never_coerce` | Floats, duplicate keys, non-finite syntax and over-limit inputs never dispatch | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-007 | T | `tests/test_math_adapter.py::MathAdapterTests.test_schema_flags_tool_and_envelope_mutations_quarantine`; `tests/test_math_adapter.py::MathAdapterTests.test_malformed_partial_duplicate_and_oversized_output_quarantine`; `tests/test_math_adapter.py::MathAdapterTests.test_output_integer_larger_than_input_bit_cap_is_preserved` | Malformed or mismatched replies quarantine | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-008 | T | `tests/test_math_adapter.py::MathAdapterTests.test_real_all_nineteen_through_inherited_core_and_differential`; `tests/test_math_adapter.py::MathAdapterTests.test_positive_scalar_and_false_identity_are_different_claims`; `tests/test_math_adapter.py::MathAdapterTests.test_empty_domain_and_authored_match_do_not_promote` | Adapter output compared to the same bridge's direct output: preservation evidence, not independent mathematical corroboration | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-009 | T | `tests/test_process_and_cli.py::ExecutorTests.test_timeout_terminates_and_unknown_execution`; `tests/test_process_and_cli.py::ExecutorTests.test_child_not_reading_full_pipe_still_times_out`; `tests/test_process_and_cli.py::ExecutorTests.test_adapter_keeps_execution_uncertainty` | Timeout kills the child and keeps uncertainty | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-010 | T | `tests/test_process_and_cli.py::ExecutorTests.test_cancellation_terminates_and_no_partial_evidence`; `tests/test_process_and_cli.py::ExecutorTests.test_cancel_before_spawn`; `tests/test_process_and_cli.py::ExecutorTests.test_crash_and_late_reply_are_not_success` | No partial output admitted | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-011 | T | `tests/test_process_and_cli.py::ExecutorTests.test_bounded_stdout_and_stderr_overflow`; `tests/test_process_and_cli.py::ExecutorTests.test_oversized_request_rejected_without_process`; `tests/test_process_and_cli.py::ExecutorTests.test_nonempty_stderr_is_not_itself_failure` | Overflow stops the exchange | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-012 | T | `tests/test_core.py::CoreTests.test_decision_identity_is_consumed_not_automatic_retry` | Second execution of a consumed decision does not dispatch | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-013 | T | `tests/test_core.py::CoreTests.test_stale_revision_denies_and_keeps_history` | Stale revision denied; history kept | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-014 | T | `tests/test_bootstrap.py::LedgerBindingTests.test_distinct_ports_over_same_canonical_path_are_refused_before_construction`; `tests/test_bootstrap.py::LedgerBindingTests.test_same_port_cannot_bind_two_live_cores`; `tests/test_bootstrap.py::LedgerBindingTests.test_failed_or_recursive_construction_does_not_leave_a_binding` | In-process canonical path aliases only; cross-process exclusion is a host responsibility | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-015 | T | `tests/test_math_adapter.py::MathAdapterTests.test_unknown_or_formal_capability_is_not_dispatched` | `foundation_engine` request refused without dispatch | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-016 | T | `tests/test_claim_gate.py::Cli.test_unavailable_atom_registry_fails_closed` | Exit status 2, structured Registry error on stderr, empty stdout | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-017 | T | `tests/test_cli_approver.py::CliApproverTests.test_approve_dispatches_through_core`; `tests/test_cli_approver.py::CliApproverTests.test_deny_and_missing_approver_never_dispatch`; `tests/test_cli_approver.py::CliApproverTests.test_missing_or_mismatched_file_answer_denies` | Core binding cases also in `tests/test_approval_policy.py` | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-018 | T, I | `tests/test_cli_approver.py::CliApproverTests.test_consumption_survives_new_adapter`; `tests/test_cli_approver.py::CliApproverTests.test_terminal_answer_and_unavailable_terminal` | Inspect `adapters/terminal_approver.py` for the five-minute expiry and `bootstrap.py` for grant restriction | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-019 | I | Inspection: `contracts/SOURCE-PINS.json`, `reasoning/poodo/` (test plan TP-3) | Gap: no automated test | Not run at this baseline |
| CS-REQ-020 | T | `tests/test_endoforge_port.py::EndoforgePortTests.test_protocol_surface`; `tests/test_endoforge_port.py::EndoforgePortTests.test_append_and_filter_preserve_evidence`; `tests/test_endoforge_port.py::EndoforgePortTests.test_reject_unbound_or_invalid_input` | Protocol fake; file adapter evidence under CS-REQ-024 | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-021 | T | `tests/test_endoforge_port.py::EndoforgePortTests.test_corruption_fails_closed` | Fake rejects tampering; file I/O under CS-REQ-025 | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-022 | T | `tests/test_endoforge_port.py::EndoforgePortTests.test_append_and_filter_preserve_evidence`; `tests/test_endoforge_port.py::EndoforgePortTests.test_reject_unbound_or_invalid_input` | Filters, ordering, detached reads, missing-filter rejection | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-023 | T, I | `tests/test_endoforge_port.py::EndoforgePortTests.test_protocol_surface`; `tests/test_process_and_cli.py::CliTests.test_real_local_harness_process` | Port has only the four evidence methods; unbound CLI reports `endoforge_implemented: false`. Inspect `docs/icd/icd-endoforge.md` §2 and §6 | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-024 | T | `tests/test_endoforge_ledger.py::EndoforgeLedgerTests.test_protocol_and_reopen`; `tests/test_endoforge_ledger.py::EndoforgeLedgerTests.test_unmatched_and_invalid_inputs_do_not_append`; `tests/test_endoforge_ledger.py::EndoforgeLedgerTests.test_concurrent_writer_refused` | Durable reopen, binding, process and hard-link exclusion; power loss not tested | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-025 | T | `tests/test_endoforge_ledger.py::EndoforgeLedgerTests.test_corruption_fails_closed`; `tests/test_endoforge_ledger.py::EndoforgeLedgerTests.test_io_errors_and_uncertain_acknowledgement` | Short writes, write, fsync and read errors, uncertain acknowledgement | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-026 | T | `tests/test_endoforge_ledger.py::EndoforgeLedgerTests.test_protocol_and_reopen`; `tests/test_endoforge_ledger.py::EndoforgeLedgerTests.test_unmatched_and_invalid_inputs_do_not_append` | Shared port conformance, including after reopen | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-027 | T | `tests/test_endoforge_routing.py::EndoforgeRoutingTests.test_precommit_before_dispatch_and_outcome_chain`; `tests/test_endoforge_routing.py::EndoforgeRoutingTests.test_approval_decisions_are_witnessed`; `tests/test_refrigeration_e2e.py::RefrigerationE2ETests.test_approved` | Precommit before dispatch, approval_id and verdicts witnessed | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-028 | T | `tests/test_endoforge_routing.py::EndoforgeRoutingTests.test_storage_failures_block_dispatch_and_retry`; `tests/test_endoforge_routing.py::EndoforgeRoutingTests.test_failed_outcome_is_not_success_or_retried`; `tests/test_endoforge_routing.py::EndoforgeRoutingTests.test_failed_execution_preserves_uncertainty` | Storage failures block dispatch; no implicit retry | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-029 | T | `tests/test_endoforge_ledger.py::EndoforgeLedgerTests.test_concurrent_writer_refused`; `tests/test_endoforge_routing.py::EndoforgeRoutingTests.test_cli_uses_only_host_config_and_closes_storage` | Chain reopened and verified after a configured run | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-030 | T, I | `tests/test_endoforge_routing.py::EndoforgeRoutingTests.test_cli_uses_only_host_config_and_closes_storage` | Trusted config, request path rejection, configured status, no fallback. Inspect `docs/icd/icd-endoforge.md` §6 | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-031 | T | `tests/test_refrigeration_e2e.py` | Real CLI and Foundation, synthetic host verdict; no plant or engineering acceptance | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-032 | T | `tests/test_workcell_run.py`; `tests/test_forge_integrity.py::Faults`; `tests/test_forge_integrity.py::RefusedChecks` | Real CLI, core, pool, gates and ledger with a stub model transport | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-033 | T | `tests/test_workcell_foundation_imports.py`; `tests/test_foundation_kernels.py::Differential`; `tests/test_film_kernel.py`; `tests/test_robotics_kernel.py`; `tests/test_workcell_film_robotics.py::Forged` | ptrace spawn count over the whole job on Linux; differential vectors are a sample | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-034 | T | `tests/test_workcell_refusals.py`; `tests/test_workcell_other_foundations.py`; `tests/test_forge_integrity.py::Refusals`; `tests/test_forge_identity.py::Coders` | Named hostile kernels against the real core; a workcell is not an OS sandbox | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-035 | T | `tests/test_workcell_kill.py`; `tests/test_core_crash.py`; `tests/test_forge_recovery.py` | Real SIGKILL at each process; power loss not tested | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-036 | T | `tests/test_adapter_inventory.py`; `tests/test_inventory_crosscheck.py::InventoryCrossCheckTests.test_every_bootstrap_composition_passes` | Schema, lanes, duplicates, checkout match | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-037 | T | `tests/test_grant_lanes.py` | Decide and execute rechecks, read-only lanes, ordering | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-038 | T | `tests/test_approval_policy.py`; `tests/replaceability/test_truthface.py::TruthFaceFakeApproverTests` | Exact binding, single use, decline recorded | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-039 | T | `tests/test_approval_store.py` | Racing processes get exactly one yes | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-040 | T | `tests/test_budget_hard_stop.py`; `tests/replaceability/test_truthface.py::TruthFaceFakeBudgetTests` | Holds, pauses, lifts and unknown costs | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-041 | T | `tests/test_capacity_admission.py` | Limits, ordering, bounded records, fail-closed port | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-042 | T | `tests/test_core.py::CoreTests` | Every CoreTests method except those mapped to CS-REQ-012 and CS-REQ-013 | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-043 | T | `tests/test_core_reentrancy.py` | Every mutator from every hook | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-044 | T | `tests/test_core_crash.py`; `tests/test_core_recovery_accounting.py` | Kill windows simulated by truncated ledgers and real restarts | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-045 | T | `tests/test_core_unresolved.py` | Plain and witnessed ledgers | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-046 | T | `tests/test_goal_liveness.py` | Liveness never closes goals | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-047 | T | `tests/test_durable_ledger.py` | Injected short writes, full disk and fsync failure | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-048 | T | `tests/test_witnessed_ledger.py`; `tests/test_aor_session.py::WitnessedSessionTests` | Requires the `cryptography` package; skips without it | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-049 | T | `tests/test_aor_registry.py`; `tests/test_shipped_examples.py` | Shipped `aors/fleet.json` and example config validated | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-050 | T | `tests/test_aor_session.py`; `tests/test_aor_session_ownership.py` | Same-process and cross-process refusal | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-051 | T | `tests/test_e2e_agent_ledger.py` | Verdict stream and anchor checks | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-052 | T | `tests/test_mcp_driving_adapter.py`; `tests/test_mcp_conformance.py` | Golden tool list; malformed input keeps serving | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-053 | T | `tests/test_mcp_stdio_client.py` | `test_interop_with_official_typescript_sdk_server` skips unless `CSTACK_MCP_SDK_ESM` and `node` are present; a skip is not interop evidence | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-054 | T | `tests/test_fleet_mail.py`; `tests/test_fleet_mail_budget.py` | Uses a fake `gh`; no network | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-055 | T | `tests/test_relay_outbox.py` | Several processes, torn tails | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-056 | T | `tests/test_scheduled_approvals.py` | SQLite and witnessed node logs | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-057 | T | `tests/test_runtime_watch.py` | Byte and time identity after a watch | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-058 | T | `tests/test_witness_watch.py` | Deadman boundaries | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-059 | T | `tests/test_read_models.py`; `tests/test_read_models_cli.py` | Write impossibility checked by import and call inspection | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-060 | T | `tests/test_host_read_models.py` | Fixture sources only | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-061 | T | `tests/test_provider_policy.py` | Pure policy; no transport | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-062 | T | `tests/test_memory_store.py`; `tests/test_memory_ingest.py`; `tests/test_memory_cli.py` | Canary values checked absent from the database file | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-063 | T | `tests/test_workspace_snapshots.py` | Temporary Git repositories | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-064 | T | `tests/test_film_conformance.py`; `tests/test_robotics_conformance.py`; `tests/test_template_conformance.py`; `tests/test_refrigeration_conformance.py::RefrigerationAdapterTests`; `tests/test_refrigeration_conformance.py::SiblingConformanceTests`; `tests/test_refrigeration_conformance.py::RefrigerationCliTests`; `tests/test_refrigeration_conformance.py::CoreBoundaryTests.test_unimplemented_parts_stay_listed`; `tests/test_refrigeration_conformance.py::CoreBoundaryTests.test_executor_module_is_fixed_host_choice` | Real vendored bridges | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-065 | T | `tests/test_engine_conformance.py` | Two read-only validators only | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-066 | T | `tests/test_domain_registry.py` | Copies the checkout without `foundations/refrigeration/` | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-067 | T | `tests/test_process_and_cli.py::CliTests` | Exit status 2 on each rejected document | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-068 | T | `tests/test_forge_identity.py`; `tests/test_forge_inputs.py`; `tests/test_forge_journal.py` | Not-executed cases run nothing | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-069 | T | `tests/test_forge_integrity.py::Pins`; `tests/test_forge_integrity.py::Attribution`; `tests/test_foundation_kernels.py::Pins`; `tests/test_workcell_film_robotics.py::Pins` | Changed parts refuse to run | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-070 | T | `tests/test_endoforge_pin.py`; `tests/test_pin_endoforge_tool.py` | Byte identity of the vendored slice; upstream boundary suite needs `CSTACK_ENDOFORGE_CLONE` | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-071 | T | `tests/test_claim_gate.py::ClaimExtraction`; `tests/test_claim_gate.py::Verdicts`; `tests/test_claim_gate.py::Cli.test_exit_codes` | Verdict rules on fixture ledgers | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-072 | T | `tests/test_check_links.py` | Includes a run over the real repository maps | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-073 | T | `tests/test_readme_tools.py::ReadmeCheck`; `tests/test_readme_tools.py::MergeTrain`; `tests/test_readme_tools.py::ExportManifest`; `tests/test_merge_train.py` | Without `gh` on the path | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-074 | T | `tests/test_readme_tools.py::CorePin`; `tests/test_refrigeration_conformance.py::CoreBoundaryTests.test_poodo_core_bytes_match_current_pin` | SHA-256 of each pinned core file | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-075 | T | `tests/replaceability/test_shared.py`; `tests/replaceability/test_toolface.py` | Standard-library allow-list and fakes per lane | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-076 | T | `tests/test_check_trace.py` | Each failure kind produced on a fixture tree, plus the real repository | [STR-baseline](reports/STR-baseline.md) |
| CS-REQ-077 | T | `tests/test_data_dictionary.py` | Committed dictionary equals generated output | [STR-baseline](reports/STR-baseline.md) |

## Untested requirement gaps

Requirements with no automated test. Each is verified only by the stated inspection or procedure until a test exists.

| Requirement | Why there is no test | Interim verification |
|---|---|---|
| CS-REQ-019 | Comparison needs a POODO checkout at the pinned commit, which CI does not fetch | Test plan TP-3, by hand |

## Tests without a requirement

Every `test_*.py` file under `tests/` is traced above. The remaining files under `tests/` are support code:

| File | Classification |
|---|---|
| `tests/helpers.py`, `tests/aor_fixtures.py`, `tests/forge_fixtures.py`, `tests/fake_gh.py` | Infrastructure: shared fixtures and fakes |
| `tests/replaceability/compose.py` | Infrastructure: fake registry for CS-REQ-075 |
| `tests/kernels/` | Infrastructure: differential vectors and reference implementations for CS-REQ-033 |
| `tests/fixtures/` | Infrastructure: test data |
| `tests/crash_predictions/poodo_core.md` | Infrastructure: written predictions for the crash tests (CS-REQ-044) |

Vendored Foundation suites (`foundations/*/tests`) run in `ci/run-local.sh python`. They trace to each Foundation's own requirements upstream, not to CS-REQ IDs.

## Reproduction

From the repository root, in an environment with `requirements.txt` and `ci/requirements.txt` installed:

```sh
bash ci/run-local.sh python links trace
```

Record command, interpreter, commit, exit status, test count, skips and failures in a test report. Review changed assertions before closing a failed requirement; never replace a failed test with a prose waiver.

## Related verification records

- [Foundation routes](foundation-routes.md): measured routes from a workcell into each Foundation (CS-REQ-033).
- [Wiring acceptance](wiring-acceptance.md): the acceptance frozen before end-to-end wiring (historical).

## Licensing

GPL-3.0-only. Commercial licenses under different terms are available from Refrigeration.AI; contact craig@nh3.biz. See the repository LICENSE and NOTICE.md for bundled notices.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.x | 2026-10 to 2026-11-08 | various | Rows for CS-REQ-001 to CS-REQ-035 | See `git log -- docs/verification/verification-matrix.md` |
| 2.0 | 2026-11-08 | 6ae5481fd302439dabb23044d1b715ac8c4a9bec | One row per requirement in `file::Class.method` form; rows for CS-REQ-036 to CS-REQ-077; gap table; every test file traced; `tools/check_trace.py` | docs/nasa-standard PR |
