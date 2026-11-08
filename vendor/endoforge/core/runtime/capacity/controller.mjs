import { createMemoryMeter, createShareMeter, machine } from './probe.mjs';
import { createTuner } from './tuner.mjs';

export const OCCUPANCY_DEFAULTS = Object.freeze({ decay: 0.995, median: 3, floor: 0.05, ram: 0.75 });

export function createOccupancy({ decay = OCCUPANCY_DEFAULTS.decay, median = OCCUPANCY_DEFAULTS.median, floor = OCCUPANCY_DEFAULTS.floor } = {}) {
  const recent = [];
  let estimate = null, count = 0, sum = 0, squares = 0;
  return {
    get u() { return estimate; },
    observe(cpuMs, cellMs) {
      if (!(cpuMs >= 0) || !(cellMs > 0)) return estimate;
      const raw = cpuMs / cellMs;
      count += 1; sum += raw; squares += raw * raw;
      recent.push(raw);
      if (recent.length > median) recent.shift();
      const middle = [...recent].sort((a, b) => a - b)[Math.floor((recent.length - 1) / 2)];
      estimate = Math.max(floor, estimate === null ? middle : Math.max(middle, estimate * decay));
      return estimate;
    },
    stats() { const mean = count ? sum / count : null; return { windows: count, mean, sd: count > 1 ? Math.sqrt(Math.max(0, squares / count - mean * mean)) : null, u: estimate }; },
  };
}

export function occupancyCap({ share, u, headroom = 1.25, max, memoryCells = Infinity }) {
  const byCpu = u > 0 ? Math.ceil(headroom * share / u) : max;
  return Math.max(1, Math.min(max, byCpu, memoryCells));
}

export function createController({ plan, apply, cpuMs = () => null, rssMb = () => null, backlog = () => 0, probe = machine(), meter = plan.tuned ? createShareMeter(probe) : null,
  memory = plan.tuned && plan.cap === 'occupancy' ? createMemoryMeter(probe) : null, windowMs = 1000, minCompletions = 24, maxWindowMs = 10000, now = () => performance.now(),
  tuner: tunerOptions = {}, occupancy: occupancyOptions = {} } = {}) {
  const cohorts = plan.cohorts.length;
  const per = Math.max(...plan.cohorts.map(cohort => cohort.max));
  const occupancyMode = plan.tuned && plan.cap === 'occupancy';
  const headroom = plan.headroom ?? 1.25, ram = plan.ram ?? OCCUPANCY_DEFAULTS.ram;
  const startShare = (plan.allotment ?? per * cohorts) / cohorts;
  const tuner = plan.tuned ? createTuner({ start: Math.max(...plan.cohorts.map(cohort => cohort.width)), max: per, now,
    ...(occupancyMode ? { bound: Math.max(...plan.cohorts.map(cohort => cohort.width), Math.ceil(headroom * startShare)) } : {}), ...tunerOptions }) : null;
  const occupancy = occupancyMode ? createOccupancy(occupancyOptions) : null;
  const log = [];
  let window = null, inflight = 0, tracked = false, mark = now();
  const integrate = () => { const at = now(); if (window) window.cellMs += inflight * (at - mark); mark = at; };
  const open = () => { integrate(); window = { at: now(), completions: 0, saturated: 0, samples: 0, cpu: cpuMs(), cellMs: 0 }; };
  const widths = target => plan.cohorts.map(cohort => Math.max(1, Math.min(cohort.max, target)));
  const push = target => apply(widths(target));
  return {
    get width() { return tuner ? widths(tuner.width).reduce((a, b) => a + b, 0) : plan.width; },
    get widths() { return tuner ? widths(tuner.width) : plan.cohorts.map(cohort => cohort.width); },
    get occupancy() { return occupancy ? occupancy.stats() : null; },
    tuner,
    log,
    started() {
      if (!tuner) return;
      tracked = true;
      if (!window) open();
      integrate();
      inflight += 1;
    },
    completed(decided = true) {
      if (!tuner) return;
      if (!window) open();
      integrate();
      if (tracked && inflight > 0) inflight -= 1;
      window.samples += 1;
      if (backlog() > 0) window.saturated += 1;
      if (decided) window.completions += 1;
      const elapsed = now() - window.at;
      if (elapsed < windowMs || (window.completions < minCompletions && elapsed < maxWindowMs)) return;
      const cpu = cpuMs(), before = tuner.width;
      const summary = { completions: window.completions, elapsedMs: elapsed, cpuMs: cpu === null || window.cpu === null ? null : cpu - window.cpu, saturated: window.saturated * 2 >= window.samples };
      tuner.observe(summary);
      const entry = { at: Math.round(window.at), rate: +(summary.completions / elapsed * 1000).toFixed(1), cpuPer: summary.cpuMs === null ? null : +(summary.cpuMs / summary.completions).toFixed(2), width: before };
      if (meter) {
        const share = meter.sample();
        Object.assign(entry, { share: share.share, mode: share.mode, peers: share.peers, legacyShare: share.legacyShare });
        if (occupancyMode) {
          const cellMs = tracked ? window.cellMs : widths(before).reduce((a, b) => a + b, 0) * elapsed;
          const u = summary.cpuMs === null ? occupancy.u : occupancy.observe(summary.cpuMs, cellMs);
          const rss = rssMb(), total = widths(before).reduce((a, b) => a + b, 0);
          const perCell = rss === null || !(total > 0) ? null : rss / total;
          const memoryCells = perCell && memory ? Math.floor((total + memory.headroomMb() * ram / perCell) / cohorts) : Infinity;
          const cap = occupancyCap({ share: share.share / cohorts, u, headroom, max: per, memoryCells });
          if (u !== null) tuner.setBound(cap);
          Object.assign(entry, { uRaw: summary.cpuMs === null ? null : +(summary.cpuMs / cellMs).toFixed(3), u: u === null ? null : +u.toFixed(3), cap, memoryCells: Number.isFinite(memoryCells) ? memoryCells : null, rssPerCellMb: perCell === null ? null : +perCell.toFixed(1) });
        } else tuner.setBound(Math.max(1, Math.ceil(share.legacyShare * headroom / cohorts)));
      }
      Object.assign(entry, { next: tuner.width, bound: tuner.bound, phase: tuner.phase, saturated: summary.saturated });
      log.push(entry);
      if (log.length > 4096) log.splice(0, 1024);
      if (tuner.width !== before) push(tuner.width);
      open();
    },
  };
}
