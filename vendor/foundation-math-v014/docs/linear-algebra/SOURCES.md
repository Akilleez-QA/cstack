# Original sources and provenance

All lab runtime code, API documents, examples, tests, and mathematical explanations in this directory were newly authored for this standalone lab. No third-party source code, research matrix, symbolic parameter family, or external dataset was copied or loaded. The implementation uses only Python standard-library modules.

The certificate producer implements elementary Gauss-Jordan row reduction over `fractions.Fraction`. The verifier was independently authored from the documented certificate schema without reading the producer. They intentionally share the strict data contract, resource accountant, and standard rational type; that shared foundation is part of the trust boundary.

Test fixtures are deliberately small synthetic matrices: exhaustive entries in `{-1,0,1}` for selected shapes, seeded tiny rational samples, manually authored certificates, and large integer cancellation solely to test exactness. The independent rank oracle enumerates square minors; the independent determinant oracle enumerates signed permutations. Neither oracle imports or reproduces the producer's elimination algorithm.

Standard elementary facts used by the verifier are explained directly in `CERTIFICATE.md`: invertibility and determinant effects of elementary row operations, RREF pivot independence, and the free-coordinate argument for nullspace completeness. This lab claims software validation of those finite calculations, not a new theorem, formal verification, or evidence about any separate proof-repair problem.
