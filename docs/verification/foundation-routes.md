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
| Film | | JS port, process cell, whole job | 4,004 | **0** | **0** | 31 µs through WASM, 26 µs in the kernel |
| Film | | JS port, thread cell, whole job | 4,004 | **0** | **0** | 27 µs through WASM, 23 µs in the kernel |
| Film | | Pyodide, outside the guard | 1,000 | 0 | 0 | 96 µs |
| Robotics | 1,036 | stdio bridge, today | 20 | 21 | 21 | 58.3 ms |
| Robotics | | JS port, process cell, whole job | 4,004 | **0** | **0** | 126 µs through WASM, 111 µs in the kernel |
| Robotics | | JS port, thread cell, whole job | 4,004 | **0** | **0** | 104 µs through WASM, 92 µs in the kernel |
| Robotics | | Pyodide, outside the guard | 1,000 | 0 | 0 | 145 µs |
| Math | about 21,000, with its vendored helpers | stdio bridge, today | 20 | 21 | 21 | 144.7 ms |
| Math | | Pyodide, outside the guard | 1,000 | 0 | 0 | 284 µs |

The Film and Robotics JS port rows come from a later run of the same command without `--pyodide`, under Python 3.12.14, Node 26.13.0 and other work on the host; that run measured stdio at 50.0 ms for Film and 67.8 ms for Robotics. Each timed call is `cue_vocabulary_check` or `scale_timing`; the Film job also makes one Robotics call per case.

"Whole job" means the JS port's window runs from port creation to evidence, so it also covers compile, gates and frozen checks: nothing in that job spawned a process. Exact counts vary little between runs; the times are one run each and come with no variance.

## Pyodide

Pyodide 0.29.0 (MPL-2.0) ran all five Foundations unchanged, from the pinned bytes, with zero spawns. It costs 1.06 s and 169 MiB of RSS per cell before the first call. It can't run behind the workcell's WASM guard today: `pyodide.asm.wasm` imports two exception tags (`env.__c_longjmp`, `env.__cpp_exception`), the guard's rewriter doesn't support tag imports, and it fails closed with `unsupported wasm feature in bounded workcell`. Those numbers come from a bare Node process, so they aren't a workcell result. It isn't a Cstack dependency.

## Decision per Foundation

| Foundation | Route | Why, and what's left |
|---|---|---|
| Refrigeration | **Shipped: JS port plus the pinned data projections** | About 1,600 times faster than stdio and 3 times faster than Pyodide, with no per-cell cost, and it runs behind the guard. Its risk is drift, so `tests/test_foundation_kernels.py` compares about 26,000 vectors with the pinned Python on every run: every tool, error message and input digest, units, sides and atmospheres, seeded random arguments, and exact text such as `-0`, duplicate keys, long numbers and `\u` escapes. 0 differences outside the rounding limit below. Where Python raises and gives no receipt, the kernel refuses and gives none. The input digest matches for ASCII arguments, and the kernel route refuses the rest, because Python and JS differ on Unicode case and space. Vectors are a sample and don't prove equivalence |
| Template | **Shipped: JS port** | 47 lines of Python; 9 vectors, 0 differences |
| Film | **Shipped: JS port** | All six tools. Integer arithmetic only, so it is exact: products that pass 2^53 use BigInt. See the differential below |
| Robotics | **Shipped: JS port plus the pinned defaults** | All six tools. Results equal the pinned Python's or the call is refused, as the differential below measures. Calls that use `sin`, `cos`, `atan2`, `pow` or `math.dist` run nine times, so the slowest tools cost more than the table's `scale_timing` |
| Math | Not shipped; decisions through the pinned stdio bridge work today | A port is the wrong route: exact rational arithmetic over about 21,000 lines would be a second implementation of what must stay exact. Python-in-WASM is the honest route, and it needs the guard to support tag imports, or a separate cohort without the guard, which the owner would have to accept explicitly |

## Film and Robotics against the pinned Python

Both ports take what the bridge frame decoder takes: JSON integers up to 15 digits, no floats, no repeated keys, depth and size limits. They refuse the rest, plus non-ASCII text and `\u` escapes. Arguments are read into maps, so `__proto__` and numeric-looking keys behave as in Python. The reference is the pinned Python through `Bridge.handle`. `FOUNDATION_FILM_*` is read at its defaults because the stdio adapter's environment doesn't set it.

Measured 2026-11-06 with `python -B tools/fuzz_ports.py --count 100000 --scan 2000000000 --cap 400 --libm 200000` on Python 3.12.14 and Node 26.13.0, and with `--count 30000 --scan 200000000 --cap 200 --libm 50000` on Python 3.14.9, which also found 0 disagreements. Python 3.12 numbers:

| Set | Foundation | Compared | Agreed, result | Agreed, tool error | Both refused | Port refused alone | Disagreed |
|---|---|---:|---:|---:|---:|---:|---:|
| Every path | Film | 6,369 | 973 | 5,252 | 144 | 0 | **0** |
| Text traps | Film | 273 | 31 | 83 | 144 | 15 | **0** |
| Seeded fuzz | Film | 100,000 | 81,797 | 18,203 | 0 | 0 | **0** |
| Every path | Robotics | 16,662 | 2,435 | 13,457 | 280 | 490 | **0** |
| Text traps | Robotics | 273 | 24 | 90 | 144 | 15 | **0** |
| Seeded fuzz | Robotics | 100,000 | 90,093 | 8,723 | 3 | 1,181 | **0** |
| Near rounding boundaries | Robotics | 466 | 14 | 0 | 0 | 452 | **0** |

"Every path" sets one in every field of a seed to each of 27 bad values, which is why tool errors dominate it. The fuzz is where results dominate: 90 % for Robotics and 82 % for Film. Robotics' port-only refusals in the fuzz are 1,138 `numeric_boundary` and 46 `outside_domain` (with the 3 both refused), and `ik_check` accounts for 1,001 of them.

`tests/test_film_kernel.py` and `tests/test_robotics_kernel.py` run a smaller version of this on every suite run: every path, the text traps, 4,000 fuzz cases each and 126 boundary vectors.

### Numeric boundaries

Over 200,000 random calls each, against this host's glibc, V8 differed from Python in the last place on 6,690 `sin`, 7,702 `cos` and 35,310 `atan2` results and on 0 `pow` results, never by more than one unit. Robotics rounds its outputs to integers, so this only matters when an output sits at a rounding boundary or a tie. The port refuses those:

- Each call using those functions repeats under eight patterns of relative nudges of 2^-49 on their results. Any change in the integer output refuses the call with `numeric_boundary`.
- `ik_check` also refuses when a singular value is within 2^-42 of the largest eigenvalue's noise, because the fuzz found a pose that eight patterns missed.
- Coordinates above 2^25 mm in `balance_check` and `ik_check`, an offset beyond rod plus crank, and a derivative window over 10^6 frames are refused with `outside_domain`: they need integers beyond 2^53, raise in Python, or would keep Python busy for minutes.

Without the nudges, the same fuzz disagrees on 13 of 100,000 calls, as a tie in `gear_mesh` `worst_frame`; with them, 0. That is also the differential's positive control, and `tests/test_film_kernel.py` checks that it reports a changed result. An ordinary two-frame `gear_mesh` can tie this way and be refused.

Inputs are integers, so boundaries can't be bisected. The tool scans large outputs instead, where a unit in the last place is widest: 2,000,000,000 draws per family gave 466 near-boundary vectors for `ik_check`, `slider_crank` and `scale_timing`. In that set `atan2` isn't reached, because `four_bar` outputs are too small to scan to a boundary, and every `ik_check` vector was refused by the singular-value check, so it doesn't exercise the nudge. Only `gear_mesh` and the fuzz exercise those paths.

The refusal rule is measured, not proved: eight nudge patterns are a sample of the possible last-place differences. The reference is this host's libm and Python 3.12 or later, whose `sum()` is compensated; another libm can differ.

A kernel that calls a granted Foundation with no shipped route gets a refusal handle, and the run can't pass on it. `foundation_engine` isn't in this repository.

## What these numbers don't show

A spawn count of zero says nothing about correctness. A JS port is a second implementation. `contracts/SOURCE-PINS.json` pins the Python's bytes, the port's bytes, the host port, the broker and the vendored engine, and a run refuses to start if any differ, reporting that nothing ran. The host port is also in the frozen tree, so a change during a run fails the frozen check. Only the differential ties the port's meaning to the Python: the judge at run time is the pinned port, not the Python itself.

A local writer who changes a file and its pin together isn't caught. The pins detect drift and accidents, and they aren't a defence against someone who can write to this checkout. Nothing here is signed.

## Numeric limit of the JS port

`Math.exp`, `Math.log` and the libm behind Python are different implementations. Measured with Node 26.13.0 and this host's Python: `exp` differed in the last place on 19,397 of 200,000 inputs (9.7%), `log` on 2,664 of 200,000 (1.3%), by at most one unit; `pow` on 0 of 200,000. Receipts round to 4 places, so this rarely shows: 0 of 100,000 random `saturation_pressure` receipts differed. At temperatures chosen within two units in the last place of a rounding boundary, 544 of 72,000 receipts differed (0.76%), each by one unit in the last printed place, such as 2785.8792 against 2785.8791.

I chose to state this limit and not port an exp and log. Python's own results depend on the host's libm, and glibc selects different code by CPU, so a port would match one machine and not the reference in general. A held-out check whose tolerance is 0 can fail at such a boundary; it can't pass wrongly by more than that one unit. The receipt's Foundation identity carries this as `numeric_tolerance`, and the boundary test holds the difference to one unit.
