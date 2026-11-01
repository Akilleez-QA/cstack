# Third-party notices

`references/software-engineering.md` contains selected procedures adapted and rewritten from pstack 0.15.15, copyright 2026 Lauren Tan. The adaptation uses the source at commit `df581122cde17e6e27686b5a448bde23e4ad4318` in `cursor/plugins`, retrieved 2026-10-08. The source license is reproduced unmodified below.

Source: <https://github.com/cursor/plugins/tree/df581122cde17e6e27686b5a448bde23e4ad4318/pstack>

| Adapted procedure | Upstream source within `pstack/` |
| --- | --- |
| Relevant system tracing | `skills/how/references/explorer-prompt.md` |
| Historical constraints | `skills/why/SKILL.md` |
| Interface design and review | `skills/architect/SKILL.md`, `skills/architect/references/design-red-flags.md` |
| Defect investigation | `skills/poteto-mode/playbooks/bug-fix.md`, `skills/principle-fix-root-causes/SKILL.md` |
| Boundary validation | `skills/principle-boundary-discipline/SKILL.md` |
| Parallel mutation and retry behavior | `skills/principle-separate-before-serializing-shared-state/SKILL.md`, `skills/principle-make-operations-idempotent/SKILL.md` |
| Consumer-grounded tests | `skills/principle-test-behavior-not-implementation/SKILL.md` |
| Dependency frontier and verification freshness | `skills/principle-sequence-verifiable-units/SKILL.md`, `skills/poteto-mode/playbooks/shipping.md` |

The adaptation changes scope and wording to preserve POODO's domain-independent loop, evidence semantics, authority, host portability, and existing state ledger. It includes no upstream controller, executable, installer, model configuration, automation, or runtime dependency.

## Upstream license

MIT License

Copyright (c) 2026 Lauren Tan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
