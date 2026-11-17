"""cstack init (tools/cstack_init.py, adapters/local_setup.py) and the launcher's refusal to run without durable state."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from adapters import local_setup
from adapters.local_setup import SetupError, computer_name, recorded_device, resolve_device, setup, tailnet_hostname
from tests.aor_fixtures import *

ROOT = Path(__file__).resolve().parent.parent
INIT = ROOT / "tools/cstack_init.py"
MCP = ROOT / "tools/cstack_mcp.py"
NO_TAILSCALE = dict(tailnet=lambda: None, gethostname=lambda: "testbox.local")


def two_devices(directory):
    path = write_fleet(directory)
    fleet = json.loads(path.read_text())
    fleet["devices"].append({**fleet["devices"][0], "hostname": "otherbox"})
    path.write_text(json.dumps(fleet))
    return path


def snapshot(root):
    return {p.relative_to(root).as_posix(): (stat.S_IMODE(os.lstat(p).st_mode), p.read_bytes() if p.is_file() else None)
            for p in sorted(root.rglob("*"))}


def mode(path):
    return stat.S_IMODE(os.lstat(path).st_mode)


class Case(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.state = self.dir / "state"
        self.fleet = write_fleet(self.dir)

    def init(self, **kwargs):
        return setup(self.state, kwargs.pop("fleet", self.fleet), **{**NO_TAILSCALE, **kwargs})

    def statuses(self, report):
        return {status for status, _ in report.lines}


@unittest.skipUnless(HAVE_CRYPTO, NO_CRYPTO)
class InitTests(Case):
    def test_fresh_init_creates_private_durable_state(self):
        report = self.init()
        self.assertEqual(report.problems, [])
        self.assertEqual((report.device, report.bots, report.local_witnesses), ("testbox", ("alpha", "beta"), True))
        for folder in (self.state, self.state / "ledger", self.state / "ledger/keys", self.state / "ledger/witnesses",
                       self.state / "alpha", self.state / "beta"):
            self.assertEqual(mode(folder), 0o700, folder)
        files = [p for p in self.state.rglob("*") if p.is_file()]
        self.assertEqual({mode(p) for p in files}, {0o600})
        config = json.loads((self.state / "ledger.json").read_text())
        roster = json.loads((self.state / config["roster"]).read_text())
        self.assertEqual(set(config["writers"]), {"alpha", "beta"})
        self.assertEqual({w["node"] for w in roster["writers"].values()}, {"testbox"})
        self.assertEqual((roster["quorum"], len(roster["witnesses"])), (2, 2))
        self.assertEqual(recorded_device(self.state), "testbox")
        self.assertEqual(json.loads((self.state / "alpha/anchors.json").read_text()), {})

    def test_a_session_built_on_init_state_is_witnessed(self):
        from bootstrap import build_aor_session
        self.assertEqual(self.init().problems, [])
        session = build_aor_session("alpha", state_root=self.state, hostname=resolve_device(self.state),
                                    fleet_path=self.fleet)
        try:
            self.assertEqual(session.ledger_label, "witnessed")
        finally:
            session.close()

    def test_repeat_init_changes_nothing(self):
        self.init()
        before = snapshot(self.state)
        report = self.init()
        self.assertEqual((report.problems, self.statuses(report)), ([], {"ok"}))
        self.assertEqual(snapshot(self.state), before)

    def test_partial_state_is_completed_with_the_keys_already_made(self):
        self.init()
        keys = {p: p.read_bytes() for p in self.state.rglob("*.key")}
        (self.state / "ledger.json").unlink()
        (self.state / "ledger/roster.json").unlink()
        (self.state / "beta/anchors.json").unlink()
        report = self.init()
        self.assertEqual(report.problems, [])
        self.assertEqual({p: p.read_bytes() for p in self.state.rglob("*.key")}, keys)
        self.assertEqual(self.init(write=False).problems, [])

    def test_a_bot_added_later_gets_a_writer_and_old_keys_are_kept(self):
        fleet = json.loads(self.fleet.read_text())
        only_alpha = self.dir / "alpha-only.json"
        only_alpha.write_text(json.dumps({**fleet, "bots": fleet["bots"][:1]}))
        self.init(fleet=only_alpha)
        alpha_key = (self.state / "ledger/keys/alpha.key").read_bytes()
        report = self.init()
        self.assertEqual(report.problems, [])
        self.assertEqual((self.state / "ledger/keys/alpha.key").read_bytes(), alpha_key)
        self.assertIn("beta", json.loads((self.state / "ledger.json").read_text())["writers"])

    def test_loose_folder_and_settings_are_made_private(self):
        self.init()
        os.chmod(self.state, 0o755)
        os.chmod(self.state / "ledger.json", 0o644)
        checked = self.init(write=False)
        self.assertEqual(len(checked.problems), 2)
        self.assertEqual((mode(self.state), mode(self.state / "ledger.json")), (0o755, 0o644))
        report = self.init()
        self.assertEqual((report.problems, "fixed" in self.statuses(report)), ([], True))
        self.assertEqual((mode(self.state), mode(self.state / "ledger.json")), (0o700, 0o600))

    def test_an_exposed_key_is_refused_not_repaired(self):
        self.init()
        key = self.state / "ledger/keys/alpha.key"
        os.chmod(key, 0o644)
        report = self.init()
        self.assertEqual(len(report.problems), 1)
        self.assertIn("may have been copied", report.problems[0])
        self.assertEqual(mode(key), 0o644)

    def test_a_replaced_key_is_refused_and_the_roster_is_kept(self):
        from adapters.witnessed_ledger import ledger_lib
        L = ledger_lib()
        self.init()
        roster = (self.state / "ledger/roster.json").read_bytes()
        key = self.state / "ledger/keys/alpha.key"
        key.unlink()
        L.save_key(L.Ed25519PrivateKey.generate(), str(key))
        report = self.init()
        self.assertEqual(len(report.problems), 1)
        self.assertIn("does not match the ledger roster", report.problems[0])
        self.assertEqual((self.state / "ledger/roster.json").read_bytes(), roster)

    def test_a_linked_state_folder_is_refused(self):
        target = self.dir / "elsewhere"
        target.mkdir(mode=0o700)
        self.state.symlink_to(target)
        report = self.init()
        self.assertIn("not a plain folder", report.problems[0])
        self.assertEqual(list(target.iterdir()), [])

    def test_check_changes_nothing_on_a_fresh_machine(self):
        report = self.init(write=False)
        self.assertIn("is missing", report.problems[0])
        self.assertFalse(self.state.exists())

    def test_check_verifies_recorded_ledger_files_and_reports_tampering(self):
        from bootstrap import build_aor_session
        self.init()
        session = build_aor_session("alpha", state_root=self.state, hostname="testbox", fleet_path=self.fleet,
                                    fleet_mail=None)
        try:
            session.start_goal(domain=DOMAIN, objective=SAMPLE.objective, acceptance_criteria=["Fixture."])
        finally:
            session.close()
        log = self.state / f"ledger/testbox/alpha/{DOMAIN}.jsonl"
        checked = self.init(write=False)
        self.assertEqual(checked.problems, [])
        self.assertRegex(" ".join(text for _, text in checked.lines), r"file\(s\), [1-9]\d* signed entries")
        log.write_text(log.read_text().replace("Fixture", "Forged", 1))
        report = self.init(write=False)
        self.assertEqual(len(report.problems), 1)
        self.assertIn("failed verification", report.problems[0])

    def test_missing_cryptography_is_explained(self):
        with mock.patch.object(local_setup.importlib.util, "find_spec", return_value=None):
            report = self.init()
        self.assertIn("pip install -r requirements.txt", report.problems[-1])
        self.assertFalse((self.state / "ledger.json").exists())


@unittest.skipUnless(HAVE_CRYPTO, NO_CRYPTO)
class DeviceTests(Case):
    def test_tailscale_absent_or_signed_out_gives_no_name(self):
        self.assertIsNone(tailnet_hostname(which=lambda _: None))

        def fails(*args, **kwargs):
            raise subprocess.CalledProcessError(1, args[0])
        self.assertIsNone(tailnet_hostname(which=lambda _: "/usr/bin/tailscale", run=fails))
        out = mock.Mock(stdout=json.dumps({"Self": {"DNSName": "Box-1.tail1234.ts.net."}}))
        self.assertEqual(tailnet_hostname(which=lambda _: "/usr/bin/tailscale", run=lambda *a, **k: out), "box-1")

    def test_computer_name_is_a_valid_device_name(self):
        self.assertEqual(computer_name(lambda: "My_Mac.Local"), "my-mac")
        self.assertEqual(computer_name(lambda: "___"), "local")

    def test_without_tailscale_the_computer_name_is_recorded(self):
        report = self.init(fleet=two_devices(self.dir))
        self.assertEqual((report.problems, recorded_device(self.state)), ([], "testbox"))

    def test_without_tailscale_a_one_device_fleet_supplies_the_name(self):
        report = self.init(gethostname=lambda: "laptop")
        self.assertEqual((report.problems, recorded_device(self.state)), ([], "testbox"))
        self.assertIn("'laptop' is not listed", " ".join(text for _, text in report.lines))

    def test_tailscale_name_is_used_when_present(self):
        report = self.init(fleet=two_devices(self.dir), tailnet=lambda: "otherbox")
        self.assertEqual(recorded_device(self.state), "otherbox")
        self.assertEqual(report.problems, [])

    def test_an_unlisted_name_is_a_problem_and_is_not_recorded(self):
        report = self.init(fleet=two_devices(self.dir), gethostname=lambda: "laptop")
        self.assertIn("no device by that name", report.problems[0])
        self.assertIsNone(recorded_device(self.state))
        self.assertFalse((self.state / "ledger.json").exists())

    def test_device_flag_overrides_and_is_validated(self):
        fleet = two_devices(self.dir)
        self.init(fleet=fleet)
        self.assertEqual(self.init(fleet=fleet, device="otherbox").problems, [])
        self.assertEqual(recorded_device(self.state), "otherbox")
        self.assertIn("not a device name", self.init(fleet=fleet, device="Bad/Name").problems[0])

    def test_resolve_prefers_the_recorded_name_then_tailscale(self):
        self.state.mkdir()
        with self.assertRaisesRegex(SetupError, "cstack_init.py"):
            resolve_device(self.state, tailnet=lambda: None)
        self.assertEqual(resolve_device(self.state, tailnet=lambda: "tailbox"), "tailbox")
        self.init()
        self.assertEqual(resolve_device(self.state, tailnet=lambda: "tailbox"), "testbox")
        (self.state / "device.json").write_text("{}")
        with self.assertRaisesRegex(SetupError, "damaged"):
            resolve_device(self.state)


class LauncherTests(Case):
    def serve(self, *extra, env=None):
        frames = ['{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}',
                  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"aor","arguments":{}}}']
        return subprocess.run([sys.executable, "-B", str(MCP), "--aor", "alpha", "--state-root", str(self.state),
                               "--fleet", str(self.fleet), *extra], cwd=ROOT, text=True, capture_output=True,
                              timeout=120, input="\n".join(frames) + "\n", env=env)

    def test_launcher_refuses_without_durable_state_and_names_the_fix(self):
        proc = self.serve("--device", "testbox")
        self.assertEqual((proc.returncode, proc.stdout), (2, ""))
        self.assertIn("python -B tools/cstack_init.py --state-root", proc.stderr)
        self.assertIn("--allow-memory-ledger", proc.stderr)
        self.assertFalse(self.state.exists())

    def test_memory_ledger_needs_the_explicit_development_flag(self):
        proc = self.serve("--device", "testbox", "--allow-memory-ledger")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        aor = json.loads(json.loads(proc.stdout.splitlines()[-1])["result"]["content"][0]["text"])
        self.assertTrue(aor["ledger"].startswith("memory (not durable"))

    @unittest.skipUnless(HAVE_CRYPTO, NO_CRYPTO)
    def test_after_init_the_launcher_starts_witnessed_without_tailscale_or_device_flag(self):
        self.assertEqual(self.init().problems, [])
        env = {**os.environ, "PATH": str(self.dir)}
        proc = self.serve(env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        aor = json.loads(json.loads(proc.stdout.splitlines()[-1])["result"]["content"][0]["text"])
        self.assertEqual((aor["device"], aor["ledger"]), ("testbox", "witnessed"))

    def test_generated_bot_profiles_never_allow_the_memory_ledger(self):
        spec = importlib.util.spec_from_file_location("agent_profiles_under_test", ROOT / "tools/agent_profiles.py")
        profiles = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(profiles)
        from adapters.aor_registry import load_fleet
        for fleet in (self.fleet, ROOT / "aors/fleet.json"):
            files = profiles.build(load_fleet(fleet), ROOT, "/usr/bin/uv", None)
            self.assertTrue(files)
            for rel, text in files.items():
                self.assertNotIn("--allow-memory-ledger", text, rel)


@unittest.skipUnless(HAVE_CRYPTO, NO_CRYPTO)
class CommandTests(Case):
    def run_init(self, *extra):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch.object(local_setup, "tailnet_hostname", lambda: None), \
                mock.patch.object(local_setup.socket, "gethostname", lambda: "testbox"):
            spec = importlib.util.spec_from_file_location("cstack_init_under_test", INIT)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            code = module.main(["--state-root", str(self.state), "--fleet", str(self.fleet), *extra])
        return code, out.getvalue()

    def test_command_prints_a_plain_summary_and_next_steps(self):
        code, out = self.run_init("--check")
        self.assertEqual(code, 1)
        self.assertIn("Not ready", out)
        code, out = self.run_init()
        self.assertEqual(code, 0)
        self.assertIn("Ready. Bots: alpha, beta. Device: testbox.", out)
        self.assertIn(f"python -B tools/cstack_mcp.py --aor alpha --state-root {self.state}", out)
        self.assertIn("local keys on this machine", out)
        self.assertEqual(self.run_init("--check")[0], 0)


if __name__ == "__main__":
    unittest.main()
