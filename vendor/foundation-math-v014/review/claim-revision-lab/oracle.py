"""Independent BFS model of VALID ledger histories, not a validator or prover.

No candidate implementation, helper, test, fixture or private function is imported.
Canonical encoding follows the contract; propagation follows per-start-node BFS,
not the candidate's dependency-first dynamic program.
"""
from collections import deque
from copy import deepcopy
import hashlib
import json

VERSION = 'foundation-math-claim-revision/1'
SCOPE = 'All-required explicit revision dependency applicability only; no truth, proof acceptance, hypothesis checking, or formal verification.'


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def pin(record):
    return {k: record[k] for k in ('id', 'revision', 'revision_sha256')}


def seal(body):
    record = deepcopy(body)
    record.pop('revision_sha256', None)
    record['content_sha256'] = sha(record['content'])
    record['revision_sha256'] = sha(record)
    return record


def node(name, kind='claim', dependencies=(), revision=1, text=None, status='open'):
    text = text if text is not None else 'Synthetic requirement ' + name
    content = {'authored_status': status}
    if kind == 'claim':
        content.update(statement=text, scope='conditional', assumptions=['Synthetic only'], non_claims=['No theorem acceptance'])
    elif kind == 'obligation':
        content['requirement'] = text
    elif kind == 'evidence':
        content.update(description=text, evidence_type='counterexample_report', artifact_sha256='1' * 64)
    else:
        raise ValueError(kind)
    return seal({'id': name, 'revision': revision, 'kind': kind, 'content': content, 'dependencies': [pin(r) for r in dependencies]})


def event(kind, target, name, **extra):
    return {'id': name, 'kind': kind, 'target': pin(target), 'reason': 'Synthetic lifecycle reason ' + name, **extra}


def document(records, events=()):
    return {'schema': VERSION, 'records': deepcopy(records), 'events': deepcopy(list(events))}


def model(doc):
    doc = deepcopy(doc)
    current = {r['id']: r for r in doc['records']}
    versions = {(r['id'], r['revision']): r for r in doc['records']}
    lifecycle = {}
    revised_by = {}
    for e in doc['events']:
        name = e['target']['id']
        if e['kind'] == 'revise':
            current[name] = e['replacement']
            versions[name, current[name]['revision']] = current[name]
            revised_by[name] = e['id']
        else:
            lifecycle.setdefault((name, e['target']['revision']), []).append(e)

    # Root causes and usable graph edges are separate objects. A stale edge is a
    # terminal cause, not a traversal to the replacement record.
    roots = {name: [] for name in current}
    usable = {name: [] for name in current}
    for name, r in current.items():
        for e in lifecycle.get((name, r['revision']), []):
            cause = {'code': 'revision_withdrawn' if e['kind'] == 'withdraw' else 'refutation_reported_unchecked',
                     'origin': pin(r), 'event_id': e['id'], 'reason': e['reason']}
            if e['kind'] == 'record_refutation_report':
                cause['reported_evidence'] = e['evidence']
            roots[name].append((cause, []))
        for d in r['dependencies']:
            if d == pin(current[d['id']]):
                usable[name].append(d['id'])
            else:
                cause = {'code': 'dependency_revision_not_current', 'origin': pin(r),
                         'event_id': revised_by[d['id']], 'expected': d, 'current': pin(current[d['id']])}
                roots[name].append((cause, [d]))

    reports = []
    for start in sorted(current):
        # Relax paths by length then canonical bytes. BFS is independent of record
        # order; equal length lexicographically better paths may revisit a node.
        best = {start: [pin(current[start])]}
        todo = deque([start])
        while todo:
            name = todo.popleft()
            for dependency in usable[name]:
                candidate = best[name] + [pin(current[dependency])]
                previous = best.get(dependency)
                if previous is None or (len(candidate), canonical(candidate)) < (len(previous), canonical(previous)):
                    best[dependency] = candidate
                    todo.append(dependency)
        causes = {}
        for reached, path in best.items():
            for cause, suffix in roots[reached]:
                key = sha(cause)
                causes[key] = {'cause_id': key, **cause, 'path': path + suffix}
        r = current[start]
        reports.append({'pin': pin(r), 'kind': r['kind'], 'applicability': 'blocked' if causes else 'no_recorded_dependency_blockers',
                        'authored_status': r['content']['authored_status'], 'truth_assessment': 'not_assessed', 'proof_accepted': False,
                        'reasons': [causes[key] for key in sorted(causes)]})
    normalized = {**doc, 'records': sorted(doc['records'], key=lambda r: r['id'])}
    return {'schema': VERSION + '/report', 'input_sha256': sha(normalized),
            'integrity': {'record_digests_match': True, 'artifact_bytes_checked': False, 'authorship_verified': False},
            'scope': SCOPE, 'truth_assessment': 'not_assessed', 'proof_accepted': False, 'records': reports,
            'affected_claims': [r['pin']['id'] for r in reports if r['kind'] == 'claim' and r['applicability'] == 'blocked'],
            'affected_obligations': [r['pin']['id'] for r in reports if r['kind'] == 'obligation' and r['applicability'] == 'blocked'],
            'history': [{'pin': pin(r), 'kind': r['kind'], 'current': current[name]['revision'] == revision,
                         'lifecycle_events': lifecycle.get((name, revision), [])} for (name, revision), r in sorted(versions.items())],
            'events_replayed': len(doc['events'])}
