// The acceptance runner: code, not a model. It runs every acceptance test of the current revision
// against the delivered artifact and returns the `acceptance_run` event for the intent stream.
// Owner checks never hold up the automatic tests: if one is unanswered, the runner reports the
// automatic results and what is pending, and the run is recorded once the owner has answered.
import { join } from 'node:path';
import type { AcceptanceTest, IntentRef } from '@cstack/contracts';
import { ACCEPTANCE_RUNNER, checkRef, current, type IntentEvent, type IntentState, type TestResult } from '@cstack/intent';
import { artifactDigest } from './artifact.ts';
import { difference } from './compare.ts';
import { draw, seeded } from './domain.ts';
import { localCommands, noOwner, workerCalls, type Ports } from './ports.ts';

export type RunInput = {
  state: IntentState;
  ref: IntentRef;
  run_id: string;
  /** The delivered artifact directory, and the module in it that `call` tests import. */
  artifact: { dir: string; entry?: string };
  ports?: Partial<Ports>;
};
export type RunOutput = {
  /** The event to append, or null while an owner check is pending. */
  event: Extract<IntentEvent, { type: 'acceptance_run' }> | null;
  results: TestResult[];
  pending: string[];
};

export class RunRefused extends Error {}

const EVIDENCE = 1000;
const clip = (s: string) => (s.length > EVIDENCE ? s.slice(0, EVIDENCE - 3) + '...' : s);
const show = (v: unknown) => { const s = JSON.stringify(v); return s === undefined ? String(v) : s.length > 200 ? s.slice(0, 197) + '...' : s; };

export async function runAcceptance(input: RunInput): Promise<RunOutput> {
  const { state, ref, run_id, artifact } = input;
  const bad = checkRef(state, ref);
  if (bad) throw new RunRefused(bad);
  const sha = artifactDigest(artifact.dir);
  if (!state.deliveries.some((d) => d.ref.sha256 === ref.sha256 && d.artifact_sha256 === sha))
    throw new RunRefused(`the artifact at hand (${sha.slice(0, 12)}) is not a delivery of this revision`);
  const ports: Ports = { calls: workerCalls(), commands: localCommands(), owner: noOwner, ...input.ports };
  const tests = current(state)!.contract.acceptance;

  const results: TestResult[] = [];
  const pending: string[] = [];
  for (const test of tests) {
    const r = await runOne(test, ref, artifact, ports);
    if (r === null) pending.push(test.id);
    else results.push({ ...r, evidence: clip(r.evidence) });
  }
  const event = pending.length ? null
    : { type: 'acceptance_run' as const, by: ACCEPTANCE_RUNNER, ref, run_id, artifact_sha256: sha, results };
  return { event, results, pending };
}

async function runOne(test: AcceptanceTest, ref: IntentRef, artifact: RunInput['artifact'], ports: Ports): Promise<TestResult | null> {
  const c = test.check;
  const entry = () => {
    if (!artifact.entry) throw new RunRefused(`acceptance ${test.id} calls ${'call' in c ? c.call : ''}, but no entry module was given`);
    return join(artifact.dir, artifact.entry);
  };
  const fail = (evidence: string): TestResult => ({ test_id: test.id, passed: false, evidence });
  switch (c.kind) {
    case 'example': {
      const o = await ports.calls({ entry: entry(), call: c.call, cases: [c.inputs] });
      if ('fatal' in o) return fail(o.fatal);
      const r = o.results[0]!;
      if (r.error) return fail(`threw ${r.error}`);
      const d = difference(r.out, c.expect, c.tolerance_ulps);
      return d ? fail(d) : { test_id: test.id, passed: true, evidence: `matched ${show(c.expect)}` };
    }
    case 'property': {
      const { seed, rand } = seeded(`${ref.sha256}/${test.id}`);
      const cases = Array.from({ length: c.samples }, () => draw(c.domain, rand));
      const names = c.domain && typeof c.domain === 'object' && !Array.isArray(c.domain) ? Object.keys(c.domain) : ['input'];
      const o = await ports.calls({ entry: entry(), call: c.call, cases, predicate: c.predicate, names });
      if ('fatal' in o) return fail(`${o.fatal} (seed ${seed})`);
      const held = o.results.filter((r) => r.holds === true).length;
      const firstBad = o.results.findIndex((r) => r.holds !== true);
      const summary = `${held}/${c.samples} held, seed ${seed}`;
      if (firstBad < 0) return { test_id: test.id, passed: true, evidence: summary };
      const r = o.results[firstBad]!;
      return fail(`${summary}; first counterexample ${show(cases[firstBad])} ${r.error ? `threw ${r.error}` : `gave ${show(r.out)}`}`);
    }
    case 'command': {
      const o = await ports.commands(c.argv, artifact.dir);
      if (o.fatal) return fail(o.fatal);
      if (o.exit !== c.expect_exit) return fail(`exit ${o.exit}, expected ${c.expect_exit}${o.stderr_tail ? `; stderr: ${o.stderr_tail}` : ''}`);
      if (c.expect_stdout_sha256 && o.stdout_sha256 !== c.expect_stdout_sha256) return fail(`stdout sha256 ${o.stdout_sha256.slice(0, 12)} differs`);
      return { test_id: test.id, passed: true, evidence: `exit ${o.exit}${c.expect_stdout_sha256 ? ', stdout matched' : ''}` };
    }
    case 'owner_check': {
      const a = await ports.owner(test, ref);
      if (!a) return null;
      return { test_id: test.id, passed: a.passed, answered_by: a.answered_by, evidence: a.note ?? (a.passed ? 'the owner accepted it' : 'the owner turned it down') };
    }
  }
}
