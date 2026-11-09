# Measurements, November 2026

This table was the "Measured" section of the README until 2026-11-08. It is kept here as written, as a historical record; it is not a current result. Current test results are in the generated [test reports](reports/STR-baseline.md).

Measured on 2026-11-06 with Python 3.14.9 and Node 26.13.0 on Linux, at commit `e2efa37` of the unmerged draft stack, except where the table says otherwise. GitHub CI results are on the pull requests.

| Check | Command | Result |
|---|---|---|
| Core test suite on `main`, Python 3.12.14 and Node 26.13.0, 2026-11-08 | `python -B -m unittest discover -s tests`, at `e02a0c4` | 711 tests, OK, 3 skipped |
| Every README command, on a fresh clone | `python -B tools/check_readme.py --source https://github.com/Akilleez-QA/cstack --branch harden-tools` | 16 commands, 0 failed, 0 uncovered, 0 skipped. The forge goal ran twice and passed both times |
| Core test suite, optimized | `python -B -O -m unittest discover -s tests` | 663 tests, OK, 2 skipped |
| Core test suite, Python 3.12.14 on two cores, normal and optimized | `taskset -c 0,1 python -B [-O] -m unittest discover -s tests`, at `7225ae9` | 663 tests, OK, 2 skipped, each |
| Core test suite with the Film and Robotics ports, Python 3.12.14 and Node 26.13.0, normal and optimized | `python -B [-O] -m unittest discover -s tests`, at `66420c3` | 681 tests, OK, 2 skipped, each |
| Film and Robotics ports against the pinned Python | `python -B tools/fuzz_ports.py --count 100000 --scan 2000000000 --cap 400 --libm 200000`, Python 3.12.14 | 0 disagreed over 224,043 vectors; 2,153 refused by the port alone. Details in [the routes](foundation-routes.md) |
| Core test suite and all suites | `python -B -m unittest discover -s tests`, `bash ci/run-local.sh python links`, inside the check above | Both exit 0; 38 paths checked, 0 broken |
| Secret scan | `bash ci/scan-secrets.sh` (TruffleHog) | 0 verified secrets; 2 unverified, in pip's vendored code in the untracked `.venv` |
| Secret scan | `gitleaks git`, over the stack | No leaks |

Foundation route numbers are in [the routes](foundation-routes.md), from their own run.
