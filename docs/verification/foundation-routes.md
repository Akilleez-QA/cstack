# Foundation routes into a workcell

Measured 2026-11-06 with `python -B tools/measure_foundation_routes.py --calls 20 --pyodide PATH` on a shared desktop: Linux, Node 26.13.0, Python 3.14.9, one host, no quiet gate. Process and exec counts come from `tools/spawncount.py`, which uses ptrace on every process in the tree, and cover the whole window around the calls. Positive control: 20 stdio calls count 21 of each, and `tests/test_workcell_foundation_imports.py` asserts the control.

| Foundation | Python source lines | Route | Calls | Processes spawned | Exec | Time per call |
|---|---:|---|---:|---:|---:|---:|
| Refrigeration | 1,417 | stdio bridge, today | 20 | 21 | 21 | 65.6 ms |
| Refrigeration | | JS port, process cell, whole job | 12,000 | **0** | **0** | 50 µs through WASM, 40 µs in the kernel |
| Refrigeration | | JS port, thread cell, whole job | 12,000 | **0** | **0** | 41 µs through WASM, 34 µs in the kernel |
| Refrigeration | | Pyodide, outside the guard | 1,000 | 0 | 0 | 142 µs |
| Template | 47 | stdio bridge, today | 20 | 21 | 21 | 28.8 ms |
| Template | | JS port, process cell, whole job | 4,000 | **0** | **0** | 9 µs through WASM, 6 µs in the kernel |
| Template | | JS port, thread cell, whole job | 4,000 | **0** | **0** | 10 µs through WASM, 6 µs in the kernel |
| Template | | Pyodide, outside the guard | 1,000 | 0 | 0 | 44 µs |
| Film | 670 | stdio bridge, today | 20 | 21 | 21 | 35.2 ms |
| Film | | Pyodide, outside the guard | 1,000 | 0 | 0 | 96 µs |
| Robotics | 1,036 | stdio bridge, today | 20 | 21 | 21 | 58.3 ms |
| Robotics | | Pyodide, outside the guard | 1,000 | 0 | 0 | 145 µs |
| Math | about 21,000, with its vendored helpers | stdio bridge, today | 20 | 21 | 21 | 144.7 ms |
| Math | | Pyodide, outside the guard | 1,000 | 0 | 0 | 284 µs |

"Whole job" means the JS port's window runs from port creation to evidence, so it also covers compile, gates and frozen checks: nothing in that job spawned a process. Exact counts vary little between runs; the times are one run each and come with no variance.

## Pyodide

Pyodide 0.29.0 (MPL-2.0) ran all five Foundations unchanged, from the pinned bytes, with zero spawns. It costs 1.06 s and 169 MiB of RSS per cell before the first call. It can't run behind the workcell's WASM guard today: `pyodide.asm.wasm` imports two exception tags (`env.__c_longjmp`, `env.__cpp_exception`), the guard's rewriter doesn't support tag imports, and it fails closed with `unsupported wasm feature in bounded workcell`. Those numbers come from a bare Node process, so they aren't a workcell result. It isn't a Cstack dependency.

## Decision per Foundation

| Foundation | Route | Why, and what's left |
|---|---|---|
| Refrigeration | **Shipped: JS port plus the pinned data projections** | About 1,600 times faster than stdio and 3 times faster than Pyodide, with no per-cell cost, and it runs behind the guard. Its risk is drift, so `tests/test_foundation_kernels.py` compares 3,233 vectors with the pinned Python, including every tool, error message and input digest, on every run: 0 differences. The kernel route takes ASCII arguments only and refuses the rest, because Python and JS differ on Unicode case and space. Vectors are a sample and don't prove equivalence |
| Template | **Shipped: JS port** | 47 lines of Python; 9 vectors, 0 differences |
| Film | Not shipped; decisions through the pinned stdio bridge work today | A JS port is about half of Refrigeration's size and has the same shape. It needs a port, differential vectors and a fixed reading of its `FOUNDATION_FILM_*` environment defaults |
| Robotics | Not shipped; decisions through the pinned stdio bridge work today | A JS port of 1,036 lines of float arithmetic and tables. It needs a port and vectors. `pow` and `sqrt` may differ in the last place, as the differential will show |
| Math | Not shipped; decisions through the pinned stdio bridge work today | A port is the wrong route: exact rational arithmetic over about 21,000 lines would be a second implementation of what must stay exact. Python-in-WASM is the honest route, and it needs the guard to support tag imports, or a separate cohort without the guard, which the owner would have to accept explicitly |

A kernel that calls a granted Foundation with no shipped route gets a refusal handle, and the run can't pass on it. `foundation_engine` isn't in this repository.

## What these numbers don't show

A spawn count of zero says nothing about correctness. A JS port is a second implementation that a pin doesn't cover: the pin covers the port's bytes and the Python's bytes, and only the differential ties them together. The Foundation stays the reference.
