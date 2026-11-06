import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const COMPILER = Object.freeze({ name: 'assemblyscript', version: '0.28.20' });
const modules = fileURLToPath(new URL('node_modules/', import.meta.url));
const pins = Object.freeze({
  'assemblyscript/dist/asc.js': 'ebce85ca33b6e2d901ad2f9fe2daf4f98a42217a0bcbbb40fd98991ababd3891',
  'assemblyscript/dist/assemblyscript.js': 'b0ea444edfff355fe2981451358c5b8b24996f5e9190e02bceae60c94adeea19',
  'binaryen/index.js': '08e348487a67b24351d5ff81ae707e051b5d213bd359d84ad90c789f3793001a',
  'long/index.js': '8d6b1d2162ff21170db73d6b91e313e6b90bd35acfdd60453b2792ec433ae69e',
});
export const trustedWasmModules = Object.freeze([Object.freeze({
  name: 'assemblyscript-0.28.20-f64-pow',
  sha256: '24982099e4fafe2b0779b0d4cb7a78b8264ebd3890e3c8d75b6d54a3e333e189',
  maximumPages: 16,
})]);
export const workcellLimits = Object.freeze({ wasmMemoryMaxMb: 4096,
  resourceLimits: Object.freeze({ maxOldGenerationSizeMb: 1024, maxYoungGenerationSizeMb: 32 }) });

const digest = data => createHash('sha256').update(data).digest('hex');
const prelude = readFileSync(new URL('prelude.ts', import.meta.url), 'utf8');
export const preludeSha256 = digest(prelude);

export function compilerIdentity() {
  const identity = { ...COMPILER, files: {}, prelude_sha256: preludeSha256 };
  for (const [path, expected] of Object.entries(pins)) {
    const actual = digest(readFileSync(modules + path));
    if (actual !== expected) throw new Error(`compiler file differs from its pin: ${path}`);
    identity.files[path] = actual;
  }
  return identity;
}

let compiler;
export async function warmCompiler() {
  compiler ||= await import(pathToFileURL(`${modules}assemblyscript/dist/asc.js`).href);
  return compiler;
}

export async function compile(source) {
  const asc = await warmCompiler();
  const files = {}, overlay = { 'candidate.ts': source, 'cstack.ts': prelude };
  const stderr = asc.createMemoryStream();
  const result = await asc.main(['candidate.ts', '-O3', '--runtime', 'stub', '--noColors', '--initialMemory', '1',
    '--maximumMemory', '256', '--use', 'abort=', '--outFile', 'out.wasm'], {
    stdout: asc.createMemoryStream(), stderr,
    readFile: name => overlay[name] ?? null, writeFile: (name, data) => { files[name] = data; }, listFiles: () => [],
  });
  if (result.error || !files['out.wasm']) return { wasm: null, diagnostics: stderr.toString().slice(0, 4000) };
  return { wasm: files['out.wasm'], diagnostics: '' };
}
