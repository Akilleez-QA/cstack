# shields: local checks (2026-10-24, America/New_York)
Target: `products/hmi/shields/`. PR files: shields-up.sh, all-clear.sh, rig.py, ledger.py, lib/shields-local.sh, lib/codex-guard.sh, RUNBOOK.md, CHECKS.md, .gitignore (ledger.jsonl, shields.log, local-state/, snapshots/, dry-runs/, CODEX_BLOCKED are runtime, gitignored).

| Check | Result |
|---|---|
| `bash -n` on shields-up.sh, all-clear.sh, lib/shields-local.sh, lib/codex-guard.sh | ok |
| `python3 -m py_compile` rig.py, ledger.py | ok |
| `nft -c -f` on generated rulesets: rig L1, rig L2, box L1 | ok (validated without loading) |
| `shields-up.sh --dry-run --level 1` | rc=0 (dry-runs/shields-up-L1.txt). Rig: 10 codex processes would stop. Box: 0. |
| `shields-up.sh --dry-run --level 2` | rc=0 (dry-runs/shields-up-L2.txt) |
| `all-clear.sh --dry-run` | rc=0 (dry-runs/all-clear.txt). Funnel rebuild `--https=443 / → 127.0.0.1:4176` shown. Codex lock removed. |
| Ledger | 14 decision/attempt/receipt records, all `not_dispatched` (dry-run) |
| Live fire | NOT done (dry-run only by instruction) |
Not run: shellcheck (not installed on the box).

## Follow-up: rig.py host-key pin (2026-10-25, America/New_York)
| Check | Result |
|---|---|
| `py_compile` rig.py | ok |
| Pinned ed25519 (SHA256:kOy52TxkaKu9MJVijtJ4P2dhYf6e1Q+eEvNb+pVCIRw): `rig.py run true`, `rig.py ping` | rc=0, ssh-ok |
| Pin cross-checks: live `get_remote_server_key` = box's pre-existing hashed known_hosts entry = rig's own `/etc/ssh/ssh_host_ed25519_key.pub` | match |
| `RIG_HOSTKEY` = random ed25519 key (MITM simulation) | BadHostKeyException, rc=98 |
| `RIG_KNOWN_HOSTS` = empty file | "not found in known_hosts", rc=98 |
| `RIG_KNOWN_HOSTS` = file with the pinned line | rc=0 |

## Follow-up: codex-guard ledger gate (2026-10-25, America/New_York)
Depends on DECISION-004 single-use claims (`ledger.py gate --claim`). Enforcement is OFF unless `LEDGER_ENFORCE=1`.
| Check | Result |
|---|---|
| `bash -n lib/codex-guard.sh` | ok |
| `python3 -m unittest products/hmi/shields/test_codex_guard.py` | 6 tests ok: default log-only runs; enforce with no intent/env, missing key or missing ledger.py -> 77; unwitnessed -> 77; wrong argv -> 77; witnessed runs once, second launch -> 77; 6 concurrent enforced launches -> exactly one runs |
| `python3 -m unittest products/hmi/ledger/test_ledger.py` | ok (unchanged behaviour plus `intent` CLI) |
| `CODEX_BLOCKED` check | still first (exit 75 while shields are up) |

## Follow-up: shields-up / all-clear ledger hooks (2026-10-25, America/New_York)
Depends on DECISION-004 single-use claims. `lib/ledger-gate.sh` is sourced by both scripts; enforcement OFF unless `LEDGER_ENFORCE=1`.
| Check | Result |
|---|---|
| `bash -n` shields-up.sh, all-clear.sh, lib/ledger-gate.sh | ok |
| `python3 -m unittest products/hmi/shields/test_shields_ledger.py` | 6 tests ok: shields-up never blocks (unconfigured, broken roster, even with LEDGER_ENFORCE=1); writes a local signed intent (dry: not claimed; live: claimed without quorum); all-clear log-only by default; enforced all-clear 77 with no intent, unwitnessed + unreachable witnesses, or wrong scope; enforced reconcile against 2 live witnesses then claim once, second run 77; dry-run never consumes; hooks sit before any change |
| Box mirror `shields-up.sh --dry-run --level 1` / `--level 2`, `all-clear.sh --dry-run` (unconfigured) | rc=0 / 0 / 0, "ledger: not configured (log-only)" |
| Box mirror, temp ledger configured: `shields-up.sh --dry-run --level 1` | rc=0, intent written (`dry_run`, not claimed) |
| Box mirror, `LEDGER_ENFORCE=1 all-clear.sh --dry-run` with no intent | rc=77 before the decision record or any engine call |
Caveat: at Level 2 the box cannot reach the witnesses, so an enforced all-clear from the box is denied. Recovery is the board all-clear, the console (`sudo shields restore`), or the auto-rollback timer.
