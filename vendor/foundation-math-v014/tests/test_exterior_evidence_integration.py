"""New adapter boundaries, formal interpretation and coherent wire budgets."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from foundation_math.exterior import calculate_exterior, check_exterior_certificate, exterior_cli
from foundation_math.validation_evidence import plan_validation_evidence, validation_evidence_cli
from foundation_math_bridge.schemas import tool_definitions
from foundation_math_bridge.server import Bridge, PROTOCOL, MAX_FRAME_BYTES, MAX_OUTPUT_BYTES, decode_frame, encode_response, WireError
from validation_receipt import plan, seal, pin

ROOT=Path(__file__).resolve().parents[1]
CALC='calculate_formal_exterior';CHECK='check_formal_exterior_certificate';PLAN='plan_validation_evidence'

def fixture(name='stronger-exterior-test'):
    return json.loads((ROOT/'examples/exterior-power'/(name+'.request.json')).read_text())

def document(name='all-pins-match'):
    return json.loads((ROOT/'examples/validation-evidence'/(name+'.input.json')).read_text())

def frame(name,args,identifier=1):
    return {'jsonrpc':'2.0','id':identifier,'method':'tools/call','params':{'name':name,'arguments':args}}

def wire(value):
    return json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':')).encode('ascii')

def bridge():
    b=Bridge();b.dispatch({'jsonrpc':'2.0','id':0,'method':'initialize','params':{'protocolVersion':PROTOCOL}});return b

class ExteriorEvidenceTests(unittest.TestCase):
    def test_sixteen_old_complete_contracts(self):
        old=json.loads((ROOT/'docs/BASE-V013-BRIDGE-TOOLS.json').read_text())['tools'];new=tool_definitions()
        self.assertEqual(len(new),19);self.assertEqual(new[:16],old)
        self.assertEqual([x['name'] for x in new[16:]],[CALC,CHECK,PLAN])
        new[16]['inputSchema'].clear();self.assertTrue(tool_definitions()[16]['inputSchema'])

    def test_all_fourteen_exterior_examples_exact(self):
        paths=list((ROOT/'examples/exterior-power').glob('*.request.json'));self.assertEqual(len(paths),14)
        for p in paths:
            req=json.loads(p.read_text());certificate=json.loads(p.with_name(p.name.replace('.request.','.certificate.')).read_text())
            result=calculate_exterior(req);self.assertEqual(result['status'],'success',p.name)
            self.assertEqual(result['result']['certificate'],certificate)
            self.assertEqual(check_exterior_certificate(req,certificate)['status'],'success')

    def test_illustration_only_t6_not_all_twists(self):
        req=fixture();req['orders']=[1,2];req['twists']=[1,6]
        rows=calculate_exterior(req)['result']['certificate']['result']['comparisons'];by={(x['order'],x['twist']):x for x in rows}
        self.assertEqual(by[1,6]['target_minus_source'],{})
        self.assertEqual(by[2,6]['target_minus_source'],{'D':1,'P':-1,'1':-1})
        self.assertEqual(by[1,1]['target_minus_source'],{'W':1,'Wp':1,'S4':-1})
        self.assertEqual(by[1,1]['multiplicity_test'],'obstructed')

    def test_twist_after_wedge(self):
        req={'schema':'fm-exterior-request-v1','operation':'wedge_h0_comparison','source':[],
             'target':[{'irrep':'1','twist':-1,'multiplicity':2}],'orders':[2],'twists':[2]}
        row=calculate_exterior(req)['result']['certificate']['result']['comparisons'][0]
        self.assertEqual(row['target_h0']['dimension'],1) # O(-2)(2), not wedge2(O(-1)(2)^2)=O(2).

    def test_nonclaims_success_and_error(self):
        for receipt in [calculate_exterior(fixture()),calculate_exterior({}),check_exterior_certificate(fixture(),{}),plan_validation_evidence(document()),plan_validation_evidence({})]:
            self.assertIs(receipt['formal_proof'],False);self.assertIs(receipt['runtime_goal_acceptance'],False)
        for name in ('all-pins-match','mandatory-fresh-policy','unknown-environment-chain'):
            result=plan_validation_evidence(document(name))['result']
            for k in ('execution_performed','fresh_pass_claimed','skip_authorized','closure_verified','artifact_bytes_verified','authenticity_verified','mathematical_truth_checked','proof_acceptance_changed'):
                self.assertIs(result[k],False)

    def test_exact_prior_planner_reports(self):
        paths=list((ROOT/'examples/validation-evidence').glob('*.input.json'));self.assertEqual(len(paths),7)
        for path in paths:
            doc=json.loads(path.read_text());expected=json.loads(path.with_name(path.name.replace('.input.','.expected.')).read_text())
            self.assertEqual(plan_validation_evidence(doc)['result'],expected)

    def test_planner_no_execute_or_skip(self):
        doc=document();doc['tasks'][0]['content']['invocation']['argv']=['touch','never-created']
        body={k:v for k,v in doc['tasks'][0].items() if k!='revision_sha256'};doc['tasks'][0]=seal(body)
        # stale selections are blockers, not execution requests.
        with tempfile.TemporaryDirectory() as td:
            previous=Path.cwd()
            try:
                os.chdir(td);result=plan_validation_evidence(doc)
                self.assertEqual(result['status'],'success');self.assertFalse(Path('never-created').exists())
                self.assertFalse(result['result']['execution_performed']);self.assertFalse(result['result']['skip_authorized'])
            finally:os.chdir(previous)

    def test_mandatory_roles_fresh(self):
        result=plan(document('mandatory-fresh-policy'))
        tasks={x['id']:x for x in document('mandatory-fresh-policy')['tasks']}
        for row in result['tasks']:
            if tasks[row['task']['id']]['content']['role']!='historical_component':
                self.assertEqual(row['classification'],'MUST_RUN_FRESH')

    def test_exterior_original_request_binding(self):
        req=fixture();cert=calculate_exterior(req)['result']['certificate'];changed=copy.deepcopy(req);changed['twists']=[1]
        self.assertEqual(check_exterior_certificate(changed,cert)['status'],'error')
        for key in ('scope','catalog_sha256','request_sha256'):
            bad=copy.deepcopy(cert);bad[key]='false';self.assertEqual(check_exterior_certificate(req,bad)['status'],'error')
        bad=copy.deepcopy(cert);bad['result']['comparisons'][0]['multiplicity_test']='obstructed'
        self.assertEqual(check_exterior_certificate(req,bad)['status'],'error')

    def test_physical_labels_rank_order_and_twist_reject(self):
        req={'schema':'fm-exterior-request-v1','operation':'representation','representation':{'W':1},'orders':[1]}
        for bad in [dict(req,representation={'unknown':1}),dict(req,representation={'W':13}),dict(req,orders=[26]),dict(req,orders=[1,1]),dict(req,orders=[True]),dict(req,representation={'W':-1}),dict(req,actual_map=True),dict(req,proof=True)]:
            self.assertEqual(calculate_exterior(bad)['status'],'error')
        bad=fixture();bad['twists']=[17];self.assertEqual(calculate_exterior(bad)['status'],'error')

    def test_bridge_happy_roundtrip(self):
        req=fixture();b=bridge();out=b.handle(wire(frame(CALC,{'request':req})))
        certificate=out['result']['structuredContent']['receipt']['result']['certificate']
        for identifier in (1,'x'*128,'\uffff'*128,'\U0010ffff'*128,9007199254740991):
            raw=wire(frame(CHECK,{'request':req,'certificate':certificate},identifier))
            self.assertLessEqual(len(raw),MAX_FRAME_BYTES)
            self.assertFalse(b.handle(raw)['result']['isError'])

    def test_natural_oversized_certificate_withheld_but_standalone_allowed(self):
        req={'schema':'fm-exterior-request-v1','operation':'bundle',
             'bundle':[{'irrep':'1','twist':d,'multiplicity':2} for d in range(-6,6)],'orders':[10,11,12,13]}
        standalone=calculate_exterior(req);self.assertEqual(standalone['status'],'success')
        cert=standalone['result']['certificate'];self.assertGreater(len(wire(frame(CHECK,{'request':req,'certificate':cert},'\U0010ffff'*128))),MAX_FRAME_BYTES)
        out=bridge().dispatch(frame(CALC,{'request':req}));self.assertEqual(out['error']['code'],-32002);self.assertNotIn('result',out)
        out=bridge().dispatch(frame(CHECK,{'request':req,'certificate':cert}));self.assertEqual(out['error']['code'],-32002)

    def test_natural_astral_id_roundtrip_boundary_withheld(self):
        # Independent review's naturally admissible standalone certificate.
        req={'schema':'fm-exterior-request-v1','operation':'bundle',
             'bundle':[{'irrep':'1','twist':d,'multiplicity':1} for d in range(-6,6)],
             'orders':[1,2,3,4,5,6,7,9,10]}
        receipt=calculate_exterior(req);self.assertEqual(receipt['status'],'success')
        cert=receipt['result']['certificate']
        bmp=wire(frame(CHECK,{'request':req,'certificate':cert},'\uffff'*128))
        astral=wire(frame(CHECK,{'request':req,'certificate':cert},'\U0010ffff'*128))
        self.assertEqual((len(bmp),len(astral)),(65463,66231))
        self.assertLessEqual(len(bmp),MAX_FRAME_BYTES);self.assertGreater(len(astral),MAX_FRAME_BYTES)
        response=bridge().dispatch(frame(CALC,{'request':req}))
        self.assertEqual(response['error']['code'],-32002);self.assertNotIn('result',response)

    def test_exact_envelope_byte_budget(self):
        self.assertEqual(MAX_FRAME_BYTES,65536);self.assertEqual(MAX_OUTPUT_BYTES,1048576)
        raw=wire(frame(PLAN,{'document':document()}));raw+=b' '*(65536-len(raw))
        self.assertIn('result',bridge().handle(raw));self.assertEqual(bridge().handle(raw+b' ')['error']['code'],-32002)

    def test_roundtrip_reserves_twelve_ascii_bytes_per_id_character(self):
        from foundation_math_bridge.server import _exterior_roundtrip
        recorded=[]
        def inspect(raw):
            recorded.append(raw);return decode_frame(raw)
        with patch('foundation_math_bridge.server.decode_frame',side_effect=inspect):
            _exterior_roundtrip({}, {})
        value=json.loads(recorded[0]);self.assertEqual(value['id'],'\U0010ffff'*128)
        self.assertEqual(len(wire(value['id']))-2,12*128)

    def test_roundtrip_node_guard_not_just_bytes(self):
        from foundation_math_bridge.server import _exterior_roundtrip
        with patch('foundation_math_bridge.server.MAX_JSON_NODES',10):
            with self.assertRaises(WireError):_exterior_roundtrip({}, {'x':[0]*20})

    def test_unknown_transport_fields_reject(self):
        for name,args in [(CALC,{'request':fixture()}),(CHECK,{'request':fixture(),'certificate':{}}),(PLAN,{'document':document()})]:
            for key in ('command','path','url','code','limits','execute','skip','proof'):
                out=bridge().dispatch(frame(name,dict(args,**{key:'x'})));self.assertEqual(out['error']['code'],-32602)

    def test_notifications_do_not_compute(self):
        for name,args,target in [(CALC,{'request':fixture()},'calculate_exterior'),(CHECK,{'request':fixture(),'certificate':{}},'check_exterior_certificate'),(PLAN,{'document':document()},'plan_validation_evidence')]:
            req=frame(name,args);del req['id']
            with patch('foundation_math_bridge.server.'+target,side_effect=RuntimeError('must not run')) as mock:
                self.assertIsNone(bridge().dispatch(req));mock.assert_not_called()

    def test_json_rejections(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":1.0}',b'{"a":NaN}',b'\xff',b'['*81+b']'*81):
            self.assertIn('error',bridge().handle(raw))
        cycle={};cycle['x']=cycle
        self.assertEqual(calculate_exterior(cycle)['status'],'error');self.assertEqual(plan_validation_evidence(cycle)['status'],'error')

    def test_unexpected_failure_does_not_leak(self):
        with patch('foundation_math_bridge.server.plan_validation_evidence',side_effect=RuntimeError('private-file')):
            out=bridge().dispatch(frame(PLAN,{'document':document()}))
        self.assertEqual(out['error']['code'],-32603);self.assertNotIn('private-file',str(out))

    def test_verifier_does_not_import_producer(self):
        req=fixture();cert=calculate_exterior(req)['result']['certificate']
        code='import sys,json;from foundation_math.exterior import check_exterior_certificate;r,c=json.load(sys.stdin);out=check_exterior_certificate(r,c);print(json.dumps({"result":out,"producer":"exterior_power.producer" in sys.modules,"fusion":"exterior_power.fusion" in sys.modules}))'
        p=subprocess.run([sys.executable,'-B','-c',code],input=json.dumps([req,cert]),cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(p.returncode,0);out=json.loads(p.stdout);self.assertEqual(out['result']['status'],'success');self.assertFalse(out['producer']);self.assertFalse(out['fusion'])

    def test_cli_both_actual_modes_and_usage(self):
        for opt in (0,1):
            env={**os.environ,'PYTHONOPTIMIZE':'0','PYTHONDONTWRITEBYTECODE':'1'}
            flags=['-B']+(['-O'] if opt else [])
            for args,data,expected in [(['exterior-calculate','examples/exterior-power/irrep-W.request.json'],b'',0),(['exterior-check','examples/exterior-power/irrep-W.request.json','examples/exterior-power/irrep-W.certificate.json'],b'',0),(['exterior-calculate'],b'',2),(['validation-evidence-plan'],wire(document()),0),(['validation-evidence-plan','--execute'],wire(document()),2),(['validation-evidence-plan'],b'{"a":1,"a":2}',2)]:
                p=subprocess.run([sys.executable,*flags,'-m','foundation_math',*args],input=data,cwd=ROOT,env=env,capture_output=True)
                self.assertEqual(p.returncode,expected,p.stdout+p.stderr);self.assertEqual(p.stderr,b'');out=json.loads(p.stdout)
                self.assertIs(out['runtime_goal_acceptance'],False)

    def test_cli_input_limit_and_whole_output_limit(self):
        raw=wire(document())
        for size,expected in [(262144,0),(262145,2)]:
            inp=type('Input',(),{'buffer':io.BytesIO(raw+b' '*(size-len(raw)))})()
            out=io.StringIO()
            with patch('foundation_math.validation_evidence.sys.stdin',inp),patch('foundation_math.validation_evidence.sys.stdout',out):
                self.assertEqual(validation_evidence_cli(['validation-evidence-plan']),expected)
        inp=type('Input',(),{'buffer':io.BytesIO(raw)})();out=io.StringIO()
        with patch('foundation_math.validation_evidence.sys.stdin',inp),patch('foundation_math.validation_evidence.sys.stdout',out),patch('foundation_math.validation_evidence.MAX_OUTPUT_BYTES',10):
            self.assertEqual(validation_evidence_cli(['validation-evidence-plan']),2)
        self.assertNotIn('result',json.loads(out.getvalue()))
        out=io.StringIO()
        with patch('foundation_math.exterior.sys.stdout',out),patch('foundation_math.exterior.MAX_OUTPUT_BYTES',10):
            self.assertEqual(exterior_cli(['exterior-calculate',str(ROOT/'examples/exterior-power/irrep-W.request.json')]),2)
        self.assertNotIn('result',json.loads(out.getvalue()))

    def test_strict_schemas_scope_and_extension_mutations(self):
        try:from jsonschema import Draft202012Validator
        except ImportError:self.skipTest("Optional preinstalled jsonschema unavailable; no installation")
        req=fixture();cert=calculate_exterior(req)['result']['certificate']
        for definition,args in zip(tool_definitions()[16:],[{'request':req},{'request':req,'certificate':cert},{'document':document()}]):
            iv=Draft202012Validator(definition['inputSchema']);ov=Draft202012Validator(definition['outputSchema'])
            for schema in (definition['inputSchema'],definition['outputSchema']):Draft202012Validator.check_schema(schema)
            iv.validate(args);self.assertTrue(list(iv.iter_errors(dict(args,extra=True))))
            response=bridge().dispatch(frame(definition['name'],args))['result']['structuredContent'];ov.validate(response)
            for at in ([],['receipt']):
                for key in ('formal_proof','runtime_goal_acceptance'):
                    bad=copy.deepcopy(response);target=bad
                    for part in at:target=target[part]
                    target[key]=True;self.assertTrue(list(ov.iter_errors(bad)))
            bad=copy.deepcopy(response);bad['receipt']['unrequested_claim']=True;self.assertTrue(list(ov.iter_errors(bad)))
            bad=copy.deepcopy(response);bad['assessment']='tool_error';self.assertTrue(list(ov.iter_errors(bad)))
        ov=Draft202012Validator(tool_definitions()[18]['outputSchema'])
        response=bridge().dispatch(frame(PLAN,{'document':document()}))['result']['structuredContent']
        for key in ('execution_performed','fresh_pass_claimed','skip_authorized','closure_verified','artifact_bytes_verified','authenticity_verified','mathematical_truth_checked','proof_acceptance_changed'):
            bad=copy.deepcopy(response);bad['receipt']['result'][key]=True;self.assertTrue(list(ov.iter_errors(bad)))

    def test_detached_and_no_accepted_runtime_domain(self):
        from foundation_math.domains import _DOMAINS
        req=fixture();before=copy.deepcopy(req);out=calculate_exterior(req);out['result']['certificate']['request']['orders'].clear()
        self.assertEqual(req,before)
        self.assertFalse(any('exterior' in str(k) or 'evidence' in str(k) for k in _DOMAINS))

if __name__=='__main__':unittest.main()
