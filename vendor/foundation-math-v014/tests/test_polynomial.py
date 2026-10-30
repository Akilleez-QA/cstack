"""Independent integer oracle, bounded exhaustive cases, and ingress failures."""
from copy import deepcopy
from fractions import Fraction
import itertools
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from foundation_math.calculator import artifact_hash
from foundation_math import polynomial as p


def rational(n, d=1):
    return {"type": "rational", "numerator": n, "denominator": d}


def variable(name):
    return {"type": "variable", "name": name}


def add(a, b):
    return {"type": "add", "operands": [a, b]}


def multiply(a, b):
    return {"type": "multiply", "operands": [a, b]}


def request(a, b, operation="verify_identity", variables=None):
    return {"domain": "polynomial_ring", "coefficient_field": "Q", "variables": ["x", "y"] if variables is None else variables,
            "operation": operation, "operands": [a, b]}


def balanced(kind, expressions):
    values = list(expressions)
    if not values:
        return rational(0 if kind == "add" else 1)
    while len(values) > 1:
        values = [{"type": kind, "operands": values[i:i + 2]} if i + 1 < len(values) else values[i]
                  for i in range(0, len(values), 2)]
    return values[0]


def polynomial_ast(coefficients, variables):
    """Test-only AST constructor, independent of the production normalizer."""
    terms = []
    for exponent, coefficient in coefficients.items():
        factors = [rational(coefficient)]
        for name, count in zip(variables, exponent):
            factors.extend(variable(name) for _ in range(count))
        terms.append(balanced("multiply", factors))
    return balanced("add", terms)


def integer_oracle(a, b, operation):
    """Integer tuple-key convolution with no production code or Fraction use."""
    if operation == "add":
        keys = set(a) | set(b)
        result = {key: a.get(key, 0) + b.get(key, 0) for key in keys}
    else:
        result = {}
        for a_key, a_value in a.items():
            for b_key, b_value in b.items():
                exponent = tuple(a_key[i] + b_key[i] for i in range(len(a_key)))
                if exponent not in result:
                    result[exponent] = 0
                result[exponent] += a_value * b_value
    return {key: value for key, value in result.items() if value != 0}


def decoded(encoded):
    return {tuple(term["exponents"]): Fraction(term["coefficient"]["numerator"], term["coefficient"]["denominator"])
            for term in encoded["terms"]}


class PolynomialTests(unittest.TestCase):
    def setUp(self):
        self.x, self.y = variable("x"), variable("y")

    def success(self, payload):
        receipt = p.calculate_polynomial(payload)
        self.assertEqual(receipt["status"], "success", receipt["error"])
        self.assertIsNone(receipt["error"])
        return receipt

    def error(self, payload, code=None):
        receipt = p.calculate_polynomial(payload)
        self.assertEqual(receipt["status"], "error", receipt)
        self.assertIsNone(receipt["result"])
        self.assertIsNone(receipt["artifacts"]["result_sha256"])
        if code is not None:
            self.assertEqual(receipt["error"]["code"], code)
        return receipt

    def test_distributivity_is_a_formal_identity(self):
        left = multiply(add(self.x, rational(1, 2)), add(self.y, rational(2, 3)))
        right = add(add(multiply(self.x, self.y), multiply(rational(2, 3), self.x)),
                    add(multiply(rational(1, 2), self.y), rational(1, 3)))
        receipt = self.success(request(left, right))
        self.assertTrue(receipt["result"]["equal"])
        self.assertEqual(receipt["result"]["difference"], {"terms": [], "total_degree": None})
        self.assertIsNone(receipt["result"]["mismatch_witness"])
        self.assertEqual(decoded(receipt["result"]["left"]), {(1, 1): 1, (1, 0): Fraction(2, 3), (0, 1): Fraction(1, 2), (0, 0): Fraction(1, 3)})
        self.assertFalse(receipt["scope"]["formal_proof"])

    def test_false_identity_has_nonzero_coefficient_witness(self):
        left = multiply(add(self.x, self.y), add(self.x, self.y))
        right = add(multiply(self.x, self.x), multiply(self.y, self.y))
        receipt = self.success(request(left, right))
        self.assertFalse(receipt["result"]["equal"])
        witness = receipt["result"]["mismatch_witness"]
        self.assertEqual(witness["exponents"], [1, 1])
        self.assertEqual(witness["coefficient"], {"numerator": 2, "denominator": 1})
        self.assertEqual(witness["left_coefficient"], {"numerator": 2, "denominator": 1})
        self.assertEqual(witness["right_coefficient"], {"numerator": 0, "denominator": 1})

    def test_zero_one_and_negative_coefficients(self):
        cases = [(multiply(self.x, rational(0)), rational(0)),
                 (multiply(self.x, rational(1)), self.x),
                 (add(self.x, multiply(rational(-1), self.x)), rational(0))]
        for a, b in cases:
            self.assertTrue(self.success(request(a, b))["result"]["equal"])

    def test_rationals_are_reduced_and_negative_denominator_normalized(self):
        payload = request(rational(2, -4), rational(-1, 2), variables=[])
        receipt = self.success(payload)
        self.assertTrue(receipt["result"]["equal"])
        self.assertEqual(receipt["request"]["operands"][0], rational(-1, 2))
        self.assertNotEqual(receipt["artifacts"]["input_sha256"], receipt["artifacts"]["request_sha256"])
        self.assertEqual(receipt["input"], payload)

    def test_empty_variable_list_is_q(self):
        receipt = self.success(request(rational(1, 2), rational(1, 3), "add", []))
        self.assertEqual(decoded(receipt["result"]["polynomial"]), {(): Fraction(5, 6)})
        self.assertEqual(receipt["ring"]["variables"], [])

    def test_ordered_variables_define_monomial_coordinates(self):
        receipt = self.success(request(self.x, self.y, "multiply", ["y", "x"]))
        self.assertEqual(receipt["ring"]["variables"], ["y", "x"])
        self.assertEqual(decoded(receipt["result"]["left"]), {(0, 1): 1})
        self.assertEqual(decoded(receipt["result"]["right"]), {(1, 0): 1})

    def test_names_are_case_sensitive_not_aliases(self):
        receipt = self.success(request(variable("x"), variable("X"), variables=["x", "X"]))
        self.assertFalse(receipt["result"]["equal"])

    def test_terms_are_nonzero_unique_and_lexicographically_sorted(self):
        expression = add(add(self.y, self.x), add(self.x, rational(0)))
        receipt = self.success(request(expression, rational(0), "add"))
        self.assertEqual(receipt["result"]["polynomial"]["terms"], [
            {"exponents": [0, 1], "coefficient": {"numerator": 1, "denominator": 1}},
            {"exponents": [1, 0], "coefficient": {"numerator": 2, "denominator": 1}}])

    def test_independent_integer_convolution_randomized(self):
        generator = random.Random(20261024)
        keys = list(itertools.product(range(3), repeat=2))
        for _ in range(80):
            a = {key: generator.randint(-3, 3) for key in generator.sample(keys, 5)}
            b = {key: generator.randint(-3, 3) for key in generator.sample(keys, 5)}
            for operation in ("add", "multiply"):
                payload = request(polynomial_ast(a, ["x", "y"]), polynomial_ast(b, ["x", "y"]), operation)
                result = self.success(payload)["result"]["polynomial"]
                self.assertEqual(decoded(result), integer_oracle(a, b, operation))

    def test_independent_exhaustive_small_univariate_oracle(self):
        polynomials = [{(0,): a, (1,): b} for a, b in itertools.product((-1, 0, 1), repeat=2)]
        for a, b in itertools.product(polynomials, repeat=2):
            for operation in ("add", "multiply"):
                result = self.success(request(polynomial_ast(a, ["x"]), polynomial_ast(b, ["x"]), operation, ["x"]))
                self.assertEqual(decoded(result["result"]["polynomial"]), integer_oracle(a, b, operation))

    def test_distributivity_family_checked_symbolically(self):
        for a, b, c in itertools.product((-2, 0, 3), repeat=3):
            factor = add(multiply(rational(a), self.x), rational(b))
            summand = add(self.y, rational(c))
            left = multiply(factor, summand)
            right = add(multiply(factor, self.y), multiply(factor, rational(c)))
            self.assertTrue(self.success(request(left, right))["result"]["equal"])

    def test_finite_sample_agreement_is_not_identity(self):
        # x(x-1) vanishes at 0 and 1, but this backend checks coefficients.
        result = self.success(request(multiply(self.x, add(self.x, rational(-1))), rational(0)))["result"]
        self.assertFalse(result["equal"])
        self.assertEqual(result["mismatch_witness"]["exponents"], [1, 0])

    def test_no_quotient_ring_assumption(self):
        result = self.success(request(multiply(self.x, self.x), self.x))["result"]
        self.assertFalse(result["equal"])
        payload = request(self.x, self.x)
        payload["relations"] = ["x*x=x"]
        self.error(payload, "invalid_input")

    def test_x_over_x_is_rejected_even_though_rational_functions_exist(self):
        self.error(request({"type": "divide", "operands": [self.x, self.x]}, rational(1)), "unsupported_expression")

    def test_unsupported_powers_calls_and_source_strings(self):
        for bad in ({"type": "power", "base": self.x, "exponent": -1},
                    {"type": "call", "name": "exec", "arguments": []}, "x/x", "__import__('os').system('touch sentinel')"):
            self.error(request(bad, rational(0)))

    def test_unsupported_coefficient_fields_are_rejected(self):
        for field in ("R", "C", "F_2", "Z", 2, True, {}, None):
            payload = request(self.x, self.x)
            payload["coefficient_field"] = field
            self.error(payload, "unsupported_field")

    def test_wrong_domain_and_operation(self):
        for key, value, code in (("domain", "Q", "invalid_domain"), ("domain", [], "invalid_domain"),
                                 ("operation", "divide", "unsupported_operation"), ("operation", {}, "unsupported_operation")):
            payload = request(self.x, self.x)
            payload[key] = value
            self.error(payload, code)

    def test_alias_and_duplicate_variables_rejected(self):
        self.error(request(self.x, self.x, variables=["x", "x"]), "duplicate_variable")
        for names in (["x", " x"], ["x", "χ"], ["x", "x\u200b"], ["x", "1x"], ["x", {"alias": "x"}]):
            self.error(request(self.x, self.x, variables=names), "invalid_variable")
        self.error(request(variable("X"), self.x), "unknown_variable")
        payload = request(self.x, self.x)
        payload["aliases"] = {"X": "x"}
        self.error(payload, "invalid_input")

    def test_undeclared_variable_is_rejected_even_if_cancelled(self):
        unknown = variable("z")
        self.error(request(add(unknown, multiply(rational(-1), unknown)), rational(0)), "unknown_variable")

    def test_literals_reject_bool_float_string_zero_denominator(self):
        for value in (True, False, 0.5, "1", None, {}, []):
            self.error(request(rational(value), rational(0)), "invalid_input")
            self.error(request(rational(1, value), rational(0)), "invalid_input")
        self.error(request(rational(1, 0), rational(0)), "division_by_zero")

    def test_exact_object_fields_and_arity_enforced(self):
        bads = [None, [], {}, {**self.x, "unused": "x"}, {"type": "variable"},
                {"type": "add", "operands": []}, {"type": "add", "operands": [self.x]},
                {"type": "add", "operands": [self.x, self.x, self.x]},
                {"type": "add", "operands": (self.x, self.x)},
                {"type": [], "operands": []}, {1: "value", "type": "variable", "name": "x"}]
        for bad in bads:
            self.error(request(bad, self.x))
        for bad in (None, [], {}, True, {**request(self.x, self.x), "extra": 0}):
            self.error(bad, "invalid_input")

    def test_coefficient_input_bit_limit(self):
        self.error(request(rational(1 << p.MAX_INPUT_BITS), rational(0)), "resource_limit")
        self.success(request(rational((1 << p.MAX_INPUT_BITS) - 1), rational(0)))

    def test_degree_limit_and_its_boundary(self):
        boundary = balanced("multiply", [self.x] * p.MAX_DEGREE)
        receipt = self.success(request(boundary, rational(0), "add"))
        self.assertEqual(receipt["result"]["polynomial"]["total_degree"], p.MAX_DEGREE)
        self.error(request(multiply(boundary, self.x), rational(0)), "resource_limit")

    def test_terms_limit(self):
        names = list("abcdef")
        factors = [add(rational(1), add(variable(name), multiply(variable(name), variable(name)))) for name in names]
        self.error(request(balanced("multiply", factors), rational(0), variables=names), "resource_limit")

    def test_coefficient_intermediate_limit(self):
        huge = rational((1 << p.MAX_INPUT_BITS) - 1)
        self.error(request(balanced("multiply", [huge] * 9), rational(0)), "resource_limit")

    def test_depth_limit_including_cyclic_python_objects(self):
        expression = self.x
        for _ in range(p.MAX_EXPR_DEPTH):
            expression = add(expression, rational(0))
        self.error(request(expression, self.x), "resource_limit")
        cyclic = {"type": "add", "operands": [self.x]}
        cyclic["operands"].append(cyclic)
        self.error(request(cyclic, self.x), "resource_limit")

    def test_combined_ast_node_budget(self):
        expression = balanced("add", [rational(0)] * 300)
        self.error(request(expression, expression), "resource_limit")

    def test_input_size_budget_before_arithmetic(self):
        with patch.object(p, "MAX_INPUT_BYTES", 20):
            self.error(request(self.x, self.x), "resource_limit")

    def test_cumulative_arithmetic_budget(self):
        with patch.object(p, "MAX_ARITHMETIC_STEPS", 1):
            self.error(request(self.x, self.x, "multiply"), "resource_limit")

    def test_variable_count_limit(self):
        self.error(request(self.x, self.x, variables=["x"] + [f"v{i}" for i in range(p.MAX_VARIABLES)]), "invalid_input")

    def test_hashes_and_detached_receipt(self):
        payload = request(add(self.x, rational(1)), self.y, "multiply")
        saved = deepcopy(payload)
        receipt = self.success(payload)
        for field in ("input", "request", "result"):
            self.assertEqual(receipt["artifacts"][f"{field}_sha256"], artifact_hash(receipt[field]))
        for field in ("backend_source_sha256", "canonical_json_source_sha256"):
            self.assertRegex(receipt["artifacts"][field], r"^[0-9a-f]{64}$")
        payload["variables"][0] = "changed"
        payload["operands"][0]["operands"][1]["numerator"] = 100
        self.assertEqual(receipt["input"], saved)
        self.assertEqual(receipt["ring"]["variables"], ["x", "y"])
        replay = self.success(receipt["request"])
        self.assertEqual(replay["result"], receipt["result"])
        self.assertEqual(replay["artifacts"]["request_sha256"], receipt["artifacts"]["request_sha256"])

    def test_semantically_equivalent_expression_results_share_hash(self):
        a = self.success(request(add(self.x, self.y), rational(0), "add"))
        b = self.success(request(add(self.y, self.x), rational(0), "add"))
        self.assertEqual(a["artifacts"]["result_sha256"], b["artifacts"]["result_sha256"])
        self.assertNotEqual(a["artifacts"]["request_sha256"], b["artifacts"]["request_sha256"])

    def test_duplicate_json_keys_are_not_silently_overwritten(self):
        raw = json.dumps(request(self.x, self.x)).replace('"name": "x"', '"name": "x", "name": "y"', 1)
        receipt = p.calculate_polynomial_json(raw)
        self.assertEqual(receipt["status"], "error")
        self.assertEqual(receipt["error"]["code"], "invalid_json")

    def test_json_ingress_invalid_values_and_limits(self):
        for data in (b"\xff", "{", "[" * 1200 + "]" * 1200, "NaN", "Infinity", "-Infinity", None, 42):
            self.assertEqual(p.calculate_polynomial_json(data)["status"], "error")
        self.assertEqual(p.calculate_polynomial_json(" " * (p.MAX_INPUT_BYTES + 1))["error"]["code"], "resource_limit")
        self.assertEqual(p.calculate_polynomial_json("9" * 1000)["error"]["code"], "resource_limit")

    def test_json_ingress_matches_typed_api(self):
        payload = request(self.x, self.y, "multiply")
        self.assertEqual(p.calculate_polynomial_json(json.dumps(payload)), p.calculate_polynomial(payload))
        self.assertEqual(p.calculate_polynomial_json(json.dumps(payload).encode()), p.calculate_polynomial(payload))

    def test_euler_sequence_composite_is_zero_not_a_rank_theorem(self):
        composition = add(multiply(self.x, multiply(rational(-1), self.y)), multiply(self.y, self.x))
        result = self.success(request(composition, rational(0)))
        self.assertTrue(result["result"]["equal"])
        self.assertFalse(result["scope"]["formal_proof"])
        self.assertNotIn("bundle_exactness", result)
        self.assertNotIn("lift_rank", result)

    def test_cli_true_false_and_invalid_exit_codes(self):
        root = Path(__file__).resolve().parents[1]
        for payload, exit_code in ((request(self.x, self.x), 0), (request(self.x, self.y), 1),
                                   (request({"type": "divide", "operands": [self.x, self.x]}, rational(1)), 2)):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "input.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                completed = subprocess.run([sys.executable, "-m", "foundation_math", "polynomial", str(path)],
                                           cwd=root, capture_output=True, text=True, check=False, timeout=20)
                self.assertEqual(completed.returncode, exit_code, completed.stderr)
                self.assertIn("status", json.loads(completed.stdout))

    def test_cli_output_is_exclusive_and_oversize_input_is_bounded(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            path, output = Path(directory) / "input.json", Path(directory) / "receipt.json"
            path.write_text(json.dumps(request(self.x, self.x)), encoding="utf-8")
            command = [sys.executable, "-m", "foundation_math", "polynomial", str(path), "--output", str(output)]
            first = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False, timeout=20)
            self.assertEqual(first.returncode, 0)
            contents = output.read_bytes()
            second = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False, timeout=20)
            self.assertEqual(second.returncode, 2)
            self.assertEqual(output.read_bytes(), contents)
            path.write_bytes(b" " * (p.MAX_INPUT_BYTES + 1000))
            third = subprocess.run(command[:-2], cwd=root, capture_output=True, text=True, check=False, timeout=20)
            self.assertEqual(third.returncode, 2)
            self.assertEqual(json.loads(third.stdout)["error"]["code"], "resource_limit")


if __name__ == "__main__":
    unittest.main()
