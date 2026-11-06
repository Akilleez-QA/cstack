"""Each in-workcell kernel must agree with its pinned Python Foundation, which stays the reference."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tests/kernels"), str(ROOT / "foundations/refrigeration"), str(ROOT / "foundations/template")]
import vectors  # noqa: E402


class Differential(unittest.TestCase):
    def compare(self, foundation, source, module, root):
        rows = vectors.reference(foundation, source)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "vectors.json")
            path.write_text(json.dumps(rows))
            result = subprocess.run(["node", str(ROOT / "tests/kernels/differential.mjs"), str(ROOT / module), str(ROOT / root), str(path)],
                                    capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["different"], 0, report["first"])
        return report["compared"]

    def test_refrigeration(self):
        self.assertGreater(self.compare("foundation_refrigeration", vectors.refrigeration_vectors(), "adapters/workcell/kernels/refrigeration.mjs", "foundations/refrigeration"), 3000)

    def test_template(self):
        self.assertEqual(self.compare("foundation_template", vectors.template_vectors(), "adapters/workcell/kernels/template.mjs", "foundations/template"), 9)


class Pins(unittest.TestCase):
    def registry(self, id_):
        code = f"import('./adapters/workcell/kernels/registry.mjs').then(async m => {{ const f = await m.loadFoundation({json.dumps(id_)}); console.log(JSON.stringify(f.identity)); }}).catch(e => {{ console.error(e.message); process.exit(9); }});"
        return ["node", "--input-type=module", "-e", code]

    def test_identity_names_the_pin(self):
        result = subprocess.run(self.registry("foundation_refrigeration"), cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        identity = json.loads(result.stdout)
        pin = json.loads((ROOT / "contracts/SOURCE-PINS.json").read_text())["foundation_refrigeration"]
        self.assertEqual(identity["source_manifest_sha256"], pin["source_manifest_sha256"])
        self.assertEqual(identity["route"], "js-port")

    def test_a_changed_projection_refuses_to_load(self):
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory, "repo")
            for name in ("adapters/workcell/kernels", "contracts", "foundations/refrigeration"):
                shutil.copytree(ROOT / name, copy / name)
            target = copy / "foundations/refrigeration/foundation_refrigeration/data/refrigerant-saturation.nh3.json"
            target.write_bytes(target.read_bytes().replace(b'"NH3"', b'"NH4"', 1))
            result = subprocess.run(self.registry("foundation_refrigeration"), cwd=copy, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 9)
        self.assertIn("differs from its manifest", result.stderr)


if __name__ == "__main__":
    unittest.main()
