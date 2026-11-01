# v0.7: Small exact integer polynomial witnesses

This separate local derivative adds concrete integer counterexamples for false
formal Q-polynomial identities, without Cartesian-grid enumeration in the
constructor. It appends API, CLI and bridge entrypoints while retaining the
reviewed standalone witness runtime byte-for-byte. The frozen v0.6 source and
the standalone lab are not changed.

## Two different kinds of evidence

The constructor first normalizes the original left-minus-right polynomial.

- If the normalized difference is zero, it returns `coefficient_identity`.
  This is exact coefficient-normalization evidence in the declared formal
  ring. It is not a failed search. The point verifier is `not_applicable`;
  it has **not** independently proved the identity.
- If the difference is nonzero, the constructor chooses small integer
  coordinates by sequential substitution. The fresh checker reparses the
  separately supplied original identity and directly evaluates its expression
  trees, independently of the producer's normalization/substitution logic.
  It checks the supplied point, exact left and right values, and nonzero
  left-minus-right value. This certifies one concrete mismatch.

The checker does not verify the producer's trace, first-choice minimality,
individual degree bounds or trial-count claims. These metadata are tested by
an independent oracle, but they are not part of point-witness acceptance.
The producer and checker share typed parsing, canonical hashing, Python
integers/Fraction arithmetic and the runtime; this is not a diverse proof kernel.

## Mathematical scope and construction

The only supported setting is a formal commutative polynomial ring over Q,
in characteristic zero, with ordered distinct algebraically independent
variables and **no additional constraints**. This excludes quotient rings,
imposed equations, rational functions, finite fields and user-restricted loci.
A point need not satisfy an external condition that was never part of this
unrestricted ring contract. Such a condition must not be silently ignored.

For the next variable of a nonzero residual polynomial, let d be its current
degree. Try integers 0 through d, preserving the first substitution whose
remaining polynomial is nonzero. One nonzero coefficient polynomial in that
variable has degree at most d and therefore at most d roots. Thus a preserving
choice exists. Induction leaves a nonzero rational constant after all variables.

The sharper aggregate guarantee is **n + D** trial substitutions, where D is
the normalized nonzero difference’s total degree. Thus there are at most 40
trials under the current n<=8 and D<=32 caps. This improves the prior sum of
individual degree bounds without changing the algorithm. This bound does not promise polynomial total
runtime in arbitrary succinct expression input: normalization can expand terms,
and integer bit growth matters. Resource failure is inconclusive, not evidence
that no witness exists. See the [existence proof](polynomial-witness/ALGORITHM.md) and the
[sharp total-degree bound](POLYNOMIAL-WITNESS-TOTAL-DEGREE-BOUND.md).

A false-square identity returns x=1, y=1, left value 4, right value 2 and
mismatch 2. The product of eight declared variables needs 16 substitution
trials rather than enumerating a 256-point binary grid. Constants and
empty-variable rings are supported; unused variables receive 0.

## Explicit API

```python
from foundation_math.polynomial_witness import (
    Limits, construct_polynomial_witness, check_polynomial_witness,
    calculate_polynomial_witness, calculate_polynomial_witness_json,
)

receipt = construct_polynomial_witness(original_request)
if receipt["status"] == "success":
    result = receipt["result"]["result"]
    if result["kind"] == "nonzero_evaluation":
        witness = result["witness"]
        checked = check_polynomial_witness(original_request, witness)
```

`calculate_polynomial_witness` accepts exactly:

- `{"operation":"construct","request": original_request}`; or
- `{"operation":"verify","request": original_request,"witness": witness}`.

The original request uses the existing strict polynomial identity AST:
`domain: polynomial_ring`, `coefficient_field: Q`, ordered `variables`,
`operation: verify_identity`, and exactly two `operands`. Only rational
literals, declared variables, binary addition and multiplication are allowed.
No executable source, paths, backend imports or model controls are accepted.

A witness is the bare frozen-lab object containing `schema_version`, canonical
original `input_sha256`, normalized `request_sha256`, `ring`, `assignment`,
`left_value`, `right_value`, and `difference_value`. Fractions are reduced
`numerator`/positive-`denominator` pairs, not matrix `num`/`den` coefficients.
Assignments bind exactly the original declared variables and have plain
integer coordinates 0 through 32. A truthful nonminimal small point can be
accepted; acceptance does not imply it satisfies a claimed current-degree bound.

## Receipt statuses and trust

Every wrapper receipt includes:

- `scope: characteristic_zero_unrestricted_formal_polynomial`;
- `coefficient_field: Q` and `characteristic: 0`;
- `formal_proof: false` and `runtime_goal_acceptance: false`.

`status: success` contains the unchanged lab `result`, operation, a SHA-256
binding of the complete validated operation request, and source hashes for ten
fixed implementation files. Construct success may be coefficient identity or
freshly checked mismatch; verify success contains an accepted point check.

Successful nonzero construction receipts also carry `construction_bound`.
It reports the conservative executable cap n+32 (at most 40), actual trials
n+sum(chosen coordinates), and the unchanged legacy hard cap 264. It does not
recompute or claim the exact normalized degree D, and explicitly says the point
checker does not certify this bound. No second normalization is added solely
for metadata. Identity results and standalone witness checks omit this field.

`status: rejected` means the supplied witness failed checking. It has no result,
accepted claim, input hash or partial evidence. It is not a conclusion about
other possible points. `status: error` means malformed expected input, unsupported
scope, resource exhaustion or a representation/provenance failure; it likewise
has no promoted result. Neither status establishes an identity or witness absence.

Hashes support content binding and reproducibility, not signatures, trusted
loaded-code attestation or mathematical correctness. The client must supply the
intended original request separately, rather than trusting one embedded in an
untrusted producer receipt. Source files and the hosting Python process are trusted.

The domain registry, runtime work queue, scalar/polynomial/counterexample
backends, matrix runtime and Lean adapter remain byte-identical to v0.6.
These explicit tools do not register a new runtime domain, close a research
problem, satisfy a formal-proof requirement, or promote a witness receipt into
runtime goal acceptance.

## CLI

```sh
python -B -m foundation_math polynomial-witness examples/polynomial-witness/false-square.json
python -B -m foundation_math polynomial-witness examples/polynomial-witness/true-distributivity.json
python -B -m foundation_math polynomial-witness-check examples/polynomial-witness/false-square.json examples/polynomial-witness/false-square-witness.json
```

Exit 0 means a successful exact calculation or point check, not always “the
identity is false.” Inspect the explicit kind. Exit 1 means a rejected supplied
witness. Exit 2 means schema/resource/I/O failure. Optional `--output` creates a
new file and never overwrites one. The check command takes a bare original
request and a bare witness in separate files, not enclosing receipts.

The original `python -m polynomial_witness` stdin interface remains unchanged.
Its `verify` subcommand consumes a single `{"request":...,"witness":...}` envelope;
`examples/polynomial-witness/valid-witness.json` is for that standalone interface.
The wrapper adds scope and implementation provenance, not stronger mathematics.

## Resource and transport bounds

The inherited normalizer allows at most 8 variables, depth/degree 32, 1,024 AST
nodes, 256 terms, 256-bit literal components, 2,048-bit coefficients and 100,000
coefficient operations. The proven successful-construction count is at most 40 trials, while the
legacy witness-phase hard cap remains 264 for compatibility. Other caps are 100,000
term visits, 4,096-bit exact evaluation values and 4,096 checker AST-node visits.
Identity results do not consume skipped point-evaluation budgets. Intermediate
values are bounded; a final small result can still be conservatively rejected.

The wrapper limits the complete request to 262,144 canonical JSON bytes, 16,384
structural nodes and depth 80 before execution, with bounded traversal allocation.
It snapshots inputs before execution and caps the complete success receipt at
1,048,576 bytes. The JSON entrypoint also applies the raw wire byte cap.
The CLI reads at most the cap plus one byte per file; the combined check request
must still fit the wrapper cap. Validated Python `Limits` may only lower the
standalone witness-phase ceilings; bridge callers cannot supply limits.

The bridge retains its stricter 65,536-byte input frame cap. A standalone-valid
request/witness is not guaranteed to fit a later bridge frame. Limits are never
raised or bypassed automatically, and no result is truncated into evidence.
The fresh checker does not normalize and may validate a concrete point for an
AST whose polynomial expansion exceeds constructor limits. This is sound point
evidence, not a claim that construction succeeded for that AST.

This boundary is not an OS sandbox or a hard CPU/RSS guarantee. Hosts own process
timeouts. No model, credentials, network server, installs or external execution
are added. All new examples and checks use tiny original synthetic polynomials.

See [bridge contracts](POLYNOMIAL-WITNESS-BRIDGE.md),
[validation](POLYNOMIAL-WITNESS-VALIDATION.md), and
[independent integration review](POLYNOMIAL-WITNESS-REVIEW.md).
The copied `docs/polynomial-witness/` files describe the reviewed standalone
lab baseline; use the v0.7 validation commands for this integrated tree.
