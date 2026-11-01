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

## Acceptance and unresolved assurance work

A requirement is accepted only after review of its mapped assertions and a recorded run on the candidate commit. A file-level pass alone does not establish full requirement coverage. Missing tests, skipped tests and disagreements between source and requirement remain open findings; they shall not be counted as verified.

This baseline has no allocated availability target, throughput target, deployment hardware qualification, formal coverage measurement or independent safety assessment. Those require separately approved requirements and evidence before operational claims. A source hash provides byte identity, not origin authentication.

## Licensing

GPL-3.0-only. Commercial licenses under different terms are available from Refrigeration.AI; contact craig@nh3.biz. See the repository LICENSE and NOTICE.md for bundled notices.
