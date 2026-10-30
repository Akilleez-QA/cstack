# Independent review assessment

## Verdict

PASS for the bounded formal split-bundle arithmetic domain described in the reviewed source. No arithmetic, input-acceptance, certificate-binding, or claim-boundary defect remains in the inspected source. This is conditional algorithmic review, not a Lean proof, a proof of the marked catalog-to-group identification, a geometric realization, or Foundation Math runtime acceptance.

The reviewed author files are bound by REVIEWED-SOURCE.json, SHA256 3d6a775d8e92777a0614921adf23d26516d34d8312607d58040a126030b1962b. The test driver independently checks that pin and all 22 listed source-file hashes before testing. SOURCE-MANIFEST.json and the independent source audit confirm that the seven vendored character-engine files are byte-identical to both the frozen v0.9 and accepted character lab. The reviewer changed no author, frozen, or research files.

## Executed evidence

- 22,093 independent checks passed under ordinary Python and under Python -O. The two result records are identical except for the explicit python_optimized flag.
- A separately spelled-out exact Q(sqrt(5)) class oracle uses closed binomial symmetric-character polynomials, not the author recurrence or fusion table. Its character and all 81 fusion-product values match the pinned catalog.
- For every physical irreducible, all shifted line degrees from −128 through 128 were checked against that oracle. This covers every degree reachable by the bounded API, including −2, −1, and 0.
- The suite checks direct sums, Serre duality, rank/degree and Riemann–Roch, empty and zero-multiplicity bundles, duplicate blocks, maximal block/twist/multiplicity bounds, all 81 ordered irreducible Hom pairs at six degree controls, and the full ordinary Hom character as well as its equivariant invariant dimension.
- The required H⁰=1+V, H¹=1, Euler=V example passes. The Euler collision is checked at every admitted twist and justified for all integers in MATHEMATICAL-REVIEW.md. Hom_G(W(−3),W(−3))=1 is explicitly kept separate from any map-rank conclusion.
- 310 negative-control checks reject malformed data, non-exact types and primitive subclasses, cycles, bounds violations, duplicate JSON keys, bad encodings, certificate leaf changes, extra conclusions, and different externally supplied requests even when their mathematical answers coincide. Preparse nesting is tested before the backend, including quoted/escaped structural characters.
- Eight source faults are detected in both Python modes, with two passing unmodified baselines: wrong H¹ shift, unsigned Euler, physical W/Wp substitution, trusting the embedded request, wrong checker Serre shift, reversed Hom orientation, skipped certificate equality, and false Lean promotion. These 18 executions use only temporary review-owned copies.

## Independent packaging gate

standalone_replay.py verifies the eventual release manifest, copies only its listed files plus the manifest into a new directory, runs author/reviewer/fault suites normally and with -O under isolated Python, verifies source hashes before and after, checks fixed ZIP metadata and exact membership, checks byte-identical rebuilds, and requires source-drift rejection. Its final report is intentionally external to the ZIP whose hash it records. Source-level PASS above does not substitute for running that final release-specific gate.

## Boundaries and qualifications

The catalog's physical marking is a stated mathematical assumption. Orthogonality and hashes do not prove it. A supplied formal splitting is not inferred from another object. H⁰ and H¹ are genuine; their Euler difference may be virtual, and even a genuine Euler character need not be H⁰. Equivariant Euler characters at every twist do not determine the split object. Hom-space dimension does not determine a chosen map's rank, kernel, image, degeneracy, or embedding status. No actual source coefficients, points, parameters, jets, matrices, instance ranks, source-domain scan, model restart, network install, repository, or publication is involved.

A temporary documentation concern about preparse nesting was resolved by inspecting the final split-domain guard and dedicated tests; no frozen dependency change was required. The final documentation states the claim boundaries and the distinction between original and twisted degrees correctly.
