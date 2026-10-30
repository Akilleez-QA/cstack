#!/usr/bin/env python3
"""Claude Code PreToolUse hook: the same code-write policy as the Grok hook, for a Claude Code bot.

A thin vendor shim (ADR 005 item 11b) over `code_write_policy.py` and `codex_route.py`, which sit next to it.
Not installed by install.sh: wire it into a bot's managed Claude Code settings only when the owner puts a Claude
Code bot under this policy, with `MATCHER` below as the PreToolUse matcher. Never wire it into Claude Code
sessions that are meant to write code themselves.

Input is Claude Code's PreToolUse JSON on stdin (`tool_name`, `tool_input`). To block, it writes the reason on
stderr and exits 2, which Claude Code treats as a blocking error and shows to the model. Anything it cannot
read, including a missing policy file, is blocked.
"""
import json
import os
import sys

EDIT_TOOLS = {"Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path", "NotebookEdit": "notebook_path"}
SHELL_TOOLS = ("Bash",)
MATCHER = "|".join((*EDIT_TOOLS, *SHELL_TOOLS))
BOT = "This bot does not write code directly. "
try:  # -I would not put this file's directory on sys.path
    sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
    from code_write_policy import classify
    from codex_route import CODEX_TASK as ROUTE
    HOW = BOT + ROUTE.remedy
except Exception:  # a missing or broken policy file must block every call, never fail open
    classify = ROUTE = None
    HOW = BOT + "Run the change through `codex-task <repo-dir> \"<task>\"` instead."


def normalize(call):
    """Map a Claude Code PreToolUse call to the normalized call, or None when it is unreadable."""
    tool, args = call.get("tool_name"), call.get("tool_input")
    if type(tool) is not str or type(args) is not dict:
        return None
    if tool in EDIT_TOOLS:
        path = args.get(EDIT_TOOLS[tool])
        return {"kind": "edit", "path": path if type(path) is str else ""}
    if tool in SHELL_TOOLS:
        return {"kind": "shell", "command": args.get("command") or ""}
    return {"kind": "other"}


def decide(call):
    """Return why the call is direct code work, or None when it is allowed."""
    if classify is None:
        return "the code-write policy could not be loaded"
    normal = normalize(call) if type(call) is dict else None
    if normal is None:
        return "unreadable tool call"
    decision = classify(normal, ROUTE)
    return None if decision.allowed else decision.reason


def main():
    try:
        problem = decide(json.loads(sys.stdin.read() or "{}"))
    except ValueError:
        problem = "unreadable tool call"
    if problem is None:
        return 0
    print(f"Blocked: {problem}. {HOW}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
