"""Claude Code PreToolUse hook: apply one agent's AOR effects to its built-in tools, outside MCP.

    python3 -I -B tools/agent_guard.py --aor SLUG [--root DIR] < hook-input.json

Reads the hook input (tool_name, tool_input, cwd) on stdin and aors/fleet.json under the project root
($CLAUDE_PROJECT_DIR, or --root). Prints a PreToolUse decision: deny or ask, with the reason, or nothing when the
normal permission flow should decide. It fails closed: any error denies. Standard library only, so it runs under
python3 -I without the repository's dependencies. See docs/guides/explanation/starter-agents.md.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

READ_TOOLS = ("Read", "Grep", "Glob", "WebFetch", "WebSearch")
WRITE_TOOLS = ("Edit", "Write", "NotebookEdit")
PROTECTED = ("aors", "agents", ".claude", ".mcp.json", ".git", "contracts/agent.schema.json",
             "contracts/agent-org.schema.json", "tools/agent_guard.py", "tools/agent_profiles.py")
GATED_COMMANDS = (
    ("post", re.compile(r"\bgit\s+push\b")),
    ("post", re.compile(r"\bgh\s+(pr|issue|release|gist)\s+(create|comment|merge|edit|close|reopen|review)\b")),
    ("post", re.compile(r"\bgh\s+api\b.*(-X|--method)\s*(POST|PUT|PATCH|DELETE)\b")),
    ("send", re.compile(r"(^|[\s;&|(])(sendmail|mail|mailx|mutt)\s")),
    ("send", re.compile(r"\bcurl\b.*\s(-d|--data\S*|-F|--form|-T|--upload-file|-X\s*(POST|PUT|PATCH|DELETE))\b")),
    ("delete", re.compile(r"(^|[\s;&|(])rm\s")),
    ("delete", re.compile(r"\bgit\s+(branch\s+-D|clean\s+-\S*f|reset\s+--hard|push\s+\S*\s*--delete)\b")),
    ("delete", re.compile(r"\bgh\s+(repo|release)\s+delete\b")),
)


def decision(kind, reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": kind,
                                   "permissionDecisionReason": reason}}


def _under(rel, prefix):
    rel, prefix = rel.strip("/"), prefix.strip("/")
    return not prefix or rel == prefix or rel.startswith(prefix + "/")


def write_decision(rel, slug, bot, bots):
    own_memory = (f".claude/agent-memory/{slug}", f".claude/agent-memory-local/{slug}")
    if any(_under(rel, m) for m in own_memory):
        return None
    if any(_under(rel, p) for p in PROTECTED):
        return decision("deny", f"{rel} is authority or agent configuration; only the owner changes it")
    klass = bot["effects"]["write_slice"]
    if klass != "allow":
        return decision(klass, f"Writing files is '{klass}' for {slug}")
    for slice_ in bot["slices"]:
        if slice_.strip("/") and _under(rel, slice_):
            return None
    if any(s.strip("/") == "" for s in bot["slices"]):
        for other in bots:
            if other["slug"] != slug and any(s.strip("/") and _under(rel, s) for s in other["slices"]):
                return decision("deny", f"{rel} belongs to {other['slug']}; one writer per path")
        return None
    return decision("deny", f"{rel} is outside {slug}'s slices: {', '.join(bot['slices']) or 'none'}")


def bash_decision(command, slug, bot):
    klass = bot["effects"]["execute"]
    if klass != "allow":
        return decision(klass, f"Running commands is '{klass}' for {slug}")
    for effect, pattern in GATED_COMMANDS:
        if pattern.search(command):
            gated = bot["effects"][effect]
            if gated != "allow":
                return decision(gated, f"This command is a '{effect}' effect, which is '{gated}' for {slug}; "
                                       "it needs the owner's approval")
    return None


def evaluate(event, slug, root):
    bots = json.loads((root / "aors/fleet.json").read_text())["bots"]
    bot = next((b for b in bots if b["slug"] == slug), None)
    if bot is None:
        return decision("deny", f"{slug} is not in aors/fleet.json")
    tool, data = event.get("tool_name", ""), event.get("tool_input") or {}
    if tool in READ_TOOLS:
        klass = bot["effects"]["read"]
        return None if klass == "allow" else decision(klass, f"Reading is '{klass}' for {slug}")
    if tool in WRITE_TOOLS:
        raw = data.get("file_path") or data.get("notebook_path")
        if not raw:
            return decision("deny", "No file path in the tool input")
        path = Path(raw)
        if not path.is_absolute():
            path = Path(event.get("cwd") or root) / path
        resolved, base = path.resolve(), root.resolve()
        if not resolved.is_relative_to(base):
            return decision("deny", f"{raw} is outside the project")
        return write_decision(resolved.relative_to(base).as_posix(), slug, bot, bots)
    if tool == "Bash":
        return bash_decision(str(data.get("command", "")), slug, bot)
    return None


def main(argv=None, stdin=sys.stdin, stdout=sys.stdout):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--aor", required=True)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args(argv)
    try:
        root = args.root or Path(os.environ["CLAUDE_PROJECT_DIR"])
        result = evaluate(json.loads(stdin.read()), args.aor, root)
    except Exception as error:
        result = decision("deny", f"agent_guard failed closed: {type(error).__name__}")
    if result is not None:
        stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
