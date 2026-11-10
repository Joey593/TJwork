"""CI 独立执行经人工维护的固定脚本，不自动审核平台 AI 候选。"""
import json, os, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.templates import scenario
job=ROOT/'qa'/'ci-smoke';job.mkdir(parents=True,exist_ok=True)
items=[]
for kind in ['login','register','search','form']:
    for variant in [0,1]:
        items.append({'ordinal':len(items)+1,'case_id':kind+str(variant),'version':1,'body':scenario(kind,'CI-'+kind.upper(),variant)})
spec={'base_url':os.getenv('DEMO_BASE_URL','http://127.0.0.1:8000'),'browser':os.getenv('TEST_BROWSER','chromium'),'items':items}
(job/'spec.json').write_text(json.dumps(spec,ensure_ascii=False));env=os.environ.copy();env['AURORA_JOB']=str(job)
raise SystemExit(subprocess.call([sys.executable,'-m','pytest','runner/test_scenarios.py','-q','--junitxml='+str(job/'junit.xml')],cwd=ROOT/'backend',env=env))
