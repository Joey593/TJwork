import csv, html, io, json, os, re, threading, time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, update, func
from sqlalchemy.exc import IntegrityError
from . import ai
from .auth import current_user, writer, reviewer, admin, hash_password, verify_password, token
from .config import ARTIFACTS, ROOT
from .db import Base, engine, Session, User, Project, Requirement, Generation, Case, Revision, Run, Result, Audit, Experiment, serialize, now
from .schemas import Login, UserIn, ProjectIn, RequirementIn, CaseIn, CaseEdit, ReviewIn, GenerateIn, RunIn, AnalyzeIn, ExperimentIn, CaseBody
from .seed import seed
from .worker import Dispatcher

dispatcher=Dispatcher()
@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    if os.getenv('SEED_DEMO','1')=='1': seed()
    if os.getenv('DISABLE_WORKER')!='1': dispatcher.start()
    yield
    if os.getenv('DISABLE_WORKER')!='1': dispatcher.close()

app=FastAPI(title='Aurora Test · 智能自动化测试平台',version='1.0.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CORS_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(','),allow_methods=['GET','POST','PUT'],allow_headers=['Authorization','Content-Type'])

def session():
    with Session() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback();raise

def require(db,model,id):
    obj=db.get(model,id)
    if not obj: raise HTTPException(404,'记录不存在')
    return obj

def audit(db,user,action,id,detail=None): db.add(Audit(actor_id=user.id,action=action,entity_id=id,detail=detail or {}))
def point_check(req,body):
    if not set(body.requirement_points)<={p['id'] for p in req.points}: raise HTTPException(422,'用例关联了不属于该需求的需求点')

def row_list(db,model,project_id=None):
    query=select(model)
    if project_id is not None: query=query.where(model.project_id==project_id)
    return [serialize(x) for x in db.scalars(query.order_by(model.created_at.desc()).limit(500))]

@app.get('/api/health')
def health(): return {'status':'ok','version':'1.0.0'}

# 登录限速只保存失败次数，不记录密码或访问令牌。
_login_attempts={};_login_lock=threading.Lock()
@app.post('/api/auth/login')
def login(body:Login,request:Request,db=Depends(session, scope='function')):
    key=(request.client.host if request.client else '',body.username)
    with _login_lock:
        recent=[t for t in _login_attempts.get(key,[]) if time.monotonic()-t<60]
        if len(recent)>=10: raise HTTPException(429,'登录尝试过多，请稍后重试')
    user=db.scalar(select(User).where(User.username==body.username))
    if not user or not verify_password(body.password,user.password_hash):
        with _login_lock: _login_attempts[key]=recent+[time.monotonic()]
        raise HTTPException(401,'用户名或密码错误')
    with _login_lock: _login_attempts.pop(key,None)
    return {'access_token':token(user),'token_type':'bearer','user':{'id':user.id,'username':user.username,'role':user.role}}
@app.get('/api/auth/me')
def me(user=Depends(current_user)): return {'id':user.id,'username':user.username,'role':user.role}
@app.get('/api/users')
def users(user=Depends(admin),db=Depends(session, scope='function')):
    return [{'id':x.id,'username':x.username,'role':x.role,'created_at':x.created_at} for x in db.scalars(select(User))]
@app.post('/api/users',status_code=201)
def create_user(body:UserIn,user=Depends(admin),db=Depends(session, scope='function')):
    if db.scalar(select(User).where(User.username==body.username)): raise HTTPException(409,'用户名已存在')
    x=User(username=body.username,password_hash=hash_password(body.password),role=body.role);db.add(x);db.flush();audit(db,user,'user.created',x.id)
    return {'id':x.id,'username':x.username,'role':x.role}
@app.get('/api/config')
def config(user=Depends(current_user)):
    return {'llm_configured':bool(os.getenv('LLM_API_KEY')),'llm_model':os.getenv('LLM_MODEL','gpt-4o-mini'),'database':'mysql' if engine.dialect.name=='mysql' else 'sqlite','browsers':['chromium','firefox','webkit'],'prompt_version':ai.PROMPT_VERSION}
@app.get('/api/projects')
def projects(user=Depends(current_user),db=Depends(session, scope='function')): return row_list(db,Project)
@app.post('/api/projects',status_code=201)
def create_project(body:ProjectIn,user=Depends(writer),db=Depends(session, scope='function')):
    p=Project(**body.model_dump(),owner_id=user.id);db.add(p);db.flush();audit(db,user,'project.created',p.id);return serialize(p)
@app.put('/api/projects/{id}')
def edit_project(id:str,body:ProjectIn,user=Depends(writer),db=Depends(session, scope='function')):
    p=require(db,Project,id)
    for k,v in body.model_dump().items(): setattr(p,k,v)
    audit(db,user,'project.updated',p.id);return serialize(p)
@app.get('/api/requirements')
def requirements(project_id:str,user=Depends(current_user),db=Depends(session, scope='function')): return row_list(db,Requirement,project_id)
@app.post('/api/requirements',status_code=201)
def create_requirement(body:RequirementIn,user=Depends(writer),db=Depends(session, scope='function')):
    require(db,Project,body.project_id);r=Requirement(**body.model_dump());db.add(r);db.flush();audit(db,user,'requirement.created',r.id);return serialize(r)
@app.get('/api/cases')
def cases(project_id:str,status:str|None=None,user=Depends(current_user),db=Depends(session, scope='function')):
    q=select(Case).where(Case.project_id==project_id)
    if status: q=q.where(Case.status==status)
    return [serialize(c) for c in db.scalars(q.order_by(Case.created_at.desc()).limit(1000))]
@app.post('/api/cases',status_code=201)
def create_case(body:CaseIn,user=Depends(writer),db=Depends(session, scope='function')):
    req=require(db,Requirement,body.requirement_id)
    if req.project_id!=body.project_id: raise HTTPException(422,'需求与项目不匹配')
    point_check(req,body.body)
    c=Case(project_id=body.project_id,requirement_id=body.requirement_id,body=body.body.model_dump(),status='pending',version=1);db.add(c);db.flush()
    db.add(Revision(case_id=c.id,actor_id=user.id,version=1,action='created',body=c.body,note='人工录入'))
    audit(db,user,'case.created',c.id);return serialize(c)
@app.put('/api/cases/{id}')
def edit_case(id:str,body:CaseEdit,user=Depends(writer),db=Depends(session, scope='function')):
    c=require(db,Case,id);point_check(require(db,Requirement,c.requirement_id),body.body)
    changed=db.execute(update(Case).where(Case.id==id,Case.version==body.version).values(body=body.body.model_dump(),version=body.version+1,status='pending'))
    if changed.rowcount!=1: raise HTTPException(409,'用例已被修改，请刷新后重试')
    db.add(Revision(case_id=id,actor_id=user.id,version=body.version+1,action='edited',body=body.body.model_dump(),note=body.note))
    audit(db,user,'case.edited',id,{'version':body.version+1});db.flush();db.refresh(c);return serialize(c)
@app.post('/api/cases/{id}/review')
def review_case(id:str,body:ReviewIn,user=Depends(reviewer),db=Depends(session, scope='function')):
    c=require(db,Case,id)
    if c.status!='pending': raise HTTPException(409,'只有待审核用例可审核')
    validated=CaseBody.model_validate(c.body);point_check(require(db,Requirement,c.requirement_id),validated)
    changed=db.execute(update(Case).where(Case.id==id,Case.version==body.version,Case.status=='pending').values(status=body.decision,version=body.version+1))
    if changed.rowcount!=1: raise HTTPException(409,'版本发生变化，请刷新后重新审核')
    db.add(Revision(case_id=id,actor_id=user.id,version=body.version+1,action=body.decision,body=c.body,note=body.note))
    audit(db,user,'case.'+body.decision,id,{'version':body.version+1,'note':body.note});db.flush();db.refresh(c);return serialize(c)
@app.get('/api/cases/{id}/history')
def history(id:str,user=Depends(current_user),db=Depends(session, scope='function')):
    require(db,Case,id);return [serialize(x) for x in db.scalars(select(Revision).where(Revision.case_id==id).order_by(Revision.version.desc()))]
@app.post('/api/generations',status_code=201)
def generation(body:GenerateIn,user=Depends(writer),db=Depends(session, scope='function')):
    req=require(db,Requirement,body.requirement_id)
    try: response=ai.generate(req,body.method,body.count)
    except (ValueError,KeyError,json.JSONDecodeError) as exc: raise HTTPException(422,str(exc))
    except Exception as exc:
        # 不把供应商响应头或密钥暴露给客户端。
        raise HTTPException(502,'大模型服务调用失败，请检查服务端配置、网络或额度') from exc
    accepted=response.pop('cases')
    g=Generation(project_id=req.project_id,requirement_id=req.id,**response);db.add(g);db.flush()
    existing={ai.fingerprint(c.body) for c in db.scalars(select(Case).where(Case.requirement_id==req.id))}
    created=[];cross_duplicates=0
    for candidate in accepted:
        fp=ai.fingerprint(candidate)
        if fp in existing: cross_duplicates+=1;continue
        existing.add(fp)
        c=Case(project_id=req.project_id,requirement_id=req.id,generation_id=g.id,body=candidate,status='pending',version=1);db.add(c);db.flush();created.append(serialize(c))
        db.add(Revision(case_id=c.id,actor_id=user.id,version=1,action='generated',body=c.body,note='待人工审核'))
    g.payload={**g.payload,'cross_duplicates':cross_duplicates,'created_count':len(created)}
    audit(db,user,'generation.completed',g.id,{'method':body.method,'created':len(created)})
    return {'generation':serialize(g),'cases':created}
@app.get('/api/generations')
def generations(project_id:str,user=Depends(current_user),db=Depends(session, scope='function')): return row_list(db,Generation,project_id)
@app.post('/api/runs',status_code=202)
def create_run(body:RunIn,user=Depends(writer),db=Depends(session, scope='function')):
    p=require(db,Project,body.project_id)
    selected=list(db.scalars(select(Case).where(Case.id.in_(body.case_ids))))
    if len(selected)!=len(body.case_ids) or any(c.project_id!=p.id or c.status!='approved' for c in selected): raise HTTPException(422,'只能执行当前项目已审核通过的用例')
    mapping={c.id:c for c in selected};items=[]
    for repetition in range(body.repeat):
        for id in body.case_ids:
            c=mapping[id];CaseBody.model_validate(c.body)
            items.append({'ordinal':len(items)+1,'case_id':c.id,'version':c.version,'body':c.body,'repetition':repetition+1})
    run=Run(project_id=p.id,actor_id=user.id,name=body.name,browser=body.browser,repeat=body.repeat,status='queued',snapshot={'base_url':p.base_url,'items':items},summary={'total':len(items),'completed':0,'passed':0,'failed':0,'skipped':0})
    db.add(run);db.flush();audit(db,user,'run.created',run.id,{'count':len(items)})
    return serialize(run)
@app.get('/api/runs')
def runs(project_id:str,user=Depends(current_user),db=Depends(session, scope='function')): return row_list(db,Run,project_id)
@app.get('/api/runs/{id}')
def run_detail(id:str,user=Depends(current_user),db=Depends(session, scope='function')):
    r=require(db,Run,id);return {**serialize(r),'results':[serialize(x) for x in db.scalars(select(Result).where(Result.run_id==id).order_by(Result.ordinal))]}
@app.post('/api/runs/{id}/cancel')
def cancel_run(id:str,user=Depends(writer),db=Depends(session, scope='function')):
    r=require(db,Run,id)
    queued=db.execute(update(Run).where(Run.id==id,Run.status=='queued').values(status='cancelled',finished_at=now()))
    if queued.rowcount!=1:
        running=db.execute(update(Run).where(Run.id==id,Run.status=='running').values(status='cancelling'))
        if running.rowcount!=1: raise HTTPException(409,'任务已结束或正在取消')
    db.refresh(r)
    audit(db,user,'run.cancelled',id);return serialize(r)
@app.post('/api/results/{id}/analysis')
def analyze_result(id:str,body:AnalyzeIn,user=Depends(writer),db=Depends(session, scope='function')):
    r=require(db,Result,id)
    if r.status!='failed': raise HTTPException(422,'仅可分析失败用例')
    try: r.analysis=ai.analyze(r.evidence,body.method)
    except ValueError as exc: raise HTTPException(422,str(exc))
    except Exception as exc: raise HTTPException(502,'模型分析失败，请检查配置或稍后重试') from exc
    audit(db,user,'result.analyzed',id,{'method':body.method});return r.analysis
@app.get('/api/runs/{id}/artifacts/{filename}')
def artifact(id:str,filename:str,user=Depends(current_user),db=Depends(session, scope='function')):
    require(db,Run,id)
    if not re.fullmatch(r'(\d{4}\.(png|trace\.zip)|pytest\.log|junit\.xml)',filename): raise HTTPException(404,'文件不存在')
    file=ARTIFACTS/id/filename
    if not file.is_file(): raise HTTPException(404,'该证据不可用，请查看用例错误记录')
    return FileResponse(file,filename=filename)
@app.get('/api/dashboard')
def dashboard(project_id:str,user=Depends(current_user),db=Depends(session, scope='function')):
    require(db,Project,project_id)
    cs=list(db.scalars(select(Case).where(Case.project_id==project_id)))
    rs=list(db.scalars(select(Run).where(Run.project_id==project_id).order_by(Run.created_at.desc())))
    reqs=list(db.scalars(select(Requirement).where(Requirement.project_id==project_id)))
    total_points={(r.id,p['id']) for r in reqs for p in r.points}
    covered={(c.requirement_id,p) for c in cs if c.status=='approved' for p in c.body['requirement_points']}
    results=list(db.scalars(select(Result).join(Run,Result.run_id==Run.id).where(Run.project_id==project_id)))
    passed=sum(x.status=='passed' for x in results);failed=sum(x.status=='failed' for x in results)
    return {'cases':len(cs),'approved':sum(c.status=='approved' for c in cs),'pending':sum(c.status=='pending' for c in cs),'runs':len(rs),'passed':passed,'failed':failed,'executed':len(results),'pass_rate':round(passed/(passed+failed)*100,1) if passed+failed else None,'coverage':round(len(covered&total_points)/len(total_points)*100,1) if total_points else 0,'requirement_points':len(total_points),'covered_points':len(covered&total_points),'trend':[{'name':r.name,'created_at':r.created_at,'status':r.status,**r.summary} for r in reversed(rs[:10])],'recent_runs':[serialize(r) for r in rs[:5]]}
@app.get('/api/traceability')
def traceability(project_id:str,user=Depends(current_user),db=Depends(session, scope='function')):
    reqs=list(db.scalars(select(Requirement).where(Requirement.project_id==project_id)))
    cs=list(db.scalars(select(Case).where(Case.project_id==project_id)))
    results=list(db.scalars(select(Result).join(Run,Result.run_id==Run.id).where(Run.project_id==project_id).order_by(Result.created_at.desc())))
    rows=[]
    for req in reqs:
        for point in req.points:
            related=[c for c in cs if c.requirement_id==req.id and point['id'] in c.body['requirement_points']]
            related_ids={c.id for c in related};last=next((r for r in results if r.case_id in related_ids),None)
            rows.append({'requirement_id':req.id,'requirement_title':req.title,**point,'cases':[{'id':c.id,'title':c.body['title'],'status':c.status,'version':c.version} for c in related],'last_result':{'id':last.id,'run_id':last.run_id,'status':last.status,'case_version':last.evidence.get('case_version')} if last else None})
    return rows

def metrics(o):
    return {'coverage':o['covered_points']/o['requirement_total'],'validity':o['valid']/o['generated'],'executability':o['executable']/o['valid'] if o['valid'] else None,'duplicate_rate':o['duplicates']/o['generated'],'defect_detection':o['defects_detected']/o['defects_total'] if o['defects_total'] else None,'revision_seconds':o['revision_seconds'],'generation_ms':o['generation_ms']}
@app.get('/api/experiments')
def experiments(project_id:str,user=Depends(current_user),db=Depends(session, scope='function')):
    return [{**x,'metrics':metrics(x['observations'])} for x in row_list(db,Experiment,project_id)]
@app.post('/api/experiments',status_code=201)
def create_experiment(body:ExperimentIn,user=Depends(writer),db=Depends(session, scope='function')):
    require(db,Project,body.project_id);e=Experiment(**body.model_dump());db.add(e);db.flush();audit(db,user,'experiment.created',e.id);return {**serialize(e),'metrics':metrics(e.observations)}
@app.get('/api/experiments/export')
def export_experiments(project_id:str,user=Depends(current_user),db=Depends(session, scope='function')):
    rows=row_list(db,Experiment,project_id)
    stream=io.StringIO();w=csv.writer(stream);w.writerow(['id','name','method','created_at','observations','metrics'])
    for x in rows: w.writerow([x['id'],x['name'],x['method'],x['created_at'],json.dumps(x['observations'],ensure_ascii=False),json.dumps(metrics(x['observations']))])
    return Response('\ufeff'+stream.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="experiments.csv"'})
@app.get('/api/runs/{id}/report')
def report(id:str,format:str='html',user=Depends(current_user),db=Depends(session, scope='function')):
    run=require(db,Run,id);results=list(db.scalars(select(Result).where(Result.run_id==id).order_by(Result.ordinal)))
    data={**serialize(run),'results':[serialize(r) for r in results]}
    if format=='json': return data
    if format=='csv':
        stream=io.StringIO();w=csv.writer(stream);w.writerow(['ordinal','case_id','title','version','status','duration_ms','error'])
        for r in results: w.writerow([r.ordinal,r.case_id,r.evidence.get('title'),r.evidence.get('case_version'),r.status,r.duration_ms,r.evidence.get('error')])
        return Response('\ufeff'+stream.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="run-{id}.csv"'})
    if format!='html': raise HTTPException(422,'format 仅支持 html/json/csv')
    esc=lambda v:html.escape(str(v))
    cards=''.join(f'<section><h3>{r.ordinal}. {esc(r.evidence.get("title"))} · {r.status}</h3><p>用例 {r.case_id} / v{r.evidence.get("case_version")} · {r.duration_ms} ms</p><pre>{esc(r.evidence.get("error", ""))}</pre><p>截图：{esc(r.evidence.get("screenshot","不可用"))} · Trace：{esc(r.evidence.get("trace","不可用"))}</p><pre>{esc(json.dumps(r.analysis,ensure_ascii=False,indent=2)) if r.analysis else ""}</pre></section>' for r in results)
    markup=f'<!doctype html><meta charset="utf-8"><title>{esc(run.name)} · 测试报告</title><style>body{{font:15px system-ui;max-width:1000px;margin:40px auto;color:#243147;background:#f6f8fc}}section{{background:white;border:1px solid #ddd;border-radius:12px;padding:20px;margin:16px 0}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}}h1{{color:#5148e5}}</style><h1>Aurora Test · 测试报告</h1><h2>{esc(run.name)}</h2><p>{esc(run.status)} · {esc(run.created_at)} · {esc(run.browser)}</p><p>{esc(json.dumps(run.summary,ensure_ascii=False))}</p><p>以下是运行时的不可变用例版本。完整截图、Trace、JUnit 和日志请在平台任务详情下载。</p>{cards}'
    return HTMLResponse(markup,headers={'Content-Disposition':f'attachment; filename="run-{id}.html"'})
@app.get('/api/audit')
def audit_logs(user=Depends(admin),db=Depends(session, scope='function')):
    return [serialize(x) for x in db.scalars(select(Audit).order_by(Audit.created_at.desc()).limit(200))]
@app.get('/demo/')
def demo(): return FileResponse(Path(__file__).with_name('demo.html'),media_type='text/html')

# 生产前端静态文件，与 API 同源部署；开发时使用 Vite proxy。
@app.get('/{path:path}',include_in_schema=False)
def frontend(path:str):
    dist=ROOT/'frontend'/'dist'
    candidate=(dist/path).resolve()
    if candidate.is_relative_to(dist.resolve()) and candidate.is_file(): return FileResponse(candidate)
    if path.startswith('api/'): raise HTTPException(404,'接口不存在')
    if (dist/'index.html').exists(): return FileResponse(dist/'index.html')
    return HTMLResponse('<h1>Aurora Test API 已启动</h1><p>前端构建后在此访问，API 文档：<a href="/docs">/docs</a></p>')
