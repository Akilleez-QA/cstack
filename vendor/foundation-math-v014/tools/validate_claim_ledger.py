#!/usr/bin/env python3
"""Validate research evidence bookkeeping, never mathematical truth.

Run from any directory: python /path/to/tools/validate_claim_ledger.py LEDGER.json
Artifact paths are relative to the ledger, not the current working directory.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


STATUSES = frozenset({
    "proof_draft", "reviewed_conditional", "formally_checked", "conjecture", "refuted"
})
SUPPORTING_STATUSES = frozenset({"reviewed_conditional", "formally_checked"})
KINDS = frozenset({"proof", "test", "formal_check", "counterexample", "source"})
ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]*$")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Issue:
    code: str
    location: str
    message: str

    def __str__(self) -> str:
        return f"{self.location}: [{self.code}] {self.message}"


def validate_ledger(
    data: Any, *, base_dir: Path, verify_artifacts: bool = True
) -> list[Issue]:
    """Return structural, dependency, and evidence-pin issues without executing evidence.

    A zero-length result certifies this bookkeeping contract only. It does not
    authenticate reviewer/checker declarations, run a checker, establish a proof,
    or establish that natural-language and encoded statements agree.
    """
    issues: list[Issue] = []
    base_dir = Path(base_dir).resolve()

    def error(code: str, location: str, message: str) -> None:
        issues.append(Issue(code, location, message))

    def obj(value: Any, location: str, required: set[str], optional: set[str] | None = None) -> bool:
        if not isinstance(value, dict):
            error("type", location, "Expected an object.")
            return False
        for key in sorted(required - value.keys()):
            error("missing_field", location, f"Missing required field {key!r}.")
        for key in sorted(value.keys() - required - (optional or set())):
            error("unknown_field", location, f"Unknown field {key!r}.")
        return True

    def string(value: Any, location: str) -> bool:
        if not isinstance(value, str) or not value.strip():
            error("type", location, "Expected a nonblank string.")
            return False
        return True

    def strings(value: Any, location: str, nonempty: bool = False) -> bool:
        if not isinstance(value, list):
            error("type", location, "Expected an array of strings (use [] when explicitly empty).")
            return False
        valid = True
        seen: set[str] = set()
        if nonempty and not value:
            error("empty", location, "At least one explicit entry is required.")
            valid = False
        for i, item in enumerate(value):
            if not string(item, f"{location}[{i}]"):
                valid = False
            elif item in seen:
                error("duplicate_value", f"{location}[{i}]", f"Duplicate value {item!r}.")
                valid = False
            else:
                seen.add(item)
        return valid

    def artifact(value: Any, location: str) -> bool:
        start = len(issues)
        if not obj(value, location, {"path", "sha256"}):
            return False
        path = value.get("path")
        digest = value.get("sha256")
        safe_path = False
        if string(path, location + ".path"):
            parts = path.split("/")
            safe_path = not ("\\" in path or ":" in path or any(p in {"", ".", ".."} for p in parts))
            if not safe_path:
                error("artifact_path", location + ".path", "Use a relative POSIX path with no empty, dot, or parent components, backslashes, or colons.")
        valid_hash = isinstance(digest, str) and HASH_PATTERN.fullmatch(digest) is not None
        if not valid_hash:
            error("artifact_hash", location + ".sha256", "Expected a lowercase, 64-hex-character SHA-256 digest.")
        if verify_artifacts and safe_path and valid_hash:
            try:
                target = (base_dir / path).resolve()
                try:
                    target.relative_to(base_dir)
                except ValueError:
                    error("artifact_path", location + ".path", "Resolved evidence path escapes the ledger directory (possibly through a symlink).")
                    return False
                if not target.is_file():
                    error("artifact_missing", location + ".path", "Evidence file does not exist or is not a regular file.")
                else:
                    actual = hashlib.sha256()
                    with target.open("rb") as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            actual.update(chunk)
                    if actual.hexdigest() != digest:
                        error("artifact_mismatch", location + ".sha256", f"File bytes do not match the pinned SHA-256 (actual {actual.hexdigest()}).")
            except (OSError, RuntimeError, ValueError) as exc:
                error("artifact_read", location + ".path", f"Cannot read evidence: {exc}")
        return len(issues) == start

    if not obj(data, "$", {"schema_version", "title", "claims"}):
        return issues
    if type(data.get("schema_version")) is not int or data.get("schema_version") != 1:
        error("schema_version", "$.schema_version", "Only integer schema version 1 is supported.")
    string(data.get("title"), "$.title")
    claims = data.get("claims")
    if not isinstance(claims, list) or not claims:
        error("type", "$.claims", "Expected a nonempty array of claims.")
        return issues

    by_id: dict[str, dict[str, Any]] = {}
    locations: dict[str, str] = {}
    graph: dict[str, list[str]] = {}
    for i, claim in enumerate(claims):
        loc = f"$.claims[{i}]"
        if not obj(claim, loc, {"id", "statement", "assumptions", "dependencies", "status", "closure", "evidence", "verification"}):
            continue
        claim_id = claim.get("id")
        valid_id = string(claim_id, loc + ".id")
        if valid_id and not ID_PATTERN.fullmatch(claim_id):
            error("claim_id", loc + ".id", "Use a stable letter-led ID containing only letters, digits, _, ., :, or -.")
            valid_id = False
        if valid_id:
            if claim_id in by_id:
                error("duplicate_id", loc + ".id", f"Duplicate claim ID {claim_id!r}; first seen at {locations[claim_id]}.")
            else:
                by_id[claim_id] = claim
                locations[claim_id] = loc
        string(claim.get("statement"), loc + ".statement")
        valid_assumptions = strings(claim.get("assumptions"), loc + ".assumptions")
        valid_dependencies = strings(claim.get("dependencies"), loc + ".dependencies")
        if valid_id and by_id.get(claim_id) is claim:
            graph[claim_id] = claim["dependencies"] if valid_dependencies else []
        status = claim.get("status")
        if not isinstance(status, str) or status not in STATUSES:
            error("status", loc + ".status", "Expected one of: " + ", ".join(sorted(STATUSES)) + ".")
        closure = claim.get("closure")
        if not isinstance(closure, str) or closure not in {"open", "closed"}:
            error("closure", loc + ".closure", "Expected 'open' or 'closed'.")
        if closure == "closed" and status in ("proof_draft", "conjecture"):
            error("closure_status", loc + ".closure", "A draft or conjecture cannot be marked closed.")

        verification = claim.get("verification")
        if obj(verification, loc + ".verification", {"scope", "reviewers", "trust"}):
            string(verification.get("scope"), loc + ".verification.scope")
            strings(verification.get("reviewers"), loc + ".verification.reviewers", status in ("reviewed_conditional", "refuted"))
            strings(verification.get("trust"), loc + ".verification.trust", status == "formally_checked")

        evidence = claim.get("evidence")
        if not isinstance(evidence, list):
            error("type", loc + ".evidence", "Expected an array of evidence records.")
            evidence = []
        usable_kinds: set[str] = set()
        for j, record in enumerate(evidence):
            evloc = f"{loc}.evidence[{j}]"
            start = len(issues)
            if not obj(record, evloc, {"kind", "description", "artifact"}, {"checker", "encoded_statement", "assumptions", "trust", "result"}):
                continue
            kind = record.get("kind")
            if not isinstance(kind, str) or kind not in KINDS:
                error("evidence_kind", evloc + ".kind", "Expected one of: " + ", ".join(sorted(KINDS)) + ".")
            string(record.get("description"), evloc + ".description")
            artifact(record.get("artifact"), evloc + ".artifact")
            formal_fields = {"checker", "encoded_statement", "assumptions", "trust", "result"}
            if kind == "formal_check":
                for key in sorted(formal_fields - record.keys()):
                    error("missing_field", evloc, f"Formal-check evidence requires {key!r}.")
                checker = record.get("checker")
                if obj(checker, evloc + ".checker", {"name", "version"}):
                    string(checker.get("name"), evloc + ".checker.name")
                    string(checker.get("version"), evloc + ".checker.version")
                string(record.get("encoded_statement"), evloc + ".encoded_statement")
                formal_assumptions = strings(record.get("assumptions"), evloc + ".assumptions")
                if valid_assumptions and formal_assumptions and set(record["assumptions"]) != set(claim["assumptions"]):
                    error("formal_assumptions", evloc + ".assumptions", "Formal evidence and claim must declare the same assumptions; correspondence still needs substantive review.")
                strings(record.get("trust"), evloc + ".trust", nonempty=True)
                if record.get("result") != "pass":
                    error("formal_result", evloc + ".result", "A formal_check record must report 'pass'; keep failed attempts as test/source evidence.")
            else:
                for key in sorted(formal_fields & record.keys()):
                    error("unexpected_formal_field", evloc + "." + key, "This field is only allowed for formal_check evidence.")
            if len(issues) == start and isinstance(kind, str):
                usable_kinds.add(kind)

        if status == "reviewed_conditional" and "proof" not in usable_kinds:
            error("review_evidence", loc + ".evidence", "Reviewed conditional claims require a valid pinned proof artifact; tests or source references alone are insufficient.")
        if status == "formally_checked" and "formal_check" not in usable_kinds:
            error("formal_evidence", loc + ".evidence", "Formally checked claims require valid pinned formal-check evidence with checker version, statement, assumptions, trust, and pass result.")
        if status == "refuted" and not ({"counterexample", "proof"} & usable_kinds):
            error("refutation_evidence", loc + ".evidence", "Refuted claims require a valid pinned counterexample or refutation proof.")

    for claim_id, dependencies in graph.items():
        claim = by_id[claim_id]
        for dependency in dependencies:
            if dependency not in by_id:
                error("missing_dependency", locations[claim_id] + ".dependencies", f"Unknown dependency {dependency!r}.")
            elif claim.get("closure") == "closed":
                dep = by_id[dependency]
                if dep.get("status") not in ("reviewed_conditional", "formally_checked") or dep.get("closure") != "closed":
                    error("unresolved_dependency", locations[claim_id] + ".dependencies", f"Closed claim depends on {dependency!r}, whose status/closure is {dep.get('status')!r}/{dep.get('closure')!r}; refuted claims cannot support a conclusion.")

    # Iterative depth-first traversal also works for ledgers deeper than Python's
    # recursion limit. A cycle is not a valid evidential dependency graph.
    colors: dict[str, int] = {}
    for root in graph:
        if colors.get(root, 0):
            continue
        colors[root] = 1
        path = [root]
        position = {root: 0}
        stack = [(root, iter(graph[root]))]
        while stack:
            node, successors = stack[-1]
            dependency = next(successors, None)
            if dependency is None:
                colors[node] = 2
                stack.pop()
                position.pop(node)
                path.pop()
            elif dependency in graph:
                color = colors.get(dependency, 0)
                if color == 1:
                    cycle = path[position[dependency]:] + [dependency]
                    error("dependency_cycle", locations[node] + ".dependencies", "Cycle: " + " -> ".join(cycle))
                elif color == 0:
                    colors[dependency] = 1
                    position[dependency] = len(path)
                    path.append(dependency)
                    stack.append((dependency, iter(graph[dependency])))
    return issues


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-JSON numeric constant: {value}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--structure-only", action="store_true", help="Check declarations and graph only, without reading/hashing artifact files. This is a weaker check.")
    args = parser.parse_args(argv)
    try:
        with args.ledger.open(encoding="utf-8") as stream:
            data = json.load(stream, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        issues = validate_ledger(data, base_dir=args.ledger.resolve().parent, verify_artifacts=not args.structure_only)
    except (OSError, ValueError, RecursionError) as exc:
        print(f"Cannot validate ledger: {exc}", file=sys.stderr)
        return 2
    if issues:
        for issue in issues:
            print(issue, file=sys.stderr)
        print(f"INVALID: {len(issues)} issue(s).", file=sys.stderr)
        return 1
    if args.structure_only:
        print("VALID STRUCTURE ONLY: artifact bytes were not checked. This is not a proof certificate.")
    else:
        print("VALID BOOKKEEPING: structure, dependencies, and artifact hashes match. This is not a proof certificate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
