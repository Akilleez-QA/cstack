import { KernelRefusal, isObject, parseArguments } from './common.mjs';

const VERSION = '0.1.0';
const BOUNDARY = { observation_only: true, domain_determination: false, control_action: false };
const entry = (applies_to, note) => ({ applies_to, evidence: { basis: { kind: 'practice', note }, status: 'CHECK' } });

export function createKernel() {
  const run = (name, argumentsText) => {
    if (name !== 'echo_observation') throw new KernelRefusal('unknown_tool', `No kernel tool ${name}`);
    const { value, inputSha256 } = parseArguments(argumentsText);
    if (!isObject(value)) throw new KernelRefusal('invalid_arguments', 'Arguments must be an object');
    const base = { tool: name, version: VERSION, input_sha256: inputSha256, boundary: { ...BOUNDARY } };
    if (Object.keys(value).length !== 1 || !Object.hasOwn(value, 'observation')) {
      return { ...base, status: 'error', result: null, error: 'echo_observation takes exactly one argument: observation',
        evidence: [entry('error', 'Argument check by the template Foundation; the request was not observed.')] };
    }
    const observation = value.observation;
    if (typeof observation !== 'string' || observation.length < 1 || observation.length > 256) {
      return { ...base, status: 'error', result: null, error: 'observation must be a string of 1 to 256 characters',
        evidence: [entry('error', 'Argument check by the template Foundation; the request was not observed.')] };
    }
    return { ...base, status: 'ok', result: { observation }, error: null,
      evidence: [entry('result.observation', "Placeholder echo of the caller's own input; no domain source backs it.")] };
  };
  return { foundation: 'foundation_template', version: VERSION, tools: ['echo_observation'], run };
}
