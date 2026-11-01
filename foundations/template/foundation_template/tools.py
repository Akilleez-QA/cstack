import hashlib
import json

from . import __version__

TOOL_NAMES = ("echo_observation",)
BOUNDARY = {"observation_only": True, "domain_determination": False, "control_action": False}
MAX_OBSERVATION_CHARS = 256


class ToolInputError(ValueError):
    pass


def input_sha256(arguments):
    return hashlib.sha256(json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                                     allow_nan=False).encode("ascii")).hexdigest()


def evidence(applies_to, note):
    return {"applies_to": applies_to, "evidence": {"basis": {"kind": "practice", "note": note}, "status": "CHECK"}}


def echo_observation(arguments):
    if set(arguments) != {"observation"}:
        raise ToolInputError("echo_observation takes exactly one argument: observation")
    value = arguments["observation"]
    if type(value) is not str or not 1 <= len(value) <= MAX_OBSERVATION_CHARS:
        raise ToolInputError(f"observation must be a string of 1 to {MAX_OBSERVATION_CHARS} characters")
    return "observation_echoed", {"observation": value}, [
        evidence("result.observation", "Placeholder echo of the caller's own input; no domain source backs it.")]


TOOLS = {"echo_observation": echo_observation}


def run(name, arguments):
    try:
        assessment, result, entries = TOOLS[name](arguments)
        failed, status, error = False, "ok", None
    except ToolInputError as problem:
        assessment, result, failed, status, error = "tool_error", None, True, "error", str(problem)
        entries = [evidence("error", "Argument check by the template Foundation; the request was not observed.")]
    return failed, assessment, {"tool": name, "version": __version__, "status": status,
                                "input_sha256": input_sha256(arguments), "boundary": dict(BOUNDARY),
                                "result": result, "error": error, "evidence": entries}
