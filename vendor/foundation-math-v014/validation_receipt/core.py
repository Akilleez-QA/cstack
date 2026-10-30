"""Bounded, pure, caller-authored receipt applicability; never execution or proof."""
import hashlib
import json
import re

SCHEMA = 'foundation-math-validation-receipt-plan/1'
MAX_INPUT_BYTES = 262144
MAX_OUTPUT_BYTES = 524288
MAX_TASKS = 32
MAX_RECEIPTS = 64
MAX_EDGES = 128
MAX_FILES = 512
ID = re.compile(r'[A-Za-z][A-Za-z0-9_.-]{0,63}\Z')
HASH = re.compile(r'[0-9a-f]{64}\Z')
ROLES = ('historical_component', 'archival_full_replay', 'current_runtime', 'new_adapter')
MANDATORY_FRESH = frozenset(ROLES[1:])


class PlanError(ValueError):
    def __init__(self, code, path, message):
        self.code, self.path, self.message = code, path, message
        super().__init__(f'{code} at {path}: {message}')


def fail(code, path, message):
    raise PlanError(code, path, message)


def raw(value):
    """Detach ordinary JSON, with explicit depth/node/type/size guards."""
    count = 0
    active = set()
    def visit(x, depth, path):
        nonlocal count
        count += 1
        if depth > 16 or count > 32768:
            fail('budget_exceeded', path, 'JSON depth or node budget')
        t = type(x)
        if x is None or t is bool:
            return x
        if t is int:
            if not -(2**31) <= x < 2**31:
                fail('budget_exceeded', path, '32-bit integer budget')
            return x
        if t is str:
            if len(x) > 2048 or any(0xD800 <= ord(c) <= 0xDFFF for c in x):
                fail('invalid_string', path, 'string budget or Unicode surrogate')
            return x
        if t not in (list, dict):
            fail('invalid_type', path, 'ordinary JSON values only; no floats/subclasses')
        if id(x) in active:
            fail('cyclic_python_value', path, 'cyclic Python input')
        if len(x) > (512 if t is list else 16):
            fail('budget_exceeded', path, 'container budget')
        active.add(id(x))
        if t is list:
            result = [visit(v, depth + 1, path + f'/{i}') for i, v in enumerate(x)]
        else:
            result = {}
            for k, v in x.items():
                if type(k) is not str or len(k) > 64 or any(0xD800 <= ord(c) <= 0xDFFF for c in k):
                    fail('invalid_key', path, 'ordinary bounded Unicode string key required')
                result[k] = visit(v, depth + 1, path + '/' + k)
        active.remove(id(x))
        return result
    return visit(value, 0, '$')


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def canonical_bytes(value):
    return encode(raw(value))


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def loads(value):
    if type(value) not in (str, bytes):
        fail('invalid_type', '$', 'JSON text or UTF-8 bytes required')
    try:
        data = value.encode('utf-8') if type(value) is str else value
        if len(data) > MAX_INPUT_BYTES:
            fail('budget_exceeded', '$', 'encoded input budget')
        text = data.decode('utf-8')
        def pairs(items):
            d = {}
            for k, v in items:
                if k in d:
                    fail('duplicate_key', '$', 'duplicate JSON object key')
                d[k] = v
            return d
        def non_integer(_):
            fail('invalid_type', '$', 'floats and nonfinite numbers forbidden')
        return raw(json.loads(text, object_pairs_hook=pairs, parse_float=non_integer, parse_constant=non_integer))
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, PlanError):
            raise
        fail('invalid_json', '$', 'invalid UTF-8 JSON or excessive parse nesting')


def obj(value, keys, path):
    if type(value) is not dict or set(value) != set(keys.split()):
        fail('shape', path, 'exact object keys required: ' + keys)


def string(value, path, maximum=1024):
    if type(value) is not str or not value.strip() or len(value) > maximum or '\x00' in value:
        fail('string', path, 'bounded nonblank string without NUL required')


def integer(value, path, low=0, high=2**31-1):
    if type(value) is not int or not low <= value <= high:
        fail('integer', path, 'ordinary bounded integer required')


def identifier(value, path):
    if type(value) is not str or not ID.fullmatch(value):
        fail('id', path, 'invalid identifier')


def hash_value(value, path, nullable=False):
    if nullable and value is None:
        return
    if type(value) is not str or not HASH.fullmatch(value):
        fail('hash', path, 'lowercase SHA256 digest required')


def choice(value, options, path):
    if type(value) is not str or value not in options:
        fail('enum', path, 'unsupported literal')


def sequence(value, path, maximum, minimum=0):
    if type(value) is not list or not minimum <= len(value) <= maximum:
        fail('budget_exceeded', path, 'bounded ordinary array required')


def pin(record):
    return {k: record[k] for k in ('id', 'revision', 'revision_sha256')}


def check_pin(value, path):
    obj(value, 'id revision revision_sha256', path)
    identifier(value['id'], path + '/id')
    integer(value['revision'], path + '/revision', 1, 1000000)
    hash_value(value['revision_sha256'], path + '/revision_sha256')


def seal(body):
    """Construction only. Semantic content is validated by plan(), not trusted here."""
    body = raw(body)
    obj(body, 'id revision content', '$')
    identifier(body['id'], '$/id')
    integer(body['revision'], '$/revision', 1, 1000000)
    return {**body, 'revision_sha256': digest(body)}


def envelope(record, path):
    obj(record, 'id revision content revision_sha256', path)
    check_pin(pin(record), path)
    if record['revision_sha256'] != digest({k: record[k] for k in ('id', 'revision', 'content')}):
        fail('integrity', path, 'record hash mismatch')


def relative_path(value, path, dot=False):
    string(value, path, 512)
    if dot and value == '.':
        return
    if value.startswith('/') or '\\' in value or any(x in ('', '.', '..') for x in value.split('/')):
        fail('path', path, 'normalized relative POSIX path required')
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        fail('path', path, 'control character in path')


def task_content(c, path):
    obj(c, 'role invocation inputs environment closure dependencies', path)
    choice(c['role'], ROLES, path + '/role')
    inv = c['invocation']
    obj(inv, 'argv cwd stdin_sha256', path + '/invocation')
    sequence(inv['argv'], path + '/invocation/argv', 32, 1)
    for arg in inv['argv']:
        # Empty positional arguments are meaningful and preserved.
        if type(arg) is not str or len(arg) > 1024 or '\x00' in arg:
            fail('argv', path, 'bounded literal argv string without NUL required')
    string(inv['argv'][0], path + '/invocation/argv/0')
    relative_path(inv['cwd'], path + '/invocation/cwd', True)
    hash_value(inv['stdin_sha256'], path + '/invocation/stdin_sha256', True)
    sequence(c['inputs'], path + '/inputs', 256)
    names = []
    for f in c['inputs']:
        obj(f, 'path bytes sha256', path + '/inputs')
        relative_path(f['path'], path + '/inputs/path')
        integer(f['bytes'], path + '/inputs/bytes')
        hash_value(f['sha256'], path + '/inputs/sha256', True)
        names.append(f['path'])
    if names != sorted(set(names)):
        fail('manifest_order', path + '/inputs', 'unique paths in lexical order required')
    env = c['environment']
    obj(env, 'runner_sha256 environment_sha256 description', path + '/environment')
    hash_value(env['runner_sha256'], path + '/environment/runner_sha256', True)
    hash_value(env['environment_sha256'], path + '/environment/environment_sha256', True)
    string(env['description'], path + '/environment/description')
    closure = c['closure']
    obj(closure, 'declaration files process_state external_state randomness clock', path + '/closure')
    choice(closure['declaration'], ('caller_declares_complete', 'unknown'), path + '/closure/declaration')
    choice(closure['files'], ('exact_selected_manifest', 'unknown'), path + '/closure/files')
    choice(closure['process_state'], ('pinned_environment_and_stdin', 'unknown'), path + '/closure/process_state')
    for k in ('external_state', 'randomness', 'clock'):
        choice(closure[k], ('none', 'unknown'), path + '/closure/' + k)
    sequence(c['dependencies'], path + '/dependencies', MAX_TASKS)
    ids = []
    for dep in c['dependencies']:
        check_pin(dep, path + '/dependencies'); ids.append(dep['id'])
    if ids != sorted(set(ids)):
        fail('dependency_order', path, 'unique dependency IDs in lexical order required')


def receipt_content(c, path):
    obj(c, 'task availability result dependency_receipts', path)
    check_pin(c['task'], path + '/task')
    choice(c['availability'], ('supplied', 'withdrawn'), path + '/availability')
    result = c['result']
    obj(result, 'outcome exit_code output_sha256', path + '/result')
    choice(result['outcome'], ('declared_pass', 'declared_fail', 'unknown'), path + '/result/outcome')
    if result['exit_code'] is not None:
        integer(result['exit_code'], path + '/result/exit_code', -255, 255)
    hash_value(result['output_sha256'], path + '/result/output_sha256', True)
    sequence(c['dependency_receipts'], path + '/dependency_receipts', MAX_TASKS)
    ids = []
    for dep in c['dependency_receipts']:
        obj(dep, 'task receipt', path + '/dependency_receipts')
        check_pin(dep['task'], path + '/dependency_receipts/task')
        check_pin(dep['receipt'], path + '/dependency_receipts/receipt')
        ids.append(dep['task']['id'])
    if ids != sorted(set(ids)):
        fail('dependency_order', path, 'unique dependency task IDs in lexical order required')


def topology(graph, path):
    """Stable-ID DAG, including stale pins. No cross-version cycle exceptions."""
    order, active, done = [], set(), set()
    def visit(node):
        if node in active:
            fail('dependency_cycle', path, 'stable-ID dependency cycle')
        if node in done:
            return
        active.add(node)
        for dep in sorted(graph[node]):
            if dep not in graph:
                fail('dangling_dependency', path, 'dependency target absent: ' + dep)
            visit(dep)
        active.remove(node); done.add(node); order.append(node)
    for node in sorted(graph):
        visit(node)
    return order


def plan(document):
    """Return classifications only. Does not read, execute, skip, approve or persist."""
    doc = raw(document)
    if len(encode(doc)) > MAX_INPUT_BYTES:
        fail('budget_exceeded', '$', 'encoded input budget')
    obj(doc, 'schema tasks receipts selections', '$')
    choice(doc['schema'], (SCHEMA,), '$/schema')
    registries = []
    for key, limit, validator in [('tasks', MAX_TASKS, task_content), ('receipts', MAX_RECEIPTS, receipt_content)]:
        sequence(doc[key], '$/' + key, limit, 1 if key == 'tasks' else 0)
        registry = {}
        for i, record in enumerate(doc[key]):
            path = '$/' + key + '/' + str(i)
            envelope(record, path); validator(record['content'], path + '/content')
            if record['id'] in registry:
                fail('duplicate_id', path, 'duplicate registry ID')
            registry[record['id']] = record
        registries.append(registry)
    tasks, receipts = registries
    if sum(len(t['content']['inputs']) for t in tasks.values()) > MAX_FILES:
        fail('budget_exceeded', '$/tasks', 'aggregate manifest file budget')
    if sum(len(t['content']['dependencies']) for t in tasks.values()) > MAX_EDGES or sum(len(r['content']['dependency_receipts']) for r in receipts.values()) > MAX_EDGES:
        fail('budget_exceeded', '$', 'aggregate edge budget')
    order = topology({k: [p['id'] for p in t['content']['dependencies']] for k, t in tasks.items()}, '$/tasks')
    topology({k: [p['receipt']['id'] for p in r['content']['dependency_receipts']] for k, r in receipts.items()}, '$/receipts')
    for r in receipts.values():
        c = r['content']
        if c['task']['id'] not in tasks or any(p['task']['id'] not in tasks for p in c['dependency_receipts']):
            fail('dangling_dependency', '$/receipts', 'receipt task target absent')
    sequence(doc['selections'], '$/selections', MAX_TASKS)
    selections = {}
    for selection in doc['selections']:
        obj(selection, 'task receipt', '$/selections')
        check_pin(selection['task'], '$/selections/task')
        check_pin(selection['receipt'], '$/selections/receipt')
        key = selection['task']['id']
        if key not in tasks:
            fail('dangling_selection', '$/selections', 'selection task target absent')
        if key in selections:
            fail('duplicate_selection', '$/selections', 'one explicit selection per task')
        selections[key] = selection
    reports = {}
    for key in order:
        task = tasks[key]; c = task['content']; reasons = []
        def reason(code, subject=key, expected=None, supplied=None):
            reasons.append({'code': code, 'subject': subject, 'expected': expected, 'supplied': supplied})
        if c['role'] in MANDATORY_FRESH:
            reason('mandatory_fresh_policy')
        if c['closure'] != {'declaration': 'caller_declares_complete', 'files': 'exact_selected_manifest', 'process_state': 'pinned_environment_and_stdin', 'external_state': 'none', 'randomness': 'none', 'clock': 'none'}:
            reason('closure_not_declared_complete')
        if c['invocation']['stdin_sha256'] is None or any(f['sha256'] is None for f in c['inputs']):
            reason('input_pin_unknown')
        if any(c['environment'][k] is None for k in ('runner_sha256', 'environment_sha256')):
            reason('environment_pin_unknown')
        fresh_deps = []
        ancestors = set()
        for dep in c['dependencies']:
            actual = pin(tasks[dep['id']])
            if dep != actual:
                reason('dependency_task_pin_not_current', dep['id'], dep, actual)
            if reports[dep['id']]['classification'] == 'MUST_RUN_FRESH':
                fresh_deps.append(dep['id']); ancestors.add(dep['id'])
                ancestors.update(reports[dep['id']]['fresh_ancestors'])
        if fresh_deps:
            reason('dependency_requires_fresh')
        selection = selections.get(key)
        prior = None
        if selection is None:
            reason('prior_receipt_not_selected')
        else:
            if selection['task'] != pin(task):
                reason('selection_task_pin_not_current', key, selection['task'], pin(task))
            prior = receipts.get(selection['receipt']['id'])
            if prior is None:
                reason('selected_receipt_not_supplied', selection['receipt']['id'], selection['receipt'])
            elif selection['receipt'] != pin(prior):
                reason('selected_receipt_pin_not_current', prior['id'], selection['receipt'], pin(prior))
            else:
                rc = prior['content']
                if rc['task'] != pin(task):
                    reason('receipt_task_pin_not_current', key, rc['task'], pin(task))
                if rc['availability'] != 'supplied':
                    reason('prior_receipt_withdrawn')
                result = rc['result']
                if result['outcome'] != 'declared_pass' or result['exit_code'] != 0:
                    reason('prior_result_not_declared_pass')
                if result['output_sha256'] is None:
                    reason('prior_output_pin_unknown')
                expected_deps = {d['id']: d for d in c['dependencies']}
                prior_deps = {d['task']['id']: d for d in rc['dependency_receipts']}
                if set(expected_deps) != set(prior_deps):
                    reason('receipt_dependency_set_mismatch')
                for dep_id in sorted(set(expected_deps) & set(prior_deps)):
                    edge = prior_deps[dep_id]
                    if edge['task'] != expected_deps[dep_id]:
                        reason('receipt_dependency_task_pin_mismatch', dep_id, edge['task'], expected_deps[dep_id])
                    actual_receipt = receipts[edge['receipt']['id']]
                    if edge['receipt'] != pin(actual_receipt):
                        reason('dependency_receipt_pin_not_current', dep_id, edge['receipt'], pin(actual_receipt))
                    if actual_receipt['content']['task'] != edge['task']:
                        reason('dependency_receipt_task_mismatch', dep_id, edge['task'], actual_receipt['content']['task'])
                    dep_selection = selections.get(dep_id)
                    if dep_selection is None or edge['receipt'] != dep_selection['receipt']:
                        reason('dependency_receipt_not_selected_exactly', dep_id, edge['receipt'], None if dep_selection is None else dep_selection['receipt'])
        reports[key] = {
            'task': pin(task),
            'classification': 'MUST_RUN_FRESH' if reasons else 'PRIOR_PINNED_EVIDENCE_MATCHES',
            'selected_receipt': None if selection is None else selection['receipt'],
            'supplied_receipt': None if prior is None else pin(prior),
            'reasons': reasons,
            'fresh_dependencies': sorted(fresh_deps),
            'fresh_ancestors': sorted(ancestors),
            'selected_manifest_sha256': digest(c['inputs']),
        }
    normalized = {**doc, 'tasks': sorted(doc['tasks'], key=lambda x: x['id']), 'receipts': sorted(doc['receipts'], key=lambda x: x['id']), 'selections': sorted(doc['selections'], key=lambda x: x['task']['id'])}
    result = {
        'schema': 'foundation-math-validation-receipt-report/1',
        'input_sha256': hashlib.sha256(encode(normalized)).hexdigest(),
        'tasks': [reports[k] for k in sorted(reports)],
        'execution_performed': False,
        'fresh_pass_claimed': False,
        'skip_authorized': False,
        'closure_verified': False,
        'artifact_bytes_verified': False,
        'authenticity_verified': False,
        'mathematical_truth_checked': False,
        'proof_acceptance_changed': False,
        'scope': 'Syntactic integrity and applicability within a caller-declared closed input boundary only.',
    }
    if len(encode(result)) > MAX_OUTPUT_BYTES:
        fail('budget_exceeded', '$', 'encoded output budget')
    return result
