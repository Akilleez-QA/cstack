import { execFileSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { availableParallelism, freemem, platform } from 'node:os';

const CGROUP = '/sys/fs/cgroup';

export function parseCpuList(text) {
  const out = [];
  for (const part of String(text ?? '').trim().split(',')) {
    if (!part) continue;
    const [low, high = low] = part.split('-').map(Number);
    if (!Number.isSafeInteger(low) || !Number.isSafeInteger(high) || high < low) return null;
    for (let cpu = low; cpu <= high; cpu++) out.push(cpu);
  }
  return out.length ? out : null;
}

const defaultHost = () => ({
  read: path => readFileSync(path, 'utf8'),
  list: path => readdirSync(path),
  isDir: path => { try { return statSync(path).isDirectory(); } catch { return false; } },
  exists: existsSync,
  parallelism: availableParallelism(),
  freeMb: Math.floor(freemem() / 1048576),
  os: platform(),
  run: (command, args) => execFileSync(command, args, { encoding: 'utf8', timeout: 2000, stdio: ['ignore', 'pipe', 'ignore'] }),
});

export function darwinAvailableMb(run) {
  let text;
  try { text = run('/usr/bin/vm_stat', []); } catch { return null; }
  const page = Number(text.match(/page size of (\d+) bytes/)?.[1]);
  const pages = name => Number(text.match(new RegExp(`^Pages ${name}:\\s+(\\d+)`, 'm'))?.[1] ?? NaN);
  const total = ['free', 'inactive', 'speculative', 'purgeable'].map(pages);
  if (!Number.isFinite(page) || total.some(value => !Number.isFinite(value))) return null;
  return Math.floor(total.reduce((a, b) => a + b, 0) * page / 1048576);
}

function darwinPerfLevels(run) {
  const read = name => { try { const value = Number(run('/usr/sbin/sysctl', ['-n', name]).trim()); return Number.isSafeInteger(value) ? value : null; } catch { return null; } };
  const performance = read('hw.perflevel0.physicalcpu'), efficiency = read('hw.perflevel1.physicalcpu');
  return performance === null ? null : { performance, efficiency: efficiency ?? 0 };
}

export function probeMachine(host = {}) {
  const { read, exists, parallelism, freeMb, os, run } = { ...defaultHost(), ...host };
  const notes = [];
  const text = path => { try { return read(path); } catch { return null; } };
  const status = text('/proc/self/status')?.match(/^Cpus_allowed_list:\s*(\S+)/m);
  const affinity = status ? parseCpuList(status[1]) : null;
  if (!affinity) notes.push('no /proc/self/status affinity: using availableParallelism');
  const leaf = text('/proc/self/cgroup')?.split('\n').find(line => line.startsWith('0::'));
  let quota = null, quotaCgroup = null, cpuset = null, memoryLimit = null, memoryCgroup = null;
  const chain = [], levels = [];
  if (leaf) {
    for (let dir = CGROUP + leaf.slice(3).replace(/\/+$/, ''); dir.startsWith(CGROUP); dir = dir.slice(0, dir.lastIndexOf('/'))) {
      chain.push(dir);
      if (dir === CGROUP) break;
    }
    for (const [index, dir] of chain.entries()) {
      const [limit, period] = (text(`${dir}/cpu.max`) || 'max').trim().split(/\s+/);
      const cpus = limit === 'max' ? Infinity : Number(limit) / Number(period);
      if (cpus > 0 && Number.isFinite(cpus)) levels.push({ cgroup: dir, quota: +cpus.toFixed(2), branch: index ? chain[index - 1] : null });
      if (cpus > 0 && Number.isFinite(cpus) && (quota === null || cpus < quota)) { quota = cpus; quotaCgroup = dir; }
      if (!cpuset) cpuset = parseCpuList(text(`${dir}/cpuset.cpus.effective`));
      const ceilings = ['memory.high', 'memory.max'].map(name => Number((text(`${dir}/${name}`) || 'max').trim())).filter(Number.isFinite);
      const ceiling = ceilings.length ? Math.min(...ceilings) : Infinity;
      if (Number.isFinite(ceiling) && (memoryLimit === null || ceiling < memoryLimit)) { memoryLimit = ceiling; memoryCgroup = dir; }
    }
  } else notes.push('no cgroup v2 membership: no CPU quota or memory ceiling read');
  let cpus = affinity || Array.from({ length: parallelism }, (_, index) => index);
  if (cpuset) cpus = cpus.filter(cpu => cpuset.includes(cpu));
  if (!cpus.length) { cpus = Array.from({ length: parallelism }, (_, index) => index); notes.push('affinity and cpuset do not intersect: using availableParallelism'); }
  const allotment = Math.max(1, Math.min(cpus.length, quota ?? Infinity, affinity ? Infinity : parallelism));
  const slice = chain.findIndex((dir, index) => index > 0 && dir.endsWith('.slice'));
  if (slice > 0 && !levels.some(level => level.cgroup === chain[slice] || chain[slice].startsWith(`${level.cgroup}/`))) {
    const span = parseCpuList(text(`${chain[slice]}/cpuset.cpus.effective`)) ?? parseCpuList(text('/sys/devices/system/cpu/online')) ?? cpus;
    levels.push({ cgroup: chain[slice], quota: Math.max(cpus.length, span.length), branch: chain[slice - 1], weighted: true });
    levels.sort((a, b) => chain.indexOf(a.cgroup) - chain.indexOf(b.cgroup));
  }
  const domains = new Map(), cores = new Map();
  let topologyRead = true;
  for (const cpu of cpus) {
    const base = `/sys/devices/system/cpu/cpu${cpu}`;
    let shared = null;
    for (let index = 0; index < 6 && shared === null; index++) {
      if ((text(`${base}/cache/index${index}/level`) || '').trim() === '3') shared = (text(`${base}/cache/index${index}/shared_cpu_list`) || '').trim() || null;
    }
    const siblings = parseCpuList(text(`${base}/topology/thread_siblings_list`));
    if (shared === null || !siblings) topologyRead = false;
    const domain = shared ?? 'all';
    if (!domains.has(domain)) domains.set(domain, { cpus: [], cores: new Set() });
    const core = siblings ? Math.min(...siblings) : cpu;
    domains.get(domain).cpus.push(cpu);
    domains.get(domain).cores.add(core);
    cores.set(core, (cores.get(core) || 0) + 1);
  }
  if (!topologyRead) notes.push('no sysfs L3 or SMT topology: treating every allowed CPU as one core in one cache domain');
  const domainList = topologyRead ? [...domains.values()].map(({ cpus, cores }) => ({ cpus, cores: cores.size })) : [{ cpus, cores: cpus.length }];
  const meminfo = text('/proc/meminfo')?.match(/^MemAvailable:\s+(\d+)\s+kB/m);
  const darwinMb = !meminfo && os === 'darwin' ? darwinAvailableMb(run) : null;
  const availableMb = meminfo ? Math.floor(Number(meminfo[1]) / 1024) : darwinMb ?? freeMb;
  if (!meminfo) notes.push(darwinMb !== null ? 'no /proc/meminfo: memory headroom from vm_stat (free, inactive, speculative and purgeable pages)' : 'no /proc/meminfo: memory headroom from os.freemem');
  const perfLevels = os === 'darwin' ? darwinPerfLevels(run) : null;
  if (perfLevels && perfLevels.efficiency) notes.push(`mixed cores: ${perfLevels.performance} performance and ${perfLevels.efficiency} efficiency; all are counted as cores in one domain`);
  let headroomMb = availableMb;
  if (memoryLimit !== null) {
    const current = Number((text(`${memoryCgroup}/memory.current`) || '').trim());
    if (Number.isFinite(current)) headroomMb = Math.min(headroomMb, Math.floor((memoryLimit - current) / 1048576));
  }
  const taskset = os === 'linux' ? ['/usr/bin/taskset', '/bin/taskset'].find(path => exists(path)) ?? null : null;
  if (!taskset && domainList.length > 1) notes.push('no taskset: cohorts cannot be pinned to cache domains');
  return {
    os, cpus, quota, quotaCgroup, levels, ownCgroup: quotaCgroup && chain.length ? chain.findLast(dir => dir.startsWith(`${quotaCgroup}/`) && dir.slice(quotaCgroup.length + 1).indexOf('/') < 0) ?? quotaCgroup : null,
    allotment: +allotment.toFixed(2), domains: domainList, cores: topologyRead ? cores.size : cpus.length, smt: topologyRead && [...cores.values()].some(count => count > 1),
    perfLevels, memory: { availableMb, headroomMb, limitMb: memoryLimit === null ? null : Math.floor(memoryLimit / 1048576), cgroup: memoryCgroup }, taskset, notes,
  };
}

let cached;
export const machine = () => cached ??= probeMachine();

export function fairShare(quota, peers) {
  const sorted = peers.filter(used => used > 0).sort((a, b) => a - b);
  let remaining = quota, count = sorted.length + 1;
  for (const used of sorted) {
    const level = remaining / count;
    if (used >= level) return level;
    remaining -= used;
    count -= 1;
  }
  return remaining;
}

export const ACTIVE_PEER_CPUS = 0.5;
export const STARVED = 0.1;

export function createShareMeter(probe = machine(), host = {}) {
  const { read, list, isDir } = { ...defaultHost(), ...host };
  const stat = dir => { try { return read(`${dir}/cpu.stat`); } catch { return null; } };
  const usage = dir => { const text = stat(dir); const hit = text && text.match(/^usage_usec (\d+)/m); return hit ? Number(hit[1]) : null; };
  const throttled = dir => Number(stat(dir)?.match(/^throttled_usec (\d+)/m)?.[1] ?? 0);
  const stall = dir => { try { const hit = read(`${dir}/cpu.pressure`).match(/^some .*total=(\d+)/m); return hit ? Number(hit[1]) : null; } catch { return null; } };
  const levels = (probe.levels ?? (probe.quotaCgroup ? [{ cgroup: probe.quotaCgroup, quota: probe.quota, branch: probe.ownCgroup === probe.quotaCgroup ? null : probe.ownCgroup }] : []))
    .filter(level => level.quota > 0);
  const siblings = level => { if (!level.branch) return []; try { return list(level.cgroup).map(name => `${level.cgroup}/${name}`).filter(dir => dir !== level.branch && isDir(dir) && usage(dir) !== null); } catch { return []; } };
  const snapshot = () => ({ at: performance.now(), levels: levels.map(level => ({ total: usage(level.cgroup), own: level.branch ? usage(level.branch) : null, throttled: throttled(level.cgroup), peers: new Map(siblings(level).map(dir => [dir, { usage: usage(dir), stall: stall(dir) }])) })) });
  const whole = { share: probe.allotment, mode: 'lone', peers: 0, othersCpus: 0, throttledMs: 0, level: null, legacyShare: probe.allotment, source: 'allotment' };
  let last = levels.length ? snapshot() : null;
  return {
    sample() {
      if (!last || last.levels.every(level => level.total === null)) return { ...whole };
      const now = snapshot(), seconds = (now.at - last.at) / 1000;
      if (seconds <= 0) return { ...whole };
      let share = probe.allotment, binding = null, peers = 0, legacy = null;
      const report = levels.map((level, index) => {
        const before = last.levels[index], after = now.levels[index];
        const others = level.branch && after.total !== null && before.total !== null && after.own !== null && before.own !== null ? Math.max(0, (after.total - before.total - (after.own - before.own)) / 1e6 / seconds) : 0;
        const seen = [...after.peers].filter(([dir]) => before.peers.has(dir)).map(([dir, value]) => {
          const prior = before.peers.get(dir), used = Math.max(0, (value.usage - prior.usage) / 1e6 / seconds);
          const starved = value.stall !== null && prior.stall !== null && (value.stall - prior.stall) / 1e6 / seconds > STARVED;
          return { used, starved };
        });
        const active = seen.filter(peer => peer.used > ACTIVE_PEER_CPUS).length, starved = seen.filter(peer => peer.used > ACTIVE_PEER_CPUS && peer.starved).length;
        const fair = active ? fairShare(level.quota, seen.map(peer => peer.used > ACTIVE_PEER_CPUS && peer.starved ? Infinity : peer.used)) : level.quota;
        if (fair < share) { share = fair; binding = level.cgroup; }
        peers += active;
        return { cgroup: level.cgroup, quota: level.quota, others: +others.toFixed(2), peers: active, starved, fair: +fair.toFixed(2), throttledMs: +((after.throttled - before.throttled) / 1000).toFixed(1) };
      });
      const tight = report.find(level => level.cgroup === probe.quotaCgroup) ?? report.reduce((low, level) => level.quota < low.quota ? level : low, report[0]);
      legacy = Math.min(probe.allotment, Math.max(1, tight.quota - tight.others, tight.quota / (1 + tight.peers)));
      last = now;
      share = Math.max(1, Math.min(probe.allotment, share));
      return { share: +share.toFixed(2), mode: peers ? 'shared' : 'lone', peers, othersCpus: tight.others, throttledMs: tight.throttledMs, level: binding, legacyShare: +legacy.toFixed(2), levels: report, source: 'cgroup' };
    },
  };
}

export function createMemoryMeter(probe = machine(), host = {}) {
  const { read, run, os } = { ...defaultHost(), ...host };
  const text = path => { try { return read(path); } catch { return null; } };
  let cached = null;
  return {
    headroomMb() {
      const meminfo = text('/proc/meminfo')?.match(/^MemAvailable:\s+(\d+)\s+kB/m);
      if (!meminfo && os === 'darwin' && (!cached || performance.now() - cached.at > 5000)) cached = { at: performance.now(), mb: darwinAvailableMb(run) };
      let headroom = meminfo ? Math.floor(Number(meminfo[1]) / 1024) : cached?.mb ?? probe.memory.headroomMb;
      const dir = probe.memory.cgroup;
      if (dir) {
        const ceilings = ['memory.high', 'memory.max'].map(name => Number((text(`${dir}/${name}`) || 'max').trim())).filter(Number.isFinite);
        const current = Number((text(`${dir}/memory.current`) || '').trim());
        if (ceilings.length && Number.isFinite(current)) headroom = Math.min(headroom, Math.floor((Math.min(...ceilings) - current) / 1048576));
      }
      return Math.max(0, headroom);
    },
  };
}
