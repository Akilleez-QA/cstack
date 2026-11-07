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
| Refrigeration | **Shipped: JS port plus the pinned data projections** | About 1,600 times faster than stdio and 3 times faster than Pyodide, with no per-cell cost, and it runs behind the guard. Its risk is drift, so `tests/test_foundation_kernels.py` compares about 26,000 vectors with the pinned Python on every run: every tool, error message and input digest, units, sides and atmospheres, seeded random arguments, and exact text such as `-0`, duplicate keys, long numbers and `\\u` escapes. 0 differences outside the rounding limit below. Where Python raises and gives no receipt, the kernel refuses and gives none. The input digest matches for ASCII arguments, and the kernel route refuses the rest, because Python and JS differ on Unicode case and space. Vectors are a sample and don't prove equivalence |
| Template | **Shipped: JS port** | 47 lines of Python; 9 vectors, 0 differences |
| Film | Not shipped; decisions through the pinned stdio bridge work today | A JS port is about half of Refrigeration's size and has the same shape. It needs a port, differential vectors and a fixed reading of its `FOUNDATION_FILM_*` environment defaults |
| Robotics | Not shipped; decisions through the pinned stdio bridge work today | A JS port of 1,036 lines of float arithmetic and tables. It needs a port and vectors. `pow` and `sqrt` may differ in the last place, as the differential will show |
| Math | Not shipped; decisions through the pinned stdio bridge work today | A port is the wrong route: exact rational arithmetic over about 21,000 lines would be a second implementation of what must stay exact. Python-in-WASM is the honest route, and it needs the guard to support tag imports, or a separate cohort without the guard, which the owner would have to accept explicitly |

A kernel that calls a granted Foundation with no shipped route gets a refusal handle, and the run can't pass on it. `foundation_engine` isn't in this repository.

## What these numbers don't show

A spawn count of zero says nothing about correctness. A JS port is a second implementation. `contracts/SOURCE-PINS.json` pins the Python's bytes, the port's bytes, the host port, the broker and the vendored engine, and a run refuses to start if any differ, reporting that nothing ran. The host port is also in the frozen tree, so a change during a run fails the frozen check. Only the differential ties the port's meaning to the Python: the judge at run time is the pinned port, not the Python itself.

A local writer who changes a file and its pin together isn't caught. The pins detect drift and accidents, and they aren't a defence against someone who can write to this checkout. Nothing here is signed.

## Numeric limit of the JS port

`Math.exp`, `Math.log` and the libm behind Python are different implementations. Measured with Node 26.13.0 and this host's Python: `exp` differed in the last place on 19,397 of 200,000 inputs (9.7%), `log` on 2,664 of 200,000 (1.3%), by at most one unit; `pow` on 0 of 200,000. Receipts round to 4 places, so this rarely shows: 0 of 100,000 random `saturation_pressure` receipts differed. At temperatures chosen within two units in the last place of a rounding boundary, 544 of 72,000 receipts differed (0.76%), each by one unit in the last printed place, such as 2785.8792 against 2785.8791.

I chose to state this limit and not port an exp and log. Python's own results depend on the host's libm, and glibc selects different code by CPU, so a port would match one machine and not the reference in general. A held-out check whose tolerance is 0 can fail at such a boundary; it can't pass wrongly by more than that one unit. The receipt's Foundation identity carries this as `numeric_tolerance`, and the boundary test holds the difference to one unit.
