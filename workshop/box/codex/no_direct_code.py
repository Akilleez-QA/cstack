#!/usr/bin/env python3
"""Grok PreToolUse hook: Grok bots never write code themselves; code work goes through Codex CLI.

A thin vendor shim (ADR 005 item 11b): it maps Grok's hook JSON to a normalized call, asks the pure
classifier `code_write_policy.py` with the route in `codex_route.py`, and maps the decision back. Both sit
next to it in /opt/cstack. If either cannot be loaded, every call is blocked.

For Grok bots only. Never install it as a Codex hook: Codex reports its own edits as `apply_patch` calls, which
this hook would block, and Codex is the sanctioned code writer.

Installed root-owned at /opt/cstack/no_direct_code.py and wired from /etc/grok/requirements.toml, so bots
cannot disable it (Grok enforces hooks from root-owned policy layers). It reads the tool call as JSON on
stdin. To block, it prints a deny decision on stdout and the reason on stderr, and exits 2. This is a guard
rail, not a sandbox: a determined shell command can still smuggle a write, so the hard boundary stays on the
receiving side (GitHub branch protection, ADR 004 gates).
"""
import json
import os
import sys

EDIT_TOOLS = ("search_replace", "Write", "Edit", "MultiEdit", "write_file", "edit_file")
SHELL_TOOLS = ("bash", "Bash", "run_terminal_cmd", "shell")
BOT = "Grok bots do not write code directly. "
try:  # the classifier and route sit next to this file (/opt/cstack); -I would not put this dir on sys.path
    sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
    from code_write_policy import classify
    from codex_route import CODEX_TASK as ROUTE
    HOW = BOT + ROUTE.remedy
except Exception:  # a missing or broken policy file must block every call, never fail open
    classify = ROUTE = None
    HOW = BOT + "Run the change through `codex-task <repo-dir> \"<task>\"` instead."


def normalize(call):
    """Map a Grok hook call to code_write_policy's normalized call, or None when its arguments are unreadable."""
    tool = call.get("tool_name") or call.get("toolName") or call.get("name") or ""
    args = call.get("tool_input") or call.get("toolInput") or call.get("arguments") or {}
    if type(args) is not dict:
        return None
    if tool in EDIT_TOOLS:
        path = args.get("file_path") or args.get("path") or args.get("target_file") or ""
        return {"kind": "edit", "path": str(path)}
    if tool in SHELL_TOOLS:
        return {"kind": "shell", "command": str(args.get("command") or args.get("cmd") or "")}
    return {"kind": "other"}


def decide(call):
    """Return why the call is direct code work, or None when it is allowed."""
    if classify is None:
        return "the code-write policy could not be loaded"
    normal = normalize(call)
    if normal is None:
        return "unreadable tool arguments"
    decision = classify(normal, ROUTE)
    return None if decision.allowed else decision.reason


def main():
    try:
        call = json.loads(sys.stdin.read() or "{}")
        problem = decide(call) if type(call) is dict else "unreadable tool call"
    except ValueError:
        problem = "unreadable tool call"
    if problem is None:
        return 0
    reason = f"Blocked: {problem}. {HOW}"
    print(json.dumps({"decision": "block", "reason": reason, "hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}))
    print(reason, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
