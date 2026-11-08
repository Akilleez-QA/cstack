# Prospective acceptance contract v0.1

Prospective acceptance criteria for the POODO-core/base extension architecture, immutable Math v014 bridge contract, and INTERFACES.md v0.1. See version-bound validation reports for actual outcomes; this document alone is not a pass receipt. It is a historical record of the v0.1 slice: Foundation Engine, Refrigeration and the Endoforge workcell runtime were implemented later, under the addendum below, CS-REQ-031 to CS-REQ-035 and the [wiring acceptance](../docs/verification/wiring-acceptance.md).

## Intended success surface

A caller-supplied synthetic goal produces a precommitted, authorized POODO decision; the inherited POODO core routes the call through the Math domain extension and replaceable adapter; the real pinned bridge computes; the core retains exact scoped evidence and does not close the goal. The same core works with an unrelated fake domain and fake capability, showing a reusable extension seam rather than a Math wrapper.

## Precommitted observations

| ID | Observable and oracle | Required outcome |
|---|---|---|
| AC-01 | Import/dependency inspection of core and a test without Math on import path | Core has no concrete domain, transport, subprocess or provider dependency |
| AC-02 | FoundationMath extends PoodoCore; fake sibling extension uses same inherited lifecycle | No core edit or lifecycle override needed |
| AC-03 | Fixed manifest and tool inventory verification before/after run | All 561 bound source files unchanged; inventory hash matches |
| AC-04 | Real bridge synthetic Q addition 1/2 + 1/3 | Exact 5/6; source/request/attempt identity retained |
| AC-05 | Real false polynomial identity | Completed negative mathematical result retained, never truth/proof/closure |
| AC-06 | Core snapshot and ledger before/after each call | Goal/revision, phase, decision, authorization and outcome owned by core; flags false |
| AC-07 | Same test cases normal and `python -O` | Guards do not depend on assertions; test set passes both modes |
| AC-08 | Explicit unsupported Foundation Engine/Refrigeration and Lean requests | Unavailable/unsupported, no guessed capability or fallback |
| AC-09 | Source root missing, wrong hash, wrong inventory or changed contract version | Refuse dispatch; no silent compatibility assumption |
| AC-10 | Non-Math fake adapter and fake domain with different result semantics | No Math-specific acceptance or numeric assumption leaks into core |

A normal/-O run is repeated observation under a different interpreter setting, not independent mathematical corroboration. A fake adapter verifies ownership/control only. The real bridge smoke verifies the actual handoff and synthetic calculation, not full bridge correctness. Existing full Math validation remains distinct and is not claimed rerun unless actually executed.

## Negative controls

- N-01: disallowed operation/capability, forged grant in JSON, tool text asking for a new action, or mutated decision arguments: deny before dispatch.
- N-02: goal revision changes after decide: stale decision rejected; no silent repin.
- N-03: phase skipping, missing research record, fewer than 20 option IDs, duplicate IDs, no prospective oracle: reject the structural transition. Do not claim a count validates option quality.
- N-04: inherited critical-method override through supported extension API: rejected or unavailable; unsafe raw Python monkeypatching is outside threat model.
- N-05: adapter advertises formal proof, returns runtime_goal_acceptance true, wrong tool, mismatched ID, wrong ID type, malformed result/error combination or invalid structured payload: protocol failure, no promotion.
- N-06: exact Z division of 1 by 2 remains an error, no Q/float coercion; malformed denominators remain rejected.
- N-07: duplicate JSON keys, floating/nonfinite Math numbers, malformed UTF-8, oversized/truncated lines, over-budget requests or huge inventory: fail boundedly with no partial evidence.
- N-08: timeout, cancellation, crash, partial reply and late reply: record unknown execution outcome where appropriate, release resources, do not retry or close goal.
- N-09: first four loose Math output schemas cannot permit wrong tool/flags/receipt merely because JSON Schema passes.
- N-10: unchanged caller input dictionaries and immutable snapshots after hook/adapter calls; mutation attempts cannot rewrite prior decisions/evidence.
- N-11: consistent false authored hypothesis matching, empty finite search domains, rejected witnesses or blocked claim replay cannot become general theorem success. At least one semantic no-promotion fixture must cover these, even if full real calls are deferred.
- N-12: bounds on retained goals/evidence/calls enforced; resource rejection never becomes missing-history success.
- N-13: source identity, candidate ID, artifact hash, build cache key and attempt/evaluation receipt are not treated as interchangeable evidence identities.
- N-14: a core-version change cannot silently accept a previously rejected extension fixture; contract version migration/conformance must be explicit.

## Prediction, failure meaning, rollback and stop

Prediction: the selected narrow slice passes AC-01 through AC-10 and relevant negative controls without modifying Math, making model calls, publishing, or asserting formal proof. Scope is trusted local single-operator execution, synthetic fixtures, one small in-memory ledger.

Failure means: a failing control blocks architecture-conformance and dependent widening claims; it does not by itself invalidate Math arithmetic. Preserve raw failures and narrow the claim first. A test may be marked invalid only on outcome-independent evidence; changed tests receive a new version and rerun.

Monitoring: inspect each deterministic test/real invocation result; no background autonomous work. Retrying a read-only calculation is allowed only as a new deliberate attempt and after uncertain process state is cleaned up; no automatic retry in v0.1.

Rollback: remove or quarantine only the NEW harness artifacts, leaving the pinned Math source and unrelated projects untouched. No upstream source migration is performed by this prototype.

Stop immediately on source drift, unauthorized external action, private problem-instance exposure, evidence escalation, unbounded subprocess/resource behavior, or an adapter needing unapproved install/credentials/network. Stop and report incomplete on missing independent intended-use observation. Defer Endoforge/MCP/Lean work rather than silently substitute a different trust or protocol profile.

## Terminal receipt requirements

Record delivery_state, outcome_state, highest_justified_claim, required_runtime_observation, who_controls_next_test, all input/output pins, commands, environment, pass/fail counts, skipped checks, and raw artifact locators. A passing narrow harness may be described as a tested local POODO-to-Math capability slice, not full automated POODO, verified general mathematics, MCP compatibility, Endoforge portability or production security.

## Addendum for ADR 002 (Foundation Refrigeration v0.1)

AC-08 now applies to the parts of Refrigeration that are still unimplemented: rules, reference plants and determinations. The implemented sibling is checked by `tests/test_refrigeration_conformance.py` and by the Foundation's own suite (`foundations/refrigeration/tests`). Each suite runs in normal and `-O` modes. The added observations are:

- **AC-R1** The sibling imports nothing from Math, and the `poodo_core` bytes are unchanged.
- **AC-R2** The real bridge serves all 7 tools through the inherited core, with a differential replay.
- **AC-R3** The census R717 golden points hold (15.69, 33.49 and 181.10 psig), and the generated tables match direct CoolProp 8.0.0 points within their recorded interpolation error.
- **AC-R4** Each of the following fails closed: a dishonest boundary, digest, Evidence or schema in a reply; an input with an exponent, a nonfinite value or an over-budget frame; a changed source.
- **AC-R5** The CLI example `examples/refrigeration-reading-check.json` runs a real round trip. It ends with a completed negative tool_error (the blend side is not guessed) and an open goal.

Passing these checks is a tested local slice. It is not property-data approval, engineering acceptance, or MCP compatibility.
