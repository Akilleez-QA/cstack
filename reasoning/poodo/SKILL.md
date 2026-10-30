---
name: poodo
description: Structure consequential or ambiguous decisions, investigations, strategy, and improvement through a continuity-aware Pontificate-Observe-Orient-Decide-Orchestrate loop. Use only when explicitly invoked for rigorous evidence separation, adversarial assumption testing, agentic orchestration, and verified learning. Do not use for simple facts or routine execution.
disable-model-invocation: true
metadata:
  version: "3.3"
---

# POODO 3.3

Move ambiguity toward a justified decision and either a verified outcome or an explicit verification boundary. POODO is an epistemic control loop, not a checklist or a performance of named methodologies. Rigor means better discrimination and state integrity, never more prose.

## Choose depth first

Before anything else, pick a depth and record it in one line with its reason. Re-pick when new evidence raises or lowers the stakes.

- **Quick:** the choice is reversible, low-consequence, undisputed, and nothing downstream depends on it. Decide directly using a small criterion set, state how to reverse it, and stop. Skip the research gate, path enumeration, fan-out, and capsules, and do not explain the skipped steps beyond that one depth line.
- **Standard:** the default for non-trivial work that is not Deep. Run the loop at proportionate size: research when external knowledge could change the decision, at least five materially distinct paths including the strongest rival and a stop or defer path, and fan-out only when a separable question could change the next transition.
- **Deep:** consequential, irreversible, disputed, incident, failed-outcome, multi-session, or the user asks for full POODO or Deep. Apply every rule below at full strength.

The invariants on claims, evidence, contradictions, authority, and continuity apply at every depth.

## Non-negotiable invariants

1. **Keep claim states separate.** Possibility, reported claim, observation, corroboration, inference, orientation, decision, action, outcome, and learning are not interchangeable. Implementation is not effect; structural conformance is not runtime validation.
2. **Respect the evidence ceiling.** A conclusion may be no stronger than the combined load-bearing evidence entails. Repetition, fluency, agreement among agents reading the same source, hashes, summaries, and self-authored validators do not independently corroborate a claim.
3. **Test the intended success surface.** Trace goal → acceptance criterion → observable signal → sensor → oracle → artifact/environment → outcome. A proxy can support only a proxy-scoped claim.
4. **Challenge the favored model.** Preserve the strongest credible rival and an observation capable of discriminating between it and the favored orientation. For consequential, disputed, or failed-outcome work, use an independent critic when available and label the degree of independence.
5. **Precommit before acting.** Record the prospective prediction, oracle and version, success boundary, artifact and environment identity, failure meaning, monitoring, rollback, and stop condition. Retrodictive explanations must be labeled as such.
6. **Contradictions interrupt.** A valid observation against a load-bearing prediction retracts or narrows the affected success claim before causal explanation. Default to `failed`; use `failed_with_test_concern` for an unproven caveat. Declare a test `invalid` only with outcome-independent evidence of invalidity.
7. **Authority does not emerge from reasoning.** Act only within the user's authorization. Compaction, delegation, confidence, and prior action never expand authority.
8. **Continuation state is metadata, not evidence.** At lossy boundaries, preserve provenance, lineage, contradictions, and exact artifact identity. Rehydrated claims remain reported prior state until their required evidence is checked.
9. **Research gates Deep orientation without overruling evidence.** At Deep depth, end every Observe phase with deep web research that seeks authoritative foundations, current domain evidence, and credible challenges to the favored frame; record queries, sources, dates, conflicts, and non-entailments. Prior model knowledge or one convenient source does not satisfy it; if research is impossible, stop before Orient and report the boundary. At Standard depth, research when external knowledge could change the decision, otherwise record in one line why it could not. Published material never overrides stronger direct evidence. Details: [observe.md](references/observe.md).
10. **Diverge before converging.** At Deep depth, name exactly 20 materially distinct paths before ranking; at Standard, at least five. Cosmetic variants and versions of the favored approach do not count. Include diagnostic, conservative, reversible, stop/defer, and escalation paths when applicable. The list is working substrate; show it only when asked or when it changes the user's decision. Details: [orient.md](references/orient.md).
11. **Ground the frame before observing.** Decompress the user's language into objective, acceptance, scope, authority, and assumptions, keeping what the user stated separate from what you inferred. Ask the user only when an answer could change the work; when they cannot be asked, proceed on stated assumptions.
12. **Use fan-out as a spike, not a ritual.** At Deep stage transitions, consider a bounded parallel spike and use one when separable workstreams can improve coverage, falsification, option diversity, or verification. Record the use or reason for non-use. Agent agreement is not independent corroboration when context, evidence, models, or prompts are shared. Details: [fan-out-spikes.md](references/fan-out-spikes.md).
13. **Traverse before collapsing.** Treat a stated goal as a constraint surface within a wider topology of meanings, mechanisms, dependencies, stakeholders, failure modes, and rival frames. Claim bounded saturation only against an explicit map; record unreached regions instead of claiming exhaustiveness. Details: [semantic-topology.md](references/semantic-topology.md).
14. **Bind durable work to the host's native goal.** When the user invokes `/goal`, asks to create or resume persistent goal work, or an active native goal governs the thread, bind POODO's objective, acceptance, phase, ledger head, and next checkpoint to it. Use only goal operations the current client actually exposes. Do not complete a goal until its intended outcome, not merely an artifact or proxy, meets acceptance. Details: [goal-integration.md](references/goal-integration.md).

Order governs presentation, never disclosure: surface a contradiction, authority problem, or safety finding the moment you find it, whatever phase you are in.

Do not claim that POODO can prevent every failure. Report only behavior demonstrated within tested scope.

## Run the loop

1. **Pontificate:** frame the problem per invariant 11. Read [pontificate.md](references/pontificate.md) at Deep depth.
2. **Observe:** gather decision-relevant evidence. Record provenance, freshness, evidence family, missing sensors, and what each observation cannot establish. Apply the research rule for the chosen depth.
3. **Orient:** traverse the problem, generate the paths for the chosen depth, and synthesize while preserving the strongest rival, disconfirming evidence, uncovered regions, and the actual success surface.
4. **Decide:** treat the paths as a design space, not a ballot. Select, combine, sequence, condition, test, defer, or escalate; compare with explicit criteria, uncertainty, reversibility, and reversal conditions. Pass the epistemic and authority gates before commitment.
5. **Orchestrate:** coordinate authorized execution, binding every workstream to its prospective prediction and named success surface; read [orchestrate.md](references/orchestrate.md).
6. **Loop:** compare outcome with prediction. Correct the claim before explaining a contradiction. Promote learning only with provenance and a stated applicability boundary.

Choose only operations that answer a necessary question or improve discrimination; see [method-selection.md](references/method-selection.md).

## Respond

The user-facing answer is the deliverable; ledgers, path lists, research logs, and capsules are working state.

- Lead with the answer: the decision, verdict, or retraction in the first sentence. When asked to choose, choose.
- Then give only the decisive evidence, the strongest rival with its discriminator, the main uncertainty, and the next action.
- Keep working records out of the reply unless the user asks, a handoff or compaction boundary requires a capsule, or the record changes what the user will decide.
- Do not narrate the method or the steps you skipped.

For consequential implementation handoffs, also state `delivery_state`, `outcome_state`, `highest_justified_claim`, `required_runtime_observation`, and `who_controls_next_test`. Do not use unqualified `fixed`, `resolved`, `successful`, or `validated` unless the predefined intended-use criterion passed on the named artifact and environment. If execution is complete but the user controls runtime testing, say so directly. Formats: [output-patterns.md](references/output-patterns.md).

## Optional Mega Observe (expensive)

Only when the user explicitly selects **Mega Observe**, read [mega-observe.md](references/mega-observe.md) before Observe. Target a broad, traceable web investigation organized into **200 materially distinct categories, each evaluated in 200 materially distinct ways**: 40,000 substantive evaluation records. Preserve the no-padding quality gate; fewer defensible categories or evaluations means an incomplete run, never fabricated completion.

Agree on the problem, accessible search scope, and a spend/resource ceiling before launching this mode. It can require substantial inference, retrieval, and review, potentially hundreds of dollars; estimate from the selected environment rather than promising a price. No host can prove it searched the entire internet. Report coverage, exclusions, uncertainty, and unresolved regions. More records and more spending do not establish completeness or truth. Mega Observe implies Deep depth.

## Conditional routing

- Only when software work is in scope and system tracing, historical constraints, interface design, defect investigation, or release verification could change the decision, read [software-engineering.md](references/software-engineering.md). Select the relevant procedure; do not load it solely because POODO was invoked, code appears in the evidence, or a script is used for analysis. Keep mixed-domain workstreams and outcome criteria distinct.
- For consequential validation, disputed evidence, incidents, or Deep work, read [epistemic-integrity.md](references/epistemic-integrity.md).
- On a failed prediction, user contradiction, or incompatible evidence, read [contradiction-protocol.md](references/contradiction-protocol.md).
- At handoff, pause, material state transition, recovery, or imminent/actual compaction, read [continuity-and-ledger.md](references/continuity-and-ledger.md) and emit a canonical capsule.
- For skill maintenance, read [evaluation.md](references/evaluation.md). Structural checks never establish behavioral correctness.

## Stopping

Stop when the intended outcome is validated within a named scope, a justified decision and next action exist, or a precise evidence or authority gap prevents responsible progress.
