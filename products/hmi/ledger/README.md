# Private witnessed ledger (prototype)

Design: `contracts/DECISION-004-private-witnessed-ledger.md`. Private and tailnet-only, with no public chain, tokens or wallets.

- Each node has one append-only, hash-chained log, and every entry is ed25519-signed by a writer bound to that node.
- Always-on witness nodes keep a verified replica of each log. They co-sign C2SP-shaped checkpoints only when the log has grown append-only.
- `authorize()` is the gate. An effect is allowed only when a signed intent exists for exactly that action, the intent hasn't been used, and a k-of-n witness quorum has covered it. `shields-up` needs only a local signed intent, so an e-stop is never blocked.
- Intents are single-use under concurrency. `Log.claim()` (CLI: `gate --claim --key K --writer W`) takes an exclusive `flock` on `<log>.lock`, re-reads the log, runs `authorize()` and appends a `claim` entry in one critical section. A chokepoint executes only after the claim succeeds, and later records the `result` against the same intent.
- Witness hardening: `serve --host` takes this node's tailnet IP only (refuses `0.0.0.0`, LAN and hostnames; loopback only with `--allow-loopback` for tests). Funnel is on at host-a, so never map the witness port through Funnel or `tailscale serve`. POST bodies over 1 MiB get `413`.
- The box is a writer, never a witness. It queues entries while it is asleep or cut off, then calls `reconcile()` on wake. Until a quorum co-signs, its effects are denied.

```
pip install cryptography            # only non-stdlib dependency
python3 -m unittest -v products/hmi/ledger/test_ledger.py
python3 products/hmi/ledger/ledger.py keygen ~/.config/cstack/ledger/<name>.key   # never inside the repo
python3 products/hmi/ledger/ledger.py gate --log L --origin O --roster R --intent H --action '{"op":"merge","pr":1}'
python3 products/hmi/ledger/ledger.py gate ... --claim --key K --writer W     # consume atomically; act only on exit 0
```

Exit codes: `0` allowed or ok, `77` denied (fail closed), `3` alarm on `verify`. When `LEDGER_ALARMS` is set, alarms are appended to that JSONL file for the sentinel.
The prototype isn't wired into any chokepoint yet; follow-up PRs will do that (see the DECISION-004 delivery plan).
