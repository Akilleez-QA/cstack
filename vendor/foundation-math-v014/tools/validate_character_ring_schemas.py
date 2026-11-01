"""Audit fixed-character JSON Schema contracts using preinstalled jsonschema only.

No installation or network is attempted. Structure and arithmetic verification
are deliberately separate: schema acceptance cannot certify mathematical truth.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from foundation_math.character_ring import calculate_character
from foundation_math_bridge.schemas import tool_definitions
from foundation_math_bridge.server import Bridge, PROTOCOL
from foundation_math_bridge.character_ring_schemas import CALCULATE, CHECK


def request(expression, classification='any', equals=None):
    return {'schema': 'fm-character-request-v1', 'expression': expression,
            'expectation': {'classification': classification, 'equals': equals}}


def main():
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print(json.dumps({'status': 'unavailable',
            'reason': 'No preinstalled jsonschema; no installation attempted.'}))
        return 2
    checks = 0

    def require(condition, label):
        nonlocal checks
        checks += 1
        if not condition:
            raise RuntimeError(label)

    definitions = {tool['name']: tool for tool in tool_definitions()}
    require(len(definitions) == 15, 'append-only fifteen-tool inventory')
    for tool in definitions.values():
        for key in ('inputSchema', 'outputSchema'):
            Draft202012Validator.check_schema(tool[key]); checks += 1
    bridge = Bridge()
    bridge.dispatch({'jsonrpc': '2.0', 'id': 0, 'method': 'initialize',
                     'params': {'protocolVersion': PROTOCOL}})

    def call(name, args):
        response = bridge.dispatch({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': name, 'arguments': args}})
        require('result' in response, 'valid bridge call did not return an envelope')
        content = response['result']['structuredContent']
        errors = list(Draft202012Validator(definitions[name]['outputSchema']).iter_errors(content))
        require(not errors, 'actual output violates schema: ' + '; '.join(error.message for error in errors[:2]))
        require(response['result']['isError'] == (content['receipt']['status'] == 'error'),
                'transport error flag disagrees with receipt')
        return content

    fixtures = [request({'op': 'irrep', 'label': 'W'}), request({'op': 'irrep', 'label': 'Wp'}),
        request({'op': 'irrep', 'label': 'A'}), request({'op': 'irrep', 'label': 'V'}),
        request({'op': 'virtual', 'coefficients': {}}, 'genuine', {}),
        request({'op': 'virtual', 'coefficients': {'A': 1, 'W': -1}}, 'proper_virtual'),
        request({'op': 'virtual', 'coefficients': {'A': 1, 'V': -1}}, 'proper_virtual'),
        request({'op': 'symmetric_power', 'degree': 256}),
        request({'op': 'tensor', 'left': {'op': 'irrep', 'label': 'P'},
                 'right': {'op': 'irrep', 'label': 'W'}}, 'genuine', {'T6': 1, 'Wp': 1})]
    for value in fixtures:
        certificate = calculate_character(value)['result']['certificate']
        for name in (CALCULATE, CHECK):
            args = {'request': value}
            if name == CHECK:
                args['certificate'] = certificate
            inp = Draft202012Validator(definitions[name]['inputSchema'])
            out = Draft202012Validator(definitions[name]['outputSchema'])
            require(inp.is_valid(args), 'good input rejected')
            actual = call(name, args)
            require(actual['receipt']['status'] == 'success', 'good request not successful')
            for key in ('limits', 'path', 'code', 'command', 'group', 'formal_proof'):
                require(not inp.is_valid({**args, key: True}), 'extra tool argument accepted')
                bad = deepcopy(args); bad['request'][key] = True
                require(not inp.is_valid(bad), 'extra request field accepted')
            for flag in ('formal_proof', 'runtime_goal_acceptance'):
                forged = deepcopy(actual); forged[flag] = True
                require(not out.is_valid(forged), 'envelope evidence promotion accepted')
            for key, replacement in [('formal_proof', True), ('runtime_goal_acceptance', True),
                                     ('geometric_realization', True), ('table_group_identification_assumed', False),
                                     ('scope', 'geometric_theorem'), ('computational_field', 'R')]:
                forged = deepcopy(actual); forged['receipt'][key] = replacement
                require(not out.is_valid(forged), 'receipt scope/evidence promotion accepted')
            for key, replacement in [('runtime_acceptance', True), ('lean_proof', True),
                                     ('scope', 'formal_proof'), ('status', 'theorem_proved')]:
                forged = deepcopy(actual); forged['receipt']['result']['verification'][key] = replacement
                require(not out.is_valid(forged), 'frozen verification promotion accepted')
            forged = deepcopy(actual); forged['assessment'] = 'tool_error'
            require(not out.is_valid(forged), 'successful receipt can have error assessment')
            forged = deepcopy(actual); forged['receipt']['request_sha256'] += '\n'
            require(not out.is_valid(forged), 'nonexact hash accepted')
            forged = deepcopy(actual); forged['receipt']['implementation']['source_sha256'].popitem()
            require(not out.is_valid(forged), 'missing implementation source hash accepted')
            if name == CHECK:
                forged = deepcopy(actual); forged['receipt']['result']['certificate'] = certificate
                require(not out.is_valid(forged), 'verification response contains producer certificate')
            else:
                forged = deepcopy(actual); forged['receipt']['result']['certificate']['scope'] = 'geometric_realization'
                require(not out.is_valid(forged), 'certificate scope promotion accepted')
            bad = deepcopy(args); bad['request']['expression'] = {'op': 'virtual', 'coefficients': {'W': True}}
            require(not inp.is_valid(bad), 'boolean coefficient accepted')
            failed = call(name, bad)
            require(failed['assessment'] == 'tool_error', 'invalid input not an error')
            for field in ('result', 'certificate'):
                forged = deepcopy(failed); forged['receipt'][field] = {'accepted': True}
                require(not out.is_valid(forged), 'error carries partial evidence')
            forged = deepcopy(failed); forged['assessment'] = actual['assessment']
            require(not out.is_valid(forged), 'error has success assessment')

    inp = Draft202012Validator(definitions[CALCULATE]['inputSchema'])
    check_inp = Draft202012Validator(definitions[CHECK]['inputSchema'])
    good = fixtures[0]
    for expression in [{'op': 'irrep', 'label': '3'}, {'op': 'irrep', 'label': 'A/V'},
                       {'op': 'virtual', 'coefficients': {'W': 0}},
                       {'op': 'virtual', 'coefficients': {'W': 1 << 63}},
                       {'op': 'symmetric_power', 'degree': -1},
                       {'op': 'symmetric_power', 'degree': 257},
                       {'op': 'symmetric_power', 'degree': 2, 'representation': 'Wp'},
                       {'op': 'eval', 'expression': 'W*W'}]:
        require(not inp.is_valid({'request': request(expression)}), 'invalid expression accepted by schema')
    # JSON Schema integers describe values, not lexical JSON tokens or exact
    # in-memory Python types. This limitation is explicit rather than hidden.
    decimal = request({'op': 'virtual', 'coefficients': {'W': 1.0}})
    require(inp.is_valid({'request': decimal}), 'JSON Schema integral-number semantics changed')
    require(call(CALCULATE, {'request': decimal})['receipt']['error']['code'] == 'E_TYPE',
            'runtime exact integer type not enforced')
    false_expectation = request({'op': 'irrep', 'label': 'W'}, equals={'Wp': 1})
    require(inp.is_valid({'request': false_expectation}), 'schema unexpectedly evaluates expectations')
    require(call(CALCULATE, {'request': false_expectation})['receipt']['error']['code'] == 'E_EXPECTATION',
            'runtime expectation not enforced')
    deep = {'op': 'irrep', 'label': '1'}
    for _ in range(16):
        deep = {'op': 'add', 'left': deep, 'right': {'op': 'virtual', 'coefficients': {}}}
    require(inp.is_valid({'request': request(deep)}), 'schema unexpectedly enforces dynamic depth')
    require(call(CALCULATE, {'request': request(deep)})['receipt']['error']['code'] == 'E_BUDGET',
            'runtime depth not enforced')
    certificate = calculate_character(good)['result']['certificate']
    for kind in ('dimension', 'noncanonical_fraction', 'binding'):
        bad = deepcopy(certificate)
        if kind == 'dimension': bad['result']['dimension'] += 1
        elif kind == 'noncanonical_fraction': bad['class_values'][0] = [4, 2, 0, 1]
        else: bad['request_sha256'] = '0' * 64
        args = {'request': good, 'certificate': bad}
        require(check_inp.is_valid(args), 'structural schema unexpectedly verifies ' + kind)
        rejected = call(CHECK, args)
        require(rejected['receipt']['error']['code'] == 'E_CERTIFICATE', 'runtime fails to verify ' + kind)
    # A distinct expression with identical arithmetic still needs its own binding.
    same_value = request({'op': 'add', 'left': {'op': 'irrep', 'label': 'W'},
                          'right': {'op': 'virtual', 'coefficients': {}}})
    require(check_inp.is_valid({'request': same_value, 'certificate': certificate}), 'structure enforces hash equality')
    require(call(CHECK, {'request': same_value, 'certificate': certificate})['receipt']['error']['code'] == 'E_CERTIFICATE',
            'external request substitution accepted')
    names = ['foundation_math_bridge/character_ring_schemas.py', 'tools/validate_character_ring_schemas.py']
    print(json.dumps({'status': 'passed', 'checks': checks, 'optimization': sys.flags.optimize,
        'dependency': 'Preinstalled jsonschema only; no install or runtime dependency.',
        'source_sha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in names},
        'scope': 'Structural schemas and runtime semantic rejection are distinct; no formal proof, group identification or runtime goal acceptance.'},
        indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
