# Verification matrix

Command: `python -B -m unittest discover -s tests -t .` from the repository root. Baseline: the initial commit on `main`.

| REQ | Method | Evidence | Result |
|---|---|---|---|
| REQ-FILM-001 | T | tests/test_tools.py | pass at baseline |
| REQ-FILM-002 | T | tests/test_bridge.py, tests/test_tools.py | pass at baseline |
| REQ-FILM-003 | T | tests/test_bridge.py, tests/test_tools.py | pass at baseline |
| REQ-FILM-004 | T | tests/test_bridge.py, tests/test_tools.py | pass at baseline |
| REQ-FILM-005 | T | tests/test_bridge.py, tests/test_tools.py | pass at baseline |
| REQ-FILM-006 | T | tests/test_bridge.py, tests/test_tools.py | pass at baseline |
| REQ-FILM-007 | T | tests/test_bridge.py | pass at baseline |
| REQ-FILM-008 | I | inspection of foundation_film/tools.py and its tool implementations | pass at baseline |
| REQ-FILM-009 | T | tests/test_bridge.py, tests/test_tools.py | pass at baseline |
| REQ-FILM-010 | T | tests/test_bridge.py | pass at baseline |
| REQ-FILM-011 | I | inspection of source | pass at baseline |
| REQ-FILM-012 | T | tests/test_requirement_limits.py: RequirementLimitsTests.test_req_film_012_input_limits, RequirementLimitsTests.test_req_film_012_stream_frame_limit | pass |
