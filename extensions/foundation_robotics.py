"""Foundation Robotics / Mechanical Engineering: the physics motion must obey, as judgements. A sibling of Math.

Its tools judge numbers sampled from an animation (three.js poses, Blender actions, baked clips): scale-correct
timing, gait, balance, joint-chain reach and conditioning, mechanism kinematics, and squash volume. A verdict compares
the supplied motion with first-principles relations and stated thresholds; it is never acceptance of an animation,
which stays a person's call on moving playblasts.
"""
from poodo_core import Admission, CapabilityDescriptor, DomainDescriptor, Interpretation, PoodoCore

ROBOTICS_DOMAIN_ID = "foundation_robotics"
ROBOTICS_TOOL_NAMES = ("scale_timing", "gait_check", "balance_check", "ik_check", "mechanism_check", "squash_check")

ROBOTICS_CAPABILITY = CapabilityDescriptor(ROBOTICS_DOMAIN_ID, "foundation-robotics-v01", ROBOTICS_TOOL_NAMES,
                                           lane="ToolFace")
ROBOTICS_DOMAIN = DomainDescriptor(ROBOTICS_DOMAIN_ID, "0.1.0", (ROBOTICS_CAPABILITY,),
    "Bounded JSON integers and strings only, in milli-SI units: mm, ms, mrad, mm/s, mm/s^2, mrad/s, milli-fps and "
    "per-mille; no floating, exponent or nonfinite numbers.")

INTERPRETATION_LIMITS = (
    "A verdict compares the caller's sampled motion with physical relations and thresholds; it is not acceptance "
    "of an animation.",
    "The caller's sampling (world space, contact flags, centre of mass) is taken as given; nothing here sees a rig.",
    "CHECK thresholds are not yet calibrated on known-good and known-bad motion for every tool.",
    "Observation only: no rig, render, write path or control action is offered or implied.",
    "Tool success is not goal acceptance.",
)


class RoboticsExtension:
    def descriptor(self):
        return ROBOTICS_DOMAIN

    def admit_goal(self, goal):
        return Admission(goal.domain_id == ROBOTICS_DOMAIN_ID,
                         "Domain shape checked; goal assumptions and the animation's quality are not established.")

    def validate_call(self, goal, request):
        return Admission(request.capability_id == ROBOTICS_DOMAIN_ID and request.operation in ROBOTICS_TOOL_NAMES,
                         "Named operation belongs to the fixed Foundation Robotics v0.1 inventory.")

    def interpret(self, goal, request, outcome):
        completed = outcome.to_dict()["execution_status"] == "completed"
        return Interpretation("tool_observation" if completed else "unassessed",
            "Only the supplied numbers against the pinned Robotics Foundation; no rig, clip or render is assessed.",
            INTERPRETATION_LIMITS)


class FoundationRobotics(PoodoCore):
    def __init__(self, capability, grants, ledger, **host):
        # host: approvals, approver, clock (ADR 003), supplied only by bootstrap.
        super().__init__(RoboticsExtension(), {ROBOTICS_DOMAIN_ID: capability}, grants, ledger, **host)
