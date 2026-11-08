import { createShareMeter, machine } from './probe.mjs';
import { createTuner } from './tuner.mjs';

export function createController({ plan, apply, cpuMs = () => null, backlog = () => 0, probe = machine(), meter = plan.tuned ? createShareMeter(probe) : null,
  windowMs = 1000, minCompletions = 24, maxWindowMs = 10000, now = () => performance.now(), tuner: tunerOptions = {} } = {}) {
  const cohorts = plan.cohorts.length;
  const per = Math.max(...plan.cohorts.map(cohort => cohort.max));
  const tuner = plan.tuned ? createTuner({ start: Math.max(...plan.cohorts.map(cohort => cohort.width)), max: per, now, ...tunerOptions }) : null;
  const log = [];
  let window = null;
  const open = () => { window = { at: now(), completions: 0, saturated: 0, samples: 0, cpu: cpuMs() }; };
  const widths = target => plan.cohorts.map(cohort => Math.max(1, Math.min(cohort.max, target)));
  const push = target => apply(widths(target));
  return {
    get width() { return tuner ? widths(tuner.width).reduce((a, b) => a + b, 0) : plan.width; },
    get widths() { return tuner ? widths(tuner.width) : plan.cohorts.map(cohort => cohort.width); },
    tuner,
    log,
    completed(decided = true) {
      if (!tuner) return;
      if (!window) open();
      window.samples += 1;
      if (backlog() > 0) window.saturated += 1;
      if (decided) window.completions += 1;
      const elapsed = now() - window.at;
      if (elapsed < windowMs || (window.completions < minCompletions && elapsed < maxWindowMs)) return;
      const cpu = cpuMs(), before = tuner.width;
      const summary = { completions: window.completions, elapsedMs: elapsed, cpuMs: cpu === null || window.cpu === null ? null : cpu - window.cpu, saturated: window.saturated * 2 >= window.samples };
      tuner.observe(summary);
      if (meter) {
        const share = meter.sample();
        summary.share = share;
        tuner.setBound(Math.max(1, Math.ceil(share.share * (plan.headroom ?? 1.25) / cohorts)));
      }
      log.push({ at: Math.round(window.at), rate: +(summary.completions / elapsed * 1000).toFixed(1), cpuPer: summary.cpuMs === null ? null : +(summary.cpuMs / summary.completions).toFixed(2), width: before, next: tuner.width, phase: tuner.phase, saturated: summary.saturated, share: summary.share?.share, peers: summary.share?.peers });
      if (log.length > 4096) log.splice(0, 1024);
      if (tuner.width !== before) push(tuner.width);
      open();
    },
  };
}
