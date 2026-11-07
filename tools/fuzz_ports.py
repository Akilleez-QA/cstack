"""Fuzz the Film and Robotics JS ports against the pinned Python, search for rounding boundaries, and measure libm differences. A measurement; results go in docs/verification."""
import argparse
import json
import math
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tests/kernels"), str(ROOT / "foundations/film"), str(ROOT / "foundations/robotics")]
import film_vectors  # noqa: E402
import port_reference  # noqa: E402
import robotics_vectors  # noqa: E402
MODULES = ("balance", "gait", "kinematics", "mechanisms", "scale", "squash")
LIBM = """
const rows = JSON.parse(require('fs').readFileSync(process.argv[1], 'utf8'));
const f = { sin: Math.sin, cos: Math.cos, atan2: Math.atan2, pow: Math.pow };
process.stdout.write(JSON.stringify(rows.map(([name, ...args]) => f[name](...args))));
"""


def strip(report):
    report = dict(report)
    report["first"] = report["first"][:3]
    return report


def fuzz(count, seed):
    out = {}
    for foundation, source in (("foundation_film", film_vectors), ("foundation_robotics", robotics_vectors)):
        out[foundation] = dict(structured=strip(port_reference.compare(foundation, source.structured())), lexical=strip(port_reference.compare(foundation, source.lexical_vectors())),
                               fuzz=strip(port_reference.compare(foundation, source.fuzz(count, seed), timeout=3000)))
    out["unguarded_robotics_fuzz"] = strip(port_reference.compare("foundation_robotics", robotics_vectors.fuzz(count, seed), guard="unguarded", timeout=3000))
    return out


class Probe:
    """Run the pinned Python twice, once with libm outputs nudged by 2^-50, and rate each rounded output: its distance to a rounding boundary over how far the nudge moved it. Under 1, the nudge can flip it."""
    NUDGE = 1 + 2 ** -50

    def __init__(self):
        import importlib
        self.tools = importlib.import_module("foundation_robotics.tools")
        measures = importlib.import_module("foundation_robotics.measures")
        self.real_rnd, self.modules, self.values, self.on = measures.rnd, [importlib.import_module("foundation_robotics." + name) for name in MODULES], [], False
        shim = types.SimpleNamespace(**{name: getattr(math, name) for name in dir(math) if not name.startswith("_")})
        for name in ("sin", "cos", "atan2", "dist"):
            setattr(shim, name, self._nudged(getattr(math, name)))
        self.originals = [(module, {name: getattr(module, name) for name in ("math", "rnd", "predicted_stride") if hasattr(module, name)}) for module in self.modules]
        for module in self.modules:
            module.rnd = self._rnd
            if hasattr(module, "math"):
                module.math = shim
            if hasattr(module, "predicted_stride"):
                module.predicted_stride = self._nudged(module.predicted_stride)

    def _nudged(self, function):
        return lambda *args: function(*args) * (self.NUDGE if self.on else 1)

    def _rnd(self, x):
        self.values.append(x)
        return self.real_rnd(x)

    def _run(self, tool, args, on):
        self.on, self.values = on, []
        failed, _, _ = self.tools.run(tool, args)
        return None if failed else self.values

    def score(self, tool, args):
        try:
            base, moved = self._run(tool, args, False), self._run(tool, args, True)
        except Exception:
            return math.inf
        if base is None or moved is None:
            return math.inf
        if len(base) != len(moved):
            return 0.0
        best = math.inf
        for x, y in zip(base, moved):
            if x is None or y is None:
                if x is not y:
                    return 0.0
            elif x != y and abs(x) < 1e12:
                best = min(best, abs(abs(x) % 1.0 - 0.5) / abs(x - y))
        return best


def _ik(q1, q2):
    joints = [{"id": "r", "type": "revolute", "axis": [0, 0, 1], "origin_mm": [0, 0, 0], "min": -10 ** 9, "max": 10 ** 9}, {"id": "p", "type": "prismatic", "axis": [1, 0, 0], "origin_mm": [0, 0, 0], "min": -10 ** 9, "max": 10 ** 9}]
    return "ik_check", {"joints": joints, "tip_mm": [0, 0, 0], "poses": [{"q": [q1, q2]}]}


FAMILIES = {"ik_cos": lambda a, b: _ik(a, b), "slider": lambda a, b: ("mechanism_check", {"kind": "slider_crank", "crank_mm": b, "rod_mm": 10 ** 7, "frames": [{"crank_mrad": a, "slider_mm": 0}]}),
            "stride": lambda a, b: ("scale_timing", {"leg_length_mm": b, "froude_permille": [a]})}
SCAN = """
const [count, seed, cap] = process.argv.slice(1).map(Number);
let state = seed >>> 0;
const random = () => { state = (state + 0x6d2b79f5) >>> 0; let t = Math.imul(state ^ (state >>> 15), 1 | state); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
const families = {
  ik_cos: [() => [Math.floor(random() * 2e9) - 1e9, 5e8 + Math.floor(random() * 5e8)], (a, b) => b * Math.cos(a / 1000)],
  slider: [() => [Math.floor(random() * 2e6) - 1e6, 1e6 + Math.floor(random() * 9e6)], (a, b) => { const s = b * Math.sin(a / 1000); return b * Math.cos(a / 1000) + Math.sqrt(1e14 - s * s); }],
  stride: [() => [1 + Math.floor(random() * 999), 1e6 + Math.floor(random() * 9e6)], (a, b) => 2.3 * b * Math.pow(a / 1000, 0.3)],
};
const out = {};
for (const [name, [draw, value]] of Object.entries(families)) {
  out[name] = [];
  for (let i = 0; i < count && out[name].length < cap; i++) {
    const [a, b] = draw();
    const x = Math.abs(value(a, b));
    if (Math.abs(x % 1 - 0.5) < x * 2 ** -50) out[name].push([a, b]);
  }
}
process.stdout.write(JSON.stringify(out));
"""


def search(count, seed, cap):
    """Scan for outputs a last-place libm difference can flip. Inputs are integers, so this samples large outputs, where a unit in the last place is widest, instead of bisecting."""
    done = subprocess.run(["node", "-e", SCAN, str(count), str(seed), str(cap)], capture_output=True, text=True, timeout=3000, check=True)
    probe = Probe()
    found = []
    for name, pairs in json.loads(done.stdout).items():
        for a, b in pairs:
            tool, args = FAMILIES[name](a, b)
            found.append({"tool": tool, "family": name, "pair": [a, b], "flip_ratio": probe.score(tool, args), "arguments": args})
    for module, names in probe.originals:
        for name, value in names.items():
            setattr(module, name, value)
    return found


def boundary_report(found):
    vectors = [(row["tool"], json.dumps(row["arguments"], separators=(",", ":"))) for row in found]
    ratios = {}
    for row in found:
        ratios.setdefault(row["family"], []).append(row["flip_ratio"])
    return dict(vectors=len(vectors), flip_ratio_median={k: sorted(v)[len(v) // 2] for k, v in ratios.items()}, within_a_nudge={k: sum(x < 1 for x in v) for k, v in ratios.items()},
                guarded=strip(port_reference.compare("foundation_robotics", vectors, timeout=3000)), unguarded=strip(port_reference.compare("foundation_robotics", vectors, guard="unguarded", timeout=3000)))


def _ulps(a, b):
    if a == b:
        return 0
    x, y = (struct.unpack("<q", struct.pack("<d", v))[0] for v in (a, b))
    return abs(x - y)


def libm(count, seed):
    rng = random.Random(seed)
    calls = {"sin": math.sin, "cos": math.cos, "atan2": math.atan2, "pow": math.pow}
    rows = []
    for _ in range(count):
        rows.append(["sin", rng.randint(-10 ** 12, 10 ** 12) / 1000 if rng.random() < .3 else rng.randint(-7000, 7000) / 1000])
        rows.append(["cos", rng.randint(-10 ** 12, 10 ** 12) / 1000 if rng.random() < .3 else rng.randint(-7000, 7000) / 1000])
        rows.append(["atan2", rng.uniform(-1e6, 1e6), rng.uniform(-1e6, 1e6)])
        rows.append(["pow", rng.uniform(1e-6, 1e3), 0.3 if rng.random() < .7 else rng.uniform(.1, 3)])
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory, "rows.json")
        path.write_text(json.dumps(rows))
        done = subprocess.run(["node", "-e", LIBM, str(path)], capture_output=True, text=True, timeout=600, check=True)
    report = {}
    for row, ours in zip(rows, json.loads(done.stdout)):
        line = report.setdefault(row[0], dict(compared=0, different=0, max_ulps=0))
        difference = _ulps(calls[row[0]](*row[1:]), ours)
        line["compared"] += 1
        line["different"] += difference != 0
        line["max_ulps"] = max(line["max_ulps"], difference)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--scan", type=int, default=1000000000)
    parser.add_argument("--cap", type=int, default=400)
    parser.add_argument("--keep", type=int, default=60)
    parser.add_argument("--libm", type=int, default=100000)
    parser.add_argument("--boundaries", help="also write the boundary vectors here")
    args = parser.parse_args()
    found = search(args.scan, args.seed, args.cap)
    if args.boundaries:
        pairs = {name: [row["pair"] for row in found if row["family"] == name][:args.keep] for name in FAMILIES}
        Path(args.boundaries).write_text(json.dumps(pairs, separators=(",", ":")) + "\n")
    print(json.dumps(dict(python=sys.version.split()[0], fuzz=fuzz(args.count, args.seed), boundaries=boundary_report(found), libm=libm(args.libm, args.seed)), indent=1))


if __name__ == "__main__":
    main()
