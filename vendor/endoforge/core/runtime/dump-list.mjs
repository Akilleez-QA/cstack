import { randomBytes } from 'node:crypto';
import { closeSync, fsyncSync, mkdirSync, openSync, renameSync, rmSync, statSync, writeSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

export const SCHEMA = 'memguard-dump/1';
export const SIGNAL = 'SIGUSR2';
export const REFRESH_MS = 2000;
export const NAME = /^[A-Za-z0-9_.-]{1,64}$/;

export function dumpListDirectory(env = process.env) {
  const state = typeof env.XDG_STATE_HOME === 'string' && env.XDG_STATE_HOME.startsWith('/') ? env.XDG_STATE_HOME : join(homedir(), '.local', 'state');
  return join(state, 'memguard', 'dump-list.d');
}

export function dumpListEnabled(env = process.env) {
  if (env.ENDOFORGE_DUMP_LIST === '0') return false;
  if (env.ENDOFORGE_DUMP_LIST === '1') return true;
  try { return statSync(dumpListDirectory(env)).isDirectory(); } catch { return false; }
}

export function writeAtomic(directory, file, text) {
  const temp = join(directory, `.${file}.${randomBytes(6).toString('hex')}.tmp`);
  const fd = openSync(temp, 'wx', 0o600);
  try {
    writeSync(fd, text);
    fsyncSync(fd);
  } catch (error) {
    closeSync(fd);
    rmSync(temp, { force: true });
    throw error;
  }
  closeSync(fd);
  try { renameSync(temp, join(directory, file)); } catch (error) { rmSync(temp, { force: true }); throw error; }
}

const listening = new Set();
const registered = new Set();
let exitHook = false;
const onSignal = () => { for (const holder of [...listening]) holder.shedNow(); };
const removeAll = () => { for (const holder of [...registered]) holder.remove(); };

const inert = Object.freeze({ enabled: false, refused: null, path: null, bytes: 0, writes: 0, sheds: 0, refresh() {}, shedNow: () => Promise.resolve(), close() {} });

export function signalConflict(target = process) {
  const report = target.report;
  return report && report.reportOnSignal && report.signal === SIGNAL ? 'report-on-signal' : null;
}

export function registerHolder({ name, priority, measure, shed, pid = process.pid, listen = pid === process.pid, env = process.env,
  directory, refreshMs = REFRESH_MS, enabled = directory !== undefined || dumpListEnabled(env) } = {}) {
  if (typeof name !== 'string' || !NAME.test(name)) throw new TypeError('holder name must match [A-Za-z0-9_.-]{1,64}');
  if (!Number.isSafeInteger(priority) || priority < 0 || priority > 199) throw new TypeError('priority must be an integer from 0 to 199');
  if (typeof measure !== 'function') throw new TypeError('measure must be a function');
  if (shed !== undefined && typeof shed !== 'function') throw new TypeError('shed must be a function');
  if (!Number.isSafeInteger(pid) || pid <= 0) throw new TypeError('pid must be a positive integer');
  if (!enabled) return inert;
  const conflict = listen ? signalConflict() : null;
  if (conflict) return Object.freeze({ ...inert, refused: conflict });
  const folder = directory ?? dumpListDirectory(env);
  mkdirSync(folder, { recursive: true, mode: 0o700 });
  const file = `${pid}-${name}.json`;
  let last = -1, checkedAt = 0, timer = null, closed = false, shedding = null, again = false;
  const holder = {
    enabled: true,
    refused: null,
    path: join(folder, file),
    bytes: 0,
    writes: 0,
    sheds: 0,
    errors: 0,
    write(bytes) {
      try {
        writeAtomic(folder, file, `${JSON.stringify({ schema: SCHEMA, pid, name, priority, sheddable_bytes: bytes, signal: SIGNAL, updated: new Date().toISOString() })}\n`);
        holder.writes += 1;
        last = bytes;
      } catch { holder.errors += 1; }
    },
    measure() {
      let bytes = 0;
      try { bytes = Math.max(0, Math.floor(Number(measure()) || 0)); } catch { holder.errors += 1; }
      holder.bytes = bytes;
      return bytes;
    },
    refresh(force = false) {
      if (closed) return;
      if (!force) {
        const wait = refreshMs - (Date.now() - checkedAt);
        if (wait > 0) {
          if (!timer) { timer = setTimeout(() => { timer = null; holder.refresh(); }, wait); timer.unref(); }
          return;
        }
      }
      checkedAt = Date.now();
      const bytes = holder.measure();
      if (!force && bytes === last) return;
      clearTimeout(timer);
      timer = null;
      holder.write(bytes);
    },
    shedNow() {
      if (closed) return Promise.resolve();
      if (shedding) { again = true; return shedding; }
      shedding = (async () => {
        do {
          again = false;
          holder.sheds += 1;
          try { await shed?.(); } catch { holder.errors += 1; }
          holder.refresh(true);
        } while (again && !closed);
        shedding = null;
      })();
      return shedding;
    },
    remove() {
      registered.delete(holder);
      try { rmSync(holder.path, { force: true }); } catch {}
    },
    close() {
      if (closed) return;
      closed = true;
      clearTimeout(timer);
      holder.remove();
      if (listening.delete(holder) && !listening.size) process.removeListener(SIGNAL, onSignal);
    },
  };
  if (listen) {
    if (!listening.size) process.on(SIGNAL, onSignal);
    listening.add(holder);
  }
  registered.add(holder);
  if (!exitHook) { exitHook = true; process.once('exit', removeAll); }
  holder.refresh(true);
  return holder;
}
