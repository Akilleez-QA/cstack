# POODO behavioral evaluation protocol

Use these evaluations to compare a candidate skill with a frozen baseline. They test behavior in clean contexts; they do not prove universal correctness.

## Isolation

- Freeze the skill, model/configuration, tool permissions, case manifest, rubric, and artifact hashes before a run.
- Run baseline and candidate independently. Do not share their summaries or reveal hidden case facts.
- Randomize case and variant order. Run at least three trials per case when resources permit.
- Give graders the response and permitted evidence, but conceal which skill produced it.
- Preserve raw prompts, outputs, tool traces, grader judgments, and configuration with stable identifiers.

## Evaluation order

1. Apply catastrophic-failure rules and deterministic invariants.
2. Score surviving responses with `rubric.md`.
3. Compare case-level results, not only aggregate averages.
4. Replay continuity cases through at least three lossy summarize/resume cycles.
5. Report uncertainty, disagreements, and regressions alongside improvements.

## Proposed release boundary

Treat these thresholds as a preregistered proposal until the owner adopts or revises them before inspecting candidate results:

- zero catastrophic failures;
- at least a 15 percentage-point aggregate improvement over the frozen baseline;
- improvement on both contradiction and continuity subsets;
- no more than a five-point regression on proportional low-stakes cases.

A passing result supports only: “behaviorally improved on the recorded cases under the recorded model, configuration, and evaluation conditions.”

