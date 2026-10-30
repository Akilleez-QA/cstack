# Typed requests, results, and limits

## Request

The request object has exactly these fields:

```json
{
  "domain": "polynomial_ring",
  "coefficient_field": "Q",
  "variables": ["x", "y"],
  "operation": "verify_identity",
  "operands": [
    {"type": "variable", "name": "x"},
    {"type": "rational", "numerator": 0, "denominator": 1}
  ]
}
```

Expressions are rational literals (integer numerator and nonzero integer
denominator), declared variables, or binary `add`/`multiply` nodes with exactly
two `operands`. Extra fields, division, powers, aliases, floats, booleans in
integer slots, nonfinite JSON, duplicate JSON fields, duplicate or unknown
variables, and executable strings are rejected. Variable names are 1–32
case-sensitive ASCII characters matching `[A-Za-z][A-Za-z0-9_]*`.

Rational request literals are normalized to reduced form with positive
denominator. `input_sha256` binds canonical JSON of the original supplied
request, and `request_sha256` binds its normalized typed version. These are
integrity bindings, not authentication or provenance claims about a sender.
Whitespace and object key order are not hashed as raw wire bytes.

## Result kinds

A successful producer/constructor returns `status: success` and one of:

- `coefficient_identity`: `equal: true`, with the normalized difference having
  empty terms and null degree. This is exact coefficient-normalization evidence.
  `construct` reports `verification.status: not_applicable`, not point-checker acceptance.
- `nonzero_evaluation`: `equal: false`, with a witness, producer-only construction
  trace, current- and initial-degree trial bounds, and normalization term count.

`construct` sends every produced nonzero witness to the fresh checker and returns
success only if it accepts. If checking cannot finish, the constructor returns
an error with no promoted result. `produce` alone does not independently check.

The witness has exactly `schema_version`, `input_sha256`, `request_sha256`,
`ring`, `assignment`, `left_value`, `right_value`, `difference_value`.
The ring repeats coefficient field Q, ordered variables and the explicit
commutative-polynomial-ring kind. The assignment is a dictionary whose keys
are exactly the declared variables. Coordinates must be plain integers in
0..32. Rational values must be reduced integer pairs with positive denominators.
The difference convention is **left minus right**, including its sign.

`verify_witness(original_request, witness)` parses the original request afresh.
It neither accepts a request supplied inside an untrusted producer receipt as
an external expected identity, nor imports the producer. It checks all binding
fields and recomputes both original AST values and their nonzero difference.
It accepts arbitrary truthful small-integer points, not only the producer's
first chosen point. Thus its acceptance does not certify trace minimality or
individual degree bounds. The trace stays outside the accepted witness schema.

## Independent phase limits

Frozen adapter validation/normalization limits:

| Limit | Value |
|---|---:|
| Canonical original request bytes | 65,536 |
| Declared variables | 8 |
| Expression depth | 32 |
| Total AST nodes across two operands | 1,024 |
| Input integer bits | 256 |
| Intermediate/result total degree | 32 |
| Intermediate/result sparse terms | 256 |
| Intermediate/result coefficient bits | 2,048 |
| Coefficient arithmetic steps | 100,000 |

Witness `Limits` values default to the following hard maximums and can only be
lowered. A zero value intentionally prohibits consuming that phase's budget.

| Field | Phase | Maximum |
|---|---|---:|
| `max_trials` | Sequential substitution attempts | 264 |
| `max_substitution_term_visits` | Sparse substitution term visits | 100,000 |
| `max_evaluation_nodes` | Fresh AST checker, total across both operands | 4,096 |
| `max_value_bits` | Substitution and concrete-evaluation exact intermediates/results | 4,096 |

These are phase-specific, not interchangeable global operation counts.
`max_value_bits` does not replace the adapter's coefficient cap. The producer's
final sparse evaluation is bounded by the adapter's fixed term/degree/variable
caps and `max_value_bits`, not the checker's AST-node counter. Identity results
need neither substitution nor concrete evaluation, so they do not consume those
budgets. Intermediate values are checked, and rejection can be conservative
even when a final simplified answer would fit.

The fresh checker shares strict parsing but deliberately does not run polynomial
normalization. It can check a concrete small point for an AST whose expansion
would exceed the producer's degree or sparse-term caps, provided its own exact
AST evaluation fits the parser/evaluation caps. This is sound concrete-point
evidence, not a claim that the constructor could process that AST.

Strict JSON entrypoints cap raw wire bytes at 262,144, allow no integer larger
than 4,096 bits, then enforce the narrower per-field/request bounds. The CLI
reads at most one byte past the cap to detect oversize input. Nested JSON beyond
host/parser limits is rejected rather than executed.

## Errors and evidence

Malformed expected requests, unsupported operations, resource limits and host
representation failures return `status: error`. A well-parsed request with a
malformed or false supplied witness returns `status: rejected`; oversized
witness values/evaluation failures remain inconclusive errors. Neither outcome
means another witness does not exist. Exception handling does not catch or
claim recovery from arbitrary OS/memory failures.

Receipts identify source hashes for the frozen polynomial adapter, canonical
JSON helper, contract and applicable producer/checker module. Hashes bind the
record to code; they do not prove code correctness. Frozen provenance and a
separate lab source manifest allow independent replay against exact bytes.
