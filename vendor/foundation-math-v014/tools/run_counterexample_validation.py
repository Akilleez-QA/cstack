#!/usr/bin/env python3
"""Run normal/-O tests and the independently implemented bounded oracle."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def sources():
    return {str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest()
            for path in sorted(ROOT.rglob('*'))
            if path.is_file() and 'evidence' not in path.relative_to(ROOT).parts
            and '__pycache__' not in path.parts and path.name != 'SOURCE-MANIFEST.json'}


def main():
    before = sources()
    destination = ROOT / 'evidence'
    destination.mkdir(exist_ok=True)
    runs = []
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for optimized in (False, True):
        flag = ['-O'] if optimized else []
        name = 'optimized' if optimized else 'normal'
        command = [sys.executable, *flag, '-m', 'unittest', 'discover', '-s', 'tests', '-v']
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=180, check=False)
        log = result.stdout + result.stderr
        (destination / f'unit-tests-{name}.txt').write_text(log, encoding='utf-8')
        count = re.search(r'Ran (\d+) tests?', log)
        skipped = re.search(r'OK \(skipped=(\d+)\)', log)
        runs.append({'kind':'unit_tests','optimized':optimized,'command':command,
                     'exit_code':result.returncode,'tests_run':int(count.group(1)) if count else None,
                     'skipped':int(skipped.group(1)) if skipped else 0,
                     'passed':result.returncode == 0 and count is not None,
                     'log':f'evidence/unit-tests-{name}.txt'})
        output = f'evidence/independent-audit-{name}.json'
        command = [sys.executable, *flag, 'tools/independent_audit.py', '--output', output]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=180, check=False)
        audit = json.loads((ROOT / output).read_text()) if (ROOT / output).exists() else {}
        runs.append({'kind':'independent_oracle','optimized':optimized,'command':command,
                     'exit_code':result.returncode,'passed':result.returncode == 0 and audit.get('status') == 'pass',
                     'counters':audit.get('counters'),'report':output})
    stable = before == sources()
    report = {'schema_version':'1.0','kind':'bounded_counterexample_validation','python_version':platform.python_version(),
              'status':'pass' if stable and all(run['passed'] for run in runs) else 'fail',
              'source_snapshot_stable':stable,'source_sha256':before,'runs':runs,
              'scope':'Executed bounded software tests, not a universal theorem or independently verified proof kernel.'}
    (destination/'validation.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':report['status'],'source_snapshot_stable':stable,'runs':runs},indent=2))
    return 0 if report['status']=='pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
