"""Pinned v0.14 inputs and exact v0.13 reconstruction; integrity is not authentication."""
from contextlib import contextmanager
from pathlib import Path
import io
import os
import tempfile
import zipfile

from baseline_snapshot import snapshot as s
from tools.hypothesis_scope_release_support import source_fd, read, require

BASE_MANIFEST_PIN = 'e2d034b8703bd1c98c847962627fbfd2f86c695ecc19dab83c596873f2de7de8'
BASE_ZIP_PIN = '2d3098ecc24fc34c9e0e9df740a7fae4a2e10d83f16086b8ab89c1b553113bda'
BASE_ZIP_BYTES = 5979419
RECIPE_PIN = 'e67eaa66f4f6484ca81ab1fddb313613d170bc0664e51cb315b8a39c5efc5453'
ALLOWED_BASE_CHANGES = frozenset(['README.md','RELEASE-FILES.json','foundation_math/cli.py',
    'foundation_math_bridge/__init__.py','foundation_math_bridge/schemas.py','foundation_math_bridge/server.py',
    'tests/test_agent_bridge.py','tests/test_character_ring_integration.py','tests/test_claim_revision_integration.py',
    'tests/test_hypothesis_scope_integration.py','tests/test_linear_algebra_bridge.py','tests/test_linear_systems_integration.py',
    'tests/test_portable_validation.py','tests/test_split_bundle_integration.py'])
SNAPSHOT = 'snapshots/v013'
LABS = {
    'exterior': {'archive':'vendor/exterior-power-lab.zip','manifest':'docs/EXTERIOR-LAB-SOURCE-MANIFEST.json',
      'archive_sha256':'a6c32c393e7ebc61af34ec50d1793f6905b85c4d0043847152fc22a79c59eb67',
      'manifest_sha256':'89264e3f2d6dd2391f80bf5a1d07292a3748166bef9c60d9ab9f82c3c34d078e',
      'archive_bytes':371086,'package':'exterior_power','examples':'examples/exterior-power','docs_prefix':'EXTERIOR-LAB-'},
    'receipt': {'archive':'vendor/validation-receipt-lab.zip','manifest':'docs/RECEIPT-LAB-SOURCE-MANIFEST.json',
      'archive_sha256':'5edf69aab764b000aca6b24c8503e277e85abe617cbc17b61b13d74796e575b0',
      'manifest_sha256':'87e9ebc74819e201513887908b67e8e4b717bf90702e64cab413eb442b094515',
      'archive_bytes':326451,'package':'validation_receipt','examples':'examples/validation-evidence','docs_prefix':'RECEIPT-LAB-'},
}


def environment():
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONOPTIMIZE='0')
    for key in ('PYTHONPATH','PYTHONHOME','SPLIT_REVIEW_ROOT'):
        env.pop(key,None)
    return env


def lab_mapping(spec,manifest):
    mapping={}
    for name in manifest['files']:
        if name.startswith(spec['package']+'/'):mapping[name]=name
        elif name.startswith('examples/') and name.endswith('.json'):
            mapping[spec['examples']+'/'+name.split('/',1)[1]]=name
        elif name.startswith('docs/') and name.endswith('.md'):
            mapping['docs/'+spec['docs_prefix']+name.split('/',1)[1]]=name
    if spec['package']=='validation_receipt':mapping['schemas/validation-evidence-request.schema.json']='schema/input.schema.json'
    return mapping


def lab_inputs(root):
    values={}
    for label,spec in LABS.items():
        raw=read(root,spec['manifest']);require(s.digest(raw)==spec['manifest_sha256'],'lab manifest pin: '+label)
        manifest=s.decode(raw,'lab manifest');mapping=lab_mapping(spec,manifest)
        for new,old in mapping.items():
            row=manifest['files'][old];data=read(root,new)
            require(s.digest(data)==row['sha256'] and len(data)==row['bytes'],'accepted lab source drift: '+new)
        raw=read(root,spec['archive']);require(s.digest(raw)==spec['archive_sha256'] and len(raw)==spec['archive_bytes'],'lab archive pin: '+label)
        values[label]={'manifest_sha256':spec['manifest_sha256'],'archive_sha256':spec['archive_sha256'],
                       'source_pins':{new:manifest['files'][old] for new,old in mapping.items()}}
    return values


def pins(root):
    raw=read(root,'EXTERIOR-EVIDENCE-PINS.json');value=s.decode(raw,'v014 pins')
    s.exact_keys(value,('schema','baseline_manifest_sha256','baseline_archive_sha256','baseline_archive_bytes','recipe_sha256','labs'),'v014 pins')
    require(raw==s.canonical(value),'noncanonical pins')
    require(value['schema']=='foundation-math-v014-exterior-evidence-pins-v1','pin schema')
    require((value['baseline_manifest_sha256'],value['baseline_archive_sha256'],value['baseline_archive_bytes'])==
            (BASE_MANIFEST_PIN,BASE_ZIP_PIN,BASE_ZIP_BYTES),'baseline pins')
    require(value['recipe_sha256']==RECIPE_PIN,'recipe pin')
    require(value['labs']==lab_inputs(root),'lab source mapping')
    recipe=s.validate_recipe(read(root,SNAPSHOT+'/recipe.json',s.LIMITS['recipe_bytes']),RECIPE_PIN,BASE_MANIFEST_PIN,BASE_ZIP_PIN)
    raw=read(root,SNAPSHOT+'/baseline-manifest.json',s.LIMITS['manifest_bytes']);baseline=s.source_manifest(raw,BASE_MANIFEST_PIN)
    require({r['path']:r['sha256'] for r in recipe['files']}==baseline,'baseline coverage')
    s.replay_eligibility(recipe,len(read(root,SNAPSHOT+'/recipe.json')),len(raw))
    expected={'recipe.json','baseline-manifest.json'}|{'blobs/'+r['sha256'] for r in recipe['files'] if r['source']=='blob'}
    with source_fd(root) as fd,s.directory(fd,SNAPSHOT) as snap:
        actual,dirs=s.inventory(snap);require(actual==expected and dirs==s.expected_dirs(expected),'snapshot inventory')
    return value,recipe,baseline


def preservation(root):
    value,recipe,baseline=pins(root)
    changed={n for n,pin in baseline.items() if s.digest(read(root,n))!=pin}
    require(changed==ALLOWED_BASE_CHANGES,'unexpected baseline changes: '+str(sorted(changed)))
    donors={r['path'] for r in recipe['files'] if r['source']=='donor'}
    require(donors==set(baseline)-ALLOWED_BASE_CHANGES,'complete donor projection')
    from foundation_math_bridge.schemas import tool_definitions
    old=s.decode(read(root,'docs/BASE-V013-BRIDGE-TOOLS.json'),'old contracts')['tools'];new=tool_definitions()
    require(len(old)==16 and len(new)==19 and new[:16]==old,'sixteen complete prior contracts')
    require([t['name'] for t in new[16:]]==['calculate_formal_exterior','check_formal_exterior_certificate','plan_validation_evidence'],'three appended tools')
    runtime=[n for n in baseline if n.startswith(('foundation_math/','claim_revision/','character_ring/','split_bundle/',
             'exact_linalg/','exact_systems/','bounded_counterexample/','polynomial_witness/','hypothesis_scope/')) and n!='foundation_math/cli.py']
    require(all(s.digest(read(root,n))==baseline[n] for n in runtime),'prior runtime/acceptance drift')
    return {'status':'passed','baseline_selected_files':len(baseline),'unchanged_baseline_files':len(donors),
            'changed_baseline_files':sorted(changed),'prior_complete_contracts_unchanged':16,'runtime_tool_count':19,
            'inherited_runtime_sources_unchanged':len(runtime),'runtime_acceptance_unchanged':True,
            'historical_code_and_archives_unchanged':True}


@contextmanager
def restored_baseline(root):
    value,recipe,baseline=pins(root)
    with tempfile.TemporaryDirectory(prefix='fm-v014-baseline-') as td:
        work=Path(td);(work/'inputs/donor').mkdir(parents=True);(work/'inputs/snapshot').mkdir();(work/'outputs').mkdir()
        names={'recipe.json','baseline-manifest.json'}|{'blobs/'+r['sha256'] for r in recipe['files'] if r['source']=='blob'}
        for name in sorted(names):
            raw=read(root,SNAPSHOT+'/'+name);target=work/'inputs/snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        for row in recipe['files']:
            if row['source']=='donor':
                raw=read(root,row['path'],row['bytes']);require(s.digest(raw)==row['sha256'] and len(raw)==row['bytes'],'donor drift')
                target=work/'inputs/donor'/row['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        with s.Workspace(work) as workspace:
            receipt=s.restore(workspace,'snapshot','donor','baseline',recipe_sha256=RECIPE_PIN,
                              baseline_manifest_sha256=BASE_MANIFEST_PIN,baseline_archive_sha256=BASE_ZIP_PIN)
        yield work/'outputs/baseline/restored',work/'outputs/baseline/baseline.zip',receipt


def unpack_lab(root,label,output):
    spec=LABS[label];raw=read(root,spec['archive']);require(s.digest(raw)==spec['archive_sha256'],'lab archive pin')
    manifest_raw=read(root,spec['manifest']);require(s.digest(manifest_raw)==spec['manifest_sha256'],'lab manifest pin')
    manifest=s.decode(manifest_raw,'lab manifest')['files'];output=Path(output);output.mkdir(exist_ok=False)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        rows=archive.infolist();require([r.filename for r in rows]==sorted([*manifest,'SOURCE-MANIFEST.json']),'lab exact inventory')
        require(len(rows)<=2048 and sum(r.file_size for r in rows)<=s.LIMITS['input_bytes'],'lab extraction limits')
        for row in rows:
            s.name(row.filename);require(row.file_size<=s.LIMITS['file_bytes'] and row.external_attr>>16==0o100644,'lab file type/size')
            data=archive.read(row);pin=spec['manifest_sha256'] if row.filename=='SOURCE-MANIFEST.json' else manifest[row.filename]['sha256']
            require(s.digest(data)==pin,'lab source pin');path=output/row.filename;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    return output
