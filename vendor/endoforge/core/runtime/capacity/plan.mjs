import { machine } from './probe.mjs';

export const TUNED_POLICY = Object.freeze({ mode: 'tuned', headroom: 1.25 });
export const POLICY = Object.freeze({ mode: 'fixed', width: 'cores', perDomain: 1, headroom: 1.25 });

const split = (count, parts) => Array.from({ length: parts }, (_, index) => Math.floor(count / parts) + (index < count % parts ? 1 : 0));

export function plan({ queues = 1, allotment, probe = machine(), policy = POLICY } = {}) {
  if (!Number.isSafeInteger(queues) || queues < 1) throw new TypeError('queues must be a positive integer');
  const share = Math.max(1, Math.min(allotment ?? probe.allotment, probe.cpus.length));
  const notes = [...probe.notes];
  const pinnable = Boolean(probe.taskset) && probe.domains.length > 1;
  const pinned = pinnable && share >= 2 * probe.domains.length && policy.pin !== false;
  if (probe.domains.length > 1 && !pinned) notes.push(pinnable ? 'allotment too small to split across cache domains: one cohort' : 'cannot pin: one unpinned cohort per queue');
  const slots = pinned ? probe.domains.map(domain => ({ cpus: domain.cpus, cores: domain.cores })) : [{ cpus: probe.cpus, cores: probe.cores }];
  const count = Math.max(slots.length * (pinned ? policy.perDomain ?? 1 : 1), Math.min(queues, Math.max(1, Math.floor(share))));
  const perSlot = split(count, slots.length);
  const shares = split(Math.round(share * 100), count).map(value => value / 100);
  const cohorts = [];
  let index = 0;
  slots.forEach((slot, slotIndex) => {
    const cores = split(slot.cores, perSlot[slotIndex]), threads = split(slot.cpus.length, perSlot[slotIndex]);
    for (let local = 0; local < perSlot[slotIndex]; local++, index++) {
      const portion = shares[index];
      const max = Math.max(1, Math.min(threads[local] || 1, Math.ceil(portion * policy.headroom)));
      const fixed = policy.mode !== 'fixed' ? null : policy.width === 'cores' ? Math.max(1, Math.min(cores[local] || 1, Math.ceil(portion))) : Number.isSafeInteger(policy.width) ? policy.width : null;
      const start = fixed ?? Math.max(1, Math.min(max, cores[local] || 1, Math.ceil(portion)));
      cohorts.push({ queue: index % queues, width: start, max: fixed ?? max, share: portion, cpus: pinned ? slot.cpus : null });
    }
  });
  return {
    mode: policy.mode, tuned: policy.mode === 'tuned', headroom: policy.headroom ?? 1.25, allotment: +share.toFixed(2), queues, pinned, cohorts,
    width: cohorts.reduce((total, cohort) => total + cohort.width, 0), max: cohorts.reduce((total, cohort) => total + cohort.max, 0), notes,
  };
}

export const defaultWidth = (options = {}) => plan(options).width;
