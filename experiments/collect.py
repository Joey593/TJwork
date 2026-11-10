#!/usr/bin/env python3
"""真实 API/浏览器实验采集。AI 候选不会被此脚本自动批准。"""
import argparse, json, os, time
from datetime import datetime, timezone
from pathlib import Path
import httpx
p=argparse.ArgumentParser()
p.add_argument('--url',default='http://127.0.0.1:8000');p.add_argument('--username',default='admin')
p.add_argument('--suite',choices=['prepare','acceptance','generation'],default='acceptance')
p.add_argument('--output',default='experiments/results');p.add_argument('--requirement-id',default='');args=p.parse_args()
password=os.getenv('AURORA_PASSWORD')
if not password:
    import getpass
    password=getpass.getpass('平台密码: ')
client=httpx.Client(base_url=args.url.rstrip('/'),timeout=100)
def api(method,path,**kw):
    r=client.request(method,'/api'+path,**kw);r.raise_for_status();return r.json()
login=api('POST','/auth/login',json={'username':args.username,'password':password})
client.headers['Authorization']='Bearer '+login['access_token']
projects=api('GET','/projects');project=next((p for p in projects if 'Campus Lab' in p['name']),projects[0]);pid=project['id']
output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
points=[{'id':'ACC-LOGIN','text':'有效账号登录成功，错误密码拒绝'},{'id':'ACC-REGISTER','text':'注册邮箱校验'},{'id':'ACC-SEARCH','text':'按关键词查询课程'},{'id':'ACC-FORM','text':'反馈内容必填校验'}]
content='演示页面 /demo/。student / Study123! 登录成功提示“欢迎回来，student”，错误提示“用户名或密码错误”。有效注册邮箱提示“注册成功”，否则“请输入有效邮箱”。关键词包含 Playwright 返回“Playwright 实战”，其他返回“未找到结果”。反馈非空提示“提交成功”，空值提示“请填写反馈内容”。'
def save(name,data):
    target=output/f'{stamp}-{name}.json';target.write_text(json.dumps(data,ensure_ascii=False,indent=2));print(target);return target
def wait_run(id):
    deadline=time.monotonic()+900
    while time.monotonic()<deadline:
        r=api('GET','/runs/'+id)
        if r['status'] not in ['queued','running','cancelling']: return r
        time.sleep(.5)
    raise TimeoutError('等待超时；任务仍可在平台查询')
def start(name,ids,repeat=1):
    start=time.perf_counter();r=api('POST','/runs',json={'project_id':pid,'name':name,'case_ids':ids,'repeat':repeat});elapsed=(time.perf_counter()-start)*1000
    final=wait_run(r['id']);final['create_api_ms']=elapsed;save(name,final)
    print(name,final['status'],final['summary'],'create_ms',round(elapsed,3));return final
if args.suite=='prepare':
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
    from app.templates import scenario
    req=api('POST','/requirements',json={'project_id':pid,'title':'验收基线 '+stamp,'content':content,'points':points});created=[]
    for i in range(20):
        kind=['login','register','search','form'][i%4];variant=(i//4)%2
        body=scenario(kind,points[i%4]['id'],variant);body['title']=f'验收-{i+1:02d} · '+body['title']
        if kind=='register': value=f'student{i}@example.com' if not variant else f'invalid-{i}';body['test_data']['email']=value;body['script'][1]['value']=value
        elif kind=='search': value=f'Playwright {i}' if not variant else f'不存在课程-{i}';body['test_data']['query']=value;body['script'][1]['value']=value
        elif kind=='form': value=f'反馈样本 {i}' if not variant else ' '*((i//4)+1);body['test_data']['message']=value;body['script'][1]['value']=value
        elif variant: value=f'bad-password-{i}';body['test_data']['password']=value;body['script'][2]['value']=value
        elif i: body['script'][1]['locator']={'by':'test_id','value':'login-username'}
        created.append(api('POST','/cases',json={'project_id':pid,'requirement_id':req['id'],'body':body}))
    for kind,point,variant in [('login',points[0],1),('register',points[1],1),('search',points[2],0),('form',points[3],1)]:
        body=scenario(kind,point['id'],variant);body['title']='缺陷检出-'+kind;body['script'][0]['value']='/demo/?bug='+kind
        created.append(api('POST','/cases',json={'project_id':pid,'requirement_id':req['id'],'body':body}))
    save('prepared',{'requirement_id':req['id'],'cases':created,'review':'pending; explicitly review before execution'})
    print('创建 24 条人工设计候选；请在界面核对并审核。脚本不会自动批准。')
elif args.suite=='acceptance':
    cases=api('GET','/cases',params={'project_id':pid})
    reqs=api('GET','/requirements',params={'project_id':pid})
    req_id=args.requirement_id or next((r['id'] for r in reqs if r['title'].startswith('验收基线 ')),None)
    cases=[c for c in cases if c['requirement_id']==req_id]
    baseline=sorted([c for c in cases if c['status']=='approved' and c['body']['title'].startswith('验收-')],key=lambda c:c['body']['title'])[:20]
    if len(baseline)<20: raise SystemExit('需要20条已审核验收用例。先运行 --suite prepare，再人工审核。')
    batch=start('20条批量验收',[c['id'] for c in baseline]);stable=start('单用例20次稳定性',[baseline[0]['id']],20)
    defects=[c for c in cases if c['status']=='approved' and c['body']['title'].startswith('缺陷检出-')]
    defect=start('四类预置缺陷检出',[c['id'] for c in defects[:4]]) if len(defects)>=4 else None
    evidence=[]
    if defect:
        for r in defect['results']:
            entry={'result_id':r['id'],'status':r['status'],'has_error':bool(r['evidence'].get('error'))}
            for key in ['screenshot','trace']:
                filename=r['evidence'].get(key);response=client.get('/api/runs/'+defect['id']+'/artifacts/'+filename) if filename else None
                entry[key]={'filename':filename,'download_status':response.status_code if response is not None else None,'bytes':len(response.content) if response is not None else 0}
                if response is not None and response.status_code==200: (output/f"{defect['id']}-{filename}").write_bytes(response.content)
            evidence.append(entry)
    report={'timestamp':stamp,'environment':{'backend':args.url,'browser':'chromium','database':api('GET','/config')['database']},'batch':{'distinct_cases':len(baseline),'run_id':batch['id'],'summary':batch['summary'],'status':batch['status'],'create_api_ms':batch['create_api_ms']},'stability':{'run_id':stable['id'],'repeats':20,'summary':stable['summary'],'observed_failure_rate':stable['summary']['failed']/20,'create_api_ms':stable['create_api_ms'],'interpretation':'固定演示环境20次重复；不能证明其他环境的长期稳定性'},'defects':{'run_id':defect['id'],'summary':defect['summary'],'evidence':evidence} if defect else None,'llm_experiment':'not run without configured real model; no effectiveness claims'}
    save('acceptance-summary',report)
    success=batch['status']=='passed' and batch['summary']['completed']==20 and stable['summary']['completed']==20 and stable['summary']['failed']/20<=.05 and max(batch['create_api_ms'],stable['create_api_ms'])<=1000
    if defect: success=success and defect['summary']['failed']==4 and all(e['has_error'] and e['screenshot']['download_status']==200 and e['trace']['download_status']==200 for e in evidence)
    raise SystemExit(0 if success else 1)
else:
    config=api('GET','/config');records=[]
    for method in ['rules','direct_llm','constrained_llm']:
        if method!='rules' and not config['llm_configured']:
            records.append({'method':method,'state':'not_run','reason':'LLM_API_KEY not configured'});continue
        req=api('POST','/requirements',json={'project_id':pid,'title':'生成对照 '+stamp,'content':content,'points':points})
        result=api('POST','/generations',json={'requirement_id':req['id'],'method':method,'count':8})
        records.append({'method':method,'state':'pending_manual_review_and_real_execution','generation':result['generation'],'case_ids':[c['id'] for c in result['cases']]})
    save('generation-comparison',records)
    print('生成采集完成；可执行率、缺陷检出率及修订时间需审核与真实执行后填写。')
