"""Two appended explicit-system contracts; no changes to prior definitions."""
from copy import deepcopy
from .schemas import DRAFT, INTEGER, obj, array, _matrix_defs
from foundation_math.linear_systems import IMPLEMENTATION_FILES

SOLVE = 'solve_rational_linear_system'
CHECK = 'check_rational_linear_system_certificate'


def _defs():
    definitions = _matrix_defs()
    dimension = {'type': 'integer', 'minimum': 0, 'maximum': 16}
    vector = array({'$ref': '#/$defs/coefficient'}, 0, 16)
    system = obj({'matrix': {'$ref': '#/$defs/matrix'}, 'rhs': vector})
    system['allOf'] = [{'if': {'properties': {'matrix': {'properties': {'domain': {'const': 'Z'}}}}},
                       'then': {'properties': {'rhs': {'items': INTEGER}}}}]
    system['description'] = ('One explicit A,b with one RHS. Runtime binds exact shapes and domain; RHS has exactly A.rows '
                             'coefficients. Z restricts both A and b to integer tokens, but solutions are over Q.')
    certificate_common = {'schema': {'const': 'foundation-math-rational-linear-system/1'},
                          'system': {'$ref': '#/$defs/system'}}
    verification_common = {'accepted': {'const': True}, 'scope': {'const': 'one_explicit_linear_system'},
        'computational_field': {'const': 'Q'}, 'input_domain': {'enum': ['Z', 'Q']},
        'rows': dimension, 'cols': dimension, 'formal_proof': {'const': False},
        'runtime_goal_acceptance': {'const': False}, 'family_or_generic_claim': {'const': False}}
    for outcome in ('consistent', 'inconsistent'):
        certificate_fields = ({'particular': vector, 'matrix_certificate': {'$ref': '#/$defs/certificate'}}
                              if outcome == 'consistent' else
                              {'left_nullvector': vector, 'rhs_pairing': {'allOf': [
                                  {'$ref': '#/$defs/coefficient'}, {'not': {'const': 0}}]}})
        verification_fields = ({'particular': vector, 'nullspace': {'$ref': '#/$defs/q_matrix'},
                                'rank': dimension, 'nullity': dimension}
                               if outcome == 'consistent' else certificate_fields)
        definitions[outcome + '_certificate'] = obj({**certificate_common,
            'outcome': {'const': outcome}, **certificate_fields})
        definitions[outcome + '_verification'] = obj({**verification_common,
            'outcome': {'const': outcome}, **verification_fields})
    definitions['system'] = system
    definitions['system_certificate'] = {'oneOf': [
        {'$ref': '#/$defs/' + outcome + '_certificate'} for outcome in ('consistent', 'inconsistent')],
        'description': 'Runtime checks against separately supplied expected A,b. A schema match is not certificate verification.'}
    return definitions


def _input(check):
    fields = {'system': {'$ref': '#/$defs/system'}}
    if check:
        fields['certificate'] = {'$ref': '#/$defs/system_certificate'}
    return {'$schema': DRAFT, **obj(fields), '$defs': _defs()}


def _output(check):
    common = {'schema_version': {'const': 1}, 'scope': {'const': 'one_explicit_linear_system'},
              'computational_field': {'const': 'Q'}, 'formal_proof': {'const': False},
              'runtime_goal_acceptance': {'const': False}, 'family_or_generic_claim': {'const': False}}
    digest = {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'}
    implementation = obj({'name': {'const': 'foundation-math-exact-linear-systems'},
                          'version': {'type': 'string'},
                          'source_sha256': obj({name: digest for name in IMPLEMENTATION_FILES})})
    success = []
    for outcome in ('consistent', 'inconsistent'):
        result = {'ok': {'const': True}, 'verification': {'$ref': '#/$defs/' + outcome + '_verification'}}
        if not check:
            result['certificate'] = {'$ref': '#/$defs/' + outcome + '_certificate'}
        success.append(obj({**common, 'status': {'const': 'success'},
            'operation': {'const': 'verify' if check else 'solve'}, 'request_sha256': digest,
            'implementation': implementation, 'result': obj(result)}))
    error = obj({**common, 'status': {'const': 'error'}, 'error': obj({
        'code': {'type': 'string'}, 'message': {'type': 'string'}, 'path': {'type': 'string'}})})
    assessment = 'rational_linear_system_certificate_valid' if check else 'rational_linear_system_solved'
    schema = obj({'tool': {'const': CHECK if check else SOLVE},
                  'assessment': {'enum': [assessment, 'tool_error']},
                  'formal_proof': {'const': False}, 'runtime_goal_acceptance': {'const': False},
                  'receipt': {'oneOf': success + [error]}})
    schema['allOf'] = [{'if': {'properties': {'receipt': {'properties': {'status': {'const': 'success'}}}}},
                        'then': {'properties': {'assessment': {'const': assessment}}},
                        'else': {'properties': {'assessment': {'const': 'tool_error'}}}}]
    return {'$schema': DRAFT, **schema, '$defs': _defs()}


def tool_definitions():
    scope = (' One explicit rational system with one RHS only. Consistency returns a particular solution and a complete '
             'Q-nullspace basis; inconsistency returns y with y^T*A=0 and y^T*b nonzero. Inconsistency is a successful checked '
             'mathematical outcome, not a tool error. Z restricts input tokens only; no integer-lattice/Diophantine, generic, '
             'symbolic, family, formal-proof or runtime-goal claim. At most 16 rows/columns, 256 cells per matrix, 128-bit input '
             'components, 2048-bit stored rational components, 1024 row operations and 2000000 total charged work units '
             'statically partitioned across stages. Unused shares are not transferred. Bridge limits remain 65536 input bytes, '
             '1048576 output bytes and 16384 JSON nodes; a standalone-valid certificate can exceed bridge limits. '
             'Resource failures carry no mathematical outcome. No caller-selected limits, paths, code or commands. '
             'Hashes bind bytes, not authenticity. Python Fraction/parser/verifier remain trusted, not a diverse proof kernel.')
    return [
        {'name': SOLVE, 'description': 'Produce and independently verify an exact certificate against the supplied original A,b.' + scope,
         'inputSchema': _input(False), 'outputSchema': _output(False), 'readOnly': True},
        {'name': CHECK, 'description': 'Freshly verify a certificate against separately supplied expected A,b, including the exact input-domain tag. '
         'The checker imports neither producer and performs no elimination. Certificate rejection returns isError=true, tool_error and no partial result.' + scope,
         'inputSchema': _input(True), 'outputSchema': _output(True), 'readOnly': True},
    ]
