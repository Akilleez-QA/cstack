"""Optional development-only JSON Schema checks; never a runtime dependency.

Uses jsonschema if already installed. Does not install anything. The standard-
library bridge and full unittest suite do not require this optional tool.
"""
from __future__ import annotations

from copy import deepcopy
import importlib.metadata
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from foundation_math_bridge.schemas import tool_definitions


def main() -> int:
    try:
        import jsonschema
    except ImportError:
        print(json.dumps({"status": "unavailable", "reason": "Optional development validator jsonschema is not installed; no installation attempted."}))
        return 2
    definitions = {tool["name"]: tool for tool in tool_definitions()}
    checks = 0
    for tool in definitions.values():
        for name in ("inputSchema", "outputSchema"):
            jsonschema.Draft202012Validator.check_schema(tool[name])
            checks += 1
    transcript = json.loads((ROOT / "evidence/bridge-transcript-validation.json").read_text())
    messages = [json.loads(line) for line in (ROOT / "examples/bridge/session-requests.jsonl").read_text().splitlines()]
    by_id = {reply["id"]: reply for reply in transcript["responses"]}
    for message in messages:
        if message["method"] != "tools/call" or message["params"]["name"] not in definitions:
            continue
        definition = definitions[message["params"]["name"]]
        jsonschema.Draft202012Validator(definition["inputSchema"]).validate(message["params"]["arguments"])
        jsonschema.Draft202012Validator(definition["outputSchema"]).validate(by_id[message["id"]]["result"]["structuredContent"])
        checks += 2
    sample = next(message["params"]["arguments"] for message in messages if message["id"] == "false-identity")
    validator = jsonschema.Draft202012Validator(definitions["polynomial_identity"]["inputSchema"])
    for name in ("x\n", "x\r", "x\r\n", "x\u2028", "x!", "1x", "_x", "x" * 33):
        invalid = deepcopy(sample)
        invalid["variables"] = [name]
        invalid["operands"][0]["name"] = name
        if validator.is_valid(invalid):
            raise RuntimeError("Schema accepted an invalid variable identifier")
        checks += 1
    print(json.dumps({"status": "passed", "validator": "jsonschema", "version": importlib.metadata.version("jsonschema"),
                      "checks": checks, "scope": "Optional preinstalled development validator only; bridge runtime and self-contained tests require no external dependencies."},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
