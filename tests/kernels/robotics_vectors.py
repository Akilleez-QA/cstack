"""Differential vectors for the Robotics port: every tool, enum, boundary and error path of the pinned Python, a seeded fuzz and a search for rounding boundaries."""
import json
import random
from film_vectors import BAD, _drop, _paths, _set, _text
from lexical_vectors import lexical

MESHES = ("external", "internal", "belt", "crossed_belt")
FOOT = {"positions_mm": [[0, 0, 0], [5, 0, 1], [10, 0, 0], [400, 0, 90], [800, 0, 0], [803, 0, 0], [806, 0, 0], [1200, 0, 80], [1600, 0, 0], [1601, 2, 0]], "contact": [1, 1, 1, 0, 1, 1, 1, 0, 1, 1]}
OTHER = {"positions_mm": [[0, 100, 0], [100, 100, 40], [400, 100, 0], [403, 100, 0], [800, 100, 90], [1200, 100, 0], [1203, 100, 0], [1600, 100, 90], [2000, 100, 0], [2001, 100, 0]], "contact": [0, 0, 1, 1, 0, 1, 1, 0, 1, 1]}
STAND = [[-200, 0, -200], [200, 0, -200], [200, 0, 200], [-200, 0, 200]]
LEG = [{"id": "hip", "type": "revolute", "axis": [0, 0, 1], "origin_mm": [0, 0, 0], "min": -2000, "max": 2000}, {"id": "knee", "type": "revolute", "axis": [0, 0, 1], "origin_mm": [450, 0, 0], "min": -100, "max": 2500}]
SLIDE = {"id": "s", "type": "prismatic", "axis": [1, 0, 0], "origin_mm": [10, 20, 30], "min": -500, "max": 500}
SEEDS = {"scale_timing": {"height_mm": 6000, "appendages": [{"id": "arm", "length_mm": 800}], "drop_heights_mm": [1000], "froude_permille": [50, 250], "gravity_mm_s2": 3721},
         "gait_check": {"leg_length_mm": 928, "speed_mm_s": 1348, "feet": [{"id": "l", "track": FOOT}, {"id": "r", "track": OTHER, "stance_ms": 600}], "fps_milli": 24000, "up_axis": "z", "gait": "walk", "thresholds": {"froude_max": 400}},
         "balance_check": {"fps_milli": 24000, "frames": [{"com_mm": [i * 2, 900, i], "support_mm": STAND} for i in range(12)], "mode": "stop", "up_axis": "y", "thresholds": {"margin_mm": 1}},
         "ik_check": {"joints": LEG + [SLIDE], "tip_mm": [400, 0, 0], "poses": [{"q": [100, 400, 5], "target_mm": [800, 300, 30]}, {"q": [0, 0, 0]}]},
         "mechanism_check": {"kind": "gear_mesh", "driver_teeth": 12, "driven_teeth": 36, "mesh": "external", "frames": [{"driver_mrad": 300, "driven_mrad": -100}, {"driver_mrad": 600, "driven_mrad": -210}]},
         "squash_check": {"frames": [{"scale_permille": [1180, 780, 1180]}, {"scale_permille": [1000, 1000, 1000]}], "axis": "z"}}
TRAIN = {"kind": "gear_train", "input": "a", "input_speed_mrad_s": 1000, "stages": [{"driver": "a", "driven": "b", "driver_teeth": 20, "driven_teeth": 40, "mesh": "external"}, {"driver": "c", "driven": "d", "driver_teeth": 3, "driven_teeth": 7, "mesh": "crossed_belt"}], "shafts": [["b", "c"]], "measured_speeds_mrad_s": {"b": -500, "d": 214}}
SLIDER = {"kind": "slider_crank", "crank_mm": 50, "rod_mm": 200, "offset_mm": 5, "frames": [{"crank_mrad": 700, "slider_mm": 230}, {"crank_mrad": -3000, "slider_mm": 150}]}
FOUR = {"kind": "four_bar", "ground_mm": 100, "input_mm": 30, "coupler_mm": 90, "output_mm": 80, "frames": [{"input_mrad": 500, "output_mrad": 1400}, {"input_mrad": 4000, "output_mrad": -900}]}
STROBE = {"kind": "rotor_strobe", "blades": 5, "speed_mrad_s": 62832, "fps_milli": 24000, "shutter_permille": 500}
KINDS = (TRAIN, SEEDS["mechanism_check"], SLIDER, FOUR, STROBE)


def structured():
    out = []
    add = lambda tool, value: out.append((tool, _text(value)))
    bases = [(tool, seed) for tool, seed in SEEDS.items()] + [("mechanism_check", kind) for kind in KINDS]
    for tool, seed in bases:
        add(tool, seed)
        for path in _paths(seed):
            for bad in BAD:
                add(tool, _set(seed, path, bad))
            if path:
                add(tool, _drop(seed, path))
        add(tool, {**seed, "extra": 1})
        add(tool, {**seed, "aa": 1, "zz": 2})
    for leg in ({"leg_length_mm": 928}, {"height_mm": 1750}, {"height_mm": 1}, {"height_mm": 10 ** 7}, {"leg_length_mm": 1}, {"leg_length_mm": 10 ** 7}, {}, {"height_mm": 1, "leg_length_mm": 1}):
        add("scale_timing", leg)
        for gravity in ({}, {"gravity_mm_s2": 1}, {"gravity_mm_s2": 10 ** 6}):
            add("scale_timing", {**leg, **gravity})
            for speed in (0, 1, 1348, 10 ** 6):
                for gait in ("walk", "run", "stand", "skip"):
                    add("gait_check", {**leg, **gravity, "speed_mm_s": speed, "gait": gait})
                    add("gait_check", {**leg, **gravity, "speed_mm_s": speed, "gait": gait, "stride_mm": 1617, "cycle_ms": 1200, "feet": [{"id": "l", "stance_ms": 633, "slide_mean_mm_s": 3}]})
    for froude in ([1], [5000], [50, 250, 500], [0], [5001], [1] * 8, [1] * 9, []):
        add("scale_timing", {"height_mm": 1750, "froude_permille": froude})
    for up in ("y", "z", "x", 1):
        add("gait_check", {**SEEDS["gait_check"], "up_axis": up})
        add("balance_check", {**SEEDS["balance_check"], "up_axis": up})
    for mode in ("static", "dynamic", "stop", "jump"):
        add("balance_check", {**SEEDS["balance_check"], "mode": mode})
        add("balance_check", {"fps_milli": 24000, "mode": mode, "frames": [{"com_mm": [0, 2000 - i * i * 8, 0], "support_mm": []} for i in range(14)]})
        add("balance_check", {"fps_milli": 24000, "mode": mode, "frames": [{"com_mm": [0, 900, 0], "support_mm": [[0, 0, 0]]}]})
        add("balance_check", {"fps_milli": 24000, "mode": mode, "frames": [{"com_mm": [i, 900, 0], "support_mm": [[0, 0, 0], [100, 0, 0]]} for i in range(11)]})
        add("balance_check", {"fps_milli": 24000, "mode": mode, "frames": [{"com_mm": [0, 0, 0], "support_mm": [[0, 10, 0]]}]})
        add("balance_check", {"fps_milli": 1000, "mode": mode, "frames": [{"com_mm": [0, 900 - 50000 * i * i, 0], "support_mm": [[0, -10 ** 7, 0]]} for i in range(5)]})
    for window in (0, 1, -10 ** 12, 200, 2000, 10 ** 5, 10 ** 12):
        for fps in (1, 1000, 24000, 10 ** 6):
            if window * fps < 2 * 10 ** 11:
                add("balance_check", {**SEEDS["balance_check"], "fps_milli": fps, "thresholds": {"derivative_window_ms": window}})
    add("balance_check", {"fps_milli": 24000, "frames": [{"com_mm": [2 ** 25, 900, 0], "support_mm": STAND}]})
    add("balance_check", {"fps_milli": 24000, "frames": [{"com_mm": [2 ** 25 + 1, 900, 0], "support_mm": STAND}]})
    add("balance_check", {"fps_milli": 24000, "frames": [{"com_mm": [0, 900, 0], "support_mm": [[-2 ** 25, 0, -2 ** 25], [2 ** 25, 0, -2 ** 25], [2 ** 25, 0, 2 ** 25], [-2 ** 25, 0, 2 ** 25]]}], "mode": "static"})
    for pose in ([0, 0, 0], [0, 1570, 0], [3141, 3141, 500], [10 ** 9, -10 ** 9, 10 ** 9], [2000, 2500, -500], [2001, 0, 0], [0, 0, 501]):
        for target in (None, [0, 0, 0], [850, 0, 0], [10 ** 6, 0, 0], [10 ** 9, 10 ** 9, -10 ** 9]):
            row = {"q": pose} if target is None else {"q": pose, "target_mm": target}
            add("ik_check", {**SEEDS["ik_check"], "poses": [row]})
    for joints in (LEG, LEG[:1], [SLIDE], [SLIDE, {**SLIDE, "id": "t"}], [{**LEG[0], "axis": [1, 1, 1]}, {**LEG[1], "axis": [0, 1, -1]}], [{**LEG[0], "axis": [0, 0, 0]}], LEG + LEG, [{**LEG[0], "min": 5, "max": 1}], [{**LEG[0], "type": "ball"}], [{**LEG[0], "origin_mm": [2 ** 25, 0, 0]}], [{**LEG[0], "origin_mm": [2 ** 25 + 1, 0, 0]}], [{**LEG[0], "axis": [10 ** 9, 0, 0]}]):
        add("ik_check", {"joints": joints, "tip_mm": [400, 0, 0], "poses": [{"q": [0] * len(joints), "target_mm": [100, 100, 0]}, {"q": [900] * len(joints)}]})
    straight = [{**LEG[0], "origin_mm": [0, 0, 0]}, {**LEG[1], "origin_mm": [10 ** 6, 0, 0]}]
    add("ik_check", {"joints": straight, "tip_mm": [10 ** 6, 0, 0], "poses": [{"q": [0, 0]}, {"q": [10, 0]}, {"q": [1571, 0]}]})
    for mesh in (*MESHES, "chain"):
        add("mechanism_check", {**TRAIN, "stages": [{**TRAIN["stages"][0], "mesh": mesh}]})
        add("mechanism_check", {**SEEDS["mechanism_check"], "mesh": mesh})
    add("mechanism_check", {**TRAIN, "input_speed_mrad_s": 0, "measured_speeds_mrad_s": {"a": 0, "b": 5}})
    add("mechanism_check", {**TRAIN, "measured_speeds_mrad_s": {"zz": 0, "aa": 5}})
    add("mechanism_check", {**TRAIN, "measured_speeds_mrad_s": {}})
    add("mechanism_check", {"kind": "gear_train", "input": "2", "input_speed_mrad_s": 7, "stages": [{"driver": "2", "driven": "1", "driver_teeth": 1, "driven_teeth": 3, "mesh": "belt"}, {"driver": "1", "driven": "0", "driver_teeth": 1, "driven_teeth": 3, "mesh": "belt"}], "measured_speeds_mrad_s": {"0": 1}})
    for lengths in ((100, 30, 90, 80), (30, 100, 90, 80), (100, 90, 30, 80), (100, 90, 80, 30), (10, 10, 10, 10), (40, 30, 20, 10), (10, 30, 40, 60), (20, 20, 20, 50), (10 ** 7, 1, 10 ** 7, 1), (100, 200, 10, 10)):
        for branch in ("open", "crossed", "other"):
            for full in (False, True, 1):
                add("mechanism_check", {"kind": "four_bar", "ground_mm": lengths[0], "input_mm": lengths[1], "coupler_mm": lengths[2], "output_mm": lengths[3], "branch": branch, "input_full_turn": full, "frames": [{"input_mrad": 500, "output_mrad": 1400}, {"input_mrad": 0, "output_mrad": 0}, {"input_mrad": 3142, "output_mrad": 1}]})
    for crank, rod, offset in ((50, 200, 0), (50, 200, 149), (50, 200, 150), (50, 200, -151), (50, 200, 250), (50, 200, 251), (50, 200, -251), (200, 50, 0), (200, 50, 100), (10 ** 7, 10 ** 7, 0), (10 ** 7, 10 ** 7, 2 * 10 ** 7), (10 ** 7, 10 ** 7, 2 * 10 ** 7 + 1), (10 ** 7, 10 ** 7, 10 ** 12), (1, 1, -10 ** 12), (3, 94906267, 94906270)):
        add("mechanism_check", {"kind": "slider_crank", "crank_mm": crank, "rod_mm": rod, "offset_mm": offset})
        add("mechanism_check", {"kind": "slider_crank", "crank_mm": crank, "rod_mm": rod, "offset_mm": offset, "frames": [{"crank_mrad": 700, "slider_mm": 230}, {"crank_mrad": 0, "slider_mm": 0}, {"crank_mrad": 1571, "slider_mm": 0}]})
    for blades, speed, shutter in ((5, 62832, 500), (5, 0, 0), (1, 10 ** 12, 1000), (1000, 1, 0), (5, -62832, 0), (4, 39270, 0), (4, 39270 * 2, 0), (4, 39270 * 2, 1000), (3, 50265, 0), (3, 49000, 0), (3, 52000, 0)):
        add("mechanism_check", {"kind": "rotor_strobe", "blades": blades, "speed_mrad_s": speed, "fps_milli": 24000, "shutter_permille": shutter})
    for axis in ("x", "y", "z", "w", 0):
        for scale in ([1, 1, 1], [10 ** 6, 10 ** 6, 10 ** 6], [1000, 1000, 1000], [1090, 890, 1090], [999, 1001, 1000], [0, 1, 1], [1, 1], [10 ** 6 + 1, 1, 1]):
            add("squash_check", {"axis": axis, "frames": [{"scale_permille": scale}]})
    return out


def lexical_vectors():
    out = []
    for tool, seed, key, head in (("scale_timing", {"height_mm": 6000}, '"height_mm":6000', '"height_mm":'), ("squash_check", SEEDS["squash_check"], '"axis":"z"', '"thresholds":{"volume_error_max":'), ("mechanism_check", STROBE, '"blades":5', '"blades":')):
        tail = "}," if tool == "squash_check" else ""
        out += lexical(tool, seed, (head, key, tail + ('"axis":"z"' if tool == "squash_check" else "")))
    return out


def fuzz(count, seed):
    rng = random.Random(seed)
    good = lambda: rng.random() < 0.97
    scale = lambda top: rng.randint(1, top) if rng.random() < .5 else rng.randint(1, max(1, min(top, 10 ** rng.randint(1, 8))))
    signed = lambda top: rng.choice((-1, 1)) * scale(top)
    mrad = lambda: rng.randint(-7000, 7000) if rng.random() < .8 else rng.randint(-10 ** 12, 10 ** 12)
    limits = lambda keys: {k: rng.randint(-5, 2000) for k in rng.sample(keys, rng.randint(0, min(2, len(keys))))}

    def scale_tool():
        args = {rng.choice(("height_mm", "leg_length_mm")): scale(10 ** 7)}
        if rng.random() < .3:
            args["gravity_mm_s2"] = scale(10 ** 6)
        if rng.random() < .5:
            args["froude_permille"] = [rng.randint(1, 5000) for _ in range(rng.randint(1, 8))]
        if rng.random() < .5:
            args["appendages"] = [{"id": f"a{i}", "length_mm": scale(10 ** 7)} for i in range(rng.randint(0, 4))]
        if rng.random() < .5:
            args["drop_heights_mm"] = [scale(10 ** 7) for _ in range(rng.randint(0, 4))]
        return "scale_timing", args

    def track(frames):
        x = rng.randint(-1000, 1000)
        positions, contact = [], []
        state = rng.randint(0, 1)
        for _ in range(frames):
            if rng.random() < .2:
                state = 1 - state
            x += rng.randint(0, 60) if not state else rng.randint(0, 2)
            positions.append([x, rng.randint(0, 100), rng.randint(0, 100)])
            contact.append(state)
        return {"positions_mm": positions, "contact": contact}

    def gait_tool():
        args = {rng.choice(("height_mm", "leg_length_mm")): scale(10 ** 5), "speed_mm_s": rng.choice((0, rng.randint(0, 3000), scale(10 ** 6)))}
        if rng.random() < .4:
            args["stride_mm"] = scale(10 ** 5)
        if rng.random() < .4:
            args["cycle_ms"] = scale(10 ** 4)
        feet = []
        for name in rng.sample(("l", "r", "1", "0"), rng.randint(0, 4 if rng.random() < .2 else 2)):
            foot = {"id": name}
            if rng.random() < .6:
                foot["track"] = track(rng.randint(2, 60))
                args["fps_milli"] = rng.choice((24000, 30000, 23976, 60000, scale(10 ** 6)))
            if rng.random() < .3:
                foot["stance_ms"] = scale(5000)
            if rng.random() < .3:
                foot["slide_mean_mm_s"] = rng.randint(0, 100)
            feet.append(foot)
        if feet or rng.random() < .3:
            args["feet"] = feet
        if rng.random() < .5:
            args["gait"] = rng.choice(("walk", "run", "stand"))
        if rng.random() < .3:
            args["up_axis"] = rng.choice(("y", "z"))
        if rng.random() < .2:
            args["gravity_mm_s2"] = scale(10 ** 6)
        if rng.random() < .3:
            args["thresholds"] = limits(["froude_min", "froude_max", "stride_ratio_min", "stride_ratio_max", "duty_walk_min", "slide_mean_mm_s", "kinematic_mismatch_max", "step_time_asymmetry_max"])
        return "gait_check", args

    def balance_tool():
        up = rng.choice(("y", "z"))
        idx = 1 if up == "y" else 2
        n = rng.randint(1, 30)
        box = rng.randint(50, 500)
        def point(h):
            p = [rng.randint(-box, box), rng.randint(-box, box), rng.randint(-box, box)]
            p[idx] = h
            return p
        frames = []
        com = [rng.randint(-100, 100), rng.randint(-100, 100), rng.randint(-100, 100)]
        com[idx] = rng.randint(200, 2000)
        flight = rng.random() < .15
        for i in range(n):
            c = list(com)
            c[0] += rng.randint(-5, 5) * i
            if flight:
                c[idx] -= int(4903 * (i / 24) ** 2)
            contacts = [] if flight or rng.random() < .05 else [point(0) for _ in range(rng.randint(1, 6))]
            frames.append({"com_mm": c, "support_mm": contacts})
        args = {"fps_milli": rng.choice((24000, 30000, 60000, 1000, 120000)), "frames": frames, "mode": rng.choice(("static", "dynamic", "stop"))}
        if up == "z" or rng.random() < .3:
            args["up_axis"] = up
        if rng.random() < .3:
            args["thresholds"] = limits(["margin_mm", "flight_gravity_error_max"])
            if rng.random() < .3:
                args["thresholds"]["derivative_window_ms"] = rng.randint(0, 1000)
        return "balance_check", args

    def ik_tool():
        joints = []
        for i in range(rng.randint(1, 7)):
            kind = "prismatic" if rng.random() < .2 else "revolute"
            axis = rng.choice(([0, 0, 1], [1, 0, 0], [0, 1, 0], [rng.randint(-9, 9), rng.randint(-9, 9), rng.randint(1, 9)]))
            joints.append({"id": f"j{i}", "type": kind, "axis": axis, "origin_mm": [signed(2000), signed(2000), rng.randint(-50, 50)], "min": -rng.randint(0, 4000), "max": rng.randint(0, 4000)})
        poses = []
        for _ in range(rng.randint(1, 4)):
            pose = {"q": [rng.randint(-3500, 3500) if rng.random() < .9 else signed(10 ** 9) for _ in joints]}
            if rng.random() < .5:
                pose["target_mm"] = [signed(5000), signed(5000), signed(5000)]
            poses.append(pose)
        args = {"joints": joints, "tip_mm": [signed(1000), signed(1000), rng.randint(-50, 50)], "poses": poses}
        if rng.random() < .2:
            args["thresholds"] = limits(["tolerance_mm", "singular_ratio_min"])
        return "ik_check", args

    def mechanism_tool():
        kind = rng.choice(("gear_train", "gear_mesh", "slider_crank", "four_bar", "rotor_strobe"))
        if kind == "gear_train":
            names = rng.sample(("a", "b", "c", "d", "e", "1", "0", "9"), 8)
            stages = [{"driver": names[i], "driven": names[i + 1], "driver_teeth": scale(10 ** 5), "driven_teeth": scale(10 ** 5), "mesh": rng.choice(MESHES)} for i in range(rng.randint(1, 6))]
            args = {"kind": kind, "input": names[0], "input_speed_mrad_s": rng.randint(-10 ** 6, 10 ** 6), "stages": stages, "measured_speeds_mrad_s": {names[i]: rng.randint(-10 ** 6, 10 ** 6) for i in range(rng.randint(0, 3))}}
        elif kind == "gear_mesh":
            n1, n2 = scale(500), scale(500)
            mesh = rng.choice(MESHES)
            sign = -1 if mesh in ("external", "crossed_belt") else 1
            args = {"kind": kind, "driver_teeth": n1, "driven_teeth": n2, "mesh": mesh, "frames": []}
            for i in range(rng.randint(2, 20)):
                driver = rng.randint(-20000, 20000)
                args["frames"].append({"driver_mrad": driver, "driven_mrad": int(sign * n1 / n2 * driver) + rng.randint(-3, 3)})
        elif kind == "slider_crank":
            r, l = scale(10 ** 5), scale(10 ** 5)
            args = {"kind": kind, "crank_mm": r, "rod_mm": l, "frames": [{"crank_mrad": mrad(), "slider_mm": rng.randint(-10 ** 5, 10 ** 5)} for _ in range(rng.randint(0, 6))]}
            if rng.random() < .6:
                args["offset_mm"] = rng.randint(-max(r, l), max(r, l))
        elif kind == "four_bar":
            args = {"kind": kind, "ground_mm": scale(10 ** 4), "input_mm": scale(10 ** 4), "coupler_mm": scale(10 ** 4), "output_mm": scale(10 ** 4), "frames": [{"input_mrad": mrad(), "output_mrad": mrad()} for _ in range(rng.randint(0, 6))]}
            if rng.random() < .5:
                args["branch"] = rng.choice(("open", "crossed"))
            if rng.random() < .3:
                args["input_full_turn"] = rng.choice((True, False))
        else:
            args = {"kind": kind, "blades": rng.randint(1, 12), "speed_mrad_s": rng.randint(-10 ** 6, 10 ** 6), "fps_milli": rng.choice((24000, 30000, scale(10 ** 6))), "shutter_permille": rng.randint(0, 1000)}
        return "mechanism_check", args

    def squash_tool():
        args = {"frames": [{"scale_permille": [scale(3000), scale(3000), scale(3000)]} for _ in range(rng.randint(1, 8))]}
        if rng.random() < .5:
            args["axis"] = rng.choice("xyz")
        if rng.random() < .3:
            args["thresholds"] = limits(["volume_error_max"])
        return "squash_check", args

    out = []
    makers = (scale_tool, gait_tool, balance_tool, ik_tool, mechanism_tool, squash_tool)
    for _ in range(count):
        tool, args = rng.choice(makers)()
        if rng.random() < .05:
            path = rng.choice([p for p in _paths(args) if p])
            args = _set(args, path, rng.choice(BAD)) if rng.random() < .7 else _drop(args, path)
        elif rng.random() < .02:
            args["extra" if rng.random() < .5 else "aa"] = 1
        thresholds = args.get("thresholds") if isinstance(args, dict) else None
        if isinstance(thresholds, dict) and type(thresholds.get("derivative_window_ms")) is int and thresholds["derivative_window_ms"] > 10 ** 4:
            thresholds["derivative_window_ms"] = 10 ** 4
        out.append((tool, _text(args)))
    return out
