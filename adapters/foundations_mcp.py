import copy
import json

from jsonschema import Draft202012Validator
from referencing import Registry

from poodo_core import ContractError
from .mcp_stdio_server import McpServer
from .wire import WireFailure

COMBINATORS = ("allOf", "anyOf", "oneOf")
OPTIONS = tuple(f"option-{i}" for i in range(1, 21))
NEXT_PHASE = {"pontificate": "observe", "orchestrate": "observe", "observe": "orient", "orient": "decide"}
ADMITTED = ("completed", "tool_error")
META_KEY = "cstack/poodo"


def _no_external_schema(uri):
    raise WireFailure("External schema resolution is forbidden")


def tool_name(domain_id, operation):
    return f"{domain_id.removeprefix('foundation_')}.{operation}"


def _merged(values):
    distinct = []
    for value in values:
        if value not in distinct:
            distinct.append(value)
    return distinct[0] if len(distinct) == 1 else {"anyOf": distinct}


def advertised_schema(schema):
    if not any(key in schema for key in COMBINATORS):
        return copy.deepcopy(schema)
    projected = {key: copy.deepcopy(value) for key, value in schema.items() if key not in COMBINATORS}
    branches = [b for key in ("oneOf", "anyOf") for b in schema.get(key, ()) if type(b) is dict]
    if branches and "properties" not in projected:
        names = list(dict.fromkeys(name for b in branches for name in b.get("properties", {})))
        projected["properties"] = {name: copy.deepcopy(_merged([b["properties"][name] for b in branches
                                                                  if name in b.get("properties", {})]))
                                   for name in names}
        shared = set.intersection(*(set(b.get("required", ())) for b in branches))
        projected["required"] = [name for name in branches[0].get("required", ()) if name in shared]
        if all(b.get("additionalProperties") is False for b in branches):
            projected["additionalProperties"] = False
    projected["type"] = "object"
    return projected


def _tool(domain_id, entry):
    name = tool_name(domain_id, entry["name"])
    return {"name": name, "title": name, "description": entry["description"],
            "inputSchema": advertised_schema(entry["inputSchema"]),
            "annotations": {"title": name, "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True,
                            "openWorldHint": False}}


def _refused(payload, poodo=None):
    result = {"content": [{"type": "text", "text": json.dumps(payload, sort_keys=True)}],
              "structuredContent": payload, "isError": True}
    if poodo is not None:
        result["_meta"] = {META_KEY: poodo}
    return result


class FoundationsMcpServer(McpServer):
    INSTRUCTIONS = ("Read-only tools of the Foundations this host pinned. Each call is decided and recorded by POODO "
                    "under this bot's AOR. A result is the Foundation's own structuredContent, with its receipt, "
                    "Evidence and boundary, unchanged: CHECK values are not approved, and an observation is not an "
                    "engineering, safety or compliance determination.")

    def __init__(self, session, inventories, *, name="cstack-foundations"):
        super().__init__(session, name=name)
        registry = Registry(retrieve=_no_external_schema)
        classes = session.classes
        self._routes, self._goals, tools = {}, {}, []
        for domain_id, inventory in inventories.items():
            if classes.get(domain_id, "deny") == "deny":
                continue
            for entry in inventory:
                Draft202012Validator.check_schema(entry["inputSchema"])
                tool = _tool(domain_id, entry)
                self._routes[tool["name"]] = (domain_id, entry["name"],
                                              Draft202012Validator(entry["inputSchema"], registry=registry))
                tools.append(tool)
        self._tools = tuple(tools)
        self._by_name = {tool["name"]: tool for tool in self._tools}

    def _call(self, tool, arguments):
        domain, operation, validator = self._routes[tool["name"]]
        problem = next(iter(sorted(validator.iter_errors(arguments), key=lambda e: list(map(str, e.absolute_path)))),
                       None)
        if problem is not None:
            return _refused({"error": "Arguments do not match the pinned input schema",
                             "path": [str(p) for p in problem.absolute_path], "detail": problem.message[:300]})
        poodo = {"bot": self._session.bot.slug, "domain": domain, "operation": operation,
                 "ledger": self._session.ledger_label}
        try:
            poodo.update(self._decide(domain, operation, arguments))
            ran = self._session.execute(domain, poodo["decision_id"])
        except (ContractError, ValueError, TypeError) as error:
            return _refused({"error": str(error) or type(error).__name__}, poodo)
        if ran["status"] != "executed":
            return _refused({"error": ran["status"], "dispatched": False}, poodo)
        outcome = ran["outcome"]
        poodo.update({key: outcome[key] for key in ("attempt_id", "execution_status", "execution_certainty",
                                                    "assessment", "source_manifest_sha256", "inventory_sha256")})
        raw = outcome["raw_result"]
        if outcome["execution_status"] not in ADMITTED or type(raw) is not dict:
            return _refused({"error": "No Foundation result was admitted",
                             "execution_status": outcome["execution_status"],
                             "execution_certainty": outcome["execution_certainty"],
                             "assessment": outcome["assessment"], "limitations": outcome["limitations"]}, poodo)
        content = raw["structuredContent"]
        result = {"content": [{"type": "text", "text": json.dumps(content, sort_keys=True)}],
                  "isError": raw["isError"], "_meta": {META_KEY: poodo}}
        if type(content) is dict:
            result["structuredContent"] = content
        return result

    def _decide(self, domain, operation, arguments):
        goal = self._goals.get(domain)
        if goal is None:
            snapshot = self._session.start_goal(
                domain, f"Answer read-only {domain} tool calls from the Foundations MCP server.",
                ["Each call returns the pinned Foundation's receipt unchanged, or a stated refusal."],
                exclusions=["No CHECK value is approved and no determination or control action is made."])
            goal = self._goals[domain] = {"goal_id": snapshot["contract"]["goal_id"], "phase": snapshot["phase"]}
        goal_id = goal["goal_id"]
        while goal["phase"] != "decide":
            step = NEXT_PHASE[goal["phase"]]
            snapshot = self._session.advance(
                domain, goal_id, step, f"Host-authored checkpoint for {tool_name(domain, operation)}.",
                research_references=[f"{domain} pinned tool inventory: {operation}"] if step == "orient" else [],
                option_ids=list(OPTIONS) if step == "decide" else [])
            goal["phase"] = snapshot["phase"]
        record = self._session.decide(
            domain, goal_id, operation, arguments,
            f"The pinned {domain} tool {operation} returns a receipt bound to these arguments, with its Evidence.",
            "Only the supplied arguments against the pinned Foundation; nothing is approved or determined.",
            "A tool error, refusal or unknown outcome is reported as such, with no automatic retry.")
        goal["phase"] = self._session.advance(domain, goal_id, "orchestrate",
                                              "Host-authored checkpoint: run the precommitted call.")["phase"]
        return {"goal_id": goal_id, "decision_id": record["decision_id"], "request_sha256": record["request_sha256"],
                "approval_required": record["approval_required"]}
