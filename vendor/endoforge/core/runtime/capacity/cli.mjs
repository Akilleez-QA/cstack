#!/usr/bin/env node
import { createShareMeter, INTERFACE_VERSION, plan, probe } from './index.mjs';

const [command = 'plan', ...rest] = process.argv.slice(2);
const flag = name => { const hit = rest.find(item => item.startsWith(`--${name}=`)); return hit === undefined ? undefined : hit.slice(name.length + 3); };
const usage = 'usage: cli.mjs probe | plan [--queues=N] [--allotment=CPUS] | share [--ms=1000]';
const number = (name, test) => { const raw = flag(name); if (raw === undefined) return undefined; const value = Number(raw); if (!test(value)) { process.stderr.write(`${usage}\n`); process.exit(2); } return value; };
const out = value => process.stdout.write(`${JSON.stringify({ interface: INTERFACE_VERSION, ...value })}\n`);
if (command === 'probe') out({ probe: probe() });
else if (command === 'plan') out({ probe: probe(), plan: plan({ queues: number('queues', Number.isSafeInteger) ?? 1, allotment: number('allotment', value => value > 0) }) });
else if (command === 'share') {
  const meter = createShareMeter(probe());
  await new Promise(done => setTimeout(done, number('ms', value => Number.isSafeInteger(value) && value > 0) ?? 1000));
  out({ share: meter.sample() });
} else { process.stderr.write(`${usage}\n`); process.exit(2); }
