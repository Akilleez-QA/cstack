"""Pure bounded revision applicability accounting. Never a theorem verifier."""
from __future__ import annotations

import hashlib
import json
import re
from collections import deque
from typing import Any

VERSION = "foundation-math-claim-revision/1"
MAX_INPUT_BYTES = 262144
MAX_RECORDS = 64
MAX_EDGES = 256
MAX_EVENTS = 64
MAX_REASONS = 4096
MAX_PATH_PINS = 32768
MAX_OUTPUT_BYTES = 4194304
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
KINDS = ("claim", "obligation", "evidence")
STATUSES = ("open", "draft", "claimed_established", "claimed_refuted")
EVIDENCE_TYPES = ("informal_argument", "exact_computation", "independent_review", "formal_proof_report", "counterexample_report")
_BODY_FIELDS = {"id", "revision", "kind", "content", "dependencies"}
_RECORD_FIELDS = _BODY_FIELDS | {"content_sha256", "revision_sha256"}


class LedgerError(ValueError):
    """Explicit failure, with machine-readable code and location; no partial result."""
    def __init__(self, code: str, path: str, message: str):
        self.code, self.path = code, path
        super().__init__(f"{code} at {path}: {message}")


def _fail(code: str, path: str, message: str) -> None:
    raise LedgerError(code, path, message)


def _guard(value: Any) -> None:
    """Bound and reject non-JSON Python types before serialization, including cycles."""
    stack, count = [(value, 0)], 0
    while stack:
        item, depth = stack.pop()
        count += 1
        if count > 65536 or depth > 16:
            _fail("budget_exceeded", "$", "JSON node/depth budget exceeded")
        if type(item) is dict:
            if len(item) > 32:
                _fail("budget_exceeded", "$", "Too many object fields")
            for key, val in item.items():
                if type(key) is not str or len(key) > 128:
                    _fail("malformed_type", "$", "Object keys must be short strings")
                try:
                    key.encode("utf-8")
                except UnicodeEncodeError:
                    _fail("malformed_type", "$", "Unpaired Unicode surrogate in object key")
                stack.append((val, depth + 1))
        elif type(item) is list:
            if len(item) > 4096:
                _fail("budget_exceeded", "$", "Array budget exceeded")
            stack.extend((val, depth + 1) for val in item)
        elif type(item) is str:
            if len(item) > 8192:
                _fail("budget_exceeded", "$", "String budget exceeded")
            try:
                item.encode("utf-8")
            except UnicodeEncodeError:
                _fail("malformed_type", "$", "Unpaired Unicode surrogate")
        elif type(item) is int:
            if item.bit_length() > 32:
                _fail("budget_exceeded", "$", "Integer budget exceeded")
        elif item is not None and type(item) is not bool:
            _fail("malformed_type", "$", "Only ordinary JSON data is accepted; no floats")


def canonical_bytes(value: Any) -> bytes:
    """Internal canonical JSON: UTF-8, sorted keys, compact, no normalization."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    _guard(value)
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _obj(value: Any, fields: set[str], path: str) -> dict:
    if type(value) is not dict:
        _fail("malformed_type", path, "Expected an object")
    if set(value) != fields:
        _fail("fields", path, "Missing or unsupported fields")
    return value


def _text(value: Any, path: str, maximum: int = 2048) -> None:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        _fail("malformed_type", path, f"Expected nonblank text of at most {maximum} characters")


def _identifier(value: Any, path: str) -> None:
    if type(value) is not str or _ID.fullmatch(value) is None:
        _fail("malformed_type", path, "Expected a simple 1-64 character identifier")


def _hash(value: Any, path: str) -> None:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        _fail("malformed_type", path, "Expected a lowercase SHA-256 hex string")


def _revision(value: Any, path: str) -> None:
    if type(value) is not int or not 1 <= value <= 1000000:
        _fail("malformed_type", path, "Expected revision integer 1..1000000 (not bool)")


def _pin(value: Any, path: str) -> None:
    _obj(value, {"id", "revision", "revision_sha256"}, path)
    _identifier(value["id"], path + ".id")
    _revision(value["revision"], path + ".revision")
    _hash(value["revision_sha256"], path + ".revision_sha256")


def pin(record: dict) -> dict:
    return {key: record[key] for key in ("id", "revision", "revision_sha256")}


def _content(kind: str, content: Any, path: str) -> None:
    fields = {
        "claim": {"statement", "scope", "assumptions", "non_claims", "authored_status"},
        "obligation": {"requirement", "authored_status"},
        "evidence": {"description", "evidence_type", "artifact_sha256", "authored_status"},
    }[kind]
    _obj(content, fields, path)
    if type(content["authored_status"]) is not str or content["authored_status"] not in STATUSES:
        _fail("malformed_type", path + ".authored_status", "Unknown authored status")
    if kind == "claim":
        _text(content["statement"], path + ".statement")
        if type(content["scope"]) is not str or content["scope"] not in ("universal", "generic", "existential", "instance", "conditional"):
            _fail("malformed_type", path + ".scope", "Unknown scope")
        for field in ("assumptions", "non_claims"):
            values = content[field]
            if type(values) is not list or len(values) > 32:
                _fail("malformed_type", path + "." + field, "Expected at most 32 text entries")
            for i, value in enumerate(values):
                _text(value, f"{path}.{field}[{i}]")
    elif kind == "obligation":
        _text(content["requirement"], path + ".requirement")
    else:
        _text(content["description"], path + ".description")
        if type(content["evidence_type"]) is not str or content["evidence_type"] not in EVIDENCE_TYPES:
            _fail("malformed_type", path + ".evidence_type", "Unknown evidence type")
        _hash(content["artifact_sha256"], path + ".artifact_sha256")


def _body(body: Any, path: str) -> None:
    _obj(body, _BODY_FIELDS, path)
    _identifier(body["id"], path + ".id")
    _revision(body["revision"], path + ".revision")
    if type(body["kind"]) is not str or body["kind"] not in KINDS:
        _fail("malformed_type", path + ".kind", "Unknown record kind")
    _content(body["kind"], body["content"], path + ".content")
    deps = body["dependencies"]
    if type(deps) is not list or len(deps) > MAX_RECORDS:
        _fail("budget_exceeded", path + ".dependencies", "Expected a bounded dependency list")
    seen = set()
    for i, dep in enumerate(deps):
        p = f"{path}.dependencies[{i}]"
        _pin(dep, p)
        if dep["id"] in seen:
            _fail("duplicate_dependency", p, "At most one all-required edge per target ID")
        if dep["id"] == body["id"]:
            _fail("cycle", p, "Self dependencies are forbidden, including older revisions")
        seen.add(dep["id"])


def seal_record(body: Any) -> dict:
    """Build integrity digests, NOT evidence approval. Caller must supply exact pins."""
    _guard(body)
    _body(body, "record")
    result = json.loads(canonical_bytes(body))
    result["content_sha256"] = digest(result["content"])
    result["revision_sha256"] = digest(result)
    return result


def _record(value: Any, path: str) -> dict:
    _obj(value, _RECORD_FIELDS, path)
    _body({key: value[key] for key in _BODY_FIELDS}, path)
    _hash(value["content_sha256"], path + ".content_sha256")
    _hash(value["revision_sha256"], path + ".revision_sha256")
    if digest(value["content"]) != value["content_sha256"]:
        _fail("content_hash_mismatch", path, "Content bytes do not match the declared digest")
    body = {key: val for key, val in value.items() if key != "revision_sha256"}
    if digest(body) != value["revision_sha256"]:
        _fail("revision_hash_mismatch", path, "Revision body does not match the declared digest")
    return value


def _match(target: dict, current: dict[str, dict], path: str) -> dict:
    _pin(target, path)
    if target["id"] not in current:
        _fail("missing_reference", path, "Target ID does not exist")
    record = current[target["id"]]
    if target != pin(record):
        _fail("pin_mismatch", path, "Exact current revision and hash are required")
    return record


def _topological(current: dict[str, dict]) -> list[str]:
    edge_count = sum(len(record["dependencies"]) for record in current.values())
    if edge_count > MAX_EDGES:
        _fail("budget_exceeded", "records", "Graph edge budget exceeded")
    waiting = {rid: len(record["dependencies"]) for rid, record in current.items()}
    children = {rid: [] for rid in current}
    for rid, record in current.items():
        for dep in record["dependencies"]:
            if dep["id"] not in current:
                _fail("missing_reference", rid, "Dependency ID does not exist")
            children[dep["id"]].append(rid)
    ready, order = deque(sorted(rid for rid, n in waiting.items() if n == 0)), []
    while ready:
        rid = ready.popleft()
        order.append(rid)
        for child in sorted(children[rid]):
            waiting[child] -= 1
            if waiting[child] == 0:
                ready.append(child)
    if len(order) != len(current):
        _fail("cycle", "records", "Cycles in the current stable-ID dependency graph are forbidden")
    return order


def _reason(code: str, origin: dict, event_id: str | None, **details: Any) -> dict:
    cause = {"code": code, "origin": origin, "event_id": event_id, **details}
    return {"cause_id": digest(cause), **cause, "path": [origin]}


def _analyze(current: dict[str, dict], life: dict[tuple[str, int], list[dict]], changed_by: dict[str, str]) -> list[dict]:
    """One canonical shortest witness per cause, not exponential path enumeration."""
    reports, reasons_by_id = {}, {}
    reason_count = path_count = 0
    for rid in _topological(current):
        record, reasons = current[rid], {}
        origin = pin(record)
        for event in life.get((rid, record["revision"]), []):
            code = "revision_withdrawn" if event["kind"] == "withdraw" else "refutation_reported_unchecked"
            details = {"reason": event["reason"]}
            if "evidence" in event:
                details["reported_evidence"] = event["evidence"]
            r = _reason(code, origin, event["id"], **details)
            reasons[r["cause_id"]] = r
        for dep in sorted(record["dependencies"], key=lambda value: value["id"]):
            actual = pin(current[dep["id"]])
            if dep != actual:
                r = _reason("dependency_revision_not_current", origin, changed_by.get(dep["id"]), expected=dep, current=actual)
                r["path"].append(dep)
                reasons[r["cause_id"]] = r
            else:
                for r in reasons_by_id[dep["id"]]:
                    candidate = {**r, "path": [origin] + r["path"]}
                    old = reasons.get(r["cause_id"])
                    if old is None or (len(candidate["path"]), canonical_bytes(candidate["path"])) < (len(old["path"]), canonical_bytes(old["path"])):
                        reasons[r["cause_id"]] = candidate
        ordered = [reasons[key] for key in sorted(reasons)]
        reason_count += len(ordered)
        path_count += sum(len(r["path"]) for r in ordered)
        if reason_count > MAX_REASONS or path_count > MAX_PATH_PINS:
            _fail("budget_exceeded", "analysis", "Reason/path output budget exceeded; no partial result")
        reasons_by_id[rid] = ordered
        reports[rid] = {"pin": origin, "kind": record["kind"],
            "applicability": "blocked" if ordered else "no_recorded_dependency_blockers",
            "authored_status": record["content"]["authored_status"],
            "truth_assessment": "not_assessed", "proof_accepted": False, "reasons": ordered}
    return [reports[rid] for rid in sorted(reports)]


def loads(text: Any) -> dict:
    """Strict bounded JSON entrypoint, rejecting duplicate object keys."""
    if type(text) not in (str, bytes):
        _fail("malformed_type", "$", "Expected UTF-8 JSON text or bytes")
    try:
        raw = text.encode("utf-8") if type(text) is str else text
        if len(raw) > MAX_INPUT_BYTES:
            _fail("budget_exceeded", "$", "Input byte budget exceeded")
        def pairs(entries: list[tuple[str, Any]]) -> dict:
            result = {}
            for key, value in entries:
                if key in result:
                    _fail("duplicate_key", "$", "Duplicate JSON object key")
                result[key] = value
            return result
        def invalid_constant(value: str) -> None:
            _fail("malformed_type", "$", "Nonfinite JSON constant")
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, LedgerError):
            raise
        _fail("malformed_json", "$", "Invalid UTF-8 JSON")
    _guard(value)
    return value


def replay(document: Any) -> dict:
    """Atomically validate and replay a complete bounded document, without I/O."""
    _guard(document)
    if len(canonical_bytes(document)) > MAX_INPUT_BYTES:
        _fail("budget_exceeded", "$", "Input byte budget exceeded")
    _obj(document, {"schema", "records", "events"}, "$")
    if type(document["schema"]) is not str or document["schema"] != VERSION:
        _fail("schema", "schema", "Unsupported schema")
    records, events = document["records"], document["events"]
    if type(records) is not list or not 1 <= len(records) <= MAX_RECORDS:
        _fail("budget_exceeded", "records", "Expected 1..64 initial records")
    if type(events) is not list or len(events) > MAX_EVENTS:
        _fail("budget_exceeded", "events", "Expected at most 64 events")
    # Detach all data; no input object can subsequently mutate the result.
    detached = json.loads(canonical_bytes(document))
    records, events = detached["records"], detached["events"]
    current, history, life, changed_by, seen_events = {}, [], {}, {}, set()
    for index, record in enumerate(records):
        path = f"records[{index}]"
        _record(record, path)
        if record["id"] in current:
            _fail("duplicate_id", path, "Initial record IDs must be unique")
        current[record["id"]] = record
        history.append(record)
    for record in records:
        for i, dep in enumerate(record["dependencies"]):
            _match(dep, current, f"{record['id']}.dependencies[{i}]")
    _topological(current)
    for i, event in enumerate(events):
        path = f"events[{i}]"
        if type(event) is not dict:
            _fail("malformed_type", path, "Expected an event object")
        kind = event.get("kind")
        if type(kind) is not str or kind not in ("withdraw", "revise", "record_refutation_report"):
            _fail("malformed_type", path, "Unknown event kind")
        fields = {"id", "kind", "target", "reason"}
        if kind == "revise":
            fields.add("replacement")
        if kind == "record_refutation_report":
            fields.add("evidence")
        _obj(event, fields, path)
        _identifier(event["id"], path + ".id")
        if event["id"] in seen_events:
            _fail("duplicate_id", path, "Event IDs must be unique in their namespace")
        seen_events.add(event["id"])
        _text(event["reason"], path + ".reason")
        target = _match(event["target"], current, path + ".target")
        key = (target["id"], target["revision"])
        if kind == "revise":
            new = _record(event["replacement"], path + ".replacement")
            if new["id"] != target["id"] or new["kind"] != target["kind"] or new["revision"] != target["revision"] + 1:
                _fail("invalid_revision", path, "Replacement must preserve ID/kind and increment revision by one")
            for j, dep in enumerate(new["dependencies"]):
                _match(dep, current, f"{path}.replacement.dependencies[{j}]")
            current[target["id"]] = new
            _topological(current)
            changed_by[target["id"]] = event["id"]
            history.append(new)
        else:
            if any(old["kind"] == kind for old in life.get(key, [])):
                _fail("duplicate_transition", path, "This lifecycle event kind was already recorded for this revision")
            if kind == "record_refutation_report":
                if target["kind"] != "claim":
                    _fail("invalid_refutation_target", path, "Only a claim can receive a theorem-refutation report")
                evidence = _match(event["evidence"], current, path + ".evidence")
                if evidence["kind"] != "evidence" or evidence["content"]["evidence_type"] != "counterexample_report":
                    _fail("invalid_refutation_evidence", path, "A pinned counterexample-report evidence record is required")
                # Availability is deliberately NOT evidence validation. Reports
                # remain objections even if their cited artifact later changes.
            life.setdefault(key, []).append(event)
    reports = _analyze(current, life, changed_by)
    normalized = {**detached, "records": sorted(records, key=lambda record: record["id"])}
    result = {"schema": VERSION + "/report", "input_sha256": digest(normalized),
        "integrity": {"record_digests_match": True, "artifact_bytes_checked": False, "authorship_verified": False},
        "scope": "All-required explicit revision dependency applicability only; no truth, proof acceptance, hypothesis checking, or formal verification.",
        "truth_assessment": "not_assessed", "proof_accepted": False,
        "records": reports,
        "affected_obligations": [r["pin"]["id"] for r in reports if r["kind"] == "obligation" and r["applicability"] == "blocked"],
        "affected_claims": [r["pin"]["id"] for r in reports if r["kind"] == "claim" and r["applicability"] == "blocked"],
        "history": [{"pin": pin(record), "kind": record["kind"], "current": current[record["id"]]["revision"] == record["revision"],
                     "lifecycle_events": life.get((record["id"], record["revision"]), [])}
                    for record in sorted(history, key=lambda r: (r["id"], r["revision"]))],
        "events_replayed": len(events)}
    if len(canonical_bytes(result)) > MAX_OUTPUT_BYTES:
        _fail("budget_exceeded", "report", "Output byte budget exceeded; no partial result")
    return result
