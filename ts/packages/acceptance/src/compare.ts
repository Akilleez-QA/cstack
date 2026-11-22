// Deep comparison of a kernel's output with the expected value, allowing tolerance_ulps on numbers.
import type { Json } from '@cstack/contracts';

const view = new DataView(new ArrayBuffer(8));
function ordered(x: number): bigint {
  view.setFloat64(0, x);
  const bits = view.getBigInt64(0);
  return bits < 0n ? -(bits & 0x7fffffffffffffffn) : bits;
}

/** Distance in units in the last place between two doubles; Infinity if either is NaN. */
export function ulps(a: number, b: number): number {
  if (Number.isNaN(a) || Number.isNaN(b)) return Infinity;
  if (a === b) return 0;
  const d = ordered(a) - ordered(b);
  return Number(d < 0n ? -d : d);
}

/** Where `actual` first differs from `expect`, or null when they match. */
export function difference(actual: unknown, expect: Json, tolerance: number, at = ''): string | null {
  if (typeof expect === 'number') {
    if (typeof actual !== 'number') return `${at || '/'}: expected a number, got ${describe(actual)}`;
    const d = ulps(actual, expect);
    return d <= tolerance ? null : `${at || '/'}: expected ${expect}, got ${actual}${tolerance ? ` (${d} ulps)` : ''}`;
  }
  if (expect === null || typeof expect !== 'object')
    return actual === expect ? null : `${at || '/'}: expected ${JSON.stringify(expect)}, got ${describe(actual)}`;
  if (Array.isArray(expect)) {
    if (!Array.isArray(actual)) return `${at || '/'}: expected an array, got ${describe(actual)}`;
    if (actual.length !== expect.length) return `${at || '/'}: expected length ${expect.length}, got ${actual.length}`;
    for (let i = 0; i < expect.length; i++) {
      const d = difference(actual[i], expect[i]!, tolerance, `${at}/${i}`);
      if (d) return d;
    }
    return null;
  }
  if (!actual || typeof actual !== 'object' || Array.isArray(actual)) return `${at || '/'}: expected an object, got ${describe(actual)}`;
  const a = actual as Record<string, unknown>;
  const keys = new Set([...Object.keys(a), ...Object.keys(expect)]);
  for (const k of [...keys].sort()) {
    if (!(k in expect)) return `${at}/${k}: unexpected key`;
    const d = difference(a[k], expect[k]!, tolerance, `${at}/${k}`);
    if (d) return d;
  }
  return null;
}

function describe(v: unknown): string {
  const s = JSON.stringify(v);
  return s === undefined ? String(v) : s.length > 80 ? s.slice(0, 77) + '...' : s;
}
