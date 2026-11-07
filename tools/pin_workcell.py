"""Record the hash of every file in adapters/workcell in contracts/SOURCE-PINS.json. A reviewed step, like any pin change."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREE = ROOT / "adapters/workcell"


def main():
    path = ROOT / "contracts/SOURCE-PINS.json"
    pins = json.loads(path.read_text())
    files = {p.relative_to(TREE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(TREE.rglob("*")) if p.is_file()}
    pins["workcell_runtime"] = {"root": "adapters/workcell", "files": files}
    path.write_text(json.dumps(pins, indent=1) + "\n")
    print(json.dumps({"files": len(files)}))


if __name__ == "__main__":
    main()
