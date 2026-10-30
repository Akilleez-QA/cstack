"""Foundation Refrigeration extends the POODO base as a sibling of Math, never a subclass of it.

The domain owns its own numeric semantics (finite decimals with explicit units, canonical
kPa(a)/degC) and its own meaning: a tool result is an observation, never an engineering, safety
or compliance determination, and nothing operates a plant (monitoring-only, never control).
"""
from poodo_core import Admission, CapabilityDescriptor, DomainDescriptor, Interpretation, PoodoCore

REFRIGERATION_TOOL_NAMES = (
    "saturation_pressure", "saturation_temperature", "convert_pressure", "convert_temperature",
    "check_reading_against_saturation", "exposure_limits", "resolve_equipment_kind")

REFRIGERATION_CAPABILITY = CapabilityDescriptor("foundation_refrigeration", "foundation-refrigeration-v01",
                                                REFRIGERATION_TOOL_NAMES, lane="ToolFace")
REFRIGERATION_DOMAIN = DomainDescriptor("foundation_refrigeration", "0.1.0", (REFRIGERATION_CAPABILITY,),
    "Finite decimal JSON numbers with an explicit unit ({value, unit}); canonical storage kPa(a) and degC; "
    "no exponent, NaN or infinity; IEEE double arithmetic with rounded decimal results, not exact values. "
    "Not Foundation Math's integer-only profile.")

INTERPRETATION_LIMITS = (
    "A tool observation is not an engineering, safety or compliance determination.",
    "Monitoring-only: no control action, write path or plant operation is offered or implied.",
    "Superheat- and subcooling-style deltas are observations, never a diagnosis or a normal/abnormal call.",
    "CHECK values are recorded but not approved by a qualified person; DISPUTED values are unresolved.",
    "Tool success is not goal acceptance; the receipt's assumptions (atmosphere, sensor placement) remain the caller's.",
)


class RefrigerationExtension:
    def descriptor(self):
        return REFRIGERATION_DOMAIN

    def admit_goal(self, goal):
        return Admission(goal.domain_id == "foundation_refrigeration",
                         "Domain shape checked; goal assumptions and plant facts are not established.")

    def validate_call(self, goal, request):
        return Admission(request.capability_id == "foundation_refrigeration"
                         and request.operation in REFRIGERATION_TOOL_NAMES,
                         "Named operation belongs to the fixed Foundation Refrigeration v0.1 inventory.")

    def interpret(self, goal, request, outcome):
        completed = outcome.to_dict()["execution_status"] == "completed"
        return Interpretation("tool_observation" if completed else "unassessed",
            "Only the supplied request against the Foundation's pinned data; no plant, sensor or person is assessed.",
            INTERPRETATION_LIMITS)


class FoundationRefrigeration(PoodoCore):
    def __init__(self, capability, grants, ledger, **host):
        # host: approvals, approver, clock (ADR 003), supplied only by bootstrap.
        super().__init__(RefrigerationExtension(), {"foundation_refrigeration": capability}, grants, ledger, **host)
