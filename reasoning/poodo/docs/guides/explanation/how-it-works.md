# How POODO works

POODO is a set of instructions for an agent. Its purpose is to keep a decision tied to evidence and a testable outcome as the work progresses.

| Phase | Question | Useful output |
| --- | --- | --- |
| Pontificate | What work and outcome does the user mean? | Objective, scope, authority, assumptions |
| Observe | What is actually known? | Evidence records and web research |
| Orient | What explanations and paths survive scrutiny? | A mapped problem space, 20 distinct paths, credible rivals |
| Decide | What should happen under these constraints? | Commitment, tradeoffs, reversal conditions |
| Orchestrate | How will authorized action produce and verify the outcome? | Work plan, prospective prediction, observations |

Read the exact requirements in [SKILL.md](../../../SKILL.md); this introduction does not replace them.

## Three distinctions that matter

**A report is not an observation.** A prior summary can tell an agent where to look. It cannot independently prove the underlying claim.

**A structural check is not an outcome test.** A matching hash says something about artifact identity. It says nothing by itself about whether the user can finish a task.

**A plausible cause is not a demonstrated cause.** Keep a credible rival explanation and identify an observation that would distinguish them.

## Before action

Record the predicted effect, criterion, oracle version, exact artifact and environment, failure meaning, monitoring, rollback, and stop condition. Changing the criterion after observing the result creates a new prospective test; it does not repair the old outcome.

When an observation contradicts a load-bearing prediction, narrow the claim before explaining the cause. A concern about the test is not proof that the test was invalid.

## Across sessions

A continuation capsule preserves objective, authority, evidence locators, artifact identity, contradictions, and the next checkpoint. Re-read the required evidence when resuming. See [continuity and ledger](../../../references/continuity-and-ledger.md) for the schema.

The checker validates a structural subset of one capsule. It cannot inspect the world behind evidence links or compare sibling capsule branches.

## Handoffs between sessions

Long work outlives one session. If a session ends mid-investigation, the next one should pick up the same goal and open questions, not a rosier summary. At a handoff, pause or context compaction, the agent writes a *continuation capsule*: a YAML file with the goal, what the agent may do, its predictions and any open contradictions. The next session resumes from it without treating old claims as fresh facts. You do not write capsules yourself. If you keep one, `scripts/check_capsule.py` checks its structure.

The checker catches history that has been quietly rewritten. Here it runs on a sample capsule from the test fixtures, where a prediction went from `failed` back to `pending`, and the prediction points to an acceptance criterion (`AC-demo-visible`) that the file never defines:

```console
$ python scripts/check_capsule.py evals/fixtures/invalid-resurrection.yaml
INVALID POODO capsule structure:
- predictions[0].status_history: terminal prediction was resurrected; create a new prediction ID
- predictions[0].oracle: unresolved ID AC-demo-visible
No judgment about epistemic truth was performed.
```

It exits 1. A failed prediction stays failed. A retest needs a new prediction ID. This output came from a run on 2026-11-08.

## Cost and fit

Mandatory research and divergent exploration make the full loop inappropriate for simple questions. Stop at a precise evidence boundary if required research is unavailable. For complex work, the working records can be detailed while the user-facing answer stays concise.

## The loop in pseudocode

A developer's sketch of the control flow. It is illustrative, not executable, and it does not replace [SKILL.md](../../../SKILL.md), which remains the authoritative contract.

```python
def poodo(request, authority):
    # Authority comes only from the user. Reasoning, delegation, compaction,
    # confidence, and prior action never expand it.

    # ── PONTIFICATE: frame the problem before gathering evidence ──   [references/pontificate.md]
    if not context_clearly_establishes(work, ideal_outcome):
        ask_user("What are you working on? What does the ideal outcome look like?")
    frame = decompress(request)        # objective, acceptance criteria, scope, authority,
                                       # stakes, assumptions, unknowns, rival framings
    frame.separate(user_stated, agent_inferred)
    frame.rival = strongest_rival_frame(frame)
    checkpoint("Pontificate -> Observe")

    while True:
        # ── OBSERVE: establish what is actually known ──   [references/observe.md]
        evidence = gather(frame)       # each record: source, locator, freshness, evidence
                                       # family, scope, and what it does NOT establish
        topology = map_neighborhood(frame, evidence)   # meanings, mechanisms, dependencies,
                                                       # stakeholders, failure modes, unknowns
        if user_selected("Mega Observe"):              # optional, expensive, explicit only
            require(agreed_scope and resource_ceiling)
            evidence += mega_observe(categories=200, evaluations_each=200)  # [references/mega-observe.md]
        research = deep_web_research(topology, include_disconfirming_queries=True)
        if not research.satisfied:     # no web access, snippets only, one convenient source...
            return stop(reason="research gate unsatisfied", boundary=evidence.boundary)
        checkpoint("Observe -> Orient")

        # ── ORIENT: diverge before converging ──   [references/semantic-topology.md, references/orient.md]
        traverse(topology, until=bounded_saturation)   # record unreached regions
        paths = enumerate_paths(count=20, materially_distinct=True)  # incl. diagnostic,
                                       # conservative, rollback, defer/stop, escalate
        viable = cluster_and_eliminate(paths)          # every rejection keeps a reason
        favored, rival = rank(viable), strongest_credible_rival(viable)
        discriminator = observation_that_separates(favored, rival)
        checkpoint("Orient -> Decide")

        # ── DECIDE: the 20 paths are a design space, not a ballot ──   [references/decide.md]
        decision = compose(viable)     # select, combine, sequence, condition, test,
                                       # defer, or escalate any subset
        decision.reverse_if = reversal_conditions(decision)
        assert decision.within(authority)
        assert decision.claim_strength <= evidence.ceiling
        checkpoint("Decide -> Orchestrate")

        # ── ORCHESTRATE: precommit, then act and verify ──   [references/orchestrate.md]
        prediction = precommit(        # recorded BEFORE observing the outcome
            observable, acceptance_boundary, oracle, oracle_version,
            artifact_identity, environment, failure_meaning,
            monitoring, rollback, stop_condition)
        outcome = execute_authorized(decision, monitor=True)
        checkpoint("Orchestrate -> Loop")

        # ── LOOP: compare the outcome with the prediction ──   [references/contradiction-protocol.md]
        if contradicts(outcome, prediction):
            retract_or_narrow(success_claim)           # correct the claim first, explain later
            prediction.status = "failed"               # or "failed_with_test_concern";
                                                       # "invalid" only with outcome-independent proof
            reopen(dependents_of(prediction))
            restore(rival)
            frame = frame.with_contradiction(outcome)  # new prediction ID on any retest
            continue
        if validated_in_named_scope(outcome) or justified_decision_and_next_action() \
                or precise_evidence_or_authority_gap():
            return terminal_claim(     # [references/output-patterns.md]
                delivery_state,                # authored | checked | built | deployed
                outcome_state,                 # unobserved | observed | passed | failed | ...
                highest_justified_claim,
                required_runtime_observation,
                who_controls_next_test)
        frame = frame.with_learning(outcome)   # promote learning only with provenance + scope


def checkpoint(boundary):
    # Run at every stage transition.   [references/fan-out-spikes.md, references/continuity-and-ledger.md]
    if separable_workstreams_could_change(boundary):
        results = fan_out(workers_with_distinct_questions_or_evidence)  # bounded, read-only by default
        reconcile_into_ledger(results)         # agents sharing sources != independent corroboration
    record(fanout_used, reason_if_not)
    if handoff or pause or compaction_imminent:
        emit_continuation_capsule()            # state metadata, never evidence
```

Throughout, claim states stay separate: a report is not an observation, a passing structural check is not a runtime outcome, and a plausible cause is not a demonstrated one.

## Where each step is specified

| Pseudocode | Document | What it breaks down |
| --- | --- | --- |
| `poodo()` as a whole | [SKILL.md](../../../SKILL.md) | The 14 invariants, loop order, routing, terminal claim contract, scaling and stopping |
| `ask_user`, `decompress` | [pontificate.md](../../../references/pontificate.md) | Opening exchange, when it may be waived, linguistic decompression |
| `gather`, `deep_web_research` | [observe.md](../../../references/observe.md) | Evidence records and the mandatory web-research gate |
| `mega_observe` | [mega-observe.md](../../../references/mega-observe.md), [charter template](../../../assets/mega-observe-charter.yaml) | 200 × 200 protocol, budget reservations, no-padding review, durable artifacts |
| `map_neighborhood`, `traverse` | [semantic-topology.md](../../../references/semantic-topology.md) | Topology map, traversal operations, bounded-saturation gate |
| `enumerate_paths`, `cluster_and_eliminate` | [orient.md](../../../references/orient.md) | The 20-path rule and what counts as materially distinct |
| `compose`, `reverse_if` | [decide.md](../../../references/decide.md) | Treating paths as a design space; reversal conditions |
| `precommit`, `execute_authorized` | [orchestrate.md](../../../references/orchestrate.md) | Workstream binding, monitoring, rollback, replanning |
| `contradicts`, `retract_or_narrow` | [contradiction-protocol.md](../../../references/contradiction-protocol.md) | `failed` / `failed_with_test_concern` / `invalid` / `inconclusive`, propagation, anti-rationalization |
| `oracle`, `evidence.ceiling` | [epistemic-integrity.md](../../../references/epistemic-integrity.md) | Verification vs. validation, oracle independence, discriminating tests, terminal labels |
| `checkpoint`, `fan_out` | [fan-out-spikes.md](../../../references/fan-out-spikes.md) | Transition checkpoints, worker assignments, barriers, council debate |
| `emit_continuation_capsule` | [continuity-and-ledger.md](../../../references/continuity-and-ledger.md), [`check_capsule.py`](../../../scripts/check_capsule.py) | Capsule schema, lifecycle rules, re-entry and fork handling |
| `terminal_claim` | [output-patterns.md](../../../references/output-patterns.md) | Recommendation, contradiction, and handoff formats |
| Native `/goal` binding (not shown) | [goal-integration.md](../../../references/goal-integration.md) | Codex goal entry, stage sync, status semantics |
| Choosing which operations to run | [method-selection.md](../../../references/method-selection.md) | Matching an operation to the open question; Quick/Standard/Deep depth |

## Mega Observe (expensive)

An optional research mode for a large semantic map: **200 distinct categories × 200 distinct evaluations each = 40,000 substantive records**. Invoke it explicitly:

```text
Use $poodo in Mega Observe mode to map this problem space. First prepare
its scope, source plan, quality criteria, and cost estimate. Do not begin
the expensive run until a resource ceiling is established.
```

Each category and evaluation must earn its place through a distinct, relevant question and traceable evidence or a documented knowledge gap. Duplicate headings, generic text, unsupported certainty, and invented citations fail the quality gate. If 200 meaningful categories cannot be supported, the result is incomplete.

The mode can require substantial inference and review, potentially hundreds of dollars depending on the host and models. It uses budget checkpoints and resumable records. This repository supplies the [protocol](../../../references/mega-observe.md) and [charter](../../../assets/mega-observe-charter.yaml); it does not include a crawler, paid execution service, or a billing cap implementation.

Literal coverage of the entire internet cannot be verified. The output must report the searched corpus, exclusions, uncertainty, and remaining frontier. The 200 × 200 design is experimental; neither spending nor record count proves completeness.
