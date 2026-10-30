"""CLI exposure must not promote finite exhaustion into runtime proof acceptance."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import bounded_counterexample
from foundation_math import counterexample
from foundation_math.domains import DomainError, domain_handler
from foundation_math.orchestrator import Runtime, WorkflowError

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / 'examples/counterexample' / name).read_text())


def polynomial_workflow(request, expected):
    return {'schema_version':1, 'problem': {'id':'bounded-is-not-global','domain':request['domain'],
            'goal':'Check exactly this structured polynomial identity.','assumptions':[],
            'goal_request':deepcopy(request),'required_evidence':'exact_computation'},
            'goal_task_id':'verify','tasks':[
                {'id':'propose','role':'proposer','dependencies':[],
                 'payload':{'request':deepcopy(request),'expected':expected}},
                {'id':'calculate','role':'calculator','dependencies':['propose']},
                {'id':'verify','role':'verifier','dependencies':['propose','calculate']}]}


class CounterexampleIntegrationTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'foundation_math', *args],
                              cwd=ROOT, text=True, capture_output=True, check=False)

    def test_public_api_bridge_is_exactly_lab_api(self):
        self.assertIs(counterexample.search_counterexample, bounded_counterexample.search_counterexample)
        self.assertIs(counterexample.check_witness, bounded_counterexample.check_witness)

    def test_true_bounded_search_cli_is_explicitly_not_proof(self):
        result = self.run_cli('counterexample-search','examples/counterexample/true-bounded-inequality.json')
        self.assertEqual(result.returncode,0,result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['result']['outcome'],'no_counterexample_in_declared_finite_domain')
        self.assertIs(report['scope']['universal_proof'],False)
        self.assertIs(report['scope']['formal_proof'],False)

    def test_false_cli_and_checked_witness(self):
        result = self.run_cli('counterexample-search','examples/counterexample/false-bounded-inequality.json')
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertEqual(json.loads(result.stdout)['result']['assignment'],{'x':-3})
        checked = self.run_cli('counterexample-check','examples/counterexample/false-bounded-inequality.json',
                               'examples/counterexample/valid-witness.json')
        self.assertEqual(checked.returncode,0,checked.stderr)
        self.assertIs(json.loads(checked.stdout)['result']['valid'],True)

    def test_domain_pitfall_cli_rejects_half(self):
        result = self.run_cli('counterexample-check','examples/counterexample/integer-domain-pitfall.json',
                              'examples/counterexample/rational-half-not-in-domain.json')
        self.assertEqual(result.returncode,1,result.stderr)
        self.assertIs(json.loads(result.stdout)['result']['valid'],False)

    def test_cli_resource_and_unsupported_error_are_not_success(self):
        result = self.run_cli('counterexample-search','examples/counterexample/rejected-polynomial-division.json')
        self.assertEqual(result.returncode,2,result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'error')

    def test_cli_output_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'receipt.json'
            args = ('counterexample-search','examples/counterexample/true-bounded-inequality.json','--output',str(path))
            self.assertEqual(self.run_cli(*args).returncode,0)
            before = path.read_bytes()
            self.assertEqual(self.run_cli(*args).returncode,2)
            self.assertEqual(path.read_bytes(),before)

    def test_finite_domain_not_admitted_as_runtime_goal(self):
        req = load('true-bounded-inequality.json')
        receipt = counterexample.search_counterexample(req)
        self.assertEqual(receipt['status'],'success')
        with self.assertRaises(DomainError):
            domain_handler(req['domain'])
        with self.assertRaises(WorkflowError):
            Runtime.from_dict(polynomial_workflow(req,receipt['result']))

    def test_boolean_box_exhaustion_cannot_prove_formal_identity(self):
        finite = load('integer-domain-pitfall.json')
        finite['bounds']['x'] = {'lower':0,'upper':1}
        finite['assertion']['relation'] = 'eq'
        bounded = counterexample.search_counterexample(finite)
        self.assertEqual(bounded['result']['outcome'],'no_counterexample_in_declared_finite_domain')
        formal = {'domain':'polynomial_ring','coefficient_field':'Q','variables':['x'],
                  'operation':'verify_identity','operands':[finite['assertion']['left'],finite['assertion']['right']]}
        expected = {'domain':'polynomial_ring','coefficient_field':'Q','variables':['x'],'equal':True}
        workflow = polynomial_workflow(formal,expected)
        workflow['tasks'][0]['payload']['rationale'] = json.dumps(bounded)
        report = Runtime.from_dict(workflow).run()
        self.assertNotEqual(report['goal_status'],'exact_result_verified')
        self.assertEqual(report['proof_status'],'not_formally_verified')

    def test_v03_acceptance_boundary_sources_unchanged(self):
        base = json.loads((ROOT/'docs/BASE-V03-SOURCE-MANIFEST.json').read_text())
        for name in ('foundation_math/domains.py','foundation_math/orchestrator.py','foundation_math/polynomial.py',
                     'foundation_math/calculator.py','foundation_math/lean_adapter.py'):
            self.assertEqual(sha256((ROOT/name).read_bytes()).hexdigest(),base['files'][name])


if __name__ == '__main__':
    unittest.main()
