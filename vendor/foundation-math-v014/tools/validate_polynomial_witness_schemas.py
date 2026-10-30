"""Optional preinstalled JSON Schema validator; no install or runtime dependency."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from foundation_math_bridge.schemas import tool_definitions
from foundation_math_bridge.server import Bridge, PROTOCOL

def main():
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print(json.dumps({'status': 'unavailable', 'reason': 'Optional preinstalled jsonschema not available; no installation attempted.'}))
        return 2
    checks = 0
    def require(condition, label):
        nonlocal checks
        checks += 1
        if not condition:
            raise RuntimeError(label)
    bridge = Bridge()
    bridge.dispatch({'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL}})
    definitions = {t['name']: t for t in tool_definitions()}
    for tool in definitions.values():
        for name in ('inputSchema', 'outputSchema'):
            Draft202012Validator.check_schema(tool[name]); checks += 1
    def invoke(name, arguments):
        response = bridge.dispatch({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                                    'params': {'name': name, 'arguments': arguments}})
        content = response['result']['structuredContent']
        errors = list(Draft202012Validator(definitions[name]['outputSchema']).iter_errors(content))
        require(not errors, 'actual output violates schema: ' + '; '.join(str(e.message) for e in errors[:2]))
        return content
    construct = 'construct_polynomial_witness'; check = 'check_polynomial_witness'
    request = json.loads((ROOT / 'examples/polynomial-witness/false-square.json').read_text())
    accepted = invoke(construct, {'request': request})
    witness = accepted['receipt']['result']['result']['witness']
    for name, args in ((construct, {'request': request}), (check, {'request': request, 'witness': witness})):
        validator = Draft202012Validator(definitions[name]['inputSchema'])
        require(validator.is_valid(args), 'valid input rejected by advertised schema')
        for field in ('path', 'limits', 'command', 'backend', 'formal_proof'):
            require(not validator.is_valid({**args, field: True}), 'unexpected outer field allowed')
        bad = deepcopy(args); bad['request']['coefficient_field'] = 'F2'
        require(not validator.is_valid(bad), 'finite field accepted structurally')
        bad = deepcopy(args); bad['request']['constraints'] = []
        require(not validator.is_valid(bad), 'constraints allowed structurally')
    for fixture in ('true-distributivity', 'zero-variable-zero', 'zero-variable-false-constant',
                    'unused-variables', 'degree-32-many-roots', 'eight-variable-sparse-product',
                    'rejected-degree-limit', 'rejected-constraints', 'rejected-finite-field', 'rejected-division'):
        invoke(construct, {'request': json.loads((ROOT / f'examples/polynomial-witness/{fixture}.json').read_text())})
    invoke(check, {'request': request, 'witness': witness})
    for field, value in (('difference_value', {'numerator': 0, 'denominator': 1}), ('assignment', {'x': 0, 'y': 0}),
                         ('input_sha256', '0'*64), ('extra', True)):
        bad = deepcopy(witness); bad[field] = value
        rejected = invoke(check, {'request': request, 'witness': bad})
        require(rejected['assessment'] == 'polynomial_witness_rejected', 'invalid witness not rejected')
    invoke(check, {'request': {}, 'witness': witness})
    for flag in ('formal_proof', 'runtime_goal_acceptance'):
        bad = deepcopy(accepted); bad[flag] = True
        require(not Draft202012Validator(definitions[construct]['outputSchema']).is_valid(bad), 'envelope promotion allowed')
        bad = deepcopy(accepted); bad['receipt'][flag] = True
        require(not Draft202012Validator(definitions[construct]['outputSchema']).is_valid(bad), 'receipt promotion allowed')
    for field in ('exact_difference_degree_recomputed', 'point_checker_certifies_bound'):
        bad = deepcopy(accepted); bad['receipt']['construction_bound'][field] = True
        require(not Draft202012Validator(definitions[construct]['outputSchema']).is_valid(bad), 'bound metadata overclaim allowed')
    for wrong_cap in (31, 33):
        bad = deepcopy(accepted); bad['receipt']['construction_bound']['normalizer_total_degree_cap'] = wrong_cap
        require(not Draft202012Validator(definitions[construct]['outputSchema']).is_valid(bad), 'wrong normalizer cap allowed')
    identity = invoke(construct, {'request': json.loads((ROOT / 'examples/polynomial-witness/zero-variable-zero.json').read_text())})
    identity['receipt']['construction_bound'] = accepted['receipt']['construction_bound']
    require(not Draft202012Validator(definitions[construct]['outputSchema']).is_valid(identity), 'identity carries nonzero construction bound')
    bad = deepcopy(accepted); bad['assessment'] = 'polynomial_coefficient_identity'
    require(not Draft202012Validator(definitions[construct]['outputSchema']).is_valid(bad), 'wrong semantic branch allowed')
    print(json.dumps({'status': 'passed', 'checks': checks, 'optimization': sys.flags.optimize,
                      'scope': 'Structural schemas and actual synthetic branches only; schema conformance is not mathematical verification.',
                      'dependency': 'Already-installed jsonschema; no install or runtime dependency.',
                      'source_sha256': {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest() for p in
                                        [ROOT/'foundation_math_bridge/polynomial_witness_schemas.py', ROOT/'tools/validate_polynomial_witness_schemas.py']}}, indent=2, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
