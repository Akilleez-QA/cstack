"""Foundation Film: film-production meaning and acceptance as measured gates. A sibling of Math, never a subclass.

Its tools judge the JSON measures that Endoforge's film producers emit (forge/endoforge/tools/film/): cinematic bands,
the mix contract, control-pass drift, the shared cue vocabulary and a look rejection alarm against an approved target
frame. A verdict compares supplied measures with stated thresholds; it is never acceptance of a film, which stays a
person's quality call.
"""
from poodo_core import Admission, CapabilityDescriptor, DomainDescriptor, Interpretation, PoodoCore

FILM_DOMAIN_ID = "foundation_film"
FILM_TOOL_NAMES = ("cinematic_gate", "reference_bands", "audio_gate", "drift_verdict", "cue_vocabulary_check",
                   "look_gate")

FILM_CAPABILITY = CapabilityDescriptor(FILM_DOMAIN_ID, "foundation-film-v01", FILM_TOOL_NAMES, lane="ToolFace")
FILM_DOMAIN = DomainDescriptor(FILM_DOMAIN_ID, "0.1.0", (FILM_CAPABILITY,),
    "Bounded JSON integers and strings only; every measure is an integer in milli-units of its natural unit "
    "(per-mille shares, milliseconds, milli-dB/LU, thousandths otherwise); no floating, exponent or nonfinite numbers.")

INTERPRETATION_LIMITS = (
    "A verdict compares the caller's measures with stated thresholds; it is not acceptance of a film.",
    "Measures are proxies for cinematic and audio quality (I12, I16); a person's quality call still decides.",
    "CHECK thresholds are not yet calibrated on known-good and known-bad films.",
    "look_gate is a rejection alarm only; the client judges the look on moving proofs.",
    "Observation only: no render, generation, write path or control action is offered or implied.",
    "Tool success is not goal acceptance.",
)


class FilmExtension:
    def descriptor(self):
        return FILM_DOMAIN

    def admit_goal(self, goal):
        return Admission(goal.domain_id == FILM_DOMAIN_ID,
                         "Domain shape checked; goal assumptions and the film's quality are not established.")

    def validate_call(self, goal, request):
        return Admission(request.capability_id == FILM_DOMAIN_ID and request.operation in FILM_TOOL_NAMES,
                         "Named operation belongs to the fixed Foundation Film v0.1 inventory.")

    def interpret(self, goal, request, outcome):
        completed = outcome.to_dict()["execution_status"] == "completed"
        return Interpretation("tool_observation" if completed else "unassessed",
            "Only the supplied measures against the pinned Film Foundation; no film, audio file or person is assessed.",
            INTERPRETATION_LIMITS)


class FoundationFilm(PoodoCore):
    def __init__(self, capability, grants, ledger, **host):
        # host: approvals, approver, clock (ADR 003), supplied only by bootstrap.
        super().__init__(FilmExtension(), {FILM_DOMAIN_ID: capability}, grants, ledger, **host)
