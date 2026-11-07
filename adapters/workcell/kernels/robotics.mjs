import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { KernelRefusal, ToolInputError, sha256 } from './common.mjs';
import { boundedOutput, evidence, parseProfile } from './integer-profile.mjs';
import { createMachines } from './robotics-machines.mjs';
import { createMotion } from './robotics-motion.mjs';
import { guarded } from './robotics-numeric.mjs';

const VERSION = '0.1.0';
const TOOLS = ['scale_timing', 'gait_check', 'balance_check', 'ik_check', 'mechanism_check', 'squash_check'];
const BOUNDARY = { observation_only: true, acceptance_decision: false, control_action: false };
const NUMERIC_TOLERANCE = 'Results match the pinned Python exactly or are refused. sin, cos, atan2, pow and math.dist can differ from the Python libm in the last places, so each call using them is repeated under eight patterns of relative nudges of 2^-49 on those functions, and any change in the integer results refuses the call with numeric_boundary. Python 3.12 or later is the reference, because its sum() is compensated.';
const DEFAULTS_FILE = 'foundation_robotics/data/defaults.json';
const SOURCES = {
  alexander_1976: "Alexander, R. McN. (1976). Estimates of speeds of dinosaurs. Nature 261, 129-130 (relative stride = 2.3 x Froude^0.3, fitted across walking and running animals).",
  alexander_jayes_1983: "Alexander, R. McN. and Jayes, A. S. (1983). A dynamic similarity hypothesis for the gaits of quadrupedal mammals. Journal of Zoology 201, 135-152.",
  alexander_1989: "Alexander, R. McN. (1989). Optimization and gaits in the locomotion of vertebrates. Physiological Reviews 69(4), 1199-1227 (walk-run transition near Froude 0.5; duty factor).",
  kram_1997: "Kram, R., Domingo, A. and Ferris, D. P. (1997). Effect of reduced gravity on the preferred walk-run transition speed. Journal of Experimental Biology 200, 821-826.",
  winter: "Winter, D. A. (2009). Biomechanics and Motor Control of Human Movement, 4th ed., Wiley, ch. 4 (segment lengths as fractions of height: greater trochanter 0.530 H).",
  perry: "Perry, J. and Burnfield, J. M. (2010). Gait Analysis: Normal and Pathological Function, 2nd ed., SLACK (stance about 60 % and swing about 40 % of the cycle at a free walk).",
  kovar_2002: "Kovar, L., Schreiner, J. and Gleicher, M. (2002). Footskate cleanup for motion capture editing. ACM SIGGRAPH/Eurographics Symposium on Computer Animation, 97-104.",
  zmp: "Vukobratovic, M. and Borovac, B. (2004). Zero-moment point: thirty five years of its life. International Journal of Humanoid Robotics 1(1), 157-173; Kajita, S. et al. (2003). Biped walking pattern generation by using preview control of zero-moment point. IEEE ICRA, 1620-1626 (cart-table model).",
  capture_point: "Pratt, J., Carff, J., Drakunov, S. and Goswami, A. (2006). Capture point: a step toward humanoid push recovery. IEEE-RAS Humanoids, 200-207; Hof, A. L., Gazendam, M. G. J. and Sinke, W. E. (2005). The condition for dynamic stability. Journal of Biomechanics 38(1), 1-8.",
  savitzky_golay: "Savitzky, A. and Golay, M. J. E. (1964). Smoothing and differentiation of data by simplified least squares procedures. Analytical Chemistry 36(8), 1627-1639.",
  newton: "Newton's second law: a body with no support accelerates downward at g (any mechanics text, e.g. Meriam, J. L. and Kraige, L. G., Engineering Mechanics: Dynamics).",
  lynch_park: "Lynch, K. M. and Park, F. C. (2017). Modern Robotics: Mechanics, Planning, and Control. Cambridge University Press, ch. 4 (product of exponentials) and ch. 5 (Jacobian, singularities, manipulability).",
  yoshikawa: "Yoshikawa, T. (1985). Manipulability of robotic mechanisms. International Journal of Robotics Research 4(2), 3-9.",
  norton: "Norton, R. L. (2012). Design of Machinery, 5th ed., McGraw-Hill: ch. 2 (Grashof condition), ch. 4 (four-bar and slider-crank position analysis) and ch. 9 (gear trains).",
  stosic: "Stosic, N., Smith, I. K. and Kovacevic, A. (2005). Screw Compressors: Mathematical Modelling and Performance Calculation. Springer (male and female rotors turn in inverse ratio of their lobe counts).",
  shannon: "Shannon, C. E. (1949). Communication in the presence of noise. Proceedings of the IRE 37(1), 10-21 (a motion sampled at the frame rate is unambiguous only below half a period per sample).",
  thomas_johnston: "Thomas, F. and Johnston, O. (1981). The Illusion of Life: Disney Animation. Abbeville (squash and stretch keeps the volume); Lasseter, J. (1987). Principles of traditional animation applied to 3D computer animation. SIGGRAPH Computer Graphics 21(4), 35-44.",
  haldane: "Haldane, J. B. S. (1926). On being the right size; Galileo's square-cube law (strength grows with area, weight with volume).",
  pendulum: "Small-oscillation period of a physical pendulum, T = 2 pi sqrt(I / (m g d)); a uniform rod swung from one end gives T = 2 pi sqrt(2 L / (3 g)) (any mechanics text).",
  kinematics: "Kinematic identity: speed = stride length / cycle time. A planted foot that does not meet it must slide.",
  calibration: "foundation_robotics/data/calibration.json: the known-good and known-bad motion this threshold was tried on (an internal motion trial, the the giant character timeline).",
};

const cited = (applies_to, key, note, state = 'RECORDED') => evidence(applies_to, 'cited', SOURCES[key], note, state);
const derived = (applies_to, note) => evidence(applies_to, 'derived', "the caller's numbers", note, 'RECORDED');

export function createKernel({ root, numericGuard = true }) {
  const raw = readFileSync(join(root, DEFAULTS_FILE));
  const table = JSON.parse(raw);
  const value = (section, key) => table[section][key].value;
  const defaults = (section, keys) => Object.fromEntries(keys.map(key => [key, value(section, key)]));
  const data = { value, defaults };
  const { scaleTiming, gaitCheck, balanceCheck } = createMotion(data);
  const { ikCheck, mechanismCheck, squashCheck } = createMachines(data);

  const thresholdEvidence = (section, result, note) => {
    const entries = [];
    const named = kind => Object.entries(result.threshold_sources).filter(([, source]) => source === kind).map(([key]) => key);
    const defaulted = named('default'), supplied = named('caller');
    if (defaulted.length) entries.push(cited('result.thresholds', 'calibration', `${note} Defaults in use: ${defaulted.join(', ')}.`, defaulted.some(k => table[section][k].status === 'CHECK') ? 'CHECK' : 'RECORDED'));
    if (supplied.length) entries.push(evidence('result.thresholds', 'caller', "the caller's input", `Thresholds supplied by the caller: ${supplied.join(', ')}.`, 'CHECK'));
    return entries;
  };

  const receipts = {
    scale_timing(args) {
      const [assessment, result] = scaleTiming(args);
      const entries = [cited('result.factors', 'alexander_jayes_1983', 'Dynamic similarity: at equal Froude number, times scale with sqrt(L / g), speeds with sqrt(g L), accelerations not at all.'),
        cited('result.walk', 'alexander_1976', 'Stride = 2.3 L Froude^0.3, fitted across animals with scatter. On the approved walk the measured stride was 1.23 times this prediction, so read it as the centre of a band (gait_check judges the band).', 'CHECK'),
        cited('result.limits', 'kram_1997', 'People change from walking to running near Froude 0.5; an inverted-pendulum walk cannot exceed Froude 1 (the body would leave the ground).'),
        cited('result.leg_swing_period_ms', 'pendulum', 'The passive swing of a uniform leg about the hip. A driven leg swings faster; use it as the scaling reference for swing and follow-through, not as a target.'),
        cited('result.factors.strength_to_weight_permille', 'haldane', 'Strength over weight falls as 1 / L under geometric similarity: a big body cannot snap its limbs about as sharply relative to g.')];
      if (result.leg_source === 'winter_hip_height') entries.push(cited('result.leg_length_mm', 'winter', 'Hip height from standing height (0.530 H) for an adult of human proportions; give leg_length_mm for other builds.'));
      if (result.gravity_source === 'caller') entries.push(evidence('arguments.gravity_mm_s2', 'caller', "the caller's input", 'Gravity supplied by the caller.', 'CHECK'));
      return [assessment, result, entries];
    },
    gait_check(args) {
      const [assessment, result] = gaitCheck(args);
      return [assessment, result, [derived('result.measured', "Froude number, stride over Alexander's prediction, kinematic mismatch and step asymmetry from the caller's speed, stride, cycle and foot tracks; this Foundation never sees a clip."),
        cited('result.checks', 'alexander_1989', 'Walking needs double support (duty factor at least 0.5) and gives way to running near Froude 0.5 (Kram et al. 1997 confirmed the 0.5 transition under reduced gravity).'),
        cited('result.checks', 'alexander_1976', 'Over-striding for the Froude number at a slow cadence is the slow-motion signature: the rejected generated walk measured 2.09 times the predicted stride, the approved loop 1.23.', 'CHECK'),
        cited('result.feet', 'kovar_2002', 'Footskate: a foot in contact must not move on the ground. The allowance is the calibrated human limit scaled by sqrt(leg / reference leg) (dynamic similarity).'),
        ...thresholdEvidence('gait', result, 'Calibrated on the approved walk loop (pass) and four rejected walks (fail): two slow-motion generated walks and two raw retargets with foot slide. Not yet calibrated on quadrupeds, runs or giants judged by a person (I3).')]];
    },
    balance_check(args) {
      const [assessment, result] = balanceCheck(args);
      return [assessment, result, [derived('result.frames', 'COM velocity and acceleration by central differences of the supplied frames; support polygons as convex hulls of the supplied contact points.'),
        cited('result.checks', 'zmp', 'The ZMP must lie inside the support polygon; the cart-table formula neglects the rate of change of angular momentum about the COM, so a pass is necessary, not sufficient.'),
        cited('result.frames', 'capture_point', 'A body stops without stepping only if its capture point is inside the support polygon.'),
        cited('result.checks', 'newton', 'Frames with no support must fall at g.'),
        ...thresholdEvidence('balance', result, 'Margins and the flight tolerance are not yet calibrated on captured motion; the suite tries them on constructed standing, leaning, swaying and falling cases only (I3).')]];
    },
    ik_check(args) {
      const [assessment, result] = ikCheck(args);
      return [assessment, result, [cited('result.poses', 'lynch_park', 'Forward kinematics as a product of exponentials and the positional geometric Jacobian, both computed from the supplied chain.'),
        cited('result.checks', 'yoshikawa', `Singular values of the Jacobian: their ratio measures how far the pose is from a singularity, where IK needs unbounded joint speed and pops.${result.mixed_joint_types ? ' This chain mixes revolute and prismatic joints, so the ratio mixes units.' : ''}`, 'CHECK'),
        ...thresholdEvidence('ik', result, 'The tolerance and the singularity ratio are tried on constructed two-link legs (bent knee passes, straight knee, out-of-reach target and limit violation fail), not on character rigs (I3).')]];
    },
    mechanism_check(args) {
      const [assessment, result] = mechanismCheck(args);
      const source = { gear_train: 'stosic', rotor_strobe: 'shannon' }[result.kind] ?? 'norton';
      const notes = { gear_train: 'Equal pitch-line speed at every mesh; screw rotors mesh like gears with lobes as teeth.', gear_mesh: 'Meshing members keep their phase modulo one tooth pitch.', slider_crank: 'Closed-form slider position from crank angle, rod length and offset.',
        four_bar: 'Grashof classification and the loop-closure output angle.', rotor_strobe: 'Sampled at the frame rate, rotation reads true only below half a blade pitch per frame.' };
      const entries = [cited('result.detail', source, notes[result.kind])];
      if (source !== 'norton') entries.push(cited('result.detail', 'norton', 'Gear-train and mechanism kinematics.'));
      return [assessment, result, [...entries, ...thresholdEvidence('mechanism', result, 'Tolerances are tried on constructed exact and perturbed mechanisms only (I3).')]];
    },
    squash_check(args) {
      const [assessment, result] = squashCheck(args);
      return [assessment, result, [cited('result.frames', 'thomas_johnston', 'Squash and stretch keeps the volume: scale x times y times z stays 1; conserving_lateral_permille is the side scale that would.'),
        ...thresholdEvidence('squash', result, 'The tolerance is a starting value tried on constructed cases and the the giant character squeeze (+8.6 % volume), not yet judged by a person (I3).')]];
    },
  };

  const run = (name, argumentsText) => {
    if (!TOOLS.includes(name)) throw new KernelRefusal('unknown_tool', `No kernel tool ${name}`);
    const { value: args, inputSha256 } = parseProfile(argumentsText);
    const base = { tool: name, version: VERSION, input_sha256: inputSha256, boundary: { ...BOUNDARY } };
    return boundedOutput(guarded(numericGuard, () => {
      try {
        const [assessment, result, entries] = receipts[name](args);
        return { ...base, status: 'ok', assessment, result, error: null, evidence: entries };
      } catch (error) {
        if (!(error instanceof ToolInputError)) throw error;
        return { ...base, status: 'error', assessment: 'tool_error', result: null, error: error.message.slice(0, 1024),
          evidence: [evidence('error', 'derived', 'Foundation Robotics argument check', 'The request was refused before anything was judged.', 'RECORDED')] };
      }
    }), argumentsText.length);
  };
  return { foundation: 'foundation_robotics', version: VERSION, tools: TOOLS, run, numeric_tolerance: NUMERIC_TOLERANCE, projections: { [DEFAULTS_FILE]: sha256(raw) } };
}
