#!/usr/bin/env bash
# Install Codex CLI and the "code goes through Codex" policy on a fleet device (run as root on the Grok VM box;
# the same steps work on host-a). Dry run by default; --apply makes changes. Idempotent.
# Owner: Grok VM maintenance (box installs). Codex sign-in is the owner's: `codex login --device-auth`.
set -euo pipefail
CODEX_VERSION=${CODEX_VERSION:-0.164.0}
here=$(cd "$(dirname "$0")" && pwd)
apply=0; [ "${1:-}" = "--apply" ] && apply=1
run() { if [ $apply = 1 ]; then echo "+ $*"; "$@"; else echo "would: $*"; fi; }
[ "$(id -u)" = 0 ] || { echo "install.sh: run as root (it writes /opt/cstack, /etc/grok and /usr/local/bin)" >&2; exit 77; }

# 1. Codex CLI, pinned.
have=$(codex --version 2>/dev/null | awk '{print $2}' || true)
if [ "$have" != "$CODEX_VERSION" ]; then
  command -v npm >/dev/null || { echo "install.sh: npm not found; install Node.js LTS first" >&2; exit 69; }
  run npm install -g "@openai/codex@$CODEX_VERSION"
else echo "ok: codex $have already installed"; fi

# 2. The hook and the codex-task wrapper, root-owned so bots cannot edit them. The hook is a Grok shim over the
#    classifier and route beside it; install those first, so an upgraded hook never runs without them.
run install -D -o root -g root -m 0644 "$here/code_write_policy.py" /opt/cstack/code_write_policy.py
run install -D -o root -g root -m 0644 "$here/codex_route.py" /opt/cstack/codex_route.py
run install -D -o root -g root -m 0755 "$here/no_direct_code.py" /opt/cstack/no_direct_code.py
run install -D -o root -g root -m 0755 "$here/codex-task" /usr/local/bin/codex-task
# The worker registry: codex-task registers every run with it and refuses without it. Each bot user then enables the
# push timer so host-a sees this box's workers: put WORKERS_PUSH_TO=<rig ssh name> in ~/.config/workers/push.env and
# run `systemctl --user enable --now workers-push.timer` (the box SSHes out to the rig; never the other way).
run install -D -o root -g root -m 0755 "$here/../../../forge/endoforge/tools/throttle/workers" /usr/local/bin/workers
run install -D -o root -g root -m 0644 "$here/workers-push.service" /etc/systemd/user/workers-push.service
run install -D -o root -g root -m 0644 "$here/workers-push.timer" /etc/systemd/user/workers-push.timer

# 3. Grok policy layer. Never overwrite an existing policy silently.
if [ -e /etc/grok/requirements.toml ] && ! cmp -s "$here/requirements.toml" /etc/grok/requirements.toml; then
  echo "install.sh: /etc/grok/requirements.toml exists and differs; merge by hand:" >&2
  diff -u /etc/grok/requirements.toml "$here/requirements.toml" >&2 || true
  exit 75
fi
run install -D -o root -g root -m 0644 "$here/requirements.toml" /etc/grok/requirements.toml

# 4. codex-guard must exist, or codex-task refuses to run. Same fixed path as codex-task (never from the env).
guard=/workspace/ops/shields/lib/codex-guard.sh
[ -x "$guard" ] && echo "ok: codex-guard at $guard" || echo "WARN: codex-guard missing at $guard (deploy products/hmi/shields first)"

# 5. Self-test the hook and the Codex sandbox, then report Codex sign-in.
if [ $apply = 1 ]; then
  echo '{"tool_name":"search_replace","tool_input":{"file_path":"x.py"}}' | /opt/cstack/no_direct_code.py >/dev/null 2>&1 \
    && { echo "FAIL: hook allowed a code edit" >&2; exit 1; } || echo "ok: hook blocks direct code edits"
  # A hook that cannot load its policy blocks everything, so also prove that an allowed call passes.
  echo '{"tool_name":"read_file","tool_input":{"file_path":"x.py"}}' | /opt/cstack/no_direct_code.py >/dev/null 2>&1 \
    && echo "ok: hook loads its policy and allows reads" || { echo "FAIL: hook blocks reads (policy not loaded?)" >&2; exit 1; }
fi
# Codex's Linux sandbox (bubblewrap) needs user namespaces, which containers often lack. Without it every command
# Codex runs fails, so report it here rather than on a bot's first task.
if codex sandbox -- /bin/true >/dev/null 2>&1; then echo "ok: codex sandbox runs (codex sandbox -- /bin/true)"
else echo "WARN: codex sandbox -- /bin/true failed; enable user namespaces before codex-task can do useful work"; fi
if codex login status >/dev/null 2>&1; then echo "ok: codex signed in"
else echo "ACTION (the owner): sign Codex in on this device: codex login --device-auth"; fi
