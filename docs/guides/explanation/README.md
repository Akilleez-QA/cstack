# Explanation

Background that helps you reason about Cstack. These pages say why, not how-to.

| Page | Explains |
|---|---|
| [How Cstack vendors and runs EndoForge](endoforge-vendoring.md) | Why EndoForge is a pinned copy, what the slice holds, and how a forge goal crosses from the core to the workcells and back |
| [The server, the driver and the adapters](server-and-adapters.md) | The CLI driver, the MCP server for bot sessions, the capability adapters and what the host keeps |
| [Architecture](../../architecture/architecture.md) | Control-core composition and the Foundation boundary |
| [Foundations and pins](foundations-and-pins.md) | Which Foundations ship here and why Cstack refuses one whose files changed |
| [Control decisions](../../../contracts/DECISION.md) | The core's invariants and capability model, and the later decision records beside it |
| [Limitations and safety-relevant use](limitations.md) | What results mean, what Cstack does not do, and how not to use it |

Return to the [documentation index](../../README.md).
