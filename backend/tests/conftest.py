import os, tempfile
os.environ['DATA_DIR']=tempfile.mkdtemp(prefix='aurora-test-')
os.environ['DATABASE_URL']='sqlite:///'+os.environ['DATA_DIR']+'/test.db'
os.environ['DISABLE_WORKER']='1'
os.environ['ADMIN_PASSWORD']='Admin12345!'
os.environ.pop('LLM_API_KEY',None)
import pytest
from fastapi.testclient import TestClient
from app.main import app
@pytest.fixture(scope='session')
def client():
    with TestClient(app) as client: yield client
@pytest.fixture
def auth(client):
    r=client.post('/api/auth/login',json={'username':'admin','password':'Admin12345!'})
    assert r.status_code==200
    return {'Authorization':'Bearer '+r.json()['access_token']}
@pytest.fixture
def context(client,auth):
    from uuid import uuid4
    p=client.post('/api/projects',headers=auth,json={'name':'测试 '+uuid4().hex[:6],'description':'fixture','base_url':'http://127.0.0.1:8000'}).json()
    req=client.post('/api/requirements',headers=auth,json={'project_id':p['id'],'title':'登录需求','content':'有效账号可登录，错误密码被拒绝','points':[{'id':'REQ-1','text':'有效账号登录'}]}).json()
    from app.templates import scenario
    case=client.post('/api/cases',headers=auth,json={'project_id':p['id'],'requirement_id':req['id'],'body':scenario('login','REQ-1')}).json()
    return p,req,case
