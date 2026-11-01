# Bounded API and CLI

Python3.10+ standard library only; no installation, network or sibling checkout required. From this directory, import calculate and verify from split_bundle. calculate(request) returns a certificate. verify(expected_request, certificate) returns a verification receipt or raises VerificationError. Verification always requires the caller's external expected request. The schema versions are fm-split-bundle-request-v1, fm-split-bundle-certificate-v1 and fm-split-bundle-verification-v1.

## Requests

Cohomology request:

```json
{"schema":"fm-split-bundle-request-v1","operation":"cohomology","bundle":[{"irrep":"1","twist":-10,"multiplicity":1},{"irrep":"1","twist":-8,"multiplicity":1},{"irrep":"V","twist":-8,"multiplicity":1}],"twists":[8]}
```

Hom request:

```json
{"schema":"fm-split-bundle-request-v1","operation":"hom","source":[{"irrep":"W","twist":-3,"multiplicity":1}],"target":[{"irrep":"W","twist":-3,"multiplicity":1}]}
```

Each bundle is a list of zero to32 blocks. Each block has exactly irrep, twist, multiplicity. Multiplicity is an exact integer0..1,000,000; zero multiplicities are accepted. Duplicate blocks remain a multiset and add their multiplicities; their request identity/order is preserved. The empty list represents the zero bundle. Physical labels are exactly 1,W,A,S4,D,T6,P,Wp,V. Every block twist is an exact integer-64..64. The cohomology twists list has1..32 distinct exact integers in-64..64; order is preserved. Hom source/target orientation matters, and the operation has no twist list.

All object keys are required and no additional keys are accepted. No inline asserted geometric property, object name, experimental map data, point, matrix, embedding requirement or map-rank field is part of this grammar. Floats, booleans, subclasses of JSON primitives and nulls in required fields are rejected. Strings are not coerced to integers.

## Output

The certificate binds the canonical request's SHA256 and full detached request, the fixed catalog SHA256, explicit assumptions, scope, and result. The scope is formal_supplied_split_bundle_arithmetic_only. There is no producer status that grants runtime acceptance.

Cohomology result contains operation, bundle={rank,degree}, and one result per requested twist, containing twist,rank,degree,h0,h1,euler. Here degree in each row is the degree after twisting, while bundle.degree is the original degree.

A character has multiplicities in the fixed nine-label order, dimension, classification (genuine or proper_virtual), center_parity (zero/even/odd/mixed), even_dimension, odd_dimension, negative_multiplicities and nine class_values. Classification and parity apply to the full irreducible support, not just signed dimension. Zero is genuine with zero parity. H0 and H1 must be genuine; Euler may have negative multiplicities. class_values contains reduced rational-pair entries [a_num,a_den,b_num,b_den] for a+b√5. Signed dimension0 does not imply a zero character.

Hom result contains source/target rank and degree, hom_character, equivariant_hom_dimension, and an explicit conclusion limiting this to the dimension of the equivariant map space. The dimension of hom_character is the dimension of all sheaf maps, not just equivariant maps. Neither number is a map rank. No actual map or embedding conclusion is generated.

Verification rebuilds all fields, not just a digest or a few invariants. Changed labels, class values, dimensions, provenance, scope, assumptions, conclusions, extra fields, or a different external request are rejected. Even changing a zero-multiplicity block, reordering input blocks, or changing a redundant formal presentation requires its own certificate. This is intentional request binding, not mathematical inequivalence.

## Finite resource bounds

- Request bytes≤65,536; certificate bytes≤262,144, for ingestion and canonical in-memory encoding.
- At most32 blocks per bundle and32 requested twists. Cohomology has at most1,024 block/twist pairs. Hom has at most1,024 source/target pairs.
- Twists/multiplicities as above. H0 symmetric degree≤128; H1 degree≤126; Hom degree≤128. Symmetric characters are cached.
- Result irreducible coefficients have at most128 bits. Fixed catalog arithmetic uses exact rational numbers, no unbounded input polynomial/AST.
- In-memory JSON data: depth≤16, at most8,192 values, strings/object keys≤256 characters, integer magnitude≤300 bits. Strict JSON ingestion additionally caps integer literals at90 digits and rejects duplicates, NaN, infinities and all floating-point literals. The byte stream's nesting is bounded before JSON parsing.
- Limits are enforced by ordinary checks, not Python assert, and survive python -O.

Resource limits are an explicit supported domain, not a mathematical restriction on the underlying formulas. Above-limit requests are rejected rather than truncated. No overall wall-clock claim is made; the elementary operation counts are bounded.

## CLI

```sh
python cli.py calculate examples/negative_h1_critical.request.json > /tmp/certificate.json
python cli.py verify examples/negative_h1_critical.request.json /tmp/certificate.json
python -m split_bundle calculate examples/hom_not_map_rank.request.json
python -O run_tests.py
python reproduce.py
```

Use an absolute path to cli.py to invoke from another working directory. The module form requires this directory on Python's import path. CLI output is JSON; exit0 means successful calculation or verification, exit2 means an input/error response on stderr. argparse usage errors also use exit2. Output redirection is the caller's file-writing action; the arithmetic API does not write files.

The tests, reproducibility and packaging scripts write only local evidence/examples or the requested ZIP. run_tests.py uses deterministic synthetic fixtures. reproduce.py compares normal/-O outputs and replays the manifest-selected archive in an isolated temporary directory. build_release.py builds only from RELEASE-FILES.json, never a recursive directory scrape.
