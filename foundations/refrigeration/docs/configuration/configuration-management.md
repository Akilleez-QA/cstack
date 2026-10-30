# Configuration management

- Versioning: SemVer. Current version 0.1.0, recorded in `SOURCE-MANIFEST.json`.
- Baseline: the initial commit on `main`.
- Change control: pull requests only, one concern, about 400 changed lines. Refrigeration.AI merges after checking the head SHA. Branches are kept.
- Pins: after any change run `python -B tools/build_manifest.py` and commit the new `SOURCE-MANIFEST.json`. Consumers repin from its output.
- Releases and tags: none yet. A tag is created only with owner approval.
- Secret scanning: gitleaks and trufflehog run before every push.
