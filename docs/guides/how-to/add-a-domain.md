# How to add a domain

A domain is a set of tools the core can call, packaged as a Foundation and reached through an adapter. Cstack ships a Template Foundation to copy. The refrigeration, film and robotics domains are three complete worked examples; read their files beside these steps.

## The pieces

| Piece | Copy from | What it does |
|---|---|---|
| `foundations/<name>/` | `foundations/template/` | The Foundation: its tools, a stdio JSON-RPC bridge, tests and a `SOURCE-MANIFEST.json` of file hashes |
| `schemas/<name>-v01-tools.json` | `schemas/template-v01-tools.json` | The pinned tool catalog the adapter checks the live bridge against |
| `adapters/<name>_stdio.py` | `adapters/template_stdio.py` | A profile on `adapters/foundation_stdio.py`: source hash, file count, protocol, bridge module and boundary |
| `extensions/foundation_<name>.py` | `extensions/foundation_template.py` | The domain extension the core binds |
| A row in `contracts/ADAPTERS.json` | the `foundation-template-stdio` row | The adapter's identity and lane. `bootstrap.check_grants` refuses a grant that doesn't match it |
| An entry in `contracts/SOURCE-PINS.json` | the `foundation_template` entry | The expected manifest hash |
| A `register(Domain(...))` call in `bootstrap.py` | the `foundation_template` call | Adds the domain to `bootstrap.DOMAINS`, the one registry |

## Steps

1. Copy `foundations/template` to `foundations/<name>` and rename its packages.
2. Replace the placeholder tool with your own. Each result should carry a receipt and Evidence, as the template's do.
3. Rebuild its manifest with `foundations/<name>/tools/build_manifest.py`, then add the pin.
4. Add the schema, adapter, extension and inventory row from the table.
5. Register the domain in `bootstrap.py`.
6. Run every suite, on a reviewed branch: [run CI checks locally](run-ci-locally.md).

A pin proves that the bytes are unchanged. It doesn't prove the content is correct, so your Foundation's own tests matter. [Foundations and pins](../explanation/foundations-and-pins.md) explains the checks, and [the server, the driver and the adapters](../explanation/server-and-adapters.md) explains what each adapter does at run time.

Return to the [how-to guides](README.md).
