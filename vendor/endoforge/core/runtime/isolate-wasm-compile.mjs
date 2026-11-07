import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { parentPort, workerData } from 'node:worker_threads';
import { installWasmLimit } from './isolate-wasm.mjs';

const { wasmMemoryMaxMb, trustedWasmModules, sources } = workerData;
const check = installWasmLimit(wasmMemoryMaxMb, () => process.exit(18), trustedWasmModules);
parentPort.postMessage(sources.flatMap(({ sha256, path }) => {
  const bytes = readFileSync(path);
  if (createHash('sha256').update(bytes).digest('hex') !== sha256) return [];
  const module = new WebAssembly.Module(bytes);
  return [{ sha256, module, data: check.describe(module) }];
}));
