# Foundations and pins

A Foundation is a domain package, such as exact math or refrigeration data, that Cstack runs through an adapter. This page explains which Foundations ship in this repository and why Cstack refuses to run one whose files have changed.

## Which Foundations ship here

Most Foundations are vendored, meaning copied into this repository and pinned by hash. Each has its own upstream repository.

| Foundation | In this repository | How Cstack uses it |
|---|---|---|
| [foundation-math](https://github.com/Akilleez-QA/foundation-math) | `vendor/foundation-math-v014/`, plus the research layer in `foundations/math/` | Vendored copy of v0.14, run through `adapters/math_stdio.py` and `extensions/foundation_math.py` |
| [foundation-film](https://github.com/Akilleez-QA/foundation-film) | [`foundations/film/`](../../../foundations/film/) | Vendored copy, byte-pinned |
| [foundation-refrigeration](https://github.com/Akilleez-QA/foundation-refrigeration) | [`foundations/refrigeration/`](../../../foundations/refrigeration/) | Vendored copy, byte-pinned. Also an in-process kernel in workcells |
| [foundation-robotics](https://github.com/Akilleez-QA/foundation-robotics) | [`foundations/robotics/`](../../../foundations/robotics/) | Vendored copy, byte-pinned |
| [foundation-template](https://github.com/Akilleez-QA/foundation-template) | [`foundations/template/`](../../../foundations/template/) | Vendored copy, byte-pinned. Also an in-process kernel in workcells |
| [foundation-engine](https://github.com/Akilleez-QA/foundation-engine) | `vendor/foundation-engine-v020/`, partial: bridge, schema and manifest | Two read-only validators, run through `adapters/engine_stdio.py` and `extensions/foundation_engine.py`. The engine's TypeScript runtime isn't included |
| [endoforge](https://github.com/Akilleez-QA/endoforge) | [`vendor/endoforge/`](../../../vendor/endoforge/), byte-pinned | Lifecycle, gates, ledger and `IsolatePool`, run through `adapters/endoforge_workcell.py` |
| [poodo](https://github.com/Akilleez-QA/poodo) | `reasoning/poodo/` | Earlier snapshot of the skill that the core follows |

## How pins work

Cstack does not trust a vendored Foundation just because it is present. Each one ships a `SOURCE-MANIFEST.json` that lists a hash for every file. `contracts/SOURCE-PINS.json` records the expected hash of each manifest, and the adapters refuse to run a Foundation whose files or manifest don't match. To update a Foundation, copy in the new version, rebuild its manifest with `foundations/<name>/tools/build_manifest.py`, update the pin, and run all the test suites on a reviewed branch. EndoForge has its own tool; see [repin EndoForge](../how-to/repin-endoforge.md). There is no automatic upgrade. The pin values are listed in [docs/icd/icd-foundations.md](../../icd/icd-foundations.md). A matching pin proves that the bytes are unchanged. It does not prove that the content is correct.

Return to the [explanation index](README.md).
