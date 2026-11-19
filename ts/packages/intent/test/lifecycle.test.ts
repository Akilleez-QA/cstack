import { test } from 'node:test';
import assert from 'node:assert/strict';
import { digest, type IntentContract, type IntentRef } from '@cstack/contracts';
import {
  ACCEPTANCE_RUNNER, CORE, HOST, LIFECYCLE, checkRef, draftProblems, initial, refOf, replay, staleArtifacts,
  transition, type IntentEvent, type IntentState,
} from '@cstack/intent';
import { sample } from './helpers.ts';

const OWNER = 'owner';
const ART = 'a'.repeat(64);
const allPass = (c: IntentContract) => c.acceptance.map((t) => ({ test_id: t.id, passed: true, evidence: 'ok' }));

function apply(state: IntentState, ...events: IntentEvent[]): IntentState {
  for (const e of events) {
    const out = transition(state, e);
    if (!out.ok) assert.fail(`${e.type} refused: ${out.refusal}`);
    state = out.state;
  }
  return state;
}
function refused(state: IntentState, event: IntentEvent, pattern: RegExp) {
  const out = transition(state, event);
  assert.equal(out.ok, false, `${event.type} should be refused`);
  if (!out.ok) assert.match(out.refusal, pattern);
}
const confirm = (ref: IntentRef, id = 'ap-1', approver = OWNER): IntentEvent =>
  ({ type: 'intent_confirmed', by: HOST, ref, approval: { approval_id: id, approver, subject_sha256: ref.sha256 } });

/** The whole goal with the confirm card left unanswered until the end. */
function delivered() {
  const c = sample();
  const ref = refOf(c);
  const events: IntentEvent[] = [
    { type: 'intent_drafted', by: 'chief', contract: c },
    { type: 'intent_proposed', by: 'chief', ref },
    { type: 'derived', by: 'scribe', ref, artifact_sha256: 'b'.repeat(64), what: 'spec' },
    { type: 'derived', by: 'smith', ref, artifact_sha256: ART, what: 'kernel' },
    { type: 'delivery_recorded', by: LIFECYCLE, ref, artifact_sha256: ART, how_to_run: c.delivery.how_to_run },
    { type: 'acceptance_run', by: ACCEPTANCE_RUNNER, ref, run_id: 'run-1', artifact_sha256: ART, results: allPass(c) },
  ];
  return { c, ref, events, state: apply(initial(OWNER), ...events) };
}

test('E13 (pure): the unanswered card blocks nothing; build, delivery and acceptance all run on the proposed digest', () => {
  const { state } = delivered();
  assert.equal(state.confirmed, false);
  assert.equal(state.status, 'delivered');
});

test('E5 (pure): the goal closes only on acceptance of the delivered artifact, with the owner\'s one confirmation', () => {
  const { ref, state } = delivered();
  refused(state, { type: 'goal_closed', by: CORE, ref, run_id: 'run-1' }, /awaiting the owner/);
  const closed = apply(state, confirm(ref), { type: 'goal_closed', by: CORE, ref, run_id: 'run-1' });
  assert.equal(closed.status, 'accepted');
  assert.equal(closed.closed_by, 'run-1');
  refused(closed, { type: 'derived', by: 'smith', ref, artifact_sha256: ART, what: 'kernel' }, /closed/);
});

test('a failing acceptance run never closes the goal', () => {
  const { c, ref, state } = delivered();
  const results = allPass(c).map((r, i) => (i === 1 ? { ...r, passed: false } : r));
  const failed = apply(state, confirm(ref),
    { type: 'acceptance_run', by: ACCEPTANCE_RUNNER, ref, run_id: 'run-2', artifact_sha256: ART, results });
  assert.equal(failed.status, 'failed');
  refused(failed, { type: 'goal_closed', by: CORE, ref, run_id: 'run-2' }, /acceptance failed: stays-in-range/);
});

test('acceptance runs only against a delivered artifact, reporting every test once', () => {
  const { c, ref, state } = delivered();
  const run = (over: object): IntentEvent =>
    ({ type: 'acceptance_run', by: ACCEPTANCE_RUNNER, ref, run_id: 'r', artifact_sha256: ART, results: allPass(c), ...over } as IntentEvent);
  refused(state, run({ artifact_sha256: 'c'.repeat(64) }), /delivered artifact only/);
  refused(state, run({ results: allPass(c).slice(1) }), /every acceptance test exactly once/);
  refused(state, run({ by: 'warden' }), /only the acceptance runner/);
});

test('E2: a run with no ref, a stale ref or a mismatched ref is refused, 3 of 3', () => {
  const { c, ref, state } = delivered();
  const c2 = { ...structuredClone(c), revision: 2, supersedes: ref.sha256 };
  c2.restatement.exclusions = [...c2.restatement.exclusions, 'negative bounds'];
  const revised = apply(state, { type: 'intent_revised', by: 'chief', contract: c2 }, { type: 'intent_proposed', by: 'chief', ref: refOf(c2) });
  assert.match(checkRef(revised, undefined)!, /no IntentRef/);
  assert.match(checkRef(revised, ref)!, /stale: revision 1 was superseded by revision 2/);
  assert.match(checkRef(revised, { ...refOf(c2), sha256: 'f'.repeat(64) })!, /mismatch/);
  assert.equal(checkRef(revised, refOf(c2)), null);
});

test('E9: only the owner, through the host, confirms; relayed or replayed approvals are refused', () => {
  const { ref, state } = delivered();
  refused(state, { ...confirm(ref), by: 'chief' } as IntentEvent, /only the host/);
  refused(state, confirm(ref, 'ap-x', 'chief'), /only the owner decides/);
  refused(state, { ...confirm(ref), approval: { approval_id: 'ap-y', approver: OWNER, subject_sha256: 'e'.repeat(64) } } as IntentEvent, /different digest/);
  const once = apply(state, confirm(ref, 'ap-1'));
  refused(once, confirm(ref, 'ap-1'), /already/);
  const abandon: IntentEvent = { type: 'intent_abandoned', by: HOST, ref, approval: { approval_id: 'ap-1', approver: OWNER, subject_sha256: ref.sha256 } };
  refused(once, abandon, /already used/);
});

test('E10: revising after the build marks everything from the old digest stale and refuses to deliver it', () => {
  const { c, ref, state } = delivered();
  const c2 = { ...structuredClone(c), revision: 2, supersedes: ref.sha256 };
  c2.restatement.objective = 'Clamp i32 arrays in place, and return how many values changed.';
  const ref2 = refOf(c2);
  let s = apply(state, confirm(ref), { type: 'intent_revised', by: 'chief', contract: c2 });
  assert.equal(s.confirmed, false, 'a confirmation binds one digest');
  assert.equal(staleArtifacts(s).length, 2);
  s = apply(s, { type: 'intent_proposed', by: 'chief', ref: ref2 });
  refused(s, { type: 'delivery_recorded', by: LIFECYCLE, ref: ref2, artifact_sha256: ART, how_to_run: ['x'] }, /not derived from this revision/);
  refused(s, { type: 'derived', by: 'smith', ref, artifact_sha256: ART, what: 'kernel' }, /stale/);
  refused(s, { type: 'goal_closed', by: CORE, ref, run_id: 'run-1' }, /stale/);
  s = apply(s, { type: 'derived', by: 'smith', ref: ref2, artifact_sha256: 'd'.repeat(64), what: 'kernel' });
  assert.equal(s.status, 'in_build');
});

test('a revision must supersede the current digest, keep the id and be written by the chief', () => {
  const { c, ref, state } = delivered();
  const c2 = { ...structuredClone(c), revision: 2, supersedes: ref.sha256 };
  refused(state, { type: 'intent_revised', by: 'smith', contract: c2 }, /not this intent's chief/);
  refused(state, { type: 'intent_revised', by: 'chief', contract: { ...c2, supersedes: 'f'.repeat(64) } }, /supersede/);
  refused(state, { type: 'intent_revised', by: 'chief', contract: { ...c2, revision: 3 } }, /add 1/);
  refused(state, { type: 'intent_revised', by: 'chief', contract: { ...c2, intent_id: 'other' } }, /keep the intent_id/);
});

test('E11: a draft with an acceptance test that cannot fail is refused', () => {
  const identity = sample();
  identity.acceptance[0]!.check = { kind: 'example', call: 'id', inputs: [1, 2], expect: [1, 2], tolerance_ulps: 0 };
  const trivial = sample();
  for (const predicate of ['true', '() => true', 'x => { return true; }', '!0']) {
    trivial.acceptance[1]!.check = { kind: 'property', call: 'clamp', domain: 'i32', predicate, samples: 10 };
    assert.match(draftProblems(trivial).join(), /true for every input/, predicate);
  }
  const alwaysOk = sample();
  alwaysOk.acceptance[2]!.check = { kind: 'command', argv: ['true'], expect_exit: 0 };
  assert.match(draftProblems(identity).join(), /equals its input/);
  assert.match(draftProblems(alwaysOk).join(), /always exits 0/);
  refused(initial(OWNER), { type: 'intent_drafted', by: 'chief', contract: identity }, /can't fail/);
  assert.deepEqual(draftProblems(sample()), []);
});

test('acceptance tests are written by someone other than the spec writer and the builder', () => {
  for (const author of ['scribe', 'smith']) {
    const c = sample();
    c.acceptance[0]!.author = author;
    assert.match(draftProblems(c).join(), /written independently/, author);
  }
  const dup = sample();
  dup.acceptance[1]!.id = dup.acceptance[0]!.id;
  assert.match(draftProblems(dup).join(), /duplicate id/);
});

test('an owner_check passes only on the owner\'s own answer', () => {
  const c = sample();
  c.acceptance.push({ id: 'feels-right', says: 'The owner is happy with the API.', author: 'sage', check: { kind: 'owner_check', prompt: 'Is the API what you wanted?' } });
  const ref = refOf(c);
  const s = apply(initial(OWNER),
    { type: 'intent_drafted', by: 'chief', contract: c }, { type: 'intent_proposed', by: 'chief', ref },
    { type: 'derived', by: 'smith', ref, artifact_sha256: ART, what: 'kernel' },
    { type: 'delivery_recorded', by: LIFECYCLE, ref, artifact_sha256: ART, how_to_run: ['node', 'clamp.mjs'] });
  const run = (answered_by?: string): IntentEvent => ({ type: 'acceptance_run', by: ACCEPTANCE_RUNNER, ref, run_id: 'r', artifact_sha256: ART,
    results: allPass(c).map((r) => (r.test_id === 'feels-right' ? { ...r, answered_by } : r)) });
  refused(s, run('chief'), /owner's to judge/);
  apply(s, run(OWNER));
});

test('E3′ (pure): replaying the stream rebuilds the identical state, and the goal continues from it', () => {
  const { ref, events, state } = delivered();
  const rebuilt = replay(OWNER, structuredClone(events));
  assert.deepEqual(rebuilt, state);
  assert.equal(digest(rebuilt as unknown as object), digest(state as unknown as object));
  const closed = apply(rebuilt, confirm(ref), { type: 'goal_closed', by: CORE, ref, run_id: 'run-1' });
  assert.equal(closed.status, 'accepted');
  const tampered = structuredClone(events);
  (tampered[2] as { ref: IntentRef }).ref = { ...ref, sha256: '0'.repeat(64) };
  assert.throws(() => replay(OWNER, tampered), /entry 2 \(derived\) is refused: mismatch/);
});

test('only the chief drafts and proposes, and only the current revision', () => {
  const c = sample();
  refused(initial(OWNER), { type: 'intent_drafted', by: 'smith', contract: c }, /not this intent's chief/);
  const s = apply(initial(OWNER), { type: 'intent_drafted', by: 'chief', contract: c });
  refused(s, { type: 'derived', by: 'smith', ref: refOf(c), artifact_sha256: ART, what: 'k' }, /not proposed yet/);
  refused(s, { type: 'intent_proposed', by: 'scribe', ref: refOf(c) }, /not this intent's chief/);
  refused(s, { type: 'intent_drafted', by: 'chief', contract: c }, /already has a draft/);
});
