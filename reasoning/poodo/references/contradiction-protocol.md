# Contradiction protocol

Use when a valid observation conflicts with a load-bearing claim, prediction, decision premise, outcome assertion, or authority record.

## Interrupt and retract

Stop dependent action when safe. Preserve the observation and test context. Lead with the correction: retract or narrow the affected outcome claim before investigating cause. Evidence about a user-only observable surface is direct evidence of that surface, though it does not by itself establish cause.

## Classify without protecting the theory

- `failed`: the prediction missed its boundary in an apparently valid test.
- `failed_with_test_concern`: it failed, but an unproven environment, sensor, artifact, or oracle concern exists.
- `invalid`: outcome-independent evidence shows the test could not adjudicate the prediction.
- `inconclusive`: the observation or boundary cannot distinguish pass from fail.

Do not use `invalid` merely because the result disappointed. Ask whether the alleged defect would also have invalidated a favorable result. Require a positive control, independent observation, or separately established defect when feasible.

## Propagate and repair

1. Add an observation with provenance, evidence family, scope, and limitations.
2. Add a contradiction targeting the exact record.
3. Mark the original prediction failed, failed-with-concern, invalid, or inconclusive; never reset it.
4. Trace and reopen every dependent orientation, decision, action, outcome, validator, and lesson.
5. Restore the strongest credible rival.
6. Choose the smallest discriminating observation.
7. Version any justified oracle change independently and create a new prediction for a rerun.
8. Retain the contradiction tombstone until all active dependencies are repaired.

## Anti-rationalization check

- Did the evidence reach the intended success surface or only a proxy?
- Would this test-validity objection have been raised after a favorable result?
- Are implementation and validator derived from the same assumption?
- Does the explanation predict a new observation, or only make failure sound compatible?
- What prior success language must be explicitly retracted?

Example: several structural checks pass, but a valid user-visible runtime test shows no intended improvement. Retract the improvement claim immediately. Preserve the structural passes as conformance evidence only. Record the runtime failure and investigate artifact drift, incomplete implementation, test-path problems, and causal-model error as live alternatives.
