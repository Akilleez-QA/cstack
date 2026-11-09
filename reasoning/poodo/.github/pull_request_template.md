<!-- Peer-review record (SWEHB 5.03 tailored). -->

## Problem and resulting behavior

Describe the concrete trigger and what changes. Link issues: Fixes #, Refs #.

## Requirements, design and interface impact

- Requirements added, changed or deleted (REQ-PO-###):
- SDD, ICD or data dictionary updated: yes / no / not needed
- Verification matrix updated: yes / not needed

## Evidence and verification

List checks run at the head commit, their outcomes, and remaining limitations. For method changes, link the frozen evaluation configuration and results, or mark behavioral effects unmeasured.

- [ ] `python scripts/validate_skill.py`
- [ ] `python -m unittest discover -s evals -p 'test_*.py' -v`
- [ ] `python scripts/check_capsule.py evals/fixtures/valid-capsule.yaml`
- [ ] `python tools/check_trace.py`
- [ ] `python -m unittest discover -s tools -p 'test_*.py' -v`

## Peer review record

- Reviewers: <!-- human approver; agent reviewers (agent review is not independent) -->
- Review type: code / docs / requirements / design
- Findings: <!-- count by severity; list or link resolved threads -->
- Outcome: approved / changes requested / re-review

## Documentation checklist

<!-- For a docs PR, paste docs/rules/documentation-checklist.md here and tick it. For a code PR, tick the line below. -->

- [ ] Docs whose derivation paths this PR touches are updated or confirmed still accurate.
