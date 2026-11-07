"""Measure every Foundation route with the real spawn counter. A measurement, not a gate; results go in docs/verification."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tools")]
import spawncount  # noqa: E402

CASES = {
    "foundation_refrigeration": ("saturation_pressure", {"fluid": "NH3", "temperature": {"value": -10, "unit": "degC"}}),
    "foundation_template": ("echo_observation", {"observation": "fixture"}),
    "foundation_film": ("cue_vocabulary_check", {"provided": [{"id": "b4:w:heat", "t_ms": 41000}], "aliases": {"b4:heat": "b4:w:heat"},
                                                 "lanes": [{"lane": "scene-b04", "references": ["b4:heat", "slam-1"]}]}),
    "foundation_robotics": ("scale_timing", {"height_mm": 6000}),
    "foundation_math": ("exact_scalar", {"domain": "Q", "operation": "add", "operands": [{"numerator": 1, "denominator": 2}, {"numerator": 1, "denominator": 3}]}),
}
PYODIDE = [
    dict(foundation="foundation_template", path="foundations/template", prelude="from foundation_template.tools import run", expression="run('echo_observation', json.loads(text))"),
    dict(foundation="foundation_refrigeration", path="foundations/refrigeration", prelude="from foundation_refrigeration.tools import run as rrun", expression="rrun('saturation_pressure', json.loads(text))"),
    dict(foundation="foundation_robotics", path="foundations/robotics", prelude="from foundation_robotics.tools import run as brun", expression="brun('scale_timing', json.loads(text))"),
    dict(foundation="foundation_film", path="foundations/film", prelude="from foundation_film.tools import run as frun", expression="frun('cue_vocabulary_check', json.loads(text))"),
    dict(foundation="foundation_math", path="vendor/foundation-math-v014", prelude="from foundation_math_bridge.server import _tool_result", expression="_tool_result('exact_scalar', json.loads(text))"),
]


def stdio_child(foundation, calls):
    from bootstrap import DOMAINS
    from poodo_core import CapabilityRequest
    domain = DOMAINS[foundation]
    capability = domain.capability(domain.source_root)
    tool, arguments = CASES[foundation]
    started = time.perf_counter()
    window = time.monotonic_ns()
    statuses = []
    for i in range(calls):
        request = CapabilityRequest.from_dict(dict(schema="poodo.capability-request/0.1", request_id=f"r{i}", goal_id="g", goal_revision=1, decision_id=f"d{i}",
                                                   capability_id=foundation, operation=tool, arguments=arguments, required_evidence="tool_observation"))
        statuses.append(capability.invoke(request, f"attempt-{i}").to_dict()["execution_status"])
    print(json.dumps(dict(per_call_ms=(time.perf_counter() - started) * 1000 / calls, window_ns=[window, time.monotonic_ns()], statuses=sorted(set(statuses)))))


def stdio_arm(foundation, calls):
    with tempfile.TemporaryDirectory() as directory:
        out, events = Path(directory, "out"), Path(directory, "events")
        spawncount.trace([sys.executable, "-B", __file__, "--stdio-child", foundation, "--calls", str(calls)], str(events), stdout=str(out))
        row = json.loads(out.read_text())
        counted = spawncount.count(json.loads(events.read_text()), *row["window_ns"])
    return dict(foundation=foundation, route="stdio", calls=calls, process=counted["process"], exec=counted["exec"], per_call_ms=row["per_call_ms"], statuses=row["statuses"])


def pyodide_arm(path, calls):
    rows = [dict(row, arguments=CASES[row["foundation"]][1]) for row in PYODIDE]
    with tempfile.TemporaryDirectory() as directory:
        out, events = Path(directory, "out"), Path(directory, "events")
        spawncount.trace(["node", str(ROOT / "tools/measure_routes_pyodide.mjs"), path, str(ROOT), json.dumps(rows), str(calls)], str(events), stdout=str(out))
        report = json.loads(out.read_text())
        recorded = json.loads(events.read_text())
        for row in report["rows"]:
            row.update(spawncount.count(recorded, *map(int, row.pop("window_ns"))))
    return report


def js_port_arm():
    from tests.forge_fixtures import Forge, goal, outcome
    from tests.test_workcell_film_robotics import FILM_LOOP, IMPORTS, ROBOTICS_LOOP, arguments
    from tests.test_workcell_foundation_imports import REFRIGERATION, TEMPLATE, TEMPLATE_ARGUMENTS, traced
    rows = []
    for foundation, source, document in (("foundation_refrigeration", REFRIGERATION, goal()), ("foundation_template", TEMPLATE, goal(**TEMPLATE_ARGUMENTS)),
                                         ("foundation_film", FILM_LOOP, goal(**arguments())), ("foundation_robotics", ROBOTICS_LOOP, goal(**arguments()))):
        for isolation in ("process", "thread"):
            forge = Forge(source, isolation=isolation, imports=IMPORTS)
            try:
                _, result, events = traced(forge, document)
            finally:
                forge.close()
            attempt = outcome(result)["raw_result"]["candidates"][0]
            start, end = map(int, attempt["window_ns"])
            inside = spawncount.count(events, start, end)
            rows.append(dict(foundation=foundation, route="js-port", isolation=isolation, status=attempt["status"], calls=attempt["calls"], process=inside["process"], exec=inside["exec"],
                             thread=inside["thread"], foundation_us_per_call=int(attempt["foundation_ns"]) / attempt["calls"] / 1000,
                             wall_us_per_call_through_wasm=sum(r["wall_ms"] for r in attempt["runs"]) * 1000 / attempt["calls"], compile_ms=attempt["wasm"]["compile_ms"]))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdio-child")
    parser.add_argument("--calls", type=int, default=20)
    parser.add_argument("--pyodide", help="path to pyodide.mjs from a separate npm install; not a Cstack dependency")
    args = parser.parse_args()
    if args.stdio_child:
        return stdio_child(args.stdio_child, args.calls)
    report = dict(stdio=[stdio_arm(name, args.calls) for name in CASES], js_port=js_port_arm())
    if args.pyodide:
        report["pyodide"] = pyodide_arm(args.pyodide, 1000)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
