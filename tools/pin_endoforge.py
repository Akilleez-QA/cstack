"""Rebuild vendor/endoforge from one committed EndoForge revision, and record its pin. No network, no working tree."""
import argparse
import hashlib
import io
import json
import shutil
import subprocess
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/Akilleez-QA/endoforge"
SLICE = ("core/__init__.py", "core/lifecycle.py", "tests/test_endoforge_core_boundary.py",
         "core/ledger/__init__.py", "core/ledger/frozen.py", "core/ledger/ledger.py", "core/ledger/record.schema.json",
         "core/engine/evaluator.mjs", "core/engine/frozen.py", "core/engine/gates.mjs",
         "core/runtime/capacity/cli.mjs", "core/runtime/capacity/controller.mjs", "core/runtime/capacity/index.mjs",
         "core/runtime/capacity/plan.mjs", "core/runtime/capacity/probe.mjs", "core/runtime/capacity/tuner.mjs",
         "core/runtime/isolate-cgroup.mjs", "core/runtime/isolate-ledger.mjs", "core/runtime/isolate-pool.mjs",
         "core/runtime/isolate-wasm-compile.mjs", "core/runtime/isolate-wasm.mjs", "core/runtime/isolate-workcell.mjs",
         "tools/factory_quality/index.mjs", "tools/ledger_writer.py", "LICENSE")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def strip_python_comments(source):
    text = source.decode("utf-8")
    lines = text.splitlines(keepends=True)
    comments = [token.start for token in tokenize.generate_tokens(io.StringIO(text).readline)
                if token.type == tokenize.COMMENT]
    for row, column in comments:
        line = lines[row - 1]
        ending = "\n" if line.endswith("\n") else ""
        lines[row - 1] = line[:column].rstrip() + ending
    return "".join(lines).encode("utf-8")


def build(source, commit, out):
    if out.exists():
        raise SystemExit("The output directory must be absent")
    upstream, files = {}, {}
    for path in SLICE:
        data = subprocess.run(["git", "-C", str(source), "show", f"{commit}:{path}"], check=True, capture_output=True).stdout
        upstream[path] = sha256(data)
        if path.endswith(".py"):
            data = strip_python_comments(data)
        files[path] = sha256(data)
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    manifest = {"schema": "endoforge-source-manifest/1", "repository": REPOSITORY, "commit": commit,
                "strip_python_comments": True, "upstream_files": upstream, "files": files}
    raw = (json.dumps(manifest, indent=1, sort_keys=False) + "\n").encode("ascii")
    (out / "SOURCE-MANIFEST.json").write_bytes(raw)
    return sha256(raw), len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="a clone of EndoForge that holds the commit")
    parser.add_argument("--commit", required=True, help="the full commit hash to pin")
    args = parser.parse_args()
    commit = subprocess.run(["git", "-C", str(args.source), "rev-parse", "--verify", args.commit + "^{commit}"],
                            check=True, capture_output=True, text=True).stdout.strip()
    target = ROOT / "vendor/endoforge"
    fresh = ROOT / "vendor/.endoforge-new"
    digest, count = build(args.source, commit, fresh)
    shutil.rmtree(target)
    fresh.rename(target)
    pins_path = ROOT / "contracts/SOURCE-PINS.json"
    pins = json.loads(pins_path.read_text())
    pins["endoforge"].update(commit=commit, source_manifest_sha256=digest, source_manifest_entry_count=count)
    pins_path.write_text(json.dumps(pins, indent=1) + "\n")
    print(json.dumps({"commit": commit, "source_manifest_sha256": digest, "files": count}))


if __name__ == "__main__":
    main()
