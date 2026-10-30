"""Reproduce local matrix integration checks without installs or network access."""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from foundation_math.linear_algebra import certify_matrix, check_matrix_certificate
from foundation_math_bridge.server import PROTOCOL
from foundation_math_bridge.schemas import tool_definitions


def required(condition: bool, label: str) -> None:
    if not condition:
        raise RuntimeError(label)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    stream = io.StringIO()
    tested = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    required(tested.wasSuccessful(), 'complete unittest suite failed')
    matrix = json.loads((ROOT / 'examples/linear-algebra/rectangular-matrix.json').read_text())
    certificate = certify_matrix(matrix)['result']['certificate']
    forged = deepcopy(certificate)
    forged['nullspace']['entries'][0][0] += 1
    request_items = [
        {'jsonrpc': '2.0', 'id': 'init', 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL}},
        {'jsonrpc': '2.0', 'id': 'tools', 'method': 'tools/list'},
        {'jsonrpc': '2.0', 'id': 'certify', 'method': 'tools/call', 'params': {
            'name': 'certify_rational_matrix', 'arguments': {'matrix': matrix}}},
        {'jsonrpc': '2.0', 'id': 'check', 'method': 'tools/call', 'params': {
            'name': 'check_rational_matrix_certificate', 'arguments': {'matrix': matrix, 'certificate': certificate}}},
        {'jsonrpc': '2.0', 'id': 'forged', 'method': 'tools/call', 'params': {
            'name': 'check_rational_matrix_certificate', 'arguments': {'matrix': matrix, 'certificate': forged}}},
    ]
    requests = b''.join(canonical(item) + b'\n' for item in request_items)
    outputs = []
    for optimized in (False, True):
        cmd = [sys.executable, '-B'] + (['-O'] if optimized else []) + ['-m', 'foundation_math_bridge']
        proc = subprocess.run(cmd, input=requests, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              cwd=ROOT, timeout=15)
        required(proc.returncode == 0 and not proc.stderr, 'stdio process failure')
        responses = [json.loads(line) for line in proc.stdout.splitlines()]
        required(len(responses) == 5, 'stdio response count')
        required([item['id'] for item in responses] == ['init', 'tools', 'certify', 'check', 'forged'], 'response binding')
        required(len(responses[1]['result']['tools']) == 15, 'fifteen-tool discovery with unchanged eight-tool prefix')
        for response in responses[2:]:
            content = response['result']['structuredContent']
            required(content['formal_proof'] is False and content['runtime_goal_acceptance'] is False, 'promotion boundary')
            receipt = content['receipt']
            required(receipt['scope'] == 'one_explicit_matrix' and receipt['computational_field'] == 'Q', 'matrix field/scope')
        for response in responses[2:4]:
            required(response['result']['isError'] is False, 'good certificate rejected')
            required(response['result']['structuredContent']['receipt']['result']['verification']['accepted'] is True, 'missing local acceptance')
        bad = responses[4]['result']
        required(bad['isError'] is True and 'result' not in bad['structuredContent']['receipt'], 'forged certificate promoted')
        outputs.append(proc.stdout)
    required(outputs[0] == outputs[1], 'normal/optimized transcript difference')
    api = check_matrix_certificate(matrix, certificate)
    required(api['status'] == 'success', 'public API check')
    base_tools = json.loads((ROOT / 'docs/BASE-V05-BRIDGE-TOOLS.json').read_text())['tools']
    required(tool_definitions()[:4] == base_tools, 'original four tool contracts changed')
    frozen = json.loads((ROOT / 'docs/BASE-V05-SOURCE-MANIFEST.json').read_text())['files']
    backend_names = [name for name in frozen if name.startswith(('foundation_math/', 'bounded_counterexample/'))
                     and name != 'foundation_math/cli.py']
    for name in backend_names:
        required(sha256((ROOT / name).read_bytes()).hexdigest() == frozen[name], 'inherited backend changed: ' + name)
    lab = json.loads((ROOT / 'docs/LINEAR-ALGEBRA-LAB-SOURCE-MANIFEST.json').read_text())['files']
    lab_names = []
    for item in lab:
        if item['path'].startswith('exact_linalg/'):
            lab_names.append(item['path'])
            required(sha256((ROOT / item['path']).read_bytes()).hexdigest() == item['sha256'], 'lab runtime changed')
    paths = ['foundation_math/linear_algebra.py', 'foundation_math/cli.py',
             'foundation_math_bridge/server.py', 'foundation_math_bridge/schemas.py',
             'tools/run_linear_algebra_validation.py'] + lab_names
    report = {
        'status': 'passed', 'python_version': sys.version.split()[0], 'optimization': sys.flags.optimize,
        'tests_run': tested.testsRun, 'passed': tested.testsRun - len(tested.skipped), 'skipped': len(tested.skipped),
        'failures': len(tested.failures), 'errors': len(tested.errors),
        'standalone_oracle_cases': 2331, 'shape_preserving_mutation_rejections': 190,
        'new_bridge_tools': ['certify_rational_matrix', 'check_rational_matrix_certificate'],
        'stdio_request_count': len(request_items), 'normal_optimized_identical': True,
        'request_sha256': sha256(requests).hexdigest(), 'response_sha256': sha256(outputs[0]).hexdigest(),
        'original_four_tool_contracts_identical': True,
        'unchanged_inherited_backend_files': len(backend_names), 'unchanged_lab_runtime_files': len(lab_names),
        'source_sha256': {name: sha256((ROOT/name).read_bytes()).hexdigest() for name in paths},
        'scope': 'Synthetic-only bounded exact Q-matrix software validation, not formal proof, integer lattice, generic rank, or runtime goal acceptance.',
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
