#!/usr/bin/env python3
"""Independent v0.13 integration audit, normal/-O, selected-only and offline.

Usage: python -B review/v013_review.py [ROOT] (or --root ROOT).
Own hashes, records, fixtures, expectations and ZIP serializer are used. Neither
construction helpers nor the author's tests are used as an oracle. Source mutants
are executed in detached module namespaces; the candidate is never modified.
The full historical/frozen-lab aggregates belong to the release gate, not this
focused review. Hashes bind bytes, not authenticity or mathematical truth.
"""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from pathlib import Path, PurePosixPath
from unittest.mock import patch
import argparse
import ast
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import types
import zipfile

sys.dont_write_bytecode = True
BASE_MANIFEST = 'dcd1c48e50f3c384b96e7eea4a442286fc669ad71dd10e0704366632e75adf9d'
BASE_ZIP = '8aeadce5e8e343794f7716c7a1fb31e8eeb953191f7e4d52448d6459d2921814'
BASE_BYTES = 5682102
LAB_MANIFEST = '0d7cb6249f9c94eb073d330bd8c1ae59b0440e7ce703182cc4c2ee5856c079b9'
LAB_ZIP = 'd32bf32ddf6baa1a013425d9775a2e8ddf84a8a8ceedb11615679ff21875bd79'
RECIPE = '3f33b16d89722d45e4c360fade0ae446cd6c58f454534c4b6d05d9a24afa3deb'
SCHEMA = 'foundation-math-hypothesis-scope/1'
LIMITS = {'file_bytes': 8388608, 'manifest_bytes': 1048576, 'recipe_bytes': 2097152,
          'source_files': 2048, 'input_reads': 8192, 'input_bytes': 67108864,
          'output_files': 4096, 'output_bytes': 67108864, 'snapshot_bytes': 33554432,
          'path_bytes': 240, 'path_depth': 16}
CHANGED = {'README.md', 'RELEASE-FILES.json', 'foundation_math/cli.py',
           'foundation_math_bridge/__init__.py', 'foundation_math_bridge/schemas.py',
           'foundation_math_bridge/server.py', 'tests/test_agent_bridge.py',
           'tests/test_character_ring_integration.py', 'tests/test_claim_revision_integration.py',
           'tests/test_linear_algebra_bridge.py', 'tests/test_linear_systems_integration.py',
           'tests/test_portable_validation.py', 'tests/test_split_bundle_integration.py'}
COUNTS = Counter()
MUTANTS = []


class ReviewFailure(Exception):
    pass


def need(value, label):
    COUNTS['explicit_checks'] += 1
    if not value:
        raise ReviewFailure(label)


def H(raw):
    return sha256(raw).hexdigest()


def C(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n').encode()


def J(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ReviewFailure('duplicate JSON key')
            result[key] = value
        return result
    def reject(token):
        raise ReviewFailure('float/nonfinite JSON token')
    return json.loads(raw, object_pairs_hook=pairs, parse_float=reject, parse_constant=reject)


def source(root, name):
    path = PurePosixPath(name)
    need(type(name) is str and not path.is_absolute() and str(path) == name and
         all(p not in ('', '.', '..') for p in path.parts), 'unsafe selected path')
    current = root
    for part in path.parts:
        current /= part
        need(not current.is_symlink(), 'symlink source')
    info = current.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= LIMITS['file_bytes'], 'nonordinary source')
    return current.read_bytes()


def archive(files):
    """Own fixed-profile serializer, not the snapshot/release builder."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, raw in sorted(files.items()):
            row = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            row.create_system = 3
            row.external_attr = 0o100644 << 16
            row.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(row, raw, compresslevel=9)
    return output.getvalue()


def populate(root, files):
    root.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)


def check_selection(root):
    raw = source(root, 'SOURCE-MANIFEST.json'); manifest = strict(raw)
    selection_raw = source(root, 'RELEASE-FILES.json'); selection = strict(selection_raw)
    need(raw == C(manifest) and selection_raw == C(selection), 'canonical current manifests')
    need(selection['schema'] == 'foundation-math-v013-selected-files-v1', 'selection schema')
    names = selection['files']
    need(names == sorted(set(names)) and set(names) == set(manifest['files']), 'exact selected inventory')
    need('SOURCE-MANIFEST.json' not in names and 'RELEASE-FILES.json' in names, 'acyclic manifest')
    for n in ('review/v013_review.py', 'review/V013-REVIEW.md', 'review/V013-REVIEW-PINS.json',
              'tools/run_hypothesis_scope_validation.py', 'tools/reproduce_hypothesis_scope_release.py'):
        need(n in names, 'required selected review/gate: ' + n)
    files = {n: source(root, n) for n in names}
    need({n: H(v) for n, v in files.items()} == manifest['files'], 'selected source hashes')
    need(not any(n.startswith(('evidence/', 'work/', '.git/')) or '__pycache__' in n or n.endswith(('.pyc', '.pyo')) for n in names), 'generated bytes selected')
    need(not any(n.endswith('.zip') and not n.startswith('vendor/') for n in names), 'unexpected nested archive')
    need(not any('foundation-math-v0' + v + '-source.zip' in n for n in names for v in ('11', '12')), 'compact history replaced by nested full ZIP')
    need(manifest['version'] == '0.13.0-dev' and manifest['baseline_manifest_sha256'] == BASE_MANIFEST and
         manifest['snapshot_recipe_sha256'] == RECIPE and manifest['accepted_lab_manifest_sha256'] == LAB_MANIFEST, 'manifest provenance')
    pins_raw = files['review/V013-REVIEW-PINS.json']; pins = strict(pins_raw)
    need(pins_raw == C(pins), 'canonical reviewer pins')
    expected_names = set(names) - {'RELEASE-FILES.json', 'review/V013-REVIEW.md', 'review/V013-REVIEW-PINS.json'}
    need(set(pins['files']) == expected_names and all(H(files[n]) == h for n, h in pins['files'].items()), 'independent pre-freeze byte pins')
    need(pins['baseline_manifest_sha256'] == BASE_MANIFEST and pins['accepted_lab_manifest_sha256'] == LAB_MANIFEST, 'review provenance pins')
    return manifest, files


def check_history(root, selected):
    base_raw = selected['snapshots/v012/baseline-manifest.json']; base = strict(base_raw)['files']
    need(H(base_raw) == BASE_MANIFEST and len(base) == 401, 'accepted baseline manifest')
    recipe_raw = selected['snapshots/v012/recipe.json']; recipe = strict(recipe_raw)
    need(H(recipe_raw) == RECIPE and recipe_raw == C(recipe), 'frozen recipe')
    need(set(recipe) == {'schema', 'zip_profile', 'baseline_manifest_sha256', 'baseline_archive_sha256',
         'baseline_archive_bytes', 'donor_projection_sha256', 'files'}, 'closed recipe/no cyclic field')
    need(recipe['baseline_manifest_sha256'] == BASE_MANIFEST and recipe['baseline_archive_sha256'] == BASE_ZIP and
         recipe['baseline_archive_bytes'] == BASE_BYTES, 'recipe baseline pins')
    need(recipe['zip_profile'] == 'fm-v011-python-deflate9-fixed-2026-v1', 'serializer unchanged')
    rows = recipe['files']; need([r['path'] for r in rows] == sorted(base), 'recipe exact baseline coverage')
    donors = {r['path']: r['sha256'] for r in rows if r['source'] == 'donor'}
    need(H(C(donors)) == recipe['donor_projection_sha256'], 'donor projection hash')
    need('SOURCE-MANIFEST.json' not in donors and H(source(root, 'SOURCE-MANIFEST.json')) not in recipe_raw.decode(), 'no next-manifest cycle')
    restored = {}
    expected_snapshot = {'snapshots/v012/recipe.json', 'snapshots/v012/baseline-manifest.json'}
    for row in rows:
        need(set(row) == {'path', 'source', 'sha256', 'bytes'} and row['sha256'] == base[row['path']], 'recipe row')
        need(row['source'] in ('donor', 'blob'), 'closed source category')
        name = row['path'] if row['source'] == 'donor' else 'snapshots/v012/blobs/' + row['sha256']
        if row['source'] == 'blob':
            expected_snapshot.add(name)
        raw = selected[name]
        need(len(raw) == row['bytes'] and H(raw) == row['sha256'], 'exact old source bytes')
        restored[row['path']] = raw
    actual_snapshot = {n for n in selected if n.startswith('snapshots/v012/')}
    need(actual_snapshot == expected_snapshot, 'exact selected snapshot inventory')
    actual_disk = {p.relative_to(root).as_posix() for p in (root/'snapshots/v012').rglob('*') if p.is_file()}
    need(actual_disk == expected_snapshot, 'extra unselected snapshot payload')
    changed = {n for n in base if selected[n] != restored[n]}
    need(changed == CHANGED and set(donors) == set(base)-CHANGED, 'only declared old file changes')
    for n in base:
        if n.startswith(('vendor/', 'snapshots/v011/', 'baseline_snapshot/')):
            need(selected[n] == restored[n], 'old archive/snapshot implementation changed')
        if n.startswith(('foundation_math/', 'claim_revision/', 'character_ring/', 'split_bundle/',
                         'exact_linalg/', 'exact_systems/', 'bounded_counterexample/', 'polynomial_witness/')) and n != 'foundation_math/cli.py':
            need(selected[n] == restored[n], 'math/acceptance/domain registry changed')
    restored['SOURCE-MANIFEST.json'] = base_raw
    raw_zip = archive(restored)
    need(H(raw_zip) == BASE_ZIP and len(raw_zip) == BASE_BYTES, 'independently reconstructed exact original ZIP')
    from baseline_snapshot import snapshot as snapshot
    need(snapshot.LIMITS == LIMITS, 'snapshot budgets weakened')
    from tools.hypothesis_scope_release_support import restored_baseline
    with restored_baseline(root) as (tree, zip_path, receipt):
        need(zip_path.read_bytes() == raw_zip, 'production restore differs from independent ZIP')
        need({p.relative_to(tree).as_posix() for p in tree.rglob('*') if p.is_file()} == set(restored), 'restored inventory')
        need(all((tree/n).read_bytes() == raw for n, raw in restored.items()), 'production restored bytes differ')
        need(receipt['source_files'] == 401, 'restoration source count')
    return restored, {'selected_files': 401, 'unchanged_files': len(donors), 'archive_sha256': H(raw_zip), 'archive_bytes': len(raw_zip)}


def check_lab(selected):
    raw = selected['docs/HYPOTHESIS-SCOPE-LAB-SOURCE-MANIFEST.json']
    need(H(raw) == LAB_MANIFEST, 'accepted lab manifest')
    manifest = strict(raw)['files']; need(len(manifest) == 34, 'lab inventory count')
    zraw = selected['vendor/hypothesis-scope-lab.zip']; need(H(zraw) == LAB_ZIP, 'accepted lab ZIP')
    with zipfile.ZipFile(io.BytesIO(zraw)) as z:
        need(z.namelist() == sorted([*manifest, 'SOURCE-MANIFEST.json']), 'lab archive exact inventory')
        data = {r.filename: z.read(r) for r in z.infolist()}
        for row in z.infolist():
            need(row.external_attr == 0o100644 << 16 and row.file_size <= LIMITS['file_bytes'], 'lab archive type/size')
        need(data['SOURCE-MANIFEST.json'] == raw and all(H(data[n]) == h for n, h in manifest.items()), 'lab archive selected byte hashes')
    mapping = {'hypothesis_scope/__init__.py': 'hypothesis_scope/__init__.py',
               'hypothesis_scope/__main__.py': 'hypothesis_scope/__main__.py', 'hypothesis_scope/core.py': 'hypothesis_scope/core.py',
               'docs/HYPOTHESIS-SCOPE-LAB-CONTRACT.md': 'docs/CONTRACT.md',
               'docs/HYPOTHESIS-SCOPE-LAB-REVIEW.md': 'docs/INDEPENDENT-REVIEW.md',
               'schemas/hypothesis-scope-request.schema.json': 'schemas/request.schema.json'}
    mapping.update({n: 'fixtures/' + n.rsplit('/', 1)[1] for n in selected if n.startswith('examples/hypothesis-scope/')})
    for new, old in mapping.items():
        need(selected[new] == data[old], 'accepted lab bytes changed: ' + new)
    pins = strict(selected['HYPOTHESIS-SCOPE-PINS.json'])
    need(pins['lab_source_pins'] == {new: H(data[old]) for new, old in mapping.items()}, 'lab pin mapping')
    return {'selected_files': len(manifest), 'immutable_copied_files': len(mapping), 'archive_sha256': H(zraw)}


def record(identifier, content, revision=1):
    body = {'id': identifier, 'revision': revision, 'content': deepcopy(content)}
    return {**body, 'revision_sha256': H(J(body))}


def pin(value):
    return {k: value[k] for k in ('id', 'revision', 'revision_sha256')}


def reseal(value):
    return record(value['id'], value['content'], value['revision'])


def fixture():
    object_types = {n: 'coherent_sheaf' for n in ('X', 'Y', 'Z', 'K', 'I', 'T', 'U', 'K2')}
    object_types.update({'R': 'representation', 'V': 'vector_space', 'S': 'formal_splitting', 'L': 'locus'})
    objects = {n: record(n, {'object_type': t, 'context_sha256': '1'*64, 'description': 'Unverified ' + n}) for n, t in object_types.items()}
    edges = {'f': ('X', 'Y'), 'f2': ('X', 'Y'), 'g': ('Y', 'Z'), 'fg': ('X', 'Z'),
             'inc': ('K', 'X'), 'inc2': ('K', 'X'), 'otherinc': ('K2', 'X'),
             'image': ('I', 'Y'), 'iso': ('T', 'U'), 'iso2': ('T', 'U')}
    maps = {n: record(n, {'source': pin(objects[a]), 'target': pin(objects[b]), 'description': 'Unverified ' + n}) for n, (a, b) in edges.items()}
    o = lambda n: pin(objects[n]); m = lambda n: pin(maps[n])
    predicates = [
        {'kind': 'generic_sheaf_equality', 'left': o('X'), 'right': o('Y'), 'locus': o('L')},
        {'kind': 'coherent_sheaf_equality', 'left': o('X'), 'right': o('Y')},
        *[{'kind': k, 'kernel': o('K'), 'inclusion': m('inc'), 'of_map': m('f')} for k in ('selected_subkernel', 'full_kernel')],
        {'kind': 'abstract_splitting', 'object': o('X'), 'splitting': o('S')},
        {'kind': 'embedded_splitting', 'object': o('X'), 'splitting': o('S'), 'inclusion': m('f')},
        *[{'kind': k, 'image': o('I'), 'inclusion': m('image'), 'of_map': m('f')} for k in ('coherent_image', 'saturated_image')],
        {'kind': 'physical_representation', 'object': o('R'), 'catalog_sha256': '2'*64, 'label': 'W'},
        {'kind': 'object_rank', 'object': o('X'), 'value': 7},
        {'kind': 'object_dimension', 'object': o('V'), 'value': 7},
        {'kind': 'map_rank', 'map': m('f'), 'value': 7},
        {'kind': 'map_injective', 'map': m('f')}, {'kind': 'map_zero', 'map': m('f')},
        {'kind': 'constant_vanishing', 'constants': o('K'), 'inclusion': m('inc'), 'path': [m('f'), m('g')]},
        {'kind': 'torsion_identification', 'role': 'original', 'torsion': o('T'), 'of_map': m('f'), 'identified_with': o('U'), 'identification': m('iso')},
        {'kind': 'object_identity', 'left': o('X'), 'right': o('Y')},
        {'kind': 'map_identity', 'left': m('f'), 'right': m('f2')},
    ]
    return list(objects.values()), list(maps.values()), predicates


def document(required=None, supplied=None):
    objects, maps, predicates = fixture()
    required = deepcopy(predicates[3] if required is None else required)
    supplied = deepcopy(required if supplied is None else supplied)
    fact = record('Fact', {'predicate': supplied, 'availability': 'supplied',
                  'provenance': {'artifact_sha256': '0'*64, 'description': 'Authored assertion, no artifact supplied'}})
    rule = record('Rule', {'purpose': 'No proof of the described mathematical conclusion',
                          'requirements': [{'id': 'Need', 'predicate': required}]})
    return {'schema': SCHEMA, 'objects': objects, 'maps': maps, 'facts': [fact], 'rule': rule,
            'application': {'rule': pin(rule), 'bindings': [{'requirement_id': 'Need', 'fact': pin(fact)}]}}


def flags(receipt):
    need(receipt['scope'] == 'exact_authored_premise_matching_only' and receipt['truth_assessment'] == 'not_assessed', 'authored scope only')
    for key in ('formal_proof', 'runtime_goal_acceptance', 'fact_truth_checked', 'rule_soundness_checked', 'geometry_checked'):
        need(receipt[key] is False, 'literal false receipt flag: ' + key)
    if 'result' in receipt:
        for key in ('fact_truth_checked', 'rule_soundness_checked', 'geometry_checked', 'runtime_acceptance', 'lean_proof'):
            need(receipt['result'][key] is False, 'literal false result flag: ' + key)


def expected(receipt, status):
    flags(receipt); need(receipt['status'] == 'success', 'valid comparison should execute')
    report = receipt['result']; need(report['all_requirements_matched'] is (status == 'exact_match'), 'exact match flag')
    need([r['status'] for r in report['requirements']] == [status], 'required comparison status: ' + status)
    return report


def check_scope(adapter):
    predicates = fixture()[2]
    for a in predicates:
        for b in predicates:
            doc = document(a, b); before = deepcopy(doc)
            result = expected(adapter.check_hypothesis_scope(doc), 'exact_match' if a == b else 'predicate_mismatch')
            normalized = deepcopy(doc)
            for key in ('objects', 'maps', 'facts'):
                normalized[key].sort(key=lambda r: r['id'])
            normalized['application']['bindings'].sort(key=lambda r: r['requirement_id'])
            need(result['input_sha256'] == H(J(normalized)) and doc == before, 'independent input digest and nonmutation')
    for a in ('1', 'W', 'A', 'S4', 'D', 'T6', 'P', 'Wp', 'V'):
        for b in ('1', 'W', 'A', 'S4', 'D', 'T6', 'P', 'Wp', 'V'):
            req = dict(predicates[8], label=a); supplied = dict(predicates[8], label=b)
            expected(adapter.check_hypothesis_scope(document(req, supplied)), 'exact_match' if a == b else 'predicate_mismatch')
    substitutions = [(14, 'path', [pin(fixture()[1][3])]), (14, 'inclusion', pin(fixture()[1][5])),
                     (15, 'role', 'induced'), (15, 'of_map', pin(fixture()[1][1])),
                     (15, 'identification', pin(fixture()[1][9])), (12, 'map', pin(fixture()[1][1])),
                     (8, 'catalog_sha256', '3'*64)]
    for i, key, val in substitutions:
        supplied = deepcopy(predicates[i]); supplied[key] = val
        expected(adapter.check_hypothesis_scope(document(predicates[i], supplied)), 'predicate_mismatch')
    for label in ('rule_pin_not_current', 'missing_binding', 'fact_not_supplied', 'fact_pin_not_current', 'fact_withdrawn'):
        doc = document()
        if label == 'rule_pin_not_current': doc['application']['rule']['revision'] += 1
        if label == 'missing_binding': doc['application']['bindings'] = []
        if label == 'fact_not_supplied': doc['facts'] = []
        if label == 'fact_pin_not_current': doc['application']['bindings'][0]['fact']['revision_sha256'] = '0'*64
        if label == 'fact_withdrawn':
            doc['facts'][0]['content']['availability'] = 'withdrawn'; doc['facts'][0] = reseal(doc['facts'][0])
            doc['application']['bindings'][0]['fact'] = pin(doc['facts'][0])
        expected(adapter.check_hypothesis_scope(doc), label)
    # Precedence must not silently repin a changed, withdrawn or different fact.
    doc = document(); doc['facts'][0]['content']['availability'] = 'withdrawn'; doc['facts'][0] = reseal(doc['facts'][0])
    expected(adapter.check_hypothesis_scope(doc), 'fact_pin_not_current')
    doc['application']['rule']['revision'] += 1
    expected(adapter.check_hypothesis_scope(doc), 'rule_pin_not_current')
    # Equal descriptions, dimensions or endpoint summaries do not equate IDs.
    req = deepcopy(predicates[16]); supplied = deepcopy(req); supplied['left'] = pin(fixture()[0][2])
    expected(adapter.check_hypothesis_scope(document(req, supplied)), 'predicate_mismatch')
    vanishing = deepcopy(predicates[14]); vanishing['constants'] = pin(fixture()[0][7]); vanishing['inclusion'] = pin(fixture()[1][6])
    expected(adapter.check_hypothesis_scope(document(predicates[14], vanishing)), 'predicate_mismatch')
    # Even self-consistent claims of an impossible rank still only match syntax.
    impossible = dict(predicates[9], value=999999)
    expected(adapter.check_hypothesis_scope(document(impossible)), 'exact_match')
    from foundation_math.domains import _DOMAINS, domain_handler, DomainError
    need(set(_DOMAINS) == {'Z', 'Q', 'polynomial_ring'}, 'runtime domain registry unchanged')
    for name in ('hypothesis_scope', 'match_hypothesis_scope', 'coherent_sheaf'):
        rejected = False
        try: domain_handler(name)
        except DomainError: rejected = True
        need(rejected, 'scope matching promoted to runtime domain')
    original = document(); shuffled = deepcopy(original)
    for key in ('objects', 'maps', 'facts'): shuffled[key].reverse()
    need(adapter.check_hypothesis_scope(original) == adapter.check_hypothesis_scope(shuffled), 'registry order invariance')
    bad = []
    d = document(); d['maps'][0]['content']['source']['revision'] += 1; d['maps'][0] = reseal(d['maps'][0]); bad.append(d)
    d = document(); d['facts'][0]['content']['predicate']['inclusion']['revision'] += 1; d['facts'][0] = reseal(d['facts'][0]); bad.append(d)
    d = document(); d['facts'][0]['revision_sha256'] = '0'*64; bad.append(d)
    d = document(); d['facts'][0]['content']['predicate']['inclusion'] = pin(d['maps'][7]); d['facts'][0] = reseal(d['facts'][0]); bad.append(d)
    d = document(); d['objects'][0]['content']['context_sha256'] = '4'*64; d['objects'][0] = reseal(d['objects'][0])
    for item in d['maps']:
        for side in ('source', 'target'):
            if item['content'][side]['id'] == d['objects'][0]['id']: item['content'][side] = pin(d['objects'][0])
        item.update(reseal(item))
    bad.append(d)
    d = document(); d['objects'][0]['revision'] = True; bad.append(d)
    d = document(); d['facts'][0]['content'].pop('provenance'); d['facts'][0] = reseal(d['facts'][0]); bad.append(d)
    d = document(); d['application']['bindings'] *= 2; bad.append(d)
    d = document(); d['objects'] *= 6; bad.append(d)
    cycle = {}; cycle['cycle'] = cycle; bad.append(cycle)
    bad.extend([None, [], {}, dict(document(), conclusion=True), {'x': '\ud800'}, {'x': 1.0}, {'x': 2**40}])
    for d in bad:
        r = adapter.check_hypothesis_scope(d); flags(r)
        need(r['status'] == 'error' and 'result' not in r, 'malformed scope has no partial evidence')
    return {'ordered_predicate_pairs': 324, 'physical_label_pairs': 81, 'scope_substitutions': len(substitutions) + 2, 'malformed_documents': len(bad)}


def bridge(module):
    instance = module.Bridge()
    result = instance.dispatch({'jsonrpc': '2.0', 'id': 0, 'method': 'initialize', 'params': {'protocolVersion': 'foundation-math-jsonrpc/1'}})
    need('result' in result, 'bridge initialize')
    return instance


def frame(doc, **extra):
    return {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {'name': 'match_hypothesis_scope', 'arguments': {'document': doc, **extra}}}


def invoke_cli(module, raw, args=None, output_limit=None):
    sink = io.StringIO(); stdin = types.SimpleNamespace(buffer=io.BytesIO(raw))
    with patch.object(module.sys, 'stdin', stdin), patch.object(module.sys, 'stdout', sink):
        if output_limit is None:
            code = module.hypothesis_scope_cli(['hypothesis-scope-check'] if args is None else args)
        else:
            with patch.object(module, 'MAX_OUTPUT_BYTES', output_limit):
                code = module.hypothesis_scope_cli(['hypothesis-scope-check'] if args is None else args)
    return code, strict(sink.getvalue())


def check_transport(root, adapter, server):
    doc = document(); raw = J(doc); wire = J(frame(doc))
    need(server.MAX_FRAME_BYTES == 65536 and server.MAX_OUTPUT_BYTES == 1048576 and
         server.MAX_JSON_DEPTH == 80 and server.MAX_JSON_NODES == 16384, 'original bridge budgets')
    need(adapter.MAX_INPUT_BYTES == 262144 and adapter.MAX_OUTPUT_BYTES == 262144, 'CLI inherited budgets')
    for size in (65535, 65536, 65537):
        response = bridge(server).handle(wire + b' '*(size-len(wire)))
        need(('result' in response) is (size <= 65536), 'raw bridge frame cap')
    for key in ('path', 'file', 'code', 'command', 'url', 'network', 'limits', 'budget', 'ledger', 'accept_proof'):
        need(bridge(server).dispatch(frame(doc, **{key: 'x'}))['error']['code'] == -32602, 'closed argument: ' + key)
    for invalid in (b'{"x":1,"x":2}', b'{"x":1.0}', b'{"x":NaN}', b'\xff', b'['*100+b']'*100):
        need('error' in bridge(server).handle(invalid), 'strict bridge raw JSON')
    notification = frame(doc); del notification['id']
    with patch.object(server, 'check_hypothesis_scope', side_effect=RuntimeError('unexpected execution')) as call:
        need(bridge(server).dispatch(notification) is None and call.call_count == 0, 'notification performed math')
    with patch.object(server, 'check_hypothesis_scope', side_effect=RuntimeError('/private/path secret')):
        result = bridge(server).dispatch(frame(doc))
        need(result['error']['code'] == -32603 and '/private/path' not in json.dumps(result), 'backend error leaks/partial output')
    result = strict(server.encode_response({'jsonrpc':'2.0', 'id': 1, 'result':'x'*1048576}))
    need('result' not in result and result['error']['code'] == -32002, 'bridge output withholding')
    cases = [((), raw, 0), (('some-file.json',), raw, 2), (('--limit', '1'), raw, 2),
             (('--url', 'https://invalid.example'), raw, 2), (('--code', '1+1'), raw, 2),
             ((), b'{"x":1,"x":2}', 2), ((), b'\xff', 2), ((), b'{"x":1.0}', 2),
             ((), raw+b' '*(262144-len(raw)), 0), ((), raw+b' '*(262145-len(raw)), 2)]
    for args, data, code in cases:
        process = subprocess.run([sys.executable, '-B', *(['-O'] if sys.flags.optimize else []), '-m', 'foundation_math',
                                  'hypothesis-scope-check', *args], input=data, capture_output=True, cwd=root, env=environment(), timeout=30)
        need(process.returncode == code and process.stderr == b'', 'stdin CLI status/stderr')
        receipt = strict(process.stdout); flags(receipt)
        need(len(process.stdout.rstrip(b'\n')) <= 262144 and (b'\\u' in process.stdout or process.stdout.isascii()), 'bounded ASCII CLI envelope')
        if code: need('result' not in receipt, 'CLI invalid input partial result')
        else: expected(receipt, 'exact_match')
    code, receipt = invoke_cli(adapter, raw, output_limit=1000)
    need(code == 2 and 'result' not in receipt and receipt['error']['code'] == 'budget_exceeded', 'CLI output withholding')
    class Broken:
        def read(self, amount): raise OSError('private input failure')
    sink = io.StringIO()
    with patch.object(adapter.sys, 'stdin', types.SimpleNamespace(buffer=Broken())), patch.object(adapter.sys, 'stdout', sink):
        need(adapter.hypothesis_scope_cli(['hypothesis-scope-check']) == 2, 'input I/O status')
    need(strict(sink.getvalue())['error']['code'] == 'input_io' and 'private input failure' not in sink.getvalue(), 'input I/O redaction')
    return {'raw_bridge_input_bytes': 65536, 'cli_input_output_bytes': 262144, 'cli_subprocess_cases': len(cases)}


def check_schema(schema_module, server):
    from jsonschema import Draft202012Validator
    definition = schema_module.tool_definitions()[0]
    need(definition['name'] == 'match_hypothesis_scope' and definition['readOnly'] is True, 'one read-only scope tool')
    for key in ('inputSchema', 'outputSchema'):
        Draft202012Validator.check_schema(definition[key])
        def visit(value):
            if isinstance(value, dict):
                if '$ref' in value:
                    ref = value['$ref']; need(ref.startswith('#/'), 'external schema reference')
                    target = definition[key]
                    for part in ref[2:].split('/'):
                        need(part in target, 'unresolved schema reference'); target = target[part]
                for v in value.values(): visit(v)
            elif isinstance(value, list):
                for v in value: visit(v)
        visit(definition[key])
    iv = Draft202012Validator(definition['inputSchema']); ov = Draft202012Validator(definition['outputSchema'])
    need(iv.is_valid({'document': document()}), 'schema rejects own valid input')
    need(not iv.is_valid({'document': document(), 'path': 'x'}), 'input schema open arguments')
    receipts = []
    for doc in (document(), document(fixture()[2][2], fixture()[2][3]), {}):
        content = bridge(server).dispatch(frame(doc))['result']['structuredContent']; receipts.append(content)
        need(ov.is_valid(content), 'output schema rejects actual receipt')
        for path in (['formal_proof'], ['runtime_goal_acceptance'],
                     *[['receipt', k] for k in ('formal_proof', 'runtime_goal_acceptance', 'fact_truth_checked', 'rule_soundness_checked', 'geometry_checked')],
                     *([['receipt', 'result', k] for k in ('fact_truth_checked', 'rule_soundness_checked', 'geometry_checked', 'runtime_acceptance', 'lean_proof')] if doc else [])):
            for replacement in (True, 0, None):
                altered = deepcopy(content); target = altered
                for part in path[:-1]: target = target[part]
                target[path[-1]] = replacement
                need(not ov.is_valid(altered), 'output schema permits non-false flag')
        altered = deepcopy(content); altered['assessment'] = 'tool_error' if content['assessment'] != 'tool_error' else 'authored_premise_scope_compared'
        need(not ov.is_valid(altered), 'assessment/status schema link')
        altered = deepcopy(content); altered['receipt']['proof'] = 'claimed'
        need(not ov.is_valid(altered), 'receipt schema permits extra fields')
    for field in ('rule', 'current_rule'):
        altered = deepcopy(receipts[0]); altered['receipt']['result'][field]['revision'] = 0
        need(not ov.is_valid(altered), 'output pin schema bounds')
    return {'draft': '2020-12', 'all_refs_local_and_resolved': True, 'literal_false_constraints': True}


def environment():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for key in ('PYTHONPATH', 'PYTHONHOME', 'SPLIT_REVIEW_ROOT'): env.pop(key, None)
    return env


def old_tool_cases(root):
    def read(name): return strict((root/name).read_bytes())
    finite = read('examples/counterexample/false-bounded-inequality.json')
    matrix = read('examples/linear-algebra/rectangular-matrix.json')
    polynomial = read('examples/polynomial-witness/false-square.json')
    system = read('examples/linear-systems/consistent-system.json')
    character = read('examples/character-ring/physical_tensor.request.json')
    return [
        ('exact_scalar', {'domain':'Q', 'operation':'add', 'operands':[{'numerator':1, 'denominator':2}, {'numerator':1, 'denominator':3}]}),
        ('polynomial_identity', read('examples/polynomial/distributivity.json')),
        ('finite_box_search', finite),
        ('check_finite_box_witness', {'request':finite, 'assignment':read('examples/counterexample/valid-witness.json')}),
        ('certify_rational_matrix', {'matrix':matrix}),
        ('check_rational_matrix_certificate', {'matrix':matrix, 'certificate':read('examples/linear-algebra/rectangular-certificate.json')}),
        ('construct_polynomial_witness', {'request':polynomial}),
        ('check_polynomial_witness', {'request':polynomial, 'witness':read('examples/polynomial-witness/false-square-witness.json')}),
        ('solve_rational_linear_system', {'system':system}),
        ('check_rational_linear_system_certificate', {'system':system, 'certificate':read('examples/linear-systems/consistent-certificate.json')}),
        ('calculate_fixed_character', {'request':character}),
        ('check_fixed_character_certificate', {'request':character, 'certificate':read('examples/character-ring/physical_tensor.certificate.json')}),
        ('calculate_formal_split_bundle', {'request':read('examples/split-bundle/negative_h1_critical.request.json')}),
        ('check_formal_split_bundle_certificate', {'request':read('examples/split-bundle/hom_not_map_rank.request.json'), 'certificate':read('examples/split-bundle/hom_not_map_rank.certificate.json')}),
        ('replay_claim_applicability', {'ledger':read('examples/claim-revision/boundary-withdrawal.ledger.json')})]


def check_legacy(root, restored):
    positive = old_tool_cases(root); cases = []
    for name, args in positive:
        cases.extend([(name, args), (name, {}), (name, None), (name, dict(args, unexpected=True))])
        for key in args:
            altered = deepcopy(args); altered[key] = None; cases.append((name, altered))
    frames = [{'jsonrpc':'2.0', 'id':'init', 'method':'initialize', 'params':{'protocolVersion':'foundation-math-jsonrpc/1'}},
              {'jsonrpc':'2.0', 'id':'list', 'method':'tools/list'}]
    frames += [{'jsonrpc':'2.0', 'id':i, 'method':'tools/call', 'params':{'name':n, 'arguments':a}} for i, (n, a) in enumerate(cases)]
    wire = b''.join(J(x)+b'\n' for x in frames)
    with tempfile.TemporaryDirectory(prefix='fm-v013-independent-legacy-') as td:
        base = Path(td)/'baseline'; populate(base, restored); outputs = []
        for tree in (base, root):
            result = subprocess.run([sys.executable, '-B', *(['-O'] if sys.flags.optimize else []), '-m', 'foundation_math_bridge'],
                                    input=wire, cwd=tree, capture_output=True, env=environment(), timeout=90)
            need(result.returncode == 0 and result.stderr == b'', 'old/new bridge subprocess')
            rows = [strict(x) for x in result.stdout.splitlines()]; need(len(rows) == len(frames), 'legacy response count'); outputs.append(rows)
    old, new = outputs
    need(old[0]['result']['serverInfo'].pop('version') == '0.11.0-dev' and new[0]['result']['serverInfo'].pop('version') == '0.13.0-dev', 'expected packaging-only baseline version')
    need(old[0] == new[0], 'legacy initialize contract changed')
    old_tools = old[1]['result']['tools']; new_tools = new[1]['result']['tools']
    need(len(old_tools) == 15 and len(new_tools) == 16 and new_tools[:15] == old_tools and new_tools[15]['name'] == 'match_hypothesis_scope', 'exactly one additive tool')
    need([t['name'] for t in old_tools] == [n for n, _ in positive], 'fifteen tools covered')
    need(strict((root/'docs/BASE-V012-BRIDGE-TOOLS.json').read_bytes())['tools'] == old_tools, 'frozen contract copy')
    need(old[2:] == new[2:], 'legacy response drift')
    for case in positive:
        response = old[2+cases.index(case)]; need('result' in response and response['result']['isError'] is False, 'old positive fixture not exercised')
    return {'tools': 15, 'cases': len(cases), 'complete_contracts_identical': True, 'response_sha256': H(J(old[2:]))}


def check_static(selected):
    names = ['foundation_math/hypothesis_scope.py', 'hypothesis_scope/core.py', 'foundation_math_bridge/hypothesis_scope_schemas.py']
    forbidden = {'eval', 'exec', 'compile', '__import__', 'open'}
    imports = {'os', 'pathlib', 'socket', 'requests', 'urllib', 'http', 'subprocess', 'openai'}
    for name in names:
        for node in ast.walk(ast.parse(selected[name])):
            need(not isinstance(node, ast.Assert), 'optimized-away implementation guard')
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                need(node.func.id not in forbidden, 'new code/path execution surface')
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module or '']
                need(not any(m.split('.')[0] in imports for m in modules), 'new file/network/process import')
    return {'new_modules_scanned': names, 'findings': [], 'scope': 'Static surface review, not a sandbox certification.'}


def detached(text, package):
    module = types.ModuleType(package + '._independent_review_mutant')
    module.__package__ = package
    exec(compile(text, '<independent-review-source-control>', 'exec'), module.__dict__)
    return module


def mutation(selected, name, package, before, after, probe):
    text = selected[name].decode(); need(text.count(before) == 1, 'unique source mutation anchor: ' + before)
    probe(detached(text, package))
    changed = detached(text.replace(before, after), package)
    killed = False
    try:
        probe(changed)
    except ReviewFailure:
        killed = True
    need(killed, 'source mutant survived: ' + name + ': ' + before)
    MUTANTS.append({'file': name, 'guard': before, 'killed': True})


def check_mutations(selected):
    adapter = 'foundation_math/hypothesis_scope.py'; server = 'foundation_math_bridge/server.py'; schemas = 'foundation_math_bridge/hypothesis_scope_schemas.py'
    raw = J(document()); padded = raw+b' '*(262145-len(raw))
    def args(m): need(invoke_cli(m, raw, ['hypothesis-scope-check', '--path', 'unused'])[0] == 2, 'CLI argument guard')
    def limit(m): need(invoke_cli(m, padded)[0] == 2, 'CLI bounded raw input')
    def output(m):
        code, r = invoke_cli(m, raw, output_limit=1000); need(code == 2 and 'result' not in r, 'CLI output result withheld')
    def proof(m): flags(m.check_hypothesis_scope(document()))
    def extra(m): need('error' in bridge(m).dispatch(frame(document(), path='unused')), 'dispatch rejects surplus arguments')
    def frame_cap(m):
        wire = J(frame(document())); need('error' in bridge(m).handle(wire+b' '*(65537-len(wire))), 'raw 64KiB guard')
    def assessment(m): need(bridge(m).dispatch(frame(document()))['result']['structuredContent']['assessment'] == 'authored_premise_scope_compared', 'nonproof assessment')
    def false_schema(m):
        from jsonschema import Draft202012Validator
        import foundation_math_bridge.server as real
        value = bridge(real).dispatch(frame(document()))['result']['structuredContent']; value['receipt']['geometry_checked'] = True
        need(not Draft202012Validator(m.tool_definitions()[0]['outputSchema']).is_valid(value), 'schema false flag')
    def closed_schema(m):
        from jsonschema import Draft202012Validator
        need(not Draft202012Validator(m.tool_definitions()[0]['inputSchema']).is_valid({'document':document(), 'path':'unused'}), 'schema exact argument object')
    def pin_schema(m):
        from jsonschema import Draft202012Validator
        import foundation_math_bridge.server as real
        value = bridge(real).dispatch(frame(document()))['result']['structuredContent']; value['receipt']['result']['current_rule']['revision'] = 0
        need(not Draft202012Validator(m.tool_definitions()[0]['outputSchema']).is_valid(value), 'schema output exact pin')
    mutation(selected, adapter, 'foundation_math', "if argv != ['hypothesis-scope-check']:", 'if False:', args)
    mutation(selected, adapter, 'foundation_math', 'read(MAX_INPUT_BYTES + 1)', 'read(MAX_INPUT_BYTES)', limit)
    mutation(selected, adapter, 'foundation_math', "if len(output.encode('ascii')) > MAX_OUTPUT_BYTES:", 'if False:', output)
    mutation(selected, adapter, 'foundation_math', "'geometry_checked': False", "'geometry_checked': True", proof)
    mutation(selected, adapter, 'foundation_math', "'runtime_goal_acceptance': False", "'runtime_goal_acceptance': True", proof)
    mutation(selected, server, 'foundation_math_bridge', 'fields = _exact_object(arguments, {"document"})', 'fields = arguments', extra)
    mutation(selected, server, 'foundation_math_bridge', 'MAX_FRAME_BYTES = 65536', 'MAX_FRAME_BYTES = 262144', frame_cap)
    mutation(selected, server, 'foundation_math_bridge', 'assessment = "authored_premise_scope_compared"', 'assessment = "mathematical_truth_established"', assessment)
    mutation(selected, schemas, 'foundation_math_bridge', "**{key: {'const': False} for key in ('formal_proof', 'runtime_goal_acceptance',", "**{key: {'type': 'boolean'} for key in ('formal_proof', 'runtime_goal_acceptance',", false_schema)
    mutation(selected, schemas, 'foundation_math_bridge', "'required': list(properties), 'additionalProperties': False", "'required': list(properties), 'additionalProperties': True", closed_schema)
    mutation(selected, schemas, 'foundation_math_bridge', "pin = {'$ref': '#/$defs/pin'}", "pin = {'type': 'object'}", pin_schema)
    return MUTANTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidate', nargs='?', type=Path); parser.add_argument('--root', type=Path)
    args = parser.parse_args()
    need(not (args.root and args.candidate), 'choose one root form')
    root = (args.root or args.candidate or Path(__file__).resolve().parents[1]).resolve()
    sys.path.insert(0, str(root))
    manifest, selected = check_selection(root)
    restored, historical = check_history(root, selected)
    lab = check_lab(selected)
    import foundation_math.hypothesis_scope as adapter
    import foundation_math_bridge.server as server
    import foundation_math_bridge.hypothesis_scope_schemas as schemas
    need(schemas.REQUEST == strict(selected['schemas/hypothesis-scope-request.schema.json']), 'embedded request schema differs from frozen lab')
    result = {'status': 'PASS', 'review': 'v0.13 independent integration',
              'selected_source_files': len(selected), 'historical_restoration': historical,
              'accepted_lab': lab, 'scope_matching': check_scope(adapter),
              'transport': check_transport(root, adapter, server), 'schemas': check_schema(schemas, server),
              'old_tool_differential': check_legacy(root, restored), 'static_surface': check_static(selected),
              'source_mutations': check_mutations(selected),
              'scope': 'Syntactic authored-premise matching and byte-integrity only; no truth, geometry, authentication, rule adequacy, formal proof or runtime promotion.',
              'limitations': ['Finite differential replay is not exhaustive program equivalence.',
                              'Trusted single-writer POSIX packaging, not race-hardening or a sandbox.',
                              'Historical full and frozen-lab aggregates must run fresh in the release gate.',
                              'No real Lean backend is installed or invoked by this review.']}
    need(all(source(root, n) == raw for n, raw in selected.items()), 'review changed candidate source')
    result['explicit_checks'] = COUNTS['explicit_checks']
    print(C(result).decode(), end='')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ReviewFailure as error:
        print(C({'status': 'FAIL', 'error': str(error)}).decode(), end='')
        raise SystemExit(1)
