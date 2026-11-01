# Reproduction and adversarial validation

Run `python reproduce.py` from this directory, or invoke it by absolute path from another working directory. It runs the same suite in ordinary and optimized Python, compares their bytes, and checks a fresh isolated copy containing only this pack. Python's standard library is sufficient. Every child process is bounded by a 180-second test-harness timeout; that is a test failure limit, not a claimed runtime resource bound.

The authored suite checks all 257 allowed symmetric degrees, all 81 ordered irreducible tensor products and all 729 associativity triples, together with signed and zero expressions. Catalog verification checks orthogonality, dimensions, center parity and all fusion identities. Tests use explicit conditions that remain active under Python -O.

Adversarial controls cover physical A/V and W/Wp confusion; positive-dimensional and dimension-zero nongenuine characters; modified coefficients, class values, order, metadata and scope; wrong external requests with recomputed hashes; noncanonical rational encodings; altered fixed table weights/markings/fusion data; aliases; booleans/floats; node/depth/degree/coefficient bounds; oversized work hidden behind cancellation; duplicate JSON keys; invalid UTF-8; nonfinite numbers; malformed JSON; input byte limits; CLI error exits; and verifier-only import independence.

The independent review's program, result files and hash-pinned assessment are under review/. It is separately authored and compares against an exact binomial character oracle, rather than calling the producer for expected answers. A receipt's PASS means only its explicitly stated arithmetic and software tests passed against the recorded files.

The source manifest binds distributed files and excludes itself to avoid a self-referential hash. Integrity verification must compare the recorded expected manifest hash supplied with the artifact, not trust a maliciously replaced manifest. Hashes are provenance/integrity aids, never proofs of the mathematical group identification or operational authorization.

No installed Lean executable or Lean theorem is required or claimed. No historical runtime source, research packet, network service or hidden input tree is required to replay this pack.
