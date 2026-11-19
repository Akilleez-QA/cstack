#!/usr/bin/env python3
"""Golden digest vectors for the TypeScript intent contract, made by Python's v1 canonical form.

Python is the spec: poodo_core.models.canonical and digest decide the bytes. The TS port
(ts/packages/contracts/src/canonical.ts) must match every vector. The test on each side reads
the same file, so a change on either side that moves a byte fails CI.

  python3 tools/intent_vectors.py           # rewrite the vectors
  python3 tools/intent_vectors.py --check   # exit 1 if the file is stale
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from poodo_core.models import canonical, digest  # noqa: E402

OUT = ROOT / 'ts' / 'packages' / 'intent' / 'vectors' / 'digest.json'

CONTRACT = {
    'schema': 'cstack.intent/1',
    'intent_id': 'intent.example-clamp',
    'revision': 1,
    'supersedes': None,
    'owner_words': {'text': 'I need a clamp for integer arrays that never allocates.',
                    'channel': 'chat', 'received_at': '2026-11-19T09:00:00Z'},
    'restatement': {'objective': 'A kernel that clamps every element of an i32 array into [lo, hi] in place.',
                    'assumptions': ['lo <= hi is the caller’s job'],
                    'exclusions': ['floating-point arrays'],
                    'questions_asked': [{'q': 'In place, or a new array?', 'owner_answer': 'In place.'}]},
    'roles': {'chief': 'chief', 'spec_writer': 'scribe', 'builder': 'smith'},
    'acceptance': [
        {'id': 'clamps-example', 'says': 'Values below lo become lo and above hi become hi.', 'author': 'sage',
         'check': {'kind': 'example', 'call': 'clamp', 'inputs': {'xs': [-5, 0, 9], 'lo': 0, 'hi': 3},
                   'expect': [0, 0, 3], 'tolerance_ulps': 0}},
        {'id': 'stays-in-range', 'says': 'Every output is between lo and hi.', 'author': 'sage',
         'check': {'kind': 'property', 'call': 'clamp', 'domain': {'xs': 'i32[0..1024]', 'lo': 'i32', 'hi': 'i32'},
                   'predicate': 'out.every(v => lo <= v && v <= hi)', 'samples': 1000}},
        {'id': 'runs', 'says': 'The delivered package runs its own self-check.', 'author': 'sage',
         'check': {'kind': 'command', 'argv': ['node', 'clamp.mjs', '--self-check'], 'expect_exit': 0}},
    ],
    'delivery': {'kind': 'kernel', 'how_to_run': ['node', 'clamp.mjs'], 'where': 'artifacts/clamp'},
    'limits': {'budget_cents': 0, 'model_runs': 'stand-in', 'deadline': None},
}

CASES = {
    'contract': CONTRACT,
    'empty-object': {},
    'nested-order': {'b': {'z': 1, 'a': [3, 2, 1]}, 'a': None, 'A': True, '_': False},
    'non-ascii': {'text': 'café — 漢字 \U0001f600'},
    'astral-key-order': {'\U0001f600': 1, '￿': 2, '': 3, 'z': 4},
    'del-and-controls': {'s': '\x7f\x00\x01\x08\t\n\x0c\r\x1f"\\/'},
    'lone-surrogate': {'s': '\ud800x'},
    'safe-integer-edges': {'max': 2**53 - 1, 'min': -(2**53 - 1), 'zero': 0, 'neg': -42},
    'stored-separators': {'k': ', : {} []'},
}

# Python accepts these; the TS port refuses them because the intent contract is float-free.
TS_REFUSES = {'float': {'x': 1.5}, 'one-point-zero': {'x': 1.0}, 'big-int': {'x': 2**53 + 1}}


def build():
    vectors = [{'name': n, 'value': v, 'canonical': canonical(v), 'sha256': digest(v)} for n, v in CASES.items()]
    refused = [{'name': n, 'canonical': canonical(v)} for n, v in TS_REFUSES.items()]
    return json.dumps({'generated_by': 'tools/intent_vectors.py', 'vectors': vectors, 'ts_refuses': refused},
                      indent=1, ensure_ascii=True) + '\n'


def main(argv):
    text = build()
    if '--check' in argv:
        if not OUT.exists() or OUT.read_text() != text:
            print(f'stale: {OUT.relative_to(ROOT)} (run python3 tools/intent_vectors.py)')
            return 1
        return 0
    OUT.write_text(text)
    print(f'wrote {OUT.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
