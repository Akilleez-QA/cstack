# Foundation Math research layer
`fm_research` uses stdlib exact arithmetic over untouched, byte-pinned
`vendor/foundation-math-v014`. A `fm-research-problem/1` JSON file records repo/commit,
role handles, assumptions, exclusions, and a DAG of computed/cited/argued claims.
The example's `unpinned-example` is illustrative, not a research pin.
Kernels: `twoi.decompose_sym_W`, `twoi.decompose_tensor`,
`twoi.invariant_count_sym_W`, `twoi.distinct`, `rank`, `p1.h0_dim`, `p1.h1_dim`.
Ranks support Q, Q(sqrt5), F_p; rationals are integers or `n/d` strings;
quadratic `[a,b]` means a+b*sqrt(5). Floats are rejected; decomposition term order is ignored.
Evidence binds arguments, expectation, output, module bytes and catalog; rank includes
a verified certificate. Git HEAD/Python version record context. Hashes are not signatures:
use trusted local records, rerunning untrusted ones. Certified means an exact finite check
matched with certified/cited ancestors; FAIL is refuted; ERROR/missing is unchecked;
unmet dependencies block a passing check. Cited/argued claims need human review,
never certification. No surrounding argument is proved. POODO maps `fm-research-gate/1`
to valid identifier `fm-research-gate:1`, requires 1..32 computed criteria, and trims prose/lists.
Endoforge gets a need/acceptance seed; its atomizer must supply the DAG. From `foundations/math`:
`python3 -B -m fm_research check examples/2i-regression.problem.json` accepts `--claim ID` / `--evidence-out FILE.jsonl`; `goal SPEC` / `atoms SPEC` emit JSON.
Tests: `python3 -B -m unittest discover -s tests -t .` and `python3 -B -O -m unittest discover -s tests -t .`.
