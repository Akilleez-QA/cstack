"""Closed structural exterior schemas; exact arithmetic and aggregate guards are runtime checks."""
from copy import deepcopy

LABELS = ('1', 'W', 'A', 'S4', 'D', 'T6', 'P', 'Wp', 'V')
SCOPE = 'formal_exterior_representation_and_supplied_split_bundle_arithmetic_only'
ASSUMPTIONS = {'group': 'SL2(F5) over C', 'physical_catalog': 'fixed_identification_assumed_not_proved',
    'base': 'P(W) with standard O(1) linearization', 'splitting': 'caller_supplied_formal_equivariant_direct_sum',
    'maps': 'no_actual_map_rank_injectivity_or_existence_claim', 'proof': 'not_Lean_or_runtime_acceptance'}
DRAFT = 'https://json-schema.org/draft/2020-12/schema'


def obj(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def integer(lo=-(2**256-1), hi=2**256-1):
    return {'type': 'integer', 'minimum': lo, 'maximum': hi}


def array(item, maximum, minimum=0):
    return {'type': 'array', 'items': item, 'minItems': minimum, 'maxItems': maximum}


def sparse(positive=True):
    return {'type': 'object', 'properties': {k: integer(1 if positive else -(2**256-1)) for k in LABELS},
            'additionalProperties': False, 'maxProperties': 9}


def request_schema():
    block = obj({'irrep': {'enum': list(LABELS)}, 'twist': integer(-16,16), 'multiplicity': integer(1,24)})
    bundle = array(block,12)
    common = {'schema': {'const': 'fm-exterior-request-v1'}, 'orders': {**array(integer(0,25),26,1), 'uniqueItems': True}}
    representation = sparse();representation['properties'] = {k:integer(1,24) for k in LABELS}
    return {'oneOf': [obj({**common, 'operation': {'const': 'representation'}, 'representation': representation}),
        obj({**common, 'operation': {'const': 'bundle'}, 'bundle': bundle}),
        obj({**common, 'operation': {'const': 'wedge_h0_comparison'}, 'source': bundle, 'target': bundle,
             'twists': {**array(integer(-16,16),8,1), 'uniqueItems': True}})]}


def certificate_schema():
    parity = {'enum': ['zero','even','odd','mixed']}
    field = {'type': 'array', 'minItems':4, 'maxItems':4,
             'prefixItems':[integer(),integer(1),integer(),integer(1)], 'items':False}
    char = obj({'multiplicities': sparse(), 'dimension': integer(0), 'module_center_parity': parity,
                'class_values': array(field,9,9)})
    determinant = obj({'module': {'const': {'1':1}}, 'line_degree': integer()})
    stats = obj({'rank':integer(0),'degree':integer(),'determinant':determinant})
    bundle = obj({'terms':array(obj({'line_degree':integer(-384,384),'character':char,'bundle_center_parity':parity}),8192),
                  'rank':integer(0),'degree':integer(),'bundle_center_parity':parity,'determinant':determinant})
    result = {'oneOf':[
        obj({'operation':{'const':'representation'},'input_dimension':integer(0,24),
             'powers':array(obj({'order':integer(0,25),'character':char}),26,1)}),
        obj({'operation':{'const':'bundle'},'input':stats,'powers':array(obj({'order':integer(0,25),'bundle':bundle}),26,1)}),
        obj({'operation':{'const':'wedge_h0_comparison'},'source':stats,'target':stats,
             'comparisons':array(obj({'order':integer(0,25),'twist':integer(-16,16),'source_h0':char,'target_h0':char,
                                     'target_minus_source':sparse(False),'multiplicity_test':{'enum':['passes','obstructed']}}),208,1),
             'conclusion':{'const':'finite_necessary_tests_only_not_sufficient_for_any_map_or_injection'}})]}
    return obj({'schema':{'const':'fm-exterior-certificate-v1'},
                'catalog_sha256':{'const':'84ceb37bc32d10c4908e5b5f1f2f5994082074f2c2a9f36c846347750c79fa74'},
                'request_sha256':{'type':'string','pattern':'^[0-9a-f]{64}$','maxLength':64},
                'request':request_schema(),'result':result,'scope':{'const':SCOPE},'assumptions':{'const':ASSUMPTIONS}})


def tool_definitions():
    verification = obj({'status':{'const':'verified'},'scope':{'const':SCOPE},
        'request_sha256':{'type':'string','pattern':'^[0-9a-f]{64}$','maxLength':64},
        **{k:{'const':False} for k in ('runtime_acceptance','lean_proof','geometric_realization','map_existence_or_injectivity')}})
    common = {'schema_version':{'const':1},'scope':{'const':'formal_exterior_arithmetic_only'},
              **{k:{'const':False} for k in ('formal_proof','runtime_goal_acceptance','geometric_realization','map_existence_or_injectivity')},
              **{k:{'const':True} for k in ('table_group_identification_assumed','supplied_splitting_assumed')}}
    tools=[]
    for check in (False,True):
        name = 'check_formal_exterior_certificate' if check else 'calculate_formal_exterior'
        assessment = 'formal_exterior_certificate_valid' if check else 'formal_exterior_arithmetic_checked'
        args = {'request':request_schema()};result={'verification':verification}
        if check:args['certificate']=certificate_schema()
        else:result['certificate']=certificate_schema()
        success=obj({**common,'status':{'const':'success'},'operation':{'const':'verify' if check else 'calculate'},'result':obj(result)})
        error=obj({**common,'status':{'const':'error'},'error':obj({'code':{'type':'string'},'message':{'type':'string'}})})
        output=obj({'tool':{'const':name},'assessment':{'enum':[assessment,'tool_error']},
                    'formal_proof':{'const':False},'runtime_goal_acceptance':{'const':False},'receipt':{'oneOf':[success,error]}})
        output['allOf']=[{'if':{'properties':{'receipt':{'properties':{'status':{'const':'success'}}}}},
                          'then':{'properties':{'assessment':{'const':assessment}}},
                          'else':{'properties':{'assessment':{'const':'tool_error'}}}}]
        tools.append({'name':name,'readOnly':True,'description':
          'Exact bounded formal exterior representation/supplied split-bundle arithmetic, independently checked by Adams/Newton. '
          'Fixed physical SL2(F5) identification assumed. Comparison twist applies AFTER wedge. Finite necessary comparison only; '
          'not actual geometry, map existence/injectivity, all-twist theorem, Lean proof or runtime acceptance. '
          'Bridge keeps 65536-byte input and 1048576-byte output limits. Certificates must fit a compact ASCII verifier '
          'request including the original request and a maximally escaped legal id, and every existing node/depth/string guard; '
          'oversized results are wholly rejected, never truncated. Standalone CLI limits are separate. No caller budgets.',
          'inputSchema':{'$schema':DRAFT,**obj(args)},'outputSchema':{'$schema':DRAFT,**output}})
    return deepcopy(tools)
