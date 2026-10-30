from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from bounded_counterexample import (check_witness, check_witness_json,
                                    search_counterexample, search_counterexample_json)
from bounded_counterexample import core
from bounded_counterexample._vendor.calculator import artifact_hash


def q(n, d=1):
    return {"type": "rational", "numerator": n, "denominator": d}


def v(name="x"):
    return {"type": "variable", "name": name}


def binary(op, a, b):
    return {"type": op, "operands": [a, b]}


def add(a, b):
    return binary("add", a, b)


def mul(a, b):
    return binary("multiply", a, b)


def predicate(left, relation="ge", right=None):
    return {"relation": relation, "left": left, "right": q(0) if right is None else right}


def request(assertion=None, bounds=None, constraints=None):
    return {"domain": "finite_integer_box", "coefficient_field": "Q", "variables": ["x"],
            "bounds": {"x": {"lower": -3, "upper": 3}} if bounds is None else bounds,
            "constraints": [] if constraints is None else constraints,
            "assertion": predicate(mul(v(), v())) if assertion is None else assertion}


class SearchTests(unittest.TestCase):
    def successful(self, result):
        self.assertEqual(result["status"], "success", result.get("error"))
        self.assertIsNone(result["error"])

    def test_true_bounded_inequality(self):
        result = search_counterexample(request())
        self.successful(result)
        self.assertEqual(result["result"]["outcome"], "no_counterexample_in_declared_finite_domain")
        self.assertEqual(result["progress"]["domain_cardinality"], 7)
        self.assertEqual(result["progress"]["visited_count"], 7)
        self.assertEqual(result["progress"]["eligible_count"], 7)
        self.assertIs(result["progress"]["complete"], True)
        self.assertIs(result["scope"]["universal_proof"], False)
        self.assertIs(result["scope"]["formal_proof"], False)

    def test_false_inequality_exact_witness(self):
        result = search_counterexample(request(predicate(v(), "ge", q(1, 2))))
        self.successful(result)
        self.assertEqual(result["result"]["outcome"], "counterexample_found")
        self.assertEqual(result["result"]["assignment"], {"x": -3})
        self.assertEqual(result["result"]["evaluation"]["assertion"]["left"], {"numerator": -3, "denominator": 1})
        self.assertEqual(result["result"]["evaluation"]["assertion"]["right"], {"numerator": 1, "denominator": 2})
        self.assertEqual(result["progress"]["visited_count"], 1)
        self.assertIs(result["progress"]["complete"], False)

    def test_all_six_relations(self):
        for relation, first, visits in (("lt", 0, 4), ("le", 1, 5), ("eq", -3, 1),
                                        ("ne", 0, 4), ("ge", -3, 1), ("gt", -3, 1)):
            with self.subTest(relation=relation):
                result = search_counterexample(request(predicate(v(), relation)))
                self.assertEqual(result["result"]["assignment"], {"x": first})
                self.assertEqual(result["progress"]["visited_count"], visits)

    def test_constraints_filter_false_assertions(self):
        req = request(predicate(v()), constraints=[predicate(v(), "ge", q(1))])
        result = search_counterexample(req)
        self.successful(result)
        self.assertEqual(result["result"]["outcome"], "no_counterexample_in_declared_finite_domain")
        self.assertEqual(result["progress"]["eligible_count"], 3)
        checked = check_witness(req, {"x": -2})
        self.assertIs(checked["result"]["valid"], False)
        self.assertEqual(checked["result"]["reason"], "constraint_not_satisfied")
        self.assertIsNone(checked["result"]["evaluation"]["assertion"])

    def test_all_constraints_are_evaluated(self):
        req = request(predicate(q(0), "gt"), constraints=[predicate(v(), "gt", q(9)), predicate(v(), "lt", q(-9))])
        result = check_witness(req, {"x": 0})
        self.assertEqual(len(result["result"]["evaluation"]["constraints"]), 2)
        self.assertIs(result["result"]["valid"], False)

    def test_unsatisfiable_constraints_report_vacuous_bounded_exhaustion(self):
        req = request(predicate(q(0), "gt"), constraints=[predicate(v(), "gt", q(10))])
        result = search_counterexample(req)
        self.successful(result)
        self.assertEqual(result["progress"]["eligible_count"], 0)
        self.assertEqual(result["progress"]["visited_count"], 7)
        self.assertIs(result["progress"]["complete"], True)

    def test_empty_variable_constant_case(self):
        for relation, outcome in (("eq", "no_counterexample_in_declared_finite_domain"), ("gt", "counterexample_found")):
            req = {"domain": "finite_integer_box", "coefficient_field": "Q", "variables": [],
                   "bounds": {}, "constraints": [], "assertion": predicate(q(0), relation)}
            result = search_counterexample(req)
            self.successful(result)
            self.assertEqual(result["progress"]["domain_cardinality"], 1)
            self.assertEqual(result["progress"]["visited_count"], 1)
            self.assertIs(result["progress"]["complete"], True)
            self.assertEqual(result["result"]["outcome"], outcome)
            checked = check_witness(req, {})
            self.assertEqual(checked["result"]["valid"], relation == "gt")

    def test_singleton_and_last_witness_complete(self):
        req = request(predicate(v(), "ne", q(3)))
        result = search_counterexample(req)
        self.assertEqual(result["result"]["assignment"], {"x": 3})
        self.assertIs(result["progress"]["complete"], True)
        req["bounds"]["x"] = {"lower": 0, "upper": 0}
        result = search_counterexample(req)
        self.assertEqual(result["progress"]["domain_cardinality"], 1)

    def test_declared_order_is_preserved(self):
        req = {"domain": "finite_integer_box", "coefficient_field": "Q", "variables": ["z", "a"],
               "bounds": {"a": {"lower": 0, "upper": 1}, "z": {"lower": 2, "upper": 3}},
               "constraints": [], "assertion": predicate(add(v("z"), v("a")), "eq", q(2))}
        result = search_counterexample(req)
        self.assertEqual(result["result"]["assignment"], {"z": 2, "a": 1})
        self.assertEqual(result["progress"]["domain_cardinality"], 4)
        self.assertEqual(result["progress"]["visited_count"], 2)

    def test_negative_denominator_and_canonical_values(self):
        req = request(predicate(add(q(-2, -4), v()), "lt", q(0)))
        req["bounds"]["x"] = {"lower": 0, "upper": 0}
        result = search_counterexample(req)
        self.assertEqual(result["request"]["assertion"]["left"]["operands"][0], q(1, 2))
        self.assertEqual(result["input"]["assertion"]["left"]["operands"][0], q(-2, -4))
        self.assertEqual(result["result"]["evaluation"]["assertion"]["left"], {"numerator": 1, "denominator": 2})

    def test_no_input_mutation(self):
        req = request()
        before = deepcopy(req)
        search_counterexample(req)
        check_witness(req, {"x": 0})
        self.assertEqual(req, before)


class WitnessTests(unittest.TestCase):
    def test_search_witness_rechecked_from_original(self):
        req = request(predicate(v(), "gt"))
        found = search_counterexample(req)
        checked = check_witness(req, found["result"]["assignment"])
        self.assertEqual(checked["status"], "success")
        self.assertIs(checked["result"]["valid"], True)
        self.assertEqual(checked["progress"]["checked_assignment_count"], 1)
        self.assertEqual(checked["progress"]["visited_count"], 0)
        self.assertIs(checked["progress"]["complete"], False)

    def test_checker_rejects_forged_producer_verdict(self):
        req = request()
        fake = {"outcome": "counterexample_found", "assignment": {"x": 0}, "valid": True}
        self.assertIs(check_witness(req, fake)["result"]["valid"], False)
        self.assertIs(check_witness(req, fake["assignment"])["result"]["valid"], False)

    def test_different_original_request_changes_witness_validity(self):
        req = request(predicate(v(), "gt"))
        self.assertIs(check_witness(req, {"x": 0})["result"]["valid"], True)
        req["assertion"]["relation"] = "ge"
        self.assertIs(check_witness(req, {"x": 0})["result"]["valid"], False)

    def test_integer_domain_pitfall(self):
        req = request(predicate(add(mul(v(), v()), mul(q(-1), v()))))
        result = search_counterexample(req)
        self.assertEqual(result["result"]["outcome"], "no_counterexample_in_declared_finite_domain")
        checked = check_witness(req, {"x": {"numerator": 1, "denominator": 2}})
        self.assertIs(checked["result"]["valid"], False)
        self.assertEqual(checked["result"]["reason"], "assignment_values_must_be_json_integers")
        self.assertEqual(Fraction(1, 2) ** 2 - Fraction(1, 2), Fraction(-1, 4))

    def test_assignment_shape_and_noninteger_controls(self):
        class Integer(int):
            pass
        for assignment in ({}, {"x": 0, "y": 1}, {"X": 0}, [0], {"x": True}, {"x": 0.0},
                           {"x": "0"}, {"x": Integer(0)}, {"x": Fraction(0)}, {"x": 1 << 256}):
            with self.subTest(assignment=assignment):
                result = check_witness(request(predicate(q(0), "gt")), assignment)
                self.assertEqual(result["status"], "success")
                self.assertIs(result["result"]["valid"], False)
                self.assertEqual(result["usage"]["evaluation_steps"], 0)

    def test_outside_bounds_is_not_witness(self):
        result = check_witness(request(predicate(v(), "lt", q(5))), {"x": 9})
        self.assertIs(result["result"]["valid"], False)
        self.assertEqual(result["result"]["reason"], "assignment_outside_declared_integer_bounds")
        self.assertEqual(result["supplied_assignment"], {"x": 9})

    def test_boundary_values_are_included(self):
        req = request(predicate(q(0), "gt"))
        for x in (-3, 3):
            self.assertIs(check_witness(req, {"x": x})["result"]["valid"], True)


class InvalidInputTests(unittest.TestCase):
    def error(self, req, code=None):
        for result in (search_counterexample(req), check_witness(req, {"x": 0})):
            self.assertEqual(result["status"], "error")
            self.assertIsNone(result["result"])
            self.assertIsNone(result["artifacts"]["result_sha256"])
            self.assertIs(result["progress"]["complete"], False)
            if code:
                self.assertEqual(result["error"]["code"], code)

    def test_exact_top_fields(self):
        for key in request():
            req = request()
            del req[key]
            self.error(req, "invalid_input")
        req = request()
        req["universal"] = True
        self.error(req, "invalid_input")

    def test_invalid_domain_and_field(self):
        for domain in ("Q", "R", "polynomial_ring", {}, None):
            req = request()
            req["domain"] = domain
            self.error(req, "invalid_domain")
        req = request()
        req["coefficient_field"] = "R"
        self.error(req, "unsupported_field")

    def test_variable_declarations(self):
        for variables, code in ((["x", "x"], "duplicate_variable"), (["х"], "invalid_variable"),
                                (["x "], "invalid_variable"), ([1], "invalid_variable"),
                                (["x" * 33], "invalid_variable"), (["x"] * 9, "invalid_input")):
            req = request()
            req["variables"] = variables
            self.error(req, code)

    def test_strict_bounds_binding(self):
        for bounds in ({}, {"X": {"lower": 0, "upper": 2}}, {"x": {"lower": 0, "upper": 2}, "y": {}},
                       {"x": {"lower": 0, "upper": 2, "step": 1}}):
            req = request(bounds=bounds)
            self.error(req, "invalid_input")
        self.error(request(bounds={"x": {"lower": 1, "upper": 0}}), "invalid_bounds")

    def test_noninteger_bounds(self):
        for value in (True, 0.0, "0", {"numerator": 0, "denominator": 1}):
            self.error(request(bounds={"x": {"lower": value, "upper": 2}}), "invalid_input")
        self.error(request(bounds={"x": {"lower": 0, "upper": 1 << 256}}), "resource_limit")

    def test_unsupported_expressions_and_relations(self):
        for expr in ("x*x", {"type": "power", "base": v(), "exponent": 2},
                     {"type": "call", "name": "open"}, {"type": "divide", "operands": [v(), v()]}):
            self.error(request(predicate(expr)))
        self.error(request(predicate(v("y"))), "unknown_variable")
        self.error(request(predicate(v(), "=>")), "unsupported_relation")
        req = request()
        req["assertion"]["source"] = "trust me"
        self.error(req, "invalid_input")

    def test_rational_literal_guards(self):
        for value in (True, 1.2, "1"):
            self.error(request(predicate(q(value))), "invalid_input")
        self.error(request(predicate(q(1, 0))), "division_by_zero")
        self.error(request(predicate(q(1 << 256))), "resource_limit")

    def test_expression_arity(self):
        for values in ([], [q(0)], [q(0)] * 3, (q(0), q(0))):
            self.error(request(predicate({"type": "add", "operands": values})), "invalid_input")

    def test_constraints_shape(self):
        self.error(request(constraints={}), "invalid_input")
        self.error(request(constraints=[predicate(q(0))] * 17), "invalid_input")

    def test_subclasses_and_cyclic_ast(self):
        class Mapping(dict):
            pass
        self.error(Mapping(request()), "invalid_input")
        cycle = {"type": "add", "operands": []}
        cycle["operands"] = [cycle, q(0)]
        self.error(request(predicate(cycle)), "resource_limit")


class ResourceTests(unittest.TestCase):
    def test_full_cardinality_not_truncated(self):
        req = request(bounds={"x": {"lower": 0, "upper": 10000}})
        result = search_counterexample(req)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "resource_limit")
        self.assertIsNone(result["result"])
        self.assertEqual(result["progress"]["domain_cardinality"], 10001)
        self.assertEqual(result["progress"]["visited_count"], 0)

    def test_product_cardinality(self):
        req = request()
        req["variables"] = ["x", "y"]
        req["bounds"] = {"x": {"lower": -9, "upper": 10}, "y": {"lower": -4, "upper": 5}}
        result = search_counterexample(req)
        self.assertEqual(result["progress"]["domain_cardinality"], 200)
        self.assertEqual(result["progress"]["visited_count"], 200)

    def test_depth_limit(self):
        expr = q(0)
        for _ in range(32):
            expr = add(expr, q(0))
        result = search_counterexample(request(predicate(expr)))
        self.assertEqual(result["error"]["code"], "resource_limit")

    def test_degree_limit_even_if_later_cancelled(self):
        expr = v()
        for _ in range(6):
            expr = mul(expr, expr)
        result = search_counterexample(request(predicate(mul(q(0), expr))))
        self.assertEqual(result["error"]["code"], "resource_limit")

    def test_total_nodes_across_predicates(self):
        expr = q(0)
        for _ in range(5):
            expr = add(expr, expr)
        req = request(predicate(expr), constraints=[predicate(expr)] * 16)
        result = search_counterexample(req)
        self.assertEqual(result["error"]["code"], "resource_limit")

    def test_intermediate_value_bound(self):
        expr = q(1 << 255)
        for _ in range(5):
            expr = mul(expr, expr)
        result = search_counterexample(request(predicate(expr)))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "resource_limit")
        self.assertEqual(result["progress"]["visited_count"], 0)
        self.assertIsNone(result["result"])

    def test_work_budget_error_never_exhaustion(self):
        req = request(bounds={"x": {"lower": 0, "upper": 9999}}, constraints=[predicate(q(0))] * 16)
        result = search_counterexample(req)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["code"], "resource_limit")
        self.assertIsNone(result["result"])
        self.assertIs(result["progress"]["complete"], False)
        self.assertEqual(result["progress"]["domain_cardinality"], 10000)
        self.assertGreater(result["progress"]["visited_count"], 0)
        self.assertLess(result["progress"]["visited_count"], 10000)
        self.assertEqual(result["usage"]["evaluation_steps"], core.MAX_EVALUATION_STEPS)

    def test_checker_resource_error_never_valid_false_success(self):
        with patch.object(core, "MAX_EVALUATION_STEPS", 1):
            result = check_witness(request(), {"x": 0})
        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["result"])


class JsonAndEvidenceTests(unittest.TestCase):
    def test_json_round_trip(self):
        req = request(predicate(v(), "gt"))
        self.assertEqual(search_counterexample(req), search_counterexample_json(json.dumps(req)))
        self.assertEqual(check_witness(req, {"x": 0}), check_witness_json(json.dumps(req), '{"x":0}'))

    def test_strict_json_controls(self):
        for data in ('{"x":0,"x":1}', '{"x":NaN}', '{"x":Infinity}', '{"x":' + '9' * 79 + '}',
                     '[]', b'\xff', '{', ' ' * (core.MAX_INPUT_BYTES + 1), None, '"\ud800"'):
            with self.subTest(data=str(data)[:80]):
                result = search_counterexample_json(data)
                self.assertEqual(result["status"], "error")
                self.assertIsNone(result["result"])
                self.assertIs(result["progress"]["complete"], False)
        result = check_witness_json(json.dumps(request()), '{"x":0,"x":1}')
        self.assertEqual(result["status"], "error")

    def test_hashes_recompute_and_bind_domain(self):
        result = search_counterexample(request())
        artifacts = result["artifacts"]
        self.assertEqual(artifacts["input_sha256"], artifact_hash(result["input"]))
        self.assertEqual(artifacts["request_sha256"], artifact_hash(result["request"]))
        self.assertEqual(artifacts["result_sha256"], artifact_hash(result["result"]))
        evidence = deepcopy(result)
        del evidence["artifacts"]["evidence_sha256"]
        self.assertEqual(artifacts["evidence_sha256"], artifact_hash(evidence))
        modified = request(bounds={"x": {"lower": -2, "upper": 2}})
        different = search_counterexample(modified)
        self.assertEqual(result["result"], different["result"])
        self.assertNotEqual(artifacts["evidence_sha256"], different["artifacts"]["evidence_sha256"])
        self.assertNotEqual(artifacts["request_sha256"], different["artifacts"]["request_sha256"])

    def test_hashes_do_not_authenticate_tampered_evidence(self):
        result = search_counterexample(request())
        original = result["artifacts"]["evidence_sha256"]
        result["progress"]["visited_count"] = 0
        evidence = deepcopy(result)
        del evidence["artifacts"]["evidence_sha256"]
        self.assertNotEqual(original, artifact_hash(evidence))
        # A forger can recompute hashes. Only replay, not hashes alone, checks math.
        result["artifacts"]["evidence_sha256"] = artifact_hash(evidence)
        self.assertNotEqual(result, search_counterexample(request()))

    def test_original_and_normalized_hashes_distinct(self):
        req = request(predicate(q(2, 4)))
        result = search_counterexample(req)
        self.assertNotEqual(result["artifacts"]["input_sha256"], result["artifacts"]["request_sha256"])

    def test_source_hashes(self):
        result = search_counterexample(request())
        root = Path(core.__file__).parent
        for key, file in (("backend_source_sha256", root / "core.py"),
                          ("parser_source_sha256", root / "_vendor/polynomial.py"),
                          ("canonical_json_source_sha256", root / "_vendor/calculator.py")):
            self.assertEqual(result["artifacts"][key], sha256(file.read_bytes()).hexdigest())


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "bounded_counterexample", *args],
                              cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, check=False)

    def test_search_and_checker_exit_codes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "request.json"
            assignment = Path(folder) / "assignment.json"
            path.write_text(json.dumps(request()), encoding="utf-8")
            assignment.write_text('{"x":0}', encoding="utf-8")
            self.assertEqual(self.run_cli("search", str(path)).returncode, 0)
            self.assertEqual(self.run_cli("check-witness", str(path), str(assignment)).returncode, 1)
            path.write_text(json.dumps(request(predicate(q(0), "gt"))), encoding="utf-8")
            self.assertEqual(self.run_cli("search", str(path)).returncode, 1)
            self.assertEqual(self.run_cli("check-witness", str(path), str(assignment)).returncode, 0)
            path.write_text('{}', encoding="utf-8")
            self.assertEqual(self.run_cli("search", str(path)).returncode, 2)

    def test_cli_no_overwrite_and_missing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "request.json"
            output = Path(folder) / "receipt.json"
            path.write_text(json.dumps(request()), encoding="utf-8")
            result = self.run_cli("search", str(path), "--output", str(output))
            self.assertEqual(result.returncode, 0)
            original = output.read_bytes()
            result = self.run_cli("search", str(path), "--output", str(output))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(output.read_bytes(), original)
            self.assertEqual(self.run_cli("search", str(path) + ".missing").returncode, 2)


if __name__ == "__main__":
    unittest.main()
