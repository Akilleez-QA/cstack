"""Replay the fixed bridge transcript and emit bounded validation evidence.

This developer tool launches only the fixed local bridge, never a supplied
command. It does not form part of the bridge's exposed tool surface.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def validate() -> dict:
    requests = (ROOT / "examples/bridge/session-requests.jsonl").read_bytes()
    expected = [json.loads(line) for line in requests.splitlines()]
    runs = []
    for optimized in (False, True):
        command = [sys.executable, "-B"] + (["-O"] if optimized else []) + ["-m", "foundation_math_bridge"]
        process = subprocess.run(command, input=requests, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, cwd=ROOT, timeout=15)
        if process.returncode != 0 or process.stderr:
            raise RuntimeError("bridge transcript process failed")
        replies = [json.loads(line) for line in process.stdout.splitlines()]
        if len(replies) != len(expected) or [r["id"] for r in replies] != [r["id"] for r in expected]:
            raise RuntimeError("bridge transcript request/response pairing failed")
        by_id = {reply["id"]: reply for reply in replies}
        if by_id["init"]["result"]["protocolVersion"] != "foundation-math-jsonrpc/1" or by_id["init"]["result"]["mcpCompatible"] is not False:
            raise RuntimeError("protocol identity check failed")
        wanted = {"scalar": "exact_scalar_result", "false-identity": "formal_polynomial_identity_not_equal",
                  "finite-exhaustion": "no_counterexample_in_declared_finite_domain", "search": "counterexample_found",
                  "fresh-check": "witness_valid", "changed-assertion-check": "witness_rejected"}
        for identifier, assessment in wanted.items():
            data = by_id[identifier]["result"]["structuredContent"]
            if data["assessment"] != assessment or data["formal_proof"] is not False or data["runtime_goal_acceptance"] is not False:
                raise RuntimeError("mathematical scope check failed")
        if by_id["unknown-tool"]["error"]["code"] != -32602:
            raise RuntimeError("unknown tool was not rejected")
        runs.append(process.stdout)
    if runs[0] != runs[1]:
        raise RuntimeError("normal and optimized transcript responses differ")
    return {"status": "passed", "scope": "Fixed local stdio integration transcript, not MCP client interoperability or proof correctness",
            "protocol": "foundation-math-jsonrpc/1", "mcp_compatibility_claim": False,
            "runs": ["normal", "optimized"], "request_count": len(expected), "response_count": len(expected),
            "request_sha256": hashlib.sha256(requests).hexdigest(),
            "response_sha256": hashlib.sha256(runs[0]).hexdigest(),
            "normal_optimized_identical": True,
            "responses": [json.loads(line) for line in runs[0].splitlines()]}


def main() -> int:
    try:
        print(json.dumps(validate(), indent=2, sort_keys=True))
        return 0
    except Exception:
        print(json.dumps({"status": "failed", "error": "bridge transcript validation failed; inspect locally"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
