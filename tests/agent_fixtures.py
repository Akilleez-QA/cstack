import json
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STARTERS = ("archivist", "chief", "keeper", "lab", "oracle", "sage", "scribe", "smith", "warden")


def copy_tree(case):
    tmp = Path(tempfile.mkdtemp(prefix="cstack-agents-")).resolve()
    case.addCleanup(shutil.rmtree, tmp, True)
    shutil.copytree(ROOT / "agents", tmp / "agents")
    (tmp / "aors").mkdir()
    shutil.copy(ROOT / "aors/fleet.json", tmp / "aors/fleet.json")
    return tmp


def edit_json(path, change):
    document = json.loads(path.read_text())
    change(document)
    path.write_text(json.dumps(document, indent=2))


def edit_front(path, change):
    text = path.read_text()
    head, front, rest = text.split("---\n", 2)
    document = json.loads(front)
    change(document)
    path.write_text(f"{head}---\n{json.dumps(document, indent=2)}\n---\n{rest}")
