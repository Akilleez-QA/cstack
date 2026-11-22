import { test } from 'node:test';
import assert from 'node:assert/strict';
import { appendFileSync } from 'node:fs';
import { join } from 'node:path';
import { CORE, refOf } from '@cstack/intent';
import { localCommands, runAcceptance, RunRefused, workerCalls, type Ports } from '@cstack/acceptance';
import { GOOD, OWNER, apply, artifact, confirm, delivered, sample } from './fixtures.ts';

const ENTRY = 'clamp.mjs';
const fast = { calls: workerCalls({ timeoutMs: 2000 }) };

test('E5: a correct artifact passes every acceptance test, and the goal closes on that run', async () => {
  const c = sample();
  const dir = artifact(GOOD);
  const { ref, state } = delivered(c, dir);
  const out = await runAcceptance({ state, ref, run_id: 'run-1', artifact: { dir, entry: ENTRY }, ports: fast });
  assert.deepEqual(out.pending, []);
  for (const r of out.results) assert.equal(r.passed, true, `${r.test_id}: ${r.evidence}`);
  assert.match(out.results.find((r) => r.test_id === 'stays-in-range')!.evidence, /^1000\/1000 held, seed \d+$/);
  const closed = apply(state, out.event!, confirm(ref), { type: 'goal_closed', by: CORE, ref, run_id: 'run-1' });
  assert.equal(closed.status, 'accepted');
});

// Mini E6, deterministic: each kernel misreads the owner in one way. Acceptance must catch every one.
const PLANTED: Record<string, string> = {
  'no upper bound': 'xs[i] = xs[i] < lo ? lo : xs[i]',
  'off by one at hi': 'xs[i] = xs[i] < lo ? lo : xs[i] > hi ? hi - 1 : xs[i]',
  'does nothing': 'xs[i] = xs[i]',
  'bounds swapped': 'xs[i] = xs[i] < lo ? hi : xs[i] > hi ? lo : xs[i]',
  'lower bound fixed at 0': 'xs[i] = xs[i] < 0 ? 0 : xs[i] > hi ? hi : xs[i]',
  'only the first three': 'if (i < 3) xs[i] = xs[i] < lo ? lo : xs[i] > hi ? hi : xs[i]',
};
const kernel = (body: string) => GOOD.replace('xs[i] = xs[i] < lo ? lo : xs[i] > hi ? hi : xs[i]', body);

test('mini E6: acceptance catches 6 of 6 planted misreadings, including ones the example misses', async () => {
  let caught = 0, exampleMissed = 0;
  for (const [name, body] of Object.entries(PLANTED)) {
    const c = sample();
    const dir = artifact(kernel(body));
    const { ref, state } = delivered(c, dir);
    const out = await runAcceptance({ state, ref, run_id: 'r', artifact: { dir, entry: ENTRY }, ports: fast });
    const failed = out.results.filter((r) => !r.passed).map((r) => r.test_id);
    if (failed.length) caught++;
    if (!failed.includes('clamps-example')) exampleMissed++;
    assert.ok(failed.length, `${name} was not caught`);
    const s = apply(state, out.event!, confirm(ref));
    assert.equal(s.status, 'failed', name);
  }
  assert.equal(caught, 6);
  assert.ok(exampleMissed >= 2, 'the property test should be catching what the single example cannot');
});

test('a typed-array result with the right values passes; the comparison is by value', async () => {
  const c = sample();
  const dir = artifact(GOOD.replace('return xs;', 'return Int32Array.from(xs);'));
  const { ref, state } = delivered(c, dir);
  const out = await runAcceptance({ state, ref, run_id: 'r', artifact: { dir, entry: ENTRY }, ports: fast });
  assert.ok(out.results.every((r) => r.passed), JSON.stringify(out.results));
});

test('a kernel that hangs fails on a timeout instead of hanging the runner', async () => {
  const c = sample();
  const dir = artifact(GOOD.replace('for (let i = 0;', 'for (;;) {} for (let i = 0;'));
  const { ref, state } = delivered(c, dir);
  const t0 = Date.now();
  const out = await runAcceptance({ state, ref, run_id: 'r', artifact: { dir, entry: ENTRY }, ports: { calls: workerCalls({ timeoutMs: 300 }), commands: localCommands({ timeoutMs: 300 }) } });
  assert.ok(Date.now() - t0 < 5000);
  assert.match(out.results.find((r) => r.test_id === 'clamps-example')!.evidence, /timed out after 300 ms/);
  assert.match(out.results.find((r) => r.test_id === 'runs')!.evidence, /timed out after 300 ms/);
});

test('a missing export and a crash on load are failures with plain evidence', async () => {
  for (const [source, why] of [['export const nope = 1;', /exports no function "clamp"/], ['throw new Error("boom")', /boom/]] as const) {
    const c = sample();
    const dir = artifact(source);
    const { ref, state } = delivered(c, dir);
    const out = await runAcceptance({ state, ref, run_id: 'r', artifact: { dir, entry: ENTRY }, ports: fast });
    assert.match(out.results[0]!.evidence, why);
  }
});

test('the runner refuses an artifact changed after delivery, and a stale ref', async () => {
  const c = sample();
  const dir = artifact(GOOD);
  const { ref, state } = delivered(c, dir);
  appendFileSync(join(dir, 'clamp.mjs'), '\n// edited after delivery\n');
  await assert.rejects(runAcceptance({ state, ref, run_id: 'r', artifact: { dir, entry: ENTRY } }), RunRefused);
  const c2 = { ...structuredClone(c), revision: 2, supersedes: ref.sha256 };
  c2.restatement.exclusions.push('empty arrays');
  const revised = apply(state, { type: 'intent_revised', by: 'chief', contract: c2 }, { type: 'intent_proposed', by: 'chief', ref: refOf(c2) });
  await assert.rejects(runAcceptance({ state: revised, ref, run_id: 'r', artifact: { dir, entry: ENTRY } }), /stale/);
});

test('a command test checks the exit code and, when given, the stdout digest', async () => {
  const c = sample();
  c.acceptance[2]!.check = { kind: 'command', argv: ['node', 'clamp.mjs', '--self-check'], expect_exit: 0, expect_stdout_sha256: 'f'.repeat(64) };
  const dir = artifact(GOOD);
  const { ref, state } = delivered(c, dir);
  const out = await runAcceptance({ state, ref, run_id: 'r', artifact: { dir, entry: ENTRY }, ports: fast });
  assert.match(out.results.find((r) => r.test_id === 'runs')!.evidence, /stdout sha256 .* differs/);
  const broken = artifact(GOOD.replace("'0,0,3'", "'0,0,4'"));
  const b = delivered(sample(), broken);
  const out2 = await runAcceptance({ state: b.state, ref: b.ref, run_id: 'r', artifact: { dir: broken, entry: ENTRY }, ports: fast });
  assert.match(out2.results.find((r) => r.test_id === 'runs')!.evidence, /exit 1, expected 0/);
});

test('an unanswered owner check holds back only the record, never the automatic tests', async () => {
  const c = sample();
  c.acceptance.push({ id: 'feels-right', says: 'The API is what the owner wanted.', author: 'sage', check: { kind: 'owner_check', prompt: 'Is the API right?' } });
  const dir = artifact(GOOD);
  const { ref, state } = delivered(c, dir);
  const waiting = await runAcceptance({ state, ref, run_id: 'r', artifact: { dir, entry: ENTRY }, ports: fast });
  assert.equal(waiting.event, null);
  assert.deepEqual(waiting.pending, ['feels-right']);
  assert.equal(waiting.results.length, 3);
  const by = (who: string): Partial<Ports> => ({ ...fast, owner: async () => ({ passed: true, answered_by: who }) });
  const answered = await runAcceptance({ state, ref, run_id: 'r2', artifact: { dir, entry: ENTRY }, ports: by(OWNER) });
  apply(state, answered.event!);
  const relayed = await runAcceptance({ state, ref, run_id: 'r3', artifact: { dir, entry: ENTRY }, ports: by('chief') });
  assert.throws(() => apply(state, relayed.event!), /owner's to judge/);
});

test('property inputs are seeded by the intent digest: two runs give identical evidence', async () => {
  const c = sample();
  const dir = artifact(kernel(PLANTED['lower bound fixed at 0']!));
  const { ref, state } = delivered(c, dir);
  const a = await runAcceptance({ state, ref, run_id: 'r', artifact: { dir, entry: ENTRY }, ports: fast });
  const b = await runAcceptance({ state, ref, run_id: 'r', artifact: { dir, entry: ENTRY }, ports: fast });
  assert.deepEqual(a.results, b.results);
  assert.match(a.results[1]!.evidence, /held, seed \d+; first counterexample/);
});
