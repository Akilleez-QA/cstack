<p align="center"><img src=".github/assets/social-preview.png" alt="foundation-film" width="100%"></p>

# foundation-film

Film-production acceptance checks as integer-only, read-only tools with Evidence on every result

[<img src="https://img.shields.io/github/actions/workflow/status/Akilleez-QA/foundation-film/ci.yml?branch=main&style=flat-square&labelColor=000000" alt="CI">](https://github.com/Akilleez-QA/foundation-film/actions/workflows/ci.yml) <img src="https://img.shields.io/badge/license-GPL--3.0--only-2400FF?style=flat-square&labelColor=000000">

## Status

Version 0.1.0, no release tag yet. Six read-only tools behind a stdio JSON-RPC bridge, standard library only, plus an optional offline video producer. Every result carries Evidence and an input hash. A verdict is an observation, not an acceptance decision.

Classification: self-assessed Class E analog (research and general-purpose software), not safety-critical. This is not a NASA compliance determination. See the [software management plan](docs/plan/software-management-plan.md#1-software-classification-self-assessed).

## Quickstart

```
git clone https://github.com/Akilleez-QA/foundation-film
cd foundation-film
python -B -m unittest discover -s tests -t .
python -B tools/build_manifest.py
```

The tests print `OK (skipped=4)`; the four skipped tests need the optional video libraries below. The manifest tool prints the file count, the manifest SHA-256 and the tool inventory SHA-256 that a host pins. To send your first request to the bridge, follow the [tutorial](docs/guides/tutorials/first-check.md).

### Local video measurements

The visual core of Endoforge's `tools/film/filmstats.py` now lives in
`foundation_film/filmstats.py`. Run it locally with optional CPU dependencies:

```
uv run --no-project --python 3.12 --with numpy --with opencv-python-headless --with scenedetect python -B -m foundation_film.filmstats sample.avi --fps 8 --width 640 > shots.json
```

The output is the `{"shots": [...]}` argument object for `reference_bands` or
`cinematic_gate` (add reference bands or rules for the gate). Times are milliseconds;
all metrics are milli-units. This offline producer opens the supplied video and
retains sampled frames in memory; it is outside the bounded stdio bridge.
It ports shot detection, optical-flow camera classification and visual measures.
Audio extraction, palettes, contact strips and legacy summary files are deferred.

## What is inside

| Tool | Purpose |
|---|---|
| `cinematic_gate` | Per-segment cinematic gate: duration-weighted shot measures (filmstats.py, milli-units) against reference bands (default filmgate.py rules) or explicit rules |
| `reference_bands` | Duration-weighted p25/p50/p75 bands per shot metric, and moving_share, from a measured reference (filmstats.py, milli-units) |
| `audio_gate` | Soundtrack against the mix contract: integrated loudness and true peak (milli-LU/dBTP), voice over bed (milli-dB), share of cuts carrying a hit, AudioSet classes heard, WER per line (per-mille) |
| `drift_verdict` | Clip verdict for control-conditioned generation (I20): per-frame edge F1 and mask IoU, optional depth error and identity similarity (driftgate.py, milli-units) against thresholds, gated on the worst frame; first failing frame and worst-frame summary |
| `cue_vocabulary_check` | Static check of the shared cue vocabulary (I18): ids each lane references against the ids the voice/markers provide (with aliases), per-beat required order and minimum gaps in time |
| `look_gate` | Rejection alarm for the look: per frame, lookgate.py's palette distance, exposure, contrast range, clipping, detail and chroma ratios against an approved target frame (milli-units), every frame against every threshold |

## Measured

Test results for the documented baseline, with commit, environment and per-test outcomes, are in the latest generated [test report](docs/verification/reports/README.md). CI runs the suite in normal and `-O` modes on Python 3.12 without the optional libraries, verifies the source manifest and runs gitleaks. The producer's video tests need the full-dependency commands:

```
uv run --no-project --python 3.12 --with numpy --with opencv-python-headless --with scenedetect python -B -m unittest discover -s tests -t .
uv run --no-project --python 3.12 --with numpy --with opencv-python-headless --with scenedetect python -B -O -m unittest discover -s tests -t .
```

## Limitations

- Results judge measurements the caller supplies. A pass is not acceptance of a film, cut or mix; the client stays the acceptance authority.
- Default rules, the mix contract and the look thresholds come from one reference production run and are mostly marked `CHECK` in Evidence.
- See [Limitations](docs/guides/explanation/limitations.md).

## Documentation

See [docs/README.md](docs/README.md): tutorial, how-to guides, tool reference, explanation, and the control documents (management plan, requirements, design, interface, data dictionary, test plan, verification matrix, configuration management, test reports, version descriptions, assurance record).

Evidence citations default to the relative locations `docs/PLAYBOOK-film.md` and
`tools/film/`. Set `FOUNDATION_FILM_PLAYBOOK` and `FOUNDATION_FILM_PRODUCERS` before
starting the bridge or importing `foundation_film.tools` to cite other locations.
The producer directory may include a trailing slash. These are citation locations;
the tools do not open these files or require them to exist in this repository.

## Related projects

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

## Layout

| Path | Contents |
|---|---|
| `foundation_film/` | Domain package |
| `foundation_film_bridge/` | stdio JSON-RPC bridge and schemas |
| `tests/` | Unit and bridge tests |
| `tools/` | Manifest and data tools |
| `docs/` | Control documents and guides |
| `SOURCE-MANIFEST.json` | SHA-256 of every shipped source file outside root `.github/` |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Help: [SUPPORT.md](SUPPORT.md).

## Security

See [SECURITY.md](SECURITY.md).

## License

This project is available under the GNU General Public License v3.0 only (GPL-3.0-only). If you want to use it to create a product or service under different terms, commercial licenses are available from Refrigeration.AI. Contact craig@nh3.biz.
