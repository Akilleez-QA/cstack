SQLite/FTS5 stores host-sanitized facts with provenance and trust labels; it grants no authority.
Set `CSTACK_MEMORY_DB` to a private path outside the repository ending in `*.memory.db`, or pass it explicitly; supply an integer epoch host clock.
Facts remain proposals until a named human confirms them through the host review channel; rejection retains them and both reviews are terminal.
`ledger_ref` links a review to the existing ledger entry in the DECISION-004 witnessed format; memory creates no second chain.
An indexing adapter calls `propose_reference` per catalog chunk with source/path/sha256 and either its embedding or a `ref_vec_id` opaque pointer into an external vector store; keyword search is this store's FTS; entries are proposals reviewed like any fact.
Archive ingest reads a host-supplied local export directory only (push-only transfer); the shared wall screens whole threads and records counts only.

Run `python3 -B -m adapters.memory --db /private/knowledge.memory.db <command>`
(or set `CSTACK_MEMORY_DB`). Commands: `ingest ROOT [--label L]`,
`search QUERY [--status S] [--limit N]`, `list [--status S] [--limit N]`,
`show FACT_ID`, `stats`, `confirm FACT_ID --by NAME [--note T] [--ledger-ref HEX]`,
and `reject FACT_ID --by NAME --note T [--ledger-ref HEX]`. Output is JSON;
errors go to stderr with exit 2. Ingest never pulls or accesses a network.

Hosts may pass an existing `LedgerPort` as `MemoryStore(..., ledger=ledger)`.
Reviews validate first, reserve capacity, then append a `decision` containing only
action, fact ID, status and reviewer. The returned hash becomes `ledger_ref`;
an explicit reference cannot be combined with a ledger. Append precedes the guarded
database update: a failed update leaves a ledger intent without a state change.
Memory creates no ledger or chain; the supplied ledger owns durability and witnessing.
