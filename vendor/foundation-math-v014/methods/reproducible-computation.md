# Reproducible mathematical computation

A computational result has two obligations: the program must perform the stated calculation, and the calculation must have the stated mathematical consequence. Neither obligation replaces the other.

## 1. Prove the search domain before searching

An exhaustive search is exhaustive only relative to a specified finite domain. Explain why every object relevant to the claim maps into that domain.

For example, if integer degrees e₁, …, eᵣ satisfy eᵢ ≤ c and sum to d, then each eᵢ ≥ d − (r − 1)c. This elementary bound makes the degree domain finite. Additional parity, symmetry, or representation constraints may prune it only when their necessity has been proved.

Where possible, construct the same domain in two different ways. One builder might enumerate irreducible blocks; another might enumerate ordinary degree partitions and then decorate them with representations. Compare the complete normalized sets, not only their cardinalities.

Never define the exhaustive domain by loading a list produced by an exploratory search whose completeness has not been proved. Exploration may discover the right bound; the certificate should rebuild the domain from that bound.

## 2. Give every filter a proof obligation

For each filter, record:

- Input domain and output interpretation.
- The theorem that makes rejection sound.
- Any newly required hypotheses.
- Its behavior on multiplicities, boundary cases, degeneracies, and zero values.
- Whether it is necessary, sufficient, or both.

Some conditions become valid only after previous filters establish a missing premise. Record this ordering. A later proved zero torsion defect cannot be used to justify an earlier unramified enumeration.

Preserve witness correlation. If one fixed witness must satisfy all tests, check that witness throughout. “For each test there exists a witness” does not imply “there exists a witness satisfying every test.” Likewise, do not replace an existing relation of compatible pairs by the Cartesian product of its projections.

## 3. Use arithmetic appropriate to the conclusion

Exact integer, rational, algebraic-number, or symbolic arithmetic avoids numerical ambiguity when the objects permit it. A floating-point rank or near-zero residual needs an error analysis or an exact certificate before being used as a proof.

Track enough structure. An ordinary dimension can erase a nonzero virtual character. A total torsion length can erase the local characters that matter to an equivariant identity. A rank can erase the position of the image.

**Local checked example.** A flag obstruction had an equivariant Euler discrepancy of ordinary dimension zero. Dimension checks passed; the full character did not. The example supports a general rule: keep the invariant in which the theorem is stated rather than projecting prematurely to a weaker one.

## 4. Separate replay from independent reconstruction

Use distinct labels:

- **Replay:** execute the supplied implementation against frozen inputs.
- **Independent implementation:** reconstruct the calculation without importing the production algorithm or its survivor lists.
- **Independent mathematical review:** inspect the argument relating the computation to the theorem.

Two implementations that share the same mistaken formula can agree. Seek diversity at the fragile point: a character recurrence versus exact conjugacy-class inner products, block enumeration versus partitions, or a duality identity derived from a locally free resolution rather than copied from the author.

**Local checked example.** A reviewer rebuilt an exact representation ring using conjugacy classes rather than the author's recurrence, generated the domain from ordinary partitions, and compared full intermediate sets. This is stronger evidence than rerunning the original script, but it still leaves the imported geometric premises explicit.

## 5. Test that the checker can fail for the right reasons

A passing run establishes little about a test suite that would also accept the wrong mathematics.

Add executable negative controls that deliberately:

- Omit an allowed case or repeated factor.
- Change a sign, degree, twist, or parity.
- Conflate same-dimensional but distinct representations.
- Replace a full character by its dimension.
- Remove a required dependency or corrupt its bytes.
- Erase a hypothesis required by the claimed implication.

Mutation tests must reach the intended semantic check. Syntax errors, missing files, and timeouts are not successful detection of a mathematical error. Pair them with positive controls: a known valid example should remain accepted, and an intentionally unexcluded branch should remain unexcluded.

**Local checked example.** In one review, three incorrect variants left the final output unchanged because other filters later eliminated the affected cases. Final-output comparison alone therefore missed the mutations. Domain-cardinality, dualized-resolution, and source-character controls were added. The lesson is to instrument the invariant where the bug occurs, not only the final survivor count.

## 6. Make execution portable and fail-closed

- Resolve inputs relative to the program, not the caller's working directory.
- Use explicit failing checks for proof-critical conditions.
- Test ordinary and optimized execution if Python is used. Python's `-O` removes `assert` statements, so a certificate whose correctness checks disappear in that mode is unsafe to describe as mode-independent. [Python documentation](https://docs.python.org/3/using/cmdline.html#cmdoption-O)
- Keep deterministic mathematical output separate from timings and machine-specific diagnostics.
- Return a nonzero exit status on failure.
- Record runtime and dependency versions, exact invocation, exit code, and input identities.
- Reproduce from a clean copy or checkout, without stale caches or exploratory outputs supplying hidden state.

Hashes identify bytes; they do not establish mathematical truth or authorship. Store immutable source locations and content digests together, and explain what was actually checked.

## 7. Publish the verification boundary

A compact certificate should include:

```text
CLAIM: What the computation establishes, and under which premises.
DOMAIN: Why every relevant case is represented.
INPUTS: Immutable source identities and content digests.
METHOD: Exact arithmetic, generation, normalization, and rejection rules.
RESULT: Complete survivors or a reproducible certificate of emptiness.
CONTROLS: Positive examples and executed semantic mutations.
REPLAY: Environment, command, exit status, and result comparison.
LIMITS: Mathematics not encoded, untested cases, and explicit non-claims.
```

A written proof, a small trusted checker, and a richer exploratory program can coexist. Keep their responsibilities distinct. Formal proof-repair work such as Sisyphus similarly distinguishes automated reconstruction from residual obligations requiring further proof. Its setting is verified software, not automatic validation of informal mathematical research. [Gopinathan, Keoliya, and Sergey](https://verse-lab.github.io/sisyphus/pdfs/sisyphus-pldi23.pdf)
