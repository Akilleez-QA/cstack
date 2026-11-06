"""The forge domain: one governed EndoForge run. Host configuration decides what it may import; a request only names it."""
from poodo_core import Admission, CapabilityDescriptor, DomainDescriptor, Interpretation, PoodoCore

FORGE_DOMAIN_ID = "cstack_forge"
FORGE_TOOL_NAMES = ("run_goal",)
FORGE_CAPABILITY = CapabilityDescriptor(FORGE_DOMAIN_ID, "cstack-forge-v01", FORGE_TOOL_NAMES, lane="RuntimeFace")
FORGE_DOMAIN = DomainDescriptor(FORGE_DOMAIN_ID, "0.1.0", (FORGE_CAPABILITY,),
                                "Bounded JSON integers and strings in requests; kernels and Foundations own their own numbers.")
ARGUMENT_FIELDS = {"need", "declared_imports", "signature", "cases", "checks", "max_candidates"}
LIMITATIONS = (
    "A passed run means the candidate passed the gates and this frozen evaluator under the stated environment.",
    "It is not engineering, safety or compliance approval, and it is not goal acceptance.",
    "Cohort containment is what the receipt records; no OS sandbox is claimed.",
)


class ForgeExtension:
    def descriptor(self):
        return FORGE_DOMAIN

    def admit_goal(self, goal):
        return Admission(goal.domain_id == FORGE_DOMAIN_ID, "Domain shape checked; the run decides nothing about the world.")

    def validate_call(self, goal, request):
        arguments = request.arguments
        return Admission(request.capability_id == FORGE_DOMAIN_ID and request.operation in FORGE_TOOL_NAMES
                         and type(arguments) is dict and set(arguments) == ARGUMENT_FIELDS,
                         "Named operation and closed argument fields belong to the forge domain.")

    def interpret(self, goal, request, outcome):
        completed = outcome.to_dict()["execution_status"] == "completed"
        return Interpretation("tool_observation" if completed else "unassessed",
                              "Only this candidate, evaluator and environment; nothing outside them is assessed.", LIMITATIONS)


class CstackForge(PoodoCore):
    def __init__(self, capability, grants, ledger, **host):
        super().__init__(ForgeExtension(), {FORGE_DOMAIN_ID: capability}, grants, ledger, **host)
