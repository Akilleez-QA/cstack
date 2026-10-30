"""Today's sanctioned code-writing route for code_write_policy: Codex CLI, launched through codex-task.

RuntimeFace data, not logic: swapping the code writer means a new Route here, not a change to the classifier
or to any hook shim. ADR 005 item 11a's code-writing port is expected to supply this route.
"""
import re

from code_write_policy import Route

CODEX_TASK = Route(
    writer="codex",
    launchers=("codex-guard.sh", "codex-task"),
    guard="codex-guard.sh",
    # codex-task fixes Codex's argv; a direct codex-guard.sh launch must not widen the sandbox or approvals.
    widening=re.compile(r"^(--dangerously-|--yolo$|--approve-for-me$|--add-dir|--full-auto$)|danger-full-access"),
    control_dirs=frozenset({".codex"}),  # ~/.codex and <repo>/.codex: Codex config, rules and auth
    control_names=frozenset({"AGENTS.md", "AGENTS.override.md"}),  # AGENTS files steer Codex
    control_extensions=(".rules",),  # Codex execpolicy: an `allow` rule runs a command outside Codex's sandbox
    unrouted="Codex must be launched through codex-task (it runs codex-guard.sh), so shields-up can stop it",
    widened="`{}` would widen Codex's sandbox or approvals",
    substituted="a command substitution resolves to codex; launch it through codex-task",
    remedy=("Run the change through Codex instead: "
            "`codex-task <repo-dir> \"<what to change and how to verify it>\"` "
            "(it calls codex-guard.sh codex exec). "
            "Codex makes the edits and runs the checks; you review its result and open the PR."),
    # Other agent CLIs: a bot under this policy must not write code through any of them (that would route around
    # the shields and the ledger gate). Codex itself is the writer above, never listed here.
    other_agents=frozenset({
        "claude", "claude-code", "hermes", "cursor-agent", "gemini", "aider", "opencode", "goose",
        "amp", "crush", "qwen-code", "qwen", "llm", "ollama", "copilot", "kimi", "droid",
    }),
    agent_runners=frozenset({"npx", "bunx", "uvx", "pipx"}),  # npx/bunx/uvx <pkg>, pipx run <pkg>
    other_agent="an agent CLI cannot write code here; code work must go through the sanctioned route",
    ambiguous=("this command cannot be checked statically (a dynamically built command name, a shell or eval of "
               "something this policy cannot read, or a decoded command), so it is refused"),
)
