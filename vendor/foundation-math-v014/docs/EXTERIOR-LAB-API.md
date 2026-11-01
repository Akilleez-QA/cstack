# Data-only API and bounded transport

Public Python functions: `exterior_power.calculate(request)` and `exterior_power.verify(request, certificate)`. No expression evaluation, shell commands, paths, URLs, plugins, model names, or backend selection occur inside requests. The local CLI reads paths only as input-file arguments and writes JSON to stdout; it does not create certificate files itself.

All requests have `schema: "fm-exterior-request-v1"`, a supported `operation`, and a nonempty explicit list of distinct `orders`. Exact object keys are required; extensions fail closed.

## Representation

```json
{"schema":"fm-exterior-request-v1","operation":"representation","representation":{"W":2,"Wp":1},"orders":[0,1,2,3,4,5,6,7]}
```

Sparse multiplicities are positive exact integers; `{}` is the zero representation. Negative virtual inputs and explicit zero multiplicities are rejected. Total dimension is at most 24. Labels are exactly `1,W,A,S4,D,T6,P,Wp,V`.

## Supplied split bundle

```json
{"schema":"fm-exterior-request-v1","operation":"bundle","bundle":[{"irrep":"W","twist":-2,"multiplicity":1},{"irrep":"Wp","twist":1,"multiplicity":1}],"orders":[0,1,2,3,4,5]}
```

The empty block list denotes zero. Each block has exactly `irrep`, `twist`, and `multiplicity`. Repeated blocks are allowed and mean repeated direct sums. Multiplicity must be positive. Input twists are integers in [-16,16], at most 12 blocks and rank at most 24. Output terms are sorted by exact line degree and combined canonically. A term contains its full character decomposition and exact class values. The result reports rank, degree, determinant, and bundle central parity.

## Finite necessary H0 comparisons

```json
{"schema":"fm-exterior-request-v1","operation":"wedge_h0_comparison","source":[{"irrep":"S4","twist":-1,"multiplicity":1}],"target":[{"irrep":"W","twist":-1,"multiplicity":1},{"irrep":"Wp","twist":-1,"multiplicity":1}],"orders":[1,2],"twists":[6]}
```

The target is already the supplied formal R(-2), if that interpretation is intended. The calculator does not add a hidden -2 shift. Each row calculates H0((Lambda^k source)(t)), H0((Lambda^k target)(t)), and a possibly signed sparse `target_minus_source`. `multiplicity_test` is `passes` or `obstructed`. This is a formal conditional comparison, never a map verdict.

## Envelopes and budgets

Requests: <=65,536 bytes, canonical form <=65,536 bytes; exterior orders 0..25 (at most 26); comparison twists -16..16 (1..8). Certificates: canonical bytes <=2,097,152. CLI success uses compact JSON plus one newline, so its maximum certificate response is 2,097,153 bytes. Unicode is ASCII-escaped in canonical hashes.

Both JSON ingestion and direct Python boundaries reject floats, bools, nonfinite values, custom containers, unknown fields, unknown labels, cycles, nesting beyond 16, strings longer than 256, and integers beyond 512 bits. JSON integer token length is capped at 155 digits. Duplicate JSON object keys are rejected. Direct dictionaries are copied through a validated canonical round trip before calculation.

Data trees are limited to 180,000 values. Every input source/target rank is <=24; there are <=24 actual repeated summands. Character coefficient arithmetic is bounded at 256 bits. Graded intermediate terms are capped at 8,192, with the producer counting all live order/degree cells and the checker each live order's degree cells. Larger intermediate supports may be rejected even when the syntactic request is within its input limits. Field numerator/denominator components are bounded at 256 bits. Exact symmetric degrees are bounded by 400. No failure returns a partial/truncated result.

A certificate contains the fixed catalog hash, canonical request hash, detached request, entire exact result, scope, and assumptions. The verifier treats the separately supplied request as authoritative. It rebuilds the entire certificate independently and requires exact canonical equality; equivalent but noncanonical rational encodings are not accepted. Certificate dimensions, decomposition, class values, degree, parity, labels, scope, and embedded request are not trusted individually.

CLI exits: 0 success; 2 invalid/bounded-domain/certificate rejection; 4 unexpected internal failure. Unexpected exceptions are not mislabeled mathematical rejection. Missing catalog files presently lead to an internal unavailable failure (exit 4), never verification success. A missing or altered seed/catalog does not trigger a fallback.

Low-level `class_arithmetic.class_powers`, `adams`, and `exterior_graded` expose the exact algorithm for audit and bounded tests, not an alternate externally validated request grammar. The supported trust boundary is `calculate`/`verify` or the CLI.
