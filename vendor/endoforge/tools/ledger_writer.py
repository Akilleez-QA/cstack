from collections import OrderedDict, deque
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import queue
import resource
import select
import sqlite3
import struct
import sys
import threading
import time
import traceback

from core.ledger.ledger import TABLES, Ledger

MAGIC = b"EFJ1"
HEADER = struct.Struct(">4sI32s")
SEGMENT_BYTES = 128 * 2**20
HANDLES = 1024
WINDOW = 0.010
BATCH = 128
GROUP = 16
WRITES = {"INSERT", "UPDATE", "DELETE", "CREATE", "REPLAC"}
VERSION_TABLE = "CREATE TABLE IF NOT EXISTS ledger_journal (version INTEGER PRIMARY KEY, digest TEXT NOT NULL)"
MARK = "INSERT INTO ledger_journal (version, digest) VALUES (?, ?)"


class JournalCorrupt(Exception):
    pass


def journal_directory():
    configured = os.environ.get("ENDOFORGE_LEDGER_JOURNAL")
    if configured:
        return Path(configured)
    state = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
    return Path(state) / "endoforge" / "ledger-journal"


def encode_frame(payload):
    return HEADER.pack(MAGIC, len(payload), hashlib.sha256(payload).digest()) + payload


def parse_frame(data, offset):
    if len(data) - offset < HEADER.size:
        return None
    magic, length, digest = HEADER.unpack_from(data, offset)
    start = offset + HEADER.size
    if magic != MAGIC or start + length > len(data):
        return None
    payload = data[start:start + length]
    if hashlib.sha256(payload).digest() != digest:
        return None
    return payload, start + length


def scan(data):
    frames, offset = [], 0
    while offset < len(data):
        parsed = parse_frame(data, offset)
        if parsed is None:
            break
        payload, offset = parsed
        frames.append(payload)
    if offset < len(data):
        position = data.find(MAGIC, offset + 1)
        while position != -1:
            if parse_frame(data, position):
                raise JournalCorrupt(f"damaged frame at byte {offset} is followed by a valid frame at byte {position}")
            position = data.find(MAGIC, position + 1)
    return frames, offset


_libc = ctypes.CDLL(None, use_errno=True)
_syncfs = getattr(_libc, "syncfs", None)


def fsync_path(path, directory=False):
    try:
        fd = os.open(path, os.O_RDONLY | (os.O_DIRECTORY if directory else 0))
    except FileNotFoundError:
        return 0
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return 1


def make_durable(paths):
    syncs, devices = 0, {}
    for path in paths:
        parent = Path(path).parent
        try:
            devices.setdefault(parent.stat().st_dev, (parent, []))[1].append(path)
        except FileNotFoundError:
            continue
    for parent, members in devices.values():
        if _syncfs is not None:
            fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                if _syncfs(fd) != 0:
                    error = ctypes.get_errno()
                    raise OSError(error, os.strerror(error), str(parent))
            finally:
                os.close(fd)
            syncs += 1
            continue
        for path in members:
            syncs += fsync_path(path) + fsync_path(path + "-wal") + fsync_path(os.path.dirname(path), True)
    return syncs


def ledger_connection(path):
    ledger = Ledger.__new__(Ledger)
    ledger.path = str(path)
    fresh = not os.path.exists(ledger.path) or os.path.getsize(ledger.path) == 0
    db = ledger._connect()
    quiet = hasattr(db, "setconfig") and hasattr(sqlite3, "SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE")
    mode = "OFF" if quiet else "NORMAL"
    if fresh:
        db.execute(f"PRAGMA synchronous={mode}")
        db.execute("PRAGMA journal_mode=WAL")
    if db.execute("PRAGMA journal_mode").fetchone()[0] == "wal":
        db.execute(f"PRAGMA synchronous={mode}")
        db.execute("PRAGMA cache_size=-256")
        if quiet:
            db.execute("PRAGMA wal_autocheckpoint=0")
            db.setconfig(sqlite3.SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)
    else:
        db.execute("PRAGMA synchronous=FULL")
    return ledger, db


class Recorder:
    __slots__ = ("db", "log")

    def __init__(self, db):
        self.db, self.log = db, []

    def execute(self, sql, parameters=()):
        if sql.lstrip()[:6].upper() in WRITES:
            self.log.append([sql, list(parameters)])
        return self.db.execute(sql, parameters)

    def __getattr__(self, name):
        return getattr(self.db, name)


class Journal:
    def __init__(self, directory, segment_bytes=SEGMENT_BYTES):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.segment_bytes = segment_bytes
        self.writer = f"{os.getpid()}-{time.time_ns()}-{os.urandom(4).hex()}"
        self.counts = dict(frames=0, journal_syncs=0, segment_syncs=0, retire_syncs=0, recovery_syncs=0,
                           journal_bytes=0, segments_recovered=0, frames_replayed=0, ledgers_replayed=0,
                           torn_tails=0, conflicts=0, ledgers_missing=0)
        self.retiring = []
        self.serial = 0
        lock = os.open(self.directory / ".recover", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.recover_all()
            self.open_segment()
        finally:
            os.close(lock)

    def open_segment(self):
        self.serial += 1
        name = f"{self.writer}-{self.serial}.journal"
        staging = self.directory / f"{name}.new"
        fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.rename(staging, self.directory / name)
        self.counts["segment_syncs"] += fsync_path(self.directory, True)
        self.fd, self.path, self.size, self.touched = fd, self.directory / name, 0, set()

    def recover_all(self):
        for path in sorted(self.directory.iterdir()):
            if not (path.name.endswith(".journal") or path.name.endswith(".journal.new")):
                continue
            try:
                fd = os.open(path, os.O_RDWR)
            except FileNotFoundError:
                continue
            try:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                if path.name.endswith(".new"):
                    os.unlink(path)
                    continue
                self.recover(path, fd)
            finally:
                os.close(fd)

    def recover(self, path, fd):
        with open(path, "rb") as handle:
            data = handle.read()
        frames, end = scan(data)
        if end < len(data):
            quarantine = path.with_name(f"{path.name}.torn-{end}.{time.time_ns()}")
            with open(quarantine, "xb") as output:
                output.write(data[end:])
                output.flush()
                os.fsync(output.fileno())
            os.ftruncate(fd, end)
            os.fsync(fd)
            self.counts["recovery_syncs"] += 2 + fsync_path(self.directory, True)
            self.counts["torn_tails"] += 1
        pending = {}
        for payload in frames:
            entry = json.loads(payload)
            for ledger_path, version, digest, statements in entry["ledgers"]:
                pending.setdefault(ledger_path, []).append((version, digest, statements))
        for ledger_path, entries in pending.items():
            self.replay(ledger_path, sorted(entries, key=lambda item: item[0]))
        self.counts["recovery_syncs"] += make_durable(list(pending))
        os.unlink(path)
        self.counts["segments_recovered"] += 1

    def replay(self, path, entries):
        if not os.path.isdir(os.path.dirname(path)):
            self.counts["ledgers_missing"] += 1
            return
        conflict = path + ".journal-conflict"
        if os.path.exists(conflict):
            return
        _, db = ledger_connection(path)
        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute(VERSION_TABLE)
            replayed = 0
            for version, digest, statements in entries:
                row = db.execute("SELECT digest FROM ledger_journal WHERE version = ?", (version,)).fetchone()
                if row is not None:
                    if row[0] != digest:
                        raise ValueError(f"ledger holds a different batch at journal version {version}")
                    continue
                current = db.execute("SELECT coalesce(max(version), 0) FROM ledger_journal").fetchone()[0]
                if version != current + 1:
                    raise ValueError(f"journal version {version} does not follow ledger version {current}")
                for sql, parameters in statements:
                    db.execute(sql, parameters)
                db.execute(MARK, (version, digest))
                replayed += 1
            db.commit()
            if replayed:
                self.counts["frames_replayed"] += replayed
                self.counts["ledgers_replayed"] += 1
        except (sqlite3.Error, ValueError) as error:
            db.rollback()
            with open(conflict, "x") as output:
                json.dump(dict(writer=self.writer, error=str(error), versions=[v for v, _, _ in entries]), output)
                output.flush()
                os.fsync(output.fileno())
            self.counts["recovery_syncs"] += 1
            self.counts["conflicts"] += 1
        finally:
            db.close()

    def frame(self, entries):
        self.counts["frames"] += 1
        return encode_frame(f'{{"writer":"{self.writer}","frame":{self.counts["frames"]},"ledgers":[{",".join(text for _, text in entries)}]}}'.encode())

    def append(self, data):
        view = memoryview(data)
        while view:
            view = view[os.write(self.fd, view):]

    def sync(self):
        os.fdatasync(self.fd)
        self.counts["journal_syncs"] += 1

    def write(self, entries):
        data = self.frame(entries)
        self.append(data)
        self.sync()
        self.size += len(data)
        self.counts["journal_bytes"] += len(data)
        self.touched.update(path for path, _ in entries)
        if self.size >= self.segment_bytes:
            old = (self.fd, self.path, self.touched)
            self.open_segment()
            thread = threading.Thread(target=self.retire, args=old)
            thread.start()
            self.retiring.append(thread)

    def retire(self, fd, path, touched):
        self.counts["retire_syncs"] += make_durable(list(touched))
        os.unlink(path)
        os.close(fd)

    def close(self):
        for thread in self.retiring:
            thread.join()
        self.retire(self.fd, self.path, self.touched)


def raise_descriptor_limit(wanted=4 * HANDLES + 64):
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    target = wanted if hard == resource.RLIM_INFINITY else min(hard, wanted)
    if soft != resource.RLIM_INFINITY and soft < target:
        resource.setrlimit(resource.RLIMIT_NOFILE, (target, hard))


class Writer:
    def __init__(self, process, extension=None, journal=None, output=None):
        self.process = process
        self.extension = extension
        self.journal = journal or Journal(journal_directory())
        self.output = output or sys.stdout
        self.handles = OrderedDict()
        self.counts = dict(batches=0, requests=0, max_batch=0, flushes=0)
        self.pending = None
        self.syncer = None
        self.gap = WINDOW
        self.arrived = None

    def start(self):
        self.pending = queue.SimpleQueue()
        self.syncer = threading.Thread(target=self.drain, name="ledger-journal", daemon=True)
        self.syncer.start()

    def handle(self, path, create):
        entry = self.handles.get(path)
        if entry is None:
            if os.path.exists(path + ".journal-conflict"):
                raise ValueError("ledger refused: it disagrees with an acknowledged journal frame")
            if create:
                os.makedirs(os.path.dirname(path), exist_ok=True)
            ledger, db = ledger_connection(path)
            entry = self.handles[path] = [ledger, db, [], True]
        self.handles.move_to_end(path)
        return entry

    def drop(self, path):
        entry = self.handles.pop(path, None)
        if entry:
            entry[1].close()

    def apply(self, path, requests, responses, entries):
        actions = self.extension.LOOP if self.extension else {}
        answered = []
        try:
            entry = self.handle(path, any(r["action"] == "admit" for r in requests))
            ledger, db, cache, schema = entry
            db.execute("BEGIN IMMEDIATE")
            try:
                head = Recorder(db)
                if schema:
                    for statement in TABLES:
                        head.execute(statement)
                head.execute(VERSION_TABLE)
                version = db.execute("SELECT coalesce(max(version), 0) FROM ledger_journal").fetchone()[0] + 1
                statements, applied = head.log, False
                prior, previous = ledger._read(db, cache)
                for request in requests:
                    recorder = Recorder(db)
                    db.execute("SAVEPOINT request")
                    saved_prior, saved_previous = dict(prior), previous

                    def append(record):
                        nonlocal previous
                        previous = ledger._append(recorder, record, prior, previous)
                        return previous

                    try:
                        action = actions.get(request["action"])
                        result = (action(request, prior, append, self.process, recorder) if action
                                  else self.process(request, prior, append))
                        answered.append(dict(id=request["id"], result=result))
                        statements.extend(recorder.log)
                        applied = True
                    except Exception as error:
                        db.execute("ROLLBACK TO request")
                        prior, previous = saved_prior, saved_previous
                        answered.append(dict(id=request["id"], error=str(error)))
                    db.execute("RELEASE request")
                if applied:
                    encoded = json.dumps(statements, separators=(",", ":"))
                    digest = hashlib.sha256(encoded.encode()).hexdigest()
                    db.execute(MARK, (version, digest))
                db.commit()
                entry[3] = False
            except Exception:
                db.rollback()
                cache.clear()
                raise
            if applied:
                entries.append((path, f'[{json.dumps(path)},{version},"{digest}",{encoded}]'))
        except Exception as error:
            self.drop(path)
            answered = [dict(id=r["id"], error=str(error)) for r in requests]
        responses.extend(answered)

    def batch(self, lines):
        groups = {}
        for line in lines:
            request = json.loads(line)
            groups.setdefault(request["job"]["reference"]["ledger"], []).append(request)
        responses, entries = [], []
        for path, requests in groups.items():
            self.apply(path, requests, responses, entries)
        now = time.monotonic()
        if self.arrived is not None:
            self.gap += ((now - self.arrived) / len(lines) - self.gap) / 8
        self.arrived = now
        self.counts["batches"] += 1
        self.counts["requests"] += len(lines)
        self.counts["max_batch"] = max(self.counts["max_batch"], len(lines))
        while len(self.handles) > HANDLES:
            self.handles.popitem(last=False)[1][1].close()
        if self.pending is None:
            self.flush([(entries, responses)])
        else:
            self.pending.put((entries, responses))

    def drain(self):
        while True:
            items = [self.pending.get()]
            deadline = time.monotonic() + (WINDOW if self.gap < WINDOW / 2 else 0)
            while items[-1] is not None:
                waiting = sum(len(responses) for _, responses in items)
                remaining = deadline - time.monotonic()
                try:
                    items.append(self.pending.get(timeout=remaining) if waiting < GROUP and remaining > 0
                                 else self.pending.get_nowait())
                except queue.Empty:
                    break
            stop = items[-1] is None
            if stop:
                items.pop()
            if items:
                try:
                    self.flush(items)
                except BaseException:
                    traceback.print_exc()
                    os._exit(70)
            if stop:
                return

    def flush(self, items):
        entries = [entry for batch, _ in items for entry in batch]
        if entries:
            self.journal.write(entries)
        write_decision = getattr(self.extension, "write_decision", None)
        out = []
        for _, responses in items:
            for response in responses:
                if write_decision:
                    try:
                        write_decision(response.get("result"))
                    except Exception as error:
                        response = dict(id=response["id"], error=str(error))
                out.append(json.dumps(response) + "\n")
        self.counts["flushes"] += 1
        self.respond(out)

    def respond(self, lines):
        self.output.write("".join(lines))
        self.output.flush()

    def close(self):
        if self.syncer is not None:
            self.pending.put(None)
            self.syncer.join()
        for entry in self.handles.values():
            entry[1].close()
        self.handles.clear()
        self.journal.close()

    def stats(self):
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return dict(self.counts, **self.journal.counts, user=usage.ru_utime, system=usage.ru_stime,
                    max_rss_kib=usage.ru_maxrss)


def serve(process, extension=None, source=0):
    raise_descriptor_limit()
    writer = Writer(process, extension)
    writer.respond([json.dumps(dict(id=0, result="ready")) + "\n"])
    writer.start()
    lines, partial, ended = deque(), [], False
    while lines or not ended:
        while not ended and (not lines or select.select([source], [], [], 0)[0]):
            chunk = os.read(source, 1 << 20)
            if not chunk:
                ended = True
                break
            pieces = chunk.split(b"\n")
            if len(pieces) > 1:
                lines.append(b"".join(partial + [pieces[0]]))
                lines.extend(pieces[1:-1])
                partial = []
            if pieces[-1]:
                partial.append(pieces[-1])
            if len(lines) >= BATCH:
                break
        if lines:
            writer.batch([lines.popleft() for _ in range(min(BATCH, len(lines)))])
    writer.close()
    report = os.environ.get("ENDOFORGE_LEDGER_STATS")
    if report:
        with open(report, "w") as output:
            json.dump(writer.stats(), output)
