# How POODO works

POODO is a set of instructions for an agent. Its purpose is to keep a decision tied to evidence and a testable outcome as the work progresses.

| Phase | Question | Useful output |
| --- | --- | --- |
| Pontificate | What work and outcome does the user mean? | Objective, scope, authority, assumptions |
| Observe | What is actually known? | Evidence records and web research |
| Orient | What explanations and paths survive scrutiny? | A mapped problem space, 20 distinct paths, credible rivals |
| Decide | What should happen under these constraints? | Commitment, tradeoffs, reversal conditions |
| Orchestrate | How will authorized action produce and verify the outcome? | Work plan, prospective prediction, observations |

Read the exact requirements in [SKILL.md](../SKILL.md); this introduction does not replace them.

## Three distinctions that matter

**A report is not an observation.** A prior summary can tell an agent where to look. It cannot independently prove the underlying claim.

**A structural check is not an outcome test.** A matching hash says something about artifact identity. It says nothing by itself about whether the user can finish a task.

**A plausible cause is not a demonstrated cause.** Keep a credible rival explanation and identify an observation that would distinguish them.

## Before action

Record the predicted effect, criterion, oracle version, exact artifact and environment, failure meaning, monitoring, rollback, and stop condition. Changing the criterion after observing the result creates a new prospective test; it does not repair the old outcome.

When an observation contradicts a load-bearing prediction, narrow the claim before explaining the cause. A concern about the test is not proof that the test was invalid.

## Across sessions

A continuation capsule preserves objective, authority, evidence locators, artifact identity, contradictions, and the next checkpoint. Re-read the required evidence when resuming. See [continuity and ledger](../references/continuity-and-ledger.md) for the schema.

The checker validates a structural subset of one capsule. It cannot inspect the world behind evidence links or compare sibling capsule branches.

## Cost and fit

Mandatory research and divergent exploration make the full loop inappropriate for simple questions. Stop at a precise evidence boundary if required research is unavailable. For complex work, the working records can be detailed while the user-facing answer stays concise.
