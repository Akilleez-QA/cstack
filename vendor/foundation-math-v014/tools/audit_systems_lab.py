#!/usr/bin/env python3
"""Deterministic synthetic corruption and independent minor-oracle audit."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from test_systems import independent_check, spec
from exact_systems.api import handle_request
from exact_systems.producer import produce


def scalar_paths(obj, prefix=()):
    if type(obj) is dict:
        for key,value in obj.items():
            yield from scalar_paths(value,prefix+(key,))
    elif type(obj) is list:
        for index,value in enumerate(obj):
            yield from scalar_paths(value,prefix+(index,))
    elif type(obj) is int:
        yield prefix


def mutate(obj,path):
    result=deepcopy(obj);current=result
    for key in path[:-1]:current=current[key]
    current[path[-1]]+=1
    return result


def main() -> int:
    # The selected systems include unique, affine, inconsistent and zero-shaped
    # cases. No external problem data is read by this audit.
    systems=[spec([[2,1],[1,1]],[1,2]),
             spec([[2,1,1],[1,1,0],[3,2,1]],[1,2,3]),
             spec([[1,2],[2,4]],[1,3]),
             spec([[0,0],[0,0]],[0,0]),
             spec([[0,0],[0,0]],[0,1]),
             spec([],[],cols=3),spec([[],[]],[0,0],cols=0),
             spec([[],[]],[0,2],cols=0),spec([],[],cols=0),
             spec([[{'num':1,'den':2},{'num':1,'den':3}]],
                  [{'num':1,'den':7}],domain='Q')]
    test=unittest.TestCase()
    total,rejected,accepted_valid=0,0,0
    valid_changes=[]
    binding_total=0
    for number,system in enumerate(systems):
        certificate=produce(system)
        for path in scalar_paths(certificate):
            changed=mutate(certificate,path)
            result=handle_request({'operation':'verify','system':system,'certificate':changed})
            total+=1
            if not result['ok']:
                rejected+=1
                continue
            # Some witness/solution changes genuinely remain mathematically
            # valid (e.g. any x for A=0). Never label those rejection failures.
            independent_check(test,system,result)
            accepted_valid+=1
            valid_changes.append({'case':number,'path':list(path)})
        for path in scalar_paths(system):
            changed=mutate(system,path)
            result=handle_request({'operation':'verify','system':changed,'certificate':certificate})
            test.assertFalse(result['ok'], (number,path,result))
            binding_total+=1
    report={'passed':True,'synthetic_cases':len(systems),
            'numeric_leaf_certificate_mutations':total,
            'rejected_certificate_mutations':rejected,
            'accepted_mathematically_valid_mutations':accepted_valid,
            'accepted_valid_changes':valid_changes,
            'changed_external_system_mutations_rejected':binding_total,
            'oracle':'Leibniz-minor rank and direct rational product checks, no elimination',
            'formal_proof':False}
    print(json.dumps(report,indent=2,sort_keys=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
