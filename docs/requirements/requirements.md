# Cstack software requirements specification

Status: reusable documentation baseline; approval is through repository review. This document describes inspected implementation, not a NASA compliance determination or certification.

Organization follows the requirements, design, traceability and configuration-control concerns of [NPR 7150.2](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all) and [NASA-STD-8739.8](https://standards.nasa.gov/standard/nasa/nasa-std-87398). No NASA software classification, hazard analysis or independent verification is asserted.

## Scope and authority

These requirements capture selected existing control-core and Foundation boundary behaviors. They do not specify every fleet, HMI, memory or merge-train feature. Each identifier is stable within this baseline. “Shall” states an acceptance obligation proposed for maintenance; source paths provide derivation evidence. Changes require review of affected design and verification records.

The trusted host supplies implementations, roots, grants and inventory. Requests are untrusted structured data. Foundation operations provide bounded observations; engineering, safety, compliance and general mathematical truth are outside this specification. The process boundary assumes a trusted single operator and does not isolate hostile source code.

## Functional and assurance requirements

### CS-REQ-001 — Composition

The host shall select Foundation implementations and source roots through bootstrap.DOMAINS; an unregistered domain shall be rejected without fallback.

Derivation: `bootstrap.py`. Verification method: automated test plus source inspection of the stated condition.

### CS-REQ-002 — Authority lanes

The host shall reject a grant whose capability has no inventory mapping, whose adapter is absent, or whose lane differs from the adapter inventory.

Derivation: `bootstrap.py; contracts/ADAPTERS.json`. Verification method: automated test plus source inspection of the stated condition.

### CS-REQ-003 — Math source identity

The Math adapter shall verify the pinned source manifest identity, listed file count and every listed file digest before dispatch and after a completed exchange.

Derivation: `adapters/math_stdio.py`. Verification method: automated test plus source inspection of the stated condition.

### CS-REQ-004 — Source rejection

The Math adapter shall withhold dispatch when its source manifest is missing or changed.

Derivation: `adapters/math_stdio.py`. Verification method: automated test plus source inspection of the stated condition.

### CS-REQ-005 — Catalog identity

The Math adapter shall compare the live tool catalog with the pinned inventory before dispatching a tool call.

Derivation: `adapters/math_stdio.py; schemas/math-v014-tools.json`. Verification method: automated test plus source inspection of the stated condition.

### CS-REQ-006 — Input admission

The Math adapter shall reject floating-point inputs and inputs exceeding its wire limits before dispatch.

Derivation: `adapters/math_stdio.py; adapters/wire.py`. Verification method: automated test plus source inspection of the stated condition.

### CS-REQ-007 — Response admission

The Math adapter shall quarantine mismatched response identities, inconsistent error flags, invalid output schemas and evidence-ceiling violations.

Derivation: `adapters/math_stdio.py`. Verification method: automated test plus source inspection of the stated condition.

### CS-REQ-008 — Evidence ceiling

A completed Math tool observation shall retain formal_proof=false and runtime_goal_acceptance=false; successful execution shall not itself close the goal.

Derivation: `extensions/foundation_math.py; adapters/math_stdio.py`. Verification method: automated test plus source inspection of the stated condition.

### CS-REQ-009 — Deadline

The local bridge executor shall terminate a child that exceeds its configured deadline and retain execution uncertainty.

Derivation: `adapters/execution.py`. Verification method: automated test plus source inspection of the stated condition.

### CS-REQ-010 — Cancellation

The local bridge executor shall honor cancellation without admitting partial output as evidence.

Derivation: `adapters/execution.py`. Verification method: automated test plus source inspection of the stated condition.

### CS-REQ-011 — Output bounds

The local bridge executor shall stop exchanges exceeding stdout or stderr limits.

Derivation: `adapters/execution.py`. Verification method: automated test plus source inspection of the stated condition.

### CS-REQ-012 — Decision consumption

The core shall consume decision identity so repeated execution does not automatically retry the capability.

Derivation: `poodo_core/`. Verification method: automated test plus source inspection of the stated condition.

### CS-REQ-013 — Goal revision

The core shall deny a decision bound to a stale goal revision and preserve its history.

Derivation: `poodo_core/`. Verification method: automated test plus source inspection of the stated condition.

### CS-REQ-014 — Ledger ownership

The composition root shall refuse a second live core over the same canonical ledger path in the same process.

Derivation: `bootstrap.py`. Verification method: automated test plus source inspection of the stated condition.

### CS-REQ-015 — Unavailable engine

The Math adapter shall refuse a foundation_engine capability request without dispatch.

Derivation: `extensions/foundation_math.py; adapters/math_stdio.py`. Verification method: automated test plus source inspection of the stated condition.

### CS-REQ-016 — Unavailable approved-atoms registry

When approved-atom validation is requested without an in-repository Registry provider, the claim-gate CLI shall fail closed with exit status 2, a JSON error on stderr identifying the unavailable Registry, and no success output.

Derivation: `tools/claim_gate.py`. Verification method: CLI regression test with empty and nonempty atom references.

### CS-REQ-017 — CLI approval gate

For a CLI call with effect ask, the driver shall require a host ApprovalPort record bound to the exact request, decision, goal revision and named approver before dispatch. Missing approver, explicit denial, missing file answer and unavailable terminal shall deny without a capability action or outcome.

Derivation: `cli.py; adapters/terminal_approver.py; poodo_core/core.py`. Verification: CLI approval tests and core approval-policy tests.

### CS-REQ-018 — CLI approval consumption

The terminal adapter shall accept only an explicit approve answer, issue approval records expiring after five minutes, and durably consume each approval ID at most once across adapter instances. Request JSON shall only restrict existing grants through ask, never select approval sources or enlarge authority.

Derivation: `bootstrap.py; adapters/terminal_approver.py`. Verification: adapter consumption and terminal-answer tests, plus source inspection.

### CS-REQ-019 — Reasoning snapshot provenance

The mirrored POODO subset shall match the upstream commit and file scope recorded in `contracts/SOURCE-PINS.json`; incomplete synchronization shall remain explicit and retired paths shall be preserved under `TODELETE/`. Verification: byte comparison with the pinned checkout and inspection of deferred lists and rename identities.

## Endoforge contract requirements (runtime acceptance pending)

### CS-REQ-020 — Witnessed append contract

EndoforgePort shall expose typed precommit and outcome appends using DecisionRecord and CapabilityOutcome, returning a record hash as specified by the Endoforge ICD. A future adapter shall preserve payloads and bind outcomes to prior precommits in the same session.

Derivation: `docs/icd/icd-endoforge.md` sections 3–4. Verification: protocol/fake test; durable witnessing remains pending adapter qualification.

### CS-REQ-021 — Chain verification and fail-closed storage

EndoforgePort shall expose whole-chain verification. A future adapter shall reject corrupted-chain appends/reads and propagate storage failures without successful receipts or partial evidence; callers shall withhold dispatch on failed precommit and retain uncertainty on failed acknowledgement.

Derivation: `docs/icd/icd-endoforge.md` section 5. Verification: fake tamper test and inspection; storage failure and caller integration tests remain pending.

### CS-REQ-022 — Scoped evidence retrieval

EndoforgePort shall expose detached append-ordered records filtered by goal id, session id, or their intersection, requiring at least one filter and returning an empty tuple for no matches after chain verification.

Derivation: `docs/icd/icd-endoforge.md` sections 3–4. Verification: protocol/fake tests; adapter snapshot isolation remains pending.

### CS-REQ-023 — Authority and implementation status

The Endoforge interface shall allocate policy to POODO and witnessed storage to Endoforge, without granting execution, proof or goal acceptance. Runtime integration status shall distinguish configured evidence routing from agent running and caching.

Derivation: `docs/icd/icd-endoforge.md` sections 2 and 6. Verification: ICD, protocol and CLI source inspection; fake conformance is not runtime acceptance; configured routing evidence is mapped under CS-REQ-027–030.

## Endoforge file adapter requirements

### CS-REQ-024 — Durable append and writer ownership

EndoforgeLedger shall implement CS-REQ-020 using unchanged payloads and same-session outcome bindings, hold exclusive writer ownership across processes and hard-link aliases, and return record hashes only after file fsync. The host shall serialize calls and preserve file identity on a local POSIX filesystem.

Derivation: `docs/icd/icd-endoforge.md` sections 3–4. Verification: shared port conformance, reopen, binding and exclusive-writer tests; deployment power-loss qualification remains pending.

### CS-REQ-025 — File integrity and uncertain acknowledgement

EndoforgeLedger shall implement CS-REQ-021 by verifying the whole chain before reads/appends, rejecting corruption without repair or truncation, and propagating storage failures without successful receipts. Failed acknowledgement may follow persistence and shall require caller reconciliation before retry.

Derivation: `docs/icd/icd-endoforge.md` section 5. Verification: tamper tests and injected short-write, write, read and fsync failures; external witnessing and caller dispatch gating remain pending.

### CS-REQ-026 — File evidence retrieval

EndoforgeLedger shall implement CS-REQ-022 with detached append-ordered records, exact goal/session filters and whole-chain verification before filtering, including after closing and reopening the ledger.

Derivation: `docs/icd/icd-endoforge.md` sections 3–4. Verification: shared port conformance and file reopen tests; host serialization and exclusive writer ownership bound snapshot consistency.

## Endoforge configured routing requirements

### CS-REQ-027 — Configured evidence routing

EndoforgePort shall expose typed precommit and outcome appends using DecisionRecord and CapabilityOutcome, returning a record hash as specified by the Endoforge ICD. Configured cores shall witness decisions before dispatch, include ApprovalPort verdicts and approval_id, and append unchanged admitted outcomes after execution. The adapter shall preserve payloads and bind outcomes to prior precommits in the same session.

Derivation: `docs/icd/icd-endoforge.md` sections 3–4. Verification: protocol/fake and file adapter conformance, reopen and exclusive-writer tests; deployment durability qualification remains pending.

### CS-REQ-028 — Runtime fail-closed storage

EndoforgePort shall expose whole-chain verification. The adapter shall reject corrupted-chain appends/reads and propagate storage failures without successful receipts or partial evidence; callers shall withhold dispatch on failed precommit and retain uncertainty on failed acknowledgement.

Derivation: `docs/icd/icd-endoforge.md` section 5. Verification: fake and file tamper tests, injected write/fsync failures, and runtime dispatch/outcome failure tests in `tests/test_endoforge_routing.py`.

### CS-REQ-029 — Configured evidence retrieval

EndoforgePort shall expose detached append-ordered records filtered by goal id, session id, or their intersection, requiring at least one filter and returning an empty tuple for no matches after chain verification.

Derivation: `docs/icd/icd-endoforge.md` sections 3–4. Verification: shared conformance assertions against fake and file adapter; file ownership excludes concurrent writers and hosts serialize calls.

### CS-REQ-030 — Trusted routing configuration and status

The Endoforge interface shall allocate policy to POODO and witnessed storage to Endoforge, without granting execution, proof or goal acceptance. Only trusted host configuration shall select storage and session identity. The CLI shall report implementation enabled only when bound to the real adapter; configured storage failure shall never fall back to an unconfigured run.

Derivation: `docs/icd/icd-endoforge.md` sections 2 and 6. Verification: ICD inspection and configured CLI tests in `tests/test_endoforge_routing.py`; deployment qualification remains separate.


### CS-REQ-031 — Refrigeration acceptance through host approval

The refrigeration acceptance example shall execute through the real CLI with a host-selected file approval store and Endoforge configuration. Selecting the SQLite file approver shall classify all selected domain operations as ask. An approved request shall return the real Foundation outcome, retain a POODO decision, witness precommit before outcome in one verified session, and bind the approval_id to the consumed approval store record. A declined request shall produce neither dispatch nor outcome. The configured CLI shall report `endoforge_implemented: true`.

Verification: `tests/test_refrigeration_e2e.py`; reproduce the approved example with `PYTHON=python3 bash tools/e2e_refrigeration.sh`. This synthetic acceptance establishes integration behavior only.

## Acceptance and unresolved assurance work

A requirement is accepted only after review of its mapped assertions and a recorded run on the candidate commit. A file-level pass alone does not establish full requirement coverage. Missing tests, skipped tests and disagreements between source and requirement remain open findings; they shall not be counted as verified.

This baseline has no allocated availability target, throughput target, deployment hardware qualification, formal coverage measurement or independent safety assessment. Those require separately approved requirements and evidence before operational claims. A source hash provides byte identity, not origin authentication.

## Licensing

GPL-3.0-only. Commercial licenses under different terms are available from Refrigeration.AI; contact craig@nh3.biz. See the repository LICENSE and NOTICE.md for bundled notices.

### CS-REQ-032 — One governed goal through the workcell runtime

A `cstack_forge` goal runs through a host grant and POODO decision, real EndoForge gates and ledger in `IsolatePool` workcells, and a witnessed receipt naming the decision, grant, compiler and Foundation versions. Producers don't judge themselves; the pinned Foundation does.

### CS-REQ-033 — Foundations as declared in-process imports

A kernel reaches a Foundation only through an import that its binary carries, its request declares and host configuration allows. Pure computation on a shipped route starts no process, and each result is attributable to pinned bytes.

### CS-REQ-034 — Authority stays with the core

A candidate proposes decisions only as data, through its host, and the core accepts or refuses them. It can't grant itself authority, reach an undeclared Foundation, pass after a refusal, or record a pass from a refused or unknown run.

### CS-REQ-035 — Outcome unknown is a state

A kill of a workcell, supervisor or controller during a run records `outcome_unknown`, with no pass and no automatic retry. A later session records a controller's lost attempt once.
