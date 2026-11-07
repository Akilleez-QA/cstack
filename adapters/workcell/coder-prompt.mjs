const INTERFACE = `You write one kernel in AssemblyScript, the TypeScript-like language that compiles to WebAssembly. It is compiled with --runtime stub and runs once per step in a fresh instance.

Dialect limits: no JSON object, no closures, no union types, no any, no undefined, no regular expressions, no exceptions you can catch, no imports other than ./cstack. There is no JSON parser, so read values with field() and build JSON text by joining strings. Numbers read by field() are JSON text; pass them on as text, so nothing is lost. Top-level code must not call event, emit or a Foundation: do all work inside the exported functions.

Import what you use from "./cstack":
  event(): string                   the current event as JSON text
  emit(transition: string): void    gives the host your transition as JSON text; call it exactly once
  field(json: string, path: string): string   the raw JSON text at a dotted path, or "null"
  refrigeration(tool: string, args: string): string   calls that Foundation with JSON text arguments and returns its receipt as JSON text
  template(tool: string, args: string): string
  film(tool: string, args: string): string
  robotics(tool: string, args: string): string
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
  foundation_film: `foundation_film, called with film(tool, args). Every number is a JSON integer in milli-units; a float, an exponent, a repeated key or a unicode escape is refused, and a refusal fails the run. Every receipt has status, assessment, result and error; assessment is thresholds_met, thresholds_not_met, not_scored or tool_error.
  reference_bands {"shots":[{"start_ms":0,"end_ms":7000,"camera":"static","metrics":{"sharp":500}}]}. Cameras: static, pan, tilt, push/pull. Result: result.bands.moving_share, result.bands.metrics.<name>, result.duration_ms.
  cinematic_gate {"shots":[...],"bands":{...}} or {"shots":[...],"rules":[{"metric":"sharp","op":">=","target":300}]}, optional "segments":[{"id":"s1","start_ms":0,"end_ms":9000}]. Result: result.verdict, result.segments, result.failing_segments.
  audio_gate {"integrated_lufs":-16500,"true_peak_dbtp":-1200,"voice_over_bed_db":14000,"cuts":50,"cuts_with_hit":40,"heard":["Speech","Music"],"line_wer":[{"line":"l1","wer_permille":20}]}; each may be null, all are required. Optional "contract". Result: result.verdict, result.failing.
  drift_verdict {"frames":{"edge_f1":[980,80]}}, optional mask_iou, depth_error, identity_similarity series and "thresholds". Result: result.verdict, result.first_failing_frame, result.metrics.
  cue_vocabulary_check {"provided":[{"id":"a","t_ms":1000}],"lanes":[{"lane":"l1","references":["a"]}]}, optional "aliases", "orders", "min_gaps". Result: result.verdict, result.missing_ids.
  look_gate {"frames":[{"id":"f1","metrics":{"palette_ab":5000,"palette_L":7000,"median_L":9000,"range_L":14000,"clip_white":30,"clip_black":70,"detail_ratio":990,"chroma_ratio":1000}}]}, optional "thresholds". Result: result.verdict, result.failing_frames.`,
  foundation_robotics: `foundation_robotics, called with robotics(tool, args). Every number is a JSON integer in milli-SI units; a float, an exponent, a repeated key or a unicode escape is refused, and a refusal fails the run. So is a result too close to a rounding boundary to match the pinned Python (numeric_boundary), and a coordinate over 33554432 mm in balance_check or ik_check. Every receipt has status, assessment, result and error.
  scale_timing {"height_mm":6000} or {"leg_length_mm":928}, optional gravity_mm_s2, froude_permille, appendages, drop_heights_mm. Result: result.leg_swing_period_ms, result.walk, result.factors.time_permille.
  gait_check {"leg_length_mm":928,"speed_mm_s":1348,"stride_mm":1617,"cycle_ms":1200,"feet":[{"id":"l","stance_ms":633,"slide_mean_mm_s":3}]}, optional gait walk|run|stand, up_axis y|z, foot "track" with fps_milli. Result: result.verdict, result.measured.
  balance_check {"fps_milli":24000,"frames":[{"com_mm":[0,900,0],"support_mm":[[-200,0,-200],[200,0,-200],[200,0,200]]}],"mode":"static"}, mode static|dynamic|stop. Result: result.verdict, result.worst, result.first_failing_frame.
  ik_check {"joints":[{"id":"hip","type":"revolute","axis":[0,0,1],"origin_mm":[0,0,0],"min":-2000,"max":2000}],"tip_mm":[400,0,0],"poses":[{"q":[100],"target_mm":[400,40,0]}]}; revolute q is in mrad. Result: result.verdict, result.poses, result.reach_mm.
  mechanism_check {"kind":"rotor_strobe","blades":5,"speed_mrad_s":62832,"fps_milli":24000}; kinds gear_train, gear_mesh, slider_crank, four_bar, rotor_strobe. Result: result.verdict, result.detail.
  squash_check {"frames":[{"scale_permille":[1180,780,1180]}]}. Result: result.verdict, result.worst_frame.`,
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
