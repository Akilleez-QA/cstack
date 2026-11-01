#!/usr/bin/env python3
"""Independent bounded v0.14 integration review; no long gate or provider calls.

Uses independent selection checks, reconstruction, ZIP serialization, task records,
finite differential requests, combinatorial exterior controls and fault injection.
Production functions are subjects, not expected-value oracles. Full fresh history
and lab aggregate execution is required separately by the final release gate.
"""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from itertools import combinations
from math import comb
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
BASE_MANIFEST = 'e2d034b8703bd1c98c847962627fbfd2f86c695ecc19dab83c596873f2de7de8'
BASE_ARCHIVE = '2d3098ecc24fc34c9e0e9df740a7fae4a2e10d83f16086b8ab89c1b553113bda'
RECIPE = 'e67eaa66f4f6484ca81ab1fddb313613d170bc0664e51cb315b8a39c5efc5453'
BASE_BYTES = 5979419
LABS = {
 'exterior': ('vendor/exterior-power-lab.zip', 'docs/EXTERIOR-LAB-SOURCE-MANIFEST.json',
              'a6c32c393e7ebc61af34ec50d1793f6905b85c4d0043847152fc22a79c59eb67',
              '89264e3f2d6dd2391f80bf5a1d07292a3748166bef9c60d9ab9f82c3c34d078e', 371086, 55),
 'receipt': ('vendor/validation-receipt-lab.zip', 'docs/RECEIPT-LAB-SOURCE-MANIFEST.json',
             '5edf69aab764b000aca6b24c8503e277e85abe617cbc17b61b13d74796e575b0',
             '87e9ebc74819e201513887908b67e8e4b717bf90702e64cab413eb442b094515', 326451, 41)}
CHANGED = {'README.md', 'RELEASE-FILES.json', 'foundation_math/cli.py',
 'foundation_math_bridge/__init__.py', 'foundation_math_bridge/schemas.py', 'foundation_math_bridge/server.py',
 'tests/test_agent_bridge.py', 'tests/test_character_ring_integration.py', 'tests/test_claim_revision_integration.py',
 'tests/test_hypothesis_scope_integration.py', 'tests/test_linear_algebra_bridge.py', 'tests/test_linear_systems_integration.py',
 'tests/test_portable_validation.py', 'tests/test_split_bundle_integration.py'}
PROVENANCE = 'vendor/validation-receipt-lab.zip!reference/PROVENANCE.json'
PROVENANCE_HASH = '92a0c8b93142259e399f8600970744e19a19784f3c707e5acda443985a493e3a'
CALC, CHECK, PLAN = 'calculate_formal_exterior', 'check_formal_exterior_certificate', 'plan_validation_evidence'
COUNTS = Counter()


class ReviewFailure(Exception):
    pass


def need(value, label):
    COUNTS['explicit_checks'] += 1
    if not value:
        raise ReviewFailure(label)


def H(raw):
    return sha256(raw).hexdigest()


def C(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + '\n').encode()


def J(value, ascii=True):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=ascii, allow_nan=False).encode('utf-8')


def strict(raw):
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise ReviewFailure('duplicate selected JSON key')
            out[k] = v
        return out
    def reject(token):
        raise ReviewFailure('non-exact selected JSON number')
    return json.loads(raw, object_pairs_hook=pairs, parse_float=reject, parse_constant=reject)


def source(root, name):
    p = PurePosixPath(name)
    need(type(name) is str and not p.is_absolute() and str(p) == name and
         all(x not in ('', '.', '..') for x in p.parts), 'unsafe source name')
    current = root
    for part in p.parts:
        current /= part
        need(not current.is_symlink(), 'symlink selected source')
    st = current.stat()
    need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size <= 8388608, 'nonordinary selected source')
    return current.read_bytes()


def archive(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(files.items()):
            row = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            row.create_system = 3
            row.external_attr = 0o100644 << 16
            row.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(row, data, compresslevel=9)
    return output.getvalue()


def populate(root, files):
    root.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


def selection(root):
    raw = source(root, 'SOURCE-MANIFEST.json'); manifest = strict(raw)
    selected = strict(source(root, 'RELEASE-FILES.json')); names = selected['files']
    need(raw == C(manifest) and source(root, 'RELEASE-FILES.json') == C(selected), 'canonical current metadata')
    need(selected['schema'] == 'foundation-math-v014-selected-files-v1', 'selection version')
    need(names == sorted(set(names)) and set(names) == set(manifest['files']), 'exact selected inventory')
    need('SOURCE-MANIFEST.json' not in names and 'RELEASE-FILES.json' in names, 'acyclic selection')
    for n in ('review/v014_review.py', 'review/V014-REVIEW.md', 'review/V014-REVIEW-PINS.json',
              'tools/run_exterior_evidence_validation.py', 'tools/run_full_archival_replay.py',
              'tools/reproduce_exterior_evidence_release.py'):
        need(n in names, 'required release member: ' + n)
    files = {n: source(root, n) for n in names}
    need({n: H(d) for n, d in files.items()} == manifest['files'], 'source hashes')
    need(not any(n.startswith(('evidence/', 'work/', '.git/')) or '__pycache__' in n or
                 n.endswith(('.pyc', '.pyo')) for n in names), 'generated selected source')
    need(not any(n.endswith('.zip') and not n.startswith('vendor/') for n in names), 'unexpected archive')
    need(all('vendor/foundation-math-v0' + v + '-source.zip' not in names for v in ('11', '12', '13')), 'full nested compact baseline')
    need(manifest['version'] == '0.14.0-dev' and manifest['baseline_manifest_sha256'] == BASE_MANIFEST and
         manifest['snapshot_recipe_sha256'] == RECIPE, 'provenance metadata')
    pins = strict(files['review/V014-REVIEW-PINS.json'])
    expected = set(names) - {'RELEASE-FILES.json', 'review/V014-REVIEW.md', 'review/V014-REVIEW-PINS.json'}
    need(set(pins['files']) == expected and all(H(files[n]) == v for n, v in pins['files'].items()), 'reviewer pre-freeze pins')
    need(pins['baseline_manifest_sha256'] == BASE_MANIFEST and pins['recipe_sha256'] == RECIPE, 'reviewer provenance')
    return manifest, files


def history(root, files):
    raw = files['snapshots/v013/baseline-manifest.json']; old = strict(raw)['files']
    need(H(raw) == BASE_MANIFEST and len(old) == 454, 'exact prior source manifest')
    rr = files['snapshots/v013/recipe.json']; recipe = strict(rr)
    need(H(rr) == RECIPE and rr == C(recipe), 'exact recipe bytes')
    need(set(recipe) == {'schema','zip_profile','baseline_manifest_sha256','baseline_archive_sha256',
         'baseline_archive_bytes','donor_projection_sha256','files'}, 'closed recipe')
    need(recipe['baseline_manifest_sha256'] == BASE_MANIFEST and recipe['baseline_archive_sha256'] == BASE_ARCHIVE and
         recipe['baseline_archive_bytes'] == BASE_BYTES and recipe['zip_profile'] == 'fm-v011-python-deflate9-fixed-2026-v1', 'recipe identity')
    need([r['path'] for r in recipe['files']] == sorted(old), 'recipe exact coverage')
    restored = {}; donors = {}; snapshot = {'snapshots/v013/recipe.json', 'snapshots/v013/baseline-manifest.json'}
    for row in recipe['files']:
        name = row['path']
        need(set(row) == {'path','bytes','sha256','source'} and row['sha256'] == old[name], 'recipe row')
        need(row['source'] in ('donor','blob'), 'closed recipe source')
        if row['source'] == 'donor':
            src = name; donors[name] = row['sha256']
        else:
            src = 'snapshots/v013/blobs/' + row['sha256']; snapshot.add(src)
        data = files[src]
        need(len(data) == row['bytes'] and H(data) == row['sha256'], 'exact reconstructed old bytes')
        restored[name] = data
    need(H(C(donors)) == recipe['donor_projection_sha256'] and len(donors) == 440, 'donor projection')
    need({n for n in files if n.startswith('snapshots/v013/')} == snapshot, 'selected recipe payload exact')
    need({p.relative_to(root).as_posix() for p in (root/'snapshots/v013').rglob('*') if p.is_file()} == snapshot, 'recipe disk inventory exact')
    changed = {n for n in old if files[n] != restored[n]}
    need(changed == CHANGED and set(donors) == set(old) - CHANGED, 'only declared old file changes')
    need(all(files[n] == restored[n] for n in old if n.startswith(('vendor/', 'snapshots/', 'tools/', 'review/', 'baseline_snapshot/'))), 'old history/gates unchanged')
    runtime = [n for n in old if n.startswith(('foundation_math/', 'claim_revision/', 'character_ring/', 'split_bundle/',
               'exact_linalg/', 'exact_systems/', 'bounded_counterexample/', 'polynomial_witness/', 'hypothesis_scope/')) and n != 'foundation_math/cli.py']
    need(all(files[n] == restored[n] for n in runtime), 'old math and runtime acceptance bytes unchanged')
    # All old CLI statements remain exact ASTs after removing only the two additions.
    before = ast.parse(restored['foundation_math/cli.py']); after = ast.parse(files['foundation_math/cli.py'])
    main = next(n for n in after.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    need(len(main.body) >= 3 and all(isinstance(x, ast.If) for x in main.body[1:3]), 'new CLI branches')
    del main.body[1:3]
    need(ast.dump(before) == ast.dump(after), 'historical CLI semantics changed')
    old_ast = ast.parse(restored['foundation_math_bridge/server.py']); new_ast = ast.parse(files['foundation_math_bridge/server.py'])
    defs = lambda t: {n.name: n for n in t.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    a, b = defs(old_ast), defs(new_ast)
    need(all(ast.dump(node) == ast.dump(b[name]) for name, node in a.items() if name != '_tool_result'), 'old wire/parser/dispatch functions changed')
    def branches(node):
        first = next(n for n in node.body if isinstance(n, ast.If)); rows = []
        while True:
            rows.append((ast.dump(first.test), [ast.dump(x) for x in first.body]))
            if len(first.orelse) == 1 and isinstance(first.orelse[0], ast.If):
                first = first.orelse[0]
            else:
                return rows, [ast.dump(x) for x in first.orelse]
    old_branches, old_end = branches(a['_tool_result']); new_branches, new_end = branches(b['_tool_result'])
    need(new_branches[:len(old_branches)] == old_branches and old_end == new_end, 'old tool routing changed')
    need([ast.dump(x) for x in a['_tool_result'].body[1:]] == [ast.dump(x) for x in b['_tool_result'].body[1:]], 'old result envelope semantics changed')
    restored['SOURCE-MANIFEST.json'] = raw; old_zip = archive(restored)
    need(H(old_zip) == BASE_ARCHIVE and len(old_zip) == BASE_BYTES, 'independent reconstructed original ZIP')
    from tools.exterior_evidence_release_support import restored_baseline
    with restored_baseline(root) as (tree, zipped, receipt):
        need(zipped.read_bytes() == old_zip and receipt['source_files'] == 454, 'production snapshot differs')
        need({p.relative_to(tree).as_posix() for p in tree.rglob('*') if p.is_file()} == set(restored), 'restored exact inventory')
        need(all((tree/n).read_bytes() == data for n, data in restored.items()), 'restored source bytes differ')
    return restored, old_zip, {'source_files':454,'donor_files':440,'old_byte_blobs':14,
            'archive_sha256':H(old_zip),'archive_bytes':len(old_zip),'unchanged_runtime_files':len(runtime)}


def lab_integrity(files):
    reports = {}; receipt_members = None
    for label, (path, mf, zh, mh, size, count) in LABS.items():
        need(H(files[path]) == zh and len(files[path]) == size and H(files[mf]) == mh, 'accepted lab artifact pins')
        manifest = strict(files[mf])['files']; need(len(manifest) == count, 'accepted lab count')
        with zipfile.ZipFile(io.BytesIO(files[path])) as z:
            need(z.namelist() == sorted([*manifest, 'SOURCE-MANIFEST.json']), 'accepted lab exact inventory')
            members = {n: z.read(n) for n in z.namelist()}
            for row in z.infolist():
                need(row.external_attr == 0o100644 << 16 and row.file_size <= 8388608, 'accepted lab metadata')
        need(members['SOURCE-MANIFEST.json'] == files[mf], 'accepted lab manifest bytes')
        need(all(H(members[n]) == pin['sha256'] and len(members[n]) == pin['bytes'] for n, pin in manifest.items()), 'accepted lab source pins')
        package, examples, prefix = ('exterior_power','exterior-power','EXTERIOR-LAB-') if label == 'exterior' else ('validation_receipt','validation-evidence','RECEIPT-LAB-')
        mapping = {}
        for n in manifest:
            if n.startswith(package+'/'): mapping[n] = n
            elif n.startswith('examples/') and n.endswith('.json'): mapping['examples/'+examples+'/'+n.split('/',1)[1]] = n
            elif n.startswith('docs/') and n.endswith('.md'): mapping['docs/'+prefix+n.split('/',1)[1]] = n
        if label == 'receipt':
            mapping['schemas/validation-evidence-request.schema.json'] = 'schema/input.schema.json'; receipt_members = members
        need(all(files[n] == members[o] for n, o in mapping.items()), 'accepted lab transplanted bytes')
        need(strict(files['EXTERIOR-EVIDENCE-PINS.json'])['labs'][label]['source_pins'] == {n:manifest[o] for n,o in mapping.items()}, 'transplant pin coverage')
        reports[label] = {'archive_sha256':zh,'manifest_sha256':mh,'source_files':count,'byte_preserved_copies':len(mapping)}
    return reports, receipt_members


def clean_env():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONOPTIMIZE='0')
    for key in ('PYTHONPATH','PYTHONHOME','SPLIT_REVIEW_ROOT'):
        env.pop(key, None)
    return env


def bridge_run(root, frames, mode):
    code = 'import runpy,sys;sys.path.insert(0,sys.argv[1]);expected=int(sys.argv[2]);sys.exit(93) if sys.flags.optimize!=expected else None;sys.argv=["bridge"];runpy.run_module("foundation_math_bridge",run_name="__main__")'
    p = subprocess.run([sys.executable,'-I','-B',*(['-O'] if mode else []),'-c',code,str(root),str(mode)],
        input=b''.join(J(f)+b'\n' for f in frames),cwd=root,env=clean_env(),capture_output=True,timeout=120)
    need(p.returncode == 0 and not p.stderr, 'independent differential subprocess')
    return [json.loads(line) for line in p.stdout.splitlines()]


def frame(name, args, identifier=7):
    return {'jsonrpc':'2.0','id':identifier,'method':'tools/call','params':{'name':name,'arguments':args}}


def legacy_differential(root, restored):
    get = lambda n: strict(restored[n])
    cases = [
     ('exact_scalar', {'domain':'Q','operation':'multiply','operands':[{'numerator':-7,'denominator':9},{'numerator':3,'denominator':14}]}),
     ('polynomial_identity', get('examples/polynomial/distributivity.json')),
     ('finite_box_search', get('examples/counterexample/false-bounded-inequality.json')),
     ('check_finite_box_witness', {'request':get('examples/counterexample/false-bounded-inequality.json'),'assignment':get('examples/counterexample/valid-witness.json')}),
     ('certify_rational_matrix', {'matrix':get('examples/linear-algebra/rectangular-matrix.json')}),
     ('check_rational_matrix_certificate', {'matrix':get('examples/linear-algebra/rectangular-matrix.json'),'certificate':get('examples/linear-algebra/rectangular-certificate.json')}),
     ('construct_polynomial_witness', {'request':get('examples/polynomial-witness/false-square.json')}),
     ('check_polynomial_witness', {'request':get('examples/polynomial-witness/false-square.json'),'witness':get('examples/polynomial-witness/false-square-witness.json')}),
     ('solve_rational_linear_system', {'system':get('examples/linear-systems/consistent-system.json')}),
     ('check_rational_linear_system_certificate', {'system':get('examples/linear-systems/consistent-system.json'),'certificate':get('examples/linear-systems/consistent-certificate.json')}),
     ('calculate_fixed_character', {'request':get('examples/character-ring/distinct_doublets.request.json')}),
     ('check_fixed_character_certificate', {'request':get('examples/character-ring/distinct_three_spaces.request.json'),'certificate':get('examples/character-ring/distinct_three_spaces.certificate.json')}),
     ('calculate_formal_split_bundle', {'request':get('examples/split-bundle/hom_not_map_rank.request.json')}),
     ('check_formal_split_bundle_certificate', {'request':get('examples/split-bundle/hom_not_map_rank.request.json'),'certificate':get('examples/split-bundle/hom_not_map_rank.certificate.json')}),
     ('replay_claim_applicability', {'ledger':get('examples/claim-revision/diamond-shortest-path.ledger.json')}),
     ('match_hypothesis_scope', {'document':get('examples/hypothesis-scope/exact-full-kernel.json')})]
    requests = []
    for name,args in cases:
        requests.extend([(name,args),(name,{}),(name,None),(name,dict(args,execute=True))])
    init = {'jsonrpc':'2.0','id':'init','method':'initialize','params':{'protocolVersion':'foundation-math-jsonrpc/1'}}
    frames = [init,{'jsonrpc':'2.0','id':'list','method':'tools/list'}] + [frame(n,a,i) for i,(n,a) in enumerate(requests)]
    hashes = []
    with tempfile.TemporaryDirectory(prefix='v014-review-old-') as td:
        base = Path(td); populate(base, restored)
        for mode in (0,1):
            old, new = bridge_run(base,frames,mode), bridge_run(root,frames,mode)
            need(len(old) == len(new) == len(frames), 'differential response count')
            ov = old[0]['result']['serverInfo'].pop('version'); nv = new[0]['result']['serverInfo'].pop('version')
            need((ov,nv) == ('0.13.0-dev','0.14.0-dev') and old[0] == new[0], 'old initialization contract')
            ot,nt = old[1]['result']['tools'],new[1]['result']['tools']
            need(len(ot) == 16 and len(nt) == 19 and ot == nt[:16], 'all sixteen complete old tool contracts')
            need([t['name'] for t in nt[16:]] == [CALC,CHECK,PLAN], 'three appended adapters only')
            need([t['name'] for t in ot] == [n for n,a in cases], 'old tool coverage')
            need(old[2:] == new[2:], 'old finite differential responses')
            for i in range(16):
                need('result' in old[2+4*i] and not old[2+4*i]['result']['isError'], 'positive legacy fixture '+cases[i][0])
            hashes.append(H(J(old[2:])))
    need(len(set(hashes)) == 1, 'normal/optimized old differential')
    return {'complete_contracts':16,'calls_per_mode':len(requests),'modes':[0,1],'response_sha256':hashes[0]}


def new_bridge():
    from foundation_math_bridge.server import Bridge
    b = Bridge(); b.initialized = True
    return b


def receipt(response):
    need('result' in response and not response['result']['isError'], 'successful new bridge operation')
    out = response['result']['structuredContent']
    need(out['formal_proof'] is False and out['runtime_goal_acceptance'] is False, 'outer no-promotion flags')
    return out['receipt']


def exterior_checks(root):
    from foundation_math.exterior import calculate_exterior, check_exterior_certificate
    from foundation_math_bridge import server as srv
    from foundation_math_bridge.schemas import tool_definitions
    from jsonschema import Draft202012Validator
    need((srv.MAX_FRAME_BYTES,srv.MAX_OUTPUT_BYTES,srv.MAX_JSON_NODES,srv.MAX_JSON_DEPTH,
          srv.MAX_STRING_CHARS,srv.MAX_INTEGER_BITS,srv.MAX_ID_CHARS) == (65536,1048576,16384,80,4096,4096,128), 'unchanged bridge limits')
    schemas = {t['name']:t for t in tool_definitions()[16:]}
    for t in schemas.values():
        need(t['readOnly'] is True, 'new tool read-only contract')
        for k in ('inputSchema','outputSchema'): Draft202012Validator.check_schema(t[k])
    # Independent subset enumeration for trivial-character line sums, including
    # duplicate summands, negative grades, order zero and above-rank zero.
    families = [(),(0,),(-2,3),(-1,-1,2),(0,0,0,0),(-3,-1,0,2,4)]
    successes = 0
    for grades in families:
        request = {'schema':'fm-exterior-request-v1','operation':'bundle','bundle':[
          {'irrep':'1','twist':d,'multiplicity':1} for d in grades],'orders':list(range(len(grades)+2))}
        before = deepcopy(request); b = new_bridge(); response = b.handle(J(frame(CALC,{'request':request})))
        result = receipt(response); cert = result['result']['certificate']
        need(request == before, 'input not mutated')
        Draft202012Validator(schemas[CALC]['outputSchema']).validate(response['result']['structuredContent'])
        for p in cert['result']['powers']:
            k = p['order']; expected = Counter(sum(c) for c in combinations(grades,k))
            terms = p['bundle']['terms']
            need({t['line_degree']:t['character']['multiplicities'] for t in terms} == {d:{'1':n} for d,n in sorted(expected.items())}, 'independent subset exterior coefficients')
            need(p['bundle']['rank'] == (comb(len(grades),k) if k <= len(grades) else 0), 'independent exterior binomial rank')
            need(p['bundle']['degree'] == sum(d*n for d,n in expected.items()), 'independent graded exterior degree')
        for identifier in (0,-9007199254740991,'x'*128,'\uffff'*128,'\U0010ffff'*128):
            wire = J(frame(CHECK,{'request':request,'certificate':cert},identifier))
            need(len(wire) <= 65536, 'successful producer whole certificate roundtrip fits')
            checked = receipt(b.handle(wire)); need(checked['result']['verification']['status'] == 'verified','roundtrip independently verifies')
        for key,value in [('scope','proof'),('catalog_sha256','0'*64),('request_sha256','0'*64)]:
            bad=deepcopy(cert);bad[key]=value
            need(check_exterior_certificate(request,bad)['status'] == 'error', 'certificate binding mutation rejected')
        bad=deepcopy(cert);bad['result']['powers'][0]['bundle']['rank'] += 1
        need(check_exterior_certificate(request,bad)['status'] == 'error', 'certificate arithmetic mutation rejected')
        successes += 1
    # The independently discovered natural astral-ID counterexample.
    req={'schema':'fm-exterior-request-v1','operation':'bundle','bundle':[
         {'irrep':'1','twist':d,'multiplicity':1} for d in range(-6,6)],'orders':[1,2,3,4,5,6,7,9,10]}
    cert=calculate_exterior(req)['result']['certificate']
    sizes=[len(J(frame(CHECK,{'request':req,'certificate':cert},id))) for id in ('\uffff'*128,'\U0010ffff'*128)]
    need(sizes == [65463,66231], 'natural astral-ID boundary sizes')
    result=new_bridge().handle(J(frame(CALC,{'request':req})))
    need(result.get('error',{}).get('code') == -32002 and 'result' not in result, 'astral-ID roundtrip bound must withhold entire producer result')
    # Natural node-count control stays well below byte cap; no reduced threshold.
    bad={'values':[0]*16400}; need(len(J(frame(CHECK,{'request':{},'certificate':bad}))) < 65536,'node-only boundary fixture')
    try: srv._exterior_roundtrip({},bad)
    except srv.WireError as e: need(e.code == -32002, 'natural node-limit rejection')
    else: need(False,'roundtrip ignored node limit')
    request={'schema':'fm-exterior-request-v1','operation':'representation','representation':{'W':1},'orders':[0,1,2,3]}
    cert=calculate_exterior(request)['result']['certificate']
    need([p['character']['multiplicities'] for p in cert['result']['powers']] == [{'1':1},{'W':1},{'1':1},{}], 'physical W and determinant boundary')
    other=deepcopy(request);other['representation']={'Wp':1}
    need(calculate_exterior(other)['result']['certificate']['result']['powers'][1]['character']['multiplicities'] == {'Wp':1}, 'physical Wp not W')
    illustration={'schema':'fm-exterior-request-v1','operation':'wedge_h0_comparison','source':[{'irrep':'S4','twist':-1,'multiplicity':1}],
        'target':[{'irrep':'W','twist':-1,'multiplicity':1},{'irrep':'Wp','twist':-1,'multiplicity':1}], 'orders':[1,2],'twists':[1,6]}
    comparisons=calculate_exterior(illustration)['result']['certificate']['result']['comparisons']
    lookup={(x['order'],x['twist']):x['target_minus_source'] for x in comparisons}
    need(lookup[(1,6)] == {} and lookup[(2,6)] == {'1':-1,'D':1,'P':-1} and lookup[(1,1)] == {'W':1,'Wp':1,'S4':-1}, 'finite illustration not all-twist claim')
    # Independently import checker-only in a clean child, never importing producer.
    code='import sys,json;sys.path.insert(0,sys.argv[1]);from foundation_math.exterior import check_exterior_certificate;r,c=json.load(sys.stdin);x=check_exterior_certificate(r,c);print(json.dumps([x,"exterior_power.producer" in sys.modules,"exterior_power.fusion" in sys.modules]))'
    p=subprocess.run([sys.executable,'-I','-B','-c',code,str(root)],input=J([request,cert]),env=clean_env(),capture_output=True,timeout=60)
    need(p.returncode == 0,'checker-only process'); x,producer,fusion=json.loads(p.stdout)
    need(x['status']=='success' and not producer and not fusion,'checker independent import boundary')
    return {'independent_subset_families':successes,'successful_roundtrip_id_shapes':5,'natural_astral_boundary_bytes':sizes,
            'natural_node_boundary_checked':True,'physical_labels_preserved':True,'finite_illustration_scope_checked':True}


def record(identifier, content):
    body={'id':identifier,'revision':1,'content':deepcopy(content)}
    return {**body,'revision_sha256':H(J(body,ascii=False))}


def pin(r):
    return {k:r[k] for k in ('id','revision','revision_sha256')}


def planning_document(role='historical_component', environment_known=True, closure_known=True):
    c={'role':role,'invocation':{'argv':['this-is-inert-data','; touch NEVER_EXECUTE'], 'cwd':'.','stdin_sha256':'0'*64},
       'inputs':[{'path':'fixture.txt','bytes':3,'sha256':'1'*64}],
       'environment':{'runner_sha256':'2'*64 if environment_known else None,'environment_sha256':'3'*64 if environment_known else None,'description':'Fabricated review fixture; not measured execution.'},
       'closure':{'declaration':'caller_declares_complete' if closure_known else 'unknown','files':'exact_selected_manifest',
                  'process_state':'pinned_environment_and_stdin','external_state':'none','randomness':'none','clock':'none'},'dependencies':[]}
    task=record('task',c)
    r=record('receipt',{'task':pin(task),'availability':'supplied','result':{'outcome':'declared_pass','exit_code':0,'output_sha256':'4'*64},'dependency_receipts':[]})
    return {'schema':'foundation-math-validation-receipt-plan/1','tasks':[task],'receipts':[r],'selections':[{'task':pin(task),'receipt':pin(r)}]}


def planner_checks():
    from foundation_math.validation_evidence import plan_validation_evidence
    from foundation_math_bridge.schemas import tool_definitions
    from foundation_math_bridge import server as srv
    from jsonschema import Draft202012Validator
    tool=tool_definitions()[-1]; iv=Draft202012Validator(tool['inputSchema']); ov=Draft202012Validator(tool['outputSchema'])
    cases=[('historical_component',True,True,[]),('current_runtime',True,True,['mandatory_fresh_policy']),
           ('new_adapter',True,True,['mandatory_fresh_policy']),('archival_full_replay',True,True,['mandatory_fresh_policy']),
           ('historical_component',False,True,['environment_pin_unknown']),('historical_component',True,False,['closure_not_declared_complete'])]
    flags=('execution_performed','fresh_pass_claimed','skip_authorized','closure_verified','artifact_bytes_verified','authenticity_verified','mathematical_truth_checked','proof_acceptance_changed')
    for role,env,closure,reasons in cases:
        doc=planning_document(role,env,closure);before=deepcopy(doc);iv.validate({'document':doc})
        with patch('subprocess.run',side_effect=ReviewFailure('planner executed a process')):
            out=new_bridge().handle(J(frame(PLAN,{'document':doc})))
        value=receipt(out);ov.validate(out['result']['structuredContent']); result=value['result']; task=result['tasks'][0]
        need([x['code'] for x in task['reasons']] == reasons,'independent planner reason list')
        need(task['classification'] == ('MUST_RUN_FRESH' if reasons else 'PRIOR_PINNED_EVIDENCE_MATCHES'), 'independent planner classification')
        need(all(result[k] is False for k in flags) and all(value[k] is False for k in ('execution_performed','fresh_pass_claimed','skip_authorized')), 'planner never authorizes skips/execution')
        need(result['input_sha256'] == H(J(doc,ascii=False)) and task['selected_manifest_sha256'] == H(J(doc['tasks'][0]['content']['inputs'],ascii=False)), 'independent task/report hashing')
        expected = {'schema':'foundation-math-validation-receipt-report/1',
          'input_sha256':H(J(doc,ascii=False)), 'scope':'Syntactic integrity and applicability within a caller-declared closed input boundary only.',
          **{k:False for k in flags}, 'tasks':[{'task':pin(doc['tasks'][0]),
            'classification':'MUST_RUN_FRESH' if reasons else 'PRIOR_PINNED_EVIDENCE_MATCHES',
            'selected_receipt':pin(doc['receipts'][0]), 'supplied_receipt':pin(doc['receipts'][0]),
            'selected_manifest_sha256':H(J(doc['tasks'][0]['content']['inputs'],ascii=False)),
            'fresh_dependencies':[], 'fresh_ancestors':[],
            'reasons':[{'code':r,'subject':'task','expected':None,'supplied':None} for r in reasons]}]}
        need(result == expected, 'independently assembled complete planner report')
        need(doc == before,'planner input not mutated')
        for k in flags:
            bad=deepcopy(out['result']['structuredContent']);bad['receipt']['result'][k]=True
            need(bool(list(ov.iter_errors(bad))),'planner schema denies '+k)
    doc=planning_document();doc['selections']=[]
    need(plan_validation_evidence(doc)['result']['tasks'][0]['reasons'][0]['code']=='prior_receipt_not_selected','no implicit latest')
    for name,args,attribute in [(CALC,{'request':{}},'calculate_exterior'),(CHECK,{'request':{},'certificate':{}},'check_exterior_certificate'),(PLAN,{'document':doc},'plan_validation_evidence')]:
        for key in ('path','command','execute','skip','proof','limits'):
            out=new_bridge().handle(J(frame(name,{**args,key:True})))
            need(out.get('error',{}).get('code')==-32602,'closed adapter arguments')
        notification=frame(name,args);del notification['id']
        with patch.object(srv,attribute,side_effect=ReviewFailure('notification executed work')) as mock:
            need(new_bridge().handle(J(notification)) is None and mock.call_count==0,'notifications inert')
    with patch.object(srv,'plan_validation_evidence',side_effect=RuntimeError('PRIVATE_DETAIL')):
        out=new_bridge().handle(J(frame(PLAN,{'document':planning_document()})))
    need(out.get('error',{}).get('code')==-32603 and b'PRIVATE_DETAIL' not in J(out),'closed unexpected exception')
    return {'independent_classification_cases':len(cases),'positive_match_is_not_execution':True,'mandatory_fresh_roles':3,'nonclaims_per_plan':8}


def cli_checks(root):
    from foundation_math import exterior, validation_evidence
    cases = [(['exterior-calculate','examples/exterior-power/irrep-W.request.json'], b'', 0),
             (['exterior-check','examples/exterior-power/irrep-W.request.json','examples/exterior-power/irrep-W.certificate.json'], b'', 0),
             (['exterior-calculate'], b'', 2),
             (['validation-evidence-plan'], J(planning_document()), 0),
             (['validation-evidence-plan','unexpected-path'], J(planning_document()), 2),
             (['validation-evidence-plan'], b'{"x":1,"x":2}', 2)]
    raw=J(planning_document())
    cases.extend([(['validation-evidence-plan'],raw+b' '*(n-len(raw)),expected) for n,expected in [(262144,0),(262145,2)]])
    code=('import runpy,sys;sys.path.insert(0,sys.argv[1]);expected=int(sys.argv[2]);'
          'sys.exit(94) if sys.flags.optimize!=expected else None;'
          'sys.argv=["foundation_math"]+sys.argv[3:];runpy.run_module("foundation_math",run_name="__main__")')
    for mode in (0,1):
        for args,data,status in cases:
            p=subprocess.run([sys.executable,'-I','-B',*(['-O'] if mode else []),'-c',code,str(root),str(mode),*args],
                input=data,cwd=root,env=clean_env(),capture_output=True,timeout=60)
            need(p.returncode==status and not p.stderr,'CLI command/exit contract')
            out=json.loads(p.stdout);need(out['formal_proof'] is False and out['runtime_goal_acceptance'] is False,'CLI no promotion')
            need((out['status']=='success') == (status==0),'CLI receipt/exit consistency')
    for module,func,args,input_bytes in [
       (exterior,exterior.exterior_cli,['exterior-calculate',str(root/'examples/exterior-power/irrep-W.request.json')],b''),
       (validation_evidence,validation_evidence.validation_evidence_cli,['validation-evidence-plan'],J(planning_document()))]:
        output=io.StringIO();input_stream=types.SimpleNamespace(buffer=io.BytesIO(input_bytes))
        with patch.object(module,'MAX_OUTPUT_BYTES',32),patch.object(module.sys,'stdout',output),patch.object(module.sys,'stdin',input_stream):
            status=func(args)
        result=json.loads(output.getvalue())
        need(status==2 and result['status']=='error' and 'result' not in result,'whole CLI envelope withheld on overflow')
    return {'cases_per_mode':len(cases),'modes':[0,1],'real_stdin_byte_boundary':[262144,262145],
            'reduced_limit_whole_output_controls':2}


def integration_mutations(root):
    # Every selected mutation returns normally before a specific semantic
    # assertion detects the fault; exceptions or import failures never count.
    raw=(root/'foundation_math_bridge/server.py').read_text()
    req={'schema':'fm-exterior-request-v1','operation':'bundle','bundle':[
      {'irrep':'1','twist':d,'multiplicity':1} for d in range(-6,6)],'orders':[1,2,3,4,5,6,7,9,10]}
    mutants=[('bmp_instead_of_astral_reservation',"'\\U0010ffff' * MAX_ID_CHARS","'\\uffff' * MAX_ID_CHARS"),
             ('omit_whole_roundtrip_guard','    decode_frame(raw)\n','    return None\n')]
    killed=[]
    for name,old,new in mutants:
        need(raw.count(old)==1,'unique integration mutation target')
        namespace={'__name__':'foundation_math_bridge.review_mutant','__package__':'foundation_math_bridge'}
        exec(compile(raw.replace(old,new),'<independent-integration-mutant>','exec'),namespace)
        b=namespace['Bridge']();b.initialized=True
        result=b.handle(J(frame(CALC,{'request':req})))
        need('result' in result and not result['result']['isError'],'mutant returned successfully, not incidental crash')
        need(result.get('error',{}).get('code') != -32002,'expected boundary regression detected')
        killed.append(name)
    raw=(root/'foundation_math/validation_evidence.py').read_text()
    old="'skip_authorized': False";need(raw.count(old)==1,'unique planner adapter mutation target')
    namespace={'__name__':'foundation_math.review_mutant','__package__':'foundation_math'}
    exec(compile(raw.replace(old,"'skip_authorized': True"),'<independent-integration-mutant>','exec'),namespace)
    result=namespace['plan_validation_evidence'](planning_document())
    need(result['status']=='success' and result['skip_authorized'] is True,'successful semantic skip-authority mutation detected')
    killed.append('promote_planner_to_skip_authority')
    return {'semantic_mutants_killed':len(killed),'names':killed,'incidental_crashes_counted':False}


def freshness_checks(root, restored, old_zip, receipt_members):
    # Audit exact imported/called surfaces; do not interpret invocation text.
    for name in ('validation_receipt/core.py','foundation_math/validation_evidence.py','foundation_math_bridge/validation_evidence_schemas.py'):
        tree=ast.parse((root/name).read_bytes())
        for node in ast.walk(tree):
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                imports=[n.name for n in node.names] if isinstance(node,ast.Import) else [node.module or '']
                need(all(n.split('.')[0] in ('hashlib','json','re','sys','copy','validation_receipt') for n in imports), 'planner import whitelist')
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
                need(node.func.id not in ('eval','exec','compile','__import__','open'), 'planner executable call surface')
    gate_names=('tools/run_exterior_evidence_validation.py','tools/run_full_archival_replay.py','tools/reproduce_exterior_evidence_release.py')
    for name in gate_names:
        tree=ast.parse((root/name).read_bytes())
        strings={n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
        need(not any('PRIOR_PINNED_EVIDENCE_MATCHES' in s or '--skip' in s for s in strings),'gate contains skip profile')
        need(not any(isinstance(n,ast.Name) and n.id in ('plan','plan_validation_evidence') for n in ast.walk(tree)),'gate depends on planner result')
    delivery=json.loads(receipt_members['reference/v013-delivery-replay.json'])
    def keys(v):
        if isinstance(v,dict):
            return set(v).union(*(keys(x) for x in v.values()))
        if isinstance(v,list):return set().union(*(keys(x) for x in v))
        return set()
    need(not {'runner_sha256','environment_sha256','closure'} & keys(delivery), 'prior delivery unexpectedly provides exact closure prerequisites')
    # Actual orchestration function, instrumented rather than running long history.
    from tools import run_full_archival_replay as historical
    from contextlib import contextmanager
    calls=[]
    with tempfile.TemporaryDirectory(prefix='v014-review-gate-') as td:
        temp=Path(td);base=temp/'base';populate(base,restored);z=temp/'baseline.zip';z.write_bytes(old_zip)
        @contextmanager
        def replacement(root):yield base,z,{'source_files':454}
        def fake_run(tree,script,*args,**kwargs):
            calls.append(script)
            if script=='tools/build_hypothesis_scope_release.py':
                Path(kwargs['args'][1]).write_bytes(old_zip)
                return types.SimpleNamespace(stdout='{}')
            need(script=='tools/run_hypothesis_scope_validation.py','unanticipated historical command')
            return types.SimpleNamespace(stdout=json.dumps({'status':'passed','source_manifest_sha256':BASE_MANIFEST}))
        with patch.object(historical,'restored_baseline',replacement),patch.object(historical,'run',fake_run):
            report=historical.replay(root)
        need(calls==['tools/build_hypothesis_scope_release.py','tools/run_hypothesis_scope_validation.py'],'full prior builder and aggregate mandatory')
        need(report['prior_pinned_evidence_reused'] is False and report['v013_gate_modified'] is False,'historical no-reuse semantics')
    # Forced actual mode under hostile inherited settings, with observations only.
    from tools.exterior_evidence_validation_runner import run
    modes=[]
    with tempfile.TemporaryDirectory(prefix='v014-review-mode-') as td:
        p=Path(td);(p/'probe.py').write_text('import sys,json;print(json.dumps({"actual":sys.flags.optimize}))\n')
        for mode in (0,1):
            with patch.dict(os.environ,{'PYTHONOPTIMIZE':'2','PYTHONPATH':'invalid','PYTHONHOME':'invalid'}):
                child=run(p,'probe.py',bool(mode),log_dir=p,label='mode'+str(mode))
            need(json.loads(child.stdout)['actual']==mode,'actual child mode')
            measurement=json.loads((p/('mode'+str(mode)+'.measurement.json')).read_bytes())
            need(measurement['closure_certified'] is False and measurement['historical_reuse_authorized'] is False,'timing not reuse authority')
            modes.append(mode)
    return {'prior_exact_runner_environment_closure_unavailable':True,'full_archival_orchestration_instrumented':True,
            'full_archival_execution_in_this_review':False,'planner_controls_gate':False,'actual_child_modes':modes}


def privacy_checks(root, manifest, files, receipt_members):
    provenance=receipt_members['reference/PROVENANCE.json']
    need(H(provenance)==PROVENANCE_HASH,'exact provenance exception hash')
    doc=json.loads(provenance);need(set(doc)=={'pins','scope'} and len(doc['pins'])==10,'closed technical provenance shape')
    need(all(set(v)=={'bytes','sha256','source'} and type(v['bytes']) is int and len(v['sha256'])==64 for v in doc['pins'].values()),'technical provenance metadata only')
    need(provenance.decode().count('/workspace/')==10,'ten reviewed technical source paths')
    # Independent recursive scanner, including older archives. The exception is
    # evaluated only for one exact qualified member and exact bytes.
    markers=('/workspace/','/home/','file://','codex://','ghp_','sk-proj-','BEGIN PRIVATE KEY','BEGIN RSA PRIVATE KEY')
    exceptions=[];counts=Counter()
    def scan(name,raw,depth=0):
        need(depth<=8,'nested archive scan depth')
        if name.endswith('.zip'):
            counts['archives']+=1
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                need(len(z.infolist())<=4096 and sum(i.file_size for i in z.infolist())<=67108864,'archive scan bounds')
                for i in z.infolist():
                    if not i.is_dir():scan(name+'!'+i.filename,z.read(i),depth+1)
        elif name.endswith(('.md','.json','.jsonl','.txt')):
            counts['text_files']+=1;text=raw.decode()
            for marker in markers:
                if marker in text:
                    need(name==PROVENANCE and H(raw)==PROVENANCE_HASH and marker=='/workspace/' and text.count(marker)==10,'unreviewed privacy/path marker')
                    exceptions.append(name)
    for name,data in sorted({**files,'SOURCE-MANIFEST.json':(root/'SOURCE-MANIFEST.json').read_bytes()}.items()):scan(name,data)
    need(exceptions==[PROVENANCE],'exactly one exception, no broad bypass')
    from tools.v014_privacy import privacy
    report=privacy(root,manifest)
    need(report['findings']==[] and len(report['reviewed_provenance_exceptions'])==1,'production exception report')
    # Mutate only detached fixtures, never selected sources.
    controls=[('reference/PROVENANCE.json',provenance+b'\n'),('reference/OTHER.json',provenance),
              ('reference/PROVENANCE.json',provenance.replace(b'/workspace/',b'/home/',1)),
              ('reference/PROVENANCE.json',provenance+b'\nsk-proj-test-only\n')]
    with tempfile.TemporaryDirectory(prefix='v014-review-privacy-') as td:
        temp=Path(td);(temp/'vendor').mkdir();(temp/'SOURCE-MANIFEST.json').write_bytes(b'{}\n')
        f=temp/'vendor/validation-receipt-lab.zip'; fake={'files':{'vendor/validation-receipt-lab.zip':'unused'}}
        f.write_bytes(archive({'reference/PROVENANCE.json':provenance}));privacy(temp,fake)
        for name,data in controls:
            f.write_bytes(archive({name:data}))
            try: privacy(temp,fake)
            except RuntimeError: pass
            else: need(False,'privacy exception mutation accepted')
            COUNTS['privacy_rejection_controls']+=1
        f.write_bytes(archive({'reference/PROVENANCE.json':provenance,'extra.json':b'{"path":"/workspace/unreviewed"}'}))
        try:privacy(temp,fake)
        except RuntimeError:pass
        else:need(False,'extra marker bypassed exact exception')
        COUNTS['privacy_rejection_controls']+=1
    return {'exact_member':PROVENANCE,'sha256':PROVENANCE_HASH,'technical_paths':10,
            'independent_scanned_archives':counts['archives'],'independent_scanned_text_files':counts['text_files'],
            'rejection_controls':COUNTS['privacy_rejection_controls'],'universal_secret_detection_claimed':False}


def packaging(root,manifest,files):
    from tools.build_exterior_evidence_release import create_zip,verify
    payload={**files,'SOURCE-MANIFEST.json':(root/'SOURCE-MANIFEST.json').read_bytes()};expected=archive(payload)
    with tempfile.TemporaryDirectory(prefix='v014-review-package-') as td:
        path=Path(td)/'built.zip';out=create_zip(path,root)
        need(path.read_bytes()==expected and out['sha256']==H(expected),'independent final selected ZIP bytes')
        with zipfile.ZipFile(path) as z:
            need(z.namelist()==sorted(payload),'final ZIP inventory')
            for row in z.infolist():
                need(row.date_time==(2026,1,1,0,0,0) and row.external_attr==0o100644<<16 and row.create_system==3 and row.compress_type==zipfile.ZIP_DEFLATED,'final ZIP metadata')
        target=Path(td)/'clean';populate(target,payload)
        need(verify(target)==manifest,'selected-only verification')
        # Source drift is rejected even though stale source metadata is present.
        p=target/'foundation_math/exterior.py';p.write_bytes(p.read_bytes()+b'\n')
        try:verify(target)
        except RuntimeError:pass
        else:need(False,'selected-only source drift accepted')
    # Avoid self-referential archive pins in selected reports; the actual final
    # archive identity is delivered in external release evidence.
    return {'independent_final_zip_bytes_equal':True,'zip_members':len(payload),'selected_only_verification':True,'source_drift_rejected':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',nargs='?',type=Path);parser.add_argument('--root',dest='named_root',type=Path)
    args=parser.parse_args();root=(args.named_root or args.root or Path(__file__).resolve().parents[1]).resolve();sys.path.insert(0,str(root))
    manifest,files=selection(root)
    restored,old_zip,hist=history(root,files)
    labs,receipt_members=lab_integrity(files)
    report={'status':'PASS','baseline':hist,'accepted_labs':labs,'legacy_differential':legacy_differential(root,restored),
            'exterior':exterior_checks(root),'planner':planner_checks(),'cli':cli_checks(root),'integration_mutations':integration_mutations(root),
            'freshness':freshness_checks(root,restored,old_zip,receipt_members),
            'privacy':privacy_checks(root,manifest,files,receipt_members),'packaging':packaging(root,manifest,files)}
    need(all(H(source(root,n))==pin for n,pin in manifest['files'].items()),'final source drift')
    report['checks']=dict(sorted(COUNTS.items()))
    report['scope']='Focused independent integration checks, not exhaustive mathematical proof, authenticity, real geometry, actual HM data, prior execution reuse or the long final delivery gate.'
    print(C(report).decode(),end='')


if __name__=='__main__':
    main()
