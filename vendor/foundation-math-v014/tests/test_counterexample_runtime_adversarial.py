"""Independent finite-search controls; finite exhaustion never proves a theorem."""
from __future__ import annotations

import copy
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from foundation_math.counterexample import check_witness, search_counterexample
from foundation_math.domains import DomainError, domain_handler
from foundation_math.orchestrator import Runtime

ROOT = Path(__file__).resolve().parents[1]


def literal(n, d=1):
    return {"type": "rational", "numerator": n, "denominator": d}


def variable(name):
    return {"type": "variable", "name": name}


def binary(op, left, right):
    return {"type": op, "operands": [left, right]}


def predicate(left, relation="eq", right=None):
    return {"left": left, "relation": relation, "right": literal(0) if right is None else right}


def request(assertion=None, constraints=None):
    return {"domain": "finite_integer_box", "coefficient_field": "Q", "variables": ["x"],
            "bounds": {"x": {"lower": -1, "upper": 1}}, "constraints": [] if constraints is None else constraints,
            "assertion": predicate(variable("x")) if assertion is None else assertion}


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def rehash(receipt):
    receipt["artifacts"]["result_sha256"] = digest(receipt["result"])
    unsigned = copy.deepcopy(receipt)
    unsigned["artifacts"].pop("evidence_sha256")
    receipt["artifacts"]["evidence_sha256"] = digest(unsigned)


class CounterexampleRuntimeAdversarialTests(unittest.TestCase):
    def test_36_integer_oracle_cases_with_unused_variable_and_order(self):
        expression = binary("add", binary("multiply", literal(3), variable("x")),
                            binary("multiply", literal(-2), variable("y")))
        compare = {"lt": lambda a, b: a < b, "le": lambda a, b: a <= b,
                   "eq": lambda a, b: a == b, "ne": lambda a, b: a != b,
                   "ge": lambda a, b: a >= b, "gt": lambda a, b: a > b}
        points = [dict(zip(["u", "y", "x"], values)) for values in product(range(-1, 2), range(3), range(-1, 3))]
        for relation, cutoff, constrained in product(compare, (-1, 0, 1), (False, True)):
            with self.subTest(relation=relation, cutoff=cutoff, constrained=constrained):
                data = request(predicate(expression, relation, literal(cutoff)))
                data["variables"] = ["u", "y", "x"]
                data["bounds"] = {"x": {"lower": -1, "upper": 2}, "y": {"lower": 0, "upper": 2}, "u": {"lower": -1, "upper": 1}}
                if constrained:
                    data["constraints"] = [predicate(variable("y"), "ge", literal(1)), predicate(variable("x"), "le", literal(1))]
                witness = None
                visited = eligible = 0
                for point in points:
                    visited += 1
                    allowed = not constrained or (point["y"] >= 1 and point["x"] <= 1)
                    eligible += int(allowed)
                    if allowed and not compare[relation](3 * point["x"] - 2 * point["y"], cutoff):
                        witness = point
                        break
                receipt = search_counterexample(data)
                self.assertEqual(receipt["status"], "success")
                self.assertEqual(receipt["domain"]["variables"], ["u", "y", "x"])
                self.assertEqual(receipt["progress"]["domain_cardinality"], 36)
                self.assertEqual(receipt["progress"]["visited_count"], visited)
                self.assertEqual(receipt["progress"]["eligible_count"], eligible)
                self.assertIs(receipt["progress"]["complete"], visited == 36)
                self.assertEqual(receipt["result"]["assignment"], witness)
                outcome = "counterexample_found" if witness is not None else "no_counterexample_in_declared_finite_domain"
                self.assertEqual(receipt["result"]["outcome"], outcome)
                for point in (points[0], points[-1]):
                    allowed = not constrained or (point["y"] >= 1 and point["x"] <= 1)
                    expected = allowed and not compare[relation](3 * point["x"] - 2 * point["y"], cutoff)
                    self.assertIs(check_witness(data, point)["result"]["valid"], expected)

    def test_final_point_witness_is_complete_but_not_exhaustion(self):
        data = request(predicate(variable("x"), "ne", literal(1)))
        receipt = search_counterexample(data)
        self.assertEqual(receipt["progress"]["visited_count"], 3)
        self.assertTrue(receipt["progress"]["complete"])
        self.assertEqual(receipt["result"]["outcome"], "counterexample_found")
        self.assertEqual(receipt["result"]["assignment"], {"x": 1})
        self.assertFalse(receipt["scope"]["universal_proof"])

    def test_singleton_empty_product_and_vacuity_are_distinct(self):
        data = request(predicate(literal(0), "gt", literal(0)))
        data.update(variables=[], bounds={})
        found = search_counterexample(data)
        self.assertEqual(found["domain"]["cardinality"], 1)
        self.assertEqual(found["result"]["assignment"], {})
        self.assertEqual(found["result"]["outcome"], "counterexample_found")
        data["constraints"] = [predicate(literal(0), "gt", literal(1))]
        vacuous = search_counterexample(data)
        self.assertEqual(vacuous["progress"]["visited_count"], 1)
        self.assertEqual(vacuous["progress"]["eligible_count"], 0)
        self.assertTrue(vacuous["progress"]["complete"])
        self.assertEqual(vacuous["result"]["outcome"], "no_counterexample_in_declared_finite_domain")
        self.assertFalse(check_witness(data, {})["result"]["valid"])

    def test_witness_rechecks_changed_constraints_and_bounds(self):
        original = request(predicate(variable("x"), "ge"))
        found = search_counterexample(original)
        self.assertEqual(found["result"]["assignment"], {"x": -1})
        candidate = found["result"]["assignment"]
        changed = copy.deepcopy(original)
        changed["constraints"] = [predicate(variable("x"), "ge")]
        constrained = check_witness(changed, candidate)
        self.assertEqual(constrained["result"]["reason"], "constraint_not_satisfied")
        self.assertNotEqual(constrained["artifacts"]["request_sha256"], found["artifacts"]["request_sha256"])
        changed = copy.deepcopy(original)
        changed["bounds"]["x"]["lower"] = 0
        bounded = check_witness(changed, candidate)
        self.assertEqual(bounded["result"]["reason"], "assignment_outside_declared_integer_bounds")
        self.assertNotEqual(bounded["artifacts"]["request_sha256"], found["artifacts"]["request_sha256"])

    def test_rehashed_forged_witness_is_not_accepted(self):
        data = request(predicate(variable("x"), "ge"))
        forged = search_counterexample(data)
        forged["result"]["assignment"] = {"x": 0}
        forged["result"]["evaluation"]["assertion_violated"] = True
        forged["scope"]["universal_proof"] = True
        rehash(forged)
        unsigned = copy.deepcopy(forged)
        unsigned["artifacts"].pop("evidence_sha256")
        self.assertEqual(forged["artifacts"]["evidence_sha256"], digest(unsigned))
        self.assertFalse(check_witness(data, forged)["result"]["valid"])
        checked = check_witness(data, forged["result"]["assignment"])
        self.assertFalse(checked["result"]["valid"])
        self.assertEqual(checked["result"]["reason"], "assertion_not_violated")
        self.assertFalse(checked["scope"]["universal_proof"])

    def test_work_budget_failure_is_not_successful_exhaustion(self):
        data = request(predicate(literal(0)), constraints=[predicate(literal(0)) for _ in range(16)])
        data["bounds"]["x"] = {"lower": 0, "upper": 9999}
        receipt = search_counterexample(data)
        self.assertEqual(receipt["status"], "error")
        self.assertEqual(receipt["error"]["code"], "resource_limit")
        self.assertIsNone(receipt["result"])
        self.assertFalse(receipt["progress"]["complete"])
        self.assertGreater(receipt["progress"]["visited_count"], 0)
        self.assertLess(receipt["progress"]["visited_count"], 10000)
        self.assertEqual(receipt["domain"]["cardinality"], 10000)
        self.assertEqual(receipt["usage"]["evaluation_steps"], 250000)

    def test_object_api_host_decimal_limit_returns_serializable_error(self):
        # Isolate the interpreter safety setting; the library must not change it.
        code = '''import json,sys
from bounded_counterexample import search_counterexample,check_witness
big={"type":"rational","numerator":(1<<250)-1,"denominator":1}
left=big
for _ in range(9): left={"type":"multiply","operands":[left,big]}
request={"domain":"finite_integer_box","coefficient_field":"Q","variables":[],"bounds":{},"constraints":[],"assertion":{"relation":"eq","left":left,"right":{"type":"rational","numerator":0,"denominator":1}}}
sys.set_int_max_str_digits(640)
receipts=[search_counterexample(request),check_witness(request,{})]
json.dumps(receipts,allow_nan=False)
print(json.dumps({"limit":sys.get_int_max_str_digits(),"optimized":not __debug__,"receipts":receipts}))
'''
        flags = ["-O"] if sys.flags.optimize else []
        run = subprocess.run([sys.executable, *flags, "-c", code], cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(run.returncode, 0, run.stderr)
        output = json.loads(run.stdout)
        self.assertEqual(output["limit"], 640)
        self.assertIs(output["optimized"], bool(sys.flags.optimize))
        for receipt in output["receipts"]:
            self.assertEqual(receipt["status"], "error")
            self.assertEqual(receipt["error"]["code"], "representation_limit")
            self.assertIsNone(receipt["result"])
            self.assertIsNone(receipt["artifacts"]["result_sha256"])
            self.assertFalse(receipt["progress"]["complete"])

    def test_untrusted_expression_text_never_starts_process(self):
        with patch("subprocess.run", side_effect=AssertionError("unexpected process")), \
             patch("os.system", side_effect=AssertionError("unexpected shell")):
            for payload in ("__import__('os').system('false')", {"type": "call", "name": "eval", "argument": "1+1"}):
                data = request(predicate(payload))
                receipt = search_counterexample(data)
                self.assertEqual(receipt["status"], "error")
                self.assertIsNone(receipt["result"])

    def test_finite_exhaustion_and_its_rehash_cannot_prove_polynomial_goal(self):
        x = variable("x")
        polynomial = binary("add", binary("multiply", x, x), binary("multiply", literal(-1), x))
        finite = request(predicate(polynomial))
        finite["bounds"]["x"] = {"lower": 0, "upper": 1}
        receipt = search_counterexample(finite)
        self.assertEqual(receipt["result"]["outcome"], "no_counterexample_in_declared_finite_domain")
        receipt["scope"]["universal_proof"] = True
        receipt["scope"]["formal_proof"] = True
        rehash(receipt)
        goal = {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": ["x"],
                "operation": "verify_identity", "operands": [polynomial, literal(0)]}
        data = {"schema_version": 1, "problem": {"id": "finite-not-global", "domain": "polynomial_ring", "assumptions": [],
                "goal": "Assert unrestricted polynomial equality.", "goal_request": goal, "required_evidence": "exact_computation"},
                "goal_task_id": "verify", "tasks": [
                    {"id": "propose", "role": "proposer", "dependencies": [], "payload": {"request": goal,
                        "expected": {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": ["x"], "equal": True},
                        "rationale": json.dumps(receipt)}},
                    {"id": "calculate", "role": "calculator", "dependencies": ["propose"]},
                    {"id": "verify", "role": "verifier", "dependencies": ["propose", "calculate"]}]}
        report = Runtime.from_dict(data).run()
        self.assertEqual(report["goal_status"], "not_verified")
        self.assertEqual(report["tasks"]["verify"]["status"], "rejected")
        self.assertEqual(report["proof_status"], "not_formally_verified")
        with self.assertRaises(DomainError):
            domain_handler("finite_integer_box")


if __name__ == "__main__":
    unittest.main()
