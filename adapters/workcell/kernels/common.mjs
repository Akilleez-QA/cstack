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

export function canonicalPython(argumentsText) {
  let at = 0;
  const space = () => { while (' \t\r\n'.includes(argumentsText[at]) && at < argumentsText.length) at++; };
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
      const fields = [];
      space();
      if (argumentsText[at] === '}') { at++; return '{}'; }
      for (;;) {
        space();
        const key = string();
        space();
        at++;
        fields.push([key, value()]);
        space();
        if (argumentsText[at++] === '}') break;
      }
      const order = (a, b) => {
        const x = [...a[0]], y = [...b[0]];
        for (let i = 0; i < Math.min(x.length, y.length); i++) {
          const d = x[i].codePointAt(0) - y[i].codePointAt(0);
          if (d) return d;
        }
        return x.length - y.length;
      };
      return `{${fields.sort(order).map(([k, v]) => `${escape(k)}:${v}`).join(',')}}`;
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
    const match = /^(?:true|false|null|-?(?:0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?)/.exec(argumentsText.slice(at, at + 400));
    if (!match) throw new KernelRefusal('invalid_json', 'Foundation arguments must be JSON');
    at += match[0].length;
    if (match[1] === undefined && match[2] === undefined) return match[0];
    return pyFloat(Number(match[0]));
  };
  const text = value();
  space();
  if (at !== argumentsText.length) throw new KernelRefusal('invalid_json', 'Foundation arguments must be one JSON value');
  return text;
}

export function parseArguments(argumentsText) {
  if (typeof argumentsText !== 'string' || argumentsText.length > 65536) throw new KernelRefusal('input_too_large', 'Foundation arguments exceed 65536 characters');
  if (/[^\x00-\x7f]/.test(argumentsText) || /\\u/.test(argumentsText)) throw new KernelRefusal('non_ascii', 'This kernel route takes ASCII arguments only; use the pinned Foundation through a decision');
  let value;
  try { value = JSON.parse(argumentsText, (key, item) => { if (key === '__proto__') throw new Error('reserved key'); return item; }); }
  catch { throw new KernelRefusal('invalid_json', 'Foundation arguments must be JSON'); }
  return { value, inputSha256: sha256(canonicalPython(argumentsText)) };
}
