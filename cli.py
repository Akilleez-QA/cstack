"""Versioned local single-run driver, NOT MCP and NOT a public network server."""
import argparse
import json
import sys
import time

from adapters.endoforge_ledger import DecisionReuseRefused
from adapters.terminal_approver import APPROVER, TerminalApprover
from adapters.wire import WireFailure, decode, encode
from bootstrap import DOMAINS, RUNTIMES, build_domain, cli_approval_session, endoforge_session, registered
from extensions.cstack_forge import request_problem
from poodo_core import (CapabilityRequest, ContractError, GoalContract, Phase, PhaseCheckpoint, Precommitment,
                       exact_fields)

CLI_SCHEMA = "cstack.run/0.1"
MAX_OUTPUT = 33 * 1024 * 1024


class DriverRefusal(ContractError):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code


def run_document(document, approver=None, *, config=None, resume=None):
    if resume is not None:
        session = endoforge_session(config, resume=resume) if config else endoforge_session(resume=resume)
    else:
        session = endoforge_session() if config is None else endoforge_session(config)
    with session as host, cli_approval_session(approver) as approval_host:
        if isinstance(approver, str) and not approval_host:
            approver = TerminalApprover(approver)
        host = dict(host)
        reconciled = host.pop("reconciled", ())
        result = _run_document(document, {**host, **approval_host}, approver)
        return {**result, "reconciled_outcome_unknown": list(reconciled)} if reconciled else result


def _run_document(document, host, approver):
    host = {k: v for k, v in host.items() if k != "workcell" or document.get("goal", {}).get("domain_id") in RUNTIMES}
    exact_fields(document, {"schema", "goal", "checkpoints", "calls"})
    if document["schema"] != CLI_SCHEMA:
        raise ContractError("Unsupported local driver version")
    goal = GoalContract.from_dict(document["goal"])
    if goal.domain_id in RUNTIMES:
        if "workcell" not in host:
            raise DriverRefusal("workcell_not_configured", "This host has no workcell section in its configuration")
        for call in document["calls"] if type(document["calls"]) is list else ():
            problem = request_problem(call["request"].get("arguments")) if type(call) is dict and type(call.get("request")) is dict else "a call needs a request"
            if problem:
                raise DriverRefusal("invalid_forge_request", problem)
    calls, checkpoints = document["calls"], document["checkpoints"]
    if type(calls) is not list or not 1 <= len(calls) <= 64 or type(checkpoints) is not list or len(checkpoints) != 4:
        raise ContractError("Driver requires 1..64 calls and four preauthored phase checkpoints")
    ask_operations = []
    for call in calls:
        if type(call) is not dict:
            raise ContractError("Call must be an object")
        exact_fields(call, {"request", "precommitment", "effect"} if "effect" in call else {"request", "precommitment"})
        if call.get("effect", "allow") not in ("allow", "ask"):
            raise ContractError("Call effect must be allow or ask")
        if call.get("effect") == "ask":
            ask_operations.append(CapabilityRequest.from_dict(call["request"]).operation)
    if "approvals" in host:
        ask_operations = list(registered(goal.domain_id).tool_names)
        core, _ = build_domain(goal.domain_id, goal.goal_id, ask_operations=tuple(ask_operations), **host)
    elif ask_operations:
        approver = approver or TerminalApprover()
        core, _ = build_domain(goal.domain_id, goal.goal_id, ask_operations=tuple(ask_operations),
                               approvals=approver, approver=APPROVER, clock=lambda: int(time.time()), **host)
    else:
        core, _ = build_domain(goal.domain_id, goal.goal_id, **host)
    core.start_goal(goal)
    parsed = []
    for data in checkpoints:
        exact_fields(data, {"checkpoint_id", "rationale", "research_references", "option_ids"})
        if type(data["research_references"]) is not list or type(data["option_ids"]) is not list:
            raise ContractError("Checkpoint arrays required")
        parsed.append(PhaseCheckpoint(data["checkpoint_id"], data["rationale"],
            tuple(data["research_references"]), tuple(data["option_ids"])))
    for phase, checkpoint in zip((Phase.OBSERVE, Phase.ORIENT, Phase.DECIDE), parsed[:3]):
        core.advance(goal.goal_id, phase, checkpoint)
    decisions = []
    for call in calls:
        precommit = exact_fields(call["precommitment"], {"expected_observation", "success_boundary", "failure_meaning",
                                                        "oracle_id", "oracle_version"})
        request = CapabilityRequest.from_dict(call["request"])
        core.decide(request, Precommitment(**precommit))
        decisions.append(request.decision_id)
    core.advance(goal.goal_id, Phase.ORCHESTRATE, parsed[3])
    stopped = None
    for index, decision in enumerate(decisions):
        try:
            if ask_operations:
                request = CapabilityRequest.from_dict(calls[index]["request"])
                if request.operation in ask_operations and "approvals" not in host:
                    approver.prepare(request)
            core.execute(decision)
        except (ContractError, OSError, RuntimeError) as error:
            acted = any(e["kind"] == "action" and e["data"].get("decision_id") == decision for e in core.ledger())
            stopped = {"decision_id": decision, "execution_certainty": "unknown" if acted else "not_dispatched",
                       "reason": "core_contract_or_retention_gate" if isinstance(error, ContractError)
                                 else "endoforge_storage_failure", "later_not_dispatched": decisions[index+1:]}
            break
    return {"schema": "cstack.run-result/0.1", "goal": core.snapshot(goal.goal_id).to_dict(),
        "events": core.ledger(), "run_status": "stopped" if stopped else "completed", "stopped": stopped,
        "outcome_unknown": [{"decision_id": e["data"]["outcome"]["decision_id"], "attempt_id": e["data"]["outcome"]["attempt_id"],
                             "assessment": e["data"]["outcome"]["assessment"]} for e in core.ledger() if e["kind"] == "outcome"
                            and e["data"]["outcome"]["execution_certainty"] == "unknown"],
        "mcp_compatible": False, "endoforge_implemented": "endoforge" in host,
        "note": "Preauthored checkpoint records were structurally checked, not researched or reasoned by this driver."}


def _goal_domain(value):
    domain_id = value["goal"].get("domain_id") if type(value) is dict and type(value.get("goal")) is dict else None
    return domain_id if type(domain_id) is str else None


def _decode_for_domain(raw):
    """Each registered domain's own numeric profile; a domain without one uses Math's exact integer-only decode."""
    for domain in (*DOMAINS.values(), *RUNTIMES.values()):
        if domain.decode is None:
            continue
        try:
            document = domain.decode(raw)
        except WireFailure:
            continue
        if _goal_domain(document) == domain.domain_id:
            return document
    document = decode(raw)
    own = DOMAINS.get(_goal_domain(document)) or RUNTIMES.get(_goal_domain(document))
    if own is not None and own.decode is not None:
        raise WireFailure("A document must satisfy its own domain's numeric profile")
    return document


def main():
    parser = argparse.ArgumentParser(description="Supply structured JSON on stdin.")
    parser.add_argument("--approver", nargs="?", const="terminal", default="deny", metavar="deny|file:PATH")
    parser.add_argument("--config")
    parser.add_argument("--resume", metavar="DECISION_ID", help="run again a decision whose earlier outcome is unknown; host choice, never from the request")
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(65_537)
        if len(raw) > 65_536:
            raise ContractError("Local driver input exceeds 65,536 bytes")
        result = run_document(_decode_for_domain(raw), args.approver, config=args.config, resume=args.resume)
        output = encode(result)
        if len(output) > MAX_OUTPUT:
            raise ContractError("Complete driver output exceeds budget; output withheld")
        sys.stdout.buffer.write(output + b"\n")
        return 0
    except BrokenPipeError:
        return 2
    except (DecisionReuseRefused, DriverRefusal) as error:
        code = error.code if isinstance(error, DriverRefusal) else "decision_reuse_refused"
        sys.stdout.write(json.dumps({"schema": "cstack.driver-error/0.1", "error": code, "detail": str(error),
                                     "formal_proof": False, "runtime_goal_acceptance": False}) + "\n")
        return 2
    except (ContractError, WireFailure, ValueError, TypeError, KeyError, OSError, RuntimeError):
        sys.stdout.write(json.dumps({"schema": "cstack.driver-error/0.1", "error": "invalid_or_unsupported_request",
            "formal_proof": False, "runtime_goal_acceptance": False}) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

