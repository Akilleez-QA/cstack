import { KernelRefusal, ToolInputError } from './common.mjs';
import { array, boundedOutput, check, evidence, exact, fail, get, ID, ID_TEXT, identifier, integer, measure, parseProfile, pyList, sorted, verdict } from './integer-profile.mjs';

const VERSION = '0.1.0';
const TOOLS = ['cinematic_gate', 'reference_bands', 'audio_gate', 'drift_verdict', 'cue_vocabulary_check', 'look_gate'];
const BOUNDARY = { observation_only: true, acceptance_decision: false, control_action: false };
const PLAYBOOK = 'docs/PLAYBOOK-film.md';
const PRODUCERS = 'tools/film/';
const MS_LIMIT = 86400000;
const ms = (value, name) => integer(value, name, 0, MS_LIMIT);
const METRIC = /^[a-z][a-z0-9_]{0,31}$/;
const METRIC_TEXT = '[a-z][a-z0-9_]{0,31}\\Z';
const metricName = (value, name) => identifier(value, name, METRIC, METRIC_TEXT);
const derived = (applies_to, note) => evidence(applies_to, 'derived', "the caller's measures", note, 'RECORDED');
const caller = (applies_to, note) => evidence(applies_to, 'caller', "the caller's input", note, 'CHECK');

function divRound(numerator, denominator) {
  const magnitude = Math.abs(numerator);
  const remainder = magnitude % denominator;
  const quotient = (magnitude - remainder) / denominator + (2 * remainder >= denominator ? 1 : 0);
  return numerator >= 0 ? quotient : (quotient === 0 ? 0 : -quotient);
}

function weightedMean(parts, name, covered) {
  let bound = 0, total = 0;
  for (const [shot, weight] of parts) {
    const value = shot.metrics.get(name);
    bound += Math.abs(value) * weight;
    total += value * weight;
  }
  if (bound < 2 ** 52) return divRound(total, covered);
  let exactTotal = 0n;
  for (const [shot, weight] of parts) exactTotal += BigInt(shot.metrics.get(name)) * BigInt(weight);
  const size = BigInt(covered), magnitude = exactTotal < 0n ? -exactTotal : exactTotal;
  const remainder = magnitude % size;
  const quotient = Number(magnitude / size + (2n * remainder >= size ? 1n : 0n));
  return exactTotal >= 0n ? quotient : (quotient === 0 ? 0 : -quotient);
}

const CAMERAS = ['static', 'pan', 'tilt', 'push/pull'];
const QUANTILES = [250, 500, 750];
const DEFAULT_RULE_METRICS = ['sharp', 'black', 'subject_motion', 'luma'];
const BLACK_FLOOR = 350;

function readShots(value) {
  const items = [];
  let names = null;
  array(value, 'shots', 1, 400).forEach((raw, i) => {
    const shot = exact(raw, `shots[${i}]`, ['start_ms', 'end_ms', 'camera', 'metrics']);
    const start = ms(shot.get('start_ms'), `shots[${i}].start_ms`), end = ms(shot.get('end_ms'), `shots[${i}].end_ms`);
    if (end <= start) fail(`shots[${i}] must end after it starts`);
    if (!CAMERAS.includes(shot.get('camera'))) fail(`shots[${i}].camera must be one of ${pyList(CAMERAS)}`);
    const metrics = shot.get('metrics');
    if (!(metrics instanceof Map) || metrics.size < 1 || metrics.size > 32) fail(`shots[${i}].metrics must be an object of 1 to 32 measures`);
    for (const [name, number] of metrics) {
      metricName(name, `shots[${i}].metrics key`);
      if (name === 'moving_share' || name === 'duration_ms') fail(`${name} is derived from the shots and cannot be supplied`);
      measure(number, `shots[${i}].metrics.${name}`);
    }
    const here = sorted(metrics.keys());
    if (names === null) names = here;
    else if (here.join() !== names.join()) fail(`shots[${i}] must carry the same metric names as shots[0]`);
    if (items.length && start < items.at(-1).end_ms) fail(`shots[${i}] overlaps the shot before it; shots are in time order and tile the film`);
    items.push({ start_ms: start, end_ms: end, camera: shot.get('camera'), metrics });
  });
  return [items, names];
}

function weightedPercentile(values, weights, permille) {
  const order = values.map((_, k) => k).sort((a, b) => values[a] - values[b] || a - b);
  const total = weights.reduce((a, b) => a + b, 0);
  let running = 0;
  for (const k of order) {
    running += weights[k];
    if (running * 1000 >= permille * total) return values[k];
  }
  return values[order.at(-1)];
}

function referenceBands(args) {
  exact(args, 'arguments', ['shots']);
  const [items, names] = readShots(args.get('shots'));
  const durations = items.map(s => s.end_ms - s.start_ms);
  const total = durations.reduce((a, b) => a + b, 0);
  const band = values => QUANTILES.map(q => weightedPercentile(values, durations, q));
  const moving = items.reduce((sum, s, i) => sum + (s.camera !== 'static' ? durations[i] : 0), 0);
  const metrics = {};
  for (const n of names) metrics[n] = band(items.map(s => s.metrics.get(n)));
  return ['bands_measured', { bands: { moving_share: divRound(1000 * moving, total), metrics }, duration_ms: band(durations), n_shots: items.length, total_ms: total, quantiles_permille: [...QUANTILES] }];
}

function readBands(value, needed) {
  const bands = exact(value, 'bands', ['moving_share', 'metrics']);
  integer(bands.get('moving_share'), 'bands.moving_share', 0, 1000);
  const metrics = bands.get('metrics');
  if (!(metrics instanceof Map) || metrics.size > 32) fail('bands.metrics must be an object of at most 32 bands');
  for (const [name, raw] of metrics) {
    metricName(name, 'bands.metrics key');
    const triple = array(raw, name, 3, 3).map((v, i) => measure(v, `bands.metrics.${name}[${i}]`));
    if (!(triple[0] <= triple[1] && triple[1] <= triple[2])) fail(`bands.metrics.${name} must be ordered p25 <= p50 <= p75`);
  }
  const absent = needed.filter(n => !metrics.has(n));
  if (absent.length) fail(`default rules need bands for ${pyList(absent)}; supply them or supply rules`);
  return bands;
}

function defaultRules(bands) {
  const m = bands.get('metrics');
  return [{ metric: 'moving_share', op: '>=', target: bands.get('moving_share') },
    { metric: 'sharp', op: '<=', target: m.get('sharp')[2] },
    { metric: 'sharp', op: '>=', target: Math.ceil(m.get('sharp')[0] / 2) + 0 },
    { metric: 'black', op: '<=', target: Math.max(m.get('black')[2], BLACK_FLOOR) },
    { metric: 'subject_motion', op: '>=', target: m.get('subject_motion')[0] },
    { metric: 'luma', op: '>=', target: m.get('luma')[0] }];
}

const readRules = (value, names) => array(value, 'rules', 1, 32).map((raw, i) => {
  const rule = exact(raw, `rules[${i}]`, ['metric', 'op', 'target']);
  if (rule.get('metric') !== 'moving_share' && !names.includes(rule.get('metric'))) fail(`rules[${i}].metric must be moving_share or a measured shot metric`);
  if (rule.get('op') !== '>=' && rule.get('op') !== '<=') fail(`rules[${i}].op must be >= or <=`);
  return { metric: rule.get('metric'), op: rule.get('op'), target: measure(rule.get('target'), 'target') };
});

function readSegments(value, filmEnd) {
  if (value === null || value === undefined) return [{ id: 'film', start_ms: 0, end_ms: filmEnd }];
  const seen = new Set();
  return array(value, 'segments', 1, 64).map((raw, i) => {
    const seg = exact(raw, `segments[${i}]`, ['id', 'start_ms', 'end_ms']);
    const id = identifier(seg.get('id'), `segments[${i}].id`);
    const start = ms(seg.get('start_ms'), 'start_ms'), end = ms(seg.get('end_ms'), 'end_ms');
    if (end <= start || seen.has(id)) fail(`segments[${i}] must have a unique id and end after it starts`);
    seen.add(id);
    return { id, start_ms: start, end_ms: end };
  });
}

function cinematicGate(args) {
  exact(args, 'arguments', ['shots'], ['bands', 'rules', 'segments']);
  const [items, names] = readShots(args.get('shots'));
  let rules, source;
  if (args.has('rules')) {
    rules = readRules(args.get('rules'), names);
    source = 'caller';
    if (args.has('bands')) readBands(args.get('bands'), []);
  } else if (args.has('bands')) {
    const absent = DEFAULT_RULE_METRICS.filter(n => !names.includes(n));
    if (absent.length) fail(`default rules need shot metrics ${pyList(absent)}`);
    rules = defaultRules(readBands(args.get('bands'), DEFAULT_RULE_METRICS));
    source = 'reference_bands_default';
  } else fail('cinematic_gate needs bands (for the default rules) or rules');
  const out = [], all = [];
  for (const seg of readSegments(args.get('segments'), Math.max(...items.map(s => s.end_ms)))) {
    const parts = items.map(s => [s, Math.min(s.end_ms, seg.end_ms) - Math.max(s.start_ms, seg.start_ms)]).filter(([, w]) => w > 0);
    const covered = parts.reduce((sum, [, w]) => sum + w, 0);
    const measured = {};
    if (covered) {
      for (const n of names) measured[n] = weightedMean(parts, n, covered);
      measured.moving_share = divRound(1000 * parts.reduce((sum, [s, w]) => sum + (s.camera !== 'static' ? w : 0), 0), covered);
    }
    const checks = rules.map(r => check(r.metric, Object.hasOwn(measured, r.metric) ? measured[r.metric] : null, r.op === '>=' ? r.target : null, r.op === '<=' ? r.target : null));
    all.push(...checks);
    out.push({ ...seg, covered_ms: covered, verdict: verdict(checks), measured, checks, failing: checks.filter(c => c.status !== 'pass').map(c => c.check) });
  }
  const judged = verdict(all);
  return [judged, { verdict: judged, rule_source: source, rules, segments: out, failing_segments: out.filter(s => s.verdict !== 'thresholds_met').map(s => s.id) }];
}

const LABEL = /^[\x20-\x7e]{1,96}$/;
const LEVELS = ['loudness_target', 'loudness_tolerance', 'true_peak_max', 'voice_over_bed_min', 'voice_over_bed_max'];
const CONTRACT_KEYS = [...LEVELS, 'cut_hit_share_min', 'required_heard', 'forbidden_heard', 'wer_max'];
const AUDIO_FIELDS = ['integrated_lufs', 'true_peak_dbtp', 'voice_over_bed_db', 'cuts', 'cuts_with_hit', 'heard', 'line_wer'];

const readLabels = (value, name) => array(value, name, 0, 128).map((label, i) => {
  if (typeof label !== 'string' || !LABEL.test(label)) fail(`${name}[${i}] must be printable ASCII text of 1 to 96 characters`);
  return label;
});

function readContract(value) {
  const contract = { loudness_target: -16000, loudness_tolerance: 1000, true_peak_max: -1000, voice_over_bed_min: 12000, voice_over_bed_max: 15000, cut_hit_share_min: 800, required_heard: ['Speech', 'Music'], forbidden_heard: ['Sine wave'], wer_max: 50 };
  if (value === null || value === undefined) return [contract, []];
  exact(value, 'contract', [], CONTRACT_KEYS);
  for (const [key, number] of value) {
    if (LEVELS.includes(key)) contract[key] = measure(number, `contract.${key}`);
    else if (key === 'cut_hit_share_min' || key === 'wer_max') contract[key] = integer(number, `contract.${key}`, 0, 1000);
    else contract[key] = readLabels(number, `contract.${key}`);
  }
  if (contract.loudness_tolerance < 0 || contract.voice_over_bed_min > contract.voice_over_bed_max) fail('contract tolerance must be >= 0 and voice_over_bed_min <= voice_over_bed_max');
  return [contract, sorted(value.keys())];
}

function readLineWer(value) {
  const seen = new Set();
  return array(value, 'line_wer', 1, 512).map((raw, i) => {
    const row = exact(raw, `line_wer[${i}]`, ['line', 'wer_permille']);
    const line = identifier(row.get('line'), `line_wer[${i}].line`);
    if (seen.has(line)) fail(`line_wer repeats line ${line}`);
    seen.add(line);
    return { line, wer_permille: integer(row.get('wer_permille'), 'wer_permille', 0, 10000) };
  });
}

function audioGate(args) {
  exact(args, 'arguments', AUDIO_FIELDS, ['contract']);
  const [contract, overrides] = readContract(args.get('contract'));
  const optional = (key, parse) => (args.get(key) === null ? null : parse(args.get(key)));
  const loud = optional('integrated_lufs', v => measure(v, 'integrated_lufs'));
  const peak = optional('true_peak_dbtp', v => measure(v, 'true_peak_dbtp'));
  const margin = optional('voice_over_bed_db', v => measure(v, 'voice_over_bed_db'));
  const cuts = optional('cuts', v => integer(v, 'cuts', 0, 100000));
  const hits = optional('cuts_with_hit', v => integer(v, 'cuts_with_hit', 0, 100000));
  if (cuts !== null && hits !== null && hits > cuts) fail('cuts_with_hit cannot exceed cuts');
  const share = cuts && hits !== null ? divRound(1000 * hits, cuts) : null;
  const heard = optional('heard', v => readLabels(v, 'heard'));
  const lines = optional('line_wer', readLineWer);
  const folded = heard === null ? null : new Set(heard.map(label => label.toLowerCase()));
  const missing = folded === null ? null : contract.required_heard.filter(x => !folded.has(x.toLowerCase()));
  const present = folded === null ? null : contract.forbidden_heard.filter(x => folded.has(x.toLowerCase()));
  const worst = lines === null ? null : lines.reduce((best, line) => (line.wer_permille > best.wer_permille ? line : best));
  const checks = [check('integrated_loudness', loud, contract.loudness_target - contract.loudness_tolerance, contract.loudness_target + contract.loudness_tolerance),
    check('true_peak', peak, null, contract.true_peak_max),
    check('voice_over_bed', margin, contract.voice_over_bed_min, contract.voice_over_bed_max),
    check('cut_hit_share', share, contract.cut_hit_share_min, null),
    check('heard_required_missing', missing === null ? null : missing.length, null, 0),
    check('heard_forbidden_present', present === null ? null : present.length, null, 0),
    check('worst_line_wer', worst === null ? null : worst.wer_permille, null, contract.wer_max)];
  const judged = verdict(checks);
  return [judged, { verdict: judged, checks, contract, contract_overrides: overrides, heard: { missing, forbidden_present: present },
    wer: { lines: lines === null ? 0 : lines.length, worst_line: worst === null ? null : worst.line, failing_lines: lines === null ? [] : lines.filter(x => x.wer_permille > contract.wer_max).map(x => x.line) },
    failing: checks.filter(c => c.status !== 'pass').map(c => c.check) }];
}

const DRIFT = { edge_f1: ['min', 450], mask_iou: ['min', 600], depth_error: ['max', null], identity_similarity: ['min', null] };
const DRIFT_KEYS = { edge_f1: 'edge_f1_min', mask_iou: 'mask_iou_min', depth_error: 'depth_error_max', identity_similarity: 'identity_similarity_min' };

const readSeries = (name, value) => array(value, `frames.${name}`, 1, 2048).map((number, i) => {
  if (number !== null) {
    if (name === 'depth_error') {
      measure(number, `frames.${name}[${i}]`);
      if (number < 0) fail('depth_error must be >= 0');
    } else integer(number, `frames.${name}[${i}]`, 0, 1000);
  }
  return number;
});

function driftVerdict(args) {
  exact(args, 'arguments', ['frames'], ['thresholds']);
  const frames = exact(args.get('frames'), 'frames', ['edge_f1'], Object.keys(DRIFT));
  const series = new Map();
  for (const name of Object.keys(DRIFT)) if (frames.has(name)) series.set(name, readSeries(name, frames.get(name)));
  const count = series.get('edge_f1').length;
  if ([...series.values()].some(v => v.length !== count)) fail('every per-frame series must have the same length');
  const given = exact(get(args, 'thresholds', new Map()), 'thresholds', [], Object.values(DRIFT_KEYS));
  const thresholds = {}, sources = {};
  for (const name of series.keys()) {
    const key = DRIFT_KEYS[name];
    if (given.has(key)) {
      thresholds[key] = integer(given.get(key), `thresholds.${key}`, 0, name === 'depth_error' ? 10 ** 12 : 1000);
      sources[key] = 'caller';
    } else if (DRIFT[name][1] !== null) {
      thresholds[key] = DRIFT[name][1];
      sources[key] = 'driftgate_default';
    } else fail(`${name} has no calibrated default; supply thresholds.${key}`);
  }
  const unused = [...given.keys()].filter(key => !Object.hasOwn(thresholds, key));
  if (unused.length) fail(`thresholds ${pyList(sorted(unused))} name a series that was not supplied`);
  const perFrame = [];
  for (let i = 0; i < count; i++) {
    const checks = [];
    for (const [name, values] of series) {
      const side = DRIFT[name][0], bound = thresholds[DRIFT_KEYS[name]];
      checks.push(check(name, values[i], side === 'min' ? bound : null, side === 'max' ? bound : null));
    }
    perFrame.push(checks);
  }
  const failing = [];
  perFrame.forEach((checks, i) => { if (checks.some(c => c.status === 'fail')) failing.push(i); });
  const summary = {};
  for (const [name, values] of series) {
    const side = DRIFT[name][0];
    let worst = null, worstFrame = null, total = 0, measured = 0;
    values.forEach((v, i) => {
      if (v === null) return;
      measured += 1;
      total += v;
      if (worst === null || (side === 'min' ? v < worst : v > worst)) { worst = v; worstFrame = i; }
    });
    summary[name] = { threshold: thresholds[DRIFT_KEYS[name]], side, worst, worst_frame: worstFrame, mean: measured ? divRound(total, measured) : null, measured_frames: measured,
      failing_frames: perFrame.filter(c => c.some(x => x.check === name && x.status === 'fail')).length };
  }
  const edge = series.get('edge_f1');
  const rank = i => [-perFrame[i].filter(c => c.status === 'fail').length, edge[i] !== null ? edge[i] : 1001];
  let worstFrame = 0, best = rank(0);
  for (let i = 1; i < count; i++) {
    const here = rank(i);
    if (here[0] < best[0] || (here[0] === best[0] && here[1] < best[1])) { worstFrame = i; best = here; }
  }
  const values = {};
  for (const [name, v] of series) values[name] = v[worstFrame];
  const judged = verdict(perFrame.flat());
  return [judged, { verdict: judged, gate: 'worst_frame', frames: count, first_failing_frame: failing.length ? failing[0] : null, failing_frames: failing.length, failing_frame_indices: failing.slice(0, 64),
    metrics: summary, thresholds, threshold_sources: sources, worst_frame: { frame: worstFrame, values } }];
}

function readIdentifiers(value, name, max, min = 0) {
  const items = array(value, name, min, max).map((v, i) => identifier(v, `${name}[${i}]`));
  if (new Set(items).size !== items.length) fail(`${name} must not repeat an id`);
  return items;
}

function cueVocabularyCheck(args) {
  exact(args, 'arguments', ['provided', 'lanes'], ['aliases', 'orders', 'min_gaps']);
  const markers = new Map();
  array(args.get('provided'), 'provided', 1, 1024).forEach((raw, i) => {
    const row = exact(raw, `provided[${i}]`, ['id', 't_ms'], ['end_ms']);
    const id = identifier(row.get('id'), `provided[${i}].id`);
    if (markers.has(id)) fail(`provided repeats id ${id}`);
    const start = ms(row.get('t_ms'), `provided[${i}].t_ms`);
    const end = row.has('end_ms') ? ms(row.get('end_ms'), `provided[${i}].end_ms`) : null;
    if (end !== null && end < start) fail(`provided[${i}] ends before it starts`);
    markers.set(id, { t_ms: start, end_ms: end });
  });
  const aliases = get(args, 'aliases', new Map());
  if (!(aliases instanceof Map) || aliases.size > 512) fail('aliases must be an object of at most 512 entries');
  for (const [key, target] of aliases) {
    identifier(key, 'aliases key');
    identifier(target, `aliases.${key}`);
    if (markers.has(key)) fail(`alias ${key} shadows a provided id`);
  }
  const broken = sorted([...aliases.keys()].filter(key => !markers.has(aliases.get(key))));
  const missing = new Set();
  const resolve = id => {
    if (markers.has(id)) return id;
    if (aliases.has(id) && markers.has(aliases.get(id))) return aliases.get(id);
    missing.add(id);
    return null;
  };
  const seen = new Set(), lanes = [];
  array(args.get('lanes'), 'lanes', 1, 64).forEach((raw, i) => {
    const row = exact(raw, `lanes[${i}]`, ['lane', 'references']);
    const lane = identifier(row.get('lane'), `lanes[${i}].lane`);
    if (seen.has(lane)) fail(`lanes repeats lane ${lane}`);
    seen.add(lane);
    const refs = readIdentifiers(row.get('references'), `lanes[${i}].references`, 256);
    const resolved = refs.map(ref => [ref, resolve(ref)]);
    lanes.push({ lane, references: refs.length, direct: refs.filter(r => markers.has(r)).length,
      by_alias: resolved.filter(([r, t]) => t !== null && t !== r).map(([r, t]) => ({ id: r, to: t })),
      missing: sorted(resolved.filter(([, t]) => t === null).map(([r]) => r)) });
  });
  const orders = [], checks = [];
  array(get(args, 'orders', []), 'orders', 0, 64).forEach((raw, i) => {
    const row = exact(raw, `orders[${i}]`, ['beat', 'sequence']);
    const beat = identifier(row.get('beat'), `orders[${i}].beat`);
    const steps = readIdentifiers(row.get('sequence'), `orders[${i}].sequence`, 64, 2).map((ref, k) => [k, ref, resolve(ref)]);
    const timed = steps.filter(([, , t]) => t !== null).map(([k, ref, t]) => [k, ref, markers.get(t).t_ms]);
    let violation = null, violations = 0;
    for (let n = 1; n < timed.length; n++) {
      if (timed[n][2] <= timed[n - 1][2]) {
        violations += 1;
        violation ??= { index: timed[n][0], id: timed[n][1], t_ms: timed[n][2], previous_id: timed[n - 1][1], previous_t_ms: timed[n - 1][2] };
      }
    }
    const orderCheck = check(`order:${beat}`, timed.length < 2 ? null : violations, null, 0);
    checks.push(orderCheck);
    orders.push({ beat, status: orderCheck.status, resolved: timed.length, unresolved: steps.filter(([, , t]) => t === null).map(([, ref]) => ref), first_violation: violation });
  });
  const gaps = [];
  array(get(args, 'min_gaps', []), 'min_gaps', 0, 64).forEach((raw, i) => {
    const row = exact(raw, `min_gaps[${i}]`, ['rule', 'after', 'next', 'min_ms']);
    const rule = identifier(row.get('rule'), `min_gaps[${i}].rule`);
    const after = resolve(identifier(row.get('after'), 'after')), next = resolve(identifier(row.get('next'), 'next'));
    let gap = null;
    if (after !== null && next !== null) {
      const end = markers.get(after).end_ms;
      gap = markers.get(next).t_ms - (end === null ? markers.get(after).t_ms : end);
    }
    const gapCheck = check(`gap:${rule}`, gap, ms(row.get('min_ms'), `min_gaps[${i}].min_ms`), null);
    checks.push(gapCheck);
    gaps.push({ rule, gap_ms: gap, min_ms: gapCheck.min, status: gapCheck.status });
  });
  const all = [check('missing_ids', missing.size, null, 0), check('broken_aliases', broken.length, null, 0), ...checks];
  const judged = verdict(all);
  return [judged, { verdict: judged, checks: all, missing_ids: sorted(missing), broken_aliases: broken.map(key => ({ id: key, to: aliases.get(key) })), lanes, orders, gaps, provided: markers.size,
    aliases_used: new Set(lanes.flatMap(lane => lane.by_alias.map(r => r.id))).size }];
}

const LOOK_METRICS = ['palette_ab', 'palette_L', 'median_L', 'range_L', 'clip_white', 'clip_black', 'detail_ratio', 'chroma_ratio'];
const LOOK_CHECKS = [['palette_ab', null, 'palette_ab'], ['palette_L', null, 'palette_L'], ['median_L', null, 'median_L'], ['range_L', null, 'range_L'], ['clip_white', null, 'clip_white'], ['clip_black', null, 'clip_black'], ['detail_ratio', 'detail_min', 'detail_max'], ['chroma_ratio', 'chroma_min', 'chroma_max']];
const LOOK_DEFAULTS = { palette_ab: 6000, palette_L: 8000, median_L: 10000, range_L: 15000, clip_white: 40, clip_black: 80, detail_min: 550, detail_max: 1800, chroma_min: 700, chroma_max: 1400 };
const lookCeiling = key => (key === 'clip_white' || key === 'clip_black' ? 1000 : 10 ** 9);

function lookGate(args) {
  exact(args, 'arguments', ['frames'], ['thresholds']);
  const given = exact(get(args, 'thresholds', new Map()), 'thresholds', [], Object.keys(LOOK_DEFAULTS));
  const thresholds = { ...LOOK_DEFAULTS }, sources = {};
  for (const [key, number] of given) thresholds[key] = integer(number, `thresholds.${key}`, 0, lookCeiling(key));
  for (const [low, high] of [['detail_min', 'detail_max'], ['chroma_min', 'chroma_max']]) if (thresholds[low] > thresholds[high]) fail(`thresholds.${low} must not exceed thresholds.${high}`);
  for (const key of Object.keys(LOOK_DEFAULTS)) sources[key] = given.has(key) ? 'caller' : 'lookgate_default';
  const frames = array(args.get('frames'), 'frames', 1, 128).map((raw, i) => {
    const row = exact(raw, `frames[${i}]`, ['id', 'metrics']);
    const id = identifier(row.get('id'), `frames[${i}].id`);
    const metrics = exact(row.get('metrics'), `frames[${i}].metrics`, LOOK_METRICS);
    for (const name of LOOK_METRICS) if (metrics.get(name) !== null) integer(metrics.get(name), `frames[${i}].metrics.${name}`, 0, lookCeiling(name));
    const checks = LOOK_CHECKS.map(([name, low, high]) => check(name, metrics.get(name), low === null ? null : thresholds[low], thresholds[high]));
    return { id, verdict: verdict(checks), checks, failing: checks.filter(c => c.status === 'fail').map(c => c.check), not_measured: checks.filter(c => c.status === 'not_measured').map(c => c.check) };
  });
  if (new Set(frames.map(f => f.id)).size !== frames.length) fail('frames must not repeat an id');
  const judged = verdict(frames.flatMap(f => f.checks));
  return [judged, { verdict: judged, gate: 'every_frame', role: 'rejection_alarm', frames, failing_frames: frames.filter(f => f.verdict === 'thresholds_not_met').map(f => f.id), thresholds, threshold_sources: sources }];
}

const receipts = {
  cinematic_gate(args) {
    const [assessment, result] = cinematicGate(args);
    const entries = [derived('result.segments', 'Duration-weighted means of the supplied per-shot measures (filmstats.py shots.json); this Foundation never sees the film. Being inside the reference bands is a measured proxy for cinematic quality, not the outcome (I12, I16).')];
    if (result.rule_source === 'caller') entries.push(caller('result.rules', "Rules supplied by the caller; their calibration is the caller's."));
    else entries.push(evidence('result.rules', 'cited', `${PRODUCERS}filmgate.py (default rules); ${PLAYBOOK}`, "filmgate.py's default rules, first used on the 2026-10-26 reference run against bands from its CG shots. Not yet calibrated on known-good and known-bad films (I3).", 'CHECK'));
    if (args.has('bands')) entries.push(caller('arguments.bands', 'Reference bands supplied by the caller; expected to come from reference_bands over the whole reference (I16).'));
    return [assessment, result, entries];
  },
  reference_bands(args) {
    const [assessment, result] = referenceBands(args);
    return [assessment, result, [derived('result.bands', 'Lower duration-weighted percentile per metric: the first value, in ascending order, at which cumulative screen time reaches 25, 50 or 75 % of the total. moving_share is the screen-time share of shots whose camera is not static.'),
      evidence('result.bands', 'cited', `${PRODUCERS}filmstats.py; ${PLAYBOOK}`, "The same method reproduces the duration band of the 2026-10-26 reference bands exactly (7.0, 14.67, 23.71 s over 41 shots). Which shots form a reference subset (for example CG shots only) is the caller's choice.", 'RECORDED')]];
  },
  audio_gate(args) {
    const [assessment, result] = audioGate(args);
    const entries = [derived('result.checks', 'Measured values from the caller (EBU R128 loudness and true peak, stem levels from audiostats.py, AudioSet classes from audiotags.py, per-line WER) against the contract.'),
      evidence('result.contract', 'cited', `${PLAYBOOK} (the mix gate)`, 'Mix contract learned on the 2026-10-26 reference run: -16 +/- 1 LUFS, <= -1 dBTP, voice 12-15 dB over the bed, a hit on >= 80 % of cuts, Speech and Music heard and no Sine wave, WER <= 5 % per line. The reference measured -16.9 LUFS, a bed about 14 dB under the voice and a hit on 78 % of cuts; the rejected cut read as sine wave at -34 LUFS.', 'CHECK')];
    if (result.contract_overrides.length) entries.push(caller('arguments.contract', `Contract values overridden by the caller: ${result.contract_overrides.join(', ')}.`));
    return [assessment, result, entries];
  },
  drift_verdict(args) {
    const [assessment, result] = driftVerdict(args);
    const entries = [derived('result.metrics', 'Per-frame control-fidelity measures from the caller (driftgate.py); the gate is the worst frame, never the clip mean.'),
      evidence('result.gate', 'cited', `${PLAYBOOK} (drift gate, I20)`, 'An unconditioned image-to-video pilot measured edge F1/mask IoU 0.98/0.84 at frame 0 and 0.08/0.0 at frame 90: a clip mean would have hidden the collapse.', 'RECORDED')];
    const sources = Object.values(result.threshold_sources);
    if (sources.includes('driftgate_default')) entries.push(evidence('result.thresholds', 'cited', `${PRODUCERS}driftgate.py (defaults)`, 'Starting thresholds edge F1 >= 0.45, mask IoU >= 0.60. Calibration pending: the control renders must pass with margin, an unconditioned clip must fail early, and perturbed passes must fail on the matching metric. The 2026-10-26 control bake-off clips failed from frame 0 (edge F1 mean 0.21-0.56), so edge extraction and thresholds are calibrated together.', 'CHECK'));
    if (sources.includes('caller')) entries.push(caller('arguments.thresholds', 'Thresholds supplied by the caller.'));
    return [assessment, result, entries];
  },
  cue_vocabulary_check(args) {
    const [assessment, result] = cueVocabularyCheck(args);
    return [assessment, result, [derived('result', 'Set and order comparison of the supplied ids, aliases and marker times.'),
      evidence('result.checks', 'cited', `AGENTS.md I18; ${PLAYBOOK} (lessons 66-67)`, 'Shared vocabulary is contract: every id two lanes must agree on is frozen before either lane starts and checked statically before any render.', 'RECORDED')]];
  },
  look_gate(args) {
    const [assessment, result] = lookGate(args);
    const entries = [derived('result.frames', 'Per-frame look measures from the caller (lookgate.py, frame against its approved target), each against its threshold; every frame must pass every check.'),
      evidence('result.role', 'cited', `${PLAYBOOK} (the look gate; the prep-stage decision)`, "A rejection alarm, not acceptance: thresholds_met means the frame was not rejected. The client stays the acceptance authority and judges moving proofs, not stills or metrics (I11, I12). Structure is drift_verdict's question; this one asks only whether the look could be right.", 'RECORDED')];
    const sources = Object.values(result.threshold_sources);
    if (sources.includes('lookgate_default')) entries.push(evidence('result.thresholds', 'cited', `${PRODUCERS}lookgate.py (defaults)`, 'Calibrated as an alarm on the 2026-10-26 reference run only: the concept frame against itself, re-encoded copies and a restyled keyframe pass (detail 0.99); all 14 rendered beats fail (11 on detail at 0.065-0.433 of the target, the end card at 2.37, b1 and b10 on palette and chroma) and unconditioned generated clips fail (detail 0.16-0.29). Not yet calibrated on other films or looks (I3).', 'CHECK'));
    if (sources.includes('caller')) entries.push(caller('arguments.thresholds', 'Thresholds supplied by the caller.'));
    return [assessment, result, entries];
  },
};

export function createKernel() {
  const run = (name, argumentsText) => {
    if (!TOOLS.includes(name)) throw new KernelRefusal('unknown_tool', `No kernel tool ${name}`);
    const { value, inputSha256 } = parseProfile(argumentsText);
    const base = { tool: name, version: VERSION, input_sha256: inputSha256, boundary: { ...BOUNDARY } };
    try {
      const [assessment, result, entries] = receipts[name](value);
      return boundedOutput({ ...base, status: 'ok', assessment, result, error: null, evidence: entries }, argumentsText.length);
    } catch (error) {
      if (!(error instanceof ToolInputError)) throw error;
      return { ...base, status: 'error', assessment: 'tool_error', result: null, error: error.message.slice(0, 1024),
        evidence: [evidence('error', 'derived', 'Foundation Film argument check', 'The request was refused before anything was judged.', 'RECORDED')] };
    }
  };
  return { foundation: 'foundation_film', version: VERSION, tools: TOOLS, run };
}
