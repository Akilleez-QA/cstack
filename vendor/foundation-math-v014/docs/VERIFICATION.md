# Verification contract

## Separate evidence dimensions

Do not squeeze all evidence into one numerical confidence score. Track at least:

1. Statement and domain precision.
2. Dependency and assumption completeness.
3. Written mathematical argument.
4. Computational coverage and reproducibility.
5. Independent adversarial review.
6. Formal proof checking and its trust boundary.
7. Correspondence between formal and informal statements.

These dimensions can disagree. A formally checked lemma may not be the lemma the problem needs. A correct finite computation may omit a boundary stratum. A reviewed proof can rely on an unresolved imported hypothesis.

## Acceptance rules

- Pin evidence to exact artifact bytes and source revisions.
- Record field characteristic, representation conventions, signs, shifts, normalizations and quantifiers where they affect the claim.
- Preserve nonreduced, degenerate, boundary and torsion cases unless a proved reduction removes them.
- Require complete finite-domain construction before calling an enumeration exhaustive.
- Check both successful and intentionally corrupted examples. Mutation tests should target intermediate semantic gates, not merely final output.
- Treat unavailable, failed, timed out, unsupported and not run as distinct outcomes.
- Keep a minimal trusted checker where feasible. A large producer should not be its own only validator.
- Preserve retractions and revisions. A disproved claim stays traceable, and its dependents need renewed review.

## Lean-specific boundary

Lean can check a proof against a formal proposition in a particular environment. It does not automatically validate translation from a manuscript or guarantee that an imported axiom is justified for the intended application.

A deployable formal-check receipt should retain toolchain and dependency pins, source digest, target declarations, process result, diagnostics and an axiom audit. Placeholder scanning is a useful early rejection, not a substitute for kernel checking or a complete axiom audit. Comments, generated code, macros and imported declarations make textual checks incomplete.

Do not execute arbitrary submitted Lean projects in the coordinator's trusted process. Use an isolated worker with explicit resource and access limits. The initial adapter documents what it enforces and what still needs a production isolation layer.

## Progress without invented percentages

Maintain a stable universe when counting cases. When a classification changes, record the new universe and the map from the old one. Distinguish a necessary surviving case from a constructed example. Display independent obligations separately instead of pretending that all branches have equal difficulty.

A new reduction, counterexample, certificate, reusable verified mechanism or corrected obstruction can be progress. Re-reading an unchanged result is supporting verification, not a new mathematical advance.

## Executable acceptance contract

v0.3 distinguishes successful operation, accepted structured result, and requested
evidence. See [DOMAIN-RUNTIME.md](DOMAIN-RUNTIME.md). A false identity is successful
computation but rejected mathematical acceptance. A true identity can satisfy an
exact-computation requirement, never a formal-proof requirement in this runtime.
The report explicitly leaves informal correspondence and formal proof unverified.
