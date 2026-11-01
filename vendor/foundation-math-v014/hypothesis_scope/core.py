"""Exact matching of authored typed premises. Not a mathematical verifier."""
from __future__ import annotations

import hashlib
import json
import re

VERSION = "foundation-math-hypothesis-scope/1"
MAX_INPUT_BYTES = 262144
MAX_OBJECTS = 64
MAX_MAPS = 64
MAX_FACTS = 64
MAX_REQUIREMENTS = 32
MAX_PATH = 4
MAX_OUTPUT_BYTES = 262144
OBJECT_TYPES = ("coherent_sheaf", "vector_space", "representation", "formal_splitting", "locus")
PHYSICAL_LABELS = ("1", "W", "A", "S4", "D", "T6", "P", "Wp", "V")
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
# Field types are a closed vocabulary. Every predicate is compared literally.
PREDICATES = {
    "generic_sheaf_equality": {"left": "sheaf", "right": "sheaf", "locus": "locus"},
    "coherent_sheaf_equality": {"left": "sheaf", "right": "sheaf"},
    "selected_subkernel": {"kernel": "sheaf", "inclusion": "map", "of_map": "map"},
    "full_kernel": {"kernel": "sheaf", "inclusion": "map", "of_map": "map"},
    "abstract_splitting": {"object": "sheaf", "splitting": "splitting"},
    "embedded_splitting": {"object": "sheaf", "splitting": "splitting", "inclusion": "map"},
    "coherent_image": {"image": "sheaf", "inclusion": "map", "of_map": "map"},
    "saturated_image": {"image": "sheaf", "inclusion": "map", "of_map": "map"},
    "physical_representation": {"object": "representation", "catalog_sha256": "hash", "label": "label"},
    "object_rank": {"object": "sheaf", "value": "natural"},
    "object_dimension": {"object": "space_or_representation", "value": "natural"},
    "map_rank": {"map": "map", "value": "natural"},
    "map_injective": {"map": "map"},
    "map_zero": {"map": "map"},
    "constant_vanishing": {"constants": "object", "inclusion": "map", "path": "map_path"},
    "torsion_identification": {"role": "torsion_role", "torsion": "sheaf", "of_map": "map", "identified_with": "sheaf", "identification": "map"},
    "object_identity": {"left": "object", "right": "object"},
    "map_identity": {"left": "map", "right": "map"},
}


class ScopeError(ValueError):
    def __init__(self, code, path, message):
        self.code, self.path, self.message = code, path, message
        super().__init__(f"{code} at {path}: {message}")


def fail(code, path, message):
    raise ScopeError(code, path, message)


def guard(value):
    stack, count = [(value, 0)], 0
    while stack:
        item, depth = stack.pop()
        count += 1
        if count > 32768 or depth > 16:
            fail("budget_exceeded", "$", "JSON node/depth budget exceeded")
        if type(item) is dict:
            if len(item) > 16:
                fail("budget_exceeded", "$", "Too many fields")
            for key, val in item.items():
                if type(key) is not str or len(key) > 64:
                    fail("malformed_type", "$", "Keys must be ordinary short strings")
                utf8(key)
                stack.append((val, depth + 1))
        elif type(item) is list:
            if len(item) > 256:
                fail("budget_exceeded", "$", "Array budget exceeded")
            stack.extend((val, depth + 1) for val in item)
        elif type(item) is str:
            if len(item) > 2048:
                fail("budget_exceeded", "$", "String budget exceeded")
            utf8(item)
        elif type(item) is int:
            if not -(2**31) <= item < 2**31:
                fail("budget_exceeded", "$", "Integer budget exceeded")
        elif item is not None and type(item) is not bool:
            fail("malformed_type", "$", "Only ordinary JSON types are supported; no floats")


def utf8(text):
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError:
        fail("malformed_type", "$", "Unpaired Unicode surrogate")


def canonical_bytes(value):
    guard(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def obj(value, fields, path):
    if type(value) is not dict:
        fail("malformed_type", path, "Expected an object")
    if set(value) != set(fields):
        fail("fields", path, "Missing or unsupported fields")


def identifier(value, path):
    if type(value) is not str or _ID.fullmatch(value) is None:
        fail("malformed_type", path, "Expected an ASCII identifier of length 1..64")


def hash_value(value, path):
    if type(value) is not str or _HASH.fullmatch(value) is None:
        fail("malformed_type", path, "Expected lowercase SHA-256 hex")


def natural(value, path, minimum=0, maximum=1000000):
    if type(value) is not int or not minimum <= value <= maximum:
        fail("malformed_type", path, "Expected an ordinary bounded integer")


def text_value(value, path):
    if type(value) is not str or not value.strip() or len(value) > 1024:
        fail("malformed_type", path, "Expected nonblank text of length at most 1024")


def enum(value, choices, path):
    if type(value) is not str or value not in choices:
        fail("malformed_type", path, "Unsupported value")


def array(value, maximum, path, minimum=0):
    if type(value) is not list or not minimum <= len(value) <= maximum:
        fail("budget_exceeded", path, "Expected a bounded array")


def validate_pin(value, path):
    obj(value, ("id", "revision", "revision_sha256"), path)
    identifier(value["id"], path + ".id")
    natural(value["revision"], path + ".revision", 1)
    hash_value(value["revision_sha256"], path + ".revision_sha256")


def pin(record):
    """Construction helper; not a trust or evidence check."""
    result = {k: record[k] for k in ("id", "revision", "revision_sha256")}
    validate_pin(result, "pin")
    return result


def seal(body):
    """Seal an authored record body. Does not validate content or prove it."""
    guard(body)
    obj(body, ("id", "revision", "content"), "record")
    identifier(body["id"], "record.id")
    natural(body["revision"], "record.revision", 1)
    result = json.loads(canonical_bytes(body))
    result["revision_sha256"] = digest(body)
    return result


def record(value, path):
    obj(value, ("id", "revision", "content", "revision_sha256"), path)
    validate_pin(pin(value), path)
    body = {k: value[k] for k in ("id", "revision", "content")}
    if digest(body) != value["revision_sha256"]:
        fail("record_hash_mismatch", path, "Record differs from its revision digest")


def resolve(reference, registry, path):
    validate_pin(reference, path)
    if reference["id"] not in registry:
        fail("missing_reference", path, "Exact target ID is absent or in the wrong namespace")
    result = registry[reference["id"]]
    if reference != pin(result):
        fail("pin_mismatch", path, "Exact current revision and digest are required")
    return result


def predicate(value, objects, maps, path):
    if type(value) is not dict or type(value.get("kind")) is not str or value["kind"] not in PREDICATES:
        fail("predicate_kind", path, "Unknown predicate kind")
    kind, resolved_objects, resolved_maps = value["kind"], {}, {}
    obj(value, {"kind", *PREDICATES[kind]}, path)
    types = {"sheaf": ("coherent_sheaf",), "locus": ("locus",), "splitting": ("formal_splitting",), "representation": ("representation",), "space_or_representation": ("vector_space", "representation"), "object": OBJECT_TYPES}
    for field, category in PREDICATES[kind].items():
        item, p = value[field], path + "." + field
        if category in types:
            target = resolve(item, objects, p)
            if target["content"]["object_type"] not in types[category]:
                fail("object_type", p, "Object type is incompatible with this field")
            resolved_objects[field] = target
        elif category == "map":
            resolved_maps[field] = resolve(item, maps, p)
        elif category == "map_path":
            array(item, MAX_PATH, p, 1)
            sequence = [resolve(ref, maps, f"{p}[{i}]") for i, ref in enumerate(item)]
            for first, second in zip(sequence, sequence[1:]):
                if first["content"]["target"] != second["content"]["source"]:
                    fail("map_endpoint", p, "Map paths must compose in the written order")
            resolved_maps.update({str(i): val for i, val in enumerate(sequence)})
        elif category == "hash":
            hash_value(item, p)
        elif category == "natural":
            natural(item, p)
        elif category == "label":
            enum(item, PHYSICAL_LABELS, p)
        elif category == "torsion_role":
            enum(item, ("original", "induced"), p)
    # A context pin is opaque; equality here checks caller-supplied universe identity only.
    contexts = {x["content"]["context_sha256"] for x in resolved_objects.values()}
    for m in resolved_maps.values():
        contexts.add(objects[m["content"]["source"]["id"]]["content"]["context_sha256"])
    if len(contexts) > 1:
        fail("context_mismatch", path, "One predicate cannot mix context identities")
    def endpoint(map_field, side, object_field):
        if resolved_maps[map_field]["content"][side] != value[object_field]:
            fail("map_endpoint", path, "Pinned map endpoint does not match the named object")
    if kind in ("selected_subkernel", "full_kernel"):
        endpoint("inclusion", "source", "kernel")
        if resolved_maps["inclusion"]["content"]["target"] != resolved_maps["of_map"]["content"]["source"]:
            fail("map_endpoint", path, "Kernel inclusion must target the exact map source")
    if kind in ("coherent_image", "saturated_image"):
        endpoint("inclusion", "source", "image")
        if resolved_maps["inclusion"]["content"]["target"] != resolved_maps["of_map"]["content"]["target"]:
            fail("map_endpoint", path, "Image inclusion must target the exact map target")
    if kind == "embedded_splitting":
        endpoint("inclusion", "source", "object")
    if kind == "constant_vanishing":
        endpoint("inclusion", "source", "constants")
        if resolved_maps["inclusion"]["content"]["target"] != resolved_maps["0"]["content"]["source"]:
            fail("map_endpoint", path, "Constants inclusion must target the first map source")
    if kind == "torsion_identification":
        endpoint("identification", "source", "torsion")
        endpoint("identification", "target", "identified_with")
        if objects[resolved_maps["of_map"]["content"]["source"]["id"]]["content"]["object_type"] != "coherent_sheaf":
            fail("object_type", path, "Torsion provenance must name a sheaf map")
    if kind == "object_identity":
        if resolved_objects["left"]["content"]["object_type"] != resolved_objects["right"]["content"]["object_type"]:
            fail("object_type", path, "Object identity requires the same declared type")
    if kind == "map_identity":
        for side in ("source", "target"):
            if resolved_maps["left"]["content"][side] != resolved_maps["right"]["content"][side]:
                fail("map_endpoint", path, "Map identity requires identical exact endpoints")


def check(document):
    """Validate a closed snapshot and check explicit exact fact-to-premise bindings."""
    raw = canonical_bytes(document)
    if len(raw) > MAX_INPUT_BYTES:
        fail("budget_exceeded", "$", "Input byte budget exceeded")
    d = json.loads(raw)  # detach; the pure API never mutates caller data
    obj(d, ("schema", "objects", "maps", "facts", "rule", "application"), "$")
    enum(d["schema"], (VERSION,), "schema")
    namespaces, used = {}, set()
    for field, cap in (("objects", MAX_OBJECTS), ("maps", MAX_MAPS), ("facts", MAX_FACTS)):
        array(d[field], cap, field)
        registry = {}
        for i, value in enumerate(d[field]):
            path = f"{field}[{i}]"
            record(value, path)
            if value["id"] in used:
                fail("duplicate_id", path, "Record IDs are unique across all namespaces")
            used.add(value["id"])
            registry[value["id"]] = value
        namespaces[field] = registry
    objects, maps, facts = (namespaces[k] for k in ("objects", "maps", "facts"))
    for rid, value in objects.items():
        c, p = value["content"], "objects." + rid
        obj(c, ("object_type", "context_sha256", "description"), p)
        enum(c["object_type"], OBJECT_TYPES, p + ".object_type")
        hash_value(c["context_sha256"], p + ".context_sha256")
        text_value(c["description"], p + ".description")
    for rid, value in maps.items():
        c, p = value["content"], "maps." + rid
        obj(c, ("source", "target", "description"), p)
        source, target = resolve(c["source"], objects, p + ".source"), resolve(c["target"], objects, p + ".target")
        st, tt = source["content"]["object_type"], target["content"]["object_type"]
        if st != tt or st not in ("coherent_sheaf", "vector_space", "representation"):
            fail("object_type", p, "Maps connect two objects of the same supported declared type")
        if source["content"]["context_sha256"] != target["content"]["context_sha256"]:
            fail("context_mismatch", p, "Map endpoints must have the same context identity")
        text_value(c["description"], p + ".description")
    for rid, value in facts.items():
        c, p = value["content"], "facts." + rid
        obj(c, ("predicate", "availability", "provenance"), p)
        predicate(c["predicate"], objects, maps, p + ".predicate")
        enum(c["availability"], ("supplied", "withdrawn"), p + ".availability")
        obj(c["provenance"], ("artifact_sha256", "description"), p + ".provenance")
        hash_value(c["provenance"]["artifact_sha256"], p + ".provenance.artifact_sha256")
        text_value(c["provenance"]["description"], p + ".provenance.description")
    r = d["rule"]
    record(r, "rule")
    if r["id"] in used:
        fail("duplicate_id", "rule", "Rule ID collides with another record")
    obj(r["content"], ("purpose", "requirements"), "rule.content")
    text_value(r["content"]["purpose"], "rule.content.purpose")
    requirements = r["content"]["requirements"]
    array(requirements, MAX_REQUIREMENTS, "rule.content.requirements", 1)
    reqs = {}
    for i, req in enumerate(requirements):
        p = f"rule.content.requirements[{i}]"
        obj(req, ("id", "predicate"), p)
        identifier(req["id"], p + ".id")
        if req["id"] in reqs:
            fail("duplicate_requirement", p, "Requirement IDs must be unique")
        predicate(req["predicate"], objects, maps, p + ".predicate")
        reqs[req["id"]] = req
    app = d["application"]
    obj(app, ("rule", "bindings"), "application")
    validate_pin(app["rule"], "application.rule")
    array(app["bindings"], MAX_REQUIREMENTS, "application.bindings")
    bindings = {}
    for i, bind in enumerate(app["bindings"]):
        p = f"application.bindings[{i}]"
        obj(bind, ("requirement_id", "fact"), p)
        identifier(bind["requirement_id"], p + ".requirement_id")
        validate_pin(bind["fact"], p + ".fact")
        if bind["requirement_id"] not in reqs:
            fail("unknown_requirement", p, "Binding names no requirement in this rule")
        if bind["requirement_id"] in bindings:
            fail("duplicate_binding", p, "At most one fact per requirement")
        bindings[bind["requirement_id"]] = bind["fact"]
    checks = []
    rule_current = app["rule"] == pin(r)
    for rid in sorted(reqs):
        bound = bindings.get(rid)
        current = facts.get(bound["id"]) if bound is not None else None
        code = "exact_match"
        if not rule_current:
            code = "rule_pin_not_current"
        elif bound is None:
            code = "missing_binding"
        elif current is None:
            code = "fact_not_supplied"
        elif bound != pin(current):
            code = "fact_pin_not_current"
        elif current["content"]["availability"] == "withdrawn":
            code = "fact_withdrawn"
        elif current["content"]["predicate"] != reqs[rid]["predicate"]:
            code = "predicate_mismatch"
        checks.append({"requirement_id": rid, "status": code, "required_predicate": reqs[rid]["predicate"], "bound_fact": bound, "current_fact": pin(current) if current is not None else None})
    # Registry/binding order is irrelevant. Requirement/path order is part of rule identity.
    normalized = dict(d)
    for field in ("objects", "maps", "facts"):
        normalized[field] = sorted(d[field], key=lambda x: x["id"])
    normalized["application"] = {"rule": app["rule"], "bindings": sorted(app["bindings"], key=lambda x: x["requirement_id"])}
    result = {"schema": VERSION + "/report", "input_sha256": digest(normalized), "rule": app["rule"], "current_rule": pin(r), "all_requirements_matched": all(c["status"] == "exact_match" for c in checks), "requirements": checks, "semantics": "exact_authored_premise_matching_only", "fact_truth_checked": False, "rule_soundness_checked": False, "geometry_checked": False, "runtime_acceptance": False, "lean_proof": False}
    if len(canonical_bytes(result)) > MAX_OUTPUT_BYTES:
        fail("budget_exceeded", "$", "Output byte budget exceeded")
    return result


def loads(data):
    if type(data) not in (str, bytes):
        fail("malformed_type", "$", "Expected text or UTF-8 bytes")
    if type(data) is str:
        data = utf8(data)
    if len(data) > MAX_INPUT_BYTES:
        fail("budget_exceeded", "$", "Input byte budget exceeded")
    def pairs(values):
        result = {}
        for key, val in values:
            if key in result:
                fail("duplicate_key", "$", "Duplicate JSON key")
            result[key] = val
        return result
    def integer(token):
        if len(token) > 11:
            fail("budget_exceeded", "$", "Integer token too large")
        return int(token)
    def unsupported(token):
        fail("malformed_type", "$", "Floating point and nonfinite tokens are unsupported")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_int=integer, parse_float=unsupported, parse_constant=unsupported)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, ScopeError):
            raise
        fail("malformed_json", "$", "Invalid UTF-8 JSON")
    guard(value)
    return value
