#!/usr/bin/env python3
"""Private witnessed ledger (DECISION-004 prototype). One hash-chained, signed log per node; always-on witness nodes
keep verified replicas and co-sign checkpoints; effects run only against a quorum-witnessed intent (pre-register, then act).
The box is a writer-only client: it signs locally, queues while asleep, pushes on wake, and is never a witness.
ledger.py keygen PATH                                   -> new ed25519 key (0600, outside the repo); prints public hex
ledger.py intent --log F --origin O --roster R --key K --writer W --action JSON  -> prints the intent hash (pre-register)
ledger.py reconcile --log F --origin O --roster R --witness URL [--witness URL ...]  -> 0 quorum checkpoint stored, 77 not
ledger.py bundle --log F --origin O --roster R --intent H                    -> JSON proof {intent, chain, checkpoint} for the board
ledger.py verify --log F --origin O --roster R          -> exit 0 ok, 3 alarm
ledger.py gate --log F --origin O --roster R --intent H --action JSON [--claim --key K --writer W]
                                                        -> exit 0 allowed (and consumed with --claim), 77 denied
ledger.py serve --name N --key K --roster R --dir D --host TAILNET_IP [--port 0]
                                                        -> witness; refuses 0.0.0.0/LAN/hostnames, POST capped at MAX_BODY (413)
Fails closed: any parse, signature, chain, sequence or quorum problem denies. Nothing here retries on its own."""
import argparse, base64, contextlib, fcntl, hashlib, ipaddress, json, os, socket, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization as ser
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

KINDS = {"intent", "claim", "result", "shields", "checkin", "merge", "note"}
SAFE_DIRECTION = {"shields-up"}  # an e-stop is never blocked on quorum; a local signed intent is enough
GENESIS = "0" * 64
MAX_BODY = 1 << 20  # witness POST cap; a full L2 backlog push is far below this
TAILNET = (ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48"))

class LedgerError(Exception): pass
class Denied(LedgerError): pass
class Alarm(LedgerError):
    """Sentinel-facing: appended to $LEDGER_ALARMS (JSONL) when set, so the sentinel raises it."""
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}"); self.code = code
        p = os.environ.get("LEDGER_ALARMS")
        if p:
            with open(p, "a") as f: f.write(json.dumps({"ts": int(time.time()), "code": code, "detail": detail}) + "\n")

def canon(o): return json.dumps(o, sort_keys=True, separators=(",", ":")).encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def digest(action): return sha(canon(action))
def pub_hex(k): return k.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw).hex()
def sign(k, msg): return base64.b64encode(k.sign(msg)).decode()
def ok_sig(pubhex, sig, msg):
    try: Ed25519PublicKey.from_public_bytes(bytes.fromhex(pubhex)).verify(base64.b64decode(sig), msg); return True
    except (InvalidSignature, ValueError, TypeError): return False
def save_key(k, path):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f: f.write(k.private_bytes(ser.Encoding.Raw, ser.PrivateFormat.Raw, ser.NoEncryption()).hex())
def load_key(path):
    if os.stat(path).st_mode & 0o077: raise LedgerError(f"key {path} is readable by group/other")
    with open(path) as f: return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(f.read().strip()))
def load_roster(path):
    with open(path) as f: r = json.load(f)  # public keys only: {"writers": {name: {"pub": hex, "node": origin}}, "witnesses": {name: hex}, "quorum": 2}
    if r.get("quorum", 0) < 2 or len(r.get("witnesses", {})) < r["quorum"]: raise LedgerError("roster needs quorum >= 2 witnesses")
    return r

def cp_text(origin, size, head): return f"{origin}\n{size}\n{head}\n".encode()  # C2SP tlog-checkpoint shaped
def cosign(key, name, origin, size, head, ts=None):
    ts = int(ts or time.time())
    return {"name": name, "ts": ts, "sig": sign(key, ts.to_bytes(8, "big") + cp_text(origin, size, head))}
def quorum_names(roster, origin, size, head, cosigs):
    good = set()
    for c in cosigs:
        pk = roster["witnesses"].get(c.get("name"))
        if pk and isinstance(c.get("ts"), int) and ok_sig(pk, c.get("sig", ""), c["ts"].to_bytes(8, "big") + cp_text(origin, size, head)):
            good.add(c["name"])
    return good

class Log:
    """Append-only JSONL file. Re-verified in full on open; production files carry chattr +a (see DECISION-004)."""
    def __init__(self, path, origin, roster):
        self.path, self.origin, self.roster = path, origin, roster
        self.entries, self.wseq, self.cps, self._mu = [], {}, [], threading.Lock()
        self.refresh()
    def refresh(self):
        """Verify and load entries other writers appended since we last read (the whole file on first open)."""
        if os.path.exists(self.path):
            with open(self.path) as f: lines = [l for l in f if l.strip()]
            if len(lines) < len(self.entries): raise Alarm("rollback", f"{self.path} shrank to {len(lines)} < {len(self.entries)}")
            self.extend([json.loads(l) for l in lines[len(self.entries):]], persist=False)
        if os.path.exists(self.path + ".cp"):
            with open(self.path + ".cp") as f: self.cps = [json.loads(l) for l in f if l.strip()]
    @contextlib.contextmanager
    def locked(self):
        """Exclusive across threads and processes (flock on <log>.lock); re-reads the file so seq/wseq/use are current."""
        with self._mu, open(self.path + ".lock", "a") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            try: self.refresh(); yield self
            finally: fcntl.flock(lk, fcntl.LOCK_UN)
    @property
    def head(self): return self.entries[-1]["hash"] if self.entries else GENESIS
    def _check(self, e, seq, prev, wseq):
        if not isinstance(e, dict): raise Alarm("malformed-entry")
        body = {k: v for k, v in e.items() if k not in ("sig", "hash")}
        w = self.roster["writers"].get(e.get("writer"))
        if e.get("origin") != self.origin: raise Alarm("wrong-origin", str(e.get("origin")))
        if not w or w.get("node") != self.origin: raise Alarm("unknown-writer", str(e.get("writer")))
        if e.get("kind") not in KINDS: raise Alarm("unknown-kind", str(e.get("kind")))
        if not e.get("sig") or not ok_sig(w["pub"], e["sig"], canon(body)): raise Alarm("bad-signature", f"seq {e.get('seq')}")
        if e.get("hash") != sha(canon({**body, "sig": e["sig"]})): raise Alarm("hash-mismatch", f"seq {e.get('seq')}")
        if e.get("seq") != seq or e.get("prev") != prev: raise Alarm("chain-break", f"at seq {seq}")
        want = wseq.get(e["writer"], 0) + 1
        if e.get("wseq") != want: raise Alarm("writer-seq-gap", f"{e['writer']} expected {want} got {e.get('wseq')}")
    def extend(self, new, persist=True):
        """Verify every new entry against the current head first; commit all or nothing."""
        seq, prev, wseq = len(self.entries), self.head, dict(self.wseq)
        for e in new:
            seq += 1; self._check(e, seq, prev, wseq); prev, wseq[e["writer"]] = e["hash"], e["wseq"]
        if persist: self._persist(new)
        self.entries.extend(new); self.wseq = wseq
    def _persist(self, new):
        if not new: return
        with open(self.path, "a") as f:
            for e in new: f.write(json.dumps(e, sort_keys=True) + "\n")
            f.flush(); os.fsync(f.fileno())
    def write(self, key, writer, kind, body, ref=None):
        with self.locked(): return self._write(key, writer, kind, body, ref)
    def _write(self, key, writer, kind, body, ref=None):
        e = {"v": 1, "origin": self.origin, "seq": len(self.entries) + 1, "prev": self.head, "writer": writer,
             "wseq": self.wseq.get(writer, 0) + 1, "kind": kind, "ts": int(time.time()), "body": body, "ref": ref}
        e["sig"] = sign(key, canon(e)); e["hash"] = sha(canon(e)); self.extend([e]); return e
    def intent(self, key, writer, action): return self.write(key, writer, "intent", {"digest": digest(action), "op": action.get("op")})
    def result(self, key, writer, intent_hash, outcome): return self.write(key, writer, "result", {"outcome": outcome}, ref=intent_hash)
    def claim(self, key, writer, intent_hash, action):
        """Gate and consume in one critical section: of N concurrent callers on one intent, exactly one gets the claim
        entry back; the rest get Denied('intent-already-used'). Callers execute only after claim() returns."""
        with self.locked():
            authorize(self, intent_hash, action)
            return self._write(key, writer, "claim", {"digest": digest(action)}, ref=intent_hash)
    def add_checkpoint(self, size, head, cosigs):
        if not (0 < size <= len(self.entries)) or self.entries[size - 1]["hash"] != head: raise Alarm("checkpoint-mismatch", f"size {size}")
        if len(quorum_names(self.roster, self.origin, size, head, cosigs)) < self.roster["quorum"]: raise Denied("checkpoint below quorum")
        cp = {"size": size, "head": head, "cosigs": cosigs}
        with open(self.path + ".cp", "a") as f: f.write(json.dumps(cp, sort_keys=True) + "\n")
        self.cps.append(cp); return cp
    def witnessed_size(self):
        best = 0
        for cp in self.cps:
            s = cp["size"]
            if s <= len(self.entries) and self.entries[s - 1]["hash"] == cp["head"] and \
               len(quorum_names(self.roster, self.origin, s, cp["head"], cp["cosigs"])) >= self.roster["quorum"]: best = max(best, s)
        return best

def authorize(log, intent_hash, action):
    """The gate. Valid only if a signed intent for exactly this action exists, is unused, and is quorum-witnessed."""
    e = next((x for x in log.entries if x["hash"] == intent_hash), None)
    if not e or e["kind"] != "intent": raise Denied("no-intent: execute-then-log is not allowed")
    if e["body"].get("digest") != digest(action): raise Denied("intent-digest-mismatch")
    if any(x["kind"] in ("claim", "result") and x.get("ref") == intent_hash for x in log.entries): raise Denied("intent-already-used")
    if action.get("op") in SAFE_DIRECTION: return e
    if log.witnessed_size() < e["seq"]: raise Denied("intent-not-witnessed-by-quorum")
    return e

def bundle(log, intent_hash):
    """Self-contained proof for verifiers that cannot read the log (the board): intent, chain up to a quorum checkpoint, cosigs."""
    e = next((x for x in log.entries if x["hash"] == intent_hash and x["kind"] == "intent"), None)
    if not e: raise Denied("no-intent")
    ok = [c for c in log.cps if e["seq"] <= c["size"] <= len(log.entries) and log.entries[c["size"] - 1]["hash"] == c["head"]
          and len(quorum_names(log.roster, log.origin, c["size"], c["head"], c["cosigs"])) >= log.roster["quorum"]]
    if not ok: raise Denied("intent-not-witnessed-by-quorum")
    cp = min(ok, key=lambda c: c["size"])
    return {"intent": e, "chain": log.entries[e["seq"] - 1:cp["size"]], "checkpoint": cp}

def _check_entry(e, origin, roster):
    body = {k: v for k, v in e.items() if k not in ("sig", "hash")}
    w = roster["writers"].get(str(e.get("writer")))
    if e.get("origin") != origin or not w or w["node"] != origin: raise Denied("unknown-writer-or-origin")
    if not isinstance(e.get("sig"), str) or not ok_sig(w["pub"], e["sig"], canon(body)): raise Denied("bad-signature")
    if e.get("hash") != sha(canon({**body, "sig": e["sig"]})): raise Denied("hash-mismatch")

def verify_bundle(b, action, roster):
    """Offline twin of control-board lib/ledger.ts verifyIntent(): same checks, same error names. Returns the intent hash."""
    it, chain, cp = (b or {}).get("intent"), (b or {}).get("chain"), (b or {}).get("checkpoint")
    if not isinstance(it, dict) or not isinstance(chain, list) or not chain or not isinstance(cp, dict) \
       or not isinstance(cp.get("cosigs"), list) or it.get("kind") != "intent": raise Denied("no-intent")
    origin = str(it.get("origin"))
    _check_entry(it, origin, roster)
    if (it.get("body") or {}).get("digest") != digest(action): raise Denied("intent-digest-mismatch")
    if chain[0].get("hash") != it["hash"]: raise Denied("chain-must-start-at-intent")
    for p, e in zip(chain, chain[1:]):
        _check_entry(e, origin, roster)
        if e.get("seq") != p["seq"] + 1 or e.get("prev") != p["hash"]: raise Denied("chain-break")
        if e["kind"] in ("claim", "result") and e.get("ref") == it["hash"]: raise Denied("intent-already-used")
    if chain[-1]["seq"] != cp.get("size") or chain[-1]["hash"] != cp.get("head"): raise Denied("checkpoint-does-not-cover-intent")
    if len(quorum_names(roster, origin, cp["size"], cp["head"], cp["cosigs"])) < roster["quorum"]:
        raise Denied("intent-not-witnessed-by-quorum")
    return it["hash"]

COSIGN_TTL = 600
def _b64u(s): return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
def cosign_challenge(intent, scope, nonce, exp):
    return hashlib.sha256(canon({"op": "all-clear-cosign", "intent": intent, "scope": sorted(scope), "nonce": nonce, "exp": exp})).digest()

def verify_cosign(a, intent, scope, c, now):
    """Twin of control-board lib/cosign.ts verifyCosign(): the owner's phone passkey (ES256 WebAuthn assertion) signed exactly
    this all-clear. c = roster["cosigners"][name] = {credentialId, spki (b64 DER), rpId, origins}. Returns the sign count."""
    if not isinstance(a, dict): raise Denied("absent")
    if a.get("credentialId") != c["credentialId"]: raise Denied("unknown-credential")
    if a.get("intent") != intent or sorted(a.get("scope") or []) != sorted(scope): raise Denied("binding-mismatch")
    exp = a.get("exp")
    if not isinstance(exp, int) or exp < now or exp > now + COSIGN_TTL: raise Denied("expired")
    try: cd, ad, sg = _b64u(a["clientDataJSON"]), _b64u(a["authenticatorData"]), _b64u(a["signature"]); client = json.loads(cd)
    except Exception: raise Denied("bad-client-data")
    if not isinstance(client, dict) or client.get("type") != "webauthn.get": raise Denied("bad-client-data")
    want = base64.urlsafe_b64encode(cosign_challenge(intent, a["scope"], a.get("nonce"), exp)).decode().rstrip("=")
    if client.get("challenge") != want: raise Denied("challenge-mismatch")
    if client.get("origin") not in c["origins"]: raise Denied("bad-origin")
    if len(ad) < 37 or ad[:32] != hashlib.sha256(c["rpId"].encode()).digest(): raise Denied("bad-rp")
    if ad[32] & 0x05 != 0x05: raise Denied("needs-user-presence-and-verification")
    try: ser.load_der_public_key(base64.b64decode(c["spki"])).verify(sg, ad + hashlib.sha256(cd).digest(), ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError, TypeError): raise Denied("bad-signature")
    return int.from_bytes(ad[33:37], "big")

class Witness:
    """Keeps a verified replica per origin and co-signs only append-only growth of it."""
    def __init__(self, name, key, roster, d):
        self.name, self.key, self.roster, self.dir = name, key, roster, d; os.makedirs(d, exist_ok=True)
    def replica(self, origin): return Log(os.path.join(self.dir, origin + ".replica.jsonl"), origin, self.roster)
    def add_checkpoint(self, origin, old, entries, size, head):
        r = self.replica(origin)
        with r.locked(): return self._add(r, origin, old, entries, size, head)  # concurrent POSTs for one origin serialize
    def _add(self, r, origin, old, entries, size, head):
        n = len(r.entries)  # rollback is judged against what this witness already verified, before any staleness check
        if size < n or size < old: raise Alarm("rollback", f"{origin} presents size {size}, witnessed {n}, client old {old}")
        if old != n: return {"conflict": n}  # only a genuinely stale or ahead `old` with no shrink: client re-reads /head
        try: r.extend(entries, persist=False)  # verify in memory; write to disk only once the checkpoint matches
        except Alarm as a: raise Alarm("equivocation", f"{origin}: new entries do not extend witnessed head ({a.code})")
        if len(r.entries) != size or r.head != head: raise Alarm("equivocation", f"{origin}: checkpoint differs from replica")
        r._persist(entries)
        return {"cosig": cosign(self.key, self.name, origin, size, head)}
    def compare(self, origin, size, head):
        """Gossip check against another witness's (size, head): a different hash at the same size is a fork."""
        r = self.replica(origin)
        if 0 < size <= len(r.entries) and r.entries[size - 1]["hash"] != head: raise Alarm("fork", f"{origin} at {size}")

def push(log, url):
    """Send the entries a witness has not seen and return its cosignature, or None if unreachable (caller stays denied)."""
    try:
        old = json.load(urlopen(f"{url}/head?origin={log.origin}", timeout=5))["size"]
        body = canon({"origin": log.origin, "old": old, "entries": log.entries[old:], "size": len(log.entries), "head": log.head})
        return json.load(urlopen(Request(f"{url}/add-checkpoint", data=body, method="POST"), timeout=10)).get("cosig")
    except HTTPError as h:
        if h.code == 422:  # the witness raised an alarm (rollback, equivocation): surface it on this node's sentinel too
            try: Alarm("witness-" + str(json.load(h).get("alarm")), f"{url} origin {log.origin}")
            except ValueError: Alarm("witness-alarm", url)
        return None
    except (OSError, ValueError): return None
def reconcile(log, urls):
    """On wake or all-clear: push the queued tail to every witness; store a checkpoint only if a quorum co-signed."""
    cosigs = [c for c in (push(log, u) for u in urls) if c]
    try: return log.add_checkpoint(len(log.entries), log.head, cosigs) if log.entries else None
    except Denied: return None

def check_bind(host, allow_loopback=False):
    """Witnesses listen on a tailnet address only. Wildcards, LAN and hostnames are refused; loopback only for tests,
    because reverse proxies can forward to localhost targets."""
    try: ip = ipaddress.ip_address(host)
    except ValueError: raise LedgerError(f"witness bind must be a literal tailnet IP, got {host!r}")
    if ip.is_unspecified: raise LedgerError(f"refusing wildcard bind {host}")
    if ip.is_loopback and allow_loopback: return host
    if not any(ip in n for n in TAILNET): raise LedgerError(f"refusing non-tailnet bind {host}")
    return host

def serve(w, host, port=0, allow_loopback=False, max_body=MAX_BODY):
    host = check_bind(host, allow_loopback)
    class H(BaseHTTPRequestHandler):
        def _send(self, code, obj):
            b = canon(obj); self.send_response(code); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
        def log_message(self, *a): pass
        def do_GET(self):
            o = self.path.partition("origin=")[2]
            if self.path.startswith("/head?") and o.replace("-", "_").isidentifier(): self._send(200, {"size": len(w.replica(o).entries)})
            else: self._send(404, {})
        def do_POST(self):
            n = self.headers.get("Content-Length", "")
            if not n.isdigit(): self.close_connection = True; return self._send(411, {"error": "length required"})
            if int(n) > max_body: self.close_connection = True; return self._send(413, {"error": "body too large", "max": max_body})
            try:
                m = json.loads(self.rfile.read(int(n)))
                if not str(m["origin"]).replace("-", "_").isidentifier(): raise ValueError("origin")
                out = w.add_checkpoint(m["origin"], m["old"], m["entries"], m["size"], m["head"])
                self._send(409 if "conflict" in out else 200, out)
            except Alarm as a: self._send(422, {"alarm": a.code})
            except (LedgerError, ValueError, KeyError, TypeError): self._send(400, {"error": "bad request"})
    class S(ThreadingHTTPServer): address_family = socket.AF_INET6 if ":" in host else socket.AF_INET
    s = S((host, port), H); print(s.server_address[1], flush=True); s.serve_forever()

def main(argv=None):
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="op", required=True)
    sp.add_parser("keygen").add_argument("path")
    for n in ("verify", "gate", "intent", "reconcile", "bundle"):
        p = sp.add_parser(n); p.add_argument("--log", required=True); p.add_argument("--origin", required=True); p.add_argument("--roster", required=True)
        if n == "reconcile": p.add_argument("--witness", action="append", required=True)
        if n == "bundle": p.add_argument("--intent", required=True)
        if n == "intent": p.add_argument("--action", required=True); p.add_argument("--key", required=True); p.add_argument("--writer", required=True)
        if n == "gate":
            p.add_argument("--intent", required=True); p.add_argument("--action", required=True)
            p.add_argument("--claim", action="store_true", help="consume the intent atomically (needs --key/--writer); run the action only on exit 0")
            p.add_argument("--key"); p.add_argument("--writer")
    p = sp.add_parser("serve"); [p.add_argument(f"--{a}", required=True) for a in ("name", "key", "roster", "dir")]; p.add_argument("--port", type=int, default=0)
    p.add_argument("--host", required=True, help="this node's tailnet IP (100.64.0.0/10 or fd7a:115c:a1e0::/48); never 0.0.0.0")
    p.add_argument("--allow-loopback", action="store_true", help="tests only")
    x = ap.parse_args(argv)
    try:
        if x.op == "keygen": k = Ed25519PrivateKey.generate(); save_key(k, x.path); print(pub_hex(k)); return 0
        if x.op == "serve": check_bind(x.host, x.allow_loopback); serve(Witness(x.name, load_key(x.key), load_roster(x.roster), x.dir), x.host, x.port, x.allow_loopback); return 0
        log = Log(x.log, x.origin, load_roster(x.roster))
        if x.op == "verify": print(json.dumps({"size": len(log.entries), "head": log.head, "witnessed": log.witnessed_size()})); return 0
        if x.op == "reconcile":
            with log.locked(): cp = reconcile(log, x.witness)
            print(json.dumps({"size": len(log.entries), "witnessed": log.witnessed_size()})); return 0 if cp else 77
        if x.op == "bundle": print(json.dumps(bundle(log, x.intent), sort_keys=True)); return 0
        if x.op == "intent": print(log.intent(load_key(x.key), x.writer, json.loads(x.action))["hash"]); return 0
        if x.claim:
            if not (x.key and x.writer): raise LedgerError("--claim needs --key and --writer")
            log.claim(load_key(x.key), x.writer, x.intent, json.loads(x.action)); print("claimed"); return 0
        authorize(log, x.intent, json.loads(x.action)); print("allowed"); return 0
    except Denied as d: print(f"DENIED {d}", file=sys.stderr); return 77
    except Alarm as a: print(f"ALARM {a}", file=sys.stderr); return 3 if x.op == "verify" else 77
    except (LedgerError, OSError, ValueError) as ex: print(f"DENIED (fail closed) {type(ex).__name__}: {ex}", file=sys.stderr); return 77

if __name__ == "__main__": sys.exit(main())
