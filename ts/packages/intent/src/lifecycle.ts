// The intent stream as a pure state machine: transition(state, event) gives a new state or a refusal.
// No I/O. The ledger authenticates `by` (each entry is signed by its writer); this code decides
// whether that writer may write that event now.
//
// Trust model (owner, 2026-11-18): confirmation never blocks the work. Derivation, delivery and
// acceptance run against the *proposed* digest. Only goal_closed needs the owner's confirmation.
import { digest, type IntentContract, type IntentRef } from '@cstack/contracts';
import { draftProblems } from './draft.ts';

export const HOST = 'host';
export const LIFECYCLE = 'lifecycle';
export const ACCEPTANCE_RUNNER = 'acceptance-runner';
export const CORE = 'core';

/** An owner decision from the host's ApprovalPort, bound to one digest. */
export type Approval = { approval_id: string; approver: string; subject_sha256: string };
export type TestResult = { test_id: string; passed: boolean; evidence: string; answered_by?: string };

export type IntentEvent =
  | { type: 'intent_drafted'; by: string; contract: IntentContract }
  | { type: 'intent_proposed'; by: string; ref: IntentRef }
  | { type: 'intent_confirmed'; by: string; ref: IntentRef; approval: Approval }
  | { type: 'intent_revised'; by: string; contract: IntentContract }
  | { type: 'derived'; by: string; ref: IntentRef; artifact_sha256: string; what: string }
  | { type: 'delivery_recorded'; by: string; ref: IntentRef; artifact_sha256: string; how_to_run: string[] }
  | { type: 'acceptance_run'; by: string; ref: IntentRef; run_id: string; artifact_sha256: string; results: TestResult[] }
  | { type: 'goal_closed'; by: string; ref: IntentRef; run_id: string }
  | { type: 'intent_abandoned'; by: string; ref: IntentRef; approval: Approval };

export type Status = 'empty' | 'drafted' | 'proposed' | 'in_build' | 'delivered' | 'failed' | 'accepted' | 'abandoned';

export type IntentState = {
  readonly owner: string;
  readonly status: Status;
  readonly revisions: readonly { ref: IntentRef; contract: IntentContract }[];
  readonly proposed: boolean;            // the current revision has been proposed (the card is up)
  readonly confirmed: boolean;           // the owner confirmed the current revision
  readonly used_approvals: readonly string[];
  readonly derived: readonly { ref: IntentRef; by: string; artifact_sha256: string; what: string }[];
  readonly deliveries: readonly { ref: IntentRef; artifact_sha256: string; how_to_run: string[] }[];
  readonly runs: readonly { ref: IntentRef; run_id: string; artifact_sha256: string; results: TestResult[] }[];
  readonly closed_by: string | null;
};

export type Outcome = { ok: true; state: IntentState } | { ok: false; refusal: string };

export function initial(owner: string): IntentState {
  return { owner, status: 'empty', revisions: [], proposed: false, confirmed: false, used_approvals: [],
    derived: [], deliveries: [], runs: [], closed_by: null };
}

export function refOf(contract: IntentContract): IntentRef {
  return { intent_id: contract.intent_id, revision: contract.revision, sha256: digest(contract) };
}

export function current(state: IntentState): { ref: IntentRef; contract: IntentContract } | null {
  return state.revisions.at(-1) ?? null;
}

const same = (a: IntentRef, b: IntentRef) => a.intent_id === b.intent_id && a.revision === b.revision && a.sha256 === b.sha256;

/** Why this ref can't be built on now, or null when it is the current, proposed revision. */
export function checkRef(state: IntentState, ref: IntentRef | null | undefined): string | null {
  const now = current(state);
  if (!ref) return 'no IntentRef: every run must carry the intent it serves';
  if (!now || ref.intent_id !== now.ref.intent_id) return `unknown intent ${ref.intent_id}`;
  const known = state.revisions.find((r) => r.ref.revision === ref.revision);
  if (!known || known.ref.sha256 !== ref.sha256) return `mismatch: ${ref.sha256.slice(0, 12)} is not revision ${ref.revision}`;
  if (ref.revision !== now.ref.revision) return `stale: revision ${ref.revision} was superseded by revision ${now.ref.revision}`;
  if (state.status === 'abandoned') return 'the owner abandoned this intent';
  if (state.status === 'accepted') return 'this intent is closed';
  if (!state.proposed) return 'revision not proposed yet';
  return null;
}

/** True when the ref names an older revision of this intent. */
export function stale(state: IntentState, ref: IntentRef): boolean {
  const now = current(state);
  return !!now && ref.intent_id === now.ref.intent_id && ref.revision < now.ref.revision;
}

/** Everything built from a superseded revision; it must be re-derived before it is promoted. */
export function staleArtifacts(state: IntentState) {
  return state.derived.filter((d) => stale(state, d.ref));
}

const refuse = (refusal: string): Outcome => ({ ok: false, refusal });
const next = (state: IntentState, change: Partial<IntentState>): Outcome => ({ ok: true, state: { ...state, ...change } });

function ownerApproval(state: IntentState, approval: Approval, ref: IntentRef): string | null {
  if (approval.approver !== state.owner) return `only the owner decides; ${approval.approver} is not the owner`;
  if (approval.subject_sha256 !== ref.sha256) return 'the approval is bound to a different digest';
  if (state.used_approvals.includes(approval.approval_id)) return `approval ${approval.approval_id} was already used`;
  return null;
}

export function transition(state: IntentState, event: IntentEvent): Outcome {
  const now = current(state);
  switch (event.type) {
    case 'intent_drafted': {
      if (now) return refuse('this stream already has a draft; revise it instead');
      if (event.by !== event.contract.roles?.chief) return refuse(`${event.by} is not this intent's chief`);
      if (event.contract.revision !== 1) return refuse('a first draft is revision 1');
      const problems = draftProblems(event.contract);
      if (problems.length) return refuse(problems.join('; '));
      return next(state, { status: 'drafted', revisions: [{ ref: refOf(event.contract), contract: event.contract }] });
    }
    case 'intent_revised': {
      if (!now) return refuse('nothing to revise');
      if (state.status === 'accepted' || state.status === 'abandoned') return refuse(`the intent is ${state.status}`);
      if (event.by !== now.contract.roles.chief) return refuse(`${event.by} is not this intent's chief`);
      const c = event.contract;
      if (c.intent_id !== now.ref.intent_id || c.revision !== now.ref.revision + 1 || c.supersedes !== now.ref.sha256)
        return refuse('a revision must keep the intent_id, add 1 to the revision and supersede the current digest');
      const problems = draftProblems(c);
      if (problems.length) return refuse(problems.join('; '));
      return next(state, { status: 'drafted', proposed: false, confirmed: false,
        revisions: [...state.revisions, { ref: refOf(c), contract: c }] });
    }
    case 'intent_proposed': {
      if (!now) return refuse('nothing drafted');
      if (event.by !== now.contract.roles.chief) return refuse(`${event.by} is not this intent's chief`);
      if (!same(event.ref, now.ref)) return refuse('only the current revision can be proposed');
      if (state.proposed) return refuse('already proposed');
      return next(state, { status: 'proposed', proposed: true });
    }
    case 'intent_confirmed': {
      if (event.by !== HOST) return refuse(`only the host writes confirmations, not ${event.by}`);
      const bad = checkRef(state, event.ref) ?? ownerApproval(state, event.approval, event.ref);
      if (bad) return refuse(bad);
      if (state.confirmed) return refuse('already confirmed');
      return next(state, { confirmed: true, used_approvals: [...state.used_approvals, event.approval.approval_id] });
    }
    case 'derived': {
      const bad = checkRef(state, event.ref);
      if (bad) return refuse(bad);
      const d = { ref: event.ref, by: event.by, artifact_sha256: event.artifact_sha256, what: event.what };
      return next(state, { derived: [...state.derived, d],
        status: state.status === 'proposed' ? 'in_build' : state.status });
    }
    case 'delivery_recorded': {
      if (event.by !== LIFECYCLE) return refuse(`only lifecycle activate records a delivery, not ${event.by}`);
      const bad = checkRef(state, event.ref);
      if (bad) return refuse(bad);
      if (!state.derived.some((d) => same(d.ref, event.ref) && d.artifact_sha256 === event.artifact_sha256))
        return refuse('the delivered artifact was not derived from this revision');
      const d = { ref: event.ref, artifact_sha256: event.artifact_sha256, how_to_run: event.how_to_run };
      return next(state, { status: 'delivered', deliveries: [...state.deliveries, d] });
    }
    case 'acceptance_run': {
      if (event.by !== ACCEPTANCE_RUNNER) return refuse(`only the acceptance runner records results, not ${event.by}`);
      const bad = checkRef(state, event.ref);
      if (bad) return refuse(bad);
      if (!state.deliveries.some((d) => same(d.ref, event.ref) && d.artifact_sha256 === event.artifact_sha256))
        return refuse('acceptance runs against a delivered artifact only');
      const tests = now!.contract.acceptance;
      const ids = event.results.map((r) => r.test_id).sort();
      if (ids.join('\n') !== tests.map((t) => t.id).sort().join('\n')) return refuse('a run reports every acceptance test exactly once');
      for (const r of event.results) {
        const t = tests.find((x) => x.id === r.test_id)!;
        if (t.check.kind === 'owner_check' && r.passed && r.answered_by !== state.owner)
          return refuse(`acceptance ${t.id} is the owner's to judge`);
      }
      const run = { ref: event.ref, run_id: event.run_id, artifact_sha256: event.artifact_sha256, results: event.results };
      return next(state, { runs: [...state.runs, run], status: event.results.every((r) => r.passed) ? 'delivered' : 'failed' });
    }
    case 'goal_closed': {
      if (event.by !== CORE) return refuse(`only the core closes a goal, not ${event.by}`);
      const bad = checkRef(state, event.ref);
      if (bad) return refuse(bad);
      if (!state.confirmed) return refuse('delivered, awaiting the owner\'s confirmation');
      const run = state.runs.find((r) => r.run_id === event.run_id);
      if (!run || !same(run.ref, event.ref)) return refuse('no acceptance run for this revision with that id');
      const failing = run.results.filter((r) => !r.passed).map((r) => r.test_id);
      if (failing.length) return refuse(`acceptance failed: ${failing.join(', ')}`);
      return next(state, { status: 'accepted', closed_by: event.run_id });
    }
    case 'intent_abandoned': {
      if (event.by !== HOST) return refuse(`only the host records the owner abandoning, not ${event.by}`);
      if (!now || !same(event.ref, now.ref)) return refuse('abandon names the current revision');
      if (state.status === 'accepted') return refuse('this intent is closed');
      const bad = ownerApproval(state, event.approval, event.ref);
      if (bad) return refuse(bad);
      return next(state, { status: 'abandoned', used_approvals: [...state.used_approvals, event.approval.approval_id] });
    }
  }
}

/** Rebuilds state from the stream (E3′). A refused entry in a stored stream means it was tampered with. */
export function replay(owner: string, events: Iterable<IntentEvent>): IntentState {
  let state = initial(owner);
  let i = 0;
  for (const event of events) {
    const out = transition(state, event);
    if (!out.ok) throw new Error(`entry ${i} (${event.type}) is refused: ${out.refusal}`);
    state = out.state;
    i++;
  }
  return state;
}
