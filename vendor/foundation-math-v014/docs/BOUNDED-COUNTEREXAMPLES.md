# Foundation Math: bounded exact counterexample lab

This v0.4 local development extension keeps bounded-search evidence separate from runtime goal acceptance. It is not a published release.
This advances one obligation: search an explicit finite integer Cartesian box for
an assignment satisfying every constraint and falsifying a rational-polynomial
assertion, then check a proposed assignment against the original request.

The implementation uses Python 3.11+ and the standard library only. No model calls,
network, shell-expression evaluation, installs, credentials or repository setup.
The source parser is a byte-identical, provenance-pinned snapshot of the prior
polynomial extension. Neither that source tree nor the v0.3 runtime is modified.
The base is the frozen v0.3 domain-aware runtime, retained in this tree without changes to its verifier or domain registry.

## Run

From this directory:

```sh
python -m bounded_counterexample search examples/counterexample/true-bounded-inequality.json
python -m bounded_counterexample search examples/counterexample/false-bounded-inequality.json
python -m bounded_counterexample check-witness examples/counterexample/false-bounded-inequality.json examples/counterexample/valid-witness.json
python -m bounded_counterexample search examples/counterexample/integer-domain-pitfall.json
python -m bounded_counterexample check-witness examples/counterexample/integer-domain-pitfall.json examples/counterexample/rational-half-not-in-domain.json
python -m unittest discover -s tests -v
python -O -m unittest discover -s tests -v
python tools/independent_audit.py
```

Search exits 0 for complete finite exhaustion, 1 for a concrete counterexample,
and 2 for errors. Checking exits 0 for a valid witness, 1 for a rejected witness,
and 2 for invalid original requests/resource errors. `--output new-file.json`
creates a new file and refuses to overwrite one. These exit meanings are
operation-specific; exit 0 is **not** universal truth or formal verification.

## Contract

Public functions are `search_counterexample(request)`,
`check_witness(original_request, assignment)`, and strict JSON variants
`search_counterexample_json(data)` / `check_witness_json(request_data, assignment_data)`.

The exact required request fields are:

```json
{
  "domain": "finite_integer_box",
  "coefficient_field": "Q",
  "variables": ["x"],
  "bounds": {"x": {"lower": -3, "upper": 3}},
  "constraints": [],
  "assertion": {
    "relation": "ge",
    "left": {"type": "variable", "name": "x"},
    "right": {"type": "rational", "numerator": 0, "denominator": 1}
  }
}
```

Each constraint uses the same predicate shape as the assertion. Relations are
`lt`, `le`, `eq`, `ne`, `ge`, `gt`. Expressions are exactly typed rational literals,
declared variables, or binary `add`/`multiply` nodes with a two-element `operands`
array. Negative coefficients express subtraction. There are no text expressions,
functions, division/power nodes, aliases, quantifiers or executable programs.
The validated expression tree is compiled to frozen typed nodes, not evaluated
as Python source. Runtime checks remain mandatory despite public TypedDicts.

Variables are distinct, ordered, case-sensitive ASCII identifiers matching
`[A-Za-z][A-Za-z0-9_]{0,31}`. Bounds must bind exactly these names, and every closed
integer interval must satisfy lower <= upper. Empty intervals are rejected rather
than silently interpreted. Unused declared variables still contribute their full
factor to the domain cardinality. The zero-variable box contains exactly one
assignment, `{}`, and handles constant assertions/constraints accordingly.

All supplied assignments must bind every declared variable exactly once using
built-in JSON integers. Booleans, floats, strings, Fraction objects and rational
objects are not coerced, even if numerically integral. The bounds are inclusive.
The coefficient field Q describes polynomial coefficients, **not** the assignment
domain. The assignment domain is finite and integer-valued.

## Outcomes and scope

A successful search returns one of:

- `counterexample_found`, with an exact assignment and evaluated constraint and
  assertion sides as reduced rational numerator/denominator pairs.
- `no_counterexample_in_declared_finite_domain`, only after the complete declared
  box has been adjudicated. This means exactly what the label says, nothing about
  larger integer boxes, all integers, rationals or reals.

Every constraint is evaluated at a visited point. The assertion is evaluated only
if all constraints hold. A false assertion outside the constraints is not a
counterexample. If no points satisfy the constraints, exhaustion is recorded with
`eligible_count: 0`, making the vacuous finite result visible.

Search is deterministic: variables use declaration order; each interval is
ascending; the final coordinate varies fastest. It stops at the first witness.
`visited_count` counts fully adjudicated points, not partially evaluated points;
`eligible_count` counts those fully adjudicated points satisfying all constraints.
`complete` means every point of the full box was adjudicated. It can be true even
with a counterexample if that witness was the last point. It is never a universal
proof flag. Checker receipts have `visited_count: 0`, `complete: false` and a
separate `checked_assignment_count` because checking one witness is not search.

`check_witness` accepts the original request and an assignment only. It re-parses
the domain, bounds, constraints and assertion, enforces integer membership, and
computes the values anew. It does not consume a producer verdict, claimed values,
or supplied success flag. A completed check returns `valid: false` for an invalid
assignment, failed constraint or true assertion. Invalid original requests,
unsupported input and resource exhaustion return `status: error`, `result: null`.
Neither error nor witness rejection is interpreted as finite exhaustion.
Final receipt serialization is also fail-closed: if a host representation limit
prevents hashing an otherwise bounded exact result, the result is discarded and
an explicit representation_limit error is returned without changing host limits.
The error receipt is hashed if representable; otherwise its evidence hash is null.

## Resource and input boundary

Fixed, non-request-configurable limits are included in every receipt:

- 65,536 canonical request bytes and, for JSON entrypoints, raw UTF-8 bytes;
- 8 variables, 16 constraints, full box cardinality at most 10,000;
- expression depth 32, 1,024 total AST nodes across all predicates;
- syntactic polynomial degree upper bound 32;
- 256 bits per input integer, 4,096 bits per exact intermediate value;
- 250,000 cumulative evaluation steps across the search.

Every AST node visit and predicate comparison costs one step. Fraction operations
are bounded by the value-size limit, including intermediate values. One operation
may form a temporary numerator/denominator up to twice the bit cap before rejecting
it; this remains bounded. Degree is a conservative syntactic bound: multiplication
adds degree bounds even if cancellation or a zero factor could simplify the result.
No sparse normalization or expansion is needed for evaluation. Parsing and
compilation are separately bounded by node/depth/input limits. Search cannot extend
a box, silently truncate it, sample randomly or restart a work budget per point.

Strict JSON ingress rejects duplicate keys at every level, nonfinite constants,
huge integer tokens, oversized wire data and unsupported nesting. The object API
accepts built-in JSON-shaped values only; annotations do not authorize coercion.
A completely validated box is retained with its exact full cardinality even if a
later admission, AST or evaluation limit fails. Otherwise domain/cardinality is
null. No successful partial exhaustion receipt is returned.

## Evidence and trust

Receipts include original validated input, normalized request, exact domain,
counts, completeness, limits, work usage, outcome, backend/Python versions and
SHA-256 hashes for original input, normalized request, result, overall evidence
and implementation/parser/canonical-JSON source. Witness-check receipts also bind
validly shaped integer assignments, including integer assignments outside bounds.
A malformed/noninteger/oversized candidate is not retained or hashed. Its rejection
receipt identifies the rejection reason, **not** the original malformed bytes;
different such candidates may have the same evidence hash. Raw wire bytes and
whitespace are not hashed by the API. Callers needing that identity can hash their
transport file separately.

The evidence hash covers every receipt field except itself. Canonical JSON is the
schema-local convention inherited from the calculator, not a general RFC 8785
claim. Hashes bind content, not authorship, truth or authenticity. A malicious
producer can recompute hashes. Trusted verification must replay the original
request or call `check_witness` on the exact intended request and assignment.

Search and checker share the parser and evaluator. The checker is independent of
the producer's verdict, **not** an independently implemented mathematical kernel.
A separately implemented integer-pair oracle is used in the validation audit.
Passing tests is executable evidence, not a proof of implementation correctness.
No Lean kernel is run, and receipts explicitly set `formal_proof: false` and
`universal_proof: false`.

## Domain pitfall example

The polynomial x*x - x is nonnegative at every integer in the example box [-3,3].
At rational x=1/2 its value is -1/4, but that point is not an integer and therefore
is rejected by the integer-domain checker. The finite search establishes neither
nonnegativity at all integers nor nonnegativity over Q or R. A future rational-grid
search would need its own explicit domain contract, not reinterpret these receipts.

## Integration boundary

The parent must review this new integration tree before packaging. A found and checked witness
could refute a precisely matching assertion under its declared constraints. Finite
exhaustion must never close an unrestricted polynomial or universal goal. Exact
original request, variable order, coefficient field, domain, bounds and constraints
must remain bound to evidence. The v0.4 CLI adds explicit counterexample-search and counterexample-check commands. The frozen v0.3 tree is unchanged. Runtime domains remain Z, Q and polynomial_ring, so finite-box receipts cannot close runtime goals.
