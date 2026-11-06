import { createHash } from 'node:crypto';

export const sha256 = data => createHash('sha256').update(data).digest('hex');

export class ToolInputError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

export class KernelRefusal extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

export class KernelFault extends Error {}

export const isObject = value => value !== null && typeof value === 'object' && !Array.isArray(value);
export const keysAre = (value, names) => {
  const keys = Object.keys(value);
  return keys.length === names.length && names.every(name => Object.hasOwn(value, name));
};

export function pyRound(value, places) {
  if (!Number.isFinite(value)) return value;
  const exact = Math.abs(value).toFixed(100);
  const point = exact.indexOf('.');
  const rest = exact.slice(point + 1 + places);
  if (rest[0] === '5' && /^0*$/.test(rest.slice(1))) {
    const kept = exact.slice(0, point + 1 + places);
    const digit = Number(places ? kept.at(-1) : exact[point - 1]);
    const step = 10 ** -places;
    const low = Number(kept);
    const magnitude = digit % 2 === 0 ? low : Number((low + step).toFixed(places));
    return value < 0 ? -magnitude : magnitude;
  }
  return Number(value.toFixed(places));
}

export const rounded = (value, places) => {
  const out = pyRound(value, places);
  return out === 0 ? 0 : out;
};

export function pyFloat(value) {
  if (Object.is(value, -0)) return '-0.0';
  const text = String(value);
  const abs = Math.abs(value);
  if (abs >= 1e16 || (abs !== 0 && abs < 1e-4)) {
    const [mantissa, exponent] = value.toExponential().split('e');
    const sign = exponent[0] === '-' ? '-' : '+';
    return `${mantissa}e${sign}${exponent.replace(/^[-+]/, '').padStart(2, '0')}`;
  }
  return /[.]/.test(text) ? text : `${text}.0`;
}

const escape = text => JSON.stringify(text).replace(/[\u007f-￿]/g, c => `\\u${c.charCodeAt(0).toString(16).padStart(4, '0')}`);
const NUMBER = /-?(?:0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?/y;
const MAX_INTEGER_DIGITS = 4300;
const order = (a, b) => {
  const x = [...a[0]], y = [...b[0]];
  for (let i = 0; i < Math.min(x.length, y.length); i++) {
    const d = x[i].codePointAt(0) - y[i].codePointAt(0);
    if (d) return d;
  }
  return x.length - y.length;
};

export function canonicalPython(argumentsText) {
  let at = 0;
  const space = () => { while (at < argumentsText.length && ' \t\r\n'.includes(argumentsText[at])) at++; };
  const string = () => {
    const start = at++;
    while (argumentsText[at] !== '"') at += argumentsText[at] === '\\' ? 2 : 1;
    return JSON.parse(argumentsText.slice(start, ++at));
  };
  const value = () => {
    space();
    const c = argumentsText[at];
    if (c === '{') {
      at++;
      const fields = new Map();
      space();
      if (argumentsText[at] === '}') { at++; return '{}'; }
      for (;;) {
        space();
        const key = string();
        space();
        at++;
        fields.set(key, value());
        space();
        if (argumentsText[at++] === '}') break;
      }
      return `{${[...fields].sort(order).map(([k, v]) => `${escape(k)}:${v}`).join(',')}}`;
    }
    if (c === '[') {
      at++;
      const items = [];
      space();
      if (argumentsText[at] === ']') { at++; return '[]'; }
      for (;;) {
        items.push(value());
        space();
        if (argumentsText[at++] === ']') break;
      }
      return `[${items.join(',')}]`;
    }
    if (c === '"') return escape(string());
    for (const word of ['true', 'false', 'null']) {
      if (argumentsText.startsWith(word, at)) { at += word.length; return word; }
    }
    NUMBER.lastIndex = at;
    const match = NUMBER.exec(argumentsText);
    at = NUMBER.lastIndex;
    if (match[1] === undefined && match[2] === undefined) {
      if (match[0].length > MAX_INTEGER_DIGITS) throw new KernelRefusal('input_too_large', 'Foundation arguments hold an integer over 4300 digits');
      return match[0] === '-0' ? '0' : match[0];
    }
    const number = Number(match[0]);
    if (!Number.isFinite(number)) throw new KernelRefusal('non_finite', 'Foundation arguments must be finite');
    return pyFloat(number);
  };
  return value();
}

const asciiOnly = value => {
  if (typeof value === 'string') return !/[^\x00-\x7f]/.test(value);
  if (Array.isArray(value)) return value.every(asciiOnly);
  if (value !== null && typeof value === 'object') return Object.entries(value).every(([key, item]) => asciiOnly(key) && asciiOnly(item));
  return true;
};

export function parseArguments(argumentsText) {
  if (typeof argumentsText !== 'string' || argumentsText.length > 65536) throw new KernelRefusal('input_too_large', 'Foundation arguments exceed 65536 characters');
  let value;
  try { value = JSON.parse(argumentsText); }
  catch { throw new KernelRefusal('invalid_json', 'Foundation arguments must be JSON'); }
  if (!asciiOnly(value)) throw new KernelRefusal('non_ascii', 'This kernel route takes ASCII arguments only; use the pinned Foundation through a decision');
  try { return { value, inputSha256: sha256(canonicalPython(argumentsText)) }; }
  catch (error) {
    if (error instanceof RangeError) throw new KernelRefusal('input_too_deep', 'Foundation arguments are nested too deeply');
    throw error;
  }
}
