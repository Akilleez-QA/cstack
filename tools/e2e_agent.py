"""End-to-end proof (ADR 003, PR 5): the REAL agent CLI drives one bot's AOR through the cstack MCP stdio server.

    uv run -q --no-project --python 3.12 --with jsonschema==4.26.0 --with cryptography==50.0.2 \
        python -B tools/e2e_agent.py [--keep]

Everything runs in a fresh temporary directory: a copy of the generated .agent/ wiring (tools/agent_profiles.py)
whose server command gains --state-root <tmp>/state and a wire tap, and nothing in ~/.agent is edited. Stages:

1. handshake: `agent mcp doctor` connects to the server. No model and no sign-in are needed. The tap records
   the initialize request, so the negotiated MCP protocolVersion comes from the wire, not from agent's text.
2. goal: `agent -p` as the bot's agent profile runs one Foundation Refrigeration goal (R717 saturation pressure
   at 20 degF). Only that bot's tools are pre-approved (`--permission-mode dontAsk` plus an MCPTool allow
   rule), unless --approve always is given. Cstack's own AOR gate is the real gate either way.
3. verify: the goal's state root gets a throwaway ADR 004 roster, writer key and ledger.json before the run,
   so the server writes a WitnessedLedger. Each of the bot's streams on that log is reopened with its own
   signature and chain check and the host's per-stream anchor, and the refrigeration stream
   "<slug>.foundation_refrigeration" must hold an executed outcome event reading 33.49 psig. Agent's text is
   never trusted.

Exit codes: 0 passed, 1 verification failed, 2 agent failed, 77 agent is not signed in (sign in, then rerun;
this harness never logs in or touches auth). The JSON report goes to stdout (and to <tmp>/report.json with
--keep).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))
import agent_profiles  # noqa: E402
from adapters.aor_registry import load_fleet  # noqa: E402
from adapters.witnessed_ledger import WitnessedLedger, ledger_lib  # noqa: E402

DOMAIN = "foundation_refrigeration"
EXPECTED_PSIG = "33.49"
AUTH_MARKERS = ("Not signed in", "Authentication required", "session has expired", "agent login")
# Process-only switches: grant this run's temp folder trust without persisting it, and keep the user's
# Claude/Cursor MCP servers and hooks out of the run. None of them writes any config file.
AGENT_ENV = {"AGENT_FOLDER_TRUST": "0", "AGENT_CLAUDE_MCPS_ENABLED": "false", "AGENT_CURSOR_MCPS_ENABLED": "false",
            "AGENT_CLAUDE_HOOKS_ENABLED": "false", "AGENT_CURSOR_HOOKS_ENABLED": "false", "AGENT_SUBAGENTS": "0"}
DISALLOWED = "run_terminal_cmd,search_replace,web_search,web_fetch,Agent"

# The wire tap: a transparent stdio relay that logs every newline-delimited frame with a timestamp.
TAP = r'''
import json, subprocess, sys, threading, time
log = open(sys.argv[1], "a", buffering=1)
child = subprocess.Popen(sys.argv[2:], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
def note(direction, raw):
    log.write(json.dumps({"t": time.time(), "dir": direction, "line": raw.decode("utf-8", "replace").rstrip("\n")}) + "\n")
def pump_in():
    for raw in sys.stdin.buffer:
        note("client->server", raw)
        try:
            child.stdin.write(raw); child.stdin.flush()
        except BrokenPipeError:
            break
    try:
        child.stdin.close()
    except BrokenPipeError:
        pass
threading.Thread(target=pump_in, daemon=True).start()
for raw in child.stdout:
    note("server->client", raw)
    sys.stdout.buffer.write(raw); sys.stdout.buffer.flush()
sys.exit(child.wait())
'''


def prompt(slug, name):
    options = ", ".join(f'"option-{i:02d}"' for i in range(1, 21))
    return f"""You are {name}, working only through your own MCP server cstack-{slug}. Do exactly these steps with its tools, in order, taking every id from the previous tool result:
1. Call `aor` and note your bot slug and the class of {DOMAIN}.
2. Call `start_goal` with domain "{DOMAIN}", objective "Read the R717 saturation pressure at 20 degF from Foundation Refrigeration.", acceptance_criteria ["One scoped Foundation Refrigeration tool observation, with Evidence, giving psig."].
3. Call `advance` three times on that goal_id: next_phase "observe" (rationale "Observe the request."); next_phase "orient" (rationale "Orient on the refrigeration contract.", research_references ["contracts/DECISION-002-foundation-refrigeration.md"]); next_phase "decide" (rationale "Decide among 20 options.", option_ids [{options}]).
4. Call `decide` with domain "{DOMAIN}", that goal_id, operation "saturation_pressure", arguments {{"fluid": "R717", "temperature": {{"value": 20, "unit": "degF"}}}}, expected_observation "R717 saturation pressure at 20 degF in psig", success_boundary "Only this one synthetic R717 reading.", failure_meaning "The pinned Refrigeration contract does not match.".
5. If decide says approval_required is true, stop and report the decision_id. Otherwise call `advance` with next_phase "orchestrate" (rationale "Run the precommitted call."), then `execute` with that decision_id.
6. Reply with one line: PSIG=<the psig value from the execute outcome's pressure_views>, then the decision_id.
Use no other tools."""


def write_wiring(root, slug, *, uv, state_root, wire_log, enable_in_config):
    """A temp copy of the generated .agent/ wiring, with the test-only --state-root and the wire tap."""
    fleet = load_fleet(REPO / "aors/fleet.json")
    files = agent_profiles.build(fleet, REPO, uv, state_root)
    python = "/usr/bin/python3" if Path("/usr/bin/python3").exists() else sys.executable
    tap = root / "wire_tap.py"
    tap.write_text(TAP)
    wrapped = {"command": python, "args": ["-I", "-B", str(tap), str(wire_log), uv,
                                           *agent_profiles.server_args(REPO, slug, state_root)]}
    name = agent_profiles.server_name(slug)
    original = json.dumps({"name": name, "command": uv, "args": agent_profiles.server_args(REPO, slug, state_root),
                           "env": []}, ensure_ascii=False)
    profile = files[f".agent/agents/{slug}.md"]
    if original not in profile:
        raise SystemExit("generated profile shape changed")
    files[f".agent/agents/{slug}.md"] = profile.replace(
        original, json.dumps({"name": name, **wrapped, "env": []}, ensure_ascii=False))
    config = files[".agent/config.toml"]
    head = f"[mcp_servers.{name}]\n"
    start = config.index(head) + len(head)
    end = config.index("\n\n", start)
    block = (f"command = {json.dumps(wrapped['command'])}\nargs = {json.dumps(wrapped['args'])}\n"
             f"enabled = {'true' if enable_in_config else 'false'}\n"
             f"startup_timeout_sec = {agent_profiles.STARTUP_TIMEOUT_SEC}\n"
             f"tool_timeout_sec = {agent_profiles.TOOL_TIMEOUT_SEC}")
    files[".agent/config.toml"] = config[:start] + block + config[end:]
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    return root / f".agent/agents/{slug}.md"


def repo_wiring_current(uv):
    fleet = load_fleet(REPO / "aors/fleet.json")
    return not agent_profiles.check(agent_profiles.build(fleet, REPO, uv), REPO)


def read_wire(path):
    if not path.exists():
        return []
    frames = []
    for line in path.read_text().splitlines():
        entry = json.loads(line)
        try:
            entry["msg"] = json.loads(entry["line"])
        except ValueError:
            entry["msg"] = None
        frames.append(entry)
    return frames


def summarize_wire(frames):
    sent = {f["msg"].get("id"): f for f in frames if f["dir"] == "client->server" and isinstance(f["msg"], dict)
            and "method" in f["msg"] and "id" in f["msg"]}
    out = {"initialize": None, "methods": [], "tool_calls": []}
    for f in frames:
        msg = f["msg"]
        if not isinstance(msg, dict):
            continue
        if f["dir"] == "client->server" and "method" in msg:
            out["methods"].append(msg["method"])
            if msg["method"] == "initialize":
                out["initialize"] = {"requested": msg.get("params", {}).get("protocolVersion"),
                                     "clientInfo": msg.get("params", {}).get("clientInfo")}
        elif f["dir"] == "server->client" and msg.get("id") in sent:
            request = sent[msg["id"]]["msg"]
            if request["method"] == "initialize" and out["initialize"] is not None:
                out["initialize"]["negotiated"] = msg.get("result", {}).get("protocolVersion")
            if request["method"] == "tools/call":
                result = msg.get("result", {})
                out["tool_calls"].append({
                    "tool": request["params"].get("name"), "arguments": request["params"].get("arguments"),
                    "is_error": result.get("isError"), "ms": round((f["t"] - sent[msg["id"]]["t"]) * 1000),
                    "result": result.get("structuredContent")})
    return out


def run(command, *, cwd, timeout):
    started = time.monotonic()
    env = {**os.environ, **AGENT_ENV}
    try:
        done = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout,
                              check=False)
        rc, out, err = done.returncode, done.stdout, done.stderr
    except subprocess.TimeoutExpired as expired:
        rc, out, err = "timeout", expired.stdout or "", expired.stderr or ""
        out, err = (x.decode() if isinstance(x, bytes) else x for x in (out, err))
    return {"argv": command, "rc": rc, "seconds": round(time.monotonic() - started, 2), "stdout": out[-20000:],
            "stderr": err[-8000:]}


def find_psig(value):
    """Every psig reading in pressure_views anywhere inside value."""
    found = []
    if isinstance(value, dict):
        for view in value.get("pressure_views", []) if isinstance(value.get("pressure_views"), list) else []:
            if isinstance(view, dict) and view.get("unit") == "psig":
                found.append(view.get("value"))
        for child in value.values():
            found += find_psig(child)
    elif isinstance(value, list):
        for child in value:
            found += find_psig(child)
    return found


def seed_witnessed(state_root, slug, node="e2e"):
    """A throwaway ADR 004 roster (3 test witnesses, quorum 2), this bot's writer key, and ledger.json."""
    L = ledger_lib()
    (state_root / "ledger").mkdir(parents=True, mode=0o700)
    keys = {name: L.Ed25519PrivateKey.generate() for name in (slug, "w1", "w2", "w3")}
    roster = {"quorum": 2, "witnesses": {w: L.pub_hex(keys[w]) for w in ("w1", "w2", "w3")},
              "writers": {slug: {"pub": L.pub_hex(keys[slug]), "node": node}}}
    (state_root / "ledger/roster.json").write_text(json.dumps(roster))
    L.save_key(keys[slug], str(state_root / f"ledger/{slug}.key"))
    (state_root / "ledger.json").write_text(json.dumps({
        "node": node, "log": f"ledger/{node}.jsonl", "roster": "ledger/roster.json",
        "writers": {slug: {"writer": slug, "key": f"ledger/{slug}.key"}}}))


def verify_ledger(state_root, slug):
    """Reopen each of the bot's witnessed ledger streams with its own checks and the host's per-stream anchor;
    find the 33.49 outcome in the refrigeration stream. Every anchored stream must verify."""
    config = json.loads((state_root / "ledger.json").read_text())
    log = state_root / config["log"]

    def store(name):  # bootstrap gives every core its own file: <log without suffix>/<bot>/<domain>.jsonl
        return log.with_suffix("") / slug / f"{name[len(slug) + 1:]}.jsonl"
    path = store(f"{slug}.{DOMAIN}")
    if not path.exists():
        return {"ok": False, "reason": f"no ledger at {path}"}
    anchors_path = state_root / slug / "anchors.json"
    anchors = json.loads(anchors_path.read_text()) if anchors_path.exists() else {}
    stream = f"{slug}.{DOMAIN}"
    if any(not name.startswith(slug + ".") for name in anchors):
        return {"ok": False, "reason": f"{anchors_path} is not keyed by {slug}'s ledger streams"}
    streams = {}
    for name in sorted({stream, *anchors}):
        anchor = tuple(anchors[name]) if name in anchors else None
        ledger = WitnessedLedger(store(name), config["node"], state_root / config["roster"], slug,
                                 state_root / config["writers"][slug]["key"], stream=name, anchor=anchor)
        try:
            streams[name] = (ledger.read(), ledger.head(), anchor)
        finally:
            ledger.close()
    events, head, anchor = streams[stream]
    outcomes = []
    for event in events:
        if event["kind"] != "outcome":
            continue
        outcome = event["data"].get("outcome", {})
        readings = [f"{v:.2f}" for v in find_psig(outcome) if isinstance(v, (int, float))]
        outcomes.append({"sequence": event["sequence"], "event_sha256": event["event_sha256"],
                         "prior_event_sha256": event["prior_event_sha256"],
                         "execution_status": outcome.get("execution_status"),
                         "assessment": outcome.get("assessment"), "operation": outcome.get("operation"),
                         "decision_id": outcome.get("decision_id"), "psig": readings})
    hit = [o for o in outcomes if o["execution_status"] == "completed" and EXPECTED_PSIG in o["psig"]]
    return {"ok": bool(hit), "ledger": str(path), "stream": stream, "events": len(events), "head": list(head),
            "anchor_matches_head": _same_stream_tip(anchor, head), "kinds": [e["kind"] for e in events], "outcomes": outcomes,
            "streams": {name: {"events": len(e), "head": list(h), "anchor_matches_head": _same_stream_tip(a, h)}
                        for name, (e, h, a) in streams.items()},
            "reason": None if hit else f"no outcome event reads {EXPECTED_PSIG} psig"}


def _same_stream_tip(anchor, head):
    """A stream's anchor records the node log where that stream last wrote; other streams may have written since,
    so only the stream part (stream, events, last_event_sha256) is compared. The node part was verified on open."""
    return anchor is not None and len(anchor) == 5 and tuple(anchor[2:]) == tuple(head[2:])


def agent_json(text):
    for line in reversed(text.strip().splitlines()):
        try:
            return json.loads(line)
        except ValueError:
            continue
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--slug", default="example", help="the AOR whose profile agent runs as")
    parser.add_argument("--agent", default=shutil.which("agent"), help="agent executable")
    parser.add_argument("--uv", default=shutil.which("uv"))
    parser.add_argument("--approve", choices=("rules", "always"), default="rules",
                        help="rules: dontAsk plus an allow rule for this bot's MCP tools only; always: --always-approve")
    parser.add_argument("--enable-in-config", action="store_true",
                        help="also set enabled = true in the temp config.toml (default: the profile alone enables it)")
    parser.add_argument("--model", help="agent model id (default: agent's own default)")
    parser.add_argument("--max-turns", type=int, default=40)
    parser.add_argument("--timeout", type=int, default=900, help="seconds for the goal run")
    parser.add_argument("--skip-goal", action="store_true", help="run only the handshake stage")
    parser.add_argument("--keep", action="store_true", help="keep the temp directory")
    args = parser.parse_args(argv)
    if not args.agent or not args.uv:
        raise SystemExit("agent and uv must be on PATH (or pass --agent/--uv)")
    if not agent_profiles.SLUG.fullmatch(args.slug):
        raise SystemExit("Unsafe slug")
    uv = str(Path(args.uv).absolute())
    fleet = load_fleet(REPO / "aors/fleet.json")
    bot = fleet.bot(args.slug)
    tmp = Path(tempfile.mkdtemp(prefix="cstack-e2e-agent-"))
    started = time.monotonic()
    report = {"slug": args.slug, "bot": bot.name, "tmp": str(tmp), "repo_wiring_current": repo_wiring_current(uv),
              "agent_version": run([args.agent, "--version"], cwd=tmp, timeout=30)["stdout"].strip(), "stages": {}}
    code = 0
    try:
        # Stage 1: handshake through `agent mcp doctor`, which needs no sign-in. Its own state root and tap.
        shake = tmp / "handshake"
        shake.mkdir()
        write_wiring(shake, args.slug, uv=uv, state_root=shake / "state", wire_log=shake / "wire.jsonl",
                     enable_in_config=True)
        doctor = run([args.agent, "mcp", "doctor", agent_profiles.server_name(args.slug), "--json"], cwd=shake,
                     timeout=120)
        wire = summarize_wire(read_wire(shake / "wire.jsonl"))
        try:
            doctor_json = json.loads(doctor["stdout"])
        except ValueError:
            doctor_json = None
        checks = [c for s in (doctor_json or {}).get("servers", []) for c in s.get("checks", [])]
        report["stages"]["handshake"] = {
            "rc": doctor["rc"], "seconds": doctor["seconds"], "checks": checks, "wire": wire,
            "ok": doctor["rc"] == 0 and bool(wire["initialize"]) and wire["initialize"].get("negotiated") is not None}
        if not report["stages"]["handshake"]["ok"]:
            report["stages"]["handshake"]["stdout"], report["stages"]["handshake"]["stderr"] = (
                doctor["stdout"][-4000:], doctor["stderr"][-4000:])
            code = 2

        # Stage 2: the goal, headless, as the bot's own agent profile.
        if not args.skip_goal and code == 0:
            work = tmp / "run"
            work.mkdir()
            state_root = work / "state"
            state_root.mkdir(mode=0o700)
            seed_witnessed(state_root, args.slug)
            profile = write_wiring(work, args.slug, uv=uv, state_root=state_root, wire_log=work / "wire.jsonl",
                                   enable_in_config=args.enable_in_config)
            command = [args.agent, "-p", prompt(args.slug, bot.name), "--agent", str(profile), "--cwd", str(work),
                       "--output-format", "json", "--max-turns", str(args.max_turns), "--no-subagents",
                       "--disallowed-tools", DISALLOWED]
            command += (["--always-approve"] if args.approve == "always" else
                        ["--permission-mode", "dontAsk",
                         "--allow", f"MCPTool({agent_profiles.server_name(args.slug)}__*)"])
            command += ["--model", args.model] if args.model else []
            goal = run(command, cwd=work, timeout=args.timeout)
            answer = agent_json(goal["stdout"]) or {}
            stage = {"rc": goal["rc"], "seconds": goal["seconds"], "argv": [a if len(a) < 200 else a[:60] + "…"
                                                                              for a in command],
                     "agent_answer": answer, "wire": summarize_wire(read_wire(work / "wire.jsonl"))}
            text = goal["stdout"] + goal["stderr"]
            if goal["rc"] != 0 and any(m in text for m in AUTH_MARKERS):
                stage["auth"] = "agent is not signed in; run `agent login` yourself, then rerun this harness"
                stage["stdout"], stage["stderr"] = goal["stdout"][-2000:], goal["stderr"][-2000:]
                code = 77
            elif goal["rc"] != 0:
                stage["stdout"], stage["stderr"] = goal["stdout"][-4000:], goal["stderr"][-4000:]
                code = 2
            report["stages"]["goal"] = stage

            # Stage 3: the ledger, not agent's text, decides.
            try:
                verdict = verify_ledger(state_root, args.slug)
            except Exception as error:  # a broken chain or anchor is a verification failure, reported as such
                verdict = {"ok": False, "reason": f"{type(error).__name__}: {error}"}
            report["stages"]["verify"] = verdict
            if code == 0 and not verdict["ok"]:
                code = 1
    finally:
        report["seconds"] = round(time.monotonic() - started, 2)
        report["exit_code"] = code
        (tmp / "report.json").write_text(json.dumps(report, indent=2, default=str))
        print(json.dumps(report, indent=2, default=str))
        if not args.keep:
            shutil.rmtree(tmp, ignore_errors=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
