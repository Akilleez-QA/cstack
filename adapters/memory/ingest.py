"""Stream thread archives into screened candidate facts and an atomic receipt."""
import gzip
import json
import re
import uuid
import zlib
from pathlib import Path

from adapters.memory.redact import has_secret, redact
from adapters.memory.confidentiality_wall import Wall
from adapters.memory.store import MemoryStore, _COUNTERS, _safe
from poodo_core.models import ContractError, identifier, prose

_CUES = tuple((kind, re.compile(r'\b(?:' + pattern + r')\b', re.I)) for kind, pattern in (
    ('decision', r"decided|decision|we will|we'll use|going with|chose|agreed|from now on|always|never|must|do not|don't|policy|rule|instead of|switch(?:ed)? to|prefer"),
    ('observation', r'is located|lives (?:in|at)|path is|default is|runs on|deployed|merged|released|root cause|the fix|fixed by|requires|depends on|configured|version'),
    ('learning', r'lesson|learned|gotcha|turns out|note that|remember')))

def _sentences(text):
    fence = None
    for line in text.splitlines():
        marker = re.match(r'(`{3,}|~{3,})', line.lstrip())
        if marker:
            if fence is None or marker[1][0] == fence:
                fence = marker[1][0] if fence is None else None
            continue
        if fence is None:
            line = re.sub(r'^\s*(?:[-*+]\s+|\d+[.)]\s+|#+\s*)', '', line)
            for sentence in re.split(r'(?<=[.!?])\s+', line):
                sentence = ' '.join(sentence.split()).strip('` ')
                if 30 <= len(sentence) <= 400:
                    kind = next((k for k, cue in _CUES if cue.search(sentence)), None)
                    if kind:
                        yield sentence, kind

def ingest_archive(store: MemoryStore, root: str | Path, *, label='archive', ledger_ref=None) -> dict:
    if not isinstance(root, (str, Path)):
        raise ContractError('Archive root must be a path')
    if ledger_ref is not None and (type(ledger_ref) is not str or
                                  re.fullmatch(r'[0-9a-f]{64}', ledger_ref) is None):
        raise ContractError('Invalid ledger reference')
    try:
        wall = Wall.from_env()
        identifier(label)
        _safe(label)
        if wall.path_blocked(label) or wall.text_blocked(label):
            raise ContractError('Unsafe archive label')
        directory = Path(root) / 'threads'
        if not directory.is_dir():
            raise ContractError('Archive threads directory required')
        with store._transaction():
            receipt = dict(run_id='run-' + uuid.uuid4().hex, archive_label=label,
                           started_at=store._now(), **dict.fromkeys(_COUNTERS, 0))
            for path in sorted(directory.glob('*.jsonl.gz')):
                account = path.name[:-9]
                receipt['files'] += 1
                reason = 'confidentiality_wall' if wall.path_blocked(account) else (
                    'secret_residue' if has_secret(account) else None)
                try:
                    identifier(account)
                except ContractError:
                    reason = reason or 'unparseable'
                if reason:
                    receipt[reason] += 1
                    continue
                with gzip.open(path, 'rb') as source:
                    for raw in source:
                        receipt['threads'] += 1
                        try:
                            thread = json.loads(raw.decode('utf-8'))
                            if not isinstance(thread, dict):
                                raise ValueError('Expected thread object')
                            if wall.record_blocked(thread):
                                receipt['confidentiality_wall'] += 1
                                continue
                            tid, msgs = prose(thread.get('thread_id'), 512), thread.get('msgs')
                            if '\0' in tid or not isinstance(msgs, list) or any(
                                    not isinstance(m, dict) or not isinstance(m.get('text'), str) for m in msgs):
                                raise ValueError('Invalid thread')
                            identifier(thread.get('account', account))
                        except (ContractError, UnicodeError, ValueError, RecursionError):
                            receipt['unparseable'] += 1
                            continue
                        if any(has_secret(v) for v in (tid, thread.get('account', account))):
                            receipt['secret_residue'] += 1
                            continue
                        parent = re.fullmatch(r'(.+):agent-[^:]+', tid)
                        receipt['subagent_threads'] += int(parent is not None)
                        receipt['messages'] += len(msgs)
                        seen = set()
                        for offset, msg in enumerate(msgs):
                            role = str(msg.get('role', '')).lower()
                            if role not in ('user', 'assistant'):
                                continue
                            for index, (sentence, kind) in enumerate(_sentences(msg['text'])):
                                if sentence.casefold() in seen or len(seen) == 25:
                                    continue
                                seen.add(sentence.casefold())
                                text, counts = redact(sentence)
                                for key, count in counts.items():
                                    receipt[key] += count
                                if text is None or '\0' in text:
                                    continue
                                ts = msg.get('ts')
                                ts = ts if isinstance(ts, str) and 0 < len(ts) <= 64 else None
                                if ts is not None and (has_secret(ts) or '\0' in ts):
                                    ts = None
                                _, added = store.propose(text, archive_label=account, thread_id=tid,
                                    line_offset=offset, chunk_index=index, role=role, kind=kind,
                                    trust='agent_written' if role == 'assistant' else 'unknown',
                                    source_ts=ts, parent_thread_id=parent[1] if parent else None)
                                receipt['facts_added' if added else 'duplicates'] += 1
                        receipt['empty'] += int(not seen)
            return store._insert_receipt(receipt | dict(finished_at=store._now(), ledger_ref=ledger_ref))
    except (OSError, EOFError, zlib.error, UnicodeError, ValueError):
        raise ContractError('Archive ingest failed') from None
