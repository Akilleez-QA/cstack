#!/bin/bash
# ALL CLEAR (run from the box): box first (level 2 needs the tailnet back), then host-a, each from its own latest local snapshot.
# Usage: all-clear.sh --authorized-by "owner via approver <msg>" [--dry-run]
set -u; cd "$(dirname "$0")"
DRY=0; WHO=""
while [ $# -gt 0 ]; do case "$1" in --dry-run) DRY=1;; --authorized-by) WHO=$2; shift;; *) echo "unknown $1"; exit 2;; esac; shift; done
[ $DRY = 1 ] && WHO=${WHO:-dry-run}
[ -n "$WHO" ] || { echo "fail closed: --authorized-by is required (all clear is the owner's word only)"; exit 3; }
LOG=shields.log; R="./rig.py"; TS=$(date +%Y%m%d-%H%M%S); SNAP=snapshots/$TS-clear; mkdir -p $SNAP
say(){ echo "$(date '+%F %T %Z') $*" | tee -a $LOG; }
DRYF=""; [ $DRY = 1 ] && DRYF="--dry-run"
. lib/ledger-gate.sh; ledger_all_clear "$DRY" || exit 77   # DECISION-004: quorum intent when LEDGER_ENFORCE=1, before any change
ID=$(./ledger.py decision --who "$WHO" --level 0 --scope box,host-a --reason "all clear" $DRYF) || exit 3
say "=== ALL CLEAR decision $ID by '$WHO' (dry=$DRY) ==="
fp(){ if [ $1 = rig ]; then $R run 'sudo -n tailscale debug prefs | grep -E "\"(ShieldsUp|AdvertiseRoutes)\"" -A2; sudo -n nft list table inet shields 2>&1; tailscale serve status --json 2>&1' > $2 2>&1 || echo UNREACHABLE > $2
      else { sudo ~/ts/tailscale --socket=~/ts/sock debug prefs | grep -E '"(ShieldsUp|ExitNodeID)"'; sudo nft list table inet shields 2>&1; pgrep -f seal-watch.sh >/dev/null && echo seal-watch=on || echo seal-watch=off; } > $2 2>&1; fi; }
fp box $SNAP/box-before.txt; BB=$(./ledger.py hash $SNAP/box-before.txt)
if [ $DRY = 1 ]; then
  echo "----- box engine dry-run -----"; sudo ./lib/shields-local.sh --role box --dry-run restore | sed 's/^/  box| /'
  echo "----- host-a engine dry-run -----"; $R put lib/shields-local.sh /tmp/shields-dry.sh && $R run "sudo -n bash /tmp/shields-dry.sh --dry-run --role rig restore; rm -f /tmp/shields-dry.sh" | sed 's/^/  rig| /'
  for m in box host-a; do ./ledger.py receipt "$ID" --machine $m --before "$BB" --checks '{"dry_run":true}' --outcome not_dispatched; done
  say "dry-run done: nothing changed"; exit 0
fi
./ledger.py attempt "$ID" --machine box --action restore
sudo ./lib/shields-local.sh --role box restore >>$LOG 2>&1; sleep 6
fp box $SNAP/box-after.txt; BA=$(./ledger.py hash $SNAP/box-after.txt)
BOXIP=$(curl -s -m8 -x socks5h://127.0.0.1:1055 https://api.ipify.org || true); BNFT=$(grep -c 'table inet shields' $SNAP/box-after.txt)
./ledger.py receipt "$ID" --machine box --before "$BB" --after "$BA" --checks "{\"nft_loaded\":$BNFT,\"socks_exit_ip\":\"$BOXIP\"}" --outcome $([ "$BNFT" = 0 ] && echo applied || echo failed)
fp rig $SNAP/rig-before.txt; RB=$(./ledger.py hash $SNAP/rig-before.txt)
if grep -q UNREACHABLE $SNAP/rig-before.txt; then
  ./ledger.py receipt "$ID" --machine host-a --before "$RB" --checks '{"ssh":"unreachable"}' --outcome not_dispatched
  say "host-a unreachable (L2 still holding). Restore there: board 'All clear', the auto-rollback timer, or at the console: sudo shields restore"
else
  ./ledger.py attempt "$ID" --machine host-a --action restore
  $R run 'sudo -n /usr/local/sbin/shields restore' >>$LOG 2>&1; RC=$?
  fp rig $SNAP/rig-after.txt; RA=$(./ledger.py hash $SNAP/rig-after.txt)
  EG=$($R run 'curl -s -m6 -o /dev/null -w "%{http_code}" https://example.com' 2>/dev/null || true); RNFT=$(grep -c 'table inet shields' $SNAP/rig-after.txt)
  OUT=$([ $RC = 0 ] && [ "$RNFT" = 0 ] && [ "${EG:-000}" != 000 ] && echo applied || echo $([ $RC = 97 ] && echo unknown || echo failed))
  ./ledger.py receipt "$ID" --machine host-a --before "$RB" --after "$RA" --checks "{\"rc\":$RC,\"nft_loaded\":$RNFT,\"example_com_http\":\"${EG:-000}\",\"exit_ip_box\":\"$BOXIP\"}" --outcome $OUT
  say "verify: rig=$OUT (egress http ${EG:-000}), box exit IP $BOXIP (expect 96.59.9.1)"
fi
say "=== ALL CLEAR $ID done. Next: reconnect email per RUNBOOK.md ==="
