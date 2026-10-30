# Data contract and failure semantics

## Requests

An exact-key JSON object:

```json
{
  "schema": "fm-character-request-v1",
  "expression": {
    "op": "tensor",
    "left": {"op": "irrep", "label": "W"},
    "right": {"op": "irrep", "label": "W"}
  },
  "expectation": {
    "classification": "genuine",
    "equals": {"1": 1, "A": 1}
  }
}
```

The expression grammar has exactly these variants:

- `{"op":"irrep","label":LABEL}`.
- `{"op":"virtual","coefficients":SPARSE_INTEGER_MAP}`.
- `{"op":"symmetric_power","degree":INTEGER}`. This always means Sym^degree(W), never an arbitrary representation's symmetric power.
- `{"op":"add"|"subtract"|"tensor","left":EXPRESSION,"right":EXPRESSION}`.

Only the nine exact physical labels are allowed. Sparse maps omit all zero coefficients; the empty map is zero. Coefficients are signed JSON integers, never booleans, floats, numeric strings or fractions. Operator strings are data, not executable expressions. Unknown keys, unknown schemas, aliases and duplicate JSON keys are errors.

`expectation.classification` is `any`, `genuine` or `proper_virtual`. `equals` is either null or an exact sparse decomposition in the same labeling. An unmet expectation raises `E_EXPECTATION`, rather than returning a misleading success certificate. Genuine includes the zero character; proper_virtual means at least one negative irreducible multiplicity. Every accepted expression represents an integral virtual character.

All in-memory data containers and string/integer fields must have their exact built-in types; subclasses and custom equal/hash-equivalent dictionary keys are not accepted. The API takes ordinary data dictionaries and returns ordinary data dictionaries. Request parsing constructs a frozen internal AST and detaches the request from caller-owned mutable objects. The separate verifier validates the external expected request itself; it does not accept a request solely because the certificate embeds it.

## Certificates and verification receipts

A certificate has exactly: schema, catalog_sha256, request_sha256, request, result, class_values, scope. The schema is fm-character-certificate-v1; scope is universal_representation_arithmetic_only.

`result` records the nine ordered multiplicities, signed dimension, genuine/proper_virtual classification, center_parity, signed even_dimension and odd_dimension, and a sparse map of negative_multiplicities. Center parity depends on nonzero irreducible support, not just on the trace at the center or signed dimension. It is zero/even/odd/mixed; zero is distinguished because the zero representation has no unique nonzero support parity.

`class_values` contains nine exact values a+b sqrt(5), each encoded `[a_numerator,a_denominator,b_numerator,b_denominator]` in reduced form with positive denominators. Integer zero is encoded `[0,1,0,1]`. Noncanonical but equal rational encodings are rejected, not silently normalized.

JSON hashes use SHA-256 on ASCII JSON with sorted object keys, no whitespace, ensure_ascii=true and no nonfinite numbers. Arrays retain their order. The catalog pin instead hashes the exact distributed catalog bytes, including whitespace. Hashes provide content binding only, not mathematical truth or authorization.

`verify(expected_request, certificate)` reevaluates all arithmetic from the external request and requires the complete canonical certificate data to agree. It rejects extra claims, modified scope, booleans in place of integers, shortened vectors, changed request hashes, and valid certificates for a different request. Its receipt explicitly has runtime_acceptance=false and lean_proof=false. Do not treat this receipt as a proof object in another system.

## Exact budgets

- Request input: at most 65,536 raw bytes and at most 65,536 bytes in canonical ASCII JSON.
- Certificate input: at most 262,144 raw bytes and at most 262,144 bytes in canonical ASCII JSON.
- Fixed catalog: at most 65,536 bytes; a specific SHA-256 is mandatory.
- Expression: at most 127 nodes; root depth 1, maximum depth 16. Each occurrence is counted, even if Python objects are shared.
- Symmetric degree: integer from 0 through 256 inclusive.
- Input sparse coefficient: absolute value at most 2^63−1.
- Every intermediate and final irreducible coefficient: absolute value at most 2^256−1.
- Expected decomposition coefficients: the same 256-bit bound.
- Every reduced numerator and denominator of an intermediate verifier class value: at most 272 bits in absolute value.
- Certificate data tree: at most 8,192 values and depth 32, with the root at depth 1. Container occurrences count as values; dictionary keys do not. These bounds also terminate cyclic or oversized in-memory objects before serialization.
- JSON integer token: at most 90 decimal digits, excluding its optional minus sign. Later field bounds still apply.
- The immutable audited table cache holds one table. Every use still rereads and hashes the fixed catalog bytes before reusing it.

Intermediate budgets apply before cancellation at an ancestor: a too-large expression minus itself is rejected. Temporary multiplication and finite sums are bounded by these operand limits and the fixed nine-by-nine catalog, not by wall-clock time. With 127 nodes there are at most 64 leaves and 63 binary nodes; even all 64 leaves at Sym^256 use at most 16,384 symmetric recurrence steps. No unrestricted loops, external evaluators, subprocesses, filesystem paths, group definitions or resource-limit overrides may appear in a request. This is a deterministic bounded arithmetic contract, not an operating-system sandbox or hard wall-clock/memory quota.

Files are read with limit+1 bytes before JSON parsing. The API receives in-memory Python data and applies the same structural/canonical-size bounds; allocation of the caller's already-created object is outside the contract. Certificate canonical-byte size, including JSON escaping and dictionary keys, is counted before constructing its serialized copy; large strings are first rejected using a constant-time length lower bound. All code uses explicit exceptions rather than assert for acceptance checks.

## Errors and exits

Errors are exceptions with a stable `code` property; producer/boundary errors use DomainError, independent verifier errors use VerificationError. CLI errors are one JSON object on stderr; there is no success JSON on stdout.

- E_USAGE: unsupported CLI arguments.
- E_IO: requested input file cannot be read.
- E_JSON: malformed JSON/UTF-8, recursion during JSON decode, or duplicate key.
- E_TYPE: a field is not the required exact type, including float/boolean coefficients.
- E_SCHEMA: wrong/extra/missing keys, unknown label/operator/schema or invalid decomposition shape.
- E_BUDGET: a stated input or arithmetic budget is exceeded.
- E_CATALOG: missing, changed or inconsistent fixed catalog.
- E_CHARACTER: failed integrality/reconstruction of an evaluated class function. Valid expressions should never reach this failure; investigate the implementation or input assumptions rather than treating it as a theorem.
- E_EXPECTATION: arithmetic is defined but the requested classification or decomposition is false.
- E_CERTIFICATE: certificate disagrees with the external expected request, fixed catalog, exact result or allowed scope.
- E_INTERNAL: unexpected implementation exception. It is not a mathematical rejection and requires investigation.

Exit 0 means calculation/verification completed; exit 2 means validation, I/O, catalog or certificate rejection; exit 3 means unmet expectation; exit 4 means unexpected internal failure. Error wording is descriptive; codes and exit meanings are the stable contract.

A producer certificate is not automatically accepted. Supply it and the original expected request to the independent verifier. Verification cannot establish that the caller's request accurately formalized their intended mathematical problem.
