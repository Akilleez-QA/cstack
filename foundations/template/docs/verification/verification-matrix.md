# Verification matrix

Command: `python -B -m unittest discover -s tests -t .` from the repository root. Baseline: the initial commit on `main`.

| REQ | Method | Evidence | Result |
|---|---|---|---|
| REQ-TPL-001 | T | tests/test_bridge.py | pass at baseline |
| REQ-TPL-002 | T | tests/test_bridge.py | pass at baseline |
| REQ-TPL-003 | T | tests/test_bridge.py | pass at baseline |
| REQ-TPL-004 | T | tests/test_bridge.py | pass at baseline |
| REQ-TPL-005 | T | tests/test_bridge.py | pass at baseline |
| REQ-TPL-006 | I | inspection of source | pass at baseline |
| REQ-TPL-007 | T | tests/test_input_limits.py: InputLimitTests | pass |
