export const TUNER_DEFAULTS = Object.freeze({ min: 1, gain: 0.03, marginal: 0.25, keep: 0.98, costRise: 0.15, drift: 0.25, driftWindows: 5, holdMs: 60000, boundsWindows: 2 });

export function createTuner({ start, max, now = () => performance.now(), ...options } = {}) {
  const o = { ...TUNER_DEFAULTS, ...options };
  if (!Number.isSafeInteger(max) || max < o.min) throw new TypeError('tuner needs an integer max of at least min');
  let bound = Math.max(o.min, Math.min(max, Math.round(o.bound ?? max))), width = Math.max(o.min, Math.min(bound, Math.round(start ?? bound)));
  let phase = 'explore', step, anchor, table, tried, visited, skip = true, settled = null, strays = 0, pendingBound = null, pendingCount = 0, lastChange = -Infinity;
  const history = [];
  const begin = from => { phase = 'explore'; anchor = from; step = Math.max(1, Math.ceil(from / 4)); table = new Map(); tried = new Set(); visited = new Set([from]); settled = null; strays = 0; };
  begin(width);
  const move = (to, why) => {
    if (to === width) return width;
    history.push({ at: now(), from: width, to, why, phase });
    width = to;
    skip = true;
    lastChange = now();
    return width;
  };
  const perCell = () => Math.max(...[...table].map(([w, m]) => m.rate / w));
  const best = () => Math.max(...[...table.values()].map(m => m.rate));
  const grows = (probe, base, added) => probe.rate >= base.rate * (1 + o.gain) && (probe.rate - base.rate) / added >= o.marginal * perCell()
    && !(probe.cpu > base.cpu * (1 + o.costRise) && probe.rate < base.rate * (1 + 2 * o.gain));
  const keeps = probe => probe.rate >= o.keep * best();
  const next = () => {
    for (;;) {
      const up = Math.min(bound, anchor + step), down = Math.max(o.min, anchor - step);
      for (const candidate of [up, down]) {
        if (candidate === anchor || tried.has(candidate)) continue;
        if (!table.has(candidate)) return move(candidate, 'probe');
        tried.add(candidate);
        if (!visited.has(candidate) && (candidate > anchor ? grows(table.get(candidate), table.get(anchor), candidate - anchor) : keeps(table.get(candidate)))) { anchor = candidate; visited.add(candidate); tried = new Set(); return next(); }
      }
      if (step === 1) { phase = 'settled'; settled = { rate: table.get(anchor).rate, at: now() }; strays = 0; return move(anchor, 'settle'); }
      step = Math.ceil(step / 2);
      tried = new Set();
    }
  };
  return {
    get width() { return width; },
    get phase() { return phase; },
    get bound() { return bound; },
    history,
    observe({ completions, elapsedMs, cpuMs = null, saturated = true }) {
      if (!(completions > 0) || !(elapsedMs > 0)) return width;
      if (skip) { skip = false; return width; }
      const sample = { rate: completions / elapsedMs * 1000, cpu: cpuMs === null ? 0 : cpuMs / completions };
      if (phase === 'explore') {
        if (!saturated && width > anchor) { tried.add(width); return next(); }
        table.set(width, sample);
        if (width === anchor || !table.has(anchor)) { anchor = width; return next(); }
        tried.add(width);
        if (!visited.has(width) && (width > anchor ? grows(sample, table.get(anchor), width - anchor) : keeps(sample))) { anchor = width; visited.add(width); tried = new Set(); }
        return next();
      }
      if (!saturated) { strays = 0; return width; }
      strays = Math.abs(sample.rate / settled.rate - 1) > o.drift ? strays + 1 : 0;
      if (strays >= o.driftWindows && now() - lastChange >= o.holdMs) {
        begin(width);
        step = 1;
        table.set(width, sample);
        return next();
      }
      return width;
    },
    setBound(value) {
      const target = Math.max(o.min, Math.min(max, Math.round(value)));
      const band = Math.max(2, Math.round(bound * 0.2));
      if (Math.abs(target - bound) < band) { pendingBound = null; pendingCount = 0; return width; }
      const same = pendingBound !== null && Math.sign(pendingBound - bound) === Math.sign(target - bound);
      pendingCount = same ? pendingCount + 1 : 1;
      pendingBound = same ? (target < bound ? Math.max(pendingBound, target) : Math.min(pendingBound, target)) : target;
      if (pendingCount < o.boundsWindows) return width;
      bound = pendingBound;
      pendingBound = null;
      pendingCount = 0;
      if (width > bound) { begin(bound); return move(bound, 'bound'); }
      if (phase === 'settled' && target > width && now() - lastChange >= o.holdMs) { begin(width); step = 1; skip = true; lastChange = now(); }
      return width;
    },
    snapshot() { return { width, phase, bound, anchor, step, settled, table: table ? Object.fromEntries(table) : {}, changes: history.length }; },
  };
}
