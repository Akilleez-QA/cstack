#!/usr/bin/env bash
# codex-guard: every Codex CLI worker launch goes through this (or does the same check).
# usage: codex-guard.sh codex exec ...      exits 75 (EX_TEMPFAIL) while shields are up.
# This guard is for codex only. Refuse any other program (exit 76) so it can't be used to launch a different agent
# CLI around the shields and the ledger gate. An empty argv is the pre-flight check (codex-pool's CODEX_POOL_GUARD),
# so it is allowed; a path whose basename is `codex` (e.g. /usr/bin/codex) is allowed. 76 is distinct from the
# shields-up 75 and the ledger-deny 77.
if [ "$#" -gt 0 ] && [ "$(basename -- "$1")" != codex ]; then
  echo "codex-guard: refusing to run '$1': this guard launches codex only. Use codex-task for code work." >&2
  exit 76
fi
for L in /workspace/ops/shields/CODEX_BLOCKED /var/lib/shields/CODEX_BLOCKED; do
  if [ -e "$L" ]; then echo "codex blocked: shields up ($(cat "$L" 2>/dev/null)). Wait for the owner's all clear." >&2; exit 75; fi
done
# Ledger gate (DECISION-004). Action = {"op":"codex","argv":[...]}; it must match a pre-registered, quorum-witnessed intent.
#   LEDGER_ENFORCE=1 : exit 77 unless `ledger.py gate --claim` passes. The claim consumes the intent atomically (single use)
#                      before Codex starts, so two launches can never share one intent.
#   default (off)    : log only. Says what enforcement would do (read-only gate, nothing consumed), then runs anyway.
# Env: LEDGER_INTENT LEDGER_LOG LEDGER_ORIGIN LEDGER_ROSTER LEDGER_KEY LEDGER_WRITER [LEDGER_PY] [LEDGER_GUARD_LOG]
LPY=${LEDGER_PY:-$(cd "$(dirname "$0")/../.." 2>/dev/null && pwd)/ledger/ledger.py}
lnote(){ echo "codex-guard ledger: $*" >&2; [ -n "${LEDGER_GUARD_LOG:-}" ] && echo "$(date '+%F %T %Z') $*" >> "$LEDGER_GUARD_LOG"; return 0; }
ACTION=$(python3 -c 'import json,sys; print(json.dumps({"op":"codex","argv":sys.argv[1:]},sort_keys=True))' "$@" 2>/dev/null)
if [ "${LEDGER_ENFORCE:-0}" = 1 ]; then
  for v in LEDGER_INTENT LEDGER_LOG LEDGER_ORIGIN LEDGER_ROSTER LEDGER_KEY LEDGER_WRITER; do
    [ -n "${!v:-}" ] || { lnote "DENIED: $v not set (enforcing, fail closed)"; exit 77; }
  done
  [ -n "$ACTION" ] || { lnote "DENIED: could not encode argv (fail closed)"; exit 77; }
  R=$(python3 "$LPY" gate --claim --log "$LEDGER_LOG" --origin "$LEDGER_ORIGIN" --roster "$LEDGER_ROSTER" --intent "$LEDGER_INTENT" \
      --key "$LEDGER_KEY" --writer "$LEDGER_WRITER" --action "$ACTION" 2>&1 >/dev/null) \
    || { lnote "DENIED: $(printf '%s\n' "$R" | tail -1)"; exit 77; }
  lnote "allowed: intent ${LEDGER_INTENT:0:12} claimed"
elif [ -n "${LEDGER_INTENT:-}" ] && [ -n "${LEDGER_LOG:-}" ] && [ -n "${LEDGER_ORIGIN:-}" ] && [ -n "${LEDGER_ROSTER:-}" ]; then
  if R=$(python3 "$LPY" gate --log "$LEDGER_LOG" --origin "$LEDGER_ORIGIN" --roster "$LEDGER_ROSTER" --intent "$LEDGER_INTENT" \
         --action "$ACTION" 2>&1 >/dev/null); then lnote "log-only: would allow intent ${LEDGER_INTENT:0:12}"
  else lnote "log-only: would DENY ($(printf '%s\n' "$R" | tail -1))"; fi
else
  lnote "log-only: no intent supplied (would DENY when LEDGER_ENFORCE=1)"
fi
# Worker registry (forge/endoforge/tools/throttle/workers): a launch not already registered (codex-task and codex-pool
# register their own) is registered here under WORKER_BOT, or as `unknown`, so `workers list` shows every Codex worker
# on this host. Visibility only: a missing registry never blocks the launch.
if [ "${WORKERS_REGISTERED:-0}" != 1 ]; then
  for W in "${WORKERS_BIN:-}" /usr/local/bin/workers "$HOME/.local/bin/workers"; do
    [ -n "$W" ] && [ -x "$W" ] && WORKERS_ALLOW_UNREGISTERED=1 exec "$W" run --bot "${WORKER_BOT:-}" -- "$@"
  done
fi
exec "$@"
