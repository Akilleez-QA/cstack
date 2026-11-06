"""The forge domain: one governed EndoForge run. Host configuration decides what it may import; a request only names it."""
from poodo_core import Admission, CapabilityDescriptor, DomainDescriptor, Interpretation, PoodoCore

FORGE_DOMAIN_ID = "cstack_forge"
FORGE_TOOL_NAMES = ("run_goal",)
FORGE_CAPABILITY = CapabilityDescriptor(FORGE_DOMAIN_ID, "cstack-forge-v01", FORGE_TOOL_NAMES, lane="RuntimeFace")
FORGE_DOMAIN = DomainDescriptor(FORGE_DOMAIN_ID, "0.1.0", (FORGE_CAPABILITY,),
                                "Bounded JSON integers and strings in requests; kernels and Foundations own their own numbers.")
ARGUMENT_FIELDS = {"need", "declared_imports", "signature", "cases", "checks", "max_candidates"}
CHECK_FIELDS = {"case", "foundation", "tool", "arguments", "path", "tolerance"}
MAX_CANDIDATES = 8
MAX_CASES = 64
LIMITATIONS = (
    "A passed run means the candidate passed the gates and this frozen evaluator under the stated environment.",
    "It is not engineering, safety or compliance approval, and it is not goal acceptance.",
    "Cohort containment is what the receipt records; no OS sandbox is claimed.",
)


def _number(value):
    return type(value) in (int, float)


def request_problem(arguments):
    """The closed shape of a run, checked before anything is decided. None means it's well formed."""
    if type(arguments) is not dict or set(arguments) != ARGUMENT_FIELDS:
        return "arguments must have exactly: " + ", ".join(sorted(ARGUMENT_FIELDS))
    if type(arguments["need"]) is not str or not arguments["need"].strip():
        return "need must be nonempty text"
    imports = arguments["declared_imports"]
    if type(imports) is not list or not imports or any(type(n) is not str for n in imports) or len(set(imports)) != len(imports):
        return "declared_imports must be a nonempty list of distinct names"
    if type(arguments["signature"]) is not dict:
        return "signature must be an object"
    budget = arguments["max_candidates"]
    if type(budget) is not int or not 1 <= budget <= MAX_CANDIDATES:
        return f"max_candidates must be an integer from 1 to {MAX_CANDIDATES}"
    cases = arguments["cases"]
    if type(cases) is not list or not 1 <= len(cases) <= MAX_CASES:
        return f"cases must be a list of 1 to {MAX_CASES}"
    if any(type(c) is not dict or set(c) != {"id", "inputs"} or type(c["id"]) is not str or type(c["inputs"]) is not dict for c in cases):
        return "each case must be exactly an id and inputs"
    ids = [c["id"] for c in cases]
    if len(set(ids)) != len(ids):
        return "case ids must be distinct"
    checks = arguments["checks"]
    if type(checks) is not list:
        return "checks must be a list of held-out checks"
    for check in checks:
        if type(check) is not dict or set(check) != CHECK_FIELDS or any(type(check[k]) is not str for k in ("case", "foundation", "tool", "path")):
            return "each held-out check must be exactly: " + ", ".join(sorted(CHECK_FIELDS))
        if type(check["arguments"]) is not dict or not _number(check["tolerance"]) or check["tolerance"] < 0:
            return "a held-out check needs object arguments and a nonnegative tolerance"
        if check["case"] not in ids:
            return "a held-out check names an unknown case"
    missing = sorted(set(ids) - {check["case"] for check in checks})
    if missing:
        return "every case needs a held-out check; missing: " + ", ".join(missing)
    return None


class ForgeExtension:
    def descriptor(self):
        return FORGE_DOMAIN

    def admit_goal(self, goal):
        return Admission(goal.domain_id == FORGE_DOMAIN_ID, "Domain shape checked; the run decides nothing about the world.")

    def validate_call(self, goal, request):
        problem = request_problem(request.arguments)
        return Admission(request.capability_id == FORGE_DOMAIN_ID and request.operation in FORGE_TOOL_NAMES and problem is None,
                         problem or "Named operation and closed argument fields belong to the forge domain.")

    def interpret(self, goal, request, outcome):
        completed = outcome.to_dict()["execution_status"] == "completed"
        return Interpretation("tool_observation" if completed else "unassessed",
                              "Only this candidate, evaluator and environment; nothing outside them is assessed.", LIMITATIONS)


class CstackForge(PoodoCore):
    def __init__(self, capability, grants, ledger, **host):
        super().__init__(ForgeExtension(), {FORGE_DOMAIN_ID: capability}, grants, ledger, **host)
