import argparse
import datetime
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import check_trace
from build_manifest import canonical_inventory

START = re.compile(r"^(test_\w+) \(([\w.]+)\)")
OUTCOME = re.compile(r" \.\.\. (ok|FAIL|ERROR|skipped.*|expected failure|unexpected success)$")
RAN = re.compile(r"^Ran (\d+) tests? in ", re.M)
SEVERITY = ["ok", "expected failure", "skipped", "unexpected success", "FAIL", "ERROR"]


def rank(outcome):
    return SEVERITY.index("skipped" if outcome.startswith("skipped") else outcome)


def parse(stderr):
    results = {}
    key = None
    for line in stderr.splitlines():
        if line.startswith(("=" * 10, "-" * 10)):
            break
        start = START.match(line)
        if start:
            name, where = start.groups()
            parts = where.split(".")
            cls = parts[-2] if parts[-1] == name else parts[-1]
            module = parts[1] if parts[0] == "tests" else parts[0]
            key = f"tests/{module}.py::{cls}.{name}"
        outcome = OUTCOME.search(line)
        if key and outcome:
            found = outcome.group(1)
            if key not in results or rank(found) > rank(results[key]):
                results[key] = found
    ran = RAN.search(stderr)
    return results, int(ran.group(1)) if ran else None


def assess(suites, problems, manifest_current):
    gates = []
    for command, code, results, _tail, _digest, ran in suites:
        if code != 0:
            gates.append(f"`{command}` exited {code}")
        if ran is None or ran != len(results) or not results:
            gates.append(f"`{command}` reported {ran} tests but {len(results)} outcomes were parsed")
        counts = {}
        for outcome in results.values():
            if outcome != "ok":
                label = "skipped" if outcome.startswith("skipped") else outcome
                counts[label] = counts.get(label, 0) + 1
        gates += [f"`{command}` had {n} {label}" for label, n in sorted(counts.items())]
    if problems:
        gates.append(f"trace check failed with {len(problems)} problems")
    if not manifest_current:
        gates.append("SOURCE-MANIFEST.json does not match the working tree")
    if gates:
        return "NOT PASSED: " + "; ".join(gates) + " (see sections 3 and 4)", gates
    return "all suites passed with every test ok in both modes; trace check passed; manifest current", gates


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def run_suite(optimized):
    command = [sys.executable, "-B", *(["-O"] if optimized else []), "-m", "unittest", "discover", "-s", "tests",
               "-t", ".", "-v"]
    proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    results, ran = parse(proc.stderr)
    tail = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else ""
    digest = hashlib.sha256(proc.stderr.encode()).hexdigest()
    return " ".join(["python", *command[1:]]), proc.returncode, results, tail, digest, ran


def gh(*args):
    if shutil.which("gh") is None:
        return None
    proc = subprocess.run(["gh", *args], cwd=ROOT, capture_output=True, text=True)
    return json.loads(proc.stdout) if proc.returncode == 0 else None


def trace_map():
    inventory = check_trace.tests()
    rows, _ = check_trace.matrix_rows()
    mapping = {}
    for cells in rows:
        for ref in check_trace.TICKED.findall(cells[2]):
            for test in check_trace.expand(ref, inventory) or ():
                mapping.setdefault(test, set()).add(cells[0])
    return mapping


def lines(patterns):
    total = 0
    for pattern in patterns:
        for path in ROOT.glob(pattern):
            if "__pycache__" not in path.parts:
                total += len(path.read_text(encoding="utf-8").splitlines())
    return total


def manifest_state():
    raw = (ROOT / "SOURCE-MANIFEST.json").read_bytes()
    recorded = json.loads(raw)["files"]
    actual = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(ROOT.rglob("*")) if p.is_file() and "__pycache__" not in p.parts and ".git" not in p.parts
              and p.relative_to(ROOT).parts[0] != ".github" and p.suffix != ".pyc" and p.name != "SOURCE-MANIFEST.json"}
    return {"files": len(recorded), "sha256": hashlib.sha256(raw).hexdigest(), "current": recorded == actual,
            "inventory_sha256": hashlib.sha256(canonical_inventory()).hexdigest(),
            "version": json.loads(raw)["version"]}


def header(doc_id, title, label, date, commit):
    return [f"# foundation-robotics {title} {label}", "", "| Field | Value |", "|---|---|",
            f"| Document ID | {doc_id} |", "| Version | 1.0 |", "| Status | Draft |", "| Owner | Akilleez-QA |",
            f"| Date | {date} |", f"| Baseline commit | {commit} |",
            f"| Applies to | foundation-robotics main at baseline commit (label `{label}`; no release tag exists) |",
            "| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |", "",
            "> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_"
            "&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the "
            "[NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance)"
            " documentation guidance. This is not a NASA compliance determination or certification. The software "
            "classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent "
            "verification and validation, or hazard analysis is asserted. The document describes the implementation "
            "inspected at the baseline commit.", "",
            f"Generated by `python -B tools/gen_reports.py --label {label}`. Do not edit by hand; regenerate.", ""]


def footer(date, commit):
    return ["", "## Change history", "", "| Version | Date | Commit | Change | Reviewed in |", "|---|---|---|---|---|",
            f"| 1.0 | {date} | {commit[:7]} | Generated | docs/nasa-standard PR |", ""]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    commit = git("rev-parse", "HEAD")
    dirty = git("status", "--porcelain", "--untracked-files=no")
    date = datetime.date.today().isoformat()
    try:
        import importlib.metadata
        import jsonschema
        schema_validation = f"active (jsonschema {importlib.metadata.version(jsonschema.__name__)})"
    except ImportError:
        schema_validation = "inactive (jsonschema not installed; output-schema validation in tests/test_tools.py skipped)"
    suites = [run_suite(False), run_suite(True)]
    problems, trace = check_trace.check()
    mapping = trace_map()
    manifest = manifest_state()
    open_issues = gh("issue", "list", "--state", "open", "--json", "number,title,labels")
    closed_issues = gh("issue", "list", "--state", "closed", "--json", "number")
    merged = gh("pr", "list", "--state", "merged", "--limit", "200", "--json", "number,reviews")
    tags = git("tag", "--list")
    env = f"{platform.system()} {platform.machine()}, Python {platform.python_version()}"

    str_lines = header(f"FROBO-STR-{args.label.upper()}", "software test report", args.label, date, commit)
    conclusion, failed = assess(suites, problems, manifest["current"])
    str_lines += ["## 1. Summary", "",
                  f"- Conclusion: {conclusion}.",
                  f"- Output-schema validation inside the suite: {schema_validation}.",
                  "- Remaining deficiencies: the untested behaviour listed in SRS §8 (GAP-ROB-*) is not exercised by "
                  "any test.",
                  f"- Working tree at run time: {'clean' if not dirty else 'tracked changes present'}.", "",
                  "## 2. Test log", "", "| Item | Value |", "|---|---|", f"| Commit | `{commit}` |",
                  f"| Tags | {tags or 'none'} |", f"| Date | {date} |", f"| Environment | {env} |",
                  "| Run by | operator, local run of `tools/gen_reports.py` |"]
    for command, code, results, tail, digest, ran in suites:
        str_lines.append(f"| `{command}` | exit {code}; {ran} tests reported, {len(results)} outcomes parsed; {tail}; "
                         f"stderr SHA-256 `{digest[:16]}` |")
    str_lines += ["", "## 3. Results", "", "| Test | Requirements | Normal | `-O` |", "|---|---|---|---|"]
    names = sorted(set(suites[0][2]) | set(suites[1][2]))
    for name in names:
        reqs = ", ".join(sorted(mapping.get(name, ()))) or "supporting"
        str_lines.append(f"| `{name}` | {reqs} | {suites[0][2].get(name, 'not run')} | "
                         f"{suites[1][2].get(name, 'not run')} |")
    str_lines += ["", "## 4. Problems and deviations", ""]
    deviations = [f"| `{n}` | {s[2].get(n, 'not run')} |" for s in suites for n in names if s[2].get(n) != "ok"]
    str_lines += (["| Test | Outcome |", "|---|---|"] + deviations) if deviations else ["None recorded in this run."]
    str_lines += ([""] + [f"- Gate not passed: {gate}." for gate in failed]) if failed else []
    str_lines += ["", "## 5. Metrics", "", "| Measure | Value | Command |", "|---|---|---|",
                  f"| Tests run (normal / -O) | {len(suites[0][2])} / {len(suites[1][2])} | unittest discover -v |",
                  "| Tests failed, errored or unexpectedly passed | "
                  f"{sum(1 for s in suites for v in s[2].values() if v in ('FAIL', 'ERROR', 'unexpected success'))}"
                  " | unittest discover -v |",
                  "| Tests skipped or expected failures | "
                  f"{sum(1 for s in suites for v in s[2].values() if v.startswith('skipped') or v == 'expected failure')}"
                  " | unittest discover -v |",
                  f"| Requirements | {trace['requirements']} | tools/check_trace.py |",
                  f"| Tests traced to a requirement or listed as supporting | {trace['tests_traced']} of {trace['tests']}"
                  " | tools/check_trace.py |",
                  f"| Trace problems | {trace['problems']} | tools/check_trace.py |",
                  f"| Open issues | {'not queried' if open_issues is None else len(open_issues)} | gh issue list |",
                  f"| Closed issues | {'not queried' if closed_issues is None else len(closed_issues)} | gh issue list |",
                  f"| PRs merged / with at least one review | "
                  f"{'not queried' if merged is None else str(len(merged)) + ' / ' + str(sum(1 for p in merged if p['reviews']))}"
                  " | gh pr list |",
                  f"| Python lines: package / bridge / tests / tools | {lines(['foundation_robotics/*.py'])} / "
                  f"{lines(['foundation_robotics_bridge/*.py'])} / {lines(['tests/*.py'])} / {lines(['tools/*.py'])} |"
                  " line count |",
                  f"| Markdown lines under docs/ | {lines(['docs/**/*.md'])} | line count |",
                  "| Coverage | not measured: no coverage tool in CI; standard library only | — |", "",
                  "## 6. Rationale for decisions", "",
                  ("No known failure was accepted. " if not failed else
                   "The gates not passed are listed in section 4; this report accepts none of them. ") +
                  "The `-O` run exists because CI runs it; it confirms no behaviour "
                  "depends on `assert` statements."]
    str_lines += footer(date, commit)

    vdd = header(f"FROBO-VDD-{args.label.upper()}", "version description", args.label, date, commit)
    vdd += ["## 1. Identification", "", "| Item | Value |", "|---|---|", "| Name | foundation-robotics |",
            f"| Version | {manifest['version']} (from `SOURCE-MANIFEST.json`) |", f"| Tag | {tags or 'none'} |",
            f"| Commit | `{commit}` |", f"| Commit date | {git('show', '-s', '--format=%cs', 'HEAD')} |",
            "| Previous tag | none |", "",
            "## 2. Contents", "", "| Path | Contents |", "|---|---|",
            "| `foundation_robotics/` | Domain package and `data/defaults.json`, `data/calibration.json` |",
            "| `foundation_robotics_bridge/` | stdio JSON-RPC bridge and schemas |",
            "| `tests/` | Unit, bridge and documentation tests |", "| `tools/` | Manifest, trace and generator tools |",
            "| `docs/` | Control documents and guides |", "",
            "No vendored or third-party code is shipped; the package uses the Python standard library only.", "",
            "## 3. Build and install", "", "There is no build step and no package installation.", "", "```",
            "git clone https://github.com/Akilleez-QA/foundation-robotics",
            "cd foundation-robotics", f"git checkout {commit}", "python -B -m unittest discover -s tests -t .",
            "python -B -m foundation_robotics_bridge", "```", "", "Requires Python 3.11 or newer.", "",
            "## 4. Integrity", "", "| Item | Value |", "|---|---|",
            f"| `SOURCE-MANIFEST.json` SHA-256 | `{manifest['sha256']}` |",
            f"| Manifest file count | {manifest['files']} |",
            f"| Canonical tool inventory SHA-256 | `{manifest['inventory_sha256']}` |",
            f"| Manifest matches working tree | {'yes' if manifest['current'] else 'NO'} |", "",
            "## 5. Changes since previous tag", "",
            "No previous tag exists. Commits on main up to this commit:", "", "```",
            git("log", "--oneline", "--first-parent", commit), "```", "",
            "## 6. Open problems and workarounds", ""]
    if open_issues is None:
        vdd += ["GitHub issues were not queried (gh unavailable)."]
    elif not open_issues:
        vdd += ["No open GitHub issues at generation time. Known untested behaviour is listed in SRS §8."]
    else:
        vdd += ["| Issue | Title |", "|---|---|"] + [f"| #{i['number']} | {i['title']} |" for i in open_issues]
    vdd += ["", "## 7. Documentation baseline", "",
            "Control documents in `docs/` state their own baseline commit in their metadata header.", "",
            "## 8. Verification and scans", "",
            f"- Test report: [STR-{args.label}](../verification/reports/STR-{args.label}.md).",
            f"- Trace check: {trace['problems']} problems.",
            "- Secret scan: CI job `gitleaks` (see the assurance record for the local run)."]
    vdd += footer(date, commit)

    (ROOT / f"docs/verification/reports/STR-{args.label}.md").parent.mkdir(parents=True, exist_ok=True)
    (ROOT / f"docs/verification/reports/STR-{args.label}.md").write_text("\n".join(str_lines), encoding="utf-8")
    (ROOT / f"docs/releases/VDD-{args.label}.md").parent.mkdir(parents=True, exist_ok=True)
    (ROOT / f"docs/releases/VDD-{args.label}.md").write_text("\n".join(vdd), encoding="utf-8")
    print(json.dumps({"commit": commit, "suites": [s[1] for s in suites], "trace_problems": trace["problems"]}))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
