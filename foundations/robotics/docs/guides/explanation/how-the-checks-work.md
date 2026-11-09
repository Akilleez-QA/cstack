# How the checks work

Each tool turns numbers the caller measured into checks. A check has a value, an optional minimum and maximum, and a status of `pass`, `fail` or `not_measured`. The verdict is `thresholds_not_met` if any check fails, `not_scored` if any check could not be measured, and `thresholds_met` otherwise. `scale_timing` has no checks; it returns expectations (`timing_estimated`).

All quantities cross the bridge as integers in milli-SI units or per-mille ratios. Inside, the tools compute in floating point and round each output once, half away from zero.

## Dynamic similarity (`scale_timing`, `gait_check`)

Two bodies of different size move alike when their Froude number, v² / (g L), is equal, where L is leg length. At equal Froude number, times scale with √(L / g) and speeds with √(g L) (Alexander and Jayes 1983). Leg length is the caller's value or 0.530 x standing height (Winter). The reference adult is 1750 mm tall, so the reference leg is 927.5 mm.

- Predicted stride is 2.3 L Froude^0.3 (Alexander 1976). It is a fit across animals with scatter, so `gait_check` accepts a band: 0.7 to 1.4 times the prediction by default.
- A walk is judged between Froude 0.05 and 0.5. People switch to running near 0.5 (Kram et al. 1997).
- A walking foot is down for at least half the cycle (duty factor 0.5); a run is below half (Alexander 1989).
- Foot slide while in contact is limited to 10 mm/s at the reference leg, scaled by √(leg / reference leg).
- When stride and cycle both come from the caller or from foot tracks, speed must equal stride / cycle within 2 %.
- With two tracked feet, the two step times must agree within 5 %.

A giant that walks with human timing fails the Froude check; one that walks at human speed fails the stride check. Only time scaled by √(size) passes (`GaitTests` shows all three).

## Balance (`balance_check`)

- Static: the centre of mass, projected to the ground, must lie inside the convex hull of the contact points.
- Dynamic: the zero-moment point from the cart-table model must lie inside the hull. COM velocity and acceleration come from a quadratic least-squares fit over a 200 ms window. The model ignores angular momentum about the COM, so a pass is necessary, not sufficient.
- Stop: at the last fully windowed frame the capture point, COM + velocity / √(g / height), must lie inside the hull.
- Flight: a frame with no contacts must accelerate downward at g, within 15 %.

## Kinematics (`ik_check`)

Forward kinematics is a product of exponentials over the chain (Lynch and Park). The positional Jacobian's singular values come from a Jacobi eigen-solver on J Jᵀ. Their ratio (smallest over largest) measures distance from a singularity; below 0.05 the pose is judged too close. Reach, joint limits and tip error (10 mm default) are also checked.

## Mechanisms (`mechanism_check`)

- Gear trains: equal pitch-line speed at each mesh; external meshes and crossed belts reverse the sense. Gears on one shaft share a speed. Screw-compressor rotors follow the same rule with lobes as teeth.
- Gear mesh: the driven member keeps its phase relative to the driver modulo one tooth pitch, within 10 % of a pitch.
- Slider-crank: closed-form slider position from crank angle, rod length and offset, within 2 mm.
- Four-bar: Grashof classification and the loop-closure output angle, within 17 mrad.
- Rotor strobe: sampled at the frame rate, rotation reads true only below half a blade pitch per frame (Shannon). Faster rotors must blur at least one full pitch, or they read as stationary, backwards or slowed.

## Squash and stretch (`squash_check`)

The product of the three scales should stay 1 (Thomas and Johnston). The default tolerance is 30 permille. Each frame also reports the side scale, 1 / √(axis scale), that would conserve volume.

## Where each number comes from

Every default value has a status. `RECORDED` values are physical constants or measured ratios from a cited source. `CHECK` values are thresholds not yet approved by a qualified person; most were tried on the cases in `foundation_robotics/data/calibration.json`, and the suite replays those cases on every run. See the [defaults table](../../data/defaults.md) and the [calibration cases](../../data/calibration-cases.md).
