"""Independent executable review. Explicit checks remain effective under -O."""
from copy import deepcopy
from itertools import product
from pathlib import Path
from collections import Counter
import ast
import hashlib
import importlib.util
import json
import os
import random
import subprocess
import sys
import types
from unittest.mock import patch

from oracle import canonical, sha, seal, pin, node, event, document, model

class ReviewFailure(Exception):
    pass

def check(condition, message):
    if not condition:
        raise ReviewFailure(message)


def load_core(root):
    spec = importlib.util.spec_from_file_location('candidate_core', root / 'claim_revision/core.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_cases():
    a = node('Root', 'evidence')
    b = node('APath', 'obligation', [a])
    c = node('ZPath', 'claim', [a])
    d = node('Tip', 'claim', [c, b])
    independent = node('Unrelated', status='claimed_established')
    yield 'diamond_lex_tie', document([d, c, a, independent, b], [event('withdraw', a, 'withdraw_root')])
    d2 = node('Tip', 'claim', [c, a, b])
    yield 'shortest_beats_lex', document([a, b, c, d2], [event('withdraw', a, 'withdraw_root')])
    yield 'multiple_independent_causes', document([a, b, c, d], [event('withdraw', a, 'root_w'), event('withdraw', c, 'path_w')])
    a2 = node('Root', 'evidence', revision=2)
    a3 = node('Root', 'evidence', revision=3)
    yield 'withdraw_then_revise', document([a, b, c, d], [event('withdraw', a, 'root_w'), event('revise', a, 'root_r', replacement=a2)])
    yield 'stale_does_not_inherit_replacement', document([a, b, c, d], [event('revise', a, 'root_r', replacement=a2), event('withdraw', a2, 'root_w2')])
    yield 'latest_revision_event', document([a, b, c, d], [event('revise', a, 'root_r2', replacement=a2), event('revise', a2, 'root_r3', replacement=a3)])
    b2 = node('APath', 'obligation', [a2], revision=2)
    c2 = node('ZPath', 'claim', [a2], revision=2)
    d2 = node('Tip', 'claim', [b2, c2], revision=2)
    repair = [event('withdraw', a, 'w'), event('revise', a, 'ra', replacement=a2), event('revise', b, 'rb', replacement=b2), event('revise', c, 'rc', replacement=c2), event('revise', d, 'rd', replacement=d2)]
    yield 'explicit_repin_all', document([a, b, c, d], repair)
    yield 'explicit_repin_partial', document([a, b, c, d], repair[:-1])
    claim = node('Claim', status='claimed_refuted')
    dependent = node('Review', 'obligation', [claim])
    ce = node('Counter', 'evidence')
    claim2 = node('Claim', revision=2)
    ce2 = node('Counter', 'evidence', revision=2)
    report = event('record_refutation_report', claim, 'objection', evidence=pin(ce))
    yield 'unchecked_objection_not_truth', document([claim, dependent, ce], [report])
    yield 'withdrawn_counter_still_reportable', document([claim, dependent, ce], [event('withdraw', ce, 'wc'), report])
    yield 'counter_revision_keeps_exact_objection', document([claim, dependent, ce], [report, event('revise', ce, 'rc', replacement=ce2)])
    yield 'counter_withdrawal_keeps_exact_objection', document([claim, dependent, ce], [report, event('withdraw', ce, 'wc')])
    yield 'historical_report_and_withdrawal', document([claim, dependent, ce], [report, event('withdraw', claim, 'wclaim'), event('revise', claim, 'rclaim', replacement=claim2)])
    # The evidence may depend on its report's target without creating a graph edge
    # in the opposite direction merely because a report cites it.
    cyclic_report_evidence = node('Counter', 'evidence', [claim])
    yield 'report_is_not_dependency_edge', document([claim, cyclic_report_evidence], [event('record_refutation_report', claim, 'report', evidence=pin(cyclic_report_evidence))])
    for status in ('open', 'draft', 'claimed_established', 'claimed_refuted'):
        yield 'authored_status_' + status, document([node('Claim', status=status)])
    yield 'opaque_unexecuted_text', document([node('Payload', text="__import__('os').system('touch /tmp/should_never_exist_claim_review'); https://example.invalid/private; /etc/passwd")])
    # Dependency array order binds identity but does not change applicability.
    left, right = node('Left'), node('Right')
    yield 'ordered_dependencies_1', document([left, right, node('Join', dependencies=[left, right])], [event('withdraw', right, 'wr')])
    yield 'ordered_dependencies_2', document([left, right, node('Join', dependencies=[right, left])], [event('withdraw', right, 'wr')])
    yield 'unicode_is_not_normalized', document([node('Unicode', text='é and e\u0301 remain distinct')])
    edge_records = [node('Base' + str(i)) for i in range(16)]
    edge_records += [node('Join' + str(i), dependencies=edge_records[:16]) for i in range(16)]
    yield 'exact_256_edges', document(edge_records)
    yield 'exact_64_records', document([node('N' + str(i)) for i in range(64)])
    changing = node('Changing')
    events = []
    original = changing
    for i in range(64):
        newer = node('Changing', revision=changing['revision'] + 1)
        events.append(event('revise', changing, 'R' + str(i), replacement=newer))
        changing = newer
    yield 'exact_64_revision_events', document([original], events)


def random_cases(count=240):
    rng = random.Random(202610241)
    for case in range(count):
        records = []
        for i in range(12):
            kind = ('evidence', 'claim', 'obligation')[i % 3]
            dependencies = [r for r in records if rng.randrange(5) == 0]
            records.append(node('N' + str(i), kind, dependencies, status=rng.choice(['open', 'claimed_established', 'claimed_refuted'])))
        current = {r['id']: r for r in records}
        events = []
        transitions = set()
        for step in range(32):
            i = rng.randrange(12)
            old = current['N' + str(i)]
            op = rng.randrange(4)
            if op < 2:
                dependencies = [current['N' + str(j)] for j in range(i) if rng.randrange(4) == 0]
                rng.shuffle(dependencies)
                newer = node(old['id'], old['kind'], dependencies, old['revision'] + 1, text='Revision ' + str(step))
                events.append(event('revise', old, 'E' + str(step), replacement=newer))
                current[old['id']] = newer
            else:
                kind = 'record_refutation_report' if op == 3 and old['kind'] == 'claim' else 'withdraw'
                key = old['id'], old['revision'], kind
                if key in transitions:
                    continue
                transitions.add(key)
                extra = {'evidence': pin(current['N0'])} if kind == 'record_refutation_report' else {}
                events.append(event(kind, old, 'E' + str(step), **extra))
        rng.shuffle(records)
        yield 'random_history_' + str(case), document(records, events)


def exhaustive_cases():
    # All 543 labeled directed acyclic graphs on four nodes, not just the 64
    # subgraphs of one preselected topological order. Floyd closure detects cycles.
    pairs = [(i, j) for i in range(4) for j in range(4) if i != j]
    graph_count = 0
    for mask in range(1 << len(pairs)):
        edges = {pair for bit, pair in enumerate(pairs) if mask & (1 << bit)}
        reach = [[(i, j) in edges for j in range(4)] for i in range(4)]
        for k, i, j in product(range(4), repeat=3):
            reach[i][j] = reach[i][j] or (reach[i][k] and reach[k][j])
        if any(reach[i][i] for i in range(4)):
            continue
        graph_count += 1
        cache = {}
        def build(i):
            if i not in cache:
                cache[i] = node('N' + str(i), ('claim', 'obligation', 'evidence', 'claim')[i], [build(j) for j in range(4) if (i, j) in edges])
            return cache[i]
        records = [build(i) for i in range(4)]
        for withdrawn in range(16):
            events = [event('withdraw', records[i], 'W' + str(i)) for i in range(4) if withdrawn & (1 << i)]
            yield 'exhaustive_%s_%s' % (mask, withdrawn), document(records, events)
        for changed in range(4):
            old = records[changed]
            newer = deepcopy(old)
            newer['revision'] += 1
            newer = seal(newer)
            events = [event('revise', old, 'Revise', replacement=newer), event('withdraw', newer, 'WithdrawReplacement')]
            yield 'exhaustive_revision_%s_%s' % (mask, changed), document(records, events)
    check(graph_count == 543, 'Labeled four-node DAG enumeration was not 543')


def invalid_cases():
    a = node('A')
    b = node('B', 'obligation', [a])
    ce = node('Counter', 'evidence')
    a2 = node('A', revision=2)
    yield 'wrong_schema', {**document([a]), 'schema': 'other'}, 'schema'
    yield 'empty_records', document([]), 'budget_exceeded'
    yield 'too_many_records', document([node('N' + str(i)) for i in range(65)]), 'budget_exceeded'
    yield 'too_many_events', document([a], [event('withdraw', a, 'W' + str(i)) for i in range(65)]), 'budget_exceeded'
    yield 'duplicate_record', document([a, a]), 'duplicate_id'
    yield 'duplicate_event', document([a], [event('withdraw', a, 'W'), event('withdraw', a, 'W')]), 'duplicate_id'
    yield 'repeat_withdraw', document([a], [event('withdraw', a, 'W1'), event('withdraw', a, 'W2')]), 'duplicate_transition'
    yield 'repeat_report', document([a, ce], [event('record_refutation_report', a, 'R1', evidence=pin(ce)), event('record_refutation_report', a, 'R2', evidence=pin(ce))]), 'duplicate_transition'
    yield 'missing_dependency', document([b]), 'missing_reference'
    bad = deepcopy(b); bad['dependencies'].append(pin(a)); bad = seal(bad)
    yield 'duplicate_dependency', document([a, bad]), 'duplicate_dependency'
    bad = deepcopy(b); bad['dependencies'][0]['revision_sha256'] = '0' * 64; bad = seal(bad)
    yield 'wrong_dependency_digest', document([a, bad]), 'pin_mismatch'
    bad = deepcopy(a); bad['content']['statement'] += ' tampered'
    yield 'wrong_content_hash', document([bad]), 'content_hash_mismatch'
    bad['content_sha256'] = sha(bad['content'])
    yield 'wrong_revision_hash', document([bad]), 'revision_hash_mismatch'
    bad = deepcopy(a); bad['revision'] = True; bad = seal(bad)
    yield 'boolean_revision', document([bad]), 'malformed_type'
    yield 'old_target_after_revision', document([a], [event('revise', a, 'R', replacement=a2), event('withdraw', a, 'W')]), 'pin_mismatch'
    yield 'revision_gap', document([a], [event('revise', a, 'R', replacement=node('A', revision=3))]), 'invalid_revision'
    yield 'revision_kind_change', document([a], [event('revise', a, 'R', replacement=node('A', 'obligation', revision=2))]), 'invalid_revision'
    yield 'revision_id_change', document([a], [event('revise', a, 'R', replacement=node('B', revision=2))]), 'invalid_revision'
    b2 = node('B', 'obligation', [a], revision=2)
    yield 'replacement_stale_pin', document([a, b], [event('revise', a, 'RA', replacement=a2), event('revise', b, 'RB', replacement=b2)]), 'pin_mismatch'
    cyc = node('A', dependencies=[b], revision=2)
    yield 'cross_revision_stable_id_cycle', document([a, b], [event('revise', a, 'R', replacement=cyc)]), 'cycle'
    selfdep = deepcopy(a); selfdep['revision'] = 2; selfdep['dependencies'] = [pin(a)]; selfdep = seal(selfdep)
    yield 'self_historical_revision_cycle', document([a], [event('revise', a, 'R', replacement=selfdep)]), 'cycle'
    wrong = deepcopy(ce); wrong['content']['evidence_type'] = 'formal_proof_report'; wrong = seal(wrong)
    yield 'not_counterexample_evidence', document([a, wrong], [event('record_refutation_report', a, 'R', evidence=pin(wrong))]), 'invalid_refutation_evidence'
    yield 'obligation_not_refutation_target', document([a, b, ce], [event('record_refutation_report', b, 'R', evidence=pin(ce))]), 'invalid_refutation_target'
    yield 'claim_not_refutation_evidence', document([a], [event('record_refutation_report', a, 'R', evidence=pin(a))]), 'invalid_refutation_evidence'
    yield 'future_evidence_pin', document([a, ce], [event('record_refutation_report', a, 'R', evidence=pin(node('Counter', 'evidence', revision=2)))]), 'pin_mismatch'
    for key in ['execute', 'accept_proof', 'reactivate', 'delete', 'add_record']:
        yield 'unsupported_event_' + key, document([a], [event(key, a, 'E')]), 'malformed_type'
    for badid in ['', 'bad space', 'É', 'a\n', 'a' * 65]:
        bad = deepcopy(a); bad['id'] = badid; bad = seal(bad)
        yield 'bad_id_' + repr(badid), document([bad]), 'malformed_type'
    for revision in [0, -1, 1000001, '1', 1.0, None, False]:
        bad = deepcopy(a); bad['revision'] = revision; bad = seal(bad)
        yield 'bad_revision_' + repr(revision), document([bad]), 'malformed_type'
    for field in ['id', 'kind', 'content', 'dependencies', 'content_sha256', 'revision_sha256']:
        bad = deepcopy(a); bad.pop(field)
        yield 'missing_record_field_' + field, document([bad]), 'fields'
    bad = deepcopy(a); bad['extra'] = 1
    yield 'unknown_record_field', document([bad]), 'fields'
    bad = deepcopy(a); bad['content']['statement'] = '  \n\t'; bad = seal(bad)
    yield 'blank_text', document([bad]), 'malformed_type'
    bad = deepcopy(a); bad['content']['statement'] = 'a' * 2049; bad = seal(bad)
    yield 'long_authored_text', document([bad]), 'malformed_type'
    bad = deepcopy(a); bad['content']['assumptions'] = ['x'] * 33; bad = seal(bad)
    yield 'too_many_assumptions', document([bad]), 'malformed_type'
    chain = []
    for i in range(64):
        chain.append(node('C' + str(i), dependencies=chain[-1:]))
    yield 'real_output_path_budget', document(chain, [event('withdraw', r, 'W' + str(i)) for i, r in enumerate(chain)]), 'budget_exceeded'
    dense = [node('D' + str(i)) for i in range(16)]
    dense += [node('J' + str(i), dependencies=dense[:16]) for i in range(16)]
    dense.append(node('Over', dependencies=dense[:1]))
    yield '257_edges', document(dense), 'budget_exceeded'


def reject(core, doc, code, name):
    try:
        core.replay(doc)
    except core.LedgerError as exc:
        check(exc.code == code, '%s rejected with %s, expected %s' % (name, exc.code, code))
    else:
        raise ReviewFailure(name + ' accepted invalid document')


def compare(core, name, doc):
    before = deepcopy(doc)
    got = core.replay(doc)
    expected = model(doc)
    check(got == expected, name + ': full report differs from independent BFS model')
    check(doc == before, name + ': input mutated')
    return got


def raw_and_type_checks(core, root):
    counts = Counter()
    malformed = ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}', '{"x":1.0}', '{', b'\xff', '{"x":"\\ud800"}', '{"x":"\\udfff"}', '{"\\ud800":1}', '{"outer":{"\\udfff":1}}', '{"x":' + '1' * 5000 + '}']
    for raw in malformed:
        try:
            core.loads(raw)
        except core.LedgerError:
            counts['raw_rejections'] += 1
        else:
            raise ReviewFailure('loads accepted malformed input ' + repr(raw)[:80])
    for value in [{'\ud800': 1}, {'outer': {'\udfff': 1}}, {'x': '\ud800'}, 1.0, (1, 2), {1: 'value'}, {('x',): 1}, 2**33, 'x' * 8193, [None] * 4097, {str(i): i for i in range(33)}]:
        try:
            core.replay(value)
        except core.LedgerError:
            counts['structured_type_rejections'] += 1
        else:
            raise ReviewFailure('replay accepted invalid raw type')
    class EvilDict(dict): pass
    class EvilList(list): pass
    class EvilStr(str): pass
    class EvilInt(int): pass
    for value in [EvilDict(), EvilList(), EvilStr('x'), EvilInt(1), {'x': EvilStr('y')}]:
        try: core.replay(value)
        except core.LedgerError: counts['subclass_rejections'] += 1
        else: raise ReviewFailure('Accepted Python subclass')
    cycle = []; cycle.append(cycle)
    try: core.replay(cycle)
    except core.LedgerError as exc: check(exc.code == 'budget_exceeded', 'Cycle raw budget wrong'); counts['cyclic_raw_rejections'] += 1
    else: raise ReviewFailure('Accepted cyclic raw object')
    core.loads(' ' * (262144 - 2) + '{}')
    try: core.loads(' ' * (262144 - 1) + '{}')
    except core.LedgerError as exc: check(exc.code == 'budget_exceeded', 'Raw byte budget code wrong'); counts['byte_boundaries'] += 2
    else: raise ReviewFailure('Accepted over-budget raw bytes')
    nested = 0
    for i in range(17): nested = [nested]
    try: core.loads(canonical(nested))
    except core.LedgerError as exc: check(exc.code == 'budget_exceeded', 'Depth budget wrong'); counts['depth_rejections'] += 1
    else: raise ReviewFailure('Accepted depth 17')
    tree = ast.parse((root / 'claim_revision/core.py').read_text())
    allowed = {'__future__', 'hashlib', 'json', 're', 'collections', 'typing'}
    imports = set()
    for item in ast.walk(tree):
        if isinstance(item, ast.Import): imports.update(x.name for x in item.names)
        elif isinstance(item, ast.ImportFrom): imports.add(item.module)
        elif isinstance(item, ast.Call) and isinstance(item.func, ast.Name):
            check(item.func.id not in {'eval', 'exec', 'compile', 'open', '__import__', 'input'}, 'Core uses arbitrary I/O/code evaluation')
    check(imports <= allowed, 'Core imports unexpected I/O module: ' + repr(imports - allowed))
    with patch('builtins.open', side_effect=ReviewFailure('Core attempted file I/O')), patch('os.system', side_effect=ReviewFailure('Core attempted command execution')):
        compare(core, *next((x for x in valid_cases() if x[0] == 'opaque_unexecuted_text')))
    counts['pure_core_static_and_dynamic_controls'] += 1
    return counts


def cli_checks(root):
    counts = Counter()
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME')}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    doc = dict(valid_cases())['historical_report_and_withdrawal']
    mode = ['-O'] if sys.flags.optimize else []
    for seed in ['1', '8843']:
        env['PYTHONHASHSEED'] = seed
        p = subprocess.run([sys.executable, '-B', *mode, '-m', 'claim_revision'], input=canonical(doc), cwd=root, env=env, capture_output=True, timeout=20)
        check(p.returncode == 0 and json.loads(p.stdout) == model(doc), 'CLI deterministic full replay failed')
        counts['cli_full_replays'] += 1
    for raw in [b'{"\\ud800":1}', b'{"outer":{"\\udfff":1}}', b'{"x":1,"x":2}', b'{"x":NaN}', b'{' , b' ' * 262145]:
        p = subprocess.run([sys.executable, '-B', *mode, '-m', 'claim_revision'], input=raw, cwd=root, env=env, capture_output=True, timeout=20)
        check(p.returncode == 2 and json.loads(p.stdout)['status'] == 'rejected' and p.stderr == b'', 'CLI failed structured rejection: ' + repr(raw[:40]))
        counts['cli_structured_rejections'] += 1
    return counts


def source_mutations(core, root):
    source = (root / 'claim_revision/core.py').read_text()
    valid = dict(valid_cases())
    invalid = {name: (doc, code) for name, doc, code in invalid_cases()}
    mutants = [
        ('ignore_content_hash', 'if digest(value["content"]) != value["content_sha256"]:', 'if False:', 'wrong_content_hash'),
        ('ignore_revision_hash', 'if digest(body) != value["revision_sha256"]:', 'if False:', 'wrong_revision_hash'),
        ('name_only_pin_match', 'if target != pin(record):', 'if False:', 'wrong_dependency_digest'),
        ('ignore_stable_id_cycles', 'if len(order) != len(current):', 'if False:', 'cross_revision_stable_id_cycle'),
        ('allow_duplicate_withdrawals', 'if any(old["kind"] == kind for old in life.get(key, [])):', 'if False:', 'repeat_withdraw'),
        ('leak_historical_lifecycle', 'for event in life.get((rid, record["revision"]), []):', 'for event in [event for (name, revision), events in life.items() if name == rid for event in events]:', 'historical_report_and_withdrawal'),
        ('drop_lifecycle_causes', 'for event in life.get((rid, record["revision"]), []):', 'for event in []:', 'multiple_independent_causes'),
        ('drop_transitive_causes', 'for r in reasons_by_id[dep["id"]]:', 'for r in []:', 'diamond_lex_tie'),
        ('inherit_replacement_causes_across_stale_edge', '            else:\n                for r in reasons_by_id[dep["id"]]:', '            if True:\n                for r in reasons_by_id[dep["id"]]:', 'stale_does_not_inherit_replacement'),
        ('silently_rebind_pins', 'if dep != actual:', 'if False:', 'withdraw_then_revise'),
        ('wrong_latest_revision_event', 'changed_by[target["id"]] = event["id"]', 'changed_by.setdefault(target["id"], event["id"])', 'latest_revision_event'),
        ('wrong_shortest_and_lex_order', '(len(candidate["path"]), canonical_bytes(candidate["path"])) < (len(old["path"]), canonical_bytes(old["path"]))', '(len(candidate["path"]), canonical_bytes(candidate["path"])) > (len(old["path"]), canonical_bytes(old["path"]))', 'shortest_beats_lex'),
        ('wrong_lexicographic_tie', 'for dep in sorted(record["dependencies"], key=lambda value: value["id"]):', 'for dep in sorted(record["dependencies"], key=lambda value: value["id"], reverse=True):', 'diamond_lex_tie'),
        ('withdrawal_is_refutation', 'code = "revision_withdrawn" if event["kind"] == "withdraw" else "refutation_reported_unchecked"', 'code = "refutation_reported_unchecked"', 'diamond_lex_tie'),
        ('authored_status_becomes_acceptance', '"proof_accepted": False, "reasons": ordered', '"proof_accepted": True, "reasons": ordered', 'authored_status_claimed_established'),
        ('boolean_revision', 'if type(value) is not int or not 1 <= value <= 1000000:', 'if not isinstance(value, int) or not 1 <= value <= 1000000:', 'boolean_revision'),
        ('ignore_record_budget', 'not 1 <= len(records) <= MAX_RECORDS:', 'not 1 <= len(records) <= 1000:', 'too_many_records'),
    ]
    rows = []
    for name, before, after, test in mutants:
        check(source.count(before) == 1, 'Mutant anchor not unique: ' + name)
        mutated = source.replace(before, after)
        if name == 'wrong_lexicographic_tie':
            anchor = 'if old is None or (len(candidate["path"]), canonical_bytes(candidate["path"])) < (len(old["path"]), canonical_bytes(old["path"])):'
            check(mutated.count(anchor) == 1, 'Tie mutation anchor not unique')
            mutated = mutated.replace(anchor, 'if old is None or len(candidate["path"]) < len(old["path"]):')
        module = types.ModuleType('review_mutant_' + name)
        exec(compile(mutated, '<review mutant ' + name + '>', 'exec'), module.__dict__)
        try:
            if test in valid:
                compare(module, test, valid[test])
            else:
                doc, code = invalid[test]
                reject(module, doc, code, test)
        except ReviewFailure as exc:
            rows.append({'mutant': name, 'test': test, 'killed_by_explicit_comparison': True, 'finding': str(exc)})
        except Exception as exc:
            raise ReviewFailure('Mutant crashed instead of semantic detection: ' + name + ': ' + type(exc).__name__) from exc
        else:
            raise ReviewFailure('Surviving mutant: ' + name)
    return rows


def verify_manifest(root):
    path = root / 'SOURCE-MANIFEST.json'
    manifest = json.loads(path.read_bytes())
    seen = set()
    for row in manifest['files']:
        name = row['path']
        check(name not in seen and not Path(name).is_absolute() and '..' not in Path(name).parts, 'Unsafe or duplicate manifest path')
        seen.add(name)
        target = root / name
        check(target.is_file() and not target.is_symlink() and target.resolve().is_relative_to(root.resolve()), 'Non-file manifest member')
        raw = target.read_bytes()
        check(len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'], 'Manifest pin mismatch: ' + name)
    return {'manifest_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'core_sha256': hashlib.sha256((root / 'claim_revision/core.py').read_bytes()).hexdigest(), 'manifest_files': len(seen)}


def run(root):
    pins = verify_manifest(root)
    core = load_core(root)
    counts = Counter()
    for name, doc in valid_cases():
        compare(core, name, doc); counts['targeted_valid_cases'] += 1
        reversed_doc = {**doc, 'records': list(reversed(doc['records']))}
        check(core.replay(doc) == core.replay(reversed_doc), 'Record order changed report: ' + name)
        counts['record_order_metamorphic_checks'] += 1
    for name, doc in random_cases():
        compare(core, name, doc); counts['seeded_mixed_history_cases'] += 1
    for name, doc in exhaustive_cases():
        compare(core, name, doc)
        counts['all_labeled_four_node_revision_states' if name.startswith('exhaustive_revision') else 'all_labeled_four_node_withdrawal_states'] += 1
    for name, doc, code in invalid_cases():
        reject(core, doc, code, name); counts['adversarial_document_rejections'] += 1
    counts.update(raw_and_type_checks(core, root))
    counts.update(cli_checks(root))
    mutations = source_mutations(core, root)
    return {'status': 'pass', 'python_optimized': bool(sys.flags.optimize), 'source_pins': pins, 'counts': dict(counts), 'mutations': mutations,
            'scope': 'Synthetic bounded dependency applicability only. No proof acceptance or theorem validation. Independent oracle has no candidate imports.'}

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python -B review.py CANDIDATE_SOURCE_ROOT')
    print(json.dumps(run(Path(sys.argv[1]).resolve()), sort_keys=True, indent=2))
