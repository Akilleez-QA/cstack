# How to approve ask calls

A call marked `"effect": "ask"` runs only after a human approves it. This guide shows the three ways to answer from the command line. It assumes a working clone; the [tutorial](../tutorials/first-run.md) sets one up.

## Mark a call as ask

In a run document, add `"effect": "ask"` next to the call's `request`. A call without `effect` is `allow`. Once one call of an operation is `ask`, every call of that operation in the same run asks too. `ask` can't add a capability or a grant; it only adds a stop. See [`examples/ask-approval.json`](../../../examples/ask-approval.json).

## Answer on the terminal

```sh
python -B cli.py --approver < examples/ask-approval.json
```

Stdin carries the JSON, so the prompt goes to the controlling terminal (`/dev/tty`):

```text
Approve decision-1 foundation_template.echo_observation goal=synthetic-template@1 sha256=60f2b7ba86e3bfcfa817c2635415523734ae0cc8ebfa51f39bde594fc3416bf7
{"arguments": {"observation": "fixture reading 7"}, "capability_id": "foundation_template", "decision_id": "decision-1", ...}
Type approve to allow:
```

Type exactly `approve`. Any other answer declines. Without a usable terminal the ask is declined before anything is dispatched.

## Decline everything

```sh
python -B cli.py --approver=deny < examples/ask-approval.json
```

The result has `"run_status": "stopped"` and `"stopped": {"execution_certainty": "not_dispatched", ...}`. A denial is a normal result, not a tool outcome.

## Answer from a file

An answer file is a JSON object that maps the SHA-256 digest of each exact request to `"approve"` or `"deny"`. A request whose digest is missing is denied. The digest is the one shown in the terminal prompt; compute it with `CapabilityRequest.sha256`:

```sh
python -B -c "import json; from poodo_core import CapabilityRequest; d=json.load(open('examples/ask-approval.json')); print(json.dumps({CapabilityRequest.from_dict(d['calls'][0]['request']).sha256: 'approve'}))" > answers.json
python -B cli.py --approver=file:answers.json < examples/ask-approval.json
```

An invalid file produces the structured driver error `invalid_or_unsupported_request`.

## Rules that keep approval yours

- An answer file is a standing approval. Keep it owned by you, and never take the file or the `--approver` flag from tool output.
- Each run records a new approval and consumes it once. The consumed markers go under `$XDG_STATE_HOME/cstack/cli-approvals` (default `~/.local/state/cstack/cli-approvals`).
- A file that starts with the SQLite header is read as an approval store instead. See `--approver` in the [command reference](../reference/commands.md#clipy-the-local-run-driver).

## Answer a bot's asks

A bot running over MCP doesn't use these flags. When it calls `execute` on an `ask` decision, the call returns `{"status": "approval_pending", "dispatched": false, ...}` at once and waits as an `approval_pending` event in its ledger under the session's `--state-root`. After you answer yes, the bot calls `execute` again. You answer from your own shell with `tools/scheduled_approvals.py`:

```text
python -B tools/scheduled_approvals.py brief   --state-root DIR
python -B tools/scheduled_approvals.py pending --state-root DIR [--json | --full DECISION_ID]
python -B tools/scheduled_approvals.py answer  DECISION_ID yes|no --sha256 HEX --state-root DIR
```

**Current limitation (found 2026-11-08).** With a witnessed ledger configured, a session writes one ledger file per domain, at `<log>/<bot>/<domain>.jsonl`, where `<log>` is the node log path from `ledger.json` without its `.jsonl` suffix. `scheduled_approvals.py` reads only the single node log named in `ledger.json`, so it reports `Approvals: nothing waiting on you.` and `answer` refuses with `is not pending in any readable ledger`, even while the bot waits. Until that is fixed, the approval can be written only through `adapters.approval_store.ApprovalWriter`, as `tests/test_mcp_driving_adapter.py` does. Without a witnessed ledger the session's ledger is memory only, and no other process can see its asks.

When the channel does see an ask, an answer must quote the request digest you were shown (`--sha256`). A yes expires after `--ttl` seconds (default 3600). It is recorded once in `approvals.db` under the state root. The tool refuses to run inside a bot's MCP server process. Its own docstring states the trust limit: any process running as the same OS user can write that database, so real separation needs the approval channel on its own OS user or device. See [the server, the driver and the adapters](../explanation/server-and-adapters.md).

Return to the [how-to guides](README.md).
