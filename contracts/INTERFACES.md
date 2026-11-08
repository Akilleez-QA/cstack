# Cstack interface contract 0.1

## Ownership and dependency direction

- poodo_core contains immutable records, core-owned ports, authority policy and inherited lifecycle control. It imports no concrete Foundation, subprocess, MCP, provider SDK or adapter module.
- extensions/foundation_math.py binds a MathExtension and capability to FoundationMath(PoodoCore).
- adapters/math_stdio.py maps semantic capability calls to the unchanged custom Math bridge; adapters/execution.py owns the replaceable local process boundary.
- adapters/memory_ledger.py provides bounded single-process append-only events.
- bootstrap.py alone selects concrete implementations, fixed paths and host authority.
- cli.py drives the core with versioned structured local input. It is not a network server or MCP endpoint.

Ports describe purposeful conversations, not a framework layer around every function. Arbitrary plugin names, commands, executable paths and mutable grants are not request data.

## Base and extension contract

DomainExtension version poodo.domain-extension/0.1 provides descriptor, admit_goal, validate_call and interpret. It returns immutable data and scoped proposals. It receives no core reference, ledger writer or authority mutator.

PoodoCore owns start_goal, revise_goal, advance, decide, execute and evidence admission. Supported extensions cannot override protected inherited control methods. This prevents accidental API misuse; trusted Python code is not a hostile-code security boundary, and typing.final is not runtime enforcement.

Domain extensions own domain semantics and acceptance criteria. Core guards authority, identity and evidence ceilings without inventing mathematical or engineering meaning. This release has no automatic goal closure, formal-proof promotion or effect-grant API.

Contract versions fail closed when unsupported. Rerun extension conformance and migration fixtures when changing core or domain contracts. Shared control must not make assumptions from one Foundation apply to another.

## Core records

GoalContract binds goal ID, positive revision, domain ID, objective, assumptions, exclusions and versioned acceptance criteria. A CapabilityRequest binds the exact goal revision, decision ID, capability ID, operation, arguments and required evidence. Decisions pin request bytes, grant identity and a prospective oracle, expected observation, success boundary and failure meaning.

Host-supplied authority bounds domain, capability, operations, goal IDs and call budget. JSON requests, hook returns and tool text cannot create or enlarge it. Recheck phase, goal revision, request digest and authority immediately before dispatch. Record an action before execution; consume its decision once. A retry is a new explicit attempt, not a reused correlation ID.

Phases are pontificate, observe, orient, decide and orchestrate. Structural gates require research references and 20 distinct option IDs where appropriate. Counting IDs does not establish material option diversity, adequate research or good reasoning. Preauthored example checkpoints are labeled fixtures, not autonomous research.

Ledger events retain proposals, observations, inferences, decisions, actions, outcomes, learning and corrections separately. A raw tool result is evidence of a bounded observation, not corroboration or truth by itself. Corrections reference historical events rather than overwrite them. `adapters/memory_ledger.py` is single-process memory; durability comes only from a ledger the host binds, such as `adapters/durable_ledger.py` for forge sessions or the witnessed ledgers of DECISION-004 and `EndoforgePort`.

## Capability JSON contracts

The adjacent JSON Schemas specify poodo.capability-request/0.1 and poodo.capability-result/0.1. They are semantic boundary records, not MCP wire formats. The local driver uses a separately versioned wrapper.

CapabilityOutcome separates execution_status, execution_certainty, assessment and epistemic_status. Certainty is not_dispatched, responded or unknown. Timeout, cancellation or crash after dispatch may mean unknown execution, never proof of nonexecution. Both formal_proof and runtime_goal_acceptance are false.

Keep the complete accepted raw result, request hash, source manifest hash, inventory hash and distinct attempt ID. A cache key, candidate identity, executable artifact hash and evaluation receipt are different identities. Hashes identify bytes, not authenticity or permission.

A completed false identity is an observed negative mathematical answer, not a protocol failure and not proof. Tool errors remain distinct from protocol/resource/unavailability failures. Malformed or conflicting evidence is quarantined, and a bounded terminal event must survive admission failure. Preflight the entire eventual ledger event, including escaped Unicode, nesting and node count, before append.

## Foundation Math v014 adapter

SOURCE-PINS.json binds the complete 561-file source manifest and canonical 19-tool inventory. Verify them before execution; validate preservation after tests. Map tool names one-to-one and forward only their exact arguments. POODO metadata must not be injected into the closed Math arguments.

The trusted local profile uses fixed argv [python, -B, -m, foundation_math_bridge], fixed source root, no shell and no request-controlled environment. The adapter owns initialization, framing, deadline, bounded stdout/stderr, cleanup and outcome classification. A subprocess is not an OS sandbox.

The protocol is foundation-math-jsonrpc/1, explicitly not MCP. Initialization uses that exact protocol ID. Request frames are at most 65,536 bytes; response frames are at most 1,048,576 bytes excluding LF. The 353,012-byte canonical inventory exceeds the input cap, so response decoding is separate. Exact output integers may exceed input numeric caps.

Math input rejects duplicate keys, floats/exponents/nonfinite values, malformed UTF-8 and over-budget structures. Future domains declare their own numeric/unit semantics; generic core must not silently inherit Math's integer-only transport profile. No automatic network schema resolution is allowed.

Validate JSON-RPC ID equality including type, exact result/error envelope, tool identity, literal boolean isError and fixed false proof/acceptance flags. Validate outputSchema against structuredContent. The first four schemas intentionally leave receipt details loose, so schema success alone is not sufficient to establish correspondence or meaning. Preserve receipts without rewriting them or erasing negative verdicts.

## Endoforge and future domains

Endoforge is intended to produce, qualify, preview, revise, activate and dispose task-specific UI/software under POODO governance. Foundations supply domain primitives and verifiers to generated artifacts. Keep host-owned UI state and exact revision, action and source bindings stable across disposable generation.

Generation and lower execution adapters are distinct. A JavaScript/WASM boundary must preserve exact numbers by an explicit supported encoding or reject them; it must not coerce arbitrary-precision Math to Number. Runtime CPU/memory/time limits are profile-specific, not universal core guarantees.

Endoforge UI/software generation and Lean verification are unimplemented. Foundation Engine is implemented only as two read-only validators (`extensions/foundation_engine.py`, `adapters/engine_stdio.py`). The Endoforge workcell runtime runs governed `cstack_forge` goals; its boundaries are in `docs/icd/icd-endoforge.md` section 7. Foundation Refrigeration v0.1 is implemented only as described below and in ADR 002; its rules, reference-plant and determination parts remain unimplemented. Do not infer availability from reserved interfaces.

## Foundation Refrigeration v0.1 adapter (ADR 002)

SOURCE-PINS.json binds the Foundation's complete source manifest and its canonical 7-tool inventory. The adapter verifies both before dispatch and after each accepted response. It maps tool names one-to-one and forwards only their exact arguments. The trusted profile uses the fixed argv [python, -B, -m, foundation_refrigeration_bridge] and the fixed root foundations/refrigeration. The executor module is a host allowlist entry, never request data.

The protocol is foundation-refrigeration-jsonrpc/1, explicitly not MCP. Its numeric profile is the domain's own: finite decimal literals with explicit units, and no exponent, NaN or Infinity. Input frames are at most 65,536 bytes and response frames at most 1,048,576 bytes. Duplicate keys and over-budget structures fail closed. Math's integer-only profile is not applied to Refrigeration, and Refrigeration's profile is not applied to Math.

The adapter validates the outputSchema, the tool identity, the false proof and acceptance flags, and the fixed receipt boundary block (observation only; no determination, diagnosis or control action). It also checks that the receipt input digest equals its own digest of the exact arguments, and that isError, the assessment and the receipt status agree. A tool error, such as out of range or a blend side not given, is kept as tool_error and is never treated as a result. Every receipt carries Evidence. CHECK values are not approved, and DISPUTED decisions are not chosen.

## MCP and formal verification

MCP is an application protocol with transport bindings. Any later adapter must state its tested revision and demonstrate actual client interoperability. Current 2026-07-28 uses per-request metadata and server/discover; legacy 2025-11-25 uses initialize/initialized. A legacy SDK does not prove current-revision support.

`adapters/mcp_stdio_client.py` is an MCP client CapabilityPort with tested revision **2025-11-25** only. It is not 2026-07-28. The host fixes:
- the server argv, cwd and env allowlist;
- per tool, a read/write/execute effect class and a sha256 pin of the whole reviewed tools/list entry (`tool_sha256`), including title, icons, execution and `_meta`;
- optionally, `ignored_tools`: names that may be listed but are never callable. The default is an exact catalog match.

The live catalog must match the allowlist and its pins. Each pinned entry must fit the 2025-11-25 Tool shape. Each schema is checked in its declared `$schema` dialect (2020-12 by default; 2019-09 and draft-07 are also supported; any other dialect is refused), all before dispatch. A JSON-RPC error to `initialize`, such as one from a 2026-07-28-only server, is `mcp_revision_unsupported`. A host read tool must carry `readOnlyHint: true`, since a missing hint defaults to false. Arguments are validated against the pinned inputSchema and `structuredContent` against the outputSchema. Outcomes map as follows:

| Event | Status |
|---|---|
| `isError` | `tool_error` |
| JSON-RPC error | `protocol_error` |
| Timeout, crash or cancellation after dispatch | certainty `unknown` |

Results are fenced as `raw_result = {provenance: "mcp:<capability_id>", trust: "untrusted", mcp_result}`. Cleanup kills the server's process group. A descendant that calls setsid escapes it. The env allowlist is not secret isolation from a same-user server.

Interop evidence (2026-10-25):
- A fixture server in `tests/test_mcp_stdio_client.py`.
- The official `@modelcontextprotocol/sdk` 1.30.0 TypeScript server (LATEST_PROTOCOL_VERSION 2025-11-25), via the opt-in `CSTACK_MCP_SDK_ESM` test: a completed call, an `isError` call and a catalog refusal.
- `@modelcontextprotocol/server-filesystem` 2025.7.1 (SDK 1.17.0), which negotiates 2025-06-18, was refused before dispatch.

A future formal-proof capability must pin the exact challenge/theorem, toolchain, imports, artifact, transitive axiom policy, checker and isolation identity. Compilation success alone does not establish the intended theorem. Generated proof source is executable code. Missing Lean is unavailable, never a passing proof check.

## Ask and deny authority (ADR 003)

A grant may list `deny_operations` and `ask_operations`.
- **Deny** in any grant refuses the operation at decide and at execute. The first refusal per exact request is recorded, and the record count is bounded.
- **Ask** in any grant for the capability makes approval mandatory. Execute dispatches only with a host `ApprovalRecord` that binds:
  - the exact decision id, request digest, goal id and goal revision;
  - the configured approver (in Cstack, `owner-via-approver`).

  The record must also be unexpired by the host's integer clock, and `ApprovalPort.consume()` must confirm single use durably.
- **No approval** raises `ApprovalPending`. It is recorded once, and nothing is dispatched or consumed.
- **A bound decline** is honoured even if expired. It is recorded, consumes the decision and raises `ApprovalDeclined`. It never becomes a tool outcome.
- **Ledger capacity is reserved before any approval is spent**, so a capacity refusal does not burn an approval or lose a decline. This does not make approval consumption and subsequent ledger writes atomic; see the interrupt limits below.
- **Requests, hooks and tool text cannot create, select or alter approvals.** Subclasses cannot shadow core state.

## Goal liveness (PR 6)

Every open goal names who owns its next action. Logs, PIDs, comments and evidence are not liveness.
- **The host supplies it.** `record_liveness(LivenessRecord)` binds the goal id and current revision, an `owner` identifier, a required `waiting_on` (`agent`, `approval` or `external`), a short reason and an optional `review_by` deadline on the host clock. Requests, hooks and tool text cannot reach it.
- **Changes are ledgered.** Each change appends one `liveness_set` decision with the prior record. Supplying the same record again appends nothing.
- **`liveness(goal_id)` evaluates the claim now.** A goal has no live path when it has no record, the record names a stale revision, the bounded wait has expired, or it waits on `approval` while no ask decision for that revision is pending or the owner is not the configured approver.
- **`goals_without_live_path()`** lists every open goal with no live path and the reason.
- **It reports; it does not gate.** Liveness never closes a goal, changes a phase or grants authority. Requiring it at a phase exit is a later, separate decision.

## Budget hard stop (PR 9)

The host can bound spend per AOR. A grant names its `aor_id`; the host supplies one `CostBudget` (AOR, positive integer limit, unit such as `usd_micros`) per AOR and a `CostPort` that prices calls.
- **No unbudgeted bypass.** Once any budget or grant AOR is configured, every grant must name a budgeted AOR and a cost port must be present, or the core refuses to start.
- **Unknown is unaffordable.** An estimate that is `None`, not a bounded non-negative integer, or raised by the port refuses the call at decide and at execute. So does an estimate that does not fit the remaining limit. The first refusal per exact request is recorded (`budget_refused`), bounded.
- **Reserve, then settle.** Execute checks the budget before any approval is spent, reserves ledger room for settlement and a pause, then holds the estimate in the action event (`cost_reserved`). After the outcome is recorded, `budget_settled` releases a hold that never dispatched, charges the host's actual price, or keeps the whole hold when the actual is unknown (timeouts, crashes).
- **Hard stop.** When committed spend reaches the limit, the AOR pauses (`budget_paused`). A pause refuses new decisions and executions, including already-decided ones, until the host calls `lift_budget_pause(aor_id, new_limit)` with a limit above committed spend (`budget_pause_lifted`). Revising or starting goals does not lift it.
- Requests, hooks and tool text cannot set prices, budgets or pauses. Cores built without budgets behave and ledger exactly as before.

## Lanes (ADR 005)

Every grant and every capability names one of eight port lanes. They are exact strings, defined once as `poodo_core` `LANES`: `HMIFace`, `TruthFace`, `RuntimeFace`, `EvidenceFace`, `SupervisorFace`, `ToolFace`, `ReadModelFace`, `LearningFace`.
- **Required, no default.** `AuthorityGrant(..., lane=...)` and `CapabilityDescriptor(..., lane=...)` take `lane` as a required keyword. A grant or descriptor without one does not construct, and an unknown lane or a `str` subclass is refused. Existing grants were migrated explicitly: every Foundation capability and every `bootstrap.py` grant is `ToolFace`.
- **The core refuses a mismatch.** At construction, a grant whose lane differs from its capability's declared lane is refused. At decide and at execute, the core refuses the call unless the grant's lane equals the declared lane and the bound port's `describe()` still equals the declared descriptor. A port that fails to describe, or describes another lane, is refused. Execute re-checks the current grant and port, so a decision made earlier does not carry its lane forward.
- **Recorded once, bounded.** The first refusal per exact request appends one `lane_refused` decision: the grant, capability and described lanes (each `null` when invalid or absent) and a reason (`lane_mismatch`, `descriptor_drift` or `read_only_lane`). The record count is bounded like `denied` and `budget_refused`, by `PoodoCore.MAX_NOTED`, which a subclass cannot override.
- **No re-entry.** `describe()` runs inside decide or execute, under the core-wide re-entrancy guard below, so the port cannot call back into the core before the call is bound. The lane is re-validated as an exact lane string at every check.
- **Liveness.** An approval wait whose every pending decision has been lane-refused reports `approval_blocked_by_lane`, not live. This is conservative: it clears when the decision executes.
- **Order.** The lane check runs after deny and before budget and approval. A refused call holds no spend, spends or looks up no approval, and does not consume its decision; a bound decline is still honoured once the lane matches.
- **Read-only lanes never execute.** Every grant operation is an operation for `execute`, the core's only dispatch path. So a `ReadModelFace` or `LearningFace` grant is refused at construction, and the core refuses to bind a capability in either lane. Those lanes attach through their own ports (ADR 005 items 8 and 9), not through `CapabilityPort`.
- **Host-only.** Lanes come from host grants and extension descriptors. A request cannot carry a lane (its fields are exact), and arguments and tool output naming a lane are ignored. A subclass body cannot override `_check_lane` or shadow its state; as elsewhere in the core, this guards against accidents, not hostile Python that patches instances at runtime.
- **AOR effect sets.** A fleet bot may name an optional `lane` for its effect set (`contracts/aor.schema.json`). A `ReadModelFace` or `LearningFace` effect set must deny every effect but `read`. `aors/fleet.json` assigns no lanes yet; that is a follow-up for the owner's review. A later change cross-checks grant lanes against `contracts/ADAPTERS.json` in `bootstrap.py`.

## Re-entrancy guard

A `PoodoCore` is **single-caller**: the host must serialise all calls (reads and mutations) from different threads. The guard only refuses same-call-stack mutation re-entry by host/port code; it provides no cross-thread safety or refusal guarantee. The public mutating operations are `start_goal`, `revise_goal`, `advance`, `decide`, `execute`, `record_liveness` and `lift_budget_pause`.
- **Refused, nothing changed.** While an operation holds the guard, a nested mutation from a port (`describe`, `invoke`), a hook (`admit_goal`, `validate_call`, `interpret`) or a host callback (`ApprovalPort`, `CostPort`, clock, `LedgerPort`, cancellation) raises `ReentryRefused` (a `ContractError`) before the nested call reads or changes any state. So a callback cannot dispatch a decision twice, spend an approval twice, overspend a budget, move a phase under a decision or interleave ledger events. Mutations are also refused until construction finishes.
- **Reads may re-enter on the same call stack.** `snapshot`, `budget`, `descriptor`, `ledger`, `liveness` and `goals_without_live_path` change nothing, so a port may call them mid-operation and sees the state as it stands. A top-level `ledger`, `liveness` or `goals_without_live_path` also holds the guard while it calls host code (ledger read, clock), so that code cannot start a mutation in the middle of a read. The host's serialisation must cover these reads too.
- **Contained callback failures after the action event.** A cancellation object's `is_set` failure counts as set (nothing is dispatched). Failures from `invoke`, outcome admission/`interpret` or `CostPort.actual` are contained at those callback boundaries. A caught `KeyboardInterrupt`, `SystemExit` or other non-`Exception` `BaseException` is held until guard exit. If subsequent ledger operations succeed and no further interrupt occurs, the outcome and any budget settlement are written before it is re-raised. `LedgerPort.reserve` and `append` failures are not contained, including outcome, `budget_settled` and `budget_paused` appends; they can leave incomplete records or unsettled holds. Arbitrary asynchronous interrupts outside the contained boundaries have no settlement guarantee.
- **Interrupt limits.** Before the action event, interrupts propagate without rollback: prior ledger events or external effects may already exist. In particular, `ApprovalPort.consume` may have spent an approval before its event or the action is recorded, so retry can fail without any dispatch. An interrupt after the guard token is acquired but before its `try/finally`, or during guard release, can leave the core refusing later mutations; the host must discard and rebuild that core. Reads do not establish that such a core is usable.
- **Not shadowable.** The guard and its state are core state (`_guard`, `_busy`, `_interrupted`) and the guarded methods are final. No base in a subclass's MRO, before or after `PoodoCore`, may shadow them or define `__getattribute__`, `__getattr__`, `__setattr__` or `__delattr__`. The guard uses `object.__getattribute__`; the MRO check prevents descriptors from shadowing guard state, and a class-level `__dict__` is never consulted. `__init__` refuses to run twice on one core. This intentionally breaks compatibility with extensions using attribute-hook mixins, even harmless logging or delegation hooks; neither current extension in `extensions/` defines these hooks. As elsewhere in the core, this guards against accidents, not hostile Python that patches instances at runtime.
- **Per core, one core per ledger store.** The guard belongs to one core: two live cores must not share one ledger store (log, file, or node log), whether through one port object or several. One core's appends would use room the other reserved before dispatch. Bootstrap's `build_core` registry rejects duplicate live bindings in this process, and releases a binding when the core is garbage-collected. Current builders use fresh in-memory ledgers; path-backed builders must supply the underlying `store_path` to the helper. Paths are canonicalised for relative and symlink aliases; hosts must also exclude hard-link aliases and arrange exclusive store ownership across processes. The registry does not provide a cross-process file lock.

## Capacity admission (ADR 005 item 5a)

`AdmissionPort` is a SupervisorFace port. Its one method, `capacity(aor_id)`, returns the host's `CapacityLimits` for one AOR:
- `max_open_goals`, `max_live_attempts` (dispatched and not yet settled) and `max_pending_asks` (the approval queue);
- `live_cap`, the host's current dial on live attempts, from 0 to `max_live_attempts`. **0 pauses the AOR**;
- optional `other_open_goals`, `other_live_attempts` and `other_pending_asks`: usage the host sees outside this core, added to the core's own count;
- an optional `soonest_reset_at` (epoch seconds), for the later multi-account design.

Every count is a bounded non-negative `int`.
- **Fail closed at startup.** With `admission=` configured, every grant must name an AOR, and the port must return a valid record for every AOR, or the core does not construct. A grant naming an AOR still needs a `CostBudget` and a `CostPort` (PR 9).
- **Consulted live, under the re-entrancy guard.** The core asks the port again at every check, so the host can lower a cap or pause at any time:
  - `start_goal`: the pause, then open goals for every AOR whose grants list the goal. A goal no AOR's grant lists is refused (`no_aor`). The core has no goal closure, so every goal it has started stays open and counts.
  - `decide`, only when the call would become an ask: the approval queue. An ask is queued while it is unconsumed, names its goal's current revision and its grant has calls left, so a stale or exhausted ask frees its slot. The pause is not checked here; it stops the ask at execute.
  - `execute`: the pause, then live attempts against `live_cap`. Execute runs alone under the guard, so the core's own live count is at most 1 and 0 when checked; `other_live_attempts` carries the host's wider view.
- **Unknown refuses.** `None`, any other type, a record for another AOR, a record whose fields no longer validate, or a raise (including `ReentryRefused` from a port that calls back into the core) refuses the call (`unknown_capacity`).
- **Refusals raise `CapacityRefused`** (a `ContractError`, carrying `soonest_reset_at`). The first refusal per exact request and gate appends one `capacity_refused` decision: the gate, AOR, the goal id and digest or the decision id and request digest, the reason (`open_goals`, `live_attempts`, `approval_queue`, `paused`, `unknown_capacity` or `no_aor`), the limit and the count in use, and `soonest_reset_at` only when the port supplied one. The records are bounded by `PoodoCore.MAX_NOTED`, like `budget_refused`.
- **Order.** deny, then lane, then capacity, then budget, then approval. A capacity refusal holds no spend, looks up or spends no approval, and does not consume its decision. The decision executes once capacity allows.
- **Live means unsettled.** An attempt is live from its action event until its outcome and settlement are written. One whose outcome fails to record stays live, which fails closed, as its budget hold does. `soonest_reset_at` is bounded so a refusal record always fits the ledger; like `budget_refused`, the record is appended without a prior reservation.
- Requests, hooks and tool text cannot reach the port or its limits. A subclass cannot override the checks or shadow their state. Cores built without `admission=` behave and ledger exactly as before. Leases (item 5b) are out of scope.
