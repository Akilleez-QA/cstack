import { availableParallelism } from 'node:os';
import { performance } from 'node:perf_hooks';
import { resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { Worker } from 'node:worker_threads';
import { execFileSync, fork, spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dumpListEnabled, registerHolder } from './dump-list.mjs';
import { attachCgroup, prepareCgroup, releaseCgroup } from './isolate-cgroup.mjs';
import { LedgerBridge } from './isolate-ledger.mjs';
import { trustedWasmPolicy } from './isolate-wasm.mjs';

const positive = value => Number.isSafeInteger(value) && value > 0;
const stackMargin = 192;
const stackFlag = (stackKb, args) => {
  const block = [...args, ...Object.entries(process.env).map(([name, value]) => `${name}=${value}`)];
  const bytes = block.reduce((total, entry) => total + Buffer.byteLength(entry) + 9, 0);
  const size = stackKb - stackMargin - Math.ceil(bytes / 1024);
  if (size < stackMargin) throw new Error('stackSizeMb is too small for this environment and its arguments');
  return `--stack-size=${size}`;
};
const requireProcessStack = stackSizeMb => {
  try { execFileSync('/bin/sh', ['-c', 'ulimit -s "$1"', 'sh', String(stackSizeMb * 1024)], { stdio: 'ignore' }); }
  catch { throw new Error('this host cannot raise the process stack limit to stackSizeMb'); }
};
const maxHostCalls = 4096;
const maxHostCallBytes = 1048576;
const killGraceMs = 1000;
const exitGraceMs = 500;
export const POOL_DUMP_DEFAULTS = Object.freeze({ name: 'endoforge-isolate-pool', priority: 20, floor: 1, holdMs: 30000, intervalMs: 2000, settleMs: 1500 });
const PRIVATE = /^Private_(?:Clean|Dirty):\s+(\d+)/gm;
const privateBytes = pid => {
  try { return [...readFileSync(`/proc/${pid}/smaps_rollup`, 'utf8').matchAll(PRIVATE)].reduce((total, match) => total + Number(match[1]) * 1024, 0); } catch { return 0; }
};

export class IsolatePool {
  #size;
  #hostPort;
  #limits;
  #wasmMemoryMaxMb;
  #trustedWasmModules;
  #isolation;
  #cgroupRoot;
  #cgroupLimits;
  #jobTimeoutMs;
  #cells = new Set();
  #queue = [];
  #pending = new Set();
  #ledger;
  #cellEnv;
  #cellFlags;
  #jobDeadlineMs;
  #closing = false;
  #stopping = false;
  #closed;
  #warm;
  #sharedSources;
  #sharedModules = [];
  #sharing;
  #warmOptions;
  #warmTimeoutMs;
  #startFailures = 0;
  #hostCalls;
  #frozenThroughLedger;
  #hostCall;
  #retireAfterJobs;
  #busyMs = 0;
  #dumpOptions = null;
  #dump = null;
  #ratio = null;
  #shedUntil = 0;
  #holdTimer = null;
  #rates;

  constructor({ hostPort, size = availableParallelism(), resourceLimits = {}, wasmMemoryMaxMb = 64,
    isolation = 'thread', cgroupRoot, cgroupLimits = {}, trustedWasmModules = [], sharedWasmModules = [], prewarm = false, warm, warmTimeoutMs = 60000, jobTimeoutMs, jobDeadlineMs, hostCall, hostCalls, frozenThroughLedger = false, cellEnv, cellFlags = [], ledgerBridge, retireAfterJobs = 256, dumpList, rates = null } = {}) {
    if (!positive(retireAfterJobs)) throw new TypeError('retireAfterJobs must be a positive integer');
    this.#retireAfterJobs = retireAfterJobs;
    this.#rates = rates;
    this.#hostCall = hostCall;
    this.#cellEnv = cellEnv;
    this.#cellFlags = cellFlags;
    this.#ledger = new LedgerBridge(ledgerBridge);
    if (jobDeadlineMs !== undefined && !positive(jobDeadlineMs)) throw new TypeError('jobDeadlineMs must be a positive integer');
    this.#jobDeadlineMs = jobDeadlineMs;
    if (!['thread', 'process'].includes(isolation)) throw new TypeError('isolation must be thread or process');
    if (cgroupRoot !== undefined && (typeof cgroupRoot !== 'string' || !cgroupRoot)) throw new TypeError('cgroupRoot path required');
    if (!positive(size)) throw new TypeError('positive integer pool size required');
    if (typeof prewarm !== 'boolean') throw new TypeError('prewarm must be boolean');
    if (warm !== undefined && (warm === null || typeof warm !== 'object')) throw new TypeError('warm must be an options object');
    if (!positive(warmTimeoutMs)) throw new TypeError('warmTimeoutMs must be a positive integer');
    if (hostCalls !== undefined && typeof hostCalls !== 'function') throw new TypeError('hostCalls must be a function');
    if (typeof frozenThroughLedger !== 'boolean') throw new TypeError('frozenThroughLedger must be boolean');
    this.#hostCalls = hostCalls;
    this.#frozenThroughLedger = frozenThroughLedger;
    this.#warmOptions = warm;
    this.#warmTimeoutMs = warmTimeoutMs;
    if (typeof hostPort !== 'string' || !hostPort) throw new TypeError('hostPort module path required');
    if (!positive(wasmMemoryMaxMb) || wasmMemoryMaxMb > 4096) {
      throw new TypeError('wasmMemoryMaxMb must be an integer from 1 to 4096');
    }
    const limits = { maxOldGenerationSizeMb: 128, maxYoungGenerationSizeMb: 16, ...resourceLimits };
    const { maxOldGenerationSizeMb, maxYoungGenerationSizeMb, stackSizeMb, ...unknownLimits } = limits;
    if (Object.keys(unknownLimits).length || !Object.values(limits).every(positive)) {
      throw new TypeError('positive integer old and young generation limits required');
    }
    if (stackSizeMb !== undefined && isolation === 'process') requireProcessStack(stackSizeMb);
    if (jobTimeoutMs !== undefined && !positive(jobTimeoutMs)) throw new TypeError('jobTimeoutMs must be a positive integer');
    this.#jobTimeoutMs = jobTimeoutMs;
    if (process.execArgv.some(arg => /^--max[-_](old[-_]space|semi[-_]space)[-_]size/.test(arg)) ||
        /--max[-_](old[-_]space|semi[-_]space)[-_]size/.test(process.env.NODE_OPTIONS || '')) {
      throw new Error('heap command-line overrides conflict with workcell limits');
    }
    this.#size = size;
    this.#hostPort = pathToFileURL(resolve(hostPort)).href;
    this.#limits = Object.freeze(limits);
    this.#wasmMemoryMaxMb = wasmMemoryMaxMb;
    this.#trustedWasmModules = trustedWasmPolicy(trustedWasmModules, wasmMemoryMaxMb);
    this.#isolation = isolation;
    if (!Array.isArray(sharedWasmModules) || !sharedWasmModules.every(({ sha256, path }) => typeof path === 'string' && path &&
        this.#trustedWasmModules.some(entry => entry.sha256 === sha256))) throw new TypeError('sharedWasmModules must name trustedWasmModules digests and paths');
    this.#sharedSources = isolation === 'thread' ? sharedWasmModules.map(({ sha256, path }) => ({ sha256, path })) : [];
    this.#cgroupLimits = Object.freeze({ memoryMax: Math.max(256, limits.maxOldGenerationSizeMb + 3 * limits.maxYoungGenerationSizeMb + 128) * 1048576,
      cpuMax: '100000 100000', pidsMax: 64, ...cgroupLimits });
    const { memoryMax, cpuMax, pidsMax } = this.#cgroupLimits;
    if (Object.keys(this.#cgroupLimits).length !== 3 || !positive(memoryMax) || !positive(pidsMax) ||
        typeof cpuMax !== 'string' || !/^(max|[1-9]\d*) [1-9]\d*$/.test(cpuMax)) throw new TypeError('invalid cgroupLimits');
    this.#cgroupRoot = isolation === 'process' ? prepareCgroup(cgroupRoot) : null;
    this.#dumpOptions = poolDumpOptions(dumpList);
    if (prewarm) this.ready().catch(() => {});
  }

  ready() {
    if (this.#closing) return Promise.reject(new Error('isolate pool is closing'));
    return this.#warm ||= (async () => {
      await this.#share();
      if (this.#closing) throw new Error('isolate pool is closing');
      const before = process.memoryUsage.rss(), spawned = this.#size - this.#cells.size;
      while (this.#cells.size < this.#size) this.#spawn();
      const [started] = await Promise.all([Promise.all([...this.#cells].map(cell => cell.started)), this.#ledger.start()]);
      if (!started.every(Boolean)) throw new Error('workcell failed before ready');
      if (this.#dumpOptions && !this.#closing) {
        await Promise.all([...this.#cells].map(cell => this.#weigh(cell)));
        const weighed = [...this.#cells].reduce((total, cell) => total + (cell.heapBytes ?? 0), 0);
        if (this.#ratio === null && spawned === this.#cells.size && weighed > 0) this.#ratio = Math.min(1, Math.max(0.05, (process.memoryUsage.rss() - before) / weighed));
        this.#register();
      }
    })();
  }

  #register() {
    if (this.#dump) return;
    const { name, priority, intervalMs, directory, env } = this.#dumpOptions;
    this.#dump = registerHolder({ name, priority, measure: () => this.#sheddable(), shed: () => this.#shed(), refreshMs: intervalMs, directory, env, enabled: true });
  }

  #spareCells() {
    return [...this.#cells].filter(cell => cell.ready && !cell.job && !cell.stopping).slice(this.#dumpOptions.floor);
  }

  #weigh(cell) {
    if (!this.#dumpOptions || this.#isolation !== 'thread' || typeof cell.worker.getHeapStatistics !== 'function') return Promise.resolve();
    return cell.worker.getHeapStatistics().then(heap => { cell.heapBytes = heap.total_physical_size + heap.malloced_memory + heap.external_memory; }, () => {});
  }

  #bytesOf(cell) {
    return this.#isolation === 'process' ? privateBytes(cell.worker.pid) : (cell.heapBytes ?? 0) * (this.#ratio ?? 1);
  }

  #sheddable() {
    return Math.round(this.#spareCells().reduce((total, cell) => total + this.#bytesOf(cell), 0));
  }

  get dump() {
    return this.#dump?.enabled ? { path: this.#dump.path, bytes: this.#dump.bytes, writes: this.#dump.writes, sheds: this.#dump.sheds, ratio: this.#ratio } : null;
  }

  shed() {
    return this.#dump?.enabled ? this.#dump.shedNow() : Promise.resolve();
  }

  async #shed() {
    if (this.#closing) return;
    const { holdMs, settleMs } = this.#dumpOptions;
    this.#shedUntil = Date.now() + holdMs;
    clearTimeout(this.#holdTimer);
    this.#holdTimer = setTimeout(() => {
      if (this.#closing || this.#stopping || !this.#warm) return;
      try { while (this.#cells.size < this.#size && !this.#noStarts) this.#spawn(); } catch { }
      this.#dump?.refresh();
    }, holdMs);
    this.#holdTimer.unref();
    const spares = this.#spareCells();
    if (!spares.length) return;
    const before = process.memoryUsage.rss(), predicted = spares.reduce((total, cell) => total + this.#bytesOf(cell), 0);
    for (const cell of spares) { cell.shed = true; cell.stopping = true; cell.worker.terminate(); }
    let timer;
    await Promise.race([Promise.all(spares.map(cell => cell.gone)), new Promise(resolve => { timer = setTimeout(resolve, settleMs); timer.unref(); })]);
    clearTimeout(timer);
    if (this.#isolation === 'thread' && predicted > 0 && spares.every(cell => !this.#cells.has(cell))) {
      const observed = Math.min(2, Math.max(0.05, (before - process.memoryUsage.rss()) / predicted * (this.#ratio ?? 1)));
      this.#ratio = this.#ratio === null ? observed : (this.#ratio + observed) / 2;
    }
  }

  get ledger() {
    return this.#ledger;
  }

  get stats() {
    return { size: this.#size, workers: this.#cells.size,
      busy: [...this.#cells].filter(cell => cell.job).length, queued: this.#queue.length };
  }

  get busyMs() {
    return this.#busyMs;
  }

  get halted() {
    return this.#noStarts || this.#ledger.failed;
  }

  get #noStarts() {
    return this.#startFailures >= this.#size + 2;
  }

  #share() {
    return this.#sharing ||= (async () => {
      if (!this.#sharedSources.length) return;
      const worker = new Worker(new URL('./isolate-wasm-compile.mjs', import.meta.url), {
        resourceLimits: this.#limits, execArgv: [],
        workerData: { wasmMemoryMaxMb: this.#wasmMemoryMaxMb, trustedWasmModules: this.#trustedWasmModules, sources: this.#sharedSources },
      });
      this.#sharedModules = await new Promise(resolve => {
        worker.once('message', resolve);
        worker.once('error', () => resolve([]));
        worker.once('exit', () => resolve([]));
      });
      await worker.terminate();
    })();
  }

  #persist(action, job, result) {
    return this.#ledger.request(action, job, result);
  }

  run(input) {
    if (this.#closing) return Promise.reject(new Error('isolate pool is closing'));
    let data;
    try {
      data = structuredClone(input);
      if (!Array.isArray(data.candidates) || !data.candidates.length ||
          !data.candidates.every(c => typeof c === 'string' && c.length) ||
          new Set(data.candidates).size !== data.candidates.length) throw new Error('unique candidates required');
    } catch (error) { return Promise.reject(error); }
    const promise = new Promise((resolve, reject) => {
      const job = { data, resolve, reject, ready: false, started: performance.now(), rate: this.#rates?.arrive('cell') };
      this.#queue.push(job);
      Promise.all([data.ledger === 'caller' ? null : this.#persist('prepare', data), this.#share()]).then(() => { job.prepared = performance.now(); job.ready = true; this.#pump(); }, error => {
        this.#queue.splice(this.#queue.indexOf(job), 1);
        this.#rates?.done(job.rate);
        reject(error);
        this.#pump();
      });
    });
    this.#pending.add(promise);
    promise.then(() => this.#pending.delete(promise), () => this.#pending.delete(promise));
    return promise;
  }

  #spawn() {
    const subprocess = this.#isolation === 'process';
    const entry = new URL('./isolate-workcell.mjs', import.meta.url);
    const policy = { wasmMemoryMaxMb: this.#wasmMemoryMaxMb, trustedWasmModules: this.#trustedWasmModules,
      ...(this.#warmOptions ? { warm: this.#warmOptions, hostPort: this.#hostPort } : {}) };
    const heapArgv = [`--max-old-space-size=${this.#limits.maxOldGenerationSizeMb}`, `--max-semi-space-size=${this.#limits.maxYoungGenerationSizeMb}`, ...this.#cellFlags];
    const processOptions = { serialization: 'advanced', stdio: ['ignore', 'ignore', 'pipe', 'ipc'], ...(this.#cellEnv ? { env: this.#cellEnv } : {}) };
    const processArguments = [JSON.stringify({ ...policy, resourceLimits: this.#limits })];
    const stackKb = this.#limits.stackSizeMb && this.#limits.stackSizeMb * 1024;
    const worker = subprocess ? (stackKb
      ? spawn('/bin/sh', ['-c', 'ulimit -s "$1" && shift && exec "$@"', 'sh', String(stackKb), process.execPath, ...heapArgv,
        stackFlag(stackKb, [process.execPath, ...heapArgv, fileURLToPath(entry), ...processArguments]), fileURLToPath(entry), ...processArguments], processOptions)
      : fork(entry, processArguments, { execArgv: heapArgv, ...processOptions })) : new Worker(entry, {
      resourceLimits: this.#limits, execArgv: [],
      workerData: { ...policy, sharedWasmModules: this.#sharedModules },
    });
    const directory = subprocess ? attachCgroup(worker.pid, this.#cgroupRoot, this.#cgroupLimits) : null;
    const cell = { worker, id: subprocess ? worker.pid : worker.threadId, job: null, error: null,
      metadata: { ...(this.#sharedSources.length ? { sharedWasmModules: this.#sharedModules.map(entry => entry.sha256) } : {}), isolation: this.#isolation, cgroup: subprocess ? (directory ? 'enabled' : 'unavailable') : 'not_applicable',
        ...(directory ? { cgroupLimits: this.#cgroupLimits } : {}) } };
    if (subprocess) {
      let tail = '';
      worker.stderr.on('data', chunk => {
        tail = (tail + chunk).slice(-8192);
        if (/FATAL ERROR:.*(?:heap out of memory|heap limit|Allocation failed)/i.test(tail)) cell.error = { code: 'ERR_WORKER_OUT_OF_MEMORY' };
      });
      worker.postMessage = message => worker.send(message, error => {
        if (error && cell.error?.code !== 'ERR_WORKCELL_DEADLINE') { cell.error = error; worker.kill(); }
      });
      worker.terminate = () => new Promise(resolve => {
        const kill = setTimeout(() => worker.kill('SIGKILL'), killGraceMs);
        cell.gone.then(() => { clearTimeout(kill); resolve(); });
        worker.kill();
      });
    }
    cell.started = new Promise(resolve => { cell.markStarted = resolve; });
    cell.gone = new Promise(resolve => { cell.markGone = resolve; });
    this.#cells.add(cell);
    if (this.#warmOptions) cell.warmTimer = setTimeout(() => {
      cell.error ||= { code: 'ERR_WORKCELL_WARM_TIMEOUT' };
      cell.stopping = true;
      worker.terminate();
    }, this.#warmTimeoutMs);
    worker.on('message', result => {
      if (result?.type === 'ready') {
        cell.ready = true;
        this.#startFailures = 0;
        clearTimeout(cell.warmTimer);
        if (cell.job && !cell.job.settled) this.#arm(cell, cell.job);
        return cell.markStarted(!result.warmError);
      }
      const job = cell.job;
      if (!job || job.settled || job.deadlineFired) return;
      if (result.type === 'host_call' || result.type === 'host_frozen') return this.#answer(cell, result);
      if (result.type === 'host-call') return this.#relay(cell, result);
      if (result.type === 'pong') { cell.job.pong = performance.now(); return; }
      if (result.type === 'limit') {
        cell.error = { code: result.error };
        return;
      }
      if (!this.#claim(job)) return;
      cell.job = null;
      this.#finish(job, { ...result, ...cell.metadata });
      if (this.#dump?.enabled) this.#weigh(cell).then(() => this.#dump?.refresh());
      cell.jobs = (cell.jobs ?? 0) + 1;
      if (cell.jobs >= this.#retireAfterJobs) { cell.stopping = true; cell.worker.terminate(); }
      this.#pump();
    });
    worker.on('error', error => { if (cell.error?.code !== 'ERR_WORKCELL_DEADLINE') cell.error = error; });
    let exited = false;
    let exitTimer;
    const gone = (code, signal) => {
      if (exited) return;
      exited = true;
      clearTimeout(exitTimer);
      clearTimeout(cell.warmTimer);
      cell.markGone();
      this.#cells.delete(cell);
      cell.markStarted(false);
      releaseCgroup(directory);
      if (subprocess && code === 18) cell.error = { code: 'ERR_WORKCELL_WASM_MEMORY_LIMIT' };
      const limited = ['ERR_WORKER_OUT_OF_MEMORY', 'ERR_WORKCELL_WASM_MEMORY_LIMIT'].includes(cell.error?.code);
      const job = cell.job;
      const claimed = this.#claim(job);
      if (job) cell.job = null;
      if (claimed) this.#finish(job, { status: subprocess && limited ? 'rejected' : 'outcome_unknown',
        reason: cell.error?.code === 'ERR_WORKCELL_DEADLINE' ? 'deadline' : limited ? (subprocess ? (cell.error.code === 'ERR_WORKER_OUT_OF_MEMORY' ? 'heap' : 'wasm_memory') : 'limit') : 'worker_exit',
        error: cell.error?.code || null, exitCode: code, signal: signal || null, report: null, ...cell.metadata,
        workcell: cell.id, resourceLimits: this.#limits, wasmMemoryMaxMb: this.#wasmMemoryMaxMb });
      if (!cell.ready && cell.error?.code !== 'ERR_WORKCELL_DEADLINE') this.#startFailures += 1;
      if (!this.#stopping) {
        if (!this.#noStarts && !(cell.shed && Date.now() < this.#shedUntil)) try { this.#spawn(); } catch { }
        this.#pump();
        this.#dump?.refresh();
      }
    };
    worker.on(subprocess ? 'close' : 'exit', gone);
    if (subprocess) worker.on('exit', (code, signal) => {
      cell.stopping = true;
      exitTimer = setTimeout(() => setImmediate(() => {
        if (!exited) worker.stderr.destroy();
        gone(code, signal);
      }), exitGraceMs);
    });
    return cell;
  }

  #pump() {
    while (this.#queue[0]?.ready) {
      let cell = [...this.#cells].find(cell => !cell.job && !cell.stopping);
      if (!cell && (this.#noStarts ? this.#cells.size : this.#cells.size >= this.#size)) return;
      const job = this.#queue.shift();
      if (!cell && this.#noStarts) {
        this.#rates?.done(job.rate);
        this.#finish(job, { status: 'outcome_unknown', reason: 'workcell_start_failed', report: null, workcell: null,
          isolation: this.#isolation, resourceLimits: this.#limits, wasmMemoryMaxMb: this.#wasmMemoryMaxMb });
        continue;
      }
      try {
        cell ||= this.#spawn();
        cell.job = job;
        job.dispatched = performance.now();
        this.#rates?.start(job.rate);
        if (cell.ready) this.#arm(cell, job);
        if (this.#jobDeadlineMs) job.total = setTimeout(() => this.#stop(cell), this.#jobDeadlineMs);
        const { reference, candidates, portOptions } = job.data;
        job.hostCalls = 0;
        cell.worker.postMessage({ reference, candidates, portOptions, hostPort: this.#hostPort, frozenThroughLedger: this.#frozenThroughLedger });
      } catch (error) {
        if (cell?.job === job) cell.job = null;
        if (this.#claim(job)) this.#finish(job, { status: 'outcome_unknown', reason: error.message,
          report: null, workcell: cell?.id ?? null, ...cell?.metadata, resourceLimits: this.#limits, wasmMemoryMaxMb: this.#wasmMemoryMaxMb });
      }
    }
  }

  async #answer(cell, { type, id, request, reference }) {
    const job = cell.job;
    const reply = message => { try { cell.worker.postMessage({ type: 'host_reply', id, ...message }); } catch { } };
    try {
      if (type === 'host_frozen') return reply({ result: await this.#ledger.request('frozen', { reference }) });
      if (!this.#hostCalls) throw new Error('no host calls are configured');
      if (++job.hostCalls > maxHostCalls) throw new Error('host-call-limit');
      if (JSON.stringify(request).length > maxHostCallBytes) throw new Error('host-call-size');
      reply({ result: await this.#hostCalls(request, { candidates: job.data.candidates, workcell: cell.id }) });
    } catch (error) { reply({ error: error.message || String(error) }); }
  }

  #stop(cell) {
    if (cell.job?.settled) return;
    if (cell.job) cell.job.deadlineFired = true;
    cell.error = { code: 'ERR_WORKCELL_DEADLINE' };
    cell.stopping = true;
    cell.worker.terminate();
  }

  #arm(cell, job) {
    if (!this.#jobTimeoutMs) return;
    job.budget ??= this.#jobTimeoutMs;
    job.armed = performance.now();
    job.deadline = setTimeout(() => this.#stop(cell), Math.max(0, job.budget));
  }

  #disarm(job) {
    if (job.dispatched) this.#busyMs += performance.now() - job.dispatched;
    job.dispatched = 0;
    this.#rates?.done(job.rate);
    clearTimeout(job.deadline);
    clearTimeout(job.total);
    clearInterval(job.liveness);
  }

  #relay(cell, { id, call }) {
    const job = cell.job;
    job.calls = (job.calls ?? 0) + 1;
    if (job.calls === 1 && this.#jobTimeoutMs) {
      clearTimeout(job.deadline);
      job.budget -= performance.now() - job.armed;
      job.pong = performance.now();
      job.liveness = setInterval(() => {
        if (performance.now() - job.pong > this.#jobTimeoutMs) return this.#stop(cell);
        try { cell.worker.postMessage({ type: 'ping' }); } catch { }
      }, Math.ceil(this.#jobTimeoutMs / 3));
    }
    Promise.resolve().then(() => {
      if (!this.#hostCall) throw new Error('no host call handler');
      return this.#hostCall(call, job.data);
    }).then(value => ({ id, value }), error => ({ id, error: error.message || String(error) })).then(reply => {
      if (cell.job !== job || cell.stopping) return;
      job.calls -= 1;
      if (job.calls === 0 && this.#jobTimeoutMs) {
        clearInterval(job.liveness);
        this.#arm(cell, job);
      }
      try { cell.worker.postMessage({ type: 'host-reply', ...reply }); } catch { }
    });
  }

  #claim(job) {
    if (!job || job.settled) return false;
    job.settled = true;
    this.#disarm(job);
    return true;
  }

  async #finish(job, result) {
    result = { ...result, trustedWasmModules: this.#trustedWasmModules };
    try {
      const evaluated = performance.now();
      const receipts = job.data.ledger === 'caller' ? [] : await this.#persist('append', job.data, result);
      const timings = { gate: evaluated - job.prepared, ledger: job.prepared - job.started + performance.now() - evaluated };
      job.resolve({ ...result, receipts, ...(job.data.timing === true ? { timings } : {}) });
    }
    catch (error) { error.result = result; job.reject(error); }
  }

  close() {
    this.#closing = true;
    clearTimeout(this.#holdTimer);
    this.#dump?.close();
    return this.#closed ||= (async () => {
      await Promise.allSettled([...this.#pending, this.#sharing]);
      await this.#ledger.close();
      this.#stopping = true;
      await Promise.all([...this.#cells].map(cell => cell.worker.terminate()));
    })();
  }
}

function poolDumpOptions(options) {
  if (options === false) return null;
  const { enabled, directory, env = process.env, ...rest } = options && typeof options === 'object' ? options : {};
  if (!(enabled ?? (options === true || directory !== undefined || dumpListEnabled(env)))) return null;
  const merged = { ...POOL_DUMP_DEFAULTS, ...rest, directory, env };
  if (!Number.isSafeInteger(merged.floor) || merged.floor < 0 || ![merged.holdMs, merged.intervalMs, merged.settleMs].every(positive)) throw new TypeError('dump list floor must be a non-negative integer and holdMs, intervalMs and settleMs positive integers');
  return merged;
}
