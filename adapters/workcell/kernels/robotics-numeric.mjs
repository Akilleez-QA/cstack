import { KernelRefusal } from './common.mjs';
import { array, fail, get, integer, measure, pyList, sorted, exact } from './integer-profile.mjs';

const NUDGE = 2 ** -49;
const PATTERNS = 8;
let mode = 0, counter = 0, state = 0, used = 0;

const nudged = (value, family) => {
  used += 1;
  if (mode === 0 || value === 0 || !Number.isFinite(value)) return value;
  counter += 1;
  let up;
  if (mode === 1) up = true;
  else if (mode === 2) up = false;
  else if (mode === 3) up = counter % 2 === 0;
  else if (mode === 4) up = counter % 2 === 1;
  else if (mode === 5) up = family % 2 === 0;
  else if (mode === 6) up = family % 2 === 1;
  else {
    state = (Math.imul(state, 1103515245) + 12345) & 0x7fffffff;
    up = ((state >> 16) & 1) === (mode === 7 ? 0 : 1);
  }
  return value * (up ? 1 + NUDGE : 1 - NUDGE);
};

export const lib = {
  sin: x => (x === 0 ? x : nudged(Math.sin(x), 0)),
  cos: x => (x === 0 ? 1 : nudged(Math.cos(x), 1)),
  atan2: (y, x) => (y === 0 || x === 0 ? Math.atan2(y, x) : nudged(Math.atan2(y, x), 2)),
  pow: (x, y) => (x === 1 || x === 0 || y === 0 ? x ** y : nudged(Math.pow(x, y), 3)),
  sq: x => (Number.isInteger(x) && Math.abs(x) < 2 ** 26 ? x * x : nudged(x * x, 3)),
  dist: (p, q) => {
    let total = 0;
    for (let i = 0; i < p.length; i++) total += (p[i] - q[i]) * (p[i] - q[i]);
    return nudged(Math.sqrt(total), 4);
  },
};

export function guarded(enabled, evaluate) {
  mode = 0;
  used = 0;
  const first = evaluate();
  if (!enabled || used === 0) return first;
  const text = JSON.stringify(first);
  try {
    for (let pattern = 1; pattern <= PATTERNS; pattern++) {
      mode = pattern;
      counter = 0;
      state = pattern;
      if (JSON.stringify(evaluate()) !== text) throw new KernelRefusal('numeric_boundary', 'This result sits so close to a rounding or branch boundary that Python and JS libm could differ; use the pinned Foundation through a decision');
    }
  } finally { mode = 0; }
  return first;
}

export function pySum(values) {
  let total = 0, carry = 0;
  for (const x of values) {
    const t = total + x;
    carry += Math.abs(total) >= Math.abs(x) ? (total - t) + x : (x - t) + total;
    total = t;
  }
  return carry && Number.isFinite(carry) ? total + carry : total;
}

export const mean = values => (values.length ? pySum(values) / values.length : null);

export function roundHalfEven(x) {
  const floor = Math.floor(x), part = x - floor;
  if (part < 0.5) return floor;
  if (part > 0.5) return floor + 1;
  return floor % 2 === 0 ? floor : floor + 1;
}

export function rnd(x) {
  if (x === null || x === undefined) return null;
  if (!Number.isFinite(x)) fail('a derived value is not finite; check the inputs');
  const value = Math.min(10 ** 12, Math.floor(Math.abs(x) + 0.5));
  return x >= 0 || value === 0 ? value : -value;
}

export const COORD_LIMIT = 10 ** 9;
const EXACT_COORD = 2 ** 25;
export const STANDARD_GRAVITY = 9806.65;
const UP_AXES = { y: 1, z: 2 };

export const positive = (value, name, hi = 10 ** 12) => integer(value, name, 1, hi);

export function choice(value, name, options) {
  if (typeof value !== 'string' || !options.includes(value)) fail(`${name} must be one of ${pyList(sorted(options))}`);
  return value;
}

export const vec3 = (value, name, limit = COORD_LIMIT) => array(value, name, 3, 3).map((v, i) => integer(v, `${name}[${i}]`, -limit, limit));

export function exactCoordinates(point) {
  if (point.some(c => Math.abs(c) > EXACT_COORD)) throw new KernelRefusal('outside_domain', `This route takes coordinates up to ${EXACT_COORD} here, where products stay exact; use the pinned Foundation through a decision`);
  return point;
}

export function uniqueIds(items, name, id = item => item.get('id')) {
  const ids = items.map(id);
  if (new Set(ids).size !== ids.length) fail(`${name} must not repeat an id`);
  return ids;
}

export const gravity = args => (args.has('gravity_mm_s2') ? [positive(args.get('gravity_mm_s2'), 'gravity_mm_s2', 10 ** 6), 'caller'] : [STANDARD_GRAVITY, 'standard']);
export const upAxis = args => UP_AXES[choice(get(args, 'up_axis', 'y'), 'up_axis', Object.keys(UP_AXES))];
export const ground = (point, up) => point.filter((_, i) => i !== up);

export function thresholds(args, defaults) {
  const supplied = exact(get(args, 'thresholds', new Map()), 'thresholds', [], Object.keys(defaults));
  const values = {}, sources = {};
  for (const [key, fallback] of Object.entries(defaults)) {
    if (supplied.has(key)) { values[key] = measure(supplied.get(key), `thresholds.${key}`); sources[key] = 'caller'; }
    else { values[key] = fallback; sources[key] = 'default'; }
  }
  return [values, sources];
}

export function percentile(values, share) {
  const ordered = [...values].sort((a, b) => a - b);
  return ordered[Math.max(0, Math.ceil(share * ordered.length) - 1)];
}
