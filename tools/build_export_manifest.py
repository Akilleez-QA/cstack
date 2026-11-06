import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    argparse.ArgumentParser(description="Write EXPORT-MANIFEST.json, listing every file git tracks with its hash and size.").parse_args()
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.split("\0")
    files = {}
    for path in (ROOT / name for name in sorted(filter(None, tracked))):
        if not path.is_file() or path.name == "EXPORT-MANIFEST.json":
            continue
        raw = path.read_bytes()
        files[path.relative_to(ROOT).as_posix()] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    manifest = {"schema": "your-org/cstack-export-listing/1", "license": "GPL-3.0-only", "files": files}
    (ROOT / "EXPORT-MANIFEST.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"{len(files)} files")


if __name__ == "__main__":
    main()
