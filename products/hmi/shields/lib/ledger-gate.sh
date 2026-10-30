# shellcheck shell=bash
# DECISION-004 ledger hooks for shields-up.sh / all-clear.sh (sourced; expects cwd = products/hmi/shields and say()).
# E-stop asymmetry: shields-up only ever *writes* a local signed intent and never blocks. All-clear needs a
# quorum-witnessed, unused intent when LEDGER_ENFORCE=1 and is refused with 77 before any change; default is log only.
# Env: LEDGER_LOG LEDGER_ORIGIN LEDGER_ROSTER LEDGER_KEY LEDGER_WRITER [LEDGER_INTENT] [LEDGER_WITNESSES="url url"] [LEDGER_PY]
LPY=${LEDGER_PY:-../ledger/ledger.py}
ledger_configured(){ [ -n "${LEDGER_LOG:-}" ] && [ -n "${LEDGER_ORIGIN:-}" ] && [ -n "${LEDGER_ROSTER:-}" ] && [ -n "${LEDGER_KEY:-}" ] && [ -n "${LEDGER_WRITER:-}" ]; }
lpy(){ local op=$1; shift; python3 "$LPY" "$op" --log "$LEDGER_LOG" --origin "$LEDGER_ORIGIN" --roster "$LEDGER_ROSTER" "$@"; }
# shields-up: record {"op":"shields-up",...} as a local signed intent, then claim it. Any failure is a warning only.
ledger_shields_up(){ # $1 level  $2 decision id  $3 dry(0|1)
  ledger_configured || { say "ledger: not configured (log-only); shields-up proceeds"; return 0; }
  local act h; act=$(python3 -c 'import json,sys; print(json.dumps({"op":"shields-up","level":int(sys.argv[1]),"decision":sys.argv[2],"dry_run":sys.argv[3]=="1"},sort_keys=True))' "$1" "$2" "$3" 2>/dev/null)
  h=$(lpy intent --key "$LEDGER_KEY" --writer "$LEDGER_WRITER" --action "$act" 2>/dev/null) \
    || { say "ledger: WARN could not write shields-up intent (never blocks an e-stop)"; return 0; }
  if [ "$3" = 1 ]; then say "ledger: shields-up intent ${h:0:12} (dry_run, not claimed)"; return 0; fi
  lpy gate --claim --key "$LEDGER_KEY" --writer "$LEDGER_WRITER" --intent "$h" --action "$act" >/dev/null 2>&1 \
    && say "ledger: shields-up intent ${h:0:12} claimed" || say "ledger: WARN shields-up intent ${h:0:12} not claimed (proceeding)"
  return 0
}
# all-clear: returns 77 when enforcing and the quorum gate fails. Dry-run gates read-only (nothing consumed).
ledger_all_clear(){ # $1 dry(0|1)
  local dry=$1 act='{"op":"all-clear","scope":["box","host-a"]}' r w
  if [ "${LEDGER_ENFORCE:-0}" != 1 ]; then
    if ledger_configured && [ -n "${LEDGER_INTENT:-}" ]; then
      r=$(lpy gate --intent "$LEDGER_INTENT" --action "$act" 2>&1 >/dev/null) \
        && say "ledger: log-only, all-clear would be allowed" || say "ledger: log-only, all-clear would be DENIED ($(printf '%s\n' "$r" | tail -1))"
    else say "ledger: not configured or no LEDGER_INTENT (log-only; enforcement would deny)"; fi
    return 0
  fi
  ledger_configured && [ -n "${LEDGER_INTENT:-}" ] || { say "ledger: DENIED all-clear (enforcing; LEDGER_* or LEDGER_INTENT missing)"; return 77; }
  if [ -n "${LEDGER_WITNESSES:-}" ]; then
    set -- ; for w in $LEDGER_WITNESSES; do set -- "$@" --witness "$w"; done
    lpy reconcile "$@" >/dev/null 2>&1 || say "ledger: reconcile below quorum (witnesses unreachable?)"
  fi
  if [ "$dry" = 1 ]; then r=$(lpy gate --intent "$LEDGER_INTENT" --action "$act" 2>&1 >/dev/null)
  else r=$(lpy gate --claim --key "$LEDGER_KEY" --writer "$LEDGER_WRITER" --intent "$LEDGER_INTENT" --action "$act" 2>&1 >/dev/null); fi \
    || { say "ledger: DENIED all-clear ($(printf '%s\n' "$r" | tail -1)). At L2 the box cannot reach witnesses: use the board all-clear, the console, or the rollback timer"; return 77; }
  say "ledger: all-clear intent ${LEDGER_INTENT:0:12} $([ "$dry" = 1 ] && echo 'passes the gate (dry-run, not claimed)' || echo claimed)"
}
