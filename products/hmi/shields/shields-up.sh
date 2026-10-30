#!/bin/bash
# SHIELDS UP (run from the box). Level 1 = external lockdown, box->rig SSH kept. Level 2 = full isolation (severs tailnet peers).
# Usage: shields-up.sh --authorized-by "WHO + source" [--level 1|2] [--rollback-min N] [--reason TEXT] [--no-confirm] [--dry-run]
# Every run is a ledger decision -> attempt -> receipt (ledger.jsonl). Outcome is 'unknown' unless verified.
# Trigger policy, order and checks: RUNBOOK.md. Never fired without the owner's word (via Friday) or a confirmed active compromise.
set -u; cd "$(dirname "$0")"
LVL=1; DRY=0; MIN=""; CONFIRM=1; WHO=""; WHY=""
while [ $# -gt 0 ]; do case "$1" in --level) LVL=$2; shift;; --rollback-min) MIN=$2; shift;; --no-confirm) CONFIRM=0;; --dry-run) DRY=1;;
  --authorized-by) WHO=$2; shift;; --reason) WHY=$2; shift;; *) echo "unknown $1"; exit 2;; esac; shift; done
case "$LVL" in 1|2) ;; *) echo "level must be 1 or 2"; exit 2;; esac
[ $DRY = 1 ] && WHO=${WHO:-dry-run}
[ -n "$WHO" ] || { echo "fail closed: --authorized-by is required (who said so, and where)"; exit 3; }
MIN=${MIN:-$([ "$LVL" = 2 ] && echo 60 || echo 10)}
TS=$(date +%Y%m%d-%H%M%S); SNAP=snapshots/$TS; LOG=shields.log; R="./rig.py"
say(){ echo "$(date '+%F %T %Z') $*" | tee -a $LOG; }
run(){ if [ $DRY = 1 ]; then echo "[dry-run box] $*"; else echo "+ $*" >>$LOG; bash -c "$*"; fi; }
DRYF=""; [ $DRY = 1 ] && DRYF="--dry-run"
ID=$(./ledger.py decision --who "$WHO" --level "$LVL" --scope box,host-a --reason "$WHY" $DRYF) || exit 3
say "=== SHIELDS UP level $LVL decision $ID by '$WHO' (rollback ${MIN} min, dry=$DRY) ==="
. lib/ledger-gate.sh; ledger_shields_up "$LVL" "$ID" "$DRY"   # DECISION-004: local signed intent only; never blocks
rig_fp(){ $R run 'sudo -n tailscale debug prefs | grep -E "\"(ShieldsUp|AdvertiseRoutes|WantRunning)\"" -A2; sudo -n nft list table inet shields 2>&1; tailscale serve status --json 2>&1' > "$1" 2>&1 || echo UNREACHABLE > "$1"; }
box_fp(){ { sudo ~/ts/tailscale --socket=~/ts/sock debug prefs | grep -E '"(ShieldsUp|ExitNodeID)"'; sudo nft list table inet shields 2>&1; pgrep -f seal-watch.sh >/dev/null && echo seal-watch=on || echo seal-watch=off; } > "$1" 2>&1; }
mkdir -p "$SNAP/rig" "$SNAP/box"
rig_fp "$SNAP/rig/fp-before.txt"; box_fp "$SNAP/box/fp-before.txt"
RB=$(./ledger.py hash "$SNAP/rig/fp-before.txt"); BB=$(./ledger.py hash "$SNAP/box/fp-before.txt")
RIG=1; grep -q UNREACHABLE "$SNAP/rig/fp-before.txt" && { RIG=0; say "WARN host-a unreachable: rig must be shielded at its console (sudo shields up $LVL) or via the board"; }
if [ $DRY = 1 ]; then
  echo "----- host-a engine dry-run -----"; $R put lib/shields-local.sh /tmp/shields-dry.sh && $R run "sudo -n bash /tmp/shields-dry.sh --dry-run --role rig up $LVL --rollback-min $MIN; rm -f /tmp/shields-dry.sh" | sed 's/^/  rig| /'
  echo "----- box engine dry-run -----"; sudo ./lib/shields-local.sh --role box --dry-run up $LVL --rollback-min $MIN | sed 's/^/  box| /'; echo "-----"
  for m in host-a box; do ./ledger.py receipt "$ID" --machine $m --before "$([ $m = box ] && echo $BB || echo $RB)" --after "" --checks '{"dry_run":true}' --outcome not_dispatched; done
  say "dry-run done: nothing changed; ledger $ID marked not_dispatched"; exit 0
fi
# 1 archive full state of both machines (read-only)
for f in "debug prefs:ts-prefs.json" "status --json:ts-status.json" "serve status --json:ts-serve.json"; do
  [ $RIG = 1 ] && $R run "sudo -n tailscale ${f%%:*}" > $SNAP/rig/${f##*:} 2>&1
  sudo ~/ts/tailscale --socket=~/ts/sock ${f%%:*} > $SNAP/box/${f##*:} 2>/dev/null
done
[ $RIG = 1 ] && { $R run 'sudo -n nft list ruleset' > $SNAP/rig/nft-ruleset.txt; $R run 'sudo -n ufw status verbose' > $SNAP/rig/ufw-status.txt; }
sudo nft list ruleset > $SNAP/box/nft-ruleset.txt
# 2 host-a: install engine (restore must be local for level 2), then apply
if [ $RIG = 1 ]; then
  ./ledger.py attempt "$ID" --machine host-a --action "install engine; shields up $LVL rollback ${MIN}m"
  run "$R put lib/shields-local.sh /tmp/shields.new && $R run 'sudo -n install -m 755 /tmp/shields.new /usr/local/sbin/shields && rm /tmp/shields.new && sudo -n mkdir -p /var/lib/shields'"
  if [ "$LVL" = 1 ]; then run "$R run 'sudo -n /usr/local/sbin/shields up 1 --rollback-min $MIN'"
  else run "$R run 'sudo -n systemd-run --unit=shields-apply --collect --on-active=5s /usr/local/sbin/shields up 2 --rollback-min $MIN'"; fi   # detached: SSH dies at L2
fi
# 3 box
./ledger.py attempt "$ID" --machine box --action "shields up $LVL rollback ${MIN}m"
run "sudo ./lib/shields-local.sh --role box up $LVL --rollback-min $MIN"
sleep 10
# 4 verify -> receipts (never assume)
box_fp "$SNAP/box/fp-after.txt"; BA=$(./ledger.py hash "$SNAP/box/fp-after.txt")
BOXEG=$(curl -s -m6 -o /dev/null -w '%{http_code}' https://example.com 2>/dev/null || true); BOXNFT=$(grep -c 'table inet shields' "$SNAP/box/fp-after.txt")
BOXOK=$([ "$BOXNFT" -ge 1 ] && [ "${BOXEG:-000}" = 000 ] && echo applied || echo failed)
./ledger.py receipt "$ID" --machine box --before "$BB" --after "$BA" --checks "{\"nft_loaded\":$BOXNFT,\"example_com_http\":\"${BOXEG:-000}\"}" --outcome $BOXOK
if [ $RIG = 0 ]; then ./ledger.py receipt "$ID" --machine host-a --before "$RB" --checks '{"ssh":"unreachable before fire"}' --outcome not_dispatched
elif [ "$LVL" = 1 ]; then
  rig_fp "$SNAP/rig/fp-after.txt"; RA=$(./ledger.py hash "$SNAP/rig/fp-after.txt")
  SSH=$($R ping >/dev/null 2>&1 && echo ok || echo fail)
  RIGEG=$($R run 'curl -s -m6 -o /dev/null -w "%{http_code}" https://example.com' 2>/dev/null || true)
  RNFT=$(grep -c 'table inet shields' "$SNAP/rig/fp-after.txt"); EXIT=$(grep -c '0.0.0.0/0' "$SNAP/rig/fp-after.txt")
  if [ "$SSH" = ok ] && [ "${RIGEG:-000}" = 000 ] && [ "$RNFT" -ge 1 ] && [ "$EXIT" = 0 ]; then OUT=applied; else OUT=$([ "$SSH" = ok ] && echo failed || echo unknown); fi
  ./ledger.py receipt "$ID" --machine host-a --before "$RB" --after "$RA" --checks "{\"ssh\":\"$SSH\",\"example_com_http\":\"${RIGEG:-000}\",\"nft_loaded\":$RNFT,\"exit_node_advertised\":$EXIT}" --outcome $OUT
  say "verify L1: ssh=$SSH rig_egress_http=${RIGEG:-000} rig_nft=$RNFT exit_adv=$EXIT box_egress_http=${BOXEG:-000} -> rig=$OUT box=$BOXOK"
  if [ $CONFIRM = 1 ] && [ $OUT = applied ] && [ $BOXOK = applied ]; then
    run "$R run 'sudo -n /usr/local/sbin/shields confirm'"; run "sudo ./lib/shields-local.sh --role box confirm"; say "confirmed: auto-rollback cancelled"
  else say "NOT confirmed: auto-rollback restores in $MIN min"; fi
else
  SSH=$($R ping >/dev/null 2>&1 && echo still-reachable || echo unreachable)
  # From the box, unreachable is expected but is not proof of the rig's state: outcome stays unknown until the rig checks in (board) or the owner reads 'sudo shields status'.
  ./ledger.py receipt "$ID" --machine host-a --before "$RB" --checks "{\"ssh_from_box\":\"$SSH\"}" --outcome unknown
  say "verify L2: rig ssh_from_box=$SSH (outcome recorded unknown), box=$BOXOK. Rig auto-restores in $MIN min unless 'sudo shields confirm' at the console or board holds L2"
fi
say "=== SHIELDS UP $ID done. Snapshot $SNAP. Next: pause email routines/connectors per RUNBOOK.md ==="
