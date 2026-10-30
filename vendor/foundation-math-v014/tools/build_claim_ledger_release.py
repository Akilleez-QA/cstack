"""Selected-only reproducible v0.11 build. Manifest writing is not validation."""
from hashlib import sha256
import argparse,json,zipfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[1]
SELECTION='RELEASE-FILES.json'
MANIFEST='SOURCE-MANIFEST.json'
def require(ok,label):
    if not ok:raise RuntimeError(label)
def digest(path):return sha256(path.read_bytes()).hexdigest()
def names(root):
    selected=json.loads((root/SELECTION).read_text())
    require(selected['schema']=='foundation-math-v011-selected-files-v1','selection schema')
    result=selected['files'];require(result==sorted(set(result)),'noncanonical release selection')
    for name in result:
        require(type(name) is str,'selection name type')
        p=PurePosixPath(name)
        require(not p.is_absolute() and '..' not in p.parts and str(p)==name and '\\' not in name,'unsafe source path')
        require(name!=MANIFEST and not name.startswith('evidence/') and '__pycache__' not in p.parts,'generated source selected')
        require(not name.endswith('.zip') or name.startswith('vendor/'),'output archive selected')
        target=root/name
        require(target.is_file() and not target.is_symlink(),'source must be regular: '+name)
    return result

def freeze(root=ROOT):
    selected=names(root)
    obj={'version':'0.11.0-dev','release_variant':'bounded-claim-revision-applicability',
         'base_manifest_sha256':digest(root/'docs/BASE-V010-SOURCE-MANIFEST.json'),
         'claim_revision_lab_manifest_sha256':digest(root/'docs/CLAIM-REVISION-LAB-SOURCE-MANIFEST.json'),
         'files':{name:digest(root/name) for name in selected},
         'scope':'Selected source, documentation, synthetic formal fixtures and authenticated frozen inputs. Generated evidence excluded; hashes bind bytes, not mathematical truth.'}
    (root/MANIFEST).write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n');return obj

def verify(root=ROOT):
    obj=json.loads((root/MANIFEST).read_text());selected=names(root)
    require(obj['version']=='0.11.0-dev' and list(obj['files'])==selected,'source manifest selection mismatch')
    require(obj['base_manifest_sha256']==digest(root/'docs/BASE-V010-SOURCE-MANIFEST.json'),'base manifest binding')
    require(obj['claim_revision_lab_manifest_sha256']==digest(root/'docs/CLAIM-REVISION-LAB-SOURCE-MANIFEST.json'),'lab manifest binding')
    for name,pin in obj['files'].items():require(digest(root/name)==pin,'source drift: '+name)
    return obj

def create_zip(output,root=ROOT):
    obj=verify(root);selected=sorted(list(obj['files'])+[MANIFEST])
    require(output.resolve() not in {(root/n).resolve() for n in selected},'output collides with selected source')
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in selected:
            info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.create_system=3;info.external_attr=0o100644<<16
            z.writestr(info,(root/name).read_bytes(),compresslevel=9)
    return {'sha256':digest(output),'bytes':output.stat().st_size,'files':len(selected),'source_manifest_sha256':digest(root/MANIFEST)}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--freeze',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.freeze:freeze()
    print(json.dumps(create_zip(a.output),indent=2,sort_keys=True))
if __name__=='__main__':main()
