# Methods for doing difficult mathematics

Foundation Math treats mathematical progress as a collection of precise, inspectable changes in what is known. A promising argument, an exact computation, a reviewed conditional lemma, and a complete theorem are useful achievements, but they are different achievements.

The purpose of this guide is to make those differences operational. It is not a claim that a workflow can manufacture a breakthrough or eliminate the need for mathematical judgment.

## The working loop

1. **State the claim.** Fix its quantifiers, objects, hypotheses, and intended strength. Write what would count as success and what would not.
2. **Expose the dependencies.** Identify the actual maps and structures used, not just their numerical invariants. Separate imported premises from newly established deductions.
3. **Choose a discriminating move.** Ask what proof, counterexample, or computation would change the next decision. Prefer a small decisive test to a large undirected search.
4. **Construct and attack.** Develop the argument while testing its fragile interfaces, omitted cases, and crucial hypotheses.
5. **Freeze and reproduce.** Bind the statement, proof, inputs, code, and result to an identifiable version. Recompute rather than trusting saved survivor lists.
6. **Review the exact scope.** Audit the geometry or analysis separately from the arithmetic. Reviewers should report what they checked and what they inherited.
7. **Update only the claims earned.** An excluded subcase does not close a whole profile. A necessary survivor is not an example. A replay is not a new proof.
8. **Stop, transfer, or pivot deliberately.** Preserve a useful partial result, but do not keep spending resources on a filter proved incapable of giving new information.

## Read by problem

- “What have we actually proved?” → [Claim contracts and dependency control](claim-contracts.md)
- “Can this argument be repaired or reused?” → [Proof repair and interface-safe reuse](proof-repair-and-reuse.md)
- “What does this computation establish?” → [Reproducible mathematical computation](reproducible-computation.md)
- “What should we try next, and when should we stop?” → [Experiments, stopping, and pivots](experiments-and-pivots.md)
- “How can several people or agents work without losing accountability?” → [Collaboration and release discipline](collaboration-and-release.md)
- “What are the recurring traps?” → [Failure-mode checklist](failure-modes.md)
- “Where do these recommendations come from?” → [Evidence and references](evidence-and-references.md)

## A few distinctions that must survive every summary

- Abstract invariants are not actual maps or compatible splittings.
- A projected map is not the full map.
- A coherent image is not automatically its saturation.
- Necessary conditions are not sufficient conditions.
- Matching counts are not matching sets.
- Running the author's code is not independent reconstruction.
- Passing a checker is not verification of unencoded mathematics.
- An objection to a proof is not automatically a counterexample to its conclusion.
- Stopping an experiment is not proving impossibility.

## Evidence boundary

The methods are original procedural recommendations synthesized from public primary sources and locally inspected mathematical proof packets. Examples explicitly marked **local checked example** refer to unpublished material with executable arithmetic and review records. They illustrate a practice, not a publication claim or an independently formalized theorem. The underlying research collection is not copied into Foundation Math. See the [evidence register](evidence-and-references.md) for the limits of each kind of support.
