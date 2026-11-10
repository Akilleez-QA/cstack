# Tutorial: run your first goals on a fresh clone

This tutorial takes you from an empty directory to three kinds of run:

1. a Foundation call through the control core,
2. a call that needs a human approval,
3. a forge goal that compiles a kernel in an EndoForge workcell and checks it against a pinned Foundation.

It takes about ten minutes. Every command and every output line below was run on a fresh clone of `main` at `e02a0c4`, on Linux with Node 26.13.0, once with Python 3.12.14 and once with Python 3.14.9.

## Before you start

You need:

- Linux or macOS. The spawn counter in the test suite needs Linux; the tutorial itself doesn't.
- Python 3.12 or newer. The pinned numpy doesn't install on 3.11.
- Node 22 or newer, on `PATH`. The forge goal starts a Node supervisor.
- `git` and `npm`.

You don't need an API key, a model login or network access after the install step.

## 1. Clone and install

```sh
git clone https://github.com/Akilleez-QA/cstack
cd cstack
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r ci/requirements.txt
npm ci --prefix adapters/workcell-toolchain --ignore-scripts --no-audit --no-fund
```

The last command installs the pinned AssemblyScript 0.28.20 compiler that the workcells use. It is locked in `adapters/workcell-toolchain/package-lock.json`, and its hashes are checked before every forge run.

## 2. Create the host configuration

```sh
cp cstack.config.example.json cstack.config.json
```

`cstack.config.json` is host configuration. It decides where the witnessed ledger lives (`endoforge.path`) and what a forge run may use (`workcell`). Request data can't change either. The [configuration reference](../reference/configuration.md) lists every key.

## 3. Run a Foundation call

The example `examples/scalar-and-negative.json` is a goal in the `foundation_math` domain with two calls: an exact rational addition and a polynomial identity that is false.

```sh
python -B cli.py < examples/scalar-and-negative.json | python -c 'import json,sys; d=json.load(sys.stdin); print(d["run_status"], d["endoforge_implemented"], [e["data"]["outcome"]["assessment"] for e in d["events"] if e["kind"]=="outcome"])'
```

Output:

```text
completed True ['exact_scalar_result', 'formal_polynomial_identity_not_equal']
```

What happened:

- The driver started the goal, moved it through the observe, orient and decide phases using the checkpoints in the file, and recorded one decision per call.
- The core checked each call against a host grant, then the Math adapter started the pinned bridge in `vendor/foundation-math-v014` and checked its source manifest before and after.
- The second outcome is a completed negative answer. It is evidence, not an error, and it is not a proof.
- The goal stays open (`"closed": false`). A tool result never closes a goal.
- `endoforge_implemented` is `True` because the config names a witnessed ledger. Every decision and outcome went into `endoforge.jsonl`.

The full output is one JSON document with the schema `cstack.run-result/0.1`. Drop the pipe to see it.

## 4. Ask for approval

`examples/ask-approval.json` marks its call `"effect": "ask"`. An ask needs a host approval before anything is dispatched. With `--approver=deny` nothing runs:

```sh
python -B cli.py --approver=deny < examples/ask-approval.json | python -c 'import json,sys; d=json.load(sys.stdin); print(d["run_status"], d["stopped"]["execution_certainty"])'
```

```text
stopped not_dispatched
```

Now approve it with a host answer file. The file maps the SHA-256 digest of the exact request to `"approve"`:

```sh
python -B -c "import json; from poodo_core import CapabilityRequest; d=json.load(open('examples/ask-approval.json')); print(json.dumps({CapabilityRequest.from_dict(d['calls'][0]['request']).sha256: 'approve'}))" > answers.json
python -B cli.py --approver=file:answers.json < examples/ask-approval.json | python -c 'import json,sys; d=json.load(sys.stdin); print(d["run_status"], [e["data"]["outcome"]["assessment"] for e in d["events"] if e["kind"]=="outcome"])'
```

```text
completed ['observation_echoed']
```

Each run creates a new approval and consumes it once. The consumed markers go under `$XDG_STATE_HOME/cstack/cli-approvals` (default `~/.local/state/cstack/cli-approvals`). A bare `--approver` prompts on your terminal instead; type exactly `approve`.

## 5. Run a forge goal

A forge goal asks a model for a kernel, compiles it in a workcell and judges it. This step uses the stub transport, which replays a recorded answer (`examples/forge/saturation.ts`), so no model is called.

```sh
CSTACK_STUB_TRANSPORT_SCRIPT=examples/forge/saturation-stub.json python -B cli.py < examples/forge/saturation-goal.json > forge-run.json
python -c 'import json; d=json.load(open("forge-run.json")); o=[e["data"]["outcome"] for e in d["events"] if e["kind"]=="outcome"][0]; r=o["raw_result"]; print(d["run_status"], o["assessment"], r["compiler"]["name"], r["compiler"]["version"], {k: v["route"] for k, v in r["foundations"].items()}, r["candidates"][0]["cgroup"])'
```

Output on a host that doesn't delegate cgroups to the user:

```text
completed candidate_passed assemblyscript 0.28.20 {'foundation_refrigeration': 'js-port'} unavailable
```

The last field is the receipt's `cgroup` entry. It says `enabled` where the host delegates cgroups. Workcells are V8 isolates, not an OS sandbox, so the receipt records what containment there was.

What happened, in order:

1. The core recorded a decision for one `run_goal` call in the `cstack_forge` domain, under a host grant.
2. `adapters/endoforge_workcell.py` checked `adapters/workcell/` and `vendor/endoforge/` against `contracts/SOURCE-PINS.json`, froze the evaluator in the EndoForge ledger (`forge.sqlite`) and started one Node supervisor.
3. The supervisor asked the transport for source, compiled it with AssemblyScript in an `IsolatePool` workcell, and ran it.
4. The kernel called `foundation_refrigeration` through a declared import. The call ran in process, through the JavaScript port of the pinned Foundation.
5. The gates and the frozen evaluator compared the kernel's outputs with the pinned Foundation's own results on the held-out checks.
6. The receipt names the decision, grant, compiler, Foundation versions and the runtime pin. It was witnessed in `endoforge.jsonl`.

Run the same command again. It passes again, with a new task and a new candidate, because each run is its own attempt.

The run left these files next to your config:

| Path | What |
|---|---|
| `endoforge.jsonl` | The host's witnessed ledger: one hash-chained JSON line per precommit and outcome |
| `forge.sqlite` | The EndoForge run ledger: frozen evaluator, candidates and receipts |
| `forge.sqlite.core/` | One core ledger per forge session; `.closed` when the session ended with every outcome known, `.recovered` when it left an `unknown` outcome |
| `forge.sqlite.journal/` | The vendored ledger writer's journal |

## 6. Clean up

```sh
rm -rf endoforge.jsonl forge.sqlite forge.sqlite.core forge.sqlite.journal forge-run.json answers.json
```

Keep `cstack.config.json` if you want to carry on. It is ignored by git.

## Where next

- Run the checks CI runs: [run CI checks locally](../how-to/run-ci-locally.md).
- Use a real model: set `workcell.transport` to `adapters/workcell/claude-transport.mjs`, as [use a real model](../how-to/use-a-real-model.md) describes.
- Understand what you just ran: [how Cstack vendors and runs EndoForge](../explanation/endoforge-vendoring.md).
- Look up a flag, key or variable: [reference](../reference/README.md).
