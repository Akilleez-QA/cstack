"""Scheduled approval channel (ADR 003): list the asks waiting on the owner, print the morning brief, record the answer.

A bot's ask-class decision raises ApprovalPending and writes one `approval_pending` observation. This tool reads
every bot's ledgers under a state root, lists the asks with no recorded answer, and records the owner's yes or no as
exactly one ApprovalRecord through ApprovalWriter (approver `owner-via-approver`, bound to the ledger's digest).

    scheduled_approvals.py pending --state-root DIR [--json | --full DECISION_ID]
    scheduled_approvals.py brief   --state-root DIR
    scheduled_approvals.py answer  DECISION_ID yes|no --sha256 HEX --state-root DIR [--ttl 3600] [--bot SLUG]

Ledgers read: `<state_root>/<bot>/*.ledger.db` (DurableLedger SQLite, opened read-only), `<state_root>/<bot>/
*.ledger.json` (MemoryLedger-shaped exports), and the ADR 004 node log named by `<state_root>/ledger.json`
(verified with adapters, which needs `cryptography`; POODO events in `body.event_json`, legacy
`body.event` accepted only without it). Every POODO event chain is re-verified; a broken
ledger is reported and none of its asks can be answered. Answers go to `<state_root>/approvals.db`.

What the checks mean. The POODO hash chain is unkeyed: it detects corruption and careless edits, not forgery by
anyone who can rewrite the file. The bot label is only the directory name (or the ledger.json writer entry); it is
not an authenticated identity. Everything inside an ask (arguments, expectation, limit) is bot-supplied text, so it
is shown only as escaped JSON, never truncated, and an answer must quote the digest the owner saw (--sha256).

WHO RUNS IT. Only the configured human approver runs this channel on the host shell.
It must never be exposed as a bot MCP tool or called from a bot's process. It refuses to run when the
CSTACK_MCP_SERVER environment marker is set, or when the MCP driving adapter is loaded in this process.

TRUST LIMIT. Those checks stop accidents, not hostile code. Any process running as the same OS user can run this
file, or write approvals.db directly. Real separation needs the approval channel on its own OS user or device; until then the
ledger's precommit, approval_pending and approved/declined events are the audit trail of every answer.
"""
import argparse
import importlib.util
import json
import os
import socket
import sqlite3
import stat
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.approval_store import ApprovalReader, ApprovalWriter  # noqa: E402
from poodo_core import ApprovalRecord, CapabilityRequest, ContractError, Precommitment  # noqa: E402
from poodo_core.models import canonical, digest, identifier  # noqa: E402

APPROVER = "owner-via-approver"
MCP_MARKER = "CSTACK_MCP_SERVER"
BRIEF_LIMIT = 5
SHA_SHOWN = 16  # digest hex shown in the brief and required to answer
LINE_LIMIT = 600  # longer asks are not briefed in full; they need the host and the full digest
_EVENT_KEYS = {"sequence", "kind", "data", "prior_event_sha256", "event_sha256"}
_HMI_LEDGER = Path(__file__).resolve().parents[1] / "adapters/ledger.py"


def refuse_inside_bot():
    if os.environ.get(MCP_MARKER) or "adapters.mcp_stdio_server" in sys.modules:
        raise ContractError("Scheduled's approval channel never runs inside a bot MCP server process")


def verify_chain(events, label):
    """Re-check a MemoryLedger-shaped event list: contiguous, chained, and every digest exact."""
    prior = None
    for number, event in enumerate(events, 1):
        ok = type(event) is dict and set(event) == _EVENT_KEYS
        if ok:
            frame = {"sequence": number, "kind": event["kind"], "data": event["data"], "prior_event_sha256": prior}
            ok = canonical(event) == canonical({**frame, "event_sha256": digest(frame)})
        if not ok:
            raise ContractError(f"{label}: ledger chain broken at event {number}")
        prior = event["event_sha256"]
    return events


def _private_file(path):
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ContractError(f"{path}: must be a regular 0600 file owned by this user")


def read_sqlite(path):
    _private_file(path)
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    try:
        rows = db.execute("SELECT event FROM events ORDER BY sequence").fetchall()
    finally:
        db.close()
    return [(json.loads(text), None) for (text,) in rows]


def read_json(path):
    _private_file(path)
    value = json.loads(Path(path).read_text())
    return [(event, None) for event in (value["events"] if type(value) is dict else value)]


def hmi_ledger():
    """The ADR 004 ledger library, loaded read-only from the shared adapters directory."""
    if importlib.util.find_spec("cryptography") is None:
        raise ContractError("ledger.json is configured but 'cryptography' is missing; cannot verify the node log")
    spec = importlib.util.spec_from_file_location("cstack_witnessed_ledger_v1", _HMI_LEDGER)
    lib = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lib)
    return lib


def read_witnessed(state_root):
    """{(bot, stream): [(event, ts)]} from the ADR 004 node log, verified in full by the HMI ledger library.

    #25 named streams: one writer holds one POODO chain per stream (body.stream, "<bot>.<domain>"), so events are
    grouped by stream before their chains are checked. An entry with no stream (before streams) is stream None."""
    lib = hmi_ledger()
    config = json.loads((state_root / "ledger.json").read_text())
    try:
        log = lib.Log(str(state_root / config["log"]), config.get("node", socket.gethostname()), lib.load_roster(state_root / config["roster"]))
    except lib.LedgerError as error:
        raise ContractError(f"Witnessed node log failed verification: {error}") from None
    found = {}
    for bot, writer in config["writers"].items():
        streams = {}
        try:
            for e in log.entries:
                body = e.get("body")
                if e["writer"] != writer["writer"] or type(body) is not dict or \
                        not ("event_json" in body or "event" in body):
                    continue
                stream = body.get("stream")
                if stream is not None and type(stream) is not str:
                    raise ContractError(f"node seq {e['seq']}: stream is not a string")
                streams.setdefault(stream, []).append((node_event(body, e["seq"]), e["ts"]))
        except ContractError as error:
            streams = {None: error}
        for stream, pairs in streams.items():
            found[(bot, stream)] = pairs
    return found


def _no_duplicates(pairs):
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ContractError("duplicate JSON key")
    return dict(pairs)


def _no_constant(name):
    raise ContractError(f"non-finite JSON number {name}")


def node_event(body, seq):
    """The POODO event in one node-log entry. #25 stores body.event_json, a canonical JSON string (DEL escaped):
    parsed strictly (no duplicate keys, NaN or Infinity) and required to be canonical. body.event is read only for
    entries that predate it and carry no event_json; an entry carrying both must agree."""
    if "event_json" not in body:
        return body["event"]
    text = body["event_json"]
    try:
        event = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_no_constant)
        exact = type(event) is dict and canonical(event).replace("\x7f", "\\u007f") == text
    except (ContractError, ValueError, TypeError) as error:
        raise ContractError(f"node seq {seq}: event_json refused: {error}") from None
    if not exact:
        raise ContractError(f"node seq {seq}: event_json is not canonical")
    if "event" in body and (type(body["event"]) is not dict or canonical(body["event"]) != canonical(event)):
        raise ContractError(f"node seq {seq}: event_json and event disagree")
    return event


def ledgers(state_root):
    """Yield (bot, label, [(event, ts)]) or (bot, label, ContractError) for every ledger under the state root."""
    state_root = Path(state_root)
    for bot_dir in sorted(p for p in state_root.iterdir() if p.is_dir()):
        for path in sorted([*bot_dir.glob("*.ledger.db"), *bot_dir.glob("*.ledger.json")]):
            try:
                pairs = read_sqlite(path) if path.suffix == ".db" else read_json(path)
                verify_chain([event for event, _ in pairs], str(path))
                yield bot_dir.name, str(path), pairs
            except (ContractError, OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
                yield bot_dir.name, str(path), ContractError(f"{path}: {error}")
    if (state_root / "ledger.json").exists():
        label = str(state_root / "ledger.json")
        try:
            found = read_witnessed(state_root)
        except (ContractError, OSError, ValueError, KeyError, TypeError) as error:
            found = {("?", None): ContractError(f"{label}: {error}")}
        for (bot, stream), pairs in found.items():
            where = f"{label}#{bot}" + (f"/{stream}" if stream is not None else "")
            try:
                if not isinstance(pairs, ContractError):
                    verify_chain([event for event, _ in pairs], where)
            except ContractError as error:
                pairs = error
            yield bot, where, pairs


def asks_in(bot, label, pairs, problems):
    """Every ask in one verified ledger that raised approval_pending and was never answered, run or superseded.
    A malformed ask becomes a problem; it never hides the other asks or stops the brief."""
    revisions, precommits, pending, settled = {}, {}, {}, set()
    for event, ts in pairs:
        data = event["data"]
        action = data.get("action")
        if action in ("start_goal", "revise_goal"):
            contract = data["snapshot"]["contract"]
            revisions[contract["goal_id"]] = (contract["revision"], contract["domain_id"])
        elif action == "precommit":
            precommits[data["request"]["decision_id"]] = data
        elif action == "approval_pending":
            pending.setdefault(data["decision_id"], (data, event["sequence"], ts))
        elif action in ("approved", "declined") or event["kind"] == "action":
            settled.add(data.get("decision_id"))
    items = []
    for decision_id, (note, sequence, ts) in pending.items():
        try:
            commit = precommits.get(decision_id)
            if commit is None or decision_id in settled:
                continue
            request = CapabilityRequest.from_dict(commit["request"])
            revision, domain = revisions.get(request.goal_id, (None, None))
            if revision != request.goal_revision:
                continue  # The goal was revised; this ask can no longer execute.
            Precommitment(**commit["precommitment"])
            exact = request.sha256 == digest(commit["request"]) == commit["request_sha256"] == note["request_sha256"]
            items.append({"bot": bot, "domain": identifier(domain), "capability_id": request.capability_id,
                          "decision_id": decision_id, "operation": request.operation, "arguments": request.arguments,
                          "precommitment": commit["precommitment"], "goal_id": request.goal_id,
                          "goal_revision": request.goal_revision, "request_sha256": request.sha256,
                          "approver": note.get("approver"), "pending_since": ts if type(ts) is int else None,
                          "pending_event": sequence, "ledger": label,
                          "problem": None if exact else "request digest does not match the precommit"})
        except (ContractError, KeyError, TypeError, AttributeError) as error:
            problems.append(f"{label}: ask {quote(decision_id)} is malformed: {quote(str(error))}")
    return items


def fair(items):
    """Round-robin across bots (each bot oldest first), so no bot can fill the brief by asking more."""
    queues = {}
    for item in sorted(items, key=lambda i: (i["pending_since"] or 0, i["ledger"], i["pending_event"])):
        queues.setdefault(item["bot"], []).append(item)
    ordered, lanes = [], [queues[bot] for bot in sorted(queues)]
    while any(lanes):
        ordered += [lane.pop(0) for lane in lanes if lane]
    return ordered


def scan(state_root, approvals=None):
    """(items still waiting on the owner, ledger problems). A store answer for the same request means answered; a
    store answer for a different request under the same decision id is a collision, shown and unanswerable."""
    items, problems = [], []
    for bot, label, pairs in ledgers(state_root):
        try:
            if isinstance(pairs, ContractError):
                raise pairs
            items.extend(asks_in(identifier(bot), label, pairs, problems))
        except (ContractError, KeyError, TypeError, AttributeError) as error:
            problems.append(quote(str(error)) if isinstance(pairs, ContractError) else f"{label}: {quote(str(error))}")
    store = Path(approvals or Path(state_root) / "approvals.db")
    if store.exists() and items:
        reader = ApprovalReader(store, clock=lambda: int(time.time()), consumer="scheduled")
        try:
            kept = []
            for item in items:
                row = reader.lookup(item["decision_id"])
                if row is None or item["problem"]:
                    kept.append(item)
                elif row.request_sha256 != item["request_sha256"]:
                    kept.append({**item, "problem": "collision: this decision id already has a recorded answer "
                                                    "for a different request"})
            items = kept
        finally:
            reader.close()
    for item in items:
        if item["problem"]:
            problems.append(f"{item['ledger']}: {item['bot']} {item['decision_id']}: {item['problem']}")
    return fair(items), problems


def quote(value):
    """Bot-supplied data as one escaped JSON literal: no newline, control, bidi or other non-ASCII survives raw."""
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def line(item):
    """One plain-English line. Every bot-supplied value is quoted and escaped, never truncated."""
    when = (datetime.fromtimestamp(item["pending_since"], timezone.utc).strftime("%b %d %H:%M UTC")
            if item["pending_since"] else f"ledger event {item['pending_event']}")
    pre = item["precommitment"]
    return (f"{item['bot']} wants to run {item['operation']} on {item['capability_id']} ({item['domain']}). "
            f"Bot-quoted arguments: {quote(item['arguments'])}. "
            f"Bot-quoted expectation: {quote(pre['expected_observation'])}; "
            f"bot-quoted limit: {quote(pre['success_boundary'])}. "
            f"Goal {item['goal_id']} rev {item['goal_revision']}, waiting since {when}. "
            f"Reply yes or no to {item['decision_id']} sha {item['request_sha256'][:SHA_SHOWN]}.")


def too_long(item):
    return len(line(item)) > LINE_LIMIT


def brief(items, problems):
    """Scheduled's morning-brief block: action first, at most five items, plain English (OWNER-STYLE)."""
    ready = [item for item in items if not item["problem"]]
    out = [f"Approvals: {len(ready)} waiting on your yes or no." if ready else "Approvals: nothing waiting on you."]
    for n, item in enumerate(ready[:BRIEF_LIMIT], 1):
        out.append(f"{n}. " + (line(item) if not too_long(item) else
                   f"{item['bot']} wants to run {item['operation']} on {item['capability_id']} "
                   f"({item['decision_id']}): too long to brief; review on host with "
                   f"`pending --full {item['decision_id']}`."))
    if len(ready) > BRIEF_LIMIT:
        out.append(f"{len(ready) - BRIEF_LIMIT} more after these; I'll bring them next brief.")
    if problems:
        out.append(f"{len(problems)} ask(s) blocked (ledger problem); see `pending`.")
    return "\n".join(out)


def answer(state_root, decision_id, verdict, *, sha256, ttl=3600, bot=None, clock=None, approvals=None):
    """Record exactly one ApprovalRecord for one pending ask, bound to the digest the owner saw.

    sha256 is mandatory for yes and for no (a decline also blocks the decision): at least the 16 hex shown in the
    brief, or the full 64 when the ask was too long to brief. Refuses anything not pending, answered or inexact."""
    refuse_inside_bot()
    identifier(decision_id)
    if verdict not in ("yes", "no"):
        raise ContractError("The answer is yes or no")
    if type(sha256) is not str or len(sha256) < SHA_SHOWN or set(sha256) - set("0123456789abcdef"):
        raise ContractError(f"Give at least the {SHA_SHOWN} hex digest characters the owner saw")
    if type(ttl) is not int or not 60 <= ttl <= 7 * 86400:
        raise ContractError("ttl must be 60 seconds to 7 days")
    clock = clock or (lambda: int(time.time()))
    store = Path(approvals or Path(state_root) / "approvals.db")
    items, _ = scan(state_root, store)
    matches = [i for i in items if i["decision_id"] == decision_id and (bot is None or i["bot"] == bot)]
    if not matches and store.exists():
        reader = ApprovalReader(store, clock=clock, consumer="scheduled")
        try:
            if reader.lookup(decision_id) is not None:
                raise ContractError(f"{decision_id} already has a recorded answer")
        finally:
            reader.close()
    if not matches:
        raise ContractError(f"{decision_id} is not pending in any readable ledger")
    if len(matches) > 1:
        raise ContractError(f"{decision_id} is pending for several bots; name one with --bot")
    item = matches[0]
    if item["problem"]:
        raise ContractError(f"{decision_id}: {item['problem']}; refusing to answer")
    if not item["request_sha256"].startswith(sha256):
        raise ContractError("The digest the owner saw does not match the ledger's precommit")
    if too_long(item) and sha256 != item["request_sha256"]:
        raise ContractError("This ask was too long to brief; answer it with the full 64-hex digest from pending --full")
    if item["approver"] != APPROVER:
        raise ContractError(f"This core waits on approver {quote(item['approver'])}, not {APPROVER}")
    record = ApprovalRecord(approval_id="scheduled." + digest([decision_id, item["request_sha256"]])[:32],
                            decision_id=decision_id, request_sha256=item["request_sha256"], goal_id=item["goal_id"],
                            goal_revision=item["goal_revision"], approver=APPROVER,
                            verdict="approved" if verdict == "yes" else "declined", not_after=clock() + ttl)
    writer = ApprovalWriter(store, clock=clock)
    try:
        writer.record(record)
    finally:
        writer.close()
    return record, item


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("pending", "brief", "answer"):
        command = commands.add_parser(name)
        command.add_argument("--state-root", required=True, type=Path)
        command.add_argument("--approvals", type=Path, help="default: <state_root>/approvals.db")
        if name == "pending":
            command.add_argument("--json", action="store_true")
            command.add_argument("--full", metavar="DECISION_ID", help="every field of one ask, full digest")
        if name == "answer":
            command.add_argument("decision_id")
            command.add_argument("verdict", choices=("yes", "no"))
            command.add_argument("--sha256", required=True, help=f"digest the owner saw (at least {SHA_SHOWN} hex)")
            command.add_argument("--ttl", type=int, default=3600)
            command.add_argument("--bot")
    args = parser.parse_args(argv)
    try:
        refuse_inside_bot()
        if args.command == "answer":
            record, item = answer(args.state_root, args.decision_id, args.verdict, sha256=args.sha256, ttl=args.ttl,
                                  bot=args.bot, approvals=args.approvals)
            print(f"Recorded {record.verdict} for {item['bot']}: {item['operation']} ({record.decision_id}), "
                  f"valid until {datetime.fromtimestamp(record.not_after, timezone.utc):%b %d %H:%M UTC}.")
            return 0
        items, problems = scan(args.state_root, args.approvals)
        if args.command == "brief":
            print(brief(items, problems))
        elif args.json or args.full:
            chosen = [i for i in items if args.full is None or i["decision_id"] == args.full]
            print(json.dumps({"pending": chosen, "problems": problems}, indent=2, sort_keys=True, ensure_ascii=True))
        else:
            for item in items:
                print(("BLOCKED: " if item["problem"] else "") + line(item))
            for problem in problems:
                print("Ledger problem: " + problem, file=sys.stderr)
        return 2 if problems else 0
    except (ContractError, OSError) as error:
        print(f"Refused: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
