"""Code-write policy: decide whether one normalized tool call is direct code work (ADR 005 item 11b).

Pure and vendor-neutral. No stdin, stdout or environment, and no hook vendor or code-writing runtime is
named here (a test enforces that). A per-vendor hook shim maps its vendor's JSON to a normalized call:

    {"kind": "edit", "path": "..."}  |  {"kind": "shell", "command": "..."}  |  {"kind": "other"}

and `classify(call, route)` returns a `Decision`. The `Route` says which writer is sanctioned and how it must
be launched; the shims pass today's route from the sibling route module. This is a guard rail, not a
sandbox: a determined shell command can still smuggle a write, so the hard boundary stays on the receiving
side.
"""
import os
import re
import shlex
from typing import Mapping, NamedTuple

CODE_EXTENSIONS = (
    ".py", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".sh", ".bash", ".zsh", ".go", ".rs", ".c",
    ".h", ".cc", ".cpp", ".hpp", ".java", ".kt", ".swift", ".rb", ".php", ".lua", ".sql", ".css", ".scss",
    ".html", ".vue", ".svelte", ".toml", ".yaml", ".yml", ".json", ".gradle", ".cs", ".dart", ".ex", ".exs",
)
CODE_NAMES = frozenset({"Makefile", "Dockerfile", "Justfile", "package.json", "pyproject.toml"})
GIT_WRITES = {"commit", "push", "merge", "rebase", "cherry-pick", "revert", "am", "apply", "pull", "tag",
              "stash", "checkout", "switch", "restore", "rm", "mv", "add", "worktree"}
WRITERS = {"tee", "cp", "mv", "install", "truncate", "patch", "dd", "ln", "rsync"}
SHELLS = {"sh", "bash", "dash", "zsh", "ksh", "mksh", "ash", "busybox"}
SEPARATORS = {";", ";;", "&", "&&", "|", "||", "|&", "(", ")", "\n"}
MAX_DEPTH = 4
# Bots keep notebooks here and may commit them; every other repository is code and goes through the writer.
NOTE_REPOS = ("/workspace/ops",)
KINDS = ("edit", "shell", "other")
ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# A command word we cannot resolve statically: built from a variable ($x, ${x}) or a substitution ($( ), ` `).
DYNAMIC = re.compile(r"(^\$)|\$\(|`")
# The only agent-CLI arguments that are clearly read-only; an agent launched with anything else is denied.
READONLY_FLAGS = frozenset({"--version", "-V", "-v", "--help", "-h", "help", "version", "--help-all"})
# Launcher wrappers that pass their tail on to another command; map each to the flags of its own that take a value,
# so the real command word can be found behind them (`env`, `sudo -u bot`, `timeout 5`, `nohup`, ...).
WRAPPERS = {
    "env": ("-u", "-C", "-S"), "nohup": (), "setsid": (), "command": (), "exec": ("-a",),
    "sudo": ("-u", "-g", "-C", "-p", "-r", "-t", "-U", "-R"), "nice": ("-n",),
    "ionice": ("-c", "-n", "-p"), "stdbuf": ("-i", "-o", "-e"), "chrt": (),
    "timeout": ("-s", "-k", "--signal", "--kill-after"), "setarch": (),
}


class Route(NamedTuple):
    """The sanctioned code writer and the only ways to launch it."""
    writer: str                      # the writer's command word; launching it directly is refused
    launchers: tuple                 # command words that may launch the writer
    guard: str                       # the launcher whose argv must not carry `widening` flags
    widening: "re.Pattern"           # flags that would widen the writer's sandbox or approvals
    control_dirs: frozenset          # path parts that hold the writer's config, rules and auth
    control_names: frozenset         # file names that steer the writer
    control_extensions: tuple        # file extensions that steer the writer
    unrouted: str                    # reason: the writer was launched another way
    widened: str                     # reason, formatted with the flag: a guard launch widens the writer
    substituted: str                 # reason: a command substitution resolves to the writer
    remedy: str                      # what to do instead; shims append it to the reason they show
    other_agents: frozenset          # other agent-CLI command words that must not write code themselves
    agent_runners: frozenset         # package runners (npx-style) that could fetch and run an agent CLI
    other_agent: str                 # reason: an agent CLI other than the writer was launched
    ambiguous: str                   # reason: the command cannot be resolved statically, so it fails closed


class Decision(NamedTuple):
    verdict: str                     # "allow" or "deny"
    reason: str                      # why; for "deny" the problem, without the remedy

    @property
    def allowed(self):
        return self.verdict == "allow"


ALLOW = Decision("allow", "not direct code work")


def classify(call: Mapping, route: Route) -> Decision:
    """Return allow or deny for one normalized tool call. Anything malformed is denied (fail closed)."""
    if not isinstance(call, Mapping) or call.get("kind") not in KINDS:
        return Decision("deny", "unreadable tool call")
    if call["kind"] == "edit":
        path = call.get("path") or ""
        if type(path) is not str:
            return Decision("deny", "unreadable tool call")
        if not path or is_code_path(path, route):
            return Decision("deny", f"direct edit of the code file {path}")
        return ALLOW
    if call["kind"] == "shell":
        command = call.get("command") or ""
        if type(command) is not str:
            return Decision("deny", "unreadable tool call")
        problem = bash_problem(command, route)
        return Decision("deny", problem) if problem else ALLOW
    return ALLOW


def base(word):
    return word.rstrip("/").rsplit("/", 1)[-1]


def is_code_path(path, route):
    parts = [p for p in path.split("/") if p]
    name = parts[-1] if parts else ""
    return (name in CODE_NAMES or name in route.control_names
            or any(name.endswith(ext) for ext in CODE_EXTENSIONS + route.control_extensions)
            or any(p in route.control_dirs for p in parts))


def peel_wrappers(words, route):
    """Skip launcher wrappers (and the writer's guard) and return the words of the real command.

    Returns None when the line only looks a command up (`command -v NAME`) rather than running it.
    """
    i = 0
    while i < len(words):
        name = base(words[i])
        if name == route.guard:  # the guard launches the writer only; whatever follows is the real command
            i += 1
            continue
        if name not in WRAPPERS:
            break
        value_flags = WRAPPERS[name]
        i += 1
        while i < len(words) and (words[i].startswith("-") or (name == "env" and ASSIGN.match(words[i]))):
            if name in ("command", "exec") and words[i] in ("-v", "-V"):
                return None  # `command -v NAME` prints a path; it does not launch NAME
            if words[i] in value_flags:
                i += 1
            i += 1
        if name == "timeout" and i < len(words) and not words[i].startswith("-"):
            i += 1  # the DURATION operand
        if name == "setarch" and i < len(words):
            i += 1  # the architecture operand
    return words[i:]


def is_dynamic(word):
    """True when a command word is built from a variable or a substitution, so it cannot be resolved here."""
    return bool(DYNAMIC.search(word))


def agent_short_name(package):
    """The bare agent name inside a runner's package argument (`@scope/some-cli@1.2` -> `some-cli`)."""
    return base(package).split("@")[0]


def runner_problem(runner, args, route):
    """Return why a package runner (`npx`/`uvx`/`pipx run` ...) launches an agent CLI, or None."""
    rest = list(args)
    if runner == "pipx":
        if not rest or rest[0] != "run":  # `pipx install`/`pipx list` are not a run
            return None
        rest = rest[1:]
    package = next((a for a in rest if not a.startswith("-")), None)
    if package is None:
        return None
    if is_dynamic(package):
        return route.ambiguous
    if agent_short_name(package) in route.other_agents:
        return route.other_agent
    return None


def agent_problem(words, route):
    """Return why this simple command launches an agent CLI, or is too dynamic to resolve, or None."""
    rest = peel_wrappers(words, route)
    if not rest:  # empty, or a harmless `command -v` lookup
        return None
    command_word = rest[0]
    name = base(command_word)
    if is_dynamic(command_word):
        return route.ambiguous
    if name in route.agent_runners:
        return runner_problem(name, rest[1:], route)
    if name in route.other_agents and name != route.writer:
        agent_args = rest[1:]
        if agent_args and all(a in READONLY_FLAGS for a in agent_args):
            return None  # `<agent> --version` / `<agent> --help`: a clearly read-only invocation stays allowed
        return route.other_agent
    if name in SHELLS and not any(re.match(r"^-[a-zA-Z]*c", a) for a in rest[1:]):
        return route.ambiguous  # a bare shell runs a script or stdin we cannot read: it could launch an agent CLI
    return None


def substitutions(command):
    """Yield the inner text of every $(...), `...`, <(...) and >(...). Raises ValueError when unbalanced."""
    i = 0
    while i < len(command):
        if command[i] == "\\":
            i += 2
            continue
        if command[i] == "`":
            end = command.find("`", i + 1)
            if end < 0:
                raise ValueError("unbalanced backtick")
            yield command[i + 1:end]
            i = end + 1
            continue
        if command[i] in "$<>" and command[i + 1:i + 2] == "(":
            depth, j = 1, i + 2
            while j < len(command) and depth:
                depth += {"(": 1, ")": -1}.get(command[j], 0)
                j += 1
            if depth:
                raise ValueError("unbalanced command substitution")
            yield command[i + 2:j - 1]
            i = j
            continue
        i += 1


def simple_commands(command):
    """Split a shell line into simple commands (word lists) at ; & && | || ( ) and newlines."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = "#"
    current = []
    for token in lexer:
        if token in SEPARATORS:
            if current:
                yield current
            current = []
        else:
            current.append(token)
    if current:
        yield current


def git_problem(words, assignments):
    j, target, notes_ok = 1, "", not any(a.split("=", 1)[0].startswith("GIT_") for a in assignments)
    while j < len(words) and words[j].startswith("-"):  # git's own options, some with a value
        if words[j].startswith(("--git-dir", "--work-tree")):
            notes_ok = False  # the repository is chosen by this option, not by -C
        if words[j] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") and j + 1 < len(words):
            if words[j] == "-C":
                target = os.path.join(target, words[j + 1])  # repeated -C options accumulate, as in git
            j += 1
        j += 1
    sub = words[j] if j < len(words) else ""
    real = os.path.realpath(target) if target.startswith("/") else ""
    roots = [os.path.realpath(r) for r in NOTE_REPOS]  # realpath = normpath plus symlinks, on both sides
    notes = notes_ok and bool(real) and any(real == r or real.startswith(r + "/") for r in roots)
    rest = words[j + 1:]
    read_only = ("--dry-run" in rest or (sub == "stash" and "list" in rest)
                 or (sub == "apply" and "--apply" not in rest
                     and any(w in ("--check", "--stat", "--numstat", "--summary") for w in rest)))
    if sub in GIT_WRITES and not notes and not read_only:
        return f"`git {sub}` changes a repository"
    return None


def command_problem(words, depth, route):
    assignments = []
    while words and ASSIGN.match(words[0]):
        assignments.append(words.pop(0))
    if not words:
        return None
    agent = agent_problem(words, route)  # an agent CLI launched any way but the sanctioned route, or too dynamic
    if agent:
        return agent
    launcher = base(words[0]) in route.launchers
    for i, word in enumerate(words):
        name = base(word)
        if name == route.writer and not launcher:
            return route.unrouted
        if name == "base64" and any(a in ("-d", "-D", "--decode") for a in words[i + 1:]):
            return route.ambiguous  # a decoded command cannot be read here, so it fails closed
        if base(words[0]) == route.guard and route.widening.search(word):  # launchers pass the task after --
            return route.widened.format(word)
        if name == "git" and i + 1 < len(words):
            problem = git_problem(words[i:], assignments if i == 0 else [])
            if problem:
                return problem
        if name in SHELLS or name == "eval":
            if name == "eval":
                inner = " ".join(words[i + 1:])
            else:
                flag = next((k for k in range(i + 1, len(words))
                             if re.match(r"^-[a-zA-Z]*c[a-zA-Z]*$", words[k])), None)
                inner = next((w for w in words[flag + 1:] if not w.startswith("-")), "") if flag else None
            if inner is not None:
                problem = bash_problem(inner, route, depth + 1)
                if problem:
                    return f"{problem} (inside `{name}`)"
        if name in ("sed", "perl") and any(w == "-i" or w.startswith("-i") for w in words[i + 1:i + 4]):
            if any(is_code_path(w, route) for w in words[i + 1:]):
                return f"in-place `{name} -i` edit of a code file"
        if name in WRITERS and any(is_code_path(w, route) for w in words[i + 1:] if not w.startswith("-")):
            return f"`{name}` writes a code file"
    return None


def bash_problem(command, route, depth=0):
    """Return why a shell command is direct code work, or None when it is allowed."""
    if depth > MAX_DEPTH:
        return "the command nests shells too deeply to check"
    try:
        for inner in substitutions(command):
            if any(base(w) == route.writer for w in re.split(r"[\s;&|()<>'\"`$]+", inner)):
                return route.substituted
            problem = bash_problem(inner, route, depth + 1)
            if problem:
                return problem
        commands = list(simple_commands(command))
    except ValueError:
        return "the command could not be parsed safely"
    for words in commands:
        problem = command_problem(words, depth, route)
        if problem:
            return problem
    for target in re.findall(r"(?<![0-9&])>>?\s*([^\s;&|]+)", command):
        if is_code_path(target.strip("'\""), route):
            return f"shell redirect writes the code file {target}"
    return None
