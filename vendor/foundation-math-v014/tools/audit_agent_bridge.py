#!/usr/bin/env python3
"""Independent, deterministic audit of the local JSON-RPC math bridge.

No external packages, network, live models, or arbitrary request execution.
Oracles below do not call backend parsing, arithmetic, or evaluation helpers.
Run from the source root: python -B tools/audit_agent_bridge.py
Also run with -O; checks deliberately do not use Python assert statements.
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
from io import BytesIO
from itertools import product
import json
from pathlib import Path
import random
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from foundation_math_bridge import server

CHECKS: dict[str, int] = {}


def require(condition: bool, category: str, detail: str) -> None:
    CHECKS[category] = CHECKS.get(category, 0) + 1
    if not condition:
        raise RuntimeError(f"{category}: {detail}")


def rpc(method: str, params: dict | None = None, identifier: object = 1) -> bytes:
    frame = {"jsonrpc": "2.0", "id": identifier, "method": method}
    if params is not None:
        frame["params"] = params
    return json.dumps(frame, separators=(",", ":"), ensure_ascii=True).encode()


def call(bridge: server.Bridge, name: str, arguments: dict) -> dict:
    response = bridge.handle(rpc("tools/call", {"name": name, "arguments": arguments}))
    require(response is not None and "result" in response, "tool_envelope", name)
    result = response["result"]
    content = result["structuredContent"]
    require(content["tool"] == name and content["formal_proof"] is False and
            content["runtime_goal_acceptance"] is False, "no_promotion", name)
    require(result["isError"] == (content["receipt"]["status"] != "success"),
            "tool_envelope", "error flag agrees with backend")
    return content


def lit(value: int, denominator: int = 1) -> dict:
    return {"type": "rational", "numerator": value, "denominator": denominator}


def var(name: str = "x") -> dict:
    return {"type": "variable", "name": name}


def binary(kind: str, left: dict, right: dict) -> dict:
    return {"type": kind, "operands": [left, right]}


def expression(rng: random.Random, depth: int, variables: tuple[str, ...]) -> dict:
    if depth == 0 or rng.randrange(4) == 0:
        return var(rng.choice(variables)) if rng.randrange(2) else lit(rng.randint(-4, 4), rng.randint(1, 5))
    return binary(rng.choice(("add", "multiply")), expression(rng, depth - 1, variables),
                  expression(rng, depth - 1, variables))


def value(node: dict, assignment: dict) -> Fraction:
    if node["type"] == "rational":
        return Fraction(node["numerator"], node["denominator"])
    if node["type"] == "variable":
        return Fraction(assignment[node["name"]])
    a, b = (value(n, assignment) for n in node["operands"])
    return a + b if node["type"] == "add" else a * b


def coefficients(node: dict) -> list[Fraction]:
    """Independent dense univariate coefficient oracle, low degree first."""
    if node["type"] == "rational":
        return [Fraction(node["numerator"], node["denominator"])]
    if node["type"] == "variable":
        return [Fraction(0), Fraction(1)]
    a, b = map(coefficients, node["operands"])
    if node["type"] == "add":
        return [(a[i] if i < len(a) else 0) + (b[i] if i < len(b) else 0)
                for i in range(max(len(a), len(b)))]
    out = [Fraction(0)] * (len(a) + len(b) - 1)
    for i, first in enumerate(a):
        for j, second in enumerate(b):
            out[i + j] += first * second
    return out


def predicate(node: dict, assignment: dict) -> bool:
    a, b = value(node["left"], assignment), value(node["right"], assignment)
    return {"lt": a < b, "le": a <= b, "eq": a == b, "ne": a != b,
            "ge": a >= b, "gt": a > b}[node["relation"]]


def polynomial_request(left: dict, right: dict) -> dict:
    return {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": ["x"],
            "operation": "verify_identity", "operands": [left, right]}


def audit_wire() -> None:
    b = server.Bridge()
    malformed = [b"", b"\xff", b'{"jsonrpc":"2.0","jsonrpc":"2.0"}',
                 b'{"a":1.0}', b'{"a":1e2}', b'{"a":NaN}', b'{"a":Infinity}',
                 b'{"a":-Infinity}', b'{"a":00}', b'{}{}']
    for frame in malformed:
        require(b.handle(frame)["error"]["code"] == -32700, "wire_rejection", repr(frame))
    bounded = [b"[" * 81 + b"]" * 81, b'["' + b"x" * 4097 + b'"]',
               b"[" + b"0," * 16384 + b"0]", b'0' + b' ' * 65536,
               str(1 << 4096).encode()]
    for frame in bounded:
        require(b.handle(frame)["error"]["code"] == -32002, "wire_resource", str(len(frame)))
    for identifier in (None, True, False, [], {}, 9007199254740992, -9007199254740992, "x" * 129):
        require(b.handle(rpc("ping", identifier=identifier))["error"]["code"] == -32600,
                "wire_ids", repr(identifier))
    for identifier in (0, -9007199254740991, 9007199254740991, "", "x" * 128, "☃"):
        require(b.handle(rpc("ping", identifier=identifier))["id"] == identifier,
                "wire_ids", "valid IDs retained")
    for frame in (b"[]", b"[{}]", b"null", b"true", b"1", b'"ping"'):
        require(b.handle(frame)["error"]["code"] == -32600, "wire_rejection", repr(frame))
    require(b.handle(rpc("tools/list"))["error"]["code"] == -32000, "protocol_state", "init gate")
    require(b.handle(b'{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"foundation-math-jsonrpc/1"}}') is None
            and not b.initialized, "protocol_state", "notification cannot initialize")
    require(b.handle(rpc("initialize", {"protocolVersion": "2025-03-26"}))["error"]["code"] == -32001,
            "protocol_state", "MCP version rejected")
    init = b.handle(rpc("initialize", {"protocolVersion": server.PROTOCOL}))
    require(init["result"]["mcpCompatible"] is False, "protocol_state", "not MCP")
    require(b.handle(rpc("initialize", {"protocolVersion": server.PROTOCOL}))["error"]["code"] == -32000,
            "protocol_state", "repeat initialize rejected")
    for method in ("resources/read", "prompts/get", "execute", "eval", "notifications/cancelled"):
        require(b.handle(rpc(method))["error"]["code"] == -32601, "protocol_allowlist", method)
    for name in ("lean", "exec", "run", "read_file", "../../etc/passwd"):
        require(b.handle(rpc("tools/call", {"name": name, "arguments": {}}))["error"]["code"] == -32602,
                "protocol_allowlist", name)
    original = server.calculate
    def forbidden(_: dict) -> dict:
        raise RuntimeError("a notification reached arithmetic")
    server.calculate = forbidden
    try:
        require(b.handle(b'{"jsonrpc":"2.0","method":"tools/call","params":{"name":"exact_scalar","arguments":{}}}') is None,
                "protocol_state", "notification performs no work")
    finally:
        server.calculate = original
    ping = rpc("ping")
    for size, exit_code, responses in ((65535, 0, 2), (65536, 0, 2), (65537, 2, 1)):
        sink = BytesIO()
        require(server.serve(BytesIO(ping + b" " * (size - len(ping)) + b"\n" + ping + b"\n"), sink) == exit_code
                and len(sink.getvalue().splitlines()) == responses, "stdio_framing", str(size))
    sink = BytesIO()
    require(server.serve(BytesIO(ping), sink) == 2 and json.loads(sink.getvalue())["error"]["code"] == -32700,
            "stdio_framing", "unterminated frame")
    sink = BytesIO()
    require(server.serve(BytesIO(b"bad\n" + ping + b"\n"), sink) == 0
            and len(sink.getvalue().splitlines()) == 2, "stdio_framing", "recover after bounded syntax error")
    oversized = server.encode_response({"jsonrpc": "2.0", "id": 3, "result": "x" * (server.MAX_OUTPUT_BYTES + 1)})
    require(json.loads(oversized)["error"]["code"] == -32002 and len(oversized) < 512,
            "output_limit", "oversized result withheld")
    command = [sys.executable, "-B"] + (["-O"] if sys.flags.optimize else []) + ["-m", "foundation_math_bridge"]
    process = subprocess.run(command, cwd=ROOT,
                             input=rpc("initialize", {"protocolVersion": server.PROTOCOL}) + b"\n" + ping + b"\n",
                             capture_output=True, timeout=10, check=False)
    require(process.returncode == 0 and process.stderr == b"" and len(process.stdout.splitlines()) == 2,
            "stdio_process", "only protocol on stdout")


def audit_math(bridge: server.Bridge) -> None:
    rng = random.Random(20261024)
    for i in range(150):
        a, b = Fraction(rng.randint(-50, 50), rng.randint(1, 20)), Fraction(rng.randint(-50, 50), rng.randint(1, 20))
        operation = rng.choice(("add", "subtract", "multiply", "divide", "negate", "power"))
        if operation == "divide" and not b:
            b = Fraction(1)
        if operation == "power":
            b = Fraction(rng.randint(1, 5) if not a else rng.randint(-5, 5))
        expected = {"add": lambda: a + b, "subtract": lambda: a - b, "multiply": lambda: a * b,
                    "divide": lambda: a / b, "negate": lambda: -a, "power": lambda: a ** int(b)}[operation]()
        operands = [{"numerator": q.numerator, "denominator": q.denominator} for q in ([a] if operation == "negate" else [a, b])]
        got = call(bridge, "exact_scalar", {"domain": "Q", "operation": operation, "operands": operands})
        result = got["receipt"]["result"]
        require(got["assessment"] == "exact_scalar_result" and Fraction(result["numerator"], result["denominator"]) == expected,
                "scalar_oracle", str(i))
    for operands, operation in (([1, 2], "divide"), ([0, 0], "power"), ([True, 1], "add"), ([1, 0], "divide")):
        got = call(bridge, "exact_scalar", {"domain": "Z", "operation": operation, "operands": operands})
        require(got["assessment"] == "tool_error" and got["receipt"]["result"] is None,
                "domain_rejection", f"{operation} {operands}")
    for i in range(96):
        left = expression(rng, 3, ("x",))
        right = binary("add", lit(0), deepcopy(left)) if i % 3 == 0 else expression(rng, 3, ("x",))
        a, b = coefficients(left), coefficients(right)
        expected = {j: (a[j] if j < len(a) else 0) - (b[j] if j < len(b) else 0)
                    for j in range(max(len(a), len(b)))}
        expected = {j: c for j, c in expected.items() if c}
        got = call(bridge, "polynomial_identity", polynomial_request(left, right))
        result = got["receipt"]["result"]
        actual = {term["exponents"][0]: Fraction(term["coefficient"]["numerator"], term["coefficient"]["denominator"])
                  for term in result["difference"]["terms"]}
        require(actual == expected and result["equal"] == (not expected), "polynomial_oracle", str(i))
        require(got["assessment"] == ("formal_polynomial_identity_not_equal" if expected else "formal_polynomial_identity_equal"),
                "no_promotion", "false identity is not a tool error or acceptance")
    base = {"domain": "finite_integer_box", "coefficient_field": "Q", "variables": ["y", "x"],
            "bounds": {"y": {"lower": -2, "upper": 2}, "x": {"lower": -2, "upper": 2}},
            "constraints": [], "assertion": {"relation": "ge", "left": var(), "right": lit(0)}}
    for i in range(90):
        request = deepcopy(base)
        predicates = [{"relation": rng.choice(("lt", "le", "eq", "ne", "ge", "gt")),
                       "left": expression(rng, 2, ("y", "x")), "right": expression(rng, 2, ("y", "x"))}
                      for _ in range(1 + i % 3)]
        request["constraints"], request["assertion"] = predicates[:-1], predicates[-1]
        witness, visited, eligible = None, 0, 0
        for y, x in product(range(-2, 3), repeat=2):
            assignment = {"y": y, "x": x}
            visited += 1
            if all(predicate(p, assignment) for p in request["constraints"]):
                eligible += 1
                if not predicate(request["assertion"], assignment):
                    witness = assignment
                    break
        got = call(bridge, "finite_box_search", request)
        receipt = got["receipt"]
        require(receipt["result"]["assignment"] == witness and receipt["progress"]["visited_count"] == visited
                and receipt["progress"]["eligible_count"] == eligible and receipt["progress"]["complete"] == (visited == 25),
                "finite_box_oracle", str(i))
        require(got["assessment"] == ("counterexample_found" if witness is not None else "no_counterexample_in_declared_finite_domain")
                and receipt["scope"]["universal_proof"] is False, "no_promotion", "finite exhaustion is not universal")
        if witness is not None:
            checked = call(bridge, "check_finite_box_witness", {"request": request, "assignment": witness})
            require(checked["assessment"] == "witness_valid", "witness_oracle", str(i))
        rejected = call(bridge, "check_finite_box_witness", {"request": request, "assignment": {"y": 3, "x": 0}})
        require(rejected["assessment"] == "witness_rejected", "witness_oracle", "outside declared box")
    for candidate in ({"y": 0, "x": {"numerator": 1, "denominator": 2}}, {"y": False, "x": 0}, {}, {"y": 0, "x": 0, "z": 1}):
        checked = call(bridge, "check_finite_box_witness", {"request": base, "assignment": candidate})
        require(checked["assessment"] == "witness_rejected", "witness_oracle", "no assignment coercion")
    large = deepcopy(base)
    large["bounds"]["x"]["upper"] = 10000
    got = call(bridge, "finite_box_search", large)
    require(got["assessment"] == "tool_error" and got["receipt"]["progress"]["complete"] is False,
            "resource_no_promotion", "oversized box")
    expression16 = var()
    for _ in range(4):
        expression16 = binary("add", deepcopy(expression16), deepcopy(expression16))
    budget = {"domain": "finite_integer_box", "coefficient_field": "Q", "variables": ["x"],
              "bounds": {"x": {"lower": 0, "upper": 9999}}, "constraints": [],
              "assertion": {"relation": "eq", "left": expression16, "right": deepcopy(expression16)}}
    got = call(bridge, "finite_box_search", budget)
    require(got["assessment"] == "tool_error" and got["receipt"]["result"] is None
            and got["receipt"]["progress"]["complete"] is False
            and got["receipt"]["usage"]["evaluation_steps"] == 250000,
            "resource_no_promotion", "partial search cannot claim exhaustion")
    empty = {"domain": "finite_integer_box", "coefficient_field": "Q", "variables": [], "bounds": {},
             "constraints": [], "assertion": {"relation": "eq", "left": lit(0), "right": lit(1)}}
    got = call(bridge, "finite_box_search", empty)
    require(got["assessment"] == "counterexample_found" and got["receipt"]["result"]["assignment"] == {}
            and got["receipt"]["progress"]["visited_count"] == 1, "boundary_semantics", "empty Cartesian product")
    fake = polynomial_request(binary("multiply", var(), var()), var())
    got = call(bridge, "polynomial_identity", fake)
    require(got["assessment"] == "formal_polynomial_identity_not_equal", "domain_rejection", "Q[x] is not Q[x]/(x²-x)")
    fake["relations"] = ["x*x=x"]
    require(call(bridge, "polynomial_identity", fake)["assessment"] == "tool_error", "domain_rejection", "quotient injection")


def main() -> int:
    manifest = json.loads((ROOT / "docs/BASE-V04-SOURCE-MANIFEST.json").read_text())["files"]
    # v0.6 deliberately extends only the CLI dispatcher. Its new commands have
    # dedicated integration tests; all 15 mathematical/acceptance backend files
    # from v0.4 remain pinned byte-for-byte. Do not exempt any other backend.
    frozen = {p: h for p, h in manifest.items()
              if p.startswith(("foundation_math/", "bounded_counterexample/"))
              and p != "foundation_math/cli.py"}
    for path, digest in frozen.items():
        require(sha256((ROOT / path).read_bytes()).hexdigest() == digest, "frozen_backends", path)
    audit_wire()
    bridge = server.Bridge()
    bridge.handle(rpc("initialize", {"protocolVersion": server.PROTOCOL}))
    audit_math(bridge)
    files = ["foundation_math_bridge/__init__.py", "foundation_math_bridge/__main__.py",
             "foundation_math_bridge/schemas.py", "foundation_math_bridge/server.py", "tools/audit_agent_bridge.py"]
    report = {"status": "passed", "audit": "independent deterministic bridge audit", "seed": 20261024,
              "python_version": sys.version.split()[0], "optimization": sys.flags.optimize,
              "checks": CHECKS, "total_checks": sum(CHECKS.values()), "frozen_backend_files": len(frozen),
              "intentional_cli_extension": "foundation_math/cli.py; covered by matrix CLI integration tests",
              "source_sha256": {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in files},
              "scope": "Independent exact scalar, dense univariate polynomial, and finite-box oracles; hostile protocol frames and stdio. Not a formal proof, OS isolation test, or independent proof-kernel check."}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
