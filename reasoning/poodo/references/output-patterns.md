# Output patterns

Choose the smallest form that preserves the decision and its evidence boundary. Do not print stage headings merely to demonstrate compliance.

## Recommendation

Lead with the recommendation, then decisive evidence, strongest rival, uncertainty, tradeoff, next action, and verification.

## Contradiction

Lead with the retraction or narrowed claim. State the failed prediction, observed result, remaining known state, test concern if any, and next discriminator. Explanation follows correction.

## Consequential implementation handoff

Always state `delivery_state`, `outcome_state`, `highest_justified_claim`, `required_runtime_observation`, and `who_controls_next_test`. Avoid unqualified success language unless intended-use acceptance passed.

## Experiment charter

State hypothesis, whether prediction is prospective, intervention, baseline, artifact/environment, sensor, versioned oracle, acceptance boundary, failure meaning, rollback, and response to each result.

## Continuation boundary

Emit the canonical capsule from [continuity-and-ledger.md](continuity-and-ledger.md) on failure, handoff, pause, recovery, material transition, or compaction boundary. Natural prose is presentation; the capsule is canonical state metadata. Neither is outcome evidence.
