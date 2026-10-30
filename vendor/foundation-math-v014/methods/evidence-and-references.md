# Evidence and references

This guide separates published source material, inspected local examples, and proposed working practices. Citations support the associated idea; they do not certify every recommendation in Foundation Math.

## Public primary sources

1. **Terence Tao, “On ‘local’ and ‘global’ errors in mathematical papers, and how to detect them.”** Distinguishes invalid steps, ambiguity, circularity, and broader inconsistencies. Used in the claim-interface and proof-triage guidance. [Read](https://terrytao.wordpress.com/advice-on-writing-papers/on-local-and-global-errors-in-mathematical-papers-and-how-to-detect-them/)

2. **Terence Tao, “Be sceptical of your own work.”** Recommends counterexample searches and checking whether a method would prove known false statements or fails to use crucial hypotheses. Used in experimental design and adversarial checking. [Read](https://terrytao.wordpress.com/career-advice/be-sceptical-of-your-own-work/)

3. **Cosmo Viola, Max Fan, and Talia Ringer, “Proof Repair across Quotient Type Equivalences,” version 7, 2025.** Studies proof repair across representation changes involving quotient-type equivalences, with setoid-based support in Rocq and related case studies. Used as a formal proof-engineering analogue for explicit transport obligations. It is not evidence that the informal geometric examples here are formally verified. [Read](https://arxiv.org/abs/2310.06959v7)

4. **Kiran Gopinathan, Mayank Keoliya, and Ilya Sergey, “Mostly Automated Proof Repair for Verified Libraries,” PLDI 2023.** Studies invariant reconstruction and proof repair for changed imperative implementations with fixed specifications, including residual obligations. Used to motivate separating automatic reconstruction from obligations not discharged. [Read](https://verse-lab.github.io/sisyphus/pdfs/sisyphus-pldi23.pdf)

5. **Python documentation, command-line option `-O`.** Documents removal of assertions and code conditional on `__debug__`. Supports the optimized-execution warning. [Read](https://docs.python.org/3/using/cmdline.html#cmdoption-O)

These sources were consulted directly. The guide uses original summaries and original workflow recommendations rather than reproducing source text.

## Local checked examples: unpublished, limited evidence

The following examples came from inspected mathematical artifacts and review records. Their full research packets are not included here. They should not be cited as published theorems or as a public reproduction package.

### A. Full-map connection obstruction

The written argument replaced an invalid projected-rank route with a global direct-summand construction killed by the full derivative. The review distinguished an induced connection from the stronger assertion of horizontality. It also preserved the distinction between an actual coherent image and its saturation.

For preparation of this guide, the author verifier, independent arithmetic checker, and an 11-mutation control suite were replayed in isolated copies, normally and with optimized Python, from an unrelated working directory. All runs passed and the paired mathematical JSON results agreed. This is a fresh replay of their arithmetic and controls, not a formal verification of the geometric proof.

### B. Intrinsic-tail proof transfer

The reviewed transfer identified a common actual kernel problem reached by two different configurations. Its review audited the precise reuse cut point, actual injections, full quotients, nonzero rows, and later filtration positions.

The author checker and the independent transfer checker were replayed in both Python modes with agreeing mathematical outputs. This supports the reproducibility example. It does not independently reconstruct all ancestor geometric premises or establish a global theorem.

### C. Torsion-safe necessary reduction

The inspected reduction retained positive defects, local torsion characters, repeated factors, and multiplicity-sensitive constraints. Its final inventory had 46 descriptions with a recorded first kernel and 34 after forgetting it; these remained necessary candidates, not realized objects.

The production verifier and independent reconstruction were replayed normally and optimized. Both independent runs reported the same final 46 descriptions and 4,849 explicit checks; their saved mathematical results agreed with each other and the frozen result. The 15-case mutation suite was also rerun, rejecting all 30 normal/optimized variants. The review's account of early mutation-test blind spots was read alongside the tests; it motivated the intermediate-control recommendation.

### D. Exhaustion of Euler and cohomology filters

Inspected proof texts derived a second-order Euler recurrence and justified finite all-twist cohomology windows using vanishing outside the window. They also distinguished common witnesses from witnesses chosen separately for each twist. These texts informed the stopping and witness-correlation recommendations; their full computational packets were not rerun for this guide.

## What is a recommendation rather than a result?

The claim-record format, role split, experiment card, publication whitelist, status-update procedure, and suggested acceptance checks are proposed practices. They are not theorems, controlled productivity results, or promises of correctness. Adapt their overhead to the problem while preserving the core distinctions between a claim, its evidence, and its unresolved obligations.
