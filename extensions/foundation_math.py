"""Foundation Math extends the POODO base through trusted, versioned hooks."""
from poodo_core import (Admission, CapabilityDescriptor, DomainDescriptor, Interpretation, PoodoCore)

TOOL_NAMES = (
    "exact_scalar", "polynomial_identity", "finite_box_search", "check_finite_box_witness",
    "certify_rational_matrix", "check_rational_matrix_certificate", "construct_polynomial_witness",
    "check_polynomial_witness", "solve_rational_linear_system", "check_rational_linear_system_certificate",
    "calculate_fixed_character", "check_fixed_character_certificate", "calculate_formal_split_bundle",
    "check_formal_split_bundle_certificate", "replay_claim_applicability", "match_hypothesis_scope",
    "calculate_formal_exterior", "check_formal_exterior_certificate", "plan_validation_evidence")

MATH_CAPABILITY = CapabilityDescriptor("foundation_math", "foundation-math-v014", TOOL_NAMES, lane="ToolFace")
MATH_DOMAIN = DomainDescriptor("foundation_math", "0.1.0", (MATH_CAPABILITY,),
    "Explicit exact Z/Q/formal domains only; no floating-point fallback. Assumed input objects remain assumptions.")


class MathExtension:
    def descriptor(self):
        return MATH_DOMAIN

    def admit_goal(self, goal):
        return Admission(goal.domain_id == "foundation_math", "Domain shape checked, assumptions not proved.")

    def validate_call(self, goal, request):
        return Admission(request.capability_id == "foundation_math" and request.operation in TOOL_NAMES,
                         "Named operation belongs to the pinned Math capability.")

    def interpret(self, goal, request, outcome):
        completed = outcome.to_dict()["execution_status"] == "completed"
        return Interpretation("tool_observation" if completed else "unassessed",
            "Only the exact supplied request in its declared formal domain; goal assumptions remain unproved.",
            ("Tool success is not predicate truth, formal proof, or goal acceptance.",
             "Caller-authored objects, hypotheses and physical identifications are not established by the tool.",
             "Hashes identify bytes, not authentic provenance or mathematical truth."))


class FoundationMath(PoodoCore):
    def __init__(self, capability, grants, ledger, **host):
        # host: approvals, approver, clock (ADR 003), supplied only by bootstrap.
        super().__init__(MathExtension(), {"foundation_math": capability}, grants, ledger, **host)


UNIMPLEMENTED_FOUNDATIONS = {
    "foundation_engine": "Unimplemented sibling domain contract; not Foundation Math and not Endoforge.",
    # Foundation Refrigeration v0.1 is a sibling extension (extensions/foundation_refrigeration.py, ADR 002).
    # Only the parts it does not implement stay listed here.
    "foundation_refrigeration.rules": "B114 marker rules, P&ID rule packs and claim policy are unimplemented; "
                                      "the marker scheme and 70 psig split are DISPUTED, not chosen.",
    "foundation_refrigeration.reference_plants": "No reference-plant/1 projection; the reference model is unverified.",
    "foundation_refrigeration.determinations": "No diagnosis, normal-range call, engineering, safety or compliance "
                                               "determination, and no control path; tools return observations only.",
    "lean": "No real isolated formal verifier is bound to this prototype.",
    "endoforge": "Generative UI/disposable-software engine role reserved; generator lifecycle is unimplemented here."}
