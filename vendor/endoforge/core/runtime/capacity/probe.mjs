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
});

export function probeMachine(host = {}) {
  const { read, exists, parallelism, freeMb, os } = { ...defaultHost(), ...host };
  const notes = [];
  const text = path => { try { return read(path); } catch { return null; } };
  const status = text('/proc/self/status')?.match(/^Cpus_allowed_list:\s*(\S+)/m);
  const affinity = status ? parseCpuList(status[1]) : null;
  if (!affinity) notes.push('no /proc/self/status affinity: using availableParallelism');
  const leaf = text('/proc/self/cgroup')?.split('\n').find(line => line.startsWith('0::'));
  let quota = null, quotaCgroup = null, cpuset = null, memoryLimit = null, memoryCgroup = null;
  const chain = [];
  if (leaf) {
    for (let dir = CGROUP + leaf.slice(3).replace(/\/+$/, ''); dir.startsWith(CGROUP); dir = dir.slice(0, dir.lastIndexOf('/'))) {
      chain.push(dir);
      if (dir === CGROUP) break;
    }
    for (const dir of chain) {
      const [limit, period] = (text(`${dir}/cpu.max`) || 'max').trim().split(/\s+/);
      const cpus = limit === 'max' ? Infinity : Number(limit) / Number(period);
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
  const availableMb = meminfo ? Math.floor(Number(meminfo[1]) / 1024) : freeMb;
  if (!meminfo) notes.push('no /proc/meminfo: memory headroom from os.freemem');
  let headroomMb = availableMb;
  if (memoryLimit !== null) {
    const current = Number((text(`${memoryCgroup}/memory.current`) || '').trim());
    if (Number.isFinite(current)) headroomMb = Math.min(headroomMb, Math.floor((memoryLimit - current) / 1048576));
  }
  const taskset = os === 'linux' ? ['/usr/bin/taskset', '/bin/taskset'].find(path => exists(path)) ?? null : null;
  if (!taskset && domainList.length > 1) notes.push('no taskset: cohorts cannot be pinned to cache domains');
  return {
    os, cpus, quota, quotaCgroup, ownCgroup: quotaCgroup && chain.length ? chain.findLast(dir => dir.startsWith(`${quotaCgroup}/`) && dir.slice(quotaCgroup.length + 1).indexOf('/') < 0) ?? quotaCgroup : null,
    allotment: +allotment.toFixed(2), domains: domainList, cores: topologyRead ? cores.size : cpus.length, smt: topologyRead && [...cores.values()].some(count => count > 1),
    memory: { availableMb, headroomMb, limitMb: memoryLimit === null ? null : Math.floor(memoryLimit / 1048576) }, taskset, notes,
  };
}

let cached;
export const machine = () => cached ??= probeMachine();

export function createShareMeter(probe = machine(), host = {}) {
  const { read, list, isDir } = { ...defaultHost(), ...host };
  const usage = dir => { try { return Number(read(`${dir}/cpu.stat`).match(/^usage_usec (\d+)/m)[1]); } catch { return null; } };
  const throttled = dir => { try { return Number(read(`${dir}/cpu.stat`).match(/^throttled_usec (\d+)/m)?.[1] ?? 0); } catch { return 0; } };
  const siblings = () => { try { return list(probe.quotaCgroup).map(name => `${probe.quotaCgroup}/${name}`).filter(dir => dir !== probe.ownCgroup && isDir(dir) && usage(dir) !== null); } catch { return []; } };
  const snapshot = () => ({ at: performance.now(), total: usage(probe.quotaCgroup), own: probe.ownCgroup === probe.quotaCgroup ? null : usage(probe.ownCgroup), throttled: throttled(probe.quotaCgroup), peers: new Map(siblings().map(dir => [dir, usage(dir)])) });
  let last = probe.quotaCgroup ? snapshot() : null;
  return {
    sample() {
      if (!last || last.total === null) return { share: probe.allotment, othersCpus: 0, peers: 0, throttledMs: 0, source: 'allotment' };
      const now = snapshot(), seconds = (now.at - last.at) / 1000;
      if (seconds <= 0) return { share: probe.allotment, othersCpus: 0, peers: 0, throttledMs: 0, source: 'allotment' };
      const others = now.own === null ? 0 : Math.max(0, (now.total - last.total - (now.own - last.own)) / 1e6 / seconds);
      const peers = [...now.peers].filter(([dir, value]) => last.peers.has(dir) && (value - last.peers.get(dir)) / 1e6 / seconds > 0.5).length;
      const quota = probe.quota ?? probe.allotment;
      const share = Math.min(probe.allotment, Math.max(1, quota - others, quota / (1 + peers)));
      const result = { share: +share.toFixed(2), othersCpus: +others.toFixed(2), peers, throttledMs: +((now.throttled - last.throttled) / 1000).toFixed(1), source: 'cgroup' };
      last = now;
      return result;
    },
  };
}
