"""Claude Code PreToolUse hook: apply one agent's AOR effects to its built-in tools, outside MCP.

    python3 -I -B tools/agent_guard.py --aor SLUG [--root DIR] < hook-input.json

Reads the hook input (tool_name, tool_input, cwd) on stdin and aors/fleet.json under the project root
($CLAUDE_PROJECT_DIR, or --root). Prints a PreToolUse decision: deny or ask, with the reason, or nothing when the
normal permission flow should decide. It fails closed: any error denies. Standard library only, so it runs under
python3 -I without the repository's dependencies. See docs/guides/explanation/starter-agents.md.
"""
import argparse
import itertools
import json
import os
import re
import shlex
import sys
from pathlib import Path

READ_TOOLS = ("Read", "Grep", "Glob", "WebFetch", "WebSearch")
WRITE_TOOLS = ("Edit", "Write", "NotebookEdit")
PROTECTED = ("aors", "agents", ".claude", ".mcp.json", ".git", "contracts/agent.schema.json",
             "contracts/agent-org.schema.json", "tools/agent_guard.py", "tools/agent_profiles.py")
SEPARATORS = {";", "&&", "||", "|", "|&", "&", ";;", "\n"}
WRITE_REDIRECTS = {">", ">>", ">|", "&>", "&>>", "<>", ">&"}
OTHER_REDIRECTS = {"<", "<<", "<<-", "<<<", "<&"}
KEYWORDS = {"if", "then", "else", "elif", "fi", "do", "done", "while", "until", "!", "{", "}", "time", "function"}
WRAPPERS = {"sudo", "env", "command", "builtin", "nice", "nohup", "timeout", "stdbuf", "exec", "caffeinate", "doas"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish", "csh", "tcsh"}
INLINE_CODE = {"python": "c", "node": "ep", "bun": "ep", "ruby": "e", "perl": "eE", "php": "r", "lua": "e",
               "osascript": "e", "rscript": "e", "pwsh": "c", "deno": ""}
LONG_INLINE = {"--eval", "--print", "-command", "--command"}
SELF_CONTAINED = {"--test", "--run", "--version", "-v", "-V", "--help", "-h"}  # runs no code from its input
DELETES = {"rm", "rmdir", "unlink", "shred", "srm", "trash", "truncate"}
SENDS = {"sendmail", "mail", "mailx", "mutt", "msmtp", "nc", "ncat", "netcat", "ssh", "scp", "sftp", "telnet", "ftp"}
WRITERS = DELETES | {"cp", "mv", "ln", "install", "tee", "touch", "mkdir", "chmod", "chown", "chgrp", "dd", "patch",
                     "rsync", "tar", "unzip", "ditto"}
GIT_WRITERS = {"checkout", "restore", "apply", "am", "mv", "rm", "add", "reset", "stash", "switch"}
GH_DELETES = {"delete"}
GH_POSTS = {"create", "comment", "merge", "edit", "close", "reopen", "review", "ready", "lock", "unlock", "set", "run",
            "upload", "fork", "rename", "archive", "unarchive", "transfer", "sync", "enable", "disable", "add",
            "remove", "cancel", "rerun", "pin", "unpin", "develop", "install", "upgrade"}
UNRESOLVED = set("$*?[{`")
MAX_DEPTH = 8


class Command:
    """What one Bash command line may do, worked out from its words instead of matched against patterns.

    A denylist of patterns misses `/bin/rm`, `find -delete` and `python -c`, so this parses the line into simple commands
    (through pipes, lists, subshells, command substitution, `sh -c`, `eval`, `xargs` and `find -exec`), names each
    program by its basename, and classifies it. Anything it cannot read is 'unknown', which is never 'allow' for a bot
    whose send, post or delete is gated. Paths a command writes are resolved against the tracked working directory and
    checked against the protected authority paths. It reads the command; it is not a sandbox, so a script or build the
    bot runs can still do anything its process can. The OS sandbox and the MCP server stay the authority.
    """

    def __init__(self, root, cwd, slug):
        self.root, self.slug = root.resolve(), slug
        self.effects, self.protected, self.unresolved_write = {}, [], []
        self.cwd = [Path(cwd).resolve() if cwd else self.root]

    def note(self, effect, why):
        self.effects.setdefault(effect, why)

    def read(self, text, depth=0):
        if depth > MAX_DEPTH:
            return self.note("unknown", "nested too deeply to read")
        text = _strip_heredocs(text, self, depth)
        split = _substitutions(text)
        if split is None:
            return self.note("unknown", "unbalanced quoting or substitution")
        outer, inners = split
        for inner in inners:
            self.read(inner, depth + 1)
        try:
            lexer = shlex.shlex(outer.replace("\n", " ; "), posix=True, punctuation_chars=True)
            lexer.whitespace_split = True
            tokens = list(lexer)
        except ValueError:
            return self.note("unknown", "unbalanced quoting")
        words = []
        for token in tokens + [";"]:
            if token in SEPARATORS or token in ("(", ")"):
                self.simple(words, depth)
                words = []
                if token == "(":
                    self.cwd.append(self.cwd[-1])
                elif token == ")" and len(self.cwd) > 1:
                    self.cwd.pop()
            else:
                words.append(token)

    def simple(self, words, depth):
        args, targets, i = [], [], 0
        while i < len(words):
            if words[i] in WRITE_REDIRECTS or words[i] in OTHER_REDIRECTS:
                if i + 1 < len(words) and words[i] in WRITE_REDIRECTS and not re.fullmatch(r"\d+|-", words[i + 1]):
                    targets.append(words[i + 1])
                i += 2
                continue
            args.append(words[i])
            i += 1
        for target in targets:
            self.written(target)
        while args and (args[0] in KEYWORDS or re.match(r"[A-Za-z_]\w*=", args[0])):
            args = args[1:]
        if args:
            self.program(args, depth)

    def program(self, args, depth):
        while args and _base(args[0]) in WRAPPERS:
            wrapper, args = _base(args[0]), args[1:]
            while args and (args[0].startswith("-") or (wrapper == "env" and "=" in args[0])):
                args = args[2:] if wrapper in ("sudo", "doas") and args[0] in ("-u", "-g") else args[1:]
            if wrapper == "timeout" and args:
                args = args[1:]
        if not args:
            return
        name, rest = _base(args[0]), args[1:]
        if set(args[0]) & UNRESOLVED:
            return self.note("unknown", f"the program name '{args[0]}' is computed at run time")
        if name in ("cd", "pushd"):
            return self.change_directory(rest)
        if name == "eval":
            return self.read(" ".join(rest), depth + 1)
        if name == "xargs":
            while rest and rest[0].startswith("-"):
                rest = rest[2:] if rest[0] in ("-I", "-n", "-P", "-L", "-d", "-E", "-s") else rest[1:]
            if rest and _base(rest[0]) in WRITERS:
                self.unresolved_write.append(f"xargs {rest[0]} writes paths read from its input")
            return self.program(rest, depth + 1) if rest else None
        if name in SHELLS:
            return self.shell(name, rest, depth)
        interpreter = "python" if re.fullmatch(r"python[\d.]*", name) else name
        if interpreter in INLINE_CODE:
            return self.interpreter(interpreter, rest)
        if name in DELETES:
            self.note("delete", f"{name} deletes files")
        if name in SENDS:
            self.note("send", f"{name} sends data off this machine")
        if name == "find":
            self.find(rest, depth)
        elif name == "git":
            self.git(rest)
        elif name == "gh":
            self.gh(rest)
        elif name == "curl":
            if any(re.match(r"(-d|--data|-F|--form|-T|--upload-file|--json)", a) for a in rest) or \
                    _method(rest, ("-X", "--request")) not in ("GET", "HEAD", None):
                self.note("send", "curl sends data")
        elif name == "wget":
            if any(re.match(r"--(post|body)-(data|file)|--method", a) for a in rest):
                self.note("send", "wget sends data")
        elif name == "rsync":
            if any(re.match(r"rsync://|[^/\s]+:", a) for a in rest if not a.startswith("-")):
                self.note("send", "rsync copies to another machine")
            if any(a.startswith("--delete") or a == "--remove-source-files" for a in rest):
                self.note("delete", "rsync deletes files")
        if name in WRITERS or (name in ("sed", "perl") and any(re.match(r"-[a-zA-Z]*i", a) for a in rest)):
            self.paths(rest)
        elif name == "git" and _git_sub(rest)[0] in GIT_WRITERS:
            self.paths(_git_sub(rest)[1])

    def shell(self, name, rest, depth):
        for i, arg in enumerate(rest):
            if re.fullmatch(r"-[a-zA-Z]*c[a-zA-Z]*", arg):
                return self.read(rest[i + 1], depth + 1) if i + 1 < len(rest) else self.note("unknown", f"{name} -c")
            if arg in ("-s", "-"):
                break
            if not arg.startswith("-"):
                return None  # a script file: project code, like make or a test runner
        self.note("unknown", f"{name} runs commands from its input")

    def interpreter(self, name, rest):
        letters = INLINE_CODE[name]
        if name == "deno" and rest[:1] == ["eval"]:
            return self.note("unknown", "deno eval runs inline code")
        for arg in rest:
            if arg.lower() in LONG_INLINE or arg.split("=")[0] in LONG_INLINE or arg == "-" or \
                    (letters and re.fullmatch(rf"-[a-zA-Z]*[{letters}][a-zA-Z]*", arg)):
                return self.note("unknown", f"{name} runs inline code")
            if arg == "-m" or arg in SELF_CONTAINED or not arg.startswith("-"):
                return None  # a module, a script file or a built-in mode
        self.note("unknown", f"{name} runs code from its input")

    def find(self, rest, depth):
        if "-delete" in rest:
            self.note("delete", "find -delete deletes files")
        for i, arg in enumerate(rest):
            if arg in ("-exec", "-execdir", "-ok", "-okdir"):
                inner = list(itertools.takewhile(lambda a: a not in (";", "+"), rest[i + 1:]))
                if inner:
                    self.program(inner, MAX_DEPTH - 1)

    def git(self, rest):
        sub, args = _git_sub(rest)
        flags = set(args)
        if sub == "push":
            self.note("post", "git push publishes commits")
            if flags & {"--delete", "-d", "--force", "-f", "--mirror", "--prune"} or \
                    any(a.startswith((":", "+", "--force")) for a in args):
                self.note("delete", "git push deletes or overwrites remote history")
        elif (sub == "branch" and flags & {"-D", "-d", "--delete"}) or (sub == "tag" and flags & {"-d", "--delete"}) \
                or (sub == "clean" and any(re.fullmatch(r"-[a-zA-Z]*f[a-zA-Z]*|--force", a) for a in args)) \
                or (sub == "reset" and "--hard" in flags) or sub == "rm" \
                or (sub == "stash" and args[:1] in (["drop"], ["clear"])) \
                or (sub == "worktree" and args[:1] in (["remove"], ["prune"])) \
                or (sub == "checkout" and flags & {"--", ".", "-f", "--force"}) \
                or (sub == "restore" and not (flags & {"--staged", "-S"} and not flags & {"--worktree", "-W"})) \
                or (sub in ("reflog", "update-ref") and flags & {"expire", "delete", "-d"}):
            self.note("delete", f"git {sub} discards work")

    def gh(self, rest):
        words = [a for a in rest if not a.startswith("-")]
        group, verb = (words + ["", ""])[:2]
        if group == "api":
            method = _method(rest, ("-X", "--method"))
            if method is None and any(re.match(r"-f|-F|--field|--raw-field|--input", a) for a in rest):
                method = "POST"
            if method == "DELETE":
                self.note("delete", "gh api DELETE")
            elif method not in (None, "GET", "HEAD"):
                self.note("post", f"gh api {method}")
        elif verb in GH_DELETES:
            self.note("delete", f"gh {group} {verb}")
        elif verb in GH_POSTS:
            self.note("post", f"gh {group} {verb}")

    def change_directory(self, rest):
        target = next((a for a in rest if not a.startswith("-")), str(Path.home()))
        if set(target) & UNRESOLVED or target == "-":
            self.cwd[-1] = None
        elif self.cwd[-1] is not None or Path(target).expanduser().is_absolute():
            self.cwd[-1] = ((self.cwd[-1] or self.root) / Path(target).expanduser()).resolve()

    def paths(self, args):
        for arg in args:
            value = arg.split("=", 1)[1] if arg.startswith("--") and "=" in arg else arg
            if value and not value.startswith("-"):
                self.written(value)

    def written(self, raw):
        if set(raw) & UNRESOLVED:
            self.unresolved_write.append(f"'{raw}' is computed at run time")
            return
        path = Path(raw).expanduser()
        if not path.is_absolute():
            if self.cwd[-1] is None:
                self.unresolved_write.append(f"'{raw}' is relative to a directory computed at run time")
                return
            path = self.cwd[-1] / path
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root):
            return
        rel = resolved.relative_to(self.root).as_posix()
        own = (f".claude/agent-memory/{self.slug}", f".claude/agent-memory-local/{self.slug}")
        if any(_under(rel, p) for p in PROTECTED) and not any(_under(rel, m) for m in own):
            self.protected.append(rel)


def _base(word):
    return os.path.basename(word).lower()


def _method(args, flags):
    for i, arg in enumerate(args):
        for flag in flags:
            if arg == flag and i + 1 < len(args):
                return args[i + 1].upper()
            if arg.startswith(flag) and len(arg) > len(flag):
                return arg[len(flag):].lstrip("=").upper()
    return None


def _git_sub(args):
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in ("-C", "-c") else 1
    return (args[i], args[i + 1:]) if i < len(args) else ("", [])


def _substitutions(text):
    """Split out $(...), <(...), >(...) and `...` bodies; each body is read as its own command. None if unbalanced."""
    outer, inners, i, quote = [], [], 0, None
    while i < len(text):
        c = text[i]
        if c == "\\" and quote != "'":
            outer.append(text[i:i + 2])
            i += 2
            continue
        if quote == "'":
            quote = None if c == "'" else quote
            outer.append(c)
            i += 1
            continue
        if c in "'\"" and (quote is None or quote == c):
            quote = None if quote == c else c
            outer.append(c)
            i += 1
            continue
        if c == "`":
            end = text.find("`", i + 1)
            if end < 0:
                return None
            inners.append(text[i + 1:end])
            outer.append("$__SUB__")
            i = end + 1
            continue
        if c in "$<>" and text[i + 1:i + 2] == "(":
            depth, j, inner_quote = 0, i + 1, None
            while j < len(text):
                d = text[j]
                if inner_quote:
                    inner_quote = None if d == inner_quote else inner_quote
                elif d in "'\"":
                    inner_quote = d
                elif d == "(":
                    depth += 1
                elif d == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if j >= len(text):
                return None
            inners.append(text[i + 2:j])
            outer.append("$__SUB__")
            i = j + 1
            continue
        outer.append(c)
        i += 1
    return None if quote else ("".join(outer), inners)


def _strip_heredocs(text, command, depth):
    """Here-document bodies are data, except that an unquoted delimiter still expands $(...) inside them."""
    lines, out, i = text.split("\n"), [], 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        tags = re.findall(r"<<(-?)\s*(['\"]?)([A-Za-z_][\w.-]*)\2", line)
        i += 1
        for dash, quoted, tag in tags:
            body = []
            while i < len(lines) and (lines[i].lstrip("\t") if dash else lines[i]) != tag:
                body.append(lines[i])
                i += 1
            i += 1
            if not quoted:
                split = _substitutions("\n".join(body).replace("'", " ").replace('"', " "))
                if split is None:
                    command.note("unknown", "unbalanced substitution in a here-document")
                else:
                    for inner in split[1]:
                        command.read(inner, depth + 1)
    return "\n".join(out)

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


STRICTNESS = {"allow": 0, "ask": 1, "deny": 2}


def bash_decision(command, slug, bot, cwd, root):
    klass = bot["effects"]["execute"]
    if klass != "allow":
        return decision(klass, f"Running commands is '{klass}' for {slug}")
    found = Command(root, cwd, slug)
    found.read(command)
    if found.protected:
        return decision("deny", f"{found.protected[0]} is authority or agent configuration; only the owner changes it")
    worst, reason = "allow", ""
    for effect in ("delete", "post", "send"):
        if effect in found.effects and STRICTNESS[bot["effects"][effect]] > STRICTNESS[worst]:
            worst = bot["effects"][effect]
            reason = f"This command is a '{effect}' effect ({found.effects[effect]}), which is '{worst}' for {slug}"
    if "unknown" in found.effects:
        gated = max((bot["effects"][e] for e in ("delete", "post", "send")), key=STRICTNESS.get)
        if STRICTNESS[gated] > STRICTNESS[worst]:
            worst, reason = gated, f"The guard can't tell what this command does ({found.effects['unknown']})"
    if found.unresolved_write and worst == "allow":
        worst, reason = "ask", f"The guard can't check where this command writes ({found.unresolved_write[0]})"
    if worst == "allow":
        return None
    return decision(worst, reason + "; it needs the owner's approval" if worst == "ask" else reason)

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
        return bash_decision(str(data.get("command", "")), slug, bot, event.get("cwd"), root)
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
