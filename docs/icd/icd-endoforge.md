# Cstack–Endoforge interface control document

| Field | Value |
|---|---|
| Document ID | CSTACK-ICD-ENDOFORGE |
| Version | 2.2 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-09 |
| Baseline commit | 84cd19d238a057b1c07af63e64b50edfb515d615 |
| Applies to | cstack main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see [SMP §1](../plan/software-management-plan.md#1-software-classification-self-assessed)) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

Status: contract baseline 0.3; approval is through repository review. The protocol,
local file adapter, host-configured POODO/CLI evidence routing and the workcell runtime are **implemented**.

## 1. Purpose, scope and references

This ICD controls witnessed evidence storage between POODO and an
Endoforge adapter, and the runtime in section 7. Sections 2 to 6 specify synchronous, in-process Python calls, not a wire
transport, agent runner or caching service.

Controlled sources: `poodo_core/ports.py`, `poodo_core/models.py` and
`tests/test_endoforge_port.py`, `adapters/endoforge_ledger.py` and
`tests/test_endoforge_ledger.py`, `tests/test_endoforge_routing.py`, `poodo_core/core.py`, `bootstrap.py` and `cli.py`. Related baselines are the
[requirements](../requirements/requirements.md),
[design](../architecture/architecture.md),
[verification matrix](../verification/verification-matrix.md) and
[source-pin ICD](icd-endoforge-pin.md).

## 2. Allocation and authority

POODO owns policy: goals, revisions, grants, approvals, decisions, precommitments,
execution admission and interpretation. Endoforge owns witnessed storage:
append ordering, durable receipts, chain integrity and retrieval. Storage
success neither authorizes execution nor proves a goal or domain claim.
Foundations retain domain meaning and acceptance. The trusted host selects the
ledger and session; request data cannot select storage roots or implementations.

`EndoforgePort` is separate from `LedgerPort`; this change replaces neither the
existing ledger nor its adapter. `cli.py` reports `endoforge_implemented: True`
when host configuration binds this port, otherwise `False`.

The current claim-gate CLI rejects `--atoms`, `--atom-refs` and `--consumer` requests with exit status 2 and a `cstack.claim-gate/0.1` JSON error on stderr stating that the approved-atoms Registry is unavailable. It emits no verdict on stdout. The pinned lifecycle slice does not provide that Registry; the dead optional import has been removed. Calls without atom options retain the ledger-only interface.

[PR #16](https://github.com/Akilleez-QA/cstack/pull/16) added a pinned lifecycle-core slice from Endoforge commit `cebd463ea9828dfd9bbf09181a631ee604eac8cf`. That slice held data and lifecycle rules plus an import-boundary test; the current pin, Endoforge `main` commit `ea7b8d651ce23acd100f5a5d81d6e8fda0d604a3`, adds the gates, ledger, `IsolatePool` and capacity planner that section 7 runs or carries. It has no agent runner or caching implementation. Its source-pin ICD, [icd-endoforge-pin.md](icd-endoforge-pin.md), records the manifest hash. Vendoring source does not implement `EndoforgePort`.

## 3. Operations and sequencing

| Operation | Inputs | Return and obligation |
|---|---|---|
| `append_precommit` | `session_id: str`, `decision: DecisionRecord` | `str` record hash after durable witnessed append of the decision and its prospective precommitment |
| `append_outcome` | `session_id: str`, `outcome: CapabilityOutcome` | `str` record hash after durable witnessed append of the unchanged outcome |
| `verify_chain` | None; host-bound ledger | Exact `bool`: `True` only for a complete valid snapshot, including an empty ledger; `False` for detected corruption |
| `read_records` | Keyword-only `goal_id: str \| None = None`, `session_id: str \| None = None` | `tuple[Document, ...]`, detached records in append order |

A precommit must be witnessed before the associated action is dispatched. An
outcome must match an earlier precommit in the same session on request id,
decision id, goal id, revision, capability, operation and request hash. Outcome
attempt identity is preserved. Storage validates this binding without deciding
whether the action was authorized. Failed or uncertain execution is recorded
with its original certainty and evidence ceiling.

Configured cores append at decision creation and again after execution gates,
before dispatch. The second precommit includes the consumed ApprovalPort approval,
when required; a bound decline is also witnessed before refusal. These are distinct
policy snapshots, not retries. Outcomes retain their original schema and correlate
to approvals through session, decision and request identity. Pending approvals do
not dispatch. An append error latches the core against further witnessed work.

At least one read filter is required. Each supplied id is an exact match; two
filters mean intersection. Unknown ids return an empty tuple. Reads verify the
whole chain before filtering and return a consistent snapshot, never partial
results. Host calls must be serialized; the adapter must provide atomic
append and exclusive writer ownership across processes.

## 4. Data formats and identity

Session and goal identifiers follow `models.identifier`: 1–128 characters from
`[A-Za-z0-9_.:-]`. Core model versions and validation remain authoritative.
Precommit input uses `DecisionRecord`, including `CapabilityRequest` and
`Precommitment`; its `request_sha256` must equal `request.sha256`.
Outcome input uses `CapabilityOutcome` without rewriting assessment, provenance,
certainty, limitations, `formal_proof` or `runtime_goal_acceptance`.

Each returned `Document` contains exactly these JSON fields:

| Field | Format / meaning |
|---|---|
| `schema` | `poodo.endoforge-record/0.1`, or `poodo.endoforge-record/0.2` for approval-bearing precommits |
| `record_id` | 64 lowercase hexadecimal SHA-256 characters |
| `previous_id` | Previous record hash; `null` for the first record |
| `kind` | `precommit` or `outcome` |
| `session_id`, `goal_id` | Valid identifiers; goal derived from the request/outcome |
| `payload` | Object defined below |

Precommit payload has exactly `request` (`CapabilityRequest.to_dict()`),
`request_sha256`, `grant_id` (identifier), and `precommitment`
(`Precommitment.to_dict()`). Outcome payload is `CapabilityOutcome.to_dict()`.
`DecisionRecord.approval` is an optional captured Document. When present, schema
0.2 adds exactly `approval`: the complete ApprovalRecord fields (`approval_id`,
`decision_id`, `request_sha256`, `goal_id`, `goal_revision`, `approver`, `verdict`,
`not_after`). Storage validates its request binding; POODO validates authority.
Readers accept mixed 0.1/0.2 chains without rewriting old bytes or hashes. Old
readers reject 0.2; upgrade readers before enabling approval-bearing writes.
The record hash is `models.digest` of the envelope excluding `record_id`, using
bounded canonical ASCII JSON with sorted keys and finite numbers. The complete
record must satisfy `Document.capture` limits. Hashes provide content identity
and linkage, not signature authentication or proof of external execution.
Physical storage and external witnessing mechanisms remain adapter decisions;
a hash chain alone cannot detect deletion of an otherwise valid final suffix.

### Local file adapter

`EndoforgeLedger(path)` binds a trusted host-selected path in an existing directory.
It holds a nonblocking exclusive `flock` on the file until `close()` or context
manager exit; competing opens, including hard-link aliases, raise `OSError`.
The host serializes calls and must not replace, unlink or externally modify the
file while open. Deployment requires a local POSIX filesystem supporting flock,
atomic append positioning and fsync. Each canonical ASCII JSON record occupies
one newline-terminated line, submitted in one `O_APPEND` write. The file and its
parent directory are synced at open, and each append is synced before its hash
is returned. Local fsync acknowledgement is this adapter's durable witness;
there is no independent external witness or suffix-rollback protection.
A short write fails closed. At open, a last line with no newline is a write that was never acknowledged: its bytes move to `<ledger>.torn-<hash>`, the file is cut back to the last whole line, and the run result reports `witness_quarantined`. A complete record that fails its chain raises `WitnessChainBroken`, naming the record, with no repair. The CLI reports `witness_chain_broken` and runs nothing.
Power-loss qualification and recovery procedures remain deployment work.
The pinned slice's own SQLite ledger holds the run's records; this file adapter stays the host's witness.

## 5. Errors and fail-closed behavior

Malformed inputs, missing read filters and unmatched outcomes raise
`ContractError` before append. Unavailable storage or witnessing raises
`OSError`; corruption prevents reads/appends with `RuntimeError` and makes
`verify_chain` return `False`. No exception becomes an empty read, valid chain
or successful receipt. Verification I/O failure raises rather than returning
`True`. Append/read must validate chain integrity at the operation boundary.

A goal's decision binds one request for the life of the ledger: a different request under the same goal and decision raises `DecisionReuseRefused`. An identical request may run again after a known outcome. After an unknown outcome it runs again only with the host's `cli.py --resume DECISION_ID`. This is goal-scoped, because the shipped examples reuse decision ids across goals.

An append failure may occur after persistence but before acknowledgement; callers
must retain uncertainty and reconcile by session/goal before any explicit retry.
There is no implicit retry, deduplication or exactly-once guarantee. Failed
precommit prevents dispatch; failed outcome persistence prevents treating the
operation as durably evidenced. The core enforces these integration obligations;
failed outcome persistence withholds normal completion and leaves the attempt consumed.
No success receipt precedes durable
witness acknowledgement.

## 6. Verification, configuration and open work

CS-REQ-020 through CS-REQ-023 allocate the port contract; CS-REQ-024 through
CS-REQ-026 allocate the local file adapter; CS-REQ-027 through CS-REQ-030
allocate configured routing. The in-memory fake exercises
method signatures, payload preservation, correlation, filters and tamper
rejection. Adapter tests reuse conformance assertions and exercise reopen,
cross-process exclusion, corruption, short writes and acknowledgement failures.
Runtime Protocol checks only detect member presence.

`tests/test_endoforge_routing.py` supplies runtime evidence for ordering, storage
failures, outcomes, approval verdicts, chain reopen and trusted CLI configuration.
Bootstrap reads repository-local `cstack.config.json`; the example's `endoforge.path`
resolves relative to that config file. The parent directory must already exist.
It creates a fresh host session id and closes storage at run exit, including errors.
Missing config/section preserves the unconfigured driver; malformed or inaccessible
configured storage never falls back. Request JSON cannot select the port, path or session.
Other hosts must explicitly inject the port and session; AOR composition is unchanged.

Change signatures, envelope version, requirements and matrix together through
repository review. Incompatible payload/hash changes require a new schema
version and migration rules; silently reinterpreting stored records is forbidden.
Independent witnessing and deployment durability qualification remain
open acceptance work. Evidence routing does not implement an Endoforge agent runner or cache.

### Refrigeration CLI acceptance interface

`python -B cli.py --config <host.json> --approver=file:<approvals.db>` consumes `examples/refrigeration-e2e.json` on stdin. The explicit config follows the existing `endoforge.path` contract. For CS-REQ-031, the SQLite file approver requires an existing ApprovalWriter SQLite store containing an exact request-bound verdict from `owner-via-approver`; selecting it makes all domain operations ask. No option creates an approval. Missing, expired, mismatched or spent approvals cannot dispatch. The SQLite header selects this reader; JSON file answers retain the existing TerminalApprover behavior, as do terminal and deny modes.

`tools/e2e_refrigeration.sh` runs the approved acceptance and prints JSON fields `endoforge_implemented`, `approval_id`, `ledger_events`, and `verify_chain`. Two precommits represent the prospective decision and the approval-bearing execution gate; the outcome follows both in the same session. The deny acceptance uses a declined approval and retains no action or outcome.

## 7. Workcell runtime

A goal in the `cstack_forge` domain is one capability call on the RuntimeFace lane. `adapters/endoforge_workcell.py` runs inside `core.execute`, under its decision and grant. It freezes the evaluator in the pinned EndoForge ledger, starts one Node supervisor (`adapters/workcell/supervisor.mjs`) outside every cohort, and exchanges JSON lines with it. `RUNTIMES` is separate from `DOMAINS`, so AOR sessions gain no run authority. `workcell` in host configuration selects the ledger, transport, importable Foundations and decision operations. Request data can name a Foundation; it can't add one.

| Boundary | Rule |
|---|---|
| Candidate | Model text, identified by a hash of its task and source, compiled in the cell by the pinned AssemblyScript 0.28.20, to a WASM kernel exporting exactly `signature`, `reduce` and `memory`. Bad handles, out-of-bounds addresses, traps and top-level host calls are kernel failures that allow repair |
| Foundation import | Module `foundation_<name>`, function `call`, read from the binary and not from a manifest. It must be declared in the request and allowed by host configuration. Anything else fails the `forbidden_effects` gate |
| Foundation result | A host-owned buffer read by handle. The kernel gets no pointer into trusted state. Attribution names the version, route, port hash, source manifest hash, input and output hashes, for the first 64 calls; the receipt counts the rest in `attributions_omitted`. A refused call fails the run whatever the kernel does with it |
| Decision proposal | An effect, returned as data: `{capability: "poodo", operation: "propose_decision", payload}` with a closed payload. The host fills every identity. Each gets its own goal and core, so the running core stays single-caller |
| Judgement | Every case needs a held-out check. Checks run against the pinned Foundation kernel, compare as exact decimals, and never reach the prompt |
| Refusal | A refused or invalid effect adds a name the frozen evaluator doesn't allow, so the gate fails whatever the kernel returns. A refusal ends the run; it isn't repaired past |
| Lost cell or supervisor | `outcome_unknown`: an inconclusive receipt where a pool survives, `indeterminate`/`unknown` in the outcome, no retry. If nothing was in flight, or a failure came before dispatch, the outcome is `unavailable`/`not_dispatched` and says nothing ran |
| Lost controller | The next session reads the run ledger. A durable receipt with no candidate left in flight becomes `candidate_passed_recovered` or `candidate_rejected_recovered`; anything else is recorded `process_ended_before_outcome`/`unknown`, once. Each forge session keeps a core ledger in `<ledger>.core/`, the next session's core replays a lost one, and the run result lists `unresolved_attempts`. When a session ends, its core ledger is renamed `.recovered` if it holds an outcome whose certainty is `unknown`, and `.closed` otherwise, so later sessions keep listing that attempt in `unresolved_attempts` |
| Ledger journal | The vendored group-commit ledger writer journals in `<ledger>.journal/`, beside the run ledger. The supervisor sets `ENDOFORGE_LEDGER_JOURNAL` to that path for every run, overriding any inherited value, so a run writes nothing under `~/.local/state/endoforge` |
| Runtime pin | A run verifies `contracts/SOURCE-PINS.json` for every file in `adapters/workcell` and the vendored engine before starting, and `adapters/workcell` is the frozen tree. A local writer who changes the pins too isn't caught |
| Coder approvals | Approvals don't reach coder cores. An operation in `workcell.decision_ask_operations` is refused for a coder (`approval_not_routed_to_coders`) instead of running unapproved |

Limits, and what the runtime doesn't prove: V8 has no instruction fuel, so `fuel` counts Foundation calls per round and a hung kernel stops at `jobTimeoutMs`. Workcells aren't an OS sandbox and cgroups are host-dependent. Foundation kernels other than Refrigeration and Template aren't shipped; see [the routes](../verification/foundation-routes.md). The witness is this file's local fsync, not an independent quorum. `CapabilityPort` maps to ToolFace in `poodo_core/ports.py`, so the runtime's inventory row names no port until ADR 005 item 12b is settled.

## 8. Endoforge interfaces Cstack uses

These are the only vendored Endoforge names Cstack code calls at the current pin. A repin that changes any of them changes this interface; see [the repin guide](../guides/how-to/repin-endoforge.md).

| Caller | Endoforge interface | Use |
|---|---|---|
| `adapters/endoforge_workcell.py` | `core.ledger.ledger.Ledger(path)`, `.append(...)` and `.records()` | Opens the run ledger, records the run's task and admitted input, and reads receipts during recovery |
| `adapters/endoforge_workcell.py` | `core.ledger.frozen.FrozenEvaluators(ledger).freeze(...)` | Freezes `adapters/workcell` as the evaluator for one task, bound to the decision |
| `adapters/workcell/supervisor.mjs` | `new IsolatePool({...})`, `ready()`, `run(job)`, `close()` | Options passed: `hostPort`, `size`, `isolation`, `trustedWasmModules`, the `workcellLimits` (`wasmMemoryMaxMb`, `resourceLimits`), `frozenThroughLedger: true`, `hostCalls`, `warm.foundations`, `jobTimeoutMs`, `cgroupRoot` |
| `adapters/endoforge_workcell.py` | `ENDOFORGE_LEDGER_JOURNAL`, read by `vendor/endoforge/tools/ledger_writer.py` | Set to `<ledger>.journal` for every run |
| `adapters/endoforge_workcell.py` | `ENDOFORGE_DUMP_LIST`, read by `vendor/endoforge/core/runtime/dump-list.mjs` and `vendor/endoforge/tools/dump_list.py` | Not set; inherited from the host environment. With `1`, or with `<state>/memguard/dump-list.d` present, the pool and the ledger writer register sheddable memory there and shed on `SIGUSR2`. Cstack passes no `dumpList` option, so the pool uses EndoForge's defaults |
| `tests/test_endoforge_pin.py` | `vendor/endoforge/tests/test_endoforge_core_boundary.py` | Run as the import-boundary check |

Inside the pool, the vendored workcell calls the vendored gates and evaluator (`core/engine/`) and the ledger bridge, and loads Cstack's `adapters/workcell/host-port.mjs` as its host port. The capacity planner in `core/runtime/capacity/` is vendored but not called. Endoforge's own interface documents for these parts are its [ledger ICD](https://github.com/Akilleez-QA/endoforge/blob/main/docs/interfaces/ledger-icd.md) and [capacity ICD](https://github.com/Akilleez-QA/endoforge/blob/main/docs/interfaces/capacity-icd.md); they describe Endoforge `main`, which may be ahead of the pin.

## Requirements addressed

CS-REQ-020 to CS-REQ-030 (evidence port, file adapter and configured routing); CS-REQ-031 (refrigeration acceptance); CS-REQ-032 to CS-REQ-035, CS-REQ-068 and CS-REQ-069 (workcell runtime). See the [verification matrix](../verification/verification-matrix.md) for the tests.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.x | 2026-10 to 2026-11-08 | various | Earlier versions | See `git log -- docs/icd/icd-endoforge.md` |
| 2.0 | 2026-11-08 | 6ae5481fd302439dabb23044d1b715ac8c4a9bec | Family standard header and disclaimer; requirements-addressed section | docs/nasa-standard PR |
| 2.1 | 2026-11-08 | 84cd19d238a057b1c07af63e64b50edfb515d615 | Pin commit updated; ENDOFORGE_DUMP_LIST row added to section 8 | PR #79 |
| 2.2 | 2026-11-09 | 6088dd4 | Lost-controller row: a session that ends with an unknown outcome keeps its core ledger as `.recovered` | PR fixing the 2026-11-09 backfill-review findings |
