import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRS = ROOT / "docs/requirements/requirements.md"
VM = ROOT / "docs/verification/verification-matrix.md"
SDD = ROOT / "docs/architecture/architecture.md"
REQ_HEADING = re.compile(r"^### (REQ-REF-\d{3}) — (.+)$")
REQ_ID = re.compile(r"REQ-REF-\d{3}")
TEST_REF = re.compile(r"(tests/test_\w+\.py)::(\w+)\.(test_\w+)")
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")
FIELDS = ("Rationale:", "Derivation:", "Allocated to:", "Verification:", "Status:")
METHODS = {"T", "A", "I", "D"}
SKIP_DIRS = {".git", "__pycache__", ".venv"}


def requirements(text):
    found, current = {}, None
    for line in text.splitlines():
        match = REQ_HEADING.match(line)
        if match:
            current = match.group(1)
            found[current] = {"name": match.group(2), "lines": []}
        elif line.startswith("## ") or line.startswith("### "):
            current = None
        elif current:
            found[current]["lines"].append(line)
    return found


def collected_tests():
    tests = set()
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                        tests.add("tests/%s::%s.%s" % (path.name, node.name, item.name))
    return tests


def table_rows(text, header_start):
    rows, inside = [], False
    for line in text.splitlines():
        if line.startswith(header_start):
            inside = True
            continue
        if inside:
            if not line.startswith("|"):
                if rows:
                    break
                continue
            if set(line.replace("|", "").strip()) <= {"-", " "}:
                continue
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def slug(heading):
    text = re.sub(r"[`*_]", "", heading.strip().lower())
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def anchors(path):
    found, counts = set(), {}
    fenced = False
    for line in path.read_text().splitlines():
        if line.startswith("```"):
            fenced = not fenced
        if fenced:
            continue
        match = re.match(r"^#{1,6} (.+)$", line)
        if match:
            base = slug(match.group(1))
            number = counts.get(base, 0)
            counts[base] = number + 1
            found.add(base if number == 0 else "%s-%d" % (base, number))
    return found


def markdown_files():
    return sorted(p for p in ROOT.rglob("*.md") if not SKIP_DIRS & set(p.relative_to(ROOT).parts))


def outside_distribution(path):
    ci = ROOT / ".github"
    return not ci.exists() and path.is_relative_to(ci)


def dead_links():
    problems = []
    for path in markdown_files():
        fenced = False
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if line.startswith("```"):
                fenced = not fenced
            if fenced:
                continue
            for target in LINK.findall(line):
                if re.match(r"^[a-z]+:", target):
                    continue
                file_part, _, anchor = target.partition("#")
                resolved = path if not file_part else (path.parent / file_part).resolve()
                relative = path.relative_to(ROOT).as_posix()
                if not resolved.exists() and outside_distribution(resolved):
                    continue
                if not resolved.exists():
                    problems.append("%s:%d: dead link %s" % (relative, number, target))
                elif anchor and resolved.suffix == ".md" and anchor not in anchors(resolved):
                    problems.append("%s:%d: missing anchor %s" % (relative, number, target))
    return problems


def check():
    problems = []
    reqs = requirements(SRS.read_text())
    if not reqs:
        problems.append("SRS: no requirements found")
    for req, body in reqs.items():
        text = "\n".join(body["lines"])
        if " shall " not in text:
            problems.append("%s: no shall statement" % req)
        for field in FIELDS:
            if field not in text:
                problems.append("%s: missing field %s" % (req, field))
        derivation = re.search(r"Derivation: (.+)", text)
        for path in re.findall(r"`([^`]+)`", derivation.group(1) if derivation else ""):
            if not (ROOT / path.split("::")[0]).exists():
                problems.append("%s: derivation path missing: %s" % (req, path))
    tests = collected_tests()
    vm_text = VM.read_text()
    rows = table_rows(vm_text, "| Requirement |")
    traced, referenced = {}, set()
    for row in rows:
        if len(row) < 5 or not REQ_ID.fullmatch(row[0]):
            problems.append("VM: malformed row %s" % row)
            continue
        req, method, target, last = row[0], row[1], row[2], row[4]
        traced.setdefault(req, []).append(method)
        if method not in METHODS:
            problems.append("%s: unknown method %s" % (req, method))
        refs = ["%s::%s.%s" % m for m in TEST_REF.findall(target)]
        if method == "T" and not refs:
            problems.append("%s: test method without a test reference" % req)
        for ref in refs:
            referenced.add(ref)
            if ref not in tests:
                problems.append("%s: referenced test does not exist: %s" % (req, ref))
        if method in {"I", "A"}:
            paths = re.findall(r"`([^`]+)`", target)
            if not paths:
                problems.append("%s: inspection/analysis row names no target" % req)
            for path in paths:
                if not (ROOT / path.split("::")[0]).exists():
                    problems.append("%s: inspection target missing: %s" % (req, path))
        link = re.search(r"\(([^)]+)\)", last)
        if not link or not (VM.parent / link.group(1)).exists():
            problems.append("%s: last result does not link an existing report" % req)
    for req in reqs:
        if req not in traced:
            problems.append("%s: no verification matrix row" % req)
    for req in traced:
        if req not in reqs:
            problems.append("%s: matrix row for unknown requirement" % req)
    supporting = {"%s::%s.%s" % m for row in table_rows(vm_text, "| Test |") for m in TEST_REF.findall(row[0])}
    for ref in sorted(supporting - tests):
        problems.append("VM: supporting test does not exist: %s" % ref)
    for ref in sorted(tests - referenced - supporting):
        problems.append("VM: test traces to no requirement and is not classified: %s" % ref)
    sdd_rows = table_rows(SDD.read_text(), "| Component |")
    allocated = set()
    for row in sdd_rows:
        ids = set(REQ_ID.findall(row[-1]))
        allocated |= ids
        if not ids and "infrastructure" not in row[-1].lower():
            problems.append("SDD: component %s implements no requirement and is not infrastructure" % row[0])
        for req in ids - set(reqs):
            problems.append("SDD: component %s cites unknown %s" % (row[0], req))
    for req in sorted(set(reqs) - allocated):
        problems.append("%s: not allocated to any SDD component" % req)
    problems.extend(dead_links())
    summary = {"requirements": len(reqs), "traced": len(set(reqs) & set(traced)), "tests": len(tests),
               "tests_traced": len(tests & referenced), "tests_supporting": len(tests & supporting),
               "markdown_files": len(markdown_files())}
    return problems, summary


def main():
    problems, summary = check()
    for problem in problems:
        print(problem)
    print("trace: %(requirements)d requirements, %(traced)d traced; %(tests)d tests, %(tests_traced)d traced to "
          "requirements, %(tests_supporting)d supporting; %(markdown_files)d markdown files link-checked" % summary)
    print("%d problem(s)" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
