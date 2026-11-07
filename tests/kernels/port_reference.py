"""The reference for the bounded-integer ports: the pinned Python Foundation, reached through its real bridge frame decoder."""
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BRIDGES = {"foundation_film": ("foundations/film", "foundation_film_bridge.server", "foundation-film-jsonrpc/1"),
           "foundation_robotics": ("foundations/robotics", "foundation_robotics_bridge.server", "foundation-robotics-jsonrpc/1")}
MODULES = {"foundation_film": "adapters/workcell/kernels/film.mjs", "foundation_robotics": "adapters/workcell/kernels/robotics.mjs"}


def bridge(foundation):
    root, module, protocol = BRIDGES[foundation]
    if str(ROOT / root) not in sys.path:
        sys.path.insert(0, str(ROOT / root))
    server = importlib.import_module(module)
    instance = server.Bridge()
    instance.dispatch({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": protocol}})
    return server, instance


def reference(foundation, vectors):
    server, instance = bridge(foundation)
    rows = []
    for tool, text in vectors:
        frame = '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":%s,"arguments":%s}}' % (json.dumps(tool), text)
        answer = json.loads(server.encode_response(instance.handle(frame.encode("utf-8", "surrogatepass"))))
        if "error" in answer:
            python = {"wire": answer["error"]["code"]}
        else:
            content = answer["result"]["structuredContent"]
            python = {"assessment": content["assessment"], "receipt": content["receipt"]}
        rows.append({"tool": tool, "arguments": text, "python": python})
    return rows


def compare(foundation, vectors, guard="guarded", timeout=600):
    return compare_rows(foundation, reference(foundation, vectors), guard, timeout)


def compare_rows(foundation, rows, guard="guarded", timeout=600):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory, "vectors.json")
        path.write_text(json.dumps(rows))
        done = subprocess.run(["node", str(ROOT / "tests/kernels/port_differential.mjs"), str(ROOT / MODULES[foundation]), str(ROOT / BRIDGES[foundation][0]), str(path), guard],
                              capture_output=True, text=True, timeout=timeout)
    if done.returncode:
        raise RuntimeError(done.stderr[-2000:])
    return json.loads(done.stdout)


def outcome_of(foundation, tool, text):
    module = Path(MODULES[foundation]).name
    code = f"import('./adapters/workcell/kernels/{module}').then(m => {{ try {{ console.log(JSON.stringify(m.createKernel({{root:{json.dumps(BRIDGES[foundation][0])}}}).run({json.dumps(tool)}, {json.dumps(text)}))); }} catch (e) {{ console.log(JSON.stringify({{code:e.code}})); }} }});"
    done = subprocess.run(["node", "--input-type=module", "-e", code], cwd=ROOT, capture_output=True, text=True, timeout=60, check=True)
    return json.loads(done.stdout)
