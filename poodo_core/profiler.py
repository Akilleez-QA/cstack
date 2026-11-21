import hashlib

from .models import ContractError, Document, GoalContract, canonical, identifier, prose


COUNTERS = ('duration', 'busy', 'slots', 'branches', 'divergent', 'cache_hits',
            'cache_lookups', 'burn', 'envelope', 'planned_burn')
FIELDS = set(COUNTERS) | {'mission', 'kernel', 'dependencies', 'waiting_on',
                         'held_locks', 'conflict', 'policy', 'outcomes'}


def validate_profile(data):
    if set(data) != FIELDS:
        raise ContractError('Aggregate profile fields required')
    for key in ('mission', 'kernel'):
        identifier(data[key])
    for key in COUNTERS:
        if type(data[key]) is not int or not 0 <= data[key] <= 2**53:
            raise ContractError('Bounded integer counters required')
    if (not data['duration'] or not data['slots'] or not data['envelope']
            or data['busy'] > data['duration'] * data['slots']
            or data['divergent'] > data['branches'] or data['cache_hits'] > data['cache_lookups']):
        raise ContractError('Invalid aggregate profile')
    for key in ('dependencies', 'waiting_on', 'held_locks', 'outcomes'):
        values = data[key]
        if type(values) is not list or len(values) > 256 or len(set(values)) != len(values):
            raise ContractError('Bounded unique references required')
        for value in values:
            identifier(value)
    if type(data['conflict']) is not bool:
        raise ContractError('Conflict flag required')
    if data['policy'] is not None:
        identifier(data['policy'])


def record_profile(ledger, **data):
    validate_profile(data)
    root = ledger.append_batch([('observation', {'schema': 'forge.profile/1', **data})])
    ledger.append('observation', {'schema': 'forge.profile-root/1', 'root': root})
    return root


def record_decision(ledger, *, mission, revision, action, context, reason):
    identifier(mission)
    prose(reason)
    if (type(revision) is not int or revision < 1 or type(context) is not dict or not context
            or action not in ('approve', 'reject', 'edit_spec', 'resolve_conflict')
            or len(canonical(context)) > 16384):
        raise ContractError('Versioned host decision with context required')
    return ledger.append('decision', {'schema': 'forge.craig-decision/1', 'mission': mission,
                         'revision': revision, 'action': action, 'context': context, 'reason': reason})


def export_decisions(ledger):
    return [{'schema': 'forge.honcho-decision/1', 'event_sha256': e['event_sha256'],
             **{k: e['data'][k] for k in ('mission', 'revision', 'action', 'context', 'reason')}}
            for e in ledger.read() if e['kind'] == 'decision'
            and e['data'].get('schema') == 'forge.craig-decision/1']


def ratio(a, b):
    return a / b if b else None


class ForgeBoard:
    def __init__(self, ledger):
        self.ledger = ledger

    def run_acceptance(self, goal, registry):
        refs = goal.to_dict()['acceptance_criteria']
        checks = [registry.get(ref['target']) for ref in refs]
        if any(not callable(check) for check in checks):
            raise ContractError('Executable acceptance registry required')
        results = []
        for ref, check in zip(refs, checks):
            try:
                passed = check() is True
            except Exception:
                passed = False
            results.append({**ref, 'result': 'passed' if passed else 'failed'})
        self.ledger.append('observation', {'schema': 'forge.acceptance/1',
                           'contract': goal.to_dict(), 'results': results})

    def read(self):
        events = self.ledger.read()
        by_hash = {e['event_sha256']: e for e in events}
        kernels, missions, roots, pending_roots = {}, {}, [], set()
        for event in events:
            data = event['data']
            schema = data.get('schema')
            if data.get('action') in ('start_goal', 'revise_goal') and 'snapshot' in data:
                contract = data['snapshot']['contract']
                current = missions.get(contract['goal_id'])
                if current is None or current['revision'] < contract['revision']:
                    missions[contract['goal_id']] = {
                        'revision': contract['revision'],
                        'diff': [{**ref, 'result': 'missing'} for ref in contract['acceptance_criteria']],
                        'confidence': 0, 'runtime_goal_acceptance': False}
            if schema == 'forge.profile-root/1':
                if data['root'] not in pending_roots:
                    raise ContractError('Profile batch root mismatch')
                pending_roots.remove(data['root'])
                roots.append(data['root'])
            elif schema == 'forge.profile/1':
                sample = {k: v for k, v in data.items() if k != 'schema'}
                validate_profile(sample)
                pending_roots.add(hashlib.sha256(b'\x00' + canonical(event).encode('ascii')).hexdigest())
                kernel = kernels.setdefault(data['kernel'], {**sample, 'passed': 0, 'verified': 0,
                                                            'capacity_time': 0, 'seen': set()})
                if kernel['mission'] != data['mission'] or kernel['envelope'] != data['envelope']:
                    raise ContractError('Kernel binding changed')
                if kernel['capacity_time']:
                    for key in COUNTERS:
                        if key not in ('envelope', 'slots'):
                            kernel[key] += data[key]
                kernel['capacity_time'] += data['duration'] * data['slots']
                for key in ('waiting_on', 'held_locks', 'conflict', 'policy', 'dependencies'):
                    kernel[key] = data[key]
                for ref in data['outcomes']:
                    source = by_hash.get(ref)
                    if source is None or source['kind'] != 'outcome':
                        raise ContractError('Missing F2 outcome')
                    verdict = source['data'].get('interpretation', {}).get('verdict')
                    if verdict not in ('passed', 'failed', 'unverified'):
                        raise ContractError('Missing F2 verdict')
                    if ref not in kernel['seen']:
                        kernel['seen'].add(ref)
                        kernel['verified'] += 1
                        kernel['passed'] += verdict == 'passed'
            elif schema == 'forge.acceptance/1':
                contract = GoalContract.from_dict(data['contract']).to_dict()
                expected = contract['acceptance_criteria']
                if (len(data['results']) != len(expected) or any(
                        set(result) != {'kind', 'target', 'result'}
                        or {k: result[k] for k in ('kind', 'target')} != ref
                        or result['result'] not in ('passed', 'failed')
                        for ref, result in zip(expected, data['results']))):
                    raise ContractError('Acceptance result binding mismatch')
                prior = missions.get(contract['goal_id'])
                if prior is None or contract['revision'] >= prior['revision']:
                    results = data['results']
                    missions[contract['goal_id']] = {
                        'revision': contract['revision'], 'diff': results,
                        'confidence': ratio(sum(x['result'] == 'passed' for x in results), len(results)),
                        'runtime_goal_acceptance': False}
        paths = {}

        def critical(key, visiting):
            if key in visiting or key not in kernels:
                raise ContractError('Unresolved or cyclic kernel dependency')
            if key not in paths:
                paths[key] = kernels[key]['duration'] + max(
                    (critical(dep, visiting | {key}) for dep in kernels[key]['dependencies']), default=0)
            return paths[key]

        def deadlocked(key, visiting):
            if key in visiting:
                return True
            item = kernels.get(key)
            return bool(item and item['held_locks'] and any(
                deadlocked(dep, visiting | {key}) for dep in item['waiting_on']))

        feed, projected = [], {}
        for key, kernel in sorted(kernels.items()):
            verify = ratio(kernel['passed'], kernel['verified'])
            divergence = ratio(kernel['divergent'], kernel['branches'])
            projected[key] = {k: kernel[k] for k in ('mission', 'burn', 'envelope', 'cache_hits')}
            projected[key].update(occupancy=ratio(kernel['busy'], kernel['capacity_time']),
                                  divergence_rate=divergence, verify_pass_rate=verify,
                                  cache_hit_rate=ratio(kernel['cache_hits'], kernel['cache_lookups']),
                                  burn_vs_envelope=ratio(kernel['burn'], kernel['envelope']),
                                  critical_path=critical(key, set()))
            faults = {'burn_over_plan': kernel['burn'] > kernel['planned_burn'],
                      'verify_collapse': verify is not None and verify < .5,
                      'divergence_explosion': divergence is not None and divergence > .5,
                      'scope_lock_deadlock': deadlocked(key, set()),
                      'goal_conflict_no_policy': kernel['conflict'] and kernel['policy'] is None}
            feed.extend({'mission': kernel['mission'], 'kernel': key, 'anomaly': name}
                        for name, active in faults.items() if active)
        return Document.capture({'schema': 'forge.board/1', 'kernels': projected,
                                 'missions': missions, 'exceptions': feed, 'batch_roots': roots}).read()
