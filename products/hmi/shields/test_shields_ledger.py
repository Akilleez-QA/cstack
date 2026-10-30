"""shields-up / all-clear ledger hooks (lib/ledger-gate.sh, DECISION-004).
Run: python3 -m unittest -v products/hmi/shields/test_shields_ledger.py   (needs ledger single-use claims)"""
import json, os, subprocess, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
LPY = os.path.join(HERE, "..", "ledger", "ledger.py")
sys.path.insert(0, os.path.dirname(LPY))
import ledger as L
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

WIT = ("host-a", "host-b", "pi")
ALL_CLEAR = {"op": "all-clear", "scope": ["box", "host-a"]}

class Hooks(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.p = lambda n: os.path.join(self.d, n)
        self.k = {n: Ed25519PrivateKey.generate() for n in ("box-bot", *WIT)}
        self.roster = {"quorum": 2, "witnesses": {n: L.pub_hex(self.k[n]) for n in WIT},
                       "writers": {"box-bot": {"pub": L.pub_hex(self.k["box-bot"]), "node": "box"}}}
        with open(self.p("roster.json"), "w") as f: json.dump(self.roster, f)
        L.save_key(self.k["box-bot"], self.p("box.key"))
        self.cfg = {"LEDGER_LOG": self.p("box.jsonl"), "LEDGER_ORIGIN": "box", "LEDGER_ROSTER": self.p("roster.json"),
                    "LEDGER_KEY": self.p("box.key"), "LEDGER_WRITER": "box-bot"}
    def hook(self, call, **env):
        sh = f'say(){{ echo "$*"; }}; . lib/ledger-gate.sh; {call}; echo "rc=$?"'
        r = subprocess.run(["bash", "-c", sh], cwd=HERE, env={"PATH": os.environ["PATH"], **env}, capture_output=True, text=True, timeout=60)
        return int(r.stdout.strip().rsplit("rc=", 1)[1]), r.stdout + r.stderr
    def log(self): return L.Log(self.p("box.jsonl"), "box", self.roster)
    def entries(self, kind): return [e for e in self.log().entries if e["kind"] == kind] if os.path.exists(self.p("box.jsonl")) else []
    def intent(self, act=ALL_CLEAR, witnessed=True):
        log = self.log(); e = log.intent(self.k["box-bot"], "box-bot", act)
        if witnessed:
            ws = [L.Witness(n, self.k[n], self.roster, self.p("w-" + n)) for n in WIT[:2]]
            log.add_checkpoint(len(log.entries), log.head, [w.add_checkpoint("box", 0, log.entries, len(log.entries), log.head)["cosig"] for w in ws])
        return e["hash"]
    def spawn(self, name):  # tolerant of whether witness hardening (serve --host) is applied
        kp = self.p(name + ".key"); L.save_key(self.k[name], kp)
        extra = ["--host", "127.0.0.1", "--allow-loopback"] if hasattr(L, "check_bind") else []
        pr = subprocess.Popen([sys.executable, LPY, "serve", "--name", name, "--key", kp, "--roster", self.p("roster.json"), "--dir", self.p("srv-" + name), *extra],
                              stdout=subprocess.PIPE, text=True)
        self.addCleanup(pr.stdout.close); self.addCleanup(pr.wait); self.addCleanup(pr.terminate)
        return f"http://127.0.0.1:{int(pr.stdout.readline())}"

    def test_shields_up_never_blocks(self):
        rc, out = self.hook('ledger_shields_up 2 D1 0'); self.assertEqual(rc, 0); self.assertIn("not configured", out)
        rc, out = self.hook('ledger_shields_up 2 D1 0', **{**self.cfg, "LEDGER_ROSTER": "/nonexistent", "LEDGER_ENFORCE": "1"})
        self.assertEqual(rc, 0); self.assertIn("WARN", out)
    def test_shields_up_writes_local_intent_and_claims_without_quorum(self):
        rc, out = self.hook('ledger_shields_up 1 D7 1', **self.cfg); self.assertEqual(rc, 0, out); self.assertIn("dry_run, not claimed", out)
        rc, out = self.hook('ledger_shields_up 2 D8 0', **self.cfg); self.assertEqual(rc, 0, out); self.assertIn("claimed", out)
        ins = self.entries("intent"); self.assertEqual([i["body"]["op"] for i in ins], ["shields-up", "shields-up"])
        self.assertEqual(ins[0]["body"]["digest"], L.digest({"op": "shields-up", "level": 1, "decision": "D7", "dry_run": True}))
        self.assertEqual([c["ref"] for c in self.entries("claim")], [ins[1]["hash"]]); self.assertEqual(self.log().witnessed_size(), 0)
    def test_all_clear_default_log_only(self):
        rc, out = self.hook('ledger_all_clear 0'); self.assertEqual(rc, 0); self.assertIn("log-only", out)
        h = self.intent(witnessed=False)
        rc, out = self.hook('ledger_all_clear 0', **self.cfg, LEDGER_INTENT=h); self.assertEqual(rc, 0); self.assertIn("would be DENIED", out)
        self.assertFalse(self.entries("claim"))
    def test_all_clear_enforced_denied_without_quorum(self):
        rc, out = self.hook('ledger_all_clear 0', LEDGER_ENFORCE="1"); self.assertEqual(rc, 77)
        rc, _ = self.hook('ledger_all_clear 0', **self.cfg, LEDGER_ENFORCE="1"); self.assertEqual(rc, 77)  # no LEDGER_INTENT
        h = self.intent(witnessed=False)
        rc, out = self.hook('ledger_all_clear 0', **self.cfg, LEDGER_ENFORCE="1", LEDGER_INTENT=h, LEDGER_WITNESSES="http://127.0.0.1:9 http://127.0.0.1:9")
        self.assertEqual(rc, 77); self.assertIn("not-witnessed", out); self.assertIn("board all-clear", out)
        h2 = self.intent({"op": "all-clear", "scope": ["box"]})  # witnessed, but for a different action
        rc, out = self.hook('ledger_all_clear 0', **self.cfg, LEDGER_ENFORCE="1", LEDGER_INTENT=h2); self.assertEqual(rc, 77); self.assertIn("digest-mismatch", out)
    def test_all_clear_enforced_reconciles_then_claims_once(self):
        h = self.intent(witnessed=False); urls = f"{self.spawn('host-a')} {self.spawn('host-b')}"
        env = {**self.cfg, "LEDGER_ENFORCE": "1", "LEDGER_INTENT": h, "LEDGER_WITNESSES": urls}
        rc, out = self.hook('ledger_all_clear 1', **env); self.assertEqual(rc, 0, out); self.assertIn("dry-run, not claimed", out)
        self.assertFalse(self.entries("claim"))
        rc, out = self.hook('ledger_all_clear 0', **env); self.assertEqual(rc, 0, out); self.assertIn("claimed", out)
        rc, out = self.hook('ledger_all_clear 0', **env); self.assertEqual(rc, 77); self.assertIn("already-used", out)
    def test_scripts_call_hooks_before_any_change(self):
        with open(os.path.join(HERE, "all-clear.sh")) as f: ac = f.read()
        self.assertIn('ledger_all_clear "$DRY" || exit 77', ac)
        self.assertLess(ac.index("ledger_all_clear"), ac.index("./ledger.py decision")); self.assertLess(ac.index("ledger_all_clear"), ac.index("shields-local.sh"))
        with open(os.path.join(HERE, "shields-up.sh")) as f: su = f.read()
        line = next(l for l in su.splitlines() if "ledger_shields_up" in l); self.assertNotIn("exit", line.split("#")[0])

if __name__ == "__main__": unittest.main()
