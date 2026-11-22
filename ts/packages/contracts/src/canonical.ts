// The v1 canonical form, byte for byte the same as Python's poodo_core.models.canonical:
// json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).
// This port is float-free: any number that isn't a safe integer is refused, so no float
// formatting has to match. Golden vectors from Python pin the bytes (packages/intent/vectors).
import { createHash } from 'node:crypto';

export const MAX_DOCUMENT_BYTES = 2_097_152;
const MAX_DEPTH = 128;
const MAX_NODES = 200_000;

export class ContractError extends Error {}

// Python sorts str keys by code point; JS sorts by UTF-16 unit. They differ for astral keys.
function byCodePoint(a: string, b: string): number {
  const x = [...a], y = [...b];
  for (let i = 0; i < Math.min(x.length, y.length); i++) {
    const d = x[i]!.codePointAt(0)! - y[i]!.codePointAt(0)!;
    if (d) return d;
  }
  return x.length - y.length;
}

// JSON.stringify already escapes " \ and C0 controls the way Python does, and lone
// surrogates as \udxxx. ensure_ascii also escapes DEL and everything above it.
function quote(s: string): string {
  return JSON.stringify(s).replace(/[\u007f-￿]/g, (c) => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0'));
}

export function canonical(value: unknown): string {
  let nodes = 0;
  const parts: string[] = [];
  const walk = (item: unknown, depth: number): void => {
    if (++nodes > MAX_NODES || depth > MAX_DEPTH) throw new ContractError('Document structure exceeds core budget');
    if (item === null) parts.push('null');
    else if (item === true) parts.push('true');
    else if (item === false) parts.push('false');
    else if (typeof item === 'string') parts.push(quote(item));
    else if (typeof item === 'number') {
      if (!Number.isSafeInteger(item)) throw new ContractError('Only safe integers are admitted (the intent contract has no floats)');
      parts.push(Object.is(item, -0) ? '0' : String(item));
    } else if (Array.isArray(item)) {
      parts.push('[');
      item.forEach((v, i) => { if (i) parts.push(','); walk(v, depth + 1); });
      parts.push(']');
    } else if (typeof item === 'object' && Object.getPrototypeOf(item) === Object.prototype) {
      const record = item as Record<string, unknown>;
      parts.push('{');
      Object.keys(record).sort(byCodePoint).forEach((k, i) => {
        if (i) parts.push(',');
        parts.push(quote(k), ':');
        walk(record[k], depth + 1);
      });
      parts.push('}');
    } else throw new ContractError('Only explicit JSON values are admitted');
  };
  walk(value, 0);
  const text = parts.join('');
  if (text.length > MAX_DOCUMENT_BYTES) throw new ContractError('Document exceeds core byte budget');
  return text;
}

export function digest(value: unknown): string {
  return createHash('sha256').update(canonical(value), 'ascii').digest('hex');
}

const INTEGER_TEXT = /^-?(?:0|[1-9][0-9]*)$/;

/**
 * JSON.parse that refuses any number written as a float or beyond 2^53 - 1. Plain JSON.parse turns
 * `1.0` into 1, which would digest as `1` where Python digests `1.0`: a silent mismatch. Every intent
 * entry read from disk or the wire goes through this.
 */
export function parseStrict(text: string): unknown {
  return JSON.parse(text, function (this: unknown, _key: string, value: unknown, context?: { source?: string }) {
    if (typeof value === 'number') {
      const source = context?.source;
      if (source === undefined) throw new ContractError('This runtime cannot check number text (needs JSON.parse source access)');
      if (!INTEGER_TEXT.test(source) || !Number.isSafeInteger(value))
        throw new ContractError(`Only safe integers are admitted (the intent contract has no floats): ${source}`);
    }
    return value;
  });
}
