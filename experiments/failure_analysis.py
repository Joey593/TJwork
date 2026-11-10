#!/usr/bin/env python3
import argparse, json, os, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.ai import analyze
p=argparse.ArgumentParser();p.add_argument('--dataset',default='experiments/failure_dataset.json');p.add_argument('--output',default='experiments/results/failure-classification.json');args=p.parse_args()
data=json.loads(Path(args.dataset).read_text());out=[]
for method in ['rules','direct_llm','constrained_llm']:
    if method!='rules' and not os.getenv('LLM_API_KEY'):
        out.append({'method':method,'state':'not_run','reason':'LLM_API_KEY not configured'});continue
    rows=[]
    for item in data:
        try:
            result=analyze({'error':item['error'],'steps':[]},method)
            rows.append({**item,'prediction':result['category'],'analysis':result})
        except Exception as exc: rows.append({**item,'prediction':'provider_error','error_detail':str(exc)})
    labels=['assertion','locator','timeout','infrastructure'];f1=[]
    for label in labels:
        tp=sum(r['label']==label and r['prediction']==label for r in rows)
        fp=sum(r['label']!=label and r['prediction']==label for r in rows)
        fn=sum(r['label']==label and r['prediction']!=label for r in rows)
        f1.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
    out.append({'method':method,'state':'completed','dataset':args.dataset,'note':'默认数据是8条人工标注的机制验证夹具，不能代表生产分类效果','accuracy':sum(r['label']==r['prediction'] for r in rows)/len(rows),'macro_f1':sum(f1)/len(f1),'rows':rows})
output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(out,ensure_ascii=False,indent=2));print(output)
