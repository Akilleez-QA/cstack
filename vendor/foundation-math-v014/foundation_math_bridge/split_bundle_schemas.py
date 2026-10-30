"""Append-only formal supplied-splitting JSON Schema 2020-12 contracts.

These are strict data shapes, not arithmetic proofs. Runtime separately enforces
exact built-in types, lexical JSON integers, duplicate-key rejection, canonical
rational encoding, byte/tree budgets, external request binding and every result.
"""
from copy import deepcopy

from .schemas import DRAFT, obj, array
from foundation_math.split_bundle import IMPLEMENTATION_FILES

CALCULATE = 'calculate_formal_split_bundle'
CHECK = 'check_formal_split_bundle_certificate'
LABELS = ('1', 'W', 'A', 'S4', 'D', 'T6', 'P', 'Wp', 'V')
SCOPE = 'formal_supplied_split_bundle_arithmetic_only'
CATALOG_SHA256 = '84ceb37bc32d10c4908e5b5f1f2f5994082074f2c2a9f36c846347750c79fa74'
ASSUMPTIONS = {
    'group': 'SL2(F5) over C',
    'catalog_identification': 'fixed_physical_marking_assumed_not_proved',
    'base': 'P(W) with determinant-one W and standard O(1) linearization',
    'splitting': 'supplied_formal_equivariant_direct_sum_assumed',
    'geometry': 'no_active_research_bundle_identification_or_map_rank_inference',
}
HOM_CONCLUSION = 'dimension_of_equivariant_map_space_only_no_map_rank_or_embedding_claim'
MAX_RESULT_COEFFICIENT = (1 << 128) - 1
MAX_FIELD_COMPONENT = (1 << 300) - 1
MAX_RANK = 32 * 6 * 1000000
DIGEST = {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'}
ERROR_CODES = ('E_USAGE', 'E_IO', 'E_JSON', 'E_TYPE', 'E_SCHEMA', 'E_BUDGET',
               'E_CATALOG', 'E_CHARACTER', 'E_EXPECTATION', 'E_CERTIFICATE',
               'E_RIEMANN_ROCH', 'E_INTERNAL')


def _integer(minimum, maximum):
    return {'type': 'integer', 'minimum': minimum, 'maximum': maximum}


def _character(genuine=False):
    coefficient = _integer(0 if genuine else -MAX_RESULT_COEFFICIENT, MAX_RESULT_COEFFICIENT)
    dimension = _integer(0 if genuine else -30 * MAX_RESULT_COEFFICIENT, 30 * MAX_RESULT_COEFFICIENT)
    negative = {'type': 'object', 'propertyNames': {'enum': list(LABELS)},
                'maxProperties': 0 if genuine else 9,
                'additionalProperties': _integer(-MAX_RESULT_COEFFICIENT, -1)}
    shape = obj({'multiplicities': array(coefficient, 9, 9), 'dimension': dimension,
        'classification': {'const': 'genuine'} if genuine else {'enum': ['genuine', 'proper_virtual']},
        'center_parity': {'enum': ['zero', 'even', 'odd', 'mixed']},
        'even_dimension': dimension, 'odd_dimension': dimension,
        'negative_multiplicities': negative,
        'class_values': array({'$ref': '#/$defs/field_value'}, 9, 9)})
    if not genuine:
        shape['allOf'] = [{'if': {'properties': {'classification': {'const': 'genuine'}}},
            'then': {'properties': {
                'multiplicities': {'items': {'minimum': 0}},
                'dimension': {'minimum': 0}, 'even_dimension': {'minimum': 0},
                'odd_dimension': {'minimum': 0}, 'negative_multiplicities': {'maxProperties': 0}}},
            'else': {'properties': {'multiplicities': {'contains': {'type': 'integer', 'maximum': -1}},
                                    'negative_multiplicities': {'minProperties': 1}}}}]
    shape['description'] = ('Multiplicities use the exact order 1,W,A,S4,D,T6,P,Wp,V. H0, H1 and Hom '
        'are genuine; Euler can be proper virtual. Signed dimension zero need not mean a zero character. '
        'Runtime recomputes every field, including parity, negative support and exact class values; '
        'structural constraints do not prove those relationships or identify a geometric object.')
    return shape


def _defs():
    block = obj({'irrep': {'enum': list(LABELS)}, 'twist': _integer(-64, 64),
                 'multiplicity': _integer(0, 1000000)})
    bundle = array({'$ref': '#/$defs/block'}, 0, 32)
    bundle['description'] = ('A supplied formal direct-sum multiset, not a recognized geometric bundle. '
        'Empty bundles and zero multiplicities are allowed; duplicate blocks add, but all block order '
        'and redundant presentations remain part of the exact request binding.')
    cohomology_request = obj({'schema': {'const': 'fm-split-bundle-request-v1'},
        'operation': {'const': 'cohomology'}, 'bundle': {'$ref': '#/$defs/bundle'},
        'twists': {**array(_integer(-64, 64), 1, 32), 'uniqueItems': True}})
    hom_request = obj({'schema': {'const': 'fm-split-bundle-request-v1'},
        'operation': {'const': 'hom'}, 'source': {'$ref': '#/$defs/bundle'},
        'target': {'$ref': '#/$defs/bundle'}})
    request = {'oneOf': [cohomology_request, hom_request], 'description': (
        'Formal cohomology on P(W) or Hom from the supplied source to target. Twists are ordered. '
        'No actual object identification, map rank, embedding or kernel inference. All numbers must be '
        'exact built-in integers at runtime, not bool, float or coerced strings. JSON Schema integer '
        'semantics alone cannot enforce lexical or Python type restrictions. Request/certificate byte '
        'limits are 65536/262144, including canonical ASCII JSON; depth 16, 8192 data values, '
        '256-character strings/keys and 300-bit integer magnitudes are separately checked at runtime.')}
    statistics = obj({'rank': _integer(0, MAX_RANK), 'degree': _integer(-64 * MAX_RANK, 64 * MAX_RANK)})
    field_value = {'type': 'array', 'minItems': 4, 'maxItems': 4,
        'prefixItems': [_integer(-MAX_FIELD_COMPONENT, MAX_FIELD_COMPONENT), _integer(1, MAX_FIELD_COMPONENT),
                        _integer(-MAX_FIELD_COMPONENT, MAX_FIELD_COMPONENT), _integer(1, MAX_FIELD_COMPONENT)],
        'items': False, 'description': ('Exact a+b*sqrt(5), encoded [a_num,a_den,b_num,b_den]. '
            'Runtime enforces reduced fractions, positive denominators and canonical zero [0,1,0,1]. '
            'The schema bounds data components by the vendored 300-bit integer guard, not an arithmetic proof.')}
    row = obj({'twist': _integer(-64, 64), 'rank': _integer(0, MAX_RANK),
        'degree': _integer(-128 * MAX_RANK, 128 * MAX_RANK),
        'h0': {'$ref': '#/$defs/genuine_character'}, 'h1': {'$ref': '#/$defs/genuine_character'},
        'euler': {'$ref': '#/$defs/character'}})
    row['description'] = ('Degree is after twisting. H0/H1 depend on the supplied splitting, not merely '
        'its Euler character. Runtime independently verifies H0-H1 and signed Riemann-Roch; '
        'the schema does not infer vanishing from Euler data.')
    cohomology_result = obj({'operation': {'const': 'cohomology'},
        'bundle': {'$ref': '#/$defs/statistics'}, 'twists': array({'$ref': '#/$defs/cohomology_row'}, 1, 32)})
    hom_result = obj({'operation': {'const': 'hom'}, 'source': {'$ref': '#/$defs/statistics'},
        'target': {'$ref': '#/$defs/statistics'}, 'hom_character': {'$ref': '#/$defs/genuine_character'},
        'equivariant_hom_dimension': _integer(0, MAX_RESULT_COEFFICIENT),
        'conclusion': {'const': HOM_CONCLUSION}})
    hom_result['description'] = ('Hom-character dimension counts all sheaf maps; the trivial-irrep '
        'multiplicity counts equivariant maps. Neither quantity is a rank of any map, and no '
        'injectivity, surjectivity, embedding or existence of a map with prescribed rank follows.')
    result = {'oneOf': [cohomology_result, hom_result]}
    certificate = obj({'schema': {'const': 'fm-split-bundle-certificate-v1'},
        'catalog_sha256': {'const': CATALOG_SHA256}, 'request_sha256': DIGEST,
        'request': {'$ref': '#/$defs/request'}, 'result': {'$ref': '#/$defs/result'},
        'scope': {'const': SCOPE}, 'assumptions': obj({key: {'const': value} for key, value in ASSUMPTIONS.items()})})
    certificate['allOf'] = [{'if': {'properties': {'request': {'properties': {'operation': {'const': 'hom'}}}}},
        'then': {'properties': {'result': {'properties': {'operation': {'const': 'hom'}}}}},
        'else': {'properties': {'result': {'properties': {'operation': {'const': 'cohomology'}}}}}}]
    certificate['description'] = ('Certificate data only, not verified evidence. The independent checker '
        'revalidates a separately supplied expected request and recomputes the entire canonical '
        'certificate using exact class functions, without importing either producer or its request '
        'contract. Request hashes bind exact presentations and order, not only equivalent arithmetic. '
        'Hashes establish neither mathematical truth, provenance authenticity nor group identification.')
    verification = obj({'schema': {'const': 'fm-split-bundle-verification-v1'},
        'status': {'const': 'verified_arithmetic'}, 'catalog_sha256': {'const': CATALOG_SHA256},
        'request_sha256': DIGEST, 'certificate_sha256': DIGEST, 'result': {'$ref': '#/$defs/result'},
        'scope': {'const': SCOPE}, 'runtime_acceptance': {'const': False},
        'lean_proof': {'const': False}, 'geometric_realization': {'const': False}})
    return {'block': block, 'bundle': bundle, 'request': request, 'statistics': statistics,
        'field_value': field_value, 'character': _character(), 'genuine_character': _character(True),
        'cohomology_row': row, 'result': result, 'certificate': certificate, 'verification': verification}


def _input(check):
    fields = {'request': {'$ref': '#/$defs/request'}}
    if check:
        fields['certificate'] = {'$ref': '#/$defs/certificate'}
    return {'$schema': DRAFT, **obj(fields), '$defs': _defs()}


def _output(check):
    common = {'schema_version': {'const': 1}, 'scope': {'const': SCOPE},
        'computational_field': {'const': 'Q(sqrt(5))'}, 'formal_proof': {'const': False},
        'runtime_goal_acceptance': {'const': False}, 'table_group_identification_assumed': {'const': True},
        'supplied_splitting_assumed': {'const': True}, 'geometric_realization': {'const': False},
        'map_rank_claim': {'const': False}}
    result = {'verification': {'$ref': '#/$defs/verification'}}
    if not check:
        result['certificate'] = {'$ref': '#/$defs/certificate'}
    success = obj({**common, 'status': {'const': 'success'},
        'operation': {'const': 'verify' if check else 'calculate'}, 'request_sha256': DIGEST,
        'implementation': obj({'name': {'const': 'foundation-math-formal-split-bundle'},
            'version': {'const': '0.10.0-dev'},
            'source_sha256': obj({name: DIGEST for name in IMPLEMENTATION_FILES})}),
        'result': obj(result)})
    error = obj({**common, 'status': {'const': 'error'}, 'error': obj({
        'code': {'enum': list(ERROR_CODES)}, 'message': {'type': 'string'}})})
    assessment = 'formal_split_bundle_certificate_valid' if check else 'formal_split_bundle_arithmetic_checked'
    schema = obj({'tool': {'const': CHECK if check else CALCULATE},
        'assessment': {'enum': [assessment, 'tool_error']}, 'formal_proof': {'const': False},
        'runtime_goal_acceptance': {'const': False}, 'receipt': {'oneOf': [success, error]}})
    schema['allOf'] = [{'if': {'properties': {'receipt': {'properties': {'status': {'const': 'success'}}}}},
        'then': {'properties': {'assessment': {'const': assessment}}},
        'else': {'properties': {'assessment': {'const': 'tool_error'}}}}]
    return {'$schema': DRAFT, **schema, '$defs': _defs()}


def tool_definitions():
    scope = (' Formal supplied equivariant direct sums on P(W) only. The fixed physical table and '
        'the supplied splitting are assumptions, not proved object identifications. A is not V; W is '
        'not Wp. H0 and H1 are separately computed; Euler equality does not identify cohomology or '
        'splittings. Hom dimension is not map rank. No active research object identification, '
        'geometric realization, map-rank or embedding claim, formal proof, Lean check or runtime '
        'goal acceptance. Exact class values are in Q(sqrt(5)); no floating-point fallback. '
        'At most 32 blocks per bundle and 32 distinct requested twists; block/requested twists '
        'in [-64,64], multiplicity in [0,1000000], symmetric degree at most 128; result irreducible '
        'coefficients at most 128 bits. Request/certificate canonical byte limits 65536/262144, '
        'data depth 16, 8192 values, string/key length 256, integer magnitude 300 bits. '
        'Bridge limits remain 65536 input bytes, 1048576 output bytes and 16384 JSON nodes, so '
        'a standalone-valid certificate can exceed bridge limits. No caller-selected bounds, '
        'paths, code, commands, group tables, points or maps. Failure/budget exhaustion is '
        'inconclusive and carries no partial result. Schemas are data shapes, not arithmetic '
        'verification; hashes bind bytes, not truth or authenticity. Bounded deterministic '
        'software arithmetic is not an OS sandbox or hard wall-clock quota.')
    return deepcopy([
        {'name': CALCULATE, 'description': 'Produce a formal split-bundle certificate and independently check it '
            'against the supplied original request.' + scope,
         'inputSchema': _input(False), 'outputSchema': _output(False), 'readOnly': True},
        {'name': CHECK, 'description': 'Freshly check a certificate against the separately supplied expected '
            'request, without importing either producer or its request contract. Failure is '
            'isError=true with assessment=tool_error, never partial acceptance.' + scope,
         'inputSchema': _input(True), 'outputSchema': _output(True), 'readOnly': True},
    ])
