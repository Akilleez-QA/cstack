import { KernelRefusal } from './common.mjs';
import { array, check, exact, fail, get, identifier, integer, verdict } from './integer-profile.mjs';
import { choice, exactCoordinates, gravity, ground, lib, mean, percentile, positive, pySum, rnd, roundHalfEven, thresholds, uniqueIds, upAxis, vec3 } from './robotics-numeric.mjs';

const GAIT_THRESHOLDS = ['froude_min', 'froude_max', 'stride_ratio_min', 'stride_ratio_max', 'duty_walk_min', 'slide_mean_mm_s', 'kinematic_mismatch_max', 'step_time_asymmetry_max'];
const BALANCE_THRESHOLDS = ['margin_mm', 'flight_gravity_error_max', 'derivative_window_ms'];
const MAX_REFERENCE_WINDOW = 10 ** 6;

export function createMotion(data) {
  const { value: defaultOf, defaults } = data;
  const hipPerHeight = defaultOf('anthropometry', 'hip_height_per_height');
  const referenceLeg = () => defaultOf('anthropometry', 'reference_height_mm') * hipPerHeight / 1000;

  const legLength = args => {
    if (args.has('leg_length_mm') === args.has('height_mm')) fail('give exactly one of leg_length_mm and height_mm');
    if (args.has('leg_length_mm')) return [positive(args.get('leg_length_mm'), 'leg_length_mm', 10 ** 7), 'caller'];
    return [positive(args.get('height_mm'), 'height_mm', 10 ** 7) * hipPerHeight / 1000, 'winter_hip_height'];
  };

  const predictedStride = (leg, froude) => (defaultOf('scale', 'stride_coefficient') / 1000) * leg * lib.pow(froude, defaultOf('scale', 'stride_exponent') / 1000);

  const walkAt = (leg, g, froude) => {
    const speed = Math.sqrt(froude * g * leg);
    const stride = predictedStride(leg, froude);
    const cycle = stride / speed;
    return { froude_permille: rnd(froude * 1000), speed_mm_s: rnd(speed), stride_mm: rnd(stride), step_mm: rnd(stride / 2), cycle_ms: rnd(cycle * 1000), step_ms: rnd(cycle * 500), cadence_milli_steps_per_min: rnd(2 / cycle * 60 * 1000) };
  };

  const scaleTiming = args => {
    exact(args, 'arguments', [], ['height_mm', 'leg_length_mm', 'gravity_mm_s2', 'froude_permille', 'appendages', 'drop_heights_mm']);
    const [leg, legSource] = legLength(args);
    const [g, gSource] = gravity(args);
    const table = array(get(args, 'froude_permille', defaultOf('scale', 'walk_froude_table')), 'froude_permille', 1, 8).map((f, i) => integer(f, `froude_permille[${i}]`, 1, 5000));
    const appendages = array(get(args, 'appendages', []), 'appendages', 0, 16);
    appendages.forEach((item, i) => {
      exact(item, `appendages[${i}]`, ['id', 'length_mm']);
      identifier(item.get('id'), `appendages[${i}].id`);
      positive(item.get('length_mm'), `appendages[${i}].length_mm`, 10 ** 7);
    });
    uniqueIds(appendages, 'appendages');
    const drops = array(get(args, 'drop_heights_mm', []), 'drop_heights_mm', 0, 16).map((h, i) => positive(h, `drop_heights_mm[${i}]`, 10 ** 7));
    const s = leg / referenceLeg();
    const rod = length => 2 * Math.PI * Math.sqrt(2 * length / (3 * g)) * 1000;
    const froudeMax = defaultOf('gait', 'froude_max');
    return ['timing_estimated', {
      leg_length_mm: rnd(leg), leg_source: legSource, gravity_mm_s2: rnd(g), gravity_source: gSource, reference_leg_mm: rnd(referenceLeg()),
      factors: { length_permille: rnd(s * 1000), time_permille: rnd(Math.sqrt(s) * 1000), speed_permille: rnd(Math.sqrt(s) * 1000), acceleration_permille: 1000, strength_to_weight_permille: rnd(1000 / s) },
      walk: table.map(f => walkAt(leg, g, f / 1000)),
      limits: { walk_run_froude_permille: froudeMax, walk_run_speed_mm_s: rnd(Math.sqrt(froudeMax / 1000 * g * leg)), max_walk_speed_mm_s: rnd(Math.sqrt(g * leg)) },
      leg_swing_period_ms: rnd(rod(leg)),
      appendages: appendages.map(a => ({ id: a.get('id'), length_mm: a.get('length_mm'), period_ms: rnd(rod(a.get('length_mm'))) })),
      drops: drops.map(h => ({ height_mm: h, fall_ms: rnd(Math.sqrt(2 * h / g) * 1000) })),
    }];
  };

  const readTrack = (foot, name, fps, up) => {
    const track = exact(foot.get('track'), `${name}.track`, ['positions_mm', 'contact']);
    const positions = array(track.get('positions_mm'), `${name}.track.positions_mm`, 2, 1200).map((p, i) => vec3(p, `${name}.track.positions_mm[${i}]`));
    const contact = array(track.get('contact'), `${name}.track.contact`, 2, 1200).map((c, i) => integer(c, `${name}.track.contact[${i}]`, 0, 1));
    if (contact.length !== positions.length) fail(`${name}.track: contact and positions_mm must have one entry per frame`);
    const dt = 1000 / fps;
    const slides = [];
    for (let i = 0; i < contact.length - 1; i++) if (contact[i] && contact[i + 1]) slides.push(lib.dist(ground(positions[i], up), ground(positions[i + 1], up)) / dt);
    const strikes = [];
    for (let i = 1; i < contact.length; i++) if (contact[i] && !contact[i - 1]) strikes.push(i);
    const stances = [];
    for (const s of strikes) {
      let end = s;
      while (end < contact.length && contact[end]) end += 1;
      if (end < contact.length) stances.push((end - s) * dt);
    }
    const pairs = strikes.slice(1).map((b, i) => [strikes[i], b]);
    return { contact_frames: contact.reduce((a, b) => a + b, 0), strikes: strikes.length, strike_times: strikes.map(s => s * dt),
      cycle: mean(pairs.map(([a, b]) => (b - a) * dt)), stance: mean(stances),
      stride: mean(pairs.map(([a, b]) => lib.dist(ground(positions[a], up), ground(positions[b], up)))),
      slide: slides.length ? [mean(slides), percentile(slides, 0.95), Math.max(...slides)] : [null, null, null] };
  };

  const asymmetry = (a, b) => {
    const events = [...a.map(t => [t, 0]), ...b.map(t => [t, 1])].sort((x, y) => x[0] - y[0] || x[1] - y[1]);
    const steps = [[], []];
    for (let i = 1; i < events.length; i++) if (events[i - 1][1] !== events[i][1]) steps[events[i - 1][1]].push(events[i][0] - events[i - 1][0]);
    const m1 = mean(steps[0]), m2 = mean(steps[1]);
    return m1 === null || m2 === null ? null : Math.abs(m1 - m2) / ((m1 + m2) / 2);
  };

  const gaitCheck = args => {
    exact(args, 'arguments', ['speed_mm_s'], ['leg_length_mm', 'height_mm', 'stride_mm', 'cycle_ms', 'feet', 'fps_milli', 'up_axis', 'gait', 'gravity_mm_s2', 'thresholds']);
    const [leg, legSource] = legLength(args);
    const [g] = gravity(args);
    const up = upAxis(args);
    const gait = choice(get(args, 'gait', 'walk'), 'gait', ['walk', 'run', 'stand']);
    const speed = integer(args.get('speed_mm_s'), 'speed_mm_s', 0, 10 ** 6);
    const [limits, sources] = thresholds(args, defaults('gait', GAIT_THRESHOLDS));
    const feet = array(get(args, 'feet', []), 'feet', 0, 4);
    feet.forEach((foot, i) => {
      exact(foot, `feet[${i}]`, ['id'], ['stance_ms', 'slide_mean_mm_s', 'track']);
      identifier(foot.get('id'), `feet[${i}].id`);
    });
    uniqueIds(feet, 'feet');
    let fps = null;
    if (feet.some(f => f.has('track'))) {
      if (!args.has('fps_milli')) fail('fps_milli is required with foot tracks');
      fps = positive(args.get('fps_milli'), 'fps_milli', 10 ** 6);
    }
    const tracks = new Map();
    feet.forEach((f, i) => { if (f.has('track')) tracks.set(f.get('id'), readTrack(f, `feet[${i}]`, fps, up)); });
    const trackCycles = [...tracks.values()].map(t => t.cycle).filter(v => v !== null);
    const trackStrides = [...tracks.values()].map(t => t.stride).filter(v => v !== null);
    let cycle = null, cycleSource = null, stride = null, strideSource = null;
    if (args.has('cycle_ms')) { cycle = positive(args.get('cycle_ms'), 'cycle_ms', 10 ** 7) / 1000; cycleSource = 'caller'; }
    else if (trackCycles.length) { cycle = mean(trackCycles); cycleSource = 'track'; }
    if (args.has('stride_mm')) { stride = positive(args.get('stride_mm'), 'stride_mm', 10 ** 7); strideSource = 'caller'; }
    else if (trackStrides.length) { stride = mean(trackStrides); strideSource = 'track'; }
    else if (cycle !== null && speed) { stride = speed * cycle; strideSource = 'speed_x_cycle'; }
    if (cycle === null && stride !== null && speed) { cycle = stride / speed; cycleSource = 'stride_over_speed'; }
    const froude = speed * speed / (g * leg);
    const checks = [];
    const measured = { froude_permille: rnd(froude * 1000), stride_mm: rnd(stride), cycle_ms: rnd(cycle === null ? null : cycle * 1000) };
    if (gait === 'walk') checks.push(check('froude_permille', measured.froude_permille, limits.froude_min, limits.froude_max));
    if (gait !== 'stand') {
      const predicted = speed ? predictedStride(leg, froude) : null;
      const ratio = stride !== null && predicted ? rnd(stride / predicted * 1000) : null;
      measured.predicted_stride_mm = rnd(predicted);
      measured.stride_ratio_permille = ratio;
      checks.push(check('stride_ratio_permille', ratio, limits.stride_ratio_min, limits.stride_ratio_max));
      if ((strideSource === 'caller' || strideSource === 'track') && (cycleSource === 'caller' || cycleSource === 'track') && stride) {
        const mismatch = rnd(Math.abs(speed * cycle - stride) / stride * 1000);
        measured.kinematic_mismatch_permille = mismatch;
        checks.push(check('kinematic_mismatch_permille', mismatch, 0, limits.kinematic_mismatch_max));
      }
    }
    const slideLimit = limits.slide_mean_mm_s * Math.sqrt(leg / referenceLeg());
    measured.slide_limit_mm_s = rnd(slideLimit);
    const rows = feet.map(foot => {
      const id = foot.get('id'), t = tracks.get(id) ?? {};
      let slide = t.slide ?? [null, null, null];
      if (foot.has('slide_mean_mm_s')) slide = [integer(foot.get('slide_mean_mm_s'), `feet.${id}.slide_mean_mm_s`, 0, 10 ** 7), null, null];
      const stance = foot.has('stance_ms') ? positive(foot.get('stance_ms'), `feet.${id}.stance_ms`, 10 ** 7) / 1000 : (t.stance ?? null);
      const duty = stance !== null && cycle ? rnd(stance / cycle * 1000) : null;
      if (gait === 'walk') checks.push(check(`duty_permille:${id}`, duty, limits.duty_walk_min, 1000));
      else if (gait === 'run') checks.push(check(`duty_permille:${id}`, duty, 0, limits.duty_walk_min - 1));
      checks.push(check(`slide_mean_mm_s:${id}`, rnd(slide[0]), 0, rnd(slideLimit)));
      return { id, contact_frames: t.contact_frames ?? null, strikes: t.strikes ?? null, cycle_ms: rnd(t.cycle === null || t.cycle === undefined ? null : t.cycle * 1000), stance_ms: rnd(stance === null ? null : stance * 1000), duty_permille: duty,
        stride_mm: rnd(t.stride ?? null), slide_mean_mm_s: rnd(slide[0]), slide_p95_mm_s: rnd(slide[1]), slide_max_mm_s: rnd(slide[2]) };
    });
    if (tracks.size === 2 && gait !== 'stand') {
      const [a, b] = [...tracks.values()].map(t => t.strike_times);
      const asym = asymmetry(a, b);
      measured.step_time_asymmetry_permille = rnd(asym === null ? null : asym * 1000);
      checks.push(check('step_time_asymmetry_permille', measured.step_time_asymmetry_permille, 0, limits.step_time_asymmetry_max));
    }
    if (!checks.length) fail('nothing to judge: a stand needs feet with tracks or slide_mean_mm_s');
    const judged = verdict(checks);
    return [judged, { verdict: judged, gait, leg_length_mm: rnd(leg), leg_source: legSource, stride_source: strideSource, cycle_source: cycleSource, measured, checks, feet: rows,
      expected: { at_this_speed: speed ? walkAt(leg, g, froude) : null, preferred: walkAt(leg, g, 0.25) }, thresholds: limits, threshold_sources: sources }];
  };

  const hull = points => {
    const unique = [...new Map(points.map(p => [`${p[0]},${p[1]}`, p])).values()].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
    if (unique.length <= 2) return unique;
    const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
    const half = list => {
      const out = [];
      for (const p of list) {
        while (out.length >= 2 && cross(out.at(-2), out.at(-1), p) <= 0) out.pop();
        out.push(p);
      }
      return out.slice(0, -1);
    };
    return [...half(unique), ...half([...unique].reverse())];
  };

  const segmentDistance = (p, a, b) => {
    const ab = [b[0] - a[0], b[1] - a[1]];
    const length2 = ab[0] * ab[0] + ab[1] * ab[1];
    const t = length2 === 0 ? 0 : Math.max(0, Math.min(1, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / length2));
    return lib.dist(p, [a[0] + t * ab[0], a[1] + t * ab[1]]);
  };

  const signedDistance = (p, polygon) => {
    if (polygon.length === 1) return -lib.dist(p, polygon[0]);
    const edges = polygon.length > 2 ? polygon.map((a, i) => [a, polygon[(i + 1) % polygon.length]]) : [[polygon[0], polygon[1]]];
    const nearest = Math.min(...edges.map(([a, b]) => segmentDistance(p, a, b)));
    if (polygon.length === 2) return -nearest;
    return edges.every(([a, b]) => (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= 0) ? nearest : -nearest;
  };

  const balanceCheck = args => {
    exact(args, 'arguments', ['fps_milli', 'frames'], ['mode', 'up_axis', 'gravity_mm_s2', 'thresholds']);
    const fps = positive(args.get('fps_milli'), 'fps_milli', 10 ** 6) / 1000;
    const mode = choice(get(args, 'mode', 'dynamic'), 'mode', ['static', 'dynamic', 'stop']);
    const up = upAxis(args);
    const [g, gSource] = gravity(args);
    const [limits, sources] = thresholds(args, defaults('balance', BALANCE_THRESHOLDS));
    const frames = array(args.get('frames'), 'frames', 1, 400);
    const com = [], support = [];
    frames.forEach((frame, i) => {
      exact(frame, `frames[${i}]`, ['com_mm', 'support_mm']);
      com.push(exactCoordinates(vec3(frame.get('com_mm'), `frames[${i}].com_mm`)));
      const contacts = array(frame.get('support_mm'), `frames[${i}].support_mm`, 0, 16);
      support.push(contacts.map((p, j) => exactCoordinates(vec3(p, `frames[${i}].support_mm[${j}]`))));
    });
    const m = Math.max(1, roundHalfEven(limits.derivative_window_ms / 2000 * fps));
    if (m > MAX_REFERENCE_WINDOW) throw new KernelRefusal('outside_domain', 'This derivative window would keep the reference busy for minutes; use a shorter one');
    const offsets = [];
    let k2 = 0, k4 = 0;
    if (2 * m < frames.length) for (let k = -m; k <= m; k++) { offsets.push(k); k2 += k * k; k4 += k ** 4; }
    const n = 2 * m + 1;
    const deriv = (i, order) => [0, 1, 2].map(c => (order === 1
      ? offsets.reduce((sum, k) => sum + k * com[i + k][c], 0) / k2 * fps
      : 2 * pySum(offsets.map(k => (k * k - k2 / n) * com[i + k][c])) / (k4 - k2 * k2 / n) * fps * fps));
    const rows = frames.map((_, i) => {
      const polygon = hull(support[i].map(p => ground(p, up)));
      const floor = support[i].length ? support[i].reduce((sum, p) => sum + p[up], 0) / support[i].length : null;
      const row = { frame: i, contacts: support[i].length, com_margin_mm: null, zmp_margin_mm: null, capture_margin_mm: null, flight_gravity_error_permille: null };
      const interior = m <= i && i < frames.length - m;
      if (polygon.length) {
        row.com_margin_mm = rnd(signedDistance(ground(com[i], up), polygon));
        const height = com[i][up] - floor;
        if (height <= 0) fail(`frames[${i}]: the COM must be above its support`);
        if (interior) {
          const acc = deriv(i, 2), vel = deriv(i, 1);
          if (acc[up] + g <= 0) fail(`frames[${i}]: the COM accelerates down faster than g while supported`);
          const groundCom = ground(com[i], up), groundAcc = ground(acc, up), groundVel = ground(vel, up);
          row.zmp_margin_mm = rnd(signedDistance(groundCom.map((c, k) => c - height * groundAcc[k] / (acc[up] + g)), polygon));
          const omega = Math.sqrt(g / height);
          row.capture_margin_mm = rnd(signedDistance(groundCom.map((c, k) => c + groundVel[k] / omega), polygon));
        }
      } else if (interior) row.flight_gravity_error_permille = rnd(Math.abs(deriv(i, 2)[up] + g) / g * 1000);
      return row;
    });
    const lowest = (key, subset) => {
      const values = subset.filter(r => r[key] !== null);
      if (!values.length) return [null, null];
      const r = values.reduce((best, x) => (x[key] < best[key] ? x : best));
      return [r[key], r.frame];
    };
    const supported = rows.filter(r => r.contacts);
    const checks = [], worst = {};
    if (mode === 'static' && supported.length) {
      worst.com_margin_mm = lowest('com_margin_mm', supported);
      checks.push(check('com_margin_mm', worst.com_margin_mm[0], limits.margin_mm));
    }
    if ((mode === 'dynamic' || mode === 'stop') && supported.length) {
      worst.zmp_margin_mm = lowest('zmp_margin_mm', supported);
      checks.push(check('zmp_margin_mm', worst.zmp_margin_mm[0], limits.margin_mm));
    }
    if (mode === 'stop') {
      const last = rows.length > 2 * m ? rows.at(-1 - m) : null;
      checks.push(check('final_capture_margin_mm', last === null ? null : last.capture_margin_mm, limits.margin_mm));
    }
    const flight = rows.map(r => r.flight_gravity_error_permille).filter(v => v !== null);
    if (flight.length) checks.push(check('flight_gravity_error_permille', Math.max(...flight), 0, limits.flight_gravity_error_max));
    if (!checks.length) fail('nothing to judge: no supported frame and no interior flight frame');
    const key = mode === 'static' ? 'com_margin_mm' : 'zmp_margin_mm';
    const failing = rows.filter(r => (r[key] !== null && r[key] < limits.margin_mm) || (r.flight_gravity_error_permille ?? 0) > limits.flight_gravity_error_max).map(r => r.frame);
    const judged = verdict(checks);
    const worstOut = {};
    for (const [name, [value, frame]] of Object.entries(worst)) worstOut[name] = { value, frame };
    return [judged, { verdict: judged, mode, gravity_mm_s2: rnd(g), gravity_source: gSource, checks, worst: worstOut, first_failing_frame: failing.length ? failing[0] : null, frames: rows, thresholds: limits, threshold_sources: sources }];
  };

  return { scaleTiming, gaitCheck, balanceCheck };
}
