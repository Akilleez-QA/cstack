# End-to-end wiring: acceptance precommit

Status: frozen 2026-11-06 before any wiring was committed. Each item is judged on a fresh clone with the documented setup. A failure stays a recorded failure, and expected results don't change to make a test pass.

## Design target

EndoForge Edition 3 §4 (cycle), §5 (the kernel exports functions and imports capabilities; nothing reaches the broker, renderer or ledger except through the host), §6, §9 (the controller and ledger sit outside every cohort; outcome unknown is a state) and §12. Diagram Atlas sheets 01, 03, 06, 09, 11, 19, 20, 21 and 22. Hexagonal: the POODO core at the centre, running on EndoForge, with Foundations as driven-side domain extensions that own domain meaning and acceptance. Producers measure; Foundations judge. V8 isolates host the WASM, not bubblewrap.

## Items

1. One goal runs through a POODO grant and decision, a real EndoForge run in `IsolatePool` workcells using the real gates and ledger, and back to a witnessed receipt naming the decision, grant, compiler and Foundation versions. The test uses a stub model transport. No API keys and no real model calls.
2. Inside a workcell, a coder or kernel calls a Foundation through a declared import, in-process, with zero process spawns per call for pure computation, and gets a pinned, attributable result. A real spawn counter measures this per Foundation: refrigeration, math, film, robotics, template. The route is decided per Foundation from numbers among a compiled or JS port of pure kernels, versioned data projections, or a Python-in-WASM runtime. The chosen route ships for at least Refrigeration and Template, and what each other Foundation would need is stated.
3. A coder proposes a decision through the broker and the core accepts or refuses it. A candidate can't grant itself authority, can't reach a Foundation it didn't declare, can't get past a refusal, and can't record a pass from a refused or unknown run. Each has its own test.
4. Every README command passes, including approvals, `--approver=deny`, fleet validation, the merge train dry-run and the AOR MCP session. The README's "no runtime wiring" text and related-projects table are corrected to what's then true. A kill during a run surfaces as `outcome_unknown`, tested with a real SIGKILL.

## Failure meaning

An item that fails is reported as failed, with its command and result. A design violation is reported as a failure, not scoped out as a limit.
