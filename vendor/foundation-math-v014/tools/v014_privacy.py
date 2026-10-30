"""Bounded textual scan with one exact immutable technical-provenance exception."""
import io
import zipfile
from baseline_snapshot import snapshot as s
from tools.exterior_evidence_release_support import require

PROVENANCE_MEMBER='vendor/validation-receipt-lab.zip!reference/PROVENANCE.json'
PROVENANCE_PIN='92a0c8b93142259e399f8600970744e19a19784f3c707e5acda443985a493e3a'


def privacy(root,manifest):
    markers=('/workspace/','/home/','file://','codex://','ghp_','sk-proj-','BEGIN PRIVATE KEY','BEGIN RSA PRIVATE KEY')
    findings=[];exceptions=[];counts={'text_files':0,'archive_files':0}
    def scan(name,raw,depth=0):
        require(depth<=8,'nested archive depth')
        if name.endswith('.zip'):
            counts['archive_files']+=1
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                require(len(archive.infolist())<=4096,'archive inventory cap')
                require(sum(i.file_size for i in archive.infolist())<=64*1024*1024,'archive uncompressed cap')
                for info in archive.infolist():
                    if not info.is_dir():scan(name+'!'+info.filename,archive.read(info),depth+1)
        elif name.endswith(('.md','.json','.jsonl','.txt')):
            counts['text_files']+=1;text=raw.decode('utf-8')
            for marker in markers:
                if marker not in text:continue
                if (name==PROVENANCE_MEMBER and marker=='/workspace/' and s.digest(raw)==PROVENANCE_PIN
                        and text.count(marker)==10):
                    exceptions.append({'member':name,'sha256':PROVENANCE_PIN,'technical_source_path_count':10,
                        'reason':'Exact immutable accepted-lab design provenance only; no personal data or credential content. Not a blanket path exemption.'})
                else:findings.append({'file':name,'marker':marker})
    for name in sorted([*manifest['files'],'SOURCE-MANIFEST.json']):scan(name,(root/name).read_bytes())
    require(not findings,'privacy/portability findings: '+str(findings))
    return {'status':'passed_with_exact_reviewed_provenance_exception','findings':findings,**counts,
            'reviewed_provenance_exceptions':exceptions,
            'scope':'Bounded selected textual-source and nested-history scan. The single exact technical provenance exception is reported; no universal secret-detection claim.'}
