# Native Codex goal integration

Use the native goal as POODO's durable execution envelope in both Codex CLI and Desktop. The goal tracks the long-running objective and lifecycle; POODO supplies the epistemic loop, acceptance contract, evidence lineage, phase state, and continuation details. Neither replaces the other.

## Entry and binding

When the user invokes `/goal`, explicitly requests persistent goal work, asks to resume it, or an active goal is visible:

1. Inspect the native goal with the available client/tool capability before dependent action.
2. If no goal exists, create one only when the user explicitly requested goal creation. Do not infer goal creation from an ordinary complex task.
3. Bind the native objective to the POODO objective. Preserve user wording; identify any mismatch, supersession, or scope conflict instead of silently rewriting either.
4. Decompress acceptance criteria, authority, constraints, current POODO phase, active claim/decision/prediction, artifact identity, unresolved contradictions, and next checkpoint.
5. Rehydrate the latest valid continuation capsule and verify mutable, load-bearing state. Goal state and capsules are continuation metadata, not evidence.

Record a compact bridge in the working ledger: native goal identity/status if exposed, objective, POODO phase, current head, active acceptance IDs, latest capsule ID/location, delivery state, outcome state, and next checkpoint.

## Stage synchronization

At every POODO stage transition:

- confirm the work still serves the bound goal and acceptance surface;
- reconcile user changes, contradictions, fan-out results, and artifact identity;
- update the canonical ledger/capsule when durable writes are authorized;
- keep goal status distinct from POODO phase and from delivery/outcome state;
- do not use a stage transition, long runtime, token usage, or completed subtask as evidence that the goal is complete.

At compaction or handoff, emit a valid POODO continuation capsule whose objective and current head remain bound to the native goal. On resume, inspect native goal state again, select capsule ancestry rather than newest prose, revalidate mutable facts, and continue from the first unresolved gate. Do not restart automatically or trust a stale summary.

## Status semantics

Use only goal controls the current client exposes. A slash command entered by the user and an agent-callable goal operation are not assumed equivalent. Never claim to have paused, resumed, replaced, or otherwise changed native status unless the client confirms that operation.

- `complete`: set only when the stated objective is genuinely achieved and no required work remains. Apply POODO's terminal claim contract first. Static checks, authored changes, builds, deployment, agent consensus, or exhausted budget are insufficient when runtime outcome remains required.
- `blocked`: set only when the native contract's blocking threshold is met and meaningful progress cannot continue without user input or an external state change. Difficulty, uncertainty, waiting for one worker, or desire for clarification is not blockage.
- paused/resumed or other client-owned states: acknowledge the user's command, inspect the resulting goal state when possible, and continue or stop accordingly. Do not emulate the transition through unrelated tools.

When a contradiction reopens a supposedly achieved surface, retract the POODO outcome claim immediately. If native goal status cannot be reopened through exposed controls, state the mismatch and bind continued work to the user's current directive without falsifying goal history.

## Cross-client continuity

CLI and Desktop may expose different controls or render the same goal differently. Keep the bridge portable:

- rely on native goal identity/status returned by the active client, not UI position or remembered command syntax;
- store durable POODO detail in the repository or authorized workspace, with stable paths and artifact identities;
- use the same objective and acceptance IDs across clients;
- treat client handoff, cloud/local sync, and autocompaction as provenance boundaries requiring freshness checks;
- never assume a goal visible on one client has synchronized to another until observed.

The highest justified claim is always bounded by the observed operational surface, regardless of what either client displays.
