"""Tests for the private witnessed ledger. Run: python3 -m unittest -v products/hmi/ledger/test_ledger.py
Witnesses here stand in for always-on tailnet nodes (host-a + two others). The box is a writer only, never a witness."""
import base64, hashlib, json, os, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger as L
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

HERE = os.path.dirname(os.path.abspath(__file__))
WITNESSES = ("host-a", "host-b", "pi")
UNREACHABLE = "http://127.0.0.1:9"  # discard port: nothing listens, like a sleeping peer

class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); os.environ["LEDGER_ALARMS"] = self.p("alarms.jsonl")
        self.k = {n: Ed25519PrivateKey.generate() for n in ("box-bot", "rig-bot", *WITNESSES)}
        self.roster = {"quorum": 2, "witnesses": {n: L.pub_hex(self.k[n]) for n in WITNESSES},
                       "writers": {"box-bot": {"pub": L.pub_hex(self.k["box-bot"]), "node": "box"},
                                   "rig-bot": {"pub": L.pub_hex(self.k["rig-bot"]), "node": "host-a"}}}
        with open(self.p("roster.json"), "w") as f: json.dump(self.roster, f)
        self.w = {n: L.Witness(n, self.k[n], self.roster, self.p(n)) for n in WITNESSES}
    def tearDown(self): os.environ.pop("LEDGER_ALARMS", None)
    def p(self, *a): return os.path.join(self.d, *a)
    def log(self, origin="box", name="box.jsonl"): return L.Log(self.p(name), origin, self.roster)
    def witness_all(self, log, names=WITNESSES):
        cos = []
        for n in names:
            old = len(self.w[n].replica(log.origin).entries)
            cos.append(self.w[n].add_checkpoint(log.origin, old, log.entries[old:], len(log.entries), log.head)["cosig"])
        return log.add_checkpoint(len(log.entries), log.head, cos)
    def lines(self, name):
        with open(self.p(name)) as f: return f.read().splitlines()
    def rewrite(self, name, lines):
        with open(self.p(name), "w") as f: f.write("\n".join(lines) + "\n")
    def alarms(self): return [json.loads(l)["code"] for l in self.lines("alarms.jsonl")] if os.path.exists(self.p("alarms.jsonl")) else []

class Gate(Base):
    ACT = {"op": "merge", "repo": "cstack", "pr": 42}
    def test_unsigned_action_rejected(self):
        log = self.log()
        with self.assertRaises(L.Denied): L.authorize(log, "f" * 64, self.ACT)
        forged = {"v": 1, "origin": "box", "seq": 1, "prev": L.GENESIS, "writer": "box-bot", "wseq": 1, "kind": "intent",
                  "ts": 0, "body": {"digest": L.digest(self.ACT)}, "ref": None, "sig": ""}
        forged["hash"] = L.sha(L.canon(forged))
        with self.assertRaises(L.Alarm) as c: log.extend([forged])
        self.assertEqual(c.exception.code, "bad-signature")
        e = log.intent(self.k["box-bot"], "box-bot", self.ACT); self.witness_all(log)  # unknown writer key is refused too
        with self.assertRaises(L.Alarm): log.write(Ed25519PrivateKey.generate(), "intruder", "intent", {})
        self.assertEqual(L.authorize(log, e["hash"], self.ACT)["hash"], e["hash"])
    def test_execute_before_intent_and_single_use(self):
        log = self.log(); e = log.intent(self.k["box-bot"], "box-bot", self.ACT); self.witness_all(log)
        with self.assertRaises(L.Denied): L.authorize(log, e["hash"], {**self.ACT, "pr": 43})  # different action
        L.authorize(log, e["hash"], self.ACT); log.result(self.k["box-bot"], "box-bot", e["hash"], "applied")
        with self.assertRaisesRegex(L.Denied, "already-used"): L.authorize(log, e["hash"], self.ACT)
    def test_shields_up_never_blocked_on_quorum_but_all_clear_is(self):
        log = self.log(); up = log.intent(self.k["box-bot"], "box-bot", {"op": "shields-up", "level": 2})
        L.authorize(log, up["hash"], {"op": "shields-up", "level": 2})
        clear = log.intent(self.k["box-bot"], "box-bot", {"op": "all-clear"})
        with self.assertRaises(L.Denied): L.authorize(log, clear["hash"], {"op": "all-clear"})
    def test_cli_gate_exit_codes(self):
        log = self.log(); e = log.intent(self.k["box-bot"], "box-bot", self.ACT)
        args = ["--log", self.p("box.jsonl"), "--origin", "box", "--roster", self.p("roster.json"), "--intent", e["hash"], "--action", json.dumps(self.ACT)]
        self.assertEqual(L.main(["gate", *args]), 77)
        self.witness_all(log); self.assertEqual(L.main(["gate", *args]), 0)
        self.assertEqual(L.main(["gate", *args[:-1], "{not json"]), 77)

class Integrity(Base):
    def test_skipped_writer_sequence_flagged(self):
        log = self.log(); log.write(self.k["box-bot"], "box-bot", "note", {"n": 1})
        e = {"v": 1, "origin": "box", "seq": 2, "prev": log.head, "writer": "box-bot", "wseq": 3,  # wseq 2 dropped/hidden
             "kind": "note", "ts": 0, "body": {"n": 3}, "ref": None}
        e["sig"] = L.sign(self.k["box-bot"], L.canon(e)); e["hash"] = L.sha(L.canon(e))
        with self.assertRaises(L.Alarm) as c: log.extend([e])
        self.assertEqual(c.exception.code, "writer-seq-gap"); self.assertIn("writer-seq-gap", self.alarms())
    def test_tampered_entry_detected_on_reopen(self):
        log = self.log()
        for i in range(3): log.write(self.k["box-bot"], "box-bot", "note", {"n": i})
        lines = self.lines("box.jsonl"); e = json.loads(lines[1]); e["body"]["n"] = 99
        lines[1] = json.dumps(e); self.rewrite("box.jsonl", lines)
        with self.assertRaises(L.Alarm) as c: self.log()
        self.assertEqual(c.exception.code, "bad-signature")
        self.assertEqual(L.main(["verify", "--log", self.p("box.jsonl"), "--origin", "box", "--roster", self.p("roster.json")]), 3)
    def test_deleted_entry_detected(self):
        log = self.log()
        for i in range(3): log.write(self.k["box-bot"], "box-bot", "note", {"n": i})
        lines = self.lines("box.jsonl"); del lines[1]; self.rewrite("box.jsonl", lines)
        with self.assertRaises(L.Alarm) as c: self.log()
        self.assertEqual(c.exception.code, "chain-break")

class Quorum(Base):
    def test_single_node_rewrite_rejected_by_quorum(self):
        rig = self.log("host-a", "rig.jsonl"); act = {"op": "poodo", "goal": "g1"}
        rig.intent(self.k["rig-bot"], "rig-bot", act); rig.write(self.k["rig-bot"], "rig-bot", "note", {"x": "original"})
        self.witness_all(rig, ("host-b", "pi"))
        os.remove(self.p("rig.jsonl")); os.remove(self.p("rig.jsonl.cp"))
        evil = self.log("host-a", "rig.jsonl"); evil.intent(self.k["rig-bot"], "rig-bot", act)
        bad = evil.write(self.k["rig-bot"], "rig-bot", "intent", {"digest": L.digest({"op": "poodo", "goal": "evil"})})
        for n in ("host-b", "pi"):
            with self.assertRaises(L.Alarm) as c: self.w[n].add_checkpoint("host-a", 2, [], 2, evil.head)
            self.assertEqual(c.exception.code, "equivocation")
        own = L.cosign(self.k["host-a"], "host-a", "host-a", 2, evil.head)  # its own witness alone is below quorum
        with self.assertRaises(L.Denied): evil.add_checkpoint(2, evil.head, [own])
        with self.assertRaisesRegex(L.Denied, "not-witnessed"): L.authorize(evil, bad["hash"], {"op": "poodo", "goal": "evil"})
        with self.assertRaises(L.Alarm) as c: self.w["host-b"].compare("host-a", 2, evil.head)
        self.assertEqual(c.exception.code, "fork")
    def test_rollback_and_stale_old_size(self):
        log = self.log()
        for i in range(3): log.write(self.k["box-bot"], "box-bot", "note", {"i": i})
        self.witness_all(log)
        log.write(self.k["box-bot"], "box-bot", "note", {})  # stale `old` with real growth is still only a 409-style conflict
        self.assertEqual(self.w["host-b"].add_checkpoint("box", 0, log.entries, 4, log.head), {"conflict": 3})
        self.assertNotIn("rollback", self.alarms())
        for old in (0, 1, 3):  # presenting a smaller log than the witness verified is a rollback alarm, never a conflict
            with self.assertRaises(L.Alarm) as c: self.w["host-b"].add_checkpoint("box", old, [], 1, log.entries[0]["hash"])
            self.assertEqual(c.exception.code, "rollback")
        self.assertEqual(self.alarms().count("rollback"), 3)
    def test_box_is_not_a_witness(self):
        self.assertNotIn("box", self.roster["witnesses"]); self.assertNotIn("box-bot", self.roster["witnesses"])
        log = self.log(); log.write(self.k["box-bot"], "box-bot", "note", {})
        with self.assertRaises(L.Denied):  # a box-key "cosignature" counts for nothing
            log.add_checkpoint(1, log.head, [L.cosign(self.k["box-bot"], "box", "box", 1, log.head), L.cosign(self.k["pi"], "pi", "box", 1, log.head)])
    def test_roster_requires_two_witnesses(self):
        with open(self.p("bad.json"), "w") as f: json.dump({**self.roster, "quorum": 1}, f)
        with self.assertRaises(L.LedgerError): L.load_roster(self.p("bad.json"))

def _race_claim(path, roster, keyhex, intent, act, barrier, q):
    log = L.Log(path, "box", roster); k = L.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(keyhex))
    barrier.wait()
    try: log.claim(k, "box-bot", intent, act); q.put("won")
    except L.Denied: q.put("denied")

class SingleUse(Base):
    ACT = {"op": "merge", "pr": 9}
    def ready(self):
        log = self.log(); e = log.intent(self.k["box-bot"], "box-bot", self.ACT); self.witness_all(log); return log, e["hash"]
    def keyhex(self): return self.k["box-bot"].private_bytes(L.ser.Encoding.Raw, L.ser.PrivateFormat.Raw, L.ser.NoEncryption()).hex()
    def test_processes_race_exactly_one_wins(self):
        import multiprocessing as mp
        _, h = self.ready(); ctx = mp.get_context("fork"); n = 8; bar, q = ctx.Barrier(n), ctx.Queue()
        ps = [ctx.Process(target=_race_claim, args=(self.p("box.jsonl"), self.roster, self.keyhex(), h, self.ACT, bar, q)) for _ in range(n)]
        for p in ps: p.start()
        for p in ps: p.join(20)
        got = sorted(q.get(timeout=5) for _ in range(n))
        self.assertEqual(got.count("won"), 1, got); self.assertEqual(got.count("denied"), n - 1)
        log = self.log(); self.assertEqual(sum(1 for e in log.entries if e["kind"] == "claim" and e["ref"] == h), 1)
    def test_threads_race_exactly_one_wins(self):
        import queue, threading
        log, h = self.ready(); n = 12; bar, q = threading.Barrier(n), queue.Queue()
        shared = [log if i % 2 else self.log() for i in range(n)]  # one shared Log object and separate ones
        def go(lg):
            bar.wait()
            try: lg.claim(self.k["box-bot"], "box-bot", h, self.ACT); q.put("won")
            except L.Denied: q.put("denied")
        ts = [threading.Thread(target=go, args=(shared[i],)) for i in range(n)]
        for t in ts: t.start()
        for t in ts: t.join(20)
        got = [q.get_nowait() for _ in range(n)]
        self.assertEqual(got.count("won"), 1, got); self.assertEqual(self.log().entries[-1]["kind"], "claim")
    def test_cli_claim_race_and_result_after_claim(self):
        _, h = self.ready(); kp = self.p("box.key"); L.save_key(self.k["box-bot"], kp)
        cmd = [sys.executable, os.path.join(HERE, "ledger.py"), "gate", "--claim", "--key", kp, "--writer", "box-bot", "--log", self.p("box.jsonl"),
               "--origin", "box", "--roster", self.p("roster.json"), "--intent", h, "--action", json.dumps(self.ACT)]
        ps = [subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for _ in range(6)]
        rcs = sorted(p.wait(30) for p in ps); self.assertEqual(rcs, [0] + [77] * 5)
        log = self.log(); log.result(self.k["box-bot"], "box-bot", h, "applied")  # result still recordable after the claim
        with self.assertRaisesRegex(L.Denied, "already-used"): L.authorize(log, h, self.ACT)
    def test_shrunk_log_is_rollback(self):
        log, _ = self.ready(); log.write(self.k["box-bot"], "box-bot", "note", {})
        self.rewrite("box.jsonl", self.lines("box.jsonl")[:1])
        with self.assertRaises(L.Alarm) as c: log.write(self.k["box-bot"], "box-bot", "note", {})
        self.assertEqual(c.exception.code, "rollback")

class Bundle(Base):
    def test_bundle_is_a_self_contained_proof_for_the_board(self):
        log = self.log(); act = {"op": "all-clear", "scope": ["box", "host-a"]}
        e = log.intent(self.k["box-bot"], "box-bot", act)
        with self.assertRaisesRegex(L.Denied, "not-witnessed"): L.bundle(log, e["hash"])
        log.write(self.k["box-bot"], "box-bot", "note", {"x": 1}); self.witness_all(log, ("host-b", "pi"))
        log.write(self.k["box-bot"], "box-bot", "note", {"x": 2}); self.witness_all(log, ("host-a", "pi"))
        b = L.bundle(log, e["hash"])  # smallest quorum checkpoint covering the intent
        self.assertEqual((b["intent"], [x["seq"] for x in b["chain"]], b["checkpoint"]["size"]), (e, [1, 2], 2))
        with self.assertRaisesRegex(L.Denied, "no-intent"): L.bundle(log, log.entries[1]["hash"])
        out = subprocess.run([sys.executable, L.__file__, "bundle", "--log", self.p("box.jsonl"), "--origin", "box",
                              "--roster", self.p("roster.json"), "--intent", e["hash"]], capture_output=True, text=True)
        self.assertEqual((out.returncode, json.loads(out.stdout)), (0, b))
    def test_verify_bundle_matches_ts_verifier(self):
        fx = json.load(open(os.path.join(HERE, "..", "control-board", "tests", "fixtures", "ledger-python.json")))
        for k in ("allClear", "checkin"): L.verify_bundle(fx[k]["bundle"], fx[k]["action"], fx["roster"])
        for k, why in (("unwitnessed", "not-witnessed"), ("used", "already-used")):
            with self.assertRaisesRegex(L.Denied, why): L.verify_bundle(fx[k]["bundle"], fx[k]["action"], fx["roster"])
        with self.assertRaisesRegex(L.Denied, "digest-mismatch"): L.verify_bundle(fx["allClear"]["bundle"], {"op": "all-clear", "scope": ["box"]}, fx["roster"])
        b = json.loads(json.dumps(fx["allClear"]["bundle"])); b["chain"][-1]["body"] = {"x": 9}
        with self.assertRaisesRegex(L.Denied, "bad-signature"): L.verify_bundle(b, fx["allClear"]["action"], fx["roster"])
        for bad in (None, {}, {"intent": {}, "chain": [], "checkpoint": {}}):
            with self.assertRaisesRegex(L.Denied, "no-intent"): L.verify_bundle(bad, fx["allClear"]["action"], fx["roster"])

class PhoneCosign(unittest.TestCase):
    """Synthetic P-256 phone authenticator; challenge bytes pinned to the same vectors as tests/cosign.test.ts."""
    def setUp(self):
        from cryptography.hazmat.primitives.asymmetric import ec
        self.ec, self.key = ec, ec.generate_private_key(ec.SECP256R1())
        spki = self.key.public_key().public_bytes(L.ser.Encoding.DER, L.ser.PublicFormat.SubjectPublicKeyInfo)
        self.c = {"credentialId": "cred-1", "spki": base64.b64encode(spki).decode(), "rpId": "shields.example.com", "origins": ["https://shields.example.com"]}
        self.now, self.H = 1_800_000_000, "ab" * 32
    def make(self, flags=0x05, origin="https://shields.example.com", key=None, exp=None):
        b = {"intent": self.H, "scope": ["box", "host-a"], "nonce": "0" * 32, "exp": exp or self.now + 300}
        u = lambda x: base64.urlsafe_b64encode(x).decode().rstrip("=")
        cd = json.dumps({"type": "webauthn.get", "challenge": u(L.cosign_challenge(**b)), "origin": origin}).encode()
        ad = hashlib.sha256(b"shields.example.com").digest() + bytes([flags]) + (9).to_bytes(4, "big")
        sg = (key or self.key).sign(ad + hashlib.sha256(cd).digest(), self.ec.ECDSA(L.hashes.SHA256()))
        return {**b, "credentialId": "cred-1", "authenticatorData": u(ad), "clientDataJSON": u(cd), "signature": u(sg)}
    def test_vectors_valid_and_rejections(self):
        self.assertEqual(L.cosign_challenge(self.H, ["host-a", "box"], "0" * 32, 1_800_000_300).hex(), "5da0b3197f32128a7251f78335fb8b84f25a49ec14e8936e0a4047797adc8659")
        self.assertEqual(L.cosign_challenge(None, ["box", "host-a"], "0" * 32, 1_800_000_300).hex(), "7311d5a0dd2b96b94220b235155f0e001aa8af6e1da936ce90c6bc27097fc89d")
        self.assertEqual(L.verify_cosign(self.make(), self.H, ["host-a", "box"], self.c, self.now), 9)
        for a, why, h in ((self.make(), "binding-mismatch", "cd" * 32), (self.make(flags=1), "needs-user", self.H),
                          (self.make(origin="https://evil"), "bad-origin", self.H), (self.make(exp=self.now - 1), "expired", self.H),
                          (self.make(key=self.ec.generate_private_key(self.ec.SECP256R1())), "bad-signature", self.H), (None, "absent", self.H)):
            with self.assertRaisesRegex(L.Denied, why): L.verify_cosign(a, h, ["box", "host-a"], self.c, self.now)

class Offline(Base):
    def test_offline_append_then_reconcile(self):
        log = self.log(); act = {"op": "checkin", "board": "hmi"}
        e = log.intent(self.k["box-bot"], "box-bot", act)
        self.assertIsNone(L.reconcile(log, [UNREACHABLE, UNREACHABLE]))  # L2 / box asleep: queue locally, stay denied
        with self.assertRaises(L.Denied): L.authorize(log, e["hash"], act)
        for i in range(3): log.write(self.k["box-bot"], "box-bot", "note", {"queued": i})
        self.witness_all(log, ("host-a", "pi"))  # all-clear: the queued tail reaches the witnesses
        self.assertEqual(log.witnessed_size(), 4); L.authorize(log, e["hash"], act)

class TwoProcess(Base):
    def spawn(self, name):
        kp = self.p(name + ".key"); L.save_key(self.k[name], kp)
        pr = subprocess.Popen([sys.executable, os.path.join(HERE, "ledger.py"), "serve", "--name", name, "--key", kp,
                               "--roster", self.p("roster.json"), "--dir", self.p("srv-" + name), "--host", "127.0.0.1", "--allow-loopback"], stdout=subprocess.PIPE, text=True)
        self.addCleanup(pr.stdout.close); self.addCleanup(pr.wait); self.addCleanup(pr.terminate)
        return pr, f"http://127.0.0.1:{int(pr.stdout.readline())}"
    def test_witness_exchange_over_http_and_fail_closed_when_down(self):
        (p1, u1), (p2, u2) = self.spawn("host-a"), self.spawn("host-b")
        log = self.log(); act = {"op": "merge", "pr": 7}; e = log.intent(self.k["box-bot"], "box-bot", act)
        self.assertIsNotNone(L.reconcile(log, [u1, u2])); L.authorize(log, e["hash"], act)
        e2 = log.intent(self.k["box-bot"], "box-bot", {"op": "merge", "pr": 8})
        p1.terminate(); p1.wait()  # one witness unreachable from the box: below quorum, fail closed
        self.assertIsNone(L.reconcile(log, [u1, u2]))
        with self.assertRaises(L.Denied): L.authorize(log, e2["hash"], {"op": "merge", "pr": 8})
        self.assertEqual(log.witnessed_size(), 1)

class Hardening(Base):
    spawn = TwoProcess.spawn
    def test_bind_policy_refuses_wildcard_lan_and_hostnames(self):
        for bad in ("0.0.0.0", "::", "", "192.168.1.20", "10.0.0.5", "localhost", "host-a", "127.0.0.1"):
            with self.assertRaises(L.LedgerError, msg=bad): L.check_bind(bad)
        from unittest.mock import patch
        with patch.object(L, "TAILNET", (L.ipaddress.ip_network("192.0.2.0/24"), L.TAILNET[1])):
            for ok in ("192.0.2.103", "fd7a:115c:a1e0::1"):
                self.assertEqual(L.check_bind(ok), ok)
        with self.assertRaises(L.LedgerError): L.check_bind("192.0.2.103")
        self.assertEqual(L.check_bind("127.0.0.1", allow_loopback=True), "127.0.0.1")
        with self.assertRaises(L.LedgerError): L.check_bind("0.0.0.0", allow_loopback=True)
        kp = self.p("w.key"); L.save_key(self.k["pi"], kp)
        r = subprocess.run([sys.executable, os.path.join(HERE, "ledger.py"), "serve", "--name", "pi", "--key", kp, "--roster", self.p("roster.json"),
                            "--dir", self.p("srv"), "--host", "0.0.0.0"], capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 77); self.assertIn("wildcard", r.stderr)
    def test_post_body_cap_413_and_length_required(self):
        import http.client
        _, u = self.spawn("host-a"); port = int(u.rsplit(":", 1)[1])
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        c.putrequest("POST", "/add-checkpoint"); c.putheader("Content-Length", str(L.MAX_BODY + 1)); c.endheaders()  # body never sent
        r = c.getresponse(); self.assertEqual(r.status, 413); self.assertEqual(json.loads(r.read())["max"], L.MAX_BODY); c.close()
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        c.putrequest("POST", "/add-checkpoint", skip_accept_encoding=True); c.endheaders()
        r = c.getresponse(); self.assertEqual(r.status, 411); r.read(); c.close()
        log = self.log(); log.write(self.k["box-bot"], "box-bot", "note", {}); self.assertIsNotNone(L.push(log, u))  # normal pushes unaffected
    def test_concurrent_posts_for_one_origin_do_not_fork_the_replica(self):
        import threading
        log = self.log()
        for i in range(5): log.write(self.k["box-bot"], "box-bot", "note", {"i": i})
        bar, out = threading.Barrier(6), []
        def go():
            bar.wait()
            try: out.append(self.w["host-b"].add_checkpoint("box", 0, log.entries, len(log.entries), log.head))
            except L.Alarm as a: out.append({"alarm": a.code})
        ts = [threading.Thread(target=go) for _ in range(6)]
        for t in ts: t.start()
        for t in ts: t.join(20)
        self.assertGreaterEqual(sum("cosig" in o for o in out), 1, out)
        self.assertFalse([o for o in out if "alarm" in o], out)
        self.assertEqual(len(self.w["host-b"].replica("box").entries), 5)  # reopen re-verifies: no duplicate or forked lines

class RollbackHTTP(Base):
    spawn = TwoProcess.spawn
    def test_rolled_back_log_gets_422_rollback_and_local_alarm(self):
        _, u = self.spawn("host-a")
        log = self.log()
        for i in range(3): log.write(self.k["box-bot"], "box-bot", "note", {"i": i})
        self.assertIsNotNone(L.push(log, u))
        self.rewrite("box.jsonl", self.lines("box.jsonl")[:1]); short = self.log()  # attacker or restore truncates the box log
        req = L.Request(f"{u}/add-checkpoint", method="POST", data=L.canon({"origin": "box", "old": 1, "entries": [], "size": 1, "head": short.head}))
        with self.assertRaises(L.HTTPError) as c: L.urlopen(req, timeout=5)
        self.assertEqual(c.exception.code, 422); self.assertEqual(json.load(c.exception)["alarm"], "rollback"); c.exception.close()
        self.assertIsNone(L.push(short, u)); self.assertIn("witness-rollback", self.alarms())

if __name__ == "__main__": unittest.main()
