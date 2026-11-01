# Collaboration and release discipline

Parallel mathematical work is valuable when it creates different evidence or attacks different obstacles. It is not valuable merely because many workers agree.

## 1. Divide by mathematical responsibility

Useful roles include:

- **Claim owner:** maintains the exact statement, current frontier, and unresolved obligations.
- **Constructor:** develops a proof, lemma, or candidate example.
- **Adversarial reviewer:** attacks the fragile implication, omitted cases, and strongest claimed conclusion.
- **Independent implementer:** rebuilds the finite calculation by a materially different route.
- **Integrator:** checks interfaces, dependency changes, and the consistency of the overall statement.

One person can hold several roles in a small project. The role labels describe responsibilities, not a guarantee of independence. Separate authorship from review where practical, and disclose shared code, formulas, source assumptions, and tools.

Assign work by claim or interface rather than by arbitrary page ranges. “Check that the coherent quotient used by the next derivative is really this bundle” is a stronger assignment than “review section 4.”

## 2. Give each task an acceptance contract

Every handoff needs:

1. A concrete question and intended output.
2. The exact frozen inputs.
3. Constraints on what may be assumed or changed.
4. A list of the most dangerous known failure modes.
5. A success condition and an honest inconclusive outcome.
6. A named owner for integration and status changes.

Do not turn “find a proof” into a demand that every task return success. A counterexample, failed interface, or proof that a filter is exhausted can be the most useful outcome.

Ask for the useful finding before the activity log. A good report says: “The transfer is valid after this cut point, provided H2 is retained. I checked X and Y; Z remains imported.” It does not bury the result under a long chronological transcript.

## 3. Freeze before reviewing

A review applies to particular content. Bind it to the proof, relevant code, inputs, and mathematical statement, not just to a branch name.

When the author edits the packet during review:

- Identify the changed content.
- Determine which review conclusions depend on it.
- Reopen the affected obligations.
- Produce a new receipt when complete.

An unrelated typo need not force every calculation to rerun. A changed target, sign, hypothesis, or case split may. Record this decision rather than assuming that any previous “pass” follows the moving draft.

**Local checked example.** Review records bound conditional verdicts to proof hashes and distinguished newly audited deductions from immutable ancestor premises. Later narrow consequences were kept separate from the frozen packet rather than silently enlarging its approved scope.

## 4. Review at more than one level

Use complementary passes:

- **Statement audit:** Is the target meaningful, correctly quantified, and consistent with known examples?
- **Structural audit:** Are the actual maps, exact sequences, quotient identifications, and dependencies valid?
- **Arithmetic audit:** Are signs, shifts, degrees, characters, and finite domains correct?
- **Execution audit:** Can the result be rebuilt from the declared inputs?
- **Scope audit:** Does the summary claim no more than the argument proves?

Review disagreement is an obligation to resolve, not a vote to outnumber. Reproduce the smallest disputed step and ask which definition, hypothesis, or calculation explains the divergence.

## 5. Keep one authoritative claim ledger

Parallel branches should not independently promote the global theorem. The integrator reconciles accepted local results into the current dependency graph and frontier.

In particular:

- Do not subtract exclusions from an inventory built under different assumptions.
- Do not mix counts before and after forgetting different pieces of data.
- Do not silently adopt a new result from an exploratory branch.
- Do not resurrect a withdrawn argument because an older draft still contains it.
- Do not describe review of a conditional result as independent proof of all its ancestors.

A contribution can be accepted while the overall problem remains open. This is a normal outcome, not a defect to hide.

## 6. Release a packet, not a workspace dump

Use an explicit publication whitelist. Include only material needed to understand or reproduce the claim:

- Statement and proof.
- Dependency and input manifest.
- Checker and required data.
- Result and verification instructions.
- Review scope and known limitations.
- Appropriate source attribution and licensing information.

Exclude temporary experiments, stale outputs, personal metadata, credentials, private conversations, and unrelated material. Search and inspect the release candidate before publication. A shared folder is not itself permission to publish all its contents.

Do a clean reconstruction from the release candidate. A result that depends on omitted files is not portable, even if it works in the author's workspace.

## 7. Preserve corrections without preserving confusion

When a released argument fails:

1. Mark the affected claim as withdrawn or under review promptly.
2. State the precise defect and affected versions.
3. Identify unaffected results and downstream claims needing reevaluation.
4. Release the correction as a new identifiable version.
5. Keep a concise record of why the old inference was invalid.

Do not erase the old state in a way that makes earlier citations misleading. Do not let the existence of a correction imply that the original theorem has been restored unless that is what the new proof establishes.
