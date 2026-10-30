"""No client, customer or maker names in the Foundation (hashed term store), and an exact source manifest."""
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DENYLIST = ROOT / "tests" / "denylist"
MIN_PART, MAX_PART, MAX_PHRASE = 4, 40, 4


def _terms():
    files = [json.loads(p.read_text()) for p in sorted(DENYLIST.glob("*.sha256.json"))]
    salt = files[0]["salt"]
    if any(f["salt"] != salt for f in files):
        raise ValueError("Term files must share one salt")
    merged = {key: set().union(*(set(f[key]) for f in files)) for key in ("word", "anywhere", "phraseHeads", "phrases")}
    return salt, merged


def scan(text, terms=None):
    """Python port of the reference app scripts/check-denylist.mjs createScanner (hashes only, no plaintext)."""
    salt, sets = terms or _terms()
    digest = lambda value: hashlib.sha256((salt + "\n" + value).encode()).hexdigest()  # noqa: E731
    lower = text.lower()
    hits = [m.group(0) for m in re.finditer(r"[a-z0-9_]+", lower) if digest(m.group(0)) in sets["word"]]
    tokens = [m.group(0) for m in re.finditer(r"[a-z0-9]+", lower)]
    for index, token in enumerate(tokens):
        parts = [token] + [piece for size in range(MIN_PART, min(len(token) - 1, MAX_PART) + 1)
                           for piece in (token[:size], token[-size:])]
        if any(digest(part) in sets["anywhere"] for part in parts):
            hits.append(token)
        if digest(token) in sets["phraseHeads"]:
            for size in range(2, MAX_PHRASE + 1):
                phrase = " ".join(tokens[index:index + size])
                if index + size <= len(tokens) and digest(phrase) in sets["phrases"]:
                    hits.append(phrase)
    return hits


def foundation_files():
    return sorted(p for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                  and p.suffix != ".pyc" and p.name != "SOURCE-MANIFEST.json")


class NameTests(unittest.TestCase):
    def test_term_store_is_hashes_only(self):
        for path in DENYLIST.glob("*.sha256.json"):
            data = json.loads(path.read_text())
            for key, values in data.items():
                if key != "salt":
                    self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}", v) for v in values), path.name)

    def test_scanner_port_finds_a_known_hashed_term(self):
        salt, sets = _terms()
        h = lambda v: hashlib.sha256((salt + "\n" + v).encode()).hexdigest()  # noqa: E731
        sets["word"].add(h("zq"))
        sets["anywhere"].add(h("qxprobe"))
        sets["phraseHeads"].add(h("north"))
        sets["phrases"].add(h("north probe"))
        hits = scan("A zq line about Qxprobeworks and the North Probe site.", (salt, sets))
        self.assertEqual(sorted(hits), ["north probe", "qxprobeworks", "zq"])
        self.assertEqual(scan("A plain line.", (salt, sets)), [])

    def test_no_denylisted_names_in_any_foundation_file(self):
        for path in foundation_files():
            if path.parent == DENYLIST:
                continue
            with self.subTest(file=str(path.relative_to(ROOT))):
                self.assertEqual(scan(path.read_text(errors="replace")), [])


class ManifestTests(unittest.TestCase):
    def test_source_manifest_is_exact(self):
        manifest = json.loads((ROOT / "SOURCE-MANIFEST.json").read_text())
        self.assertEqual(manifest["schema"], "foundation-refrigeration-source-manifest/1")
        actual = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in foundation_files()}
        self.assertEqual(manifest["files"], actual)


if __name__ == "__main__":
    unittest.main()
