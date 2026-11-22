// The runner's three ports and their default local adapters.
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { Worker } from 'node:worker_threads';
import type { AcceptanceTest, IntentRef } from '@cstack/contracts';

export type CallJob = { entry: string; call: string; cases: unknown[]; predicate?: string; names?: string[] };
export type CallOutcome = { fatal: string } | { results: { out?: unknown; holds?: boolean; error?: string }[] };
export type CommandOutcome = { exit: number | null; stdout_sha256: string; stderr_tail: string; fatal?: string };
/** The owner's answer, or null while it is pending. The host's ApprovalPort sits behind this. */
export type OwnerAnswer = { passed: boolean; answered_by: string; note?: string } | null;

export type Ports = {
  calls: (job: CallJob) => Promise<CallOutcome>;
  commands: (argv: string[], cwd: string) => Promise<CommandOutcome>;
  owner: (test: AcceptanceTest, ref: IntentRef) => Promise<OwnerAnswer>;
};

export function workerCalls({ timeoutMs = 10_000, heapMb = 256 } = {}): Ports['calls'] {
  return (job) => new Promise((resolve) => {
    const worker = new Worker(new URL('./worker.ts', import.meta.url), {
      workerData: job, resourceLimits: { maxOldGenerationSizeMb: heapMb }, stdout: true, stderr: true,
    });
    let done = false;
    const finish = (o: CallOutcome) => { if (!done) { done = true; clearTimeout(timer); void worker.terminate(); resolve(o); } };
    const timer = setTimeout(() => finish({ fatal: `timed out after ${timeoutMs} ms` }), timeoutMs);
    worker.once('message', (m) => finish(m as CallOutcome));
    worker.once('error', (e) => finish({ fatal: `the delivered module failed to load or crashed: ${e.message}` }));
    worker.once('exit', (code) => finish({ fatal: `the worker exited (${code}) without reporting` }));
  });
}

const STDOUT_CAP = 1 << 20;

export function localCommands({ timeoutMs = 30_000 } = {}): Ports['commands'] {
  return (argv, cwd) => new Promise((resolve) => {
    const [cmd, ...args] = argv;
    const child = spawn(cmd === 'node' ? process.execPath : cmd!, args, {
      cwd, env: { PATH: process.env.PATH ?? '', HOME: cwd, LANG: 'C.UTF-8' }, stdio: ['ignore', 'pipe', 'pipe'],
    });
    const hash = createHash('sha256');
    let size = 0, stderr = '', fatal: string | undefined;
    child.stdout.on('data', (b: Buffer) => {
      size += b.length;
      if (size > STDOUT_CAP) { fatal = 'stdout exceeded 1 MiB'; child.kill('SIGKILL'); } else hash.update(b);
    });
    child.stderr.on('data', (b: Buffer) => { stderr = (stderr + b.toString()).slice(-500); });
    const timer = setTimeout(() => { fatal = `timed out after ${timeoutMs} ms`; child.kill('SIGKILL'); }, timeoutMs);
    child.on('error', (e) => { fatal = e.message; });
    child.on('close', (code) => {
      clearTimeout(timer);
      resolve({ exit: code, stdout_sha256: hash.digest('hex'), stderr_tail: stderr, ...(fatal ? { fatal } : {}) });
    });
  });
}

/** No owner channel wired: every owner check stays pending. */
export const noOwner: Ports['owner'] = async () => null;
