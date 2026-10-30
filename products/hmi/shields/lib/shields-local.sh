#!/bin/bash
# shields-local.sh: on-machine shields engine. Installed as /usr/local/sbin/shields on host-a (role=rig);
# run from /workspace/ops/shields/lib on the box (role=box). Same engine the control-board poller calls.
# Usage (root): shields [--dry-run] [--role rig|box] up 1|2 [--rollback-min N] | restore [SNAPDIR] | confirm | status | snapshot
# Level 1 = external lockdown (tailnet peers still talk: box->rig SSH keeps working).
# Level 2 = full isolation (also drops tailnet peer traffic; restore is local: timer, console, or board poller).
# No secrets are read or written here.
set -u
DRY=0; ROLE=""; ROLLMIN=""
args=(); while [ $# -gt 0 ]; do case "$1" in
  --dry-run) DRY=1;; --role) ROLE="$2"; shift;; --rollback-min) ROLLMIN="$2"; shift;; *) args+=("$1");; esac; shift; done
set -- "${args[@]:-}"
CMD="${1:-status}"; LVL="${2:-1}"
if [ -z "$ROLE" ]; then [ -x ~/ts/tailscale ] && ROLE=box || ROLE=rig; fi
if [ "$ROLE" = box ]; then TS="~/ts/tailscale --socket=~/ts/sock"; STATE=/workspace/ops/shields/local-state/box
else TS="tailscale"; STATE=/var/lib/shields; fi
SELF=$(readlink -f "$0")
# Control-board host allowlist (outbound 443 kept open at every level so the board can lift shields).
BOARD_HOST="${SHIELDS_BOARD_HOST:-}"   # deployed board hostname, env only (no default); unset => board IP rule omitted. See control-board/PWA-DESIGN.md
STALE_IPS=""                    # stale nodes (old grok-box, old Windows host-a-1): never allowlisted
run(){ if [ $DRY = 1 ]; then echo "[dry-run $ROLE] $*"; else echo "+ $*"; bash -c "$*"; fi; }
log(){ echo "$(date '+%F %T %Z') [$ROLE] $*"; }
# Codex workers: killed on any shields-up, blocked by a lock file until restore (workers MUST run via lib/codex-guard.sh or check the lock).
if [ "$ROLE" = box ]; then CODEX_LOCK=/workspace/ops/shields/CODEX_BLOCKED; else CODEX_LOCK=/var/lib/shields/CODEX_BLOCKED; fi
CODEX_RE='(^|/)codex(-[a-z-]+)?( |$)|/\.codex/'
codex_procs(){ pgrep -a -f "$CODEX_RE" 2>/dev/null | grep -v -E "shields|pgrep" || true; }
codex_stop(){
  run "echo \"blocked by shields level $1 since \$(date -Is); remove only via 'shields restore'\" > '$CODEX_LOCK'; chmod 644 '$CODEX_LOCK'"
  local n; n=$(codex_procs | wc -l); log "codex processes running: $n"
  [ $DRY = 1 ] && codex_procs | sed 's/^/    would stop: /' | cut -c1-160
  run "for p in \$(pgrep -f '$CODEX_RE' | grep -v -x \$\$); do kill -TERM \$p 2>/dev/null; done; sleep 5; for p in \$(pgrep -f '$CODEX_RE'); do kill -KILL \$p 2>/dev/null; done; true"
}

own_peers(){ # tailnet IPs of the owner's own devices (same user as self), minus stale ones
  $TS status --json 2>/dev/null | python3 -c '
import json,sys
d=json.load(sys.stdin); me=d["Self"]["UserID"]; stale=set(sys.argv[1].split())
ips=[ip for p in list((d.get("Peer") or {}).values())+[d["Self"]] if p.get("UserID")==me and not stale.intersection(p.get("TailscaleIPs",[])) for ip in p.get("TailscaleIPs",[])]
print(" ".join(ips))' "$STALE_IPS"
}
board_ips(){ [ -n "$BOARD_HOST" ] || return 0; getent ahosts "$BOARD_HOST" 2>/dev/null | awk '{print $1}' | sort -u | paste -sd' '; }

snapshot(){
  local d="$STATE/$(date +%Y%m%d-%H%M%S)"; run "mkdir -p '$d' && chmod 700 '$STATE' '$d'"
  run "$TS debug prefs > '$d/ts-prefs.json'"
  run "$TS status --json > '$d/ts-status.json'"
  run "$TS serve status --json > '$d/ts-serve.json' 2>/dev/null || echo '{}' > '$d/ts-serve.json'"
  run "nft list ruleset > '$d/nft-ruleset.txt'"
  [ $ROLE = rig ] && run "ufw status verbose > '$d/ufw-status.txt' 2>&1; systemctl is-active tsexit-assert.timer > '$d/tsexit-timer.txt' 2>&1 || true"
  [ $ROLE = box ] && run "pgrep -f seal-watch.sh >/dev/null && echo running > '$d/seal-watch.txt' || echo stopped > '$d/seal-watch.txt'"
  [ $DRY = 1 ] || codex_procs > "$d/codex-procs.txt"
  run "ln -sfn '$d' '$STATE/latest'"; SNAP="$d"
}

nft_rules(){ # $1 = level. Prints the nft script for table inet shields.
  local L=$1 peers board; peers=$(own_peers); board=$(board_ips)
  local p4 p6; p4=$(echo $peers | tr ' ' '\n' | grep -v ':' | paste -sd,); p6=$(echo $peers | tr ' ' '\n' | grep ':' | paste -sd,)
  local b4; b4=$(echo $board | tr ' ' '\n' | grep -v ':' | paste -sd,)
  echo "table inet shields {"
  echo " chain input { type filter hook input priority -5; policy drop;"
  echo "  iifname \"lo\" accept"
  echo "  ct state established,related accept"
  if [ "$L" = 1 ]; then
    [ -n "$p4" ] && echo "  iifname \"tailscale0\" ip saddr { $p4 } accept"
    [ -n "$p6" ] && echo "  iifname \"tailscale0\" ip6 saddr { $p6 } accept"
  fi
  echo "  udp dport 41641 accept"            # WireGuard direct path (tailscaled itself)
  [ $ROLE = box ] && echo "  ip saddr 172.30.0.1 accept"   # Grok Bot platform gateway -> box services
  echo "  meta l4proto { icmp, ipv6-icmp } accept"
  echo " }"
  echo " chain forward { type filter hook forward priority -5; policy drop; }"   # no exit-node / subnet forwarding
  echo " chain output { type filter hook output priority -5; policy drop;"
  echo "  oifname \"lo\" accept"
  if [ "$L" = 1 ]; then
    [ -n "$p4" ] && echo "  oifname \"tailscale0\" ip daddr { $p4 } accept"
    [ -n "$p6" ] && echo "  oifname \"tailscale0\" ip6 daddr { $p6 } accept"
  fi
  if [ $ROLE = rig ]; then
    echo "  socket cgroupv2 level 2 \"system.slice/tailscaled.service\" oifname != \"tailscale0\" accept"   # control plane + DERP + WireGuard
    echo "  socket cgroupv2 level 2 \"system.slice/systemd-resolved.service\" meta l4proto { udp, tcp } th dport { 53, 853 } accept"
    # poller allowlist: matched by its dedicated uid (stable across restarts, unlike a cgroup id)
    id -u shields-poller >/dev/null 2>&1 && echo "  meta skuid \"shields-poller\" tcp dport 443 accept"
    id -u shields-poller >/dev/null 2>&1 && echo "  meta skuid \"shields-poller\" udp dport 53 accept"
  else
    echo "  ct state established,related accept"                 # replies to platform-initiated connections
    echo "  meta mark 0x000005a1 accept"                         # sandhost cgroup (Grok Bot runtime) direct egress
    echo "  ip daddr { 172.30.0.0/24, 198.18.0.0/15 } accept"    # platform gateway + fake-IP DNS range
    echo "  udp sport 41641 accept"                              # tailscaled WireGuard
    echo "  socket cgroupv2 level 1 \"tsd\" oifname != \"tailscale0\" accept"   # tailscaled control/DERP (moved to cgroup tsd on fire)
  fi
  [ -n "$b4" ] && echo "  ip daddr { $b4 } tcp dport 443 accept"   # control-board allowlist entry
  echo " }"
  echo "}"
}

up(){
  local L=$1; [ "$L" = 1 ] || [ "$L" = 2 ] || { echo "level must be 1 or 2"; exit 2; }
  local MIN=${ROLLMIN:-$([ "$L" = 2 ] && echo 60 || echo 10)}
  log "SHIELDS UP level $L (auto-rollback in ${MIN} min unless confirmed)"
  snapshot
  # 1 arm the local auto-rollback FIRST so a bad rule can't brick the machine
  if [ $ROLE = rig ]; then
    run "systemctl stop shields-rollback.timer 2>/dev/null; systemd-run --unit=shields-rollback --on-active=${MIN}min --timer-property=AccuracySec=10s $SELF restore"
  else
    run "pkill -f 'shields-rollback-sleep' ; setsid nohup bash -c 'exec -a shields-rollback-sleep sleep $((MIN*60)) && $SELF --role box restore' >>$STATE/rollback.log 2>&1 </dev/null &"
  fi
  # 2 tailscale-level changes
  if [ $ROLE = rig ]; then
    codex_stop "$L"
    run "$TS set --advertise-exit-node=false"
    run "$TS funnel reset 2>/dev/null; $TS serve reset"
  else
    codex_stop "$L"
    run "pkill -f seal-watch.sh || true"                           # stop fail-open watchdog (would switch box to direct egress)
    run "mkdir -p /sys/fs/cgroup/tsd && for p in \$(pgrep -f '~/ts/tailscaled|\./tailscaled'); do echo \$p > /sys/fs/cgroup/tsd/cgroup.procs; done"
  fi
  [ "$L" = 2 ] && run "$TS set --shields-up=true"   # NOT at level 1: Tailscale shields-up blocks ALL inbound tailnet conns incl. box->rig SSH
  # 3 firewall
  if [ $DRY = 1 ]; then echo "[dry-run $ROLE] nft -f - <<NFT"; nft_rules "$L" | sed 's/^/    /'; echo "NFT"
  else run "nft delete table inet shields 2>/dev/null; true"; nft_rules "$L" | nft -f - && echo "+ nft table inet shields loaded"; fi
  run "echo $L > $STATE/level; date +%s > $STATE/since"
  log "level $L applied. Confirm (keep) with: shields confirm   Restore with: shields restore"
}

restore(){
  local d="${1:-$STATE/latest}"; d=$(readlink -f "$d" 2>/dev/null || echo "$d")
  log "ALL CLEAR: restoring from $d"
  run "nft delete table inet shields 2>/dev/null; true"
  local P="$d/ts-prefs.json"
  if [ $DRY = 1 ] && [ ! -f "$P" ]; then
    d=$(mktemp -d); $TS debug prefs > "$d/ts-prefs.json" 2>/dev/null; $TS serve status --json > "$d/ts-serve.json" 2>/dev/null; P="$d/ts-prefs.json"
    echo "[dry-run $ROLE] (no snapshot yet: showing restore of the CURRENT live state as if it had been snapshotted)"; fi
  if [ -n "$P" ]; then
    local su ae; su=$(python3 -c 'import json,sys;print(str(json.load(open(sys.argv[1])).get("ShieldsUp",False)).lower())' "$P")
    ae=$(python3 -c 'import json,sys;r=json.load(open(sys.argv[1])).get("AdvertiseRoutes") or [];print("true" if "0.0.0.0/0" in r else "false")' "$P")
    run "$TS set --shields-up=$su"
    [ $ROLE = rig ] && run "$TS set --advertise-exit-node=$ae"
    if [ $ROLE = rig ] && [ -s "$d/ts-serve.json" ]; then
      python3 - "$d/ts-serve.json" <<'PY' | while read -r c; do run "$TS $c"; done
import json,sys
d=json.load(open(sys.argv[1])) or {}
fun=d.get("AllowFunnel") or {}
for hp,w in (d.get("Web") or {}).items():
    port=hp.rsplit(":",1)[1]
    for path,h in (w.get("Handlers") or {}).items():
        tgt=h.get("Proxy") or h.get("Path") or h.get("Text")
        if not tgt: continue
        verb="funnel" if fun.get(hp) else "serve"
        print(f"{verb} --bg --https={port} --set-path={path} {tgt}")
PY
    fi
  fi
  if [ $ROLE = box ]; then
    run "for p in \$(cat /sys/fs/cgroup/tsd/cgroup.procs 2>/dev/null); do echo \$p > /sys/fs/cgroup/agent/cgroup.procs 2>/dev/null; done; rmdir /sys/fs/cgroup/tsd 2>/dev/null; true"
    grep -q running "$d/seal-watch.txt" 2>/dev/null || [ $DRY = 1 ] && run "pgrep -f seal-watch.sh >/dev/null || setsid nohup sh ~/ts/seal-watch.sh >>/tmp/seal-watch.log 2>&1 </dev/null &"
    run "pkill -f shields-rollback-sleep || true"
  else
    run "systemctl stop shields-rollback.timer 2>/dev/null; true"
  fi
  run "rm -f '$CODEX_LOCK'"   # codex unblocked; workers are NOT auto-restarted
  run "echo 0 > $STATE/level; date +%s > $STATE/since"
  log "level 0 (normal)"
}

confirm(){ if [ $ROLE = rig ]; then run "systemctl stop shields-rollback.timer"; else run "pkill -f shields-rollback-sleep"; fi; log "auto-rollback cancelled; shields stay up until 'shields restore'"; }
status(){ echo "role=$ROLE level=$(cat $STATE/level 2>/dev/null || echo 0) since=$(cat $STATE/since 2>/dev/null || echo -)"; $TS debug prefs 2>/dev/null | grep -E '"ShieldsUp"'; nft list table inet shields >/dev/null 2>&1 && echo "nft: inet shields LOADED" || echo "nft: inet shields absent"
  [ $ROLE = rig ] && systemctl list-timers shields-rollback.timer --no-legend 2>/dev/null; true; }

[ $DRY = 1 ] || [ "$(id -u)" = 0 ] || { echo "run as root (sudo)"; exit 1; }
[ $DRY = 1 ] || mkdir -p "$STATE"
case "$CMD" in up) up "$LVL";; restore) restore "${2:-}";; confirm) confirm;; status) status;; snapshot) snapshot;; rules) nft_rules "$LVL";; *) echo "usage: shields [--dry-run] up 1|2 [--rollback-min N] | restore [DIR] | confirm | status | rules 1|2"; exit 2;; esac
