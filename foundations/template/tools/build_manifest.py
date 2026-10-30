"""Write SOURCE-MANIFEST.json: every Foundation file except itself and bytecode, with SHA-256.

Run from anywhere: python -B foundations/template/tools/build_manifest.py
Prints the manifest's SHA-256 and file count and the canonical tool inventory's SHA-256: the three pins in
the host adapter. With --inventory, prints the canonical inventory itself for the host's schemas/ copy.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from foundation_template_bridge.schemas import tool_definitions  # noqa: E402


def canonical_inventory():
    return json.dumps(tool_definitions(), ensure_ascii=True, allow_nan=False, sort_keys=True,
                      separators=(",", ":")).encode("ascii")


def main():
    if sys.argv[1:] == ["--inventory"]:
        sys.stdout.buffer.write(canonical_inventory() + b"\n")
        return
    files = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(ROOT.rglob("*")) if p.is_file() and "__pycache__" not in p.parts
             and p.suffix != ".pyc" and p.name != "SOURCE-MANIFEST.json"}
    raw = (json.dumps({"schema": "foundation-template-source-manifest/1", "version": "0.1.0", "files": files},
                      sort_keys=True, indent=2) + "\n").encode()
    (ROOT / "SOURCE-MANIFEST.json").write_bytes(raw)
    print(json.dumps({"files": len(files), "sha256": hashlib.sha256(raw).hexdigest(),
                      "inventory_sha256": hashlib.sha256(canonical_inventory()).hexdigest()}))


if __name__ == "__main__":
    main()
