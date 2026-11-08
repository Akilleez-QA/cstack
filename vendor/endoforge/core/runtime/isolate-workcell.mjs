import { parentPort, threadId, resourceLimits, workerData, Worker } from 'node:worker_threads';
import { evaluateCandidates } from '../engine/evaluator.mjs';
import { installWasmLimit } from './isolate-wasm.mjs';

const options = workerData || JSON.parse(process.argv[2]);
if (!parentPort) new Worker(`const { workerData: parent } = require('node:worker_threads');
setInterval(() => { if (process.ppid !== parent) process.kill(process.pid, 'SIGKILL'); }, 250);`, { eval: true, workerData: process.ppid,
  resourceLimits: { maxOldGenerationSizeMb: 8, maxYoungGenerationSizeMb: 2 } }).unref();
const { wasmMemoryMaxMb } = options;
const send = result => parentPort ? parentPort.postMessage(result) : process.send(result);
const metadata = { workcell: parentPort ? threadId : process.pid,
  resourceLimits: parentPort ? resourceLimits : options.resourceLimits, wasmMemoryMaxMb };
const nativeInstantiate = WebAssembly.instantiate;
let undiciTimer;
if (Number(process.versions.undici?.split('.')[0]) < 8) await Promise.race([new Promise(resolve => {
  WebAssembly.instantiate = (...args) => {
    WebAssembly.instantiate = nativeInstantiate;
    const pending = nativeInstantiate(...args);
    pending.then(resolve, resolve);
    return pending;
  };
  void globalThis.Response;
}), new Promise(resolve => { undiciTimer = setTimeout(resolve, 2000); })]);
clearTimeout(undiciTimer);
WebAssembly.instantiate = nativeInstantiate;
const checkWasm = installWasmLimit(wasmMemoryMaxMb, error => {
  send({ type: 'limit', error });
  process.exit(18);
}, options.trustedWasmModules, options.sharedWasmModules);

const warmed = options.warm ? (async () => { await (await import(options.hostPort)).warm(options.warm); })().catch(error => error.message || String(error)) : null;

const replies = new Map();
let nextCall = 0;
const callHost = message => new Promise((resolve, reject) => {
  const id = ++nextCall;
  replies.set(id, { resolve, reject });
  send({ ...message, id });
});
const host = call => callHost({ type: 'host-call', call });
const hostCall = request => callHost({ type: 'host_call', request });
const verifyFrozen = reference => callHost({ type: 'host_frozen', reference });

(parentPort || process).on('message', async message => {
  if (message.type === 'ping') return send({ type: 'pong' });
  if (message.type === 'host-reply' || message.type === 'host_reply') {
    const reply = replies.get(message.id);
    replies.delete(message.id);
    if (message.error === undefined) reply?.resolve(message.type === 'host-reply' ? message.value : message.result);
    else reply?.reject(new Error(message.error));
    return;
  }
  const { reference, candidates, hostPort, portOptions, frozenThroughLedger } = message;
  try {
    const warmError = await warmed;
    if (warmError) throw new Error(`warm failed: ${warmError}`);
    checkWasm.begin();
    const { createPort } = await import(hostPort);
    const port = await createPort(portOptions, { host, hostCall });
    const report = port.evaluate ? await port.evaluate(evaluateCandidates, reference) : await evaluateCandidates(reference, candidates, port, frozenThroughLedger ? { verifyFrozen } : {});
    checkWasm();
    const evidence = port.evidence?.();
    send({ status: report.stage === 'outcome_unknown' ? 'outcome_unknown' : report.stage === 'waiting' ? 'waiting' : 'completed',
      reason: null, report, ...(evidence === undefined ? {} : { evidence }), ...metadata });
  } catch (error) {
    checkWasm();
    send({ status: 'outcome_unknown', reason: error.message || String(error),
      report: null, ...metadata });
  }
});
send({ type: 'ready', warmError: await warmed });
