"""Foundation Engine: two read-only validators from the pinned game engine. A sibling of Math, never a subclass.

The tools return the validated value itself (a render mask, or scene output with defaults filled). They carry no
receipt or assessment, so the adapter admits them through its own result path as tool observations only.
"""
from poodo_core import Admission, CapabilityDescriptor, DomainDescriptor, Interpretation, PoodoCore

ENGINE_DOMAIN_ID = "foundation_engine"
ENGINE_TOOL_NAMES = ("validate_render_mask", "validate_scene_output")

ENGINE_CAPABILITY = CapabilityDescriptor(ENGINE_DOMAIN_ID, "foundation-engine-v020", ENGINE_TOOL_NAMES,
                                         lane="ToolFace")
ENGINE_DOMAIN = DomainDescriptor(ENGINE_DOMAIN_ID, "0.2.0", (ENGINE_CAPABILITY,),
    "Bounded JSON integers, strings and finite decimal literals; no exponent or nonfinite input numbers.")

INTERPRETATION_LIMITS = (
    "A validated value is the pinned engine's reading of the supplied input; no scene, renderer or game is assessed.",
    "Observation only: no engine state is read or changed and no control action is offered or implied.",
    "Tool success is not goal acceptance.",
)


class EngineExtension:
    def descriptor(self):
        return ENGINE_DOMAIN

    def admit_goal(self, goal):
        return Admission(goal.domain_id == ENGINE_DOMAIN_ID, "Domain shape checked; goal assumptions not established.")

    def validate_call(self, goal, request):
        return Admission(request.capability_id == ENGINE_DOMAIN_ID and request.operation in ENGINE_TOOL_NAMES,
                         "Named operation belongs to the fixed Foundation Engine v0.2.0 inventory.")

    def interpret(self, goal, request, outcome):
        completed = outcome.to_dict()["execution_status"] == "completed"
        return Interpretation("tool_observation" if completed else "unassessed",
            "Only the supplied value against the pinned Foundation Engine validators.", INTERPRETATION_LIMITS)


class FoundationEngine(PoodoCore):
    def __init__(self, capability, grants, ledger, **host):
        # host: approvals, approver, clock (ADR 003), supplied only by bootstrap.
        super().__init__(EngineExtension(), {ENGINE_DOMAIN_ID: capability}, grants, ledger, **host)
