"""Fixed local release inputs. No request-controlled paths, installs or network."""
from hashlib import sha256
import json
import os
from pathlib import Path
import zipfile

BASE_MANIFEST_PIN = '7c8c781fb33a261045eb3ebddde5805022bc5e55a6ce8521d94c5fcc83efa056'
BASE_ZIP_PIN = '9df4f74f80e40ab08b5342efd2141fbc5e9321ed1caeb5163ef7cf465fe652ea'
LAB_MANIFEST_PIN = 'fbd2014cd2931db57964142c4af7bba09853a4fa6e191bf8a550fee9f1b2cb37'
LAB_ZIP_PIN = '900e5395d6d683a6a6da0c6e48c31ec9ca17892741ad85512fbdb9c0b4936115'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def environment():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    return env


def unpack_base(root, destination):
    archive = root / 'vendor/foundation-math-v08-source.zip'
    require(digest(archive) == BASE_ZIP_PIN, 'frozen baseline archive changed')
    with zipfile.ZipFile(archive) as z:
        require(sha256(z.read('SOURCE-MANIFEST.json')).hexdigest() == BASE_MANIFEST_PIN, 'baseline manifest pin')
        manifest = json.loads(z.read('SOURCE-MANIFEST.json'))['files']
        require(set(z.namelist()) == set(manifest) | {'SOURCE-MANIFEST.json'}, 'baseline ZIP inventory')
        for name, pin in manifest.items():
            require(sha256(z.read(name)).hexdigest() == pin, 'baseline source: ' + name)
        # All archive paths come from the reviewed pinned archive, not requests.
        z.extractall(destination)
    return manifest


def unpack_lab(root, destination):
    archive = root / 'vendor/character-ring-domain-v01.zip'
    require(digest(archive) == LAB_ZIP_PIN, 'accepted character lab archive changed')
    with zipfile.ZipFile(archive) as z:
        require(sha256(z.read('SOURCE-MANIFEST.json')).hexdigest() == LAB_MANIFEST_PIN, 'lab manifest pin')
        entries = json.loads(z.read('SOURCE-MANIFEST.json'))['files']
        names = ['SOURCE-MANIFEST.json'] + [item['path'] for item in entries]
        names += ['review/review_checks.py', 'review/independent_oracle.py', 'review/standalone_replay.py']
        for item in entries:
            raw = z.read(item['path'])
            require(len(raw) == item['bytes'] and sha256(raw).hexdigest() == item['sha256'], 'lab source: ' + item['path'])
        # Historical evidence and review result files are deliberately NOT extracted.
        for name in names:
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(z.read(name))
    (destination / 'evidence').mkdir(exist_ok=True)
    return entries
