"""codex-guard.sh ledger gate (DECISION-004). Run: python3 -m unittest -v products/hmi/shields/test_codex_guard.py
Needs the ledger prototype (products/hmi/ledger) with single-use claims (gate --claim)."""
import json, os, subprocess, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ledger"))
import ledger as L
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

GUARD = os.path.join(HERE, "lib", "codex-guard.sh")
WIT = ("host-a", "host-b", "pi")

class Guard(unittest.TestCase):
    def setUp(self):
        if any(os.path.exists(m) for m in ("/workspace/ops/shields/CODEX_BLOCKED", "/var/lib/shields/CODEX_BLOCKED")):
            self.skipTest("shields are up on this host (CODEX_BLOCKED): the guard exits 75 before the ledger gate")
        self.d = tempfile.mkdtemp(); p = lambda n: os.path.join(self.d, n); self.p = p
        self.k = {n: Ed25519PrivateKey.generate() for n in ("box-bot", *WIT)}
        self.roster = {"quorum": 2, "witnesses": {n: L.pub_hex(self.k[n]) for n in WIT},
                       "writers": {"box-bot": {"pub": L.pub_hex(self.k["box-bot"]), "node": "box"}}}
        with open(p("roster.json"), "w") as f: json.dump(self.roster, f)
        L.save_key(self.k["box-bot"], p("box.key"))
        self.marker = p("ran")
        # The guard runs `codex` only, so the stand-in it launches must be basenamed codex (it writes the marker).
        self.codex = p("codex")
        with open(self.codex, "w") as f:
            f.write(f"#!/bin/sh\nprintf x >> {self.marker}\n")
        os.chmod(self.codex, 0o755)
        self.argv = [self.codex]
        self.env = {"PATH": os.environ["PATH"], "LEDGER_LOG": p("box.jsonl"), "LEDGER_ORIGIN": "box", "LEDGER_ROSTER": p("roster.json"),
                    "LEDGER_KEY": p("box.key"), "LEDGER_WRITER": "box-bot", "LEDGER_GUARD_LOG": p("guard.log")}
    def log(self): return L.Log(self.p("box.jsonl"), "box", self.roster)
    def intent(self, argv, witnessed=True):
        log = self.log(); e = log.intent(self.k["box-bot"], "box-bot", {"op": "codex", "argv": argv})
        if witnessed:
            ws = [L.Witness(n, self.k[n], self.roster, self.p("w-" + n)) for n in WIT[:2]]
            log.add_checkpoint(len(log.entries), log.head, [w.add_checkpoint("box", 0, log.entries, len(log.entries), log.head)["cosig"] for w in ws])
        return e["hash"]
    def run_guard(self, **env):
        r = subprocess.run(["bash", GUARD, *self.argv], env={**self.env, **env}, capture_output=True, text=True, timeout=30)
        ran = os.path.exists(self.marker)
        if ran: os.remove(self.marker)
        return r.returncode, ran, r.stderr
    def test_default_is_log_only_and_runs(self):
        rc, ran, err = self.run_guard()
        self.assertEqual((rc, ran), (0, True)); self.assertIn("log-only: no intent supplied", err)
        rc, ran, err = self.run_guard(LEDGER_INTENT="0" * 64)
        self.assertEqual((rc, ran), (0, True)); self.assertIn("would DENY", err)
        h = self.intent(self.argv); rc, ran, err = self.run_guard(LEDGER_INTENT=h)
        self.assertEqual((rc, ran), (0, True)); self.assertIn("would allow", err)
        self.assertFalse([e for e in self.log().entries if e["kind"] == "claim"])  # log-only never consumes
    def test_enforce_without_intent_or_env_refuses_77(self):
        rc, ran, err = self.run_guard(LEDGER_ENFORCE="1"); self.assertEqual((rc, ran), (77, False)); self.assertIn("LEDGER_INTENT not set", err)
        h = self.intent(self.argv)
        rc, ran, _ = self.run_guard(LEDGER_ENFORCE="1", LEDGER_INTENT=h, LEDGER_KEY=""); self.assertEqual((rc, ran), (77, False))
        rc, ran, _ = self.run_guard(LEDGER_ENFORCE="1", LEDGER_INTENT=h, LEDGER_PY="/nonexistent/ledger.py"); self.assertEqual((rc, ran), (77, False))
    def test_enforce_unwitnessed_or_wrong_argv_refuses_77(self):
        h = self.intent(self.argv, witnessed=False)
        rc, ran, err = self.run_guard(LEDGER_ENFORCE="1", LEDGER_INTENT=h); self.assertEqual((rc, ran), (77, False)); self.assertIn("not-witnessed", err)
        h2 = self.intent(self.argv + ["--extra"])
        rc, ran, err = self.run_guard(LEDGER_ENFORCE="1", LEDGER_INTENT=h2); self.assertEqual((rc, ran), (77, False)); self.assertIn("digest-mismatch", err)
    def test_enforce_witnessed_runs_once_then_77(self):
        h = self.intent(self.argv)
        rc, ran, err = self.run_guard(LEDGER_ENFORCE="1", LEDGER_INTENT=h); self.assertEqual((rc, ran), (0, True), err)
        rc, ran, err = self.run_guard(LEDGER_ENFORCE="1", LEDGER_INTENT=h); self.assertEqual((rc, ran), (77, False)); self.assertIn("already-used", err)
        with open(self.p("guard.log")) as f: self.assertIn("claimed", f.read())
    def test_concurrent_enforced_launches_one_wins(self):
        h = self.intent(self.argv); env = {**self.env, "LEDGER_ENFORCE": "1", "LEDGER_INTENT": h}
        ps = [subprocess.Popen(["bash", GUARD, *self.argv], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for _ in range(6)]
        self.assertEqual(sorted(p.wait(30) for p in ps), [0] + [77] * 5)
        with open(self.marker) as f: self.assertEqual(f.read(), "x")
    def test_guard_refuses_a_non_codex_program(self):
        r = subprocess.run(["bash", GUARD, "claude", "-p", "x"], env={"PATH": os.environ["PATH"]},
                           capture_output=True, text=True, timeout=15)
        self.assertEqual(r.returncode, 76, r.stderr)
        self.assertIn("launches codex only", r.stderr)

    def test_intent_cli_prints_hash_that_the_guard_accepts_after_witnessing(self):
        act = json.dumps({"op": "codex", "argv": self.argv})
        r = subprocess.run([sys.executable, os.path.join(HERE, "..", "ledger", "ledger.py"), "intent", "--log", self.p("box.jsonl"), "--origin", "box",
                            "--roster", self.p("roster.json"), "--key", self.p("box.key"), "--writer", "box-bot", "--action", act], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr); h = r.stdout.strip(); self.assertEqual(len(h), 64)
        self.assertEqual(self.log().entries[-1]["hash"], h)

if __name__ == "__main__": unittest.main()
