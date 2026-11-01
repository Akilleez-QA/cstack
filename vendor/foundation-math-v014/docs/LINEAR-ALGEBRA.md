# v0.6: Exact rational matrices with replayable certificates

## Added capability

This local-only extension certifies RREF, rank, a complete rational nullspace basis, and a square determinant for one explicit bounded matrix. It has no symbolic parameters, expression parser, model calls, arbitrary execution, installs, network service, or runtime proof-acceptance integration.

The producer and independently authored verifier are retained byte-for-byte from the audited standalone lab. Their mathematical contract and proof argument are in [CONTRACT.md](linear-algebra/CONTRACT.md) and [CERTIFICATE.md](linear-algebra/CERTIFICATE.md). The verifier checks the computation without rerunning elimination; it shares strict parsing, resource primitives, and Python `Fraction` arithmetic with the producer. Defensive checking makes the verifier source longer than the compact producer, so no literal smaller-code-kernel claim is made.

## Explicit computational field

The computational field is always **Q**, prominently reported in every receipt and accepted verification. Input `domain: Z` restricts coefficient tokens to integers and embeds them into Q. It does not request integer row reduction, an integral nullspace module, or a lattice basis.

For example, `{"domain":"Z","rows":1,"cols":2,"entries":[[2,1]]}` returns the rational nullspace column `[-1/2,1]`. That is not an integer vector. A lattice-basis feature would require a different algorithm and certificate contract; it is not implemented.

Every accepted claim has `scope: one_explicit_matrix`. It cannot establish generic rank, specialize or quantify over a parameter family, certify a geometric interpretation, or advance a separate proof-repair problem. Only original synthetic test matrices are used.

## Public API

```python
from foundation_math.linear_algebra import (
    MatrixSpec, MatrixCertificate, Limits,
    calculate_matrix, calculate_matrix_json,
    certify_matrix, check_matrix_certificate,
)

matrix: MatrixSpec = {
    "domain": "Z", "rows": 2, "cols": 3,
    "entries": [[1, 2, 3], [0, 1, 1]],
}
receipt = certify_matrix(matrix)
certificate: MatrixCertificate = receipt["result"]["certificate"]
checked = check_matrix_certificate(matrix, certificate)
```

`calculate_matrix` takes the same exact request as `exact_linalg.api.handle_request`: `operation: certify` with `matrix`, or `operation: verify` with both `matrix` and `certificate`. `calculate_matrix_json` applies the strict bounded UTF-8 JSON parser first. Unknown fields and operations are rejected. No paths, executable source, shell commands, model controls, or configurable backend imports are accepted by these interfaces.

Success receipts contain:

- `schema_version: 1`, `status: success`, and the specific operation.
- `scope: one_explicit_matrix`, `computational_field: Q`, `formal_proof: false`, and `runtime_goal_acceptance: false`.
- `request_sha256`, binding the complete validated request, including the independently supplied expected matrix and certificate for a check.
- `implementation`, with version and SHA-256 hashes of six fixed relative source files.
- `result`, containing `ok: true`, an accepted verification scoped to Q, and a produced certificate only for `certify`.

Error receipts contain the common scope/trust flags and `error: {code,message,path}`. They contain no `result`, partial certificate, successful verification, or input hash. Invalid/overlarge objects are not serialized for a failure hash.

Hashes are reproducibility metadata, not signatures, trusted loaded-code attestations, or mathematical evidence by themselves. Source files are assumed stable/trusted while the request runs. Recheck the certificate against the intended explicit matrix in a trusted process rather than trusting a supplied receipt or success flag.

## CLI

```sh
python -B -m foundation_math matrix-certify examples/linear-algebra/rational-matrix.json
python -B -m foundation_math matrix-check examples/linear-algebra/rational-matrix.json examples/linear-algebra/rational-certificate.json
python -B -m foundation_math matrix-certify examples/linear-algebra/rectangular-matrix.json --output matrix-receipt.json
```

The matrix file contains a bare `MatrixSpec`; the certificate file contains the bare certificate, not an enclosing receipt. `--output` creates a new file and never overwrites an existing one. Exit 0 means this explicit certificate was checked. Mathematical/schema/resource errors exit 2 with a structured error receipt; file I/O errors use the existing CLI's stderr/exit-2 behavior. No successful matrix exit means a formal proof or runtime goal has been accepted.

The standalone `python -B -m exact_linalg` one-request stdin interface remains available and unchanged, but does not add the Foundation Math provenance envelope. The two bounded bridge tools are documented [separately](LINEAR-ALGEBRA-BRIDGE.md).

## Bounds and receipt size

All standalone dimension, coefficient, intermediate, operation, work, depth, node, and byte ceilings remain in force. Every complete API request is bounded to 1,000,000 bytes; checking both a matrix and certificate is subject to that combined request bound. The complete success receipt, including implementation metadata, is also checked against the output limit. Small fixed-schema errors are returned even when the caller lowers a success-output limit to zero.

The CLI reads at most the input ceiling plus one byte from each file before rejecting; the combined checked request still must fit. The bridge imposes its existing stricter 65,536-byte total frame limit. A standalone certificate can therefore be too large to re-enter through the bridge. Limits are never relaxed or bypassed automatically.

## Preserved boundaries and portable provenance

The domain registry, work queue, scalar/polynomial calculators, counterexample backend, and Lean adapter remain byte-identical to the frozen base. The old CLI dispatcher is intentionally extended, not claimed unchanged. The bridge appends two allowlisted tools without changing transport limits or the original four tool contracts.

The inherited counterexample vendor provenance labels were made portable in this new copy only: `source_tree` is `Foundation Math v0.2 immutable source snapshot`, and source labels name `Foundation Math v0.2: foundation_math/<filename>`. Vendor code hashes are unchanged. This is a metadata-only cleanup, not a mathematical or implementation change.

Frozen v0.5 and the standalone lab were not edited. The copied base and lab manifests provide review references. Current verification and known limitations are recorded in [LINEAR-ALGEBRA-VALIDATION.md](LINEAR-ALGEBRA-VALIDATION.md).
