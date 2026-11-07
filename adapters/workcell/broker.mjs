import { KernelRefusal, sha256 } from './kernels/common.mjs';
import { loadFoundation } from './kernels/registry.mjs';

const MAX_CALLS = 65536;
const MAX_ATTRIBUTIONS = 64;
export const KERNEL_MODULE = 'kernel';
const KERNEL_IMPORTS = { event_size: 'function', event_read: 'function', emit: 'function', result_size: 'function', result_read: 'function' };
const FOUNDATION_IMPORT = /^foundation_[a-z]+$/;
const GUARD_EXPORT = /^__ef_(memory_limit|start)_*$/;

export function admit(module, granted) {
  const refused = [], foundations = new Set();
  for (const { module: from, name, kind } of WebAssembly.Module.imports(module)) {
    if (from === KERNEL_MODULE && KERNEL_IMPORTS[name] === kind) continue;
    if (FOUNDATION_IMPORT.test(from) && name === 'call' && kind === 'function' && granted.includes(from)) {
      foundations.add(from);
      continue;
    }
    refused.push(`${from}.${name}`);
  }
  const exports = WebAssembly.Module.exports(module).map(entry => entry.name).filter(name => !GUARD_EXPORT.test(name)).sort();
  const closed = exports.join() === 'memory,reduce,signature';
  return { refused, foundations: [...foundations], closed, exports };
}

export class Broker {
  #foundations;
  #used = new Set();
  #calls = 0;
  #attributions = [];
  #refusals = [];
  #elapsedNs = 0n;
  #omitted = 0;
  constructor(foundations) { this.#foundations = foundations; }

  static async open(granted) {
    const foundations = new Map();
    for (const id of granted) {
      const foundation = await loadFoundation(id);
      if (foundation) foundations.set(id, foundation);
    }
    return new Broker(foundations);
  }

  get used() { return [...this.#used].map(id => `import:${id}`); }
  get calls() { return this.#calls; }
  identities() { return Object.fromEntries([...this.#foundations].map(([id, f]) => [id, f.identity])); }
  report() { return { calls: this.#calls, foundation_ns: String(this.#elapsedNs), attributions: this.#attributions, attributions_omitted: this.#omitted, refusals: this.#refusals }; }

  call(id, tool, argumentsText) {
    if (++this.#calls > MAX_CALLS) throw new KernelRefusal('host_call_limit', 'kernel exceeded its Foundation call limit');
    const foundation = this.#foundations.get(id);
    if (!foundation) {
      this.#refusals.push({ foundation: id, tool, code: 'not_granted' });
      return null;
    }
    this.#used.add(id);
    const started = process.hrtime.bigint();
    try {
      const receipt = foundation.run(tool, argumentsText);
      const text = JSON.stringify(receipt);
      this.#elapsedNs += process.hrtime.bigint() - started;
      if (this.#attributions.length < MAX_ATTRIBUTIONS) {
        this.#attributions.push({ foundation: id, version: foundation.identity.version, route: foundation.identity.route, port_sha256: foundation.identity.port_sha256,
          source_manifest_sha256: foundation.identity.source_manifest_sha256, tool, input_sha256: receipt.input_sha256, output_sha256: sha256(text) });
      } else this.#omitted += 1;
      return text;
    } catch (error) {
      if (!(error instanceof KernelRefusal)) throw error;
      this.#refusals.push({ foundation: id, tool, code: error.code });
      return null;
    }
  }
}

export function instantiate(module, broker, eventText) {
  const encoder = new TextEncoder(), decoder = new TextDecoder();
  const eventBytes = encoder.encode(eventText);
  const results = [];
  let memory, emitted = null;
  const read = (pointer, length) => decoder.decode(new Uint8Array(memory.buffer, pointer, length));
  const imports = { kernel: {
    event_size: () => eventBytes.length,
    event_read: pointer => { new Uint8Array(memory.buffer, pointer, eventBytes.length).set(eventBytes); },
    emit: (pointer, length) => { emitted = read(pointer, length); },
    result_size: handle => results[handle].length,
    result_read: (handle, pointer) => { new Uint8Array(memory.buffer, pointer, results[handle].length).set(results[handle]); },
  } };
  for (const { module: from, name } of WebAssembly.Module.imports(module)) {
    if (from === 'kernel' || name !== 'call') continue;
    imports[from] ||= { call: (tool, toolLength, args, argsLength) => {
      const text = broker.call(from, read(tool, toolLength), read(args, argsLength));
      if (text === null) return -1;
      results.push(encoder.encode(text));
      return results.length - 1;
    } };
  }
  const instance = new WebAssembly.Instance(module, imports);
  memory = instance.exports.memory;
  return { exports: instance.exports, memoryBytes: () => memory.buffer.byteLength, emitted: () => emitted };
}
