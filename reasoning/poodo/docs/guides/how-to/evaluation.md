# Evaluation and verification

## What can be run today

The two Python validators and the regression suite run locally without a model. The base behavioral manifest describes 14 scenarios for a future or manually operated evaluation. There is no automated agent runner in this repository, and no behavioral results are claimed.

```sh
python scripts/validate_skill.py
python -m unittest discover -s evals -p 'test_*.py' -v
python scripts/check_capsule.py evals/fixtures/valid-capsule.yaml
```

| Check | Establishes | Does not establish |
| --- | --- | --- |
| Package validator | Selected files, metadata, and reference checks pass | Complete specification conformance or agent activation |
| Capsule checker | Implemented structural and reference constraints pass | Truth, complete prospective contracts, or fork-free lineage |
| Regression tests | Named checker cases behave as asserted | General robustness or better agent decisions |
| Behavioral comparison | Only what the recorded trials and grading support | Universal reliability or transfer to untested models |

`check_capsule.py` expects the YAML payload without continuation delimiters. Exit codes are `0` for a pass, `1` for invalid structure, and `2` for a loading error. Its default size ceiling is a rough character-based estimate of 1,800 tokens, not a tokenizer measurement. Consistent with the method's soft ceiling, an oversize capsule passes the size check only if it declares a non-empty `capsule_overflow` describing what could not safely fit; otherwise it is rejected. To inspect a larger capsule without that declaration, explicitly choose a larger budget:

```sh
python scripts/check_capsule.py path/to/capsule.yaml --hard-token-ceiling 2400
```

## Mega Observe probes

[eight additional cases](../../../evals/mega-observe.yaml) test budget authority, padding pressure, unsupported completeness, evidence-family duplication, resume behavior, and the distinction between evaluated questions and supported findings. These are proposed probes, not recorded passing results or a full Mega run.

The 3.1 addition leaves the continuation capsule schema at 3.0. Mega run records live in separate durable artifacts referenced from the capsule. The charter is a planning template, not an automatically enforced spending limit.

## Run a behavioral study

Read the [protocol](../../../evals/protocol.md), [rubric](../../../evals/rubric.md), and [manifest](../../../evals/manifest.yaml). Before execution, freeze a baseline, candidate commit, model/configuration, permissions, case set, grading instructions, and acceptance thresholds.

Separate prompts from grader-only `required`, `forbidden`, and `catastrophic_if` fields. Supply only the case prompt and permitted evidence to the evaluated agent. Run at least three independent trials per case and variant, randomize order, and blind graders to the variant. Continuity cases require at least three lossy summarize/resume cycles. Preserve failures and grader disagreements.

Use [the run-record template](../../../evals/run-record.template.yaml) to capture the experimental configuration. Raw runs belong under ignored `evals/runs/` until reviewed for intentional publication. Never commit credentials or private tool traces.

Known protocol questions to resolve prospectively:

- The `proportional-low-stakes` case asks for a simple rename and forbids extensive research; full POODO requires research. Treat it as a scope-routing case that should decline the full loop, and freeze that interpretation before trials. If evaluating mandatory full-loop invocation instead, revise the case in a separately versioned manifest.
- Not every rubric dimension is relevant to every scenario. A case may list `not_applicable` dimensions in the manifest; this must be frozen before any trial is scored, and those dimensions are excluded from that case's denominator. No other N/A is allowed, and none may be added after seeing outputs.
- These public cases are development material. Add held-out cases before making generalization claims.

Record per-case and aggregate scores, catastrophic failures, uncertainty, cost, and proportionality regressions. The [proposed thresholds](../../../references/evaluation.md) are not evidence that POODO has met them.

Outcome verification and transcript assessment answer different questions; graders can also be wrong. This distinction informs the evaluation design, as discussed in [Anthropic's agent evaluation guide](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents). It does not validate this project.
