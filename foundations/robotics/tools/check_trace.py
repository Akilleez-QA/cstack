import ast
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SRS = ROOT / "docs/requirements/requirements.md"
VM = ROOT / "docs/verification/verification-matrix.md"
SDD = ROOT / "docs/architecture/architecture.md"
REQ = re.compile(r"REQ-ROB-\d{3}")
HEADING = re.compile(r"^### (REQ-ROB-\d{3}) ", re.M)
FIELD = re.compile(r"^- (Derivation|Allocated to|Verification|Status): (.+)$", re.M)
TICKED = re.compile(r"`([^`]+)`")
LINK = re.compile(r"\]\(([^)\s]+)\)")
COMPONENT = re.compile(r"^\| (C-[A-Z-]+) \| (.+?) \| .+ \| (.+?) \|$", re.M)
METHODS = {"T", "A", "I", "D"}


def requirements():
    text = SRS.read_text(encoding="utf-8")
    found = {}
    starts = [(m.group(1), m.start()) for m in HEADING.finditer(text)]
    for (rid, start), (_, end) in zip(starts, starts[1:] + [(None, len(text))]):
        if rid in found:
            raise SystemExit(f"duplicate requirement heading {rid}")
        found[rid] = dict(FIELD.findall(text[start:end]))
    return found


def tests():
    found = {}
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                methods = {f.name for f in node.body if isinstance(f, ast.FunctionDef) and f.name.startswith("test_")}
                if methods:
                    found[f"tests/{path.name}::{node.name}"] = methods
    return found


def matrix_rows():
    rows, unlinked = [], []
    section = "matrix"
    for line in VM.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = "unlinked" if line.startswith("## Tests without a requirement") else "other"
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if section == "matrix" and REQ.fullmatch(cells[0]):
            rows.append(cells)
        elif section == "unlinked" and cells[0].startswith("`tests/"):
            unlinked.append(TICKED.findall(cells[0])[0])
    return rows, unlinked


def expand(reference, inventory):
    if "::" not in reference:
        return None
    path, _, name = reference.partition("::")
    cls, _, method = name.partition(".")
    key = f"{path}::{cls}"
    if key not in inventory or (method and method not in inventory[key]):
        return None
    return {f"{key}.{m}" for m in ([method] if method else inventory[key])}


def components():
    text = SDD.read_text(encoding="utf-8")
    return {cid: (TICKED.findall(paths), cell) for cid, paths, cell in COMPONENT.findall(text)}


def slug(heading):
    text = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return text.replace(" ", "-")


def anchors(path):
    seen, result = {}, set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            base = slug(line.lstrip("#"))
            count = seen.get(base, 0)
            seen[base] = count + 1
            result.add(base if count == 0 else f"{base}-{count}")
    return result


def outside_distribution(path):
    ci = ROOT / ".github"
    return not ci.exists() and path.is_relative_to(ci)


def links():
    problems = []
    for doc in sorted(ROOT.rglob("*.md")):
        if ".git" in doc.parts:
            continue
        text = re.sub(r"```.*?```", "", doc.read_text(encoding="utf-8"), flags=re.S)
        for target in LINK.findall(text):
            if re.match(r"[a-z]+:", target):
                continue
            file_part, _, anchor = target.partition("#")
            resolved = (doc.parent / file_part).resolve() if file_part else doc
            if not resolved.exists() and outside_distribution(resolved):
                continue
            if not resolved.exists():
                problems.append(f"{doc.relative_to(ROOT)}: dead link {target}")
            elif anchor and resolved.suffix == ".md" and anchor not in anchors(resolved):
                problems.append(f"{doc.relative_to(ROOT)}: dead anchor {target}")
    return problems


def check():
    problems = []
    reqs = requirements()
    inventory = tests()
    rows, unlinked = matrix_rows()
    comps = components()
    covered = set()
    rowed = {}
    for cells in rows:
        rid, method, target = cells[0], cells[1], cells[2]
        rowed.setdefault(rid, []).append(cells)
        if rid not in reqs:
            problems.append(f"matrix row for unknown requirement {rid}")
        methods = {m.strip() for m in method.split(",")}
        if not methods <= METHODS:
            problems.append(f"{rid}: unknown method {method}")
        refs = TICKED.findall(target)
        if not refs:
            problems.append(f"{rid}: matrix row names no test or inspection target")
        test_refs = 0
        for ref in refs:
            if ref.startswith("tests/"):
                expanded = expand(ref, inventory)
                if expanded is None:
                    problems.append(f"{rid}: matrix names missing test {ref}")
                else:
                    covered |= expanded
                    test_refs += 1
            elif not (ROOT / ref.split("::")[0]).exists():
                problems.append(f"{rid}: inspection target does not exist: {ref}")
        if "T" in methods and test_refs == 0:
            problems.append(f"{rid}: method T but no test named")
    for rid, fields in reqs.items():
        if fields.get("Status", "").startswith("Deleted"):
            continue
        for name in ("Derivation", "Allocated to", "Verification", "Status"):
            if name not in fields:
                problems.append(f"{rid}: missing field {name}")
        for path in TICKED.findall(fields.get("Derivation", "")):
            if not (ROOT / path).exists():
                problems.append(f"{rid}: derivation path does not exist: {path}")
        if rid not in rowed:
            problems.append(f"{rid}: no verification-matrix row")
        allocated = re.findall(r"C-[A-Z-]+", fields.get("Allocated to", ""))
        if not allocated:
            problems.append(f"{rid}: allocated to no SDD component")
        for cid in allocated:
            if cid not in comps:
                problems.append(f"{rid}: allocated to unknown component {cid}")
            elif rid not in comps[cid][1]:
                problems.append(f"{rid}: component {cid} does not list it")
    for cid, (paths, cell) in comps.items():
        if not REQ.search(cell) and "infrastructure" not in cell:
            problems.append(f"component {cid} implements no requirement and is not marked infrastructure")
        for rid in REQ.findall(cell):
            if rid not in reqs:
                problems.append(f"component {cid} lists unknown requirement {rid}")
        for path in paths:
            if not (ROOT / path).exists():
                problems.append(f"component {cid} path does not exist: {path}")
    for ref in unlinked:
        expanded = expand(ref, inventory)
        if expanded is None:
            problems.append(f"unlinked-test table names missing test {ref}")
        else:
            covered |= expanded
    every = {f"{key}.{m}" for key, methods in inventory.items() for m in methods}
    for name in sorted(every - covered):
        problems.append(f"test traces to no requirement and is not listed as supporting: {name}")
    problems += links()
    summary = {"requirements": len(reqs), "matrix_rows": len(rows), "tests": len(every),
               "tests_traced": len(every & covered), "components": len(comps), "problems": len(problems)}
    return problems, summary


def main():
    problems, summary = check()
    for problem in problems:
        print(problem, file=sys.stderr)
    print(json.dumps(summary, sort_keys=True))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
