#!/usr/bin/env python3
"""Validate POODO continuation capsule structure, never epistemic truth."""

from __future__ import annotations

import argparse
from datetime import datetime
import re
import sys
from pathlib import Path
from typing import Any

import yaml


SCHEMA = "POODO_CONTINUATION/3.0"
LEGACY_SCHEMAS = {"POODA_CONTINUATION/2.1"}
ID_RE = re.compile(r"^[A-Z]{1,4}-[A-Za-z0-9][A-Za-z0-9._-]*$")
CAPSULE_RE = re.compile(r"^PC-[A-Za-z0-9][A-Za-z0-9._-]*$")
RFC3339_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
REQUIRED = {
    "schema",
    "capsule_id",
    "revision",
    "parent_capsule",
    "generated_at",
    "objective",
    "acceptance",
    "authority",
    "constraints",
    "user_directives",
    "current_head",
    "claims",
    "evidence_bundles",
    "orientations",
    "alternatives",
    "decisions",
    "predictions",
    "outcomes",
    "contradictions",
    "artifacts",
    "rehydration",
    "delivery_state",
    "outcome_state",
    "highest_justified_claim",
    "required_runtime_observation",
    "who_controls_next_test",
    "next_step",
}
OPTIONAL = {"capsule_overflow"}
COLLECTIONS = {
    "acceptance",
    "claims",
    "evidence_bundles",
    "orientations",
    "alternatives",
    "decisions",
    "predictions",
    "outcomes",
    "contradictions",
    "artifacts",
}
CLAIM_STATES = {"reported", "reported_prior_state", "observed", "corroborated", "inferred"}
RECORD_STATES = {"active", "stale", "superseded", "invalidated"}
PREDICTION_STATES = {"pending", "passed", "failed", "invalid", "inconclusive", "failed_with_test_concern"}
COMPLETENESS = {"complete", "partial", "truncated"}
DELIVERY_STATES = {"authored", "checked", "built", "deployed", "other"}
OUTCOME_STATES = {"unobserved", "reported", "observed", "corroborated", "passed", "failed", "failed_with_test_concern", "invalid", "inconclusive"}


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict[str, Any]:
    loader.flatten_mapping(node)
    mapping: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping", node.start_mark, "mapping keys must be strings", key_node.start_mark
            )
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping", node.start_mark, f"duplicate key: {key}", key_node.start_mark
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def _items(data: dict[str, Any], field: str, errors: list[str]) -> list[dict[str, Any]]:
    value = data.get(field)
    if not isinstance(value, list):
        errors.append(f"{field}: must be a list")
        return []
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{field}[{index}]: must be a mapping")
        else:
            result.append(item)
    return result


def _enum(value: Any, choices: set[str]) -> bool:
    return isinstance(value, str) and value in choices


def _references(record: dict[str, Any], key: str, path: str, errors: list[str]) -> list[str]:
    value = record.get(key, [])
    if not isinstance(value, list):
        errors.append(f"{path}.{key}: must be a list of IDs")
        return []
    references = []
    for index, reference in enumerate(value):
        if not isinstance(reference, str) or not ID_RE.fullmatch(reference):
            errors.append(f"{path}.{key}[{index}]: must be a valid ID string")
        else:
            references.append(reference)
    return references


def _reference(record: dict[str, Any], key: str, path: str, errors: list[str]) -> str | None:
    if key not in record:
        return None
    value = record[key]
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        errors.append(f"{path}.{key}: must be a valid ID string")
        return None
    return value


def _timestamp(value: Any) -> bool:
    if isinstance(value, datetime):
        return value.tzinfo is not None and value.utcoffset() is not None
    if not isinstance(value, str) or not RFC3339_RE.fullmatch(value):
        return False
    if int(value[11:13]) > 23 or int(value[14:16]) > 59 or int(value[17:19]) > 59:
        return False
    # datetime rejects impossible calendar values; explicitly reject offset
    # minutes that fromisoformat otherwise normalizes (for example +01:99).
    if value[-1] != "Z" and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def validate(data: Any, raw_text: str, hard_token_ceiling: int = 1800) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["root: must be a mapping"]

    if any(not isinstance(key, str) for key in data):
        return ["root: field names must be strings"]
    missing = sorted(REQUIRED - data.keys())
    unknown = sorted(data.keys() - REQUIRED - OPTIONAL)
    if missing:
        errors.append("root: missing required fields: " + ", ".join(missing))
    if unknown:
        errors.append("root: unknown fields: " + ", ".join(unknown))
    if not _enum(data.get("schema"), {SCHEMA, *LEGACY_SCHEMAS}):
        errors.append(f"schema: expected {SCHEMA!r} or a supported legacy schema")
    capsule_id = data.get("capsule_id")
    if not isinstance(capsule_id, str) or not CAPSULE_RE.fullmatch(capsule_id):
        errors.append("capsule_id: must match PC-<namespace>-<unique-id>")
    revision = data.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append("revision: must be a positive integer")
    parent = data.get("parent_capsule")
    if parent is not None and (not isinstance(parent, str) or not CAPSULE_RE.fullmatch(parent)):
        errors.append("parent_capsule: must be null or a valid PC-* identifier")
    if isinstance(revision, int):
        if revision == 1 and parent is not None:
            errors.append("parent_capsule: revision 1 must not declare a parent")
        if revision > 1 and parent is None:
            errors.append("parent_capsule: revisions after 1 require a parent")
    if not str(data.get("objective", "")).strip():
        errors.append("objective: must not be empty")
    generated_at = data.get("generated_at")
    if not _timestamp(generated_at):
        errors.append("generated_at: must be an RFC3339-compatible timestamp")
    if not str(data.get("next_step", "")).strip():
        errors.append("next_step: must not be empty")
    if not isinstance(data.get("authority"), dict):
        errors.append("authority: must be a mapping")
    for key in ("constraints", "user_directives"):
        if not isinstance(data.get(key), (str, list, dict)) or not data.get(key):
            errors.append(f"{key}: must contain decision-relevant state")
    if not isinstance(data.get("rehydration"), dict):
        errors.append("rehydration: must be a mapping")
    for key in ("delivery_state", "outcome_state", "highest_justified_claim", "required_runtime_observation", "who_controls_next_test"):
        if not str(data.get(key, "")).strip():
            errors.append(f"{key}: must not be empty")
    if not _enum(data.get("delivery_state"), DELIVERY_STATES):
        errors.append("delivery_state: invalid state")
    if not _enum(data.get("outcome_state"), OUTCOME_STATES):
        errors.append("outcome_state: invalid state")

    records: dict[str, tuple[str, dict[str, Any]]] = {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for field in COLLECTIONS:
        grouped[field] = _items(data, field, errors)
        for index, record in enumerate(grouped[field]):
            record_id = record.get("id")
            if not isinstance(record_id, str) or not ID_RE.fullmatch(record_id):
                errors.append(f"{field}[{index}].id: missing or invalid stable ID")
            elif record_id in records:
                errors.append(f"{field}[{index}].id: duplicate ID {record_id}")
            else:
                records[record_id] = (field, record)

    for index, claim in enumerate(grouped["claims"]):
        if not str(claim.get("text", claim.get("claim", ""))).strip():
            errors.append(f"claims[{index}]: non-empty text or claim required")
        if not _enum(claim.get("state"), CLAIM_STATES):
            errors.append(f"claims[{index}].state: invalid claim state")
        if not _enum(claim.get("status"), RECORD_STATES):
            errors.append(f"claims[{index}].status: invalid record status")
        for key in ("source_type", "locator", "observed_at", "freshness", "evidence_family", "rehydration_status", "limits"):
            if key not in claim:
                errors.append(f"claims[{index}].{key}: required")
        for reference in _references(claim, "supports", f"claims[{index}]", errors):
            if reference not in records:
                errors.append(f"claims[{index}].supports: unresolved ID {reference}")

    for index, bundle in enumerate(grouped["evidence_bundles"]):
        completeness = bundle.get("completeness")
        if not _enum(completeness, COMPLETENESS):
            errors.append(f"evidence_bundles[{index}].completeness: invalid value")
        if _enum(completeness, {"partial", "truncated"}) and bundle.get("supports_claims", []):
            errors.append(f"evidence_bundles[{index}].supports_claims: partial or truncated evidence cannot support a capsule claim")
        for claim_id in _references(bundle, "supports_claims", f"evidence_bundles[{index}]", errors):
            target = records.get(claim_id)
            if target is None or target[0] != "claims":
                errors.append(f"evidence_bundles[{index}].supports_claims: unresolved claim {claim_id}")
        for artifact_id in _references(bundle, "artifacts", f"evidence_bundles[{index}]", errors):
            target = records.get(artifact_id)
            if target is None or target[0] != "artifacts":
                errors.append(f"evidence_bundles[{index}].artifacts: unresolved artifact {artifact_id}")

    invalidated = {
        record_id
        for record_id, (_, record) in records.items()
        if _enum(record.get("status"), {"invalidated", "superseded"})
    }
    for field in ("orientations", "decisions", "outcomes"):
        for index, record in enumerate(grouped[field]):
            for dependency in _references(record, "depends_on", f"{field}[{index}]", errors):
                if dependency not in records:
                    errors.append(f"{field}[{index}].depends_on: unresolved ID {dependency}")
                elif dependency in invalidated and record.get("status", "active") == "active":
                    errors.append(f"{field}[{index}]: active record depends on invalidated {dependency}")

    for index, prediction in enumerate(grouped["predictions"]):
        status = prediction.get("status")
        if not _enum(status, PREDICTION_STATES):
            errors.append(f"predictions[{index}].status: invalid prediction status")
        history = prediction.get("status_history")
        if not isinstance(history, list) or not history:
            errors.append(f"predictions[{index}].status_history: non-empty list required")
            continue
        if history[-1] != status:
            errors.append(f"predictions[{index}].status_history: final entry must equal status")
        terminal_seen = False
        for state in history:
            if not _enum(state, PREDICTION_STATES):
                errors.append(f"predictions[{index}].status_history: invalid state {state!r}")
                continue
            if terminal_seen:
                errors.append(f"predictions[{index}].status_history: terminal prediction was resurrected; create a new prediction ID")
                break
            if state != "pending":
                terminal_seen = True

        for key in ("oracle", "artifact"):
            reference = _reference(prediction, key, f"predictions[{index}]", errors)
            if reference and reference not in records:
                errors.append(f"predictions[{index}].{key}: unresolved ID {reference}")
        for reference in _references(prediction, "outcome_evidence", f"predictions[{index}]", errors):
            if reference not in records:
                errors.append(f"predictions[{index}].outcome_evidence: unresolved ID {reference}")

    required_contradiction_fields = ("target", "evidence", "scope", "effect", "affected_ids", "disposition", "repaired_by")
    for index, contradiction in enumerate(grouped["contradictions"]):
        for key in required_contradiction_fields:
            if key not in contradiction:
                errors.append(f"contradictions[{index}].{key}: required")
        target = _reference(contradiction, "target", f"contradictions[{index}]", errors)
        if target and target not in records:
            errors.append(f"contradictions[{index}].target: unresolved ID {target}")
        for key in ("evidence", "affected_ids", "repaired_by"):
            for reference in _references(contradiction, key, f"contradictions[{index}]", errors):
                if reference not in records:
                    errors.append(f"contradictions[{index}].{key}: unresolved ID {reference}")
        if not _enum(contradiction.get("disposition"), {"unresolved", "repaired", "accepted"}):
            errors.append(f"contradictions[{index}].disposition: invalid value")

    head = data.get("current_head")
    if head is not None and not isinstance(head, str):
        errors.append("current_head: must be an ID string or null")
    elif head is not None and head not in records:
        errors.append(f"current_head: unresolved ID {head}")
    elif head is not None and records[head][0] not in {"orientations", "decisions", "predictions", "contradictions"}:
        errors.append("current_head: must reference an orientation, decision, prediction, or contradiction")

    approximate_tokens = (len(raw_text) + 3) // 4
    overflow = data.get("capsule_overflow")
    declared_overflow = isinstance(overflow, str) and bool(overflow.strip())
    if approximate_tokens > hard_token_ceiling and not declared_overflow:
        errors.append(
            f"size: approximately {approximate_tokens} tokens exceeds ceiling {hard_token_ceiling}; "
            "emit a non-empty capsule_overflow rather than silently deleting critical state"
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check POODO capsule format and referential integrity. Passing does not establish truth."
    )
    parser.add_argument("capsule", type=Path)
    parser.add_argument("--hard-token-ceiling", type=int, default=1800)
    args = parser.parse_args()
    try:
        raw = args.capsule.read_text(encoding="utf-8")
        data = yaml.load(raw, Loader=UniqueKeyLoader)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        print(f"INVALID: could not load capsule: {exc}", file=sys.stderr)
        return 2
    errors = validate(data, raw, args.hard_token_ceiling)
    if errors:
        print("INVALID POODO capsule structure:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print("No judgment about epistemic truth was performed.", file=sys.stderr)
        return 1
    print("POODO capsule structure passed; epistemic and behavioral correctness remain untested.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
