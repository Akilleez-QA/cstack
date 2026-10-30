#!/usr/bin/env python3
"""Poller all-clear proof (DECISION-004): lowering to L0 needs a ledger bundle that verifies offline against the rig roster;
bad or missing proof with SHIELDS_LEDGER_ENFORCE=1 holds the level and alarms; raising never needs one.
Run: python3 poller/test_ledger_proof.py  (needs `cryptography` for ledger.py; no network, fake engine)."""
import base64, hashlib, importlib.util, json, os, sys, tempfile, time, types, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER_PY = os.path.join(HERE, "..", "..", "ledger", "ledger.py")
sys.path.insert(0, os.path.dirname(LEDGER_PY))
import ledger as L  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

WITNESSES = ("host-a", "host-b", "pi")


def load(env):
    os.environ.update(env)
    spec = importlib.util.spec_from_file_location("poller", os.path.join(HERE, "shields-poller.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Proof(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.k = {n: Ed25519PrivateKey.generate() for n in ("box-bot", *WITNESSES)}
        self.roster = {"quorum": 2, "witnesses": {n: L.pub_hex(self.k[n]) for n in WITNESSES},
                       "writers": {"box-bot": {"pub": L.pub_hex(self.k["box-bot"]), "node": "box"}}}
        with open(self.p("roster.json"), "w") as f:
            json.dump(self.roster, f)
        self.w = {n: L.Witness(n, self.k[n], self.roster, self.p("w-" + n)) for n in WITNESSES}
        self.log = L.Log(self.p("box.jsonl"), "box", self.roster)
        self.level, self.calls, self.sent, self.seq = 2, [], [], 0

    def tearDown(self):
        for v in ("SHIELDS_LEDGER_ENFORCE", "LEDGER_ALARMS"):
            os.environ.pop(v, None)

    def p(self, *a):
        return os.path.join(self.d, *a)

    def proof(self, scope=("box", "host-a"), witnesses=("host-b", "pi"), ts=None):
        if ts:  # intent written "ts" seconds since epoch (ledger.py reads time only through its module global)
            with mock.patch.object(L, "time", types.SimpleNamespace(time=lambda: ts)):
                return self.proof(scope, witnesses)
        act = {"op": "all-clear", "scope": sorted(scope)}
        e = self.log.intent(self.k["box-bot"], "box-bot", act)
        cos = []
        for n in witnesses:
            old = len(self.w[n].replica("box").entries)
            cos.append(self.w[n].add_checkpoint("box", old, self.log.entries[old:], len(self.log.entries), self.log.head)["cosig"])
        if len(witnesses) < 2:  # below quorum: the log refuses it, so hand-build the bundle a forger would send
            return {"action": act, "bundle": {"intent": e, "chain": [e], "checkpoint": {"size": e["seq"], "head": e["hash"], "cosigs": cos}}}
        self.log.add_checkpoint(len(self.log.entries), self.log.head, cos)
        return {"action": act, "bundle": L.bundle(self.log, e["hash"])}

    def poller(self, enforce=False, ledger_py=LEDGER_PY):
        m = load({"SHIELDS_POLLER_STATE": self.p("ps"), "SHIELDS_BOARD_URL": "http://127.0.0.1:9", "SHIELDS_MACHINE": "host-a",
                  "SHIELDS_LEDGER_PY": ledger_py, "SHIELDS_LEDGER_ROSTER": self.p("roster.json"),
                  "LEDGER_ALARMS": self.p("alarms.jsonl"), "SHIELDS_LEDGER_ENFORCE": "1" if enforce else "0"})
        m.ledger_checkin = lambda payload: None  # heartbeat writer/transport covered in test_checkin.py
        m.local_level = lambda: (self.level, 0)
        m.fingerprint = lambda: "fp"
        m.verify = lambda k, resp, st: (resp["payload"], None)  # HMAC path is covered by selftest.sh

        def engine(*a):
            self.calls.append(a)
            if a[0] == "restore":
                self.level = 0
            elif a[0] == "up":
                self.level = int(a[1])
            return 0, ""
        m.engine = engine
        return m

    def tick(self, m, level, ledger=None):
        self.seq += 1
        n = int(time.time())
        resp = {"payload": {"machine": "host-a", "level": level, "seq": self.seq, "decision_id": f"shd-{self.seq}",
                            "issued_at": n, "expires_at": n + 86400, "rollback_min": 60, "served_at": n}, "sig": "x"}
        if ledger is not None:
            resp["ledger"] = ledger
        m.http = lambda method, url, body=None: resp if method == "GET" else self.sent.append(body["payload"]) or {"ok": True}
        m.tick(b"k")
        return self.sent[-1]

    def alarms(self):
        if not os.path.exists(self.p("alarms.jsonl")):
            return []
        with open(self.p("alarms.jsonl")) as f:
            return [json.loads(x)["reason"] for x in f]

    def test_raise_never_needs_a_proof(self):
        self.level = 0
        m = self.poller(enforce=True)
        self.assertEqual(self.tick(m, 2)["outcome"], "applied")
        self.assertEqual((self.level, self.alarms()), (2, []))
        self.assertEqual(self.tick(m, 1)["outcome"], "applied")  # 2 -> 1 is still shields up: no proof
        self.assertEqual(self.level, 1)

    def test_enforced_all_clear_without_proof_holds_and_alarms(self):
        m = self.poller(enforce=True)
        c = self.tick(m, 0)
        self.assertEqual((c["outcome"], c["reason"], c["level"]), ("held", "ledger:absent", 2))
        self.assertEqual((self.level, self.calls, self.alarms()), (2, [], ["absent"]))

    def test_enforced_all_clear_with_valid_proof_lowers_once(self):
        m = self.poller(enforce=True)
        pr = self.proof()
        c = self.tick(m, 0, pr)
        self.assertEqual((c["outcome"], c["ledger_note"], self.level), ("applied", "ok", 0))
        self.level = 2  # shields raised again; the board replays the same proof under a new decision
        c = self.tick(m, 0, pr)
        self.assertEqual((c["outcome"], c["reason"], self.level), ("held", "ledger:intent-already-used", 2))

    def test_enforced_bad_proofs_hold(self):
        m = self.poller(enforce=True)
        bad = self.proof()
        bad["bundle"]["intent"]["body"] = {"digest": "0" * 64}
        cases = [(self.proof(scope=("box",)), "wrong-action"), (self.proof(witnesses=("pi",)), "intent-not-witnessed-by-quorum"),
                 (bad, "bad-signature"), (self.proof(ts=int(time.time()) - 2 * 86400), "stale-intent"), ({"x": 1}, "wrong-action")]
        for pr, why in cases:
            c = self.tick(m, 0, pr)
            self.assertEqual((c["outcome"], c["reason"]), ("held", f"ledger:{why}"), why)
        self.assertEqual((self.level, self.calls), (2, []))
        self.assertEqual(len(self.alarms()), len(cases))

    def test_missing_verifier_fails_safe(self):
        m = self.poller(enforce=True, ledger_py=self.p("nope.py"))
        c = self.tick(m, 0, self.proof())
        self.assertEqual((c["outcome"], self.level), ("held", 2))
        self.assertTrue(c["reason"].startswith("ledger:verifier-unavailable"))

    def test_log_only_default_lowers_but_reports(self):
        m = self.poller(enforce=False)
        c = self.tick(m, 0)
        self.assertEqual((c["outcome"], c["ledger_note"], self.level, self.alarms()), ("applied", "log-only:absent", 0, []))


class PhoneCosign(Proof):
    """the owner's phone co-sign rides beside the proof; SHIELDS_COSIGN_ENFORCE=1 makes it mandatory for all-clear."""
    def setUp(self):
        super().setUp()
        from cryptography.hazmat.primitives.asymmetric import ec
        self.ec, self.pk = ec, ec.generate_private_key(ec.SECP256R1())
        spki = self.pk.public_key().public_bytes(L.ser.Encoding.DER, L.ser.PublicFormat.SubjectPublicKeyInfo)
        self.roster["cosigners"] = {"owner-phone": {"credentialId": "cred-1", "spki": base64.b64encode(spki).decode(),
                                                    "rpId": "shields.example.com", "origins": ["https://shields.example.com"]}}
        with open(self.p("roster.json"), "w") as f:
            json.dump(self.roster, f)

    def tearDown(self):
        os.environ.pop("SHIELDS_COSIGN_ENFORCE", None)
        super().tearDown()

    def cosign(self, intent, scope=("box", "host-a"), nonce="0" * 32, flags=0x05):
        u = lambda x: base64.urlsafe_b64encode(x).decode().rstrip("=")
        b = {"intent": intent, "scope": sorted(scope), "nonce": nonce, "exp": int(time.time()) + 300}
        cd = json.dumps({"type": "webauthn.get", "challenge": u(L.cosign_challenge(**b)), "origin": "https://shields.example.com"}).encode()
        ad = hashlib.sha256(b"shields.example.com").digest() + bytes([flags, 0, 0, 0, 1])
        sg = self.pk.sign(ad + hashlib.sha256(cd).digest(), self.ec.ECDSA(L.hashes.SHA256()))
        return {**b, "credentialId": "cred-1", "authenticatorData": u(ad), "clientDataJSON": u(cd), "signature": u(sg)}

    def tick_cs(self, m, pr, cs):
        self.seq += 1
        n = int(time.time())
        resp = {"payload": {"machine": "host-a", "level": 0, "seq": self.seq, "decision_id": f"shd-{self.seq}", "issued_at": n,
                            "expires_at": n + 86400, "rollback_min": 60, "served_at": n}, "sig": "x", "ledger": pr}
        if cs is not None:
            resp["cosign"] = cs
        m.http = lambda method, url, body=None: resp if method == "GET" else self.sent.append(body["payload"]) or {"ok": True}
        m.tick(b"k")
        return self.sent[-1]

    def test_enforced_cosign(self):
        os.environ["SHIELDS_COSIGN_ENFORCE"] = "1"
        m = self.poller(enforce=True)
        pr = self.proof()
        h = pr["bundle"]["intent"]["hash"]
        for cs, why in ((None, "absent"), (self.cosign("cd" * 32), "binding-mismatch"), (self.cosign(h, flags=1), "needs-user-presence-and-verification"),
                        (self.cosign(h, scope=("box",)), "wrong-scope-or-credential")):
            c = self.tick_cs(m, pr, cs)
            self.assertEqual((c["outcome"], c["reason"], self.level), ("held", f"cosign:{why}", 2), why)
        c = self.tick_cs(m, pr, self.cosign(h))
        self.assertEqual((c["outcome"], c["ledger_note"], self.level), ("applied", "ok cosign:ok", 0))
        with open(self.p("alarms.jsonl")) as f:
            self.assertIn("poller-cosign-hold", [json.loads(x)["code"] for x in f])

    def test_cosign_off_by_default_only_reports(self):
        m = self.poller(enforce=True)
        pr = self.proof()
        c = self.tick_cs(m, pr, None)
        self.assertEqual((c["outcome"], c["ledger_note"]), ("applied", "ok"))  # no co-sign, not enforced: unchanged behavior
        self.level = 2
        c = self.tick_cs(m, self.proof(), self.cosign("cd" * 32))
        self.assertEqual((c["outcome"], c["ledger_note"]), ("applied", "ok cosign:log-only:binding-mismatch"))


if __name__ == "__main__":
    unittest.main()
