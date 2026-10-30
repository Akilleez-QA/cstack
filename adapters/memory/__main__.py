"""Local JSON command line for private knowledge proposals."""
import argparse
import json
import sys
import time

from adapters.memory import MemoryStore
from adapters.memory.ingest import ingest_archive
from poodo_core.models import ContractError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('ingest', 'search', 'list', 'show', 'stats', 'confirm', 'reject'):
        command = commands.add_parser(name)
        command.add_argument('--db', default=argparse.SUPPRESS)
        if name == 'ingest':
            command.add_argument('root')
            command.add_argument('--label', default='archive')
        if name == 'search':
            command.add_argument('query')
        if name in ('search', 'list'):
            command.add_argument('--status', choices=('proposed', 'confirmed', 'rejected'),
                                 default='proposed' if name == 'list' else None)
            command.add_argument('--limit', type=int, default=100 if name == 'list' else 20)
        if name in ('show', 'confirm', 'reject'):
            command.add_argument('fact_id')
        if name in ('confirm', 'reject'):
            command.add_argument('--by', required=True)
            command.add_argument('--note', required=name == 'reject')
            command.add_argument('--ledger-ref')
    args = parser.parse_args(argv)
    store = None
    try:
        store = MemoryStore(args.db, clock=lambda: int(time.time()))
        if args.command == 'ingest':
            result = ingest_archive(store, args.root, label=args.label)
        elif args.command == 'search':
            result = store.search(args.query, status=args.status, limit=args.limit)
        elif args.command == 'list':
            result = store.list(status=args.status, limit=args.limit)
        elif args.command == 'show':
            result = store.get(args.fact_id)
        elif args.command == 'stats':
            result = store.stats()
        else:
            result = getattr(store, args.command)(args.fact_id, by=args.by,
                                                 note=args.note, ledger_ref=args.ledger_ref)
        print(json.dumps(result, sort_keys=True, ensure_ascii=False))
        return 0
    except (ContractError, OSError, ValueError) as error:
        message = str(error) if isinstance(error, ContractError) else 'Memory command failed'
        print(json.dumps({'error': message}, sort_keys=True, ensure_ascii=False), file=sys.stderr)
        return 2
    finally:
        if store is not None:
            store.close()


if __name__ == '__main__':
    sys.exit(main())
