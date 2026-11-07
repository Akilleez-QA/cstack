const INTERFACE = `You write one kernel in AssemblyScript, the TypeScript-like language that compiles to WebAssembly. It is compiled with --runtime stub and runs once per step in a fresh instance.

Dialect limits: no JSON object, no closures, no union types, no any, no undefined, no regular expressions, no exceptions you can catch, no imports other than ./cstack. There is no JSON parser, so read values with field() and build JSON text by joining strings. Numbers read by field() are JSON text; pass them on as text, so nothing is lost. Top-level code must not call event, emit or a Foundation: do all work inside the exported functions.

Import what you use from "./cstack":
  event(): string                   the current event as JSON text
  emit(transition: string): void    gives the host your transition as JSON text; call it exactly once
  field(json: string, path: string): string   the raw JSON text at a dotted path, or "null"
  refrigeration(tool: string, args: string): string   calls that Foundation with JSON text arguments and returns its receipt as JSON text
  template(tool: string, args: string): string
Use only the Foundations declared below. Calling any other one fails the run, and so does a call the Foundation refuses, even if you ignore the answer.

Export exactly these two functions and nothing else:
  export function signature(): void   emit the signature below, exactly, as JSON text
  export function reduce(): void      handle one event

reduce gets {"kind":"case","state":null,"inputs":{...}} and emits {"value":<output>}, or {"error":{"path":"<input name>","reason":"<why>"}}.

To ask for a decision, emit it as data instead of a value: {"state":<anything to keep>,"effects":[{"capability":"poodo","operation":"propose_decision","payload":{"capability_id":"<a declared Foundation>","operation":"<tool>","arguments":{...},"expected_observation":"<text>","success_boundary":"<text>","failure_meaning":"<text>"}}]}. Payload fields are exactly those; you cannot name a grant, an approval or an identity. reduce then runs again with {"kind":"effect_results","state":<kept>,"inputs":{...},"results":[{"accepted":true,...}]}. A refused decision fails the run, whatever you emit next. Most kernels need no decisions.`;

const TOOLS = {
  foundation_refrigeration: `foundation_refrigeration, called with refrigeration(tool, args). Every receipt has status, result and error.
  saturation_pressure {"fluid":"NH3","temperature":{"value":-10,"unit":"degC"}}, optional "side":"bubble"|"dew" (required for blends), optional "atmosphere". Result: result.pressure.value in kPa(a), result.temperature.value, result.pressure_views.
  saturation_temperature {"fluid":"NH3","pressure":{"value":290,"unit":"kPa(a)"}}. Result: result.temperature.value in degC.
  convert_pressure {"pressure":{"value":1,"unit":"bar(a)"},"to_unit":"psia"}. Result: result.output.value.
  convert_temperature {"temperature":{"value":0,"unit":"degC"},"to_unit":"degF"}. Result: result.output.value.
  check_reading_against_saturation {"fluid":"NH3","pressure":{...},"temperature":{...}}. Result: result.superheat_style_delta.value_k, result.subcooling_style_delta.value_k.
  exposure_limits {"substance":"ammonia"}. resolve_equipment_kind {"term":"..."}.
  Pressure units: kPa(a), kPa(g), psia, psig, bar(a), bar(g). Temperature units: degC, degF, K, degR.`,
  foundation_template: `foundation_template, called with template(tool, args).
  echo_observation {"observation":"text"}. Result: result.observation.`,
};

const EXAMPLE = `Example shape, for a different task:
import { emit, event, field, template } from "./cstack";
export function signature(): void { emit("{\\"version\\":1,\\"name\\":\\"echo\\",\\"inputs\\":[{\\"path\\":\\"text\\",\\"type\\":\\"string\\",\\"unit\\":\\"text\\"}],\\"output\\":{\\"type\\":\\"string\\",\\"unit\\":\\"text\\"}}"); }
export function reduce(): void {
  const text = field(event(), "inputs.text");
  const receipt = template("echo_observation", "{\\"observation\\":" + text + "}");
  emit("{\\"value\\":" + field(receipt, "result.observation") + "}");
}`;

export function renderPrompt({ need, signature, declared_imports: declared, cases, diagnostics }) {
  const tools = declared.map(id => TOOLS[id] ?? `${id}: no in-process route is shipped, so a direct call is refused. Reach it through a decision.`);
  const repair = diagnostics?.length ? `\nYour previous candidate failed. Fix this:\n${JSON.stringify(diagnostics, null, 1)}\n` : '';
  return `${INTERFACE}

${EXAMPLE}

Task: ${need}

Signature to emit, exactly:
${JSON.stringify(signature)}

Declared Foundations:
${tools.join('\n')}

Example cases your kernel will get as inputs (its results are judged separately against the Foundation):
${JSON.stringify(cases)}
${repair}
Return only the AssemblyScript source, with no explanation and no code fences.`;
}

export function stripFences(text) {
  const match = /^\s*```[a-zA-Z]*\n([\s\S]*?)\n```\s*$/.exec(text);
  return match ? match[1] : text;
}
