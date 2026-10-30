"""Foundation Robotics' judgements: the calibration record, first-principles invariances and refusals. Stdlib only.

Run from foundations/robotics. When jsonschema is importable, every result is also validated against its outputSchema.
"""
import math
import unittest

from foundation_robotics.sources import CALIBRATION, DEFAULTS, SOURCES
from foundation_robotics.tools import TOOL_NAMES, run
from foundation_robotics_bridge.schemas import tool_definitions

try:
    import jsonschema
except ImportError:  # the bridge is stdlib-only; the host suite validates with jsonschema
    jsonschema = None

OUTPUT = {t["name"]: t["outputSchema"] for t in tool_definitions()}
INPUT = {t["name"]: t["inputSchema"] for t in tool_definitions()}


def invoke(name, arguments):
    failed, assessment, receipt = run(name, arguments)
    if jsonschema is not None:
        jsonschema.validate(arguments, INPUT[name])
        jsonschema.validate({"tool": name, "assessment": assessment, "formal_proof": False,
                             "runtime_goal_acceptance": False, "receipt": receipt}, OUTPUT[name])
    return failed, assessment, receipt


def ok(name, arguments):
    failed, assessment, receipt = invoke(name, arguments)
    assert not failed, receipt["error"]
    assert receipt["evidence"]
    return assessment, receipt["result"]


def failing(result):
    return {c["check"] for c in result["checks"] if c["status"] == "fail"}


def refused(test, name, arguments):
    failed, assessment, receipt = run(name, arguments)
    test.assertTrue(failed, arguments)
    test.assertEqual((assessment, receipt["status"], receipt["result"]), ("tool_error", "error", None))
    test.assertTrue(receipt["evidence"])
    return receipt["error"]


def walk_track(leg_scale=1.0, time_scale=1.0, drift_mm_s=0, cycles=4):
    """Two feet of a clean walk at 30 fps: planted in stance (60 % of the cycle), a smooth swing to the next plant.

    The reference is the approved alex loop's stride (1617 mm in a 1.2 s cycle); leg_scale scales every length and
    time_scale every duration. drift_mm_s makes the planted foot skate forward.
    """
    n = round(36 * time_scale)
    stride, period = 1617 * leg_scale, n / 30
    feet = []
    for name, phase0, side in (("l", 0.25, -1), ("r", 0.75, 1)):
        positions, contact = [], []
        for i in range(cycles * n):
            u = i / n + phase0
            k, c = math.floor(u), u % 1
            if c < 0.6:
                z, y, down = k * stride + drift_mm_s * c * period, 0, 1
            else:
                s = (c - 0.6) / 0.4
                z, y, down = k * stride + stride * (1 - math.cos(math.pi * s)) / 2, 100 * leg_scale * math.sin(
                    math.pi * s), 0
            positions.append([round(side * 100 * leg_scale), round(y), round(z)])
            contact.append(down)
        feet.append({"id": name, "track": {"positions_mm": positions, "contact": contact}})
    return {"leg_length_mm": round(928 * leg_scale), "speed_mm_s": round(stride / period), "fps_milli": 30000,
            "feet": feet}


class CalibrationTests(unittest.TestCase):
    def test_every_recorded_case_reaches_its_verdict(self):
        for case in CALIBRATION["cases"]:
            assessment, result = ok(case["tool"], case["arguments"])
            self.assertEqual(assessment, case["verdict"], case["id"])
            if "fails" in case:
                self.assertEqual(failing(result), set(case["fails"]), case["id"])
        labels = {c["label"] for c in CALIBRATION["cases"]}
        self.assertTrue({"known_good", "known_bad"} <= labels)

    def test_every_default_names_a_source_and_a_status(self):
        for section, values in DEFAULTS.items():
            if type(values) is not dict:
                continue
            for key, entry in values.items():
                self.assertIn(entry["status"], ("CHECK", "RECORDED"), key)
                self.assertIn(entry["source"], SOURCES, key)


class ScaleTimingTests(unittest.TestCase):
    def test_time_scales_with_root_length_and_mass_does_not_enter(self):
        _, giant = ok("scale_timing", {"height_mm": 6000})
        _, person = ok("scale_timing", {"height_mm": 1750})
        self.assertEqual((giant["leg_length_mm"], person["leg_length_mm"]), (3180, 928))
        self.assertEqual(giant["factors"]["time_permille"], round(1000 * math.sqrt(3180 / 927.5)))
        self.assertEqual(person["factors"]["time_permille"], 1000)
        for g, p in zip(giant["walk"], person["walk"]):
            self.assertEqual(g["froude_permille"], p["froude_permille"])
            self.assertAlmostEqual(g["cycle_ms"] / p["cycle_ms"], math.sqrt(3180 / 927.5), delta=0.002)
            self.assertAlmostEqual(g["stride_mm"] / p["stride_mm"], 3180 / 927.5, delta=0.002)
        self.assertEqual(giant["factors"]["strength_to_weight_permille"], 292)

    def test_mr_ton_walks_faster_and_steps_slower_than_a_man(self):
        _, walker = ok("scale_timing", {"height_mm": 6000, "appendages": [{"id": "arm", "length_mm": 2500}],
                                     "drop_heights_mm": [1000, 4000]})
        preferred = walker["walk"][1]
        self.assertEqual(preferred["froude_permille"], 250)
        self.assertEqual((preferred["speed_mm_s"], preferred["stride_mm"], preferred["cycle_ms"]), (2792, 4825, 1728))
        self.assertEqual(walker["limits"]["walk_run_speed_mm_s"], 3949)
        self.assertAlmostEqual(walker["drops"][1]["fall_ms"], 2 * walker["drops"][0]["fall_ms"], delta=1)  # t ~ sqrt(h)
        self.assertEqual(walker["appendages"][0]["period_ms"], round(2 * math.pi * math.sqrt(2 * 2500 / (3 * 9806.65))
                                                                  * 1000))

    def test_refusals(self):
        for arguments in ({}, {"height_mm": 1, "leg_length_mm": 1}, {"height_mm": 0}, {"height_mm": 1.5},
                          {"height_mm": 1750, "appendages": [{"id": "a", "length_mm": 1}] * 2},
                          {"height_mm": 1750, "froude_permille": []}, {"height_mm": 1750, "extra": 1}):
            refused(self, "scale_timing", arguments)


class GaitTests(unittest.TestCase):
    def test_a_clean_tracked_walk_passes_with_its_measured_cycle(self):
        assessment, result = ok("gait_check", walk_track())
        self.assertEqual(assessment, "thresholds_met", failing(result))
        self.assertEqual((result["stride_source"], result["cycle_source"]), ("track", "track"))
        self.assertEqual(result["measured"]["cycle_ms"], 1200)
        self.assertEqual(result["measured"]["step_time_asymmetry_permille"], 0)
        for foot in result["feet"]:
            self.assertEqual((foot["slide_mean_mm_s"], foot["strikes"]), (0, 4))
            self.assertAlmostEqual(foot["duty_permille"], 600, delta=20)

    def test_dynamic_similarity_a_giant_passes_only_with_time_scaled_by_root_length(self):
        s = 3180 / 928
        self.assertEqual(ok("gait_check", walk_track(s, math.sqrt(s)))[0], "thresholds_met")
        same_timing = ok("gait_check", walk_track(s, 1.0))[1]   # bigger but human timing: a run in walking clothes
        self.assertEqual(failing(same_timing), {"froude_permille"})
        human_speed = ok("gait_check", walk_track(s, s))[1]     # giant strides at a man's speed: slow motion
        self.assertEqual(failing(human_speed), {"stride_ratio_permille"})

    def test_a_skating_stance_foot_fails_on_slide_and_the_allowance_scales(self):
        result = ok("gait_check", walk_track(drift_mm_s=40))[1]
        self.assertEqual(failing(result), {"slide_mean_mm_s:l", "slide_mean_mm_s:r"})
        s = 3180 / 928
        giant = ok("gait_check", walk_track(s, math.sqrt(s), drift_mm_s=15))[1]
        self.assertEqual(giant["measured"]["slide_limit_mm_s"], round(10 * math.sqrt(3180 / 927.5)))
        self.assertEqual(failing(giant), set())   # 15 mm/s on a 6 m body is inside its scaled allowance

    def test_a_root_that_outruns_its_feet_is_a_kinematic_mismatch(self):
        arguments = walk_track()
        arguments["speed_mm_s"] = 1550
        self.assertIn("kinematic_mismatch_permille", failing(ok("gait_check", arguments)[1]))

    def test_run_duty_and_unmeasured_checks(self):
        result = ok("gait_check", {"leg_length_mm": 928, "speed_mm_s": 3000, "gait": "run", "cycle_ms": 700,
                                   "feet": [{"id": "l", "stance_ms": 250}]})[1]
        self.assertNotIn("froude_permille", {c["check"] for c in result["checks"]})
        self.assertEqual(result["feet"][0]["duty_permille"], 357)
        self.assertEqual(failing(result), set())
        self.assertEqual(ok("gait_check", {"leg_length_mm": 928, "speed_mm_s": 1348})[0], "not_scored")

    def test_refusals(self):
        track = walk_track()
        no_fps = dict(track)
        del no_fps["fps_milli"]
        uneven = walk_track()
        uneven["feet"][0]["track"]["contact"].pop()
        for arguments in ({"speed_mm_s": 1}, no_fps, uneven, {"leg_length_mm": 928, "speed_mm_s": 0, "gait": "stand"},
                          {"leg_length_mm": 928, "speed_mm_s": 1, "gait": "hop"},
                          {"leg_length_mm": 928, "speed_mm_s": 1, "thresholds": {"froude_min": 1.5}},
                          {"leg_length_mm": 928, "speed_mm_s": 1, "feet": [{"id": "l"}, {"id": "l"}]}):
            refused(self, "gait_check", arguments)


FEET = [[-100, 0, -50], [100, 0, -50], [-100, 0, 200], [100, 0, 200]]


def sway(amplitude, hz, frames=90):
    return [{"com_mm": [round(amplitude * math.sin(2 * math.pi * hz * i / 30)), 900, 75], "support_mm": FEET}
            for i in range(frames)]


class BalanceTests(unittest.TestCase):
    def test_static_com_inside_passes_and_a_lean_past_the_toes_fails(self):
        stand = [{"com_mm": [0, 900, 75], "support_mm": FEET}]
        self.assertEqual(ok("balance_check", {"fps_milli": 30000, "mode": "static", "frames": stand})[1]["checks"][0]
                         ["value"], 100)
        lean = [{"com_mm": [0, 900, 400], "support_mm": FEET}]
        result = ok("balance_check", {"fps_milli": 30000, "mode": "static", "frames": lean})[1]
        self.assertEqual((result["verdict"], result["checks"][0]["value"]), ("thresholds_not_met", -200))

    def test_zmp_follows_the_cart_table_model(self):
        for amplitude, hz in ((20, 0.3), (40, 0.5), (60, 1.0)):
            result = ok("balance_check", {"fps_milli": 30000, "frames": sway(amplitude, hz)})[1]
            expected = 100 - amplitude * (1 + 900 / 9806.65 * (2 * math.pi * hz) ** 2)
            self.assertAlmostEqual(result["worst"]["zmp_margin_mm"]["value"], expected, delta=max(10, 0.1 * abs(
                expected)))
        self.assertEqual(ok("balance_check", {"fps_milli": 30000, "frames": sway(60, 1.0)})[0], "thresholds_not_met")

    def test_flight_falls_at_g_and_a_floaty_jump_fails(self):
        def jump(g):
            return [{"com_mm": [0, round(1500 + 2000 * t - g * t * t / 2), 0], "support_mm": []}
                    for t in (i / 30 for i in range(20))]
        self.assertEqual(ok("balance_check", {"fps_milli": 30000, "frames": jump(9806.65)})[0], "thresholds_met")
        self.assertEqual(ok("balance_check", {"fps_milli": 30000, "frames": jump(3000)})[0], "thresholds_not_met")
        moon = ok("balance_check", {"fps_milli": 30000, "frames": jump(1625), "gravity_mm_s2": 1625})
        self.assertEqual(moon[0], "thresholds_met")

    def test_a_stop_needs_the_capture_point_inside(self):
        held = [{"com_mm": [0, 900, 75], "support_mm": FEET}] * 9
        self.assertEqual(ok("balance_check", {"fps_milli": 30000, "mode": "stop", "frames": held})[0], "thresholds_met")
        moving = [{"com_mm": [0, 900, 75 + round(1300 * i / 30)], "support_mm": FEET} for i in range(9)]
        result = ok("balance_check", {"fps_milli": 30000, "mode": "stop", "frames": moving})[1]
        self.assertIn("final_capture_margin_mm", failing(result))

    def test_blender_z_up_matches_three_y_up(self):
        y_up = ok("balance_check", {"fps_milli": 30000, "frames": sway(40, 0.5)})[1]
        z_frames = [{"com_mm": [f["com_mm"][0], f["com_mm"][2], f["com_mm"][1]],
                     "support_mm": [[p[0], p[2], p[1]] for p in f["support_mm"]]} for f in sway(40, 0.5)]
        z_up = ok("balance_check", {"fps_milli": 30000, "frames": z_frames, "up_axis": "z"})[1]
        self.assertEqual(y_up["worst"], z_up["worst"])

    def test_refusals(self):
        for arguments in ({"fps_milli": 30000, "frames": []}, {"fps_milli": 0, "frames": sway(1, 1, 3)},
                          {"fps_milli": 30000, "frames": [{"com_mm": [0, -5, 0], "support_mm": FEET}]},
                          {"fps_milli": 30000, "frames": [{"com_mm": [0, 900], "support_mm": FEET}]},
                          {"fps_milli": 30000, "frames": [{"com_mm": [0, 900, 0], "support_mm": []}]}):
            refused(self, "balance_check", arguments)


LEG = {"joints": [{"id": "hip", "type": "revolute", "axis": [1, 0, 0], "origin_mm": [0, 0, 0], "min": -2000,
                   "max": 2000},
                  {"id": "knee", "type": "revolute", "axis": [1, 0, 0], "origin_mm": [0, -450, 0], "min": 0,
                   "max": 2500}],
       "tip_mm": [0, -450, 0]}


class IkTests(unittest.TestCase):
    def test_forward_kinematics_of_a_bent_leg(self):
        result = ok("ik_check", {**LEG, "poses": [{"q": [-262, 524]}]})[1]
        hip, knee = -0.262, 0.524
        # rotation about +x by a turns -y towards -z: y = -450 cos a, z = -450 sin a
        expected = [0, round(-450 * math.cos(hip) - 450 * math.cos(hip + knee)),
                    round(-450 * math.sin(hip) - 450 * math.sin(hip + knee))]
        self.assertEqual(result["poses"][0]["tip_mm"], expected)
        self.assertEqual(result["verdict"], "thresholds_met")
        # a planar 2R chain: sigma_min / sigma_max follows |sin(knee)| (Lynch and Park, ex. 5.4)
        self.assertGreater(result["poses"][0]["singular_ratio_permille"], 50)

    def test_straight_knee_unreachable_target_and_limit_violations_fail(self):
        straight = ok("ik_check", {**LEG, "poses": [{"q": [0, 0], "target_mm": [0, -900, 0]}]})[1]
        self.assertEqual(failing(straight), {"singular_ratio_permille"})
        far = ok("ik_check", {**LEG, "poses": [{"q": [0, 300], "target_mm": [0, -1000, 0]}]})[1]
        self.assertEqual(failing(far), {"reach_margin_mm", "error_mm"})
        hyper = ok("ik_check", {**LEG, "poses": [{"q": [0, -100]}]})[1]
        self.assertIn("limit_margin", failing(hyper))
        self.assertEqual(hyper["poses"][0]["outside_limits"], ["knee"])

    def test_a_prismatic_joint_extends_along_its_axis(self):
        chain = {"joints": [{"id": "slide", "type": "prismatic", "axis": [0, 0, 1], "origin_mm": [0, 0, 0], "min": 0,
                             "max": 500}], "tip_mm": [0, 0, 100]}
        result = ok("ik_check", {**chain, "poses": [{"q": [300], "target_mm": [0, 0, 400]}]})[1]
        self.assertEqual((result["poses"][0]["tip_mm"], result["poses"][0]["error_mm"]), ([0, 0, 400], 0))

    def test_refusals(self):
        bad_axis = {**LEG, "joints": [{**LEG["joints"][0], "axis": [0, 0, 0]}], "poses": [{"q": [0]}]}
        for arguments in ({**LEG, "poses": [{"q": [0]}]}, bad_axis, {**LEG, "poses": []},
                          {**LEG, "joints": [{**LEG["joints"][0], "min": 5, "max": 1}], "poses": [{"q": [0]}]}):
            refused(self, "ik_check", arguments)


class MechanismTests(unittest.TestCase):
    def test_screw_rotors_turn_in_inverse_lobe_ratio_and_opposite_sense(self):
        train = {"kind": "gear_train", "input": "male", "input_speed_mrad_s": 371700,
                 "stages": [{"driver": "male", "driven": "female", "driver_teeth": 4, "driven_teeth": 6,
                             "mesh": "external"}]}
        right = ok("mechanism_check", {**train, "measured_speeds_mrad_s": {"female": -247800}})[1]
        self.assertEqual((right["verdict"], right["detail"]["stages"][0]["ratio_permille"]), ("thresholds_met", -667))
        wrong_way = ok("mechanism_check", {**train, "measured_speeds_mrad_s": {"female": 247800}})[1]
        self.assertEqual(wrong_way["verdict"], "thresholds_not_met")

    def test_a_compound_train_couples_gears_on_one_shaft(self):
        result = ok("mechanism_check", {"kind": "gear_train", "input": "a", "input_speed_mrad_s": 1000,
                                        "stages": [{"driver": "a", "driven": "b", "driver_teeth": 10,
                                                    "driven_teeth": 40, "mesh": "external"},
                                                   {"driver": "c", "driven": "d", "driver_teeth": 12,
                                                    "driven_teeth": 36, "mesh": "external"}],
                                        "shafts": [["b", "c"]], "measured_speeds_mrad_s": {"d": 83}})[1]
        self.assertEqual({g["id"]: g["speed_mrad_s"] for g in result["detail"]["gears"]},
                         {"a": 1000, "b": -250, "c": -250, "d": 83})

    def test_mesh_phase_lock(self):
        locked = [{"driver_mrad": i * 100, "driven_mrad": round(-i * 100 * 4 / 6) + 500} for i in range(100)]
        self.assertEqual(ok("mechanism_check", {"kind": "gear_mesh", "driver_teeth": 4, "driven_teeth": 6,
                                                "mesh": "external", "frames": locked})[0], "thresholds_met")
        wrapped = [{"driver_mrad": f["driver_mrad"] % 6283, "driven_mrad": f["driven_mrad"] % 6283} for f in locked]
        self.assertEqual(ok("mechanism_check", {"kind": "gear_mesh", "driver_teeth": 4, "driven_teeth": 6,
                                                "mesh": "external", "frames": wrapped})[0], "thresholds_met")
        slipping = [{"driver_mrad": i * 100, "driven_mrad": round(-i * 70)} for i in range(100)]
        self.assertEqual(ok("mechanism_check", {"kind": "gear_mesh", "driver_teeth": 4, "driven_teeth": 6,
                                                "mesh": "external", "frames": slipping})[0], "thresholds_not_met")

    def test_slider_crank_and_a_sinusoid_that_is_not_one(self):
        r, rod = 60, 200
        exact = [{"crank_mrad": i * 100, "slider_mm": round(r * math.cos(i / 10) + math.sqrt(rod * rod - (
            r * math.sin(i / 10)) ** 2))} for i in range(63)]
        result = ok("mechanism_check", {"kind": "slider_crank", "crank_mm": r, "rod_mm": rod, "frames": exact})[1]
        self.assertEqual((result["verdict"], result["detail"]["stroke_mm"]), ("thresholds_met", 120))
        sinus = [{"crank_mrad": f["crank_mrad"], "slider_mm": round(rod + r * math.cos(f["crank_mrad"] / 1000))}
                 for f in exact]
        self.assertEqual(ok("mechanism_check", {"kind": "slider_crank", "crank_mm": r, "rod_mm": rod,
                                                "frames": sinus})[0], "thresholds_not_met")
        short_rod = ok("mechanism_check", {"kind": "slider_crank", "crank_mm": 60, "rod_mm": 50})[1]
        self.assertEqual(failing(short_rod), {"rod_minus_crank_and_offset_mm"})

    def test_four_bar_grashof_and_loop_closure(self):
        d, a, b, c = 100, 40, 120, 80
        frames = []
        for i in range(0, 63):
            theta2 = i / 10
            # build the output angle geometrically: circle intersection, open branch
            ax, ay = a * math.cos(theta2), a * math.sin(theta2)
            dx, dy = d - ax, -ay
            dist = math.hypot(dx, dy)
            base = math.atan2(dy, dx)
            gamma = math.acos((dist * dist + c * c - b * b) / (2 * dist * c))
            frames.append({"input_mrad": i * 100, "output_mrad": round(1000 * (math.pi + base - gamma))})
        result = ok("mechanism_check", {"kind": "four_bar", "ground_mm": d, "input_mm": a, "coupler_mm": b,
                                        "output_mm": c, "input_full_turn": True, "frames": frames})[1]
        self.assertEqual(result["detail"]["classification"], "crank_rocker")
        crossed = ok("mechanism_check", {"kind": "four_bar", "ground_mm": d, "input_mm": a, "coupler_mm": b,
                                         "output_mm": c, "branch": "crossed", "frames": frames})[1]
        self.assertEqual({result["verdict"], crossed["verdict"]}, {"thresholds_met", "thresholds_not_met"})
        rocker = ok("mechanism_check", {"kind": "four_bar", "ground_mm": 100, "input_mm": 90, "coupler_mm": 120,
                                        "output_mm": 80, "input_full_turn": True})[1]
        self.assertEqual((rocker["detail"]["classification"], rocker["verdict"]),
                         ("non_grashof_triple_rocker", "thresholds_not_met"))

    def test_rotor_strobing_at_the_frame_rate(self):
        fan = {"kind": "rotor_strobe", "blades": 4, "speed_mrad_s": 183260, "fps_milli": 24000}  # 1750 rpm
        sharp = ok("mechanism_check", fan)[1]
        self.assertEqual((sharp["verdict"], sharp["detail"]["pitch_per_frame_permille"]), ("thresholds_not_met", 4861))
        blurred = ok("mechanism_check", {**fan, "shutter_permille": 500})[1]
        self.assertEqual((blurred["verdict"], blurred["detail"]["reads_as"]), ("thresholds_met", "smeared_disc"))
        stopped = ok("mechanism_check", {**fan, "speed_mrad_s": round(math.pi / 2 * 24 * 1000)})[1]
        self.assertEqual(stopped["detail"]["reads_as"], "stationary")
        slow = ok("mechanism_check", {**fan, "speed_mrad_s": 10000})[1]
        self.assertEqual((slow["verdict"], slow["detail"]["reads_as"]), ("thresholds_met", "true_motion"))

    def test_refusals(self):
        for arguments in ({"kind": "cam"}, {"kind": "gear_train", "input": "a", "input_speed_mrad_s": 1,
                                            "stages": [{"driver": "z", "driven": "b", "driver_teeth": 1,
                                                        "driven_teeth": 1, "mesh": "external"}]},
                          {"kind": "gear_train", "input": "a", "input_speed_mrad_s": 1,
                           "stages": [{"driver": "a", "driven": "b", "driver_teeth": 1, "driven_teeth": 1,
                                       "mesh": "external"}]},
                          {"kind": "four_bar", "ground_mm": 1, "input_mm": 1, "coupler_mm": 1, "output_mm": 1},
                          {"kind": "rotor_strobe", "blades": 4, "speed_mrad_s": 1, "fps_milli": 0},
                          {"kind": "slider_crank", "crank_mm": 1, "rod_mm": 2, "extra": 1}):
            refused(self, "mechanism_check", arguments)


class SquashTests(unittest.TestCase):
    def test_volume_is_kept_or_not(self):
        self.assertEqual(ok("squash_check", {"frames": [{"scale_permille": [1132, 780, 1132]}]})[0], "thresholds_met")
        refused(self, "squash_check", {"frames": [{"scale_permille": [1000, 0, 1000]}]})


class InventoryTests(unittest.TestCase):
    def test_inventory_order_and_every_result_carries_evidence(self):
        self.assertEqual(tuple(t["name"] for t in tool_definitions()), TOOL_NAMES)
        for name in TOOL_NAMES:
            self.assertTrue(refused(self, name, {"unexpected": 1}))


if __name__ == "__main__":
    unittest.main()
