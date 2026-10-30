# ADR 004: Private witnessed ledger as the mandatory authority gate

Status: merged to `main` by Chief of Staff as #18 (`05c9a11`). Prototype merged as #19 (`bc1aa8c`, `products/hmi/ledger/`). Enforcement is OFF by default (`LEDGER_ENFORCE` unset) until the owner turns it on; chokepoint wiring lands as separate small PRs.

## Context

the owner asked to put the fleet "on a blockchain backbone" (2026-10-24), then narrowed the request the same night (23:32–23:35 ET):

- The ledger is **private**: tailnet only, "just for us". No public chain, no OpenTimestamps, no public transparency log, no tokens or wallets.
- It is a **mandatory gate**, not an optional log. POODO actions, shields commands, board check-ins and merges are valid only if a signed ledger entry exists **before** execution. Execute-then-log is not allowed.
- **No single key or node** can rewrite or skip history, and gaps and forks alarm.
- **Shields-up Level 2** partitions the machines from each other. Nodes keep appending locally and reconcile on all-clear.
- **The Grok Bot box is unreachable whenever Grok Bot is asleep**, so it can't be a required witness. It is a writer-only client.

Today:

- `adapters/memory_ledger.py` is bounded, single-process and hash-chained. Its own docstring says "Hash chaining is not authentication."
- `products/hmi/shields/ledger.py` is an unchained, unsigned decision/attempt/receipt JSONL file.
- ADR 003 item 4 (open branch `claude-code/20261025-fleet-aor-adr`) plans a durable hash-chained `LedgerPort` adapter as Chief of Staff PR 4.

This ADR adds signatures, cross-node witnessing and the gate. The `LedgerPort` adapter should persist through this format so there aren't two ledgers (see Convergence).

## Decision

### 1. Shape

- **One log per node.** The log's `origin` is the node name: `host-a`, `box`, and so on. A log is append-only JSONL. Each entry carries `v, origin, seq, prev, writer, wseq, kind, ts, body, ref, sig, hash`, where:
  - `prev` is the previous entry's `hash` (genesis is 64 zeros);
  - `sig` is ed25519 over the canonical JSON of every field except `sig` and `hash`;
  - `hash` is sha256 over the canonical JSON including `sig`.
- **Writers** are per bot and per device. The roster binds each writer to exactly one node (`writers.<name>.node`), so a writer key can't append to another node's log.
- **Kinds:** `intent`, `result`, `shields`, `checkin`, `merge`, `note`. A `result` refers to its intent through `ref`.
- **Roster.** `roster.json` holds public keys only: writers, witnesses and `quorum`. It is versioned in the repo, so changing it is itself a reviewed PR. Private keys never enter the repo.

### 2. Witnesses and quorum

- Witnesses are **always-on tailnet nodes**. Each one keeps a verified replica of every node's log and co-signs a checkpoint only when it covers append-only growth of that replica.
- The checkpoint text has the C2SP `tlog-checkpoint` shape (`origin\nsize\nhead\n`). A cosignature signs an 8-byte big-endian timestamp followed by that text, as in C2SP `tlog-cosignature`.
- The witness API mirrors C2SP `tlog-witness`: `GET /head?origin=` returns the replica size. `POST /add-checkpoint {origin, old, entries, size, head}` returns one of:
  - `200 {cosig}`;
  - `422 {alarm: rollback}` whenever the presented `size` is below the witness's verified replica size (or below `old`). This is checked **first**, so a stale `old` can never turn a rollback into a retryable conflict. The client also writes a local `witness-rollback` alarm;
  - `409 {conflict: size}` only when the client's `old` is stale and the log has not shrunk (the client re-reads `/head`);
  - `422 {alarm}` on equivocation.
- A checkpoint counts only with cosignatures from **k distinct roster witnesses** (k ≥ 2; target 2-of-3). A node's own witness cosignature can count toward its own log's quorum, but alone it is always below quorum.
- **The box is never in the witness set.** It gets no witness key and no vote, and `load_roster` refuses `quorum < 2`.

### 3. The gate (pre-register, then act)

`authorize(log, intent_hash, action)` allows an action only if **all** of the following hold:

1. A signed `intent` entry with that hash exists in the actor's node log.
2. `intent.body.digest == sha256(canonical(action))`, so the action that runs is exactly the one that was registered.
3. No `claim` or `result` refers to the intent yet (single use). Chokepoints consume the intent with `Log.claim()` / `gate --claim`, which holds an exclusive `flock` on `<log>.lock` across re-read, `authorize()` and appending the `claim` entry, so two concurrent callers can never both pass on one intent.
4. The intent's `seq` is at or below a quorum-cosigned checkpoint.

Anything else, including parse errors, a missing roster, a missing key, an alarm on open or an unreachable witness, is **denied (exit 77)**. The CLI is `ledger.py gate --log --origin --roster --intent --action`. After the effect, the actor appends a `result` with outcome `applied`, `failed`, `unknown` or `not_dispatched`, using the same outcome vocabulary as shields `ledger.py`.

**E-stop asymmetry.** `shields-up` is allowed on a local signed intent alone, because a safety stop must never wait for quorum. `all-clear` and every effect class need quorum. During a Level 2 partition, effects are therefore denied, which matches ADR 003 item 7 (deny effectful classes under shields).

### 4. Chokepoints (follow-up PRs, each small)

| Chokepoint | Change |
|---|---|
| `products/hmi/shields/lib/codex-guard.sh` | Before `exec "$@"`, require `LEDGER_INTENT` and call `ledger.py gate`. On non-zero exit, stop with 77. Keep the existing `CODEX_BLOCKED` check first. |
| `shields-up.sh` | Write a local `shields` intent, then act. Never wait for the network. |
| `all-clear.sh` and the poller | Gate with quorum, then reconcile all logs before lifting. |
| Board API `/api/checkin` | Reject a request unless it carries `intent` and `log`, and the gate passes on the board host's replica. |
| Merges (`gh pr merge` wrapper used by Chief of Staff) | Gate `{"op":"merge","repo","pr","head_sha"}`. The head SHA is in the digest, so a later push invalidates the intent. |
| POODO kernel attempts | `LedgerPort.attempt` writes an intent, the kernel gates on it, and the receipt becomes the `result`. |

Bots can't skip these because the scripts they must call are the gates. A bot with a shell can still run a raw command around a wrapper, so the hard boundary for effects that matter is on the **receiving** side: the board API, the shields poller on host-a, and GitHub branch protection that requires Chief of Staff. Those check the ledger on hosts the bot doesn't control.

### 5. Gaps, forks and alarms

The following conditions raise an alarm. Alarms are appended to `$LEDGER_ALARMS` as JSONL; the sentinel tails that file and pages, and an alarm always also denies.

- `bad-signature`, `hash-mismatch` or `chain-break`, found by verifying the whole log on every open.
- `writer-seq-gap`: each writer's `wseq` is monotonic per node, so a hidden or dropped entry is detected.
- `unknown-writer`, `wrong-origin`.
- `equivocation`: a node offers a witness entries that don't extend the head that witness already accepted.
- `rollback`: a node presents a smaller size than before.
- `fork`: two witnesses compare (size, head) for an origin over gossip and disagree.
- `checkpoint-mismatch`.

### 6. The box (writer-only client)

- **Signing.** The box signs with its own writer key, appends to its own `box` log, and **queues** while asleep or partitioned. Queuing needs nothing: the local log is the queue.
- **On wake.** `reconcile(log, witness_urls)` pushes the unseen tail to each witness and stores a checkpoint only if k cosignatures came back.
- **Fail closed.** Gate checks for box-run effects fail closed. If witnesses are unreachable from the box, `push` returns None, no checkpoint is stored, and `authorize` denies (tested). An e-stop (`shields-up`) still works from the box.
- **Storage.** The box keeps its key on disk with mode 0600, outside the repo. It is ephemeral and shared with every Grok Bot agent, so it is the weakest key holder. Its writer entry should be limited to low-class effects until it has a hardware-backed or remotely held key.

### 7. Key custody (honest)

| Node | Target | What this guarantees |
|---|---|---|
| host-a | Witness and writer keys in a hardware key (YubiKey/ed25519-sk) or the OS keyring (Secret Service), owned by a user the bots don't run as | Root on the rig can still *use* a keyring key while it is unlocked. A touch-required hardware key limits that to one use per human touch. |
| Second and third witnesses | A key file readable only by a dedicated `ledger` user; witness process run under systemd with `ProtectHome`/`NoNewPrivileges` | Protects against bots, not against root on that device. |
| box | File key, mode 0600 | Protects against nothing beyond file permissions. Treat box entries as low assurance. |
| the owner | Phone board key as a human co-signer for high-class effects (merge to main, all-clear, money-adjacent) | The only signer outside every machine. Optional in v1 and recommended for v2. |

`chattr +a` on the log and checkpoint files makes them append-only to non-root processes. Root can clear the flag; the witnesses, not the flag, are what defend against root.

## Tailnet witness candidates (observed 2026-10-24 23:37 ET via `rig.py run 'tailscale status'`)

| Device | State seen | Always-on? |
|---|---|---|
| host-a (linux) | idle, online, offers exit node, Funnel on | **Yes.** Witness 1. |
| field-ops-tablet (linux) | active, direct LAN connection, high traffic | **Probably.** Online now and heavily used; uptime not verified. Witness 2 candidate. |
| host-b (linux) | offline, last seen 1 day ago | No, not today. Could become witness 3 if kept powered. |
| laptop-a | offline, last seen 8 min ago | No (laptop sleeps). |
| grok-box-1 / grok-box | the box; offline between wakes | **Never** a witness (writer only). |
| host-a-1 (windows) | offline, last seen 42 days ago | No. |
| the owner's phone | not on the tailnet | No. It would sleep anyway; better used as a human co-signer than a witness. |

**Gap:** only host-a is confirmed always-on, and the tablet is likely. With two witnesses, a 2-of-2 quorum means losing either one denies every effect: safe, but brittle.

**Cheapest fix:** a Raspberry Pi 4 or 5 (or any spare always-on Linux box) joined to the tailnet as witness 3, giving 2-of-3. The other option is to keep host-b powered. The phone is not a good witness because iOS and Android suspend background servers.

**Funnel:** host-a has Tailscale Funnel enabled. The witness must bind to the tailnet IP only, never to a Funnel or public listener. `ledger.py serve --host` enforces this: it accepts only a literal address in `100.64.0.0/10` or `fd7a:115c:a1e0::/48`, refuses `0.0.0.0`, `::`, LAN addresses and hostnames, and allows loopback only with `--allow-loopback` (tests), because Funnel and `tailscale serve` proxy to localhost targets. Never add a Funnel or serve mapping for the witness port. `POST /add-checkpoint` is capped at `MAX_BODY` (1 MiB): over the cap is `413`, a missing length is `411`, and the body is never read. Concurrent POSTs for one origin are serialized on the replica lock.

## Level 2 partition and reconcile

During L2, every node keeps appending to its own log with local signatures. Effects stay denied because nothing new can be witnessed, and `shields-up` still works. On all-clear:

1. All-clear itself needs a quorum. The witnesses must be reachable again, and they are always-on devices.
2. Each node runs `reconcile` and witnesses cosign the queued tails.
3. Witnesses gossip `(origin, size, head)` with each other and alarm on any fork.
4. Intents that were queued during L2 become usable only once they are witnessed. They are not re-executed automatically, because POODO never retries on its own.

## Options considered (sources fetched 2026-10-24)

| Option | What it is | Fit | Verdict |
|---|---|---|---|
| **Custom C2SP-shaped witness protocol** (this ADR) | About 200 lines of Python on `cryptography` ed25519, using the C2SP checkpoint, cosignature and witness formats | Survives a partition (local append, later witnessing); no daemon beyond a small witness; formats match the ecosystem | **Recommended.** |
| Tessera + litewitness | Tessera v1.0.4, 2026-07-16 (github.com/transparency-dev/tessera/releases; v1.0 GA: blog.transparency.dev/tessera-v1-0-is-here), a Go tlog library with a POSIX driver and C2SP witness support. litewitness (github.com/FiloSottile/torchwood, cmd/litewitness): a self-hosted C2SP witness on SQLite, keys in ssh-agent. | Strongest crypto (Merkle consistency proofs), the same formats, but adds a Go toolchain and binaries on every node | **Fallback / v2.** Migration is format-compatible. |
| immudb | v1.11.2, 2026-09-03 (github.com/codenotary/immudb/releases). Replication docs (immudb.io/docs/production/replication, /sync-replication): primary plus read-only replicas; the replicator needs admin credentials; sync replication blocks when the quorum is missing. | One primary is a single writer to compromise; a cross-node admin credential; it blocks under partition | Rejected. |
| Hyperledger Besu (QBFT) | docs.besu-eth.org: at least 4 validators, more than 2/3 must be online | Halts under L2; heavy JVM; Ethereum tooling we don't need | Rejected. |
| Hyperledger Fabric (Raft orderers) | hyperledger-fabric.readthedocs.io: at least 3 orderers (5 recommended), majority online, plus CA/MSP, peers and chaincode | Halts under L2; operationally far beyond four machines | Rejected. |

Quorum-consensus stacks stop accepting writes when partitioned. the owner needs writes to continue locally and only *authority* to wait for witnesses. Witness co-signing gives exactly that split.

## Threat model

**Assets:** the integrity and completeness of the history of authority (intents and results), and the rule that no effect runs without a witnessed intent.

**Root compromise of one node N. Root on N can:**

- Read and use any key on N, including N's writer keys and N's witness key. It can therefore append *new*, valid-looking entries to N's log for N's bots. Other witnesses will cosign those entries, because they extend history. Mitigations:
  - entries are attributable, and the sentinel and the owner can review them;
  - high-class effects require the owner's phone co-sign (v2);
  - touch-required hardware keys on the rig;
  - receiving-side gates on other hosts.
- Bypass local wrapper scripts on N and run raw effects on N itself. Those effects are invisible to the ledger. The ledger can't stop a local root; receiving-side gates on *other* hosts can.
- Clear `chattr +a` and edit N's local files. Every reader then detects the edit (signature or chain alarm), and witness replicas still hold the original.
- Withhold N's log (stop pushing). N's effects then stay denied elsewhere, and the gap is visible as a stale witnessed size.
- DoS N's own witness, reducing 2-of-3 to 2-of-2.

**Root on one node can't:**

- Rewrite or delete entries the witnesses have already cosigned. They refuse with `equivocation`, and N's own cosignature is below quorum. Tested in `test_single_node_rewrite_rejected_by_quorum`.
- Forge entries for writers bound to other nodes, or forge other witnesses' cosignatures.
- Present different histories to different witnesses without detection: gossip raises `fork`.
- Use an intent twice, or use it for a different action (digest plus single use).

**Residual risks:**

- Two of three witnesses compromised means the quorum can be forged. This is why witness 3 should be a separate physical device, and why a human co-signer is recommended for high-class effects.
- A history is only as protected as its last witnessed checkpoint. Entries a node appended but never got witnessed can be silently replaced by that node, though they can never authorize an effect.
- Timestamps are claims, not proofs; cosignature timestamps only order a witness's own view.
- The box's key is on a shared, ephemeral disk.
- The prototype re-verifies whole logs and uses no Merkle proofs: O(n) cost, acceptable up to roughly 10^5 entries. Tessera is the upgrade path.
- Roster changes are trusted at merge time. Whoever controls merges controls the roster, so roster PRs need the owner.

## Convergence with ADR 003 PR 4

**Decided (Chief of Staff): adopt directly, no wrapper.** `LedgerPort` writes this format as-is: kernel `decision` maps to `intent`, `attempt` gates on it, and `receipt` maps to `result`. The eight `memory_ledger` event kinds map onto `body.event`, so there is one durable ledger with one verifier. Device identity follows ADR 003 item 6: a witness checks that a node's Tailscale WhoIs identity matches the roster `node` (v2).

## Delivery plan (small PRs, each one concern)

1. This ADR.
2. Prototype `products/hmi/ledger/` with tests. The only new dependency is `cryptography`, already on the box and not yet on the rig.
3. Roster plus keygen runbook. Keys are created on each device, and only public keys are committed.
4. Witness service on host-a and witness 2 (systemd, tailnet bind only). It **ships disabled**.
5. `codex-guard.sh` gate, behind `LEDGER_ENFORCE=1`, default off until the owner flips it.
6. Shields scripts and poller: e-stop asymmetry and reconcile on all-clear.
7. Board `/api/checkin` gate.
8. Merge wrapper gate.
9. Sentinel tail of `$LEDGER_ALARMS`.
10. v2: human co-sign for high classes, WhoIs binding, Tessera migration if logs grow.

## Open questions

1. Which device is witness 3: a new Pi, or keeping host-b powered? Is field-ops-tablet actually always-on?
2. Should merges to main and all-clear require the owner's phone co-sign from day one?
3. Can we approve adding `cryptography` to the rig, and to `requirements.txt` for the HMI product?
4. ~~Should Chief of Staff's `LedgerPort` (ADR 003 PR 4) adopt this format directly, or wrap it?~~ **Resolved: adopt directly.** Chief of Staff decided the ADR 003 adapter uses the DECISION-004 format with no wrapper: one format, one verifier (see Convergence with ADR 003 PR 4).
5. Should the box's writer be limited to low-class effects until its key is remotely held?
