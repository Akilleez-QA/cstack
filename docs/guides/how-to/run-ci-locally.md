# How to run the CI checks locally

Run the same checks as [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml) before you open or merge a pull request, and list each one with its result in the PR body.

## Set up once per clone

CI uses Python 3.12 through uv and Node 24. Any Python 3.12 or newer and Node 22 or newer work locally.

With uv, as CI does:

```sh
uv venv --python 3.12 .venv
. .venv/bin/activate
uv pip install --python .venv -r requirements.txt -r ci/requirements.txt
npm ci --prefix adapters/workcell-toolchain --ignore-scripts --no-audit --no-fund
```

Without uv:

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt -r ci/requirements.txt
npm ci --prefix adapters/workcell-toolchain --ignore-scripts --no-audit --no-fund
```

`ci/requirements.txt` adds `cryptography`, `pillow` and `numpy` to the root requirements. Without `cryptography` about 70 witnessed-ledger tests skip instead of running.

## Run the `test` job

```sh
python -B -m unittest discover -s tests
bash ci/run-local.sh python links trace
```

The first command is the root suite. The second runs, in order:

1. the root suite again, normally and with `python -O`;
2. each `foundations/*/tests` suite from its own directory, normally and with `-O`;
3. `tools/check_links.py`, which checks that links and backticked repository paths in the documents it scans exist;
4. `tools/check_trace.py`, which checks that every requirement traces to tests and to the design, every test file is traced, and links and headings named in the control documents exist.

Both must exit 0. A failure in `-O` mode only usually means a check relied on `assert`.

`ci/run-local.sh` uses `python3` unless you set `PYTHON`:

```sh
PYTHON=.venv/bin/python bash ci/run-local.sh python links trace
```

## Run the `secrets` job

CI installs TruffleHog 3.99.7 and runs:

```sh
bash ci/scan-secrets.sh
```

It scans the working tree and fails on any finding, except the paths listed in `.trufflehog-exclude-paths.txt`. Locally it also scans untracked files such as `.venv/`, so findings in installed packages there are not repository findings; report them as such.

The repository also has a gitleaks pre-commit hook (`.pre-commit-config.yaml`, rules in `.gitleaks.toml`). Install it once per clone with `pre-commit install`.

## Other suites in `ci/run-local.sh`

`bash ci/run-local.sh` with no arguments runs `python links trace refrigeration gitleaks trufflehog`. You can name any of these suites:

| Suite | What it runs | Needs |
|---|---|---|
| `python` | Root and Foundation suites, normal and `-O` | The setup above |
| `links` | `python -B tools/check_links.py` | Nothing extra |
| `trace` | `python -B tools/check_trace.py`: requirement, design and test traceability ([verification matrix](../../verification/verification-matrix.md)) | Nothing extra |
| `readme` | `python -B tools/check_readme.py`: every README command on a fresh clone | Network for the clone and installs; `gh` and `claude` logins, or those commands are reported as skipped |
| `refrigeration` | `tools/e2e_refrigeration.sh`: the refrigeration CLI acceptance with a host approval | The setup above |
| `gitleaks` | `gitleaks dir . --no-banner` | `gitleaks` on `PATH` |
| `trufflehog` | `bash ci/scan-secrets.sh` | `trufflehog` on `PATH` |

An unknown suite name exits 64. `bash ci/run-local.sh --setup` installs `ci/requirements.txt` into the selected Python.

## Optional checks that CI skips

These tests skip unless you point them at something outside the repository:

| Variable | Test | Set it to |
|---|---|---|
| `CSTACK_ENDOFORGE_CLONE` | `tests/test_endoforge_pin.py` checks the pinned commit is reachable from the clone's `origin/main` | A fetched EndoForge clone |
| `CSTACK_MCP_SDK_ESM` | `tests/test_mcp_stdio_client.py` runs the official MCP TypeScript SDK server | An installed `@modelcontextprotocol/sdk` `dist/esm` directory |

For example:

```sh
CSTACK_ENDOFORGE_CLONE=../endoforge python -B -m unittest tests.test_endoforge_pin
```

## How long it takes

Measured on 2026-11-08 on `e02a0c4` plus this documentation refresh, Python 3.12.14 and Node 26.13.0 on Linux, on a shared 32-CPU machine with other jobs running:

| Command | Result | Wall time |
|---|---|---|
| `python -B -m unittest discover -s tests` | 712 tests, OK, 3 skipped | 11 min |
| `bash ci/run-local.sh python links` | Exit 0: root suite normal and `-O`, five Foundation suites (25, 18, 49, 34 and 10 tests) normal and `-O`, 584 paths checked, 0 broken | 20 min |

Your times will differ. Scale the checks to the change: a documentation-only change still needs `links`, and the PR should say which checks you ran.

## Report the result

List each command with a one-line result in the PR body, for example:

```text
python -B -m unittest discover -s tests: Ran N tests, OK (skipped=2)
bash ci/run-local.sh python links trace: exit 0; M paths checked, 0 broken; 0 trace failures
```

Say which checks you skipped and why. Passing checks are not engineering, safety or compliance approval.
