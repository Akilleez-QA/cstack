#!/usr/bin/env python3
"""Replay advertised JSON Schema checks using an already installed jsonschema.

This optional audit is not a bridge or test-suite dependency. It never installs
packages or performs network access. Missing jsonschema means unavailable, not
a passing validation. Every fixture is a tiny synthetic explicit matrix.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))

from foundation_math_bridge.schemas import tool_definitions
from foundation_math_bridge.server import Bridge


def invoke(name: str, arguments: dict) -> dict:
    bridge = Bridge()
    response = bridge.dispatch({"jsonrpc": "2.0", "id": 0, "method": "initialize",
                                "params": {"protocolVersion": "foundation-math-jsonrpc/1"}})
    if "error" in response:
        raise RuntimeError("Could not initialize bridge for schema audit")
    response = bridge.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                "params": {"name": name, "arguments": arguments}})
    return response["result"]["structuredContent"]


def main() -> int:
    try:
        from jsonschema import Draft202012Validator
    except ModuleNotFoundError:
        print(json.dumps({"status": "unavailable", "reason": "jsonschema is not installed; no install attempted"}))
        return 2

    checks = 0

    def require(condition: bool, detail: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            raise RuntimeError(detail)

    matrix = {"domain": "Q", "rows": 2, "cols": 2,
              "entries": [[{"num": 1, "den": 2}, 1], [1, 0]]}
    definitions = tool_definitions()
    for tool in definitions:
        for kind in ("inputSchema", "outputSchema"):
            Draft202012Validator.check_schema(tool[kind])
            checks += 1

    produced = invoke("certify_rational_matrix", {"matrix": matrix})
    certificate = produced["receipt"]["result"]["certificate"]
    matrix_tools = {tool["name"]: tool for tool in definitions if tool["name"] in ("certify_rational_matrix", "check_rational_matrix_certificate")}
    for tool in matrix_tools.values():
        arguments = {"matrix": matrix}
        if tool["name"] == "check_rational_matrix_certificate":
            arguments["certificate"] = certificate
        input_validator = Draft202012Validator(tool["inputSchema"])
        output_validator = Draft202012Validator(tool["outputSchema"])
        require(input_validator.is_valid(arguments), "Valid explicit input rejected by advertised schema")
        good = invoke(tool["name"], arguments)
        errors = list(output_validator.iter_errors(good))
        require(not errors, "Actual success receipt disagrees with advertised schema: " + str(errors))
        invalid_fields = [
            ("extra", True), ("matrix", []),
            ("matrix", {"domain": "Q", "rows": True, "cols": 0, "entries": []}),
            ("matrix", {"domain": "Q", "rows": 1, "cols": 1, "entries": [[True]]}),
            ("matrix", {"domain": "Q", "rows": 1, "cols": 1, "entries": [[{"num": 1, "den": 1}]]}),
            ("matrix", {"domain": "Z", "rows": 1, "cols": 1, "entries": [[{"num": 1, "den": 2}]]}),
        ]
        for field, value in invalid_fields:
            bad = deepcopy(arguments)
            bad[field] = value
            require(not input_validator.is_valid(bad), "Structurally invalid matrix input accepted")

        bad = deepcopy(arguments)
        bad["matrix"]["rows"] = True
        failure = invoke(tool["name"], bad)
        require(output_validator.is_valid(failure), "Actual error receipt disagrees with advertised schema")
        for key, value in (("formal_proof", True), ("runtime_goal_acceptance", True),
                           ("assessment", "counterexample_found"), ("extra", 1)):
            bad = deepcopy(good)
            bad[key] = value
            require(not output_validator.is_valid(bad), "Invalid or promoted structuredContent accepted")
        for key, value in (("computational_field", "Z"), ("scope", "all_matrices"),
                           ("formal_proof", True), ("extra", 1)):
            bad = deepcopy(good)
            bad["receipt"][key] = value
            require(not output_validator.is_valid(bad), "Invalid or promoted source receipt accepted")
        bad = deepcopy(failure)
        bad["receipt"]["result"] = {"accepted": True}
        require(not output_validator.is_valid(bad), "Error receipt containing acceptance accepted")
        bad = deepcopy(good)
        bad["assessment"] = "tool_error"
        require(not output_validator.is_valid(bad), "Assessment inconsistent with receipt accepted")
        bad = deepcopy(good)
        bad["receipt"]["result"]["verification"]["computational_field"] = "Z"
        require(not output_validator.is_valid(bad), "Non-Q verification accepted")

    for rows, cols in ((0, 0), (0, 3), (3, 0)):
        empty = {"domain": "Z", "rows": rows, "cols": cols, "entries": [[] for _ in range(rows)]}
        content = invoke("certify_rational_matrix", {"matrix": empty})
        require(Draft202012Validator(matrix_tools["certify_rational_matrix"]["outputSchema"]).is_valid(content), "Empty-shape output rejected")

    names = ("foundation_math_bridge/__init__.py", "foundation_math_bridge/schemas.py",
             "foundation_math_bridge/server.py", "foundation_math/linear_algebra.py",
             "tools/validate_matrix_bridge_schemas.py")
    print(json.dumps({
        "status": "passed", "total_checks": checks,
        "schema_draft": "https://json-schema.org/draft/2020-12/schema",
        "jsonschema_version": version("jsonschema"), "optimization": sys.flags.optimize,
        "python_version": sys.version.split()[0],
        "scope": "Advertised structural schemas, actual synthetic success/error receipts and non-promotion; not mathematical proof or exhaustive schema testing.",
        "dependency_note": "Used already installed jsonschema; no runtime/test dependency or install added.",
        "source_sha256": {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in names},
    }, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
