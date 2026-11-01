import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = {}
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or any(part in {".git", "__pycache__"} for part in path.parts):
            continue
        if path.suffix == ".pyc" or path.name == "EXPORT-MANIFEST.json":
            continue
        raw = path.read_bytes()
        files[path.relative_to(ROOT).as_posix()] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    manifest = {"schema": "your-org/cstack-export-listing/1", "license": "GPL-3.0-only", "files": files}
    (ROOT / "EXPORT-MANIFEST.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"{len(files)} files")


if __name__ == "__main__":
    main()
