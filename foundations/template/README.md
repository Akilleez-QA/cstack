# Foundation Template

The empty domain. A Foundation is whatever domain you need: it owns the domain's meaning, data and acceptance,
and POODO governs how it is used. This one is a minimal working Foundation with a single **placeholder** tool,
`echo_observation`. The tool returns its validated input as an observation, with Evidence. It proves the
plumbing and nothing else.

The plumbing is the same for every Foundation:

- **Pinned source.** `SOURCE-MANIFEST.json` hashes every file. The host adapter pins the manifest's SHA-256, its
  file count and the tool inventory's SHA-256. It re-verifies them before dispatch and after every accepted
  response.
- **Bounded execution.** The bridge runs as `python -B -m foundation_template_bridge` with a fixed cwd and a
  minimal fixed environment. Frame, depth, node, string and integer limits apply on both sides. It runs under a
  deadline, with no shell, no caller paths and no network.
- **Exact receipts.** Every result carries `receipt.input_sha256`. The host recomputes it from the request and
  validates the whole result against the pinned output schema.
- **Read-only grants.** Every tool is an observation (`boundary.observation_only`). Bootstrap grants only the
  `read` effect.
- **Evidence on every result,** errors included (`receipt.evidence`, at least one entry).

The protocol is `foundation-template-jsonrpc/1`. It is not MCP.

## Check it

```sh
cd foundations/template
python -B -m unittest discover -s tests       # the bridge over real stdio, and the manifest
python -B tools/build_manifest.py             # rewrites SOURCE-MANIFEST.json; prints the three pins
```

From the repository root, `python -B -m unittest discover -s tests` runs the host side. The template is the core
suite's sample domain.

## Make it your domain

The steps below use `widgets` as the example name.

1. **Rename.**
   - Copy `foundations/template` to `foundations/widgets`.
   - Rename the packages to `foundation_widgets` and `foundation_widgets_bridge`, and fix their imports in
     `server.py`, `tests/` and `tools/build_manifest.py`.
   - In `server.py`, set `PROTOCOL = "foundation-widgets-jsonrpc/1"` and the `serverInfo` name.
2. **Add tools.**
   - In `foundation_widgets/tools.py`, replace `echo_observation` with your tools. Name each one in `TOOL_NAMES`
     and `TOOLS`.
   - A tool takes its arguments dict and returns `(assessment, result, evidence_entries)`. It raises
     `ToolInputError` for bad input.
   - Cite real sources in Evidence instead of a practice note. Values stay `CHECK` until a qualified person
     approves them.
   - Add each tool's `inputSchema` and `outputSchema` to `foundation_widgets_bridge/schemas.py`, in the same order
     as `TOOL_NAMES`. If your Evidence cites sources, widen `EVIDENCE_ENTRY`.
   - Keep `BOUNDARY` or define your own; the host checks it exactly. Never add a control or write tool to a
     read-only Foundation.
   - The numeric profile is bounded integers and strings only. If you need decimals, change `_integer` and
     `_no_float` in `server.py`, and give the host adapter a matching `decode`. `adapters/refrigeration_stdio.py`
     shows one, where that Foundation is present.
   - Update `tests/test_bridge.py`, then run it.
3. **Pin sources.**
   - Run `python -B tools/build_manifest.py`. It prints `files`, `sha256` and `inventory_sha256`.
   - Run `python -B tools/build_manifest.py --inventory > ../../schemas/widgets-v01-tools.json`. This writes the
     host's vendored inventory copy.
   - Put the three pins in your adapter and in `contracts/SOURCE-PINS.json`.
   - Re-run both commands after any change to the Foundation. A stale pin fails closed: the adapter returns
     `source_identity_unavailable` and dispatches nothing.
4. **Register.**
   - Copy `extensions/foundation_template.py` to `extensions/foundation_widgets.py`. Set the domain id
     `foundation_widgets`, its tool names, its numeric semantics and its interpretation limits.
   - Copy `adapters/template_stdio.py` to `adapters/widgets_stdio.py`. Set its pins, inventory path, protocol,
     bridge module and boundary.
   - Add `foundation_widgets_bridge` to `LocalBridgeExecutor.BRIDGE_MODULES` in `adapters/execution.py`.
   - Add one `register(Domain(...))` entry in `bootstrap.py`. Guard it on the Foundation's folder, as
     Refrigeration's entry is guarded, if the domain is optional.
   - In `contracts/ADAPTERS.json`, add a `ToolFace` attachment row for the adapter and a `core_seam` row for the
     extension.
   - Add a host-side conformance test, modelled on `tests/test_template_conformance.py`. Run the root suite.

Keep the template registered when you add your own domain. The core tests use it, so they never depend on a real
domain.
