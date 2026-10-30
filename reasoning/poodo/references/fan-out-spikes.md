# Fan-out spike protocol

Default to considering—and normally using—multiple parallel subagents as a recurring, bounded spike tool throughout POODO. Stage transitions are decision checkpoints, not automatic spawn requirements: the outgoing stage has produced a concrete packet and the incoming stage may benefit from challenge before commitment.

## Transition checkpoint

Before crossing Pontificate → Observe, Observe → Orient, Orient → Decide, Decide → Orchestrate, and Orchestrate → Loop:

1. State the uncertainty, coverage gap, or decision that parallel work could improve.
2. Decide prospectively whether separable workstreams exist, what possible result could change the transition, and whether that information gain justifies coordination, latency, and risk.
3. Normally fan out when workers can inspect non-overlapping evidence families, pursue rival hypotheses, generate distinct solution classes, red-team a transition, or verify separate success surfaces.
4. Give each worker a bounded, versioned assignment: role, question, stage, acceptance criteria, evidence slice, artifact/environment identity, context disclosed, read/write scope, authority limits, deliverable, deadline or stop condition, and blinding/independence limits. Give blind critics raw evidence and user-stated criteria but omit prior conclusions and peer outputs unless safety or scope requires them; record unavoidable anchoring.
5. Continue useful local work while workers run. Preserve blind opening outputs before cross-worker exposure. At the barrier, wait once and follow up once; then interrupt or mark a straggler missing according to its stop rule. A missing load-bearing perspective blocks the transition; otherwise record and exclude it while narrowing confidence.
6. Reject, rerun, or explicitly exclude stale outputs when artifact identity, requirements, evidence, runtime state, or stage assumptions changed. A timeout is missing evidence, not negative evidence.
7. Reconcile agreements, contradictions, provenance, blind spots, dependency conflicts, and persistent dissent into the canonical ledger. Resolve load-bearing factual claims, contradictions, and gate inputs to underlying evidence IDs; duplicate evidence lineage counts once. Clearly labeled analysis and proposals need not masquerade as evidence.
8. Record `fanout_used`, boundary, worker roles/statuses, artifact version, context disclosed, independence dimensions and limits, evidence lineage, material disagreements, unresolved claims, stale or missing outputs, synthesis delta, and either the resulting change or concrete non-use reason.
9. Workers may assess gates or prepare inputs for the next stage, but fan-out never substitutes for stage-specific mandatory gates. Only the primary records the authoritative gate decision and rationale.

## Useful spike shapes

- Evidence partition: workers inspect different primary sources, subsystems, artifacts, or time windows.
- Rival hypotheses: workers seek discriminating evidence for competing causal models.
- Red team: one worker attacks the favored frame, test, or orchestration plan.
- Option expansion: workers generate distinct path families before the mandatory 20-path synthesis.
- Dependency reconnaissance: workers map interfaces, failure propagation, authority, or rollback constraints.
- Verification partition: workers test different acceptance criteria or independently reproduce a result from separate evidence.
- Council debate: workers form distinct positions, then challenge each other before evidence-based adjudication.

Use the smallest set of workers that creates materially distinct evidence, method, or rival coverage; when capacity and task structure permit, this is often two or three. The primary owns the concurrency budget and reserves its own slot. Batch excess work into waves. Workers must not spawn descendants unless the primary explicitly allocates capacity; descendants inherit the same authority and evidence labels and do not manufacture independence.

Non-use is justified when no separable question could plausibly change the transition, expected information gain is lower than coordination cost, capacity or latency is constrained, concurrency would be unsafe, or authority is absent. Confidence alone and convenience do not justify skipping the checkpoint.

## Council debate

Use a council for contested framings or choice-heavy transitions, especially Observe → Orient, Orient → Decide, and high-risk Decide → Orchestrate boundaries.

1. Assign distinct evidence, method, stakeholder, or rival-hypothesis roles. Do not create cosmetic personas.
2. Have members produce blind opening memos in parallel: thesis, strongest evidence, strongest disconfirmation, uncertainty, and reversal condition. Preserve each opening before exposing opposing claims.
3. Circulate compact opposing claims and run one rebuttal round. Rebuttals must identify changed claims and the evidence or reasoning that changed them. Further rounds require a named unresolved discriminator.
4. The primary adjudicates against predeclared criteria and ledger evidence. Preserve persistent dissent and reversal conditions; do not vote, average confidence, or force consensus.
5. Record independence for blind openings separately from the deliberately cross-contaminated rebuttal round. Debate consensus is not corroboration.

## Epistemic and operational limits

Parallel agents are exploration multipliers, not automatic corroborators. A worker output is reported analysis, not a new observation. Shared prompts, summaries, repository state, web sources, or model family create correlated failure. Label independence across prompt, evidence, method, model, environment, and evaluator. For attempted reproduction, vary these dimensions where available and otherwise label the result repeated observation rather than independent corroboration.

Default fan-out work to read-only analysis. For mutations, name one integration owner; snapshot artifact/revision identity; partition by dependency and state surface as well as exact paths; require changed-path reports; and serialize coupled registries, generated outputs, schemas, caches, runtime state, production systems, and external effects. Re-read and revalidate after integration. Delegation does not expand scope or authority.

If the user interrupts or redirects the task, cancel or rescope obsolete workers. Never let a late output silently alter the new task.

Fan-out is a spike, not a substitute for judgment. Do not count worker quantity as rigor, vote on truth, merge incompatible claims, or advance merely because all workers finished. Advance only after synthesis identifies what changed, what remains uncertain, and why the next stage is justified.
