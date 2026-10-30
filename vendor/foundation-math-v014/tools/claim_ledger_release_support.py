"""Pinned local frozen inputs. Hashes bind bytes, not authenticity or truth."""
from hashlib import sha256
import json
import os
from pathlib import PurePosixPath
import zipfile

BASE_MANIFEST_PIN = '7626cbaadd8b8bd70d1b8ebaea4c2e638c478c63bddbb6c7ade3a2e485b3695f'
BASE_ZIP_PIN = '6151f3f6ef3a27c082a00dc5fb91f1a8487a91869fb4c6dc1ecdd3af2bdedf4f'
LAB_MANIFEST_PIN = '37101f16966c8427ac639e3328d98aca10cc5a3b17783748a56e808fb12a9c22'
LAB_ZIP_PIN = 'c3805e92aa2b3259e310c126fac751f4bf34646f17f3442cfd63b44386d93fa9'
LAB_CORE_PIN = 'c6c1f2ef00a64d514a781f281c7318612d644dc6b872690f6de7f16577552294'
REVIEW_ZIP_PIN = '5e1beabbadd0b85477c167f90f4dd4bb76549a9f6ed1a3a9f0ea2fa2fe78ed5d'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def environment():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for key in ('PYTHONPATH', 'PYTHONHOME', 'SPLIT_REVIEW_ROOT'):
        env.pop(key, None)
    return env


def safe_name(name):
    require(type(name) is str and name and '\\' not in name, 'invalid archive name')
    path = PurePosixPath(name)
    require(not path.is_absolute() and all(p not in ('', '.', '..') for p in name.split('/')), 'unsafe archive path')
    return name


def unpack_base(root, destination):
    archive = root / 'vendor/foundation-math-v010-source.zip'
    require(digest(archive) == BASE_ZIP_PIN, 'frozen v0.10 archive drift')
    with zipfile.ZipFile(archive) as z:
        raw = z.read('SOURCE-MANIFEST.json')
        require(sha256(raw).hexdigest() == BASE_MANIFEST_PIN, 'frozen v0.10 manifest drift')
        files = json.loads(raw)['files']
        names = sorted([*files, 'SOURCE-MANIFEST.json'])
        require(z.namelist() == names, 'frozen v0.10 exact archive inventory')
        for name in names:
            safe_name(name)
            raw = z.read(name)
            if name in files:
                require(sha256(raw).hexdigest() == files[name], 'base source drift: ' + name)
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
    return files


def check_lab_sources(root):
    require(digest(root / 'vendor/claim-revision-lab.zip') == LAB_ZIP_PIN, 'accepted lab archive drift')
    require(digest(root / 'vendor/claim-revision-review.zip') == REVIEW_ZIP_PIN, 'accepted review archive drift')
    require(digest(root / 'docs/CLAIM-REVISION-LAB-SOURCE-MANIFEST.json') == LAB_MANIFEST_PIN, 'lab manifest drift')
    require(digest(root / 'claim_revision/core.py') == LAB_CORE_PIN, 'corrected core drift')
    with zipfile.ZipFile(root / 'vendor/claim-revision-lab.zip') as z:
        raw = z.read('SOURCE-MANIFEST.json')
        require(sha256(raw).hexdigest() == LAB_MANIFEST_PIN, 'embedded lab manifest drift')
        rows = json.loads(raw)['files']
        require(set(z.namelist()) == {'SOURCE-MANIFEST.json', *[x['path'] for x in rows]} and len(z.namelist()) == len(rows) + 1, 'lab exact inventory')
        for row in rows:
            safe_name(row['path']);raw = z.read(row['path'])
            require(len(raw) == row['bytes'] and sha256(raw).hexdigest() == row['sha256'], 'lab source mismatch')
            if row['path'].startswith('claim_revision/'):
                require((root / row['path']).read_bytes() == raw, 'vendored core differs')
    with zipfile.ZipFile(root / 'vendor/claim-revision-review.zip') as z:
        # The pinned archive is review history; only these source scripts execute.
        for name in ('oracle.py', 'review.py', 'reproduce_review.py'):
            require((root / 'review/claim-revision-lab' / name).read_bytes() == z.read(name), 'independent lab review script drift: ' + name)
    return {'status': 'passed', 'lab_source_files': len(rows), 'core_sha256': LAB_CORE_PIN,
            'pure_module_files_unchanged': 3, 'independent_reviewer_source_files_unchanged': 3}
