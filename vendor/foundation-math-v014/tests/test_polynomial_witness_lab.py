from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest

from polynomial_witness.api import construct, construct_json, verify_json
from polynomial_witness.checker import verify_witness
from polynomial_witness.contract import Limits, MAX_WIRE_BYTES
from polynomial_witness.producer import produce

ROOT = Path(__file__).resolve().parents[1]

def q(n, d=1):
    return {"type": "rational", "numerator": n, "denominator": d}

def v(name):
    return {"type": "variable", "name": name}

def add(a, b):
    return {"type": "add", "operands": [a, b]}

def mul(a, b):
    return {"type": "multiply", "operands": [a, b]}

def product(items):
    if not items:
        return q(1)
    if len(items) == 1:
        return items[0]
    middle = len(items) // 2
    return mul(product(items[:middle]), product(items[middle:]))

def request(variables, left, right=None):
    return {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": variables,
            "operation": "verify_identity", "operands": [left, q(0) if right is None else right]}

def pair(n, d=1):
    return {"numerator": n, "denominator": d}

class WitnessTests(unittest.TestCase):
    def assert_identity(self, req):
        result = construct(req)
        self.assertEqual(result["status"], "success", result)
        self.assertEqual(result["result"]["kind"], "coefficient_identity")
        self.assertEqual(result["result"]["normalized_difference"], {"terms": [], "total_degree": None})
        self.assertNotIn("witness", result["result"])
        self.assertEqual(result["verification"]["status"], "not_applicable")
        self.assertEqual(result["usage"]["substitution_trials"], 0)
        return result

    def assert_witness(self, req, expected_assignment=None):
        before = deepcopy(req)
        result = construct(req)
        self.assertEqual(result["status"], "success", result)
        self.assertEqual(req, before)
        self.assertEqual(result["result"]["kind"], "nonzero_evaluation")
        self.assertEqual(result["verification"]["status"], "accepted")
        w = result["result"]["witness"]
        self.assertNotEqual(w["difference_value"]["numerator"], 0)
        if expected_assignment is not None:
            self.assertEqual(w["assignment"], expected_assignment)
        traces = result["result"]["construction_trace"]
        self.assertEqual([t["variable"] for t in traces], req["variables"])
        self.assertEqual(result["usage"]["substitution_trials"], sum(len(t["trials"]) for t in traces))
        self.assertLessEqual(result["usage"]["substitution_trials"], result["result"]["current_degree_trial_bound"])
        self.assertLessEqual(result["result"]["current_degree_trial_bound"], result["result"]["initial_degree_trial_bound"])
        for t in traces:
            self.assertEqual([a["value"] for a in t["trials"]], list(range(t["chosen_value"] + 1)))
            self.assertEqual([a["remaining_nonzero"] for a in t["trials"]], [False]*t["chosen_value"] + [True])
            self.assertLessEqual(t["chosen_value"], t["current_degree"])
        return result

    def test_zero_no_variables(self):
        self.assert_identity(request([], q(0)))

    def test_zero_declared_variables(self):
        self.assert_identity(request(["x", "unused"], add(v("x"), mul(q(-1), v("x")))))

    def test_true_nontrivial_identity(self):
        x, y = v("x"), v("y")
        self.assert_identity(request(["x", "y"], mul(add(x, y), add(x, y)), add(add(mul(x, x), mul(q(2), mul(x, y))), mul(y, y))))

    def test_constant_no_variables(self):
        result = self.assert_witness(request([], q(1, 2), q(1, 3)), {})
        self.assertEqual(result["result"]["witness"]["difference_value"], pair(1, 6))
        self.assertEqual(result["usage"]["substitution_trials"], 0)

    def test_constant_declared_unused_variables(self):
        result = self.assert_witness(request(["x", "y"], q(-7, 3)), {"x": 0, "y": 0})
        self.assertEqual([t["current_degree"] for t in result["result"]["construction_trace"]], [0, 0])

    def test_unused_variable_order(self):
        self.assert_witness(request(["z", "x", "y"], v("x")), {"z": 0, "x": 1, "y": 0})

    def test_false_square_identity(self):
        x, y = v("x"), v("y")
        result = self.assert_witness(request(["x", "y"], mul(add(x, y), add(x, y)), add(mul(x, x), mul(y, y))), {"x": 1, "y": 1})
        self.assertEqual(result["result"]["witness"]["left_value"], pair(4))
        self.assertEqual(result["result"]["witness"]["right_value"], pair(2))
        self.assertEqual(result["result"]["witness"]["difference_value"], pair(2))

    def test_degree_32_with_32_bad_roots(self):
        result = self.assert_witness(request(["x"], product([add(v("x"), q(-i)) for i in range(32)])), {"x": 32})
        self.assertEqual(result["usage"]["substitution_trials"], 33)
        self.assertEqual(result["result"]["witness"]["difference_value"], pair(math.factorial(32)))

    def test_sparse_eight_variable_product_not_grid(self):
        names = ["x"+str(i) for i in range(8)]
        result = self.assert_witness(request(names, product([v(n) for n in names])), dict.fromkeys(names, 1))
        self.assertEqual(result["usage"]["substitution_trials"], 16)
        self.assertEqual(result["result"]["initial_degree_trial_bound"], 16)
        self.assertEqual(result["result"]["difference_term_count"], 1)

    def test_multivariate_root_product(self):
        names = ["x", "y", "z"]
        expr = product([product([add(v(name), q(-i)) for i in range(4)]) for name in names])
        result = self.assert_witness(request(names, expr), dict.fromkeys(names, 4))
        self.assertEqual(result["usage"]["substitution_trials"], 15)
        self.assertEqual(result["result"]["witness"]["difference_value"], pair(24**3))

    def test_dynamic_degree_can_fall(self):
        expr = add(mul(v("x"), mul(v("y"), v("y"))), q(1))
        result = self.assert_witness(request(["x", "y"], expr), {"x": 0, "y": 0})
        self.assertEqual(result["result"]["construction_trace"][1]["initial_degree"], 2)
        self.assertEqual(result["result"]["construction_trace"][1]["current_degree"], 0)

    def test_rational_negative_denominator_input(self):
        result = self.assert_witness(request(["x"], mul(q(2, -6), v("x"))), {"x": 1})
        self.assertEqual(result["result"]["witness"]["difference_value"], pair(-1, 3))
        self.assertNotEqual(result["input_sha256"], result["request_sha256"])

    def test_deterministic(self):
        req = request(["x", "y"], mul(v("x"), add(v("y"), q(-1))))
        self.assertEqual(construct(req), construct(req))

    def test_no_mutable_output_alias_to_request(self):
        req = request(["x"], v("x"))
        result = construct(req)
        result["request"]["variables"][0] = "changed"
        self.assertEqual(req["variables"], ["x"])

    def test_receipt_scope_is_detached(self):
        req = request([], q(1))
        first = produce(req)
        first["scope"]["exclusions"].append("untrusted mutation")
        self.assertNotIn("untrusted mutation", produce(req)["scope"]["exclusions"])

    def test_frozen_backend_hashes(self):
        expected = {
            "polynomial.py": "b700a069e0af9609a7b9e63d6a8185d9b430630d6d2f55f5a6ac2e5155022b9b",
            "calculator.py": "146ec4fc9fca0c3400331c06595894fd9cb6a23668abae5c7b8d196e06bad54e",
        }
        for name, digest in expected.items():
            self.assertEqual(sha256((ROOT / "polynomial_witness" / "_vendor" / name).read_bytes()).hexdigest(), digest)

    def test_identity_requires_no_search_budget(self):
        self.assertEqual(produce(request([], q(0)), Limits(0, 0, 0, 0))["result"]["kind"], "coefficient_identity")

    def test_no_variable_constant_requires_no_trials(self):
        self.assertEqual(construct(request([], q(1)), replace(Limits(), max_trials=0))["status"], "success")

class ForgeryTests(unittest.TestCase):
    def setUp(self):
        self.req = request(["x", "y"], mul(v("x"), v("y")))
        self.witness = produce(self.req)["result"]["witness"]

    def rejected(self, witness, req=None):
        result = verify_witness(self.req if req is None else req, witness)
        self.assertEqual(result["status"], "rejected", result)
        return result

    def test_wrong_point_zero_difference(self):
        self.witness["assignment"]["x"] = 0
        self.rejected(self.witness)

    def test_false_left_right_difference(self):
        for field in ("left_value", "right_value", "difference_value"):
            with self.subTest(field=field):
                w = deepcopy(self.witness)
                w[field] = pair(999)
                self.rejected(w)

    def test_wrong_request_binding(self):
        req = request(["x", "y"], add(mul(v("x"), v("y")), q(1)))
        self.rejected(self.witness, req)

    def test_raw_representation_binding(self):
        req = request(["x"], mul(q(2, 2), v("x")))
        w = produce(req)["result"]["witness"]
        req["operands"][0]["operands"][0] = q(1)
        result = self.rejected(w, req)
        self.assertEqual(result["error"]["code"], "binding_mismatch")

    def test_forged_hash(self):
        for field in ("input_sha256", "request_sha256"):
            w = deepcopy(self.witness)
            w[field] = "0"*64
            self.rejected(w)

    def test_wrong_ring_and_order(self):
        for field, value in (("coefficient_field", "F2"), ("kind", "quotient_ring"), ("variables", ["y", "x"])):
            w = deepcopy(self.witness)
            w["ring"][field] = value
            self.rejected(w)

    def test_extra_missing_or_wrong_point_types(self):
        for assignment in ({"x": 1}, {"x": 1, "y": 1, "z": 1}, {"x": True, "y": 1}, {"x": 1.0, "y": 1}, {"x": -1, "y": 1}, {"x": 33, "y": 1}, [1, 1]):
            w = deepcopy(self.witness)
            w["assignment"] = assignment
            self.rejected(w)

    def test_noncanonical_or_wrong_rational_types(self):
        for value in (pair(2, 2), pair(True), pair(1, True), pair(1.0), pair(1, 0), pair(-1, -1), {"numerator": 1}, {"numerator": 1, "denominator": 1, "extra": 0}):
            w = deepcopy(self.witness)
            w["difference_value"] = value
            self.rejected(w)

    def test_extra_witness_fields_and_wrong_schema(self):
        for key, value in (("extra", 1), ("schema_version", 1), ("schema_version", "2.0"), ("construction_trace", [])):
            w = deepcopy(self.witness)
            w[key] = value
            self.rejected(w)

    def test_identity_is_not_witness(self):
        result = verify_witness(request([], q(0)), produce(request([], q(0)))["result"])
        self.assertEqual(result["status"], "rejected")

    def test_valid_nonminimal_point_checks_but_does_not_certify_trace(self):
        self.witness["assignment"] = {"x": 2, "y": 3}
        self.witness["left_value"] = self.witness["difference_value"] = pair(6)
        result = verify_witness(self.req, self.witness)
        self.assertEqual(result["status"], "accepted")
        self.assertIn("first-choice minimality", result["scope"]["not_checked"])

    def test_checker_no_producer_import(self):
        code = "import sys; import polynomial_witness.checker; raise SystemExit('polynomial_witness.producer' in sys.modules)"
        process = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)

class ResourceAndIngressTests(unittest.TestCase):
    def test_invalid_request_shapes(self):
        base = request(["x"], v("x"))
        modifications = [("domain", "quotient_ring"), ("coefficient_field", "F2"), ("operation", "add"),
                         ("variables", ["x", "x"]), ("variables", ["x"]*9), ("variables", ["ξ"]),
                         ("variables", "x"), ("constraints", []), ("operands", [v("x")]), ("operands", "x")]
        for key, value in modifications:
            req = deepcopy(base)
            req[key] = value
            with self.subTest(key=key, value=value):
                self.assertEqual(construct(req)["status"], "error")

    def test_invalid_expressions(self):
        for expr in (q(True), q(1.5), q("1"), q(1, 0), q(1, True), q(2**256), v("z"),
                     {"type": "divide", "operands": [v("x"), v("x")]},
                     {"type": "rational", "numerator": 1, "denominator": 1, "extra": 1},
                     {"type": "add", "operands": [q(0)]}, "x", None):
            self.assertEqual(construct(request(["x"], expr))["status"], "error")

    def test_cycle_is_bounded(self):
        expr = add(q(1), q(2))
        expr["operands"][0] = expr
        result = construct(request([], expr))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "resource_limit")

    def test_degree_limit_not_no_witness(self):
        result = construct(request(["x"], product([v("x")]*33)))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "resource_limit")
        self.assertIsNone(result["result"])

    def test_term_limit(self):
        names = ["x"+str(i) for i in range(6)]
        expr = product([add(q(1), add(v(n), mul(v(n), v(n)))) for n in names])
        result = construct(request(names, expr))
        self.assertEqual(result["error"]["code"], "resource_limit")

    def test_coefficient_limit(self):
        expr = product([q(2**255)]*9)
        result = construct(request([], expr))
        self.assertEqual(result["error"]["code"], "resource_limit")

    def test_ast_node_limit(self):
        result = construct(request([], product([q(1)]*513)))
        self.assertEqual(result["error"]["code"], "resource_limit")

    def test_request_byte_limit(self):
        # Input is valid in shape but its non-normalized literal encoding is bounded.
        raw = json.dumps(request([], q(1))) + ' ' * MAX_WIRE_BYTES
        self.assertEqual(construct_json(raw)["error"]["code"], "resource_limit")

    def test_trial_limit(self):
        result = construct(request(["x"], v("x")), replace(Limits(), max_trials=1))
        self.assertEqual(result["error"]["code"], "resource_limit")
        self.assertIsNone(result["result"])

    def test_term_visit_limit(self):
        result = construct(request(["x"], v("x")), replace(Limits(), max_substitution_term_visits=0))
        self.assertEqual(result["error"]["code"], "resource_limit")

    def test_value_bit_limit(self):
        result = construct(request([], q(32)), replace(Limits(), max_value_bits=5))
        self.assertEqual(result["error"]["code"], "resource_limit")

    def test_checker_node_limit_is_inconclusive(self):
        req = request(["x"], v("x"))
        w = produce(req)["result"]["witness"]
        result = verify_witness(req, w, replace(Limits(), max_evaluation_nodes=1))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "resource_limit")
        checked = construct(req, replace(Limits(), max_evaluation_nodes=1))
        self.assertEqual(checked["error"]["code"], "witness_check_failed")
        self.assertIsNone(checked["result"])

    def test_oversized_certificate_fraction(self):
        req = request([], q(1))
        w = produce(req)["result"]["witness"]
        w["difference_value"] = pair(2**4096)
        self.assertEqual(verify_witness(req, w)["error"]["code"], "resource_limit")

    def test_invalid_limits(self):
        req = request([], q(1))
        for limits in (None, {}, Limits(max_trials=True), Limits(max_trials=-1), Limits(max_trials=265), Limits(max_value_bits=4097)):
            self.assertEqual(construct(req, limits)["error"]["code"], "invalid_limits")

    def test_strict_json(self):
        for data in ('{"domain":"polynomial_ring","domain":"polynomial_ring"}', '{"x":NaN}', b'\xff', '[]', '{', None):
            self.assertEqual(construct_json(data)["status"], "error")
        self.assertEqual(construct_json('{"x":'+str(2**4096)+'}')["error"]["code"], "resource_limit")

    def test_json_roundtrip_construct_and_verify(self):
        req = request(["x"], v("x"))
        result = construct_json(json.dumps(req))
        check = verify_json(json.dumps({"request": req, "witness": result["result"]["witness"]}))
        self.assertEqual(check["status"], "accepted")

    def test_checker_can_evaluate_without_expanding(self):
        req = request(["x"], product([v("x")]*33))
        from polynomial_witness.contract import artifact_hash, ring_for
        w = {"schema_version": "1.0", "input_sha256": artifact_hash(req), "request_sha256": artifact_hash(req),
             "ring": ring_for(req), "assignment": {"x": 1}, "left_value": pair(1), "right_value": pair(0), "difference_value": pair(1)}
        self.assertEqual(construct(req)["error"]["code"], "resource_limit")
        self.assertEqual(verify_witness(req, w)["status"], "accepted")

    def test_cli_success_and_failure_exit_codes(self):
        for mode, payload, expected in (([], request([], q(0)), 0), ([], request(["x"], v("x")), 0),
                                        ([], {"bad": True}, 2), (["bad"], {}, 2)):
            p = subprocess.run([sys.executable, "-B", "-m", "polynomial_witness", *mode], cwd=ROOT,
                               input=json.dumps(payload), text=True, capture_output=True)
            self.assertEqual(p.returncode, expected, p.stderr)
            self.assertIsInstance(json.loads(p.stdout), dict)
        req = request(["x"], v("x"))
        w = produce(req)["result"]["witness"]
        w["assignment"]["x"] = 0
        p = subprocess.run([sys.executable, "-B", "-m", "polynomial_witness", "verify"], cwd=ROOT,
                           input=json.dumps({"request": req, "witness": w}), text=True, capture_output=True)
        self.assertEqual(p.returncode, 1, p.stderr)

if __name__ == "__main__":
    unittest.main()
