#!/usr/bin/env python3
"""shields-poller: pull signed desired state from the control board, apply it locally via /usr/local/sbin/shields.

Fail-closed rules (POODO):
  * Unverifiable state (network error, bad HMAC, wrong machine, stale served_at, seq going backwards, expired) => HOLD.
    Hold = keep the last verified level and NEVER lower shields. Report outcome "held".
  * Only a verified state with seq > last_seq can change the level. seq 0 (no decision yet) never changes anything.
  * A local shields change (console / box script) newer than the board decision wins until the board issues a newer decision.
  * Each raise arms the local auto-rollback timer (the engine does it). The poller confirms (cancels the timer) only on the
    NEXT verified poll that still asks for that level, so if the board becomes unreachable the timer stays as the backup.
  * After acting, the outcome is read back from the engine. If it can't be read back, it's "unknown", never assumed "applied".
Stdlib only. Runs as user shields-poller, with sudo NOPASSWD limited to /usr/local/sbin/shields.
Key: $CREDENTIALS_DIRECTORY/shields-hmac (systemd LoadCredentialEncrypted) or $SHIELDS_HMAC_FILE. Never logged.
Board: $SHIELDS_BOARD_URL (required, https). No default host: unset => nothing can be fetched, so HOLD forever.
Check-ins carry cseq (strictly increasing: max(last+1, unix ms)) + a random nonce inside the HMAC, so the board can
reject replayed receipts (see control-board/lib/checkin.ts).
Ledger proof (DECISION-004): the HMAC proves the board sent it, not that the owner's witnessed quorum authorized it. A move to
L0 (all-clear) from L1/L2 is applied only with a ledger bundle (`ledger.py bundle`, served next to the payload as
resp["ledger"] = {action, bundle}) that verifies here, offline, against $SHIELDS_LEDGER_ROSTER (public keys only), for
{op:"all-clear", scope ∋ this machine}, issued within 24h and never used before on this machine. Bad or missing proof with
SHIELDS_LEDGER_ENFORCE=1 => HOLD the current level, alarm ($LEDGER_ALARMS), check in "held". Default is log-only (lowers,
but the check-in and log say what would have been held). Raising shields, or 2 -> 1, never needs a proof.
Phone co-sign: the all-clear may also carry resp["cosign"], the owner's passkey assertion from the board (control-board/lib/cosign.ts),
bound to the proof's intent hash. It is checked with ledger.py verify_cosign against roster "cosigners" (public keys), and
must have been live when the decision was issued, single use here. SHIELDS_COSIGN_ENFORCE=1 => missing/bad co-sign HOLDs too.
"""
import hashlib, hmac, importlib.util, json, os, secrets, subprocess, sys, time, urllib.request

BOARD = os.environ.get("SHIELDS_BOARD_URL", "").strip().rstrip("/")
MACHINE = os.environ.get("SHIELDS_MACHINE", "host-a")
ENGINE = os.environ.get("SHIELDS_ENGINE", "/usr/local/sbin/shields")
SUDO = [] if os.geteuid() == 0 else ["sudo", "-n"]
STATE_DIR = os.environ.get("SHIELDS_POLLER_STATE", "/var/lib/shields-poller")
LEVEL_FILE = os.environ.get("SHIELDS_LEVEL_FILE", "/var/lib/shields/level")
SINCE_FILE = os.environ.get("SHIELDS_SINCE_FILE", "/var/lib/shields/since")
INTERVAL = int(os.environ.get("SHIELDS_POLL_SEC", "60"))
FRESH = 300
LEDGER_ENFORCE = os.environ.get("SHIELDS_LEDGER_ENFORCE") == "1"
LEDGER_PY = os.environ.get("SHIELDS_LEDGER_PY", "/usr/local/lib/shields/ledger.py")
LEDGER_ROSTER = os.environ.get("SHIELDS_LEDGER_ROSTER", "/etc/shields-ledger-roster.json")
LEDGER_ALARMS = os.environ.get("LEDGER_ALARMS", os.path.join(STATE_DIR, "alarms.jsonl"))
COSIGN_ENFORCE = os.environ.get("SHIELDS_COSIGN_ENFORCE") == "1"
INTENT_MAX_AGE = 24 * 3600
ONCE = "--once" in sys.argv
DRY = "--dry-run" in sys.argv


def log(msg):
    print(time.strftime("%Y-%m-%d %H:%M:%S %Z"), msg, flush=True)


def key():
    p = os.path.join(os.environ.get("CREDENTIALS_DIRECTORY", ""), "shields-hmac")
    p = p if os.path.isfile(p) else os.environ.get("SHIELDS_HMAC_FILE", "")
    with open(p) as f:
        return bytes.fromhex(f.read().strip())


def canonical(d):  # must match lib/sign.ts canonical(): sorted keys, compact, raw unicode
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sig(k, d):
    return hmac.new(k, canonical(d).encode(), hashlib.sha256).hexdigest()


def load_state():
    try:
        with open(os.path.join(STATE_DIR, "poller.json")) as f:
            return json.load(f)
    except Exception:
        return {"last_seq": 0, "last_verified_level": None, "pending_confirm_seq": None}


def save_state(s):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = os.path.join(STATE_DIR, "poller.json.tmp")
    with open(tmp, "w") as f:
        json.dump(s, f)
    os.replace(tmp, os.path.join(STATE_DIR, "poller.json"))


def local_level():
    try:
        return int(open(LEVEL_FILE).read().strip() or 0), int(open(SINCE_FILE).read().strip() or 0)
    except FileNotFoundError:
        return 0, 0
    except Exception:
        return None, 0  # unreadable => unknown


def engine(*args):
    cmd = SUDO + [ENGINE] + (["--dry-run"] if DRY else []) + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout + r.stderr


def fingerprint():
    rc, out = engine("status")
    return hashlib.sha256(out.encode()).hexdigest()[:16] if rc == 0 else None


def http(method, url, body=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "User-Agent": f"shields-poller/{MACHINE}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def next_cseq():
    """Strictly increasing check-in sequence. Time-based floor keeps it moving forward even if the state file is lost."""
    path = os.path.join(STATE_DIR, "checkin-seq")
    try:
        with open(path) as f:
            last = int(f.read().strip() or 0)
    except Exception:
        last = 0
    n = max(last + 1, int(time.time() * 1000))
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(path + ".tmp", "w") as f:
            f.write(str(n))
        os.replace(path + ".tmp", path)
    except Exception as e:
        log(f"checkin-seq not persisted ({type(e).__name__}); time floor still keeps it increasing")
    return n


def checkin(k, **p):
    p.update(machine=MACHINE, ts=int(time.time()), cseq=next_cseq(), nonce=secrets.token_hex(16))
    try:
        http("POST", f"{BOARD}/api/checkin", {"payload": p, "sig": sig(k, p)})
    except Exception as e:
        log(f"checkin failed ({type(e).__name__}); continuing")
    ledger_checkin(p)


def ledger_checkin(p):
    """Signed heartbeat, independent of the HTTP receipt and all-clear enforcement."""
    try:
        origin = os.environ["LEDGER_ORIGIN"]
        if origin != MACHINE:
            raise ValueError("ledger origin must be this machine")
        L, roster = verifier(os.environ.get("LEDGER_PY", LEDGER_PY), os.environ["LEDGER_ROSTER"])
        node = L.Log(os.environ["LEDGER_LOG"], origin, roster)
        body = {name: p.get(name) for name in ("machine", "level", "outcome", "cseq", "ts")}
        last = next((e["body"] for e in reversed(node.entries)
                     if e["kind"] == "checkin" and e["body"].get("machine") == MACHINE), None)
        interval = max(0, int(os.environ.get("SHIELDS_LEDGER_CHECKIN_SEC", "300")))
        if last and all(last.get(n) == body[n] for n in ("level", "outcome")) \
                and 0 <= body["ts"] - last["ts"] < interval:
            return
        node.write(L.load_key(os.environ["LEDGER_KEY"]), os.environ["LEDGER_WRITER"], "checkin", body)
    except Exception as e:
        alarm("poller-ledger-checkin-write", error=type(e).__name__)
        return
    # No automatic push follows Log.write(). Use the existing witness transport, without a quorum gate.
    witnesses = os.environ.get("LEDGER_WITNESSES", "").split()
    if not witnesses:
        alarm("poller-ledger-checkin-push", error="no-witnesses")
    for index, url in enumerate(witnesses):
        try:
            if not L.push(node, url):
                raise RuntimeError("witness unavailable")
        except Exception as e:
            alarm("poller-ledger-checkin-push", witness=index, error=type(e).__name__)


def verify(k, resp, st):
    """Return (payload, None) if trustworthy else (None, reason)."""
    p, s = resp.get("payload"), resp.get("sig", "")
    if not isinstance(p, dict) or not hmac.compare_digest(sig(k, p), s):
        return None, "bad_signature"
    if p.get("machine") != MACHINE:
        return None, "wrong_machine"
    now = time.time()
    if abs(now - int(p.get("served_at", 0))) > FRESH:
        return None, "stale_response"
    if int(p.get("seq", 0)) < int(st["last_seq"]):
        return None, "seq_rollback"
    if int(p.get("seq", 0)) > 0 and now > int(p.get("expires_at", 0)):
        return None, "expired_decision"
    if int(p.get("level", -1)) not in (0, 1, 2):
        return None, "bad_level"
    return p, None


def alarm(code, **detail):
    try:
        with open(LEDGER_ALARMS, "a") as f:
            f.write(json.dumps({"ts": int(time.time()), "code": code, "machine": MACHINE, **detail}) + "\n")
    except Exception as e:
        log(f"alarm not written ({type(e).__name__})")
    log(f"ALARM {code} {detail}")


def verifier(path=LEDGER_PY, roster_path=LEDGER_ROSTER):
    spec = importlib.util.spec_from_file_location("shields_ledger", path)
    L = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(L)
    return L, L.load_roster(roster_path)


def cosign_check(resp, h, p, st):
    """None if resp carries the owner's valid, unused phone co-sign for this all-clear (bound to intent h), else the reason."""
    try:
        L, roster = verifier()
    except Exception as e:
        return f"verifier-unavailable:{type(e).__name__}"
    a = resp.get("cosign")
    if not isinstance(a, dict) or not isinstance(a.get("scope"), list):
        return "absent"
    c = next((v for v in (roster.get("cosigners") or {}).values() if v.get("credentialId") == a.get("credentialId")), None)
    if MACHINE not in a["scope"] or c is None:
        return "wrong-scope-or-credential"
    try:
        L.verify_cosign(a, h, a["scope"], c, int(p.get("issued_at", 0)))  # live when the board accepted it
    except L.LedgerError as e:
        return str(e)
    except Exception as e:
        return f"malformed:{type(e).__name__}"
    return "cosign-already-used" if a.get("nonce") in st.get("used_cosigns", []) else None


def ledger_proof(resp, st):
    """(intent_hash, None) if resp carries a valid, fresh, unused all-clear proof covering MACHINE, else (None, reason)."""
    try:
        L, roster = verifier()
    except Exception as e:
        return None, f"verifier-unavailable:{type(e).__name__}"
    lg = resp.get("ledger")
    if not isinstance(lg, dict):
        return None, "absent"
    act = lg.get("action")
    if not isinstance(act, dict) or act.get("op") != "all-clear" or MACHINE not in (act.get("scope") or []):
        return None, "wrong-action"
    try:
        h = L.verify_bundle(lg.get("bundle"), act, roster)
    except L.LedgerError as e:
        return None, str(e)
    except Exception as e:
        return None, f"malformed:{type(e).__name__}"
    if time.time() - int(lg["bundle"]["intent"].get("ts", 0)) > INTENT_MAX_AGE:
        return None, "stale-intent"
    if h in st.get("used_intents", []):
        return None, "intent-already-used"
    return h, None


def tick(k):
    st = load_state()
    cur, since = local_level()
    resp = {}
    try:
        resp = http("GET", f"{BOARD}/api/state/{MACHINE}")
        p, why = verify(k, resp, st)
    except Exception as e:
        p, why = None, f"unreachable:{type(e).__name__}"
    if p is None:  # FAIL CLOSED: hold, never lower
        log(f"HOLD level={cur} reason={why}")
        checkin(k, level=cur, outcome="held", reason=why, decision_id="none", seq_applied=st["last_seq"])
        return
    seq, want = int(p["seq"]), int(p["level"])
    if seq == 0:
        checkin(k, level=cur, outcome="noop", decision_id="none", seq_applied=0)
        return
    if seq == st["last_seq"]:
        # same decision: confirm a raise once the board has been re-verified (cancels local auto-rollback)
        if st.get("pending_confirm_seq") == seq and cur == want and want > 0:
            rc, _ = engine("confirm")
            if rc == 0:
                st["pending_confirm_seq"] = None
                save_state(st)
                log(f"confirmed level {want} (seq {seq}); auto-rollback cancelled")
        checkin(k, level=cur, outcome="noop", decision_id=p["decision_id"], seq_applied=seq)
        return
    # new verified decision
    if cur is None:
        log("local level unreadable; HOLD")
        checkin(k, level=None, outcome="unknown", reason="local_level_unreadable", decision_id=p["decision_id"], seq_applied=st["last_seq"])
        return
    if want < cur and since > int(p.get("issued_at", 0)):
        log(f"HOLD: local change at {since} is newer than board decision {p['decision_id']}; not lowering")
        st["last_seq"] = seq
        save_state(st)
        checkin(k, level=cur, outcome="held", reason="local_newer", decision_id=p["decision_id"], seq_applied=seq)
        return
    note = None
    if want == 0 and cur > 0:  # all-clear: needs a ledger proof. Raising (and 2 -> 1) never does.
        h, bad = ledger_proof(resp, st)
        cbad = cosign_check(resp, h, p, st) if (COSIGN_ENFORCE or "cosign" in resp) else None
        for what, why, enforced in (("ledger", bad, LEDGER_ENFORCE), ("cosign", cbad, COSIGN_ENFORCE)):
            if why and enforced:
                alarm(f"poller-{what}-hold", reason=why, decision_id=p["decision_id"], seq=seq, level=cur)
                st["last_seq"] = seq  # one hold per decision; a new board decision (new seq) is needed to retry
                save_state(st)
                checkin(k, level=cur, outcome="held", reason=f"{what}:{why}", decision_id=p["decision_id"], seq_applied=seq)
                return
        note = f"log-only:{bad}" if bad else "ok"
        if COSIGN_ENFORCE or "cosign" in resp:
            note += f" cosign:{'log-only:' + cbad if cbad else 'ok'}"
        if h:  # single use on this machine, recorded before acting
            st["used_intents"] = (st.get("used_intents", []) + [h])[-256:]
        if not cbad and isinstance(resp.get("cosign"), dict):
            st["used_cosigns"] = (st.get("used_cosigns", []) + [resp["cosign"].get("nonce")])[-256:]
        save_state(st)
        log(f"ledger proof for decision {p['decision_id']}: {note}")
    before = fingerprint()
    if want == cur:
        rc, out = 0, "already at level"
    elif want == 0:
        rc, out = engine("restore")
    else:
        if cur > 0:
            engine("restore")  # move between 1 and 2 by going back to the snapshot first
        rc, out = engine("up", str(want), "--rollback-min", str(int(p.get("rollback_min", 60))))
    after_level, _ = local_level()
    after = fingerprint()
    if after_level is None or after is None:
        outcome = "unknown"
    elif rc == 0 and after_level == want:
        outcome = "applied"
    else:
        outcome = "failed"
    st["last_seq"] = seq
    if outcome == "applied":
        st["last_verified_level"] = want
        st["pending_confirm_seq"] = seq if want > 0 else None
    save_state(st)
    log(f"decision {p['decision_id']} seq {seq}: {cur}->{want} outcome={outcome}")
    checkin(k, level=after_level, outcome=outcome, decision_id=p["decision_id"], seq_applied=seq,
            before=before, after=after, checks={"engine_rc": rc, "tail": out[-300:]}, **({"ledger_note": note} if note else {}))


def main():
    try:
        k = key()
    except Exception:
        log("no HMAC key available; nothing can be verified, so HOLD forever (no changes)")
        k = None
    if not BOARD.startswith(("https://", "http://127.0.0.1", "http://localhost")):
        log("SHIELDS_BOARD_URL unset or not https; nothing can be fetched, so HOLD forever (no changes)")
        k = None
    while True:
        if k is not None:
            try:
                tick(k)
            except Exception as e:  # never crash into an unknown state; hold
                log(f"tick error {type(e).__name__}: HOLD")
        if ONCE:
            return
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
