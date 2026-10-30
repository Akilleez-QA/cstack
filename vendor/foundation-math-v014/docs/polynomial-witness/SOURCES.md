# Source provenance and trust

The runtime has only standard-library dependencies. It includes byte-identical
snapshots of the Foundation Math exact polynomial extension's
`foundation_math/polynomial.py` and `foundation_math/calculator.py`, relocated
into `polynomial_witness/_vendor/`. The package initializer is new. The original
source files were read and copied, never edited. `VENDOR-PROVENANCE.json` records
relative source labels, byte counts and SHA-256 values; no user history or
machine-specific paths are needed to replay it.

The producer uses the snapshot's typed parser and sparse normalization helpers.
The checker uses the typed parser and canonical hashing, but its concrete AST
evaluation is independently written and does not import the producer. Neither
component is independent of Python's Fraction arithmetic or the shared parser.

All fixtures, examples and randomized oracle cases are original synthetic
polynomials. No application-source polynomial, research parameters, matrices,
problem-specific fixture or previously consumed experiment was imported or
executed. No repository or external service was created, modified or published.
The written root-bound argument is elementary and self-contained.

`SOURCE-MANIFEST.json` records source artifact hashes. Validation receipts name
the actually executed checks, not hypothetical test successes. Test evidence
is software evidence only; there is no proof-assistant kernel acceptance,
external CAS interoperability, live model execution, or production service.
