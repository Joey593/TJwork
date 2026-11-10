import json
from uuid import uuid4
from app.schemas import CaseBody, Step
from pydantic import ValidationError
import pytest

def test_auth_and_rbac(client,auth,context):
    assert client.get('/api/projects').status_code==401
    assert client.post('/api/auth/login',json={'username':'admin','password':'wrong'}).status_code==401
    username='viewer_'+uuid4().hex[:6]
    assert client.post('/api/users',headers=auth,json={'username':username,'password':'Viewer12345!','role':'viewer'}).status_code==201
    login=client.post('/api/auth/login',json={'username':username,'password':'Viewer12345!'}).json()
    h={'Authorization':'Bearer '+login['access_token']}
    assert client.get('/api/projects',headers=h).status_code==200
    assert client.post('/api/projects',headers=h,json={'name':'unauthorized','base_url':'http://localhost'}).status_code==403
    _,_,c=context
    assert client.post('/api/cases/'+c['id']+'/review',headers=h,json={'version':1,'decision':'approved','note':'no permission'}).status_code==403
    tester='tester_'+uuid4().hex[:6]
    assert client.post('/api/users',headers=auth,json={'username':tester,'password':'Tester12345!','role':'tester'}).status_code==201
    t=client.post('/api/auth/login',json={'username':tester,'password':'Tester12345!'}).json()['access_token']
    th={'Authorization':'Bearer '+t}
    assert client.post('/api/projects',headers=th,json={'name':'tester allowed','base_url':'http://localhost'}).status_code==201
    assert client.post('/api/cases/'+c['id']+'/review',headers=th,json={'version':1,'decision':'approved','note':'tester cannot approve'}).status_code==403

def test_review_gate_version_and_snapshot(client,auth,context):
    p,req,c=context
    payload={'project_id':p['id'],'case_ids':[c['id']],'name':'test'}
    assert client.post('/api/runs',headers=auth,json=payload).status_code==422
    review=client.post('/api/cases/'+c['id']+'/review',headers=auth,json={'version':1,'decision':'approved','note':'已核对预期和脚本'})
    assert review.status_code==200 and review.json()['version']==2
    r=client.post('/api/runs',headers=auth,json=payload)
    assert r.status_code==202 and r.json()['snapshot']['items'][0]['version']==2
    body={**c['body'],'title':'改动后的新标题'}
    assert client.put('/api/cases/'+c['id'],headers=auth,json={'version':1,'body':body}).status_code==409
    changed=client.put('/api/cases/'+c['id'],headers=auth,json={'version':2,'body':body})
    assert changed.json()['status']=='pending' and changed.json()['version']==3
    old=client.get('/api/runs/'+r.json()['id'],headers=auth).json()
    assert old['snapshot']['items'][0]['body']['title']==c['body']['title']
    assert client.post('/api/runs',headers=auth,json=payload).status_code==422
    history=client.get('/api/cases/'+c['id']+'/history',headers=auth).json()
    assert [x['version'] for x in history]==[3,2,1]

def test_structured_script_validation(client,auth,context):
    p,r,c=context
    bad={**c['body'],'script':[{'action':'exec','value':'print(1)'}]}
    assert client.post('/api/cases',headers=auth,json={'project_id':p['id'],'requirement_id':r['id'],'body':bad}).status_code==422
    with pytest.raises(ValidationError): Step(action='goto',value='//external.example')
    with pytest.raises(ValidationError): Step(action='goto',value='/\\external.example')
    with pytest.raises(ValidationError): CaseBody.model_validate({**c['body'],'script':[{'action':'goto','value':'/demo/'}]})
    bad={**c['body'],'requirement_points':['UNKNOWN']}
    assert client.post('/api/cases',headers=auth,json={'project_id':p['id'],'requirement_id':r['id'],'body':bad}).status_code==422

def test_generation_validation_dedup_provenance(client,auth,context,monkeypatch):
    p,r,c=context
    raw=json.dumps({'cases':[c['body'],{**c['body'],'title':'另一个标题'},{'title':'字段缺失'}]},ensure_ascii=False)
    monkeypatch.setattr('app.ai.completion',lambda _:raw)
    g=client.post('/api/generations',headers=auth,json={'requirement_id':r['id'],'method':'constrained_llm','count':3})
    assert g.status_code==201
    data=g.json();assert data['cases']==[]
    record=data['generation'];assert record['payload']['duplicates']==1 and record['payload']['valid_count']==2
    assert record['payload']['cross_duplicates']==1 and len(record['payload']['errors'])==1
    assert record['payload']['raw_response']==raw and len(record['input_hash'])==64 and record['prompt_version']
    monkeypatch.setattr('app.ai.completion',lambda _:'not json')
    bad=client.post('/api/generations',headers=auth,json={'requirement_id':r['id'],'method':'direct_llm'}).json()
    assert bad['generation']['payload']['errors'] and bad['cases']==[]

def test_model_not_configured_does_not_claim_generation(client,auth,context):
    _,r,_=context
    response=client.post('/api/generations',headers=auth,json={'requirement_id':r['id'],'method':'direct_llm'})
    assert response.status_code==422 and 'LLM_API_KEY' in response.json()['detail']

def test_cross_project_and_batch_limits(client,auth,context):
    p,r,c=context
    other=client.post('/api/projects',headers=auth,json={'name':'另一个项目','base_url':'http://localhost'}).json()
    assert client.post('/api/cases',headers=auth,json={'project_id':other['id'],'requirement_id':r['id'],'body':c['body']}).status_code==422
    assert client.post('/api/runs',headers=auth,json={'project_id':p['id'],'case_ids':[c['id'],c['id']]}).status_code==422
    assert client.post('/api/runs',headers=auth,json={'project_id':p['id'],'case_ids':[str(i) for i in range(11)],'repeat':20}).status_code==422

def test_experiment_denominators(client,auth,context):
    p,_,_=context
    o={'requirement_total':4,'covered_points':2,'generated':4,'valid':2,'executable':1,'duplicates':1,'defects_total':0,'defects_detected':0,'revision_seconds':12.5,'generation_ms':100,'evidence_ref':'fixture-only'}
    r=client.post('/api/experiments',headers=auth,json={'project_id':p['id'],'name':'指标定义验证','method':'rules','observations':o})
    assert r.status_code==201
    assert r.json()['metrics']['coverage']==.5 and r.json()['metrics']['executability']==.5 and r.json()['metrics']['defect_detection'] is None
    o['covered_points']=5
    assert client.post('/api/experiments',headers=auth,json={'project_id':p['id'],'name':'无效','method':'rules','observations':o}).status_code==422

def test_cancel_and_artifact_auth(client,auth,context):
    p,_,c=context
    client.post('/api/cases/'+c['id']+'/review',headers=auth,json={'version':1,'decision':'approved','note':'人工核对'})
    r=client.post('/api/runs',headers=auth,json={'project_id':p['id'],'case_ids':[c['id']]}).json()
    assert client.post('/api/runs/'+r['id']+'/cancel',headers=auth).json()['status']=='cancelled'
    assert client.post('/api/runs/'+r['id']+'/cancel',headers=auth).status_code==409
    assert client.get('/api/runs/'+r['id']+'/artifacts/pytest.log').status_code==401
    assert client.get('/api/runs/'+r['id']+'/artifacts/spec.json',headers=auth).status_code==404
    assert client.get('/api/runs/'+r['id']+'/report?format=html',headers=auth).status_code==200

def test_traceability_reports_and_fail_analysis(client,auth,context):
    from app.db import Session, Result, Run
    p,req,c=context
    client.post('/api/cases/'+c['id']+'/review',headers=auth,json={'version':1,'decision':'approved','note':'通过'})
    run=client.post('/api/runs',headers=auth,json={'project_id':p['id'],'case_ids':[c['id']]}).json()
    with Session.begin() as db:
        result=Result(run_id=run['id'],case_id=c['id'],ordinal=1,status='failed',duration_ms=123,evidence={'error':'AssertionError: Expected text incorrect','title':'<script>alert(1)</script>','case_version':2,'requirement_points':['REQ-1']})
        db.add(result);db.flush();id=result.id
        db.get(Run,run['id']).status='failed'
    analysis=client.post('/api/results/'+id+'/analysis',headers=auth,json={'method':'rules'}).json()
    assert analysis['category']=='assertion' and '候选原因' in analysis['disclaimer']
    matrix=client.get('/api/traceability',headers=auth,params={'project_id':p['id']}).json()
    assert matrix[0]['last_result']['case_version']==2
    report=client.get('/api/runs/'+run['id']+'/report',headers=auth).text
    assert '<script>alert' not in report and '&lt;script&gt;' in report
    assert client.get('/api/runs/'+run['id']+'/report?format=csv',headers=auth).status_code==200
