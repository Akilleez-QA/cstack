// Seeded random inputs for property tests. The domain is a small grammar, and an unknown term
// is an error, so a typo can't quietly turn a property test into one that never runs.
//
//   "i8" "u8" "i16" "u16" "i32" "u32" "bool"   one value of that type
//   "int[a..b]"                                an integer from a to b inclusive
//   "<scalar>[m..n]"                           an array of m to n of them, e.g. "i32[0..1024]"
//   {"const": v}                               exactly v
//   [d1, d2]  /  {"k": d}                      a tuple / an object of samples
//   numbers, booleans and null                 themselves
import { createHash } from 'node:crypto';
import type { Json } from '@cstack/contracts';

const RANGES: Record<string, [number, number]> = {
  i8: [-128, 127], u8: [0, 255], i16: [-32768, 32767], u16: [0, 65535],
  i32: [-2147483648, 2147483647], u32: [0, 4294967295], bool: [0, 1],
};
const TERM = /^(?:(i8|u8|i16|u16|i32|u32|bool)|int\[(-?\d+)\.\.(-?\d+)\])(?:\[(\d+)\.\.(\d+)\])?$/;

export type Rand = () => number;

/** mulberry32, seeded from text: the same intent and test always get the same inputs. */
export function seeded(text: string): { seed: number; rand: Rand } {
  const seed = createHash('sha256').update(text).digest().readUInt32BE(0);
  let a = seed;
  const rand = () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  return { seed, rand };
}

// A fifth of draws land on an edge (lo, hi, 0, ±1 when in range): that is where kernels break.
function int(lo: number, hi: number, rand: Rand): number {
  if (rand() < 0.2) {
    const edges = [lo, hi, 0, 1, -1].filter((e) => e >= lo && e <= hi);
    return edges[Math.floor(rand() * edges.length)]!;
  }
  return lo + Math.floor(rand() * (hi - lo + 1));
}

export class DomainError extends Error {}

export function draw(domain: Json, rand: Rand): Json {
  if (domain === null || typeof domain === 'number' || typeof domain === 'boolean') return domain;
  if (Array.isArray(domain)) return domain.map((d) => draw(d, rand));
  if (typeof domain === 'object') {
    const keys = Object.keys(domain);
    if (keys.length === 1 && keys[0] === 'const') return domain.const!;
    return Object.fromEntries(keys.map((k) => [k, draw(domain[k]!, rand)]));
  }
  const m = TERM.exec(domain);
  if (!m) throw new DomainError(`unknown domain term "${domain}"`);
  const [lo, hi] = m[1] ? RANGES[m[1]]! : [Number(m[2]), Number(m[3])];
  if (!(lo <= hi)) throw new DomainError(`empty range in "${domain}"`);
  const one = () => (m[1] === 'bool' ? int(0, 1, rand) === 1 : int(lo, hi, rand));
  if (m[4] === undefined) return one();
  const n = int(Number(m[4]), Number(m[5]), rand);
  return Array.from({ length: n }, one);
}
