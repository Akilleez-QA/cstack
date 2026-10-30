"""Fixed test discovery helper; reports the actual interpreter mode."""
from pathlib import Path
import json
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'baseline_snapshot'),str(ROOT)]

def main():
    if len(sys.argv)!=2 or sys.argv[1] not in ('tests','exterior_evidence_packaging_tests'):
        raise ValueError('Fixed validation suite required')
    suite=unittest.defaultTestLoader.discover(str(ROOT/sys.argv[1]))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'status':'passed' if result.wasSuccessful() else 'failed','run':result.testsRun,
                      'skipped':len(result.skipped),'actual_optimization':sys.flags.optimize},sort_keys=True))
    return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
