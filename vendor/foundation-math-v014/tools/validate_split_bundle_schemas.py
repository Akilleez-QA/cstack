"""Audit formal split-bundle data contracts with preinstalled jsonschema only.

No install or network is attempted. Successful structural validation does not
verify arithmetic, identify objects, prove table markings or establish geometry.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from foundation_math.split_bundle import calculate_split_bundle
from foundation_math_bridge.schemas import tool_definitions
from foundation_math_bridge.server import Bridge, PROTOCOL
from foundation_math_bridge.split_bundle_schemas import (CALCULATE, CHECK, ASSUMPTIONS,
    CATALOG_SHA256, LABELS, SCOPE, MAX_RANK, MAX_RESULT_COEFFICIENT, MAX_FIELD_COMPONENT, ERROR_CODES)


def block(irrep='1', twist=0, multiplicity=1):
    return {'irrep': irrep, 'twist': twist, 'multiplicity': multiplicity}


def coh(bundle=None, twists=None):
    return {'schema': 'fm-split-bundle-request-v1', 'operation': 'cohomology',
            'bundle': [block()] if bundle is None else bundle,
            'twists': [0] if twists is None else twists}


def hom(source, target):
    return {'schema': 'fm-split-bundle-request-v1', 'operation': 'hom', 'source': source, 'target': target}


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

    definitions = {item['name']: item for item in tool_definitions()}
    frozen = json.loads((ROOT / 'docs/BASE-V09-BRIDGE-TOOLS.json').read_text())['tools']
    require(len(definitions) == 15, 'fifteen-tool inventory')
    require(list(definitions.values())[:12] == frozen, 'twelve prior contracts changed')
    for definition in definitions.values():
        for key in ('inputSchema', 'outputSchema'):
            Draft202012Validator.check_schema(definition[key]); checks += 1
    # Check advertised constants against source, rather than making the schema
    # depend on the producer parser or pretending a copied pin proves identity.
    from split_bundle.contract import ASSUMPTIONS as SOURCE_ASSUMPTIONS, PIN, BUDGETS, LABELS as SOURCE_LABELS, SCOPE as SOURCE_SCOPE
    require(ASSUMPTIONS == SOURCE_ASSUMPTIONS, 'assumptions differ from vendored contract')
    require(CATALOG_SHA256 == PIN and LABELS == SOURCE_LABELS and SCOPE == SOURCE_SCOPE,
            'fixed labels, pin or scope differ from vendored source')
    require(MAX_RESULT_COEFFICIENT == (1 << BUDGETS['result_bits']) - 1, 'result coefficient bound')
    require(MAX_FIELD_COMPONENT == (1 << BUDGETS['integer_bits']) - 1, 'data integer bound')
    require(MAX_RANK == BUDGETS['blocks_per_bundle'] * 6 * BUDGETS['multiplicity'], 'rank bound')
    from foundation_math.split_bundle import ERROR_CODES as ADAPTER_CODES
    require(set(ERROR_CODES) == ADAPTER_CODES, 'error code allowlist differs')

    bridge = Bridge()
    bridge.dispatch({'jsonrpc': '2.0', 'id': 0, 'method': 'initialize',
                     'params': {'protocolVersion': PROTOCOL}})

    def call(name, args):
        response = bridge.dispatch({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': name, 'arguments': args}})
        require('result' in response, 'bridge result envelope absent')
        content = response['result']['structuredContent']
        errors = list(Draft202012Validator(definitions[name]['outputSchema']).iter_errors(content))
        require(not errors, 'actual output violates schema: ' + '; '.join(error.message for error in errors[:2]))
        require(response['result']['isError'] == (content['receipt']['status'] == 'error'),
                'transport error flag disagrees with receipt')
        return content

    fixtures = [coh(), coh([], [-64, -1, 0, 64]), coh([block('V', 64, 0)], [64]),
        coh([block('1', -10), block('1', -8), block('V', -8)], [8]),
        coh([block('1', 0), block('1', -2)], [-2, -1, 0, 1, 2]),
        coh([block('W', -1)], [-2, -1, 0, 1, 2]),
        coh([block('W'), block('1', -2, 2)]),
        coh([block('V', 0, 2), block('V', 0, 3)], [0]),
        coh([block('1', -64)], [-64]),
        hom([], []), hom([block('W', -3)], [block('W', -3)]),
        hom([block('A')], [block('V')]), hom([block('1', 1)], [block()]),
        hom([block('W', -64, 1000000)], [block('Wp', 64, 1000000)]),
        coh([block(LABELS[i % 9], 64, 1000000) for i in range(32)], list(range(33, 65)))]
    for value in fixtures:
        receipt = calculate_split_bundle(value)
        require(receipt['status'] == 'success', 'fixture not successful')
        certificate = receipt['result']['certificate']
        for name in (CALCULATE, CHECK):
            args = {'request': value}
            if name == CHECK:
                args['certificate'] = certificate
            inp = Draft202012Validator(definitions[name]['inputSchema'])
            out = Draft202012Validator(definitions[name]['outputSchema'])
            require(inp.is_valid(args), 'valid fixture rejected by input schema')
            actual = call(name, args)
            require(actual['receipt']['status'] == 'success', 'valid fixture rejected by runtime')
            for key in ('limits', 'path', 'code', 'command', 'group', 'point', 'map_rank', 'formal_proof'):
                require(not inp.is_valid({**args, key: True}), 'extra tool argument accepted')
                bad = deepcopy(args); bad['request'][key] = True
                require(not inp.is_valid(bad), 'extra request field accepted')
            for flag in ('formal_proof', 'runtime_goal_acceptance'):
                bad = deepcopy(actual); bad[flag] = True
                require(not out.is_valid(bad), 'envelope evidence promotion accepted')
            for key, replacement in [('formal_proof', True), ('runtime_goal_acceptance', True),
                    ('geometric_realization', True), ('map_rank_claim', True),
                    ('table_group_identification_assumed', False), ('supplied_splitting_assumed', False),
                    ('scope', 'geometric_theorem'), ('computational_field', 'R')]:
                bad = deepcopy(actual); bad['receipt'][key] = replacement
                require(not out.is_valid(bad), 'receipt promotion accepted: ' + key)
            for key, replacement in [('runtime_acceptance', True), ('lean_proof', True),
                    ('geometric_realization', True), ('scope', 'formal_proof'), ('status', 'theorem_proved')]:
                bad = deepcopy(actual); bad['receipt']['result']['verification'][key] = replacement
                require(not out.is_valid(bad), 'verification promotion accepted: ' + key)
            bad = deepcopy(actual); bad['assessment'] = 'tool_error'
            require(not out.is_valid(bad), 'success can have error assessment')
            bad = deepcopy(actual); bad['receipt']['request_sha256'] += '\n'
            require(not out.is_valid(bad), 'nonexact hash accepted')
            bad = deepcopy(actual); bad['receipt']['implementation']['source_sha256'].popitem()
            require(not out.is_valid(bad), 'missing implementation hash accepted')
            bad = deepcopy(actual); bad['receipt']['implementation']['source_sha256']['unexpected.py'] = '0' * 64
            require(not out.is_valid(bad), 'extra implementation hash accepted')
            if name == CHECK:
                bad = deepcopy(actual); bad['receipt']['result']['certificate'] = certificate
                require(not out.is_valid(bad), 'verification output includes producer certificate')
            else:
                for key in ASSUMPTIONS:
                    bad = deepcopy(actual); bad['receipt']['result']['certificate']['assumptions'][key] = 'proved'
                    require(not out.is_valid(bad), 'assumption promotion accepted')
                bad = deepcopy(actual); bad['receipt']['result']['certificate']['scope'] = 'geometric_realization'
                require(not out.is_valid(bad), 'certificate scope promotion accepted')
            failed_args = deepcopy(args); failed_args['request'] = coh([block(multiplicity=True)])
            require(not inp.is_valid(failed_args), 'boolean multiplicity accepted')
            failed = call(name, failed_args)
            require(failed['assessment'] == 'tool_error', 'invalid request not a tool error')
            for key in ('result', 'certificate', 'verification'):
                bad = deepcopy(failed); bad['receipt'][key] = {'accepted': True}
                require(not out.is_valid(bad), 'error carries partial evidence')
            bad = deepcopy(failed); bad['assessment'] = actual['assessment']
            require(not out.is_valid(bad), 'error has success assessment')

    inp = Draft202012Validator(definitions[CALCULATE]['inputSchema'])
    check_inp = Draft202012Validator(definitions[CHECK]['inputSchema'])
    invalid = [None, [], {}, coh([block('3')]), coh([block('A/V')]), coh([block('W/Wp')]),
        coh([block(multiplicity=-1)]), coh([block(multiplicity=1000001)]),
        coh([block(twist=-65)]), coh([block(twist=65)]), coh([block()] * 33),
        coh(twists=[]), coh(twists=[0, 0]), coh(twists=[-65]), coh(twists=[65]),
        coh(twists=[True]), coh(twists=list(range(33))),
        {**coh(), 'bundle': None}, {**coh(), 'twists': None},
        {**hom([], []), 'twists': [0]}, {**coh(), 'source': []}]
    for value in invalid:
        require(not inp.is_valid({'request': value}), 'invalid request accepted structurally')
        require(call(CALCULATE, {'request': value})['assessment'] == 'tool_error', 'invalid request accepted by runtime')
    for name in (CALCULATE, CHECK):
        pending = [definitions[name]]
        while pending:
            item = pending.pop()
            if isinstance(item, dict):
                if '$ref' in item:
                    require(item['$ref'].startswith('#/$defs/'), 'nonlocal schema reference')
                pending.extend(item.values())
            elif isinstance(item, list): pending.extend(item)

    good = coh(); certificate = calculate_split_bundle(good)['result']['certificate']
    decimal = coh([block(multiplicity=1.0)])
    require(inp.is_valid({'request': decimal}), 'JSON Schema integral-value semantics changed')
    require(call(CALCULATE, {'request': decimal})['receipt']['error']['code'] == 'E_TYPE',
            'runtime exact integer type not enforced')
    # Deliberately structurally valid false evidence demonstrates the boundary:
    # JSON Schema cannot recompute dimensions, fractions, hashes or bindings.
    for kind in ('dimension', 'noncanonical_fraction', 'binding', 'negative_support'):
        bad = deepcopy(certificate)
        if kind == 'dimension': bad['result']['twists'][0]['h0']['dimension'] += 1
        elif kind == 'noncanonical_fraction': bad['result']['twists'][0]['h0']['class_values'][0] = [2, 2, 0, 1]
        elif kind == 'binding': bad['request_sha256'] = '0' * 64
        else:
            bad['result']['twists'][0]['euler']['multiplicities'][0] = -1
            bad['result']['twists'][0]['euler']['classification'] = 'proper_virtual'
            bad['result']['twists'][0]['euler']['negative_multiplicities'] = {'V': -1}
        args = {'request': good, 'certificate': bad}
        require(check_inp.is_valid(args), 'schema unexpectedly verifies ' + kind)
        require(call(CHECK, args)['receipt']['error']['code'] == 'E_CERTIFICATE', 'runtime does not reject ' + kind)
    alternative = coh([block(), block(multiplicity=0)])
    require(check_inp.is_valid({'request': alternative, 'certificate': certificate}), 'schema unexpectedly binds request')
    require(call(CHECK, {'request': alternative, 'certificate': certificate})['receipt']['error']['code'] == 'E_CERTIFICATE',
            'equivalent result with substituted external request accepted')

    malformed = []
    for replacement in ([1, 0, 0, 1], [1, -1, 0, 1], [1, 1, 0], [1, 1, 0, 1, 0],
                        [True, 1, 0, 1], [1 << 300, 1, 0, 1]):
        bad = deepcopy(certificate); bad['result']['twists'][0]['h0']['class_values'][0] = replacement
        malformed.append(bad)
    for key, replacement in [('rank', MAX_RANK + 1), ('rank', -1), ('degree', 64 * MAX_RANK + 1)]:
        bad = deepcopy(certificate); bad['result']['bundle'][key] = replacement; malformed.append(bad)
    for key, replacement in [('multiplicities', [0] * 8), ('multiplicities', [0] * 10),
                            ('multiplicities', [-1] + [0] * 8), ('classification', 'proper_virtual'),
                            ('negative_multiplicities', {'1': -1}), ('center_parity', 'unknown')]:
        bad = deepcopy(certificate); bad['result']['twists'][0]['h0'][key] = replacement; malformed.append(bad)
    for path in [('assumptions',), ('result',), ('result', 'bundle'), ('result', 'twists', 0),
                 ('result', 'twists', 0, 'h0'), ('result', 'twists', 0, 'euler')]:
        bad = deepcopy(certificate); target = bad
        for part in path: target = target[part]
        target['unrequested'] = 1; malformed.append(bad)
    bad = deepcopy(certificate); del bad['assumptions']['splitting']; malformed.append(bad)
    bad = deepcopy(certificate); bad['request'] = hom([], []); malformed.append(bad)
    for bad in malformed:
        require(not check_inp.is_valid({'request': good, 'certificate': bad}), 'malformed certificate accepted structurally')
        require(call(CHECK, {'request': good, 'certificate': bad})['assessment'] == 'tool_error',
                'malformed certificate accepted by runtime')
    hom_request = hom([block('W')], [block('W')])
    hom_certificate = calculate_split_bundle(hom_request)['result']['certificate']
    for key, replacement in [('equivariant_hom_dimension', -1), ('conclusion', 'rank_one_map'), ('map_rank', 1)]:
        bad = deepcopy(hom_certificate); bad['result'][key] = replacement
        require(not check_inp.is_valid({'request': hom_request, 'certificate': bad}), 'Hom promotion accepted structurally')
        require(call(CHECK, {'request': hom_request, 'certificate': bad})['assessment'] == 'tool_error',
                'Hom promotion accepted by runtime')

    names = ['foundation_math_bridge/split_bundle_schemas.py', 'tools/validate_split_bundle_schemas.py']
    print(json.dumps({'status': 'passed', 'checks': checks, 'optimization': sys.flags.optimize,
        'dependency': 'Preinstalled jsonschema only; no install or runtime dependency.',
        'source_sha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in names},
        'scope': 'Structural schemas and runtime semantic rejection are distinct; no formal proof, group identification, geometric recognition, map-rank claim or runtime goal acceptance.'},
        indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
