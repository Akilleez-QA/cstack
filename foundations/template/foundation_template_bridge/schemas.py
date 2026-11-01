from copy import deepcopy

DRAFT = "https://json-schema.org/draft/2020-12/schema"
TEXT = {"type": "string", "maxLength": 1024}


def obj(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else list(required), "additionalProperties": False}


BOUNDARY = obj({"observation_only": {"const": True}, "domain_determination": {"const": False},
                "control_action": {"const": False}})
EVIDENCE_ENTRY = obj({"applies_to": TEXT, "evidence": obj({
    "basis": obj({"kind": {"const": "practice"}, "note": TEXT}), "status": {"const": "CHECK"}})})


def output(assessment, result):
    receipt = obj({"tool": TEXT, "version": TEXT, "status": {"enum": ["ok", "error"]},
                   "input_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}, "boundary": BOUNDARY,
                   "result": {"oneOf": [{"type": "null"}, result]}, "error": {"type": ["string", "null"]},
                   "evidence": {"type": "array", "items": EVIDENCE_ENTRY, "minItems": 1, "maxItems": 16}})
    return {"$schema": DRAFT, **obj({"tool": TEXT, "assessment": {"enum": [assessment, "tool_error"]},
                                     "formal_proof": {"const": False}, "runtime_goal_acceptance": {"const": False},
                                     "receipt": receipt})}


TOOLS = [
    {"name": "echo_observation",
     "description": "PLACEHOLDER: returns its validated input as an observation with Evidence. Replace with real tools.",
     "inputSchema": {"$schema": DRAFT, **obj({"observation": {"type": "string", "minLength": 1, "maxLength": 256}})},
     "outputSchema": output("observation_echoed", obj({"observation": {"type": "string", "maxLength": 256}}))},
]


def tool_definitions():
    return deepcopy(TOOLS)
