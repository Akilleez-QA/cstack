# How-to guides

Run every command from the repository root. `python` means Python 3.11 or newer.

## Run the tests

```sh
python -B -m unittest discover -s tests -t .
python -B -O -m unittest discover -s tests -t .
```

CI runs both on Python 3.12 (see the [test plan](../../verification/test-plan.md)). Four producer tests are skipped unless the optional libraries are installed.

## Run the optional producer tests

```sh
uv run --no-project --python 3.12 --with numpy --with opencv-python-headless --with scenedetect python -B -m unittest discover -s tests -t .
uv run --no-project --python 3.12 --with numpy --with opencv-python-headless --with scenedetect python -B -O -m unittest discover -s tests -t .
```

Expect `OK` with no skips. Run these after any change to `foundation_film/filmstats.py`.

## Measure a local video

```sh
uv run --no-project --python 3.12 --with numpy --with opencv-python-headless --with scenedetect python -B -m foundation_film.filmstats sample.avi --fps 8 --width 640 > shots.json
```

`shots.json` holds `{"shots": [...]}`: one entry per detected shot with `start_ms`, `end_ms`, `camera` and milli-unit `metrics`. Pass it as the arguments of `reference_bands`, or add `bands` or `rules` and pass it to `cinematic_gate`. The producer keeps every sampled frame in memory, so lower `--fps` or `--width` for long videos. On a synthetic 6 s video with one hard cut, it returns two static shots, 0–3000 ms and 3000–6000 ms.

## Rebuild the source manifest

Run after changing any file outside the root `.github/` tree, documentation included:

```sh
python -B tools/build_manifest.py
```

It rewrites `SOURCE-MANIFEST.json` and prints the file count, the manifest SHA-256 and the tool inventory SHA-256. A host that vendors this repository repins from that output. `python -B tools/build_manifest.py --inventory` prints the canonical catalog bytes.

## Override a default

- `cinematic_gate`: send `rules` instead of `bands`. The result says `rule_source: caller`.
- `audio_gate`: send `contract` with any of the default keys (see [defaults](../../data/defaults.md)). The result lists them in `contract_overrides` and adds a `caller` Evidence entry. For example, `"contract": {"cut_hit_share_min": 750}` gives `contract_overrides: ["cut_hit_share_min"]`.
- `drift_verdict` and `look_gate`: send `thresholds`. `threshold_sources` marks each value `caller` or the default source.

An unknown key or a non-integer value refuses the call.

## Change the citation locations in Evidence

Evidence cites `docs/PLAYBOOK-film.md` and `tools/film/` by default. To cite other locations, set these before starting the bridge:

```sh
FOUNDATION_FILM_PLAYBOOK=path/to/playbook.md FOUNDATION_FILM_PRODUCERS=path/to/producers python -B -m foundation_film_bridge
```

The tools never open these locations; they only appear in Evidence text.

## Troubleshoot an error

- A JSON-RPC `error` object means the message never reached a tool. Look up the code in [ICD §4](../../icd/icd-cstack.md#4-errors-and-result-semantics).
- `isError: true` with assessment `tool_error` means the tool refused its arguments; `receipt.error` says which field and why.
- `not_scored` means a check could not be measured: a `null` input, a segment no shot covers, or zero cuts.
- `default rules need bands for [...]` or `default rules need shot metrics [...]`: `cinematic_gate` with `bands` needs `sharp`, `black`, `subject_motion` and `luma`. Supply them or send `rules`.
- `... has no calibrated default; supply thresholds...`: `depth_error` and `identity_similarity` have no default threshold.
- The bridge exits with status 2 if it is given any command-line argument or an oversized line; restart it.
