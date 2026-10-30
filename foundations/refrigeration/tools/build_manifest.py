"""Write SOURCE-MANIFEST.json: every Foundation file except itself and bytecode, with SHA-256.

Run from anywhere: python -B foundations/refrigeration/tools/build_manifest.py
Prints the manifest's own SHA-256, which the cstack adapter pins.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(ROOT.rglob("*")) if p.is_file() and "__pycache__" not in p.parts
             and p.suffix != ".pyc" and p.name != "SOURCE-MANIFEST.json"}
    raw = (json.dumps({"schema": "foundation-refrigeration-source-manifest/1", "version": "0.1.0", "files": files},
                      sort_keys=True, indent=2) + "\n").encode()
    (ROOT / "SOURCE-MANIFEST.json").write_bytes(raw)
    print(json.dumps({"files": len(files), "sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
