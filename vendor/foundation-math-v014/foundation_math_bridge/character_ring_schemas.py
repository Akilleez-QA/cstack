"""Append-only fixed-character contracts, not an arithmetic proof validator.

JSON Schema describes JSON value structure. Exact Python built-in types, integer
lexical tokens, duplicate keys, canonical rational encoding, byte/tree budgets,
request/certificate bindings, arithmetic, and expectations are checked at runtime.
"""
from copy import deepcopy

from .schemas import DRAFT, obj, array
from foundation_math.character_ring import IMPLEMENTATION_FILES

CALCULATE = 'calculate_fixed_character'
CHECK = 'check_fixed_character_certificate'
LABELS = ('1', 'W', 'A', 'S4', 'D', 'T6', 'P', 'Wp', 'V')
SCOPE = 'universal_representation_arithmetic_only'
CATALOG_SHA256 = '84ceb37bc32d10c4908e5b5f1f2f5994082074f2c2a9f36c846347750c79fa74'
MAX_INPUT_COEFFICIENT = (1 << 63) - 1
MAX_RESULT_COEFFICIENT = (1 << 256) - 1
MAX_FIELD_COMPONENT = (1 << 272) - 1
DIGEST = {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'}
ERROR_CODES = ('E_USAGE', 'E_IO', 'E_JSON', 'E_TYPE', 'E_SCHEMA', 'E_BUDGET',
               'E_CATALOG', 'E_CHARACTER', 'E_EXPECTATION', 'E_CERTIFICATE', 'E_INTERNAL')


def _integer(bound, *, minimum=None, maximum=None):
    return {'type': 'integer', 'minimum': -bound if minimum is None else minimum,
            'maximum': bound if maximum is None else maximum}


def _sparse(bound, *, negative=False):
    value = _integer(bound, maximum=-1) if negative else {
        **_integer(bound), 'not': {'const': 0}}
    return {'type': 'object', 'propertyNames': {'enum': list(LABELS)},
            'maxProperties': len(LABELS), 'additionalProperties': value}


def _defs():
    expression = {'oneOf': [
        obj({'op': {'const': 'irrep'}, 'label': {'enum': list(LABELS)}}),
        obj({'op': {'const': 'virtual'}, 'coefficients': _sparse(MAX_INPUT_COEFFICIENT)}),
        obj({'op': {'const': 'symmetric_power'},
             'degree': {'type': 'integer', 'minimum': 0, 'maximum': 256}}),
        obj({'op': {'enum': ['add', 'subtract', 'tensor']},
             'left': {'$ref': '#/$defs/expression'}, 'right': {'$ref': '#/$defs/expression'}})],
        'description': ('Only fixed physical labels; A and V, and W and Wp, are distinct. '
                        'Symmetric power means Sym^degree(W) only. Runtime enforces at most '
                        '127 expression occurrences and depth 16, including repeated shared objects.')}
    request = obj({'schema': {'const': 'fm-character-request-v1'},
        'expression': {'$ref': '#/$defs/expression'},
        'expectation': obj({'classification': {'enum': ['any', 'genuine', 'proper_virtual']},
            'equals': {'oneOf': [{'type': 'null'}, _sparse(MAX_RESULT_COEFFICIENT)]}})})
    request['description'] = ('Bounded exact integral virtual-character arithmetic in one fixed table, with '
        'class values in Q(sqrt(5)). Input is at most 65536 bytes including canonical ASCII JSON. '
        'Runtime rejects nonplain Python data, booleans, floating-point and noninteger numeric tokens, '
        'duplicate keys, and unmet expectations. Schema validity does not establish these conditions.')
    result = obj({'multiplicities': array(_integer(MAX_RESULT_COEFFICIENT), 9, 9),
        'dimension': _integer(30 * MAX_RESULT_COEFFICIENT),
        'classification': {'enum': ['genuine', 'proper_virtual']},
        'center_parity': {'enum': ['zero', 'even', 'odd', 'mixed']},
        'even_dimension': _integer(30 * MAX_RESULT_COEFFICIENT),
        'odd_dimension': _integer(30 * MAX_RESULT_COEFFICIENT),
        'negative_multiplicities': _sparse(MAX_RESULT_COEFFICIENT, negative=True)})
    result['description'] = ('Multiplicities are ordered 1,W,A,S4,D,T6,P,Wp,V. Dimensions and parity '
        'subtotals are signed, not evidence of genuineness. Genuine means all multiplicities are '
        'nonnegative, including zero; proper_virtual has a negative multiplicity. Center parity is '
        'based on nonzero support. Runtime recomputes every field; the schema does not prove agreement.')
    field_value = {'type': 'array', 'minItems': 4, 'maxItems': 4,
        'prefixItems': [_integer(MAX_FIELD_COMPONENT), _integer(MAX_FIELD_COMPONENT, minimum=1),
                        _integer(MAX_FIELD_COMPONENT), _integer(MAX_FIELD_COMPONENT, minimum=1)],
        'items': False,
        'description': ('Exact a+b*sqrt(5) as [a_num,a_den,b_num,b_den]. Runtime requires reduced '
                        'fractions and positive denominators; zero is [0,1,0,1].')}
    certificate = obj({'schema': {'const': 'fm-character-certificate-v1'},
        'catalog_sha256': {'const': CATALOG_SHA256}, 'request_sha256': DIGEST,
        'request': {'$ref': '#/$defs/request'}, 'result': {'$ref': '#/$defs/character_result'},
        'class_values': array({'$ref': '#/$defs/field_value'}, 9, 9), 'scope': {'const': SCOPE}})
    certificate['description'] = ('Certificate data only: schema conformance is not verification. The independent '
        'verifier revalidates the separately supplied expected request, reevaluates the fixed table over '
        'Q(sqrt(5)), and compares the entire canonical certificate. Runtime enforces 262144 canonical bytes, '
        '8192 certificate data values and depth 32. Hashes bind bytes, not truth or authenticity.')
    verification = obj({'schema': {'const': 'fm-character-verification-v1'},
        'status': {'const': 'verified_arithmetic'}, 'catalog_sha256': {'const': CATALOG_SHA256},
        'request_sha256': DIGEST, 'certificate_sha256': DIGEST,
        'result': {'$ref': '#/$defs/character_result'}, 'scope': {'const': SCOPE},
        'runtime_acceptance': {'const': False}, 'lean_proof': {'const': False}})
    return {'expression': expression, 'request': request, 'character_result': result,
            'field_value': field_value, 'certificate': certificate, 'verification': verification}


def _input(check):
    fields = {'request': {'$ref': '#/$defs/request'}}
    if check:
        fields['certificate'] = {'$ref': '#/$defs/certificate'}
    return {'$schema': DRAFT, **obj(fields), '$defs': _defs()}


def _output(check):
    common = {'schema_version': {'const': 1}, 'scope': {'const': SCOPE},
        'computational_field': {'const': 'Q(sqrt(5))'}, 'formal_proof': {'const': False},
        'runtime_goal_acceptance': {'const': False}, 'table_group_identification_assumed': {'const': True},
        'geometric_realization': {'const': False}}
    result = {'verification': {'$ref': '#/$defs/verification'}}
    if not check:
        result['certificate'] = {'$ref': '#/$defs/certificate'}
    success = obj({**common, 'status': {'const': 'success'},
        'operation': {'const': 'verify' if check else 'calculate'}, 'request_sha256': DIGEST,
        'implementation': obj({'name': {'const': 'foundation-math-fixed-character-ring'},
            'version': {'const': '0.9.0-dev'},
            'source_sha256': obj({name: DIGEST for name in IMPLEMENTATION_FILES})}),
        'result': obj(result)})
    error = obj({**common, 'status': {'const': 'error'}, 'error': obj({
        'code': {'enum': list(ERROR_CODES)}, 'message': {'type': 'string'}})})
    assessment = 'fixed_character_certificate_valid' if check else 'fixed_character_arithmetic_checked'
    schema = obj({'tool': {'const': CHECK if check else CALCULATE},
        'assessment': {'enum': [assessment, 'tool_error']}, 'formal_proof': {'const': False},
        'runtime_goal_acceptance': {'const': False}, 'receipt': {'oneOf': [success, error]}})
    schema['allOf'] = [{'if': {'properties': {'receipt': {'properties': {'status': {'const': 'success'}}}}},
        'then': {'properties': {'assessment': {'const': assessment}}},
        'else': {'properties': {'assessment': {'const': 'tool_error'}}}}]
    return {'$schema': DRAFT, **schema, '$defs': _defs()}


def tool_definitions():
    scope = (' Only universal integral virtual-character arithmetic in a pinned fixed table, '
        'with exact class values in Q(sqrt(5)). The physical labels A/V and W/Wp remain distinct. '
        'Identification of this table with the stated group is an assumption, not a proved output. '
        'Genuine means nonnegative multiplicities, including zero, not geometric realization. '
        'No actual geometric/source instances, arbitrary theorem refutation, formal proof, Lean check '
        'or runtime goal acceptance. Expression limits: 127 nodes, depth 16, Sym^n(W) for 0<=n<=256; '
        'input coefficients <=2^63-1 in magnitude, intermediate/result coefficients <=2^256-1. '
        'Exact field components <=272 bits; request/certificate canonical byte limits 65536/262144. '
        'Bridge frame limits remain 65536 input bytes, 1048576 output bytes and 16384 JSON nodes; '
        'a standalone-valid certificate can exceed bridge limits. No caller-selected bounds, paths, '
        'code, commands or group tables. Failure and budget exhaustion carry no mathematical outcome. '
        'Schemas are structural, not arithmetic verification; hashes bind bytes, not authenticity. '
        'This is bounded deterministic software arithmetic, not an OS sandbox or hard wall-clock quota.')
    return deepcopy([
        {'name': CALCULATE, 'description': 'Produce a certificate and independently verify it against the supplied original request.' + scope,
         'inputSchema': _input(False), 'outputSchema': _output(False), 'readOnly': True},
        {'name': CHECK, 'description': 'Freshly check a certificate against the separately supplied original expected request. '
         'The verifier does not import the producer or its request parser. Certificate or expectation failure is '
         'isError=true with assessment=tool_error, never partial acceptance.' + scope,
         'inputSchema': _input(True), 'outputSchema': _output(True), 'readOnly': True},
    ])
