"""Development-only source manifest generation, not a verification verdict.

Generated evidence is not shipped source. Historical evidence is neither needed
nor implicitly validated. The portable aggregate regenerates its required logs
from the source/fixtures named here, and verifies rather than rewrites this file.
"""
from hashlib import sha256
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    files={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.rglob('*'))
           if p.is_file() and '__pycache__' not in p.parts and 'evidence' not in p.relative_to(ROOT).parts
           and p.name!='SOURCE-MANIFEST.json'}
    manifest={'version':'0.8.0-dev','release_variant':'portable-explicit-linear-systems',
        'base_manifest_sha256':'608d5703b313d0a2f8edf08b8dab40607ce61baf5921af44a0b8098062991214',
        'linear_systems_lab_manifest_sha256':'1159de46ea66a4b2564a906c81ab43744e316e0e58ec7ae33ebeb069575d226b',
        'files':files,'scope':'Shipped source, documentation and synthetic fixtures only; generated and historical evidence excluded.'}
    (ROOT/'SOURCE-MANIFEST.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(sha256((ROOT/'SOURCE-MANIFEST.json').read_bytes()).hexdigest())
if __name__=='__main__':main()
