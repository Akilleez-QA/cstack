"""Independent v0.11 integration review; portable, stdlib-only, -O-safe.

The adapter is NOT an independently implemented verifier. Semantic comparisons
below reuse the separately pinned lab review's independently written BFS model.
The new checks exercise integration boundaries, not theorem truth or proof.
"""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import ast
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'review/claim-revision-lab'))
from oracle import canonical, model, node, event, document, seal
import review as lab_review
from foundation_math import claim_ledger as adapter
from foundation_math_bridge import server
from foundation_math_bridge.schemas import tool_definitions
from foundation_math.domains import domain_handler, DomainError

COUNTS = Counter()
class ReviewFailure(Exception):
    pass

def need(condition, label):
    COUNTS['explicit_checks'] += 1
    if not condition:
        raise ReviewFailure(label)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def js(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')

def flags(receipt):
    need(receipt['schema_version'] == 1, 'receipt version')
    need(receipt['scope'] == 'bounded_dependency_applicability', 'receipt scope')
    for name in ('formal_proof', 'runtime_goal_acceptance', 'proof_accepted'):
        need(receipt[name] is False, 'never promote ' + name)
    need(receipt['truth_assessment'] == 'not_assessed', 'never assess truth')

def successful(receipt, expected, label):
    flags(receipt)
    need(set(receipt) == {'schema_version','scope','formal_proof','runtime_goal_acceptance','proof_accepted','truth_assessment','status','result'}, label + ': exact success fields')
    need(receipt['status'] == 'success', label + ': success')
    need(receipt['result'] == expected, label + ': complete report differs from separate BFS oracle')

def rejected(receipt, code=None):
    flags(receipt)
    need(set(receipt) == {'schema_version','scope','formal_proof','runtime_goal_acceptance','proof_accepted','truth_assessment','status','error'}, 'no partial error result')
    need(receipt['status'] == 'error', 'structured error status')
    need(set(receipt['error']) == {'code','path','message'}, 'typed error fields')
    need(all(type(v) is str for v in receipt['error'].values()), 'error strings')
    if code is not None:
        need(receipt['error']['code'] == code, 'expected rejection ' + code + ', got ' + repr(receipt))

def request(method, params=None, ident=1):
    return {'jsonrpc':'2.0','id':ident,'method':method,'params':{} if params is None else params}

def call(doc, ident=1):
    return request('tools/call', {'name':'replay_claim_applicability','arguments':{'ledger':doc}}, ident)

def ready_bridge():
    b=server.Bridge()
    r=b.handle(js(request('initialize',{'protocolVersion':server.PROTOCOL},0)))
    need(r['result']['mcpCompatible'] is False, 'not MCP')
    return b

def process(args, raw):
    env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')}
    env['PYTHONDONTWRITEBYTECODE']='1'
    return subprocess.run([sys.executable,'-B']+(['-O'] if sys.flags.optimize else [])+args,
        input=raw,cwd=ROOT,env=env,capture_output=True,timeout=60)

def provenance():
    baseline=json.loads((ROOT/'review/V011-BASELINE.json').read_bytes())
    for name,pin in baseline['unchanged_source_pins'].items():
        need(sha((ROOT/name).read_bytes()) == pin, 'unchanged arithmetic/runtime source: '+name)
        COUNTS['unchanged_v010_source_files'] += 1
    for name,pin in baseline['lab_source_pins'].items():
        need(sha((ROOT/name).read_bytes()) == pin, 'accepted lab source: '+name)
        COUNTS['unchanged_lab_source_files'] += 1
    for name,pin in baseline['independent_lab_reviewer_pins'].items():
        need(sha((ROOT/'review/claim-revision-lab'/name).read_bytes()) == pin, 'independent oracle provenance: '+name)
    need(tool_definitions()[:14] == baseline['tools'], 'all prior fourteen complete contracts unchanged')
    need(len(tool_definitions()) == 15, 'exactly one appended tool')
    need(tool_definitions()[14]['name'] == 'replay_claim_applicability', 'appended tool name')
    need(server.TOOL_NAMES == frozenset(t['name'] for t in tool_definitions()), 'dispatch registry exact')
    b=ready_bridge()
    for case in baseline['tool_cases']:
        r=b.handle(js(request('tools/call',{'name':case['name'],'arguments':case['arguments']})))
        need('error' not in r, 'prior tool protocol error: '+case['name'])
        need(r['result'] == case['expected'], 'prior complete tool behavior: '+case['name'])
        COUNTS['prior_tool_full_response_comparisons'] += 1
    definitions=tool_definitions()
    tool=definitions[-1]
    need(tool['readOnly'] is True, 'new tool read-only')
    need(set(tool['inputSchema']['properties']) == {'ledger'}, 'only ledger accepted')
    need(tool['inputSchema']['additionalProperties'] is False, 'closed new arguments schema')
    # Only local JSON references may appear. Schema lookup must not fetch a URL.
    todo=[tool]
    while todo:
        v=todo.pop()
        if type(v) is dict:
            if '$ref' in v:
                need(v['$ref'].startswith('#/$defs/'), 'no external schema reference')
            todo.extend(v.values())
        elif type(v) is list:todo.extend(v)
    definitions[-1]['inputSchema']['properties'].clear()
    need(set(tool_definitions()[-1]['inputSchema']['properties']) == {'ledger'}, 'schema is detached')
    need(server.MAX_FRAME_BYTES == 65536 and server.MAX_OUTPUT_BYTES == 1048576, 'bridge byte caps unchanged')
    need(server.MAX_JSON_DEPTH == 80 and server.MAX_JSON_NODES == 16384 and server.MAX_STRING_CHARS == 4096, 'other bridge limits unchanged')
    for unknown in ('bounded_dependency_applicability','claim_ledger','claim_revision','replay_claim_applicability'):
        try:domain_handler(unknown)
        except DomainError:COUNTS['runtime_registry_rejections'] += 1
        else:raise ReviewFailure('ledger added to runtime acceptance registry')
    return baseline

def semantic_comparisons():
    b=ready_bridge()
    for kind,cases in [('focused',lab_review.valid_cases()),('seeded',lab_review.random_cases()),('exhaustive',lab_review.exhaustive_cases())]:
        for name,doc in cases:
            before=deepcopy(doc)
            expected=model(doc)
            actual=adapter.replay_claim_ledger(doc)
            successful(actual,expected,name)
            need(doc == before,name+': caller input mutated')
            if kind == 'exhaustive':
                COUNTS['bfs_all_labeled_four_node_revision_states' if name.startswith('exhaustive_revision') else 'bfs_all_labeled_four_node_withdrawal_states'] += 1
            else:
                COUNTS['bfs_'+kind+'_adapter_cases'] += 1
                raw=js(call(doc))
                if len(raw) <= 65536:
                    reply=b.handle(raw)
                    need('error' not in reply, name+': bridge protocol error')
                    result=reply['result']
                    need(result['isError'] is False, name+': bridge success')
                    content=result['structuredContent']
                    need(content['assessment'] == 'claim_dependency_applicability_replayed', 'applicability assessment')
                    need(content['formal_proof'] is False and content['runtime_goal_acceptance'] is False, 'bridge no acceptance')
                    successful(content['receipt'],expected,name+': bridge')
                    COUNTS['bfs_'+kind+'_bridge_cases'] += 1
                else:
                    need(b.handle(raw)['error']['code'] == -32002, name+': large frame refused')
                    COUNTS['semantic_inputs_exceeding_bridge_cap'] += 1
            if kind == 'focused':
                shuffled={**doc,'records':list(reversed(doc['records']))}
                successful(adapter.replay_claim_ledger(shuffled),expected,name+': record-order invariant')
                actual['result']['records'].clear()
                successful(adapter.replay_claim_ledger(doc),expected,name+': output mutation isolated')
                COUNTS['metamorphic_and_detachment_cases'] += 1
    for name,doc,code in lab_review.invalid_cases():
        rejected(adapter.replay_claim_ledger(doc),code)
        COUNTS['inherited_adversarial_adapter_cases'] += 1
        raw=js(call(doc))
        if len(raw) <= 65536:
            reply=b.handle(raw)
            if 'result' in reply:
                need(reply['result']['isError'] is True, 'invalid document bridge error: '+name)
                need(reply['result']['structuredContent']['assessment'] == 'tool_error', 'invalid document no assessment')
                rejected(reply['result']['structuredContent']['receipt'],code)
            else:
                # Float/type or depth/budget guards may reject before the core.
                need(reply['error']['code'] in (-32700,-32002), 'explicit pre-core rejection: '+name)
            COUNTS['inherited_adversarial_bridge_cases'] += 1

def strict_ingress():
    b=ready_bridge()
    raw_bad=[b'{"x":1,"x":2}',
             b'{"x":NaN}',b'{"x":Infinity}',b'{"x":1.0}',b'\xff',b'{',b'']
    for raw in raw_bad:
        try:server.decode_frame(raw)
        except server.WireError as e:need(e.code == -32700,'strict malformed rejection')
        else:raise ReviewFailure('bridge decoder accepted malformed Unicode/JSON: '+repr(raw))
        need(b.handle(raw)['error']['code'] == -32700, 'wire structured malformed rejection')
        COUNTS['malformed_wire_rejections'] += 1
    # The inherited transport permits escaped lone surrogates. New ledger
    # content, unlike ping identifiers, must reject them with typed errors.
    for raw_doc in (b'{"\\ud800":1}', b'{"outer":{"\\udfff":1}}', b'{"x":"\\ud800"}'):
        frame=b'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"replay_claim_applicability","arguments":{"ledger":'+raw_doc+b'}}}'
        reply=b.handle(frame)
        need('result' in reply and reply['result']['isError'] is True, 'ledger surrogate typed bridge rejection')
        rejected(reply['result']['structuredContent']['receipt'])
        need(reply['result']['structuredContent']['assessment'] == 'tool_error', 'Unicode does not produce an assessment')
        COUNTS['ledger_unicode_wire_rejections'] += 1
    need(server.decode_frame(b'{"\\ud83d\\ude00":"\\ud83d\\ude00"}') == {'😀':'😀'}, 'valid surrogate pair allowed')
    for val in ({'\ud800':1},{'outer':{'\udfff':1}},{'x':'\ud800'},1.0,(1,2),{1:'x'}):
        rejected(adapter.replay_claim_ledger(val))
        COUNTS['structured_ingress_rejections'] += 1
    doc=document([node('Claim',status='claimed_established')])
    for key,value in [('path','/etc/passwd'),('command','whoami'),('url','https://example.invalid'),('max_records',999),('limits',{}),('accepted',True),('proof',True),('report',{})]:
        args={'ledger':doc,key:value}
        r=b.handle(js(request('tools/call',{'name':'replay_claim_applicability','arguments':args})))
        need(r['error']['code'] == -32602,'reject unsupported bridge field '+key)
        COUNTS['extra_argument_rejections'] += 1
    for args in ({},{'request':doc},{'ledger':doc,'certificate':{}},{'ledger':doc,'formal_proof':True}):
        r=b.handle(js(request('tools/call',{'name':'replay_claim_applicability','arguments':args})))
        need(r['error']['code'] == -32602,'exact ledger envelope')
        COUNTS['extra_argument_rejections'] += 1
    raw=js(call(doc));padding=b' '*(65536-len(raw))
    need('result' in b.handle(raw+padding),'exact frame limit accepted')
    need(b.handle(raw+padding+b' ')['error']['code'] == -32002,'one over frame limit rejected')
    COUNTS['wire_byte_boundaries'] += 2
    # Notifications must never run the new tool, even after initialization.
    notification=call(doc);notification.pop('id')
    with patch.object(server,'replay_claim_ledger',side_effect=ReviewFailure('notification executed backend')):
        need(b.handle(js(notification)) is None,'notification ignored')
    COUNTS['notification_no_work_controls'] += 1
    # Source text and external-looking metadata remain opaque, without file I/O.
    payload=document([node('Opaque',text="__import__('os').system('false'); /etc/passwd; https://example.invalid")])
    expected=model(payload)
    with patch('builtins.open',side_effect=ReviewFailure('adapter file I/O')),patch('os.system',side_effect=ReviewFailure('adapter command')):
        successful(adapter.replay_claim_ledger(payload),expected,'opaque payload')
    COUNTS['opaque_text_no_io_controls'] += 1

def output_boundaries():
    # Real ledger whose report fits the core but not the bridge. Independently
    # generated chain produces many distinct, long propagated witness paths.
    records=[]
    for i in range(40):records.append(node('N'+str(i),dependencies=records[-1:]))
    events=[{**event('withdraw',r,'W'+str(i)),'reason':'r'*1000} for i,r in enumerate(records[:20])]
    doc=document(records,events)
    expected=model(doc)
    need(len(js(call(doc))) < 65536,'large output example fits bridge input')
    need(1048576 < len(js(expected)) < 4194304,'large output example brackets caps')
    successful(adapter.replay_claim_ledger(doc),expected,'large report direct')
    raw=js(request('initialize',{'protocolVersion':server.PROTOCOL},0))+b'\n'+js(call(doc))+b'\n'+js(request('ping',ident=2))+b'\n'
    sink=io.BytesIO();rc=server.serve(io.BytesIO(raw),sink)
    lines=[json.loads(x) for x in sink.getvalue().splitlines()]
    need(rc == 0 and len(lines) == 3,'oversized response session continues')
    need(lines[1]['error']['code'] == -32002 and 'result' not in lines[1], 'oversized response withheld wholly')
    need(lines[2]['result'] == {},'ping after withheld result')
    need(all(len(line) <= 1048576 for line in sink.getvalue().splitlines()),'no oversized emitted frame')
    COUNTS['real_report_output_cap_controls'] += 1
    # The exact legacy frame convention counts JSON payload, excluding newline.
    prefix={'jsonrpc':'2.0','id':4,'result':''}
    prefix['result']='x'*(1048576-len(js(prefix)))
    need(len(server.encode_response(prefix)) == 1048577,'exact output payload boundary')
    prefix['result']+='x'
    need(json.loads(server.encode_response(prefix))['error']['code'] == -32002,'one over output payload withheld')
    COUNTS['wire_output_byte_boundaries'] += 2
    over=b' '*65537+b'\n'+js(request('ping'))+b'\n'
    sink=io.BytesIO();rc=server.serve(io.BytesIO(over),sink)
    need(rc == 2 and len(sink.getvalue().splitlines()) == 1,'oversized input closes without draining')
    COUNTS['oversized_input_session_controls'] += 1

def unicode_amplification_document():
    records=[]
    for i in range(35):records.append(node('N'+str(i),dependencies=records[-1:]))
    events=[{**event('withdraw',r,'W'+str(i)),'reason':'😀'*1000} for i,r in enumerate(records[:15])]
    return document(records,events)

def call_cli_locally(module, doc, args=None):
    class BoundedReader(io.BytesIO):
        def read(self, n=-1):
            need(n == 262145,'CLI must read only fixed input budget plus one')
            return super().read(n)
    output=io.StringIO()
    with patch.object(module.sys,'stdin',types.SimpleNamespace(buffer=BoundedReader(canonical(doc)))),patch.object(module.sys,'stdout',output):
        status=module.claim_ledger_cli(['claim-ledger-replay'] if args is None else args)
    return status,json.loads(output.getvalue())

def cli_checks():
    focused=dict(lab_review.valid_cases())
    for name in ('unchecked_objection_not_truth','explicit_repin_all','stale_does_not_inherit_replacement','authored_status_claimed_established','unicode_is_not_normalized'):
        doc=focused[name]
        p=process(['-m','foundation_math','claim-ledger-replay'],canonical(doc))
        need(p.returncode == 0 and not p.stderr,name+': CLI success')
        successful(json.loads(p.stdout),model(doc),name+': CLI')
        COUNTS['cli_full_bfs_comparisons'] += 1
    invalid=[b'{"\\ud800":1}',b'{"nested":{"\\udfff":1}}',b'{"x":NaN}',b'{"x":1,"x":2}',b'{',b' '*262145]
    for raw in invalid:
        p=process(['-m','foundation_math','claim-ledger-replay'],raw)
        need(p.returncode == 2 and not p.stderr,'CLI typed reject '+repr(raw[:30]))
        rejected(json.loads(p.stdout))
        COUNTS['cli_raw_rejections'] += 1
    for extra in ('/etc/passwd','--max-bytes=999999','--output','--help'):
        p=process(['-m','foundation_math','claim-ledger-replay',extra],b'')
        need(p.returncode == 2 and not p.stderr,'CLI argument rejection')
        rejected(json.loads(p.stdout),'arguments')
        COUNTS['cli_argument_rejections'] += 1
    doc=document([node('Boundary')]);raw=canonical(doc)
    p=process(['-m','foundation_math','claim-ledger-replay'],raw+b' '*(262144-len(raw)))
    need(p.returncode == 0 and not p.stderr,'CLI exact byte bound')
    successful(json.loads(p.stdout),model(doc),'CLI exact byte bound')
    p=process(['-m','foundation_math','claim-ledger-replay'],raw+b' '*(262145-len(raw)))
    need(p.returncode == 2 and not p.stderr,'CLI over byte bound')
    rejected(json.loads(p.stdout),'budget_exceeded')
    COUNTS['cli_byte_boundaries'] += 2
    amplification=unicode_amplification_document()
    expected=model(amplification)
    need(len(canonical(amplification)) < 262144 and len(canonical(expected)) < 4194304 < len(js(expected)), 'Unicode envelope amplification fixture bounds')
    status,receipt=call_cli_locally(adapter,amplification)
    need(status == 2, 'CLI complete ASCII envelope cap exit')
    rejected(receipt,'budget_exceeded')
    COUNTS['cli_complete_envelope_budget_controls'] += 1

def static_audit():
    baseline=json.loads((ROOT/'review/V011-BASELINE.json').read_bytes())
    # Remove only the explicitly appended route, branch and registry entry. The
    # remaining executable AST must equal frozen v0.10, including old CLI routes.
    class RemoveAppendOnlyIntegration(ast.NodeTransformer):
        def visit_ImportFrom(self, n):
            if n.module == 'foundation_math.claim_ledger':return None
            return n
        def visit_If(self, n):
            if isinstance(n.test,ast.BoolOp) and any(isinstance(x,ast.Compare) and any(isinstance(c,ast.Constant) and c.value == 'claim-ledger-replay' for c in x.comparators) for x in n.test.values):
                return None
            if isinstance(n.test,ast.Compare) and any(isinstance(c,ast.Constant) and c.value == 'replay_claim_applicability' for c in n.test.comparators):
                return [self.visit(x) for x in n.orelse]
            return self.generic_visit(n)
        def visit_Expr(self, n):
            if isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and n.value.func.attr == 'add_parser' and n.value.args and isinstance(n.value.args[0],ast.Constant) and n.value.args[0].value == 'claim-ledger-replay':
                return None
            return self.generic_visit(n)
        def visit_Tuple(self,n):
            n.elts=[self.visit(x) for x in n.elts if not (isinstance(x,ast.Constant) and x.value == 'replay_claim_applicability')]
            return n
    for name,expected in [('foundation_math/cli.py','cli_ast_sha256'),('foundation_math_bridge/server.py','bridge_server_ast_sha256')]:
        tree=RemoveAppendOnlyIntegration().visit(ast.parse((ROOT/name).read_text()))
        need(sha(ast.dump(tree,include_attributes=False).encode()) == baseline[expected], 'append-only executable AST: '+name)
        COUNTS['append_only_ast_checks'] += 1
    source=(ROOT/'foundation_math/claim_ledger.py').read_text()
    tree=ast.parse(source)
    imports=set()
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):imports.update(x.name for x in n.names)
        if isinstance(n,ast.ImportFrom):imports.add(n.module)
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name):
            need(n.func.id not in ('eval','exec','compile','open','input','__import__'),'adapter no dynamic execution/file open')
    need(imports <= {'json','sys','claim_revision','claim_revision.core'},'adapter import surface closed')
    pure=ast.parse((ROOT/'claim_revision/core.py').read_text())
    for n in ast.walk(pure):
        if isinstance(n,ast.Import):need(all(x.name in ('json','hashlib','re') for x in n.names),'pure core import safety')
        if isinstance(n,ast.ImportFrom):need(n.module in ('__future__','collections','typing'),'pure core import safety')
    COUNTS['source_io_boundary_audits'] += 1
    pins_path=ROOT/'review/V011-REVIEW-PINS.json'
    need(pins_path.is_file(),'review pins are required')
    for name,pin in json.loads(pins_path.read_text()).items():
        need(sha((ROOT/name).read_bytes()) == pin,'reviewed source pin: '+name)
    COUNTS['review_pin_file_verified'] += 1

def source_mutation_controls():
    source=(ROOT/'foundation_math/claim_ledger.py').read_text()
    simple=document([node('Unproved',status='claimed_established')])
    cases=[
        ('promote_formal_proof', "'formal_proof': False", "'formal_proof': True", 'valid'),
        ('promote_runtime_goal', "'runtime_goal_acceptance': False", "'runtime_goal_acceptance': True", 'valid'),
        ('promote_proof_accepted', "'proof_accepted': False", "'proof_accepted': True", 'valid'),
        ('assert_truth', "'truth_assessment': 'not_assessed'", "'truth_assessment': 'true'", 'valid'),
        ('return_input_as_report', "'result': replay(document)", "'result': document", 'valid'),
        ('turn_rejection_into_success', "return ledger_error_receipt(error)", "return {**_common(), 'status': 'success', 'result': {}}", 'invalid'),
        ('unbounded_stdin_read', 'read(MAX_INPUT_BYTES + 1)', 'read()', 'bounded_read'),
        ('allow_cli_path_arguments', "if argv != ['claim-ledger-replay']:", 'if False:', 'arguments'),
        ('omit_cli_envelope_cap', "if len(output.encode('ascii')) > MAX_OUTPUT_BYTES:", 'if False:', 'output_cap'),
    ]
    rows=[]
    for name,before,after,test in cases:
        need(source.count(before) == 1,'unique mutation anchor '+name)
        module=types.ModuleType('integration_mutant_'+name)
        exec(compile(source.replace(before,after),'<review integration mutant '+name+'>','exec'),module.__dict__)
        try:
            if test == 'valid':successful(module.replay_claim_ledger(simple),model(simple),'mutant '+name)
            elif test == 'invalid':rejected(module.replay_claim_ledger({'bad':1}))
            elif test == 'bounded_read':
                status,r=call_cli_locally(module,simple)
                need(status == 0,'normal bounded CLI');successful(r,model(simple),name)
            elif test == 'arguments':
                status,r=call_cli_locally(module,simple,['claim-ledger-replay','/etc/passwd'])
                need(status == 2,'no CLI paths');rejected(r,'arguments')
            elif test == 'output_cap':
                status,r=call_cli_locally(module,unicode_amplification_document())
                need(status == 2,'complete CLI envelope budget');rejected(r,'budget_exceeded')
        except ReviewFailure as e:
            rows.append({'mutant':name,'killed_by_explicit_guard_or_comparison':True,'finding':str(e)})
        except Exception as e:
            raise ReviewFailure('Mutation crashed instead of semantic rejection: '+name+': '+type(e).__name__) from e
        else:raise ReviewFailure('Surviving integration mutation: '+name)
    COUNTS['integration_mutations_killed'] += len(rows)
    return rows

def main():
    baseline=provenance()
    semantic_comparisons()
    strict_ingress()
    output_boundaries()
    cli_checks()
    static_audit()
    mutations=source_mutation_controls()
    return {'status':'PASS','python_optimized':bool(sys.flags.optimize),'counts':dict(COUNTS),'integration_mutations':mutations,
        'oracle':'Separately pinned accepted-lab reviewer BFS implementation, reused as explicit independent review evidence; adapter replay is NOT independent verification.',
        'baseline_source_manifest_sha256':baseline['baseline_source_manifest_sha256'],
        'accepted_lab_archive_sha256':baseline['lab_archive_sha256'],
        'scope':'Synthetic local integration, strict ingress, compatibility, bounded blocker accounting and non-promotion only. No truth judgment, proof acceptance, actual HM data, network, models or Lean.'}

if __name__ == '__main__':
    print(json.dumps(main(),indent=2,sort_keys=True))
