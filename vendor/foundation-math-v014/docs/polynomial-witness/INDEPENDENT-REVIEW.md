# Independent review of exact polynomial witnesses

Reviewed 2026-10-24. Scope: this local lab's typed identity requests, sequential
integer-point construction, fresh concrete-point checker, and bounded failure
semantics. No external repository, research instance, network access, installation,
or third-party mathematical package was used. No producer, checker, contract,
vendored source, or unit-test file was edited by this reviewer.

## Conclusion

The mathematical construction is correct for nonzero formal polynomials over
the rational numbers. The inspected implementation matches that construction.
The root-bound proof in `docs/ALGORITHM.md` and the phase/trust distinctions in
`docs/CONTRACT.md` were also reviewed and agree with the implementation.
The separate checker provides a genuinely different mathematical calculation:
it evaluates the parsed original expression tree at the supplied point rather
than replaying polynomial normalization or the producer's substitutions.

No correctness-blocking defect was found in the inspected implementation or
the independent synthetic audit. This is a source review, an elementary proof
of the algorithm, and finite software testing, **not** proof-assistant or
proof-kernel verification. Source hashes in the evidence identify the exact
reviewed files; hashes are integrity bindings, not authenticity guarantees.

## Existence theorem and proof

Let `p` be a nonzero element of `Q[x1, ..., xn]`, with a fixed declared variable
order. Suppose previous choices have left a nonzero residual `r`. Let `d` be
its degree in the next variable `xj`.

Group `r` by monomials in the other, unassigned variables:

    r = sum_m c_m(xj) m.

At least one coefficient polynomial `c_m` is nonzero, and its degree is at most
`d`. A nonzero univariate polynomial of degree at most `d` over `Q` has at most
`d` distinct roots. Consequently at least one of the `d + 1` distinct integers
`0, 1, ..., d` makes that coefficient nonzero. At that integer the residual
polynomial is nonzero. Selecting the first such integer therefore preserves
the induction invariant. After all variables are assigned, the residual is a
nonzero rational constant, so the selected integer point disproves the identity.

For a degree-zero or absent variable, the only candidate needed is zero. With
no declared variables, a nonzero constant is already a witness at the empty
assignment, with no trials. The zero polynomial is a separate coefficient-
identity branch; the root-bound argument must never be applied to it.

If `d_j` is the actual residual degree at step `j`, and `D_j` is the initial
degree in that variable, then:

    chosen_j <= d_j <= D_j
    trials <= sum_j (d_j + 1) <= sum_j (D_j + 1).

This is a **sum of trial counts**, not a Cartesian-product search, a total
running-time bound, or a polynomial-time guarantee in expression size. Each
trial performs sparse exact arithmetic; normalization, term expansion, integer
bit growth, and arithmetic costs remain relevant. Characteristic zero and
the formal unconstrained ring matter. The conclusion does not transfer as
stated to finite fields, quotient rings, rational functions, or constrained loci.

## Implementation and trust boundary

- The producer normalizes both operands with the frozen sparse backend and
  subtracts their coefficients exactly. Each substitution combines monomials
  after setting the selected exponent to zero, removes canceled coefficients,
  and checks that the final residual agrees with concrete left-minus-right.
- Declared variable order is preserved. Repeated, missing, extra, unknown,
  boolean, floating-point, and unsupported typed inputs are not silently
  interpreted as valid polynomial data.
- The witness binds the canonical original input, the canonical parsed request,
  and the exact declared ring. Original rational representations such as `1/2`
  and `2/4` have the same parsed-request hash but different original-input hashes.
  The expected original request must be supplied separately by the caller;
  accepting a self-contained untrusted request is not proof of user intent.
- The checker uses a fresh expression-tree evaluator with exact `Fraction`
  arithmetic. Parsing canonicalizes rational literals but does not expand or
  normalize the polynomial. It checks all supplied left, right, and difference
  values, requires a nonzero difference, and requires canonical rational pairs.
- Checker independence is specifically from the producer's normalization,
  substitution, and decision logic. The parser, canonical hashing, ring helpers,
  `Fraction`, and Python runtime remain shared dependencies. This is not a fully
  independent implementation of every trusted component.
- The producer's coefficient-identity branch is exact coefficient computation,
  not point evidence. The point checker does not accept identity receipts, and
  a single equal evaluation never proves identity. The checked API explicitly
  marks this branch as not applicable to concrete-point verification.
- Construction trace, exact degrees, first-choice minimality, and trial counts
  are explicitly **producer-only claims**, not checker-certified properties.
  A correctly valued, nonminimal integer point may legitimately be accepted.
  The independent audit separately tests trace claims on its synthetic corpus.
- The checker can accept a directly evaluable certificate even when producer
  expansion caps prevent construction. Its coordinate cap `0..32` is a format
  policy, not verification of the polynomial's actual degree or minimality.

## Resource semantics

Resource failures are inconclusive and carry no mathematical result. They do
not mean that the polynomials are equal or that no counterexample exists.
Normalization caps include intermediate expanded polynomials, so an expression
whose final value would be small or zero can still be conservatively rejected.

The caps are phase-specific:

- The frozen backend enforces its own input, AST, total-degree, term,
  coefficient-bit, and arithmetic-step bounds.
- `max_trials` and `max_substitution_term_visits` constrain construction.
- `max_value_bits` constrains substitution and evaluation values, rather than
  replacing the frozen normalizer's coefficient bound.
- `max_evaluation_nodes` constrains the fresh checker, not sparse producer
  evaluation. A coefficient identity requires no concrete-point evaluation.
- The checked construction API withholds a nonzero result if its separately
  configured point verification fails, including an evaluator resource failure.

The tests exercise exact-budget success and one-below-budget failure, invalid
limit values, normalization rejection before eventual cancellation, malformed
wire input, and the distinction between rejected witnesses and resource errors.
There is no claim of constant runtime or exhaustive denial-of-service resistance
for arbitrary Python objects beyond the documented bounded interfaces.

## Independent oracle and evidence

`tools/independent_audit.py` does not use the production normalizer to decide
expected results. It evaluates the original AST with `Fraction`. Structural
degree upper bounds give a small Cartesian grid. A polynomial vanishing on
that entire degree-sufficient grid is zero, by repeated univariate interpolation.
The lexicographically first nonzero grid point must be the sequential algorithm's
point: at each prefix it is the smallest coordinate preserving a nonzero
residual, and the root bound ensures that choice lies within the actual degree.

The audit also recovers actual initial and residual degrees with scalar finite
differences over the degree-sufficient grids, independently checking the trace's
degree and trial reports. Cartesian grids occur **only in this test oracle**,
not in production construction or verification.

The default corpus contains 300 cases:

- 19 targeted cases, including an empty ring, absent variables, rational sign
  and reduction, degree drops, cancellation, declared order, the maximum
  coordinate 32, and all eight declared variables.
- Every one of the 81 bivariate polynomials with support among `1, x, y, xy`
  and each coefficient in `{-1, 0, 1}`.
- 200 reproducible seeded random/distributive/cancellation fixtures.

The result is 106 identities and 194 nonidentities, all matching the independent
oracle. The audit also rejects 25 witness mutations; checks original/parsed hash
binding; confirms a valid nonminimal witness; covers typed and wire ingress;
tests cap boundaries; and proves by fault injection that checker acceptance
still works when producer and backend algebra functions are disabled.

Run from the lab root:

    python tools/independent_audit.py --output evidence/audit-normal.json
    python -O tools/independent_audit.py --output evidence/audit-optimized.json

Both modes pass. Checks use explicit exceptions rather than Python `assert`,
so optimization cannot remove the audit's verification. The reports contain
per-case results, mutation outcomes, scope and cap checks, Python version,
audit-source hash, and hashes of the evaluated package sources. The reports do
not independently establish upstream provenance of the vendored bytes; that
is a separate frozen-baseline comparison maintained by the lab.

## Remaining limitations

Finite testing cannot rule out all implementation defects. The identity branch
still trusts the exact normalization backend rather than receiving a fresh
coefficient certificate check. Source code, runtime, parser, hashing, and exact
arithmetic remain in the trusted computing base. These limitations are explicit
and do not undermine the narrower claim checked by a valid concrete mismatch.
