"""Matrix API/CLI integration cannot become a proof or integer-module result."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from exact_linalg.contract import Limits
from foundation_math.linear_algebra import (calculate_matrix, calculate_matrix_json,
                                          certify_matrix, check_matrix_certificate)
from foundation_math.domains import DomainError, domain_handler
from foundation_math.orchestrator import Runtime, WorkflowError

ROOT = Path(__file__).resolve().parents[1]
MATRIX = {'domain': 'Z', 'rows': 2, 'cols': 3, 'entries': [[1, 2, 3], [0, 1, 1]]}


class LinearAlgebraIntegration(unittest.TestCase):
    def run_cli(self, *args, optimized=False):
        cmd = [sys.executable, '-B'] + (['-O'] if optimized else []) + ['-m', 'foundation_math', *args]
        return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=10)

    def check_scope(self, receipt):
        self.assertEqual(receipt['computational_field'], 'Q')
        self.assertEqual(receipt['scope'], 'one_explicit_matrix')
        self.assertIs(receipt['formal_proof'], False)
        self.assertIs(receipt['runtime_goal_acceptance'], False)

    def test_checked_api_and_exact_provenance(self):
        receipt = certify_matrix(MATRIX)
        self.check_scope(receipt)
        self.assertEqual(receipt['status'], 'success')
        self.assertTrue(receipt['result']['verification']['accepted'])
        request = {'operation': 'certify', 'matrix': MATRIX}
        canonical = json.dumps(request, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')
        self.assertEqual(receipt['request_sha256'], sha256(canonical).hexdigest())
        for name, expected in receipt['implementation']['source_sha256'].items():
            self.assertEqual(sha256((ROOT / name).read_bytes()).hexdigest(), expected)
            self.assertFalse(name.startswith('/'))
        checked = check_matrix_certificate(MATRIX, receipt['result']['certificate'])
        self.assertEqual(checked['status'], 'success')
        self.assertEqual(checked['result']['verification'], receipt['result']['verification'])
        self.assertNotIn('certificate', checked['result'])
        self.check_scope(checked)

    def test_receipt_is_not_a_certificate_or_goal_acceptance(self):
        receipt = certify_matrix(MATRIX)
        rejected = check_matrix_certificate(MATRIX, receipt)
        self.assertEqual(rejected['status'], 'error')
        self.assertNotIn('result', rejected)
        self.check_scope(rejected)
        for label in ('rational_matrix', 'matrix', 'exact_linear_algebra'):
            with self.assertRaises(DomainError):
                domain_handler(label)
        # Relabeling the matrix as a Q scalar goal is not sufficient either.
        workflow = {'schema_version': 1,
                    'problem': {'id': 'matrix-is-not-scalar-proof', 'domain': 'Q',
                                'goal': 'Attempted matrix promotion', 'assumptions': [],
                                'goal_request': {'operation': 'certify', 'matrix': MATRIX}},
                    'goal_task_id': 'verify',
                    'tasks': [{'id': 'verify', 'role': 'verifier', 'dependencies': [],
                               'payload': {'request': MATRIX, 'expected': receipt}}]}
        with self.assertRaises(WorkflowError):
            Runtime.from_dict(workflow)

    def test_z_coefficients_are_never_integer_lattice_claim(self):
        receipt = certify_matrix({'domain': 'Z', 'rows': 1, 'cols': 2, 'entries': [[2, 1]]})
        self.check_scope(receipt)
        self.assertEqual(receipt['result']['certificate']['nullspace']['entries'], [[{'num': -1, 'den': 2}], [1]])
        self.assertEqual(receipt['result']['verification']['computational_field'], 'Q')

    def test_rebinding_and_semantic_forgeries_are_rejected(self):
        certificate = certify_matrix(MATRIX)['result']['certificate']
        changed = deepcopy(MATRIX)
        changed['entries'][0][2] += 1
        cases = [(changed, certificate)]
        for field in ('rref', 'transform', 'nullspace'):
            bad = deepcopy(certificate)
            bad[field]['entries'][0][0] += 1
            cases.append((MATRIX, bad))
        bad = deepcopy(certificate)
        bad['rank'] = 0
        cases.append((MATRIX, bad))
        bad = deepcopy(certificate)
        bad['operations'] = []
        cases.append((MATRIX, bad))
        for matrix, forged in cases:
            result = check_matrix_certificate(matrix, forged)
            self.assertEqual(result['status'], 'error')
            self.assertNotIn('result', result)
            self.check_scope(result)

    def test_request_json_rejects_duplicate_float_and_unknown_work(self):
        for raw in (b'{"operation":"certify","operation":"verify"}',
                    b'{"operation":"certify","matrix":1.2}', b'{"operation":"exec","command":"noop"}'):
            receipt = calculate_matrix_json(raw)
            self.assertEqual(receipt['status'], 'error')
            self.assertNotIn('result', receipt)
            self.check_scope(receipt)

    def test_receipt_envelope_counts_against_output_limit(self):
        request = {'operation': 'certify', 'matrix': MATRIX}
        receipt = calculate_matrix(request)
        size = len(json.dumps(receipt, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii'))
        self.assertEqual(calculate_matrix(request, Limits(max_output_bytes=size))['status'], 'success')
        limited = calculate_matrix(request, Limits(max_output_bytes=size - 1))
        self.assertEqual(limited['status'], 'error')
        self.assertEqual(limited['error']['code'], 'OUTPUT_LIMIT')
        self.assertNotIn('result', limited)

    def test_cli_certificate_and_check_normal_optimized_parity(self):
        args = ('matrix-certify', 'examples/linear-algebra/rectangular-matrix.json')
        plain, optimized = self.run_cli(*args), self.run_cli(*args, optimized=True)
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertEqual(optimized.returncode, 0, optimized.stderr)
        self.assertEqual(plain.stdout, optimized.stdout)
        self.check_scope(json.loads(plain.stdout))
        checked = self.run_cli('matrix-check', 'examples/linear-algebra/rectangular-matrix.json',
                               'examples/linear-algebra/rectangular-certificate.json')
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertTrue(json.loads(checked.stdout)['result']['verification']['accepted'])

    def test_cli_tampered_certificate_and_duplicate_json_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            matrix_path, cert_path = Path(directory) / 'matrix.json', Path(directory) / 'certificate.json'
            matrix_path.write_text(json.dumps(MATRIX))
            certificate = certify_matrix(MATRIX)['result']['certificate']
            certificate['nullspace']['entries'][0][0] += 1
            cert_path.write_text(json.dumps(certificate))
            process = self.run_cli('matrix-check', str(matrix_path), str(cert_path))
            self.assertEqual(process.returncode, 2)
            self.assertEqual(json.loads(process.stdout)['status'], 'error')
            self.assertNotIn('result', json.loads(process.stdout))
            matrix_path.write_text('{"domain":"Z","domain":"Q"}')
            process = self.run_cli('matrix-certify', str(matrix_path))
            self.assertEqual(process.returncode, 2)
            self.assertEqual(json.loads(process.stdout)['error']['code'], 'DUPLICATE_KEY')

    def test_cli_output_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'receipt.json'
            args = ('matrix-certify', 'examples/linear-algebra/rational-matrix.json', '--output', str(path))
            self.assertEqual(self.run_cli(*args).returncode, 0)
            saved = path.read_bytes()
            self.assertEqual(self.run_cli(*args).returncode, 2)
            self.assertEqual(path.read_bytes(), saved)

    def test_acceptance_boundary_and_lab_runtime_preserved(self):
        base = json.loads((ROOT/'docs/BASE-V05-SOURCE-MANIFEST.json').read_text())
        for name in ('foundation_math/domains.py', 'foundation_math/orchestrator.py', 'foundation_math/polynomial.py',
                     'foundation_math/calculator.py', 'foundation_math/lean_adapter.py'):
            self.assertEqual(sha256((ROOT/name).read_bytes()).hexdigest(), base['files'][name])
        lab = json.loads((ROOT/'docs/LINEAR-ALGEBRA-LAB-SOURCE-MANIFEST.json').read_text())
        for entry in lab['files']:
            if entry['path'].startswith('exact_linalg/'):
                self.assertEqual(sha256((ROOT/entry['path']).read_bytes()).hexdigest(), entry['sha256'])

    def test_first_four_complete_tool_contracts_remain_identical(self):
        from foundation_math_bridge.schemas import tool_definitions
        baseline = json.loads((ROOT/'docs/BASE-V05-BRIDGE-TOOLS.json').read_text())
        self.assertEqual(tool_definitions()[:4], baseline['tools'])
        pinned = json.loads((ROOT/'docs/BASE-V05-SOURCE-MANIFEST.json').read_text())
        self.assertEqual(baseline['schema_module_sha256'], pinned['files']['foundation_math_bridge/schemas.py'])

    def test_vendor_metadata_is_portable_and_hashes_preserved(self):
        provenance = json.loads((ROOT/'COUNTEREXAMPLE-VENDOR-PROVENANCE.json').read_text())
        self.assertEqual(provenance['source_tree'], 'Foundation Math v0.2 immutable source snapshot')
        for entry in provenance['files']:
            name = Path(entry['destination']).name
            self.assertEqual(entry['source'], 'Foundation Math v0.2: foundation_math/' + name)
            self.assertEqual(sha256((ROOT/entry['destination']).read_bytes()).hexdigest(), entry['sha256'])


if __name__ == '__main__':
    unittest.main()
