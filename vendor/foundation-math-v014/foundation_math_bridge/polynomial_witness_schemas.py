"""Append-only v0.7 schemas; no edits to the six inherited tool contracts."""
from copy import deepcopy

DRAFT = 'https://json-schema.org/draft/2020-12/schema'
NAME = {'type': 'string', 'pattern': r'^[A-Za-z][A-Za-z0-9_]{0,31}(?![\s\S])'}
INTEGER = {'type': 'integer'}
STRING = {'type': 'string'}
DIGEST = {'type': 'string', 'pattern': r'^[0-9a-f]{64}(?![\s\S])'}

def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}

def arr(items, maximum, minimum=0):
    return {'type': 'array', 'items': items, 'minItems': minimum, 'maxItems': maximum}

def natural(maximum):
    return {'type': 'integer', 'minimum': 0, 'maximum': maximum}

def ref(name):
    return {'$ref': '#/$defs/' + name}

def _defs(polynomial_schema):
    definitions = deepcopy(polynomial_schema['$defs'])
    request = {key: deepcopy(value) for key, value in polynomial_schema.items() if key not in ('$schema', '$defs')}
    definitions['polynomial_request'] = request
    definitions['rational_value'] = obj({'numerator': INTEGER, 'denominator': {'type': 'integer', 'minimum': 1}})
    definitions['ring'] = obj({'kind': {'const': 'commutative_polynomial_ring'}, 'coefficient_field': {'const': 'Q'},
                               'variables': {**arr(NAME, 8), 'uniqueItems': True}})
    definitions['assignment'] = {'type': 'object', 'propertyNames': NAME, 'maxProperties': 8, 'additionalProperties': natural(32),
                                 'description': 'Runtime requires exactly the original declared variables and plain integer tokens.'}
    definitions['witness'] = obj({'schema_version': {'const': '1.0'}, 'input_sha256': DIGEST, 'request_sha256': DIGEST,
        'ring': ref('ring'), 'assignment': ref('assignment'), 'left_value': ref('rational_value'),
        'right_value': ref('rational_value'), 'difference_value': ref('rational_value')})
    definitions['witness']['description'] = ('Fresh checker requires reduced rational values, matching original input/request hashes and ring, '
        'and recomputes both original AST values and a nonzero left-minus-right. Schema validity alone is not verification.')
    definitions['trial'] = obj({'value': natural(32), 'remaining_nonzero': {'type': 'boolean'}})
    definitions['trace_step'] = obj({'variable': NAME, 'initial_degree': natural(32), 'current_degree': natural(32),
        'candidate_min': {'const': 0}, 'candidate_max': natural(32), 'chosen_value': natural(32), 'trials': arr(ref('trial'), 33, 1)})
    definitions['identity'] = obj({'kind': {'const': 'coefficient_identity'}, 'equal': {'const': True},
        'normalized_difference': obj({'terms': arr({}, 0), 'total_degree': {'type': 'null'}}), 'conclusion': STRING})
    definitions['construction_bound'] = obj({'kind': {'const': 'normalizer_total_degree_cap'},
        'variable_count': natural(8), 'normalizer_total_degree_cap': {'const': 32},
        'substitution_trial_bound': {'type': 'integer', 'minimum': 32, 'maximum': 40},
        'actual_substitution_trials': natural(40), 'sum_chosen_coordinates': natural(32),
        'legacy_hard_trial_cap': {'const': 264}, 'exact_difference_degree_recomputed': {'const': False},
        'point_checker_certifies_bound': {'const': False}})
    definitions['counterexample'] = obj({'kind': {'const': 'nonzero_evaluation'}, 'equal': {'const': False},
        'witness': ref('witness'), 'construction_trace': arr(ref('trace_step'), 8),
        'current_degree_trial_bound': natural(264), 'initial_degree_trial_bound': natural(264),
        'difference_term_count': {'type': 'integer', 'minimum': 1, 'maximum': 256}})
    source_keys = ('_vendor/polynomial.py', '_vendor/calculator.py', 'contract.py')
    definitions['point_verification'] = obj({'schema_version': {'const': '1.0'}, 'status': {'const': 'accepted'},
        'input_sha256': DIGEST, 'request_sha256': DIGEST, 'ring': ref('ring'), 'assignment': ref('assignment'),
        'left_value': ref('rational_value'), 'right_value': ref('rational_value'), 'difference_value': ref('rational_value'),
        'usage': obj({'evaluation_nodes': natural(4096)}),
        'source_sha256': obj({name: DIGEST for name in (*source_keys, 'checker.py')}),
        'scope': obj({'claim': STRING, 'not_checked': arr(STRING, 4, 4), 'formal_proof': {'const': False}, 'independence': STRING})})
    common_producer = {'schema_version': {'const': '1.0'}, 'status': {'const': 'success'},
        'request': ref('polynomial_request'), 'input_sha256': DIGEST, 'request_sha256': DIGEST, 'ring': ref('ring'),
        'limits': obj({'max_trials': natural(264), 'max_substitution_term_visits': natural(100000),
                       'max_evaluation_nodes': natural(4096), 'max_value_bits': natural(4096)}),
        'scope': obj({'domain': STRING, 'evidence': STRING, 'exclusions': arr(STRING, 5, 5),
                      'resource_semantics': STRING, 'trace_semantics': STRING}),
        'source_sha256': obj({name: DIGEST for name in (*source_keys, 'producer.py')}),
        'usage': obj({'normalization_ast_nodes': natural(1024), 'normalization_arithmetic_steps': natural(100000),
                       'substitution_trials': natural(264), 'substitution_term_visits': natural(100000)})}
    definitions['identity_receipt'] = obj({**common_producer, 'result': ref('identity'),
        'verification': obj({'status': {'const': 'not_applicable'}, 'scope': STRING})})
    definitions['counterexample_receipt'] = obj({**common_producer, 'result': ref('counterexample'),
                                                'verification': ref('point_verification')})
    return definitions

COMMON = {'schema_version': {'const': 1}, 'scope': {'const': 'characteristic_zero_unrestricted_formal_polynomial'},
          'coefficient_field': {'const': 'Q'}, 'characteristic': {'const': 0},
          'formal_proof': {'const': False}, 'runtime_goal_acceptance': {'const': False}}
SOURCES = ('polynomial_witness/__init__.py', 'polynomial_witness/__main__.py',
           'polynomial_witness/api.py', 'polynomial_witness/checker.py', 'polynomial_witness/contract.py',
           'polynomial_witness/producer.py', 'polynomial_witness/_vendor/__init__.py',
           'polynomial_witness/_vendor/calculator.py', 'polynomial_witness/_vendor/polynomial.py',
           'foundation_math/polynomial_witness.py')

def _success(result, check, bounded=False):
    extra = {'construction_bound': ref('construction_bound')} if bounded else {}
    return obj({**COMMON, 'status': {'const': 'success'}, 'operation': {'const': 'verify' if check else 'construct'},
                'request_sha256': DIGEST, 'implementation': obj({'name': {'const': 'foundation-math-small-polynomial-witness'},
                 'version': STRING, 'source_sha256': obj({name: DIGEST for name in SOURCES})}), 'result': result, **extra})

def _output(definitions, check):
    name = 'check_polynomial_witness' if check else 'construct_polynomial_witness'
    common = {'tool': {'const': name}, 'formal_proof': {'const': False}, 'runtime_goal_acceptance': {'const': False}}
    error_fields = {'error': obj({'code': STRING, 'message': STRING}), 'conclusion': STRING}
    branches = [obj({**common, 'assessment': {'const': 'tool_error'},
                     'receipt': obj({**COMMON, 'status': {'const': 'error'}, **error_fields})})]
    if check:
        branches.extend([
            obj({**common, 'assessment': {'const': 'polynomial_witness_valid'}, 'receipt': _success(ref('point_verification'), True)}),
            obj({**common, 'assessment': {'const': 'polynomial_witness_rejected'},
                 'receipt': obj({**COMMON, 'status': {'const': 'rejected'}, 'operation': {'const': 'verify'}, **error_fields})})])
    else:
        for assessment, receipt in [('polynomial_coefficient_identity', 'identity_receipt'),
                                     ('polynomial_counterexample_constructed', 'counterexample_receipt')]:
            branches.append(obj({**common, 'assessment': {'const': assessment}, 'receipt': _success(ref(receipt), False, receipt == 'counterexample_receipt')}))
    return {'$schema': DRAFT, 'type': 'object', 'oneOf': branches, '$defs': deepcopy(definitions)}

SCOPE_DESCRIPTION = (
    ' Only unrestricted formal polynomials in ordered algebraically independent variables over Q, characteristic zero. '
    'No quotient rings, rational functions, finite fields, constraints or user-restricted loci. '
    'No formal-proof or runtime-goal acceptance. Resource failure is inconclusive, never absence of a witness. '
    'Successful construction uses at most n+degree(nonzero normalized difference) trials, hence <=n+32<=40. The retained 264 hard cap is a compatibility limit, not the tight theorem. No extra normalization is performed solely for bound metadata. '
    'Normalization: <=8 variables, degree/depth 32, 1024 AST nodes, 256 terms, 256-bit literal components, '
    '2048-bit coefficients and 100000 arithmetic steps. Sequential construction: <=264 substitution trials, '
    '100000 term visits and 4096-bit evaluation values. Fresh checker: <=4096 AST nodes, no normalization required. '
    'Combined standalone request <=262144 bytes; bridge frame <=65536 bytes and output <=1048576 bytes. '
    'A standalone-valid request or witness may not fit the bridge. No caller-selected limits, paths, source, commands or model. '
    'Hashes bind content, not authenticity. Shared parser, Fraction arithmetic and runtime remain trusted.')

def tool_definitions(polynomial_schema):
    definitions = _defs(polynomial_schema)
    tools = []
    for check in (False, True):
        properties = {'request': ref('polynomial_request')}
        if check:
            properties['witness'] = ref('witness')
        description = (
            'Freshly check a small integer witness against the separately supplied ORIGINAL formal polynomial identity. '
            'Recompute original AST left/right/difference values exactly, require nonzero mismatch and bind ring and input hashes. '
            'Accepts any truthful point in 0..32, not only producer-minimal points. Does not certify trace, degree bounds or identity. '
            'Rejected supplied witnesses return isError=false and polynomial_witness_rejected; resource errors return isError=true.'
            if check else
            'Construct and freshly check a concrete integer point disproving a false formal Q-polynomial identity. '
            'Exact normalization to zero reports polynomial_coefficient_identity, not failed search; that identity branch is not point-certified. '
            'For nonzero residuals try 0..current degree in each variable and keep the first nonzero residual. '
            'At most the SUM of current degrees plus one per variable, not Cartesian-grid enumeration or a general runtime complexity claim. '
            'Return exact point, left/right/mismatch values and producer-only per-variable trace; each constructed coordinate <=32.')
        tools.append({'name': 'check_polynomial_witness' if check else 'construct_polynomial_witness',
                      'description': description + SCOPE_DESCRIPTION,
                      'inputSchema': {'$schema': DRAFT, **obj(properties), '$defs': deepcopy(definitions)},
                      'outputSchema': _output(definitions, check), 'readOnly': True})
    return tools
