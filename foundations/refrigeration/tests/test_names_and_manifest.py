import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def foundation_files():
    return sorted(p for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts and ".git" not in p.parts
                  and p.relative_to(ROOT).parts[0] != ".github" and p.suffix != ".pyc" and p.name not in ("SOURCE-MANIFEST.json", "PR_BODY.md"))


class ManifestTests(unittest.TestCase):
    def test_source_manifest_is_exact(self):
        manifest = json.loads((ROOT / "SOURCE-MANIFEST.json").read_text())
        self.assertEqual(manifest["schema"], "foundation-refrigeration-source-manifest/1")
        actual = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in foundation_files()}
        self.assertEqual(manifest["files"], actual)


if __name__ == "__main__":
    unittest.main()
