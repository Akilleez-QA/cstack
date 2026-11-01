"""Fixed-script validation launches with forced and verified child optimization mode."""
from hashlib import sha256
from pathlib import Path
import json
import re
import subprocess
import sys
import time
from tools.exterior_evidence_release_support import environment, require


def run(root,script,optimized=False,args=(),timeout=1800,log_dir=None,label=None):
    mode=int(bool(optimized))
    code=('import runpy,sys;from pathlib import Path;root=sys.argv[1];script=sys.argv[2];expected=int(sys.argv[3]);'
          'sys.exit(91) if sys.flags.optimize!=expected else None;'
          'sys.stderr.write("FM_ACTUAL_OPTIMIZATION="+str(sys.flags.optimize)+"\\n");'
          'sys.path[:0]=[str(Path(root,script).parent),root];'
          'sys.argv=[root+"/"+script]+sys.argv[4:];runpy.run_path(sys.argv[0],run_name="__main__")')
    command=[sys.executable,'-I','-B']+(['-O'] if mode else [])+['-c',code,str(root),script,str(mode),*map(str,args)]
    started=time.monotonic()
    p=subprocess.run(command,cwd=root,env=environment(),capture_output=True,text=True,timeout=timeout)
    elapsed=time.monotonic()-started
    marker='FM_ACTUAL_OPTIMIZATION='+str(mode)+'\n'
    require(p.stderr.startswith(marker),'child actual optimization mode not established: '+script)
    p.stderr=p.stderr[len(marker):]
    if log_dir is not None:
        directory=Path(log_dir);directory.mkdir(exist_ok=True);name=label or Path(script).stem
        (directory/(name+'.stdout')).write_text(p.stdout);(directory/(name+'.stderr')).write_text(p.stderr)
        record={'script':script,'arguments':[str(x) for x in args],'requested_optimization':mode,'actual_optimization':mode,
                'returncode':p.returncode,'elapsed_seconds':elapsed,'stdout_sha256':sha256(p.stdout.encode()).hexdigest(),
                'stderr_sha256':sha256(p.stderr.encode()).hexdigest(),'runner_sha256':sha256(Path(sys.executable).read_bytes()).hexdigest(),
                'environment_policy':'PYTHONOPTIMIZE=0; PYTHONDONTWRITEBYTECODE=1; PYTHONPATH/PYTHONHOME/SPLIT_REVIEW_ROOT removed; isolated entry interpreter.',
                'closure_certified':False,'historical_reuse_authorized':False,
                'timing_scope':'Observed elapsed wall time of this synchronous subprocess only; no equivalence or future-time guarantee.'}
        (directory/(name+'.measurement.json')).write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    require(p.returncode==0,script+' failed: '+(p.stdout+p.stderr)[-12000:])
    return p


def tests(root,mode,directory,log_dir=None):
    p=run(root,'tools/v014_test_runner.py',mode,args=(directory,),timeout=600,
          log_dir=log_dir,label=directory+'-'+str(int(mode)))
    result=json.loads(p.stdout)
    require(result['actual_optimization']==int(bool(mode)) and result['status']=='passed','test mode/status')
    return result
