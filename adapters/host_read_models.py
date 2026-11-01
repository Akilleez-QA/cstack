"""ReadModelFace (ADR 005 item 8): host projections of this machine's live work, for the cockpit (cstack server).

The ledger projections (adapters/read_models.py) say what POODO decided. These say what the machine is doing: worker
registry, GPU queue and safety guard, fleet capacity, heavy-run throttle and memguard, agent sessions, Agent pool,
Endoforge conductor jobs, the merge train, whether POODO has a durable state root, the host's resources (CPU, memory,
swap, GPU, disks) and the work actually running (heavy jobs, GPU jobs, process families). Each is a `Projection` (the same
record as the ledger projections) that cites its source path or command, the host clock as of the read, and a
confidence: complete, partial (some input unreadable) or stale (older than its limit), with a reason.

Read-only by construction: every file is opened for reading, every command is on READ_COMMANDS, and nothing here
calls a write, a queue's `--stats` (it deletes stale tickets) or `agent-pool` (it launches agent). Agent session files
hold prompt text, so only SESSION_FIELDS are read from them. Paths and the command runner are injected (tests use fakes).
"""
from dataclasses import dataclass
import fcntl
import glob
import json
import os
import subprocess

from adapters.read_models import Confidence, Projection

HOME = os.path.expanduser("~")
READ_COMMANDS = frozenset({"workers", "system-safety-status", "heavy-run", "journalctl", "nvidia-smi"})
# process families counted in running_work (by /proc/<pid>/comm prefix): what is using the machine, never their arguments
FAMILIES = (("claude-desktop", "Claude desktop"), ("claude", "Claude Code"), ("agent", "Agent"), ("ChatGPT", "ChatGPT app"),
            ("chromium", "Chromium"), ("chrome", "Chromium"), ("blender", "Blender"), ("node", "Node"), ("python", "Python"),
            ("ffmpeg", "ffmpeg"), ("ollama", "Ollama"))
SESSION_FIELDS = ("lastActivityAt", "completedTurns", "isArchived", "model")


@dataclass(frozen=True)
class HostPaths:
    state: str = os.path.join(HOME, ".local", "state")
    sessions: str = os.path.join(HOME, ".config", "Claude", "worker-sessions")
    agent_pool: str = os.path.join(HOME, ".agent-pool")
    jobs_glob: str = "$FACTORY_SCRATCH/*/job/conductor/state.json"
    cstack_state: str = os.path.join(HOME, ".local", "state", "cstack")
    proc: str = "/proc"
    heavy_cgroup: str = f"/sys/fs/cgroup/user.slice/user-{os.getuid()}.slice/user@{os.getuid()}.service/heavy.slice"
    mounts: tuple = ("/", "/srv/scratch", "/srv/data")
    relay: str = os.path.join(HOME, ".local", "state", "cstack-relay")


def run_read(argv, timeout=5.0):
    """The default runner: only READ_COMMANDS, never a shell; returns stdout (raises on timeout)."""
    if os.path.basename(argv[0]) not in READ_COMMANDS:
        raise PermissionError(f"not a read command: {argv[0]}")
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout).stdout


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _tail_jsonl(path, n):
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            fh.seek(max(0, fh.tell() - 65536))
            lines = fh.read().decode("utf-8", "replace").splitlines()[-n:]
    except OSError:
        return [], False
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out, True


def _has_children(proc, pid):
    for children in glob.glob(os.path.join(proc, pid, "task", "*", "children")):
        try:
            with open(children, encoding="utf-8") as fh:
                if fh.read().strip():
                    return True
        except OSError:
            pass
    return False


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def _meminfo(proc):
    out = {}
    for line in (_read(os.path.join(proc, "meminfo")) or "").splitlines():
        k, _, v = line.partition(":")
        if v.strip().endswith("kB"):
            out[k] = int(v.split()[0]) * 1024
    return out


GIB = 1024 ** 3


def _proj(name, source, as_of, rows, summary, problems=(), level=None):
    level = level or ("partial" if problems else "complete")
    return Projection(name, source, as_of, Confidence(level, "; ".join(problems) or "all inputs read", {}), tuple(rows), summary)


def workers(paths, clock, runner=run_read):
    rows = json.loads(runner(["workers", "list", "--json", "--hours", "6"]) or "[]")
    count = {s: sum(r.get("state") == s for r in rows) for s in ("running", "dead", "unknown", "host")}
    return _proj("workers", {"command": "workers list --json"}, clock(),
                 [{k: r.get(k) for k in ("host", "bot", "state", "heartbeat")} for r in rows], count)


def gpu_queue(paths, clock, runner=None):
    """Tickets listed from the queue directory (prio 0 is the short lane). Names are host data: kept, not interpreted."""
    qdir = os.path.join(paths.state, "gpu-queue")
    rows, problems = [], []
    for path in sorted(glob.glob(os.path.join(qdir, "*.ticket"))):
        parts = os.path.basename(path)[:-len(".ticket")].split("-")
        if len(parts) < 3:
            problems.append(f"unparsed ticket {os.path.basename(path)}")
            continue
        t = _read_json(path, {}) or {}
        # a ticket stays while its job runs: the waiter has launched it once its pid has a child
        pid = parts[2]
        alive = os.path.exists(os.path.join(paths.proc, pid))
        rows.append({"name": t.get("name"), "lane": "short" if parts[0] == "0" else "long", "priority": int(parts[0]) if parts[0].isdigit() else None,
                     "est": t.get("est"), "queued": int(parts[1]) // 10 ** 9, "alive": alive,
                     "running": alive and _has_children(paths.proc, pid)})
    recent, ok = _tail_jsonl(os.path.join(qdir, "history.jsonl"), 8)
    if not ok:
        problems.append("no history.jsonl")
    summary = {"short": sum(r["lane"] == "short" for r in rows), "long": sum(r["lane"] == "long" for r in rows),
               "running": sum(r["running"] for r in rows), "waiting": sum(r["alive"] and not r["running"] for r in rows),
               "jobs": [{"name": r["name"], "state": "running" if r["running"] else "waiting" if r["alive"] else "orphan"} for r in rows],
               "recent": [{k: h.get(k) for k in ("lane", "waited", "ran", "rc", "ended")} for h in recent]}
    return _proj("gpu_queue", {"path": qdir}, clock(), rows, summary, problems)


def safety(paths, clock, runner=run_read):
    d = json.loads(runner([os.path.join(HOME, ".local", "bin", "system-safety-status")]))
    keep = ("healthy", "fault", "gpu_ok", "journal_ok", "guard_status", "monitor_status", "sample_age_seconds")
    stale = (d.get("sample_age_seconds") or 0) > 30
    return _proj("safety", {"command": "system-safety-status"}, clock(), [], {k: d.get(k) for k in keep},
                 ["monitor sample older than 30 s"] if stale else (), "stale" if stale else None)


def capacity(paths, clock, runner=None):
    """fleet-disconnect writes CAPACITY ('<pct> <note>') only below 100 and removes it on resume: absent is 100 %."""
    d = os.path.join(paths.state, "fleet")
    pct, drain = 100, None
    try:
        with open(os.path.join(d, "CAPACITY"), encoding="utf-8") as fh:
            pct = int(fh.read().split()[0])
    except (OSError, ValueError, IndexError):
        pass
    try:
        with open(os.path.join(d, "DRAIN"), encoding="utf-8") as fh:
            drain = fh.read().strip() or "draining"
    except OSError:
        pass
    return _proj("capacity", {"path": d}, clock(), [], {"percent": pct, "draining": drain})


def throttle(paths, clock, runner=run_read):
    slots = sorted(glob.glob(os.path.join(paths.state, "heavy-run", "slot-*.lock")))
    busy = 0
    for slot in slots:                      # a held flock is a running heavy job (a shared probe never blocks it)
        fd = os.open(slot, os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            busy += 1
        finally:
            os.close(fd)
    mem, _ = _tail_jsonl(os.path.join(paths.state, "memguard", "actions.jsonl"), 5)
    return _proj("throttle", {"path": os.path.join(paths.state, "heavy-run"), "command": "heavy-run --limits"}, clock(),
                 [{k: m.get(k) for k in ("t", "set", "why")} for m in mem],
                 {"limits": runner(["heavy-run", "--limits"]).strip(), "slots": len(slots), "busy": busy})


def agent_sessions(paths, clock, runner=None, live_s=900):
    """Claude desktop sessions: SESSION_FIELDS only (the files also hold prompt text, never read here)."""
    now_ms, counts, problems = clock() * 1000, {"total": 0, "live": 0, "blocked": 0, "review_ready": 0}, []
    for path in glob.glob(os.path.join(paths.sessions, "*", "*", "local_*.json")):
        d = _read_json(path)
        if d is None:
            problems.append("unreadable session file")
            continue
        status = (d.get("postTurnSummary") or {}).get("status_category")
        counts["total"] += 1
        if d.get("isArchived"):
            continue
        counts["live"] += bool(d.get("lastActivityAt") and now_ms - d["lastActivityAt"] < live_s * 1000)
        counts["blocked"] += status == "blocked"
        counts["review_ready"] += status == "review_ready"
    return _proj("agent_sessions", {"path": paths.sessions, "fields": list(SESSION_FIELDS) + ["postTurnSummary.status_category"]},
                 clock(), [], counts, sorted(set(problems)))


def agent_pool(paths, clock, runner=None):
    now, cooling = clock(), {}
    for path in glob.glob(os.path.join(paths.agent_pool, "cooldown", "*")):
        try:
            with open(path, encoding="utf-8") as fh:
                until = int(fh.read().strip()) // 1000
        except (OSError, ValueError):
            continue
        if until > now:
            cooling[os.path.basename(path)] = until
    slots = len(glob.glob(os.path.join(paths.agent_pool, "slots", "*", "pid")))
    return _proj("agent_pool", {"path": paths.agent_pool}, now, [], {"cooling_until": cooling, "live_slots": slots})


def conductor_jobs(paths, clock, runner=None):
    rows = []
    for path in sorted(glob.glob(paths.jobs_glob)):
        d = _read_json(path, {}) or {}
        atoms = d.get("atoms") or {}
        status = {}
        for a in atoms.values():
            status[a.get("status")] = status.get(a.get("status"), 0) + 1
        rows.append({"job": d.get("job"), "phase": d.get("phase"), "paused": bool(d.get("paused")), "stopped": bool(d.get("stopped")),
                     "atoms": status, "engines": sorted({(a.get("lane") or {}).get("engine") for a in atoms.values()
                                                         if a.get("status") in ("launched", "checking")} - {None}),
                     "open_escalations": sum(not e.get("resolved") for e in d.get("escalations") or [])})
    return _proj("conductor_jobs", {"glob": paths.jobs_glob}, clock(), rows, {"jobs": len(rows)})


def merge_train(paths, clock, runner=run_read):
    out = runner(["journalctl", "--user", "-u", "cstack-merge-train.service", "-u", "cstack-merge-train-lowrisk.service",
                  "-o", "cat", "--no-pager", "-n", "400"])
    decoder, last, i = json.JSONDecoder(), None, 0
    while (j := out.find("{", i)) >= 0:
        try:
            obj, i = decoder.raw_decode(out, j)
            if isinstance(obj, dict) and "merged" in obj:
                last = obj
        except ValueError:
            i = j + 1
    summary = {"merged": len(last["merged"]), "skipped": len(last.get("skipped") or {})} if last else {"merged": None}
    return _proj("merge_train", {"command": "journalctl --user -u cstack-merge-train*"}, clock(), [], summary,
                 () if last else ["no merge-train summary in the journal window"])


def poodo_state(paths, clock, runner=None):
    root = paths.cstack_state
    exists = os.path.isdir(root)
    shields = exists and bool(glob.glob(os.path.join(root, "SHIELDS_UP")) + glob.glob(os.path.join(root, "*", "SHIELDS_UP")))
    ledgers = (glob.glob(os.path.join(root, "ledger.json")) + glob.glob(os.path.join(root, "*", "ledger.json"))) if exists else []
    return _proj("poodo_state", {"path": root}, clock(), [], {"state_root": exists, "shields_up": shields, "ledgers": len(ledgers)},
                 () if exists else ["no POODO state root: ledgers are in memory only on this device"])


def host_resources(paths, clock, runner=run_read):
    """CPU load against threads, memory and swap (zram included), the GPU (use, VRAM, BAR1, temperature, power) and the
    disks the work lives on. Rounded so a refresh only takes a sequence when something moved."""
    problems = []
    load = (_read(os.path.join(paths.proc, "loadavg")) or "0 0 0").split()[:3]
    mi = _meminfo(paths.proc)
    if not mi:
        problems.append("no meminfo")
    total, avail = mi.get("MemTotal", 0), mi.get("MemAvailable", 0)
    swap_total, swap_free = mi.get("SwapTotal", 0), mi.get("SwapFree", 0)
    summary = {"threads": os.cpu_count(), "load": [round(float(x), 1) for x in load],
               "mem_gib": {"used": round((total - avail) / GIB, 1), "total": round(total / GIB, 1)},
               "swap_gib": {"used": round((swap_total - swap_free) / GIB, 1), "total": round(swap_total / GIB, 1)}}
    gpus = []
    try:
        out = runner(["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                      "--format=csv,noheader,nounits"])
        for line in out.strip().splitlines():
            name, util, used, tot, temp, power = [x.strip() for x in line.split(",")]
            gpus.append({"name": name, "util": int(float(util)), "vram_gib": {"used": round(float(used) / 1024, 1), "total": round(float(tot) / 1024, 1)},
                         "temp_c": int(float(temp)), "power_w": round(float(power))})
        q = runner(["nvidia-smi", "-q", "-d", "MEMORY"])
        bar = q.split("BAR1 Memory Usage", 1)[1] if "BAR1 Memory Usage" in q else ""
        vals = {k.strip(): v.split()[0] for k, v in (line.split(":", 1) for line in bar.splitlines()[1:4] if ":" in line)}
        if gpus and vals.get("Total") and vals.get("Used"):
            gpus[0]["bar1_mib"] = {"used": int(vals["Used"]), "total": int(vals["Total"])}
    except (OSError, ValueError, IndexError, subprocess.SubprocessError) as exc:
        problems.append(f"nvidia-smi: {type(exc).__name__}")
    summary["gpus"] = gpus
    disks = []
    for m in paths.mounts:
        if m != "/" and not os.path.ismount(m):     # an unmounted point would report its parent's disk again
            continue
        try:
            st = os.statvfs(m)
        except OSError:
            continue
        disks.append({"mount": m, "used_gib": round((st.f_blocks - st.f_bfree) * st.f_frsize / GIB),
                      "total_gib": round(st.f_blocks * st.f_frsize / GIB)})
    summary["disks"] = disks
    return _proj("host_resources", {"path": paths.proc, "command": "nvidia-smi --query-gpu, -q -d MEMORY", "statvfs": list(paths.mounts)},
                 clock(), [], summary, problems)


def running_work(paths, clock, runner=run_read):
    """What is running: heavy-run jobs (the heavy.slice scopes, by unit name and command name), processes holding the GPU,
    and process families by name with their resident memory. Command names only, never arguments (they can hold paths
    and prompt text)."""
    problems, heavy = [], []
    for scope in sorted(glob.glob(os.path.join(paths.heavy_cgroup, "*.scope"))):
        pids = (_read(os.path.join(scope, "cgroup.procs")) or "").split()
        mem = (_read(os.path.join(scope, "memory.current")) or "0").strip()
        comms = sorted({(_read(os.path.join(paths.proc, p, "comm")) or "?").strip() for p in pids})
        heavy.append({"unit": os.path.basename(scope)[:-len(".scope")], "commands": comms, "mem_gib": round(int(mem or 0) / GIB, 1)})
    gpu_apps = []
    try:
        out = runner(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"])
        for line in out.strip().splitlines():
            pid, used = [x.strip() for x in line.split(",")]
            gpu_apps.append({"pid": int(pid), "command": (_read(os.path.join(paths.proc, pid, "comm")) or "?").strip(),
                             "vram_gib": round(float(used) / 1024, 1)})
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        problems.append(f"nvidia-smi: {type(exc).__name__}")
    fam = {}
    page = os.sysconf("SC_PAGE_SIZE")
    for d in os.listdir(paths.proc):
        if not d.isdigit():
            continue
        comm = (_read(os.path.join(paths.proc, d, "comm")) or "").strip()
        label = next((lbl for pre, lbl in FAMILIES if comm.startswith(pre)), None)
        if not label:
            continue
        statm = (_read(os.path.join(paths.proc, d, "statm")) or "0 0").split()
        f = fam.setdefault(label, {"processes": 0, "rss_gib": 0.0})
        f["processes"] += 1
        f["rss_gib"] += int(statm[1]) * page / GIB
    families = {k: {"processes": v["processes"], "rss_gib": round(v["rss_gib"], 1)} for k, v in sorted(fam.items(), key=lambda kv: -kv[1]["rss_gib"])}
    summary = {"heavy_jobs": heavy, "gpu_processes": gpu_apps, "families": families}
    return _proj("running_work", {"cgroup": paths.heavy_cgroup, "path": paths.proc, "command": "nvidia-smi --query-compute-apps"},
                 clock(), heavy + gpu_apps, summary, problems)


def relay(paths, clock, runner=None, keep=25, agent_live_s=2400):
    """The cockpit relay (adapters/relay_outbox.py): each message with its latest state and the teams' replies, the
    teams the relay agent can reach, and when it was last seen. Read-only here; the server and the agent write."""
    def lines(name):
        out = []
        try:
            with open(os.path.join(paths.relay, name), encoding="utf-8") as fh:
                for line in fh:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
        except OSError:
            pass
        return out
    rec = {}
    for r in lines("receipts.jsonl"):
        rec.setdefault(r.get("id"), []).append(r)
    rows = []
    for m in lines("outbox.jsonl")[-keep:]:
        rs = rec.get(m.get("id"), [])
        states = [r for r in rs if r.get("state") != "reply"]
        last = states[-1] if states else {}
        rows.append({"id": m.get("id"), "at": m.get("at"), "to": m.get("to"), "about": m.get("about"), "text": m.get("text"),
                     "state": last.get("state", "queued"), "to_name": last.get("to_name"), "note": last.get("note"),
                     "replies": [{k: r.get(k) for k in ("at", "from_name", "text")} for r in rs if r.get("state") == "reply"]})
    teams = _read_json(os.path.join(paths.relay, "teams.json"), {}) or {}
    # Agent answers only while some account is not at its usage limit: say when it can, on its team entry
    cool = agent_pool(paths, clock).summary["cooling_until"]
    accounts = [os.path.basename(p) for p in glob.glob(os.path.join(paths.agent_pool, "cooldown", "*"))]
    if cool and accounts and len(cool) >= len(accounts):
        import datetime
        until = datetime.datetime.fromtimestamp(min(cool.values())).strftime("%a %b %d %H:%M")
        for t in teams.get("teams", []):
            if t.get("id") == "agent":
                t["state"] = f"usage limit until {until}"
    beat = _read_json(os.path.join(paths.relay, "heartbeat"), {}) or {}
    now = clock()
    seen = beat.get("at")
    summary = {"messages": rows[::-1], "teams": teams.get("teams", []), "agent_seen": seen,
               "agent_online": bool(seen and now - seen < agent_live_s),
               "counts": {s: sum(r["state"] == s for r in rows) for s in ("queued", "claimed", "delivered", "failed")}}
    return _proj("relay", {"path": paths.relay}, now, [], summary, () if seen else ["the relay agent has not started yet"])


PROJECTIONS = (workers, gpu_queue, safety, capacity, throttle, agent_sessions, agent_pool, conductor_jobs, merge_train, poodo_state,
               host_resources, running_work, relay)


def project_all(paths=None, clock=None, runner=run_read):
    """Every host projection; one that fails becomes a stale projection naming the error, never an exception."""
    import time
    paths, clock = paths or HostPaths(), clock or (lambda: int(time.time()))
    out = []
    for fn in PROJECTIONS:
        try:
            out.append(fn(paths, clock, runner) if fn.__code__.co_argcount >= 3 else fn(paths, clock))
        except Exception as exc:     # a broken source is reported, not fatal
            out.append(Projection(fn.__name__, {"reader": fn.__name__}, clock(),
                                  Confidence("stale", f"{type(exc).__name__}: {exc}"[:200], {}), (), {}))
    return out
