# Cstack software requirements specification

| Field | Value |
|---|---|
| Document ID | CSTACK-SRS |
| Version | 2.0 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-08 |
| Baseline commit | 6ae5481fd302439dabb23044d1b715ac8c4a9bec |
| Applies to | cstack main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see [SMP §1](../plan/software-management-plan.md#1-software-classification-self-assessed)) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

## 1. Introduction

### 1.1 Purpose and audience

This document states what Cstack shall do and how each statement is checked. It is written for maintainers changing the host, reviewers checking a pull request, and agents that need a stable list of obligations. The [verification matrix](../verification/verification-matrix.md) maps every requirement to tests. `python -B tools/check_trace.py` checks the mapping.

### 1.2 Scope

The requirements cover the control core (`poodo_core/`), the composition root (`bootstrap.py`), the CLI driver (`cli.py`), the adapters under `adapters/`, the domain extensions under `extensions/`, the forge runtime, and the repository tools whose behaviour is tested. Vendored Foundations (`foundations/*`), vendored backends (`vendor/*`) and the POODO skill snapshot (`reasoning/poodo/`) carry their own requirements upstream. Cstack's requirements here cover only how the host pins and calls them.

Trust assumptions: the trusted host supplies implementations, roots, grants, configuration and inventory. Requests are untrusted structured data. Foundation operations provide bounded observations. Engineering, safety, compliance and general mathematical truth are outside this specification. The process boundary assumes a trusted single operator and does not isolate hostile source code.

### 1.3 System overview

Cstack (code name Mjölnir) is the host of the Cstack family. It composes a POODO control core with domain extensions, Foundation adapters, a witnessed EndoForge ledger and the EndoForge workcell runtime. See the [design description](../architecture/architecture.md) and the interface documents in [`docs/icd/`](../icd/).

## 2. Requirement record format

Each requirement has an ID, one "shall" statement, a rationale, a derivation (source paths), an allocation (a component in [SDD §4](../architecture/architecture.md#4-decomposition-and-allocation)), a verification method (T test, A analysis, I inspection, D demonstration) and a status (Proposed, Baselined, Deleted). IDs are never reused. CS-REQ-001 to CS-REQ-035 keep the identifiers and obligations of the earlier baselines. CS-REQ-036 onwards were added in version 2.0 from behaviour that existing tests already check. Each test is named in the verification matrix, not here.

## 3. Functional requirements

### 3.1 Composition and authority

### CS-REQ-001 — Composition

The host shall select Foundation implementations and source roots through `bootstrap.DOMAINS`; an unregistered domain shall be rejected without fallback.

- Rationale: one registry keeps implementation choice with the host, not with request data.
- Derivation: `bootstrap.py`
- Allocated to: SDD-C1
- Verification: T, plus inspection of `bootstrap.py`
- Status: Baselined

### CS-REQ-002 — Authority lanes

The host shall reject a grant whose capability has no inventory mapping, whose adapter is absent, or whose lane differs from the adapter inventory.

- Rationale: a grant must match the reviewed adapter inventory before a core is built.
- Derivation: `bootstrap.py`; `contracts/ADAPTERS.json`
- Allocated to: SDD-C1
- Verification: T
- Status: Baselined

### CS-REQ-014 — Ledger ownership

The composition root shall refuse a second live core over the same canonical ledger path in the same process.

- Rationale: two cores appending to one ledger would interleave unrelated histories.
- Derivation: `bootstrap.py`
- Allocated to: SDD-C1
- Verification: T. Cross-process exclusion is a host responsibility.
- Status: Baselined

### CS-REQ-036 — Adapter inventory contract

`contracts/ADAPTERS.json` shall validate against `contracts/adapters.schema.json` (JSON Schema Draft 2020-12), assign each adapter to exactly one of the eight core lanes, refuse duplicate adapter and lane pairs, require a port for an adapter that sits behind one, and list exactly the adapter files present in the checkout. A strategic dependency shall need a decision record.

- Rationale: the inventory is the reviewed list of what may hold authority; drift between it and the checkout must fail.
- Derivation: `adapters/adapter_inventory.py`; `contracts/ADAPTERS.json`; `contracts/adapters.schema.json`
- Allocated to: SDD-C3
- Verification: T
- Status: Baselined

### CS-REQ-037 — Grant lane enforcement

The core shall accept only the eight exact lane names, refuse a grant whose lane differs from its capability descriptor at decide and again at execute (rechecking the current grant), give the read-only lanes no execute path, record each lane refusal once in bounded records, and check the lane before approval and budget so a refusal spends nothing.

- Rationale: lanes separate kinds of authority; a drifting port must not gain an execute path.
- Derivation: `poodo_core/core.py`; `poodo_core/models.py`
- Allocated to: SDD-C2
- Verification: T
- Status: Baselined

### CS-REQ-066 — Optional domains

The composition root and CLI shall import and run when an optional Foundation directory (for example `foundations/refrigeration/`) is absent, refuse that domain, and still run the registered ones; the CLI shall reject unregistered domains and float values in request documents.

- Rationale: a partial checkout must fail closed per domain, not as a whole.
- Derivation: `bootstrap.py`; `cli.py`
- Allocated to: SDD-C1
- Verification: T
- Status: Baselined

### 3.2 Control core

### CS-REQ-012 — Decision consumption

The core shall consume decision identity so repeated execution does not automatically retry the capability.

- Rationale: an automatic retry could repeat an effect.
- Derivation: `poodo_core/core.py`
- Allocated to: SDD-C2
- Verification: T
- Status: Baselined

### CS-REQ-013 — Goal revision

The core shall deny a decision bound to a stale goal revision and preserve its history.

- Rationale: a decision made for an older goal must not act on a revised one.
- Derivation: `poodo_core/core.py`
- Allocated to: SDD-C2
- Verification: T
- Status: Baselined

### CS-REQ-038 — Approval policy

The core shall dispatch `allow` operations without approval, let `deny` win and record it, dispatch nothing for an `ask` without a bound approval, require each approval to bind the exact request, goal revision, approver and time, refuse reuse of an approval for another decision or another core, and record a decline before consuming the decision without treating it as tool output.

- Rationale: approvals are authority; they must be exact and single-use.
- Derivation: `poodo_core/core.py`; `poodo_core/policy.py`
- Allocated to: SDD-C2
- Verification: T
- Status: Baselined

### CS-REQ-040 — Budget hard stop

For a budgeted grant, the core shall reserve the estimate before dispatch and settle the actual charge, pause decisions and executions at the limit until the host raises it, treat an unknown estimate or a failing cost port as unaffordable, keep the whole hold when the actual cost is unknown, release the hold of a call cancelled before dispatch, and refuse a plain grant beside a budgeted one.

- Rationale: spending must stop at the host's limit even when costs are unknown.
- Derivation: `poodo_core/core.py`; `poodo_core/policy.py`
- Allocated to: SDD-C2
- Verification: T
- Status: Baselined

### CS-REQ-041 — Capacity admission

When the host configures capacity limits, the core shall enforce open-goal, live-attempt and approval-queue limits, refuse before dispatch while keeping the decision, apply checks in the order deny, lane, capacity, then budget and approval, refuse startup on missing or invalid limits, refuse a call when the capacity port raises, answers unknown or re-enters the core, and record each refusal once in bounded records.

- Rationale: capacity refusal must happen before anything is spent and must fail closed.
- Derivation: `poodo_core/core.py`; `poodo_core/policy.py`
- Allocated to: SDD-C2
- Verification: T
- Status: Baselined

### CS-REQ-042 — Core request and outcome admission

The core shall deny unknown domains, goals and operations without dispatch, reject forged authority fields, boolean or non-finite revisions and contract version or ceiling mismatches, quarantine dishonest outcomes and binding mismatches, keep input snapshots and ledger records detached from caller objects, enforce ledger, document and goal budgets before dispatch, and prevent subclasses from overriding protected methods.

- Rationale: the core is the one place where untrusted request data meets authority.
- Derivation: `poodo_core/core.py`; `poodo_core/models.py`
- Allocated to: SDD-C2
- Verification: T
- Status: Baselined

### CS-REQ-043 — Re-entrancy guard

The core shall refuse every mutating call made from a hook or from another thread while an operation runs, allow reads to re-enter, refuse a mutation hosted inside a read, and re-raise an interrupt only after the outcome and settlement are recorded.

- Rationale: hooks and threads must not dispatch a decision twice, spend an approval twice or overspend a budget.
- Derivation: `poodo_core/core.py`
- Allocated to: SDD-C2
- Verification: T
- Status: Baselined

### CS-REQ-044 — Crash recovery accounting

After a restart over a ledger that holds an attempt with no recorded outcome, the core shall record one `unknown` outcome for it, refuse to rerun the same decision or request identity, keep the whole budget hold of that attempt, restore budget spend, grant uses, pauses and lifts from the ledger without new events, charge a settlement interrupted by a kill exactly once, and refuse to start over a ledger it cannot read.

- Rationale: a crash must never turn into a free retry or a lost charge.
- Derivation: `poodo_core/core.py`; `poodo_core/policy.py`
- Allocated to: SDD-C2
- Verification: T
- Status: Baselined

### CS-REQ-045 — Unresolved attempts

The core shall list every attempt whose outcome is unknown, with its original identities, across repeated restarts and kills during recovery, and shall never list an attempt that returned an answer.

- Rationale: the operator needs one place to see work that may or may not have happened.
- Derivation: `poodo_core/core.py`
- Allocated to: SDD-C2
- Verification: T
- Status: Baselined

### CS-REQ-046 — Goal liveness

The core shall report a new goal as having no live path until the host names an owner, make the old owner stale on revision, count an approval wait as live only while a real ask is pending for the configured approver and within its host-clock bound, record each change once with the prior record, and never close goals or change authority through liveness.

- Rationale: liveness is a report for the operator; it must not act.
- Derivation: `poodo_core/core.py`; `poodo_core/models.py`
- Allocated to: SDD-C2
- Verification: T
- Status: Baselined

### CS-REQ-075 — Replaceable adapters

The core shall import only allow-listed standard-library modules, and each named lane suite shall have a fake implementation of its port, so that adding a fake requires no change to `poodo_core/`.

- Rationale: adapters must be replaceable without touching the control core (DECISION-005).
- Derivation: `poodo_core/`; `tests/replaceability/compose.py`
- Allocated to: SDD-C2
- Verification: T
- Status: Baselined

### 3.3 Foundation adapters and process execution

### CS-REQ-003 — Math source identity

The Math adapter shall verify the pinned source manifest identity, listed file count and every listed file digest before dispatch and after a completed exchange.

- Rationale: results must be attributable to reviewed bytes.
- Derivation: `adapters/math_stdio.py`
- Allocated to: SDD-C5
- Verification: T, plus inspection of check placement before and after exchanges
- Status: Baselined

### CS-REQ-004 — Source rejection

The Math adapter shall withhold dispatch when its source manifest is missing or changed.

- Rationale: as CS-REQ-003.
- Derivation: `adapters/math_stdio.py`
- Allocated to: SDD-C5
- Verification: T
- Status: Baselined

### CS-REQ-005 — Catalog identity

The Math adapter shall compare the live tool catalog with the pinned inventory before dispatching a tool call.

- Rationale: a changed tool set is a changed interface.
- Derivation: `adapters/math_stdio.py`; `schemas/math-v014-tools.json`
- Allocated to: SDD-C5
- Verification: T
- Status: Baselined

### CS-REQ-006 — Input admission

The Math adapter shall reject floating-point inputs and inputs exceeding its wire limits before dispatch.

- Rationale: exact tools must not receive inexact or unbounded input.
- Derivation: `adapters/math_stdio.py`; `adapters/wire.py`
- Allocated to: SDD-C5
- Verification: T
- Status: Baselined

### CS-REQ-007 — Response admission

The Math adapter shall quarantine mismatched response identities, inconsistent error flags, invalid output schemas and evidence-ceiling violations.

- Rationale: a reply that breaks its contract is not evidence.
- Derivation: `adapters/math_stdio.py`
- Allocated to: SDD-C5
- Verification: T
- Status: Baselined

### CS-REQ-008 — Evidence ceiling

A completed Math tool observation shall retain `formal_proof=false` and `runtime_goal_acceptance=false`; successful execution shall not itself close the goal.

- Rationale: a tool run is an observation, not a proof or an acceptance.
- Derivation: `extensions/foundation_math.py`; `adapters/math_stdio.py`
- Allocated to: SDD-C5
- Verification: T
- Status: Baselined

### CS-REQ-015 — Unavailable engine

The Math adapter shall refuse a `foundation_engine` capability request without dispatch.

- Rationale: Engine is its own domain (CS-REQ-065); the Math adapter must not serve it.
- Derivation: `extensions/foundation_math.py`; `adapters/math_stdio.py`
- Allocated to: SDD-C5
- Verification: T
- Status: Baselined

### CS-REQ-064 — Sibling Foundation adapters

The Film, Refrigeration, Robotics and Template adapters shall check their source pins against the vendored Foundation and `contracts/`, return each tool result with Evidence, retain a bad-argument reply as a tool error, quarantine dishonest replies, never dispatch out-of-profile, unknown or unpinned requests, and refuse cross-domain bindings; each adapter shall be a sibling of the Math adapter, not a subclass.

- Rationale: every Foundation call must be pinned, bounded and attributable.
- Derivation: `adapters/foundation_stdio.py`; `adapters/film_stdio.py`; `adapters/refrigeration_stdio.py`; `adapters/robotics_stdio.py`; `adapters/template_stdio.py`; `extensions/foundation_film.py`; `extensions/foundation_refrigeration.py`; `extensions/foundation_robotics.py`; `extensions/foundation_template.py`
- Allocated to: SDD-C6
- Verification: T
- Status: Baselined

### CS-REQ-065 — Engine adapter

The Engine adapter shall check its pins against `vendor/foundation-engine-v020/` and `contracts/`, admit only the two read-only validators as tool observations, never dispatch exponent or non-finite numbers, quarantine non-finite or overlong reply numbers and dishonest replies, and report out-of-schema input as a bridge error, not an observation.

- Rationale: as CS-REQ-064, for the partially vendored Engine bridge.
- Derivation: `adapters/engine_stdio.py`; `extensions/foundation_engine.py`
- Allocated to: SDD-C7
- Verification: T
- Status: Baselined

### CS-REQ-009 — Deadline

The local bridge executor shall terminate a child that exceeds its configured deadline and retain execution uncertainty.

- Rationale: a hung bridge must not hang the host or count as success.
- Derivation: `adapters/execution.py`
- Allocated to: SDD-C8
- Verification: T
- Status: Baselined

### CS-REQ-010 — Cancellation

The local bridge executor shall honor cancellation without admitting partial output as evidence.

- Rationale: partial output is not a result.
- Derivation: `adapters/execution.py`
- Allocated to: SDD-C8
- Verification: T
- Status: Baselined

### CS-REQ-011 — Output bounds

The local bridge executor shall stop exchanges exceeding stdout or stderr limits.

- Rationale: bounded memory use per call.
- Derivation: `adapters/execution.py`
- Allocated to: SDD-C8
- Verification: T
- Status: Baselined

### 3.4 CLI driver and approvals

### CS-REQ-016 — Unavailable approved-atoms registry

When approved-atom validation is requested without an in-repository Registry provider, the claim-gate CLI shall fail closed with exit status 2, a JSON error on stderr identifying the unavailable Registry, and no success output.

- Rationale: a missing validator must not look like a pass.
- Derivation: `tools/claim_gate.py`
- Allocated to: SDD-C21
- Verification: T
- Status: Baselined

### CS-REQ-017 — CLI approval gate

For a CLI call with effect `ask`, the driver shall require a host ApprovalPort record bound to the exact request, decision, goal revision and named approver before dispatch. Missing approver, explicit denial, missing file answer and unavailable terminal shall deny without a capability action or outcome.

- Rationale: the CLI is a host; it must apply the same approval rule as the core.
- Derivation: `cli.py`; `adapters/terminal_approver.py`; `poodo_core/core.py`
- Allocated to: SDD-C9
- Verification: T
- Status: Baselined

### CS-REQ-018 — CLI approval consumption

The terminal adapter shall accept only an explicit approve answer, issue approval records expiring after five minutes, and durably consume each approval ID at most once across adapter instances. Request JSON shall only restrict existing grants through `ask`, never select approval sources or enlarge authority.

- Rationale: an approval must not be replayed, and requests must not mint authority.
- Derivation: `bootstrap.py`; `adapters/terminal_approver.py`
- Allocated to: SDD-C9
- Verification: T, plus inspection of expiry and grant restriction
- Status: Baselined

### CS-REQ-067 — CLI input admission

The CLI shall reject duplicate keys, floating-point and non-finite numbers, invalid UTF-8, empty documents and documents over 65,536 bytes with exit status 2, accept no path flags, grants or future capabilities from request data, run from a parent directory as a module, and keep completed run history when a later retention limit stops the run.

- Rationale: the CLI reads untrusted documents; only trusted launch options select configuration.
- Derivation: `cli.py`
- Allocated to: SDD-C9
- Verification: T
- Status: Baselined

### CS-REQ-039 — Durable approval store

The SQLite approval store shall give cores a reader with no write path, let a consume succeed exactly once across restarts and racing processes while recording the consumer, allow one final answer per decision, refuse declined and expired approvals at their boundary, and fail closed on a bad clock, a symlinked path or a closed store.

- Rationale: approvals written by the owner must be consumed once, even across processes.
- Derivation: `adapters/approval_store.py`; `adapters/private_sqlite.py`
- Allocated to: SDD-C10
- Verification: T
- Status: Baselined

### CS-REQ-056 — Scheduled approvals

`tools/scheduled_approvals.py` shall list every ask with no recorded answer under a state root, record the owner's yes or no as exactly one ApprovalRecord bound to the digest the owner saw, refuse a digest mismatch, report a broken chain as a problem instead of an ask, read ledgers read-only, show at most five items in its brief, and prevent bot-written text from faking items.

- Rationale: the owner answers from a short, trustworthy list.
- Derivation: `tools/scheduled_approvals.py`
- Allocated to: SDD-C10
- Verification: T
- Status: Baselined

### 3.5 Evidence and ledgers

### CS-REQ-020 — Witnessed append contract

EndoforgePort shall expose typed precommit and outcome appends using DecisionRecord and CapabilityOutcome, returning a record hash as specified by the EndoForge ICD. An adapter shall preserve payloads and bind outcomes to prior precommits in the same session.

- Rationale: port contract for witnessed evidence.
- Derivation: `poodo_core/ports.py`; [ICD §3–4](../icd/icd-endoforge.md)
- Allocated to: SDD-C11
- Verification: T (protocol fake)
- Status: Baselined

### CS-REQ-021 — Chain verification and fail-closed storage

EndoforgePort shall expose whole-chain verification. An adapter shall reject corrupted-chain appends and reads and propagate storage failures without successful receipts or partial evidence; callers shall withhold dispatch on failed precommit and retain uncertainty on failed acknowledgement.

- Rationale: corrupt evidence must never be extended or read as good.
- Derivation: `poodo_core/ports.py`; [ICD §5](../icd/icd-endoforge.md)
- Allocated to: SDD-C11
- Verification: T (protocol fake)
- Status: Baselined

### CS-REQ-022 — Scoped evidence retrieval

EndoforgePort shall expose detached append-ordered records filtered by goal id, session id, or their intersection, requiring at least one filter and returning an empty tuple for no matches after chain verification.

- Rationale: callers read only the evidence they asked for, after verification.
- Derivation: `poodo_core/ports.py`; [ICD §3–4](../icd/icd-endoforge.md)
- Allocated to: SDD-C11
- Verification: T (protocol fake)
- Status: Baselined

### CS-REQ-023 — Authority and implementation status

The EndoForge interface shall allocate policy to POODO and witnessed storage to EndoForge, without granting execution, proof or goal acceptance. Runtime integration status shall distinguish configured evidence routing from agent running and caching.

- Rationale: storage must not become a second authority.
- Derivation: `poodo_core/ports.py`; `cli.py`; [ICD §2 and §6](../icd/icd-endoforge.md)
- Allocated to: SDD-C11
- Verification: T (port surface and CLI status), plus inspection of the ICD
- Status: Baselined

### CS-REQ-024 — Durable append and writer ownership

EndoforgeLedger shall implement CS-REQ-020 using unchanged payloads and same-session outcome bindings, hold exclusive writer ownership across processes and hard-link aliases, and return record hashes only after file fsync. The host shall serialize calls and preserve file identity on a local POSIX filesystem.

- Rationale: durable, single-writer evidence.
- Derivation: `adapters/endoforge_ledger.py`
- Allocated to: SDD-C11
- Verification: T. Deployment power-loss qualification is not done.
- Status: Baselined

### CS-REQ-025 — File integrity and uncertain acknowledgement

EndoforgeLedger shall implement CS-REQ-021 by verifying the whole chain before reads and appends, rejecting corruption without repair or truncation, and propagating storage failures without successful receipts. A failed acknowledgement may follow persistence and shall require caller reconciliation before retry.

- Rationale: as CS-REQ-021, for the file adapter.
- Derivation: `adapters/endoforge_ledger.py`
- Allocated to: SDD-C11
- Verification: T
- Status: Baselined

### CS-REQ-026 — File evidence retrieval

EndoforgeLedger shall implement CS-REQ-022 with detached append-ordered records, exact goal and session filters and whole-chain verification before filtering, including after closing and reopening the ledger.

- Rationale: as CS-REQ-022, for the file adapter.
- Derivation: `adapters/endoforge_ledger.py`
- Allocated to: SDD-C11
- Verification: T
- Status: Baselined

### CS-REQ-027 — Configured evidence routing

Configured cores shall witness decisions before dispatch through EndoforgePort, include ApprovalPort verdicts and `approval_id`, and append unchanged admitted outcomes after execution, bound to their precommits in the same session.

- Rationale: every configured run leaves a witnessed decision before its effect.
- Derivation: `poodo_core/core.py`; `bootstrap.py`; `adapters/endoforge_ledger.py`
- Allocated to: SDD-C11
- Verification: T. Deployment durability qualification is not done.
- Status: Baselined

### CS-REQ-028 — Runtime fail-closed storage

Configured cores shall withhold dispatch on a failed precommit, latch further witnessed work, and retain uncertainty on a failed outcome acknowledgement without implicit retry.

- Rationale: a storage failure must stop work, not skip witnessing.
- Derivation: `poodo_core/core.py`; `adapters/endoforge_ledger.py`
- Allocated to: SDD-C11
- Verification: T
- Status: Baselined

### CS-REQ-029 — Configured evidence retrieval

Configured runs shall read witnessed records through the CS-REQ-026 retrieval rules, with exclusive file ownership excluding concurrent writers.

- Rationale: as CS-REQ-022, at runtime.
- Derivation: `adapters/endoforge_ledger.py`
- Allocated to: SDD-C11
- Verification: T
- Status: Baselined

### CS-REQ-030 — Trusted routing configuration and status

Only trusted host configuration shall select EndoForge storage and session identity. The CLI shall report `endoforge_implemented: true` only when bound to the real adapter; a configured storage failure shall never fall back to an unconfigured run.

- Rationale: request data must not redirect evidence.
- Derivation: `bootstrap.py`; `cli.py`
- Allocated to: SDD-C11
- Verification: T, plus inspection of the ICD
- Status: Baselined

### CS-REQ-047 — Durable JSONL ledger

The durable JSONL ledger shall finish a short write before acknowledging an event, raise and keep nothing on a failed file open, a full disk or a failed fsync, count only kept events against its budget, and survive a torn tail from a killed writer across restart and the next append.

- Rationale: a run ledger must not acknowledge what it did not keep.
- Derivation: `adapters/durable_ledger.py`
- Allocated to: SDD-C13
- Verification: T
- Status: Baselined

### CS-REQ-048 — Witnessed node ledger

The witnessed node ledger shall deny an enforced gate without a quorum and dispatch nothing, allow once with a quorum, detect tampering and truncation, keep streams on one log separate so a core reads only its own stream, refuse a second live instance on a stream and a forked child using its parent's claim, stop an owner whose claim file was replaced, refuse unsafe files and unbound writers, and finish writer processes under a deadline.

- Rationale: DECISION-004 private witnessed ledger.
- Derivation: `adapters/witnessed_ledger.py`; `adapters/ledger.py`
- Allocated to: SDD-C13
- Verification: T
- Status: Baselined

### 3.6 Forge runtime

### CS-REQ-031 — Refrigeration acceptance through host approval

The refrigeration acceptance example shall execute through the real CLI with a host-selected file approval store and EndoForge configuration. Selecting the SQLite file approver shall classify all selected domain operations as `ask`. An approved request shall return the real Foundation outcome, retain a POODO decision, witness precommit before outcome in one verified session, and bind the `approval_id` to the consumed approval store record. A declined request shall produce neither dispatch nor outcome. The configured CLI shall report `endoforge_implemented: true`.

- Rationale: one end-to-end path through every production adapter.
- Derivation: `cli.py`; `bootstrap.py`; `tools/e2e_refrigeration.sh`; `examples/refrigeration-e2e.json`
- Allocated to: SDD-C9
- Verification: T. Reproduce with `PYTHON=python3 bash tools/e2e_refrigeration.sh`. Synthetic acceptance only.
- Status: Baselined

### CS-REQ-032 — One governed goal through the workcell runtime

A `cstack_forge` goal shall run through a host grant and POODO decision, real EndoForge gates and ledger in `IsolatePool` workcells, and produce a witnessed receipt naming the decision, grant, compiler and Foundation versions. Producers shall not judge themselves; the pinned Foundation judges.

- Rationale: the forge runtime is governed like any other capability.
- Derivation: `extensions/cstack_forge.py`; `adapters/endoforge_workcell.py`; `adapters/workcell/`
- Allocated to: SDD-C12
- Verification: T (stub model transport; no real model call)
- Status: Baselined

### CS-REQ-033 — Foundations as declared in-process imports

A kernel shall reach a Foundation only through an import that its binary carries, its request declares and host configuration allows. Pure computation on a shipped route shall start no process, and each result shall be attributable to pinned bytes.

- Rationale: in-process routes remove process spawns while keeping attribution.
- Derivation: `adapters/workcell/`; `adapters/endoforge_workcell.py`
- Allocated to: SDD-C12
- Verification: T. Differential vectors are a sample, not proof of equivalence.
- Status: Baselined

### CS-REQ-034 — Authority stays with the core

A candidate shall propose decisions only as data, through its host, and the core shall accept or refuse them. A candidate shall not grant itself authority, reach an undeclared Foundation, pass after a refusal, or record a pass from a refused or unknown run.

- Rationale: model-written code must not hold authority.
- Derivation: `adapters/workcell/`; `adapters/endoforge_workcell.py`; `poodo_core/core.py`
- Allocated to: SDD-C12
- Verification: T. A workcell is not an OS sandbox.
- Status: Baselined

### CS-REQ-035 — Outcome unknown is a state

A kill of a workcell, supervisor or controller during a run shall record `outcome_unknown`, with no pass and no automatic retry. A later session shall record a controller's lost attempt once.

- Rationale: a kill must never look like a pass.
- Derivation: `adapters/endoforge_workcell.py`; `adapters/durable_ledger.py`
- Allocated to: SDD-C12
- Verification: T (real SIGKILL; power loss not tested)
- Status: Baselined

### CS-REQ-068 — Forge request shape and run conditions

A forge request shall need a held-out check per case, each naming a case, with argument types checked before anything runs; one decision shall not name two requests; decimal cases shall reach the kernel exactly; the model prompt shall carry no held-out checks; and a host with no node, missing `node_modules`, no model transport or an unopenable ledger shall run nothing and say why. The run journal shall sit beside its ledger, not in user state.

- Rationale: a run starts only when its inputs and environment are complete.
- Derivation: `extensions/cstack_forge.py`; `adapters/endoforge_workcell.py`
- Allocated to: SDD-C12
- Verification: T
- Status: Baselined

### CS-REQ-069 — Forge part pins

A forge run shall refuse to start when the workcell host port, broker, judge, a vendored EndoForge gate or a Foundation kernel projection differs from its pin, and its receipt shall say when it omitted attributions.

- Rationale: the judged code and the judge must be the reviewed bytes.
- Derivation: `adapters/endoforge_workcell.py`; `tools/pin_workcell.py`; `contracts/SOURCE-PINS.json`
- Allocated to: SDD-C12
- Verification: T
- Status: Baselined

### 3.7 Fleet, sessions and messaging

### CS-REQ-049 — AOR fleet registry

The fleet registry shall validate `aors/fleet.json` against `contracts/aor.schema.json`, never allow a gated effect class to be `allow`, fix the approver to the owner through the scheduled channel, allow one owner per path, refuse unknown fields, missing effects, dangling references and duplicates, require a slice owner to be able to write it, and return immutable records; the shipped example fleet and config shall pass this validation.

- Rationale: areas of responsibility are host configuration and must be exact.
- Derivation: `adapters/aor_registry.py`; `contracts/aor.schema.json`; `aors/fleet.json`
- Allocated to: SDD-C14
- Verification: T
- Status: Baselined

### CS-REQ-050 — AOR sessions

An AOR session shall serialize every public call on a session lock, keep domain stores separate from core ledgers, refuse a second session of the same bot until close (in the same process and from another process), refuse tampered or truncated domain stores and logs, release opened domains after a partial build failure, refuse decide and execute while shields are up, and wait for a bound host approval before dispatching an ask exactly once.

- Rationale: one bot, one live session, one history.
- Derivation: `adapters/aor_session.py`; `bootstrap.py`
- Allocated to: SDD-C14
- Verification: T
- Status: Baselined

### CS-REQ-051 — Agent ledger verdict

`tools/e2e_agent.py` shall base its verdict on the refrigeration stream, check every anchored stream, and refuse a stream anchor moved to another stream or keyed by domain.

- Rationale: the end-to-end agent check must read the right stream.
- Derivation: `tools/e2e_agent.py`
- Allocated to: SDD-C14
- Verification: T
- Status: Baselined

### CS-REQ-052 — MCP server

The MCP stdio server shall echo a supported protocol version on initialize (falling back for unknown ones), list exactly its fixed tools, refuse calls before initialize, refuse parse errors and invalid UTF-8 while continuing to serve, return invalid-params for unknown tools and non-object arguments, never answer a null id, refuse oversized frames with a bounded read, fix the bot identity at launch, and never hide or crash an execute when an anchor cannot be saved.

- Rationale: the server is the agent-facing boundary; malformed input must not stop it or change identity.
- Derivation: `adapters/mcp_stdio_server.py`; `tools/cstack_mcp.py`
- Allocated to: SDD-C15
- Verification: T
- Status: Baselined

### CS-REQ-053 — MCP client

The MCP stdio client shall take its descriptor and effects from the host, treat `isError` as a completed tool error, refuse unknown, new, changed or conflicting tools before dispatch, treat timeout, crash and cancellation after dispatch as unknown without retry, kill the whole process group, and enforce frame caps, duplicate-key and non-finite-number rejection.

- Rationale: an external MCP server is untrusted.
- Derivation: `adapters/mcp_stdio_client.py`; `adapters/wire.py`
- Allocated to: SDD-C15
- Verification: T. The TypeScript SDK interop test skips without that SDK.
- Status: Baselined

### CS-REQ-054 — Fleet mail

Fleet mail shall stamp the sender so input cannot override it, accept only fleet slugs, all-bots or host extras as recipients, refuse over-long strings, control and look-alike characters, mentions and cross-repository references, enforce send, all-bots and per-thread reply allowances with refusals recorded once per window, refuse writes while shields are up, record message number and digest but never the body, verify signatures against the roster and show forgeries as unverified, keep fleet mail out of the approval path, run `gh` with a fixed argument shape, fixed environment, stdin-only message text, deadline and output bounds, and keep the MCP mail tools off by default. The send-budget file shall be private, refuse an emptied state, and never let several processes pass the limit.

- Rationale: bots may message each other, but messages carry no authority.
- Derivation: `adapters/fleet_mail.py`; `adapters/mcp_stdio_server.py`
- Allocated to: SDD-C16
- Verification: T
- Status: Baselined

### CS-REQ-055 — Relay outbox

The relay outbox shall send a click retried from several processes once, keep reading past a torn tail and keep the next message and receipt, raise on an unreadable outbox instead of reading it as empty, and treat a missing outbox as empty.

- Rationale: at-most-once delivery with crash tolerance.
- Derivation: `adapters/relay_outbox.py`
- Allocated to: SDD-C16
- Verification: T
- Status: Baselined

### 3.8 Memory, read models and watchers

### CS-REQ-062 — Memory store

The memory store shall create its database privately (mode 0600, owned regular file, never through a symlink), keep facts as proposals until a named reviewer confirms or rejects them, validate inputs and conflicts, redact planted secrets and screen confidential threads during ingest, keep ingest free of network access, and report CLI errors on stderr with exit status 2.

- Rationale: memory holds host-sanitized facts and grants no authority.
- Derivation: `adapters/memory/`
- Allocated to: SDD-C17
- Verification: T
- Status: Baselined

### CS-REQ-059 — Read models

The read-model projections shall import no adapter and call no write, refuse a ledger object, back a goal only with completed responded outcomes on its current revision, count unknown and malformed events without failing, mark window gaps and replays partial and old or undated sources stale, cite their source range and as-of time, and the CLI brief shall be five lines or fewer.

- Rationale: read models report; they never change state.
- Derivation: `adapters/read_models.py`; `tools/read_models.py`
- Allocated to: SDD-C18
- Verification: T
- Status: Baselined

### CS-REQ-060 — Host read models

The host read models shall report GPU queue, capacity, session, agent pool, job and host resource projections as counts and names only, turn a failing source into a stale or partial projection with a reason, refuse commands off the read list, and open nothing for writing.

- Rationale: host status must be read without side effects or argument leaks.
- Derivation: `adapters/host_read_models.py`
- Allocated to: SDD-C18
- Verification: T
- Status: Baselined

### CS-REQ-057 — Runtime watch

`tools/runtime_watch.py` shall report each runtime ledger's last event, unsettled attempts, unknown outcomes, refusals and goals with no live path, alarm with exit status 75 on a stale, missing or broken ledger, apply its fresh, late and down boundaries, and leave every ledger file byte- and time-identical.

- Rationale: a watcher that writes could hide the fault it watches for.
- Derivation: `tools/runtime_watch.py`
- Allocated to: SDD-C18
- Verification: T
- Status: Baselined

### CS-REQ-058 — Witness watch and deadman

`tools/witness_watch.py` shall alarm when witness data is absent or unverifiable, report replica and quorum checkpoint ages, treat stale, missing, forged and future check-ins as deadman, unverifiable or clock skew (never fresh), keep alarm ids stable across runs, and write nothing.

- Rationale: as CS-REQ-057, for witness checkpoints.
- Derivation: `tools/witness_watch.py`
- Allocated to: SDD-C18
- Verification: T
- Status: Baselined

### 3.9 Provider policy and workspace snapshots

### CS-REQ-061 — Provider policy

The provider policy shall classify failures into a closed set, back off with capped jitter while honouring a bounded retry-after, never choose a route below the request's data class, fail over on usage limits and auth failures, never retry a context overflow on the same route, stop on invalid requests, parse absolute and relative usage-cap resets (including across a daylight-saving change), and use only the standard library with no network access.

- Rationale: model routing must be predictable and must not leak data to a lower class.
- Derivation: `adapters/provider_policy.py`
- Allocated to: SDD-C19
- Verification: T
- Status: Baselined

### CS-REQ-063 — Workspace snapshots

Workspace snapshots shall capture without changing the index, HEAD, branches or stash, skip ignored files, refuse submodules and nested repositories, restore untracked and selected paths while refusing unsnapshotted changes unless forced, prune only old snapshot refs, and `tools/snapshot_step.py` shall capture before and after a command, report the diff and pass the command's exit status through.

- Rationale: agents need undo without touching the user's Git state.
- Derivation: `adapters/workspace_snapshots.py`; `tools/snapshot_step.py`
- Allocated to: SDD-C20
- Verification: T
- Status: Baselined

### 3.10 Configuration identity and repository tools

### CS-REQ-019 — Reasoning snapshot provenance

The mirrored POODO subset shall match the upstream commit and file scope recorded in `contracts/SOURCE-PINS.json`; incomplete synchronization shall remain explicit and retired paths shall be preserved under `TODELETE/`.

- Rationale: the reasoning method is reused, not forked.
- Derivation: `contracts/SOURCE-PINS.json`; `reasoning/poodo/`
- Allocated to: SDD-C22
- Verification: I. Byte comparison with the pinned checkout (test plan TP-3). No automated test; listed as a gap in the verification matrix.
- Status: Baselined

### CS-REQ-070 — EndoForge pin

The vendored EndoForge slice shall match the pinned commit, manifest digest, file count and every exported file hash, and the pin shall record whether its commit is on upstream main. `tools/pin_endoforge.py` shall refuse a commit not reachable from `origin/main` unless the exception is requested and recorded.

- Rationale: the vendored engine must be exactly the reviewed upstream bytes.
- Derivation: `tools/pin_endoforge.py`; `vendor/endoforge/SOURCE-MANIFEST.json`; `contracts/SOURCE-PINS.json`
- Allocated to: SDD-C21
- Verification: T
- Status: Baselined

### CS-REQ-074 — Core byte pin

The files named in the latest `poodo_core_*` record of `contracts/SOURCE-PINS.json` (at this baseline `poodo_core_crash_recovery_0_3`) shall match their recorded SHA-256 values.

- Rationale: a core change must be deliberate and visible in review.
- Derivation: `contracts/SOURCE-PINS.json`; `poodo_core/`
- Allocated to: SDD-C2
- Verification: T
- Status: Baselined

### CS-REQ-071 — Claim gate verdicts

The claim gate shall extract strong words and numbers with units as claims (not questions, negations, hedges, code or quotes), mark a claim supported only by evidence of the matching kind (a unit test supports "passed" but not "live"; a number needs an outcome containing it; a hash or summary is not corroboration; failed, timed-out and corrected outcomes support nothing), reject a malformed ledger, and exit with its documented status codes.

- Rationale: written claims about work must be backed by recorded outcomes.
- Derivation: `tools/claim_gate.py`
- Allocated to: SDD-C21
- Verification: T
- Status: Baselined

### CS-REQ-072 — Link check

`tools/check_links.py` shall report every broken repository path named in the README, root files and every document under `docs/`, and fail on an allow-list entry that excuses nothing or has no reason.

- Rationale: maps that name missing files mislead readers.
- Derivation: `tools/check_links.py`; `ci/link-allowlist.txt`
- Allocated to: SDD-C21
- Verification: T
- Status: Baselined

### CS-REQ-073 — README and repository tools

`tools/check_readme.py` shall run the README's commands (the forge example twice) with `gh` commands in a separate group that is skipped with a clear reason when `gh` is absent; `tools/merge_train.py` shall skip draft PRs and print a clear message without `gh`; `tools/build_export_manifest.py --help` shall write nothing, and `EXPORT-MANIFEST.json` shall hold no `.venv/` or `node_modules` paths.

- Rationale: the repository's own tools must behave as documented.
- Derivation: `tools/check_readme.py`; `tools/merge_train.py`; `tools/build_export_manifest.py`
- Allocated to: SDD-C21
- Verification: T
- Status: Baselined

### CS-REQ-076 — Trace check

`tools/check_trace.py` shall fail when a requirement has no verification-matrix row, a requirement has no test and is not listed as a gap, a matrix row names a test file, class or method that does not exist, a test file is neither traced nor classified, a requirement's allocation disagrees with the design description, or a Markdown link in a control document points to a missing file or heading.

- Rationale: SWE-052 bidirectional traceability, checked on every run.
- Derivation: `tools/check_trace.py`
- Allocated to: SDD-C21
- Verification: T
- Status: Baselined

### CS-REQ-077 — Generated data dictionary

`tools/gen_data_dictionary.py` shall write `docs/data/data-dictionary.md` from the tool catalogs, contract schemas, example configuration and numeric limit constants, listing every tool and every top-level schema field, and its `--check` mode shall fail when the committed dictionary differs from what the sources produce.

- Rationale: the data dictionary must not drift from the schemas it describes (SWEHB 5.07).
- Derivation: `tools/gen_data_dictionary.py`; `schemas/`; `contracts/`
- Allocated to: SDD-C21
- Verification: T
- Status: Baselined

## 4. Interface requirements

The interface requirements are the ones above that name an interface: Foundation stdio bridges (CS-REQ-003 to CS-REQ-008, CS-REQ-064, CS-REQ-065; [Foundation ICD](../icd/icd-foundations.md)), EndoForge evidence and runtime (CS-REQ-020 to CS-REQ-035, CS-REQ-068, CS-REQ-069; [EndoForge ICD](../icd/icd-endoforge.md), [EndoForge pin ICD](../icd/icd-endoforge-pin.md)), POODO snapshot (CS-REQ-019; [POODO ICD](../icd/icd-poodo.md)), CLI (CS-REQ-016 to CS-REQ-018, CS-REQ-067; [commands reference](../guides/reference/commands.md)), MCP (CS-REQ-052, CS-REQ-053; [server and adapters](../guides/explanation/server-and-adapters.md)) and the adapter inventory (CS-REQ-036; [`contracts/INTERFACES.md`](../../contracts/INTERFACES.md)).

## 5. Non-functional requirements

Bounded resource use is stated as requirements where a test checks it: CS-REQ-006 (wire limits), CS-REQ-011 (output bounds), CS-REQ-009 (deadlines), CS-REQ-041 (capacity), CS-REQ-040 (budget). Replaceability is CS-REQ-075. Reuse (SWE-147) is met by the public GPL-3.0-only license and the family standard; no further obligation is stated.

This baseline has no availability target, throughput target, deployment hardware qualification, coverage threshold or independent safety assessment. Route timings in [Foundation routes](../verification/foundation-routes.md) are measurements, not requirements.

Design constraints: no code comments ([rule](../rules/no-comments.md)); vendored trees are byte-pinned and not edited.

## 6. Not applicable categories

- Safety requirements and hazard controls (SWE-184): not applicable. Cstack is not safety-critical ([SMP §1](../plan/software-management-plan.md#1-software-classification-self-assessed)).
- Control-system, operating-system, board-support-package, partitioning and hardware-interface requirements: not applicable. Cstack has none of these elements.

## 7. Qualification provisions

T: a named unittest method runs in `bash ci/run-local.sh python`. I: a named file or procedure is inspected and the procedure is in the [test plan](../verification/test-plan.md). A requirement counts as verified only when its mapped tests passed in a recorded run at a named commit ([test reports](../verification/reports/)). A file-level pass alone does not establish full coverage of a requirement. Missing tests, skipped tests and disagreements between source and requirement remain open findings and are not counted as verified.

## 8. Open items

TBD count: 0. Requirements without an automated test: 1 (CS-REQ-019; see the [verification matrix gaps](../verification/verification-matrix.md#untested-requirement-gaps)).

| ID | Open item | Owner | Issue |
|---|---|---|---|
| OI-1 | CS-REQ-019 has only a manual byte-comparison procedure | Akilleez-QA | Not filed |
| OI-2 | Deployment durability (power loss) for CS-REQ-024, CS-REQ-027 and CS-REQ-035 is not qualified | Akilleez-QA | Not filed |

## Licensing

GPL-3.0-only. Commercial licenses under different terms are available from Refrigeration.AI; contact craig@nh3.biz. See the repository LICENSE and NOTICE.md for bundled notices.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.x | 2026-10 to 2026-11-08 | various | CS-REQ-001 to CS-REQ-035 added across earlier PRs | See `git log -- docs/requirements/requirements.md` |
| 2.0 | 2026-11-08 | 6ae5481fd302439dabb23044d1b715ac8c4a9bec | Family standard format: metadata, record fields, allocation to SDD components; CS-REQ-036 to CS-REQ-077 added from tested behaviour; CS-REQ-027 to CS-REQ-030 restated without repeating the port text | docs/nasa-standard PR |
