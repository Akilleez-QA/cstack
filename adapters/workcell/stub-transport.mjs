import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { sha256 } from './kernels/common.mjs';

let index = 0;

export function generate(prompt) {
  if (!process.env.CSTACK_STUB_TRANSPORT_SCRIPT) throw new Error('the stub transport has no script');
  const scriptPath = resolve(process.env.CSTACK_STUB_TRANSPORT_SCRIPT);
  const script = JSON.parse(readFileSync(scriptPath, 'utf8'));
  if (index >= script.responses.length) throw new Error('the stub transport has no more responses');
  const text = readFileSync(new URL(script.responses[index++], pathToFileURL(scriptPath)), 'utf8');
  return { text, model: { identity: 'stub-model-transport', version: sha256(JSON.stringify(prompt)).slice(0, 16) } };
}
