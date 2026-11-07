import { createInterface } from 'node:readline';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { compilerIdentity, trustedWasmModules, workcellLimits } from './compiler.mjs';
import { renderPrompt, stripFences } from './coder-prompt.mjs';
import { IsolatePool } from '../../vendor/endoforge/core/runtime/isolate-pool.mjs';

const config = JSON.parse(process.argv[2]);
const send = message => process.stdout.write(`${JSON.stringify(message)}\n`);
const replies = new Map();
let nextCall = 0;
const hostCalls = (request, context) => new Promise((resolve, reject) => {
  const id = ++nextCall;
  replies.set(id, { resolve, reject });
  send({ call: id, request, context });
});
const pool = new IsolatePool({ hostPort: fileURLToPath(new URL('host-port.mjs', import.meta.url)), size: config.size ?? 1,
  isolation: config.isolation ?? 'process', trustedWasmModules, ...workcellLimits, frozenThroughLedger: true, hostCalls,
  warm: { foundations: config.foundations ?? [] }, jobTimeoutMs: config.jobTimeoutMs ?? 120000, cgroupRoot: config.cgroupRoot });
const { generate } = config.transport ? await import(pathToFileURL(config.transport).href) : { generate: () => { throw new Error('no model transport is configured'); } };

const commands = {
  ready: async () => { await pool.ready(); return { compiler: compilerIdentity() }; },
  generate: async request => {
    const answer = await generate({ ...request, text: renderPrompt(request) });
    return { ...answer, text: stripFences(answer.text) };
  },
  run: job => pool.run(job),
};

const stop = async code => {
  try { await Promise.race([pool.close(), new Promise(resolve => setTimeout(resolve, 2000))]); } finally { process.exit(code); }
};

createInterface({ input: process.stdin }).on('line', line => {
  const message = JSON.parse(line);
  if (message.reply !== undefined) {
    const pending = replies.get(message.reply);
    replies.delete(message.reply);
    return message.error === undefined ? pending?.resolve(message.result) : pending?.reject(new Error(message.error));
  }
  if (message.op === 'close') return stop(0);
  Promise.resolve().then(() => commands[message.op](message.input)).then(
    result => send({ id: message.id, result }),
    error => send({ id: message.id, error: error.message || String(error), result: error.result }));
}).on('close', () => process.exit(3));
