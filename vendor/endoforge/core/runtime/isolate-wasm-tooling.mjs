const { validate, CompileError, RuntimeError } = WebAssembly;
const refuse = message => { throw new CompileError(message); };
const leb = value => {
  const bytes = [];
  do { const part = value % 128; value = Math.floor(value / 128); bytes.push(part | (value ? 128 : 0)); } while (value);
  return bytes;
};
const order = [1, 2, 3, 4, 5, 13, 6, 7, 8, 9, 12, 10, 11];
const valueTypes = [0x7f, 0x7e, 0x7d, 0x7c, 0x7b, 0x70, 0x6f, 0x69];
const indexed = new Set([0x07, 0x08, 0x09, 0x0c, 0x0d, 0x10, 0x12, 0x14, 0x15, 0x18, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x3f, 0xd2, 0xd4, 0xd6]);
const plain = new Set([0x00, 0x01, 0x05, 0x0a, 0x0b, 0x0f, 0x19, 0x1a, 0x1b, 0xd1, 0xd3, 0xd5]);

export function toolingWasmPolicy(entries, maxMb) {
  if (!Array.isArray(entries)) throw new TypeError('toolingWasmModules must be an array');
  const names = new Set(), hashes = new Set();
  return Object.freeze(entries.map(({ name, sha256, maximumPages } = {}) => {
    if (typeof name !== 'string' || !/^[a-zA-Z0-9._-]{1,100}$/.test(name) ||
        typeof sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(sha256) ||
        !Number.isSafeInteger(maximumPages) || maximumPages < 1 || maximumPages > maxMb * 16 ||
        names.has(name) || hashes.has(sha256)) throw new TypeError('invalid toolingWasmModules entry');
    names.add(name); hashes.add(sha256);
    return Object.freeze({ name, sha256, maximumPages });
  }));
}

export function admitToolingWasm(bytes, entry) {
  if (!validate(bytes)) refuse('invalid wasm module');
  let offset = 8, memories = 0, types = 0, functions = 0, globals = 0;
  const limits = [], exportedMemories = [], names = new Set(), sections = [];
  const byte = () => offset < bytes.length ? bytes[offset++] : refuse('truncated wasm');
  const uint = () => {
    let value = 0;
    for (let i = 0; i < 5; i++) {
      const next = byte();
      value += (next & 127) * 2 ** (7 * i);
      if (!(next & 128)) return value;
    }
    return refuse('invalid wasm integer');
  };
  const skipLeb = (max = 5) => { for (let i = 0; i < max; i++) if (!(byte() & 128)) return; refuse('invalid wasm integer'); };
  const skip = () => { const length = uint(); offset += length; };
  const unsupported = () => refuse('unsupported wasm feature in tooling module');
  const valueType = () => { if (!valueTypes.includes(byte())) unsupported(); };
  const blockType = () => { if ([0x63, 0x64].includes(bytes[offset])) unsupported(); skipLeb(); };
  const memarg = () => { if (uint() & 0x40) uint(); skipLeb(10); };
  const ended = (end, name) => { if (offset !== end) refuse(`malformed ${name} section`); };
  while (offset < bytes.length) {
    const start = offset, id = byte(), size = uint(), end = offset + size;
    const part = { id, start, end, content: offset };
    sections.push(part);
    if (id === 1) {
      for (let count = uint(); count; count--, types++) {
        if (byte() !== 0x60) unsupported();
        for (let j = uint(); j; j--) valueType();
        for (let j = uint(); j; j--) valueType();
      }
      ended(end, 'type');
    } else if (id === 2) {
      for (let count = uint(); count; count--) {
        skip(); skip();
        const kind = byte();
        if (kind === 0) { uint(); functions++; }
        else if (kind === 1) { if (![0x70, 0x6f].includes(byte())) unsupported(); const flag = uint(); if (flag > 1) unsupported(); uint(); if (flag) uint(); }
        else if (kind === 3) { valueType(); byte(); globals++; }
        else if (kind === 4) { byte(); uint(); }
        else unsupported();
      }
      ended(end, 'import');
    } else if (id === 3) functions += uint();
    else if (id === 6) globals += uint();
    else if (id === 7) {
      for (let count = uint(); count; count--) {
        const length = uint(), name = new TextDecoder().decode(bytes.subarray(offset, offset + length));
        offset += length;
        names.add(name);
        const kind = byte(), index = uint();
        if (kind === 2) exportedMemories.push({ name, memory: index });
      }
      ended(end, 'export');
    } else if (id === 5) {
      const entries = [];
      for (let count = uint(); count; count--) {
        if (++memories > 1) unsupported();
        const flag = uint();
        if (flag > 1) unsupported();
        const initial = uint(), maximum = Math.min(flag ? uint() : Infinity, entry.maximumPages);
        if (initial > maximum) refuse('tooling module memory exceeds its pinned maximum');
        limits.push(maximum);
        entries.push(1, ...leb(initial), ...leb(maximum));
      }
      ended(end, 'memory');
      part.replace = [...leb(memories), ...entries];
    }
    offset = end;
  }
  const admitted = { flag: null, start: null, tooling: entry.name, limits, exportedMemories };
  const code = sections.find(part => part.id === 10);
  if (memories && code) {
    let flag = '__ef_grow_failed';
    while (names.has(flag)) flag += '_';
    const helper = functions, flagIndex = globals;
    const call = Uint8Array.from([0x10, ...leb(helper)]);
    offset = code.content;
    const count = uint(), bodies = [];
    for (let i = 0; i < count; i++) {
      const size = uint(), end = offset + size, parts = [];
      let from = offset;
      for (let j = uint(); j; j--) { uint(); valueType(); }
      while (offset < end) {
        const at = offset, op = byte();
        if (op === 0x40) {
          if (uint() !== 0) unsupported();
          parts.push(bytes.subarray(from, at), call);
          from = offset;
        } else if (op >= 0x45 && op <= 0xc4 || plain.has(op)) continue;
        else if (indexed.has(op)) uint();
        else if ([0x02, 0x03, 0x04, 0x06].includes(op)) blockType();
        else if (op === 0x0e) { for (let j = uint() + 1; j; j--) uint(); }
        else if ([0x11, 0x13].includes(op)) { uint(); uint(); }
        else if (op === 0x1c) { for (let j = uint(); j; j--) valueType(); }
        else if (op === 0x1f) {
          blockType();
          for (let j = uint(); j; j--) { const kind = byte(); if (kind > 3) unsupported(); if (kind < 2) uint(); uint(); }
        } else if (op >= 0x28 && op <= 0x3e) memarg();
        else if (op === 0x41) skipLeb();
        else if (op === 0x42) skipLeb(10);
        else if (op === 0x43) offset += 4;
        else if (op === 0x44) offset += 8;
        else if (op === 0xd0) blockType();
        else if (op === 0xfc) {
          const sub = uint();
          if ([8, 10, 12, 14].includes(sub)) { uint(); uint(); }
          else if ([9, 11, 13, 15, 16, 17].includes(sub)) uint();
          else if (sub > 7) unsupported();
        } else if (op === 0xfd) {
          const sub = uint();
          if (sub <= 11 || sub === 92 || sub === 93) memarg();
          else if (sub === 12 || sub === 13) offset += 16;
          else if (sub >= 21 && sub <= 34) offset += 1;
          else if (sub >= 84 && sub <= 91) { memarg(); offset += 1; }
        } else unsupported();
      }
      if (offset !== end) refuse('malformed code section');
      parts.push(bytes.subarray(from, end));
      bodies.push(Uint8Array.from(leb(parts.reduce((total, piece) => total + piece.length, 0))), ...parts);
    }
    ended(code.end, 'code');
    const grow = [0, 1, 1, 0x7f, 0x20, 0, 0x40, 0, 0x22, 1, 0x41, 0x7f, 0x46, 0x04, 0x40, 0x41, 1, 0x24, ...leb(flagIndex), 0x0b, 0x20, 1, 0x0b];
    grow[0] = grow.length - 1;
    const extend = (id, entries) => {
      const part = sections.find(item => item.id === id);
      if (!part) return sections.push({ id, replace: [...leb(1), ...entries] });
      offset = part.content;
      const total = uint() + 1;
      part.replace = [...leb(total), ...bytes.subarray(offset, part.end), ...entries];
    };
    extend(1, [0x60, 1, 0x7f, 1, 0x7f]);
    extend(3, leb(types));
    extend(6, [0x7f, 1, 0x41, 0, 0x0b]);
    extend(7, [...leb(flag.length), ...Buffer.from(flag), 3, ...leb(flagIndex)]);
    code.pieces = [Uint8Array.from(leb(count + 1)), ...bodies, Uint8Array.from(grow)];
    admitted.flag = flag;
  }
  const rank = id => order.indexOf(id);
  const placed = sections.filter(part => part.start !== undefined);
  for (const part of sections.filter(item => item.start === undefined)) {
    const at = placed.findIndex(item => item.id && rank(item.id) > rank(part.id));
    placed.splice(at < 0 ? placed.length : at, 0, part);
  }
  const output = [bytes.subarray(0, 8)];
  for (const part of placed) {
    const pieces = part.pieces ?? (part.replace ? [Uint8Array.from(part.replace)] : null);
    if (!pieces) { output.push(bytes.subarray(part.start, part.end)); continue; }
    output.push(Uint8Array.from([part.id, ...leb(pieces.reduce((total, piece) => total + piece.length, 0))]), ...pieces);
  }
  admitted.bytes = new Uint8Array(output.reduce((total, piece) => total + piece.length, 0));
  output.reduce((at, piece) => { admitted.bytes.set(piece, at); return at + piece.length; }, 0);
  return admitted;
}

export function guardToolingExports(instance, flagName, fail) {
  const flag = flagName ? instance.exports[flagName] : null;
  let depth = 0;
  const trapped = error => {
    if (flag?.value && error instanceof RuntimeError && error.message === 'unreachable') fail();
    throw error;
  };
  const wrap = target => function (...args) {
    if (flag && !depth) flag.value = 0;
    depth++;
    try { return Reflect.apply(target, this, args); } catch (error) { return trapped(error); } finally { depth--; }
  };
  const exports = Object.create(null);
  for (const [name, value] of Object.entries(instance.exports)) {
    if (name !== flagName) exports[name] = typeof value === 'function' ? wrap(value) : value;
  }
  Object.defineProperty(instance, 'exports', { value: Object.freeze(exports), enumerable: true });
}
