#!/usr/bin/env python3
"""HTTP receipts and signed ledger heartbeats; temporary keys/directories, no network.
Run: python3 poller/test_checkin.py (uses ledger.py's existing cryptography dependency)."""
import hashlib, hmac, importlib.util, io, json, os, tempfile, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))


def load(env):
    os.environ.update(env)
    spec = importlib.util.spec_from_file_location("poller", os.path.join(HERE, "shields-poller.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class CheckinTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = tmp.name
        env = mock.patch.dict(os.environ, {}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.p = load({"SHIELDS_POLLER_STATE": self.d, "SHIELDS_BOARD_URL": "http://127.0.0.1:9", "SHIELDS_MACHINE": "box",
                       "SHIELDS_LEDGER_PY": os.path.join(HERE, "../../ledger/ledger.py"),
                       "LEDGER_ORIGIN": "box", "LEDGER_LOG": os.path.join(self.d, "box.jsonl"),
                       "LEDGER_KEY": os.path.join(self.d, "writer.key"), "LEDGER_WRITER": "box-bot",
                       "LEDGER_ROSTER": os.path.join(self.d, "roster.json"),
                       "LEDGER_WITNESSES": "http://witness", "LEDGER_ALARMS": os.path.join(self.d, "alarms.jsonl")})
        spec = importlib.util.spec_from_file_location("test_ledger", self.p.LEDGER_PY)
        self.L = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.L)
        keys = {n: self.L.Ed25519PrivateKey.generate() for n in ("box-bot", "host-a", "pi")}
        self.roster = {"writers": {"box-bot": {"node": "box", "pub": self.L.pub_hex(keys["box-bot"])}},
                       "witnesses": {n: self.L.pub_hex(keys[n]) for n in ("host-a", "pi")}, "quorum": 2}
        self.L.save_key(keys["box-bot"], os.environ["LEDGER_KEY"])
        with open(os.environ["LEDGER_ROSTER"], "w") as f:
            json.dump(self.roster, f)
        self.witness = self.L.Witness("host-a", keys["host-a"], self.roster, os.path.join(self.d, "witness"))
        # Exercise push's actual serialization and witness verification without sockets.
        self.requests = []
        def transport(request, **kwargs):
            self.requests.append(request)
            if isinstance(request, str):
                return io.BytesIO(json.dumps({"size": len(self.witness.replica("box").entries)}).encode())
            p = json.loads(request.data)
            result = self.witness.add_checkpoint(p["origin"], p["old"], p["entries"], p["size"], p["head"])
            return io.BytesIO(json.dumps(result).encode())
        self.L.urlopen = transport
        self.p.verifier = lambda path, roster: (self.L, self.L.load_roster(roster))
        self.sent = []
        self.p.http = lambda method, url, body=None: self.sent.append((method, url, body)) or {"ok": True}
        self.k = os.urandom(32)

    def entries(self):
        return self.L.Log(os.environ["LEDGER_LOG"], "box", self.roster).entries

    def alarms(self):
        with open(os.environ["LEDGER_ALARMS"]) as f:
            return [json.loads(line)["code"] for line in f]

    def checkin_at(self, ts, **changes):
        with mock.patch.object(self.p.time, "time", return_value=ts):
            self.p.checkin(self.k, **{"level": 1, "outcome": "noop", **changes})

    def test_signed_and_monotonic(self):
        for _ in range(3):
            self.p.checkin(self.k, level=1, outcome="noop", decision_id="none", seq_applied=0)
        seqs, nonces = [], set()
        for method, url, body in self.sent:
            self.assertEqual((method, url), ("POST", "http://127.0.0.1:9/api/checkin"))
            p = body["payload"]
            want = hmac.new(self.k, json.dumps(p, sort_keys=True, separators=(",", ":")).encode(), hashlib.sha256).hexdigest()
            self.assertEqual(body["sig"], want)  # cseq + nonce are inside the HMAC
            self.assertRegex(p["nonce"], r"^[0-9a-f]{32}$")
            seqs.append(p["cseq"]); nonces.add(p["nonce"])
        self.assertEqual(seqs, sorted(set(seqs)))
        self.assertEqual(len(nonces), 3)

    def test_state_loss_still_moves_forward(self):
        self.p.checkin(self.k, outcome="noop")
        first = self.sent[-1][2]["payload"]["cseq"]
        os.remove(os.path.join(self.d, "checkin-seq"))
        self.p.checkin(self.k, outcome="noop")
        self.assertGreater(self.sent[-1][2]["payload"]["cseq"], first - 1000)  # time floor, not reset to 1

    def test_no_board_url_holds(self):
        m = load({"SHIELDS_BOARD_URL": ""})
        self.assertEqual(m.BOARD, "")
        with open(os.path.join(HERE, "shields-poller.py")) as f:
            self.assertNotIn("example-owner", f.read())

    def test_signed_entry_and_witness_reader(self):
        self.checkin_at(1000, reason="HTTP only", decision_id="none")
        entries = self.entries()  # reader verifies signature, hash, writer and chain against the roster
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["kind"], "checkin")
        payload = self.sent[0][2]["payload"]
        self.assertEqual(entries[0]["body"], {n: payload[n] for n in ("machine", "level", "outcome", "cseq", "ts")})
        self.assertEqual(self.witness.replica("box").entries, entries)
        self.assertEqual(len(self.requests), 2)

    def test_default_interval_and_restart(self):
        self.checkin_at(1000)
        m = load({})  # rate limit comes from the signed log, not process memory
        m.http, m.verifier = self.p.http, self.p.verifier
        self.p = m
        self.checkin_at(1299)
        self.assertEqual(len(self.entries()), 1)
        self.assertEqual(len(self.requests), 2)
        self.checkin_at(1300)
        self.assertEqual(len(self.entries()), 2)
        self.assertEqual(len(self.sent), 3)

    def test_configured_interval(self):
        os.environ["SHIELDS_LEDGER_CHECKIN_SEC"] = "10"
        for ts in (1000, 1009, 1010):
            self.checkin_at(ts)
        self.assertEqual([e["body"]["ts"] for e in self.entries()], [1000, 1010])

    def test_level_and_outcome_changes_write_immediately(self):
        self.checkin_at(1000)
        self.checkin_at(1001, level=2)
        self.checkin_at(1002, level=2, outcome="held")
        self.assertEqual(len(self.entries()), 3)

    def test_write_failure_keeps_http_and_level_even_enforcing(self):
        os.environ["LEDGER_ENFORCE"] = "1"
        os.environ["LEDGER_KEY"] = os.path.join(self.d, "missing.key")
        self.p.local_level = lambda: (2, 0)
        self.p.engine = mock.Mock(side_effect=AssertionError("must hold"))
        post = self.p.http
        def http(method, url, body=None):
            if method == "GET":
                raise OSError("offline")
            return post(method, url, body)
        self.p.http = http
        self.p.tick(self.k)
        self.assertEqual((self.sent[0][2]["payload"]["level"], self.sent[0][2]["payload"]["outcome"]), (2, "held"))
        self.assertEqual(self.p.local_level()[0], 2)
        self.p.engine.assert_not_called()
        self.assertIn("poller-ledger-checkin-write", self.alarms())
        self.assertEqual(self.requests, [])

    def test_push_failure_retries_tail_on_next_heartbeat(self):
        with mock.patch.object(self.L, "urlopen", side_effect=OSError("offline")):
            self.checkin_at(1000)
        self.assertEqual(len(self.entries()), 1)
        self.assertIn("poller-ledger-checkin-push", self.alarms())
        self.checkin_at(1001)
        self.assertEqual(len(self.entries()), 1)
        self.checkin_at(1300)
        self.assertEqual(len(self.sent), 3)
        self.assertEqual(self.witness.replica("box").entries, self.entries())

    def test_write_failure_does_not_block_raise(self):
        os.environ["LEDGER_KEY"] = os.path.join(self.d, "missing.key")
        self.p.LEDGER_ENFORCE = True
        self.p.local_level = mock.Mock(side_effect=[(0, 0), (2, 1000)])
        self.p.engine = mock.Mock(return_value=(0, "status"))
        payload = {"machine": "box", "level": 2, "seq": 1, "decision_id": "raise",
                   "issued_at": 1000, "served_at": 1000, "expires_at": 2000}
        post = self.p.http
        self.p.http = lambda method, url, body=None: (
            {"payload": payload, "sig": self.p.sig(self.k, payload)} if method == "GET" else post(method, url, body))
        with mock.patch.object(self.p.time, "time", return_value=1000):
            self.p.tick(self.k)
        self.p.engine.assert_any_call("up", "2", "--rollback-min", "60")
        receipt = self.sent[0][2]["payload"]
        self.assertEqual((receipt["level"], receipt["outcome"]), (2, "applied"))
        self.assertEqual(self.p.load_state()["last_verified_level"], 2)
        self.assertIn("poller-ledger-checkin-write", self.alarms())

    def test_http_failure_still_writes_and_pushes(self):
        self.p.http = mock.Mock(side_effect=OSError("offline"))
        self.checkin_at(1000)
        self.assertEqual(len(self.witness.replica("box").entries), 1)

    def test_alarm_failure_is_nonfatal(self):
        os.environ["LEDGER_KEY"] = os.path.join(self.d, "missing.key")
        self.p.LEDGER_ALARMS = os.path.join(self.d, "missing", "alarms")
        self.checkin_at(1000)
        self.assertEqual(len(self.sent), 1)

    def test_wrong_origin_and_missing_witness_alarm(self):
        os.environ["LEDGER_ORIGIN"] = "host-a"
        self.checkin_at(1000)
        self.assertEqual(self.entries(), [])
        self.assertIn("poller-ledger-checkin-write", self.alarms())
        os.environ["LEDGER_ORIGIN"] = "box"
        os.environ["LEDGER_WITNESSES"] = ""
        self.checkin_at(1001)
        self.assertEqual(len(self.entries()), 1)
        self.assertIn("poller-ledger-checkin-push", self.alarms())


if __name__ == "__main__":
    unittest.main()
