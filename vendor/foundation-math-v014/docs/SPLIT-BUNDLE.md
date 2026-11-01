# Formal supplied-splitting adapter contract

This adapter adds bounded formal arithmetic, not a new accepted runtime goal domain.
The accepted lab engine is unmodified. See SPLIT-BUNDLE-LAB-API.md for its exact
request grammar and SPLIT-BUNDLE-LAB-MATHEMATICS.md for all mathematical assumptions.

## Python API and CLI

- foundation_math.split_bundle.calculate_split_bundle(request): produce a certificate,
  then independently verify it against the original request before success.
- check_split_bundle_certificate(expected_request, certificate): recompute from the
  separately supplied original request. This path never imports a producer or its parser.
- python -m foundation_math split-bundle-calculate REQUEST.json
- python -m foundation_math split-bundle-check REQUEST.json CERTIFICATE.json

Receipts contain schema_version 1; status success/error; scope
formal_supplied_split_bundle_arithmetic_only; computational_field Q(sqrt(5)); and
explicit false formal_proof, runtime_goal_acceptance, geometric_realization and
map_rank_claim fields. table_group_identification_assumed and supplied_splitting_assumed
are true. Success binds source hashes and the original request hash, includes independent
verification, and includes the certificate only for calculate. The adapter version is
0.10.0-dev. Errors withhold all result/certificate fields. Exit 0 is success, exit 2 is
usage/input/domain/certificate rejection, and exit 4 is an internal failure with sanitized
details. No output-file option is supported; stdin bridge calls cannot supply paths.

The exact request limits are 32 blocks per bundle, multiplicities 0..1,000,000,
block and requested twists -64..64, and 1..32 distinct requested twists. Empty bundles,
zero multiplicities and duplicate blocks are supported. Ordered request presentation is
bound even when two different presentations have the same mathematical answer.

H⁰ and H¹ are genuine characters; Euler is their signed difference. Original degree
is distinct from degree after twisting. Hom-space dimensions are not the rank of a
chosen map, kernel/image dimensions, degeneracy, or an embedding conclusion. No actual
bundle identification, asserted geometric input, matrix or point is accepted.

The fixed physical labels distinguish A/V and W/Wp. The catalog identification and
standard P(W) linearization are assumptions, not consequences of hash checks or character
orthogonality. Every result remains conditional on the supplied formal splitting.
