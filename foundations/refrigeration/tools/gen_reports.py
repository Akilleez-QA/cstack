import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from foundation_refrigeration import __version__
from foundation_refrigeration_bridge.schemas import tool_definitions

REPORTS = ROOT / "docs/verification/reports"
RELEASES = ROOT / "docs/releases"
OWNER = "Akilleez-QA"
DISCLAIMER = (
    "> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&"
    "page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA "
    "Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) "
    "documentation guidance. This is not a NASA compliance determination or certification. The software "
    "classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent "
    "verification and validation, or hazard analysis is asserted. The document describes the implementation "
    "inspected at the baseline commit.")
LINE = re.compile(r"^(test_\w+) \(tests\.(test_\w+)\.(\w+)\.test_\w+\) \.\.\. (ok|FAIL|ERROR|skipped.*)$")
CONTROL_DOCS = ("docs/plan/software-management-plan.md", "docs/plan/compliance-matrix.md",
                "docs/requirements/requirements.md", "docs/architecture/architecture.md", "docs/icd/icd-cstack.md",
                "docs/data/data-dictionary.md", "docs/verification/test-plan.md",
                "docs/verification/verification-matrix.md", "docs/configuration/configuration-management.md",
                "docs/assurance/assurance-record.md", "docs/guides/SUM-MAP.md")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def gh(*args):
    if shutil.which("gh") is None:
        return None
    proc = subprocess.run(["gh", *args], cwd=ROOT, capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else None


def run_suite(optimized):
    command = [sys.executable, "-B", *(["-O"] if optimized else []), "-m", "unittest", "discover", "-s", "tests",
               "-t", ".", "-v"]
    proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    results = {}
    for line in proc.stderr.splitlines():
        match = LINE.match(line)
        if match:
            name, module, cls, outcome = match.groups()
            results["tests/%s.py::%s.%s" % (module, cls, name)] = outcome.split()[0]
    ran = re.search(r"^Ran (\d+) tests? in ([0-9.]+)s$", proc.stderr, re.M)
    display = "python -B%s -m unittest discover -s tests -t ." % (" -O" if optimized else "")
    return {"command": display, "returncode": proc.returncode, "results": results,
            "ran": int(ran.group(1)) if ran else 0, "seconds": ran.group(2) if ran else "unknown",
            "digest": hashlib.sha256(proc.stderr.encode()).hexdigest(), "tail": proc.stderr.strip().splitlines()[-1]}


def trace_module():
    spec = importlib.util.spec_from_file_location("check_trace", ROOT / "tools/check_trace.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def requirement_map(trace):
    mapping = {}
    for row in trace.table_rows(trace.VM.read_text(), "| Requirement |"):
        for ref in ("%s::%s.%s" % m for m in trace.TEST_REF.findall(row[2])):
            mapping.setdefault(ref, []).append(row[0])
    return mapping


def source_lines():
    counts = {}
    for name in git("ls-files").splitlines():
        path = ROOT / name
        if not path.is_file():
            continue
        kind = {".py": "Python", ".md": "Markdown", ".json": "JSON", ".yml": "YAML"}.get(path.suffix)
        if kind:
            counts[kind] = counts.get(kind, 0) + len(path.read_bytes().splitlines())
    return counts


def issue_counts():
    raw = gh("issue", "list", "--state", "all", "--limit", "500", "--json", "state,labels")
    if raw is None:
        return None
    issues = json.loads(raw)
    by = {}
    for issue in issues:
        labels = [label["name"] for label in issue["labels"] if re.fullmatch(r"S[1-4]", label["name"])] or ["unlabelled"]
        for label in labels:
            key = (issue["state"].lower(), label)
            by[key] = by.get(key, 0) + 1
    return issues, by


def header(doc_id, title, commit, label, today):
    return ["# foundation-refrigeration %s" % title, "", "| Field | Value |", "|---|---|",
            "| Document ID | %s |" % doc_id, "| Version | 1.0 |", "| Status | Draft |", "| Owner | %s |" % OWNER,
            "| Date | %s |" % today, "| Baseline commit | %s |" % commit,
            "| Applies to | foundation-refrigeration %s |" % ("main at baseline commit" if label == "unreleased"
                                                            else label),
            "| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |", "", DISCLAIMER, "",
            "Generated by `python -B tools/gen_reports.py --label %s`. Do not edit by hand; rerun the generator." % label,
            ""]


def footer(today, commit, change):
    return ["", "## Change history", "", "| Version | Date | Commit | Change | Reviewed in |", "|---|---|---|---|---|",
            "| 1.0 | %s | %s | %s | PR adding the NASA-standard documentation set |" % (today, commit[:7], change)]


def write_str(label, commit, dirty, today, runs, trace, gates):
    problems, summary = trace.check()
    mapping = requirement_map(trace)
    srs = trace.SRS.read_text()
    gaps = sorted(set(re.findall(r"GAP-REF-\d{3}", srs)))
    tbd = len(re.findall(r"\bTBD\b(?! / question)", srs))
    lines = source_lines()
    issues = issue_counts()
    merged = gh("pr", "list", "--state", "merged", "--limit", "500", "--json", "number")
    normal, optimized = runs
    passed = all(r["returncode"] == 0 for r in runs) and not problems
    out = header("FREFRIG-STR-%s" % label.upper(), "software test report %s" % label, commit, label, today)
    out += ["## 1. Summary", "",
            "- Conclusion: %s." % ("all suites passed and the trace check found no problems" if passed else
                                   "FAILED: see results and problems below"),
            "- Remaining deficiencies and limitations: %d untested behaviours are listed as gaps in the "
            "[requirements](../../requirements/requirements.md#9-untested-behaviour-gaps) (%s). No test exercises a "
            "live host; the Cstack side of the interface is verified in the Cstack repository." %
            (len(gaps), ", ".join(gaps) or "none"),
            "- Test-environment impact: tests read only files in the repository and start the bridge as a child "
            "process. No network or external service is used.", "",
            "## 2. Test log", "", "| Item | Value |", "|---|---|",
            "| Commit | `%s`%s |" % (commit, " (working tree had uncommitted changes)" if dirty else ""),
            "| Date (UTC) | %s |" % datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "| Environment | %s %s, CPython %s |" % (platform.system(), platform.machine(), platform.python_version()),
            "| Run by | operator, `tools/gen_reports.py` (local run, not CI) |"]
    for run in runs:
        out.append("| `%s` | exit %d, %s; %d tests in %s s; stderr SHA-256 `%s` |" % (
            run["command"], run["returncode"], run["tail"], run["ran"], run["seconds"], run["digest"]))
    out += ["| `python -B tools/check_trace.py` | %d problem(s); %d requirements, %d traced; %d tests, %d traced, "
            "%d supporting; %d markdown files link-checked |" % (
                len(problems), summary["requirements"], summary["traced"], summary["tests"], summary["tests_traced"],
                summary["tests_supporting"], summary["markdown_files"])]
    for name, result in gates:
        out.append("| %s | %s |" % (name, result))
    out += ["", "## 3. Results", "", "| Test | Requirements | Normal | Optimized (-O) |", "|---|---|---|---|"]
    for ref in sorted(set(normal["results"]) | set(optimized["results"])):
        out.append("| `%s` | %s | %s | %s |" % (ref, ", ".join(mapping.get(ref, [])) or "supporting",
                                               normal["results"].get(ref, "not run"),
                                               optimized["results"].get(ref, "not run")))
    out += ["", "## 4. Problems and deviations", ""]
    failures = [(ref, outcome) for run in runs for ref, outcome in run["results"].items() if outcome != "ok"]
    if failures or problems:
        out += ["| Item | Description |", "|---|---|"]
        out += ["| `%s` | %s |" % (ref, outcome) for ref, outcome in failures]
        out += ["| trace | %s |" % p.replace("|", "\\|") for p in problems]
    else:
        out.append("None. No test failed or was skipped, and the trace check reported no problems.")
    out += ["", "## 5. Metrics", "", "| Measure | Value | Command |", "|---|---|---|",
            "| Tests run / passed / failed (normal) | %d / %d / %d | `%s` |" % (
                normal["ran"], sum(v == "ok" for v in normal["results"].values()),
                sum(v != "ok" for v in normal["results"].values()), normal["command"]),
            "| Tests run / passed / failed (optimized) | %d / %d / %d | `%s` |" % (
                optimized["ran"], sum(v == "ok" for v in optimized["results"].values()),
                sum(v != "ok" for v in optimized["results"].values()), optimized["command"]),
            "| Requirements total / traced to a test or inspection | %d / %d | `python -B tools/check_trace.py` |" % (
                summary["requirements"], summary["traced"]),
            "| Untested behaviour gaps | %d | count of `GAP-REF-` IDs in the SRS |" % len(gaps),
            "| TBD markers in the SRS | %d | count of `TBD` in the SRS |" % tbd,
            "| Requirement changes since previous tag | no previous tag | `git tag --list` |"]
    if issues is None:
        out.append("| Issues by state and severity | not queried (gh unavailable) | `gh issue list` |")
    else:
        items, by = issues
        text = ", ".join("%s %s: %d" % (state, sev, n) for (state, sev), n in sorted(by.items())) or "none"
        out.append("| Issues by state and severity (total %d) | %s | `gh issue list --state all` |" % (len(items), text))
    out.append("| PRs merged (all time) | %s | `gh pr list --state merged` |" %
               ("not queried" if merged is None else len(json.loads(merged))))
    out.append("| Coverage | not measured: no coverage tool is pinned; see test plan §5 | — |")
    out.append("| Source lines by type (tracked files) | %s | `git ls-files` + line count |" %
               ", ".join("%s %d" % item for item in sorted(lines.items())))
    out += ["", "## 6. Rationale for decisions", "",
            "The report is generated from a local run on the operator's machine with the same commands CI runs. "
            "CI results for the same commit are on the pull request's checks page. Coverage is not measured because "
            "the project is standard-library only and no coverage tool is pinned."]
    out += footer(today, commit, "Generated test report")
    (REPORTS / ("STR-%s.md" % label)).write_text("\n".join(out) + "\n")
    return passed


def write_vdd(label, commit, today):
    manifest_raw = (ROOT / "SOURCE-MANIFEST.json").read_bytes()
    manifest = json.loads(manifest_raw)
    inventory = json.dumps(tool_definitions(), ensure_ascii=True, allow_nan=False, sort_keys=True,
                           separators=(",", ":")).encode("ascii")
    tags = git("tag", "--list").split()
    previous = tags[-1] if tags else None
    log = git("log", "--first-parent", "--format=%h %s", *(["%s..%s" % (previous, commit)] if previous else [commit]))
    groups = {}
    for name in manifest["files"]:
        top = name.split("/")[0] if "/" in name else "(root files)"
        groups[top] = groups.get(top, 0) + 1
    out = header("FREFRIG-VDD-%s" % label.upper(), "version description %s" % label, commit, label, today)
    out += ["## 1. Identification", "", "| Item | Value |", "|---|---|",
            "| Name | foundation-refrigeration |", "| Version | %s (`foundation_refrigeration.__version__`) |" % __version__,
            "| Tag | %s |" % (label if label != "unreleased" else "none (unreleased main)"),
            "| Commit | `%s` |" % commit, "| Previous tag | %s |" % (previous or "none"), "| Date | %s |" % today, "",
            "## 2. Contents", "",
            "Source tree only. There is no built package and no installer. Files covered by `SOURCE-MANIFEST.json` "
            "by top-level path:", "", "| Path | Files |", "|---|---|"]
    out += ["| `%s` | %d |" % (top, count) for top, count in sorted(groups.items())]
    out += ["", "No third-party code is vendored. The runtime uses the Python standard library only.", "",
            "## 3. Build and install", "", "```sh",
            "git clone https://github.com/Akilleez-QA/foundation-refrigeration", "cd foundation-refrigeration",
            "git checkout %s" % commit, "python -B -m unittest discover -s tests -t .",
            "python -B tools/build_manifest.py", "git diff --exit-code SOURCE-MANIFEST.json", "```", "",
            "Requires Python 3.11 or newer (CI uses 3.12). Start the bridge with "
            "`python -B -m foundation_refrigeration_bridge` from the repository root.", "",
            "## 4. Integrity", "", "| Item | Value |", "|---|---|",
            "| `SOURCE-MANIFEST.json` SHA-256 | `%s` |" % hashlib.sha256(manifest_raw).hexdigest(),
            "| Manifest file count | %d |" % len(manifest["files"]),
            "| Canonical tool inventory SHA-256 | `%s` |" % hashlib.sha256(inventory).hexdigest(), "",
            "These are the three values a host pins (see the [interface control document](../icd/icd-cstack.md)). "
            "Per-file digests are in `SOURCE-MANIFEST.json`; data-file digests are in the "
            "[reference data provenance](../data/reference-data.md) table.", "",
            "## 5. Changes since previous tag", "",
            "No previous tag exists, so this lists every first-parent commit up to the identified commit:" if not
            previous else "First-parent commits since `%s`:" % previous, "", "```"]
    out += log.splitlines() + ["```", "", "See [CHANGELOG.md](../../CHANGELOG.md) for the summarized changes.", "",
                               "## 6. Open problems and workarounds", ""]
    issues = issue_counts()
    if issues is None:
        out.append("Not queried: `gh` was unavailable when this was generated.")
    else:
        open_items = [i for i in issues[0] if i["state"].lower() == "open"]
        out.append("Open issues at generation: %d (`gh issue list --state open`)." % len(open_items))
    out += ["", "## 7. Documentation baseline", "", "| Document | Baseline commit |", "|---|---|"]
    for name in CONTROL_DOCS:
        match = re.search(r"^\| Baseline commit \| (\S+) \|$", (ROOT / name).read_text(), re.M)
        out.append("| [%s](../../%s) | %s |" % (name, name, match.group(1) if match else "not recorded"))
    out += ["", "## 8. Verification and scans", "",
            "Test and trace results for this commit: [STR-%s](../verification/reports/STR-%s.md). The secret scan "
            "result is recorded in the same report's test log." % (label, label)]
    out += footer(today, commit, "Generated version description")
    (RELEASES / ("VDD-%s.md" % label)).write_text("\n".join(out) + "\n")


def gitleaks_gate():
    if shutil.which("gitleaks") is None:
        return ("gitleaks", "not run: gitleaks not installed")
    proc = subprocess.run(["gitleaks", "git", "--redact", "--no-banner", "--exit-code", "1", "--config",
                           ".gitleaks.toml", "."], cwd=ROOT, capture_output=True, text=True)
    summary = re.sub(r"\x1b\[[0-9;]*m", "", proc.stdout + proc.stderr).strip().splitlines()
    return ("`gitleaks git --redact --no-banner --exit-code 1 --config .gitleaks.toml .`",
            "exit %d; %s" % (proc.returncode, summary[-1] if summary else "no output"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="unreleased")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9.\-]+", args.label):
        raise SystemExit("label must be lower-case letters, digits, dots or hyphens")
    commit = git("rev-parse", "HEAD")
    dirty = bool(git("status", "--porcelain"))
    today = datetime.date.today().isoformat()
    runs = (run_suite(False), run_suite(True))
    manifest = subprocess.run([sys.executable, "-B", "tools/build_manifest.py"], cwd=ROOT, capture_output=True,
                              text=True)
    diff = subprocess.run(["git", "diff", "--exit-code", "--quiet", "SOURCE-MANIFEST.json"], cwd=ROOT)
    gates = [("`python -B tools/build_manifest.py` then `git diff --exit-code SOURCE-MANIFEST.json`",
              "exit %d / %d" % (manifest.returncode, diff.returncode)),
             ("`python -B tools/gen_docs.py --check`", "exit %d" % subprocess.run(
                 [sys.executable, "-B", "tools/gen_docs.py", "--check"], cwd=ROOT, capture_output=True).returncode),
             gitleaks_gate()]
    REPORTS.mkdir(parents=True, exist_ok=True)
    RELEASES.mkdir(parents=True, exist_ok=True)
    passed = write_str(args.label, commit, dirty, today, runs, trace_module(), gates)
    write_vdd(args.label, commit, today)
    print(json.dumps({"commit": commit, "dirty": dirty, "passed": passed,
                      "normal": runs[0]["returncode"], "optimized": runs[1]["returncode"]}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
