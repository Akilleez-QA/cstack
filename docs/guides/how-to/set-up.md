# How to set up Cstack on a machine

One command sets up a machine so your bots can use Cstack and keep what they do:

```sh
python -B tools/cstack_init.py
```

Run it once after you install, and again whenever you add a bot to `aors/fleet.json`. Running it again is safe: it keeps everything that is already there and adds only what is missing.

## What it sets up

Everything goes in one private state folder, `~/.local/state/cstack` unless you pass `--state-root`. Folders are created readable only by you (mode 0700), and files the same way (mode 0600).

| Item | Where | Why |
|---|---|---|
| Device name | `device.json` | Says which device in `aors/fleet.json` this machine is |
| A signing key per bot | `ledger/keys/<bot>.key` | Each bot signs its own ledger entries |
| Two witness keys | `ledger/witnesses/` | The ledger format needs at least two; see [Witnesses](#witnesses) |
| Roster | `<state>/ledger/roster.json` | Public keys only: which key belongs to which bot and witness |
| Ledger settings | `ledger.json` | Where the ledger, roster and keys are; written last |
| Per-bot state | `<bot>/anchors.json` | Where each bot's server records the last ledger position it saw |

With this in place, every bot's MCP server writes to a durable, signed, hash-chained ledger that survives restarts. Without it the server won't start (see [Development without a ledger](#development-without-a-ledger)).

When it finishes, it prints what it did and what to do next:

```text
Ready. Bots: example. Device: example-host. Every bot records to a durable, signed ledger that survives restarts.

Next:
  Start a bot's server:  python -B tools/cstack_mcp.py --aor example
  Check health later:    python -B tools/cstack_init.py --check
```

## Check health

```sh
python -B tools/cstack_init.py --check
```

This changes nothing. It reports each problem in plain words with the fix, verifies every ledger file's signatures and chain, and exits 1 if anything needs attention, 0 if all is well.

## Device names and Tailscale

Each machine needs a device name that `aors/fleet.json` lists. Tailscale is optional. `cstack init` picks the name in this order:

1. `--device NAME`, if you pass it;
2. the name an earlier `cstack init` recorded;
3. this machine's Tailscale name, if Tailscale is installed and signed in;
4. otherwise this computer's own name, in lowercase.

If the name it finds isn't in the bot list and the bot list has exactly one device, it uses that device. That is why a fresh clone, with the single `example-host` device, works as is. Otherwise it asks you to add a `devices` entry or pass `--device`.

The MCP server uses the same name: `--device` if given, else the recorded name, else the Tailscale name.

## Witnesses

The ledger format (DECISION-004) expects independent witness machines to co-sign it, so that a compromised machine can't quietly rewrite its own history. `cstack init` makes two witness keys on this machine, so the ledger works from the start. Because they live on the same machine, they don't give that protection: the ledger is durable and signed, but nothing outside the machine vouches for it yet. To get real witnessing, run witnesses on other machines and list their public keys in `<state>/ledger/roster.json`. `cstack init` never replaces a roster that already exists.

## Fix problems

- **A key is readable by other users.** It may have been copied, so `cstack init` won't repair it. Delete it and run `cstack init` again to make a new one.
- **A key doesn't match the roster.** `cstack init` never replaces keys or roster entries. Put the original key back, or move `ledger/` and `ledger.json` aside to start a new ledger.
- **A ledger file failed verification.** Keep the file: it is the record. Don't run bots until you know why it changed.
- **A folder or settings file is open to other users.** `cstack init` makes it private again.

## Development without a ledger

For a throwaway session, such as a test, the server can run on a memory-only ledger that is lost when it stops. You must ask for it explicitly:

```text
python -B tools/cstack_mcp.py --aor example --device example-host --allow-memory-ledger
```

Bots configured by `tools/agent_profiles.py` never get this flag; `tests/test_cstack_init.py` fails if they do.

Return to the [how-to guides](README.md).
