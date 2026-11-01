"""Pinned manifest-only candidate replay and independent review in fresh dirs."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import zipfile

EXPECTED_ARCHIVE = 'c3805e92aa2b3259e310c126fac751f4bf34646f17f3442cfd63b44386d93fa9'
EXPECTED_MANIFEST = '37101f16966c8427ac639e3328d98aca10cc5a3b17783748a56e808fb12a9c22'
EXPECTED_CORE = 'c6c1f2ef00a64d514a781f281c7318612d644dc6b872690f6de7f16577552294'


def require(condition, explanation):
    if not condition:
        raise ValueError(explanation)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main(archive_path):
    archive_path = Path(archive_path)
    require(archive_path.stat().st_size <= 4194304, 'Archive byte limit')
    archive_bytes = archive_path.read_bytes()
    require(sha(archive_bytes) == EXPECTED_ARCHIVE, 'Archive is not the reviewed frozen pin')
    own = Path(__file__).resolve().parent
    scripts = {name: (own / name).read_bytes() for name in ['oracle.py', 'review.py']}
    with zipfile.ZipFile(archive_path) as archive, tempfile.TemporaryDirectory(prefix='independent-ledger-review-') as temp:
        infos = archive.infolist()
        names = [x.filename for x in infos]
        require(len(names) == len(set(names)) and len(names) <= 129, 'Unique archive member bound')
        require(sum(x.file_size for x in infos) <= 4194304, 'Expanded archive byte limit')
        for info in infos:
            name = info.filename
            require(not PurePosixPath(name).is_absolute() and '\\' not in name and all(part not in ('', '.', '..') for part in name.split('/')), 'Unsafe archive path')
            require(info.compress_type == zipfile.ZIP_STORED and not info.flag_bits & 1, 'Archive compression or encryption not allowed')
        manifest_raw = archive.read('SOURCE-MANIFEST.json')
        require(sha(manifest_raw) == EXPECTED_MANIFEST, 'Manifest is not reviewed frozen pin')
        manifest = json.loads(manifest_raw)
        listed = [r['path'] for r in manifest['files']]
        require(set(names) == {'SOURCE-MANIFEST.json', *listed} and len(listed) == len(set(listed)), 'Not manifest-only archive')
        require(sorted(listed) == json.loads(archive.read('RELEASE-FILES.json')), 'Release allowlist differs from manifest')
        for row in manifest['files']:
            raw = archive.read(row['path'])
            require(len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'Member pin mismatch: ' + row['path'])
        require(sha(archive.read('claim_revision/core.py')) == EXPECTED_CORE, 'Core is not reviewed frozen pin')
        root = Path(temp)
        candidate = root / 'candidate'
        reviewer = root / 'reviewer'
        reviewer.mkdir()
        for name in names:
            target = candidate / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
        for name, raw in scripts.items():
            (reviewer / name).write_bytes(raw)
        env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME')}
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        outputs = {}
        commands = [('author_aggregate', [sys.executable, '-B', 'tools/validate.py'])]
        for name, mode in [('independent_normal', []), ('independent_optimized', ['-O'])]:
            commands.append((name, [sys.executable, '-B', *mode, str(reviewer / 'review.py'), str(candidate)]))
        for name, cmd in commands:
            p = subprocess.run(cmd, cwd=candidate, env=env, capture_output=True, text=True, timeout=240)
            require(p.returncode == 0, name + ' failed:\n' + p.stdout + '\n' + p.stderr)
            outputs[name] = json.loads(p.stdout)
        require(outputs['independent_normal']['counts'] == outputs['independent_optimized']['counts'], 'Normal/optimized case counts differ')
        return {'status': 'pass', 'archive_sha256': EXPECTED_ARCHIVE, 'manifest_sha256': EXPECTED_MANIFEST, 'core_sha256': EXPECTED_CORE,
                'archive_members': len(names), 'manifest_only_extraction': True, 'candidate_external_source_dependencies': [],
                'reviewer_script_sha256': {name: sha(raw) for name, raw in scripts.items()}, 'fresh_results': outputs}


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python -B reproduce_review.py CANDIDATE.zip')
    print(json.dumps(main(sys.argv[1]), sort_keys=True, indent=2))
