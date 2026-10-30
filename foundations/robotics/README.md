# Foundation Robotics / Mechanical Engineering v0.1

The physics that motion must obey, for characters and machines alike. It owns what "this walk is right for his size",
"he would not fall", "the arm can reach that", "those rotors mesh" and "the squash keeps his volume" mean, as checks
that can fail. Animation tools stop guessing: they measure their motion and ask this Foundation. POODO governs how it
is used; it is a sibling of the other Foundations, never a subclass.

Every tool is a read-only observation and a pure function of the numbers the caller supplies: no file paths, no
rigs, no renders, no network. **Producers measure, Foundations judge.** A producer samples an animation (three.js
a Blender action, a baked GLB) into numbers; this Foundation turns them into verdicts with Evidence. A
verdict is **not acceptance of an animation**: that stays a person's call on moving playblasts, so every receipt
says `acceptance_decision: false` (I11, I12).

## The first principles

Each tool rests on a relation real bodies and machines cannot break. Specifics (proportions, thresholds, the
calibration cases) live in data: `foundation_robotics/data/defaults.json` and `data/calibration.json`.

| Area | First principle | Source | Tool |
|---|---|---|---|
| Scale | Under gravity, similar bodies move alike at equal **Froude number** v²/(gL). Times scale with √(L/g), speeds with √(gL), accelerations not at all. A 6 m giant swings his legs √3.4 = 1.85× slower than a 1.75 m man and walks 1.85× faster. | Alexander and Jayes 1983 | `scale_timing` |
| Scale | Strength grows with area, weight with volume, so strength-to-weight falls as 1/L: a big body cannot snap a limb as sharply relative to g, which is why it reads as heavy. Mass does not change the kinematics. | Haldane 1926 (square-cube law) | `scale_timing` |
| Timing | A limb or appendage swings like a pendulum, T = 2π√(I/(mgd)); for a uniform rod, 2π√(2L/3g). Follow-through and overlap lag by about that period; a fall from h takes √(2h/g). | any mechanics text | `scale_timing` |
| Gait | Stride follows speed: one full cycle λ ≈ 2.3 L Fr^0.3. Long strides at a slow cadence are the slow-motion look. | Alexander 1976 | `gait_check` |
| Gait | Walking gives way to running near Fr 0.5. A walk cannot exceed Fr 1, because the body would leave the ground. | Alexander 1989; Kram et al. 1997 | `gait_check` |
| Gait | Walking has double support, so each foot is down at least half the cycle (duty factor ≥ 0.5). A run has less than half. Stance is about 60 % at a free walk. | Alexander 1989; Perry and Burnfield 2010 | `gait_check` |
| Gait | A planted foot does not move (no footskate). Root speed = stride / cycle, or the foot must slide. | Kovar et al. 2002; kinematics | `gait_check` |
| Balance | Static: the centre of mass projects inside the support polygon. | statics | `balance_check` |
| Balance | Dynamic: the zero-moment point x − z ẍ/(z̈+g) stays inside the support polygon, or the body tips about its edge. | Vukobratović and Borovac 2004; Kajita et al. 2003 | `balance_check` |
| Balance | A body stops without another step only if its capture point x + ẋ/√(g/z) is inside the polygon. Weight shift before a step is the body moving the ZMP. | Pratt et al. 2006; Hof et al. 2005 | `balance_check` |
| Dynamics | With no support, the centre of mass falls at g whatever the limbs do (the floaty jump). | Newton | `balance_check` |
| Kinematics | Forward kinematics is a product of exponentials of joint screws. The positional Jacobian maps joint speeds to tip speed. | Lynch and Park 2017, ch. 4–5 | `ik_check` |
| Kinematics | At a singularity (a straight knee or elbow, aligned axes) the Jacobian loses rank. IK then needs unbounded joint speed and pops, so keep σ_min/σ_max away from 0. Reach is bounded by the extended chain, and joints have limits. | Yoshikawa 1985; Lynch and Park 2017 | `ik_check` |
| Mechanisms | Meshing gears have equal pitch-line speed: ω₂ = ω₁N₁/N₂, reversed by an external mesh. Screw rotors are gears whose teeth are lobes (a 4-lobe male drives a 6-lobe female at 4/6 speed, the other way). Mesh phase is locked modulo one tooth pitch. | Norton 2012, ch. 9; Stošić et al. 2005 | `mechanism_check` |
| Mechanisms | A slider-crank puts its slider at r cos θ + √(l² − (r sin θ − e)²), which is not a sine. A four-bar's Grashof condition s + l ≤ p + q decides which link can turn fully, and loop closure fixes the output angle. | Norton 2012, ch. 2 and 4 | `mechanism_check` |
| Sampling | A rotor sampled at the frame rate reads true only below half a blade pitch per frame. Faster, it aliases (wagon wheel) unless motion blur smears each blade over a pitch. | Shannon 1949 | `mechanism_check` |
| Animation | Squash and stretch keeps the volume: sx·sy·sz = 1, so squash s along one axis and 1/√s along the other two. | Thomas and Johnston 1981; Lasseter 1987 | `squash_check` |

The other animation principles have a physical reading, and for now they are tracked as gaps (listed at the end).
Anticipation is a counter-movement that loads the muscles and moves the ZMP before the move. Follow-through and
overlap are damped secondary dynamics that lag their driver by their own period. Arcs come from joints that rotate,
which sweep circles. Timing and spacing come from mass and size through the scale laws above.

## Numeric profile

Bounded integers only, in **milli-SI** units, `round(value * 1000)` of the SI unit, except lengths in millimetres:

| Quantity | On the wire | Example |
|---|---|---|
| length, position | mm | hip height 0.93 m → `930` |
| time | ms | 1.2 s cycle → `1200` |
| speed / acceleration | mm/s, mm/s² | 1.35 m/s → `1350`; g → `9807` |
| angle / angular speed | mrad, mrad/s | 30° → `524`; 3550 rpm → `371755` |
| frame rate | milli-fps | 24 fps → `24000`; 23.976 → `23976` |
| ratio, dimensionless | per-mille | Froude 0.25 → `250`; scale 1.18 → `1180` |

Positions are world space, after root motion. `up_axis` is `"y"` (three.js, glTF; the default) or `"z"` (Blender).
The host reuses the shared integer decoder (`adapters/wire.py`), so no float crosses the bridge.

## Tools

| Tool | Takes | Returns |
|---|---|---|
| `scale_timing` | height or leg length, optional gravity, Froude numbers, appendage lengths, drop heights | time, speed and strength factors against a 1.75 m adult; speed, stride, step, cycle and cadence at each Froude number; walk-run and walking-limit speeds; leg and appendage swing periods; fall times |
| `gait_check` | leg length or height, root speed, optional stride and cycle, feet with stance time, mean slide or a per-frame track (position + contact flag), frame rate, gait (`walk`, `run`, `stand`) | Froude number; stride against Alexander's prediction; kinematic mismatch; per-foot strikes, cycle, stance, duty, stride and slide (mean, p95, max); step-time asymmetry; the walk this body would make at this speed and at its preferred speed |
| `balance_check` | per frame: COM and the contact points; mode `static`, `dynamic` or `stop` | per frame: COM, ZMP and capture-point margins (signed; positive inside), free-fall error in flight; worst values and first failing frame. Derivatives use a Savitzky–Golay quadratic over 200 ms, because positions arrive as whole millimetres |
| `ik_check` | a joint chain (revolute or prismatic: axis, offset, limits), a tip offset, and poses (joint values, optional target) | per pose: forward-kinematics tip, limit margin, joints outside limits, Jacobian singular values and their ratio, reach margin and tip error |
| `mechanism_check` | `kind` and its geometry: `gear_train` (stages, shafts, measured speeds), `gear_mesh` (per-frame angles), `slider_crank`, `four_bar`, `rotor_strobe` (blades, speed, fps, shutter) | expected speeds and senses, phase drift in tooth pitches, expected slider or output angles and their errors, Grashof class, what a rotor reads as on screen (`true_motion`, `slowed`, `stationary`, `backwards`, `smeared_disc`) |
| `squash_check` | per-frame scale triples, squash axis | volume per frame and the side scale that would keep it |

Every check reads `{"check", "value", "min", "max", "status"}` with status `pass`, `fail` or `not_measured`. A verdict
is `thresholds_met`, `thresholds_not_met` or `not_scored`, and it is never met while any check is unmeasured. Each
threshold can be overridden by the caller (`thresholds`), and the receipt reports where each one came from.

Evidence on every receipt cites the source of each principle (`cited`), what was computed here (`derived`), and
values the caller supplied (`caller`). **`CHECK`** marks a threshold still awaiting calibration and a qualified
person's approval (I3). `RECORDED` marks a physical law, a cited measured ratio, or a computed value.

## Calibration (I3)

`data/calibration.json` holds synthetic example cases, and the suite replays every case:

| Case | Label | Result |
|---|---|---|
| Adult-scale walk (1.3 m/s, 1.55 m stride, 1.19 s cycle, slide 4 mm/s) | known good | passes |
| The same body at 0.35 m/s with a 1.7 s cycle | known bad (slow motion) | fails Froude |
| Normal-speed walk with about 6 cm/s foot slide | known bad | fails slide |
| A 5 m figure at 1.4 m/s with a 6 m stride | known bad | fails stride |
| A squash that widens 20 % and shortens 24 % | known bad | fails volume |

Replace them with motion you have measured and a person has judged. Balance, IK and mechanism thresholds are tried
only on constructed exact and perturbed cases, so they stay `CHECK` until real cases are added.

## How animation tools call it

Every caller follows the same three steps. **Sample** the motion per frame into world-space numbers. **Scale** them
to the wire units. **Call** the tool and keep the receipt next to the clip's QA.

- **A web timeline.** If poses are pure functions of time, a producer can evaluate them offline with no render. For
  each frame, read the foot world positions, the root and the mass-weighted centre, then call `gait_check` with
  `feet[].track` and `balance_check` with the COM and the planted foot corners. Machines call `mechanism_check`
  with their angle functions sampled per frame and the render's fps and shutter.
- **Blender bridge.** Per frame, `scene.frame_set(f)`, evaluate the depsgraph, and read pose-bone heads and tails in
  world space (`obj.matrix_world @ pbone.head`), x 1000 to mm, with `up_axis: "z"`.
- **A motion QA script.** If it already measures speed, stride, cycle, stance and slide per clip, `gait_check` takes
  them directly in mm and ms, with the clip's leg length.
- **From POODO.** `bootstrap.build_robotics(goal_id)` composes the read-only domain. Every call is a pinned,
  bounded, receipted observation (`tests/test_robotics_conformance.py` shows the round trip).

Direct, for a quick look (from `foundations/robotics`):

```sh
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"foundation-robotics-jsonrpc/1"}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"scale_timing","arguments":{"height_mm":6000}}}' \
  | python -B -m foundation_robotics_bridge
```

## Check it

```sh
cd foundations/robotics
python -B -m unittest discover -s tests       # calibration replay, invariances, refusals, the bridge, the manifest
python -B tools/build_manifest.py             # rewrites SOURCE-MANIFEST.json; prints the three pins
python -B tools/build_manifest.py --inventory > ../../schemas/robotics-v01-tools.json
```

With `jsonschema` importable (the root `requirements.txt`), the tool tests also validate every input and output
against its schema. After any change, re-pin `adapters/robotics_stdio.py` and the export rebuild step. From the
repository root, `python -B -m unittest tests.test_robotics_conformance` runs the host side.

## Not in v0.1 (gaps, in order of what animation needs next)

- **Producers.** Foot, COM and joint sampling for the three.js stage and for Blender, emitting this Foundation's
  arguments. Until they exist, callers hand-scale numbers.
- **Pops and smoothness.** Angular-acceleration spikes and jerk per joint (the motion loop's `pops` gate), with
  joint speed against the Jacobian near singularities.
- **Anticipation, follow-through and arcs.** Lead time of a counter-movement against the move's scale time, the lag
  and decay of secondary parts against their pendulum period, and end-effector path curvature.
- **Contact detail.** Sole penetration and hover, heel-to-toe roll, and hand contacts on fixed targets (the motion
  loop's 1 cm valve-rim gate).
- **Angular momentum in the ZMP.** Whole-body inertia per segment (Winter's segment masses), so arm swing and torso
  twist enter the balance check.
- **Machines.** Rotor spin-up from torque and inertia (τ = Iα), pump and valve stroke timing, belt and chain drives
  with slip.
- **Calibration.** Captured known-good and known-bad cases for balance, IK and mechanisms, and quadrupeds and runs
  for the gait bands.
