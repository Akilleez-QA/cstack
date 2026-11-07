import { compile, compilerIdentity, warmCompiler } from './compiler.mjs';
import { admit, Broker, instantiate } from './broker.mjs';
import { judge } from './kernels/judge.mjs';
import { loadFoundation } from './kernels/registry.mjs';
import { KernelFault, KernelRefusal, sha256 } from './kernels/common.mjs';

const MAX_STEPS = 8;
const MAX_TRANSITION = 1048576;
const EFFECT_FIELDS = ['capability', 'operation', 'payload'];
const PROPOSAL_FIELDS = ['capability_id', 'operation', 'arguments', 'expected_observation', 'success_boundary', 'failure_meaning'];
const kernelFailure = error => error instanceof SyntaxError || error instanceof WebAssembly.RuntimeError || error instanceof WebAssembly.LinkError ||
  error instanceof RangeError || error instanceof KernelRefusal || error instanceof KernelFault;
const closedObject = (value, fields) => value !== null && typeof value === 'object' && !Array.isArray(value) &&
  Object.keys(value).length === fields.length && fields.every(field => Object.hasOwn(value, field));

export async function warm({ foundations = [] } = {}) {
  await warmCompiler();
  for (const id of foundations) await loadFoundation(id);
  await compile('export function warm(): i32 { return 1; }');
}

export async function createPort({ task, sources, granted, signature, allowDecisions = true }, { hostCall }) {
  const compiled = new Map();
  const proposals = new Map();
  const outputs = new Map();
  const diagnostics = {};
  const runs = [];
  const windowStart = process.hrtime.bigint();
  const broker = await Broker.open(granted);
  const compiler = compilerIdentity();

  const artifact = async candidate => {
    if (compiled.has(candidate)) return compiled.get(candidate);
    const source = sources[candidate];
    if (typeof source !== 'string') throw new Error('no source for candidate');
    if (`cand:${sha256(`${task}\n${source}`)}` !== candidate) throw new Error('candidate source differs from its durable identity');
    const started = performance.now();
    const { wasm, diagnostics: text } = await compile(source);
    const record = { wasm: null, module: null, admission: null, compile_ms: performance.now() - started };
    if (wasm) {
      record.wasm = wasm;
      record.wasm_sha256 = sha256(wasm);
      try {
        record.module = new WebAssembly.Module(wasm);
        record.admission = admit(record.module, granted);
      } catch (error) {
        if (!(error instanceof WebAssembly.CompileError)) throw error;
        record.wasm = null;
        diagnostics[candidate] = error.message.slice(0, 400);
      }
    } else diagnostics[candidate] = text;
    compiled.set(candidate, record);
    return record;
  };

  const propose = async (candidate, effect) => {
    const key = sha256(JSON.stringify(effect));
    if (!proposals.has(key)) {
      proposals.set(key, await hostCall({ kind: 'propose_decision', candidate, proposal: effect.payload }));
    }
    return proposals.get(key);
  };

  const dispatch = async (candidate, effect, names) => {
    if (!closedObject(effect, EFFECT_FIELDS) || effect.capability !== 'poodo' || effect.operation !== 'propose_decision' ||
        !closedObject(effect.payload, PROPOSAL_FIELDS)) {
      names.push('effect:refused');
      const refused = { accepted: false, reason: 'effect_outside_closed_schema' };
      proposals.set(sha256(JSON.stringify(effect)), refused);
      return refused;
    }
    if (!allowDecisions) { names.push('decision:refused'); return { accepted: false, reason: 'decisions_not_allowed' }; }
    const answer = await propose(candidate, effect);
    if (answer?.accepted !== true) { names.push('decision:refused'); return { accepted: false, reason: String(answer?.reason ?? 'refused') }; }
    names.push('decision:accepted');
    return answer;
  };

  const step = (record, eventText) => {
    const cell = instantiate(record.module, broker, eventText);
    cell.exports.reduce();
    const text = cell.emitted();
    if (typeof text !== 'string' || text.length > MAX_TRANSITION) throw new SyntaxError('kernel emitted no bounded transition');
    return { transition: JSON.parse(text), memoryBytes: cell.memoryBytes() };
  };

  const runCase = async (candidate, record, item, names) => {
    let memoryBytes = 0;
    let event = { kind: 'case', state: null, inputs: item.inputs };
    for (let index = 0; index < MAX_STEPS; index++) {
      let out;
      try { out = step(record, JSON.stringify(event)); }
      catch (error) {
        if (kernelFailure(error)) {
          names.push('kernel:invalid');
          return { memoryBytes, output: { caseId: item.id, error: { path: 'kernel', reason: error.message.slice(0, 200) } } };
        }
        throw error;
      }
      memoryBytes = Math.max(memoryBytes, out.memoryBytes);
      const { transition } = out;
      const effects = transition?.effects;
      if (effects === undefined || effects === null || (Array.isArray(effects) && !effects.length)) {
        const output = Object.hasOwn(transition ?? {}, 'error') ? { caseId: item.id, error: transition.error } : { caseId: item.id, value: transition?.value };
        return { memoryBytes, output };
      }
      if (!Array.isArray(effects) || effects.length > 8) { names.push('effect:refused'); return { memoryBytes, output: { caseId: item.id, error: { path: 'effects', reason: 'effects must be a bounded list' } } }; }
      const results = [];
      for (const effect of effects) results.push(await dispatch(candidate, effect, names));
      event = { kind: 'effect_results', state: transition.state ?? null, inputs: item.inputs, results };
    }
    names.push('kernel:invalid');
    return { memoryBytes, output: { caseId: item.id, error: { path: 'kernel', reason: 'too many steps' } } };
  };

  return {
    async describe(candidate) {
      const record = await artifact(candidate);
      if (!record.wasm) return { version: 1, name: 'compile_failed', inputs: [], output: { type: 'object', unit: 'diagnostics' } };
      if (record.admission.refused.length) return signature;
      if (!record.admission.closed) return { version: 1, name: 'exports_refused', inputs: [], output: { type: 'object', unit: record.admission.exports.join('.') || 'none' } };
      try {
        const cell = instantiate(record.module, broker, '{"kind":"describe"}');
        cell.exports.signature();
        return JSON.parse(cell.emitted());
      } catch (error) {
        if (kernelFailure(error)) return { version: 1, name: 'signature_failed', inputs: [], output: { type: 'object', unit: 'diagnostics' } };
        throw error;
      }
    },
    async run(candidate, cases, limits) {
      const started = performance.now();
      const record = await artifact(candidate);
      if (!record.wasm || record.admission.refused.length) {
        return { status: 'completed', outputs: cases.map(item => ({ caseId: item.id, error: { path: 'kernel', reason: 'not admitted' } })),
          usage: { wallMs: 0, memoryBytes: 0, fuel: 0 }, effects: record.admission ? record.admission.refused.map(name => `import:${name.split('.')[0]}`) : ['compile:failed'] };
      }
      const names = [];
      const results = [];
      let memoryBytes = 0;
      const callsBefore = broker.calls;
      const refusedBefore = broker.refused;
      for (const item of cases) {
        const { output, memoryBytes: used } = await runCase(candidate, record, item, names);
        results.push(output);
        memoryBytes = Math.max(memoryBytes, used);
      }
      if (broker.refused > refusedBefore) names.push('foundation:refused');
      outputs.set(candidate, results);
      runs.push({ candidate, wall_ms: performance.now() - started, calls: broker.calls - callsBefore });
      return { status: 'completed', outputs: results,
        usage: { wallMs: performance.now() - started, memoryBytes, fuel: broker.calls - callsBefore }, effects: [...new Set([...names, ...broker.used])].sort() };
    },
    async scanEffects(candidate) {
      const record = await artifact(candidate);
      if (!record.wasm) return ['compile:failed'];
      return [...record.admission.refused.map(name => `import:${name.split('.')[0]}`), ...record.admission.foundations.map(id => `import:${id}`)].sort();
    },
    async invariant(name, candidate) {
      const record = await artifact(candidate);
      if (name === 'declared_imports') {
        return record.admission?.refused.length === 0 ? { passed: true, reason: 'the binary imports only what the grant declares' } : { passed: false, reason: 'the binary imports something undeclared' };
      }
      if (name === 'foundation_pins') {
        for (const id of granted) await loadFoundation(id);
        return { passed: true, reason: 'granted Foundations match their pins' };
      }
      return { passed: false, reason: `unknown invariant ${name}` };
    },
    async residual(candidate, bundle) {
      return judge(JSON.parse(bundle.residual).checks, outputs.get(candidate) ?? []);
    },
    async measure(candidate) {
      const record = await artifact(candidate);
      return { wasm_bytes: record.wasm.length };
    },
    evidence() {
      const artifacts = Object.fromEntries([...compiled].map(([candidate, record]) => [candidate, { wasm_sha256: record.wasm_sha256 ?? null, compile_ms: record.compile_ms, imports: record.admission?.foundations ?? [], refused: record.admission?.refused ?? [] }]));
      return { compiler, foundations: broker.identities(), broker: broker.report(), artifacts, runs, diagnostics, proposals: [...proposals.values()],
        window_ns: [String(windowStart), String(process.hrtime.bigint())], pid: process.pid };
    },
  };
}
