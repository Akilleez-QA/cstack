"""Foundation Template: the empty domain a user copies to make their own. A sibling of Math, never a subclass.

Its one tool, echo_observation, is a placeholder that echoes validated input as an observation with Evidence.
The core suite uses it as its sample domain, so the control base never depends on a particular domain.
"""
from poodo_core import Admission, CapabilityDescriptor, DomainDescriptor, Interpretation, PoodoCore

TEMPLATE_DOMAIN_ID = "foundation_template"
TEMPLATE_TOOL_NAMES = ("echo_observation",)

TEMPLATE_CAPABILITY = CapabilityDescriptor(TEMPLATE_DOMAIN_ID, "foundation-template-v01", TEMPLATE_TOOL_NAMES,
                                           lane="ToolFace")
TEMPLATE_DOMAIN = DomainDescriptor(TEMPLATE_DOMAIN_ID, "0.1.0", (TEMPLATE_CAPABILITY,),
    "Bounded JSON integers and strings only; no floating, exponent or nonfinite numbers. "
    "A placeholder profile: a real domain states its own.")

INTERPRETATION_LIMITS = (
    "A placeholder observation: the tool echoes its own input and establishes nothing about the world.",
    "Observation only: no domain determination, control action or write path is offered or implied.",
    "Tool success is not goal acceptance.",
)


class TemplateExtension:
    def descriptor(self):
        return TEMPLATE_DOMAIN

    def admit_goal(self, goal):
        return Admission(goal.domain_id == TEMPLATE_DOMAIN_ID,
                         "Domain shape checked; goal assumptions are not established.")

    def validate_call(self, goal, request):
        return Admission(request.capability_id == TEMPLATE_DOMAIN_ID and request.operation in TEMPLATE_TOOL_NAMES,
                         "Named operation belongs to the fixed Foundation Template v0.1 inventory.")

    def interpret(self, goal, request, outcome):
        completed = outcome.to_dict()["execution_status"] == "completed"
        return Interpretation("tool_observation" if completed else "unassessed",
            "Only the supplied request against the pinned template Foundation; nothing outside it is assessed.",
            INTERPRETATION_LIMITS)


class FoundationTemplate(PoodoCore):
    def __init__(self, capability, grants, ledger, **host):
        # host: approvals, approver, clock (ADR 003), supplied only by bootstrap.
        super().__init__(TemplateExtension(), {TEMPLATE_DOMAIN_ID: capability}, grants, ledger, **host)
