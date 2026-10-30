"""Development-only manifest generator, not a validation verdict."""
from hashlib import sha256
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    files={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.rglob('*'))
           if p.is_file() and '__pycache__' not in p.parts and 'evidence' not in p.relative_to(ROOT).parts
           and p != ROOT/'SOURCE-MANIFEST.json'}
    manifest={'version':'0.9.0-dev','release_variant':'portable-fixed-physical-character-ring',
        'base_manifest_sha256':'7c8c781fb33a261045eb3ebddde5805022bc5e55a6ce8521d94c5fcc83efa056',
        'character_ring_lab_manifest_sha256':'fbd2014cd2931db57964142c4af7bba09853a4fa6e191bf8a550fee9f1b2cb37',
        'files':files,'scope':'Shipped source, documentation, universal/synthetic fixtures and authenticated immutable input archives; generated evidence excluded.'}
    (ROOT/'SOURCE-MANIFEST.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(sha256((ROOT/'SOURCE-MANIFEST.json').read_bytes()).hexdigest())
if __name__=='__main__':main()
