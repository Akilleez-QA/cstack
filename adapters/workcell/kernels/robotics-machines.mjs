import { KernelRefusal } from './common.mjs';
import { array, check, exact, fail, get, identifier, integer, measure, pyList, sorted, verdict } from './integer-profile.mjs';
import { choice, COORD_LIMIT, exactCoordinates, lib, positive, pySum, rnd, thresholds, uniqueIds, vec3 } from './robotics-numeric.mjs';

const TAU = 2 * Math.PI;
const IK_THRESHOLDS = ['tolerance_mm', 'singular_ratio_min'];
const MECHANISM_THRESHOLDS = ['speed_error_max', 'mesh_phase_max', 'slider_error_max_mm', 'four_bar_error_max_mrad', 'strobe_blur_min'];
const KINDS = ['gear_train', 'gear_mesh', 'slider_crank', 'four_bar', 'rotor_strobe'];
const MESH_SIGN = { external: -1, internal: 1, belt: 1, crossed_belt: -1 };
const MAX_FRAMES = 1000;
const EIGEN_NOISE = 2 ** -42;

const wrap = angle => angle - TAU * Math.floor((angle + Math.PI) / TAU);
const firstMax = values => values.reduce((best, v, i) => (v > values[best] ? i : best), 0);
const norm = v => Math.sqrt(v.reduce((sum, c) => sum + c * c, 0));

function rodrigues(w, theta) {
  const c = lib.cos(theta), s = lib.sin(theta), k = 1 - c;
  const [x, y, z] = w;
  return [[c + x * x * k, x * y * k - z * s, x * z * k + y * s],
    [y * x * k + z * s, c + y * y * k, y * z * k - x * s],
    [z * x * k - y * s, z * y * k + x * s, c + z * z * k]];
}
const multiply = (a, b) => [0, 1, 2].map(i => [0, 1, 2].map(j => pySum([0, 1, 2].map(k => a[i][k] * b[k][j]))));
const apply = (r, v) => [0, 1, 2].map(i => pySum([0, 1, 2].map(k => r[i][k] * v[k])));
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];

function eigenSymmetric(m) {
  const a = m.map(row => [...row]);
  for (let sweep = 0; sweep < 50; sweep++) {
    const off = pySum([lib.sq(a[0][1]), lib.sq(a[0][2]), lib.sq(a[1][0]), lib.sq(a[1][2]), lib.sq(a[2][0]), lib.sq(a[2][1])]);
    if (off < 1e-18 * Math.max(1, pySum([0, 1, 2].map(i => lib.sq(a[i][i]))))) break;
    for (const [p, q] of [[0, 1], [0, 2], [1, 2]]) {
      if (a[p][q] === 0) continue;
      const phi = 0.5 * lib.atan2(2 * a[p][q], a[q][q] - a[p][p]);
      const c = lib.cos(phi), s = lib.sin(phi);
      for (let k = 0; k < 3; k++) {
        const akp = a[k][p], akq = a[k][q];
        a[k][p] = c * akp - s * akq;
        a[k][q] = s * akp + c * akq;
      }
      for (let k = 0; k < 3; k++) {
        const apk = a[p][k], aqk = a[q][k];
        a[p][k] = c * apk - s * aqk;
        a[q][k] = s * apk + c * aqk;
      }
    }
  }
  return [a[0][0], a[1][1], a[2][2]].sort((x, y) => y - x);
}

function forward(joints, tip, q) {
  let rotation = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
  let translation = [0, 0, 0];
  const points = [], axes = [];
  joints.forEach((joint, index) => {
    const value = q[index];
    const home = apply(rotation, joint.home);
    points.push(home.map((c, i) => c + translation[i]));
    axes.push(apply(rotation, joint.axis));
    if (joint.type === 'revolute') {
      const r = rodrigues(joint.axis, value);
      const turned = apply(r, joint.home);
      const moved = apply(rotation, joint.home.map((c, i) => c - turned[i]));
      translation = moved.map((c, i) => c + translation[i]);
      rotation = multiply(rotation, r);
    } else {
      const moved = apply(rotation, joint.axis.map(c => c * value));
      translation = translation.map((c, i) => c + moved[i]);
    }
  });
  const reached = apply(rotation, tip);
  const end = reached.map((c, i) => c + translation[i]);
  const columns = joints.map((joint, i) => (joint.type === 'revolute' ? cross(axes[i], end.map((c, k) => c - points[i][k])) : axes[i]));
  return [end, columns];
}

function fourBarOutput(d, a, b, c, theta, branch) {
  const k1 = d / a, k2 = d / c, k3 = (a * a - b * b + c * c + d * d) / (2 * a * c);
  const cosine = lib.cos(theta);
  const bigA = cosine - k1 - k2 * cosine + k3;
  const bigB = -2 * lib.sin(theta);
  const bigC = k1 - (k2 + 1) * cosine + k3;
  const disc = bigB * bigB - 4 * bigA * bigC;
  if (disc < 0) return null;
  const root = Math.sqrt(disc) * (branch === 'open' ? -1 : 1);
  return 2 * lib.atan2(-bigB + root, 2 * bigA);
}

function resolved(eigenvalues) {
  const noise = Math.abs(eigenvalues[0]) * EIGEN_NOISE;
  const low = e => Math.sqrt(Math.max(0, e - noise)), high = e => Math.sqrt(Math.max(0, e + noise));
  const steady = eigenvalues.every(e => rnd(low(e)) === rnd(high(e)));
  const last = eigenvalues.at(-1), first = eigenvalues[0];
  if (!steady || (high(first) > 0 && rnd(low(last) / high(first) * 1000) !== rnd(high(last) / Math.max(low(first), Number.MIN_VALUE) * 1000))) {
    throw new KernelRefusal('numeric_boundary', 'This pose is so close to a singularity that its smallest singular value is rounding noise; use the pinned Foundation through a decision');
  }
}

export function createMachines(data) {
  const { defaults } = data;

  const ikCheck = args => {
    exact(args, 'arguments', ['joints', 'tip_mm', 'poses'], ['thresholds']);
    const [limits, sources] = thresholds(args, defaults('ik', IK_THRESHOLDS));
    const joints = [];
    let home = [0, 0, 0];
    array(args.get('joints'), 'joints', 1, 16).forEach((joint, i) => {
      exact(joint, `joints[${i}]`, ['id', 'type', 'axis', 'origin_mm', 'min', 'max']);
      identifier(joint.get('id'), `joints[${i}].id`);
      const type = choice(joint.get('type'), `joints[${i}].type`, ['revolute', 'prismatic']);
      const origin = exactCoordinates(vec3(joint.get('origin_mm'), `joints[${i}].origin_mm`));
      const lo = integer(joint.get('min'), `joints[${i}].min`, -COORD_LIMIT, COORD_LIMIT), hi = integer(joint.get('max'), `joints[${i}].max`, -COORD_LIMIT, COORD_LIMIT);
      if (lo > hi) fail(`joints[${i}]: min must not exceed max`);
      home = home.map((c, k) => c + origin[k]);
      const raw = exactCoordinates(vec3(joint.get('axis'), `joints[${i}].axis`));
      const length = norm(raw);
      if (length === 0) fail(`joints[${i}].axis must not be zero`);
      joints.push({ id: joint.get('id'), type, axis: raw.map(c => c / length), origin, home, min: lo, max: hi });
    });
    uniqueIds(joints, 'joints', joint => joint.id);
    const tip = exactCoordinates(vec3(args.get('tip_mm'), 'tip_mm'));
    const tipHome = home.map((c, k) => c + tip[k]);
    const base = joints[0].home;
    const reach = pySum(joints.slice(1).map(j => norm(j.origin))) + norm(tip) + joints.filter(j => j.type === 'prismatic').reduce((sum, j) => sum + Math.max(Math.abs(j.min), Math.abs(j.max)), 0);
    const mixed = new Set(joints.map(j => j.type)).size > 1;
    const rank = Math.min(3, joints.length);
    const rows = array(args.get('poses'), 'poses', 1, 200).map((pose, p) => {
      exact(pose, `poses[${p}]`, ['q'], ['target_mm']);
      const q = array(pose.get('q'), `poses[${p}].q`, joints.length, joints.length).map((v, i) => integer(v, `poses[${p}].q[${i}]`, -COORD_LIMIT, COORD_LIMIT));
      const values = joints.map((j, i) => (j.type === 'revolute' ? q[i] / 1000 : q[i]));
      const [end, columns] = forward(joints, tipHome, values);
      const limitMargin = Math.min(...joints.map((j, i) => Math.min(q[i] - j.min, j.max - q[i])));
      const outside = joints.filter((j, i) => !(j.min <= q[i] && q[i] <= j.max)).map(j => j.id);
      const jjt = [0, 1, 2].map(a => [0, 1, 2].map(b => pySum(columns.map(c => c[a] * c[b]))));
      const eigenvalues = eigenSymmetric(jjt);
      const sigma = eigenvalues.map(e => Math.sqrt(Math.max(0, e))).slice(0, rank);
      resolved(eigenvalues.slice(0, rank));
      const row = { pose: p, tip_mm: end.map(rnd), limit_margin: limitMargin, outside_limits: outside, singular_values: sigma.map(rnd), singular_ratio_permille: sigma[0] > 0 ? rnd(sigma.at(-1) / sigma[0] * 1000) : 0, target_distance_mm: null, reach_margin_mm: null, error_mm: null };
      if (pose.has('target_mm')) {
        const target = vec3(pose.get('target_mm'), `poses[${p}].target_mm`);
        row.target_distance_mm = rnd(lib.dist(target, base));
        row.reach_margin_mm = rnd(reach - lib.dist(target, base));
        row.error_mm = rnd(lib.dist(target, end));
      }
      return row;
    });
    const worst = key => {
      const values = rows.map(r => r[key]).filter(v => v !== null);
      return values.length ? Math.min(...values) : null;
    };
    const checks = [check('limit_margin', worst('limit_margin'), 0), check('singular_ratio_permille', worst('singular_ratio_permille'), limits.singular_ratio_min)];
    if (rows.some(r => r.reach_margin_mm !== null)) {
      checks.push(check('reach_margin_mm', worst('reach_margin_mm'), 0));
      checks.push(check('error_mm', Math.max(...rows.map(r => r.error_mm).filter(v => v !== null)), 0, limits.tolerance_mm));
    }
    const failing = rows.filter(r => r.outside_limits.length || r.singular_ratio_permille < limits.singular_ratio_min || (r.error_mm ?? 0) > limits.tolerance_mm || (r.reach_margin_mm ?? 0) < 0).map(r => r.pose);
    const judged = verdict(checks);
    return [judged, { verdict: judged, reach_mm: rnd(reach), base_mm: base.map(rnd), mixed_joint_types: mixed, checks, poses: rows, first_failing_pose: failing.length ? failing[0] : null, thresholds: limits, threshold_sources: sources }];
  };

  const gearTrain = (a, limits) => {
    exact(a, 'arguments', ['kind', 'input', 'input_speed_mrad_s', 'stages'], ['shafts', 'measured_speeds_mrad_s', 'thresholds']);
    const inputId = identifier(a.get('input'), 'input');
    const speeds = new Map([[inputId, measure(a.get('input_speed_mrad_s'), 'input_speed_mrad_s')]]);
    const shafts = array(get(a, 'shafts', []), 'shafts', 0, 16).map((s, i) => array(s, `shafts[${i}]`, 2, 8).map((g, j) => identifier(g, `shafts[${i}][${j}]`)));
    const couple = () => {
      for (const shaft of shafts) {
        const known = shaft.filter(g => speeds.has(g)).map(g => speeds.get(g));
        if (known.length) for (const g of shaft) speeds.set(g, known[0]);
      }
    };
    couple();
    const stages = array(a.get('stages'), 'stages', 1, 16).map((stage, i) => {
      exact(stage, `stages[${i}]`, ['driver', 'driven', 'driver_teeth', 'driven_teeth', 'mesh']);
      const driver = identifier(stage.get('driver'), `stages[${i}].driver`), driven = identifier(stage.get('driven'), `stages[${i}].driven`);
      const n1 = integer(stage.get('driver_teeth'), `stages[${i}].driver_teeth`, 1, 10 ** 5), n2 = integer(stage.get('driven_teeth'), `stages[${i}].driven_teeth`, 1, 10 ** 5);
      const sign = MESH_SIGN[choice(stage.get('mesh'), `stages[${i}].mesh`, Object.keys(MESH_SIGN))];
      if (!speeds.has(driver)) fail(`stages[${i}]: driver ${driver} is not driven by the input or an earlier stage`);
      if (speeds.has(driven)) fail(`stages[${i}]: ${driven} is already driven`);
      speeds.set(driven, speeds.get(driver) * sign * n1 / n2);
      couple();
      return { driver, driven, ratio_permille: rnd(sign * n1 / n2 * 1000) };
    });
    const measured = get(a, 'measured_speeds_mrad_s', new Map());
    if (!(measured instanceof Map) || measured.size > 32) fail('measured_speeds_mrad_s must be an object of up to 32 gear ids');
    const checks = [], gears = [];
    for (const [gear, speed] of speeds) {
      const row = { id: gear, speed_mrad_s: rnd(speed), measured_mrad_s: null, error_permille: null };
      if (measured.has(gear)) {
        const value = measure(measured.get(gear), `measured_speeds_mrad_s.${gear}`);
        row.measured_mrad_s = value;
        row.error_permille = speed ? rnd(Math.abs(value - speed) / Math.abs(speed) * 1000) : (value === 0 ? 0 : 1000);
        checks.push(check(`speed_error_permille:${gear}`, row.error_permille, 0, limits.speed_error_max));
      }
      gears.push(row);
    }
    const unknown = [...measured.keys()].filter(g => !speeds.has(g));
    if (unknown.length) fail(`measured_speeds_mrad_s names gears not in the train: ${pyList(sorted(unknown))}`);
    return [checks, { gears, stages }];
  };

  const gearMesh = (a, limits) => {
    exact(a, 'arguments', ['kind', 'driver_teeth', 'driven_teeth', 'mesh', 'frames'], ['thresholds']);
    const n1 = integer(a.get('driver_teeth'), 'driver_teeth', 1, 10 ** 5), n2 = integer(a.get('driven_teeth'), 'driven_teeth', 1, 10 ** 5);
    const sign = MESH_SIGN[choice(a.get('mesh'), 'mesh', Object.keys(MESH_SIGN))];
    const pitch = TAU / n2;
    const phases = array(a.get('frames'), 'frames', 2, MAX_FRAMES).map((frame, i) => {
      exact(frame, `frames[${i}]`, ['driver_mrad', 'driven_mrad']);
      const phi = measure(frame.get('driven_mrad'), `frames[${i}].driven_mrad`) / 1000 - sign * n1 / n2 * measure(frame.get('driver_mrad'), `frames[${i}].driver_mrad`) / 1000;
      return phi * TAU / pitch;
    });
    const center = lib.atan2(pySum(phases.map(lib.sin)), pySum(phases.map(lib.cos)));
    const drift = phases.map(p => Math.abs(wrap(p - center)) / TAU * 1000);
    const worst = firstMax(drift);
    return [[check('phase_drift_permille_pitch', rnd(drift[worst]), 0, limits.mesh_phase_max)], { speed_ratio_permille: rnd(sign * n1 / n2 * 1000), driven_pitch_mrad: rnd(pitch * 1000), worst_frame: worst, phase_drift_permille_pitch: drift.map(rnd) }];
  };

  const sliderCrank = (a, limits) => {
    exact(a, 'arguments', ['kind', 'crank_mm', 'rod_mm'], ['offset_mm', 'frames', 'thresholds']);
    const r = positive(a.get('crank_mm'), 'crank_mm', 10 ** 7), l = positive(a.get('rod_mm'), 'rod_mm', 10 ** 7);
    const e = measure(get(a, 'offset_mm', 0), 'offset_mm');
    const checks = [check('rod_minus_crank_and_offset_mm', l - r - Math.abs(e), 1)];
    const rows = array(get(a, 'frames', []), 'frames', 0, MAX_FRAMES).map((frame, i) => {
      exact(frame, `frames[${i}]`, ['crank_mrad', 'slider_mm']);
      const theta = measure(frame.get('crank_mrad'), `frames[${i}].crank_mrad`) / 1000;
      const inside = l * l - lib.sq(r * lib.sin(theta) - e);
      const expected = inside >= 0 ? r * lib.cos(theta) + Math.sqrt(inside) : null;
      const value = measure(frame.get('slider_mm'), `frames[${i}].slider_mm`);
      return { expected_mm: rnd(expected), error_mm: expected === null ? null : rnd(Math.abs(value - expected)) };
    });
    if (rows.length) {
      const errors = rows.map(row => row.error_mm);
      checks.push(check('slider_error_mm', errors.includes(null) ? null : Math.max(...errors), 0, limits.slider_error_max_mm));
    }
    const offset = BigInt(e) ** 2n, farSquared = BigInt(l + r) ** 2n - offset, nearSquared = BigInt(l - r) ** 2n - offset;
    if (farSquared < 0n) throw new KernelRefusal('outside_domain', 'The reference has no answer for an offset beyond rod plus crank');
    const far = Math.sqrt(Number(farSquared)), near = nearSquared > 0n ? Math.sqrt(Number(nearSquared)) : 0;
    return [checks, { stroke_mm: rnd(far - near), top_dead_centre_mm: rnd(far), bottom_dead_centre_mm: rnd(near), frames: rows }];
  };

  const fourBar = (a, limits) => {
    exact(a, 'arguments', ['kind', 'ground_mm', 'input_mm', 'coupler_mm', 'output_mm'], ['branch', 'frames', 'input_full_turn', 'thresholds']);
    const [d, input, b, c] = ['ground_mm', 'input_mm', 'coupler_mm', 'output_mm'].map(k => positive(a.get(k), k, 10 ** 7));
    const branch = choice(get(a, 'branch', 'open'), 'branch', ['open', 'crossed']);
    const lengths = [d, input, b, c].sort((x, y) => x - y);
    const grashof = lengths[0] + lengths[3] - lengths[1] - lengths[2];
    const names = new Map([[d, 'ground'], [input, 'input'], [b, 'coupler'], [c, 'output']]);
    const shortest = grashof < 0 ? names.get(lengths[0]) : null;
    const kind = grashof > 0 ? 'non_grashof_triple_rocker' : grashof === 0 ? 'change_point' : { input: 'crank_rocker', output: 'rocker_crank', ground: 'double_crank', coupler: 'double_rocker' }[shortest];
    const checks = [];
    const fullTurn = get(a, 'input_full_turn', false);
    if (typeof fullTurn !== 'boolean') fail('input_full_turn must be true or false');
    if (fullTurn) checks.push(check('input_is_crank', grashof < 0 && (shortest === 'input' || shortest === 'ground') ? 1 : 0, 1, 1));
    const rows = array(get(a, 'frames', []), 'frames', 0, MAX_FRAMES).map((frame, k) => {
      exact(frame, `frames[${k}]`, ['input_mrad', 'output_mrad']);
      const expected = fourBarOutput(d, input, b, c, measure(frame.get('input_mrad'), `frames[${k}].input_mrad`) / 1000, branch);
      const value = measure(frame.get('output_mrad'), `frames[${k}].output_mrad`) / 1000;
      return { expected_mrad: rnd(expected === null ? null : wrap(expected) * 1000), error_mrad: expected === null ? null : rnd(Math.abs(wrap(value - expected)) * 1000) };
    });
    if (rows.length) {
      const errors = rows.map(row => row.error_mrad);
      checks.push(check('output_error_mrad', errors.includes(null) ? null : Math.max(...errors), 0, limits.four_bar_error_max_mrad));
    }
    return [checks, { grashof_mm: grashof, classification: kind, branch, frames: rows }];
  };

  const rotorStrobe = (a, limits) => {
    exact(a, 'arguments', ['kind', 'blades', 'speed_mrad_s', 'fps_milli'], ['shutter_permille', 'thresholds']);
    const n = integer(a.get('blades'), 'blades', 1, 1000);
    const omega = measure(a.get('speed_mrad_s'), 'speed_mrad_s') / 1000;
    const fps = positive(a.get('fps_milli'), 'fps_milli', 10 ** 6) / 1000;
    const shutter = integer(get(a, 'shutter_permille', 0), 'shutter_permille', 0, 1000) / 1000;
    const pitch = TAU / n, step = omega / fps;
    const apparent = step - pitch * Math.floor(step / pitch + 0.5);
    const blur = Math.abs(step) * shutter / pitch * 1000;
    const aliased = Math.abs(step) >= pitch / 2;
    const reads = !aliased ? 'true_motion' : blur >= limits.strobe_blur_min ? 'smeared_disc' : Math.abs(apparent) < pitch * 0.02 ? 'stationary' : apparent * step < 0 ? 'backwards' : 'slowed';
    const perFrame = rnd(Math.abs(step) / pitch * 1000);
    const checks = [!aliased ? check('pitch_per_frame_permille', perFrame, 0, 499) : check('blur_permille_pitch', rnd(blur), limits.strobe_blur_min)];
    return [checks, { reads_as: reads, pitch_per_frame_permille: perFrame, step_per_frame_mrad: rnd(step * 1000), apparent_step_mrad: rnd(apparent * 1000), blade_pitch_mrad: rnd(pitch * 1000), blur_permille_pitch: rnd(blur), max_true_speed_mrad_s: rnd(pitch / 2 * fps * 1000) }];
  };

  const handlers = { gear_train: gearTrain, gear_mesh: gearMesh, slider_crank: sliderCrank, four_bar: fourBar, rotor_strobe: rotorStrobe };

  const mechanismCheck = args => {
    const kind = choice(args.get('kind'), 'kind', KINDS);
    const [limits, sources] = thresholds(args, defaults('mechanism', MECHANISM_THRESHOLDS));
    const [checks, detail] = handlers[kind](args, limits);
    if (!checks.length) fail('nothing to judge: supply measured speeds or frames');
    const judged = verdict(checks);
    return [judged, { verdict: judged, kind, checks, detail, thresholds: limits, threshold_sources: sources }];
  };

  const squashCheck = args => {
    exact(args, 'arguments', ['frames'], ['axis', 'thresholds']);
    const [limits, sources] = thresholds(args, defaults('squash', ['volume_error_max']));
    const axis = 'xyz'.indexOf(choice(get(args, 'axis', 'y'), 'axis', ['x', 'y', 'z']));
    const rows = array(args.get('frames'), 'frames', 1, MAX_FRAMES).map((frame, i) => {
      exact(frame, `frames[${i}]`, ['scale_permille']);
      const s = array(frame.get('scale_permille'), `frames[${i}].scale_permille`, 3, 3).map((v, k) => integer(v, `frames[${i}].scale_permille[${k}]`, 1, 10 ** 6) / 1000);
      return { volume_permille: rnd(s[0] * s[1] * s[2] * 1000), conserving_lateral_permille: rnd(1000 / Math.sqrt(s[axis])) };
    });
    const errors = rows.map(row => Math.abs(row.volume_permille - 1000));
    const worst = firstMax(errors);
    const checks = [check('volume_error_permille', errors[worst], 0, limits.volume_error_max)];
    const judged = verdict(checks);
    return [judged, { verdict: judged, checks, worst_frame: worst, frames: rows, thresholds: limits, threshold_sources: sources }];
  };

  return { ikCheck, mechanismCheck, squashCheck };
}
