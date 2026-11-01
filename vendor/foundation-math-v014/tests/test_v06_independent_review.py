"""Independent integration review using only tiny original synthetic matrices.

These regressions check wrapper/transport boundaries, not a formal proof kernel.
No research data, external packages, network, credentials, or frozen-tree edits.
"""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from exact_linalg.contract import Limits
from foundation_math.linear_algebra import (
    MAX_INPUT_BYTES, calculate_matrix, calculate_matrix_json,
    certify_matrix, check_matrix_certificate,
)
from foundation_math_bridge import server


ROOT = Path(__file__).resolve().parents[1]
MATRIX = {"domain": "Z", "rows": 2, "cols": 3,
          "entries": [[0, 2, 1], [0, 4, 2]]}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def frame(method, params=None, identifier=1):
    request = {"jsonrpc": "2.0", "id": identifier, "method": method}
    if params is not None:
        request["params"] = params
    return canonical(request)


class IndependentV06IntegrationReview(unittest.TestCase):
    def setUp(self):
        self.bridge = server.Bridge()
        initialized = self.bridge.handle(frame("initialize", {"protocolVersion": server.PROTOCOL}))
        self.assertIs(initialized["result"]["mcpCompatible"], False)

    def call(self, name, arguments):
        return self.bridge.handle(frame("tools/call", {"name": name, "arguments": arguments}))

    def no_acceptance(self, receipt, code=None):
        self.assertEqual(receipt["status"], "error")
        self.assertEqual(receipt["scope"], "one_explicit_matrix")
        self.assertEqual(receipt["computational_field"], "Q")
        self.assertIs(receipt["formal_proof"], False)
        self.assertIs(receipt["runtime_goal_acceptance"], False)
        self.assertNotIn("accepted", receipt)
        self.assertNotIn("result", receipt)
        self.assertNotIn("certificate", receipt)
        self.assertNotIn("request_sha256", receipt)
        self.assertLess(len(canonical(receipt)), 512)
        if code is not None:
            self.assertEqual(receipt["error"]["code"], code)

    def cli(self, *arguments):
        command = [sys.executable, "-B"] + (["-O"] if sys.flags.optimize else [])
        return subprocess.run(command + ["-m", "foundation_math", *map(str, arguments)],
                              cwd=ROOT, capture_output=True, timeout=10, check=False)

    def test_fifteen_legacy_backend_pins_and_all_six_lab_files(self):
        legacy = json.loads((ROOT / "docs/BASE-V04-SOURCE-MANIFEST.json").read_text())["files"]
        pins = {name: digest for name, digest in legacy.items()
                if name.startswith(("foundation_math/", "bounded_counterexample/"))
                and name != "foundation_math/cli.py"}
        self.assertEqual(len(pins), 15)
        for name, digest in pins.items():
            with self.subTest(path=name):
                self.assertEqual(sha256((ROOT / name).read_bytes()).hexdigest(), digest)
        lab = json.loads((ROOT / "docs/LINEAR-ALGEBRA-LAB-SOURCE-MANIFEST.json").read_text())
        runtime = [entry for entry in lab["files"] if entry["path"].startswith("exact_linalg/")]
        self.assertEqual(len(runtime), 6)
        for entry in runtime:
            with self.subTest(path=entry["path"]):
                self.assertEqual(sha256((ROOT / entry["path"]).read_bytes()).hexdigest(), entry["sha256"])

    def test_request_hash_binds_operation_domain_and_full_certificate(self):
        request = {"operation": "certify", "matrix": deepcopy(MATRIX)}
        receipt = calculate_matrix(request)
        self.assertEqual(receipt["request_sha256"], sha256(canonical(request)).hexdigest())
        reordered = {"matrix": dict(reversed(list(MATRIX.items()))), "operation": "certify"}
        self.assertEqual(calculate_matrix(reordered)["request_sha256"], receipt["request_sha256"])
        certificate = receipt["result"]["certificate"]
        verification_request = {"operation": "verify", "matrix": MATRIX, "certificate": certificate}
        checked = calculate_matrix(verification_request)
        self.assertEqual(checked["request_sha256"], sha256(canonical(verification_request)).hexdigest())
        self.assertNotEqual(checked["request_sha256"], receipt["request_sha256"])
        # An alternate valid trace preserves the mathematical result, but changes
        # the request hash. Acceptance is semantic, not producer-hash matching.
        alternate = deepcopy(certificate)
        alternate["operations"][:0] = [{"op": "swap", "i": 0, "j": 1}] * 2
        other = check_matrix_certificate(MATRIX, alternate)
        self.assertEqual(other["result"]["verification"], checked["result"]["verification"])
        self.assertNotEqual(other["request_sha256"], checked["request_sha256"])
        q_matrix = {**deepcopy(MATRIX), "domain": "Q"}
        self.assertNotEqual(certify_matrix(q_matrix)["request_sha256"], receipt["request_sha256"])
        self.no_acceptance(check_matrix_certificate(q_matrix, certificate), "INVALID_CERTIFICATE")

    def test_no_input_mutation_and_no_alias_back_to_caller(self):
        matrix = deepcopy(MATRIX)
        saved = deepcopy(matrix)
        receipt = certify_matrix(matrix)
        self.assertEqual(matrix, saved)
        certificate = receipt["result"]["certificate"]
        original_certificate = deepcopy(certificate)
        checked = check_matrix_certificate(matrix, certificate)
        self.assertEqual(matrix, saved)
        self.assertEqual(certificate, original_certificate)
        self.assertEqual(checked["status"], "success")
        certificate["matrix"]["entries"][0][1] = 99
        self.assertEqual(matrix, saved)

    def test_success_labels_hashes_and_receipts_cannot_replace_certificate(self):
        receipt = certify_matrix(MATRIX)
        forged_receipt = deepcopy(receipt)
        forged_receipt["result"]["verification"]["rank"] = 0
        for supplied in (receipt, forged_receipt,
                         {"accepted": True, "request_sha256": receipt["request_sha256"],
                          "implementation": receipt["implementation"]}):
            self.no_acceptance(check_matrix_certificate(MATRIX, supplied), "INVALID_SCHEMA")
        certificate = deepcopy(receipt["result"]["certificate"])
        certificate["request_sha256"] = receipt["request_sha256"]
        self.no_acceptance(check_matrix_certificate(MATRIX, certificate), "INVALID_SCHEMA")

    def test_verification_does_not_call_producer_and_certify_checks_producer_output(self):
        certificate = certify_matrix(MATRIX)["result"]["certificate"]
        with patch("exact_linalg.api.produce", side_effect=RuntimeError("producer must not run")) as producer:
            self.assertEqual(check_matrix_certificate(MATRIX, certificate)["status"], "success")
            producer.assert_not_called()
        invalid = deepcopy(certificate)
        invalid["rank"] = 0
        with patch("exact_linalg.api.produce", return_value=invalid):
            self.no_acceptance(certify_matrix(MATRIX), "INVALID_CERTIFICATE")

    def test_unavailable_provenance_withholds_all_mathematical_results(self):
        with patch("foundation_math.linear_algebra._implementation",
                   side_effect=OSError("private location must not be exposed")):
            error = certify_matrix(MATRIX)
        self.no_acceptance(error, "INTERNAL_ERROR")
        self.assertNotIn("private location", canonical(error).decode("ascii"))

    def test_lowered_and_invalid_limits_fail_closed_in_both_adapters(self):
        request = {"operation": "certify", "matrix": MATRIX}
        cases = [(Limits(max_dimension=0), "INVALID_INTEGER"),
                 (Limits(max_work=0), "WORK_LIMIT"),
                 (Limits(max_output_bytes=0), "OUTPUT_LIMIT"),
                 (Limits(max_input_bytes=0), "INPUT_LIMIT"),
                 (Limits(max_nodes=0), "NODE_LIMIT"),
                 (None, "INVALID_LIMIT"), ({}, "INVALID_LIMIT")]
        for limits, expected in cases:
            with self.subTest(code=expected, limits=limits):
                self.no_acceptance(calculate_matrix(request, limits), expected)
                self.no_acceptance(calculate_matrix_json(canonical(request), limits), expected)

    def test_cli_exact_input_limit_for_matrix_and_certificate(self):
        with tempfile.TemporaryDirectory() as directory:
            matrix_path, certificate_path = Path(directory) / "matrix.json", Path(directory) / "certificate.json"
            raw = canonical(MATRIX)
            matrix_path.write_bytes(raw + b" " * (MAX_INPUT_BYTES - len(raw)))
            accepted = self.cli("matrix-certify", matrix_path)
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertEqual(accepted.stderr, b"")
            matrix_path.write_bytes(matrix_path.read_bytes() + b" ")
            rejected = self.cli("matrix-certify", matrix_path)
            self.assertEqual(rejected.returncode, 2, rejected.stderr)
            self.no_acceptance(json.loads(rejected.stdout), "INPUT_LIMIT")
            matrix_path.write_bytes(raw)
            cert = canonical(certify_matrix(MATRIX)["result"]["certificate"])
            certificate_path.write_bytes(cert + b" " * (MAX_INPUT_BYTES + 1 - len(cert)))
            rejected = self.cli("matrix-check", matrix_path, certificate_path)
            self.assertEqual(rejected.returncode, 2, rejected.stderr)
            self.no_acceptance(json.loads(rejected.stdout), "INPUT_LIMIT")

    def test_cli_cannot_overwrite_its_input_and_rejects_escaped_duplicate_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            matrix_path = Path(directory) / "matrix.json"
            original = canonical(MATRIX)
            matrix_path.write_bytes(original)
            process = self.cli("matrix-certify", matrix_path, "--output", matrix_path)
            self.assertEqual(process.returncode, 2)
            self.assertEqual(process.stdout, b"")
            self.assertEqual(matrix_path.read_bytes(), original)
            matrix_path.write_bytes(b'{"domain":"Q","\\u0064omain":"Z","rows":0,"cols":0,"entries":[]}')
            process = self.cli("matrix-certify", matrix_path)
            self.assertEqual(process.returncode, 2)
            self.no_acceptance(json.loads(process.stdout), "DUPLICATE_KEY")

    def test_bridge_strict_fields_do_not_expose_limits_paths_or_verdict_injection(self):
        for field, value in (("limits", {"max_dimension": 100}), ("path", "not-a-path"),
                             ("formal_proof", True), ("accepted", True)):
            response = self.call("certify_rational_matrix", {"matrix": MATRIX, field: value})
            self.assertEqual(response["error"]["code"], -32602)
            self.assertNotIn("result", response)
        receipt = certify_matrix(MATRIX)
        response = self.call("check_rational_matrix_certificate", {"matrix": MATRIX, "certificate": receipt})
        self.assertIs(response["result"]["isError"], True)
        content = response["result"]["structuredContent"]
        self.assertEqual(content["assessment"], "tool_error")
        self.assertIs(content["formal_proof"], False)
        self.assertIs(content["runtime_goal_acceptance"], False)
        self.no_acceptance(content["receipt"], "INVALID_SCHEMA")

    def test_matrix_notifications_never_dispatch_arithmetic(self):
        for name, target in (("certify_rational_matrix", "certify_matrix"),
                             ("check_rational_matrix_certificate", "check_matrix_certificate")):
            request = {"jsonrpc": "2.0", "method": "tools/call",
                       "params": {"name": name, "arguments": {"matrix": MATRIX}}}
            with patch.object(server, target, side_effect=RuntimeError("notification executed")) as arithmetic:
                self.assertIsNone(self.bridge.handle(canonical(request)))
                arithmetic.assert_not_called()

    def test_bridge_backend_limit_is_distinct_from_wire_limit(self):
        matrix = {"domain": "Z", "rows": 1, "cols": 1, "entries": [[1 << 128]]}
        response = self.call("certify_rational_matrix", {"matrix": matrix})
        self.assertIs(response["result"]["isError"], True)
        self.no_acceptance(response["result"]["structuredContent"]["receipt"], "BIT_LIMIT")
        matrix["entries"][0][0] = 1 << 4096
        response = self.call("certify_rational_matrix", {"matrix": matrix})
        self.assertEqual(response["error"]["code"], -32002)
        self.assertNotIn("result", response)

    def test_bridge_explicit_empty_shapes_are_distinct_and_bound(self):
        cases = [({"domain": "Q", "rows": 0, "cols": 0, "entries": []}, 1),
                 ({"domain": "Q", "rows": 0, "cols": 2, "entries": []}, None),
                 ({"domain": "Q", "rows": 2, "cols": 0, "entries": [[], []]}, None)]
        for matrix, determinant in cases:
            response = self.call("certify_rational_matrix", {"matrix": matrix})
            content = response["result"]["structuredContent"]
            self.assertEqual(content["assessment"], "rational_matrix_certified")
            verification = content["receipt"]["result"]["verification"]
            self.assertEqual((verification["rows"], verification["cols"]), (matrix["rows"], matrix["cols"]))
            self.assertEqual(verification["rank"], 0)
            self.assertEqual(verification["determinant"], determinant)
            self.assertEqual(verification["free_columns"], list(range(matrix["cols"])))
            certificate = content["receipt"]["result"]["certificate"]
            for other, _ in cases:
                if other != matrix:
                    self.no_acceptance(check_matrix_certificate(other, certificate), "INVALID_CERTIFICATE")

    def test_bridge_output_withholding_contains_no_partial_matrix_evidence(self):
        response = self.call("certify_rational_matrix", {"matrix": MATRIX})
        with patch.object(server, "MAX_OUTPUT_BYTES", 100):
            encoded = server.encode_response(response)
        failure = json.loads(encoded)
        self.assertEqual(failure["error"]["code"], -32002)
        self.assertNotIn("result", failure)
        self.assertNotIn(b"certificate", encoded)
        self.assertNotIn(b"accepted", encoded)

    def test_stdio_session_stays_usable_after_matrix_rejection(self):
        initialize = frame("initialize", {"protocolVersion": server.PROTOCOL}, "init")
        invalid = frame("tools/call", {"name": "certify_rational_matrix", "arguments": {"matrix": {}}}, "bad")
        valid = frame("tools/call", {"name": "certify_rational_matrix", "arguments": {"matrix": MATRIX}}, "good")
        sink = BytesIO()
        self.assertEqual(server.serve(BytesIO(b"\n".join((initialize, invalid, valid)) + b"\n"), sink), 0)
        responses = [json.loads(line) for line in sink.getvalue().splitlines()]
        self.assertEqual([response["id"] for response in responses], ["init", "bad", "good"])
        self.assertIs(responses[1]["result"]["isError"], True)
        self.assertIs(responses[2]["result"]["isError"], False)
        for response in responses[1:]:
            self.assertIs(response["result"]["structuredContent"]["runtime_goal_acceptance"], False)


if __name__ == "__main__":
    unittest.main()
