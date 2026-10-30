from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import itertools
import json
from pathlib import Path
import random
import subprocess
import sys
import unittest
from unittest.mock import patch

from exact_systems.api import handle_request
from exact_systems.contract import (
    Limits, MathError, SCHEMA, check_tree, encode_coefficient, loads_bounded,
    parse_coefficient, split_work,
)
from exact_systems.producer import produce
from exact_systems.verifier import verify

ROOT = Path(__file__).resolve().parents[1]
_UNSET = object()


def spec(a, b, cols=None, domain='Z'):
    return {'matrix': {'domain': domain, 'rows': len(a),
                       'cols': len(a[0]) if a else (0 if cols is None else cols),
                       'entries': deepcopy(a)}, 'rhs': deepcopy(b)}


def q(value):
    return Fraction(value) if type(value) is int else Fraction(value['num'], value['den'])


def determinant(a):
    """Small independent Leibniz oracle, no row reduction or frozen code."""
    n = len(a)
    total = Fraction(0)
    for perm in itertools.permutations(range(n)):
        inversions = sum(perm[i] > perm[j] for i in range(n) for j in range(i + 1, n))
        term = Fraction((-1) ** inversions)
        for i in range(n):
            term *= a[i][perm[i]]
        total += term
    return total


def minor_rank(a, cols):
    for k in range(min(len(a), cols), 0, -1):
        for rows in itertools.combinations(range(len(a)), k):
            for columns in itertools.combinations(range(cols), k):
                if determinant([[a[i][j] for j in columns] for i in rows]):
                    return k
    return 0


def independent_check(test, system, response):
    test.assertTrue(response['ok'], response)
    result = response['verification']
    a = [[q(x) for x in row] for row in system['matrix']['entries']]
    b = [q(x) for x in system['rhs']]
    m, n = len(a), system['matrix']['cols']
    rank = minor_rank(a, n)
    augmented_rank = minor_rank([row + [b[i]] for i, row in enumerate(a)], n + 1)
    test.assertEqual(result['outcome'] == 'consistent', rank == augmented_rank)
    test.assertEqual(result['scope'], 'one_explicit_linear_system')
    test.assertEqual(result['computational_field'], 'Q')
    for field in ('formal_proof', 'runtime_goal_acceptance', 'family_or_generic_claim'):
        test.assertIs(result[field], False)
    if result['outcome'] == 'consistent':
        x = [q(v) for v in result['particular']]
        null = [[q(v) for v in row] for row in result['nullspace']['entries']]
        test.assertEqual(len(x), n)
        test.assertEqual(result['rank'], rank)
        test.assertEqual(result['nullity'], n - rank)
        test.assertEqual([sum((u*v for u,v in zip(row,x)), Fraction(0)) for row in a], b)
        for column in range(n - rank):
            for row in a:
                test.assertEqual(sum((row[j]*null[j][column] for j in range(n)), Fraction(0)), 0)
        test.assertEqual(minor_rank(null, n - rank), n - rank)
        # Several arbitrary affine combinations are solutions as well.
        for scalar in (-2, 0, 3):
            point = [x[j] + sum((null[j][k]*Fraction(scalar+k) for k in range(n-rank)), Fraction(0))
                     for j in range(n)]
            test.assertEqual([sum((u*v for u,v in zip(row, point)), Fraction(0)) for row in a], b)
    else:
        y = [q(v) for v in result['left_nullvector']]
        test.assertEqual(len(y), m)
        for j in range(n):
            test.assertEqual(sum((y[i]*a[i][j] for i in range(m)), Fraction(0)), 0)
        pairing = sum((u*v for u,v in zip(y,b)), Fraction(0))
        test.assertNotEqual(pairing, 0)
        test.assertEqual(pairing, q(result['rhs_pairing']))


class SystemExamples(unittest.TestCase):
    def solve(self, system):
        result = handle_request({'operation': 'solve', 'system': system})
        independent_check(self, system, result)
        self.assertTrue(handle_request({'operation': 'verify', 'system': system,
                                        'certificate': result['certificate']})['ok'])
        return result

    def test_unique_integer_input_rational_solution(self):
        result = self.solve(spec([[2]], [1]))
        self.assertEqual(result['verification']['particular'], [{'num': 1, 'den': 2}])
        self.assertEqual(result['verification']['nullspace']['entries'], [[]])

    def test_underdetermined_complete_basis(self):
        result = self.solve(spec([[2, 1, 0], [0, 0, 0]], [1, 0]))
        self.assertEqual(result['verification']['nullity'], 2)
        self.assertEqual(result['verification']['nullspace']['entries'],
                         [[{'num': -1, 'den': 2}, 0], [1, 0], [0, 1]])

    def test_overdetermined_consistent_and_inconsistent(self):
        self.solve(spec([[1, 2], [2, 4], [-1, -2]], [3, 6, -3]))
        self.solve(spec([[1, 2], [2, 4], [-1, -2]], [3, 7, -3]))

    def test_rational_inputs(self):
        self.solve(spec([[{'num': 1, 'den': 2}, {'num': 1, 'den': 3}], [1, 1]],
                        [{'num': -1, 'den': 7}, 2], domain='Q'))

    def test_zero_rows_and_columns(self):
        for m,n in itertools.product(range(5), repeat=2):
            if m and n:
                continue
            self.solve(spec([[] for _ in range(m)], [0]*m, cols=n))
            if m:
                self.solve(spec([[] for _ in range(m)], [0]*(m-1)+[1], cols=n))

    def test_zero_matrix(self):
        self.solve(spec([[0,0,0], [0,0,0]], [0,0]))
        self.solve(spec([[0,0,0], [0,0,0]], [0,-3]))

    def test_noncanonical_particular_allowed_when_mathematically_valid(self):
        system = spec([[2,1]], [1])
        certificate = produce(system)
        certificate['particular'] = [0,1]
        self.assertEqual(verify(system, certificate).particular, (Fraction(0),Fraction(1)))

    def test_external_inconsistent_witness_without_matrix_producer(self):
        system = spec([[1,2],[2,4]], [1,3])
        certificate = {'schema': SCHEMA, 'system': system, 'outcome': 'inconsistent',
                       'left_nullvector': [-2,1], 'rhs_pairing': 1}
        with patch('exact_systems.verifier.verify_matrix', side_effect=RuntimeError('must not be used')):
            self.assertEqual(verify(system, certificate).rhs_pairing, 1)
        certificate['left_nullvector'] = [4,-2]
        certificate['rhs_pairing'] = -2
        self.assertEqual(verify(system, certificate).rhs_pairing, -2)

    def test_no_mutation_or_shared_result_inputs(self):
        system = spec([[1,1],[2,2]], [3,6])
        original = deepcopy(system)
        first = produce(system)
        self.assertEqual(system, original)
        saved = deepcopy(first)
        verify(system, first)
        self.assertEqual(first, saved)
        first['system']['rhs'][0] = 999
        first['matrix_certificate']['matrix']['entries'][0][0] = 999
        self.assertEqual(system, original)
        second = produce(system)
        self.assertEqual(second, saved)


class OracleTests(unittest.TestCase):
    def test_exhaustive_ternary_systems_up_to_two_by_two(self):
        count = 0
        for m,n in itertools.product(range(3), repeat=2):
            for entries in itertools.product((-1,0,1), repeat=m*n+m):
                a = [list(entries[i*n:(i+1)*n]) for i in range(m)]
                b = list(entries[m*n:])
                system = spec(a,b,cols=n)
                independent_check(self,system,handle_request({'operation':'solve','system':system}))
                count += 1
        self.assertEqual(count, 861)

    def test_seeded_rational_minor_oracles(self):
        rng = random.Random(701203)
        for _ in range(160):
            m,n = rng.randrange(6),rng.randrange(6)
            a = [[encode_coefficient(Fraction(rng.randrange(-4,5),rng.randrange(1,5))) for _ in range(n)]
                 for _ in range(m)]
            b = [encode_coefficient(Fraction(rng.randrange(-4,5),rng.randrange(1,5))) for _ in range(m)]
            system=spec(a,b,cols=n,domain='Q')
            independent_check(self,system,handle_request({'operation':'solve','system':system}))

    def test_maximum_dimension_sparse_boundaries(self):
        for m,n in ((0,16),(16,0),(16,16),(8,16),(16,8)):
            a=[[int(i==j) for j in range(n)] for i in range(m)]
            b=[1 if i<n else 0 for i in range(m)]
            result=handle_request({'operation':'solve','system':spec(a,b,cols=n)})
            self.assertTrue(result['ok'],result)
            self.assertEqual(result['verification']['outcome'],'consistent')
            self.assertEqual(result['verification']['rank'],min(m,n))


class MutationTests(unittest.TestCase):
    def setUp(self):
        self.system=spec([[2,1,1],[1,1,0],[3,2,1]],[1,2,3])
        self.certificate=produce(self.system)
        self.bad_system=spec([[2,1],[4,2]],[1,3])
        self.bad_certificate=produce(self.bad_system)

    def rejected(self,system,certificate,code=None):
        result=handle_request({'operation':'verify','system':system,'certificate':certificate})
        self.assertFalse(result['ok'],result)
        self.assertNotIn('verification',result)
        self.assertNotIn('certificate',result)
        if code:
            self.assertEqual(result['error']['code'],code,result)

    def test_each_outer_field_missing_and_unknown(self):
        for system,certificate in ((self.system,self.certificate),(self.bad_system,self.bad_certificate)):
            for key in certificate:
                changed=deepcopy(certificate)
                del changed[key]
                self.rejected(system,changed)
            changed=deepcopy(certificate)
            changed['formal_proof']=True
            self.rejected(system,changed,'INVALID_SCHEMA')

    def test_every_matrix_certificate_field_missing(self):
        for key in self.certificate['matrix_certificate']:
            changed=deepcopy(self.certificate)
            del changed['matrix_certificate'][key]
            self.rejected(self.system,changed)

    def test_binding_matrix_rhs_shape_and_domain(self):
        for target in ('expected','embedded'):
            for variant in ('matrix','rhs','domain','rows','cols'):
                system,certificate=deepcopy(self.system),deepcopy(self.certificate)
                obj=system if target=='expected' else certificate['system']
                if variant=='matrix': obj['matrix']['entries'][0][0]+=1
                elif variant=='rhs': obj['rhs'][0]+=1
                elif variant=='domain': obj['matrix']['domain']='Q'
                elif variant=='rows': obj['matrix']['rows']+=1
                elif variant=='cols': obj['matrix']['cols']+=1
                self.rejected(system,certificate)

    def test_noncanonical_and_false_particular(self):
        for value in (0,True,0.5,'1',{'num':2,'den':2},{'num':1,'den':0},{'num':1,'den':-2}):
            changed=deepcopy(self.certificate)
            changed['particular'][0]=value
            self.rejected(self.system,changed)
        for bad in ([],[1],[1,2,3,4],None,{}):
            changed=deepcopy(self.certificate)
            changed['particular']=bad
            self.rejected(self.system,changed)

    def test_rank_completeness_and_row_transform_corruptions(self):
        mutations=[
            lambda c:c.update(rank=1),
            lambda c:c.update(pivots=[0,2]),
            lambda c:c.update(free_columns=[0]),
            lambda c:c['nullspace']['entries'][0].__setitem__(0,0),
            lambda c:c['nullspace']['entries'][2].__setitem__(0,0),
            lambda c:c['rref']['entries'][0].__setitem__(0,2),
            lambda c:c['transform']['entries'][0].__setitem__(0,0),
            lambda c:c.update(operations=[]),
            lambda c:c.update(determinant=1),
            lambda c:c['matrix']['entries'][0].__setitem__(0,3),
            lambda c:c['nullspace'].update(domain='Z'),
        ]
        for mutation in mutations:
            changed=deepcopy(self.certificate)
            mutation(changed['matrix_certificate'])
            self.rejected(self.system,changed)

    def test_dependent_incomplete_kernel_even_if_membership_true(self):
        system=spec([[1,0,0]],[0])
        certificate=produce(system)
        certificate['matrix_certificate']['nullspace']['entries']=[[0,0],[1,1],[0,0]]
        self.rejected(system,certificate)
        certificate=produce(system)
        certificate['matrix_certificate']['nullspace']={'domain':'Q','rows':3,'cols':1,'entries':[[0],[1],[0]]}
        self.rejected(system,certificate)

    def test_noninvertible_operation_forgery(self):
        for operation in ({'op':'scale','i':0,'factor':0},
                          {'op':'add','target':0,'source':0,'factor':-1},
                          {'op':'swap','i':0,'j':0},
                          {'op':'add','target':0,'source':1,'factor':0},
                          {'op':'exec','code':'raise SystemExit'}):
            changed=deepcopy(self.certificate)
            changed['matrix_certificate']['operations'].append(operation)
            self.rejected(self.system,changed)

    def test_inconsistency_witness_must_annihilate_and_pair_nonzero(self):
        variants=[{'left_nullvector':[0,0],'rhs_pairing':0},
                  {'left_nullvector':[0,1]}, {'rhs_pairing':0}, {'rhs_pairing':17},
                  {'left_nullvector':[]}, {'left_nullvector':[True,1]},
                  {'left_nullvector':[{'num':1,'den':1},1]}, {'rhs_pairing':True},
                  {'left_nullvector':[-2,1,0]}]
        for variant in variants:
            changed=deepcopy(self.bad_certificate)
            changed.update(variant)
            self.rejected(self.bad_system,changed)

    def test_relabeling_outcomes_or_false_inconsistency(self):
        changed=deepcopy(self.bad_certificate)
        changed['outcome']='consistent'
        self.rejected(self.bad_system,changed)
        for outcome in ('unknown',None,True,[],{'outcome':'consistent'}):
            changed=deepcopy(self.certificate);changed['outcome']=outcome
            self.rejected(self.system,changed)
        system=spec([[1],[1]],[1,1])
        changed={'schema':SCHEMA,'system':system,'outcome':'inconsistent',
                 'left_nullvector':[-1,1],'rhs_pairing':1}
        self.rejected(system,changed)

    def test_solve_does_not_trust_producer(self):
        changed=deepcopy(self.certificate);changed['particular']=[0,0,0]
        with patch('exact_systems.api.produce',return_value=changed):
            result=handle_request({'operation':'solve','system':self.system})
        self.assertFalse(result['ok'])
        self.assertNotIn('certificate',result)


class ContractAndResourceTests(unittest.TestCase):
    def setUp(self):
        self.system=spec([[2,1],[1,1]],[1,2])
        self.request={'operation':'solve','system':self.system}

    def error(self,request=_UNSET,limits=Limits(),code=None):
        response=handle_request(self.request if request is _UNSET else request,limits)
        self.assertFalse(response['ok'],response)
        self.assertEqual(set(response),{'ok','error'})
        if code:self.assertEqual(response['error']['code'],code,response)
        return response

    def test_strict_request_fields_and_types(self):
        for request in (None,[],{},1,{'operation':'exec','system':self.system},
                        dict(self.request,expression='x+1'),
                        dict(self.request,certificate={}),{'operation':'verify','system':self.system}):
            self.error(request)
        self.error(dict(self.request,operation='certify'))

    def test_strict_input_system_matrix_rhs(self):
        variants=[{'rhs':[1]}, {'rhs':[1,2,3]}, {'rhs':None}, {'rhs':[[1],[2]]},
                  {'rhs':[True,2]}, {'rhs':[1.0,2]}, {'rhs':['1',2]},
                  {'rhs':[{'num':1,'den':2},2]}, {'rhs':[{'num':1,'den':1},2]},
                  {'extra':0}]
        for variant in variants:
            system=deepcopy(self.system);system.update(variant)
            self.error({'operation':'solve','system':system})
        for key,value in [('domain','R'),('domain',True),('rows',True),('cols',-1),
                          ('cols',17),('entries',[[1],[1]]),('entries',[[1,1]])]:
            system=deepcopy(self.system);system['matrix'][key]=value
            self.error({'operation':'solve','system':system})

    def test_limits_all_hard_ceiling_and_type_checks(self):
        from dataclasses import fields
        for field in fields(Limits):
            for value in (-1,True,1.5,getattr(Limits(),field.name)+1):
                with self.assertRaises(MathError):replace(Limits(),**{field.name:value})
        self.error(limits=None,code='INVALID_LIMIT')
        with self.assertRaises(MathError):Limits(max_input_bits=5,max_intermediate_bits=4)

    def test_dimension_cells_bits_operations_work_and_output_limits(self):
        for limits,code in [(Limits(max_dimension=1),'INVALID_INTEGER'),
                            (Limits(max_cells=3),'CELL_LIMIT'),
                            (Limits(max_input_bits=1),'BIT_LIMIT'),
                            (Limits(max_operations=0),'OPERATION_LIMIT'),
                            (Limits(max_work=0),'WORK_LIMIT'),
                            (Limits(max_output_bytes=1),'OUTPUT_LIMIT')]:
            self.error(limits=limits,code=code)
        huge=deepcopy(self.system);huge['rhs'][0]=1<<128
        self.error({'operation':'solve','system':huge},code='BIT_LIMIT')
        huge=deepcopy(self.system);huge['matrix']['entries'][0][0]=1<<128
        self.error({'operation':'solve','system':huge},code='BIT_LIMIT')

    def test_intermediate_growth_failure(self):
        system=spec([[127,1],[1,127]],[1,1])
        self.error({'operation':'solve','system':system},Limits(max_input_bits=7,max_intermediate_bits=7),'BIT_LIMIT')
        self.assertTrue(handle_request({'operation':'solve','system':system})['ok'])

    def test_shape_limits_cover_transform_and_basis(self):
        self.error({'operation':'solve','system':spec([[],[],[]],[0,0,0],cols=0)},
                   Limits(max_cells=8),'CELL_LIMIT')
        self.error({'operation':'solve','system':spec([],[],cols=3)},
                   Limits(max_cells=8),'CELL_LIMIT')

    def test_partition_never_resets_or_increases_total_work(self):
        for amount in range(20):
            first,second=split_work(Limits(max_work=amount))
            self.assertEqual(first.max_work+second.max_work,amount)
        first_seen=[]; second_seen=[]
        real_produce=produce; real_verify=verify
        def recording_produce(s,limits):
            first_seen.append(limits.max_work);return real_produce(s,limits)
        def recording_verify(s,c,limits):
            second_seen.append(limits.max_work);return real_verify(s,c,limits)
        with patch('exact_systems.api.produce',recording_produce),patch('exact_systems.api.verify',recording_verify):
            result=handle_request(self.request,Limits(max_work=20001))
        self.assertTrue(result['ok'],result)
        self.assertEqual(first_seen,[10000]);self.assertEqual(second_seen,[10001])
        # Real primitive/scan charges across all stages stay below the top-level cap.
        from exact_linalg.contract import Budget
        real_tick=Budget.tick;charges=[]
        def recording_tick(budget,amount=1):
            charges.append(amount);return real_tick(budget,amount)
        with patch.object(Budget,'tick',recording_tick):
            result=handle_request(self.request,Limits(max_work=20001))
        self.assertTrue(result['ok']);self.assertLessEqual(sum(charges),20001)

    def test_structural_byte_node_depth_limits(self):
        self.error(limits=Limits(max_input_bytes=1),code='INPUT_LIMIT')
        self.error(limits=Limits(max_nodes=1),code='NODE_LIMIT')
        self.error(limits=Limits(max_depth=1),code='DEPTH_LIMIT')
        nested=[];nested.append(nested)
        self.error(nested,code='DEPTH_LIMIT')
        self.error({'operation':'solve','system':self.system,'x':'\ud800'},code='INVALID_JSON')

    def test_json_duplicate_float_nonfinite_encoding_rejection(self):
        for raw,code in [(b'{"a":1,"a":2}','DUPLICATE_KEY'),(b'1.0','INVALID_COEFFICIENT'),
                         (b'NaN','INVALID_COEFFICIENT'),(b'Infinity','INVALID_COEFFICIENT'),
                         (b'\xff','INVALID_JSON'),(b'{','INVALID_JSON'),
                         (b'1'*3000,'BIT_LIMIT')]:
            with self.assertRaises(MathError) as context:loads_bounded(raw)
            self.assertEqual(context.exception.code,code)

    def test_zero_dimensions_valid_with_zero_dimension_ceiling(self):
        result=handle_request({'operation':'solve','system':spec([],[],cols=0)},Limits(max_dimension=0,max_cells=0))
        self.assertTrue(result['ok'],result)

    def test_exact_input_output_byte_boundaries(self):
        size=len(json.dumps(self.request,separators=(',',':'),ensure_ascii=True).encode('ascii'))
        check_tree(self.request,Limits(max_input_bytes=size))
        with self.assertRaises(MathError):check_tree(self.request,Limits(max_input_bytes=size-1))
        from exact_systems.contract import check_output
        response=handle_request(self.request)
        size=len(json.dumps(response,separators=(',',':'),ensure_ascii=True).encode('ascii'))
        check_output(response,Limits(max_output_bytes=size))
        with self.assertRaises(MathError):check_output(response,Limits(max_output_bytes=size-1))


class IsolationAndCliTests(unittest.TestCase):
    def test_verifier_imports_no_producer(self):
        script="""import sys
from exact_systems.verifier import verify
if 'exact_systems.producer' in sys.modules or 'exact_linalg.producer' in sys.modules:
    raise SystemExit('producer was imported')
print('independent import')
"""
        result=subprocess.run([sys.executable,'-B',*(['-O'] if sys.flags.optimize else []),'-c',script],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)

    def cli(self,raw):
        return subprocess.run([sys.executable,'-B',*(['-O'] if sys.flags.optimize else []),'-m','exact_systems'],cwd=ROOT,
                              input=raw,stdout=subprocess.PIPE,stderr=subprocess.PIPE)

    def test_cli_solve_and_verify(self):
        system=spec([[2,1]],[1])
        result=self.cli(json.dumps({'operation':'solve','system':system}).encode())
        self.assertEqual(result.returncode,0,result.stderr)
        response=json.loads(result.stdout)
        self.assertTrue(response['ok'])
        result=self.cli(json.dumps({'operation':'verify','system':system,
                                   'certificate':response['certificate']}).encode())
        self.assertEqual(result.returncode,0,result.stdout)
        self.assertEqual(len(result.stdout.splitlines()),1)
        self.assertEqual(result.stderr,b'')

    def test_cli_errors_no_traceback(self):
        for raw in (b'',b'{}',b'{}{}',b'NaN',b'{"operation":"solve","operation":"verify"}',b' '*1000001):
            result=self.cli(raw)
            self.assertEqual(result.returncode,2,result.stdout)
            self.assertFalse(json.loads(result.stdout)['ok'])
            self.assertEqual(result.stderr,b'')

    def test_vendored_source_byte_identical(self):
        import hashlib
        # Pin shipped sources against the frozen lab manifest, never a sibling
        # source tree or historical generated evidence that is not shipped.
        provenance=json.loads((ROOT/'docs/LINEAR-SYSTEMS-LAB-SOURCE-MANIFEST.json').read_text())['sha256']
        for name,digest in provenance.items():
            if name.startswith(('exact_linalg/', 'exact_systems/')):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),digest)



if __name__=='__main__':unittest.main()
