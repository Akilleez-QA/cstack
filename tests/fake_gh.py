"""A fake `gh` for fleet-mail tests: a tiny in-file issue tracker that records every argv. No network.

install(directory) writes an executable `gh` there and returns its path. The script keeps issues in
state.json and appends {"argv", "stdin", "env"} to argv.jsonl beside itself. It accepts only the exact argv
shapes adapters/fleet_mail.GitHubIssuesMail uses and exits 2 on anything else.
"""
import json
from pathlib import Path
import sys

SCRIPT = r'''
import json, os, re, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
STATE, LOG = HERE / "state.json", HERE / "argv.jsonl"
args = sys.argv[1:]
stdin = sys.stdin.read() if "--body-file=-" in args else ""
with LOG.open("a") as log:
    log.write(json.dumps({"argv": args, "stdin": stdin, "env": sorted(os.environ)}) + "\n")
mode = (HERE / "mode").read_text().strip() if (HERE / "mode").exists() else ""
if mode == "sleep":
    time.sleep(30)
if mode == "flood":
    sys.stdout.write("x" * (9 << 20)); sys.exit(0)
state = json.loads(STATE.read_text()) if STATE.exists() else {"next": 1, "issues": {}}
def fail(why):
    sys.stderr.write("fake gh: " + why + "\n"); sys.exit(2)
def flags(rest, allowed):
    out = {}
    for a in rest:
        m = re.fullmatch(r"--([a-z-]+)=(.*)", a, re.S)
        if not m or m.group(1) not in allowed: fail("unexpected argument " + repr(a))
        out.setdefault(m.group(1), []).append(m.group(2))
    if out.get("repo") != ["your-org/cstack"]: fail("repo")
    return out
def shape(issue, fields):
    full = {"number": issue["number"], "title": issue["title"], "body": issue["body"], "state": issue["state"].upper(),
            "labels": [{"name": n} for n in issue["labels"]], "author": {"login": "Akilleez-QA"},
            "comments": [{"body": c, "author": {"login": "Akilleez-QA"}} for c in issue["comments"]]}
    return {f: full[f] for f in fields}
def get(n):
    if not re.fullmatch(r"[1-9][0-9]*", n) or n not in state["issues"]: fail("no issue " + repr(n))
    return state["issues"][n]
if args[:2] == ["issue", "create"]:
    f = flags(args[2:], {"repo", "title", "body-file", "label"})
    if f.get("body-file") != ["-"] or len(f.get("title", [])) != 1: fail("create shape")
    n = state["next"]; state["next"] += 1
    state["issues"][str(n)] = {"number": n, "title": f["title"][0], "body": stdin, "labels": f.get("label", []),
                               "state": "open", "comments": []}
    print("https://github.com/your-org/cstack/issues/%d" % n)
elif args[:2] == ["issue", "comment"]:
    f = flags(args[3:], {"repo", "body-file"})
    if f.get("body-file") != ["-"]: fail("comment shape")
    get(args[2])["comments"].append(stdin)
elif args[:2] == ["issue", "close"]:
    flags(args[3:], {"repo"}); get(args[2])["state"] = "closed"
elif args[:2] == ["issue", "view"]:
    f = flags(args[3:], {"repo", "json"}); print(json.dumps(shape(get(args[2]), f["json"][0].split(","))))
elif args[:2] == ["issue", "list"]:
    f = flags(args[2:], {"repo", "state", "label", "limit", "json"})
    if f.get("state") != ["open"]: fail("list state")
    found = [i for _, i in sorted(state["issues"].items(), key=lambda kv: -int(kv[0]))
             if i["state"] == "open" and all(l in i["labels"] for l in f.get("label", []))]
    print(json.dumps([shape(i, f["json"][0].split(",")) for i in found[:int(f["limit"][0])]]))
else:
    fail("unknown command")
STATE.write_text(json.dumps(state))
'''


def install(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    gh = directory / "gh"
    gh.write_text(f"#!{sys.executable}\n" + SCRIPT)
    gh.chmod(0o755)
    return str(gh)


def calls(directory):
    path = Path(directory) / "argv.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def set_mode(directory, mode):
    (Path(directory) / "mode").write_text(mode)


