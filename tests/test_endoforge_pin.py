"""The staged Endoforge source must match its recorded identity and file inventory."""
import hashlib
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EndoforgePinTests(unittest.TestCase):
    def test_source_identity_and_exact_membership(self):
        pin = json.loads((ROOT / "contracts/SOURCE-PINS.json").read_text())["endoforge"]
        source = ROOT / pin["root"]
        raw = (source / "SOURCE-MANIFEST.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), pin["source_manifest_sha256"])
        manifest = json.loads(raw)
        self.assertEqual(manifest["commit"], pin["commit"])
        self.assertEqual(len(manifest["files"]), pin["source_manifest_entry_count"])
        actual = {str(p.relative_to(source)) for p in source.rglob("*") if p.is_file()}
        self.assertEqual(actual, set(manifest["files"]) | {"SOURCE-MANIFEST.json"})
        for name, expected in manifest["files"].items():
            self.assertEqual(hashlib.sha256((source / name).read_bytes()).hexdigest(), expected)

    def test_pin_records_whether_it_is_on_main(self):
        pin = json.loads((ROOT / "contracts/SOURCE-PINS.json").read_text())["endoforge"]
        self.assertIs(type(pin.get("on_main")), bool)
        if pin["on_main"]:
            self.assertRegex(pin.get("main_commit", ""), re.compile(r"\A[0-9a-f]{40}\Z"))
            self.assertNotIn("allow_unmerged", pin)
        else:
            self.assertIs(pin.get("allow_unmerged"), True)
            self.assertNotIn("main_commit", pin)

    @unittest.skipUnless(os.environ.get("CSTACK_ENDOFORGE_CLONE"), "set CSTACK_ENDOFORGE_CLONE to a fetched EndoForge clone")
    def test_recorded_main_pin_is_reachable_from_main(self):
        pin = json.loads((ROOT / "contracts/SOURCE-PINS.json").read_text())["endoforge"]
        if not pin["on_main"]:
            self.skipTest("the pin records a deliberate --allow-unmerged exception")
        clone = os.environ["CSTACK_ENDOFORGE_CLONE"]
        for main in (pin["main_commit"], "origin/main"):
            result = subprocess.run(["git", "-C", clone, "merge-base", "--is-ancestor", pin["commit"], main], capture_output=True)
            self.assertEqual(result.returncode, 0, f"{pin['commit']} is not reachable from {main} in {clone}")

    def test_upstream_import_boundary(self):
        result = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"],
                                cwd=ROOT / "vendor/endoforge", capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
