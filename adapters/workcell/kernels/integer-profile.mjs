import { KernelRefusal, ToolInputError, canonicalPython, sha256 } from './common.mjs';

const MAX_TEXT = 65000;
const MAX_DEPTH = 30;
const MAX_NODES = 16000;
const MAX_STRING = 1024;
const MAX_DIGITS = 15;
const MAX_OUTPUT = 1000000;
const INTEGER = /-?(?:0|[1-9][0-9]*)/y;
const PLAIN = /"[^"\\\x00-\x1f]*"/y;
const ESCAPES = { '"': '"', '\\': '\\', '/': '/', b: '\b', f: '\f', n: '\n', r: '\r', t: '\t' };

const refuse = (code, message) => { throw new KernelRefusal(code, message); };
const invalid = () => refuse('invalid_json', 'Foundation arguments must be JSON in the bridge numeric profile');

export function parseProfile(text) {
  if (typeof text !== 'string' || text.length > MAX_TEXT) refuse('input_too_large', `Foundation arguments exceed ${MAX_TEXT} characters`);
  if (/[^\x00-\x7f]/.test(text)) refuse('non_ascii', 'This kernel route takes ASCII arguments only; use the pinned Foundation through a decision');
  let at = 0, nodes = 0;
  const space = () => { while (at < text.length && ' \t\r\n'.includes(text[at])) at++; };
  const node = () => { if (++nodes > MAX_NODES) refuse('input_too_large', `Foundation arguments exceed ${MAX_NODES} JSON nodes`); };
  const string = () => {
    PLAIN.lastIndex = at;
    const plain = PLAIN.exec(text);
    let out;
    if (plain) { at = PLAIN.lastIndex; out = plain[0].slice(1, -1); }
    else {
      out = '';
      at++;
      for (;;) {
        if (at >= text.length || text.charCodeAt(at) < 0x20) invalid();
        const c = text[at++];
        if (c === '"') break;
        if (c !== '\\') { out += c; continue; }
        const e = text[at++];
        if (e === 'u') refuse('non_ascii', 'This kernel route takes no unicode escapes; use the pinned Foundation through a decision');
        if (!Object.hasOwn(ESCAPES, e ?? '')) invalid();
        out += ESCAPES[e];
      }
    }
    if (out.length > MAX_STRING) refuse('input_too_large', `Foundation arguments hold a string over ${MAX_STRING} characters`);
    return out;
  };
  const value = depth => {
    space();
    const c = text[at];
    node();
    if (c === '{' || c === '[') {
      if (depth >= MAX_DEPTH) refuse('input_too_deep', `Foundation arguments nest deeper than ${MAX_DEPTH}`);
      at++;
      space();
      if (c === '{') {
        const map = new Map();
        if (text[at] === '}') { at++; return map; }
        for (;;) {
          space();
          if (text[at] !== '"') invalid();
          const key = string();
          node();
          if (map.has(key)) refuse('duplicate_key', 'Foundation arguments repeat an object key');
          space();
          if (text[at++] !== ':') invalid();
          map.set(key, value(depth + 1));
          space();
          const next = text[at++];
          if (next === '}') return map;
          if (next !== ',') invalid();
        }
      }
      const list = [];
      if (text[at] === ']') { at++; return list; }
      for (;;) {
        list.push(value(depth + 1));
        space();
        const next = text[at++];
        if (next === ']') return list;
        if (next !== ',') invalid();
      }
    }
    if (c === '"') return string();
    for (const [word, literal] of [['true', true], ['false', false], ['null', null]]) {
      if (text.startsWith(word, at)) { at += word.length; return literal; }
    }
    INTEGER.lastIndex = at;
    const match = INTEGER.exec(text);
    if (!match) invalid();
    at = INTEGER.lastIndex;
    if (at < text.length && '.eE'.includes(text[at])) refuse('not_integer', 'This Foundation takes bounded integers only');
    if (match[0].replace('-', '').length > MAX_DIGITS) refuse('integer_too_large', `Foundation arguments hold an integer over ${MAX_DIGITS} digits`);
    const number = Number(match[0]);
    return number === 0 ? 0 : number;
  };
  const parsed = value(0);
  space();
  if (at !== text.length) invalid();
  if (!(parsed instanceof Map)) refuse('invalid_arguments', 'Tool arguments must be a JSON object');
  return { value: parsed, inputSha256: sha256(canonicalPython(text)) };
}

export function boundedOutput(receipt, inputLength) {
  if (inputLength > 8192 && JSON.stringify(receipt).length > MAX_OUTPUT) refuse('output_too_large', 'The receipt would exceed the bridge output limit');
  return receipt;
}

export const fail = message => { throw new ToolInputError('invalid', message); };

const pyString = text => {
  const quote = text.includes("'") && !text.includes('"') ? '"' : "'";
  let out = quote;
  for (const c of text) {
    if (c === '\\') out += '\\\\';
    else if (c === quote) out += `\\${c}`;
    else if (c === '\n') out += '\\n';
    else if (c === '\r') out += '\\r';
    else if (c === '\t') out += '\\t';
    else if (c < ' ' || c === '\x7f') out += `\\x${c.charCodeAt(0).toString(16).padStart(2, '0')}`;
    else out += c;
  }
  return out + quote;
};
export const pyList = items => `[${items.map(pyString).join(', ')}]`;
export const sorted = items => [...items].sort();

export function exact(value, name, required, optional = []) {
  if (!(value instanceof Map)) fail(`${name} must be an object`);
  const missing = required.filter(key => !value.has(key));
  const extra = [...value.keys()].filter(key => !required.includes(key) && !optional.includes(key));
  if (missing.length || extra.length) fail(`${name} fields: missing ${pyList(sorted(missing))}, unexpected ${pyList(sorted(extra))}`);
  return value;
}

export function integer(value, name, lo, hi) {
  if (typeof value !== 'number' || value < lo || value > hi) fail(`${name} must be an integer from ${lo} to ${hi}`);
  return value;
}

export const MEASURE_LIMIT = 10 ** 12;
export const measure = (value, name) => integer(value, name, -MEASURE_LIMIT, MEASURE_LIMIT);

export const ID = /^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,63}$/;
export const ID_TEXT = '[A-Za-z0-9][A-Za-z0-9:_.\\-]{0,63}\\Z';
export function identifier(value, name, pattern = ID, text = ID_TEXT) {
  if (typeof value !== 'string' || !pattern.test(value)) fail(`${name} must match ${text}`);
  return value;
}

export function array(value, name, min, max) {
  if (!Array.isArray(value) || value.length < min || value.length > max) fail(`${name} must be a list of ${min} to ${max} items`);
  return value;
}

export const check = (name, value, lo = null, hi = null) => ({ check: name, value, min: lo, max: hi,
  status: value === null ? 'not_measured' : (lo === null || value >= lo) && (hi === null || value <= hi) ? 'pass' : 'fail' });

export function verdict(checks) {
  if (checks.some(c => c.status === 'fail')) return 'thresholds_not_met';
  return !checks.length || checks.some(c => c.status === 'not_measured') ? 'not_scored' : 'thresholds_met';
}

export const get = (map, key, fallback) => (map.has(key) ? map.get(key) : fallback);
export const evidence = (applies_to, kind, source, note, status) => ({ applies_to, evidence: { basis: { kind, source, note }, status } });
