"""POODO LedgerPort that writes through the ADR 004 private witnessed ledger (adapters).

It wraps the prototype's Log, authorize() and verifier; it does not copy them, so there is one durable ledger
and one verifier. Every POODO event is stored, in its MemoryLedger shape, in body.event_json of an ADR 004 entry:

    decision (action=precommit) -> intent  digest = sha256(canonical(request)), so authorize() can gate it
    action                      -> claim   ref = that intent, digest as Log.claim(); with enforce=True, authorize()
                                           must pass first. A claim is "use" to authorize() and the board, so a
                                           concurrent `ledger.py gate --claim` on the same intent is denied
    outcome                     -> result  ref = that intent; outcome from execution_certainty/status
    everything else             -> note

body.event_json is the event's poodo_core canonical JSON as a string (DEL written as \u007f), not a nested object.
The control board's lib/ledger.ts re-canonicalizes every signed entry in a bundle chain and refuses floats and
integers beyond 2^53, both of which POODO events carry (tool readings), and it escapes DEL and orders keys by UTF-16
unit where Python does not. A string survives both serializers byte-for-byte; every other body field is checked
board-safe before signing (_board_safe), so the adapter never signs an entry the board cannot verify.

Streams: one node log per device holds many POODO chains. Each WitnessedLedger owns one named stream (for example
"<bot>.<domain>"), and every entry it signs carries body.stream, so the stream is covered by the writer's signature
and the witnesses still see one ordinary ADR 004 log. A stream is identified by (writer, stream): read(), sequence,
prior_event_sha256 and the retention budget count only this writer's entries in this stream, contiguous from 1, as
MemoryLedger does. Entries of other streams or writers are skipped unread, never treated as corruption. POODO events
keep MemoryLedger's shape, so two streams can hold byte-identical events; readers group by body.stream (and writer),
never by event content. A POODO entry of this writer with no stream predates streams and is refused (see _scan).

Claim: a stream has at most one live instance. The constructor takes an exclusive, non-blocking flock on
<log>.streams/<stream>.lock (a 0700 directory of its own, so no stream's claim can be another log's node .lock) and
holds it until close() (or until the instance is collected or the process exits); a second instance on the same
stream, in this process or another, gets ContractError. The claim is re-checked on every operation: a forked child
drops its inherited copy (it cannot write), and a lock file deleted or replaced under a live owner stops that owner
rather than admitting a second one. reserve() holds nothing until append():
that is safe only because the stream is single-owner (this claim) and its one core serializes its own calls (the
core re-entrancy guard, "one live core per ledger"). Budgets are per stream, so another stream cannot spend this
one's room; the node file as a whole is bounded only by the sum of its streams' budgets.
`cryptography` is imported lazily (ADR 004 open question 3); without it construction fails closed.

Locking: the adapter takes no lock of its own. Each operation runs inside the prototype's Log.locked() (an exclusive
flock on <log>.lock, re-reading the file under it) and appends with Log._write, the same lock-held append that
Log.claim() uses, so verify, gate, budget, POODO chaining and the append are one critical section against every
writer on the node. Log.write() cannot be called there: flock is per open file and Log's thread lock is not
re-entrant, so a nested write would deadlock, as an adapter-held flock on <log>.lock did.
"""
from contextlib import ExitStack, contextmanager
import importlib.util
import json
import fcntl
import os
from pathlib import Path
import re
import stat
import weakref

_LIVE = weakref.WeakSet()  # instances holding a claim, so a forked child can drop its inherited copies

from poodo_core.models import ContractError, canonical, digest

KINDS = ("proposal", "observation", "inference", "decision", "action", "outcome", "learning", "correction")
ENVELOPE_BYTES = 1024  # ADR 004 fields + signature + hash around each POODO event
STREAM_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")  # e.g. "agent.foundation_math"; also a safe file-name part
_SOURCE = Path(__file__).resolve().parents[1] / "adapters/ledger.py"
_lib = None


def ledger_lib():
    """The ADR 004 prototype module, loaded read-only from Example Agent's slice on first use."""
    global _lib
    if _lib is None:
        if importlib.util.find_spec("cryptography") is None:
            raise ContractError("WitnessedLedger needs the 'cryptography' package (ADR 004 open question 3)")
        spec = importlib.util.spec_from_file_location("cstack_witnessed_ledger_v1", _SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _lib = module
    return _lib


def _private(path):
    """Open or create a 0600 regular file owned by this user, never through a symlink."""
    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    except OSError as error:
        raise ContractError(f"Refusing ledger path {path}: {error.strerror}") from None
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        os.close(fd)
        raise ContractError(f"Refusing {path}: it must be a regular 0600 file owned by this user")
    return fd


def _drop_inherited_claims():
    for ledger in list(_LIVE):
        ledger._drop_claim()


os.register_at_fork(after_in_child=_drop_inherited_claims)


def _private_dir(path):
    """Create or check a 0700 directory owned by this user, never through a symlink."""
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        pass
    except OSError as error:
        raise ContractError(f"Refusing ledger directory {path}: {error.strerror}") from None
    info = os.lstat(path)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ContractError(f"Refusing {path}: it must be a 0700 directory owned by this user")


def _encode(event):
    """The one stored form of a POODO event: canonical JSON with DEL escaped (lib/ledger.ts escapes 0x7f; json does not)."""
    return canonical(event).replace("\x7f", "\\u007f")


def _decode(body):
    text = body.get("event_json")
    event = json.loads(text) if type(text) is str else None
    if type(event) is not dict or _encode(event) != text:
        raise ContractError("POODO event is not stored in canonical form")
    return event


def _board_safe(value):
    """True if Python's ledger canon and the board's lib/ledger.ts canon() produce identical bytes for value."""
    if value is None or type(value) is bool:
        return True
    if type(value) is int:
        return abs(value) <= 2 ** 53 - 1
    if type(value) is str:
        return "\x7f" not in value
    if type(value) is list:
        return all(map(_board_safe, value))
    if type(value) is dict:
        keys = list(value)
        return sorted(keys) == sorted(keys, key=lambda k: k.encode("utf-16-be", "surrogatepass")) and \
            all(map(_board_safe, keys)) and all(map(_board_safe, value.values()))
    return False  # floats and anything else: the board refuses them


def _valid_anchor(anchor, genesis):
    if len(anchor) not in (2, 5) or type(anchor[0]) is not int or anchor[0] < 0 or type(anchor[1]) is not str \
            or (anchor[0] == 0) != (anchor[1] == genesis):
        return False
    if len(anchor) == 2:
        return True
    count, last = anchor[3:]
    return type(anchor[2]) is str and type(count) is int and 0 <= count <= anchor[0] and \
        (last is None if count == 0 else type(last) is str)


def result_outcome(outcome):
    """ADR 004 result vocabulary (shared with shields ledger.py) from a POODO CapabilityOutcome."""
    certainty = outcome.get("execution_certainty")
    if certainty == "not_dispatched":
        return "not_dispatched"
    if certainty == "responded":
        return "applied" if outcome.get("execution_status") == "completed" else "failed"
    return "unknown"


class WitnessedLedger:
    def __init__(self, log_path, origin, roster_path, writer, key_path, *, stream, enforce=False,
                 max_events=100_000, max_bytes=256 << 20, anchor=None):
        """All arguments are trusted host configuration, chosen by bootstrap. enforce is LEDGER_ENFORCE.

        stream names this instance's POODO chain on the node log (STREAM_NAME); max_events and max_bytes bound it.
        anchor is an optional head() the host kept outside these files: (size, head) pins the node log, and
        (size, head, stream, events, last_event_sha256) also pins this stream; a shorter or different log, or
        another stream's anchor, is refused.
        """
        if type(stream) is not str or not STREAM_NAME.fullmatch(stream):
            raise ContractError("Invalid ledger stream name: 1-64 of [a-z0-9._-], starting with [a-z0-9]")
        if type(enforce) is not bool or type(max_events) is not int or type(max_bytes) is not int \
                or min(max_events, max_bytes) < 1:
            raise ContractError("Invalid witnessed ledger configuration")
        self._L = L = ledger_lib()
        anchor = tuple(anchor) if anchor else None
        if anchor is not None and not _valid_anchor(anchor, L.GENESIS):
            raise ContractError("Invalid witnessed ledger anchor")
        if anchor is not None and len(anchor) == 5 and anchor[2] != stream:
            raise ContractError(f"Anchor belongs to ledger stream {anchor[2]!r}, not {stream!r}")
        self._path, self._origin, self._writer, self._stream = str(log_path), origin, writer, stream
        self._enforce, self._max_events, self._max_bytes = enforce, max_events, max_bytes
        try:
            self._roster, self._key = L.load_roster(roster_path), L.load_key(key_path)
            bound = self._roster["writers"].get(writer) or {}
        except (L.LedgerError, OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            raise ContractError(f"Witnessed ledger configuration refused: {error}") from None
        if bound.get("node") != origin or bound.get("pub") != L.pub_hex(self._key):
            raise ContractError("Writer key is not the roster key bound to this node")
        if not callable(getattr(L.Log, "locked", None)) or not callable(getattr(L.Log, "_write", None)):
            raise ContractError("Witnessed ledger prototype lacks Log.locked/Log._write; refusing to write unlocked")
        self._seen = anchor[:2] if anchor else (0, L.GENESIS)
        self._tip = (0, None)  # this stream's (events, last event_sha256) at self._seen
        self._intents = {}  # decision_id -> intent hash, for this core's decisions
        self._claim = self._claim_stream()
        try:
            with self._open() as log:
                if anchor and len(anchor) == 5 and self._tip_at(log, anchor[0]) != anchor[3:]:
                    raise ContractError("Witnessed ledger failed verification: stream differs from its anchor")
                self._restore_intents(log)
        except BaseException:
            self.close()
            raise

    def _restore_intents(self, log):
        """A new process keeps recording against this stream's intents, so a late outcome is a result on its own intent."""
        for entry in log.entries:
            body = entry.get("body")
            if entry["writer"] == self._writer and entry["kind"] == "intent" and type(body) is dict \
                    and body.get("stream") == self._stream and "event_json" in body:
                self._intents[_decode(body)["data"]["request"]["decision_id"]] = entry["hash"]

    def _claim_stream(self):
        """Exclusive, non-blocking flock on <log>.streams/<stream>.lock for this instance's lifetime."""
        _private_dir(self._path + ".streams")
        self._claim_path = os.path.join(self._path + ".streams", self._stream + ".lock")
        fd = _private(self._claim_path)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            raise ContractError(f"Ledger stream {self._stream!r} already has a live owner on this log") from None
        self._claim_fd, self._pid = fd, os.getpid()
        claim = weakref.finalize(self, os.close, fd)  # closing the descriptor releases the flock
        _LIVE.add(self)
        self._check_claim(claim)
        return claim

    def _check_claim(self, claim=None):
        """Refuse unless this process still holds the flock on the file that the claim path names now."""
        claim = claim or self._claim
        if not claim.alive or self._pid != os.getpid():
            raise ContractError(f"Ledger stream {self._stream!r} is closed")
        try:
            held, named = os.fstat(self._claim_fd), os.lstat(self._claim_path)
        except OSError:
            named = held = None
        if held is None or (held.st_dev, held.st_ino) != (named.st_dev, named.st_ino):
            claim()
            raise ContractError(f"Ledger stream {self._stream!r} claim file was removed or replaced; closed")

    def _drop_claim(self):
        """In a forked child: close the inherited descriptor (the parent keeps the flock) and refuse every operation."""
        claim = getattr(self, "_claim", None)
        if claim is not None and claim.detach() is not None:
            os.close(self._claim_fd)

    @contextmanager
    def _open(self):
        """Re-open and fully verify the node log under Log's own exclusive lock, so writers on this node stay chained."""
        L = self._L
        self._check_claim()
        for suffix in ("", ".cp", ".lock"):  # create or check all three 0600 before Log opens them by name
            os.close(_private(self._path + suffix))
        with ExitStack() as stack:
            try:
                log = L.Log(self._path, self._origin, self._roster)
                stack.enter_context(log.locked())  # exclusive flock on <log>.lock, then refresh
                self._check_claim()  # not closed while this operation waited for the node lock
                size, head = self._seen
                if size > len(log.entries) or (size and log.entries[size - 1]["hash"] != head):
                    raise L.LedgerError("truncated or rewritten since last seen")
                for cp in log.cps:
                    if not 0 < cp["size"] <= len(log.entries) or log.entries[cp["size"] - 1]["hash"] != cp["head"]:
                        raise L.LedgerError("log is shorter than, or differs from, a stored checkpoint")
            except (L.LedgerError, OSError, ValueError, KeyError, TypeError) as error:
                raise ContractError(f"Witnessed ledger failed verification: {error}") from None
            self._fresh = None
            yield log
            size = len(log.entries)  # an operation that scanned (or appended) at this size already knows the tip
            self._seen = (size, log.head)
            self._tip = self._fresh[1] if self._fresh and self._fresh[0] == size else self._tip_at(log, size)

    def head(self):
        """(size, head, stream, events, last_event_sha256): the node log and this stream as last verified here, for
        the host to anchor outside these files (the anchor= argument)."""
        return (*self._seen, self._stream, *self._tip)

    @property
    def stream(self):
        return self._stream

    def _tip_at(self, log, size):
        """This stream's (event count, last event_sha256) within the first `size` node entries."""
        events = self._scan(log, size)[0]
        return (len(events), events[-1]["event_sha256"] if events else None)

    def verified_log(self):
        """A freshly verified Log, for the host to reconcile with witnesses."""
        with self._open() as log:
            return log

    def _scan(self, log, size=None):
        """(events, entries, stored bytes) of this stream, verifying its chain. Other writers' and streams' entries
        are skipped without being parsed.

        A POODO entry (event_json or poodo_denied) of this writer with no stream was written before streams existed
        (#25 before it was merged; no deployed log has one). It is refused, not adopted as a "default" stream:
        several cores may have interleaved in that one chain, which is the defect streams fix, so no stream can
        claim it, and skipping it would hide signed decisions. Such a log is retired, not migrated.
        """
        events, prior, count, stored = [], None, 0, 0
        entries = log.entries if size is None else log.entries[:size]
        for entry in entries:
            body = entry.get("body")
            if entry["writer"] != self._writer or type(body) is not dict:
                continue
            if "stream" not in body:
                if "event_json" in body or "poodo_denied" in body:
                    raise ContractError(f"POODO entry without a stream at node seq {entry['seq']}; it predates streams")
                continue
            if body["stream"] != self._stream:
                continue
            count, stored = count + 1, stored + len(json.dumps(entry, sort_keys=True)) + 1  # Log._persist's line
            if "event_json" not in body:
                continue
            event = _decode(body)
            kind = event.get("kind")
            frame = {"sequence": len(events) + 1, "kind": kind,
                     "data": event.get("data") if kind else None, "prior_event_sha256": prior}
            if kind not in KINDS or canonical(event) != canonical({**frame, "event_sha256": digest(frame)}):
                raise ContractError(f"POODO event chain broken at node seq {entry['seq']}")
            events.append(event)
            prior = event["event_sha256"]
        self._fresh = (len(entries), (len(events), prior))
        return events, count, stored

    def _budget(self, scan, event_count, byte_count):
        """This stream's own retention budget: entries and stored bytes of other streams never count against it."""
        _, count, stored = scan
        if count + event_count > self._max_events or \
                stored + byte_count + event_count * ENVELOPE_BYTES > self._max_bytes:
            raise ContractError("Ledger retention budget exhausted before dispatch")

    def _write(self, log, kind, body, ref=None):
        body = {**body, "stream": self._stream}  # signed with the entry, so a stream cannot be re-labelled
        if not _board_safe(body):
            raise ContractError("Refusing to sign a ledger entry the control board cannot canonicalize")
        try:
            return log._write(self._key, self._writer, kind, body, ref=ref)  # Log.locked() is held by _open
        except (self._L.LedgerError, OSError, ValueError, TypeError) as error:
            raise ContractError(f"Witnessed ledger append refused: {error}") from None

    def _gate(self, log, ref, data):
        """ADR 004 authorize() for this action, plus: one attempt per intent. Denials are recorded, then raised."""
        L = self._L
        try:
            intent = next((e for e in log.entries if e["hash"] == ref), None)
            if intent is None or intent["writer"] != self._writer or intent["body"].get("stream") != self._stream:
                raise L.Denied("no-intent: execute-then-log is not allowed")
            try:
                request = _decode(intent["body"])["data"]["request"]
            except (ContractError, KeyError, TypeError):
                raise L.Denied("no-intent: not a POODO intent") from None
            if data.get("request_sha256") != L.digest(request):
                raise L.Denied("action does not match the registered intent")
            L.authorize(log, ref, request)
            if any(e.get("ref") == ref for e in log.entries):
                raise L.Denied("intent-already-attempted")
        except L.LedgerError as denied:
            self._write(log, "note", {"poodo_denied": {"decision_id": data.get("decision_id"), "intent": ref,
                                                       "reason": str(denied)}})
            raise ContractError(f"Ledger gate denied execution: {denied}") from None

    def reserve(self, event_count, byte_count):
        with self._open() as log:
            self._budget(self._scan(log), event_count, byte_count)

    def append(self, kind, data):
        if kind not in KINDS or type(data) is not dict:
            raise ContractError("Unknown event classification")
        L = self._L
        with self._open() as log:
            scan = self._scan(log)
            events = scan[0]
            frame = {"sequence": len(events) + 1, "kind": kind, "data": data,
                     "prior_event_sha256": events[-1]["event_sha256"] if events else None}
            event = json.loads(canonical({**frame, "event_sha256": digest(frame)}))
            self._budget(scan, 1, len(_encode(event)))
            entry_kind, body, ref = "note", {"event_json": _encode(event)}, None
            if kind == "decision" and data.get("action") == "precommit":
                request = data.get("request")
                if type(request) is not dict or L.digest(request) != data.get("request_sha256"):
                    raise ContractError("Precommitment does not match its request digest")
                entry_kind, body = "intent", {"digest": L.digest(request), "op": "poodo.execute",
                                     "event_json": _encode(event)}
            elif kind == "action":
                ref = self._intents.get(data.get("decision_id"))
                if self._enforce:
                    self._gate(log, ref, data)
                if ref is not None:  # consume the intent as Log.claim() does, in this same locked section
                    intent = next(e for e in log.entries if e["hash"] == ref)
                    entry_kind, body = "claim", {"digest": intent["body"]["digest"], "event_json": _encode(event)}
            elif kind == "outcome":
                outcome = data.get("outcome") if type(data.get("outcome")) is dict else {}
                ref = self._intents.get(outcome.get("decision_id"))
                if ref is not None:
                    entry_kind, body = "result", {"outcome": result_outcome(outcome),
                                                    "event_json": _encode(event)}
            entry = self._write(log, entry_kind, body, ref)
            self._fresh = (len(log.entries), (event["sequence"], event["event_sha256"]))
            if entry_kind == "intent":
                self._intents[data["request"].get("decision_id")] = entry["hash"]
            return event

    def read(self):
        with self._open() as log:
            return self._scan(log)[0]

    def close(self):
        """Release the stream claim. Idempotent; every later operation on this instance is refused."""
        claim = getattr(self, "_claim", None)
        if claim is not None:
            claim()
