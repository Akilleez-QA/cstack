// Runs calls into the delivered module inside a worker thread, so a hang or a crash in the
// kernel ends the worker and not the runner. This is the stand-in until the EndoForge cell
// (createLoopPool) takes over; it is isolation for reliability, not a security sandbox.
import { parentPort, workerData } from 'node:worker_threads';
import { pathToFileURL } from 'node:url';

type Job = { entry: string; call: string; cases: unknown[]; predicate?: string; names?: string[] };
const job = workerData as Job;

// Typed arrays and other array-likes come back as plain arrays so they compare as JSON.
function plain(v: unknown): unknown {
  if (ArrayBuffer.isView(v) && !(v instanceof DataView)) return Array.from(v as unknown as ArrayLike<number>);
  if (Array.isArray(v)) return v.map(plain);
  if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, plain(x)]));
  return v;
}

const mod = await import(pathToFileURL(job.entry).href);
const fn = mod[job.call] ?? mod.default?.[job.call];
if (typeof fn !== 'function') {
  parentPort!.postMessage({ fatal: `the delivered module exports no function "${job.call}"` });
} else {
  const holds = job.predicate === undefined ? null
    : new Function(...job.names!, 'out', `"use strict"; return (${job.predicate});`);
  const results = [];
  for (const input of job.cases) {
    try {
      // The kernel may change its input in place, so it gets a copy and the predicate sees the original.
      const out = plain(await fn(structuredClone(input)));
      if (!holds) { results.push({ out }); continue; }
      const args = job.names!.length === 1 && job.names![0] === 'input' ? [input] : job.names!.map((n) => (input as Record<string, unknown>)[n]);
      results.push({ out, holds: holds(...args, out) === true });
    } catch (e) {
      results.push({ error: e instanceof Error ? `${e.name}: ${e.message}` : String(e) });
    }
  }
  parentPort!.postMessage({ results });
}
