#!/usr/bin/env bash
# Local self-test of shields-poller.py fail-closed logic with a fake engine + static mock board. Touches nothing real.
set -u; T=$(mktemp -d); cd "$T"; openssl rand -hex 32 > key
cat > eng.sh <<'E'
#!/bin/bash
D=$(dirname "$0"); case "$1" in status) cat $D/level;; up) echo $2 > $D/level; date +%s > $D/since;; restore) echo 0 > $D/level; date +%s > $D/since;; confirm) echo confirmed >> $D/eng.log;; esac
E
chmod +x eng.sh; echo 0 > level; echo 0 > since; mkdir -p www/api/state
sign(){ node -e '
const {createHmac}=require("crypto"),fs=require("fs");const k=Buffer.from(fs.readFileSync("key","utf8").trim(),"hex");
const c=o=>JSON.stringify(Object.keys(o).sort().reduce((a,k)=>(a[k]=o[k],a),{}));const [l,s,m,t]=process.argv.slice(1);const n=Math.floor(Date.now()/1000);
const p={machine:m,level:+l,seq:+s,decision_id:"shd-test-"+s,authorized_by:"board:test",issued_at:n,expires_at:n+86400,rollback_min:60,served_at:n};
const sig=createHmac("sha256",k).update(c(p)).digest("hex");if(t)p.level=0;fs.writeFileSync("www/api/state/host-a",JSON.stringify({payload:p,sig}));' "$@"; }
(cd www && timeout 30 python3 -m http.server 18777 >/dev/null 2>&1 &)
# Ready when the mock board answers, not after a fixed sleep (1s races on a slow start). Give up after 15s.
python3 - <<'PY' || exit 1
import sys, time, urllib.request
deadline = time.monotonic() + 15
while time.monotonic() < deadline:
    try:
        with urllib.request.urlopen("http://127.0.0.1:18777/", timeout=0.5) as r:
            if r.status == 200:
                sys.exit(0)
    except Exception:
        time.sleep(0.1)
sys.stderr.write("mock board not ready within 15s\n")
sys.exit(1)
PY
P(){ env SHIELDS_BOARD_URL=http://127.0.0.1:18777 SHIELDS_ENGINE=$T/eng.sh SHIELDS_POLLER_STATE=$T/ps SHIELDS_LEVEL_FILE=$T/level SHIELDS_SINCE_FILE=$T/since SHIELDS_HMAC_FILE=$T/key python3 "$OLDPWD/shields-poller.py" --once 2>&1 | grep -v checkin; echo "   -> local level $(cat level)"; }
echo "T1 valid L1 seq1 (apply):"; sign 1 1 host-a; sleep 1.1; P
echo "T2 same decision re-verified (confirm, cancel rollback):"; P
echo "T3 tampered payload lowering to 0 (HOLD):"; sign 1 2 host-a tamper; P
echo "T4 state signed for another machine (HOLD):"; sign 0 3 box; P
echo "T5 board unreachable (HOLD):"; mv www www.off; P; mv www.off www
echo "T6 valid all-clear seq3 (lowers: ledger proof is log-only by default):"; sleep 1.1; sign 0 3 host-a; P
echo "T7 replay of old seq1 (HOLD):"; sign 1 1 host-a; P
echo "T8 valid L2 seq4 (raise, no proof needed even when enforcing):"; sleep 1.1; sign 2 4 host-a; SHIELDS_LEDGER_ENFORCE=1 P
echo "T9 enforced all-clear seq5, no roster or proof (HOLD + alarm):"; sleep 1.1; sign 0 5 host-a
SHIELDS_LEDGER_ENFORCE=1 SHIELDS_LEDGER_PY="$OLDPWD/../../ledger/ledger.py" LEDGER_ALARMS=$T/alarms P; grep -c poller-ledger-hold $T/alarms
rm -rf "$T"
