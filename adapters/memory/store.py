"""Private knowledge storage. M1 callers must supply host-sanitized content."""
import math
import os
import re
import sqlite3
import struct
from contextlib import contextmanager
from contextlib import closing
from pathlib import Path

from adapters.memory.redact import has_secret
from adapters.memory.nrm_wall import Wall
from adapters.memory_ledger import EVENT_KINDS
from adapters.private_sqlite import open_private_db
from poodo_core.models import ContractError, canonical, digest, identifier, prose

TRUST_TIERS = ("user_confirmed", "operator_curated", "tool_observed", "agent_written",
               "unknown", "external_untrusted")
FACT_KINDS = EVENT_KINDS + ("reference",)
_STATUSES = ("proposed", "confirmed", "rejected")
_COUNTERS = ("files", "threads", "subagent_threads", "messages", "facts_added", "duplicates", "redactions", "nrm_wall",
             "secret_residue", "unparseable", "empty")
_SCHEMA = """CREATE TABLE schema_versions (
    version INTEGER PRIMARY KEY CHECK (version > 0), applied_at INTEGER NOT NULL
) STRICT;
CREATE TABLE facts (
    fact_pk INTEGER PRIMARY KEY, fact_id TEXT NOT NULL UNIQUE,
    text TEXT NOT NULL CHECK (length(text) BETWEEN 1 AND 4000),
    kind TEXT NOT NULL CHECK (kind IN ('proposal','observation','inference','decision','action','outcome','learning','correction','reference')),
    archive_label TEXT NOT NULL, thread_id TEXT NOT NULL,
    line_offset INTEGER NOT NULL CHECK (line_offset >= 0),
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    role TEXT NOT NULL,
    source_trust TEXT NOT NULL CHECK (source_trust IN ('operator_curated','tool_observed','agent_written','unknown','external_untrusted')),
    trust TEXT NOT NULL CHECK (trust IN ('user_confirmed','operator_curated','tool_observed','agent_written','unknown','external_untrusted')),
    status TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','confirmed','rejected')),
    created_at INTEGER NOT NULL, decided_by TEXT, decided_at INTEGER, note TEXT,
    ledger_ref TEXT CHECK (ledger_ref IS NULL OR
        (length(ledger_ref) = 64 AND ledger_ref NOT GLOB '*[^0-9a-f]*')),
    ref_source TEXT, ref_path TEXT,
    ref_sha256 TEXT CHECK (ref_sha256 IS NULL OR
        (length(ref_sha256) = 64 AND ref_sha256 NOT GLOB '*[^0-9a-f]*')),
    embedding BLOB CHECK (embedding IS NULL OR (length(embedding) BETWEEN 4 AND 16384
                                               AND length(embedding) % 4 = 0)),
    ref_vec_id TEXT,
    CHECK ((kind = 'reference' AND ref_source IS NOT NULL AND ref_path IS NOT NULL
            AND ref_sha256 IS NOT NULL) OR
           (kind != 'reference' AND ref_source IS NULL AND ref_path IS NULL
            AND ref_sha256 IS NULL AND embedding IS NULL AND ref_vec_id IS NULL)),
    CHECK ((status = 'confirmed' AND trust = 'user_confirmed') OR
           (status IN ('proposed','rejected') AND trust = source_trust)),
    CHECK ((status = 'proposed' AND decided_by IS NULL AND decided_at IS NULL
            AND note IS NULL AND ledger_ref IS NULL) OR
           (status IN ('confirmed','rejected') AND decided_by IS NOT NULL AND decided_at IS NOT NULL)),
    CHECK (status != 'rejected' OR (note IS NOT NULL AND length(trim(note)) > 0))
) STRICT;
CREATE UNIQUE INDEX facts_provenance ON facts
    (archive_label, thread_id, line_offset, chunk_index, role, coalesce(ref_sha256, ''));
CREATE INDEX facts_status_order ON facts(status, created_at, fact_id);
CREATE VIRTUAL TABLE facts_fts USING fts5(
    text, content='facts', content_rowid='fact_pk', tokenize='unicode61');
CREATE TRIGGER facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, text) VALUES (new.fact_pk, new.text);
END;
CREATE TRIGGER facts_au AFTER UPDATE OF text ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, text) VALUES ('delete', old.fact_pk, old.text);
    INSERT INTO facts_fts(rowid, text) VALUES (new.fact_pk, new.text);
END;
CREATE TRIGGER facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, text) VALUES ('delete', old.fact_pk, old.text);
END;
CREATE TRIGGER facts_no_delete BEFORE DELETE ON facts BEGIN
    SELECT RAISE(ABORT, 'Facts cannot be deleted');
END;
CREATE TRIGGER facts_terminal BEFORE UPDATE ON facts
WHEN old.status != 'proposed' OR new.status NOT IN ('confirmed','rejected') BEGIN
    SELECT RAISE(ABORT, 'Only one terminal review is allowed');
END;
INSERT INTO schema_versions(version, applied_at) VALUES (1, ?);
"""

_SCHEMA2 = """ALTER TABLE facts ADD COLUMN source_ts TEXT;
ALTER TABLE facts ADD COLUMN parent_thread_id TEXT;
CREATE TABLE ingest_runs (
    run_id TEXT PRIMARY KEY NOT NULL, archive_label TEXT NOT NULL,
    started_at INTEGER NOT NULL, finished_at INTEGER NOT NULL,
""" + "".join(f"    {k} INTEGER NOT NULL CHECK ({k} >= 0),\n" for k in _COUNTERS) + """    ledger_ref TEXT CHECK (ledger_ref IS NULL OR
        (length(ledger_ref) = 64 AND ledger_ref NOT GLOB '*[^0-9a-f]*'))
) STRICT;
CREATE TRIGGER ingest_runs_no_delete BEFORE DELETE ON ingest_runs BEGIN
    SELECT RAISE(ABORT, 'Receipts cannot be deleted');
END;
CREATE TRIGGER ingest_runs_no_update BEFORE UPDATE ON ingest_runs BEGIN
    SELECT RAISE(ABORT, 'Receipts are immutable');
END;
INSERT INTO schema_versions(version, applied_at) VALUES (2, ?);
"""


def _safe(*values):
    if any("\0" in v or Wall().text_blocked(v) or has_secret(v) for v in values):
        raise ContractError("Unsafe memory content")


def _integer(value, minimum=0):
    if type(value) is not int or not minimum <= value <= 2**63 - 1:
        raise ContractError("Expected a bounded integer")
    return value

def _fact_id(value):
    if type(value) is not str or re.fullmatch(r"fact-[0-9a-f]{64}", value) is None:
        raise ContractError("Invalid fact identifier")
    return value

class MemoryStore:
    def __init__(self, path=None, *, clock, ledger=None):
        path = os.environ.get("CSTACK_MEMORY_DB") if path is None else path
        if not isinstance(path, (str, Path)) or not str(path) or not callable(clock):
            raise ContractError("Memory requires an explicit path and host clock")
        self._clock, self._db = clock, None
        self._ledger = ledger
        try:
            self._db, self._fd = open_private_db(Path(path))
            self._db.row_factory = sqlite3.Row
            with self._transaction() as db:
                statements, pending = [], ""
                for line in (_SCHEMA + _SCHEMA2).splitlines(True):
                    pending += line
                    if sqlite3.complete_statement(pending):
                        statements.append(pending.strip())
                        pending = ""
                objects = db.execute("SELECT name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
                if not objects:
                    for statement in statements:
                        db.execute(statement, (self._now(),) if statement.startswith("INSERT") else ())
                else:
                    normalize = lambda sql: re.sub(r"\s+", " ", sql).strip().rstrip(";")
                    versions = [r[0] for r in db.execute("SELECT version FROM schema_versions ORDER BY version")]
                    if versions not in ([1], [1, 2]):
                        raise ContractError("Unsupported memory schema version")
                    boundary = next(i for i, s in enumerate(statements)
                                    if s.startswith("ALTER TABLE"))
                    current = statements if versions == [1, 2] else statements[:boundary]
                    # Let SQLite render ALTERed table SQL, including M1's reference constraints.
                    with closing(sqlite3.connect(":memory:")) as model:
                        for statement in current:
                            model.execute(statement, (0,) if statement.startswith("INSERT") else ())
                        expected = {normalize(r[0]) for r in model.execute(
                            "SELECT sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")}
                    if {normalize(row[1]) for row in objects} != expected:
                        raise ContractError("Unsupported or incomplete memory schema")
                    if versions == [1]:
                        for statement in statements[len(current):]:
                            db.execute(statement, (self._now(),) if statement.startswith("INSERT") else ())
        except (ContractError, OSError, sqlite3.Error, ValueError, TypeError):
            self.close()
            raise ContractError("Could not initialize private memory storage") from None

    def _open(self):
        if self._db is None:
            raise ContractError("Memory store is closed")
        return self._db

    def _now(self):
        try:
            return _integer(self._clock(), -(2**63))
        except Exception:
            raise ContractError("Host clock must return integer epoch seconds") from None

    @contextmanager
    def _transaction(self, *, join=False):
        db = self._open()
        if join and db.in_transaction:
            yield db
            return
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception as error:
            db.rollback()
            if isinstance(error, sqlite3.Error):
                raise ContractError("Memory transaction failed") from None
            raise

    def close(self):
        db, self._db = self._db, None
        if db is not None:
            try:
                db.close()
            finally:
                os.close(self._fd)

    def _rows(self, sql, parameters=()):
        try:
            rows = self._open().execute(sql, parameters).fetchall()
        except sqlite3.Error:
            raise ContractError("Memory read failed") from None
        results = []
        for row in rows:
            fact = {key: row[key] for key in row.keys() if key != "fact_pk"}
            blob = fact.pop("embedding")
            fact["embedding_dims"] = len(blob) // 4 if blob is not None else None
            fact["trust_label"] = "trust:" + fact["trust"]
            results.append(fact)
        return results

    def propose(self, text, *, archive_label, thread_id, line_offset, chunk_index, role,
                kind="proposal", trust="unknown", source_ts=None, parent_thread_id=None):
        if kind not in EVENT_KINDS:
            raise ContractError("Use propose_reference for reference documents")
        return self._propose(text, [archive_label, thread_id, line_offset, chunk_index, role], kind, trust,
                             source_ts=source_ts, parent_thread_id=parent_thread_id)

    def propose_reference(self, text, *, source, path, checksum, chunk_index=0,
                          trust="operator_curated", embedding=None, ref_vec_id=None):
        self._open()
        if type(checksum) is not str or re.fullmatch(r"[0-9a-f]{64}", checksum) is None:
            raise ContractError("Invalid reference checksum")
        if ref_vec_id is not None:
            identifier(ref_vec_id)
        if embedding is not None:
            if (type(embedding) not in (list, tuple) or not 1 <= len(embedding) <= 4096 or
                    any(type(v) is not float or not math.isfinite(v) for v in embedding)):
                raise ContractError("Invalid reference embedding")
            try:
                embedding = struct.pack("<%df" % len(embedding), *embedding)
            except (OverflowError, struct.error):
                raise ContractError("Embedding exceeds float32 range") from None
        return self._propose(text, [source, path, 0, chunk_index, "reference"], "reference", trust,
                             (source, path, checksum, embedding, ref_vec_id))

    def _propose(self, text, provenance, kind, trust, reference=(None,) * 5, *, source_ts=None, parent_thread_id=None):
        self._open()
        prose(text, 4000)
        if "\0" in text or trust not in TRUST_TIERS[1:]:
            raise ContractError("Invalid fact content or classification")
        archive, thread, line, chunk, role = provenance
        provenance = [identifier(archive), prose(thread, 512), _integer(line), _integer(chunk), identifier(role)]
        for value, maximum in ((source_ts, 64), (parent_thread_id, 512)):
            if value is not None:
                prose(value, maximum)
                _safe(value)
        _safe(text, archive, thread, role, *(v for v in reference if isinstance(v, str)))
        identity = provenance + ([reference[2]] if kind == "reference" else [])
        fact_id = "fact-" + digest(["cstack.memory.fact/1", *identity])
        with self._transaction(join=True) as db:
            existing = self.get(fact_id)
            if existing:
                fields = ("archive_label", "thread_id", "line_offset", "chunk_index", "role",
                          "text", "kind", "source_trust", "ref_source", "ref_path", "ref_sha256", "ref_vec_id")
                blob = db.execute("SELECT embedding FROM facts WHERE fact_id=?", (fact_id,)).fetchone()[0]
                if ([existing[k] for k in fields] !=
                        [*provenance, text, kind, trust, *reference[:3], reference[4]] or blob != reference[3]):
                    raise ContractError("Conflicting fact provenance")
                return existing, False
            db.execute("""INSERT INTO facts (fact_id, text, kind, archive_label, thread_id,
                line_offset, chunk_index, role, source_trust, trust, created_at,
                ref_source, ref_path, ref_sha256, embedding, ref_vec_id, source_ts, parent_thread_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (fact_id, text, kind, *provenance, trust, trust, self._now(), *reference, source_ts, parent_thread_id))
        return self.get(fact_id), True

    def embedding(self, fact_id):
        try:
            row = self._open().execute("SELECT embedding FROM facts WHERE fact_id=?", (_fact_id(fact_id),)).fetchone()
        except sqlite3.Error:
            raise ContractError("Memory read failed") from None
        blob = row[0] if row else None
        return list(struct.unpack("<%df" % (len(blob) // 4), blob)) if blob is not None else None

    def get(self, fact_id):
        rows = self._rows("SELECT * FROM facts WHERE fact_id=?", (_fact_id(fact_id),))
        return rows[0] if rows else None

    def _filter(self, status, limit):
        self._open()
        if (status is not None and status not in _STATUSES) or _integer(limit, 1) > 1000:
            raise ContractError("Invalid fact status or result limit")

    def list(self, *, status="proposed", limit=100):
        self._filter(status, limit)
        return self._rows("""SELECT * FROM facts WHERE (? IS NULL OR status=?)
            ORDER BY created_at, fact_id LIMIT ?""", (status, status, limit))

    def search(self, query, *, status=None, limit=20):
        self._filter(status, limit)
        terms = re.findall(r"[^\W_]+", prose(query, 4096))
        if not terms:
            return []
        match = " AND ".join('"' + term.replace('"', '""') + '"' for term in terms)
        return self._rows("""SELECT f.*, bm25(facts_fts) AS score
            FROM facts_fts JOIN facts AS f ON f.fact_pk = facts_fts.rowid
            WHERE facts_fts MATCH ? AND (? IS NULL OR f.status = ?)
            ORDER BY score ASC, f.fact_id ASC LIMIT ?""", (match, status, status, limit))

    def confirm(self, fact_id, *, by, note=None, ledger_ref=None):
        return self._review(fact_id, "confirmed", by, note, ledger_ref)

    def reject(self, fact_id, *, by, note, ledger_ref=None):
        prose(note, 4096)
        return self._review(fact_id, "rejected", by, note, ledger_ref)

    def _review(self, fact_id, status, by, note, ledger_ref):
        self._open()
        _fact_id(fact_id)
        identifier(by)
        if note is not None:
            prose(note, 4096)
        if self._ledger is not None and ledger_ref is not None:
            raise ContractError("Cannot supply ledger_ref with a ledger")
        if ledger_ref is not None and (type(ledger_ref) is not str or
                                     re.fullmatch(r"[0-9a-f]{64}", ledger_ref) is None):
            raise ContractError("Invalid ledger reference")
        _safe(by, *(() if note is None else (note,)))
        now = self._now()
        with self._transaction() as db:
            fact = self.get(fact_id)
            if fact is None or fact["status"] != "proposed":
                raise ContractError("Review requires a proposed fact")
            if self._ledger is not None:
                data = dict(action="memory_review", fact_id=fact_id, status=status, by=by)
                self._ledger.reserve(1, len(canonical(data).encode("ascii")))
                event = self._ledger.append("decision", data)
                ref = (event.get("hash") or event.get("event_sha256")) if isinstance(event, dict) else None
                if type(ref) is not str or re.fullmatch(r"[0-9a-f]{64}", ref) is None:
                    raise ContractError("Invalid review ledger hash")
                ledger_ref = ref
            trust = "user_confirmed" if status == "confirmed" else fact["source_trust"]
            updated = db.execute("""UPDATE facts SET status=?, trust=?, decided_by=?, decided_at=?,
                note=?, ledger_ref=? WHERE fact_id=? AND status='proposed'""",
                                 (status, trust, by, now, note, ledger_ref, fact_id))
            if updated.rowcount != 1:
                raise ContractError("Review requires a proposed fact")
        return self.get(fact_id)

    def _insert_receipt(self, receipt):
        values = dict(receipt)
        columns = ("run_id", "archive_label", "started_at", "finished_at", *_COUNTERS, "ledger_ref")
        self._open().execute("INSERT INTO ingest_runs (" + ",".join(columns) +
                             ") VALUES (" + ",".join("?" for _ in columns) + ")",
                             tuple(values[k] for k in columns))
        return values

    def stats(self):
        self._open()
        try:
            counts = dict(self._db.execute("SELECT status, count(*) FROM facts GROUP BY status"))
            sums = ",".join("coalesce(sum(" + k + "),0)" for k in _COUNTERS)
            totals = self._db.execute("SELECT count(*)," + sums + " FROM ingest_runs").fetchone()
        except sqlite3.Error:
            raise ContractError("Memory read failed") from None
        return {"facts": {status: counts.get(status, 0) for status in _STATUSES},
                "ingest_runs": totals[0], "ingest_totals": dict(zip(_COUNTERS, totals[1:]))}
