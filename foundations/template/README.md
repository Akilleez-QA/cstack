<p align="center"><img src=".github/assets/social-preview.png" alt="foundation-template" width="100%"></p>

# foundation-template

A minimal working Foundation to copy when you start a new domain

<img src="https://img.shields.io/badge/license-GPL--3.0--only-2400FF?style=flat-square&labelColor=000000"> <img src="https://img.shields.io/badge/python-3.11%2B-6E61FF?style=flat-square&labelColor=000000">

## Family

| Repository | Role | Relation |
|---|---|---|
| [cstack](https://github.com/Akilleez-QA/cstack) | Runs Foundations behind pinned adapters under one human approver | Host |
| [foundation-engine](https://github.com/Akilleez-QA/foundation-engine) | TypeScript and three.js framework for browser games | Foundation |
| [foundation-math](https://github.com/Akilleez-QA/foundation-math) | Exact mathematical kernels and physics research tools | Foundation |
| [foundation-film](https://github.com/Akilleez-QA/foundation-film) | Film-production acceptance checks | Foundation |
| [foundation-refrigeration](https://github.com/Akilleez-QA/foundation-refrigeration) | Refrigeration data and checks | Foundation |
| [foundation-robotics](https://github.com/Akilleez-QA/foundation-robotics) | Physics checks for motion | Foundation |
| [foundation-template](https://github.com/Akilleez-QA/foundation-template) | Minimal Foundation to copy for a new domain | Foundation |
| [endoforge](https://github.com/Akilleez-QA/endoforge) | Workshop for running coding agents with checks and receipts | Tool |
| [poodo](https://github.com/Akilleez-QA/poodo) | Reasoning skill that shows evidence before it acts | Tool |

## Status

Version 0.1.0. 1 read-only tool(s) behind a stdio JSON-RPC bridge, standard library only. Every result carries Evidence and an input hash. A verdict is an observation, not an acceptance decision.

## Quickstart

```
git clone https://github.com/Akilleez-QA/foundation-template
cd foundation-template
python -B -m unittest discover -s tests -t .
python -B tools/build_manifest.py
```

## What is inside

| Tool | Purpose |
|---|---|
| `echo_observation` | PLACEHOLDER: returns its validated input as an observation with Evidence |

## Measured

4 tests pass with `python -B -m unittest discover -s tests -t .` on Python 3.14.8 in a fresh clone (normal and `-O`). CI: local only.

## Documentation

See [docs/README.md](docs/README.md): requirements, architecture, interface control, verification matrix, configuration management.


## Layout

| Path | Contents |
|---|---|
| `foundation_template/` | Domain package |
| `foundation_template_bridge/` | stdio JSON-RPC bridge and schemas |
| `tests/` | Unit and bridge tests |
| `tools/` | Manifest and data tools |
| `docs/` | Requirements, architecture, ICD, verification, configuration, guides |
| `SOURCE-MANIFEST.json` | SHA-256 of every shipped file |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## License

This project is available under the GNU General Public License v3.0 only (GPL-3.0-only). If you want to use it to create a product or service under different terms, commercial licenses are available from Refrigeration.AI. Contact craig@nh3.biz.
