"""Finite check integration, dependency failures, integrity and CLI regressions."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from fm_research.problem import load_spec, run_check, gate, to_goal_contract, to_endoforge_atoms

BASE = Path(__file__).resolve().parents[1]
EXAMPLE = BASE / 'examples/2i-regression.problem.json'
FALSE = BASE / 'tests/fixtures/false-claim.problem.json'
sys.path.insert(0, str(BASE.parents[1]))
from poodo_core.models import GoalContract


class ProblemTests(unittest.TestCase):
    def setUp(self):
        self.spec = load_spec(EXAMPLE)
        self.claims = self.spec['claims']
        self.evidence = {c['id']: run_check(c) for c in self.claims if c['kind'] == 'computed'}

    def test_example_and_hashes(self):
        statuses = gate(self.spec, self.evidence)
        for c in self.claims[:-1]:
            self.assertEqual(statuses[c['id']], 'certified')
            self.assertEqual(self.evidence[c['id']].to_dict(), run_check(c).to_dict())
        self.assertEqual(statuses['research-argument'], 'argued')
        self.assertEqual(self.evidence['rank-q5'].observed['certificate']['rank'], 1)
        for key, value in [('args_sha256', 'bad'), ('output_sha256', 'bad'), ('kernel_source_sha256', 'bad'), ('expected', 'bad'), ('observed', 'bad')]:
            ev = dict(self.evidence, sym10=replace(self.evidence['sym10'], **{key: value}))
            self.assertEqual(gate(self.spec, ev)['sym10'], 'unchecked')

    def test_dependencies(self):
        self.claims[0]['check']['expect'] = 'wrong'
        self.claims[1]['depends_on'] = ['sym10']
        self.evidence['sym10'] = run_check(self.claims[0])
        statuses = gate(self.spec, self.evidence)
        self.assertEqual((statuses['sym10'], statuses['sym14']), ('refuted', 'blocked'))
        self.claims[-1]['depends_on'] = []
        self.claims[1]['depends_on'] = ['research-argument']
        self.assertEqual(gate(self.spec, self.evidence)['sym14'], 'blocked')
        self.claims[-1]['kind'] = 'cited'
        self.assertEqual(gate(self.spec, self.evidence)['sym14'], 'certified')
        self.claims[-1]['depends_on'] = ['sym10']
        self.assertEqual(gate(self.spec, self.evidence)['sym14'], 'blocked')
        self.assertEqual(gate(self.spec, {})['sym10'], 'unchecked')

    def test_validation(self):
        for update in [dict(depends_on=['sym10']), dict(depends_on=['missing']), dict(kind='bogus'),
                       dict(check=None), dict(check=dict(kernel='os.system', args={}, expect=1))]:
            spec = deepcopy(self.spec)
            spec['claims'][0].update(update)
            with self.assertRaises((ValueError, TypeError)):
                load_spec(spec)
        self.spec['claims'].append(deepcopy(self.claims[0]))
        with self.assertRaises(ValueError): load_spec(self.spec)
        for value in (1.5, float('nan'), float('inf')):
            spec = load_spec(EXAMPLE)
            spec['repo']['extra'] = value
            with self.assertRaises(TypeError): load_spec(spec)
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'float.json'
                path.write_text(json.dumps(spec))
                with self.assertRaises(TypeError): load_spec(path)

    def test_other_kernels_and_errors(self):
        c = deepcopy(self.claims[0])
        for kernel, args, expect in [('p1.h0_dim', dict(blocks=[dict(irrep='1', twist=2, multiplicity=1)], twist=0), 3),
                                     ('p1.h1_dim', dict(blocks=[dict(irrep='1', twist=-2, multiplicity=1)], twist=0), 1),
                                     ('rank', dict(field='Q', rows=[['1/2', 1], [1, 2]]), 1)]:
            c['check'] = dict(kernel=kernel, args=args, expect=expect)
            self.assertEqual(run_check(c).verdict, 'PASS')
        c['check']['args']['field'] = 'invalid'
        self.assertEqual(run_check(c).verdict, 'ERROR')

    def test_projections_and_cli(self):
        self.assertEqual(GoalContract.from_dict(to_goal_contract(self.spec)).domain_id, 'foundation_math')
        atoms = to_endoforge_atoms(self.spec, EXAMPLE)
        self.assertEqual(atoms['schema'], 'endoforge/atoms/1')
        self.assertEqual(len(atoms['acceptance']), len(self.evidence))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'evidence.jsonl'
            for path, flags, code in [(EXAMPLE, [], 0), (FALSE, [], 1), (EXAMPLE, ['--claim', 'rank-q5'], 0), (EXAMPLE, ['--claim', 'missing'], 2)]:
                result = subprocess.run([sys.executable, '-B', *(['-O'] if not __debug__ else []), '-m', 'fm_research', 'check', str(path), '--evidence-out', str(out), *flags], cwd=BASE, capture_output=True, text=True)
                self.assertEqual(result.returncode, code, result.stderr)
            self.assertEqual(json.loads(out.read_text())['verdict'], 'PASS')
