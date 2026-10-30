# Proof repair and interface-safe reuse

Repair begins by locating what failed, not by making the conclusion sound more plausible.

## 1. Classify the failure before choosing a repair

Ask whether the problem is:

- A calculation error with an otherwise valid argument.
- A missing hypothesis or omitted case.
- A statement imported outside its domain of validity.
- A change of object hidden by notation.
- An invalid inference from a summary invariant to an actual structure.
- A circular dependency.
- A genuine counterexample to the target statement.

A local defect may be bypassed by a new lemma. A valid counterexample requires changing or abandoning the target statement. These are different decisions. Tao's local/global distinction is a useful diagnostic lens, but a suspected global inconsistency should still be described as suspected until established. [Source](https://terrytao.wordpress.com/advice-on-writing-papers/on-local-and-global-errors-in-mathematical-papers-and-how-to-detect-them/)

For each defect, write a small failure certificate: the disputed implication, its actual hypotheses, and the counterexample or missing obligation. Preserve this certificate after the repair so that the same inference does not re-enter under different notation.

## 2. Do not replace a full map by one projection

Suppose f: V → E is a linear map and q: E → Q is a quotient map. Information about qf does not determine f. For example, f(x,y) = (x,y) has rank two, while projection onto the first coordinate has rank one. The unobserved component matters.

The geometric version can be subtler: a quotient may sit in a nonsplit extension, so a convenient decomposition of invariants does not supply a compatible decomposition of the map. Before asserting a full derivative rank, identify its complete target and control every component or prove an appropriate image statement.

**Local checked example.** A repaired obstruction explicitly stopped using a projected-rank inference through an extension. Instead it constructed a global direct summand on which the full derivative vanished. The successful replacement addressed the missing structure; it did not merely repeat the projected calculation more precisely.

Questions to ask at this interface:

1. What is the full source and full target?
2. Is the displayed map the actual map, an induced quotient, or an unrelated abstract map?
3. Is a splitting proved, and is it compatible with the operation being used?
4. Does “zero” mean zero in the full target or only after projection?
5. Does the rank refer to a generic fiber, every fiber, or a coherent image?

## 3. Distinguish objects from invariants

Equality of rank and degree does not identify bundles. Equality in a Grothendieck group does not identify an extension. An Euler-character identity does not provide an injection, a surjection, or a splitting. Equivariant dimensions can agree while characters differ.

Use invariants for the implications they support. They often give excellent obstructions. They do not create the actual morphism required by a later argument.

Maintain a three-column scratch check when an argument passes between levels:

| Level | What has been established? | What remains to be constructed or proved? |
| --- | --- | --- |
| Numerical | Rank, degree, dimension, parity | Actual object and map |
| Invariant class | Character, Euler class, K-theory class | Extension, image, compatibility |
| Actual geometry | Explicit sequence, kernel, quotient, embedding | Any additional regularity or saturation claim |

## 4. Torsion is data, not a nuisance term

For a sheaf map, its coherent image and its saturation can differ by torsion. Replacing the former by the latter can change degrees, exact sequences, and duality formulas.

At every replacement, write the exact sequence connecting the original image to the proposed replacement. Retain the torsion length and, when relevant, its support, local characters, multiplicities, and twist behavior. Derived duality may introduce an Ext term; ordinary vector-space duality intuition is not a safe substitute.

**Local checked example.** One review insisted that an injective tail map's coherent image remain identified with its source rather than with the saturated target. Another retained positive defects and repeated local torsion factors throughout a finite search. A zero defect was used as an actual isomorphism only after it had been deduced, not as an input that made the search easier.

## 5. Search for the weakest sufficient replacement

Repair need not reproduce the original route. Sometimes the failed route tried to establish more than the conclusion needs.

**Local checked example: a connection instead of horizontality.** Let F be a holomorphic subbundle of a trivial bundle on the complex projective line, and let S be a global direct summand of F with retraction p. If the full second fundamental form of F vanishes on S, then dS lies in F tensored with differential forms. Consequently p composed with d defines a holomorphic connection on S: its Leibniz term is correct because p restricts to the identity on S.

This does not claim that d preserves S. Nevertheless, a holomorphic connection on its determinant forces degree S = 0 on the projective line. Thus a negative-degree summand is impossible under these hypotheses. An additional internal-Hom vanishing, which might have been needed to prove actual horizontality, is unnecessary for this weaker but sufficient contradiction.

The workflow lesson is to distinguish the desired contradiction from an unnecessarily strong intermediate theorem. Do not generalize this example without checking its base, characteristic, regularity, full-map vanishing, and global-retraction hypotheses.

## 6. Reuse a proof only after matching its interface

Choose the exact cut point at which the old proof will be reused. Extract every hypothesis used after that point, including those invoked several paragraphs later.

Audit:

- Objects and ambient category.
- Actual source injections and quotient maps.
- Nonzero components and surjectivity, when needed.
- Rank, degree, character, and torsion data.
- Filtration positions and index conventions.
- Compatibility with a connection, group action, or duality.
- Global hypotheses such as saturation or absence of constant subobjects.

Then provide a dictionary showing that the new situation meets each item. Agreement of formulas at the cut point is not enough if a later step uses an old embedding or a special source decomposition.

**Local checked example.** Two different kernel configurations were shown to produce the same actual scalar-kernel problem. The transfer review separately checked the injection, nonzero rows, preceding quotient, later derivative targets, and positions in the original flag. Only the tail after this interface was reused. No splitting of an intervening evaluation sequence was required.

Formal proof-repair research makes analogous compatibility obligations explicit when transporting proofs across changed representations. Work on quotient-type equivalences is relevant evidence for the importance of these obligations, not a claim that informal geometric arguments can be transported automatically. [Viola, Fan, and Ringer](https://arxiv.org/abs/2310.06959v7)

## Repair is complete only when

- The original defective inference is no longer used, including indirectly.
- The new lemma has its own proof and scope.
- Downstream dependencies have been rechecked.
- Tests include the historical failure as a negative control where executable.
- The public statement says exactly which conclusion was restored and which parts remain open.
