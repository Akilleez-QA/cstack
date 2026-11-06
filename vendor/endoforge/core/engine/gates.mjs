import { canonical, validateContract, validateSignature } from '../../tools/factory_quality/index.mjs';

export const GATE_ORDER = Object.freeze(['schema', 'interface', 'bounds', 'determinism', 'forbidden_effects']);
const ensure = (condition, reason) => { if (!condition) throw new Error(reason); };
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const text = value => typeof value === 'string' && value.length > 0;
const fields = (value, names) => ensure(object(value) && canonical(Object.keys(value).sort()) === canonical([...names].sort()), `expected fields: ${names.join(', ')}`);
const effects = value => ensure(Array.isArray(value) && value.every(text), 'effects must be an explicit list of names');

function jsonCopy(value, depth = 0) {
  ensure(depth <= 64, 'JSON nesting exceeds 64');
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return value;
  if (typeof value === 'number') {
    ensure(Number.isFinite(value) && !Object.is(value, -0), 'JSON number must be finite and not negative zero');
    return value;
  }
  if (Array.isArray(value)) {
    ensure(Object.keys(value).length === value.length, 'sparse or extended array');
    return Array.from(value, item => jsonCopy(item, depth + 1));
  }
  ensure(object(value) && Object.getPrototypeOf(value) === Object.prototype, 'plain JSON object required');
  ensure(Reflect.ownKeys(value).length === Object.keys(value).length, 'hidden JSON fields');
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, jsonCopy(item, depth + 1)]));
}

const gate = (check, evaluate) => async (...args) => {
  try {
    const reason = await evaluate(...args);
    return { check, passed: true, reason };
  } catch (error) {
    return { check, passed: false, reason: error instanceof Error ? (error.message || 'check failed without a message') : 'check threw a non-Error value' };
  }
};

export const schemaGate = gate('schema', (context, snapshots = []) => {
  context = jsonCopy(context);
  fields(context, ['version', 'candidate', 'contract', 'cases', 'limits', 'allowedEffects']);
  ensure(context.version === 1 && text(context.candidate), 'version 1 and candidate identity required');
  fields(context.contract, ['version', 'signature', 'refusals', 'tolerance', 'sources']);
  validateContract(context.contract);
  ensure(context.contract.sources.every(text), 'contract sources must be named');
  for (const refusal of context.contract.refusals) fields(refusal, ['path', 'reason']);
  ensure(Array.isArray(context.cases) && context.cases.length > 0, 'nonempty probe cases required');
  const ids = new Set();
  for (const item of context.cases) {
    fields(item, ['id', 'inputs']);
    ensure(text(item.id) && !ids.has(item.id) && object(item.inputs), 'invalid or duplicate probe case');
    ids.add(item.id);
  }
  fields(context.limits, ['wallMs', 'memoryBytes', 'fuel']);
  for (const [name, limit] of Object.entries(context.limits)) {
    ensure(typeof limit === 'number' && Number.isFinite(limit) && limit > 0, `invalid limit: ${name}`);
    if (name !== 'wallMs') ensure(Number.isSafeInteger(limit), `integer limit required: ${name}`);
  }
  effects(context.allowedEffects);
  snapshots.push(context);
  return 'contract and gate input conform to version 1';
});

export const interfaceGate = gate('interface', async (context, port) => {
  const signature = jsonCopy(await port.describe(context.candidate));
  validateSignature(signature);
  ensure(canonical(signature) === canonical(context.contract.signature), 'observed signature differs from contract');
  return 'observed name, types, units and domains match the contract';
});

export const boundsGate = gate('bounds', async (context, port, runs) => {
  for (let round = 0; round < 2; round++) {
    const run = jsonCopy(await port.run(context.candidate, jsonCopy(context.cases), jsonCopy(context.limits)));
    fields(run, ['status', 'outputs', 'usage', 'effects']);
    ensure(run.status === 'completed', `round ${round + 1} did not complete within limits`);
    fields(run.usage, ['wallMs', 'memoryBytes', 'fuel']);
    for (const [name, limit] of Object.entries(context.limits)) {
      const used = run.usage[name];
      ensure(typeof used === 'number' && Number.isFinite(used) && used >= 0, `invalid usage: ${name}`);
      if (name !== 'wallMs') ensure(Number.isSafeInteger(used), `integer usage required: ${name}`);
      ensure(used <= limit, `round ${round + 1} exceeds ${name}`);
    }
    ensure(Array.isArray(run.outputs) && run.outputs.length === context.cases.length, 'one output per probe required');
    for (const [index, output] of run.outputs.entries()) {
      fields(output, Object.hasOwn(output, 'error') ? ['caseId', 'error'] : ['caseId', 'value']);
      ensure(output.caseId === context.cases[index].id, 'output case order or identity differs');
      if (Object.hasOwn(output, 'error')) {
        fields(output.error, ['path', 'reason']);
        ensure(text(output.error.path) && text(output.error.reason), 'refusal path and reason required');
      } else {
        const type = context.contract.signature.output.type;
        ensure(type === 'object' ? object(output.value) : typeof output.value === type, 'output type differs from contract');
      }
    }
    effects(run.effects);
    runs.push(run);
  }
  return 'both fresh runs completed within wall, memory and fuel limits';
});

export const determinismGate = gate('determinism', runs => {
  ensure(runs.length === 2, 'two bounded runs required');
  const outcomes = runs.map(run => canonical(jsonCopy({ outputs: run.outputs, effects: run.effects })));
  ensure(outcomes[0] === outcomes[1], 'repeated outputs, refusals or effects differ');
  return 'repeat outputs, refusals and effects match exactly';
});

export const forbiddenEffectsGate = gate('forbidden_effects', async (context, port, runs) => {
  const scanned = jsonCopy(await port.scanEffects(context.candidate));
  effects(scanned);
  const observed = [...scanned, ...runs.flatMap(run => run.effects)];
  const forbidden = [...new Set(observed.filter(effect => !context.allowedEffects.includes(effect)))].sort();
  ensure(forbidden.length === 0, `forbidden effects: ${forbidden.join(', ')}`);
  return 'static scan and both runtime traces contain only allowed effects';
});

export async function runUniversalGates(input, port) {
  const snapshots = [];
  const results = [await schemaGate(input, snapshots)];
  if (!results[0].passed) return { passed: false, firstFailure: 'schema', results };
  const context = snapshots[0];
  const runs = [];
  const remaining = [
    () => interfaceGate(context, port),
    () => boundsGate(context, port, runs),
    () => determinismGate(runs),
    () => forbiddenEffectsGate(context, port, runs),
  ];
  for (const check of remaining) {
    const result = await check();
    results.push(result);
    if (!result.passed) return { passed: false, firstFailure: result.check, results };
  }
  return { passed: true, firstFailure: null, results };
}
