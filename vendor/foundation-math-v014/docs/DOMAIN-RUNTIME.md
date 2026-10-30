# v0.3: domain-aware work queue and explicit acceptance

## Obligation advanced

Connect the existing exact scalar and polynomial calculators to the work queue
without conflating operation success, an accepted mathematical result, and formal
proof. This is software/tool maturity, not a new proof of an informal theorem.
The delivered v0.1 and v0.2 trees are unchanged. No model/API calls, installations,
external writes, or repository publication are part of this local extension.

## Run the acceptance examples

From the repository root, using only Python 3.11+ and the standard library:

```sh
python -m foundation_math run examples/workflow/polynomial_distributivity.json
python -m foundation_math run examples/workflow/polynomial_false_identity.json
python -m foundation_math run examples/workflow/polynomial_formal_requirement.json
python -m foundation_math run examples/workflow/polynomial_rejected_cancellation.json
python -m foundation_math run examples/workflow/polynomial_rejected_quotient.json
python -m foundation_math run examples/workflow/polynomial_tampered_ring.json
python -m foundation_math run examples/workflow/scalar_formal_requirement.json
```

Expected exit codes, in order: **0, 1, 1, 2, 2, 1, 1**. Exit 0 means the
structured goal's requested evidence was satisfied. Exit 1 means a valid workflow
finished without that acceptance, including a false identity, bad proposal, or an
unsupported formal-evidence requirement. Exit 2 means invalid workflow input.
Errors arising during calculation remain recorded task failures and exit 1.
`--output` creates a report without overwriting an existing file.

## Typed dispatch, not a plugin loader

`foundation_math.domains` defines `DomainName`, `RequiredEvidence`,
`DomainHandler`, `ScalarDomain`, `PolynomialDomain`, and `domain_handler(name)`.
The fixed allowlist supports:

- `Z` and `Q`: the existing exact scalar operations and result contract.
- `polynomial_ring`: formal commutative polynomials over `Q`, with explicitly
  ordered variables and the bounded AST defined in
  [POLYNOMIAL-DOMAIN.md](POLYNOMIAL-DOMAIN.md). Queue operations are `add`,
  `multiply`, and `verify_identity`.

The polynomial backend exposes `validate_polynomial_request(request)`, which
validates and returns a detached normalized request without doing arithmetic.
Admission and calculation use the same parser. There is no second AST grammar,
agent-selected code, dynamic import, executable command field, or float fallback.

## Problem and proposal API

The workflow remains schema version 1. The additive optional problem field
`required_evidence` accepts exactly `exact_computation` or `formal_proof`.
Omitting it defaults to `exact_computation`, preserving existing scalar workflows.
New examples set it explicitly. Invalid values never silently fall back.

```python
from foundation_math.orchestrator import Runtime

report = Runtime.from_dict(workflow).run()  # deterministic offline provider
```

The `problem` object has `id`, `domain`, `assumptions`, `goal`, `goal_request`,
and optional `required_evidence`. `domain` must match the structured request.
Free-text `goal` and `assumptions` are context only. An assumption such as `x*x=x`
does not impose a quotient relation on Q[x], grant cancellation, or change the
acceptance semantics.

The provider may return only `request`, `expected`, and optional text `rationale`.
For a polynomial identity the candidate is:

```json
{
  "request": {
    "domain": "polynomial_ring", "coefficient_field": "Q", "variables": ["x", "y"],
    "operation": "verify_identity",
    "operands": [{"type": "variable", "name": "x"}, {"type": "variable", "name": "x"}]
  },
  "expected": {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": ["x", "y"], "equal": true}
}
```

This minimal candidate asserts x=x; the examples include distributivity and
counterexamples. For `add` and `multiply`, replace `equal` in `expected` with
`polynomial`, holding the canonical `terms`/`total_degree` object. Terms must be
unique and lexicographically ordered, coefficients reduced and nonzero with
positive denominator, and exponent coordinates use the goal's variable order.
Zero is `{"terms": [], "total_degree": null}`. Scalar expected values retain
the original `{domain, value}` or `{domain, numerator, denominator}` format;
equivalent rational candidates such as 10/12 for 5/6 remain accepted.

## Acceptance gates

1. Admission fixes the domain, complete structured request and evidence
   requirement. Unsupported rings, quotient relations, division/cancellation
   ASTs, and unbounded polynomial requests are rejected.
2. The proposer request must be exactly the same canonical JSON as the goal,
   including ordered variables, coefficient field, operation and AST. Merely
   algebraically equivalent substituted requests are not accepted. Rational
   literals may be reduced inside the calculator, but this does not relax the
   original input binding.
3. Calculator task success means only that the operation completed. A false
   identity deliberately produces a successful calculation receipt.
4. The verifier replays the original goal through the trusted domain handler.
   The complete deterministic calculation receipt must match replay, including
   original input, normalized request, ring, result, scope, source hashes,
   backend versions and usage. Hash equality or provider claims alone do not
   pass this gate. The calculation must also bind to the same proposal receipt.
5. Scalar values must equal the candidate exactly. Polynomial add/multiply
   output must equal the candidate canonical form. An identity requires
   `result.equal is True` **and** candidate `equal is True`. Correctly predicting
   `equal: false` still does not establish the asserted identity goal; its
   coefficient mismatch witness is retained as counterevidence.
6. This implementation produces only exact-computation evidence. An exact pass
   satisfies `required_evidence: exact_computation`; it can never satisfy
   `required_evidence: formal_proof`.

Provider `status`, `confidence`, `formal_proof`, `receipts`, or
`required_evidence` overrides are unsupported fields. Prose claiming kernel
verification is inert. Providers receive detached problem/task/evidence data.
They are trusted Python integration code, however, not a sandbox for arbitrary
malicious plugins with process-memory access.

## Report semantics

`goal_status` retains `exact_result_verified` for an accepted scalar or polynomial
result, otherwise `not_verified`. Acceptance additionally requires
`evidence_requirement_satisfied: true`. `result` is null unless the goal is
accepted; the attempted exact result and false-identity witness remain in the
receipts. `proof_status` is always `not_formally_verified`, and
`informal_correspondence_verified` is always false.

An `exact_verification` receipt distinguishes:

- `receipt_replay_matches`: complete trusted replay matches recorded evidence.
- `result_accepted`: the declared domain's mathematical acceptance predicate.
- `exact_check_passed`: both preceding gates passed.
- `required_evidence`: the pinned problem requirement.
- `requirement_satisfied` and `passed`: the actual acceptance decision.
- `evidence_level`: `exact_computation` for scalars or
  `exact_polynomial_normalization` for polynomials.
- `reason`: null on acceptance; `receipt_replay_mismatch`,
  `mathematical_acceptance_failed`, or `formal_proof_not_available` otherwise.

A true exact result with a formal-proof requirement has
`exact_check_passed: true`, `requirement_satisfied: false`, and a **blocked**
verifier task. A false or mismatched result has a **rejected** verifier task.
Downstream tasks obey the existing dependency gates. Optional formalizer tasks
remain blocked; they do not transform an exact receipt into formal evidence.

## Lean and other limits

The restricted Lean adapter remains separate and unchanged. The queue does not
invoke it or import its receipts. No real Lean proof was run for v0.3; absence,
unsupported source, and simulated test-stub success cannot close formal goals.
Even a future real Lean integration will need exact statement/domain binding,
trust/axiom checks, and separate informal-correspondence review.

Replay reuses the same calculator implementation: it is not an independent
proof kernel. Independent test oracles support software confidence, not universal
correctness. The source manifest inventories the runtime and handlers. Verifier receipts
also record `acceptance_source_sha256` for `domains.py` and `orchestrator.py`,
while calculator receipts pin their respective backend source. These are current
source-file hashes, not signatures or attestations of the loaded interpreter/code;
replay must use a trusted, unchanged source tree. Hash chains provide integrity,
not signatures, authenticity, or mathematical replay of an edited report.

The queue remains local, in-memory and single-process, with bounded attempts and
leases. Its 64 KiB canonical structured-object/receipt limit can be stricter than
the standalone calculator bounds. An expression whose expanded receipt is too
large fails closed, leaves no partial result, and records the failed attempt.
A general distributed scheduler, persistent recovery, isolated untrusted workers,
live model agent, theorem search, quotient/cancellation engine and general formal
proof acceptance remain outside scope.
