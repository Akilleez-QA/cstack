# Claim contracts and dependency control

The smallest useful unit of progress is a claim whose meaning and evidence can be inspected independently of the surrounding enthusiasm.

## 1. Give each claim a contract

Before an expensive proof attempt, record:

- **Statement:** objects, quantifiers, ambient category, field or characteristic, and conclusion.
- **Scope:** universal, generic, existential, instance-specific, or conditional.
- **Hypotheses:** mathematical premises and the exact source for each imported premise.
- **Output:** the mathematical fact this work is meant to establish.
- **Non-claims:** nearby stronger statements that the output does not establish.
- **Acceptance test:** the proof obligations and evidence required before promotion.

For an enumeration, specify the domain and the interpretation of the surviving set. For a contradiction, identify the hypothesis being contradicted. For a repaired proof, say whether the original statement is unchanged or has been weakened.

“Show the obstruction” is not a contract. “Under assumptions H1–H4, show that configuration C cannot occur; do not claim exclusion of any other configuration” is one.

## 2. Track logical status and evidence separately

A single label such as “verified” hides too much. Use at least two axes.

**Logical status**

- Open: no accepted proof or disproof of the specified statement.
- Proposed: an argument has been supplied but remains under examination.
- Conditional result: a deduction is established relative to explicitly retained premises.
- Established within the stated scope: the required proof obligations have been met under the project's review standard.
- Refuted: a valid counterexample contradicts the stated claim.
- Withdrawn or superseded: the old statement or argument is no longer endorsed.

**Evidence record**

- Informal derivation or heuristic.
- Numerical experiment.
- Exact instance computation.
- Exhaustive finite computation with a proved domain bound.
- Author replay.
- Independent reconstruction.
- Human or agent mathematical review, with scope specified.
- Formal proof checked in a named system, with statement and assumptions audited.

These are not interchangeable ranks on one confidence ladder. An exact instance computation can decisively refute a universal claim while many successful numerical experiments cannot prove it. A formal theorem can establish a different statement from the one intended if its definitions were mistranslated.

## 3. Keep a dependency graph, not just a bibliography

For each imported result, record:

1. The exact version or immutable reference.
2. The statement actually needed, including all hypotheses.
3. Where each hypothesis is verified in the current argument.
4. Whether the source was checked, merely assumed, or reconstructed.
5. The downstream claims that depend on it.

Attach dependencies to individual claims rather than treating the entire project as one undifferentiated proof. A rejected lemma should invalidate precisely the deductions that use it. Independent partial results should remain usable.

If a proof uses an equivalence, store both directions. If it uses only a necessary condition, do not silently reverse the arrow. Cycles require an explicit valid device such as induction or a fixed-point theorem, not two claims citing each other.

Tao's discussion of local and global errors emphasizes that ambiguous intermediate statements can break a proof even when the individual-looking implications appear reasonable. A dependency interface must fix the meaning of the intermediate object, not only reuse its name. [Source](https://terrytao.wordpress.com/advice-on-writing-papers/on-local-and-global-errors-in-mathematical-papers-and-how-to-detect-them/)

## 4. Separate reduction, exclusion, and realization

Let A be the actual objects of interest and let D be a finite collection of abstract descriptions. Suppose a proved map sends each object in A into D, and necessary tests leave S ⊆ D.

- Every actual object has a description in S.
- If S is empty, this can prove nonexistence, provided the domain and every test are sound.
- If S is nonempty, no element of S is thereby realized by an actual object.
- Excluding one member of S is progress, but does not prove S empty.
- If several descriptions encode one object, counts require an explicit equivalence relation.

**Local checked example.** An exact endpoint reduction retained 46 descriptions when a first kernel was recorded, and 34 after that datum was forgotten. The distinction was stated explicitly; neither count was presented as a count of realizable geometric objects. The transferable rule is to name what is counted and what information has been forgotten.

## 5. Make status updates transactional

A status change should cite the exact new evidence and list the claims affected. If a revision changes a hypothesis, a map, or a case split, reopen the affected review rather than treating an earlier approval as approval of the new version.

Use short, precise updates:

- “The rank-three branch of configuration C is excluded under H. The rank-two branch remains open.”
- “All bounded cases pass the necessary tests; no realization result follows.”
- “The checker reproduces the finite arithmetic. The geometric factorization remains a written proof obligation.”
- “The argument at step L fails. The theorem itself is not disproved.”

Avoid status by proxy. A merged pull request, a large check count, or a positive review of one module does not establish an unrelated global theorem.

## Minimal claim record

```text
Claim ID:
Exact statement and quantifiers:
Current logical status:
Assumptions and immutable dependencies:
New deduction:
Evidence and verification boundary:
Known objections or unresolved obligations:
Explicit non-claims:
Owner and reviewed version:
Next action that could change the status:
```
