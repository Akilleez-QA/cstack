import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { runUniversalGates } from './gates.mjs';

const ensure = (condition, reason) => { if (!condition) throw new Error(reason); };
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const named = value => typeof value === 'string' && value.length > 0;
const copy = value => structuredClone(value);

const refusedExit = 3;
const unavailable = () => Object.assign(new Error('frozen evaluator verification unavailable'), { unavailable: true });
function checkFrozen(reference, timeoutMs) {
  return new Promise((resolve, reject) => {
    const child = execFile('python3', ['-B', '-m', 'core.engine.frozen'], {
      cwd: fileURLToPath(new URL('../../', import.meta.url)), timeout: timeoutMs, maxBuffer: 16 * 1024 * 1024,
    }, (error, stdout) => {
      if (error) return reject(error.code === refusedExit ? new Error('frozen evaluator verification failed') : unavailable());
      try { resolve(JSON.parse(stdout)); } catch { reject(unavailable()); }
    });
    child.stdin.on('error', () => {});
    child.stdin.end(JSON.stringify(reference));
  });
}

export async function requireFrozen(reference, { timeoutMs = 10000, attempts = 3 } = {}) {
  for (let attempt = 1; ; attempt++) {
    try { return await checkFrozen(reference, timeoutMs); }
    catch (error) {
      if (!error.unavailable || attempt >= attempts) throw error;
      await new Promise(resolve => setTimeout(resolve, 100 * attempt + Math.random() * 400));
    }
  }
}

function dimensions(objectives) {
  ensure(object(objectives) && Object.keys(objectives).length > 0, 'objective directions required');
  ensure(Object.values(objectives).every(value => ['min', 'max'].includes(value)), 'directions must be min or max');
  return Object.keys(objectives).sort();
}

function validateMetrics(metrics, objectives) {
  const keys = dimensions(objectives);
  ensure(object(metrics) && JSON.stringify(Object.keys(metrics).sort()) === JSON.stringify(keys), 'metric dimensions differ');
  ensure(keys.every(key => typeof metrics[key] === 'number' && Number.isFinite(metrics[key])), 'finite metrics required');
}

export function paretoFrontier(candidates, objectives) {
  const keys = dimensions(objectives);
  for (const row of candidates) validateMetrics(row.metrics, objectives);
  const dominates = (a, b) => {
    const compare = key => objectives[key] === 'min' ? a.metrics[key] <= b.metrics[key] : a.metrics[key] >= b.metrics[key];
    return keys.every(compare) && keys.some(key => a.metrics[key] !== b.metrics[key]);
  };
  return candidates.filter(b => !candidates.some(a => dominates(a, b)));
}

export async function evaluateCandidates(reference, candidates, port, { verifyFrozen: given, requireFrozen: required } = {}) {
  const verifyFrozen = given ?? required ?? requireFrozen;
  reference = copy(reference);
  candidates = copy(candidates);
  ensure(Array.isArray(candidates) && candidates.every(named) && new Set(candidates).size === candidates.length, 'unique candidate identities required');
  const frozen = await verifyFrozen(reference);
  ensure(Object.keys(frozen.bundle.configuration).sort().join(',') === 'gateInput,invariants,objectives', 'expected gateInput, invariants and objectives configuration');
  const { gateInput, invariants, objectives } = frozen.bundle.configuration;
  ensure(object(gateInput) && !Object.hasOwn(gateInput, 'candidate'), 'shared gate input required');
  ensure(Array.isArray(invariants) && invariants.every(named) && new Set(invariants).size === invariants.length, 'explicit invariant list required');
  dimensions(objectives);
  const attempts = [];
  let verified = true;
  async function evaluate(candidate, round) {
    const result = { candidate, round, frozen_evaluator: frozen.identity, evaluator_digest: frozen.digest,
      stage: 'passed', firstFailure: null, results: [], metrics: null };
    attempts.push(result);
    const fail = (check, reason, unknown = false) => {
      result.stage = unknown ? 'outcome_unknown' : 'rejected';
      result.firstFailure = check;
      result.results.push({ check, passed: false, reason });
      return result;
    };
    async function verify() {
      try {
        const current = await verifyFrozen(reference);
        ensure(current.identity === frozen.identity && current.digest === frozen.digest, 'frozen identity changed');
        verified = true;
        return true;
      } catch (error) {
        fail('frozen', error?.unavailable ? error.message : 'frozen evaluator verification failed', error?.unavailable === true);
        return false;
      }
    }
    if (!verified && !await verify()) return result;
    verified = false;
    let ambiguous = false;
    const invoke = async (method, args) => {
      try {
        const value = copy(await port[method](...args));
        ensure(value?.status !== 'outcome_unknown', 'host reported an unknown outcome');
        return value;
      }
      catch (error) { ambiguous = true; throw error; }
    };
    const gatePort = Object.fromEntries(['describe', 'run', 'scanEffects'].map(method =>
      [method, (...args) => invoke(method, args)]));
    const gates = await runUniversalGates({ ...copy(gateInput), candidate }, gatePort);
    result.results.push(...gates.results);
    if (!gates.passed) {
      result.stage = ambiguous ? 'outcome_unknown' : 'rejected';
      result.firstFailure = gates.firstFailure;
      return result;
    }
    const checks = [...invariants.map(name => [`invariant:${name}`, 'invariant', [name]]), ['residual', 'residual', []]];
    for (const [check, method, prefix] of checks) {
      let verdict;
      try { verdict = await invoke(method, [...prefix, candidate, copy(frozen.bundle), round]); }
      catch { return fail(check, 'host operation did not return an outcome', true); }
      if (!object(verdict) || typeof verdict.passed !== 'boolean' || !named(verdict.reason)) return fail(check, 'invalid check evidence');
      if (!verdict.passed) return fail(check, verdict.reason);
      result.results.push({ check, passed: true, reason: verdict.reason });
    }
    let metrics;
    try { metrics = await invoke('measure', [candidate, copy(frozen.bundle), round]); }
    catch { return fail('measurement', 'host operation did not return an outcome', true); }
    try { validateMetrics(metrics, objectives); }
    catch (error) { return fail('measurement', error.message); }
    if (await verify()) result.metrics = metrics;
    return result;
  }
  const report = (stage, frontier = []) => ({ stage, frozen_evaluator: frozen.identity,
    evaluator_digest: frozen.digest, attempts, frontier: frontier.map(row => row.candidate) });
  const survivors = [];
  for (const candidate of candidates) {
    const result = await evaluate(candidate, 0);
    if (result.stage === 'outcome_unknown') return report('outcome_unknown');
    if (result.firstFailure === 'frozen') return report('rejected');
    if (result.stage === 'passed') survivors.push(result);
  }
  const finalists = [];
  for (const finalist of paretoFrontier(survivors, objectives)) {
    const result = await evaluate(finalist.candidate, 1);
    if (result.stage === 'outcome_unknown') return report('outcome_unknown');
    if (result.firstFailure === 'frozen') return report('rejected');
    if (result.stage === 'passed') finalists.push(result);
  }
  return report('completed', paretoFrontier(finalists, objectives));
}
