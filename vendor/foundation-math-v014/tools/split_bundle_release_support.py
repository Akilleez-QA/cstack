"""Authenticated local-only frozen sources. No request-controlled paths or network."""
from hashlib import sha256
import json, os, zipfile
from pathlib import Path, PurePosixPath

BASE_MANIFEST_PIN = 'b39a8986aea180d8c24ced0606e1354ea0af53bc5f52ee7b22458e36c0e03c41'
BASE_ZIP_PIN = '748abc044c43c3690f7eb33171a7e84a2a319e9e96934b5a32692d3135354716'
LAB_MANIFEST_PIN = '83d4fd904eb85df128002dee9ba98fca51b5ba5f0e8fbdba67e0db2a9a73ea29'
LAB_SOURCE_PIN = 'e990ec49458fa8bd239b5f6277a5d36feee3c98f0d1ae82a22ee4451b983369c'
LAB_ZIP_PIN = 'bda78ce056e8b5b07ffc7a49e018f6389cbf44f62ea534e779d31151a53d23e3'

def require(ok, message):
    if not ok: raise RuntimeError(message)
def digest(path): return sha256(path.read_bytes()).hexdigest()
def environment():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for k in ('PYTHONPATH', 'PYTHONHOME', 'SPLIT_REVIEW_ROOT'): env.pop(k, None)
    return env
def safe_name(name):
    p=PurePosixPath(name)
    require(type(name) is str and not p.is_absolute() and '..' not in p.parts and str(p)==name and '\\' not in name, 'unsafe archive path')
    return name
def extract(z, names, dest):
    for name in names:
        safe_name(name)
        p=dest/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
def unpack_base(root,destination):
    archive=root/'vendor/foundation-math-v09-source.zip'
    require(digest(archive)==BASE_ZIP_PIN,'frozen v0.9 archive changed')
    with zipfile.ZipFile(archive) as z:
        require(sha256(z.read('SOURCE-MANIFEST.json')).hexdigest()==BASE_MANIFEST_PIN,'v0.9 manifest pin')
        files=json.loads(z.read('SOURCE-MANIFEST.json'))['files']
        require(set(z.namelist())==set(files)|{'SOURCE-MANIFEST.json'},'v0.9 archive inventory')
        require(len(z.namelist())==len(files)+1,'duplicate v0.9 ZIP entries')
        for name,pin in files.items():require(sha256(z.read(name)).hexdigest()==pin,'v0.9 source drift '+name)
        extract(z,sorted(set(files)|{'SOURCE-MANIFEST.json'}),destination)
    return files
def unpack_lab(root,destination):
    archive=root/'vendor/split-bundle-domain-v01.zip'
    require(digest(archive)==LAB_ZIP_PIN,'accepted split-bundle archive changed')
    with zipfile.ZipFile(archive) as z:
        require(sha256(z.read('ARTIFACT-MANIFEST.json')).hexdigest()==LAB_MANIFEST_PIN,'lab artifact manifest pin')
        require(sha256(z.read('SOURCE-MANIFEST.json')).hexdigest()==LAB_SOURCE_PIN,'lab source manifest pin')
        rows=json.loads(z.read('ARTIFACT-MANIFEST.json'))['files']
        require(set(z.namelist())=={x['path'] for x in rows}|{'ARTIFACT-MANIFEST.json'},'lab ZIP inventory')
        require(len(z.namelist())==len(rows)+1,'duplicate lab ZIP entries')
        for row in rows:
            data=z.read(row['path']);require(len(data)==row['bytes'] and sha256(data).hexdigest()==row['sha256'],'lab drift '+row['path'])
        # Extract executable source, fixtures and hash bindings, not historical results.
        selected=[x['path'] for x in rows if not x['path'].startswith(('review/','evidence/'))]
        selected += ['review/review_checks.py','review/independent_oracle.py','review/adversarial_controls.py','review/REVIEWED-SOURCE.json']
        extract(z,selected,destination)
    (destination/'evidence').mkdir(exist_ok=True)
    return rows
