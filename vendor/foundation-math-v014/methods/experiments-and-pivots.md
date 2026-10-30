# Experiments, stopping, and pivots

The right next step is the one that can change a mathematical decision, not necessarily the one that produces the most output.

## 1. Write the decision before the experiment

An experiment card should answer:

```text
Question:
Competing possibilities:
Observable result that distinguishes them:
Why that result bears on the mathematical claim:
Smallest informative case:
Estimated time and memory:
Checkpoint or partial-result plan:
Acceptance, rejection, and inconclusive outcomes:
Stopping condition:
Next action for each outcome:
```

Distinguish a search for a counterexample from a finite verification intended to support a theorem. Distinguish an actual instance computation from universal representation or degree arithmetic. Neither is inherently better; the claim determines which is relevant.

Tao recommends attempting counterexamples and testing whether a purported argument accidentally proves a known false stronger claim. These are especially useful before an expensive implementation locks in a mistaken premise. [Source](https://terrytao.wordpress.com/career-advice/be-sceptical-of-your-own-work/)

## 2. Recognize when a filter is mathematically exhausted

Suppose sequences aₜ and bₜ in an abelian group with a fixed endomorphism T both satisfy

    xₜ₊₂ = T(xₜ₊₁) − xₜ.

If aₜ = bₜ at two adjacent indices, the recurrence proves equality forward. Rewriting it as xₜ = T(xₜ₊₁) − xₜ₊₂ proves equality backward. Thus those two checks establish equality at every index.

**Local checked example.** Equivariant Euler characters in a projective-line calculation satisfied this second-order recurrence, with tensoring by a fixed representation as T. Once an identity matched at adjacent twists, checking more twists could catch implementation errors but could not eliminate additional mathematically valid candidates from the same Euler test.

That is a rigorous stopping rule for this filter, not merely “we tried a lot.” Pivot to information the invariant forgets: actual maps, compatibility across twists, local structure, extension classes, multiplication maps, or stronger cohomological constraints. Which option helps depends on the problem.

Do not overgeneralize the recurrence argument. Separate H⁰ and H¹ dimensions or characters need not satisfy the same recurrence as their alternating difference. A new positivity or exactness condition can add information even when Euler equality is exhausted.

## 3. Prove finite windows when possible

For split bundles on the projective line, sufficiently negative twists have no H⁰ and sufficiently positive twists have no H¹. If a desired all-twist inequality becomes automatic in those two regions, the remaining finite interval can be derived from the extreme splitting degrees.

**Local checked example.** An all-twist cohomology filter used this vanishing argument to justify its finite interval. It retained a common fixed kernel witness across all twists. Every surviving quotient still passed, even though some witness edges disappeared. That was a precise negative result about the filter's power, not a failure to run a large enough sample.

A sampled interval is also useful for exploration, but label it sampled until the outside region is controlled.

## 4. Distinguish mathematical stopping from operational pausing

**Stop the proposed claim or route when:**

- A verified counterexample refutes the claim as stated.
- A required implication is false and every current use depends on it.
- A theorem proves the proposed invariant carries no new distinguishing information.
- The experiment's stated question has been answered.

**Pause the computation when:**

- Its agreed resource envelope is exceeded.
- Needed data or authority is missing.
- A run is invalidated by a changed input or discovered bug.
- The expected information no longer justifies the cost.

An operational pause is not a mathematical impossibility result. Record the completed range, exact obstruction, and what would make resumption worthwhile. A timeout is “inconclusive,” not “no solution.”

## 5. Budget the experiment, not just the machine

Before scaling up:

1. Estimate the combinatorial domain size, including multiplicities and symmetry orbits.
2. Run a small representative case and measure the dominant operation.
3. Compare a direct search with structural bounds, quotienting by proved symmetries, or incremental constraints.
4. Order cheap sound filters before expensive checks where dependencies permit.
5. Cache immutable subproblems, never conclusions whose assumptions have changed.
6. Bound parallelism. Multiple workers repeating the same expensive calculation can consume the budget without adding independence.
7. Save restartable checkpoints and provenance if interruption would otherwise destroy useful work.

Reducing scope must not silently change the claim. A resource-limited subset can be an exploratory experiment; it cannot be relabeled an exhaustive proof.

## 6. A good pivot leaves behind a reusable result

When an approach stalls, preserve:

- The exact strongest statement it did prove.
- A small counterexample or obstruction explaining its limit.
- The input assumptions on which it depended.
- The new information a successor method would need.
- The next smallest discriminating question.

For example: “These necessary character conditions leave every candidate. The next question is whether their abstract exact sequences can be realized by one compatible sheaf map.” This is more actionable than “the computation found nothing.”

Stop rules protect focus; they should not become an excuse to abandon a task at the first recoverable error. Diagnose, repair, and resume within scope when the failure is operational rather than mathematical.
