# Exact polynomial identity domain

## The obligation advanced

Extend the reusable scalar calculator with one rigorously delimited symbolic
domain: formal commutative multivariate polynomials over the exact rational
field Q. Given two bounded expressions, compute their canonical sparse forms
and decide whether their coefficient difference is zero. This is an executable
normalization algorithm, not a theorem-discovery service or Lean certificate.

The standalone adapter began in the separate v0.2 extension. v0.3 integrates it
through the fixed [domain-aware work queue](DOMAIN-RUNTIME.md), with explicit
acceptance and evidence requirements. Delivered v0.1/v0.2 trees are unchanged;
polynomial receipts are never silently accepted as scalar or formal proofs.

## Run

From the repository root, with Python 3.11 or newer and no dependencies:

```sh
python -m foundation_math polynomial examples/polynomial/distributivity.json
python -m foundation_math polynomial examples/polynomial/false-square-identity.json
python -m foundation_math polynomial examples/polynomial/euler-sequence-composite.json
python -m foundation_math polynomial examples/polynomial/rejected-division.json
python -m unittest discover -s tests -v
python -O -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python tools/audit_polynomial.py .
```

Exit codes: 0 for successful addition/multiplication or a true identity;
1 for a successfully decided false identity; 2 for a rejected/error request.
`--output path.json` creates a new receipt and never overwrites an existing
file. The CLI reads at most the wire-input limit plus one byte.

## API and typed JSON contract

```python
from foundation_math.polynomial import calculate_polynomial, calculate_polynomial_json

receipt = calculate_polynomial({
    "domain": "polynomial_ring",
    "coefficient_field": "Q",
    "variables": ["x", "y"],
    "operation": "multiply",
    "operands": [
        {"type": "variable", "name": "x"},
        {"type": "variable", "name": "y"},
    ],
})
```

`PolynomialRequest`, `Expression`, `RationalExpr`, `VariableExpr` and
`BinaryExpr` describe the typed Python interface. Runtime validation remains
mandatory: type annotations are not validators. The object interface accepts
only built-in JSON-shaped dictionaries/lists, not executable Python objects,
Mapping adapters, or expression strings. Transport callers should use
`calculate_polynomial_json(text_or_utf8_bytes)`, which also rejects duplicate
object keys, nonfinite numeric constants, oversized raw input and huge integer
tokens. Both interfaces return a structured receipt, including on invalid input.

The five request fields above are required and exclusive. Operations are
binary `add`, `multiply`, and `verify_identity`. An expression is exactly one of:

| Type | Required fields | Meaning |
| --- | --- | --- |
| `rational` | `type`, integer `numerator`, integer nonzero `denominator` | Exact rational literal |
| `variable` | `type`, string `name` | A declared indeterminate |
| `add` | `type`, two-element `operands` array | Formal sum |
| `multiply` | `type`, two-element `operands` array | Formal product |

Negative coefficients are rational literals, so subtraction can be expressed
using addition and multiplication by −1. There are no division, inversion,
power, function-call, assignment, binding, evaluation, or arbitrary code nodes.
In particular, `x/x` is rejected rather than replaced by 1. A rational literal
denominator is an integer, never a polynomial.

Variables are ordered, distinct, case-sensitive ASCII names matching
`[A-Za-z][A-Za-z0-9_]{0,31}`. Duplicate declarations, Unicode/whitespace aliases,
alias maps and undeclared names are rejected. `x` and `X`, if both explicitly
declared, are distinct indeterminates, not aliases. The empty variable list is
the constant polynomial ring Q. Variable order is retained and defines the
coordinates of each exponent tuple; it is not silently alphabetized.

## Normal form and mathematical meaning

Internally, each polynomial is a map from nonnegative integer exponent tuples
to `fractions.Fraction` coefficients. Addition combines coefficients;
multiplication uses sparse convolution. Zero coefficients are removed. Output
terms have reduced rational coefficients with positive denominators, and are
sorted in ascending lexicographic exponent-tuple order. Zero is the empty term
list and has `total_degree: null`; a nonzero constant has degree 0.

For `verify_identity`, `result` contains:

- `left` and `right`: both canonical forms;
- `difference`: canonical left minus right;
- `equal`: true exactly when this difference has no terms;
- `mismatch_witness`: null for equality, otherwise the first nonzero monomial
  in the difference, its coefficient, and both side coefficients.

An identity's false result is a successful computation, not a tool failure.
The witness is a **coefficient witness**, not a sampled point. For example,
the false identity `(x+y)(x+y) = x*x+y*y` returns exponent tuple `[1,1]`,
left coefficient 2, right coefficient 0, and difference coefficient 2.
The distributivity example normalizes both sides to
`x*y + (2/3)*x + (1/2)*y + 1/3`.

Mathematically, formal polynomials are determined by these coefficient maps;
structural induction on the allowed AST and the usual convolution definition
justify the algorithm. The implementation has executable tests, not a
machine-checked proof of its own correctness. Trust still includes Python,
Fraction, this adapter, and the deployment environment.

This checks **formal polynomial ring equality only**. It does not implement
quotient relations, localization/rational functions, finite-field semantics,
pointwise finite testing, analytic identities or domain-restricted cancellation.
For example, `x*x=x` is false in Q[x] even if a separate quotient might impose
that relation, and `x*(x-1)=0` is false even though it holds at sample inputs 0
and 1. No sample evaluations are used.

## Resource limits

The fixed limits are recorded in every receipt:

- 65,536 input bytes, 8 variables, expression depth 32;
- 1,024 total AST nodes across both operands;
- total degree 32 and 256 nonzero terms in every intermediate polynomial;
- 256 bits in each input numerator/denominator;
- 2,048 bits in every intermediate/result coefficient numerator/denominator;
- 100,000 cumulative coefficient-arithmetic steps.

For typed inputs the byte limit applies to canonical JSON; strict JSON ingress
also limits original UTF-8 wire bytes. Depth is measured from 1 at each root
expression. Multiplication charges both products and coefficient accumulation
before expanding. Intermediate limits are intentionally conservative: a larger
expression can be rejected even when later multiplication by zero or
cancellation would make its final answer small. Bounds are not configurable by
an untrusted request. There is no silent float fallback or partial answer.

## Receipts and replay

Receipts retain original parsed input, a request with reduced rational literals,
explicit ring and ordered variables, result, Python/adapter versions, limits,
scope, and hashes of canonical input/request/result. Source hashes cover both
`polynomial.py` and its canonical-JSON helper module `calculator.py`. Canonical
JSON here uses the seed's schema-local convention, not a universal RFC 8785
claim. Raw whitespace/encoding bytes are not hashed as `input_sha256`; callers
may separately hash the original transport file.

Hashes bind content, not authorship, authenticity or truth. Result hashes alone
do not identify the ring: retain the corresponding request hash and explicit
ring. To validate an untrusted receipt, validate/replay its request with the
trusted backend and compare the complete result, ring, declared scope and
source versions. A hash-chain integrity check is not mathematical replay.
Parsing failures leave input/request null; resource failures after successful
parsing preserve the request but never produce a successful partial result.

## Orchestration integration

v0.3 uses a fixed typed dispatcher and the acceptance gates documented in
[DOMAIN-RUNTIME.md](DOMAIN-RUNTIME.md). The complete original request, ring,
ordered variables and deterministic receipt are bound to trusted replay.
`status=success` alone is insufficient: an identity also requires
`result.equal is True`, a matching candidate, and a satisfied evidence requirement.

`validate_polynomial_request(request)` exposes the same bounded parser without
performing arithmetic; it returns a detached normalized request or raises
`PolynomialError`. This prevents runtime admission from inventing a second AST
grammar. The existing calculation API continues to return structured errors.

The evidence remains `exact_polynomial_normalization`, not kernel-checked formal
proof. The restricted Lean adapter still cannot accept variable or
rational-polynomial statements and is not invoked by the queue.

Do not treat a receipt as proof of a broader geometric statement just because
the receipt checks one map-composition identity. The worked
[Euler-sequence pitfall](EULER-SEQUENCE-PITFALL.md) makes this distinction
concrete without any problem-specific coefficients or evaluations.
